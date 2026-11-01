---
paths:
  - "build-logic/**"
  - "lombok.config"
  - "**/*.gradle.kts"
---

# lint 설정 (backend)

검사 예외(무시 주석)의 형식은 루트 AGENTS.md의 "검사 예외 (무시 주석)"를 따른다.

| 도구 | 위치 | 검사 내용 |
| --- | --- | --- |
| Spotless (google-java-format) | `build-logic` | 포맷, import 정렬. `*.gradle.kts`는 ktlint |
| javac `-Xlint:all -Werror` | `build-logic` | 컴파일 경고를 오류로 처리한다 |
| Error Prone + NullAway | `build-logic` | 흔한 버그 패턴, `null` 반환·전달 (`com.<org>` 패키지 대상) |
| ArchUnit | 서비스별 `src/test` | 레이어 의존 방향, 서비스 간 import 금지, `GeneralCodingRules`(필드 주입, `System.out`, `java.util.logging` 금지), `java.util.Date`·`Calendar` 금지 |
| `lombok.config` | 레포 루트 | 허용 목록(`@Getter`, `@RequiredArgsConstructor`, `@Builder`) 밖의 기능을 `lombok.<기능>.flagUsage = error`로 막는다: `data`, `setter`, `value`, `sneakyThrows`, `allArgsConstructor`, `noArgsConstructor`, `toString`, `equalsAndHashCode`, `with`, `val`, `var` |

- 위 설정은 `build-logic`의 convention plugin과 레포 루트 파일에만 둔다. 서비스 모듈의 `build.gradle.kts`에서 검사를 끄거나 바꾸지 않는다.
- checkstyle은 쓰지 않는다. 포맷은 Spotless가, 버그 패턴은 Error Prone이, 구조는 ArchUnit이 맡는다.

## 설정 단위 예외 (이 목록만 허용)
- NullAway 검사 대상은 `com.<org>` 패키지로 한정한다(외부·생성 코드 제외).
