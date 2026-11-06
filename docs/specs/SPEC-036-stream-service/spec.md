---
id: SPEC-036
title: stream-service 카메라·수집 세션·STREAM Job 창 단위 완료·라이브 읽기 모델
status: Approved
owner: <이름>
repos: [backend, docs]
created: 2026-11-06
updated: 2026-11-06
related: [ADR-0015, ADR-0016, SPEC-017, SPEC-027, SPEC-031, SPEC-037]
---

# SPEC-036 stream-service 카메라·수집 세션·STREAM Job 창 단위 완료·라이브 읽기 모델

> 이 문서에는 **무엇을, 왜**만 쓴다. 클래스, 테이블, 라이브러리 같은 구현 방법은 각 레포의 plan.md에 쓴다.

## 1. 배경과 목적

실시간 카메라 스트림을 업로드와 같은 파이프라인으로 처리한다([ADR-0015](../../adr/0015-realtime-window-pipeline.md)). 카메라 1대의 수집 세션 1개가 소스가 되고, stream-ingestor([SPEC-037](../SPEC-037-stream-ingestor/spec.md))가 창(기본 20초)마다 chunk-processor와 같은 산출물을 낸다. 창 이후의 워커는 입력이 청크인지 창인지 모른다.

업로드 Job은 pipeline-service가 소유하지만, 실시간 Job(`STREAM`)은 창 수가 미리 정해지지 않고 stop까지 열려 있어 업로드 Job 모델과 맞지 않는다. 그래서 [아키텍처 v5.1](../../architecture/architecture.md) 6절과 12절은 카메라 등록, 세션 시작·종료, `STREAM` Job 생명주기, 창 단위 완료 판정, 세션 중 라이브 읽기 모델을 stream-service에 맡긴다. 이 서비스가 있어야 pipeline-service·analysis-api(다른 담당자)의 변경 없이 실시간이 동작한다.

## 2. 범위

### 포함

- 카메라 등록·수정·삭제와 카메라별 구역 정의
- 수집 세션 start·stop, 24시간 자동 회전, Ingestor 임대 감시와 재시작 복구 명령
- `STREAM` Job 등록, 창 단위 완료 판정(`analysis.completed(scope: chunk)`), 세션 종료 완료(`scope: job`)
- 세션 시작 `version.activated` 발행
- 라이브 읽기 모델: `event.analyzed`·`state.updated`·`alert.raised`를 소비해 세션 중 타임라인·상태·알림을 저장하고 조회 API로 제공
- 활성 위험 구역을 Redis 세션 키에 반영
- 라이브·과거 재생 주소
- 계약: `openapi/stream-service.yaml`, `asyncapi/stream-service.yaml`, 이벤트 `stream.command`, `analysis.completed`(생산자 추가), `state.updated`(소비)
- 처리 단계 측정, 로컬 compose에 stream-service와 토픽 추가

### 제외

- RTSP 수신, 탐지·추적, 창 산출물, 긴급 후보 발행: SPEC-037(stream-ingestor)
- 긴급 후보 판정과 `alert.raised` 발행: SPEC-020·023(event-analyzer)
- 창 단위 fold와 `state.updated` 발행: SPEC-027·028(aggregator)
- SSE 전달: notification-service(다른 담당자). 소비 계약만 적는다.
- 세션 종료 뒤 보관 결과 저장과 활성 버전: analysis-api(다른 담당자). `source.completed`를 그대로 받는다.
- 화면: SPEC-031·032의 라이브 화면 항목
- 카메라 자격 증명 저장소 자체: 비밀값은 Secrets Manager 키 이름만 다룬다.

## 3. 사용자 시나리오

### US-1 카메라를 등록하고 수집을 시작한다 (P1)

안전관리자로서 현장 카메라의 RTSP 주소를 등록하고 수집을 시작해 분석 결과가 쌓이기를 원한다. 왜냐하면 업로드 없이도 현장을 계속 보고 싶기 때문이다.

#### 인수 조건

- Given 등록된 카메라, When start를 요청하면, Then 세션이 `STARTING`으로 만들어지고 sourceId·jobId가 응답에 있으며 `stream.command(start)`와 `version.activated`가 발행된다.
- Given 같은 카메라에 `LIVE` 세션이 있음, When start를 다시 요청하면, Then 409 `STREAM_SESSION_ALREADY_ACTIVE`다.
- Given `STARTING` 세션, When Ingestor의 첫 `chunk.manifest`가 오면, Then 세션이 `LIVE`가 된다.

### US-2 창마다 결과가 확정된다 (P1)

안전관리자로서 카메라 결과가 창 단위로 끊김 없이 확정되기를 원한다.

#### 인수 조건

- Given `LIVE` 세션의 창 하나에 `segment.indexed`와 `event.manifest`가 도착함, When 둘이 모이면, Then `analysis.completed(scope: chunk, jobType: STREAM)`이 그 창의 counts로 한 번 발행된다.
- Given 같은 창의 적재 신호가 중복 도착함, When 처리하면, Then `analysis.completed`는 한 번만 발행된다.
- Given 창의 신호가 프로필 시간(기본 120초) 안에 모이지 않음, When 시간이 지나면, Then 창을 `PARTIAL`로 닫고 그때까지의 counts로 `analysis.completed(scope: chunk)`를 낸다.

### US-3 수집을 멈추고 결과를 보관한다 (P1)

안전관리자로서 수집을 멈추면 세션 전체 결과가 업로드 영상처럼 보관되기를 원한다.

#### 인수 조건

- Given `LIVE` 세션, When stop을 요청하면, Then 세션이 `STOPPING`이 되고 Redis 세션 키에 `stop`이 기록된다.
- Given `STOPPING` 세션, When `chunk.manifest(last: true)`의 창까지 완료되면, Then `analysis.completed(scope: job)`이 발행되고 세션이 `CLOSED`가 된다.
- Given 세션이 프로필 최대 길이(기본 24시간)에 닿음, When 회전 점검이 돌면, Then 현재 세션이 닫히고 같은 카메라에 새 세션이 `previousSourceId`를 싣고 시작된다.

### US-4 세션 중 라이브 상태를 본다 (P1)

안전관리자로서 수집 중인 카메라의 현재 위험 상태, 최근 이벤트, 알림을 바로 보고 싶다.

#### 인수 조건

- Given `state.updated(sequence: 5)`를 받은 세션, When 상태를 조회하면, Then sequence 5 기준의 구역별 상태·활성 위험·노출 지표가 온다.
- Given sequence 5를 저장한 뒤 sequence 4가 늦게 도착함, When 처리하면, Then 무시되고 상태는 sequence 5다.
- Given `alert.raised(pending)` 뒤 같은 candidateId의 `confirmed`가 옴, When 알림을 조회하면, Then 알림 하나가 `confirmed` 상태로 보인다.

### US-5 Ingestor가 죽어도 세션이 이어진다 (P2)

운영자로서 Ingestor Pod가 재시작돼도 세션이 끊기지 않기를 원한다.

#### 인수 조건

- Given `LIVE` 세션의 임대 키가 TTL 뒤 사라짐, When 임대 감시가 돌면, Then 같은 sourceId·jobId로 `stream.command(start)`가 다시 발행되고 세션은 `LIVE`를 유지한다.

## 4. 요구사항

### 기능 요구사항 (EARS)

| ID | 요구사항 | 시나리오 |
| --- | --- | --- |
| R-1 | WHEN 사용자가 이름·RTSP 주소 참조(Secrets 키 이름)·프로필을 담아 카메라 등록을 요청하면, THE stream-service SHALL 카메라를 만들고 201과 cameraId를 반환한다. | US-1 |
| R-2 | THE stream-service SHALL 카메라마다 구역(이름·종류·다각형) 목록을 저장하고 `PUT …/cameras/{id}/zones`로 통째로 바꾼다. 구역 변경은 다음 세션 시작부터 적용한다. | US-1 |
| R-3 | WHEN 사용자가 카메라의 세션 start를 요청하면, THE stream-service SHALL 세션을 `STARTING`으로 만들고 sourceId(= normalizationId)·jobId를 발급하며, 같은 트랜잭션에서 `stream.command(action: start)`와 `version.activated(sequence: 1)`를 Outbox에 넣는다. | US-1 |
| R-4 | IF 같은 카메라에 `STARTING`·`LIVE`·`STOPPING` 세션이 있으면, THEN THE stream-service SHALL start를 409 `STREAM_SESSION_ALREADY_ACTIVE`로 거절한다. | US-1 |
| R-5 | THE stream-service SHALL 세션 시작 때 media-service 소스 목록에 `kind: STREAM`으로 등록을 요청해 삭제·보존 전파가 `video.deleted`로 오게 한다(생산자 확인 필요). | US-3 |
| R-6 | WHEN `jobType: STREAM`인 첫 `chunk.manifest`를 받으면, THE stream-service SHALL 세션을 `STARTING`에서 `LIVE`로 바꾼다. | US-1 |
| R-7 | WHEN `jobType: STREAM`인 `chunk.manifest`·`segment.indexed`·`event.manifest`를 받으면, THE stream-service SHALL (jobId, chunkId) 창 행을 만들거나 갱신해 신호 도착을 기록한다. 같은 신호의 중복 도착은 한 번으로 센다. | US-2 |
| R-8 | WHEN 창의 `segment.indexed`와 `event.manifest`가 모두 도착하면, THE stream-service SHALL 창 행을 잠근 트랜잭션에서 창을 `COMPLETED`로 바꾸고 `analysis.completed(scope: chunk, jobType: STREAM, chunkId, counts)`를 한 번 발행한다. counts는 그 창의 `event.manifest` 발행 수와 `chunk.manifest` 트랙 수다. | US-2 |
| R-9 | IF 창 행이 만들어진 뒤 프로필 시간(기본 120초) 안에 신호가 모이지 않으면, THEN THE stream-service SHALL 창을 `PARTIAL`로 닫고 그때까지의 counts와 `partial: true`로 `analysis.completed(scope: chunk)`를 발행하며, 그 뒤 도착한 신호는 무시한다. | US-2 |
| R-10 | WHEN 사용자가 세션 stop을 요청하면, THE stream-service SHALL 세션을 `STOPPING`으로 바꾸고 Redis 세션 키 `stream:session:<sourceId>:command`에 `stop`을 쓴다. | US-3 |
| R-11 | WHEN `chunk.manifest(last: true)`의 창이 `COMPLETED` 또는 `PARTIAL`이 되고 그보다 앞선 창이 모두 닫혔으면, THE stream-service SHALL `analysis.completed(scope: job, jobType: STREAM, session.previousSourceId)`를 발행하고 세션을 `CLOSED`로 바꾼다. | US-3 |
| R-12 | WHILE 세션이 `LIVE`이고 시작 뒤 프로필 최대 길이(기본 24시간)를 넘으면, THE stream-service SHALL 그 세션을 R-10과 같이 멈추고, 같은 카메라에 `previousSourceId`를 현재 sourceId로 한 새 세션을 R-3과 같이 시작한다. | US-3 |
| R-13 | THE stream-service SHALL `STARTING`·`LIVE` 세션의 임대 키 `stream:lease:<cameraId>`를 프로필 주기(기본 15초)마다 확인하고, 키가 없으면 같은 sourceId·jobId로 `stream.command(action: start, resume: true)`를 다시 발행한다. | US-5 |
| R-14 | IF 임대가 프로필 횟수(기본 5회) 연속으로 복구되지 않으면, THEN THE stream-service SHALL 세션을 `FAILED`로 바꾸고 R-11과 같이 `analysis.completed(scope: job)`을 발행한다. | US-5 |
| R-15 | WHEN `jobType: STREAM`인 `event.analyzed`를 받으면, THE stream-service SHALL 세션 타임라인에 이벤트 요약(eventId, 유형, 시각, severity, 판정 상태, 근거 프레임 경로)을 저장한다. | US-4 |
| R-16 | WHEN `state.updated`를 받으면, THE stream-service SHALL sequence가 저장된 값보다 클 때만 세션의 현재 상태(구역별 상태·활성 위험·노출 지표·규칙 이벤트)를 갱신하고, 작거나 같으면 무시한다. | US-4 |
| R-17 | WHEN R-16으로 상태가 갱신되면, THE stream-service SHALL 활성 위험이 있는 구역 ID 목록을 Redis 세션 키 `stream:session:<sourceId>:active-risk-zones`에 쓴다. | US-4 |
| R-18 | WHEN `alert.raised`를 받으면, THE stream-service SHALL candidateId로 알림을 만들거나 상태를 갱신한다(`pending → confirmed·dismissed`). `pending`이 `confirmed` 뒤에 오면 무시한다. | US-4 |
| R-19 | THE stream-service SHALL `GET …/sessions/{id}/state · events · alerts`로 세션의 현재 상태, 시각 범위의 이벤트, 알림 목록을 제공하고, 세션 소유자(등록한 사용자)와 운영자에게만 허용한다. | US-4 |
| R-20 | THE stream-service SHALL `GET …/sessions/{id}/playback`으로 라이브 HLS 주소(`LIVE`일 때)와 창 파일 범위 재생 주소(종료 뒤)를 서명해 제공한다. | US-4 |
| R-21 | THE stream-service SHALL `GET /internal/v1/stream/sessions/{id}/zones`로 세션 시작 때의 구역 목록을 내부 호출자에게 제공한다. | US-2 |
| R-22 | WHEN `video.deleted`를 받으면, THE stream-service SHALL 그 sourceId의 세션·창·타임라인·알림을 지우고 Redis 세션 키를 지운다. | US-3 |
| R-23 | THE stream-service SHALL `CLOSED`·`FAILED` 세션의 타임라인·상태·알림 행을 프로필 보존 기간(기본 7일) 뒤 지운다. 세션·창 행은 소스 삭제까지 남긴다. | US-3 |
| R-24 | IF `jobType: STREAM`인 메시지의 sourceId에 해당하는 세션이 없으면, THEN THE stream-service SHALL 메시지를 재시도 없이 DLQ로 보낸다. | US-2 |
| R-25 | THE stream-service SHALL 처리 시간을 단계 `stream.window-complete`·`stream.state-apply`로 남긴다(SPEC-013). | US-2 |

### 비기능 요구사항

| ID | 요구사항 |
| --- | --- |
| NFR-1 | THE stream-service SHALL 창의 마지막 신호 도착부터 `analysis.completed(scope: chunk)` 발행까지 p95 1초 안에 끝낸다. |
| NFR-2 | THE stream-service SHALL 카메라 100대가 동시에 `LIVE`일 때(초당 신호 약 15건) 조회 API p95 응답을 300ms 이하로 유지한다. |
| NFR-3 | THE stream-service SHALL 모든 상태 전이를 조건부 갱신으로 해 Pod 2개 이상에서 같은 이벤트가 두 번 발행되지 않게 한다. |

## 5. 영향 범위

| 레포 / 서비스 | 변경 개요 | 담당 요구사항 |
| --- | --- | --- |
| backend / stream-service | 새 서비스: 카메라·구역·세션·창·라이브 읽기 모델, Outbox, Redis 키, 임대 감시, 회전 점검 | R-1~R-25, NFR-1~NFR-3 |
| backend / api-gateway | `/api/v1/stream/**` 라우팅 | R-19, R-20 |
| docs | 계약, 아키텍처 6·11·12절, 서비스 카탈로그 | R-3, R-8, R-11, R-19 |
| docs / local | compose에 stream-service, 토픽 `stream.command`, Redis | R-3 |
| gitops | 서비스 배포 매니페스트 | — |

## 6. 계약 변경

| 계약 파일 | 변경 | 하위호환 |
| --- | --- | --- |
| `service-contracts/openapi/stream-service.yaml` | 신규. 카메라·구역·세션·조회·재생·내부 구역 | 예(신규) |
| `service-contracts/asyncapi/stream-service.yaml` | 신규. 발행 `stream.command`·`analysis.completed`·`version.activated`, 소비 `chunk.manifest`·`segment.indexed`·`event.manifest`·`event.analyzed`·`state.updated`·`alert.raised`·`video.deleted` | 예(신규) |
| `service-contracts/events/stream.command.schema.json` | 신규 | 예 |
| `service-contracts/events/analysis.completed.schema.json` | `jobType`에 `STREAM`, `scope`(`job`·`chunk`), `chunkId`, `partial` 선택 추가 | 예 |
| `service-contracts/events/state.updated.schema.json` | 신규(생산자 aggregator, SPEC-027) | 예 |
| `service-contracts/openapi/media-service.yaml` | 소스 `kind: STREAM` 등록(생산자 확인 필요) | 예 |

## 7. 성공 지표

- 카메라 10대 24시간 세션에서 창 완료 누락 0건, `PARTIAL` 비율 1% 이하
- stop 요청부터 `analysis.completed(scope: job)`까지 60초 이내
- 임대 소실 뒤 복구까지 60초 이내

## 8. 미결 사항

- 없음
