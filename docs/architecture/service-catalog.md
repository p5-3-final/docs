---
updated: 2026-11-03
---

# 서비스 카탈로그

> 서비스를 추가하거나 변경하면 이 표를 먼저 고친다(ADR이 필요할 수 있음). 담당은 정해지면 채운다. 배포 단위 구성의 근거는 [ADR-0008](../adr/0008-industrial-safety-v3.md)이고, 흐름은 [overview.md](overview.md)에 있다.

배포 단위는 19개다. Spring 9개(사용자 요청, 업무 상태, 저장과 조회, 품질 검토)와 Python 10개(영상 디코딩, 객체 탐지·추적, 이미지 벡터, bbox 주석, 외부 AI 호출)로 나눈다. 모델 ID·차원·탐지 프로필은 코드가 아니라 프로필 값이다(overview "모델과 플랫폼 교체").

## Edge · Domain (backend, Spring)

| 서비스 | 경로 | 책임 | 받는 이벤트 → 내보내는 이벤트 | 로컬 포트 | DB | 계약 | 담당 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| api-gateway | `services/api-gateway` | 라우팅, JWT 검증(JWKS), 사용자 헤더 주입, CORS, rate limit, 알림 티켓 검증 | — | 8080 | — (Redis) | — | |
| auth-service | `services/auth-service` | 회원, 로그인, 토큰 발급·재발급·폐기, 역할, 공개키(JWKS), 알림 티켓 | — | 8081 | auth_db | `openapi/auth-service.yaml` | |
| media-service | `services/media-service` | 업로드 자리 발급, 완료 확인(조건부 전이), 원본 재생 주소, 정규화 결과 반영, 사전 견적, 삭제 전파 | `video.normalized` → `video.uploaded`, `video.deleted` | 8082 | media_db | `openapi/media-service.yaml` | |
| pipeline-service | `services/pipeline-service` | 청크 계획·분배, 3단계 공정성, 적재 완료 기준 완료 판정, 재판정·재임베딩 job | `video.normalized`, `chunk.manifest`, `segment.indexed`, `event.manifest`, `track.manifest` → `chunk.requested`, `analysis.completed`, `job.status` | 8083 | pipeline_db | `openapi/pipeline-service.yaml` | 다른 작업자 |
| analysis-api | `services/analysis-api` | 이벤트 타임라인·상세·검토, 위험 상태·상태 스냅샷 저장·조회, 위험구역 정의, 클릭 조회, 오버레이, 요약, 활성 버전, 트랙 속성 요청, 객체 자유 질문, aggregator·search-service용 내부 읽기 API | `event.analyzed`, `track.detected`, `track.analyzed`, `source.completed` → `attribute.requested`, `version.activated` | 8084 | analysis_db | `openapi/analysis-service.yaml` | 다른 작업자 |
| analysis-loader | `services/analysis-loader` | 검출 박스·트랙 위치 파일 대량 적재(analysis-api와 DB 공유, 분리 배포) | `track.detected` → — | 8085 | analysis_db | — | 다른 작업자 |
| search-service | `services/search-service` | 문장·이미지로 장면 찾기(질의 해석·시각/텍스트 검색·정밀 검색 선택), 구간·크롭 벡터 적재, bbox 주석 요청, Video RAG, 결과 재사용, 구간 주석 | `segment.embedded`, `embedding.ready`, `grounding.completed`, `version.activated`, `video.deleted` → `segment.indexed`, `segment.annotated`, `grounding.requested` | 8086 | search_db (pgvector) | `openapi/search-service.yaml` | 다른 작업자 |
| notification-service | `services/notification-service` | 진행률·분석 완료·트랙 속성·주석 클립 도착 실시간 알림(SSE) | `job.status`, `source.completed`, `track.analyzed`, `grounding.completed` → — | 8087 | — (Redis) | `openapi/notification-service.yaml` | 다른 작업자 |
| quality-service | `services/quality-service` | 검토 큐(`reviewRequired`·표본), Golden Set 버전 관리, 평가 리포트, CI Gate·회귀 평가 결과 | `event.analyzed` → — | 8088 | quality_db | `openapi/quality-service.yaml` (예정) | |

## Data Plane (ai, Python)

ai-gateway만 HTTP 서버이고 나머지 9개는 Kafka 소비 워커다. 워커는 PostgreSQL에 직접 쓰지 않고, 결과를 Kafka 이벤트나 S3 파일로 내보낸다. 저장은 데이터를 소유한 Spring 서비스가 한다. 이미지는 워커마다 따로 만든다([ADR-0001](../adr/0001-ai-uv-workspace.md)). 공급자 SDK·모델 라이브러리는 `libs/`의 인터페이스 구현 뒤에 둔다.

| 서비스 | 경로 | 책임 | 받는 이벤트 → 내보내는 이벤트 | 로컬 포트 | 저장소 | 모델·외부 AI | 담당 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ai-gateway | `services/ai-gateway` | 외부 AI 호출 관문(내부 전용), Adapter 라우팅, Prompt Registry, 규칙 사전 질의 해석, 질의·이미지 벡터, 결과 캐시, 예산·토큰 버킷, 출력 스키마 검증 | HTTP `/v1/analyze`, `/v1/embed`, `/v1/parse` | 8000 | ai_db | 이미지·질의 인코더(자체 실행), VLM·텍스트 임베딩 Adapter(`openai`·`openai_compatible`·`mock`) | |
| normalize | `services/normalize` | 영상 검증, 정규화 사본(재생 정보 이동 또는 고정 fps 재인코딩)·HLS 조각, 영상 길이·예상 비용 확정 | `video.uploaded` → `video.normalized` | — | S3 | — | |
| chunk-processor | `services/chunk-processor` | 청크 한 번 디코딩. 검색 경로: 10초 구간 대표 프레임 4장·블러. 이벤트 경로: 탐지기·ByteTrack·자세·구역·상태 변화 규칙 후보, 탐지기 능력 선언 | `chunk.requested` → `segment.ready`, `event.candidate`, `track.detected`, `chunk.boundary`, `chunk.manifest` | — | S3 | 탐지기(자체 실행) | 다른 작업자 |
| track-stitcher | `services/track-stitcher` | 경계 트랙 IoU 연결, 크롭 벡터가 모인 뒤 재등장 연결(Re-ID) | `chunk.boundary`, `segment.embedded` → `track.detected`, `track.manifest` | — | Redis | — | 사용자 |
| frame-encoder | `services/frame-encoder` | 구간 프레임 4장 평균 벡터와 트랙 크롭 벡터 생성, 벡터 파일 저장 | `segment.ready` → `segment.embedded` | — | S3 | 이미지 인코더(자체 실행) | |
| grounding-worker | `services/grounding-worker` | 상위 구간에 대상어 bbox를 그린 주석 클립 생성 | `grounding.requested` → `grounding.completed` | — | S3 | 개방 어휘 탐지기(자체 실행) | |
| event-analyzer | `services/event-analyzer` | 청크 후보 묶음을 대기 없이 병합·판정, `VLMAnalysis` 검증, 상향 판정·`reviewRequired` | `event.candidate` → `event.analyzed`, `event.manifest` | — | — | `event_judge` → 애매하거나 high면 `event_judge_escalate` | |
| track-analyzer | `services/track-analyzer` | 이벤트 관련 트랙·클릭한 트랙의 속성 분석, 객체 자유 질문 | `attribute.requested` → `track.analyzed` | — | — | `track_attribute`, `object_question` | |
| embedding-worker | `services/embedding-worker` | 이벤트 설명문, 트랙 속성, 구간 주석 묶음 텍스트 임베딩 | `event.analyzed`, `track.analyzed`, `segment.annotated` → `embedding.ready` | — | — | `embed_text` | |
| aggregator | `services/aggregator` | 청크 경계 이벤트 병합, 시간 기준 규칙(체류·배회), 상태 스냅샷·위험 상태 전이, 타임라인, 텍스트 요약 | `analysis.completed` → `source.completed` | — | — | `source_summary` | |

## Client

| 서비스 | 레포 | 책임 | 로컬 포트 |
| --- | --- | --- | --- |
| frontend | frontend | 웹 UI (업로드, 원본 재생, 진행 상태, 플레이어, 이벤트 타임라인, 위험 상태, 문장 검색·RAG, 클릭 조회, 검토 큐) | 5173 (`pnpm dev`), 3000 (compose 컨테이너) |

이후 단계 서비스는 착수할 때 추가한다: Stream·Stream Ingestor(Phase 2, 실시간 스트리밍). Quality의 Python 평가 잡은 상주 서비스가 아니라 CI·운영자가 실행하는 잡이라 배포 단위로 세지 않는다.

## 포트 규칙

- 로컬 Spring 서비스는 8080부터 순서대로, Python HTTP 서비스는 8000부터 쓴다. Kafka 소비 워커는 HTTP 포트를 열지 않는다.
- 운영(EKS)에서는 컨테이너 포트를 Spring 8080, FastAPI 8000으로 통일하고 Service 이름으로 구분한다.
