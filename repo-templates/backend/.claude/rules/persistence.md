---
paths:
  - "**/src/main/resources/db/migration/**"
  - "**/infra/persistence/**"
  - "**/domain/**/*Repository.java"
---

# DB · 마이그레이션 규칙

- 마이그레이션 파일 이름은 `V{yyyyMMddHHmm}__{snake_case_설명}.sql`이다. 타임스탬프를 쓰는 이유는 여러 사람이 동시에 추가할 때 버전 충돌을 피하기 위해서다.
- 머지된 마이그레이션은 절대 수정하지 않는다. 고칠 것이 있으면 새 마이그레이션을 추가한다.
- 운영 무중단을 위해 expand/contract 방식으로 변경한다.
  - 컬럼 삭제나 이름 변경은 "추가 → 코드 전환 → 배포 → 삭제" 순서로 PR을 나눈다.
  - `NOT NULL` 컬럼을 추가할 때는 기본값을 주거나 단계적으로 적용한다.
- 테이블과 컬럼 이름은 `snake_case`로 쓰고, 테이블 이름은 복수형이다. PK는 `id BIGINT` (IDENTITY)다.
- 모든 테이블에 `created_at`, `updated_at`(`TIMESTAMPTZ`)을 둔다.
- 다른 서비스의 테이블을 참조하는 FK를 만들지 않는다. ID 값만 저장한다.
- N+1 쿼리를 피한다. 목록 조회는 fetch join, `@EntityGraph`, 또는 DTO projection으로 처리한다.
- 페이지네이션은 `Pageable`로 하고, 정렬 필드는 화이트리스트로 검증한다.
- 스키마 변경은 plan에 명시하고 사용자에게 확인받는다.
