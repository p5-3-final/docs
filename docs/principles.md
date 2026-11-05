---
version: 1.0.0
ratified: 2026-10-28
updated: 2026-11-03
---

# 프로젝트 원칙 (Principles)

모든 spec, plan, 코드가 지켜야 하는 원칙이다. 각 레포의 plan.md는 `원칙 점검` 섹션에서 아래 원칙을 하나씩 확인한다.
원칙을 어겨야 할 때는 plan과 PR에 그 이유와 검증 결과를 남긴다. 원칙 자체의 변경은 ADR로 남긴다. 팀이 확정한 정책에 따라 별도 팀원 Approve 대기 없이 필수 검사 후 직접 머지한다(ADR-0007).

## I. 스펙 우선 (Spec-First)

기능 코드는 미결 사항이 없고 자체 검토·필수 검사를 거쳐 `Approved` 상태로 머지된 spec을 기준으로 작성한다. `Approved`는 명세 확정이며 별도 팀원 승인 대기는 요구하지 않는다. spec에는 무엇·왜를, plan에는 어떻게를 쓴다.

## II. 계약 우선 (Contract-First)

레포 경계를 넘는 모든 API와 이벤트는 `service-contracts/`에 먼저 정의하고, 구현이 그 계약을 따른다. 프론트엔드의 API 타입은 계약에서 생성한다.

## III. 테스트 우선 (Test-First, TDD)

- 모든 기능 요구사항(R-*)에는 그 요구사항을 검증하는 자동화 테스트가 있어야 한다.
- 기능 구현과 버그 수정은 Red → Green → Refactor 순서로 한다. 테스트를 먼저 쓰고 실패를 확인한 뒤에 구현한다. 버그 수정은 버그를 재현하는 테스트부터 쓴다.
- 테스트는 공개된 동작을 검증하고, 내부 구현에 묶이지 않는다.
- 실패하는 테스트를 지우거나 비활성화해서 통과시키지 않는다.
- 동작이 바뀌지 않는 리팩터링, 설정·문서 변경, infra·gitops 레포는 예외로 하고, 기존 테스트나 검증 명령으로 확인한다.

## IV. 서비스 자율성 (Service Autonomy)

- 서비스는 독립적으로 빌드, 테스트, 배포할 수 있어야 한다.
- 각 서비스는 자기 DB를 소유한다. 다른 서비스의 DB에 직접 접근하지 않는다.
- 서비스 간 코드 공유는 도메인 로직이 없는 공통 라이브러리(`libs/`)로만 한다.

## V. 단순성 (Simplicity)

- 지금 필요하지 않은 추상화, 설정, 인프라를 미리 만들지 않는다(YAGNI).
- 새 외부 의존성(라이브러리, 관리형 서비스)을 추가할 때는 plan에 이유를 쓴다.

## VI. 관측 가능성 (Observability)

- 모든 서비스는 health 엔드포인트, 구조화 로그(JSON), 요청 추적 ID 전파(W3C `traceparent`)를 갖춘다.
- 로그에 개인정보와 비밀값을 남기지 않는다.

## VII. 보안 기본값 (Secure by Default)

- 비밀값은 코드나 이미지에 넣지 않는다. 환경변수 또는 AWS Secrets Manager로 주입한다.
- 인증은 api-gateway에서 검증한다. 각 서비스는 권한(인가)을 직접 확인한다.
- 모든 외부 입력은 경계에서 검증한다.

## VIII. 문서는 코드와 함께 (Docs as Code)

- 구현이 문서와 달라지면 문서를 갱신한다. plan·tasks는 구현과 같은 PR에서, spec·계약은 docs 레포에 PR을 먼저 열어서 고친다. 문서는 Markdown, 다이어그램은 Mermaid로 작성하고 git으로 리뷰한다.
- 코드 주석은 왜를 설명하고, 코드를 바꾸면 같이 고친다. 세부 규칙은 루트 `AGENTS.md`의 "주석 규칙"에 있다.

## IX. GitOps 배포

운영 환경 변경은 오직 git을 통해서만 한다. AWS 리소스는 infra 레포(Terraform, CI가 apply), 클러스터 리소스는 gitops 레포(Argo CD가 sync)를 거친다. 클러스터에 직접 `kubectl apply`하거나, 로컬에서 `terraform apply`하거나, 콘솔에서 수동으로 변경하지 않는다. 예외는 infra 레포 `bootstrap` 스택(state 버킷, OIDC)의 최초 1회 apply뿐이다.
