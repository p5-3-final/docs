---
id: SPEC-008
title: 정규화 완료 수신과 계획 저장
status: Draft
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

- backend 소유 video.normalized 계약 초안 정리와 입력 검증 설계
- 불변 normalizationId와 분석 설정을 이용한 Job 재사용
- 정규화 수신 처리 기록·Job·Chunk의 원자적 저장 및 재조회
- eventId 기반 재전달과 의미상 동일 결과의 동시 중복 방지
- SPEC-004 구간 계산·입력 비교·영상당 활성 Job 최대 1개 정책 유지

### 제외

- 이번 요청의 애플리케이션 코드·DB 마이그레이션·계약 스키마 수정
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

### 비기능 요구사항

| ID | 요구사항 |
| --- | --- |
| NFR-1 | THE pipeline-service SHALL R-1~R-12 각각에 최소 1개의 자동화 검증을 제공한다. |
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

이 문서는 의미 기준 초안이다. 이번 요청에서는 JSON Schema·AsyncAPI·OpenAPI를 생성하거나 수정하지 않는다. 기존 envelope의 eventId/sourceId/ownerId(UUID), eventType(토픽 이름), schemaVersion, occurredAt과 traceparent를 재사용한다. sourceId를 Kafka 키로 쓴다.

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

## 8. 미결 사항

- [NEEDS CLARIFICATION: AI 입력 규격·프로필/모델 버전·결과 스키마와 시간 의미·오류 코드·추론 제한 시간·requestId 중복 제어 응답을 AI팀과 협의해야 한다. 이번 intake 구현의 선행 조건과 후속 실행 기능의 선행 조건은 plan에서 분리한다.]
- backend의 객체 참조 직렬화, 정규화 버전·설정의 정규 표현, 새 식별자의 실제 타입·마이그레이션은 후속 계약/plan에서 확정해야 한다. AI팀 소관으로 돌리지 않는다.
- Draft plan은 사용자의 문서 전용 요청에 따른 검토 자료다. 이 초안·미정 계약으로 기능 코드를 작성하지 않는다.
