---
paths:
  - "bootstrap/**"
  - "argocd/**"
  - "platform/**"
  - "apps/**"
  - "envs/**"
---

# GitOps 매니페스트 규칙

## 배치
- `apps/<service>/base`에는 환경과 무관한 공통 정의만 둔다. 환경별 차이는 `envs/<env>`에서 Kustomize patch로 적용한다.
- `envs/<env>`에는 그 환경의 차이만 둔다. `_template`과 비교했을 때 이름, 태그, 수치만 달라야 한다.
- `platform/<addon>`에는 Helm chart 버전과 values만 둔다. chart 버전은 정확한 버전으로 고정한다.

## 매니페스트
- 모든 Deployment에 다음을 둔다.
  - `resources.requests/limits`
  - `readinessProbe`/`livenessProbe`: Spring은 `/actuator/health/{readiness,liveness}`, FastAPI는 `/ready`, `/health`
  - `securityContext` (`runAsNonRoot: true`, 가능하면 `readOnlyRootFilesystem: true`)
- 라벨은 `app.kubernetes.io/name`, `app.kubernetes.io/part-of`, `app.kubernetes.io/version`을 공통으로 단다.
- ServiceAccount 이름은 서비스 이름과 같게 짓는다. infra 레포의 Pod Identity 연결이 이 이름을 기준으로 한다.
- Service는 `ClusterIP`로 만든다. 외부에는 api-gateway와 frontend만 Ingress(ALB)로 공개한다.
- ConfigMap 내용이 바뀌면 Pod가 재시작되도록 Kustomize `configMapGenerator`를 쓴다.

## Argo CD
- Application을 손으로 하나씩 만들지 않는다. `platform/*`와 `envs/*`는 ApplicationSet이 폴더를 보고 생성한다.
- 모든 Application은 AppProject에 속하고, AppProject는 허용 namespace와 소스 레포를 제한한다.
- sync 정책: `automated`(`prune: true`, `selfHeal: true`)를 기본으로 한다. 운영 성격의 환경을 추가하면 그 환경의 변경 PR에 사람 승인을 필수로 둔다.

## 검증
- 변경한 뒤에는 바뀐 환경마다 yamllint, kubeconform(CRD 스키마 카탈로그 포함), kube-linter 결과를 보고한다. 명령은 AGENTS.md의 "명령어"를 따른다.
- 애드온을 바꿨다면 `helm template` 렌더링이 성공하는지 확인한다.
