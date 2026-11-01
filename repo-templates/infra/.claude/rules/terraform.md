---
paths:
  - "bootstrap/**"
  - "modules/**"
  - "live/**"
---

# Terraform 규칙

- 모듈은 `modules/<name>`에 두고, `live/` 아래 스택(루트 모듈)이 이를 호출한다. 스택에 리소스를 직접 정의하지 않는다.
- 환경 스택(`live/envs/<env>`)은 `module "environment"` 하나만 호출한다. 환경마다 다른 값은 변수로만 표현해서, `_template`을 복사하고 변수만 바꾸면 새 환경이 되게 한다.
- 스택 간 값은 이름 규칙과 태그로 `data` 소스를 조회해 가져온다. `terraform_remote_state`는 쓰지 않는다.
- 이미 제공받은 리소스(RDS 등)는 `resource`로 선언하거나 `import`하지 않는다. `data` 소스로만 참조한다.
- 프로바이더와 모듈 버전을 고정하고 `.terraform.lock.hcl`을 커밋한다.
- 모든 리소스에 `default_tags`(`Project`, `Environment`, `ManagedBy=terraform`)를 단다.
- 변수에는 `description`과 `type`을 붙이고, 가능하면 `validation`도 단다. 비밀값은 변수로 받지 않는다. 민감한 값을 내보내는 `output`에는 `sensitive = true`를 단다.
- 리소스 이름은 `"${var.project}-${var.environment}-<역할>"` 형식으로 짓는다. shared 스택은 `environment`에 `shared`를 쓴다.
- state는 S3 원격 백엔드에 두고 `use_lockfile = true`로 잠근다. key는 `shared/<stack>.tfstate`, `envs/<env>.tfstate`다.
- Pod 권한은 EKS Pod Identity로 준다. 연결 기준은 namespace와 ServiceAccount 이름이며, gitops 레포의 이름과 같아야 한다. 노드 IAM role에 권한을 추가하지 않는다.
- 변경한 뒤에는 `fmt -check -recursive`, `tflint --recursive`, `trivy config .`, 바뀐 스택의 `validate`까지 실행한다. 자격 증명이 있으면 `plan`까지 실행하고 요약을 보고한다(apply는 하지 않는다). 리소스 교체(`-/+`)나 삭제(`-`)가 있으면 강조해서 알린다.
- GitHub Actions용 IAM Role은 OIDC trust policy의 `sub` 조건을 레포, 브랜치, Environment로 제한한다(예: `repo:p5-3-final/infra:environment:tf-dev`).
