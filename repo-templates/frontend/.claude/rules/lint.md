---
paths:
  - "eslint.config.js"
  - "tsconfig*.json"
  - ".prettierrc*"
---

# lint 설정 (frontend)

검사 예외(무시 주석)의 형식은 루트 AGENTS.md의 "검사 예외 (무시 주석)"를 따른다.

| 도구 | 설정 | 검사 내용 |
| --- | --- | --- |
| TypeScript | `tsconfig.json`: `strict`, `noUncheckedIndexedAccess`, `noImplicitOverride`, `noFallthroughCasesInSwitch` | 타입 |
| ESLint (flat config) | `eslint.config.js` | 아래 표 |
| Prettier | `.prettierrc` | 포맷. ESLint와 겹치는 규칙은 `eslint-config-prettier`로 끈다. Tailwind 클래스 순서는 `prettier-plugin-tailwindcss`로 정렬한다 |

ESLint 구성과 그 규칙이 강제하는 이 레포의 규칙은 다음과 같다.

| 구성 | 강제하는 것 |
| --- | --- |
| `typescript-eslint` `strictTypeChecked` | 타입 기반 오류. `no-explicit-any` 포함 |
| `@typescript-eslint/consistent-type-assertions` (`assertionStyle: "never"`) | `as` 강제 단언 금지 |
| `@typescript-eslint/ban-ts-comment` | `@ts-ignore`, `@ts-nocheck` 금지. `@ts-expect-error`는 설명 필수 |
| `eslint-plugin-react-hooks` | 훅 규칙, 의존성 배열 |
| `eslint-plugin-jsx-a11y` `recommended` | `alt`, `label`, 클릭 가능한 요소 |
| `eslint-plugin-boundaries` | import 방향 `pages → features → shared`, feature 간에는 `index.ts`로만 import |
| `eslint-plugin-testing-library` (테스트 파일만) | `getByRole` 우선, 구현 세부 검증 금지 |
| `no-console` | `console.*` 금지 |

- `eslint.config.js`에서 규칙을 끄거나 `warn`으로 낮추지 않는다.

## 설정 단위 예외 (이 목록만 허용)
- `src/api/generated/`: ESLint와 Prettier 대상에서 제외한다(생성 코드).
- `src/app/ErrorBoundary.tsx`: `no-console`에서 `console.error`만 허용한다(오류 보고).
