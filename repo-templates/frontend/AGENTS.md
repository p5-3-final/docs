# AGENTS.md — frontend (React SPA)

<!-- 이 레포 AI 코딩 도구 공통 규칙의 원본이다. CLAUDE.md는 이 파일을 import한다. 여기에는 frontend 고유 규칙만 둔다. -->

## 상위 규칙 (필수)
- 공통 규칙(SDD, TDD, 주석, lint·검사 예외, Git, 언어, 보안)은 docs 루트의 `../../AGENTS.md`에 있다.
  - Claude Code와 Antigravity(루트 `project/` 폴더를 연 경우)는 이 파일을 자동으로 불러온다.
  - **Codex처럼 상위 파일을 자동으로 읽지 않는 도구는 작업을 시작하기 전에 `../../AGENTS.md`를 직접 읽는다.**
- 경로별 세부 규칙은 아래 표와 같다. 해당 파일을 다룰 때 자동으로 불러오지 않는 도구는 직접 읽는다. `.agents/`는 `scripts/sync-agent-config.sh`가 만드는 생성본이므로 수정하지 않는다.

| 작업 대상 | 규칙 파일 |
| --- | --- |
| `src/**/*.{ts,tsx}` | `.claude/rules/react-style.md` |
| `eslint.config.js`, `tsconfig*.json`, `.prettierrc*` (검사 도구 설정) | `.claude/rules/lint.md` |
| `.github/workflows/**`, `Dockerfile`, `*.sh`, `.editorconfig`, `lefthook.yml` | `.claude/rules/ci-common.md` |

## 스택
Node.js 22 LTS(`.nvmrc`) · pnpm · React 19 · TypeScript(strict) · Vite · React Router · TanStack Query · Zustand(필요할 때만) · React Hook Form + Zod · Vitest · React Testing Library · MSW · Playwright · ESLint(flat config) · Prettier

## 구조 (feature 기반)
```
frontend/
├── src/
│   ├── app/                  # 진입점, providers(QueryClient, Router), 전역 스타일, 에러 바운더리
│   ├── pages/                # 라우트 단위 화면 (조립만, 로직은 features로)
│   ├── features/<feature>/   # components/, hooks/, api/, model/(타입·스키마), index.ts(공개 API)
│   ├── shared/
│   │   ├── ui/               # 도메인 무관 공통 컴포넌트
│   │   ├── lib/              # 유틸, 포맷터
│   │   └── api/              # fetch 클라이언트(baseURL, 인증 헤더, ProblemDetail 처리)
│   └── api/generated/        # OpenAPI에서 생성된 타입 (직접 수정 금지)
├── tests/e2e/                # Playwright
├── mocks/                    # MSW 핸들러
└── specs/SPEC-NNN-*/         # plan.md, tasks.md
```
import 방향은 `pages → features → shared`다. feature끼리는 서로 상대의 `index.ts`를 통해서만 import한다.

## 명령어
```bash
pnpm install
pnpm dev            # http://localhost:5173 (API는 VITE_API_BASE_URL → api-gateway)
pnpm build
pnpm typecheck      # tsc --noEmit
pnpm lint           # eslint .
pnpm format         # prettier --write .
pnpm format:check   # prettier --check .
pnpm test           # vitest
pnpm test:e2e       # playwright
pnpm gen:api        # ../../docs/contracts/openapi/*.yaml → src/api/generated
```
작업을 끝내기 전에 `pnpm typecheck && pnpm lint && pnpm format:check && pnpm test`를 실행한다.

## lint
도구: TypeScript(strict), ESLint(flat config), Prettier. 공통 도구(workflow, Dockerfile, lefthook)는 `.claude/rules/ci-common.md`에 있다.

규칙 세트와 설정 위치는 `.claude/rules/lint.md`에 있다. **검사 도구의 설정 파일을 만들거나 고칠 때는 이 파일을 먼저 읽는다.**

## 핵심 규칙
- **API 타입은 생성한다**: 백엔드 응답 타입을 손으로 쓰지 않는다. 계약이 바뀌면 `pnpm gen:api`를 실행한다. `src/api/generated/`는 수정하지 않는다.
- **API 경로**: 모든 API는 api-gateway를 거친다(`VITE_API_BASE_URL`). 개별 서비스 주소를 하드코딩하지 않는다.
- **상태 관리**
  - 서버 상태는 TanStack Query로 관리한다. query key는 feature별 `queryKeys` 팩토리로 만든다.
  - 클라이언트 전역 상태는 정말 필요할 때만 Zustand로 만든다.
  - 서버 데이터를 전역 store에 복사하지 않는다.
- **타입**: `any`, `as` 강제 단언, `@ts-ignore`는 금지한다(ESLint가 검사한다). 외부 입력(폼, URL 파라미터)은 Zod로 검증한다.
- **컴포넌트**: 함수 컴포넌트를 named export로 내보낸다. 파일 하나에 공개 컴포넌트는 하나다. 파일 이름은 `PascalCase.tsx`다. props 타입은 컴포넌트 옆에 정의한다.
- **오류 처리**: API 오류(ProblemDetail)는 `shared/api`에서 공통으로 파싱한다. 사용자에게 보여줄 메시지는 `code`를 기준으로 매핑한다.
- **환경변수**: `VITE_` 접두사가 붙은 변수는 브라우저에 그대로 노출된다. 비밀값은 절대 넣지 않는다.
- **인증 토큰**: 토큰 저장 방식은 ADR로 결정할 때까지 `localStorage`에 저장하지 않는다. 권장 방식은 httpOnly 쿠키다.
- **접근성**: 시맨틱 태그를 쓴다. 클릭할 수 있는 요소는 `<button>`이나 `<a>`로 만든다. 이미지에는 `alt`, 폼 요소에는 `label`을 단다. 키보드로 조작할 수 있어야 한다.
- **스타일**: 스타일링 방식(Tailwind, CSS Modules 등)은 첫 UI spec의 plan에서 결정하고 이 파일에 기록한다.

## 테스트
- 컴포넌트 테스트는 사용자 관점으로 쓴다. `getByRole`, `getByLabelText`를 우선 쓰고, 구현 세부(state, class)는 검증하지 않는다.
- API는 MSW로 모킹한다. 핸들러는 생성된 타입을 따른다.
- 테스트 이름에 요구사항 ID를 넣는다: `it('[SPEC-012 R-3] 이메일 형식이 틀리면 오류 메시지를 보여준다')`
- P1 사용자 시나리오는 Playwright E2E로 하나 이상 검증한다.

## CI
- PR일 때: typecheck, lint, format:check, test, build를 실행한다. 공통 검사(hadolint, actionlint, zizmor, PR 제목)는 `.claude/rules/ci-common.md`를 따른다. main 머지일 때: 이미지 빌드(nginx 정적 서빙) → ECR push(OIDC) → gitops 레포 `envs/dev` 태그 갱신
