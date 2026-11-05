# AGENTS.md — 프로젝트 루트 (docs 레포)

<!-- AI 코딩 도구(Claude Code, Codex, Antigravity) 공통 규칙의 원본이다. CLAUDE.md는 이 파일을 import한다.
     모든 레포에 공통인 규칙만 둔다. 레포별 규칙은 각 레포의 AGENTS.md에, 긴 절차는 rules와 skills에 둔다.
     Antigravity는 규칙 파일 하나당 24,000바이트 제한이 있다(한글은 글자당 3바이트). 200줄 이하를 유지한다. -->

이 디렉터리는 **프로젝트 문서를 관리하는 docs 레포**이자, 모든 서비스 레포의 작업 공간 루트다.

## 레포 지도

| 경로 | 레포 | 내용 |
| --- | --- | --- |
| `./` | docs | SDD 문서(spec), ADR, API·이벤트 계약 원본, 아키텍처 문서, 로컬 docker-compose(`local/`) |
| `repos/backend` | backend | Spring Boot 멀티모듈 MSA (api-gateway, auth, media, pipeline, analysis, search, notification) |
| `repos/ai` | ai | Python uv workspace (ai-gateway와 Data Plane 워커 8개) |
| `repos/frontend` | frontend | React SPA |
| `repos/infra` | infra | Terraform (AWS 리소스). apply는 CI만 한다(예외: `bootstrap` 스택 최초 1회) |
| `repos/gitops` | gitops | Argo CD가 추적하는 Kubernetes 매니페스트 (애드온, 서비스, 환경) |

- `repos/`는 docs 레포의 `.gitignore`에 포함된다. 그 아래 디렉터리는 **각각 독립된 git 레포**다.
- git 명령은 반드시 변경한 파일이 속한 레포 디렉터리에서 실행한다. 루트에서 `repos/*` 파일을 커밋하지 않는다.
- 레포 클론은 `./scripts/clone-repos.sh`로 한다. 레포 목록은 `repos.conf`에 있다. 새 레포는 비슷한 기존 레포의 `AGENTS.md`, `CLAUDE.md`, `.claude/`, `.github/`를 복사해서 시작한다.

### docs 레포 명령

docs 레포에서 작업을 끝내기 전에 바꾼 대상에 해당하는 명령을 실행한다. 세부 규칙은 `docs-writing.md`, `contracts.md`, `ci-common.md`에 있다.

```bash
npx markdownlint-cli2 "docs/**/*.md" "service-contracts/**/*.md" "*.md"             # 문서 형식
lychee --offline "docs/**/*.md" "service-contracts/**/*.md" "*.md"                 # 내부 링크
npx @redocly/cli lint service-contracts/openapi/*.yaml     # 계약을 바꿨을 때
oasdiff breaking <main의 계약> <바뀐 계약> --fail-on ERR  # 계약을 바꿨을 때
shellcheck scripts/*.sh                                # 스크립트를 바꿨을 때
scripts/check-service-contracts-version.sh origin/main # 계약을 바꿨을 때(VERSION을 올렸는지)
./scripts/sync-agent-config.sh --check                 # .claude/rules·skills를 바꿨을 때
```

## 아키텍처 요약

- ADR-0009: normalize·chunk-processor를 포함한 영상 처리·Kafka·계획·배정은 backend 담당, AI팀은 추론 기능 담당이다. 기존 Python 레포 경로는 담당을 결정하지 않는다. 계획은 Job·Chunk만 저장하고 실행·슬롯·chunk.requested Outbox는 배정 시 함께 저장한다. 기존 AI Gateway를 임의 교체하지 않는다.

- 흐름: 클라이언트 → `api-gateway` → 각 서비스. 서비스 간 동기 호출은 REST, 상태 변경은 Kafka 이벤트로 전달한다(ADR-0002).
- 서비스마다 자기 DB를 소유한다. 다른 서비스의 DB에 직접 접근하지 않고 API나 이벤트로만 통신한다.
- 로컬은 루트 `local/`의 docker-compose, 운영은 AWS EKS 클러스터 하나에 환경을 namespace로 나눠 운영한다.
- 운영 변경은 모두 git을 거친다. AWS 리소스는 infra 레포(Terraform, PR에서 plan, 승인 후 CI가 apply), 클러스터 리소스는 gitops 레포(Argo CD가 sync)다. 두 레포를 같이 바꿀 때는 infra를 먼저 반영한다.
- 상세 문서: `docs/architecture/overview.md`, 서비스 목록: `docs/architecture/service-catalog.md`
- 프로젝트 원칙: `docs/principles.md`. 모든 plan은 이 원칙을 지켜야 한다.

## SDD 워크플로 (필수)

코드보다 스펙이 먼저다. **미결 사항이 없고 검증을 통과해 머지된 spec 없이 기능 코드를 작성하지 않는다.** `Approved`는 명세 확정 상태이며 별도 팀원 Approve를 뜻하지 않는다.

| 단계 | 산출물 | 위치 | 스킬 |
| --- | --- | --- | --- |
| 1. Specify (무엇·왜) | `spec.md` (EARS 요구사항) | 루트 `docs/specs/SPEC-NNN-<slug>/` | `sdd-spec` |
| 2. Contract | OpenAPI / AsyncAPI | 루트 `service-contracts/` | — |
| 3. Plan (어떻게) | `plan.md` | 각 레포 `specs/SPEC-NNN-<slug>/` | `sdd-plan` |
| 4. Tasks | `tasks.md` | 각 레포 `specs/SPEC-NNN-<slug>/` | `sdd-plan` |
| 5. Implement | 코드 + 테스트 | 각 레포 | `sdd-implement` |
| 6. Verify | 요구사항별 테스트 통과, spec 상태 갱신 | — | — |

- 레포 경계를 넘는 API·이벤트 변경은 **계약 파일을 먼저 고치고** 나서 구현한다(contract-first).
- 아키텍처 수준의 결정(새 서비스, 새 인프라 구성요소, 기술 교체, 계약의 하위호환 파괴)은 ADR로 남긴다. 스킬은 `sdd-adr`.
- spec 없이 진행해도 되는 경우: 버그 수정, 동작이 바뀌지 않는 리팩터링, 의존성·설정 변경, 문서 수정. 이때는 GitHub 이슈 번호로 추적한다.
- 스킬 호출 방법
  - Claude Code: `/sdd-spec`
  - Codex: `$sdd-spec`
  - Antigravity: 요청 내용에 맞으면 자동으로 쓴다. 이름으로 직접 요청해도 된다.

## 테스트 우선 개발 (TDD)

기능 구현과 버그 수정은 **Red → Green → Refactor** 순서로 진행한다.

1. **Red**: 요구사항(`R-n`) 하나를 검증하는 테스트를 먼저 쓰고, 실행해서 실패하는 것을 확인한다.
   - 기능이 없어서 실패해야 한다. 컴파일 오류, import 오류, 설정 오류로 실패한 것은 Red가 아니다.
2. **Green**: 그 테스트를 통과시키는 최소한의 코드만 작성한다.
3. **Refactor**: 테스트가 통과하는 상태를 유지하면서 중복을 없애고 이름을 다듬는다. 이 단계에서는 동작을 바꾸지 않는다.

- 사이클 하나는 테스트 하나에서 몇 개 정도로 작게 잡는다. 테스트를 한꺼번에 몰아서 쓰고 구현을 나중에 몰아서 하지 않는다.
- 버그 수정도 버그를 재현하는 테스트를 먼저 쓰고 실패를 확인한 뒤 고친다. 테스트 이름에 이슈 번호를 넣는다(`[#87] 만료된 토큰이면 401을 반환한다`).
- 테스트는 공개된 동작(입력과 출력, API 응답, 화면에 보이는 결과)을 검증한다. private 메서드나 내부 상태를 직접 검증하지 않는다.
- 작업을 보고할 때 Red 단계의 실패 출력과 Green 단계의 통과 출력을 요약해서 함께 보고한다.
- 예외
  - 동작이 바뀌지 않는 리팩터링: 새 테스트 대신 기존 테스트가 계속 통과하는지로 확인한다.
  - 설정, 의존성, 문서 변경
  - infra·gitops 레포: 단위 테스트 대신 각 레포 AGENTS.md의 검증 명령(`terraform validate`·`plan`, `kubeconform`)으로 확인한다.
- 추적성: 요구사항부터 테스트까지 ID로 연결한다.
  - tasks.md `T003 [R-1] …`, 테스트 이름이나 DisplayName `[SPEC-012 R-1] 중복 이메일이면 409를 반환한다`, 커밋 `Refs: SPEC-012`, PR 본문 충족한 요구사항 ID 체크리스트

## 주석 규칙

- 주석은 한국어로 쓴다. 식별자는 영어로 쓴다.
- 코드가 **무엇을** 하는지가 아니라 **왜** 그렇게 하는지를 쓴다. 코드를 다시 읽어 주는 주석은 쓰지 않는다. 이름만 바꿔서 설명이 필요 없어지면 이름을 바꾼다.
- 주석을 남겨야 하는 경우
  - 비즈니스 규칙의 근거. 가능하면 요구사항 ID를 적는다(`// SPEC-012 R-3: 탈퇴 후 30일간 재가입 불가`).
  - 직관과 다른 선택: 성능, 외부 시스템의 제약, 우회 방법
  - 매직 넘버의 의미와 출처
  - 허용된 검사 예외(`# type: ignore`, `Any` 등)의 사유
- 공개 인터페이스에는 문서 주석을 단다. 자명한 getter, DTO 필드, 테스트 메서드에는 달지 않는다(테스트는 테스트 이름이 문서다).

| 언어 | 형식 | 대상 |
| --- | --- | --- |
| Java | Javadoc | `libs/`의 public 클래스·메서드, 서비스 간 호출 클라이언트 인터페이스 |
| Python | Google 스타일 docstring | 모듈 밖에서 쓰는 함수·클래스 |
| TypeScript | TSDoc(`/** */`) | `export`하는 훅, 유틸, 공용 컴포넌트 |
| Terraform | `description` 속성 | 모든 `variable`, `output` |
| YAML(매니페스트, Helm values) | `#` 주석 | 기본값과 다른 값을 쓴 이유 |

- 하지 않는 것
  - 주석으로 막아 둔 코드: 지운다. 필요하면 git 이력에서 찾는다.
  - 작성자, 날짜, 변경 이력 주석: git이 기록한다.
  - 이슈 번호 없는 TODO: `TODO(#87): 설명` 형식으로만 쓴다.
- 코드를 바꾸면 그 코드에 달린 주석도 같이 고친다. 틀린 주석은 주석이 없는 것보다 나쁘다.
- 주변 코드의 주석 밀도와 스타일에 맞춘다.

## 정적 검사 (lint)

- 포맷과 lint는 도구가 결정한다. 손으로 정렬하거나 도구 결과와 다르게 맞추지 않는다.
- 각 레포는 lefthook으로 커밋 전에 바뀐 파일을 검사하고, CI가 같은 검사를 전체 대상으로 다시 실행한다. 관문은 CI다. 단, shellcheck는 로컬 검사만 한다.
- 도구와 규칙 세트는 아래 파일에 있다. **검사 도구의 설정 파일을 만들거나 고칠 때는 해당 파일을 먼저 읽는다.**
  - 모든 레포 공통(workflow, Dockerfile, 셸, `.editorconfig`, lefthook): `.claude/rules/ci-common.md`
  - 레포 고유: 각 레포의 `.claude/rules/lint.md`
  - docs 레포: `.claude/rules/docs-writing.md`, `.claude/rules/contracts.md`의 "검사"

### 검사 예외 (무시 주석)

- 검사를 끄는 주석이나 설정은 새로 추가하지 않는 것이 원칙이다.
- 꼭 필요하면 아래를 모두 지킨다.
  - 범위를 가장 좁게 잡는다: 한 줄, 그리고 규칙 이름을 지정한다. 파일 전체나 규칙 세트 전체를 끄지 않는다.
  - 같은 줄(또는 바로 위 줄)에 사유와 이슈 번호를 쓴다.
  - PR 본문의 "검사 예외" 항목에 나열하고 범위·근거를 자체 검토한다. 팀원 Approve를 기다리지 않는다. 테스트 건너뛰기·검사 기준 완화 금지는 유지한다.
- 설정 파일 단위 예외(특정 경로 제외, 특정 파일에서 규칙 허용)는 각 레포 `.claude/rules/lint.md`의 "설정 단위 예외"에 적힌 것만 둔다. 새로 추가하려면 `lint.md`를 같은 PR에서 고치고 근거와 검증 결과를 PR에 적는다. 검사 기준을 낮추는 변경은 하지 않는다.

| 언어·도구 | 허용 형식 | 금지 |
| --- | --- | --- |
| Java | `@SuppressWarnings("<경고 이름>") // 사유 (#87)` (가장 좁은 선언에) | `@SuppressWarnings("all")`, 클래스 전체 |
| Python | `# type: ignore[<코드>]  # 사유 (#87)`, `# noqa: <규칙>  # 사유 (#87)` | 코드 없는 `# type: ignore`, `# noqa`, 파일 단위 `# ruff: noqa` |
| TypeScript | `// @ts-expect-error 사유 (#87)`, `// eslint-disable-next-line <규칙> -- 사유 (#87)` | `@ts-ignore`, `@ts-nocheck`, 파일 단위 `/* eslint-disable */` |
| Terraform | `# tflint-ignore: <규칙> # 사유 (#87)`, `#trivy:ignore:<ID> 사유 (#87)` | `lint.md`에 없는 설정 단위 예외 |
| Kubernetes | `ignore-check.kube-linter.io/<check>: "사유 (#87)"` annotation | `lint.md`에 없는 설정 단위 예외 |

- 예외 없이 금지하는 것
  - 테스트 건너뛰기: `@Disabled`, `pytest.mark.skip`, `it.skip`, `test.only`
  - 실패하는 테스트 삭제
  - 커버리지나 품질 기준값 낮추기
  - CI의 검사 단계를 끄거나 실패를 무시하기(`continue-on-error`)

## 경로별 세부 규칙

Claude Code와 Antigravity는 해당 경로의 파일을 다룰 때 아래 규칙을 자동으로 불러온다. **자동 로드를 지원하지 않는 도구(Codex 등)는 해당 작업을 시작하기 전에 규칙 파일을 직접 읽는다.**

| 작업 대상 | 규칙 파일 |
| --- | --- |
| `docs/specs/**`, 각 레포 `specs/**` (spec·plan·tasks 작성, 상태 전이) | `.claude/rules/sdd-workflow.md` |
| `docs/**/*.md` (문서 작성, EARS 문법, ADR) | `.claude/rules/docs-writing.md` |
| `service-contracts/**` (OpenAPI·AsyncAPI) | `.claude/rules/contracts.md` |
| `.github/workflows/**`, `Dockerfile`, `*.sh`, `.editorconfig`, `lefthook.yml` | `.claude/rules/ci-common.md` |

- 규칙과 스킬의 원본은 `.claude/rules/`와 `.claude/skills/`다. `.agents/`는 `./scripts/sync-agent-config.sh`가 만드는 생성본이므로 직접 수정하지 않는다.
- 원본을 수정했다면 동기화 스크립트를 실행하고, 원본과 생성본을 같은 커밋에 넣는다.

## 문서 ID 규칙

- 기능 스펙: `SPEC-NNN` (3자리, 001부터). 폴더는 `SPEC-NNN-<영문-kebab-slug>`
- 요구사항: spec 안에서 `R-1`, `NFR-1`. 다른 문서에서 참조할 때는 `SPEC-012 R-3`처럼 쓴다.
- ADR: `ADR-NNNN` (4자리), 파일은 `docs/adr/NNNN-<slug>.md`
- 태스크: tasks.md 안에서 `T001`부터

## Git 규칙 (모든 레포 공통)

- **GitHub Flow**를 쓴다. `main`은 보호 브랜치로 두고, 항상 배포 가능한 상태를 유지한다.
- 브랜치 이름: `<type>/SPEC-NNN-<slug>` 또는 `<type>/<이슈번호>-<slug>` (예: `feat/SPEC-012-sign-up`, `fix/87-token-expiry`)
- 커밋은 Conventional Commits 형식으로 쓰고, 설명은 한국어로 쓴다.
  - 형식: `<type>(<scope>): <설명>`. scope는 서비스, 모듈, 환경 이름이다.
  - type: `feat` `fix` `refactor` `test` `docs` `chore` `build` `ci` `perf`
  - 예: `feat(auth-service): 회원가입 API 추가`
  - 본문 끝에 `Refs: SPEC-012` 또는 `Closes #87`을 붙인다.
- PR: squash merge와 필수 CI 통과 및 GitHub 머지 조건 충족이 병합 조건이다. 명세·구현 PR 모두 별도 팀원 Approve 대기 없이 직접 머지할 수 있다(ADR-0007). 요구사항 충돌·미결 사항·원인 불명의 테스트 실패가 있으면 원인과 필요한 결정을 보고한다. 보호 규칙 우회·강제 push·검사 기준 완화는 하지 않는다. PR 본문에 spec 링크와 충족한 요구사항 ID를 적는다.
- `main`에 직접 push하거나 force push하지 않는다. 사용자가 요청하거나 합의된 작업 범위에 포함된 경우 커밋·push·PR 생성·직접 머지까지 이어서 진행한다. 각 단계의 허락을 반복해서 묻지 않는다.
  - 유일한 예외: gitops 레포 `envs/dev`의 이미지 태그 갱신은 서비스 레포 CI가 전용 자격 증명 하나로 `main`에 직접 커밋한다. 브랜치 보호 우회도 그 자격 증명에만 허용한다. 커밋 메시지는 `chore(envs-dev): <service> 이미지를 <sha>로 갱신`이고 본문의 `Refs:`는 생략한다. 다른 환경의 태그와 그 밖의 변경은 PR로 한다.

## 언어 규칙

- 사용자에게 하는 답변, 문서, 커밋 메시지, PR, 코드 주석은 **한국어**로 쓴다.
- 식별자(클래스·변수·함수), API 경로, DB 컬럼, 로그 메시지, 브랜치 slug는 **영어**로 쓴다.

## 보안 규칙

- `.env`, `.env.*` 파일은 읽지 않는다. 값이 필요하면 `.env.example`을 참고하거나 사용자에게 묻는다.
- 비밀값(키, 토큰, 비밀번호)을 코드, 문서, 커밋, 로그에 넣지 않는다. 로컬에서는 환경변수를, 운영에서는 AWS Secrets Manager를 쓴다.
- 새 환경변수를 추가하면 예시 파일도 같이 갱신한다. 로컬 compose로 띄울 때 쓰는 값은 루트 `local/.env.example`, 서비스를 단독 실행할 때 쓰는 값은 그 레포의 `.env.example`에 둔다. 운영 값은 비밀값이면 Secrets Manager, 아니면 gitops 레포 설정(ConfigMap)에 둔다.

## 에이전트 작업 원칙

- 선택이 필요한 경우에는 사용자에게 먼저 확인한다. 새 라이브러리나 프레임워크 도입, 계약 변경, DB 스키마 변경, 새 서비스 추가가 여기에 해당한다.
- spec에 `[NEEDS CLARIFICATION: …]` 표시가 남아 있으면 추측해서 구현하지 않고 질문한다.
- 작업을 끝내기 전에 해당 레포 AGENTS.md에 있는 lint·test 명령을 실행하고 결과를 보고한다. 실패는 실패라고 보고한다.
- 테스트를 건너뛰거나 삭제하거나, 검사를 무력화해서 통과시키지 않는다. 허용되는 예외의 형식은 "검사 예외 (무시 주석)"를 따른다.
- 구현 중 spec과 달라지면 코드를 계속 짜지 말고 멈춘 뒤 사용자에게 알린다. 코드를 바꿨는데 문서와 달라졌다면 문서도 갱신한다. plan·tasks는 같은 PR에서 고치고, spec·계약은 docs 레포에 PR을 먼저 연다(`.claude/rules/sdd-workflow.md`의 "구현 중 spec과 달라질 때").
