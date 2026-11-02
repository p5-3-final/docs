---
paths:
  - "docs/**/*.md"
---

# 문서 작성 규칙

## 공통

- 새 문서는 `docs/templates/`의 템플릿에서 시작한다. 템플릿의 섹션을 지우지 말고, 해당이 없으면 "해당 없음"이라고 쓴다.
- spec, plan, tasks, ADR에는 템플릿의 YAML frontmatter를 그대로 두고 모두 채운다. 필드를 지우지 않는다.
  - spec: `id`, `title`, `status`, `owner`, `repos`, `created`, `updated`, `related`
  - plan: `spec`, `repo`, `status`, `owner`, `created`, `updated` / tasks: `spec`, `repo`, `updated`
  - ADR: `id`, `title`, `status`, `date`, `deciders`, `related`
- 다이어그램은 Mermaid 코드 블록으로 그린다. 이미지 파일은 쓰지 않는다(diff 리뷰를 위해).
- 다른 문서는 상대 경로 링크로 참조한다. 예: `[서비스 카탈로그](../architecture/service-catalog.md)`
- 날짜는 `YYYY-MM-DD` 형식으로 쓴다.

## EARS 요구사항 문법

키워드(WHEN, WHILE, IF, THEN, WHERE, SHALL)는 영어 대문자로 쓰고, 내용은 한국어로 쓴다. 주어는 구체적인 서비스 이름(`auth-service`, `frontend` 등)으로 쓴다.

| 패턴 | 형식 | 예시 |
| --- | --- | --- |
| 상시 (Ubiquitous) | THE `<시스템>` SHALL `<응답>` | THE auth-service SHALL 비밀번호를 bcrypt로 해시해 저장한다. |
| 이벤트 (Event-driven) | WHEN `<트리거>`, THE `<시스템>` SHALL `<응답>` | WHEN 사용자가 유효한 이메일과 비밀번호로 가입을 요청하면, THE auth-service SHALL 계정을 생성하고 201을 반환한다. |
| 상태 (State-driven) | WHILE `<상태>`, THE `<시스템>` SHALL `<응답>` | WHILE 계정이 잠금 상태이면, THE auth-service SHALL 로그인 요청을 423으로 거절한다. |
| 비정상 (Unwanted) | IF `<조건>`, THEN THE `<시스템>` SHALL `<응답>` | IF 이미 가입된 이메일이면, THEN THE auth-service SHALL 409와 오류 코드 `USER_EMAIL_DUPLICATED`를 반환한다. |
| 선택 (Optional) | WHERE `<기능 포함 시>`, THE `<시스템>` SHALL `<응답>` | WHERE 소셜 로그인이 활성화된 경우, THE frontend SHALL 로그인 화면에 소셜 로그인 버튼을 표시한다. |

- 비기능 요구사항(`NFR-*`)도 측정 가능한 숫자로 쓴다. 예: THE api-gateway SHALL p95 응답 지연을 300ms 이하로 유지한다.

## ADR

- 형식은 MADR을 기반으로 한 `docs/templates/adr.md`를 따른다.
- 한 번 `Accepted`된 ADR의 결정 내용은 수정하지 않는다. 결정이 바뀌면 새 ADR을 쓰고, 기존 ADR의 상태를 `Superseded by ADR-NNNN`으로 바꾼다.
- 오타나 링크 수정은 예외로 허용한다.
- 새 ADR을 쓰면 `docs/adr/README.md` 목록에 추가한다.

## 검사

- 문서를 고친 뒤에는 아래를 실행한다. CI도 같은 검사를 한다.
  ```bash
  npx markdownlint-cli2 "docs/**/*.md" "*.md"
  lychee --offline "docs/**/*.md" "*.md"     # 내부 링크 확인
  ```
- markdownlint 규칙 세트에서 줄 길이 제한(MD013)은 끈다. 한국어 문장, 표, 코드 블록은 줄이 길어질 수밖에 없다.
- 문서나 ADR을 삭제하거나 이름을 바꾸면 lychee로 끊긴 링크가 없는지 확인한다.
