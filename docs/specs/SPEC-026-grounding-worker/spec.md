---
id: SPEC-026
title: grounding-worker 검색 상위 구간 bbox 주석 클립
status: Approved
owner: <이름>
repos: [ai, docs]
created: 2026-11-06
updated: 2026-11-06
related: [ADR-0008, SPEC-013, SPEC-025]
---

# SPEC-026 grounding-worker 검색 상위 구간 bbox 주석 클립

> 이 문서에는 **무엇을, 왜**만 쓴다. 클래스, 테이블, 라이브러리 같은 구현 방법은 각 레포의 plan.md에 쓴다.

## 1. 배경과 목적

문장 검색은 이동 시각만 돌려준다. 그래서 사용자가 10초 구간 안에서 "안전모 안 쓴 사람"이 어디 있는지 다시 찾아야 한다. [아키텍처 개요](../../architecture/overview.md) "검색 경로" 7단계에서는 search-service가 상위 3개 구간과 대상어로 `grounding.requested`를 보낸다. grounding-worker는 개방 어휘 탐지기로 대상어를 찾고, 박스를 그린 주석 클립을 만들어 `grounding.completed`로 알린다. 클립 경로는 notification-service가 SSE로 화면에 보낸다.

- 영상을 다시 분석하지 않는다. 구간 하나에서 1fps로 최대 12장만 탐지한다(overview 메모리 표: 1.5GB, 동시 1).
- 같은 대상어·구간·탐지기 버전의 클립은 한 번만 만든다(overview "검색 결과 재사용" 주석 클립 행, 다중 Pod 표 grounding-worker 행).
- 입력 `grounding.requested`는 search-service(다른 담당자)가 낸다. 계약이 없어 이 spec이 아키텍처 문서대로 소비 쪽에서 정한다(2026-11-06 사용자 결정, [handoff](../../handoff.md) 2.1).

## 2. 범위

### 포함

- 계약: `grounding.requested`(생산자 확인 필요), `grounding.completed`, 결과 파일 `groundings/v1/grounding-result`, AsyncAPI(`grounding-worker` 1.0.0, `search-service` 0.2.0), 단계 ID
- 구간 샘플 프레임 추출, 대상어를 클래스로 쓰는 개방 어휘 탐지, 박스 주석 클립 인코딩, 결과 파일 저장, 구간마다 `grounding.completed` 발행
- 이미 만든 클립 재사용(같은 경로가 있으면 다시 만들지 않음)
- 실패를 `outcome: FAILED`로 발행
- 처리 단계 측정
- 로컬 compose에 grounding-worker와 토픽 추가

### 제외

- 어느 구간·대상어로 요청할지, 클립 재사용 조회, 주석 상태 저장: search-service(다른 담당자) 몫이다.
- SSE 전달: notification-service(다른 담당자) 몫이다.
- 마스크(분할) 그리기와 SAM 계열 모델: 가중치가 준비되면 이후 spec에서 프로필 옵션으로 더한다. 지금은 박스와 대상어 라벨만 그린다.
- 탐지기 가중치 선택, 기준 신뢰도 값: AI 담당자 몫이다. 이 spec은 프로필 자리만 둔다.
- 얼굴·번호판 블러: 클립은 사용자가 이미 볼 수 있는 정규화 영상의 일부이고 외부 모델로 보내지 않는다. 블러는 외부로 나가는 이미지(ai-gateway 입력)에만 적용한다.

## 3. 사용자 시나리오

### US-1 검색 결과에서 대상 위치 보기 (P1)

안전관리자로서 "지게차 옆 안전모 안 쓴 작업자"를 검색했을 때 상위 결과 구간에 해당 대상이 박스로 표시된 클립을 보고 싶다. 왜냐하면 10초 구간 안에서 대상을 눈으로 다시 찾는 시간이 들기 때문이다.

#### 인수 조건

- Given 구간 하나와 대상어 2개가 담긴 `grounding.requested`, When 처리하면, Then 구간 길이의 H.264 클립(원본 fps, 원본에 오디오가 있으면 오디오 포함)과 결과 파일이 저장되고 `grounding.completed`(READY, 프레임별 객체 수 포함)가 발행된다.
- Given 대상어가 어떤 프레임에도 없음, When 처리하면, Then 박스 없는 클립과 객체 수 0이 담긴 READY가 발행된다.
- Given 같은 대상어는 요청이 달라도, When 클립을 그리면, Then 같은 색으로 그려진다.

### US-2 같은 주석을 다시 만들지 않음 (P2)

운영자로서 같은 검색이 반복돼도 탐지·인코딩 비용이 다시 들지 않기를 원한다.

#### 인수 조건

- Given 같은 groundingId·탐지기 버전의 결과 파일이 이미 있음, When 같은 요청이 다시 오면, Then 탐지와 인코딩을 하지 않고 저장된 결과로 같은 eventId의 `grounding.completed`를 다시 발행한다.

### US-3 실패를 알림 (P2)

사용자로서 주석 클립을 만들지 못했으면 기다리지 않게 실패 표시를 받고 싶다.

#### 인수 조건

- Given 영상 길이를 넘는 구간, When 처리하면, Then `outcome: FAILED`, `errorCode: GROUNDING_SEGMENT_OUT_OF_RANGE`가 발행된다.
- Given 정규화 영상을 읽지 못함, When 처리하면, Then `GROUNDING_SOURCE_UNREADABLE`로 FAILED가 발행된다.

## 4. 요구사항

### 기능 요구사항 (EARS)

| ID | 요구사항 | 시나리오 |
| --- | --- | --- |
| R-1 | WHEN grounding-worker가 `grounding.requested`를 받으면, THE grounding-worker SHALL `segments` 항목을 순서대로 하나씩 처리하고 항목마다 `grounding.completed`를 한 건 발행한다. | US-1 |
| R-2 | THE grounding-worker SHALL 구간 `[startMs, endMs)`에서 `startMs`부터 설정한 간격(기본 1초)으로 최대 12장의 샘플 프레임을 정규화 영상(`normalizedKey`)에서 뽑는다. | US-1 |
| R-3 | THE grounding-worker SHALL 요청의 대상어를 탐지기 텍스트 클래스로 지정해 샘플 프레임마다 탐지하고, 프로필 기준 신뢰도 이상인 탐지만 남긴다. | US-1 |
| R-4 | THE grounding-worker SHALL 구간의 모든 원본 프레임에 표시 시각이 가장 가까운 샘플 프레임의 박스와 대상어 라벨을 그려 원본 fps의 H.264 클립을 만들고, 원본에 오디오가 있으면 같은 구간의 오디오를 넣는다. | US-1 |
| R-5 | THE grounding-worker SHALL 대상어마다 박스 색을 대상어 UTF-8 바이트의 sha256 앞 3바이트(`#rrggbb`)로 정한다. | US-1 |
| R-6 | THE grounding-worker SHALL 클립을 `sources/<sourceId>/groundings/<groundingId>/<groundingModel>/clip.mp4`에, 결과 파일(`groundings/v1/grounding-result`)을 같은 폴더의 `result.json`에 이 순서로 저장한 뒤 READY `grounding.completed`를 발행한다. | US-1 |
| R-7 | THE grounding-worker SHALL READY `grounding.completed`의 `frames`에 샘플 프레임마다 대상어별 객체 수를 담는다. 탐지가 없으면 0으로 담는다. | US-1 |
| R-8 | IF R-6의 결과 파일이 이미 있으면, THEN THE grounding-worker SHALL 탐지·인코딩을 하지 않고 그 파일 내용으로 `grounding.completed`를 발행한다. | US-2 |
| R-9 | THE grounding-worker SHALL `grounding.completed`의 eventId를 groundingId와 탐지기 버전으로 결정적으로 만든다. | US-2 |
| R-10 | IF 구간 끝이 정규화 영상 길이를 넘거나 `endMs`가 `startMs` 이하이면, THEN THE grounding-worker SHALL 그 항목을 `GROUNDING_SEGMENT_OUT_OF_RANGE`로 FAILED 발행한다. | US-3 |
| R-11 | IF 정규화 영상이 없거나 디코딩하지 못하면, THEN THE grounding-worker SHALL 그 항목을 `GROUNDING_SOURCE_UNREADABLE`로 FAILED 발행한다. | US-3 |
| R-12 | IF 탐지기가 오류를 내면, THEN THE grounding-worker SHALL 그 항목을 `GROUNDING_DETECTOR_FAILED`로 FAILED 발행한다. | US-3 |
| R-13 | IF 항목 하나의 처리가 설정한 시간(기본 120초)을 넘으면, THEN THE grounding-worker SHALL 처리를 멈추고 그 항목을 `GROUNDING_TIMEOUT`으로 FAILED 발행한다. | US-3 |
| R-14 | IF 저장소·Kafka가 일시적으로 응답하지 않으면, THEN THE grounding-worker SHALL 메시지를 재시도 토픽으로 보내 다시 처리하고, R-8로 이미 끝낸 항목은 다시 만들지 않는다. | US-2 |
| R-15 | IF 메시지가 계약 스키마에 맞지 않거나 `normalizedKey`가 메시지의 sourceId·normalizationId 폴더가 아니면, THEN THE grounding-worker SHALL 재시도 없이 DLQ로 보낸다. | US-3 |
| R-16 | WHILE 메시지를 처리하는 동안, THE grounding-worker SHALL 파티션 소비를 멈춰 두고(pause) poll을 계속 불러 재배치에 응답하며, 끝나면 소비를 재개한다(resume). | US-1 |
| R-17 | THE grounding-worker SHALL 결과 파일과 `grounding.completed`에 탐지기 버전(가중치 manifest의 version)과 기준 신뢰도를 기록한다. | US-2 |
| R-18 | THE grounding-worker SHALL 처리 시간을 단계 `grounding.sample`·`grounding.detect`·`grounding.render`·`grounding.store`로 남긴다(SPEC-013). | US-1 |

### 비기능 요구사항

| ID | 요구사항 |
| --- | --- |
| NFR-1 | THE grounding-worker SHALL 로컬 compose(CPU)에서 1080p 30fps 10초 구간 하나를 p95 30초 안에 처리한다. |
| NFR-2 | THE grounding-worker SHALL 컨테이너 메모리 1.5GB 안에서 동작한다. |
| NFR-3 | THE grounding-worker SHALL 한 Pod에서 메시지를 한 번에 하나씩 처리하고, 모든 항목을 발행한 뒤 커밋한다. |

## 5. 영향 범위

| 레포 / 서비스 | 변경 개요 | 담당 요구사항 |
| --- | --- | --- |
| ai / grounding-worker | 새 워커: 샘플링, 개방 어휘 탐지, 클립 인코딩, 재사용, 실패 발행 | R-1~R-18, NFR-1~NFR-3 |
| ai / libs | 계약 모델(`GroundingRequested`, `GroundingCompleted`, 결과 파일), 단계 ID | R-6, R-9, R-18 |
| docs | 계약, overview 토픽 표, 서비스 카탈로그 | R-6, R-7 |
| docs / local | 로컬 compose에 grounding-worker, 토픽 `grounding.requested`·`grounding.completed`와 재시도·DLQ | R-14, R-15 |
| backend / search-service·notification-service (다른 담당자) | (이후) `grounding.requested` 발행, `grounding.completed` 소비 | — |

## 6. 계약 변경

| 계약 파일 | 변경 | 하위호환 |
| --- | --- | --- |
| `service-contracts/events/grounding.requested.schema.json` | 새 이벤트(생산자 확인 필요) | 예(추가) |
| `service-contracts/events/grounding.completed.schema.json` | 새 이벤트 | 예(추가) |
| `service-contracts/groundings/v1/grounding-result.schema.json` | 새 파일 형식 | 예(추가) |
| `service-contracts/asyncapi/grounding-worker.yaml` | 새 파일 | 예(추가) |
| `service-contracts/asyncapi/search-service.yaml` | `grounding.requested` 발행 채널(0.1.0 → 0.2.0) | 예(추가) |
| `service-contracts/stages/v1/stages.schema.json` | `grounding-worker.queue_wait`·`grounding-worker.handle`·`grounding.sample`·`grounding.detect`·`grounding.render`·`grounding.store` | 예(추가) |

계약 묶음 3.5.0 → 3.6.0

## 7. 성공 지표

- 로컬 compose에서 샘플 영상 구간 하나로 보낸 `grounding.requested`가 READY `grounding.completed`로 이어지고, 클립이 브라우저에서 재생되며 결과 파일이 계약 스키마를 통과한다.

## 8. 미결 사항

- 해당 없음
