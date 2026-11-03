---
id: SPEC-007
title: 영상 정규화
status: Implementing
owner: <이름>
repos: [ai, backend, frontend, docs]
created: 2026-11-03
updated: 2026-11-03
related: [ADR-0002, ADR-0008, SPEC-003, SPEC-004, SPEC-006]
---

# SPEC-007 영상 정규화

> 이 문서에는 **무엇을, 왜**만 쓴다. 클래스, 테이블, 라이브러리 같은 구현 방법은 각 레포의 plan.md에 쓴다.

## 1. 배경과 목적

사용자가 올린 원본은 코덱, 컨테이너, 프레임률이 제각각이다. 그대로 분석하면 프레임 시각(PTS)이 영상마다 다르게 해석되고, 브라우저가 열지 못하는 형식도 섞인다. 분석을 시작하기 전에 원본을 한 번 검증하고 **정규화 사본** 하나로 맞춘다. 이후 청크 계획(SPEC-004), 구간 추출, 탐지, 이벤트 시각은 모두 이 사본의 PTS(연동 정수 밀리초, 호환 표시 초)를 기준으로 한다([아키텍처 개요](../../architecture/overview.md) "분석 처리 흐름" 3단계, [ADR-0008](../../adr/0008-industrial-safety-v3.md)).

분석할 수 없는 영상은 이 단계에서 이유와 함께 거절해서, 뒤 단계가 비용을 쓰기 전에 사용자에게 알린다. 재생용 HLS 조각도 여기서 만들어 두고, 재생에 쓰는 일은 다음 spec에서 다룬다. PRD의 에픽은 아직 정의되지 않았다.

## 2. 범위

### 포함

- normalize 워커: `video.uploaded`를 받아 원본 검증, 정규화 사본과 HLS 조각 저장, 처리 시작(`video.normalizing`)과 결과(`video.normalized`) 발행
- 거절 기준: 영상 스트림·길이·프레임률을 읽을 수 없음, 디코딩 실패, 길이 1초 미만 또는 4시간 초과
- media-service: 두 이벤트를 받아 상태를 `UPLOADED` → `NORMALIZING` → `READY` 또는 `REJECTED`로 바꾸고, 영상 길이·예상 처리 시간·거절 사유를 영상 조회 API에 내보냄
- 예상 처리 시간: 영상 길이 × 처리 계수(설정 값)
- normalize의 health 엔드포인트(`/health`, `/ready`)
- frontend: 바뀐 계약으로 API 타입 다시 생성(화면 변경 없음)

### 제외

- HLS 재생 주소 발급, 플레이어 교체(hls.js 등): 다음 "정규화 사본 재생" spec
- 화면에 영상 길이·예상 처리 시간·거절 사유 표시: 다음 frontend spec
- 비용 견적: AI 호출 실측이 생긴 뒤 따로 다룬다
- 정규화가 끝나지 않고 멈춘 영상의 타임아웃·재처리 도구
- 해상도 변경(다운스케일)
- 청크 계획 시작(pipeline-service가 `video.normalized`를 받아 처리, SPEC-004 이후 범위)

## 3. 사용자 시나리오

### US-1 올린 영상이 분석 준비 상태가 됨 (P1)

로그인한 사용자로서 영상을 올린 뒤 분석을 시작할 수 있는 상태가 되었는지 알고 싶다. 왜냐하면 언제 결과를 볼 수 있을지 가늠하고 싶기 때문이다.

#### 인수 조건

- Given 업로드 완료된 H.264 mp4 영상, When 정규화가 시작되면, Then 영상 상태가 "정규화 중"(`NORMALIZING`)이 된다.
- Given 정규화 중인 영상, When 정규화가 성공하면, Then 상태가 "준비됨"(`READY`)이 되고 영상 조회에 영상 길이(초)와 예상 처리 시간(초)이 나온다.
- Given 가변 프레임률이거나 H.264가 아닌 영상, When 정규화가 성공하면, Then 고정 프레임률 H.264 사본이 만들어지고 상태는 "준비됨"이다.

### US-2 분석할 수 없는 영상은 이유와 함께 거절됨 (P1)

로그인한 사용자로서 분석할 수 없는 영상을 올렸다면 그 이유를 알고 싶다. 왜냐하면 다른 파일로 다시 올릴지 판단해야 하기 때문이다.

#### 인수 조건

- Given 영상 스트림이 없는 파일(음성만 있는 파일 등), When 정규화하면, Then 상태가 "거절됨"(`REJECTED`)이 되고 거절 사유 `NO_VIDEO_STREAM`이 나온다.
- Given 4시간이 넘는 영상, When 정규화하면, Then 거절 사유 `TOO_LONG`으로 거절된다.
- Given 거절된 영상, When 원본 재생을 요청하면, Then 원본은 계속 재생·내려받기할 수 있다(SPEC-006).

### US-3 분석 단계가 같은 기준의 영상을 받음 (P1)

분석 파이프라인(pipeline-service, chunk-processor)으로서 정규화된 영상 하나와 그 길이·프레임률을 받고 싶다. 왜냐하면 모든 시각을 같은 PTS 기준으로 계산해야 하기 때문이다.

#### 인수 조건

- Given 정규화에 성공한 영상, When `video.normalized`를 받으면, Then 정규화 사본과 HLS 재생 목록의 저장 경로, PTS 기준 영상 길이, 프레임률, 해상도를 알 수 있다.
- Given 같은 영상의 `video.uploaded`를 두 번 받음, When 둘 다 처리하면, Then 저장 경로와 `video.normalized`의 이벤트 ID가 같아 소비자가 중복을 흡수할 수 있다.

### US-4 운영 환경에서 워커 상태 확인 (P2)

운영자로서 normalize Pod가 살아 있고 일할 준비가 됐는지 쿠버네티스 프로브로 확인하고 싶다. 왜냐하면 멈춘 Pod를 자동으로 재시작해야 하기 때문이다.

#### 인수 조건

- Given 소비 루프가 돌고 있는 Pod, When `/health`를 부르면, Then 200을 받는다.
- Given 설정 검증이 끝나지 않은 Pod, When `/ready`를 부르면, Then 503을 받는다.

## 4. 요구사항

용어

- **정규화 사본**: 브라우저와 분석이 모두 읽을 수 있는 H.264 영상(음성이 있으면 AAC) mp4 파일 하나. 재생 정보(moov)를 파일 앞에 둔다.
- **복사 경로**: 원본 영상이 H.264이고 고정 프레임률이면 영상을 다시 인코딩하지 않고 컨테이너만 바꾼다.
- **재인코딩 경로**: 그 밖의 영상은 H.264 고정 프레임률로 다시 인코딩한다. 프레임률은 원본 평균 프레임률이되 30을 넘지 않는다. 해상도는 바꾸지 않는다.
- 길이 하한(1초), 상한(4시간), 프레임률 상한(30), HLS 조각 길이(기본 6초), 처리 계수는 설정 값이다.

### 기능 요구사항 (EARS)

| ID | 요구사항 | 시나리오 |
| --- | --- | --- |
| R-1 | WHEN normalize가 `video.uploaded`를 받으면, THE normalize SHALL 원본을 검증하기 전에 `video.normalizing`을 발행한다. | US-1 |
| R-2 | WHEN 원본이 거절 조건(R-7~R-12)에 하나도 해당하지 않으면, THE normalize SHALL 정규화 사본을 저장한다. | US-1, US-3 |
| R-3 | WHERE 원본 영상이 H.264이고 고정 프레임률인 경우, THE normalize SHALL 다시 인코딩하지 않고 복사 경로로 정규화 사본을 만든다. | US-1 |
| R-4 | WHERE 원본 영상이 H.264가 아니거나 가변 프레임률인 경우, THE normalize SHALL 원본 평균 프레임률(최대 30)의 고정 프레임률 H.264로 다시 인코딩한다. | US-1 |
| R-5 | WHEN 정규화 사본을 저장하면, THE normalize SHALL 정규화 사본에서 HLS 재생 목록과 조각을 만들어 저장한다. | US-3 |
| R-6 | WHEN 정규화 사본과 HLS를 모두 저장하면, THE normalize SHALL 결과 `READY`, 두 저장 경로, 정규화 사본의 durationMs(정수 밀리초)와 같은 값의 durationSec(호환 초), normalizationId·normalizationVersion, 프레임률, 가로·세로 픽셀, 재인코딩 여부를 담아 `video.normalized`를 발행한다. | US-1, US-3 |
| R-7 | IF 원본을 열 수 없으면, THEN THE normalize SHALL 결과 `REJECTED`, 거절 사유 `UNREADABLE`로 `video.normalized`를 발행한다. | US-2 |
| R-8 | IF 원본에 영상 스트림이 없으면, THEN THE normalize SHALL 거절 사유 `NO_VIDEO_STREAM`으로 거절한다. | US-2 |
| R-9 | IF 영상 길이나 프레임률을 읽을 수 없으면, THEN THE normalize SHALL 거절 사유 `MISSING_METADATA`로 거절한다. | US-2 |
| R-10 | IF 영상 길이가 1초 미만이면, THEN THE normalize SHALL 거절 사유 `TOO_SHORT`로 거절한다. | US-2 |
| R-11 | IF 영상 길이가 4시간을 넘으면, THEN THE normalize SHALL 거절 사유 `TOO_LONG`으로 거절한다. | US-2 |
| R-12 | IF 원본 영상을 디코딩하다 실패하면, THEN THE normalize SHALL 거절 사유 `DECODE_FAILED`로 거절한다. | US-2 |
| R-13 | IF 원본 품질과 무관한 이유(저장소·Kafka 장애 등)로 처리하지 못하면, THEN THE normalize SHALL 거절하지 않고 다시 시도하며, 끝내 실패한 메시지는 DLQ에 남긴다. | US-1 |
| R-14 | THE normalize SHALL 같은 영상에 대해 저장 경로와 `video.normalized` 이벤트 ID를 정규화 결과 식별자별로 불변하게 만든다. 같은 결과 재전달은 같은 ID를 쓰고, 실제 재정규화는 새 normalizationId·저장 경로·eventId를 사용한다. `video.normalizing`은 기존 시작 신호 정책을 유지한다. | US-3 |
| R-15 | WHEN media-service가 `video.normalizing`을 받고 영상이 `UPLOADED`이면, THE media-service SHALL 영상을 `NORMALIZING`으로 바꾼다. | US-1 |
| R-16 | WHEN media-service가 결과 `READY`인 `video.normalized`를 받고 영상이 `UPLOADED` 또는 `NORMALIZING`이면, THE media-service SHALL 영상을 `READY`로 바꾸고 영상 길이, 정규화 사본·HLS 경로, 예상 처리 시간을 저장한다. | US-1 |
| R-17 | WHEN media-service가 결과 `REJECTED`인 `video.normalized`를 받고 영상이 `UPLOADED` 또는 `NORMALIZING`이면, THE media-service SHALL 영상을 `REJECTED`로 바꾸고 거절 사유를 저장한다. | US-2 |
| R-18 | IF 받은 정규화 이벤트가 위 전이 조건에 맞지 않으면(이미 `READY`·`REJECTED`, 늦게 온 `video.normalizing` 등), THEN THE media-service SHALL 상태를 바꾸지 않는다. | US-1, US-3 |
| R-19 | IF media-service가 `DELETED` 영상의 `video.normalized`를 받으면, THEN THE media-service SHALL 그 영상 ID 아래 저장소 파일을 다시 지운다. | US-3 |
| R-20 | THE media-service SHALL 예상 처리 시간을 영상 길이(초) × 처리 계수로 계산하고 정수 초로 올림한다. | US-1 |
| R-21 | WHEN 영상 조회(목록·상세)에 응답하면, THE media-service SHALL `READY`인 영상에 영상 길이와 예상 처리 시간을, `REJECTED`인 영상에 거절 사유를 담고 그 밖에는 null로 둔다. | US-1, US-2 |
| R-22 | THE normalize SHALL 컨테이너 포트 8000에서 `/health`는 소비 루프가 최근 60초 안에 돌았으면 200, 아니면 503으로 응답한다. | US-4 |
| R-23 | THE normalize SHALL `/ready`는 설정 검증과 Kafka 구독 시작이 끝났으면 200, 아니면 503으로 응답한다. | US-4 |

### 비기능 요구사항

| ID | 요구사항 |
| --- | --- |
| NFR-1 | THE normalize SHALL 복사 경로에서 1080p 10분 영상을 저장소 입출력 포함 60초 안에 처리한다(로컬 compose, 2 vCPU 기준). |
| NFR-2 | THE normalize SHALL 재인코딩 경로에서 1080p 영상을 영상 길이 이하의 시간에 처리한다(2 vCPU 기준). |
| NFR-3 | THE normalize SHALL 처리 중 Pod가 종료되면 결과를 발행하지 않고 메시지를 커밋하지 않아, 다른 Pod가 처음부터 다시 처리하게 한다. |
| NFR-4 | THE normalize SHALL 로그에 원본 파일 이름과 사용자 정보를 남기지 않고 영상 ID로만 식별한다. |
| NFR-5 | THE normalize SHALL 원본·작업 파일을 Pod 안 임시 폴더에만 두고 처리가 끝나면(성공·실패 모두) 지운다. |
| NFR-6 | THE media-service SHALL 같은 정규화 이벤트를 여러 번 받아도 상태를 한 번만 바꾼다(여러 Pod 포함). |

## 5. 영향 범위

| 레포 / 서비스 | 변경 개요 | 담당 요구사항 |
| --- | --- | --- |
| ai / normalize | 새 워커: 검증, 정규화 사본, HLS, 두 이벤트 발행, health | R-1~R-14, R-22, R-23, NFR-1~NFR-5 |
| ai / libs | `libs/contracts`에 이벤트 모델 추가, `libs/common`에 워커 health 서버 | R-6, R-22, R-23 |
| backend / media-service | 두 이벤트 소비, 상태 전이, 길이·경로·예상 시간·거절 사유 저장, 조회 응답 필드 추가 | R-15~R-21, NFR-6 |
| frontend | API 타입 다시 생성(화면 변경 없음) | — |
| docs | 이벤트 계약 2종, media-service API 계약 필드 추가, 로컬 compose에 normalize 추가 | — |
| gitops·infra | (이후) normalize 배포 매니페스트와 프로브 설정. 사용자 지시 시 진행한다. | — |

## 6. 계약 변경

| 계약 파일 | 변경 | 하위호환 |
| --- | --- | --- |
| `docs/contracts/events/video.normalizing.schema.json` | 새 이벤트: envelope만 | 예(추가) |
| `docs/contracts/events/video.normalized.schema.json` | 새 이벤트: `normalizationId`, `normalizationVersion`, `durationMs`(READY), `result`(`READY`·`REJECTED`), `rejectReason`, `normalizedKey`, `hlsPlaylistKey`, `durationSec`, `fps`, `width`, `height`, `transcoded` | 예(추가) |
| `docs/contracts/asyncapi/normalize.yaml` | 새 파일: normalize가 발행하는 두 채널. 메시지 키는 sourceId | 예(추가) |
| `docs/contracts/openapi/media-service.yaml` | `VideoResponse`에 선택 필드 `durationSec`, `estimatedProcessingSec`, `rejectReason` 추가, `VideoStatus` 설명 갱신. 1.1.0 → 1.2.0 | 예(선택 필드 추가) |

소비자: media-service(두 이벤트), pipeline-service(`video.normalized`, 다른 작업자), frontend(타입 생성).

## 7. 성공 지표

- 로컬 compose에서 H.264 mp4, 가변 프레임률 영상, HEVC 영상을 올리면 모두 `READY`가 되고, 음성 파일과 깨진 파일은 사유와 함께 `REJECTED`가 된다.
- `READY` 영상의 HLS 재생 목록을 내려받아 재생 도구(ffplay 등)로 재생할 수 있다.
- 같은 `video.uploaded`를 다시 발행해도 저장 결과와 상태가 바뀌지 않는다.

## 8. 미결 사항

- 없음

### Pipeline 수신과의 호환 보완 (사용자 확정)

SPEC-008과 공유하는 video.normalized는 READY/REJECTED와 기존 메타데이터를 유지한다. READY는 normalizationId(UUID), normalizationVersion, normalizedKey·hlsPlaylistKey, 정수 durationMs와 정확히 일치하는 durationSec를 담는다. 객체 경로는 `sources/<sourceId>/normalizations/<normalizationId>/` 아래의 불변 참조다. REJECTED는 결과 식별자·버전·rejectReason을 담고 성공 메타데이터는 생략 또는 null이다. Pipeline은 이를 기록만 하고 계획하지 않는다. 구문상 같은 eventId의 변경 payload 및 같은 normalizationId의 다른 결과는 충돌이다. 변경은 아직 normalize 런타임 구현을 완료했다는 뜻이 아니다.

기존 v1 계약은 그대로 보존하고 위 보완은 schemaVersion=2로 발행한다. video.normalized.schema.json은 v1/v2 합집합, video.normalized.v2.schema.json은 Pipeline용 v2 원본이다. 신규 producer의 v2 전환은 구현 작업에서 반영하며 이번 수신 구현이 producer를 자동 교체하지 않는다.
