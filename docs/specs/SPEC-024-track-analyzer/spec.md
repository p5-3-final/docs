---
id: SPEC-024
title: track-analyzer 트랙 속성 분석과 객체 자유 질문
status: Approved
owner: <이름>
repos: [ai, docs]
created: 2026-11-06
updated: 2026-11-06
related: [ADR-0008, ADR-0012, ADR-0014, SPEC-009, SPEC-013, SPEC-016, SPEC-021, SPEC-022]
---

# SPEC-024 track-analyzer 트랙 속성 분석과 객체 자유 질문

> 이 문서에는 **무엇을, 왜**만 쓴다. 클래스, 테이블, 라이브러리 같은 구현 방법은 각 레포의 plan.md에 쓴다.

## 1. 배경과 목적

트랙(한 사람·한 장비가 화면에 있는 동안)에 속성이 붙어야 할 수 있는 일이 있다.

- "안전모를 안 쓴 작업자", "주황 조끼 입은 사람"을 텍스트로 찾기
- 화면을 클릭했을 때 그 사람이 누구인지(역할·보호구) 보여 주기
- 이벤트 상세에 관련자의 보호구 상태를 함께 보여 주기

analysis-api는 세 경우에 `attribute.requested`를 낸다. 이벤트 관련 트랙(event), 화면 클릭(click), 객체 자유 질문(question)이다. track-analyzer는 트랙 대표 크롭으로 ai-gateway를 부른다. 속성은 `track_attribute`, 질문은 `object_question`이다. 결과는 `track.analyzed`로 analysis-api(저장), embedding-worker(텍스트 인덱스), notification-service(화면 알림)에 보낸다([아키텍처 개요](../../architecture/overview.md) 분석 처리 흐름 9·12단계, "AI Gateway" taskType 표).

클릭과 질문은 사용자가 화면에서 기다리는 요청이다. 그래서 실패해도 결과 없이 끝내지 않고 `FAILED`로 알려, 화면이 기다림을 멈추게 한다.

입력 `attribute.requested`는 analysis-api(다른 담당자)가 낸다. 계약이 없어 이 spec이 아키텍처 문서대로 소비 쪽에서 정한다(2026-11-06 사용자 결정, [handoff](../../handoff.md) 2.1). 크롭 경로가 트랙 요약 파일에 있어야 analysis-api가 요청에 실을 수 있다. 그래서 트랙 요약 파일(SPEC-022)에 대표 크롭을 더한다.

## 2. 범위

### 포함

- 계약
  - `attribute.requested`(생산자 확인 필요), `track.analyzed`
  - 결과 형식 `_track-attribute`·`_object-answer`
  - 분류 체계 v2 `ppeState`·`workerRole`
  - 트랙 요약 파일 `representativeCrops`
  - ai-gateway `TaskType` 값, AsyncAPI, 단계 ID
- track-analyzer: `attribute.requested` 소비(소비 그룹 `track-analyzer`), reason별 taskType 호출, 결과·실패 발행
- ai-gateway: `track_attribute`·`object_question` taskType 등록(Registry 폴더, 로컬 프로필)
- 처리 단계 측정 `attribute.call`
- 로컬 compose에 track-analyzer와 토픽 추가

### 제외

- 요청을 언제 낼지, 트랙 속성 상태(`NONE → REQUESTED → READY`·`FAILED`) 저장, 클릭한 (t, x, y)로 트랙 찾기: analysis-api(다른 담당자) 몫이다.
- 화면 알림(SSE): notification-service(다른 담당자) 몫이다.
- 속성 텍스트 임베딩: embedding-worker(SPEC-025) 몫이다.
- 프롬프트 문안, 모델 선택, 속성 값 목록의 실제 내용: AI 담당자 몫이다. 이 spec은 자리와 동작 확인용 값만 둔다.

## 3. 사용자 시나리오

### US-1 클릭한 사람의 속성 (P1)

안전관리자로서 화면의 작업자를 누르면 안전모·조끼 착용 여부와 역할을 보고 싶다.

#### 인수 조건

- Given reason `click`, 크롭 2장인 `attribute.requested`, When 처리하면, Then 크롭 2장으로 `track_attribute`를 부르고 `outcome: READY`, `attributes`가 담긴 `track.analyzed`가 같은 requestId로 발행된다.
- Given 같은 요청을 다시 받음, When 처리하면, Then 같은 eventId로 발행된다.

### US-2 객체에 질문 (P1)

안전관리자로서 "이 사람이 손에 무엇을 들고 있나요?"처럼 물어보고 답을 받고 싶다.

#### 인수 조건

- Given reason `question`, 질문과 장면 프레임이 있는 요청, When 처리하면, Then 크롭과 장면 프레임, 질문으로 `object_question`을 부르고 `answer`가 담긴 `track.analyzed`가 발행된다.

### US-3 실패해도 화면이 기다리지 않음 (P1)

안전관리자로서 분석이 실패하면 계속 기다리지 않고 실패했다는 표시를 보고 싶다.

#### 인수 조건

- Given ai-gateway가 503을 돌려줌, When 처리하면, Then 다시 부르지 않고 `outcome: FAILED`, `errorCode: AI_PROVIDER_UNAVAILABLE`인 `track.analyzed`가 발행된다.
- Given 판정 모델이 설정되지 않음, When 처리하면, Then `outcome: READY`, `attributes.verificationStatus: unverified`로 발행된다.

### US-4 잘못된 요청 (P2)

운영자로서 계약을 어기거나 다른 영상의 이미지를 가리키는 요청이 처리되지 않기를 원한다.

#### 인수 조건

- Given 크롭 경로가 메시지의 sourceId 폴더 밖, When 받으면, Then ai-gateway를 부르지 않고 DLQ로 보낸다.

## 4. 요구사항

### 기능 요구사항 (EARS)

| ID | 요구사항 | 시나리오 |
| --- | --- | --- |
| R-1 | WHEN track-analyzer가 reason `event`·`click`인 `attribute.requested`를 받으면, THE track-analyzer SHALL taskType `track_attribute`, 그 메시지의 sourceId, 크롭(순서 유지), 변수(클래스 이름)로 ai-gateway `/v1/analyze`를 부른다. | US-1 |
| R-2 | WHEN track-analyzer가 reason `question`인 `attribute.requested`를 받으면, THE track-analyzer SHALL taskType `object_question`, 크롭 다음에 장면 프레임을 붙인 이미지(순서 유지), 변수(클래스 이름, 질문)로 `/v1/analyze`를 부른다. | US-2 |
| R-3 | WHEN ai-gateway가 결과를 돌려주면, THE track-analyzer SHALL `outcome` `READY`, reason에 맞는 결과(`attributes` 또는 `answer`), 호출 ID·모델·프롬프트 버전·분류 체계 버전을 담은 `track.analyzed`를 발행한다. 결과가 `unverified`·`unknown`이어도 같다. | US-1, US-2, US-3 |
| R-4 | IF ai-gateway 호출이 결과 없이 끝나면(SPEC-021 R-9의 재시도 소진 포함, 4xx·5xx·504·시간 초과·계약과 맞지 않는 응답), THEN THE track-analyzer SHALL `outcome` `FAILED`와 오류 코드(SPEC-021 R-12)를 담은 `track.analyzed`를 발행한다. | US-3 |
| R-5 | THE track-analyzer SHALL `track.analyzed`의 eventId를 requestId로 결정적으로 만들어, 같은 요청을 다시 처리해도 같은 eventId를 쓴다. | US-1 |
| R-6 | IF `attribute.requested`의 크롭·장면 프레임 경로가 그 메시지의 `sources/<sourceId>/` 밖이면, THEN THE track-analyzer SHALL ai-gateway를 부르지 않고 메시지를 재시도 없이 DLQ로 보낸다. | US-4 |
| R-7 | IF `attribute.requested`가 계약 스키마에 맞지 않으면, THEN THE track-analyzer SHALL 아무것도 발행하지 않고 재시도 없이 DLQ로 보낸다. | US-4 |
| R-8 | IF Kafka에 일시적으로 발행할 수 없으면, THEN THE track-analyzer SHALL 메시지를 재시도 토픽으로 보내 다시 처리한다. | US-3 |
| R-9 | THE track-analyzer SHALL ai-gateway 호출에 설정한 제한 시간으로 `X-Request-Deadline`을 싣는다(SPEC-021 R-8). | US-3 |
| R-10 | THE track-analyzer SHALL 호출 시간을 단계 `attribute.call`(보낸 이미지 수를 count로)로 남긴다(SPEC-013). | US-1 |
| R-11 | WHEN 허용된 호출자가 taskType `track_attribute`로 분석을 요청하면, THE ai-gateway SHALL 입력 변수(클래스 이름)와 이미지 1~3장을 받아 출력을 계약 `events/_track-attribute.schema.json`으로 검증해 돌려준다. 처리 순서는 SPEC-009·SPEC-016과 같다. | US-1 |
| R-12 | WHEN 허용된 호출자가 taskType `object_question`으로 분석을 요청하면, THE ai-gateway SHALL 입력 변수(클래스 이름, 1~500자 질문)와 이미지 1~11장을 받아 출력을 계약 `events/_object-answer.schema.json`으로 검증해 돌려준다. | US-2 |
| R-13 | THE ai-gateway SHALL 두 taskType의 모델 미설정·예산 초과·검증 실패 결과를 각 결과 형식의 `unverified`·`unknown`으로 만든다(판정 필드는 null, `equipment`는 빈 배열). | US-3 |

### 비기능 요구사항

| ID | 요구사항 |
| --- | --- |
| NFR-1 | THE track-analyzer SHALL 로컬 compose mock 프로필에서 `attribute.requested` 발행부터 `track.analyzed` 발행까지 p95 2초 안에 처리한다(클릭 응답). |
| NFR-2 | THE track-analyzer SHALL 한 Pod에서 메시지를 한 번에 하나씩 처리하고 발행 뒤 커밋하며, 호출이 `max.poll.interval.ms`보다 길어도 하트비트를 유지한다. |
| NFR-3 | THE track-analyzer SHALL 질문 문장과 답을 로그에 남기지 않는다. |

## 5. 영향 범위

| 레포 / 서비스 | 변경 개요 | 담당 요구사항 |
| --- | --- | --- |
| ai / track-analyzer | 새 워커: 소비·검증, 호출, 발행, 단계 측정 | R-1~R-10, NFR-1~NFR-3 |
| ai / ai-gateway | `track_attribute`·`object_question` Registry 폴더(출력은 계약 참조), 로컬 프로필 | R-11~R-13 |
| ai / libs | 계약 모델(`AttributeRequested`, `TrackAnalyzed`, 결과 형식 2종, 트랙 요약 파일 대표 크롭), 단계 ID | R-3, R-10 |
| docs | 계약, overview 토픽 표, 서비스 카탈로그 | R-3, R-11, R-12 |
| docs / local | 로컬 compose에 track-analyzer, 토픽 `attribute.requested`·`track.analyzed`와 재시도·DLQ | R-8 |
| backend / analysis-api (다른 담당자) | (이후) 요청 발행, `track.analyzed` 저장 | — |
| ai / chunk-processor (다른 담당자) | (이후) 트랙 요약 파일에 대표 크롭 | — |

## 6. 계약 변경

| 계약 파일 | 변경 | 하위호환 |
| --- | --- | --- |
| `service-contracts/events/attribute.requested.schema.json` | 새 이벤트(생산자 확인 필요) | 예(추가) |
| `service-contracts/events/track.analyzed.schema.json` | 새 이벤트 | 예(추가) |
| `service-contracts/events/_track-attribute.schema.json`, `_object-answer.schema.json` | 새 공용 결과 형식(ai-gateway 출력이 참조) | 예(추가) |
| `service-contracts/taxonomy/v2/taxonomy.schema.json` | `$defs` `ppeState`·`workerRole` | 예(추가) |
| `service-contracts/tracks/v1/chunk-tracks.schema.json` | 선택 필드 `representativeCrops` | 예(선택 필드 추가) |
| `service-contracts/openapi/ai-gateway.yaml` | `TaskType` 값 `track_attribute`·`object_question`(1.2.0) | 예(`x-extensible-enum` 값 추가, ADR-0014) |
| `service-contracts/asyncapi/track-analyzer.yaml` | 새 파일 | 예(추가) |
| `service-contracts/asyncapi/analysis-api.yaml` | 새 파일: `attribute.requested` 발행 채널(생산자 확인 필요, 0.1.0) | 예(추가) |
| `service-contracts/stages/v1/stages.schema.json` | `track-analyzer.queue_wait`·`track-analyzer.handle`·`attribute.call` | 예(추가) |

계약 묶음 3.3.0 → 3.4.0

## 7. 성공 지표

- 로컬 compose에서 테스트용 `attribute.requested`(click 1, question 1)를 넣으면 `track.analyzed` 2건이 나오고 계약 스키마를 통과한다.

## 8. 미결 사항

- 해당 없음. 속성 값 목록·프롬프트는 자리만 정했다(AI 담당자 몫).
