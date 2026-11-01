# AGENTS.md — backend (Spring Boot 멀티모듈 MSA)

<!-- 이 레포 AI 코딩 도구 공통 규칙의 원본이다. CLAUDE.md는 이 파일을 import한다. 여기에는 backend 고유 규칙만 둔다. -->

## 상위 규칙 (필수)
- 공통 규칙(SDD, TDD, 주석, lint·검사 예외, Git, 언어, 보안)은 docs 루트의 `../../AGENTS.md`에 있다.
  - Claude Code와 Antigravity(루트 `project/` 폴더를 연 경우)는 이 파일을 자동으로 불러온다.
  - **Codex처럼 상위 파일을 자동으로 읽지 않는 도구는 작업을 시작하기 전에 `../../AGENTS.md`를 직접 읽는다.**
- 경로별 세부 규칙은 아래 표와 같다. 해당 파일을 다룰 때 자동으로 불러오지 않는 도구는 직접 읽는다. `.agents/`는 `scripts/sync-agent-config.sh`가 만드는 생성본이므로 수정하지 않는다.

| 작업 대상 | 규칙 파일 |
| --- | --- |
| `**/src/main/**/*.java` | `.claude/rules/java-style.md` |
| `**/src/test/**` | `.claude/rules/testing.md` |
| `build-logic/**`, `lombok.config`, `**/*.gradle.kts` (검사 도구 설정) | `.claude/rules/lint.md` |
| `.github/workflows/**`, `Dockerfile`, `*.sh`, `.editorconfig`, `lefthook.yml` | `.claude/rules/ci-common.md` |
| `**/db/migration/**`, `**/infra/persistence/**`, `*Repository.java` | `.claude/rules/persistence.md` |
| `.github/workflows/**` | `.claude/rules/ci.md` |

## 스택
Java 21 · Spring Boot 3.5.x · Spring Cloud 2025.0.x · Gradle(Kotlin DSL, `gradle/libs.versions.toml`) · PostgreSQL · Flyway · JUnit 5 · AssertJ · Mockito · Testcontainers · ArchUnit

## 구조
```
backend/
├── build-logic/                  # convention plugin (java, spring, test 공통 설정)
├── gradle/libs.versions.toml     # 의존성 버전은 여기서만 관리
├── libs/
│   ├── common-core/              # 공통 예외, 오류 코드, 유틸 (도메인 로직 금지, Spring 의존 최소화)
│   └── common-web/               # ProblemDetail 핸들러, 로깅·추적 필터, 공통 web 설정
├── services/
│   ├── api-gateway/              # Spring Cloud Gateway (WebFlux): 라우팅, JWT 검증, CORS
│   ├── user-service/
│   └── <domain>-service/
├── specs/SPEC-NNN-*/             # plan.md, tasks.md
└── .github/workflows/<service>.yml
```

서비스 내부 패키지는 `com.<org>.<service>` 아래에 다음과 같이 나눈다.

| 패키지 | 내용 |
| --- | --- |
| `api` | Controller, 요청/응답 DTO(record) |
| `application` | 유스케이스 서비스. 트랜잭션 경계 |
| `domain` | 엔티티, 값 객체, 도메인 서비스, 리포지토리 인터페이스 |
| `infra` | JPA 구현, 외부 API 클라이언트, 메시징 |

의존 방향은 `api → application → domain ← infra`다. `domain`은 `api`나 `infra`를 import하지 않는다. 이 규칙은 ArchUnit 테스트로 강제한다.

## 명령어
```bash
./gradlew build                                   # 전체 빌드 + 테스트
./gradlew :services:user-service:test             # 서비스 하나 테스트
./gradlew :services:user-service:test --tests '*SignUp*'
./gradlew :services:user-service:bootRun --args='--spring.profiles.active=local'
./gradlew spotlessApply                           # 포맷 (커밋 전 필수)
./gradlew spotlessCheck                          # 포맷 검사 (Error Prone·NullAway는 컴파일할 때 실행된다)
./gradlew :services:user-service:bootBuildImage   # 컨테이너 이미지
```
작업을 끝내기 전에 `spotlessCheck`와 변경한 서비스의 `build`(컴파일 검사와 테스트 포함)를 실행한다.

## lint
도구: Spotless, javac `-Xlint:all -Werror`, Error Prone + NullAway, ArchUnit, `lombok.config`. 공통 도구(workflow, Dockerfile, lefthook)는 `.claude/rules/ci-common.md`에 있다.

규칙 세트와 설정 위치는 `.claude/rules/lint.md`에 있다. **검사 도구의 설정 파일을 만들거나 고칠 때는 이 파일을 먼저 읽는다.**

## 핵심 규칙
- **서비스 간 경계**: `services/a`에서 `services/b`의 코드를 의존하거나 import하지 않는다. 공유가 필요하면 `libs/`(도메인 로직 없음)로 옮기거나 API·이벤트 계약으로 해결한다.
- **API는 계약을 따른다**: `../../docs/contracts/openapi/<service>.yaml`과 경로, 필드, 상태 코드가 일치해야 한다. 계약에 없는 엔드포인트는 추가하지 않는다.
- **의존성 주입**: 생성자 주입만 쓴다(`private final` + `@RequiredArgsConstructor`). 필드 주입(`@Autowired` 필드)은 금지한다.
- **DTO와 엔티티**: Entity를 API 응답으로 노출하지 않는다. 요청과 응답 DTO는 `record`로 만들고 Bean Validation(`@Valid`)으로 검증한다.
- **Lombok**: `@Getter`, `@RequiredArgsConstructor`, `@Builder`만 허용한다. 엔티티에 `@Data`나 `@Setter`를 쓰지 않는다.
- **트랜잭션**: `@Transactional`은 `application` 레이어에만 둔다. 조회에는 `readOnly = true`를 쓴다.
- **오류 응답**: RFC 9457 `ProblemDetail`을 쓰고 `libs/common-web`의 공통 핸들러를 사용한다. 오류 코드는 `<DOMAIN>_<REASON>` 형식이다.
- **DB 스키마**: DB는 서비스마다 하나다. 스키마는 Flyway로만 변경한다(`ddl-auto`는 `validate`). 이미 머지된 마이그레이션 파일은 수정하지 않는다.
- **서비스 간 호출**: `RestClient` 또는 HTTP Interface(`@HttpExchange`)를 쓴다. connect/read 타임아웃을 필수로 설정하고, Resilience4j로 재시도와 서킷브레이커를 건다.
- **설정**: `application.yml`, `application-{local,dev,prod}.yml`로 나눈다. 비밀값은 `${ENV_VAR}`로만 주입한다.
- **로그**: SLF4J를 쓰고, 운영 환경은 JSON 형식이다. 개인정보, 토큰, 비밀번호는 로그에 남기지 않는다. `System.out`은 금지한다.
- **관측성**: Actuator `health`/`info`/`prometheus`를 켜고, Micrometer Tracing으로 `traceparent`를 전파한다.

## 새 서비스 모듈 추가
ADR이 필요하다(루트 AGENTS.md "SDD 워크플로"). 추가할 때는 다음을 같이 갱신한다.
- `settings.gradle.kts`
- `.github/workflows/<service>.yml`
- `../../docs/architecture/service-catalog.md`
- gitops 레포의 `apps/<service>/base`와 `envs/<env>` 등록, infra 레포 `modules/environment`의 서비스 목록
