---
id: SPEC-008
title: 정규화 완료 수신과 계획 저장
status: Implementing
owner: backend 담당자
repos: [backend]
created: 2026-11-03
updated: 2026-11-03
related: [SPEC-004, ADR-0002, ADR-0008, ADR-0009]
---

# SPEC-008 정규화 완료 수신과 계획 저장

## 1. 배경과 목적

SPEC-004의 청크 계산·Job/Chunk 저장을 video.normalized 수신에 연결한다. normalize와 chunk-processor를 포함한 영상 처리 파이프라인은 backend가 담당하고 AI팀은 모델 추론을 담당한다. 기존 초안의 전체 청크 요청 Outbox 선기록은 폐기한다. 책임·배정 경계는 [ADR-0009](../../adr/0009-pipeline-dispatch-boundary.md), 상세 설계는 backend의 specs/SPEC-008-normalized-intake/plan.md에 둔다.

원격 main의 SPEC-006은 원본 영상 재생이다. PR #40의 Pipeline 초안을 SPEC-008로 이동했으며 기존 재생 명세는 수정하지 않는다.

## 2. 범위

### 포함

- backend 소유 video.normalized 계약에 따른 입력 검증·수신 기록
- 불변 normalizationId와 분석 설정을 이용한 Job 재사용
- 정규화 수신 처리 기록·Job·Chunk의 원자적 저장 및 재조회
- eventId 기반 재전달과 의미상 동일 결과의 동시 중복 방지
- SPEC-004 구간 계산·입력 비교·영상당 활성 Job 최대 1개 정책 유지

### 제외

- 배정기, 실행 슬롯, executionId 생성, chunk.requested Outbox 기록·발행 구현
- normalize·chunk-processor 및 AI 서버의 런타임 구현
- 실행 임대·장애 복구·완료/실패 반영 구현 (후속 설계만 포함)
- 기존 v3 검색·위험 상태·모델·프로필 구조의 임의 교체

계획이 있으나 요청 Outbox가 없는 미배정 상태는 정상이다. 재전달을 이유로 청크 요청을 생성하지 않는다.

## 3. 사용자 시나리오

### US-1 정규화 후 계획 준비 (P1)

backend 개발자로서 유효한 정규화 결과로 미배정 계획을 만들고 싶다.

#### 인수 조건

- Given 유효한 정규화 완료 입력, When 처리하면, Then 수신 완료 기록과 Job·Chunk 계획이 함께 저장된다.
- Given 생성 직후 계획, When 조회하면, Then 청크 요청 Outbox와 실행 시도는 0건이다.

### US-2 중복과 장애 복구 (P1)

운영자로서 메시지가 다시 오거나 처리 도중 실패해도 계획이 중복되거나 입력이 덮어써지지 않기를 원한다.

#### 인수 조건

- Given 같은 eventId와 같은 입력, When 재전달되면, Then 저장 건수가 늘지 않는다.
- Given 새 eventId이지만 같은 normalizationId와 분석 설정, When 처리하면, Then 기존 Job을 재사용한다.
- Given 저장 실패, When 재전달되면, Then 부분 커밋 없이 다시 처리할 수 있다.

## 4. 요구사항

### 기능 요구사항 (EARS)

| ID | 요구사항 | 시나리오 |
| --- | --- | --- |
| R-1 | WHEN video.normalized를 수신하면, THE pipeline-service SHALL 공통 envelope와 확정된 backend 계약으로 입력을 검증한다. | US-1 |
| R-2 | WHEN 새 계획을 계산하면, THE pipeline-service SHALL SPEC-004의 구간 길이·겹침·영상 경계 규칙을 적용한다. | US-1 |
| R-3 | WHEN 정규화 수신 처리를 커밋하면, THE pipeline-service SHALL 수신 완료 기록과 Job·Chunk를 같은 트랜잭션으로 보존한다. | US-1 |
| R-4 | WHEN 계획을 생성하면, THE pipeline-service SHALL chunk.requested Outbox를 생성하지 않는다. | US-1 |
| R-5 | WHEN 같은 정규화 결과와 같은 분석 설정을 받으면, THE pipeline-service SHALL 기존 Job을 재사용한다. | US-2 |
| R-6 | IF 같은 식별자에 다른 입력이 오면, THEN THE pipeline-service SHALL 기존 입력을 덮어쓰지 않고 충돌 처리한다. | US-2 |
| R-7 | WHEN 다른 계획 생성을 시도하면, THE pipeline-service SHALL 영상당 활성 Job 최대 1개 제한을 유지한다. | US-2 |
| R-8 | WHEN 같은 eventId와 같은 입력을 재수신하면, THE pipeline-service SHALL 새로운 계획을 추가하지 않는다. | US-2 |
| R-9 | IF 수신 기록 또는 계획 저장이 실패하면, THEN THE pipeline-service SHALL 해당 처리의 신규 저장 전체를 취소한다. | US-2 |
| R-10 | WHEN DB 커밋에 성공하면, THE pipeline-service SHALL 그 이후에만 해당 입력의 성공 offset 처리를 허용한다. | US-2 |
| R-11 | WHEN 동일 결과·설정의 요청이 동시에 오면, THE pipeline-service SHALL 하나의 논리적 Job만 저장한다. | US-2 |
| R-12 | WHEN 정규화 입력과 청크 구간을 전달하면, THE pipeline-service SHALL 정규화 영상 시작 기준 정수 밀리초와 시작 포함·끝 제외 규칙을 사용한다. | US-1 |

분석 설정은 청크 길이·겹침·프로필 및 추론 프로필의 불변 버전처럼 계획·결과에 영향을 주는 값을 포함한다. eventId는 메시지 ID이며 Job ID가 아니다. 기존 SPEC-004 입력 비교를 없애지 않고 정규화 결과·설정 버전 검증을 추가하는 후속 변경이다. 기존 구현의 소수 초 DB 저장은 이미 밀리초로 바뀌었다고 서술하지 않는다.

| R-13 | WHEN 유효한 REJECTED 결과를 수신하면, THE pipeline-service SHALL 정규화 결과와 수신 사실만 저장하고 Job을 생성하지 않는다. | US-1 |

### 비기능 요구사항

| ID | 요구사항 |
| --- | --- |
| NFR-1 | THE pipeline-service SHALL R-1~R-13 각각에 최소 1개의 자동화 검증을 제공한다. |
| NFR-2 | THE pipeline-service SHALL 이번 통합 검증에서 청크 발행·영상 추출·AI 호출을 각각 0회 수행한다. |
| NFR-3 | THE pipeline-service SHALL 커밋 전 실패와 커밋 후 재전달 시나리오를 실제 PostgreSQL·Kafka로 검증한다. |

## 5. 영향 범위

| 레포 / 서비스 | 변경 개요 | 담당 |
| --- | --- | --- |
| backend / pipeline-service | 수신·계획 저장, 의미상 중복 방지 | backend |
| normalize / chunk-processor | 영상 처리 책임과 메시지 생산·소비 설계. 기존 ai 레포 경로는 물리적 배치일 뿐 담당 경계가 아님 | backend |
| AI 추론 서버 | 내부 HTTP 추론 기능. 실제 서버·Adapter 연결은 후속 확정 | AI팀 |
| docs | 책임·시간·배정 경계와 후속 설계 정합성 | backend |

## 6. 계약 변경

이 문서는 의미 기준 초안이다. 이번에 video.normalized JSON Schema·normalize AsyncAPI를 확정하며, 실행 요청·추론 계약은 후속이다. 기존 envelope의 eventId/sourceId/ownerId(UUID), eventType(토픽 이름), schemaVersion, occurredAt과 traceparent를 재사용한다. sourceId를 Kafka 키로 쓴다.

| 메시지 / API | 의미 초안 | 후속 문서 |
| --- | --- | --- |
| video.normalized | normalizationId, 불변 정규화 객체 참조, durationMs(양의 정수 밀리초), normalizationVersion | backend가 이벤트 스키마·AsyncAPI 작성 |
| chunk.requested | jobId/chunkId/executionId, normalizationId, 정규화 객체 참조, ownedRange, processingRange, processingProfile | 배정기 후속 명세에서 작성 |
| 완료·실패 이벤트 | 실행 식별자와 결과 참조 / 오류 코드 | 기존 chunk.manifest는 건수 보고이며 실행 완료 계약으로 간주하지 않음. 새 후보만 plan에 기록 |
| POST /v1/inferences | requestId↔executionId, 준비된 청크 객체 참조 input, 불변 추론 profile. 응답 requestId/modelVersion/outputSchemaVersion/output | AI팀과 output 의미·중복 제어 협의 후 OpenAPI 작성 |

객체 참조는 영상 바이트나 임시 presigned URL을 의미하지 않는다. 저장소 위치·버전 표현과 ID의 실제 타입은 backend의 후속 계약에서 정한다. 기존 plan_id(UUID)·Chunk 내부 BIGINT를 외부 ID로 무조건 노출하지 않는다. 결과 output의 검출·설명·임베딩 구조는 별도 결과 스키마 대상이다.

## 7. 성공 지표

- 유일 제약·트랜잭션으로 동일 정규화 결과·설정의 동시 생성이 Job 1건으로 수렴
- 계획 생성·재전달 후 청크 요청 Outbox 0건
- 수신 완료 기록만 또는 계획만 저장되는 부분 커밋 0건
- 밀리초 경계·SPEC-004 활성/중복 정책 회귀 검증 통과
- 계약·필수 검사 통과 후에만 구현 착수

## 8. 확정 정책과 후속 사항

- 동시 작업으로 기존 video.normalized v1 계약이 먼저 머지되어 v1은 그대로 보존한다. v2 스키마와 기존 토픽의 버전 합집합으로 추가한다. Pipeline은 v2만 수신 처리하고 v1은 성공 처리하지 않는다. 생산자는 v2 발행으로 전환해야 이 경로와 연결된다.

- 이번 수신·계획 범위의 미결 사항은 없다. 영상 정규화 SPEC-007과 사용자 확인으로 호환 보완했다.
- READY만 계획한다. REJECTED는 수신 기록·정규화 결과만 저장하며 Job은 없다.
- normalizationId는 UUID, 객체 참조는 기존 normalizedKey/hlsPlaylistKey이며 `sources/<sourceId>/normalizations/<normalizationId>/` 아래의 불변 key다. URL·바이트는 받지 않는다.
- durationMs는 양의 signed 64-bit 정수이고 durationSec와 정확히 일치해야 한다. 내부 SPEC-004 계산은 BigDecimal.valueOf(durationMs,3)로 정확히 재사용한다. 운영 길이 상한은 설정(기본 4시간)으로 관리한다. 기존 데이터의 소수 초 단위는 변경하지 않는다.
- 분석 설정은 backend의 불변 profileVersion, production/local 모드와 inferenceProfileVersion이다. 같은 설정 버전의 정의 변경은 충돌이다. 재전달 eventId는 최초 결과를 재사용하며 운영 설정이 바뀌었다고 새 Job을 만들지 않는다. 새 eventId는 현재 설정으로 의미상 Job을 찾는다.
- 기존 SPEC-004 계획에는 정규화 ID를 자동 백필하지 않는다. 활성 legacy Job이 있으면 충돌 처리하고 수신 전체를 롤백한다. 종료된 legacy Job은 보존하고 새 정규화 연결 계획을 만든다.
- 실패한 입력은 성공 offset을 커밋하지 않고 같은 파티션에서 재시도한다. 자동 DLQ/skip은 이번 범위에 없고 잘못된 입력·충돌은 운영자가 수정·해소해야 한다.
- 후속 AI 입력·output·프로필/모델·오류·timeout·requestId 중복 제어 협의는 실행 기능의 선행 조건이다. 이번 intake를 차단하지 않는다.

### 구현 결과

backend #36은 실제 수신 코드·additive migration·계약 검증·PostgreSQL/Kafka 통합 테스트를 포함해 머지됐다. 로컬 전체 backend 386개(Pipeline 99개)와 GitHub 필수 CI가 통과했다. 수신은 opt-in이며 producer의 v2 발행·운영 토픽/offset 설정·배포는 별도 연결 사항이다. 요청 Outbox·배정·슬롯·실행·영상 처리·AI는 추가하지 않았다. 배포까지 끝난 상태가 아니므로 Done으로 표기하지 않는다.
