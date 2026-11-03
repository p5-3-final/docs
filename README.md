# 프로젝트 문서 (docs 레포)

스펙, API 계약, 아키텍처 문서, 공통 규칙을 관리하는 루트 레포입니다. 서비스 코드는 레포마다 따로 있고, 이 레포 아래 `repos/`에 클론해서 작업합니다.

| 레포 | 내용 |
| --- | --- |
| [docs](https://github.com/p5-3-final/docs) | 이 레포. spec, 계약, 아키텍처, 공통 규칙, 로컬 docker-compose |
| [backend](https://github.com/p5-3-final/backend) | Spring Boot 멀티모듈 MSA |
| [ai](https://github.com/p5-3-final/ai) | Python FastAPI AI 서비스 |
| [frontend](https://github.com/p5-3-final/frontend) | React SPA |
| [infra](https://github.com/p5-3-final/infra) | Terraform (AWS) |
| [gitops](https://github.com/p5-3-final/gitops) | Argo CD가 추적하는 Kubernetes 매니페스트 |

## 시작하기

### 0. 사전 준비 (한 번만)

`p5-3-final` 조직 초대를 수락한 뒤 진행합니다.

```bash
ssh-keygen -t ed25519 -C "<내 이메일>"   # 이미 키가 있으면 생략
pbcopy < ~/.ssh/id_ed25519.pub          # GitHub → Settings → SSH and GPG keys → New SSH key에 붙여넣기
ssh -T git@github.com                   # "Hi <아이디>!"가 나오면 성공
```

[GitHub CLI](https://cli.github.com)(`gh`)는 선택입니다. 터미널에서 PR을 열고 싶을 때만 설치합니다.

```bash
brew install gh && gh auth login        # GitHub.com → SSH → 브라우저 로그인
```

### 1. 레포 클론

```bash
git clone git@github.com:p5-3-final/docs.git project
cd project
./scripts/clone-repos.sh                # repos/ 아래에 backend, ai, frontend, infra, gitops 클론
```

### 2. 도구 설치

맡은 레포에 필요한 것만 설치합니다.

| 대상 | 명령 |
| --- | --- |
| 공통 (문서, 검사) | `brew install node lychee shellcheck lefthook` |
| backend | `brew install openjdk@21` (Gradle은 wrapper가 받음) |
| ai | `brew install uv` → `uv python install 3.12` |
| frontend | `brew install fnm` → `fnm install 22` → `corepack enable` (pnpm) |
| infra | `brew install terraform tflint trivy` |
| gitops | `brew install kubeconform kube-linter yamllint kubectl helm` |
| 로컬 실행 | Docker Desktop 또는 OrbStack |

### 3. 레포별 설정 (해당 파일이 생긴 뒤)

```bash
# 레포에 lefthook.yml이 있으면 레포마다 한 번
cd repos/<레포> && lefthook install

# 로컬 전체 실행 (자세한 내용은 local/README.md)
cp local/.env.example local/.env        # 로컬 전용 값을 직접 채운다. 서명 키 만드는 법은 파일 주석에 있다
docker compose -f local/docker-compose.yml up -d --build
```

## 작업 흐름

`main`은 보호되어 있어 직접 push할 수 없습니다. 브랜치를 만들어 PR로 반영하고, squash merge만 허용합니다. 명세·구현 PR은 필수 검사와 GitHub 머지 조건을 충족하면 팀원 Approve 대기 없이 직접 머지합니다.

```bash
cd repos/<레포>                          # docs 레포 작업이면 project/에서
git switch main && git pull
git switch -c feat/SPEC-012-sign-up     # 또는 fix/87-token-expiry
# 작업, 커밋
git push -u origin HEAD
# GitHub 웹에서 PR 생성 (gh가 있으면 gh pr create)
# PR 제목은 Conventional Commits 형식 (squash 커밋 제목이 됨)
```

기능 개발은 SDD 순서를 따릅니다. 자세한 규칙은 [AGENTS.md](AGENTS.md)에 있습니다.

1. `sdd-spec`: `docs/specs/`에 spec 작성 → PR 자체 검토·필수 검사 → 명세 확정·머지
2. API·이벤트가 바뀌면 `docs/contracts/` 수정
3. 각 레포에서 `sdd-plan`: `specs/SPEC-NNN-*/plan.md`, `tasks.md` 작성
4. `sdd-implement`: 태스크마다 테스트 먼저(Red → Green → Refactor)
5. 요구사항별 테스트 통과, 배포 후 spec 상태를 `Done`으로 변경

## AI 코딩 도구

규칙 원본은 `AGENTS.md`이고, 세 도구 모두 같은 규칙을 따릅니다.

| 도구 | 실행 위치 | 스킬 호출 |
| --- | --- | --- |
| Claude Code | `project/` 또는 `repos/<레포>`. 하위 레포에서도 루트 규칙이 함께 적용됩니다. | `/sdd-spec` |
| Codex | 레포 디렉터리. 레포 `AGENTS.md`의 지시에 따라 루트 `AGENTS.md`를 직접 읽습니다. | `$sdd-spec` |
| Antigravity | `project/` 폴더를 workspace로 열어야 루트 규칙까지 적용됩니다. | 요청 내용에 맞으면 자동 |

`.claude/rules`나 `.claude/skills`를 고쳤다면 `./scripts/sync-agent-config.sh`로 `.agents/`(Codex·Antigravity용 생성본)를 갱신하고 같은 커밋에 넣습니다. 어긋나면 CI가 실패합니다.

## 디렉터리 구조

```text
project/                      ← docs 레포
├── AGENTS.md, CLAUDE.md      ← 공통 규칙
├── .claude/                  ← 규칙·스킬 원본, 권한 설정
├── .agents/                  ← Codex·Antigravity용 생성본 (직접 수정 금지)
├── docs/
│   ├── principles.md         ← 프로젝트 원칙
│   ├── product/              ← PRD, 용어집
│   ├── architecture/         ← 아키텍처 개요, 서비스 카탈로그
│   ├── specs/                ← 기능 스펙 (SPEC-NNN-*/spec.md)
│   ├── contracts/            ← OpenAPI / AsyncAPI 계약
│   ├── adr/                  ← 아키텍처 결정 기록
│   └── templates/            ← spec, plan, tasks, adr 템플릿
├── scripts/                  ← clone-repos.sh, sync-agent-config.sh
├── local/                    ← 로컬 docker-compose
├── repos.conf                ← 하위 레포 목록
└── repos/                    ← (gitignore) 하위 레포 클론 위치
```
