---
id: SPEC-NNN
title: <기능 이름>
status: Draft            # Draft | Review | Approved | Implementing | Done | Superseded
owner: <이름>
repos: [backend, frontend]  # 영향받는 레포
created: YYYY-MM-DD
updated: YYYY-MM-DD
related: []              # ADR-NNNN, SPEC-NNN
---

# SPEC-NNN <기능 이름>

> 이 문서에는 **무엇을, 왜**만 쓴다. 클래스, 테이블, 라이브러리 같은 구현 방법은 각 레포의 plan.md에 쓴다.

## 1. 배경과 목적

해결하려는 문제와 이 기능이 필요한 이유. 관련 PRD 에픽.

## 2. 범위

### 포함

-

### 제외

-

## 3. 사용자 시나리오

### US-1 <제목> (P1)

<사용자>로서 <목표>를 하고 싶다. 왜냐하면 <이유>.

#### 인수 조건

- Given <상황>, When <행동>, Then <결과>

## 4. 요구사항

### 기능 요구사항 (EARS)

| ID | 요구사항 | 시나리오 |
| --- | --- | --- |
| R-1 | WHEN <트리거>, THE <서비스> SHALL <응답>. | US-1 |
| R-2 | IF <조건>, THEN THE <서비스> SHALL <응답>. | US-1 |

### 비기능 요구사항

| ID | 요구사항 |
| --- | --- |
| NFR-1 | THE <서비스> SHALL <측정 가능한 기준>. |

## 5. 영향 범위

| 레포 / 서비스 | 변경 개요 | 담당 요구사항 |
| --- | --- | --- |
| backend / auth-service | | R-1, R-2 |
| frontend | | R-3 |

## 6. 계약 변경

| 계약 파일 | 변경 | 하위호환 |
| --- | --- | --- |
| `docs/contracts/openapi/<service>.yaml` | `POST /api/v1/...` 추가 | 예 |

## 7. 성공 지표

-

## 8. 미결 사항

- [NEEDS CLARIFICATION: <질문>]
