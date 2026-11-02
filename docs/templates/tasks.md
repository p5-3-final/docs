---
spec: SPEC-NNN
repo: <backend | ai | frontend | infra | gitops>
updated: YYYY-MM-DD
---

# Tasks: SPEC-NNN <기능 이름> — <레포>

규칙

- 태스크 하나는 커밋 하나에서 PR 하나 사이의 크기로 잡는다(반나절 이하).
- `[P]`는 다른 태스크와 병렬로 진행할 수 있다는 뜻이다. `[R-n]`은 담당 요구사항이다.
- 태스크 하나는 요구사항 하나의 Red → Green → Refactor 사이클이다. 테스트와 구현을 같은 태스크에서 끝내서, 커밋마다 테스트가 통과하는 상태를 유지한다.
- 완료한 태스크는 `[x]`로 바꾼다. 커밋한 뒤에는 커밋 해시를 덧붙인다.

## Phase 1: 준비

- [ ] T001 <설정, 의존성, 마이그레이션 파일 생성> — `경로`

## Phase 2: US-1 <시나리오 제목> (P1)

- [ ] T002 [R-1] <검증할 동작> — 테스트 `src/test/...`, 구현 `src/main/...`
- [ ] T003 [P] [R-2] <검증할 동작> — 테스트 `...`, 구현 `...`

## Phase 3: US-2 <시나리오 제목> (P2)

- [ ] T004 ...

## Phase 4: 마무리

- [ ] T0NN 계약과 구현 일치 확인 (springdoc 출력 또는 생성 타입 비교)
- [ ] T0NN 로그, 추적, 메트릭 확인
- [ ] T0NN 환경변수 반영(루트 `local/.env.example`, 레포 `.env.example`, gitops 설정), README 갱신

## 완료 조건 (Definition of Done)

- [ ] 이 레포가 담당하는 모든 R-*의 테스트 통과
- [ ] lint, 타입 검사, 전체 테스트 통과
- [ ] plan.md와 실제 구현이 일치함
- [ ] docs 레포 spec 상태 갱신 (`Implementing` / `Done`)
