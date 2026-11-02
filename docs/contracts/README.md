# API·이벤트 계약

레포 경계를 넘는 인터페이스의 **원본(single source of truth)**이다. 규칙은 [`.claude/rules/contracts.md`](../../.claude/rules/contracts.md)에 있다.

```text
contracts/
├── openapi/
│   ├── _common.yaml          # 공통 스키마 (ProblemDetail, 페이지네이션)
│   └── <service>.yaml        # 서비스별 REST 계약 (OpenAPI 3.1)
├── asyncapi/
│   └── <service>.yaml        # 발행 서비스별 이벤트 계약 (AsyncAPI 3.0, Kafka)
├── auth/
│   └── access-token.md       # 접근 토큰 형식, 공개키 목록, 키 교체 규칙 (auth-service ↔ api-gateway)
├── events/
│   └── <topic>.schema.json   # 이벤트 payload JSON Schema (Spring·Python 계약 테스트의 원본)
└── taxonomy/
    └── <version>/            # 분류 체계 (이벤트 유형, 객체 종류, 속성, 위험도). 출력 스키마 enum의 원본
```

프롬프트는 ai-gateway만 쓰므로 ai 레포 `services/ai-gateway/prompts/`에 둔다.

## 생산자와 소비자의 역할

| 역할 | 할 일 |
| --- | --- |
| 생산자 (API를 제공하는 서비스) | 계약 PR을 먼저 열고, 머지된 계약을 그대로 구현한다. springdoc으로 생성한 스펙과 계약을 CI에서 비교하는 것을 권장한다. |
| 소비자 (frontend, 호출하는 서비스) | 계약에서 클라이언트나 타입을 생성한다. 직접 타입을 작성하지 않는다. |

## 검증

규칙 세트와 하위호환 검사 방법은 [`.claude/rules/contracts.md`](../../.claude/rules/contracts.md)의 "검사"에 있다.

```bash
npx @redocly/cli lint docs/contracts/openapi/*.yaml
oasdiff breaking <main의 계약 파일> <바뀐 계약 파일> --fail-on ERR
```
