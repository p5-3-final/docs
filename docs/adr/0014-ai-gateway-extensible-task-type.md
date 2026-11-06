---
id: ADR-0014
title: ai-gateway taskType을 늘어날 수 있는 열린 목록(x-extensible-enum)으로 둔다
status: Accepted
date: 2026-11-06
deciders: [<이름>]
related: [SPEC-009, SPEC-011, SPEC-020, ADR-0012, ADR-0013]
---

# ADR-0014 ai-gateway taskType을 늘어날 수 있는 열린 목록(x-extensible-enum)으로 둔다

## 맥락

- ai-gateway 계약(`openapi/ai-gateway.yaml`)의 `TaskType`(`/v1/analyze`)과 `EmbedTaskType`(`/v1/embed`)은 닫힌 `enum`이고, 요청과 응답이 같은 스키마를 참조한다. 응답의 `taskType`은 요청 값을 그대로 돌려준다.
- 실제로 받아들이는 taskType은 ai-gateway의 Prompt Registry 폴더와 프로필 `[tasks.*]`가 정한다(ADR-0012). 코드는 enum을 쓰지 않고 모르는 값을 400 `AI_UNKNOWN_TASK_TYPE`으로 알린다(SPEC-009 R-3).
- 아키텍처는 taskType을 기능 spec마다 더하도록 정했다(`event_judge_escalate`, `track_attribute`, `object_question`, `source_summary`, `state_compare`, `risk_forecast`).
- 응답 enum에 값을 더하면 oasdiff가 하위호환 파괴(`response-property-enum-value-added`)로 판정한다. 계약 규칙상 하위호환 파괴는 major 버전·경로 버전·ADR이 필요하므로, taskType을 더할 때마다 `/v2`, `/v3`…가 생긴다.
- SPEC-020에서 `event_judge_escalate`를 처음 더하면서 이 문제가 드러났다. 지금 `/v1/analyze`·`/v1/embed` 응답을 읽는 다른 레포 코드는 없다(event-analyzer가 첫 소비자).

## 결정 요인

- 개발 단계라 운영 소비자가 없고, 이전 버전을 남기지 않는다(v4 전환 결정 6).
- taskType 추가는 앞으로 최소 6번 더 있다.
- 계약 문서에 지금 등록된 값의 목록은 남아 있어야 한다(호출자가 무엇을 부를 수 있는지 알아야 한다).

## 검토한 선택지

### 1. 응답 `taskType`만 enum 없는 string으로 바꿈

- 장점: 요청 enum은 그대로라 요청 검증이 계약에 남는다.
- 단점: 요청 enum과 응답 string이 따로 놀아 같은 개념이 두 스키마가 된다. 응답 쪽 문서에서 값 목록이 사라진다.

### 2. `TaskType`·`EmbedTaskType`을 `x-extensible-enum`으로 바꿈

- 장점: 한 스키마를 요청·응답이 함께 쓰고, 알려진 값 목록이 문서에 남는다. oasdiff가 이 표기를 알아 이후 값 추가를 하위호환으로 본다. 코드의 동작(모르는 값 → `AI_UNKNOWN_TASK_TYPE`)과 계약의 뜻이 같아진다.
- 단점: 표준 JSON Schema 키워드가 아니라 스키마 검증으로는 그냥 문자열이다. 쓰는 쪽이 모르는 값을 처리해야 한다.

### 3. 계약 규칙대로 taskType을 더할 때마다 경로 버전을 올림

- 장점: 규칙을 예외 없이 지킨다.
- 단점: 소비자가 없는데 이전 경로를 남겨야 하고, 기능마다 경로 버전이 늘어난다.

## 결정

**2. `x-extensible-enum`으로 바꾼다.** 이유:

- 값이 늘어나는 것이 설계 전제인 목록이라 닫힌 enum이 뜻과 맞지 않는다.
- 실제 목록의 원본은 Prompt Registry와 프로필이고, 계약은 알려진 값을 문서로 남기는 역할이다.
- 이번 전환은 응답에서 enum 제약을 없애므로 한 번 하위호환 파괴로 판정된다. 소비자가 없는 개발 단계라 경로(`/v1`)는 그대로 두고, 계약 문서 `info.version`을 1.0.0으로, 계약 묶음 `VERSION`을 3.0.0으로 올린다. 이후 taskType 추가는 minor다.

## 결과

- 좋아지는 점: 기능 spec이 taskType을 더해도 경로 버전을 올리지 않는다.
- 감수할 점: ai-gateway 응답의 `taskType`을 생성 코드에서 닫힌 enum 타입으로 받지 않아야 한다. 요청 값 검증은 ai-gateway가 런타임에 한다.
- 후속 작업: 다른 OpenAPI 계약에서도 늘어날 수 있는 목록은 같은 방식으로 정의한다. 이벤트 스키마(JSON Schema)의 enum은 이 결정의 대상이 아니다.

## 참고

- [SPEC-020](../specs/SPEC-020-event-analyzer-vector/spec.md) R-20
- [계약 규칙](../../.claude/rules/contracts.md)
- Zalando RESTful API Guidelines, "Prefer compatible extensions" (`x-extensible-enum`)
