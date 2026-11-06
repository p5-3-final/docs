---
id: ADR-0016
title: 상태 전이는 aggregator fold 한 곳에서 계산하고, 늦은 이벤트는 revision 재발행, 호출 carry·상한은 결정적 규칙으로 둔다
status: Accepted
date: 2026-11-06
deciders: [사용자]
related: [ADR-0010, ADR-0015, SPEC-020, SPEC-023, SPEC-027, SPEC-028]
---

# ADR-0016 상태 전이는 aggregator fold 한 곳에서 계산하고, 늦은 이벤트는 revision 재발행, 호출 carry·상한은 결정적 규칙으로 둔다

## 맥락

v4(ADR-0010)는 위험 상태·상태 스냅샷·노출 지표를 aggregator가 영상 끝에 한 번 계산한다. 실시간이 들어오면 창마다 증분으로 계산해야 하고, 완료 뒤에 도착하는 이벤트(벡터 후보 판정, 긴급 후보 판정)를 어떻게 반영할지 정해야 한다.

v5 초안은 (1) analysis-api가 늦은 이벤트를 `event.late` 토픽으로 다시 내고, (2) 긴급 후보를 `alert+vlm` 판정 방식의 별도 이벤트로 저장하고, (3) 상태형 이벤트의 재판정 간격과 Job당 호출 상한을 Redis 공유 카운터로 두었다. 재검토에서 드러난 문제는 다음과 같다.

- `event.late`는 다른 담당자 서비스(analysis-api)가 새 토픽을 내야 동작한다.
- 긴급 후보와 창 후보가 같은 순간을 두 이벤트로 저장해 타임라인에 중복이 생긴다.
- Job당 호출 상한을 Redis 카운터로 세면 청크가 병렬로 처리될 때 순서에 따라 어느 후보가 `unverified`가 될지 달라진다. 같은 입력에 같은 결과가 나오지 않아 재처리와 Golden Set 평가가 흔들린다.
- 업로드는 트랙 ID가 청크 로컬이라 "같은 트랙의 마지막 confirmed"를 Redis로 찾을 수 없다.
- 예산 초과 Job을 `COMPLETED_WITH_ERRORS`로 두는 것은 pipeline-service(다른 담당자)가 `counts.budgetExceeded`를 세야 가능하다.

## 결정 요인

- 같은 입력이면 같은 결과가 나와야 한다(SPEC-027 R-21). 재처리·재전달·평가가 이 성질에 기댄다.
- 다른 담당자 서비스의 변경 없이 동작해야 한다.
- 타임라인에 같은 순간이 두 번 나오면 안 된다.
- 상태형 이벤트(보호구 미착용)의 VLM 호출 수를 트랙당 시간당 30회 이하로 묶어야 한다(아키텍처 17.1절).

## 검토한 선택지

### 1. 늦은 이벤트를 analysis-api가 `event.late`로 다시 내고, 호출 상한은 Redis 카운터 (v5 초안)

- 장점: aggregator가 analysis-api 저장본만 보면 된다.
- 단점: 다른 담당자 토픽에 묶인다. 상한이 비결정적이다. 긴급 이벤트가 중복 저장된다.

### 2. aggregator가 `event.analyzed`를 직접 소비해 대기 집합과 revision으로 처리하고, carry·상한을 메시지 안 결정적 규칙으로 둔다

- 장점: 새 토픽이 없다. 업로드의 carry·상한이 공유 상태 없이 결정적이다. 긴급 경로는 알림만 내고 이벤트는 창 후보 하나로 저장된다.
- 단점: aggregator가 `event.analyzed`를 추가로 소비한다. 업로드 결과 파일이 revision마다 바뀌므로 소비자가 revision을 비교해야 한다. 실시간의 재판정 간격만 Redis가 남는다.

### 3. 늦은 이벤트를 반영하지 않는다

- 장점: 가장 단순하다.
- 단점: 벡터 후보 판정 결과가 위험 상태에 들어가지 않는다. v4의 행동 유형 확장(ADR-0010)이 상태에 반영되지 않는다.

## 결정

**선택지 2**를 택한다. 이유:

- `fold(state, events[]) → state'`는 aggregator에만 있는 순수 함수다. 업로드 완료(`scope: job`), 실시간 창(`scope: chunk`), 늦은 벡터 이벤트, `REANALYZE`가 모두 이 함수를 지난다.
- aggregator는 모든 Job의 `event.analyzed`를 소비한다. 업로드 Job이 완료되기 전에 온 `vector*` 이벤트는 Redis 대기 집합에 두고 완료 fold 때 읽기 API 결과와 합친다. 완료 뒤에 온 것은 그 시각 이후를 다시 fold해 `source.completed`를 `revision + 1`로 다시 낸다. analysis-api는 결정적 ID로 upsert한다(생산자 확인 필요). 실시간은 `event.analyzed`·`track.detected`를 창별 대기 집합에 모아 Kafka 입력만으로 fold한다.
- 개수 검증은 `rule*` 판정 방식만 센다. 벡터 후보·긴급 후보·트랙 속성·텍스트 임베딩은 완료 조건이 아니다.
- 긴급 후보는 `alert.raised`(`pending` → `confirmed`·`dismissed`)만 만든다. 이벤트는 같은 candidateId의 창 후보가 ai-gateway 결과 캐시 적중으로 저장한다. 판정 방식 `alert+vlm`은 두지 않는다.
- 상태형 유형의 carry: 업로드는 메시지 안에서 같은 (trackLocalId, 유형) 후보를 시작순으로 놓고 간격(기본 120초)마다 첫 후보만 판정하고 나머지는 `rule+carry`다. 실시간은 세션 전체 trackId로 Redis의 마지막 `confirmed` 시각을 본다. 창이 순서대로 오므로 둘 다 결정적이다.
- 호출 상한은 실행당 `max(3, 분당 3회 × 실행 길이)`다. 공유 카운터 없이 Job 합이 상한 이하다. 넘으면 `unverified`에 `unverifiedReason: call_cap_reached`를 붙인다.
- 예산 초과는 `unverifiedReason: budget_exceeded`로 발행되고 완료는 정상 진행된다. quality-service가 `event.analyzed`에서 재판정 큐를 만들고, 운영자가 `REANALYZE`를 돌리면 이미 판정된 후보는 캐시가 적중한다. Job 상태 `COMPLETED_WITH_ERRORS`에 기대지 않는다.
- quality-service 검토 항목의 `reason`은 사유가 늘어나는 목록이라 `x-extensible-enum`으로 바꾼다. 응답 enum 제약을 없애는 한 번의 하위호환 파괴이고, 소비자 구현이 없는 개발 단계라 경로(`/api/v1`)는 그대로 두고 `quality-service.yaml`을 2.0.0, 계약 묶음을 4.0.0으로 올린다(ADR-0014와 같은 처리).
- 운영자 검토로 `confirmed`가 된 이벤트를 상태에 반영하는 것은 이 결정의 범위 밖이다. 필요해지면 analysis-api가 `event.analyzed`를 다시 내는 방식으로 같은 경로를 쓴다.

## 결과

- 좋아지는 점: 새 토픽 없이 늦은 이벤트가 상태에 반영된다. 같은 입력에 같은 결과가 나온다. 타임라인 중복이 없다. 실시간이 analysis-api 읽기 API 없이 동작한다.
- 감수할 점: `source.completed`가 같은 jobId로 여러 번 올 수 있어 소비자가 `revision`을 비교해야 한다. 업로드의 carry는 청크 안에서만 적용되어 청크 경계마다 한 번 더 판정한다(2분 청크, 120초 간격이면 호출 수는 같다). aggregator가 Redis 대기 집합(TTL 7일)을 가진다.
- 후속 작업: SPEC-027·028(fold 정의, 대기 집합, revision, `rule*` 대조), SPEC-020·023(구간 규칙, 실행당 상한, `alert.candidate`·`alert.raised`, `unverifiedReason`), 계약 4.0.0(`source.completed.revision`, `event.analyzed.unverifiedReason`, `alert.*`), SPEC-029(재판정 큐 사유).

## 참고

- [아키텍처 v5.1](../architecture/architecture.md) 8, 9, 12, 17절
- [ADR-0015](0015-realtime-window-pipeline.md)
