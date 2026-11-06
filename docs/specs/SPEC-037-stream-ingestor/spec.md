---
id: SPEC-037
title: stream-ingestor 카메라 스트림 창 단위 산출물·연속 추적·긴급 후보
status: Approved
owner: <이름>
repos: [ai, docs]
created: 2026-11-06
updated: 2026-11-06
related: [ADR-0009, ADR-0015, ADR-0016, SPEC-014, SPEC-019, SPEC-023, SPEC-036]
---

# SPEC-037 stream-ingestor 카메라 스트림 창 단위 산출물·연속 추적·긴급 후보

> 이 문서에는 **무엇을, 왜**만 쓴다. 클래스, 테이블, 라이브러리 같은 구현 방법은 각 레포의 plan.md에 쓴다.

## 1. 배경과 목적

실시간 카메라 스트림을 업로드와 같은 워커로 처리하려면, 스트림을 받아 창(기본 20초)마다 chunk-processor와 **같은 출력 계약**으로 산출물을 내는 워커가 필요하다([ADR-0015](../../adr/0015-realtime-window-pipeline.md), [아키텍처 v5.1](../../architecture/architecture.md) 4·6절). stream-ingestor는 "실시간용 chunk-processor"다. 다른 점은 입력이 파일이 아니라 스트림이고, 추적 상태를 창 사이에 끊지 않으며, 긴급 후보를 창 종료 전에 낸다는 것이다.

frame-encoder, event-analyzer, embedding-worker, aggregator, analysis-api, search-service는 입력이 청크인지 창인지 모른다. 선택 필드 `jobType: STREAM`만으로 track-stitcher와 pipeline-service가 실시간 메시지를 건너뛴다.

## 2. 범위

### 포함

- `stream.command(start)` 수신과 카메라 임대(Redis `SET NX`), 용량 초과 시 되돌리기
- RTSP 수신, 디코딩, 탐지·추적(워커 안 모델), 세션 전체에서 이어지는 트랙 ID와 `trackIdEpoch`
- 창마다 chunk-processor와 같은 5개 토픽(`segment.ready`·`event.candidate`·`track.detected`·`chunk.boundary`·`chunk.manifest`)과 같은 S3 경로 규칙
- 녹화 조각(HLS 6초)과 창 파일
- 긴급 후보 `alert.candidate`(severity high 유형, 활성 위험 구역 진입)
- Redis 세션 키 읽기: `stop`, `reload_profile`, 활성 위험 구역
- 종료 처리(`chunk.manifest.last`), SIGTERM 처리
- 계약: `asyncapi/stream-ingestor.yaml`, `alert.candidate` 스키마, 5개 토픽의 `jobType` 선택 필드, `chunk.manifest`의 `trackIdEpoch`·`last`
- 처리 단계 측정, 로컬 compose에 stream-ingestor와 테스트용 RTSP 소스 추가

### 제외

- 카메라 등록, 세션 생명주기, 창 완료 판정, 라이브 읽기 모델: SPEC-036(stream-service)
- 긴급 후보 판정·`alert.raised`: SPEC-020·023(event-analyzer)
- 탐지기 가중치·클래스·`supportedEvents` 선택과 Golden Set 조정: AI 담당자 몫. 이 spec은 chunk-processor와 같은 탐지 프로필을 쓴다.
- 엣지 장치 분리(Phase 2-3)

## 3. 사용자 시나리오

### US-1 창마다 업로드와 같은 산출물이 나온다 (P1)

실시간 담당자로서 카메라 창 하나가 업로드 청크 하나와 같은 메시지·경로로 나와, 기존 워커를 바꾸지 않고 처리되기를 원한다.

#### 인수 조건

- Given 세션이 시작된 카메라, When 창 하나(20초)가 끝나면, Then `segment.ready`·`event.candidate`·`track.detected`·`chunk.boundary`·`chunk.manifest`가 각 1건 발행되고 모두 `jobType: STREAM`, 같은 jobId·chunkId·executionId를 가진다.
- Given 같은 창, When S3 경로를 보면, Then `sources/<sourceId>/jobs/<jobId>/chunks/<chunkId>/executions/<executionId>/` 아래에 업로드와 같은 파일명이 있고 SPEC-019 R-16 경로 검사를 통과한다.
- Given 세션의 n번째 창, When chunkId를 보면, Then `uuid5(sourceId, n)`이다.

### US-2 추적이 창 사이에 끊기지 않는다 (P1)

안전관리자로서 작업자 한 명이 창 경계를 넘어도 같은 트랙으로 보이기를 원한다.

#### 인수 조건

- Given 창 1 끝까지 보이는 사람 트랙, When 창 2가 시작되면, Then 같은 trackId로 이어지고 `track.detected`에 같은 ID가 나온다.
- Given Pod 재시작으로 임대를 이어받음, When 첫 창을 내면, Then `chunk.manifest.trackIdEpoch`가 이전보다 1 크고 트랙 ID는 새 대역이다.

### US-3 쓰러짐은 창 종료를 기다리지 않는다 (P1)

안전관리자로서 쓰러짐·화재는 몇 초 안에 알림을 받고 싶다.

#### 인수 조건

- Given `alertImmediately: true` 유형(`fall`)의 후보가 최소 관측 수(2)를 넘음, When 그 프레임이 처리되면, Then 창 종료 전에 `alert.candidate`가 1건 발행되고 근거 프레임 1~4장과 결정적 candidateId가 있다.
- Given 같은 후보, When 창이 끝나면, Then 그 창의 `event.candidate`에 같은 candidateId의 후보가 들어 있다.
- Given Redis 세션 키의 활성 위험 구역에 사람이 들어옴, When 최소 관측 수를 넘으면, Then `hazard_zone_access` `alert.candidate`가 사유 `active_risk_zone`으로 발행된다.

### US-4 명령과 종료 (P1)

운영자로서 stop을 누르면 마지막 창까지 남기고 깨끗이 끝나기를 원한다.

#### 인수 조건

- Given Redis 세션 키에 `stop`, When 소유 Pod가 임대 갱신에서 읽으면, Then 진행 중 창을 마감해 발행하고 `chunk.manifest.last: true`로 끝낸 뒤 임대를 놓는다.
- Given SIGTERM, When 받으면, Then 진행 중 창을 마감해 발행하고 임대를 놓는다. 다른 Pod가 같은 sourceId로 이어받는다.

### US-5 용량 초과 (P2)

운영자로서 Pod 용량이 찼을 때 명령이 사라지지 않기를 원한다.

#### 인수 조건

- Given Pod당 카메라 수(기본 1)가 찬 Pod, When `stream.command(start)`를 받으면, Then 임대를 잡지 않고 메시지를 재시도 토픽으로 되돌린다.

## 4. 요구사항

### 기능 요구사항 (EARS)

| ID | 요구사항 | 시나리오 |
| --- | --- | --- |
| R-1 | WHEN stream-ingestor가 `stream.command(action: start)`를 받으면, THE stream-ingestor SHALL Redis `stream:lease:<cameraId>`를 `SET NX`(TTL 30초)로 잡고, 성공하면 소유자가 되어 RTSP 수신을 시작한다. | US-1 |
| R-2 | IF 이 Pod에 배정된 카메라 수가 프로필 용량(기본 1)에 닿았거나 임대 `SET NX`가 실패하면, THEN THE stream-ingestor SHALL 메시지를 재시도 토픽으로 보내 다른 Pod가 받게 한다. | US-5 |
| R-3 | THE stream-ingestor SHALL 임대를 10초마다 갱신하고, 갱신에 실패하면(키가 다른 Pod의 것이거나 없음) 수신을 멈추고 진행 중 창을 버린다. | US-4 |
| R-4 | THE stream-ingestor SHALL 세션 시작 시각을 PTS 0으로 삼고, 모든 산출물의 시각을 세션 시작 기준 정수 밀리초로 기록한다. `normalizationId`는 sourceId와 같다. | US-1 |
| R-5 | THE stream-ingestor SHALL 프로필 창 길이(기본 20초, 10~30초)마다 창을 닫고 순번 n에 대해 `chunkId = uuid5(sourceId, n)`, 창마다 새 `executionId`를 발급하며, 창의 소유 범위는 `[n×창 길이, (n+1)×창 길이)`, 처리 범위는 앞뒤 5초를 더한 범위다. | US-1 |
| R-6 | THE stream-ingestor SHALL 창마다 chunk-processor와 같은 규칙으로 구간(10초 창·5초 간격, 프레임 4장, PTS 키 블러 사본), 탐지기 후보(실행당 `event.candidate` 1건, 0건 포함, 256개 초과면 파일), 트랙 요약과 검출 박스 파일, 경계 트랙 파일, 정적 객체 재고를 만들어 같은 S3 경로 규칙에 저장한다. | US-1 |
| R-7 | THE stream-ingestor SHALL 창마다 `segment.ready`·`event.candidate`·`track.detected`·`chunk.boundary`·`chunk.manifest`를 chunk-processor와 같은 필드로 각 1건 발행하고 `jobType: STREAM`을 싣는다. `chunk.execution.finished`는 발행하지 않는다. | US-1 |
| R-8 | THE stream-ingestor SHALL 탐지·추적을 세션 전체에서 끊지 않고 이어 같은 객체에 같은 trackId를 유지하며, `track.detected`의 트랙 ID를 세션 trackId로 낸다(청크 로컬 ID 없음). | US-2 |
| R-9 | WHEN 임대를 이어받아 세션을 재개하면(`resume: true`), THE stream-ingestor SHALL `trackIdEpoch`를 이전 값보다 1 크게 해 새 트랙 ID 대역을 쓰고 `chunk.manifest.trackIdEpoch`에 기록한다. | US-2 |
| R-10 | THE stream-ingestor SHALL 창의 `chunk.manifest`에 창 산출물 수(구간·후보·트랙), 탐지기 능력과 `unsupportedEvents`, 정적 객체 재고, `trackIdEpoch`, 프로필 버전을 싣는다. | US-1 |
| R-11 | WHEN 이벤트 정의 목록에서 `alertImmediately: true`인 유형의 후보가 최소 관측 수를 넘으면, THE stream-ingestor SHALL 창 종료를 기다리지 않고 `alert.candidate`(candidateId, 유형, 트랙, 구역, 근거 프레임 1~4장, 사유 `severity_high`)를 1건 발행한다. 같은 (트랙, 유형) 후보는 프로필 간격(기본 60초) 안에 다시 내지 않는다. | US-3 |
| R-12 | WHEN Redis 세션 키 `stream:session:<sourceId>:active-risk-zones`에 있는 구역에 사람 트랙이 들어와 최소 관측 수를 넘으면, THE stream-ingestor SHALL `hazard_zone_access` `alert.candidate`를 사유 `active_risk_zone`으로 발행한다. | US-3 |
| R-13 | THE stream-ingestor SHALL `alert.candidate`의 candidateId를 창 `event.candidate`의 같은 후보와 같은 규칙(`uuid5(sourceId, trackId, eventType, 최초 관측 PTS)`)으로 만들고, 알림을 낸 후보를 그 창의 `event.candidate`에 반드시 포함한다. | US-3 |
| R-14 | THE stream-ingestor SHALL 임대 갱신마다 Redis 세션 키 `stream:session:<sourceId>:command`를 읽고, `stop`이면 진행 중 창을 마감해 발행하고 `chunk.manifest.last: true`를 낸 뒤 임대를 놓고, `reload_profile`이면 다음 창부터 새 프로필을 적용한다. | US-4 |
| R-15 | WHEN SIGTERM을 받으면, THE stream-ingestor SHALL 진행 중 창을 마감해 발행하고(`last`는 싣지 않음) 임대를 놓은 뒤 종료한다. | US-4 |
| R-16 | THE stream-ingestor SHALL 재생용 HLS 조각(6초)을 `sources/<sourceId>/live/hls/`에, 창 파일을 `sources/<sourceId>/live/<chunkId>.mp4`에 저장한다. 보존은 프로필 값(HLS 24시간, 창 파일 7일)이다. | US-1 |
| R-17 | IF RTSP 연결이 끊기면, THEN THE stream-ingestor SHALL 프로필 간격(기본 5초)으로 재연결하고, 끊긴 동안의 창은 내지 않으며, 재연결 뒤 첫 `chunk.manifest`에 `gapMs`를 기록한다. 재연결이 프로필 시간(기본 5분) 넘게 실패하면 임대를 놓는다. | US-4 |
| R-18 | THE stream-ingestor SHALL ai-gateway를 부르지 않고 외부로 프레임을 보내지 않는다. 블러 사본만 S3에 저장한다. | US-1 |
| R-19 | IF `stream.command`가 계약 스키마에 맞지 않으면, THEN THE stream-ingestor SHALL 재시도 없이 DLQ로 보낸다. | US-5 |
| R-20 | THE stream-ingestor SHALL 처리 시간을 단계 `ingest.window`(창 마감부터 발행까지)·`ingest.alert`(관측 초과부터 `alert.candidate` 발행까지)로 남긴다(SPEC-013). | US-1, US-3 |

### 비기능 요구사항

| ID | 요구사항 |
| --- | --- |
| NFR-1 | THE stream-ingestor SHALL 1080p 5fps 카메라 1대를 CPU 1 vCPU·메모리 2GB 안에서 실시간(처리 지연 1초 미만)으로 처리한다. |
| NFR-2 | THE stream-ingestor SHALL 창 마감부터 5개 토픽 발행까지 p95 3초 안에 끝낸다. |
| NFR-3 | THE stream-ingestor SHALL `alert.candidate`를 관측 초과 프레임 처리 뒤 p95 1초 안에 발행한다. |

## 5. 영향 범위

| 레포 / 서비스 | 변경 개요 | 담당 요구사항 |
| --- | --- | --- |
| ai / stream-ingestor | 새 워커: 명령 수신·임대, RTSP 수신, 탐지·추적, 창 산출물, 긴급 후보, 녹화 | R-1~R-20, NFR-1~NFR-3 |
| ai / libs | 계약 모델(`StreamCommand`, `AlertCandidate`, 5개 토픽의 `jobType`), 단계 ID | R-7, R-11 |
| ai / track-stitcher | `jobType: STREAM`이면 건너뜀(SPEC-022 갱신) | R-7 |
| docs | 계약, 아키텍처 4·6절 | R-5, R-7, R-13 |
| docs / local | compose에 stream-ingestor, 테스트용 RTSP 소스, 토픽 `stream.command`·`alert.candidate` | R-1 |

## 6. 계약 변경

| 계약 파일 | 변경 | 하위호환 |
| --- | --- | --- |
| `service-contracts/asyncapi/stream-ingestor.yaml` | 신규. 소비 `stream.command`, 발행 5개 토픽 + `alert.candidate` | 예(신규) |
| `service-contracts/events/alert.candidate.schema.json` | 신규 | 예 |
| `service-contracts/events/segment.ready · event.candidate · track.detected · chunk.boundary · chunk.manifest` | 선택 필드 `jobType`(없으면 `FULL`) | 예 |
| `service-contracts/events/chunk.manifest.schema.json` | 선택 필드 `trackIdEpoch`, `last`, `gapMs` | 예 |
| `service-contracts/stages/v1/stages.schema.json` | `ingest.window`, `ingest.alert` | 예 |
| `service-contracts/taxonomy/v2/` 이벤트 정의 목록 | `alertImmediately`, `rejudgeIntervalS` | 예 |

## 7. 성공 지표

- 창 산출물이 chunk-processor 계약 테스트(같은 스키마·경로 검사)를 100% 통과
- 긴급 후보 발행 지연 p95 1초 이하, 창 발행 지연 p95 3초 이하
- 카메라 1대 24시간에서 창 누락 0건(RTSP 끊김 구간 제외)

## 8. 미결 사항

- 없음
