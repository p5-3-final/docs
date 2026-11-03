---
id: SPEC-010
title: Pipeline 공정 배정과 실행 슬롯·요청 발행
status: Approved
owner: backend 담당자
repos: [backend, docs]
created: 2026-11-03
updated: 2026-11-03
related: [SPEC-004, SPEC-007, SPEC-008, ADR-0002, ADR-0009]
---

# SPEC-010 Pipeline 공정 배정과 실행 슬롯·요청 발행

## 1. 배경과 목적

[SPEC-008](../SPEC-008-normalized-intake/spec.md)은 수신 기록과 계획만 저장한다. [ADR-0009](../../adr/0009-pipeline-dispatch-boundary.md)의 배정 경계를 구현해 처리 상한 안에서만 청크 요청을 발행한다. PRD 에픽은 아직 정의되지 않았다. 사용자 요청으로 명세·계약·DB 변경 및 검사 후 직접 머지까지 진행하며 별도 승인 리뷰가 있었다고 기록하지 않는다.

## 2. 범위

### 포함

- 정규화 결과·소유자·불변 분석 설정이 연결된 활성 Job의 PENDING 청크 배정
- 사용자·영상·전체 동시 처리 상한과 사용자 순환 공정성
- 실행 시도·슬롯·청크 상태·요청 Outbox의 원자적 저장
- 기존 Publisher와 검증용 Kafka 소비자를 통한 최소 한 번 전달 검증
- 만료 실행의 복구 대기 표시, 종료 확인 증거를 남기는 멱등 슬롯 반환 및 운영 명령

### 제외

- 영상 추출·AI 추론·worker 구현·완료/실패 이벤트·Job 완료 판정
- 자동 재실행, 실행 중 heartbeat·임대 갱신·분산 fencing 프로토콜
- 정규화 producer 구현, 운영 활성화·기존 offset 변경·배포
- 정규화 연결이 없는 legacy 계획의 자동 백필·배정

## 3. 사용자 시나리오

### US-1 제한된 공정 배정 (P1)

운영자로서 한 사용자의 영상들이 다른 사용자를 굶기거나 처리량 상한을 넘지 않기를 원한다.

#### 인수 조건

- Given 여러 사용자와 영상의 계획, When 배정을 반복하면, Then 처리 가능한 사용자에게 한 청크씩 순환 배정한다.
- Given 같은 DB의 두 배정 서버, When 동시에 배정하면, Then 같은 청크의 활성 실행은 한 개이고 세 단계 상한을 넘지 않는다.

### US-2 전달·장애와 회수 (P1)

운영자로서 부분 저장 없이 요청을 보내고 미확인 실행을 안전하게 회수하고 싶다.

#### 인수 조건

- Given 배정 저장 중 실패, When 롤백하면, Then 청크·실행·슬롯·Outbox가 모두 원래 상태다.
- Given 발행 후 DB 기록 전 장애, When Publisher가 재시작하면, Then 같은 eventId·executionId의 재전달만 발생한다.
- Given 만료 실행, When 시간만 지나면, Then 복구 대기이며 슬롯은 보존한다. 종료 증거를 확인한 운영 명령 후에만 반환한다.

## 4. 요구사항

### 기능 요구사항 (EARS)

| ID | 요구사항 | 시나리오 |
| --- | --- | --- |
| R-1 | WHEN 배정을 요청하면, THE pipeline-service SHALL 정규화·분석 설정이 연결되고 Job이 PLANNED 또는 RUNNING인 PENDING 청크만 선택한다. | US-1 |
| R-2 | WHEN 실행을 배정하면, THE pipeline-service SHALL 사용자별·영상별·전체 슬롯 상한을 각각 지킨다. | US-1 |
| R-3 | WHEN 복수 서버가 동시에 배정하면, THE pipeline-service SHALL 청크당 활성 실행을 최대 한 개로 유지한다. | US-1 |
| R-4 | WHEN 처리 가능한 사용자가 계속 대기하면, THE pipeline-service SHALL 직전 배정 순서를 영속화하여 사용자별 한 청크씩 순환 선택한다. | US-1 |
| R-5 | WHEN 배정을 커밋하면, THE pipeline-service SHALL 실행 시도·슬롯 점유·청크 DISPATCHED 상태·요청 Outbox를 한 트랜잭션으로 저장한다. | US-1 |
| R-6 | WHEN 요청을 발행하면, THE pipeline-service SHALL 공통 envelope·sourceId 키·traceparent와 확정된 chunk.requested 계약을 따른다. | US-2 |
| R-7 | WHEN 발행을 재시도하면, THE pipeline-service SHALL 최초 eventId·executionId·requestId와 입력을 유지한다. | US-2 |
| R-8 | IF 배정 중 DB 저장이 실패하면, THEN THE pipeline-service SHALL 이번 배정의 모든 상태·슬롯·Outbox 변경을 롤백한다. | US-2 |
| R-9 | WHEN 요청 발행이 실패하거나 발행 확인 전 프로세스가 재시작하면, THE pipeline-service SHALL 기존 Outbox Publisher로 미확인 요청을 재발행한다. | US-2 |
| R-10 | WHEN 실행의 startBefore 시각이 지나면, THE pipeline-service SHALL 실행을 RECOVERY_REQUIRED로 표시하고 슬롯을 유지한다. | US-2 |
| R-11 | WHEN 만료 실행의 종료 확인과 증거를 운영자가 제출하면, THE pipeline-service SHALL 실행 종료·청크 FAILED 전이·슬롯 반환을 원자적으로 한 번만 수행한다. | US-2 |
| R-12 | IF 종료 확인 식별자 또는 증거가 기존 기록과 충돌하면, THEN THE pipeline-service SHALL 기존 실행·슬롯·종료 기록을 변경하지 않는다. | US-2 |
| R-13 | WHEN 스케줄러를 기본 설정으로 시작하면, THE pipeline-service SHALL 자동 배정을 비활성화한다. | US-1 |

상한은 양의 운영 설정이고 기본값은 사용자 2, 영상 1, 전체 4다. 자동 주기는 1초, 한 주기 최대 100건이다. 같은 DB의 설정을 하나의 활성 구성으로 검증해 서로 다른 Pod의 상한 설정이 섞이면 배정을 거부한다. 안전하게 상한을 바꿀 때는 배정을 끄고 슬롯을 모두 반환한 뒤 새 구성으로 재시작한다.

공정성은 실행 가능한 사용자별 마지막 배정 순서가 가장 오래된 사용자를 택한다. 동일 사용자 안에서는 가장 오래된 Job, 그 안에서는 청크 순번 순서다. 상한에 막힌 사용자는 건너뛴다. 가중치·선점·사용자 내부 영상 순환은 포함하지 않는다.

식별: jobId는 기존 plan_id(UUID), chunkId는 새 불변 UUID(내부 BIGINT PK를 노출하지 않음), executionId는 실행 시도 UUID, requestId는 executionId와 같다. eventId는 별도의 메시지 UUID다. Outbox 재전달은 이 값을 유지한다. 실제 재실행은 새 executionId를 요구하지만 재시도 배정은 이번에 구현하지 않는다.

기존 NUMERIC 초를 정수 밀리초로 정확히 변환하며 반올림하지 않는다. 정규화 미연결 계획은 배정 대상이 아니다. processingProfile은 SPEC-008의 저장된 설정 버전·모드·추론 프로필 버전을 사용한다. 모델 출력·차원은 정하지 않는다.

### 슬롯 종료·복구 경계

startBefore는 배정 후 기본 5분의 새 실행 시작 기한이며 AI 실행 제한 시간이 아니다. 기한 경과는 실행 종료의 증거가 아니다. 발행 전이라도 전송 후 커밋 실패 가능성이 있으므로 published_at=null만으로 슬롯을 회수하지 않는다. 만료 확인은 주기 작업과 운영 명령에서 수행하고 복구 대기 건수를 메트릭으로 제공한다.

운영 명령은 worker가 종료됐거나 시작하지 않았음을 별도로 확인한 사람이 executionId·confirmationId(UUID)·evidence(비밀값 없는 증거 참조)를 제출하는 제한된 복구 경로다. 기한 이전 반환, 다른 실행의 반환, 증거 없는 반환은 거부한다. 같은 확인은 재시도해도 한 번만 반환한다. 결과 성공으로 기록하지 않고 FAILED로 종료한다. 정상 성공 결과·완료 이벤트 연동은 후속이며 현재 상태로 실서비스 처리 완료를 주장하지 않는다.

후속 worker는 executionId의 원자적 점유·동일 ID의 입력 비교·내구성 있는 중복 흡수와 startBefore 이후 신규 시작 거부를 구현해야 한다. Kafka의 지연·중복을 발행기에서 없애지 않는다. 이 요구는 신규 backend 요청 계약이며 실제 worker가 이미 구현했다는 가정이 아니다. 검증 소비자로만 확인한다.

### 비기능 요구사항

| ID | 요구사항 |
| --- | --- |
| NFR-1 | THE pipeline-service SHALL R-1~R-13을 실제 PostgreSQL 기반 자동화 테스트로 검증한다. |
| NFR-2 | THE pipeline-service SHALL Kafka 발행·재전달을 실제 Kafka와 계약 검증 소비자로 검증한다. |
| NFR-3 | THE pipeline-service SHALL 복구 대기 슬롯 수를 pipeline.dispatch.recovery.required 메트릭으로 제공한다. |

## 5. 영향 범위

| 레포 / 서비스 | 변경 개요 | 담당 요구사항 |
| --- | --- | --- |
| backend / pipeline-service | 배정·슬롯 원장·복구 명령·공통 Outbox 재사용 | R-1~R-13 |
| docs | 신규 요청 스키마·AsyncAPI·설계 경계 정리 | R-6 |
| chunk-processor | 후속 계약 소비자. 이번에는 검증용 소비자로 대체 | 후속 |

## 6. 계약 변경

| 계약 파일 | 변경 | 하위호환 |
| --- | --- | --- |
| `docs/contracts/events/chunk.requested.schema.json` | 신규 v1 요청. 객체 key·소유/처리 구간·프로필·시도·시작 기한 | 예(추가) |
| `docs/contracts/asyncapi/pipeline-service.yaml` | 신규 발행 계약. sourceId Kafka 키 | 예(추가) |

저장소 key는 SPEC-008 normalizedKey를 재사용한다. 저장소 endpoint·bucket·접근 권한은 worker 배포 설정으로 연결하며 메시지에 자격 증명·presigned URL을 넣지 않는다. 구간은 정규화 영상 시작 기준 정수 ms, 시작 포함·끝 제외다. 완료/실패 이벤트는 기존 계약이 없어 이번에 임의 토픽을 만들지 않는다.

## 7. 성공 지표

- 다중 배정·복구에도 상한 초과 및 중복 활성 실행 0건
- DB 장애 시 부분 커밋 0건
- 발행 실패·재시작에도 검증 소비자의 논리 실행 1건
- 만료만으로 슬롯 반환 0건, 종료 확인 후 슬롯 잔존 0건

## 8. 미결 사항

이번 backend 배정·발행·수동 복구 범위에 미결 사항은 없다. worker의 내구 중복 제어·완료/실패 계약·정상 슬롯 반환·heartbeat/fencing·자동 재시도 및 producer v2 실제 연결은 후속 연동이며 이번 구현 완료에 포함하지 않는다. 자동 배정은 운영 활성화하지 않는다.

저장소 확인 결과: ai origin/main의 normalize는 .gitkeep뿐이다. producer v2 구현이 머지되지 않았고 로컬 compose에도 pipeline 자동 수신 연결이 없다. SPEC-008 수신기는 opt-in이다. 테스트에서 만든 v2 입력은 실제 정규화 producer 연결의 증거가 아니다.
