---
id: SPEC-014
title: 청크 실행 종료 결과와 슬롯 자동 반환
status: Approved
owner: backend 담당자
repos: [backend, ai, docs]
created: 2026-11-05
updated: 2026-11-05
related: [SPEC-007, SPEC-008, SPEC-010, ADR-0009, ADR-0010, ADR-0013]
---

# SPEC-014 청크 실행 종료 결과와 슬롯 자동 반환

## 1. 배경과 목적

[SPEC-010](../SPEC-010-chunk-dispatch/spec.md)은 요청 발행과 수동 종료 확인만 제공한다. 실제 Kafka 요청 소비·워커 실행 종료·결과 전달과 Pipeline 슬롯 반환을 연결한다. PRD 에픽은 아직 정의되지 않았다. [ADR-0009](../../adr/0009-pipeline-dispatch-boundary.md)의 backend/AI 책임과 기존 AI Gateway API를 유지한다. 현재 chunk-processor는 빈 경로이고 관련 열린 PR은 없다.

## 2. 범위

### 포함

- normalize v2 최초 결과 이벤트 보존과 동일 payload 재전달(기존 SPEC-007 버그 수정)
- 기존 Python chunk-processor 경로에 Kafka 소비·실행 원장·종료 결과 Outbox 추가
- 배정받은 processingRange의 실제 영상 추출 및 실행별 결과 객체 저장
- 명시적인 테스트 환경의 추론 대역, 실제 Kafka·객체 저장소·서로 다른 worker/Pipeline DB의 통합 검증
- Pipeline 결과 입력 검증·중복/지연/충돌·상태 반영·슬롯 반환과 다음 청크 배정

### 제외

- 실제 AI Gateway 추론 요청/출력 계약 확정·모델·벡터 차원·탐지/검색 결과 적재
- 자동 재실행·임대 만료 재점유·fencing/heartbeat·Job 전체 완료 판정
- 운영 활성화·기존 Kafka offset 변경·배포

테스트 대역은 명시적인 test 환경에서만 기동한다. production에서는 검증 대역을 선택할 수 없고 실제 추론 adapter 미연결 시 기동에 실패한다. 실제 서비스가 모델 추론을 한다고 표기하지 않는다.

## 3. 사용자 시나리오

### US-1 최초 결과를 보존하고 요청을 한 번 실행 (P1)

운영자로서 재전달 때문에 정규화 결과가 충돌하거나 같은 실행이 두 번 시작되지 않기를 원한다.

#### 인수 조건

- Given 같은 업로드 재전달 및 바뀐 시계/재시작, When 결과를 다시 발행하면, Then 최초 occurredAt과 전체 payload가 같다.
- Given 같은 executionId 요청 중복, When 동시에 수신하면, Then 실제 처리 점유는 하나다.

### US-2 종료 후 슬롯 순환 (P1)

운영자로서 실제 종료 결과가 전달되면 다음 청크를 배정하고 싶다.

#### 인수 조건

- Given 성공 또는 확실하게 종료한 실패, When 결과를 수신하면, Then 상태와 슬롯을 함께 변경하고 다음 주기에 새 청크를 배정한다.
- Given timeout 또는 종료를 알 수 없는 실행, When 시간이 지나면, Then 슬롯을 유지한다.

### US-3 중복·지연·경쟁 (P1)

운영자로서 중복 결과나 복구 명령이 새 실행의 슬롯을 잘못 반환하지 않기를 원한다.

#### 인수 조건

- Given 결과 재전달/동시 수신/CLI 경쟁, When 처리하면, Then 슬롯은 최대 한 번만 반환한다.
- Given 종료한 이전 시도의 늦은 결과, When 새 실행이 있으면, Then 새 상태와 슬롯은 유지한다.

## 4. 요구사항

### 기능 요구사항 (EARS)

| ID | 요구사항 | 시나리오 |
| --- | --- | --- |
| R-1 | WHEN normalize가 동일 정규화 결과를 재전달하면, THE normalize SHALL 최초 결과 이벤트 전체를 재사용한다. | US-1 |
| R-2 | IF 동일 실행 식별자의 요청 입력이 바뀌면, THEN THE chunk-processor SHALL 기존 실행을 덮어쓰지 않고 충돌 처리한다. | US-1 |
| R-3 | WHEN 같은 executionId를 동시에 수신하면, THE chunk-processor SHALL 실행 원장을 원자적으로 점유하여 하나만 실행한다. | US-1 |
| R-4 | WHEN 시작 기한이 지난 미실행 요청을 수신하면, THE chunk-processor SHALL 작업을 시작하지 않고 종료 실패를 기록한다. | US-1 |
| R-5 | WHEN 실행이 성공하면, THE chunk-processor SHALL 결과 객체 저장 후 종료 기록과 결과 Outbox를 같은 트랜잭션으로 저장한다. | US-2 |
| R-6 | WHEN 실행이 확실히 종료된 실패이면, THE chunk-processor SHALL 실행 식별자와 오류 코드로 종료 실패를 기록한다. | US-2 |
| R-7 | IF 추론 timeout 또는 워커 장애로 종료 여부를 알 수 없으면, THEN THE chunk-processor SHALL 자동 종료 결과를 발행하지 않는다. | US-2 |
| R-8 | WHEN 결과를 재발행하면, THE chunk-processor SHALL 최초 eventId·occurredAt·전체 payload를 유지한다. | US-2 |
| R-9 | WHEN Pipeline이 유효한 현재 실행 결과를 수신하면, THE pipeline-service SHALL 수신 기록·실행 종료·청크 상태·슬롯 반환을 원자적으로 저장한다. | US-2 |
| R-10 | WHEN 같은 결과를 중복 또는 동시에 수신하면, THE pipeline-service SHALL 슬롯을 한 번만 반환한다. | US-3 |
| R-11 | WHEN 이전 실행 또는 수동 종료 뒤의 결과를 수신하면, THE pipeline-service SHALL 무시한 사실만 기록하고 현재 청크·슬롯을 변경하지 않는다. | US-3 |
| R-12 | IF 동일 이벤트 또는 이미 반영한 실행의 결과 내용이 충돌하면, THEN THE pipeline-service SHALL 기존 결과를 덮어쓰지 않는다. | US-3 |
| R-13 | WHEN 복구 CLI와 결과 수신이 경쟁하면, THE pipeline-service SHALL 하나의 종료 경로만 상태·슬롯을 변경하게 한다. | US-3 |
| R-14 | IF 결과 반영 DB 저장이 실패하면, THEN THE pipeline-service SHALL 모든 변경을 롤백하고 성공 offset을 커밋하지 않는다. | US-2 |
| R-15 | WHEN 반환 커밋 이후 배정 주기가 실행되면, THE pipeline-service SHALL 기존 공정성·상한을 적용해 다음 PENDING 청크를 배정한다. | US-2 |

종료 성공은 청크 PROCESSED, 종료 실패는 FAILED다. PROCESSED는 결과 객체 준비를 뜻하며 downstream 적재/전체 Job 완료를 뜻하지 않는다. 실행 상태는 SUCCEEDED/FAILED로 종료한다. 기존 STOPPED·RECOVERY_REQUIRED와 상한 정책을 보존한다.

현재 실행은 원 요청의 jobId/chunkId/normalizationId/sourceId/ownerId/requestId와 일치하고 활성인 executionId다. STOPPED·더 새 시도가 존재하는 실행의 결과는 우선 IGNORED다. 더 새 시도가 없는 현재 실행의 이미 반영된 종료는 아래 중복/충돌 규칙을 따른다. 같은 eventId는 전체 JSONB 입력을 비교하고, 다른 eventId의 같은 실행 결과는 outcome/resultKey/errorCode 의미를 비교한다. 이미 반영한 내용과 다르면 충돌이다. 알 수 없는 실행·식별 불일치는 오류이며 자동 skip하지 않는다.

CLI가 먼저 STOPPED를 확정하면 늦은 결과는 무시한다. 결과가 먼저 종료하면 CLI는 기존 종료를 유지하고 슬롯을 다시 반환하지 않는다. 두 경로는 같은 DB 잠금과 트랜잭션 정책을 쓴다. startBefore 경과만으로 worker 실행이 끝났다고 가정하지 않는다.

워커 원장은 worker 소유 PostgreSQL DB에 둔다. RUNNING 점유는 먼저 내구 커밋하고, 같은 ID를 자동 재점유하지 않는다. 프로세스 중단·종료 저장 실패로 남은 RUNNING은 불명 상태이며 Pipeline 수동 복구 절차가 필요하다. 입력 재전달을 이유로 실제 AI 작업을 중복 실행하지 않는다. 결과 Outbox는 재시작 후에도 독립적으로 발행한다.

normalize는 결과 이벤트를 발행하기 전에 객체 저장소의 조건부 생성으로 보존한다. 재전달은 원 입력·정규화 설정이 같은지 확인하고 저장된 이벤트를 재사용한다. 실제 재정규화는 기존처럼 새 결과 ID·경로를 쓴다. 기존 결과 스냅샷이 없는 과거 발행 건은 최초 payload를 복원할 수 없어 운영 연결 전 별도 확인이 필요하며 offset/수신 기록을 임의로 고치지 않는다.

### 비기능 요구사항

| ID | 요구사항 |
| --- | --- |
| NFR-1 | THE backend SHALL 실제 Kafka·PostgreSQL로 R-9~R-15의 중복/경쟁/롤백을 검증한다. |
| NFR-2 | THE chunk-processor SHALL 실제 Kafka 요청→추출·추론 대역→결과 전달→Pipeline 반환→다음 배정을 통합 테스트로 검증한다. |
| NFR-3 | THE 시스템 SHALL sourceId 키·공통 envelope·traceparent와 정수 ms 구간을 재사용한다. |

## 5. 영향 범위

| 레포 / 서비스 | 변경 개요 | 담당 요구사항 |
| --- | --- | --- |
| ai / normalize·storage | 최초 결과 보존과 재전달 | R-1 |
| ai / chunk-processor·contracts | 새 워커·실행 원장·요청/종료 모델 | R-2~R-8 |
| backend / Pipeline | 종료 수신·상태·슬롯 반환 | R-9~R-15 |
| docs / service-contracts | 종료 이벤트·AsyncAPI·묶음 릴리스 | 전체 |

## 6. 계약 변경

| 계약 파일 | 변경 | 하위호환 |
| --- | --- | --- |
| `service-contracts/events/chunk.execution.finished.schema.json` | 새 v1 종료 이벤트, outcome SUCCEEDED/FAILED, 성공 resultKey 또는 실패 errorCode | 예(추가) |
| `service-contracts/asyncapi/chunk-processor.yaml` | chunk.requested 소비·종료 결과 발행 | 예(추가) |
| `service-contracts/stages/v1/stages.schema.json` | 공통 메시징이 쓰는 chunk-processor.queue_wait/handle 추가 | 예(추가) |
| `service-contracts/VERSION` | 2.3.0 → 2.4.0(종료) → 2.5.0(워커 측정 단계), 소비자 lock 갱신 | 예(추가) |

종료 이벤트는 envelope와 jobId/chunkId/executionId/requestId/normalizationId를 담는다. resultKey는 `sources/<sourceId>/jobs/<jobId>/chunks/<chunkId>/executions/<executionId>/result.json`의 불변 참조다. 모델 output은 별도 스키마 대상으로 추측하지 않는다. chunk.manifest·AI Gateway API는 변경하지 않는다.

## 7. 성공 지표

- 실제 연결에서 반환 후 다음 청크 요청 관측
- 중복 실행·이중 슬롯 반환·늦은 결과의 새 실행 변경 각각 0건
- DB 실패 부분 커밋 0건, 불명 timeout의 자동 반환 0건

## 8. 미결 사항

이번 backend 소유 종료·반환 범위의 미결 사항은 없다. 실제 AI 추론 adapter·출력 스키마·모델 프로필 연동, 원장 RUNNING의 자동 장애 복구·재실행 및 전체 Job 완료는 후속이다. 테스트 추론 대역과 실제 영상 추출을 구분해서 보고한다. 운영 활성화/offset 변경은 하지 않는다.
