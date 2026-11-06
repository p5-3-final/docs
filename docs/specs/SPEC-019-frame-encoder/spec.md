---
id: SPEC-019
title: frame-encoder 구간·크롭 벡터와 프로토타입 후보
status: Implementing
owner: <이름>
repos: [ai, docs]
created: 2026-11-06
updated: 2026-11-06
related: [ADR-0008, ADR-0010, SPEC-011, SPEC-013]
---

# SPEC-019 frame-encoder 구간·크롭 벡터와 프로토타입 후보

> 이 문서에는 **무엇을, 왜**만 쓴다. 클래스, 테이블, 라이브러리 같은 구현 방법은 각 레포의 plan.md에 쓴다.

## 1. 배경과 목적

검색 경로는 영상의 10초 구간마다 벡터 하나를 만들어 문장·이미지 질의와 비교한다([아키텍처 v5](../../architecture/architecture.md) 분석 처리 흐름 5·6단계). chunk-processor가 구간마다 블러 처리한 프레임 4장과 트랙 대표 크롭을 S3에 저장하고 `segment.ready`로 알리면, frame-encoder가 벡터를 만든다.

- 구간 벡터: 프레임 4장을 각각 인코딩해 정규화한 뒤 평균을 내고 다시 정규화한다. 한 장보다 구간 전체의 장면을 잘 나타낸다.
- 크롭 벡터: 트랙 대표 크롭을 같은 인코더로 만든다. 이미지 검색과 트랙 재등장 연결(Re-ID)에 쓴다.
- 벡터는 파일로 S3에 두고 `segment.embedded`로 경로를 알린다. search-service가 읽어 자기 DB에 적재한다. 벡터를 메시지에 직접 넣지 않는 이유는 메시지 크기 때문이다.
- 프로토타입 후보(ADR-0010 ③): 탐지기 클래스가 없는 행동 유형은 구간 벡터를 유형별 텍스트 프로토타입과 비교해, 임계값을 넘는 구간을 `event.candidate.vector`로 보낸다. 프로토타입 문장과 임계값은 AI 담당자가 프로필에 채운다.

frame-encoder는 ai-gateway와 같은 인코더 구현(`libs/encoders`)과 같은 모델 ID·가중치 manifest를 쓴다. 질의 벡터와 구간 벡터가 같은 공간에 있어야 검색이 맞기 때문이다(overview "인코더 일치"). 구간 인코딩은 처리량이 중요한 파이프라인 단계라, 사용자 요청에 바로 응답하는 ai-gateway와 따로 확장·장애 격리하려고 별도 워커로 둔다(2026-11-06 검토).

`segment.ready`의 생산자는 chunk-processor(다른 담당자)다. 이 spec은 아키텍처 문서의 설명대로 메시지 형식을 계약으로 정하고, chunk-processor는 이 계약을 보고 발행을 구현한다. 지금은 발행하는 쪽이 없다.

## 2. 범위

### 포함

- `segment.ready` 소비(소비 그룹 `frame-encoder`)와 입력 검증
- 구간 벡터(프레임 4장 정규화 평균)와 크롭 벡터 생성
- 벡터 파일(JSON) 저장과 `segment.embedded` 발행. 구간·크롭이 없는 청크도 빈 파일과 이벤트를 낸다.
- 유형별 텍스트 프로토타입 비교와 `event.candidate.vector` 발행
- 프로필: 인코더(모델 ID·차원·가중치 manifest), 프로토타입(버전, 유형별 문장·임계값). 기동 시 검증
- 처리 단계 측정 `encoder.segments`·`encoder.crops`·`encoder.store`·`encoder.prototype`
- 계약: `segment.ready`, `segment.embedded`, `event.candidate.vector`, 벡터 파일 스키마, 단계 ID, AsyncAPI
- 로컬 compose에 frame-encoder 추가

### 제외

- `segment.ready` 발행(구간 나누기, 프레임 뽑기, 블러): chunk-processor 담당
- 벡터 적재와 `segment.indexed`: search-service 담당
- 프로토타입 후보 판정(`vector+vlm`): event-analyzer spec
- 크롭 벡터를 쓰는 Re-ID: track-stitcher spec
- 프로토타입 문장·임계값 내용, 인코더 모델 선택: AI 담당자 몫
- `video.deleted` 처리: frame-encoder는 DB가 없다. 벡터 파일은 영상 폴더(`sources/<sourceId>/`) 아래에 두므로 media-service의 저장소 정리가 지운다(SPEC-003 R-20).
- 정적 구간 판단: chunk-processor가 정하고 frame-encoder는 플래그를 그대로 옮긴다. 정적 구간도 벡터를 만든다(overview 5단계).

## 3. 사용자 시나리오

### US-1 구간 벡터로 장면 찾기 준비 (P1)

검색 사용자로서 영상의 장면을 문장으로 찾고 싶다. 왜냐하면 긴 영상을 처음부터 볼 수 없기 때문이다.

#### 인수 조건

- Given 구간 2개(프레임 4장씩)와 크롭 1장이 담긴 `segment.ready`, When frame-encoder가 처리하면, Then 구간 벡터 2개와 크롭 벡터 1개가 든 벡터 파일이 S3에 저장되고 `segment.embedded`가 경로·개수·모델 ID·차원과 함께 한 번 발행된다.
- Given 같은 메시지를 다시 받으면, When 처리하면, Then 같은 경로의 같은 파일과 같은 eventId의 `segment.embedded`가 나온다.
- Given 구간과 크롭이 없는 청크, When 처리하면, Then 개수 0인 벡터 파일과 `segment.embedded`가 나온다.

### US-2 질의 벡터와 같은 공간 (P1)

검색 운영자로서 구간 벡터와 질의 벡터가 같은 인코더로 만들어지기를 원한다. 왜냐하면 인코더가 다르면 검색 결과가 무의미해지기 때문이다.

#### 인수 조건

- Given 프로필의 모델 ID·차원과 다른 가중치 manifest, When frame-encoder가 기동하면, Then 기동에 실패한다.
- Given 구간 벡터, Then 벡터 파일과 `segment.embedded`에 ai-gateway와 같은 형식의 모델 ID가 기록된다.

### US-3 프로토타입으로 행동 후보 내기 (P2)

AI 담당자로서 탐지기 클래스가 없는 행동 유형도 후보로 받고 싶다. 왜냐하면 탐지기만으로는 행동 유형 후보가 0건이기 때문이다.

#### 인수 조건

- Given 유형별 프로토타입 문장과 임계값이 있는 프로필, When 구간 벡터의 점수가 임계값 이상이면, Then 그 구간·유형이 담긴 `event.candidate.vector`가 청크당 한 번 발행된다.
- Given 프로토타입이 없는 프로필이나 임계값을 넘는 구간이 없는 청크, When 처리하면, Then `event.candidate.vector`를 발행하지 않는다.
- Given 분류 체계 v2에 없는 유형을 적은 프로필, When 기동하면, Then 기동에 실패한다.

### US-4 잘못된 메시지 (P2)

운영자로서 계약을 어긴 메시지가 처리를 막지 않기를 원한다. 왜냐하면 한 메시지 때문에 다른 영상 처리가 멈추면 안 되기 때문이다.

#### 인수 조건

- Given 프레임이 4장이 아닌 구간이나 다른 영상 폴더의 경로가 담긴 메시지, When 받으면, Then 벡터 파일과 이벤트를 만들지 않고 DLQ로 보낸 뒤 다음 메시지를 처리한다.

## 4. 요구사항

### 기능 요구사항 (EARS)

| ID | 요구사항 | 시나리오 |
| --- | --- | --- |
| R-1 | WHEN frame-encoder가 `segment.ready`를 받으면, THE frame-encoder SHALL 구간마다 프레임 4장을 각각 인코딩해 길이 1로 정규화하고, 네 벡터의 평균을 다시 길이 1로 정규화한 구간 벡터를 만든다. | US-1 |
| R-2 | WHEN frame-encoder가 `segment.ready`를 받으면, THE frame-encoder SHALL 크롭마다 같은 인코더로 길이 1인 크롭 벡터를 만든다. | US-1 |
| R-3 | THE frame-encoder SHALL 구간·크롭 벡터를 계약 `vectors/v1/vector-file.schema.json` 형식의 파일 하나로 `sources/<sourceId>/jobs/<jobId>/chunks/<chunkId>/executions/<executionId>/vectors.json`에 저장한다. | US-1 |
| R-4 | WHEN 벡터 파일을 저장하면, THE frame-encoder SHALL 파일 경로, 구간 수, 크롭 수, 인코더 모델 ID, 차원을 담은 `segment.embedded`를 발행한다. | US-1 |
| R-5 | THE frame-encoder SHALL `segment.embedded`와 `event.candidate.vector`의 eventId를 executionId와 이벤트 유형으로 결정적으로 만들어, 같은 메시지를 다시 처리해도 같은 eventId와 같은 파일 경로를 쓴다. | US-1 |
| R-6 | WHERE `segment.ready`에 구간과 크롭이 모두 없으면, THE frame-encoder SHALL 개수 0인 벡터 파일을 저장하고 `segment.embedded`를 발행한다. | US-1 |
| R-7 | THE frame-encoder SHALL 구간의 정적 여부(`static`)를 벡터 파일에 그대로 옮기고 정적 구간도 벡터를 만든다. | US-1 |
| R-8 | THE frame-encoder SHALL 벡터 파일과 `segment.embedded`에 프로필의 인코더 모델 ID(`<라이브러리>:<아키텍처>:<가중치>:<집계>`)와 차원을 기록한다. | US-2 |
| R-9 | IF 가중치 manifest의 모델 ID나 차원이 프로필과 다르거나 manifest 해시가 맞지 않으면, THEN THE frame-encoder SHALL 기동에 실패한다. | US-2 |
| R-10 | WHEN frame-encoder가 기동하면, THE frame-encoder SHALL 프로필의 유형마다 문장들을 인코더 텍스트 쪽으로 인코딩해 정규화 평균한 프로토타입 벡터를 한 번 만든다. | US-3 |
| R-11 | WHEN 구간 벡터를 만들면, THE frame-encoder SHALL 구간 벡터와 각 유형 프로토타입 벡터의 코사인 유사도를 점수로 계산하고, 점수가 그 유형의 임계값 이상인 (구간, 유형)을 후보로 만든다. | US-3 |
| R-12 | WHEN 한 메시지에서 후보가 1개 이상 나오면, THE frame-encoder SHALL `segment.embedded`를 발행한 뒤 그 메시지의 후보를 모두 담은 `event.candidate.vector` 한 건을 발행한다. | US-3 |
| R-13 | WHERE 프로필에 프로토타입이 없거나 후보가 0개이면, THE frame-encoder SHALL `event.candidate.vector`를 발행하지 않는다. | US-3 |
| R-14 | THE frame-encoder SHALL 후보마다 후보 ID(executionId·segmentId·유형으로 결정적), 구간 ID·시각, 유형, 점수, 임계값, 구간 프레임 경로 4개를 담고, 메시지에 프로토타입 버전과 분류 체계 버전을 담는다. | US-3 |
| R-15 | IF 프로필의 프로토타입 유형이 분류 체계 v2의 탐지 가능 유형이 아니거나, 문장이 없거나, 임계값이 -1 초과 1 이하가 아니면, THEN THE frame-encoder SHALL 기동에 실패한다. | US-3 |
| R-16 | IF `segment.ready`가 계약 스키마에 맞지 않거나, 프레임·크롭 경로가 그 메시지의 sourceId·jobId·chunkId·executionId 폴더의 `blurred/` 아래가 아니면, THEN THE frame-encoder SHALL 벡터 파일과 이벤트를 만들지 않고 메시지를 재시도 없이 DLQ로 보낸다. | US-4 |
| R-17 | IF 프레임·크롭 이미지가 저장소에 없거나 디코딩할 수 없으면, THEN THE frame-encoder SHALL 벡터 파일과 이벤트를 만들지 않고 메시지를 재시도 없이 DLQ로 보낸다. | US-4 |
| R-18 | IF 저장소나 Kafka에 일시적으로 쓸 수 없으면, THEN THE frame-encoder SHALL 메시지를 재시도 토픽으로 보내 다시 처리한다. | US-1 |
| R-19 | THE frame-encoder SHALL 핸들러 안의 처리 시간을 단계 `encoder.segments`(구간 벡터), `encoder.crops`(크롭 벡터), `encoder.store`(파일 저장), `encoder.prototype`(프로토타입 비교)으로 남긴다(SPEC-013). | US-1 |

### 비기능 요구사항

| ID | 요구사항 |
| --- | --- |
| NFR-1 | THE frame-encoder SHALL 한 Pod에서 `segment.ready`를 한 번에 하나씩 처리한다(overview "로컬 실행 자원": 동시 1). |
| NFR-2 | THE frame-encoder SHALL 로컬 compose에서 구간 24개(프레임 96장)·크롭 30장 메시지를 120초 안에 처리한다. |
| NFR-3 | THE frame-encoder SHALL 인코딩 중에도 Kafka 소비 그룹 하트비트를 유지해, 처리 중인 메시지 때문에 리밸런스가 일어나지 않게 한다. |

## 5. 영향 범위

| 레포 / 서비스 | 변경 개요 | 담당 요구사항 |
| --- | --- | --- |
| ai / frame-encoder | 새 워커: 소비·검증, 벡터 생성, 파일 저장, 발행, 프로토타입 비교, 프로필, 단계 측정 | R-1~R-19, NFR-1~NFR-3 |
| ai / libs | 인코더(`libs/encoders`)를 ai-gateway와 함께 쓴다. 필요하면 계약 모델(`libs/contracts`)을 더한다. | R-1, R-2, R-9 |
| docs | 계약 6종, overview 토픽 표·흐름, 서비스 카탈로그, v4 전환 문서 | R-3, R-4, R-12, R-14, R-19 |
| docs / local | 로컬 compose에 frame-encoder, 토픽 `segment.ready`·`segment.embedded`·`event.candidate.vector`와 재시도·DLQ | R-18 |
| ai / chunk-processor | (이후, 다른 담당자) `segment.ready` 발행 | — |
| backend / search-service | (이후, 다른 담당자) `segment.embedded` 소비, 벡터 파일 적재 | — |
| ai / event-analyzer, track-stitcher | (이후) `event.candidate.vector`, 크롭 벡터 사용. 각 spec | — |

## 6. 계약 변경

| 계약 파일 | 변경 | 하위호환 |
| --- | --- | --- |
| `service-contracts/events/segment.ready.schema.json` | 새 이벤트(생산 chunk-processor) | 예(추가) |
| `service-contracts/events/segment.embedded.schema.json` | 새 이벤트 | 예(추가) |
| `service-contracts/events/event.candidate.vector.schema.json` | 새 이벤트 | 예(추가) |
| `service-contracts/vectors/v1/vector-file.schema.json` | 새 파일 형식 | 예(추가) |
| `service-contracts/stages/v1/stages.schema.json` | `frame-encoder.queue_wait`·`frame-encoder.handle`·`encoder.*` 4개 | 예(추가) |
| `service-contracts/asyncapi/frame-encoder.yaml`, `asyncapi/chunk-processor.yaml` | frame-encoder 발행 2종, chunk-processor의 `segment.ready` 채널 | 예(추가) |

계약 묶음 2.9.1 → 2.10.0

## 7. 성공 지표

- 로컬 compose에서 테스트용 `segment.ready`를 넣으면 S3에 벡터 파일이 생기고 `segment.embedded`가 나오며, 파일의 구간 벡터와 ai-gateway `/v1/embed`(`embed_visual_text`)의 질의 벡터를 비교할 수 있다(같은 모델 ID·차원).
- 프로토타입을 채운 로컬 프로필에서 `event.candidate.vector`가 나온다.

## 8. 미결 사항

- 해당 없음
