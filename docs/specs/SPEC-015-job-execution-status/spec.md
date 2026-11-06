---
id: SPEC-015
title: Job 실행 집계와 소유자 상태 조회
status: Implementing
owner: backend 담당자
repos: [backend, docs]
created: 2026-11-05
updated: 2026-11-05
related: [ADR-0009, SPEC-004, SPEC-008, SPEC-010, SPEC-014]
---

# SPEC-015 Job 실행 집계와 소유자 상태 조회

## 1. 배경과 목적

청크 실행 종료와 슬롯 반환(SPEC-014)을 전체 Job 실행 관점으로 집계한다. [아키텍처](../../architecture/architecture.md)의 ANALYZED·analysis.completed는 segment.indexed·event.manifest·track.manifest 적재 확인이 필요하다. 실행이 끝나도 분석 완료나 검색 준비를 선언하지 않는다.

## 2. 범위

### 포함

- 현재 청크 실행·재시도·불명 상태의 내구 집계, 실행 종료 판정, 실패 원인 조회
- 기존 배정·종료·수동 복구와 같은 트랜잭션의 집계·job.status Outbox
- 누락 집계 점검과 소유자 전용 조회, 실제 워커 경로 검증

### 제외

- Analysis/Search 적재·버전 활성화·analysis.completed·요약·실제 AI·운영 활성화
- 불명 실행 자동 재점유·시간 경과만으로 슬롯 반환·Kafka offset 변경

## 3. 사용자 시나리오

### US-1 실행 진행 확인 (P1)

영상 소유자로서 청크 진행과 실제 실행 종료 여부를 구분해 확인한다.

#### 인수 조건

- Given 두 청크, When 모두 성공, Then 실행 SUCCEEDED·진행률 100이지만 분석 상태는 RUNNING이다.
- Given 종료 불명 청크, When 기한 경과, Then 실행 미종료이며 슬롯을 유지한다.

### US-2 실패와 복구 확인 (P1)

소유자·운영자로서 재시도 중인 실패와 최종 실패를 구분하고 재시작 뒤 누락 집계를 복구한다.

#### 인수 조건

- Given 재시도 예산, When 허용 오류로 실패, Then 실행 미종료·재시도 대기 뒤 새 실행으로 배정한다.
- Given 저장 실패·재시작, When 점검 실행, Then 청크 원장 기준 집계를 복원한다.

## 4. 요구사항

### 기능 요구사항 (EARS)

| ID | 요구사항 | 시나리오 |
| --- | --- | --- |
| R-1 | WHEN Job을 집계하면, THE pipeline-service SHALL 각 청크의 최신 실행과 현재 상태를 한 번만 계산한다. | US-1 |
| R-2 | WHEN 집계를 저장하면, THE pipeline-service SHALL 성공·최종 실패·미배정·재시도 대기·실행 중·종료 불명 개수를 구분한다. | US-1 |
| R-3 | WHEN 모든 청크가 성공 또는 최종 실패이면, THE pipeline-service SHALL 성공·부분 실패·전체 실패로 실행 종료를 저장한다. | US-1 |
| R-4 | WHILE 미배정·재시도 대기·실행 중·종료 불명 청크가 있으면, THE pipeline-service SHALL 실행 미종료를 유지한다. | US-2 |
| R-5 | WHEN 재시도 가능한 확정 실패이면, THE pipeline-service SHALL 남은 예산과 불변 정책에 따라 재시도 대기로 저장한다. | US-2 |
| R-6 | WHEN 재시도 대기 기한이 도달하면, THE pipeline-service SHALL 기존 배정 상한·공정성 아래 새 executionId로 재배정한다. | US-2 |
| R-7 | WHEN 중복·이전 실행 결과를 수신하면, THE pipeline-service SHALL 집계와 상태 순번을 중복 증가시키지 않는다. | US-1 |
| R-8 | WHEN 집계가 변하면, THE pipeline-service SHALL 원본 상태 변경·집계·단조 순번의 job.status Outbox를 같은 트랜잭션에 저장한다. | US-1 |
| R-9 | WHEN 점검기를 실행하면, THE pipeline-service SHALL 원장의 누락·불일치 집계를 복구한다. | US-2 |
| R-10 | WHEN 상태 조회를 요청하면, THE pipeline-service SHALL 소유자만 Job 집계·현재 문제 청크·실패 이력을 조회하게 한다. | US-1 |
| R-11 | WHEN 실행이 종료되면, THE pipeline-service SHALL 적재 확인 전 기존 Job 분석 상태와 활성 Job 제한을 유지한다. | US-1 |
| R-12 | WHEN 종료 불명 또는 타임아웃을 집계하면, THE pipeline-service SHALL 성공 처리·자동 슬롯 반환·자동 재실행을 하지 않는다. | US-2 |

### 집계 의미와 재시도 정책

기존 jobs.status는 분석 생명주기 PLANNED→RUNNING→ANALYZED→COMPLETED를 보존한다. 별도 execution.status는 PENDING/RUNNING/UNKNOWN/SUCCEEDED/PARTIAL_FAILED/FAILED다. UNKNOWN이 다른 미종료 상태보다 우선한다. 성공 수가 전체면 SUCCEEDED, 최종 실패와 성공 혼합이면 PARTIAL_FAILED, 모두 최종 실패면 FAILED다. 실행 종료만으로 ANALYZED·COMPLETED·TIMED_OUT으로 바꾸지 않는다.

진행률은 영상 시간·추론 성공률이 아니라 **확정 종료 청크 수 / 전체 계획 청크 수 × 100의 정수 내림**이다. 확정 종료는 성공+최종 실패다. 재시도 대기·종료 불명은 분자에 넣지 않는다. successPercent는 별도로 성공 수/전체 수이며 실패가 섞인 진행률 100은 성공률 100이 아니다. 순번은 Job별 단조 증가하며 소비자는 jobId+sequence로 오래된 스냅샷을 버린다.

SPEC-010/014에는 자동 작업 재시도 구현이 없으므로 기본 maxAttempts=1(첫 실행 포함), retryableErrorCodes=[]로 기존 동작을 유지한다. 이번에 명시적인 운영 설정의 상한·오류 코드·고정 대기시간을 새 Job에 불변 저장한다. 기존 Job은 1회 정책으로 보존한다. 설정 변경은 이미 생성된 Job을 바꾸지 않는다. 확정 FAILED 결과의 허용 코드이며 실행 수가 maxAttempts보다 작을 때만 RETRY_PENDING이다. 실제 재시도는 새 executionId/requestId/eventId를 사용하고, 같은 실행의 메시지 재전달은 기존 식별자를 유지한다. STOPPED 수동 확인은 자동 재시도 대상이 아닌 최종 실패다. 종료 불명은 예산이 있어도 재시도하지 않는다.

실패 이력은 실행 ID·시도 순서·오류 코드·종료 상태를 유지한다. 현재 문제 청크는 재시도 기한·최신 실행·불명 이유(START_DEADLINE_ELAPSED)·수동 종료 코드(OPERATOR_CONFIRMED_STOP)를 포함한다. 작업자가 임의로 제출한 원문 오류나 복구 증거는 외부 API에 내보내지 않는다. 기존 owner 연결 Job의 집계가 누락되었거나 오래된 경우, 조회는 먼저 소유자를 확인하고 같은 잠금·트랜잭션으로 집계를 보정한 뒤 반환한다. 타인의 조회는 집계나 Outbox를 변경하지 않는다. owner 연결이 없는 SPEC-004 과거 계획은 소유자를 추정하지 않고 조회 404·집계 대상 제외로 둔다.

### 비기능 요구사항

| ID | 요구사항 |
| --- | --- |
| NFR-1 | THE pipeline-service SHALL 동시 마지막 결과·CLI·점검 경쟁에서 이중 전이·부분 커밋 0건을 검증한다. |
| NFR-2 | THE pipeline-service SHALL 실제 Kafka와 추론 대역 워커 경로에서 집계·job.status 발행을 검증한다. |
| NFR-3 | THE pipeline-service SHALL 점검 배치를 1~1000개 Job으로 제한하고 비활성 기본값을 제공한다. |

## 5. 영향 범위

| 레포 / 서비스 | 변경 개요 | 담당 요구사항 |
| --- | --- | --- |
| backend / pipeline-service | 집계·재시도·조회·복구·Outbox | 전체 |
| docs / 계약 | 소유자 조회·job.status 명세 | 전체 |

## 6. 계약 변경

| 계약 파일 | 변경 | 하위호환 |
| --- | --- | --- |
| `service-contracts/openapi/pipeline-service.yaml` | GET /api/v1/jobs/{jobId}/execution | 예(신규) |
| `service-contracts/events/job.status.schema.json` | 분석 status와 별도 execution, 단조 sequence 전체 스냅샷 | 예(신규) |
| `service-contracts/asyncapi/pipeline-service.yaml` | 기존 chunk.requested 보존·job.status 발행 추가 | 예(추가) |
| `service-contracts/VERSION` | 2.5.1 → 2.6.0 | 예 |

기존 개요의 GET /jobs/{sourceId}는 향후 영상별 조회 구상이다. 이번 조회는 jobId(plan_id)별 /jobs/{jobId}/execution으로 구분하며 기존 구상을 교체하지 않는다. analysis.completed는 계약 스키마·발행 구현이 아직 없으며 이번에 만들지 않는다. 향후 적재 확인은 jobId/chunkId와 수락한 executionId·resultKey를 연결하고 모두 준비된 뒤 별도 분석 상태 전이에서 수행한다.

## 7. 성공 지표

- 전체 성공·부분 실패·전체 실패·재시도·불명 상태를 실제 원장과 일치하게 조회
- 동시 마지막 결과 누락 0건, 실패 부분 커밋 0건, analysis.completed 조기 발행 0건

## 8. 미결 사항

이번 실행 집계 범위의 미결 사항은 없다. 적재 완료 이벤트·Analysis/Search 결과 스키마·버전 활성화는 후속 계약에서 정한다. 기본 재시도·기존 운영 활성화·offset을 변경하지 않는다.

## 9. 구현·검증 현황

[backend PR #49](https://github.com/p5-3-final/backend/pull/49)에서 실행 집계·불변 재시도 정책·소유자 조회·bounded 점검을 구현했다. 기존 [backend #47](https://github.com/p5-3-final/backend/pull/47)의 종료 수신과 슬롯 반환, [ai #34](https://github.com/p5-3-final/ai/pull/34)의 실제 추출·종료 Outbox를 재사용한다. ai 코드는 변경하지 않았다.

- 로컬 전체 검사 546개(Pipeline 198개), 실패·오류·건너뜀 0개. 패키징된 복구 CLI smoke도 통과했다.
- 전체 성공·혼합/전체 실패·재시도 예산·지연·이전 실행·동시 마지막 결과·CLI/점검 경쟁·집계/Outbox 롤백·누락 복구·소유자 API·JSON 계약을 검증했다.
- 실제 normalize·추론 대역 워커·Kafka·서로 다른 PostgreSQL·객체 저장소를 연결했다. 커밋한 종료 job.status의 eventId가 Kafka에 도착하는지 검증하며 중간 상태·중복 전달을 고정 메시지 수로 오판하지 않는다.

실행 종료여도 분석 status RUNNING과 활성 Job 제한을 유지한다. 후속 Analysis/Search는 수락한 executionId·resultKey에 대한 적재 확인을 설계하고, 그 확인 뒤 분석 상태·버전 활성화·analysis.completed 경로를 연결해야 한다. 실제 AI·운영 활성화·기존 offset 변경·배포는 수행하지 않아 Done으로 표시하지 않는다.
