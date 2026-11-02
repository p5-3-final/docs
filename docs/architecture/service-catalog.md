---
updated: 2026-11-02
---

# 서비스 카탈로그

> 서비스를 추가하거나 변경하면 이 표를 먼저 고친다(ADR이 필요할 수 있음). 담당은 정해지면 채운다. 배포 단위 구성의 근거는 [ADR-0005](../adr/0005-search-and-event-paths.md)다.

배포 단위는 17개다. Spring 8개(사용자 요청, 업무 상태, 저장과 조회)와 Python 9개(영상 디코딩, 객체 탐지·추적, 이미지 벡터, 외부 AI 호출)로 나눈다.

## Edge · Domain (backend, Spring)

| 서비스 | 경로 | 책임 | 받는 이벤트 → 내보내는 이벤트 | 로컬 포트 | DB | 계약 | 담당 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| api-gateway | `services/api-gateway` | 라우팅, JWT 검증(JWKS), 사용자 헤더 주입, CORS, rate limit, 알림 티켓 검증 | — | 8080 | — (Redis) | — | |
| auth-service | `services/auth-service` | 회원, 로그인, 토큰 발급·재발급·폐기, 역할, 공개키(JWKS), 알림 티켓 | — | 8081 | auth_db | `openapi/auth-service.yaml` | |
| media-service | `services/media-service` | 업로드 URL 발급, 완료 확인(조건부 전이), 사전 견적, 삭제 전파 | → `video.uploaded`, `video.deleted` | 8082 | media_db | `openapi/media-service.yaml` | |
| pipeline-service | `services/pipeline-service` | 청크 계획·분배, 3단계 공정성, 적재 완료 기준 완료 판정, 재분석·재임베딩 job | `video.normalized`, `chunk.manifest`, `track.manifest`, `event.manifest`, `frame.indexed` → `chunk.requested`, `analysis.completed`, `job.status` | 8083 | pipeline_db | `openapi/pipeline-service.yaml` | |
| analysis-api | `services/analysis-api` | 이벤트 타임라인·상세·검토, 클릭 조회, 오버레이, 요약, 활성 버전, 트랙 속성 요청, Aggregator용 내부 읽기 API | `event.analyzed`, `track.detected`, `track.analyzed`, `source.completed` → `attribute.requested`, `version.activated` | 8084 | analysis_db | `openapi/analysis-service.yaml` | |
| analysis-loader | `services/analysis-loader` | 검출 박스·트랙 위치 파일 대량 적재(analysis-api와 DB 공유, 분리 배포) | `track.detected` → — | 8085 | analysis_db | — | |
| search-service | `services/search-service` | 문장으로 장면 찾기(질의 해석·시각/텍스트 검색·장면 병합·재순위화), 프레임 벡터 적재, 결과 재사용, 프레임 주석. ai-gateway를 동기 호출하는 유일한 Spring 서비스 | `frame.embedded`, `embedding.ready`, `version.activated`, `video.deleted` → `frame.indexed`, `frame.annotated` | 8086 | search_db (pgvector) | `openapi/search-service.yaml` | |
| notification-service | `services/notification-service` | 진행률·분석 완료·트랙 속성 도착 실시간 알림(SSE) | `job.status`, `source.completed`, `track.analyzed` → — | 8087 | — (Redis) | `openapi/notification-service.yaml` | |

## Data Plane (ai, Python)

ai-gateway만 HTTP 서버이고 나머지 8개는 Kafka 소비 워커다. 워커는 PostgreSQL에 직접 쓰지 않고, 결과를 Kafka 이벤트나 S3 파일로 내보낸다. 저장은 데이터를 소유한 Spring 서비스가 한다. 이미지는 워커마다 따로 만든다([ADR-0001](../adr/0001-ai-uv-workspace.md)).

| 서비스 | 경로 | 책임 | 받는 이벤트 → 내보내는 이벤트 | 로컬 포트 | 저장소 | 외부 AI | 담당 |
| --- | --- | --- | --- | --- | --- | --- | --- |
| ai-gateway | `services/ai-gateway` | 외부 AI 호출 관문(내부 전용), 모델 라우팅, Prompt Registry, 결과 캐시, 예산·토큰 버킷, 질의용 SigLIP 2 텍스트 인코더 | HTTP `/v1/analyze`, `/v1/embed` | 8000 | ai_db | OpenAI(운영) · Ollama(로컬) · Mock(CI) | |
| normalize | `services/normalize` | 영상 검증, 정규화 사본(재생 정보 이동 또는 고정 fps 재인코딩), 영상 길이·예상 비용 확정 | `video.uploaded` → `video.normalized` | — | S3 | — | |
| chunk-processor | `services/chunk-processor` | 청크 한 번 디코딩. 검색 경로: 1fps 키프레임·중복 제거·블러. 이벤트 경로: YOLO·ByteTrack·자세 추정·규칙 후보 | `chunk.requested` → `keyframe.ready`, `event.candidate`, `track.detected`, `chunk.boundary`, `chunk.manifest` | — | S3 | — | |
| track-stitcher | `services/track-stitcher` | 청크 경계에서 끊긴 트랙 연결 | `chunk.boundary` → `track.detected`, `track.manifest` | — | Redis | — | |
| frame-encoder | `services/frame-encoder` | 키프레임을 SigLIP 2 이미지 벡터로 변환, 벡터 파일 저장 | `keyframe.ready` → `frame.embedded` | — | S3 | 없음(외부 임베딩 모드만 ai-gateway 경유) | |
| event-analyzer | `services/event-analyzer` | 청크 후보 묶음을 받아 대기 없이 VLM 판정, 설명문·근거·위험도 생성 | `event.candidate` → `event.analyzed`, `event.manifest` | — | — | `event_judge` → 애매하면 `event_judge_escalate` | |
| track-analyzer | `services/track-analyzer` | 이벤트 관련 트랙과 클릭한 트랙만 속성 분석 | `attribute.requested` → `track.analyzed` | — | — | `track_attribute` | |
| embedding-worker | `services/embedding-worker` | 이벤트 설명문, 트랙 속성, 프레임 주석 묶음 텍스트 임베딩 | `event.analyzed`, `track.analyzed`, `frame.annotated` → `embedding.ready` | — | — | `embed_text` | |
| aggregator | `services/aggregator` | 청크 경계 이벤트 병합, 시간 기준 규칙(배회) 판단, 타임라인, 이벤트 설명문 기반 텍스트 요약 | `analysis.completed` → `source.completed` | — | — | `source_summary` | |

## Client

| 서비스 | 레포 | 책임 | 로컬 포트 |
| --- | --- | --- | --- |
| frontend | frontend | 웹 UI (업로드, 진행 상태, 플레이어, 이벤트 타임라인, 문장 검색, 클릭 조회) | 5173 (`pnpm dev`), 3000 (compose 컨테이너) |

이후 단계 서비스는 착수할 때 추가한다: Quality(Phase 2, 이벤트·검색 품질 검증), Stream·Stream Ingestor(Phase 4, 실시간 스트리밍).

## 포트 규칙

- 로컬 Spring 서비스는 8080부터 순서대로, Python HTTP 서비스는 8000부터 쓴다. Kafka 소비 워커는 HTTP 포트를 열지 않는다.
- 운영(EKS)에서는 컨테이너 포트를 Spring 8080, FastAPI 8000으로 통일하고 Service 이름으로 구분한다.
