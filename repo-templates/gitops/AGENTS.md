# AGENTS.md — gitops (Argo CD · Kubernetes 매니페스트)

<!-- 이 레포 AI 코딩 도구 공통 규칙의 원본이다. CLAUDE.md는 이 파일을 import한다. 여기에는 gitops 고유 규칙만 둔다. -->

## 상위 규칙 (필수)
- 공통 규칙(SDD, TDD, 주석, lint·검사 예외, Git, 언어, 보안)은 docs 루트의 `../../AGENTS.md`에 있다.
  - Claude Code와 Antigravity(루트 `project/` 폴더를 연 경우)는 이 파일을 자동으로 불러온다.
  - **Codex처럼 상위 파일을 자동으로 읽지 않는 도구는 작업을 시작하기 전에 `../../AGENTS.md`를 직접 읽는다.**
- 경로별 세부 규칙은 아래 표와 같다. 해당 파일을 다룰 때 자동으로 불러오지 않는 도구는 직접 읽는다. `.agents/`는 `scripts/sync-agent-config.sh`가 만드는 생성본이므로 수정하지 않는다.

| 작업 대상 | 규칙 파일 |
| --- | --- |
| `bootstrap/**`, `argocd/**`, `platform/**`, `apps/**`, `envs/**` | `.claude/rules/gitops.md` |
| `.yamllint`, `.kube-linter.yaml` (검사 도구 설정) | `.claude/rules/lint.md` |
| `.github/workflows/**`, `Dockerfile`, `*.sh`, `.editorconfig`, `lefthook.yml` | `.claude/rules/ci-common.md` |

## 범위
- Argo CD가 추적하는 **유일한 레포**다. 클러스터 안의 모든 리소스(Argo CD 자신, 애드온, 서비스)를 여기서 선언한다.
- AWS 리소스(VPC, EKS, IAM, ECR, Secrets Manager 경로)는 infra 레포가 맡는다. 이 레포에서 AWS 리소스를 만들지 않는다.
- Argo CD 최초 설치와 root Application 생성은 infra 레포 `modules/argocd-bootstrap`이 한다. 그 뒤로는 Argo CD가 이 레포로 자기 자신까지 관리한다.

## 구조
```
gitops/
├── bootstrap/            # root Application 정의 (infra 레포가 참조)
├── argocd/
│   └── projects/         # AppProject: platform, 환경별
│                         # (argocd/ 바로 아래에 platform·envs용 ApplicationSet을 둔다)
├── platform/<addon>/     # 클러스터 공통 애드온: Helm chart 버전 + values
├── apps/<service>/base/  # 서비스 공통 매니페스트 (환경과 무관)
├── envs/
│   ├── _template/        # 새 환경을 만들 때 복사한다
│   └── dev/              # 환경별 차이: namespace, 이미지 태그, replica, 리소스, 호스트
└── specs/SPEC-NNN-*/
```

- 환경은 한 EKS 클러스터 안의 namespace로 나눈다.
- `envs/` 아래에 폴더를 추가하면 ApplicationSet이 감지해서 그 환경의 Application을 자동으로 만든다.

## 명령어
```bash
yamllint .                                                    # YAML 형식 (.yamllint)
kubectl kustomize envs/dev                                    # 렌더링 결과 확인
kubectl kustomize envs/dev | kubeconform -strict -summary \
  -schema-location default \
  -schema-location 'https://raw.githubusercontent.com/datreeio/CRDs-catalog/main/{{.Group}}/{{.ResourceKind}}_{{.ResourceAPIVersion}}.json'
kubectl kustomize envs/dev | kube-linter lint -               # 매니페스트 정책 (.kube-linter.yaml)
helm template <addon> <chart> --version <ver> -f platform/<addon>/values.yaml   # 애드온 렌더링
```
작업을 끝내기 전에 바뀐 환경마다 위 검사(yamllint, kubeconform, kube-linter)를 실행하고, 애드온을 바꿨다면 `helm template`도 실행한다.

## lint
도구: yamllint, kubeconform(CRD 스키마 카탈로그 포함), kube-linter. 공통 도구(workflow, Dockerfile, lefthook)는 `.claude/rules/ci-common.md`에 있다.

규칙 세트와 설정 위치는 `.claude/rules/lint.md`에 있다. **검사 도구의 설정 파일을 만들거나 고칠 때는 이 파일을 먼저 읽는다.**

## 절대 규칙
- **클러스터를 직접 변경하지 않는다**: `kubectl apply`, `edit`, `delete`, `scale`, `patch`를 실행하지 않는다. 모든 변경은 PR → 머지 → Argo CD sync로 한다.
- **비밀값**: 평문 `Secret` 매니페스트를 커밋하지 않는다. 비밀값은 `ExternalSecret`으로 Secrets Manager `/<project>/<env>/<service>/…`에서 주입한다.
- **AWS 식별자**: IAM role ARN, VPC ID, 계정 ID를 매니페스트에 하드코딩하지 않는다.
  - Pod 권한은 EKS Pod Identity로 연결되므로 ServiceAccount에 annotation을 달지 않는다.
  - 클러스터 정보는 Argo CD 클러스터 Secret의 annotation에서 ApplicationSet이 읽는다.
- **이미지 태그**: git sha로 고정한다. `latest`는 금지한다. 태그는 `envs/<env>/kustomization.yaml`의 `images:`에서만 바꾼다. dev 태그는 서비스 레포 CI가 `main`에 직접 커밋한다(루트 AGENTS.md "Git 규칙"의 유일한 예외). 다른 환경의 태그는 PR로 바꾼다.
- **infra 레포와의 순서**: 새 서비스나 새 환경처럼 AWS 리소스가 필요한 변경은 infra 레포 apply가 끝난 뒤에 머지한다.

## 새 서비스 추가
아래를 같은 PR에 넣는다.
1. `apps/<service>/base/`
2. 각 `envs/<env>`에 서비스 등록과 이미지 태그
3. infra 레포 `modules/environment`의 서비스 목록에 추가됐는지 확인 (Pod Identity, Secrets 경로)
4. docs 레포 서비스 카탈로그 갱신 확인

## 새 환경 추가
1. infra 레포에서 `live/envs/<env>` apply가 끝났는지 확인한다.
2. `envs/_template`을 `envs/<env>`로 복사하고 namespace, 이미지 태그, 호스트를 바꾼다.
3. 필요하면 `argocd/projects/`에 그 환경의 AppProject를 추가한다.
