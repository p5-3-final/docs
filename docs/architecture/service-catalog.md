---
updated: 2026-11-02
---

# 서비스 카탈로그

> 서비스를 추가하거나 변경하면 이 표를 먼저 고친다(ADR이 필요할 수 있음). 담당은 정해지면 채운다.

## Edge · Domain (backend, Spring)

| 서비스 | 경로 | 책임 | 로컬 포트 | DB | 계약 | 담당 |
| --- | --- | --- | --- | --- | --- | --- |
| api-gateway | `services/api-gateway` | 라우팅, JWT 검증(JWKS), CORS, rate limit | 8080 | — | — | |
| auth-service | `services/auth-service` | 회원, 로그인, 토큰 발급, 역할 | 8081 | auth_db | `openapi/auth-service.yaml` | |
| media-service | `services/media-service` | 업로드, 완료 확인, 사전 견적, 원본 관리 | 8082 | media_db | `openapi/media-service.yaml` | |
| pipeline-service | `services/pipeline-service` | 청크 스케줄링, 공정성, 완료 판정, 재분석 | 8083 | pipeline_db | `openapi/pipeline-service.yaml` | |
| analysis-api | `services/analysis-api` | 분석 결과 조회, 활성 버전, 클릭 조회, 타임라인 | 8084 | analysis_db | `openapi/analysis-service.yaml` | |
| analysis-loader | `services/analysis-loader` | 분석 결과·위치 시계열 적재 (analysis-api와 DB 공유, 분리 배포) | 8085 | analysis_db | — | |
| search-service | `services/search-service` | 텍스트 구간 탐색, 영상 간 검색 | 8086 | search_db (pgvector) | `openapi/search-service.yaml` | |
| notification-service | `services/notification-service` | 실시간 알림 (SSE) | 8087 | — (Redis) | `openapi/notification-service.yaml` | |

## Data Plane (ai, Python)

| 서비스 | 경로 | 책임 | 로컬 포트 | 저장소 | 담당 |
| --- | --- | --- | --- | --- | --- |
| ai-gateway | `services/ai-gateway` | 외부 AI 호출 관문, 모델 라우팅, 프롬프트 관리 (내부 전용) | 8000 | ai_db | |
| normalize | `services/normalize` | 영상 검증, 정규화 사본 생성 | — | S3 | |
| chunk-processor | `services/chunk-processor` | 청크 디코딩, 구간 샘플링, 객체 추적, 이벤트 후보 | — | S3 | |
| track-stitcher | `services/track-stitcher` | 청크 경계 트랙 연결 | — | Redis | |
| track-analyzer | `services/track-analyzer` | 트랙 속성 분석 | — | — | |
| event-analyzer | `services/event-analyzer` | 이벤트 후보 병합, 판정 | — | Redis | |
| vlm-worker | `services/vlm-worker` | 구간 설명, 구간 VLM 이벤트 후보 | — | — | |
| embedding-worker | `services/embedding-worker` | 설명 텍스트 묶음 임베딩 | — | — | |
| aggregator | `services/aggregator` | 청크 요약, 전체 요약, 이벤트 타임라인 | — | — | |

## Client

| 서비스 | 레포 | 책임 | 로컬 포트 |
| --- | --- | --- | --- |
| frontend | frontend | 웹 UI (업로드, 진행 상태, 플레이어, 검색) | 5173 |

이후 단계 서비스(Quality, Stream, Stream Ingestor)는 착수할 때 추가한다.

## 포트 규칙

- 로컬 Spring 서비스는 8080부터 순서대로, Python HTTP 서비스는 8000부터 쓴다. Kafka 소비 워커는 HTTP 포트를 열지 않는다.
- 운영(EKS)에서는 컨테이너 포트를 Spring 8080, FastAPI 8000으로 통일하고 Service 이름으로 구분한다.
