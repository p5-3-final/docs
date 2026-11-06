---
id: SPEC-027
title: aggregator 영상 단위 병합·시간 규칙·위험 상태·노출 지표·요약
status: Approved
owner: <이름>
repos: [ai, docs]
created: 2026-11-06
updated: 2026-11-06
related: [ADR-0008, SPEC-013, SPEC-017, SPEC-020, SPEC-021, SPEC-022, SPEC-023, ADR-0015, ADR-0016, SPEC-028, SPEC-036]
---

# SPEC-027 aggregator 영상 단위 병합·시간 규칙·위험 상태·노출 지표·요약

> 이 문서에는 **무엇을, 왜**만 쓴다. 클래스, 테이블, 라이브러리 같은 구현 방법은 각 레포의 plan.md에 쓴다.

## 1. 배경과 목적

이벤트는 청크 단위로 병렬 판정된다. 그래서 판정 시점에는 영상 전체를 봐야 하는 일을 할 수 없다. [아키텍처 v5](../../architecture/architecture.md) "처리 흐름" 11단계와 "위험 상태와 상태 스냅샷"은 이 일을 aggregator에 맡긴다.

- 청크 경계를 넘은 같은 사건 병합: 한 청크 실행 안의 병합은 event-analyzer가 한다(SPEC-023). 경계를 넘는 것은 영상 전체가 모인 뒤에만 보인다.
- 체류·배회처럼 시간이 기준인 규칙: chunk-processor는 트랙별 구역 진입·이탈 시각만 남긴다.
- 상태 스냅샷과 위험 상태(활성·해소): 확정 이벤트를 시간순으로 훑어야 한다.
- 위험 상태별 노출 지표(v4 ⑥): 예측 모델의 정답으로도 쓴다.
- 타임라인과 요약

aggregator는 pipeline-service의 `analysis.completed`를 받는다. 그 뒤 analysis-api 내부 읽기 API로 job의 이벤트·트랙·구역·구역 머문 구간을 한 번 읽고, 위 결과를 결과 파일 하나로 저장해 `source.completed`로 알린다. 작업 세션(SPEC-017)에 속한 영상은 세션 직전 영상의 마지막 상태로 시작한다.

같은 입력이면 같은 결과가 나와야 한다(overview 다중 Pod 표 aggregator 행: 상태 전이 계산은 순수 함수). 그래서 요약을 뺀 모든 결과는 입력 이벤트 집합과 프로필만으로 정해진다.

입력 `analysis.completed`(pipeline-service)와 analysis-api 내부 읽기 API는 다른 담당자 서비스다. 계약이 없어 이 spec이 아키텍처 문서대로 소비 쪽에서 정한다(2026-11-06 사용자 결정, [handoff](../../handoff.md) 2.1).

v5.1([아키텍처 v5.1](../../architecture/architecture.md) 9·12절, [ADR-0016](../../adr/0016-aggregator-fold-and-deterministic-caps.md)): 상태 전이는 이 spec의 계산(R-11~R-17)을 `fold(state, events[]) → state'` 한 함수로 두고, 업로드 완료·실시간 창·늦은 벡터 이벤트·`REANALYZE`가 모두 같은 함수를 지난다. 늦은 이벤트는 analysis-api의 새 토픽 없이 `event.analyzed`를 직접 받아 `revision`을 올려 다시 발행한다. 실시간은 읽기 API 없이 Kafka 입력만으로 창마다 증분 계산한다([ADR-0015](../../adr/0015-realtime-window-pipeline.md)).

## 2. 범위

### 포함

- 계약
  - `analysis.completed`(생산자 확인 필요)
  - analysis-api 내부 읽기 API `openapi/analysis-service.yaml` 0.1.0(생산자 확인 필요)
  - `source.completed`와 결과 파일 `aggregates/v1/source-result`
  - ai-gateway taskType `source_summary`와 출력 `events/_source-summary`
  - AsyncAPI(`aggregator` 1.0.0, `pipeline-service` 1.2.0)
  - 단계 ID
- 청크 경계 이벤트 병합
- 체류(`dwell`)·배회(`loiter`) 시간 규칙 템플릿 이벤트
- 상태 스냅샷, 위험 상태 활성·해소, 세션 직전 영상 상태 이어받기
- 노출 지표, 타임라인
- `source_summary` 요약. 모델이 없거나 실패해도 나머지 결과는 낸다.
- ai-gateway: `source_summary` 레지스트리 자리(입력·출력 스키마, 자리 표시 프롬프트, mock 프로필)
- 처리 단계 측정, 로컬 compose에 aggregator와 토픽 추가

### 제외

- 정적 객체 재고 비교(제거·등장·이동·미복구), `object_moved`·`equipment_abandoned`, `state_compare`, `risk_forecast`: 다음 spec(SPEC-028)에서 다룬다.
- 활성 위험 중 위험구역 접근의 VLM 재판정은 v5.1에서 R-31로 포함한다(SPEC-028 R-8 상한 공유).
- 결과 저장, 활성 버전 전환, 화면 표시: analysis-api·notification-service(다른 담당자) 몫이다.
- `source_summary` 프롬프트 문안, 시간 규칙 기준값 결정: AI 담당자 몫이다. 이 spec은 프로필 자리와 기본값만 둔다.

## 3. 사용자 시나리오

### US-1 영상 하나의 위험 흐름 보기 (P1)

안전관리자로서 영상 하나에서 언제 어떤 위험이 생기고 해소됐는지 시간순으로 보고 싶다. 왜냐하면 청크별 이벤트 목록만으로는 위험이 끝까지 남았는지 알 수 없기 때문이다.

#### 인수 조건

- Given `riskDetected=true`인 확정 이벤트 하나와, 같은 구역·유형에서 나중에 `riskDetected=false`인 확정 이벤트 하나, When 집계하면, Then 위험 상태 하나가 `resolved`로 나오고 `resolvedAtMs`가 두 번째 이벤트 시각이다.
- Given 확정 이벤트가 없는 job, When 집계하면, Then 스냅샷·위험이 빈 목록이고 요약 상태가 `empty`인 `source.completed`가 나온다.

### US-2 같은 사건이 두 번 세지지 않음 (P1)

안전관리자로서 청크 경계에 걸친 같은 사건이 두 건으로 보이지 않기를 원한다.

#### 인수 조건

- Given 같은 트랙·같은 유형이고 인접 청크에서 5초 간격으로 나온 이벤트 두 건, When 집계하면, Then 병합 묶음 하나가 나오고 점수 높은 이벤트가 대표가 된다. 다른 이벤트는 상태 계산과 타임라인에서 빠진다.

### US-3 위험구역 체류·배회 (P1)

안전관리자로서 위험구역에 오래 머물거나 여러 번 드나든 작업자를 알고 싶다.

#### 인수 조건

- Given 위험구역 안에 70초 머문 사람 트랙(체류 기준 60초), When 집계하면, Then `rule: dwell` 규칙 이벤트가 나온다.
- Given 5분 안에 같은 위험구역에 세 번 들어온 사람 트랙(기준 3회·300초), When 집계하면, Then `rule: loiter` 규칙 이벤트가 나온다.

### US-4 작업 전후 비교 (P2)

안전관리자로서 작업 세션의 작업 후 영상이 작업 전 영상의 마지막 상태에서 이어지기를 원한다.

#### 인수 조건

- Given 세션 직전 영상에 끝까지 활성인 위험이 있음, When 다음 영상을 집계하면, Then 그 위험이 원래 riskId와 `carriedOver: true`로 이어진다.
- Given 세션 직전 영상에 활성 분석 버전이 없음, When 집계하면, Then 빈 초기 상태로 계산하고 `initialState.fromSourceId`가 null이다.

### US-5 요약 (P2)

안전관리자로서 영상 결과를 두세 문장으로 먼저 읽고 싶다.

#### 인수 조건

- Given 확정 이벤트가 있는 job, When 집계하면, Then `source_summary` 결과가 요약(`status: generated`)에 담긴다.
- Given 요약 모델 미설정이나 호출 실패, When 집계하면, Then 요약만 `not_configured`·`failed`이고 나머지 결과는 그대로 발행된다.

## 4. 요구사항

### 기능 요구사항 (EARS)

| ID | 요구사항 | 시나리오 |
| --- | --- | --- |
| R-1 | WHEN aggregator가 `jobType` `FULL`·`REANALYZE`인 `analysis.completed`를 받으면, THE aggregator SHALL 그 job을 집계해 결과 파일을 저장하고 `source.completed`를 한 건 발행한다. | US-1 |
| R-2 | WHEN aggregator가 `jobType` `REEMBED`인 `analysis.completed`를 받으면, THE aggregator SHALL 집계하지 않고 건너뛴 이유를 로그에 남긴다. | US-1 |
| R-3 | THE aggregator SHALL analysis-api 내부 읽기 API로 job의 이벤트·트랙·구역 머문 구간을 마지막 쪽까지 읽고 영상의 구역 목록을 읽으며, 모든 호출에 `X-Request-Deadline`(메시지 처리 시작 + 설정한 제한 시간, 기본 300초)을 싣는다. | US-1 |
| R-4 | IF 읽은 이벤트 중 판정 방식이 `rule`로 시작하는 것의 수나 트랙 수가 `analysis.completed`의 `counts`와 다르면, THEN THE aggregator SHALL 결과를 발행하지 않고 메시지를 재시도 토픽으로 보낸다. 재시도 상한(기본 5회)을 넘으면 `partial: true`와 빠진 수(`missingCounts`)를 실어 발행한다(v5.1). | US-1 |
| R-5 | WHERE `session.previousSourceId`가 있으면, THE aggregator SHALL 그 영상의 마지막 상태(`final-state`)를 초기 상태로 쓰고, 404 `ANALYSIS_NO_ACTIVE_VERSION`이면 빈 초기 상태와 `fromSourceId: null`로 계산한다. | US-4 |
| R-6 | THE aggregator SHALL 같은 `eventType`이고 같은 trackId(둘 다 trackId가 없으면 같은 zoneId)이며 chunkId가 다른 두 이벤트의 간격(뒤 이벤트 startMs − 앞 이벤트 endMs)이 프로필 병합 간격(기본 10초) 이하이면 한 병합 묶음으로 잇는다. 이어진 이벤트는 모두 같은 묶음이다. | US-2 |
| R-7 | THE aggregator SHALL 병합 묶음의 대표를 점수가 가장 높은 이벤트로 정하고(점수 null은 가장 낮음), 같으면 startMs가 이른 것, 그다음 eventId 순으로 정한다. 대표가 아닌 이벤트는 상태 계산·노출 지표·타임라인에서 뺀다. | US-2 |
| R-8 | THE aggregator SHALL 구역 종류가 `hazard`인 구역에 사람 클래스 트랙이 프로필 체류 기준(기본 60초) 이상 머문 구간마다 `rule: dwell` 규칙 이벤트를 만든다. | US-3 |
| R-9 | THE aggregator SHALL 사람 클래스 트랙이 같은 `hazard` 구역에 프로필 배회 창(기본 300초) 안에서 배회 횟수(기본 3회) 이상 들어오면 `rule: loiter` 규칙 이벤트를 하나 만들고, 그 마지막 진입 뒤부터 다음 창을 센다. | US-3 |
| R-10 | THE aggregator SHALL 규칙 이벤트를 `verificationStatus: confirmed`·`judgmentMethod: rule`과 템플릿 설명으로 만들고, 구간이 같은 구역의 활성 위험 구간과 겹치면 severity를 high, 아니면 medium으로 정한다. 규칙 이벤트는 상태와 위험을 바꾸지 않는다. | US-3 |
| R-11 | THE aggregator SHALL 병합 대표 중 `analysis.verificationStatus`가 `confirmed`인 이벤트만 상태 계산에 넣고, 이벤트 시각(`evidenceEnd`를 ms로, 없으면 endMs) 오름차순, 같으면 eventId 순으로 처리한다. 구역이 없는 이벤트는 구역 `global`로 처리한다. | US-1 |
| R-12 | WHEN 상태 계산 중 `afterState`가 있는 이벤트를 만나면, THE aggregator SHALL 그 구역의 현재 상태를 `previousState`로, `afterState`를 `currentState`로 하는 스냅샷을 만들고 구역의 현재 상태를 바꾼다. | US-1 |
| R-13 | WHEN 상태 계산 중 `riskDetected=true`이고 `riskType`·`riskReason`이 있는 이벤트를 만나면, THE aggregator SHALL 같은 구역·유형의 활성 위험이 있으면 lastSeen과 관련 이벤트를 갱신하고, 없으면 새 활성 위험을 만든다. | US-1 |
| R-14 | WHEN 상태 계산 중 `riskDetected=false`이고 `riskType`이 있는 이벤트를 만나면, THE aggregator SHALL 같은 구역·유형의 활성 위험을 그 시각으로 `resolved`로 바꾼다. 활성 위험이 없으면 아무것도 바꾸지 않는다. | US-1 |
| R-15 | THE aggregator SHALL 초기 상태의 활성 위험을 원래 riskId, `firstSeenMs: 0`, `carriedOver: true`인 활성 위험으로 시작한다. | US-4 |
| R-16 | THE aggregator SHALL 위험마다 활성 시간(활성 시작부터 해소, 없으면 영상 끝까지), 활성 중 같은 구역(`global`이면 영상 전체)에 있었던 사람 트랙 수, 그 트랙들이 활성 구간과 겹친 시간 합을 노출 지표로 계산한다. | US-1 |
| R-17 | THE aggregator SHALL 병합 대표 이벤트, 규칙 이벤트, 위험 활성·해소를 시각 순(같으면 refId 순)으로 담은 타임라인을 만든다. | US-1 |
| R-18 | WHERE 확정 이벤트나 위험이 하나 이상이면, THE aggregator SHALL ai-gateway `/v1/analyze`를 taskType `source_summary`, 이미지 없이 타임라인·위험·구역 이름·영상 길이를 변수로 한 번 부르고, 결과를 요약에 담는다. 확정 이벤트와 위험이 없으면 부르지 않고 요약 상태를 `empty`로 둔다. | US-5 |
| R-19 | IF `source_summary`가 모델 미설정 결과(`modelId: null`)를 돌려주면, THEN THE aggregator SHALL 요약 상태를 `not_configured`로 둔다. 호출이 오류로 끝나면(SPEC-021 R-9 재시도 뒤) `failed`로 두고 나머지 결과를 그대로 발행한다. | US-5 |
| R-20 | THE aggregator SHALL 결과 파일을 `sources/<sourceId>/jobs/<jobId>/aggregate/source-result.json`에 저장한 뒤 `source.completed`를 발행하고, eventId와 결과 안의 모든 ID(병합 묶음, 규칙 이벤트, 스냅샷, 위험)를 jobId와 입력 ID로 결정적으로 만든다. | US-1, US-2 |
| R-21 | THE aggregator SHALL 같은 입력과 같은 프로필이면 요약을 뺀 결과 파일 내용이 같게 만든다. | US-1 |
| R-22 | IF 읽기 API가 SPEC-021 R-10 재시도 끝에도 503·연결 실패·시간 초과이거나, 404 `ANALYSIS_JOB_NOT_FOUND`이거나, 저장소·Kafka가 일시적으로 응답하지 않으면, THEN THE aggregator SHALL 메시지를 재시도 토픽으로 보낸다. | US-1 |
| R-23 | IF 메시지가 계약 스키마에 맞지 않거나 읽기 API가 400을 돌려주거나 응답이 계약과 맞지 않으면, THEN THE aggregator SHALL 재시도 없이 DLQ로 보낸다. | US-1 |
| R-24 | THE aggregator SHALL 처리 시간을 단계 `aggregate.read`·`aggregate.compute`·`aggregate.summary`·`aggregate.store`로 남긴다(SPEC-013). | US-1 |
| R-25 | WHEN aggregator가 `event.analyzed`를 받으면, THE aggregator SHALL `jobType`이 `STREAM`이 아니고 판정 방식이 `vector`로 시작하면 Redis 대기 집합 `pending-vector:<jobId>`(TTL 7일)에 eventId와 요약을 넣고, 그 외 업로드 이벤트는 무시한다. | US-1 |
| R-26 | THE aggregator SHALL R-3으로 읽은 이벤트와 R-25 대기 집합의 벡터 이벤트를 eventId로 중복 제거해 합친 뒤 R-11 이후의 계산에 쓴다. | US-1 |
| R-27 | WHEN 이미 `source.completed`를 발행한 job의 `vector*` `confirmed` 이벤트가 `event.analyzed`로 도착하고 그 eventId가 결과 파일의 입력 eventId 집합에 없으면, THE aggregator SHALL 그 이벤트를 포함해 다시 계산한 결과 파일을 같은 경로에 저장하고 `source.completed`를 `revision`을 1 올려 다시 발행한다. | US-1 |
| R-28 | THE aggregator SHALL `source.completed`에 `revision`(처음 1)을 싣고, 결과 파일에 입력 eventId 집합과 revision을 기록한다. | US-1 |
| R-29 | WHEN aggregator가 `jobType: STREAM`인 `event.analyzed`·`track.detected`를 받으면, THE aggregator SHALL Redis 대기 집합 `pending:<sourceId>:<chunkId>`(TTL 1시간)에 모은다. analysis-api 읽기 API는 부르지 않는다. | US-1 |
| R-30 | WHEN aggregator가 `analysis.completed(scope: chunk, jobType: STREAM)`을 받으면, THE aggregator SHALL R-29 대기 집합의 `rule*` 이벤트 수를 `counts`와 대조(R-4와 같은 재시도·`partial`)한 뒤, 세션 현재 상태(Redis, 없으면 S3 스냅샷, 없으면 `previousSourceId`의 마지막 상태, 없으면 빈 상태)에서 그 창의 `confirmed` 이벤트만으로 R-11~R-17을 증분 계산하고, 바뀐 스냅샷·위험 전이·노출 증분·규칙 이벤트를 `state.updated`(sequence = 창 순번)로 1건 발행한다. 새 상태는 Redis에 쓰고 30창마다 S3 `sources/<sourceId>/state/<sequence>.json`에 저장한다. | US-1 |
| R-31 | WHEN 상태 계산 중 `hazard_zone_access` 규칙 이벤트 구간이 같은 구역의 활성 위험 구간과 겹치면, THE aggregator SHALL 그 트랙의 대표 프레임으로 `event_judge`를 불러 결과를 그 이벤트의 `analysis`로 삼고 판정 방식을 `rule+vlm`으로 기록한다. 이 호출은 SPEC-028 R-8 상한(Job당 20회)에 센다. | US-3 |
| R-32 | WHEN aggregator가 `analysis.completed(scope: job, jobType: STREAM)`을 받으면, THE aggregator SHALL 세션 현재 상태와 세션 동안의 확정 이벤트 전체(Redis 대기 집합 누적 또는 S3 스냅샷·창 결과)로 R-16~R-18을 계산해 결과 파일을 저장하고 `source.completed`(revision 1)를 발행한다. | US-1 |
| R-33 | THE aggregator SHALL STREAM 세션의 구역을 stream-service 내부 읽기 API `GET /internal/v1/stream/sessions/{id}/zones`로 세션당 한 번 읽어 캐시한다. | US-1 |
| R-34 | THE aggregator SHALL 창 단위 계산을 단계 `aggregate.fold`로 남긴다(SPEC-013). | US-1 |

### 비기능 요구사항

| ID | 요구사항 |
| --- | --- |
| NFR-1 | THE aggregator SHALL 이벤트 2,000건·트랙 5,000개·구역 머문 구간 20,000건인 job의 계산(`aggregate.compute`)을 로컬에서 p95 5초 안에 끝낸다. |
| NFR-2 | THE aggregator SHALL NFR-1 크기의 job을 컨테이너 메모리 256MB 안에서 처리한다. |
| NFR-3 | THE aggregator SHALL 요약 문장과 이벤트 설명 원문을 로그에 남기지 않는다. |
| NFR-4 | THE aggregator SHALL 한 Pod에서 메시지를 한 번에 하나씩 처리하고, 발행 뒤 커밋한다. |

## 5. 영향 범위

| 레포 / 서비스 | 변경 개요 | 담당 요구사항 |
| --- | --- | --- |
| ai / aggregator | 새 워커: 읽기, 병합, 시간 규칙, 상태·위험·노출, 타임라인, 요약, 저장·발행 | R-1~R-24, NFR-1~NFR-4 |
| ai / libs | 계약 모델(`AnalysisCompleted`, `SourceCompleted`, 결과 파일), analysis-api 읽기 클라이언트(계약에서 생성, SPEC-021 R-6과 같은 방식), 단계 ID | R-3, R-20, R-24 |
| ai / ai-gateway | `source_summary` 레지스트리(입력·출력 스키마, 자리 표시 프롬프트), 프로필, mock | R-18, R-19 |
| docs | 계약, overview 토픽 표, 서비스 카탈로그 | R-3, R-20 |
| docs / local | 로컬 compose에 aggregator, 토픽 `analysis.completed`·`source.completed`와 재시도·DLQ | R-22, R-23 |
| backend / pipeline-service·analysis-api (다른 담당자) | (이후) `analysis.completed` 발행, 내부 읽기 API 제공, `source.completed` 저장 | — |

## 6. 계약 변경

| 계약 파일 | 변경 | 하위호환 |
| --- | --- | --- |
| `service-contracts/events/analysis.completed.schema.json` | 새 이벤트(생산자 확인 필요) | 예(추가) |
| `service-contracts/events/source.completed.schema.json` | 새 이벤트 | 예(추가) |
| `service-contracts/events/_source-summary.schema.json` | 새 공용 형식(`source_summary` 출력) | 예(추가) |
| `service-contracts/aggregates/v1/source-result.schema.json` | 새 파일 형식 | 예(추가) |
| `service-contracts/openapi/analysis-service.yaml` | 새 파일: 내부 읽기 API 5개(생산자 확인 필요, 0.1.0) | 예(추가) |
| `service-contracts/openapi/ai-gateway.yaml` | TaskType에 `source_summary` 추가(1.2.0 → 1.3.0) | 예(열린 목록 값 추가, ADR-0014) |
| `service-contracts/asyncapi/aggregator.yaml` | 새 파일 | 예(추가) |
| `service-contracts/asyncapi/pipeline-service.yaml` | `analysis.completed` 발행 채널(1.1.0 → 1.2.0, 생산자 확인 필요) | 예(추가) |
| `service-contracts/stages/v1/stages.schema.json` | `aggregator.queue_wait`·`aggregator.handle`·`aggregate.read`·`aggregate.compute`·`aggregate.summary`·`aggregate.store` | 예(추가) |
| `service-contracts/events/analysis.completed.schema.json` | v5.1: `jobType`에 `STREAM`, 선택 필드 `scope`(`job`·`chunk`), `chunkId`, `partial`. 생산자에 stream-service 추가 | 예(열거값·선택 필드 추가) |
| `service-contracts/events/source.completed.schema.json` | v5.1: 선택 필드 `revision`, `partial`, `missingCounts` | 예(선택 필드 추가) |
| `service-contracts/events/state.updated.schema.json` | v5.1 신규(생산자 aggregator). sequence, 바뀐 스냅샷·위험 전이·노출 증분·규칙 이벤트, `activeRiskZoneIds`, `partial`·`gapMs` | 예(추가) |
| `service-contracts/asyncapi/aggregator.yaml` | v5.1: `event.analyzed`·`track.detected` 소비, `state.updated` 발행(1.2.0) | 예(추가) |
| `service-contracts/openapi/stream-service.yaml` | v5.1: 내부 읽기 `GET /internal/v1/stream/sessions/{id}/zones`(SPEC-036) | 예(추가) |
| `service-contracts/stages/v1/stages.schema.json` | v5.1: `aggregate.fold` | 예(추가) |

계약 묶음 3.6.0 → 3.7.0. v5.1 변경은 3.15.0 → 4.0.0(quality-service 응답 enum을 열린 목록으로 바꾼 하위호환 파괴 1회, ADR-0016. 나머지는 선택 필드·값 추가)

## 7. 성공 지표

- 로컬 compose에서 analysis-api 자리 표시 서버(계약 예시 응답)로 보낸 `analysis.completed`가 `source.completed`로 이어지고, 결과 파일이 계약 스키마를 통과한다.
- 같은 입력으로 두 번 집계한 결과 파일이 요약을 빼고 바이트 단위로 같다.

## 8. 미결 사항

- 해당 없음
