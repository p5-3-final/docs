# AGENTS.md — infra (Terraform · AWS)

<!-- 이 레포 AI 코딩 도구 공통 규칙의 원본이다. CLAUDE.md는 이 파일을 import한다. 여기에는 infra 고유 규칙만 둔다. -->

## 상위 규칙 (필수)
- 공통 규칙(SDD, TDD, 주석, lint·검사 예외, Git, 언어, 보안)은 docs 루트의 `../../AGENTS.md`에 있다.
  - Claude Code와 Antigravity(루트 `project/` 폴더를 연 경우)는 이 파일을 자동으로 불러온다.
  - **Codex처럼 상위 파일을 자동으로 읽지 않는 도구는 작업을 시작하기 전에 `../../AGENTS.md`를 직접 읽는다.**
- 경로별 세부 규칙은 아래 표와 같다. 해당 파일을 다룰 때 자동으로 불러오지 않는 도구는 직접 읽는다. `.agents/`는 `scripts/sync-agent-config.sh`가 만드는 생성본이므로 수정하지 않는다.

| 작업 대상 | 규칙 파일 |
| --- | --- |
| `bootstrap/**`, `modules/**`, `live/**` | `.claude/rules/terraform.md` |
| `.tflint.hcl`, `.trivyignore` (검사 도구 설정) | `.claude/rules/lint.md` |
| `.github/workflows/**`, `Dockerfile`, `*.sh`, `.editorconfig`, `lefthook.yml` | `.claude/rules/ci-common.md` |

## 범위
- 이 레포는 **AWS 리소스만** 다룬다. 클러스터 안의 리소스(Deployment, 애드온 설정 등)는 gitops 레포가 맡는다.
- 예외는 `modules/argocd-bootstrap` 하나다. Argo CD Helm 설치, gitops 레포를 가리키는 root Application, 클러스터 Secret만 만들고 그 뒤는 Argo CD에 넘긴다.
- RDS는 이미 만들어진 것을 제공받는다. 생성, 삭제, 크기 변경을 하지 않고 `data` 소스로 조회만 한다. 이 레포는 접근 경로(네트워크, 보안 그룹 규칙)와 Secrets Manager 경로만 관리한다.
- 로컬 docker-compose는 docs 루트 `../../local/`에 있다.

## 구조
```
infra/
├── bootstrap/            # [사람이 1회 apply] state S3 버킷, GitHub OIDC provider, CI IAM Role(plan, apply)
├── modules/
│   ├── network/          # VPC·서브넷 (RDS가 있는 VPC 방식에 따라 조회 전용 또는 생성)
│   ├── eks/              # 클러스터, 관리형 노드 그룹, EKS 애드온
│   ├── ecr/              # 서비스별 이미지 레포
│   ├── platform-iam/     # 클러스터 애드온용 Pod Identity
│   ├── argocd-bootstrap/ # Argo CD 설치 + root Application + 클러스터 Secret
│   └── environment/      # 환경 하나: Pod Identity, Secrets 경로, RDS 접근 규칙
├── live/
│   ├── shared/           # 클러스터당 하나. 10-network → 20-eks → 30-platform 순서
│   └── envs/
│       ├── _template/    # 새 환경을 만들 때 복사한다
│       └── dev/
└── specs/SPEC-NNN-*/
```

- `live/` 아래 폴더 하나가 스택(루트 모듈) 하나이고, state도 스택마다 따로 둔다.
- 환경은 한 EKS 클러스터 안의 namespace로 나눈다. 환경 스택은 `module "environment"` 하나만 호출한다.

## GitOps 흐름
```
PR       → terraform-plan.yml  : fmt, validate, tflint, trivy, plan → PR 코멘트
main 머지 → terraform-apply.yml : 레이어 순서대로, GitHub Environment 승인 → 다시 plan → apply
```
- 승인 Environment: `tf-shared`(shared 스택), `tf-<env>`(환경 스택)
- CI 인증은 OIDC로 한다. plan role은 읽기 전용, apply role은 `main` 브랜치와 `tf-*` Environment에서만 assume할 수 있다.

## 명령어
```bash
terraform fmt -check -recursive                       # 레포 전체 포맷 검사
tflint --init && tflint --recursive                   # 레포 전체 lint (.tflint.hcl)
trivy config .                                        # 보안 설정 검사
# 바뀐 스택마다 (<stack> = live/shared/20-eks, live/envs/dev 등)
terraform -chdir=<stack> init -backend=false && terraform -chdir=<stack> validate
terraform -chdir=<stack> plan                         # 자격 증명이 있을 때만. 결과 요약을 보고한다
```
작업을 끝내기 전에 `fmt -check`, `tflint --recursive`, `trivy config`, 바뀐 스택의 `validate`를 실행한다. `modules/`만 바꿨다면 그 모듈을 호출하는 스택을 모두 validate한다.

## lint
도구: terraform fmt, tflint, trivy config. 공통 도구(workflow, Dockerfile, lefthook)는 `.claude/rules/ci-common.md`에 있다.

규칙 세트와 설정 위치는 `.claude/rules/lint.md`에 있다. **검사 도구의 설정 파일을 만들거나 고칠 때는 이 파일을 먼저 읽는다.**

## 절대 규칙
- **apply는 CI만 한다**: 사람도 에이전트도 로컬에서 `terraform apply`나 `destroy`를 실행하지 않는다. 사람은 GitHub Environment에서 승인만 한다. 예외는 `bootstrap/`의 최초 1회 apply뿐이다.
- **비밀값**: 비밀값은 Terraform 변수로 받지 않는다. 값은 Secrets Manager에 사람이 넣고, Terraform은 경로만 만든다.
  - 환경별 공개 값(이름, CIDR, 인스턴스 크기)은 스택의 `terraform.tfvars`에 두고 커밋한다.
  - `*.secret.tfvars`, `*.tfstate`, `.terraform/`은 `.gitignore`에 넣고 커밋하지 않는다. 에이전트는 이 파일을 읽지 않는다.
- **비용**: NAT Gateway, 노드 그룹 크기·타입처럼 비용이 큰 변경은 plan에 비용 영향을 적고 사용자에게 확인받는다.
- **gitops 레포와의 순서**: 두 레포를 같이 바꿔야 하면 이 레포 PR을 먼저 머지하고 apply가 끝난 뒤 gitops PR을 머지한다.

## 새 환경 추가
1. `live/envs/_template`을 `live/envs/<env>`로 복사하고 환경 이름 변수만 바꾼다.
2. GitHub에서 `tf-<env>` Environment를 만들고 승인자를 지정한다.
3. gitops 레포에서 `envs/_template`을 `envs/<env>`로 복사하는 PR을 연다(이 레포 apply 이후).

## 내리는 순서
1. gitops 레포에서 Ingress가 있는 앱을 먼저 삭제한다(ALB가 남지 않도록).
2. `live/envs/*`를 destroy한다.
3. `live/shared`를 `30-platform → 20-eks → 10-network` 순서로 destroy한다.
- destroy도 CI workflow(`workflow_dispatch` + Environment 승인)로만 실행한다.
