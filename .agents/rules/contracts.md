---
trigger: glob
globs: "service-contracts/**"
---
<!-- 자동 생성 파일: .claude/rules/ 원본을 수정하고 scripts/sync-agent-config.sh 를 실행하세요 -->

# API·이벤트 계약 규칙

- REST 계약은 OpenAPI 3.1로 작성한다. 파일은 `service-contracts/openapi/<service>.yaml`이고 서비스당 파일 하나다.
- 이벤트 계약은 AsyncAPI 3.0으로 작성한다. 파일은 `service-contracts/asyncapi/<service>.yaml`이고, 이벤트를 발행하는 서비스 기준으로 나눈다.
- `info.version`은 SemVer를 따른다.
  - 필드나 엔드포인트 추가: minor
  - 설명 수정: patch
  - 하위호환 파괴: major
- 하위호환을 깨는 변경은 ADR이 필요하고, 경로 버전을 올려야 한다(`/api/v1` → `/api/v2`). 기존 버전은 소비자가 이전할 때까지 유지한다.
  - 하위호환 파괴의 예: 필드 삭제나 이름 변경, 타입 변경, 필수 필드 추가, 상태 코드 의미 변경
- 경로 규칙: `/api/v{n}/<복수형-리소스>`, kebab-case. JSON 필드는 camelCase로 쓴다.
- 계약 묶음 버전(ADR-0013): `service-contracts/` 아래 파일을 바꾼 PR은 `service-contracts/VERSION`(SemVer)도 같은 기준(추가 minor, 설명 patch, 하위호환 파괴 major)으로 올린다. README만 바꾼 경우는 예외다. PR CI가 검사하고, main에 머지되면 GitHub Release `service-contracts-v<버전>`이 만들어진다. 다른 레포는 `service-contracts.lock`으로 버전을 고정해 쓴다.
  - 예외: api-gateway를 거치지 않는 내부 전용 서비스(ai-gateway)는 `/v{n}/<동작>`을 쓴다(예: `/v1/analyze`). AI 서빙 API의 관례를 따르고, operation에 `tags: [internal]`을 단다.
- 오류 응답은 RFC 9457 `application/problem+json`을 쓴다. 공통 스키마는 `service-contracts/openapi/_common.yaml`의 `ProblemDetail`이다. 서비스별 오류 코드는 `code` 확장 필드에 `<DOMAIN>_<REASON>` 형식으로 넣는다.
- 모든 operation에 `operationId`(camelCase), `summary`, `tags`, 성공 응답과 오류 응답 예시를 둔다.
- 계약을 바꾼 PR에는 영향받는 소비자 레포(frontend 코드 생성, 호출하는 서비스)를 PR 본문에 적는다.

## 검사

- 계약을 바꾼 뒤에는 아래를 실행하고 결과를 보고한다. CI도 같은 검사를 한다.

  ```bash
  npx @redocly/cli lint service-contracts/openapi/*.yaml
  oasdiff breaking <main의 계약 파일> <바뀐 계약 파일> --fail-on ERR
  ```

- Redocly 규칙 세트(`redocly.yaml`)는 `recommended`에 이 파일의 규칙을 추가해서 강제한다.
  - `operationId`: camelCase, 필수
  - 경로: kebab-case, `/api/v{n}/` 접두사(내부 전용 서비스 예외는 위 경로 규칙)
  - 오류 응답: `application/problem+json`, `ProblemDetail` 참조
  - `summary`, `tags`, 응답 예시: 필수
- oasdiff가 하위호환 파괴를 감지하면 `info.version`의 major를 올리고, 경로 버전을 올리고, ADR을 쓴다. 이 세 가지가 없으면 CI가 실패한다.
- AsyncAPI 계약은 `npx @asyncapi/cli validate`로 검사한다.
