<!-- 공통 규칙 원본은 AGENTS.md다(Codex·Antigravity와 공유). 여기에는 Claude Code 전용 내용만 둔다. -->
# CLAUDE.md — 프로젝트 루트 (docs 레포)

@AGENTS.md

## Claude Code 전용

- `.claude/rules/`의 규칙은 `paths`에 맞는 파일을 다룰 때 자동으로 로드된다. 직접 찾아 읽을 필요가 없다.
- 스킬은 `/sdd-spec`, `/sdd-adr`로 호출한다.
- 개인적으로 설치한 플러그인 스킬(TDD, 코드 리뷰 등)과 이 프로젝트의 규칙(AGENTS.md, `.claude/rules/`, `.claude/skills/`)이 다르면 프로젝트 규칙이 우선한다.
- `.claude/rules/`나 `.claude/skills/`를 수정했다면 `./scripts/sync-agent-config.sh`를 실행해서 `.agents/`(Codex·Antigravity용)에 반영한다.
- 권한 차단 설정은 `.claude/settings.json`에 있다(.env·tfstate 읽기, force push, `terraform apply`·`destroy`, 클러스터 변경 명령). Claude Code는 실행한 폴더의 설정만 읽으므로, 루트에서 실행해도 infra·gitops 차단이 걸리도록 루트에도 같은 목록을 둔다.
  - 허용 목록에는 `gh pr merge`만 둔다. spec·계약 PR도 자체 검토 후 직접 머지하므로(ADR-0007, `sdd-workflow.md`) 에이전트가 머지할 때 매번 막히지 않게 한다. 필수 CI와 GitHub 머지 조건은 그대로 적용된다.
  - `.env` 계열은 실제 값이 들어가는 이름(`.env`, `.env.local`, `.env.production` 등)만 차단한다. `.env.example`은 비밀값이 없는 예시라 에이전트가 고칠 수 있어야 하는데, 차단 규칙은 허용 규칙보다 우선하므로 `.env.*` 전체를 막지 않는다.
