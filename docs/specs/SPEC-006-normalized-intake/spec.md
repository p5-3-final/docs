---
id: SPEC-006
title: 정규화 완료 수신과 청크 요청 Outbox 기록
status: Draft
owner: backend 담당자
repos: [backend, ai]
created: 2026-11-03
updated: 2026-11-03
related: [SPEC-003, SPEC-004, ADR-0002, ADR-0005, ADR-0007]
---

# SPEC-006 정규화 완료 수신과 청크 요청 Outbox 기록

## 1. 배경과 목적

SPEC-004로 청크 소유·확장 구간 계산과 Job·Chunk 계획 저장을 구현했다. 현재 내부 유스케이스만 있어 normalize가 끝나도 계획을 자동 생성하지 않는다. 정규화 완료 수신을 기존 계획 기능에 연결하고, 청크 처리 요청을 DB에 내구성 있게 기록하는 것이 목적이다.

이 초안은 AI팀과 합의해야 하는 계약의 의미와 backend 내부 정책을 구분한다. 미확정 payload의 필드명·타입·필수 여부·예시 JSON은 작성하지 않는다. PRD의 상위 에픽은 아직 정의되지 않았다.

근거: [아키텍처](../../architecture/overview.md), [서비스 카탈로그](../../architecture/service-catalog.md), [SPEC-004](../SPEC-004-pipeline-job-planning/spec.md).

## 2. 범위

### 포함

- 합의된 계약에 따른 video.normalized 수신·검증
- 기존 청크 계산 및 계획 저장 기능 연결
- 입력 이벤트의 중복 수신과 동일 계획 재요청 처리
- Job·Chunk 계획, 수신 처리 결과, 청크 요청 Outbox 기록의 원자성
- 장애·재시작·재전달 후의 저장 상태 검증
- 계약 확정 후 JSON Schema·AsyncAPI와 생산자/소비자 테스트 연결

### 제외

- normalize와 chunk-processor의 실제 영상 처리 구현
- 공정성 스케줄러·작업 배정·실행 상태 전이·완료 판정 구현
- 운영 워커로의 청크 요청 발행·실제 실행 (미결 B-1 해결 전)
- 외부 HTTP API, frontend, 검색·분석·알림 기능
- AI 모델·벡터 차원 확정, 비용 승인·상한 정책의 신규 구현
- 운영 인프라와 배포 리소스 변경

Outbox 저장은 Kafka 전송 성공 또는 워커 처리 완료를 뜻하지 않는다. 여러 번 전달되는 Kafka 특성은 유지하며, 물리적인 메시지 전송을 정확히 한 번으로 보장한다고 표현하지 않는다.

## 3. 사용자 시나리오

### US-1 정규화 후 계획 준비 (P1)

backend 개발자로서 정규화 완료를 받으면 해당 영상의 처리 계획과 요청 기록이 함께 남기를 원한다. 워커와 실제 영상을 실행하지 않고도 처리 시작 경로를 검증하기 위해서다.

#### 인수 조건

- Given 계약에 맞는 정규화 완료 입력과 허용되는 작업 생성 조건, When 처리하면, Then SPEC-004의 계산 결과와 합의된 청크 요청 기록이 함께 커밋된다.
- Given 저장 완료 상태, When 별도 트랜잭션에서 조회하면, Then 수신 이벤트와 계획·Outbox 사이의 연결을 확인할 수 있다.

### US-2 중복과 부분 실패에서 복구 (P1)

운영자로서 같은 이벤트가 다시 전달되거나 저장 도중 실패해도 중복 계획·요청이 누적되지 않기를 원한다.

#### 인수 조건

- Given 이미 커밋한 동일 이벤트, When 다시 수신하면, Then Job·Chunk·논리적 Outbox 요청 수가 늘지 않는다.
- Given 계획 또는 Outbox 저장 실패, When 트랜잭션이 끝나면, Then 해당 처리의 신규 저장과 수신 완료 표시가 모두 취소된다.
- Given 커밋 후 Kafka offset 기록 전 중단, When 재전달되면, Then 커밋한 계획과 요청을 다시 만들지 않는다.

### US-3 실행을 시작하지 않는 저장 검증 (P1)

backend 개발자로서 작업 배정이 없는 이번 단계가 공정성·처리량 제한을 우회하지 않기를 원한다.

#### 인수 조건

- Given 이번 기능만 활성화된 환경, When Outbox 기록 검증을 실행하면, Then 운영 chunk-processor의 실행을 유발하지 않는다.
- Given 공통 Outbox 발행기를 사용하는 환경, When 발행을 연결하려 하면, Then B-1의 범위 충돌을 해결한 명세·계약이 먼저 필요하다.

## 4. 요구사항

다음은 초안 요구사항이다. AI팀 계약과 아래 미결 사항이 확정되기 전에는 구현 기준으로 승격하지 않는다. US-1의 요청 건수·식별 규칙은 A-2에서 정하며, 여기서 청크당 메시지 개수나 묶음 형식을 확정하지 않는다.

### 기능 요구사항 (EARS)

| ID | 요구사항 | 시나리오 |
| --- | --- | --- |
| R-1 | WHEN video.normalized를 수신하면, THE pipeline-service SHALL 확정된 버전의 계약에 따라 입력을 검증한다. | US-1 |
| R-2 | WHEN 유효한 정규화 완료 입력으로 새 계획을 만들면, THE pipeline-service SHALL SPEC-004의 프로필·구간 계산 정책을 적용한다. | US-1 |
| R-3 | WHEN 허용되는 신규 정규화 완료 처리를 커밋하면, THE pipeline-service SHALL Job·Chunk 계획과 계약에 맞는 청크 요청 기록을 함께 보존한다. | US-1 |
| R-4 | WHEN 처리 결과를 보존하면, THE pipeline-service SHALL 수신 이벤트와 생성 계획·요청 기록 사이의 추적 관계를 보존한다. | US-1 |
| R-5 | WHEN 이미 처리 완료한 같은 eventId를 재수신하면, THE pipeline-service SHALL 해당 이벤트의 신규 계획·논리적 요청 기록을 추가하지 않는다. | US-2 |
| R-6 | IF 계획 저장 또는 청크 요청 기록 중 하나라도 실패하면, THEN THE pipeline-service SHALL 해당 처리의 신규 저장 전체를 취소한다. | US-2 |
| R-7 | IF DB 처리가 커밋되지 않았으면, THEN THE pipeline-service SHALL 해당 입력을 성공 처리한 것으로 offset을 기록하지 않는다. | US-2 |
| R-8 | WHEN 동일 계획으로 판정되는 입력을 처리하면, THE pipeline-service SHALL SPEC-004의 동일 입력 재사용·다른 입력 충돌 정책을 유지한다. | US-2 |
| R-9 | WHEN 같은 영상에 다른 계획 생성을 요청하면, THE pipeline-service SHALL SPEC-004의 영상당 활성 Job 최대 1개 제한을 유지한다. | US-2 |
| R-10 | WHEN 같은 입력 이벤트를 동시에 수신하면, THE pipeline-service SHALL 해당 이벤트에 대한 하나의 논리적 처리 결과만 커밋한다. | US-2 |
| R-11 | WHEN 청크 요청을 Outbox에 기록하면, THE pipeline-service SHALL 재전송 시 같은 요청의 eventId를 유지한다. | US-2 |
| R-12 | WHILE 실행 허용과 배정 정책이 이번 기능에 연결되지 않았으면, THE pipeline-service SHALL 이번 저장 검증이 운영 청크 실행을 유발하지 않게 한다. | US-3 |

### 비기능 요구사항

| ID | 요구사항 |
| --- | --- |
| NFR-1 | THE pipeline-service SHALL R-1~R-12에 대해 각각 최소 1개의 자동화 검증을 제공한다. |
| NFR-2 | THE pipeline-service SHALL 이번 기능의 통합 테스트에서 외부 AI API와 실제 영상 처리 호출을 각각 0회 수행한다. |
| NFR-3 | THE pipeline-service SHALL PostgreSQL·Kafka 통합 검증에서 정상 수신, 재전달, 동시 중복, 저장 실패, 커밋 후 재전달 사례를 모두 검증한다. |

## 5. 영향 범위

| 레포 / 서비스 | 변경 개요 | 담당 요구사항 |
| --- | --- | --- |
| backend / pipeline-service | 수신 경계, 계획 연결, 중복 처리, 트랜잭션·Outbox 기록 | R-1~R-12, NFR-1~NFR-3 |
| backend / common-messaging | 기존 기록기 재사용 검토. 동작 변경 필요 시 별도 영향 검토 | R-3, R-11, R-12 |
| ai / normalize | video.normalized 생산자 계약과 샘플·계약 테스트 합의 | R-1, R-4, R-8의 전제 |
| ai / chunk-processor | chunk.requested 소비자 계약·재시도 의미 합의 | R-3, R-11, R-12의 전제 |
| docs | 미결 사항 정리 후 명세·이벤트 계약 확정 | 전체 |

AI팀 서비스 코드 구현은 이번 backend 작업에 자동 포함하지 않는다. 다른 서비스의 DB를 직접 조회하거나 FK로 연결하지 않는다.

## 6. 계약 변경

아래 파일은 합의 후 작성할 후보이며 아직 존재하지 않는다. 이름은 현재 문서의 토픽 이름에 따른 작성 위치이고 payload 확정을 뜻하지 않는다. 이 초안 작업에서는 계약 파일을 수정하지 않는다.

| 계약 후보 | 생산자 → 소비자 | 확정할 내용 |
| --- | --- | --- |
| events/video.normalized.schema.json | normalize → pipeline-service | 정규화 결과의 의미·참조·영상 길이·식별·버전 |
| asyncapi/normalize.yaml | normalize → pipeline-service | 채널·키·헤더·재전달 규칙 |
| events/chunk.requested.schema.json | pipeline-service → chunk-processor | 실행 입력·구간·식별·프로필·중복 의미 |
| asyncapi/pipeline-service.yaml | pipeline-service → chunk-processor | 채널·요청 단위·순서・발행 허용 조건 |

### 이미 확정되어 재사용할 기준

- [공통 envelope](../../contracts/events/_envelope.schema.json): eventId, eventType, schemaVersion, occurredAt, sourceId, ownerId의 의미와 타입
- eventType은 토픽 이름, sourceId는 Kafka 키라는 기존 공통 규칙
- [media 계약](../../contracts/asyncapi/media-service.yaml): 최소 한 번 전달, eventId로 소비 중복 흡수, traceparent 헤더
- SPEC-004의 구간 계산·입력 비교·활성 Job 제한
- common-messaging의 OutboxRecorder는 실행 중인 DB 트랜잭션을 요구하고 OutboxPublisher는 event_type 토픽으로 발행한다. 이것은 기존 구현 사실이며 미확정 메시지 계약의 대체물이 아니다.

### AI팀과 함께 확정할 계약 항목

| ID | 항목 | 확인할 질문 |
| --- | --- | --- |
| A-1 | 정규화 결과와 시간 | 처리 가능한 정규화 사본의 참조·버전, 영상 길이의 단위·정밀도·유효 범위와 PTS 의미를 어떻게 전달하는가? |
| A-2 | 청크 요청 단위·식별 | 개별 청크 또는 묶음 중 무엇인가? source·분석 버전·Job·Chunk의 연결과 소유/확장 구간의 경계를 어떻게 표현하는가? |
| A-3 | 재정규화·재전달 | 같은 정규화 결과의 재전달과 새 정규화 결과를 구별하는 기준은 무엇인가? 새 eventId로 같은 결과를 알릴 때 계획 식별은 어떻게 유지하는가? |
| A-4 | 처리 프로필·필수 정보 | 워커에 필요한 정규화 사본·프로필·전처리 버전의 정보는 무엇이며, 어떤 값의 확정 책임이 누구에게 있는가? |
| A-5 | 계약 호환·운영 실패 | 버전·필수/선택 필드·미지원 버전·잘못된 입력·중복 요청·요청 ID와 실제 실행의 의미를 어떻게 맞추는가? |

공통 envelope 외에는 필드명·타입·필수 여부·샘플 값을 여기서 확정하지 않는다. 아키텍처에 언급된 예상 비용의 실제 표현·필수 여부도 A-1/A-4에서 결정하며 비용 모델은 이번에 설계하지 않는다.

### backend에서 결정할 항목

| ID | 항목 | 내부 결정과 외부 합의의 경계 |
| --- | --- | --- |
| B-1 | Outbox 기록과 배정 분리 | 현재 발행기는 기록된 chunk.requested를 바로 전송한다. 전체 청크를 넣고 켜면 공정성·처리량 상한을 우회할 수 있다. 이번 범위를 발행 비활성 저장 검증으로 한정할지, 배정 이후에만 발행 가능한 기록 모델을 둘지 결정해야 한다. 새 토픽이나 상태를 임의로 추가하지 않는다. |
| B-2 | 수신 중복·계획 연결 | 수신 완료 기록, 유일 제약, 잠금, offset 처리, 트랜잭션 경계를 정한다. eventId를 계획 ID로 바로 치환하는 것은 내부 선택만으로 확정하지 않으며 A-3과 맞춘다. |
| B-3 | 기존 계획과 충돌 복구 | SPEC-004로 이미 생성한 계획에 Outbox가 없을 때 보완할지 거절할지, 같은 eventId의 변경 입력과 서로 다른 입력 이벤트의 같은 계획을 어떻게 처리할지 정한다. 중복 수신을 이유로 요청을 유실하거나 전체를 재생성하지 않는다. |
| B-4 | 재시도·불량 입력 | 일시 장애와 계약 위반·활성 Job 충돌을 구분하고, 재시도 횟수·간격·DLQ/보류 처리·소비 그룹·동시성을 정한다. 외부에 관찰되는 오류 의미는 A-5와 맞춘다. |
| B-5 | 저장·관측·검증 | 기존 기록기 재사용, 필요한 테이블·인덱스·보존/정리, 추적·로그, 테스트 장애 주입은 backend plan에서 정한다. 기존 Job에 없는 소유자·정규화 사본 정보의 보존 필요성도 계약 합의 후 판단한다. |

## 7. 성공 지표

- A-1~A-5 및 B-1~B-5의 결론이 명세·계약에 반영되어 구현 전 미결 사항 0건
- 합의한 생산자 샘플과 소비자 샘플이 동일 JSON Schema·AsyncAPI 검증 통과
- PostgreSQL·Kafka에서 정상·중복·동시 수신·부분 실패·재전달 검증 통과
- 단일 이벤트의 커밋 전 실패는 신규 저장 0건, 커밋 후 재전달은 논리적 요청 증가 0건
- 계획·수신 완료·Outbox 중 어느 하나만 보존되는 부분 커밋 0건
- 필수 포맷·컴파일·테스트와 GitHub 필수 검사 통과

## 8. 미결 사항

- [NEEDS CLARIFICATION: A-1~A-5의 AI 생산자·소비자 계약을 확정해야 한다. 기존 envelope 외의 payload는 미정이다.]
- [NEEDS CLARIFICATION: B-1의 기록·발행·배정 경계를 정해야 한다. 공정성 제한을 우회하는 즉시 전체 청크 발행은 이 초안으로 허용하지 않는다.]
- [NEEDS CLARIFICATION: B-2~B-4의 중복·기존 계획 보완·불량 입력/충돌 처리 정책을 정해야 한다.]

ADR-0007은 팀원 Approve 대기를 제거하지만 미확정 요구사항이나 타 팀 계약을 추측하는 것을 허용하지 않는다. 따라서 이 문서는 Draft로 유지하고 코드·계약 구현은 진행하지 않는다.
