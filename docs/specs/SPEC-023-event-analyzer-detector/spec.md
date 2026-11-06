---
id: SPEC-023
title: event-analyzer 탐지기·규칙 후보 판정과 event.manifest
status: Approved
owner: <이름>
repos: [ai, docs]
created: 2026-11-06
updated: 2026-11-06
related: [ADR-0008, ADR-0010, SPEC-009, SPEC-013, SPEC-020, SPEC-021, SPEC-022, ADR-0015, ADR-0016, SPEC-036, SPEC-037]
---

# SPEC-023 event-analyzer 탐지기·규칙 후보 판정과 event.manifest

> 이 문서에는 **무엇을, 왜**만 쓴다. 클래스, 테이블, 라이브러리 같은 구현 방법은 각 레포의 plan.md에 쓴다.

## 1. 배경과 목적

chunk-processor는 이벤트 정의 목록의 규칙에 맞고 탐지기가 지원을 선언한 순간만 후보로 모아, 청크 실행마다 `event.candidate` 한 건으로 보낸다([아키텍처 v5](../../architecture/architecture.md) 분석 처리 흐름 5·8단계, "이벤트 경로"). event-analyzer가 이 후보를 판정한다. 판정 방식은 두 가지다.

- 규칙으로 확정하는 후보(구역 진입 등)는 VLM 없이 템플릿 결과를 만든다. 판정 방식은 `rule`이다.
- 그 밖의 후보는 `event_judge`로 판정한다. 위험이 높거나 애매하면 `event_judge_escalate`로 다시 판정한다. 판정 방식은 `rule+vlm`·`rule+vlm+escalate`다.

판정에 앞서, 같은 트랙의 같은 유형이 쿨다운(기본 10초) 안에 반복되면 점수가 높은 후보 하나로 합친다. 같은 사람이 헬멧을 벗은 몇 초가 판정 수십 건이 되지 않게 하려는 것이다.

벡터 후보 판정([SPEC-020](../SPEC-020-event-analyzer-vector/spec.md))과 같은 서비스, 같은 `event.analyzed` 형식을 쓴다. 다른 점은 판정 뒤 실행마다 `event.manifest`를 한 건 발행한다는 것이다. pipeline-service는 이를 완료 판정에 세고, analysis-api는 자기 저장 수와 맞춰 본다.

입력 `event.candidate`는 chunk-processor(다른 담당자)가 만든다. 계약이 없어 이 spec이 아키텍처 문서대로 소비 쪽에서 정한다(2026-11-06 사용자 결정, [handoff](../../handoff.md) 2.1).

v5.1([아키텍처 v5.1](../../architecture/architecture.md) 6.3·8.4·17.2절, [ADR-0016](../../adr/0016-aggregator-fold-and-deterministic-caps.md)): 상태형 유형의 반복 후보를 메시지 안 구간 규칙으로 잇고(`rule+carry`), 실행당 호출 상한을 둬 공유 상태 없이 같은 입력에 같은 결과가 나오게 한다. 실시간의 긴급 후보(`alert.candidate`)는 알림만 만들고 이벤트는 창 후보가 캐시 적중으로 저장한다([ADR-0015](../../adr/0015-realtime-window-pipeline.md)).

## 2. 범위

### 포함

- 계약: `event.candidate`(생산자 확인 필요), 후보 파일 `candidates/v1/candidate-file`, `event.manifest`, `event.analyzed`의 판정 방식 `rule`·`rule+vlm`·`rule+vlm+escalate`와 근거 `detectorCandidate`, AsyncAPI, 단계 ID `analyzer.merge`
- `event.candidate` 소비(소비 그룹 `event-analyzer`). 후보가 메시지에 있든 파일에 있든 처리한다.
- 같은 트랙·같은 유형 쿨다운 병합(메시지 안)
- 규칙 후보의 템플릿 결과(템플릿 문장·기본 severity는 프로필 값)
- VLM 후보 판정과 재판정, 실패 처리. SPEC-020과 같은 규칙에, 탐지 점수의 애매 구간 상향을 더한다.
- 후보마다 `event.analyzed`, 실행마다 `event.manifest`
- 처리 단계 측정 `analyzer.merge`
- 로컬 compose 토픽 `event.candidate`·`event.manifest`와 재시도 토픽

### 제외

- chunk-processor의 후보 생성(규칙, 근거 프레임 박스 표시, 탐지기 능력 선언): 생산자(다른 담당자) 몫이다.
- 청크를 넘는 이벤트 병합, 체류·배회·장비 방치 같은 시간 기준 규칙, 정적 객체 재고 비교: aggregator(SPEC-027) 몫이다.
- 로컬 트랙 ID를 최종 trackId로 바꾸기: analysis-api가 `track.manifest` 번역표로 한다(SPEC-022).
- 템플릿 문장·기본 severity·애매 구간·프롬프트 문안의 실제 값: AI 담당자 몫이다. 이 spec은 프로필 자리와 동작 확인용 값만 둔다.
- 활성 위험 상태에 따른 판정 방식 결정: chunk-processor가 후보의 `judgment`로 정해 보낸다.

## 3. 사용자 시나리오

### US-1 탐지기 후보를 VLM으로 확인 (P1)

안전관리자로서 탐지기가 찾은 보호구 미착용·화재 후보가 실제 상황인지 확인된 결과를 보고 싶다.

#### 인수 조건

- Given `judgment: vlm` 후보 2개가 든 `event.candidate`, When 처리하면, Then 후보마다 근거 프레임으로 `event_judge`를 부르고 판정 방식 `rule+vlm`인 `event.analyzed` 2건, 이어서 `analyzedCount: 2`인 `event.manifest` 1건이 발행된다.
- Given 1차 판정이 severity `high`, When 처리하면, Then `event_judge_escalate`로 다시 판정하고 판정 방식은 `rule+vlm+escalate`다.

### US-2 규칙으로 확정하는 후보 (P1)

안전관리자로서 위험구역 진입처럼 규칙만으로 분명한 사건은 VLM 비용 없이 바로 기록되기를 원한다.

#### 인수 조건

- Given `judgment: rule`인 `hazard_zone_access` 후보, When 처리하면, Then ai-gateway를 부르지 않고 판정 방식 `rule`, `verificationStatus: confirmed`, 프로필 템플릿 문장과 기본 severity가 담긴 `event.analyzed`가 발행된다.

### US-3 반복 후보 병합 (P1)

안전관리자로서 같은 작업자가 몇 초 동안 계속 헬멧을 벗고 있으면 이벤트 하나로 보이기를 원한다. 왜냐하면 같은 사건이 수십 건으로 보이면 정말 다른 사건을 놓치기 때문이다.

#### 인수 조건

- Given 같은 트랙의 `ppe_missing` 후보 3개가 3초 간격, When 처리하면, Then 점수가 가장 높은 후보 하나만 판정하고, 나머지 두 후보 ID는 `detectorCandidate.mergedCandidateIds`에 담기며 `event.manifest`의 `mergedCount`는 2다.
- Given 트랙이 없는 `fire_or_smoke` 후보 2개, When 처리하면, Then 합치지 않는다.

### US-4 후보 0건, 큰 묶음, 잘못된 입력 (P2)

pipeline-service 담당자로서 후보가 없는 청크도 완료 신호를 받고 싶다. 운영자로서 큰 후보 묶음과 잘못된 메시지가 처리를 막지 않기를 원한다.

#### 인수 조건

- Given 후보 0개인 `event.candidate`, When 처리하면, Then `event.analyzed` 없이 `candidateCount: 0`인 `event.manifest`가 발행된다.
- Given 후보가 `candidatesKey` 파일에 있음, When 처리하면, Then 파일의 후보를 메시지에 든 것과 같이 처리한다.
- Given 없는 후보 파일이나 계약에 맞지 않는 메시지, When 받으면, Then 아무것도 발행하지 않고 DLQ로 보낸다.

## 4. 요구사항

### 기능 요구사항 (EARS)

| ID | 요구사항 | 시나리오 |
| --- | --- | --- |
| R-1 | WHEN event-analyzer가 `event.candidate`를 받으면, THE event-analyzer SHALL 메시지의 `candidates`, 없으면 `candidatesKey` 파일의 후보 목록을 처리한다. | US-1, US-4 |
| R-2 | IF `candidatesKey` 파일이 없거나 계약에 맞지 않거나 후보 수가 `candidateCount`와 다르면, THEN THE event-analyzer SHALL 아무것도 발행하지 않고 메시지를 재시도 없이 DLQ로 보낸다. | US-4 |
| R-3 | THE event-analyzer SHALL `trackLocalId`가 있는 후보를 같은 `trackLocalId`·같은 `eventType`끼리 시작 시각순으로 묶는다. 앞 후보의 끝과 다음 후보의 시작 간격이 프로필 쿨다운(기본 10초) 이하면 같은 묶음이다. 묶음마다 점수가 가장 높은 후보 하나만 남긴다(같으면 이른 시작, 그다음 candidateId 순). 나머지 후보 ID는 남긴 후보의 `mergedCandidateIds`에 담는다. | US-3 |
| R-4 | WHERE 후보의 `judgment`가 `rule`이면, THE event-analyzer SHALL ai-gateway를 부르지 않고 최종 분석을 만든다. 유형은 후보 유형, `eventDetected` true, `verificationStatus` `confirmed`, `description`은 그 유형의 프로필 템플릿에 구역 이름을 넣은 문장, `severity`는 그 유형의 프로필 기본값, `evidenceStart`·`evidenceEnd`는 후보 시각(초)이고, 나머지는 null이다. 판정 방식은 `rule`, 판정 호출 기록은 빈 배열로 둔다. | US-2 |
| R-5 | WHERE 후보의 `judgment`가 `vlm`이면, THE event-analyzer SHALL `event_judge`를 부른다. 이미지는 근거 프레임(순서 유지)이고, 변수는 후보 유형, 초 단위 시작·끝, 구역 이름, 근거(경로 `detector`, 트리거 클래스, 점수, 관측 수, 탐지 프로필)다. | US-1 |
| R-6 | IF 1차 판정이 SPEC-020 R-3의 상향 조건에 맞거나, 프로필에 그 유형의 애매 점수 구간이 있고 후보 점수가 그 구간 안이면, THEN THE event-analyzer SHALL 같은 입력으로 `event_judge_escalate`를 한 번 더 부른다. 단 SPEC-020 R-4의 제외 조건이면 부르지 않는다. | US-1 |
| R-7 | THE event-analyzer SHALL VLM 후보의 최종 분석, 검토 표시, 호출 실패 처리를 SPEC-020 R-5, R-7, R-11~R-15(SPEC-021 R-14 포함)와 같게 하고, 판정 방식은 재판정을 불렀으면 `rule+vlm+escalate`, 아니면 `rule+vlm`으로 기록한다. | US-1 |
| R-8 | WHEN 메시지의 남은 후보를 모두 판정하면, THE event-analyzer SHALL 남은 후보마다 `event.analyzed`를 한 건씩 발행한다. eventId는 SPEC-020 R-9와 같이 candidateId로 만든다. | US-1, US-2 |
| R-9 | THE event-analyzer SHALL `event.analyzed`에 SPEC-020 R-10의 공통 필드와 `detectorCandidate`(chunkId, executionId, 트리거 클래스, 점수, 관측 수, 로컬 트랙 ID, 구역 ID·이름, 탐지 프로필, 합쳐진 후보 ID)를 담는다. | US-1, US-3 |
| R-10 | WHEN 메시지의 `event.analyzed`를 모두 발행하면, THE event-analyzer SHALL `event.manifest`를 한 건 발행한다. 담는 값은 받은 후보 수, 합쳐진 후보 수, 발행 수, 발행한 eventId 목록, 메시지의 `unsupportedEvents`, 탐지 프로필이다. eventId는 executionId로 결정적으로 만든다. | US-1, US-4 |
| R-11 | IF 후보가 0개이면, THEN THE event-analyzer SHALL `event.analyzed` 없이 R-10의 `event.manifest`만 발행한다. | US-4 |
| R-12 | THE event-analyzer SHALL 한 메시지의 판정 호출을 SPEC-020 R-18의 동시 판정 수 안에서 진행한다. | US-1 |
| R-13 | THE event-analyzer SHALL 병합과 규칙 후보 확정의 처리 시간을 단계 `analyzer.merge`(받은 후보 수를 count로)로 남기고, 판정·재판정은 SPEC-020 R-19의 단계로 남긴다. | US-1 |
| R-14 | IF `event.candidate`가 계약 스키마에 맞지 않으면, THEN THE event-analyzer SHALL 아무것도 발행하지 않고 재시도 없이 DLQ로 보낸다. | US-4 |
| R-15 | IF Kafka에 일시적으로 발행할 수 없으면, THEN THE event-analyzer SHALL 메시지를 재시도 토픽으로 보내 다시 처리하고, 다시 처리할 때 같은 eventId로 발행한다. | US-4 |
| R-16 | IF 프로필에 규칙 판정이 가능한 유형의 템플릿이나 기본 severity가 없거나, 쿨다운이 0 이하이거나, 애매 점수 구간이 0~1 밖이거나 시작이 끝보다 크면, THEN THE event-analyzer SHALL 기동에 실패한다. | US-2 |
| R-17 | WHERE 후보의 유형이 이벤트 정의 목록에서 상태형(`rejudgeIntervalS`가 있음)이면, THE event-analyzer SHALL R-3 병합 뒤 같은 `trackLocalId`·유형의 남은 후보를 시작순으로 놓고, 첫 후보와 그 뒤 매 `rejudgeIntervalS`(기본 120초)가 지난 첫 후보만 판정하며, 그 사이 후보는 직전 판정 결과를 복사해 판정 방식 `rule+carry`, 호출 기록 빈 배열로 발행한다. 이 규칙은 메시지 안에서만 적용한다. | US-3 |
| R-18 | WHERE 메시지의 `jobType`이 `STREAM`이면, THE event-analyzer SHALL R-17의 "직전 판정"을 Redis 키 `rejudge:<sourceId>:<trackId>:<eventType>`의 마지막 `confirmed` 시각·결과로 대신 찾아 창을 넘어 잇고, 판정할 때마다 그 키를 갱신(TTL `rejudgeIntervalS` × 2)한다. Redis가 없으면 판정한다. | US-3 |
| R-19 | THE event-analyzer SHALL 한 메시지의 VLM 호출 수를 `max(프로필 바닥(기본 3), 분당 상한(기본 3) × 실행 길이(분))` 이하로 두고, 넘는 후보(시작순 뒤쪽)는 호출 없이 `verificationStatus: unverified`·`unverifiedReason: call_cap_reached`로 발행한다. | US-3 |
| R-20 | THE event-analyzer SHALL `event.manifest`에 `rule+carry` 발행 수(`carriedCount`), 상한으로 `unverified`가 된 수(`capReachedCount`), 예산 초과로 `unverified`가 된 수(`budgetExceededCount`)와 메시지의 `jobType`을 싣는다. | US-1 |
| R-21 | WHEN event-analyzer가 `alert.candidate`를 받으면, THE event-analyzer SHALL 먼저 `alert.raised(status: pending)`를 탐지기 근거(유형, 트랙, 구역, 근거 프레임, 사유)만으로 1건 발행한 뒤, 같은 후보를 R-5~R-7과 같이 `event_judge`로 판정해 `confirmed`(eventDetected true)면 `alert.raised(status: confirmed, analysis)`, 아니면 `alert.raised(status: dismissed)`를 1건 발행한다. `event.analyzed`는 발행하지 않는다. | US-1 |
| R-22 | THE event-analyzer SHALL `alert.candidate` 판정의 ai-gateway 입력(이미지 순서, 변수)을 같은 candidateId의 `event.candidate` 후보와 같게 만들어 결과 캐시(SPEC-016 R-2)가 적중하게 한다. | US-1 |
| R-23 | IF `alert.candidate` 판정이 예산 초과·호출 실패로 `unverified`·`unknown`이면, THEN THE event-analyzer SHALL `alert.raised(status: confirmed)`를 내지 않고 `pending`을 유지한 채 사유를 `alert.raised(status: dismissed, reason)`로 닫는다. | US-1 |
| R-24 | THE event-analyzer SHALL `alert.candidate` 처리 시간을 단계 `analyzer.alert`(받은 후보부터 첫 `alert.raised` 발행까지)로 남긴다(SPEC-013). | US-1 |

### 비기능 요구사항

| ID | 요구사항 |
| --- | --- |
| NFR-1 | THE event-analyzer SHALL 로컬 compose mock 판정 프로필에서 VLM 후보 50개 메시지를 10초 안에 처리한다. |
| NFR-2 | THE event-analyzer SHALL SPEC-020 NFR-1·NFR-2(한 번에 한 메시지, 발행 뒤 커밋, 긴 판정 중 하트비트 유지)를 `event.candidate`에도 지킨다. |

## 5. 영향 범위

| 레포 / 서비스 | 변경 개요 | 담당 요구사항 |
| --- | --- | --- |
| ai / event-analyzer | `event.candidate` 경로: 병합, 규칙 확정, 판정, `event.manifest`, 프로필 | R-1~R-16, NFR-1, NFR-2 |
| ai / libs | 계약 모델(`EventCandidate`, 후보 파일, `EventManifest`, `EventAnalyzed` 확장), 단계 ID | R-1, R-9, R-10, R-13 |
| docs | 계약, overview 토픽 표·판정 표 | R-4, R-9, R-10 |
| docs / local | 토픽 `event.candidate`·`event.manifest`, `event.candidate.event-analyzer.retry` | R-15 |
| ai / chunk-processor (다른 담당자) | (이후) `event.candidate`와 후보 파일 생성 | — |
| backend / pipeline-service, analysis-api (다른 담당자) | (이후) `event.manifest` 소비 | — |

## 6. 계약 변경

| 계약 파일 | 변경 | 하위호환 |
| --- | --- | --- |
| `service-contracts/events/event.candidate.schema.json` | 새 이벤트(생산자 확인 필요) | 예(추가) |
| `service-contracts/candidates/v1/candidate-file.schema.json` | 새 파일 형식, 후보 항목의 원본 | 예(추가) |
| `service-contracts/events/event.manifest.schema.json` | 새 이벤트 | 예(추가) |
| `service-contracts/events/event.analyzed.schema.json` | 판정 방식 enum에 `rule`·`rule+vlm`·`rule+vlm+escalate`, 선택 필드 `detectorCandidate`. `judgments` 최소 개수를 VLM 방식에만 적용(`rule`은 빈 배열) | 예. 판정 방식은 SPEC-020 계약에 "탐지기·규칙 후보 spec에서 더한다"고 예고한 값이다. `judgments` 최소 개수 완화는 `rule` 메시지에만 해당하고, 소비자가 아직 없다(개발 단계, 하위호환 안 남김 원칙) |
| `service-contracts/asyncapi/event-analyzer.yaml` | `event.candidate` 소비, `event.manifest` 발행(1.1.0) | 예(추가) |
| `service-contracts/asyncapi/chunk-processor.yaml` | `event.candidate` 발행 채널(1.3.0) | 예(추가) |
| `service-contracts/stages/v1/stages.schema.json` | `analyzer.merge` | 예(추가) |
| `service-contracts/events/alert.candidate.schema.json` | v5.1 신규(생산자 stream-ingestor, SPEC-037) | 예(추가) |
| `service-contracts/events/alert.raised.schema.json` | v5.1 신규. `status`(`pending`·`confirmed`·`dismissed`), candidateId, 근거, 확정이면 `VLMAnalysis` | 예(추가) |
| `service-contracts/events/event.manifest.schema.json` | v5.1: 선택 필드 `carriedCount`·`capReachedCount`·`budgetExceededCount`·`jobType` | 예(선택 필드 추가) |
| `service-contracts/events/event.analyzed.schema.json` | v5.1: 판정 방식 `rule+carry`, 선택 필드 `unverifiedReason`·`jobType` | 예(열거값·선택 필드 추가) |
| `service-contracts/events/event.candidate.schema.json` | v5.1: 선택 필드 `jobType` | 예(선택 필드 추가) |
| `service-contracts/asyncapi/event-analyzer.yaml` | v5.1: `alert.candidate` 소비, `alert.raised` 발행(1.2.0) | 예(추가) |
| `service-contracts/taxonomy/v2/taxonomy.schema.json` | v5.1: 이벤트 정의 항목에 선택 필드 `alertImmediately`, `rejudgeIntervalS` | 예(선택 필드 추가) |
| `service-contracts/stages/v1/stages.schema.json` | v5.1: `analyzer.alert` | 예(추가) |

계약 묶음 3.2.0 → 3.3.0. v5.1 변경은 3.15.0 → 4.0.0(quality-service 응답 enum을 열린 목록으로 바꾼 하위호환 파괴 1회, ADR-0016. 나머지는 선택 필드·값 추가)

## 7. 성공 지표

- 로컬 compose에서 테스트용 `event.candidate`(VLM 후보 3, 규칙 후보 1, 병합될 후보 2)를 넣으면 `event.analyzed` 4건과 `mergedCount: 2`인 `event.manifest` 1건이 나오고, 모두 계약 스키마를 통과한다.

## 8. 미결 사항

- 해당 없음. 템플릿 문장·기본 severity·애매 구간은 프로필 자리만 정했다(AI 담당자 몫).
