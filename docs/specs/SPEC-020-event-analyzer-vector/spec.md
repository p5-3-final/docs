---
id: SPEC-020
title: event-analyzer 벡터 후보 판정
status: Approved
owner: <이름>
repos: [ai, docs]
created: 2026-11-06
updated: 2026-11-06
related: [ADR-0008, ADR-0010, ADR-0012, ADR-0014, SPEC-009, SPEC-013, SPEC-016, SPEC-019]
---

# SPEC-020 event-analyzer 벡터 후보 판정

> 이 문서에는 **무엇을, 왜**만 쓴다. 클래스, 테이블, 라이브러리 같은 구현 방법은 각 레포의 plan.md에 쓴다.

## 1. 배경과 목적

frame-encoder는 구간 벡터가 유형별 텍스트 프로토타입과 비슷한 구간을 `event.candidate.vector`로 낸다([SPEC-019](../SPEC-019-frame-encoder/spec.md), ADR-0010 ③). 이 후보는 벡터 점수만으로 정한 것이라 실제로 일어났는지 확인해야 한다. event-analyzer가 후보마다 구간 프레임을 ai-gateway `/v1/analyze`(`event_judge`)로 판정해 `VLMAnalysis`를 만들고, 결과를 `event.analyzed`로 analysis-api·embedding-worker·quality-service에 보낸다([아키텍처 개요](../../architecture/overview.md) 분석 처리 흐름 8단계, "판정").

- 단계 상향: 1차 판정이 severity `high`이거나 판단 불가(`eventDetected` null)이면 더 강한 모델(`event_judge_escalate`)로 다시 판정하고, 두 판정이 엇갈리면 `reviewRequired`를 붙인다. 높은 위험 후보만 비싼 모델을 쓰고, 모델이 엇갈린 후보를 사람이 검토하게 하려는 것이다. 벡터 후보도 탐지기 후보와 같은 방식으로 판정한다(overview 8단계).
- 후보를 버리지 않는다: 모델 미설정·예산 초과면 `unverified`, ai-gateway가 끝까지 응답하지 않으면 `unknown`으로 기록해 발행한다.
- 메시지 단위: 후보 하나에 `event.analyzed` 하나. analysis-api가 이벤트마다 조건부로 저장하고(overview "순서"), embedding-worker가 설명문 하나씩 임베딩하기 때문이다.
- 벡터 후보는 트랙이 없어 "같은 트랙·같은 유형 쿨다운 병합"을 하지 않는다. 연속 구간을 이벤트 하나로 묶는 것은 aggregator 몫이다.
- `VLMAnalysis` 스키마는 ai-gateway 출력 스키마였는데, 다른 레포로 나가는 `event.analyzed`에 들어가므로 이 spec에서 docs 계약으로 옮긴다(ADR-0012 "다른 레포로 나가는 출력 형식").

탐지기·규칙 후보(`event.candidate`)는 아직 계약과 생산자(chunk-processor, 다른 담당자)가 없어 이 spec에서 다루지 않는다. 그 경로는 같은 서비스에 이어서 붙인다.

## 2. 범위

### 포함

- `event.candidate.vector` 소비(소비 그룹 `event-analyzer`)
- 후보마다 `event_judge` 호출, 조건에 맞으면 `event_judge_escalate` 재판정
- 최종 `VLMAnalysis` 선택, 판정 방식(`vector+vlm`·`vector+vlm+escalate`), `reviewRequired`
- ai-gateway 일시 오류의 후보 단위 재시도와 `unknown` 기록
- 후보마다 `event.analyzed` 발행(결정적 eventId)
- ai-gateway: `event_judge_escalate` taskType 등록(입출력 형식은 `event_judge`와 같음, 모델은 프로필)
- 처리 단계 측정 `analyzer.judge`·`analyzer.escalate`
- 계약: `event.analyzed`, `VLMAnalysis`(docs로 이동), 단계 ID, AsyncAPI, ai-gateway OpenAPI의 taskType
- 로컬 compose에 event-analyzer와 토픽 추가

### 제외

- `event.candidate`(탐지기·규칙 후보) 판정, 쿨다운 병합, 근거 프레임 박스 표시, `event.manifest`: 그 계약이 생기면 별도 spec. 벡터 후보는 `event.manifest` 수에 넣지 않는다(overview 8단계).
- `event.analyzed` 소비(이벤트 저장, 텍스트 임베딩, 검토 큐): analysis-api·embedding-worker·quality-service spec
- 프롬프트 문장 내용과 판정 모델 선택: AI 담당자 몫. 이 spec은 `event_judge_escalate`를 등록할 자리만 만든다.
- 연속 구간 병합과 위험 상태 전이: aggregator spec
- `video.deleted` 처리: event-analyzer는 저장소를 갖지 않는다. 호출 원문은 ai-gateway가 지운다(SPEC-009).

## 3. 사용자 시나리오

### US-1 벡터 후보를 VLM으로 확인 (P1)

안전관리자로서 벡터 점수로 걸러진 구간이 실제 사건인지 확인된 결과를 보고 싶다. 왜냐하면 점수만으로는 오탐이 많기 때문이다.

#### 인수 조건

- Given 후보 2개가 담긴 `event.candidate.vector`, When event-analyzer가 처리하면, Then 후보마다 구간 프레임 4장으로 `event_judge`를 부르고 `VLMAnalysis`·판정 방식 `vector+vlm`이 담긴 `event.analyzed` 2건이 발행된다.
- Given 같은 메시지를 다시 받으면, When 처리하면, Then 같은 eventId의 `event.analyzed`가 나온다.
- Given ai-gateway에 판정 모델이 설정되지 않았으면, When 처리하면, Then `verificationStatus`가 `unverified`인 `event.analyzed`가 발행된다.

### US-2 위험하거나 애매한 후보는 강한 모델로 다시 판정 (P1)

안전관리자로서 위험이 높은 판정은 더 강한 모델로 한 번 더 확인하고, 모델이 엇갈리면 검토 대상으로 표시되기를 원한다. 왜냐하면 놓치면 사고로 이어지는 판정을 모델 하나에만 맡기면 안 되기 때문이다.

#### 인수 조건

- Given 1차 판정이 severity `high`, When 처리하면, Then `event_judge_escalate`로 다시 판정하고 판정 방식 `vector+vlm+escalate`, 재판정 결과가 최종 분석으로 담긴다.
- Given 1차는 `confirmed`, 재판정은 `rejected`, When 처리하면, Then `reviewRequired`가 true이고 사유 `judgment_disagreement`가 담긴다.
- Given 1차 판정이 severity `medium`이고 판단 가능, When 처리하면, Then 재판정하지 않는다.

### US-3 ai-gateway 장애에도 후보를 잃지 않음 (P2)

운영자로서 ai-gateway가 잠시 응답하지 않아도 후보가 사라지지 않기를 원한다. 왜냐하면 사라진 후보는 다시 찾을 방법이 없기 때문이다.

#### 인수 조건

- Given ai-gateway가 한 번 503을 돌려주고 다음에 성공, When 처리하면, Then 성공한 판정이 담긴다.
- Given ai-gateway가 재시도 횟수만큼 계속 실패, When 처리하면, Then 그 후보는 `verificationStatus` `unknown`과 실패 코드로 발행되고 다른 후보는 정상 판정된다.

### US-4 잘못된 메시지와 설정 오류 (P2)

운영자로서 계약을 어긴 메시지나 잘못된 설정이 다른 영상 처리를 막지 않기를 원한다.

#### 인수 조건

- Given 계약 스키마에 맞지 않는 메시지, When 받으면, Then `event.analyzed`를 내지 않고 DLQ로 보낸다.
- Given ai-gateway가 호출자를 거절(403), When 처리하면, Then 그 메시지는 `event.analyzed`를 하나도 내지 않고 DLQ로 간다.

## 4. 요구사항

### 기능 요구사항 (EARS)

| ID | 요구사항 | 시나리오 |
| --- | --- | --- |
| R-1 | WHEN event-analyzer가 `event.candidate.vector`를 받으면, THE event-analyzer SHALL 후보마다 ai-gateway `/v1/analyze`를 taskType `event_judge`, 그 메시지의 sourceId, 후보의 구간 프레임 4장(순서 유지), 입력 변수(후보 유형, 초 단위 시작·끝, 구역 null, 근거)로 부른다. | US-1 |
| R-2 | THE event-analyzer SHALL 판정 입력 변수의 근거에 후보 경로 `vector`, 점수, 임계값, 프로토타입 버전, 인코더 모델 ID를 담는다. | US-1 |
| R-3 | IF 1차 판정 결과가 ai-gateway에서 왔고 severity가 `high`이거나 `eventDetected`가 null이면, THEN THE event-analyzer SHALL 같은 입력으로 taskType `event_judge_escalate`를 한 번 더 부른다. | US-2 |
| R-4 | IF 1차 판정이 `unverified`이거나 ai-gateway 실패로 event-analyzer가 만든 `unknown`이면, THEN THE event-analyzer SHALL 재판정하지 않는다. | US-2 |
| R-5 | WHERE 재판정 결과가 `confirmed`나 `rejected`이면, THE event-analyzer SHALL 재판정 결과를 최종 분석으로 쓰고, 그 밖에는 1차 판정 결과를 최종 분석으로 쓴다. | US-2 |
| R-6 | THE event-analyzer SHALL 재판정을 불렀으면 판정 방식을 `vector+vlm+escalate`, 아니면 `vector+vlm`으로 기록한다. | US-1, US-2 |
| R-7 | IF 1차와 재판정의 `verificationStatus`가 하나는 `confirmed`, 다른 하나는 `rejected`이면, THEN THE event-analyzer SHALL `reviewRequired`를 true로, 사유에 `judgment_disagreement`를 담는다. 그 밖에는 `reviewRequired`를 false로 둔다. | US-2 |
| R-8 | WHEN 한 메시지의 후보를 모두 판정하면, THE event-analyzer SHALL 후보마다 `event.analyzed`를 한 건씩 발행한다. | US-1 |
| R-9 | THE event-analyzer SHALL `event.analyzed`의 eventId를 후보 ID로 결정적으로 만들어, 같은 메시지를 다시 처리해도 같은 eventId를 쓴다. | US-1 |
| R-10 | THE event-analyzer SHALL `event.analyzed`에 후보 ID, 구간 ID·시각, 후보 유형, 근거 프레임 경로, 벡터 근거(점수·임계값·프로토타입 버전·인코더 모델 ID), 최종 `VLMAnalysis`, 판정 방식, 판정 호출마다의 taskType·호출 ID·모델·프롬프트 버전·`verificationStatus`·실패 코드, `reviewRequired`와 사유, 분류 체계 버전을 담는다. | US-1 |
| R-11 | IF ai-gateway 호출이 502·503·시간 초과·연결 실패로 끝나면, THEN THE event-analyzer SHALL 그 호출을 설정한 횟수까지 다시 시도한다. | US-3 |
| R-12 | IF 1차 판정 호출이 재시도 끝에도 실패하면, THEN THE event-analyzer SHALL 그 후보의 최종 분석을 `verificationStatus` `unknown`(나머지 판정 필드 null, 유형은 후보 유형)으로 만들고 실패 코드를 기록해 발행한다. | US-3 |
| R-13 | IF 재판정 호출이 재시도 끝에도 실패하면, THEN THE event-analyzer SHALL 1차 판정 결과를 최종 분석으로 쓰고 재판정의 실패 코드를 기록한다. | US-3 |
| R-14 | IF ai-gateway가 판정 호출에 `AI_IMAGE_NOT_FOUND`를 돌려주면, THEN THE event-analyzer SHALL 다시 시도하지 않고 R-12·R-13과 같이 그 호출을 실패로 기록한다. | US-3 |
| R-15 | IF ai-gateway가 `AI_IMAGE_NOT_FOUND` 외의 4xx를 돌려주면, THEN THE event-analyzer SHALL 그 메시지의 `event.analyzed`를 하나도 발행하지 않고 메시지를 재시도 없이 DLQ로 보낸다. | US-4 |
| R-16 | IF `event.candidate.vector`가 계약 스키마에 맞지 않으면, THEN THE event-analyzer SHALL `event.analyzed`를 발행하지 않고 메시지를 재시도 없이 DLQ로 보낸다. | US-4 |
| R-17 | IF Kafka에 일시적으로 발행할 수 없으면, THEN THE event-analyzer SHALL 메시지를 재시도 토픽으로 보내 다시 처리한다. | US-3 |
| R-18 | THE event-analyzer SHALL 한 메시지의 후보 판정을 설정한 수(기본 4)까지만 동시에 진행한다. | US-1 |
| R-19 | THE event-analyzer SHALL 핸들러 안의 처리 시간을 단계 `analyzer.judge`(1차 판정, 후보 수를 count로), `analyzer.escalate`(재판정, 재판정 수를 count로)로 남긴다(SPEC-013). | US-1 |
| R-20 | WHEN 허용된 호출자가 taskType `event_judge_escalate`로 분석을 요청하면, THE ai-gateway SHALL `event_judge`와 같은 입력·출력 형식과 같은 처리 순서(SPEC-009, SPEC-016)로, 프로필의 `event_judge_escalate` 모델과 그 taskType의 프롬프트 버전으로 처리한다. | US-2 |

### 비기능 요구사항

| ID | 요구사항 |
| --- | --- |
| NFR-1 | THE event-analyzer SHALL 한 Pod에서 `event.candidate.vector`를 한 번에 하나씩 처리하고, 메시지의 모든 후보를 발행한 뒤 오프셋을 커밋한다(overview "event-analyzer"). |
| NFR-2 | THE event-analyzer SHALL 판정이 `max.poll.interval.ms`보다 오래 걸려도 Kafka 소비 그룹 하트비트를 유지해, 처리 중인 메시지 때문에 리밸런스가 일어나지 않게 한다. |
| NFR-3 | THE event-analyzer SHALL 로컬 compose에서 mock 판정 프로필로 후보 12개 메시지를 10초 안에 처리한다. |

## 5. 영향 범위

| 레포 / 서비스 | 변경 개요 | 담당 요구사항 |
| --- | --- | --- |
| ai / event-analyzer | 새 워커: 소비·검증, 판정·재판정, 재시도, 발행, 단계 측정 | R-1~R-19, NFR-1~NFR-3 |
| ai / ai-gateway | `event_judge_escalate` 프롬프트 등록(입출력 형식은 `VLMAnalysis` 계약 참조), 로컬 프로필 | R-20 |
| ai / libs | 계약 모델(`EventAnalyzed`, `VLMAnalysis`), 단계 ID | R-10, R-19 |
| docs | 계약, overview 토픽 표·판정 표, 서비스 카탈로그 | R-6, R-10, R-19, R-20 |
| docs / local | 로컬 compose에 event-analyzer, 토픽 `event.analyzed`와 재시도·DLQ | R-17 |
| backend / analysis-api, quality-service, ai / embedding-worker | (이후) `event.analyzed` 소비. 각 spec | — |

## 6. 계약 변경

| 계약 파일 | 변경 | 하위호환 |
| --- | --- | --- |
| `service-contracts/events/_vlm-analysis.schema.json` | 새 공용 스키마. ai-gateway 출력 스키마(`VLMAnalysis`)를 그대로 옮김 | 예(추가) |
| `service-contracts/events/event.analyzed.schema.json` | 새 이벤트 | 예(추가) |
| `service-contracts/stages/v1/stages.schema.json` | `event-analyzer.queue_wait`·`event-analyzer.handle`·`analyzer.judge`·`analyzer.escalate` | 예(추가) |
| `service-contracts/asyncapi/event-analyzer.yaml` | 새 파일: `event.candidate.vector` 소비, `event.analyzed` 발행 | 예(추가) |
| `service-contracts/openapi/ai-gateway.yaml` | `TaskType`에 `event_judge_escalate`. `TaskType`·`EmbedTaskType`을 `x-extensible-enum`으로 전환([ADR-0014](../../adr/0014-ai-gateway-extensible-task-type.md)), 문서 버전 1.0.0 | 아니오(응답 enum 제약 제거 1회, 소비자 없음, 경로 `/v1` 유지) |

계약 묶음 2.10.0 → 3.0.0

## 7. 성공 지표

- 로컬 compose에서 테스트용 `event.candidate.vector`를 넣으면 후보마다 `event.analyzed`가 나오고, 계약 스키마를 통과한다.
- mock 프로필에서 severity `high` 결과가 나오는 후보는 `vector+vlm+escalate`로 기록된다.

## 8. 미결 사항

- 해당 없음
