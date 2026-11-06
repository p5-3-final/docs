---
updated: 2026-11-06
---

# 서비스 카탈로그

> 서비스를 추가하거나 변경하면 이 표를 먼저 고친다(ADR이 필요할 수 있음). 담당은 정해지면 채운다. 배포 단위 구성의 근거는 [ADR-0008](../adr/0008-industrial-safety-v3.md)이고, v4 확장 자리는 [ADR-0010](../adr/0010-v4-evaluation-readiness.md)(배포 단위 수는 같음), 실시간 2개는 [ADR-0015](../adr/0015-realtime-window-pipeline.md), 흐름은 [아키텍처 v5.1](architecture.md)에 있다. 모든 소비자는 공통 메시징 라이브러리로 `stage.timing`을 발행한다(아래 표에서는 생략).

배포 단위는 21개다. Spring 10개(사용자 요청, 업무 상태, 저장과 조회, 품질 검토, 실시간 세션)와 Python 11개(영상 디코딩, 객체 탐지·추적, 실시간 수집, 이미지 벡터, bbox 주석, 외부 AI 호출)로 나눈다. 모델 ID·차원·탐지 프로필은 코드가 아니라 프로필 값이다(아키텍처 15절).

## Edge · Domain (backend, Spring)

| 서비스 | 경로 | 책임 | 받는 이벤트 → 내보내는 이벤트 | 로컬 포트 | DB | 계약 | 담당 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| api-gateway | `services/api-gateway` | 라우팅, JWT 검증(JWKS), 사용자 헤더 주입, CORS, rate limit, 알림 티켓 검증 | — | 8080 | — (Redis) | — | |
| auth-service | `services/auth-service` | 회원, 로그인, 토큰 발급·재발급·폐기, 역할, 공개키(JWKS), 알림 티켓 | — | 8081 | auth_db | `openapi/auth-service.yaml` | |
| media-service | `services/media-service` | 업로드 자리 발급, 완료 확인(조건부 전이), 원본 재생 주소, 정규화 결과 반영, 사전 견적, 삭제 전파, v4 작업 세션·학습용 보존 동의·보존 키·외부 데이터셋 영상 등록 | `video.normalized` → `video.uploaded`, `video.deleted`, `video.retention.revoked` | 8082 | media_db | `openapi/media-service.yaml` | |
| pipeline-service | `services/pipeline-service` | 계획 저장과 배정 분리(실행·슬롯·요청 Outbox는 배정 시), 3단계 공정성, 실행 집계·소유자 조회, 적재 완료 기준 완료 판정, 재판정·재임베딩 job | `video.normalized`, `chunk.execution.finished`, `chunk.manifest`, `segment.indexed`, `event.manifest`, `track.manifest` → `chunk.requested`, `analysis.completed`, `job.status` | 8083 | pipeline_db | `openapi/pipeline-service.yaml` | backend |
| analysis-api | `services/analysis-api` | 이벤트 타임라인·상세·검토, 위험 상태·상태 스냅샷 저장·조회, 위험구역 정의, 클릭 조회, 오버레이, 요약, 활성 버전, 트랙 속성 요청, 객체 자유 질문, aggregator·search-service용 내부 읽기 API | `event.analyzed`, `track.detected`, `track.analyzed`, `source.completed` → `attribute.requested`, `version.activated` | 8084 | analysis_db | `openapi/analysis-service.yaml` | 다른 작업자 |
| analysis-loader | `services/analysis-loader` | 검출 박스·트랙 위치 파일 대량 적재(analysis-api와 DB 공유, 분리 배포) | `track.detected` → — | 8085 | analysis_db | — | 다른 작업자 |
| search-service | `services/search-service` | 문장·이미지로 장면 찾기(질의 해석·시각/텍스트 검색·정밀 검색 선택), 구간·크롭 벡터 적재, bbox 주석 요청, Video RAG, 결과 재사용, 구간 주석 | `segment.embedded`, `embedding.ready`, `grounding.completed`, `version.activated`, `video.deleted` → `segment.indexed`, `segment.annotated`, `grounding.requested` | 8086 | search_db (pgvector) | `openapi/search-service.yaml` | 다른 작업자 |
| notification-service | `services/notification-service` | 진행률·분석 완료·트랙 속성·주석 클립 도착·긴급 알림·실시간 상태 알림(SSE) | `job.status`, `source.completed`, `track.analyzed`, `grounding.completed`, `alert.raised`(v5.1), `state.updated`(v5.1) → — | 8087 | — (Redis) | `openapi/notification-service.yaml` | 다른 작업자 |
| quality-service | `services/quality-service` | 검토 큐(`reviewRequired`·표본·`unverifiedReason`·기각된 긴급 알림), Golden Set 버전 관리, 평가 리포트, CI Gate·회귀 평가 결과, v4 라벨 3종(bbox·구간·상태 변화)·외부 데이터셋 가져오기·특징 내보내기·처리 단계 성능 리포트, 긴급 알림 지표 | `event.analyzed`, `alert.raised`(v5.1), `stage.timing`, `source.completed`, `video.deleted` → — | 8088 | quality_db | `openapi/quality-service.yaml` ([SPEC-029](../specs/SPEC-029-quality-service/spec.md)) | |
| stream-service | `services/stream-service` | 카메라 등록·구역, 수집 세션 start·stop·24시간 회전, Ingestor 임대 감시, `STREAM` Job 소유와 창 단위 완료 판정, 세션 중 라이브 읽기 모델(상태·타임라인·알림), 활성 위험 구역 Redis 반영, 라이브·과거 재생 주소 (v5.1) | `chunk.manifest`, `segment.indexed`, `event.manifest`, `event.analyzed`(STREAM만), `state.updated`, `alert.raised`, `video.deleted` → `stream.command`, `analysis.completed`(STREAM), `version.activated` | 8089 | stream_db (+ Redis 세션 키) | `openapi/stream-service.yaml`, `asyncapi/stream-service.yaml` ([SPEC-036](../specs/SPEC-036-stream-service/spec.md)) | 사용자 |

## Data Plane (Python 경로와 담당 분리)

아래 경로는 기존 물리적 배치의 목표다. normalize·chunk-processor는 backend 담당이며 AI팀은 모델 추론 기능 담당이다. 실제 레포 이동·언어 변경·추론 서버 추가는 이번에 시행하지 않는다. 기존 v3의 워커 DB 직접 쓰기 금지와 달리, backend 소유 실행/결과 원장은 후속 설계에서 자체 저장소를 사용하고 타 서비스 DB에 직접 쓰지 않는다. [ADR-0009](../adr/0009-pipeline-dispatch-boundary.md)를 적용한다.

Kafka 워커는 기존 health 전용 포트 규칙을 유지하며 업무 API용 Service를 새로 만들지 않는다.

| 서비스 | 경로 | 책임 | 받는 이벤트 → 내보내는 이벤트 | 로컬 포트 | 저장소 | 모델·외부 AI | 담당 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ai-gateway | `services/ai-gateway` | 외부 AI 호출 관문(내부 전용), Adapter 라우팅, Prompt Registry(taskType 등록, 저장소 버전 경로에서 받기), 규칙 사전 질의 해석, 질의·이미지 벡터, 결과 캐시, 예산·토큰 버킷, 출력 스키마 검증 | HTTP `/v1/analyze`, `/v1/embed`, `/v1/parse` | 8000 | ai_db | 이미지·질의 인코더(자체 실행), VLM·텍스트 임베딩 Adapter(`openai`·`openai_compatible`·`mock`), v4 `predictor` Adapter | |
| normalize | `services/normalize` | 불변 정규화 결과·메타데이터 저장, 영상 검증, 정규화 사본(재생 정보 이동 또는 고정 fps 재인코딩)·HLS 조각, 영상 길이·예상 비용 확정 | `video.uploaded` → `video.normalized` | — | S3 | — | backend |
| chunk-processor | `services/chunk-processor` | 배정된 구간만 추출·AI 입력 준비·내부 HTTP 추론 호출·결과/시간 매핑 저장. 검색 경로: 10초 구간 대표 프레임 4장·블러. 이벤트 경로: 탐지기·ByteTrack·자세·구역·상태 변화 규칙 후보, 탐지기 능력 선언. v4: `chunk.manifest`에 정적 객체 재고 | `chunk.requested` → `segment.ready`, `event.candidate`, `track.detected`, `chunk.boundary`, `chunk.manifest` | — | S3 + worker 소유 실행/결과 원장(후속) | 내부 AI 추론 HTTP (후속) | backend |
| track-stitcher | `services/track-stitcher` | 경계 트랙 IoU 연결, 크롭 벡터가 모인 뒤 재등장 연결(Re-ID). `jobType: STREAM`은 건너뜀(v5.1) | `chunk.boundary`, `segment.embedded` → `track.detected`, `track.manifest` | — | Redis | — | 사용자 |
| stream-ingestor | `services/stream-ingestor` | 카메라 1대의 RTSP 수신, 세션 전체 연속 탐지·추적, 창(20초)마다 chunk-processor와 같은 산출물(`jobType: STREAM`), 녹화 조각·HLS, 긴급 후보 (v5.1) | `stream.command` → `segment.ready`, `event.candidate`, `track.detected`, `chunk.boundary`, `chunk.manifest`, `alert.candidate` | — | S3, Redis(임대) | YOLO·ByteTrack(자체 실행, chunk-processor와 같은 탐지 프로필) | 사용자 |
| frame-encoder | `services/frame-encoder` | 구간 프레임 4장 평균 벡터와 트랙 크롭 벡터 생성, 벡터 파일 저장, v4 유형별 텍스트 프로토타입 비교 후보(v5.1 연속 구간 병합·실행당 상한) | `segment.ready` → `segment.embedded`, `event.candidate.vector` | — | S3 | 이미지 인코더(자체 실행) | |
| grounding-worker | `services/grounding-worker` | 상위 구간에 대상어 bbox를 그린 주석 클립 생성 | `grounding.requested` → `grounding.completed` | — | S3 | 개방 어휘 탐지기(자체 실행) | |
| event-analyzer | `services/event-analyzer` | 청크 후보 묶음을 대기 없이 병합·판정, `VLMAnalysis` 검증, 상향 판정·`reviewRequired`, v4 벡터 후보 판정(`vector+vlm`), v5.1 구간 규칙·재판정 간격(`rule+carry`)·실행당 상한·긴급 후보 즉시 판정 | `event.candidate`, `event.candidate.vector`, `alert.candidate`(v5.1) → `event.analyzed`, `event.manifest`, `alert.raised`(v5.1) | — | Redis(실시간 재판정 간격) | `event_judge` → 애매하거나 high면 `event_judge_escalate` | |
| track-analyzer | `services/track-analyzer` | 이벤트 관련 트랙·클릭한 트랙의 속성 분석, 객체 자유 질문 | `attribute.requested` → `track.analyzed` | — | — | `track_attribute`, `object_question` | |
| embedding-worker | `services/embedding-worker` | 이벤트 설명문, 트랙 속성 설명, 구간 주석 문장을 항목마다 텍스트 임베딩해 벡터 파일로 저장(묶음 임베딩 아님, SPEC-025) | `event.analyzed`, `track.analyzed`, `segment.annotated` → `embedding.ready` | — | S3(벡터 파일) | `embed_text` | |
| aggregator | `services/aggregator` | fold 한 곳: 청크 경계 이벤트 병합, 시간 기준 규칙(체류·배회·장비 방치), 상태 스냅샷·위험 상태 전이, 타임라인, 텍스트 요약, v4 작업 세션 초기 상태·정적 객체 재고 비교·노출 지표, v5.1 늦은 벡터 이벤트 revision 재발행·실시간 창 증분 fold·활성 위험 중 접근 판정 | `analysis.completed`, `chunk.manifest`, `event.analyzed`(v5.1), `track.detected`(v5.1, STREAM만) → `source.completed`, `state.updated`(v5.1) | — | Redis(대기 집합·STREAM 상태), S3(스냅샷) | `source_summary`, `event_judge`, `state_compare`, `risk_forecast` | |

## Client

| 서비스 | 레포 | 책임 | 로컬 포트 |
| --- | --- | --- | --- |
| frontend | frontend | 웹 UI (업로드, 원본 재생, 진행 상태, 플레이어, 이벤트 타임라인, 위험 상태, 문장 검색·RAG, 클릭 조회, 검토 큐, v4 작업 세션·노출 지표·처리 시간 분해) | 5173 (`pnpm dev`), 3000 (compose 컨테이너) |

stream-service·stream-ingestor는 Phase 2(실시간)에서 구현한다. Quality의 Python 평가 잡은 상주 서비스가 아니라 CI·운영자가 실행하는 잡이라 배포 단위로 세지 않는다.

## 포트 규칙

- 로컬 Spring 서비스는 8080부터 순서대로, Python HTTP 서비스는 8000부터 쓴다. Kafka 소비 워커는 호스트에 포트를 내보내지 않는다(표의 로컬 포트 `—`).
- 운영(EKS)에서는 컨테이너 포트를 Spring 8080, FastAPI 8000으로 통일하고 Service 이름으로 구분한다.
- Kafka 소비 워커는 컨테이너 포트 8000에 health 전용 HTTP 서버만 연다. Service는 만들지 않고 kubelet이 Pod IP로 프로브를 부른다.
  - `/health`(liveness): 소비 루프가 최근에 돌았는지만 본다. Kafka 연결 여부는 넣지 않는다. 브로커가 잠깐 끊겨도 모든 워커가 한꺼번에 재시작되는 연쇄 장애를 막기 위해서다.
  - `/ready`(readiness): 프로필 검증과 모델 로드가 끝났는지 본다. 모델을 내려받는 동안 재시작되지 않도록 startupProbe도 같은 경로로 둔다.

### 배정과 AI 추론의 범위

배정기는 pipeline-service의 후속 구성요소이며 별도 새 배포 단위를 확정하지 않는다. AI 추론 서버는 논리 역할이고 POST /v1/inferences는 신규 초안이다. 기존 ai-gateway facade 또는 별도 서버 adapter 중 실제 연결을 확인하기 전까지 기존 경로를 교체하지 않는다. 작업 완료·실패 토픽은 실행 식별자·결과 참조/오류 코드가 필요한 후보이며 현재 계약으로 구현됐다고 표기하지 않는다.

Pipeline의 실제 종료 수신·슬롯 반환은 [SPEC-014](../specs/SPEC-014-execution-results/spec.md), 실행 집계·소유자 상태 조회·제한된 확정 실패 재시도는 [SPEC-015](../specs/SPEC-015-job-execution-status/spec.md)다. 실행 SUCCEEDED는 워커 결과 준비를 뜻한다. 표의 Analysis/Search 적재 완료 판정·analysis.completed·버전 활성화는 후속이며 현재 구현으로 완료를 선언하지 않는다.
