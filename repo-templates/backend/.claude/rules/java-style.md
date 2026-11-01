---
paths:
  - "**/src/main/**/*.java"
---

# Java 코드 스타일

- 포맷은 Spotless(google-java-format)가 결정한다. 수동으로 정렬하지 말고 `./gradlew spotlessApply`를 실행한다.
- 이름 규칙
  - 클래스: `PascalCase`
  - 메서드, 변수: `camelCase`
  - 상수: `UPPER_SNAKE_CASE`
  - 패키지: 소문자
- 클래스 접미사: `*Controller`, `*Service`(application), `*Repository`, `*Client`(외부 호출), `*Request`/`*Response`(DTO), `*Exception`
- 기본은 불변이다. 필드에는 `final`을 붙이고, 컬렉션은 `List.of()`나 `Collections.unmodifiable*`로 반환한다.
- `null`을 반환하지 않는다. 값이 없을 수 있으면 `Optional`을 반환한다. 단, 필드나 파라미터에는 `Optional`을 쓰지 않는다. NullAway가 컴파일할 때 검사하며, null이 꼭 필요한 곳에는 `@Nullable`(JSpecify)을 단다.
- 예외
  - 비즈니스 오류는 `common-core`의 `BusinessException`(오류 코드 포함)을 상속해서 만든다.
  - `catch (Exception e)`로 삼키지 않는다. 다시 던질 때는 원인(`cause`)을 포함한다.
- 엔티티
  - 기본 생성자는 `protected`로 둔다.
  - 상태 변경은 의도가 드러나는 메서드로 한다(`user.changeEmail(...)`). setter는 만들지 않는다.
  - 연관관계는 기본 `LAZY`다. 양방향 매핑은 꼭 필요할 때만 쓴다.
- 날짜와 시간은 `Instant`(저장, 전송)와 `ZoneId.of("Asia/Seoul")`(표시)을 쓴다. `Date`와 `Calendar`는 금지한다.
- 주석과 Javadoc은 루트 AGENTS.md의 "주석 규칙", `@SuppressWarnings`는 "검사 예외 (무시 주석)"를 따른다.
- 가상 스레드(`spring.threads.virtual.enabled=true`)를 쓴다면 `synchronized` 블록 안에서 블로킹 I/O를 하지 않는다.
