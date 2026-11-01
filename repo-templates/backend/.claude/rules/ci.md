---
paths:
  - ".github/workflows/**"
---

# CI/CD 규칙 (backend)

- workflow는 서비스마다 하나다: `.github/workflows/<service>.yml`
- `paths` 필터는 반드시 아래를 모두 포함한다. 하나라도 빠지면 공통 코드를 바꿨을 때 그 서비스가 재빌드되지 않는다.
  ```yaml
  paths:
    - "services/<service>/**"
    - "libs/**"
    - "build-logic/**"
    - "gradle/**"
    - "*.gradle.kts"
    - ".github/workflows/<service>.yml"
  ```
- PR일 때: `spotlessCheck`, `:services:<service>:build`(Error Prone·NullAway 컴파일 검사와 테스트 포함)를 실행한다. Testcontainers를 쓰므로 Docker가 있는 `ubuntu-latest` 러너를 쓴다.
- main 머지일 때
  1. 이미지를 빌드한다.
  2. ECR에 push한다. 태그는 `${{ github.sha }}`다.
  3. gitops 레포 `envs/dev`의 이미지 태그를 갱신한다(`kustomize edit set image`). gitops 레포 쓰기 권한만 가진 전용 자격 증명을 쓰고, 커밋 메시지는 루트 AGENTS.md "Git 규칙"의 예외 형식을 따른다.
- AWS 인증은 `aws-actions/configure-aws-credentials` + OIDC(`role-to-assume`)로만 한다. Access Key를 secrets에 넣지 않는다.
- 권한은 최소화한다. OIDC가 필요한 job에만 `id-token: write`를 준다. action 고정, 기본 권한, actionlint·zizmor 검사는 `ci-common.md`를 따른다.
- Gradle 캐시는 `gradle/actions/setup-gradle`로 처리한다.
