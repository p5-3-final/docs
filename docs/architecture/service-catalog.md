---
updated: 2026-10-28
---

# 서비스 카탈로그

> 서비스 이름과 담당자는 예시다. 서비스를 추가하거나 변경하면 이 표를 먼저 고친다(ADR이 필요할 수 있음).

| 서비스 | 레포 / 경로 | 책임 | 로컬 포트 | DB | 계약 | 담당 |
| --- | --- | --- | --- | --- | --- | --- |
| frontend | frontend | 웹 UI | 5173 | — | (소비자) | |
| api-gateway | backend `services/api-gateway` | 라우팅, JWT 검증, CORS, rate limit | 8080 | — | — | |
| user-service | backend `services/user-service` | 회원, 인증 토큰 발급 | 8081 | user_db | `openapi/user-service.yaml` | |
| `<domain>`-service | backend `services/<domain>-service` | 핵심 도메인 | 8082 | domain_db | `openapi/<domain>-service.yaml` | |
| ai-service | ai | AI 추론·분석 | 8000 | — | `openapi/ai-service.yaml` | |

## 포트 규칙

- 로컬 Spring 서비스는 8080부터 순서대로, Python 서비스는 8000부터 쓴다.
- 운영(EKS)에서는 컨테이너 포트를 Spring 8080, FastAPI 8000으로 통일하고 Service 이름으로 구분한다.
