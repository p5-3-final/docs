# API·이벤트 계약

레포 경계를 넘는 인터페이스의 **원본(single source of truth)**이다. 규칙은 [`.claude/rules/contracts.md`](../.claude/rules/contracts.md)에 있다.

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
├── taxonomy/
│   └── <version>/            # 분류 체계 (이벤트 유형, 객체 종류, 속성, 위험도). 출력 스키마 enum의 원본
│       ├── taxonomy.schema.json          # 이벤트 유형 8종 + other, severity, 클래스 이름 형식
│       └── detector-profile.schema.json  # 탐지 프로필(탐지기 manifest·클래스·supported_events) 형식
└── VERSION                   # 계약 묶음 버전(SemVer, ADR-0013)
```

분류 체계는 버전 폴더(`taxonomy/v2/`)로 두고 계약은 쓸 버전을 경로로 가리킨다. 개발 단계라 이전 버전은 남기지 않고 새 버전으로 바로 옮긴다. 탐지 프로필의 내용은 AI 담당자가 채우고, 여기서는 형식만 정한다([ADR-0010](../docs/adr/0010-v4-evaluation-readiness.md) ①). 라벨은 팀이 정의한 데이터셋에서 이 분류 체계의 클래스 이름으로 바로 달기 때문에 외부 데이터셋 라벨 대응표는 두지 않는다.

## 버전과 릴리스

계약은 묶음 하나로 버전을 매긴다([ADR-0013](../docs/adr/0013-service-contracts-release.md)). 이 폴더의 파일을 바꾼 PR은 [`VERSION`](VERSION)을 올리고(추가 minor, 설명 patch, 하위호환 파괴 major), main에 머지되면 CI가 GitHub Release `service-contracts-v<버전>`에 `service-contracts-<버전>.tar.gz`와 SHA-256을 올린다. 다른 레포는 루트의 `service-contracts.lock`에 버전과 SHA-256을 적고 CI에서 그 버전을 받아 쓴다. 로컬은 작업 공간의 이 폴더를 바로 읽는다.

ai-gateway 프롬프트(Prompt Registry)는 ai-gateway만 쓰므로 계약이 아니라 ai 레포 `services/ai-gateway/registry/prompts/`가 원본이다([ADR-0012](../docs/adr/0012-prompt-registry-source.md)). ai-gateway는 그 프롬프트와 이 계약의 `taxonomy/`를 합쳐 읽는다.

## 생산자와 소비자의 역할

| 역할 | 할 일 |
| --- | --- |
| 생산자 (API를 제공하는 서비스) | 계약 PR을 먼저 열고, 머지된 계약을 그대로 구현한다. springdoc으로 생성한 스펙과 계약을 CI에서 비교하는 것을 권장한다. |
| 소비자 (frontend, 호출하는 서비스) | 계약에서 클라이언트나 타입을 생성한다. 직접 타입을 작성하지 않는다. |

## 검증

규칙 세트와 하위호환 검사 방법은 [`.claude/rules/contracts.md`](../.claude/rules/contracts.md)의 "검사"에 있다.

```bash
npx @redocly/cli lint service-contracts/openapi/*.yaml
oasdiff breaking <main의 계약 파일> <바뀐 계약 파일> --fail-on ERR
```

## Pipeline 연동 초안의 위치

[ADR-0009](../docs/adr/0009-pipeline-dispatch-boundary.md)와 [SPEC-008](../docs/specs/SPEC-008-normalized-intake/spec.md)은 backend 소유 메시지의 의미 초안이다. video.normalized와 normalize AsyncAPI는 SPEC-008에서 확정한다. chunk.requested는 [SPEC-010](../docs/specs/SPEC-010-chunk-dispatch/spec.md)의 신규 backend 계약으로 정의한다. 실제 worker 소비·실행 완료/실패·POST /v1/inferences는 후속 연동이다. 공통 envelope·sourceId Kafka 키·traceparent를 재사용하고, 정수 밀리초·객체 참조·실행 식별자는 후속 계약 PR로 확정한다. 이전 아키텍처의 다른 파티션 키 표기를 구현된 계약으로 취급하지 않는다.

요청 계약: [chunk.requested](events/chunk.requested.schema.json), [Pipeline AsyncAPI](asyncapi/pipeline-service.yaml).
