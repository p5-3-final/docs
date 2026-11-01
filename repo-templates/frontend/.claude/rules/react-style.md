---
paths:
  - "src/**/*.{ts,tsx}"
---

# React · TypeScript 스타일

- 이름 규칙
  - 컴포넌트, 타입: `PascalCase`
  - 훅: `useXxx`
  - 이벤트 핸들러 props: `onXxx`, 내부 핸들러: `handleXxx`
  - 상수: `UPPER_SNAKE_CASE`
- `interface`는 props와 확장이 필요한 객체에, `type`은 유니온과 유틸리티 조합에 쓴다. `enum` 대신 `as const` 객체와 유니온을 쓴다.
- 훅 규칙(`react-hooks` ESLint)을 지킨다. `useEffect`는 외부 시스템과 동기화할 때만 쓴다. 파생 값은 렌더링 중에 계산한다.
- 데이터 패칭은 컴포넌트에서 `fetch`를 직접 부르지 않는다. `features/<f>/api`의 query/mutation 훅을 쓴다.
- 폼은 React Hook Form + `zodResolver`로 만든다. 스키마는 `features/<f>/model`에 둔다.
- 조건부 렌더링을 할 때는 로딩, 에러, 빈 상태를 모두 처리한다.
- 메모이제이션(`useMemo`, `useCallback`, `memo`)은 측정해서 문제가 확인됐을 때만 쓴다.
- 라우트 단위로 코드를 분할한다(`lazy`).
- 사용자에게 보이는 문자열은 한국어로 쓴다. 여러 곳에서 쓰는 메시지는 `shared/lib/messages.ts`에 모은다.
