---
id: SPEC-025
title: embedding-worker 이벤트·트랙·구간 주석 텍스트 벡터
status: Approved
owner: <이름>
repos: [ai, docs]
created: 2026-11-06
updated: 2026-11-06
related: [ADR-0008, SPEC-011, SPEC-013, SPEC-016, SPEC-020, SPEC-021, SPEC-023, SPEC-024]
---

# SPEC-025 embedding-worker 이벤트·트랙·구간 주석 텍스트 벡터

> 이 문서에는 **무엇을, 왜**만 쓴다. 클래스, 테이블, 라이브러리 같은 구현 방법은 각 레포의 plan.md에 쓴다.

## 1. 배경과 목적

구간 벡터는 장면의 외형만 담는다. 그래서 행동 질의("작업자가 쓰러진 장면")와 속성 질의("안전조끼 없는 작업자")는 텍스트 인덱스로 보완한다([아키텍처 개요](../../architecture/overview.md) "검색 경로" 인덱스 표). 텍스트 인덱스는 세 종류다.

| 인덱스 | 원본 | 문장 |
| --- | --- | --- |
| 텍스트·이벤트 | `event.analyzed`(SPEC-020, SPEC-023) | 설명문, 위험 사유, 조치 제안 |
| 텍스트·트랙 | `track.analyzed`(SPEC-024) | 트랙 속성 설명 |
| 텍스트·주석 | `segment.annotated`(search-service) | 정밀 검색에서 확인된 구간 주석 |

embedding-worker는 항목마다 문장을 만들고, ai-gateway `/v1/embed`(`embed_text`)로 벡터를 만든다. 그 결과를 검색 필터용 값과 함께 텍스트 벡터 파일로 저장하고 `embedding.ready`로 search-service에 알린다. 벡터처럼 큰 데이터는 이벤트에 싣지 않고 파일 경로만 싣는다(overview "통신 규칙" 대량 데이터).

입력 `segment.annotated`는 search-service(다른 담당자)가 낸다. 계약이 없어 이 spec이 아키텍처 문서대로 소비 쪽에서 정한다(2026-11-06 사용자 결정, [handoff](../../handoff.md) 2.1).

## 2. 범위

### 포함

- 계약: `segment.annotated`(생산자 확인 필요), `embedding.ready`, 파일 `vectors/v1/text-vector-file`, AsyncAPI(`embedding-worker`, `search-service` 0.1.0), 단계 ID
- 세 토픽 소비(소비 그룹 `embedding-worker`), 항목별 문장 규칙(문장 규칙 버전 `textFormat` 기록)
- `embed_text` 호출(SPEC-021 재시도·마감 규칙), 텍스트 벡터 파일 저장, `embedding.ready` 발행
- 임베딩할 문장이 없는 항목 건너뛰기
- 처리 단계 측정 `embedding.call`·`embedding.store`
- 로컬 compose에 embedding-worker와 토픽 추가

### 제외

- 텍스트 인덱스 적재, 하이브리드 검색: search-service(다른 담당자) 몫이다.
- 여러 항목을 한 번에 임베딩하는 묶음 처리: 이후 성능 spec(지금은 메시지 하나에 문장 하나)
- 임베딩 모델 교체 시 재임베딩(`REEMBED` job): pipeline-service 몫이다. 이 spec은 같은 항목·다른 모델이면 다른 파일·eventId가 되게만 한다.
- 텍스트 임베딩 모델 선택: AI 담당자 몫이다(ai-gateway 프로필).

## 3. 사용자 시나리오

### US-1 행동·속성으로 장면 찾기 (P1)

안전관리자로서 "작업자가 쓰러진 장면", "안전모 안 쓴 사람"처럼 행동·속성으로 찾고 싶다. 왜냐하면 구간 외형 벡터만으로는 행동과 속성을 구분하지 못하기 때문이다.

#### 인수 조건

- Given 설명문·위험 사유·조치 제안이 있는 `event.analyzed`, When 처리하면, Then 세 문장을 줄바꿈으로 이은 문장의 벡터가 텍스트 벡터 파일에 저장되고 `embedding.ready`(itemKind `event`)가 발행된다.
- Given `outcome: READY`, `verificationStatus: confirmed`, 설명이 있는 click `track.analyzed`, When 처리하면, Then 속성 설명의 벡터와 보호구·역할 값이 담긴 파일과 `embedding.ready`(itemKind `track`)가 나온다.
- Given `segment.annotated`, When 처리하면, Then 주석 문장의 벡터가 담긴 파일과 `embedding.ready`(itemKind `segment_annotation`)가 나온다.

### US-2 쓸모없는 항목은 건너뜀 (P2)

운영자로서 문장이 없는 결과로 임베딩 비용을 쓰지 않기를 원한다.

#### 인수 조건

- Given 설명문·위험 사유·조치 제안이 모두 null인 `event.analyzed`(unverified·unknown), When 처리하면, Then ai-gateway를 부르지 않고 아무것도 발행하지 않는다.
- Given reason `question`이거나 `outcome: FAILED`인 `track.analyzed`, When 처리하면, Then 건너뛴다.

### US-3 장애 (P2)

운영자로서 임베딩 모델이 잠시 내려가도 항목을 잃지 않기를 원한다.

#### 인수 조건

- Given ai-gateway가 503을 계속 돌려줌, When 처리하면, Then 클라이언트 재시도(2회) 뒤 메시지가 재시도 토픽으로 가고, 워커 재시도를 다 쓰면 DLQ로 간다.
- Given 임베딩 모델이 설정되지 않음(`AI_MODEL_NOT_CONFIGURED`), When 처리하면, Then 기다려도 같은 결과라 재시도 없이 DLQ로 간다.

## 4. 요구사항

### 기능 요구사항 (EARS)

| ID | 요구사항 | 시나리오 |
| --- | --- | --- |
| R-1 | WHEN embedding-worker가 `event.analyzed`를 받으면, THE embedding-worker SHALL `analysis`의 `description`·`riskReason`·`solution` 중 null이 아닌 값을 이 순서로 줄바꿈으로 이은 문장을 항목(itemKind `event`, itemId는 eventId)의 문장으로 쓴다. | US-1 |
| R-2 | WHEN embedding-worker가 reason `event`·`click`, `outcome` `READY`, `attributes.verificationStatus` `confirmed`이고 `attributes.description`이 있는 `track.analyzed`를 받으면, THE embedding-worker SHALL 그 설명을 항목(itemKind `track`, itemId는 trackId)의 문장으로 쓴다. | US-1 |
| R-3 | WHEN embedding-worker가 `segment.annotated`를 받으면, THE embedding-worker SHALL 주석 문장을 항목(itemKind `segment_annotation`, itemId는 annotationId)의 문장으로 쓴다. | US-1 |
| R-4 | IF R-1~R-3으로 만든 문장이 비었거나 R-2의 조건에 맞지 않는 `track.analyzed`이면, THEN THE embedding-worker SHALL ai-gateway를 부르지 않고 아무것도 발행하지 않으며 건너뛴 이유를 로그에 남긴다. | US-2 |
| R-5 | IF 문장이 설정한 최대 글자 수(기본 2000)를 넘으면, THEN THE embedding-worker SHALL 앞에서부터 최대 글자 수까지만 쓴다. | US-1 |
| R-6 | THE embedding-worker SHALL ai-gateway `/v1/embed`를 taskType `embed_text`, 문장 하나로 부르고, 응답 벡터를 텍스트 벡터 파일(`vectors/v1/text-vector-file`)로 `sources/<sourceId>/jobs/<jobId>/text-vectors/<itemKind>/<itemId>.json`에 저장한 뒤 `embedding.ready`를 발행한다. | US-1 |
| R-7 | THE embedding-worker SHALL 파일 `metadata`에 항목 시각(초 단위 값은 ms로)과 항목별 필터 값을 담는다. event는 유형·severity·`verificationStatus`, track은 trackId·클래스·보호구·역할, segment_annotation은 segmentId다. | US-1 |
| R-8 | THE embedding-worker SHALL 파일과 `embedding.ready`에 문장 규칙 버전(`event-v1`·`track-v1`·`segment_annotation-v1`), 응답의 모델 ID, 차원을 담고, eventId를 itemKind·itemId·모델 ID로 결정적으로 만든다. | US-1 |
| R-9 | IF `/v1/embed`가 SPEC-021 R-10의 재시도 끝에도 503·연결 실패·시간 초과로 끝나면, THEN THE embedding-worker SHALL 메시지를 재시도 토픽으로 보내 다시 처리한다. 단 오류 코드가 `AI_MODEL_NOT_CONFIGURED`·`AI_BUDGET_EXCEEDED`이면 재시도 없이 DLQ로 보낸다. | US-3 |
| R-10 | IF `/v1/embed`가 4xx를 돌려주거나 응답 벡터 수가 1이 아니거나 벡터 길이가 응답 차원과 다르면, THEN THE embedding-worker SHALL 아무것도 발행하지 않고 재시도 없이 DLQ로 보낸다. | US-3 |
| R-11 | IF 메시지가 계약 스키마에 맞지 않으면, THEN THE embedding-worker SHALL 재시도 없이 DLQ로 보낸다. | US-3 |
| R-12 | IF 저장소·Kafka가 일시적으로 응답하지 않으면, THEN THE embedding-worker SHALL 메시지를 재시도 토픽으로 보내 다시 처리하고, 같은 경로·같은 eventId로 다시 쓴다. | US-3 |
| R-13 | THE embedding-worker SHALL 처리 시간을 단계 `embedding.call`(문장 수)·`embedding.store`(파일 수)로 남긴다(SPEC-013). | US-1 |

### 비기능 요구사항

| ID | 요구사항 |
| --- | --- |
| NFR-1 | THE embedding-worker SHALL 로컬 compose mock 프로필에서 메시지 하나를 p95 500ms 안에 처리한다. |
| NFR-2 | THE embedding-worker SHALL 문장 원문과 벡터를 로그에 남기지 않는다. |
| NFR-3 | THE embedding-worker SHALL 한 Pod에서 메시지를 한 번에 하나씩 처리하고, 발행 뒤 커밋한다. |

## 5. 영향 범위

| 레포 / 서비스 | 변경 개요 | 담당 요구사항 |
| --- | --- | --- |
| ai / embedding-worker | 새 워커: 세 토픽 소비, 문장 규칙, 임베딩, 파일 저장, 발행 | R-1~R-13, NFR-1~NFR-3 |
| ai / libs | 계약 모델(`SegmentAnnotated`, `EmbeddingReady`, 텍스트 벡터 파일), 단계 ID. ai-client `embed`(SPEC-021) 사용 | R-6, R-8, R-13 |
| docs | 계약, overview 토픽 표, 서비스 카탈로그 | R-6, R-8 |
| docs / local | 로컬 compose에 embedding-worker, 토픽 `segment.annotated`·`embedding.ready`와 재시도·DLQ | R-9, R-12 |
| backend / search-service (다른 담당자) | (이후) `segment.annotated` 발행, `embedding.ready` 적재 | — |

## 6. 계약 변경

| 계약 파일 | 변경 | 하위호환 |
| --- | --- | --- |
| `service-contracts/events/segment.annotated.schema.json` | 새 이벤트(생산자 확인 필요) | 예(추가) |
| `service-contracts/events/embedding.ready.schema.json` | 새 이벤트 | 예(추가) |
| `service-contracts/vectors/v1/text-vector-file.schema.json` | 새 파일 형식 | 예(추가) |
| `service-contracts/asyncapi/embedding-worker.yaml` | 새 파일 | 예(추가) |
| `service-contracts/asyncapi/search-service.yaml` | 새 파일: `segment.annotated` 발행 채널(생산자 확인 필요, 0.1.0) | 예(추가) |
| `service-contracts/stages/v1/stages.schema.json` | `embedding-worker.queue_wait`·`embedding-worker.handle`·`embedding.call`·`embedding.store` | 예(추가) |

계약 묶음 3.4.0 → 3.5.0

## 7. 성공 지표

- 로컬 compose에서 SPEC-020 흐름으로 나온 `event.analyzed`가 `embedding.ready`로 이어지고, 파일이 계약 스키마를 통과한다.

## 8. 미결 사항

- 해당 없음
