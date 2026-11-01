---
paths:
  - "**/src/test/**"
---

# 테스트 규칙 (backend)

| 종류 | 도구 | 대상 |
| --- | --- | --- |
| 단위 | JUnit 5 + AssertJ + Mockito | domain, application |
| 슬라이스 | `@WebMvcTest`, `@DataJpaTest` | Controller 검증·직렬화, 쿼리 |
| 통합 | `@SpringBootTest` + Testcontainers(PostgreSQL) | 유스케이스 전체 흐름 |
| 아키텍처 | ArchUnit | 패키지 의존 방향, 서비스 간 import 금지 |

- DB 테스트는 H2를 쓰지 않고 Testcontainers PostgreSQL을 쓴다. 컨테이너는 `@ServiceConnection`으로 재사용한다.
- 테스트 이름은 `@DisplayName("[SPEC-012 R-1] 중복 이메일이면 409를 반환한다")`처럼 요구사항 ID를 포함한 한국어 문장으로 쓴다.
- given / when / then 구조로 쓰고, 단언은 AssertJ(`assertThat`)로 한다.
- 외부 서비스 호출은 WireMock이나 `MockRestServiceServer`로 대체한다. 테스트에서 실제 외부 API를 호출하지 않는다.
- 테스트끼리 순서나 상태를 공유하지 않는다. `@Transactional` 롤백이나 데이터 정리로 격리한다.
- 빈 테스트, 단언이 없는 테스트를 추가하지 않는다. 테스트 건너뛰기(`@Disabled`)는 루트 AGENTS.md의 "예외 없이 금지하는 것"을 따른다.
