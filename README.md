# 프로젝트 문서 (docs 레포)

프로젝트의 스펙, 아키텍처 결정, API 계약을 관리하는 루트 레포입니다. 서비스 코드는 각자 별도 레포에 있고, 이 레포 아래 `repos/`에 클론해서 작업합니다.

## 시작하기

```bash
git clone git@github.com:p5-3-final/docs.git project && cd project
./scripts/clone-repos.sh            # repos.conf 목록대로 repos/ 아래에 클론
./scripts/bootstrap-repo.sh backend # 레포에 AGENTS.md·CLAUDE.md·규칙·스킬·PR 템플릿 복사 (기존 파일은 유지)
```

## AI 코딩 도구별 사용법

규칙 원본은 `AGENTS.md`입니다. 세 도구 모두 같은 규칙을 따릅니다.

| 도구 | 읽는 파일 | 사용 시 주의 |
| --- | --- | --- |
| Claude Code | `CLAUDE.md`(→ `@AGENTS.md`), `.claude/rules`, `.claude/skills` | `repos/<레포>`에서 실행해도 루트 규칙이 자동으로 함께 적용됩니다. |
| Codex | `AGENTS.md`, `.agents/skills` | 레포가 독립 git이라 루트 `AGENTS.md`를 자동으로 읽지 않습니다. 레포 AGENTS.md에 직접 읽으라는 지시가 들어 있습니다. |
| Antigravity | `AGENTS.md`, `.agents/rules`, `.agents/skills` | 루트 `project/` 폴더를 workspace로 열어야 루트 규칙까지 적용됩니다. |

`.claude/rules`나 `.claude/skills`를 수정했다면 `./scripts/sync-agent-config.sh`를 실행해서 `.agents/`를 갱신하세요. 두 폴더가 어긋나면 CI에서 실패합니다.

## 디렉터리 구조

```
project/                      ← docs 레포 (이 레포)
├── AGENTS.md                 ← 전 레포 공통 규칙 (원본)
├── CLAUDE.md                 ← @AGENTS.md + Claude Code 전용 안내
├── .claude/
│   ├── settings.json         ← Claude Code 권한 설정 (.env 읽기, apply·클러스터 변경 명령 차단)
│   ├── rules/                ← 경로별 규칙 원본 (SDD, 문서 작성, 계약, 공통 검사 도구)
│   └── skills/               ← 스킬 원본 (sdd-spec, sdd-adr)
├── .agents/                  ← Codex·Antigravity용 생성본 (직접 수정 금지)
├── .github/workflows/        ← agent-config-sync (생성본 최신 여부 검사)
├── docs/
│   ├── principles.md         ← 프로젝트 원칙 (모든 plan의 검증 기준)
│   ├── product/              ← PRD, 용어집
│   ├── architecture/         ← 아키텍처 개요, 서비스 카탈로그
│   ├── specs/                ← 기능 스펙 (SPEC-NNN-*/spec.md)
│   ├── contracts/            ← OpenAPI / AsyncAPI 계약 원본
│   ├── adr/                  ← 아키텍처 결정 기록
│   └── templates/            ← spec / plan / tasks / adr 템플릿
├── repo-templates/           ← 각 레포 초기 설정 (AGENTS.md, CLAUDE.md, .claude/, .github/)
├── scripts/                  ← clone-repos.sh, bootstrap-repo.sh, sync-agent-config.sh
├── local/                    ← 로컬 docker-compose (repos/*를 빌드 컨텍스트로 사용)
├── repos.conf                ← 하위 레포 목록
└── repos/                    ← (gitignore) 하위 레포 클론 위치
    ├── backend/  ai/  frontend/
    ├── infra/                ← Terraform (AWS)
    └── gitops/               ← Argo CD가 추적하는 매니페스트
```

## 개발 흐름 (SDD)

1. `sdd-spec` 스킬: `docs/specs/`에 spec 작성 (무엇·왜, EARS 요구사항). PR로 리뷰받고 승인
2. 계약 변경이 있으면 `docs/contracts/` 수정
3. 각 레포에서 `sdd-plan` 스킬: `specs/SPEC-NNN-*/plan.md`, `tasks.md` 작성
4. `sdd-implement` 스킬: 태스크 단위로 테스트 먼저 작성한 뒤 구현
5. 요구사항별 테스트가 통과하고 배포까지 끝나면 spec 상태를 `Done`으로 변경

스킬 호출 방법은 도구마다 다릅니다. Claude Code는 `/sdd-spec`, Codex는 `$sdd-spec`이고, Antigravity는 요청 내용에 맞으면 자동으로 씁니다.

자세한 내용은 [docs/README.md](docs/README.md)를 보세요.
