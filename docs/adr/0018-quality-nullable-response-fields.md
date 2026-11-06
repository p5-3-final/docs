---
id: ADR-0018
title: quality-service 응답의 결측 값을 null로 표현하고 major를 올린다
status: Accepted
date: 2026-11-07
deciders: [사용자]
related: [SPEC-029, SPEC-030, SPEC-035, ADR-0014, ADR-0016]
---

# ADR-0018 quality-service 응답의 결측 값을 null로 표현하고 major를 올린다

## 맥락

SPEC-029 구현(backend #54)에서 계약 `openapi/quality-service.yaml` 2.0.0으로는 표현할 수 없는 값이 두 가지 나왔다.

- `GateResult.failures[].value`: 기준 실행에만 있고 이번 실행에 없는 지표(R-18)는 값이 없다. 필드가 필수 `number`라 구현은 그 실패를 응답에서 빼고 로그만 남겼다. 운영자는 Gate 실패 이유를 화면에서 볼 수 없다.
- `ReviewItem.analysis`: 사유 `alert_dismissed` 항목(미판정 긴급 알림, SPEC-029 R-28)은 판정 결과가 없다. 필드가 null을 받지 않아 구현은 `{}`를 저장했고, 빈 객체는 Golden Set에 넣을 때 409가 된다.

두 필드를 null 허용으로 바꾸면 oasdiff가 `response-property-became-nullable` 8건을 하위호환 파괴(ERR)로 판정한다. 계약 규칙상 major를 올려야 한다.

## 결정 요인

- 개발 단계이고 이 응답의 소비자는 frontend(SPEC-035) 하나뿐이며, 그 구현도 진행 중이다. 둘 다 같은 담당자가 맡는다.
- handoff 3절 "하위호환 안 남김": 이전 버전을 남기지 않고 새 형식으로 바로 옮긴다.
- 같은 사유로 major를 올린 선례가 있다(ADR-0014, ADR-0016).

## 검토한 선택지

### 1. null 허용, quality-service 3.0.0, 계약 묶음 5.0.0

- 장점: 값이 없다는 사실을 응답이 그대로 말한다. 화면은 null을 "이번 실행에 없음"으로 표시할 수 있다.
- 단점: major 상승 1회. 소비자 lock을 올릴 때 생성 타입이 바뀐다.

### 2. 필드를 빼거나 별도 필드(`missing: true`)로 표현하고 minor 유지

- 장점: 버전이 minor다.
- 단점: 필수 필드를 선택으로 바꾸는 것도 응답 파괴다. 별도 필드는 같은 뜻을 두 곳에 두고, `analysis`의 `{}`는 남는다.

### 3. 지금처럼 응답에서 빼고 로그만 남김

- 장점: 계약 변경이 없다.
- 단점: R-18의 Gate 실패 이유와 R-28의 미판정 알림 검토가 화면에 정확히 나오지 않는다.

## 결정

**1. null 허용, quality-service 3.0.0, 계약 묶음 5.0.0**을 택한다. 이유: 결측을 결측으로 표현하는 것이 가장 단순하고, 지금이 소비자가 없는 마지막 시점이다. 같은 PR에서 `ReviewItem.startMs`·`endMs`에 `int64`와 상한을 더하고(약 24.8일을 넘는 이벤트를 건너뛰던 생성 모델 문제), `AlertReport.firstAlert*` 설명을 구현(단계 `analyzer.alert` 측정)과 맞춘다.

## 결과

- 좋아지는 점: Gate 실패 이유와 미판정 알림을 화면에 정확히 표시한다. Golden Set이 `{}` 분석을 받는 일이 없다.
- 감수할 점: backend·frontend가 lock을 5.0.0으로 올릴 때 생성 타입을 다시 맞춘다.
- 후속 작업: backend quality-service가 null을 쓰도록 고치고, frontend SPEC-035가 null을 표시한다.

## 참고

- [SPEC-029](../specs/SPEC-029-quality-service/spec.md)
- [ADR-0014](0014-ai-gateway-extensible-task-type.md)
- [ADR-0016](0016-aggregator-fold-and-deterministic-caps.md)
