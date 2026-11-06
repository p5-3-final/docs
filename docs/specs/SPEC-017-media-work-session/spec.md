---
id: SPEC-017
title: 작업 세션
status: Approved
owner: <이름>
repos: [backend, docs]
created: 2026-11-06
updated: 2026-11-06
related: [ADR-0010, SPEC-003]
---

# SPEC-017 작업 세션

> 이 문서에는 **무엇을, 왜**만 쓴다. 클래스, 테이블, 라이브러리 같은 구현 방법은 각 레포의 plan.md에 쓴다.

## 1. 배경과 목적

3차 목표인 "작업 전후 상태 변화"는 보통 영상이 둘 이상이다. 작업 전에 한 번 찍고, 작업 후에 다시 찍는다. 지금은 상태 스냅샷이 한 영상(sourceId) 안에서만 이어지므로 "작업 전 영상에 있던 방호벽이 작업 후 영상에 없다"를 알 방법이 없다([ADR-0010](../../adr/0010-v4-evaluation-readiness.md) ④).

작업 세션은 영상 여러 개를 작업 하나로 묶는 가장 작은 장치다. 사용자가 세션을 만들고, 영상을 올릴 때 세션과 역할(작업 전·중·후)을 고른다. media-service는 `video.uploaded`에 세션과 역할을 실어 보내고, Aggregator는 세션의 직전 영상 최종 스냅샷을 초기 상태로 쓴다([아키텍처 개요](../../architecture/overview.md) 분석 처리 흐름 1·11단계).

세션과 역할은 업로드 자리를 발급할 때만 정한다. `video.uploaded`가 업로드 완료 때 세션과 역할을 실어 보내므로, 그 뒤에 바꾸면 이미 보낸 이벤트와 어긋난다.

## 2. 범위

### 포함

- 작업 세션 만들기(이름, 현장, 구역), 내 세션 목록, 세션 상세(속한 영상과 순서)
- 업로드 자리 발급 요청에 세션과 역할(`BEFORE`·`DURING`·`AFTER`)을 넣어 영상을 세션에 넣기
- 세션 안 영상 순서: 역할 순서(작업 전 → 중 → 후), 같은 역할 안에서는 업로드 완료 시각 순
- `video.uploaded`에 `sessionId`·`role`
- 영상 응답에 속한 세션과 역할
- REST 계약(`media-service.yaml`)과 이벤트 계약(`video.uploaded`)

### 제외

- 세션 이름 바꾸기, 세션 삭제: 영상은 하나씩 지운다. 빈 세션은 그대로 남는다.
- 업로드 자리를 발급한 뒤 영상의 세션·역할 바꾸기
- Aggregator가 세션의 직전 영상을 찾고 초기 상태를 읽는 방법(내부 API 또는 이벤트 필드): aggregator spec에서 정한다. 이 spec의 순서 규칙(R-7)을 따른다.
- 세션 화면(frontend): 별도 spec
- 현장·구역을 분석의 구역 정의와 잇는 것: 이번에는 표시용 문자열이다.

## 3. 사용자 시나리오

### US-1 작업 전후 영상 묶기 (P1)

현장 관리자로서 작업 전 영상과 작업 후 영상을 한 작업으로 묶고 싶다. 왜냐하면 작업 뒤에 방호벽이 제자리에 돌아왔는지를 두 영상을 비교해 알고 싶기 때문이다.

#### 인수 조건

- Given 로그인한 사용자, When 이름을 넣어 세션을 만들면, Then 세션 ID를 받는다.
- Given 내 세션, When 그 세션과 역할 `BEFORE`로 업로드 자리를 요청하고 업로드를 완료하면, Then `video.uploaded`에 세션 ID와 역할 `BEFORE`가 실린다.
- Given 세션 없이 올린 영상, When 업로드를 완료하면, Then `video.uploaded`에 세션 ID와 역할이 없다.

### US-2 세션 확인 (P1)

현장 관리자로서 세션에 어떤 영상이 어떤 순서로 들어 있는지 보고 싶다. 왜냐하면 비교 기준이 되는 영상이 맞는지 확인해야 하기 때문이다.

#### 인수 조건

- Given `AFTER` 영상을 먼저, `BEFORE` 영상을 나중에 올린 세션, When 세션 상세를 보면, Then `BEFORE` 영상이 먼저 나온다.
- Given 다른 사용자의 세션, When 상세를 요청하면, Then 404를 받는다.

### US-3 잘못된 세션 지정 (P2)

사용자로서 남의 세션이나 없는 세션에 영상을 넣지 못하기를 원한다. 왜냐하면 내 작업 기록에 남의 영상이 섞이면 안 되기 때문이다.

#### 인수 조건

- Given 다른 사용자의 세션 ID, When 그 세션으로 업로드 자리를 요청하면, Then 404를 받고 영상은 만들어지지 않는다.

## 4. 요구사항

### 기능 요구사항 (EARS)

| ID | 요구사항 | 시나리오 |
| --- | --- | --- |
| R-1 | WHEN 사용자가 이름(1~100자)과 선택 항목인 현장·구역(각 100자 이하)으로 세션 만들기를 요청하면, THE media-service SHALL 요청자를 소유자로 하는 세션을 만들고 201과 세션 정보를 반환한다. | US-1 |
| R-2 | IF 세션 만들기 요청의 이름이 없거나 길이가 범위를 벗어나거나 현장·구역이 100자를 넘으면, THEN THE media-service SHALL 400 `MEDIA_INVALID_REQUEST`를 반환한다. | US-1 |
| R-3 | WHEN 사용자가 세션 목록을 요청하면, THE media-service SHALL 요청자가 소유한 세션을 만든 시각 최신순으로 페이지 단위로 반환한다. | US-2 |
| R-4 | WHEN 소유자나 ADMIN이 세션 상세를 요청하면, THE media-service SHALL 세션 정보와 세션에 속한 "삭제"가 아닌 영상 목록을 R-7의 순서로 반환한다. | US-2 |
| R-5 | IF 세션 상세 요청의 세션이 없거나 요청자가 소유자도 ADMIN도 아니면, THEN THE media-service SHALL 둘을 구분하지 않고 404 `MEDIA_SESSION_NOT_FOUND`를 반환한다. | US-2 |
| R-6 | WHEN 업로드 자리 발급 요청에 세션 ID와 역할이 함께 있으면, THE media-service SHALL 만든 영상을 그 세션과 역할에 넣는다. | US-1 |
| R-7 | THE media-service SHALL 세션 안 영상을 역할 순서(`BEFORE` → `DURING` → `AFTER`)로, 같은 역할 안에서는 업로드 완료 시각 순으로, 업로드를 완료하지 않은 영상은 그 역할의 끝에 만든 시각 순으로 정렬한다. | US-2 |
| R-8 | IF 업로드 자리 발급 요청에 세션 ID와 역할 중 하나만 있거나 역할이 정해진 값이 아니면, THEN THE media-service SHALL 400 `MEDIA_INVALID_REQUEST`를 반환하고 영상을 만들지 않는다. | US-3 |
| R-9 | IF 업로드 자리 발급 요청의 세션이 없거나 요청자가 소유한 세션이 아니면, THEN THE media-service SHALL 404 `MEDIA_SESSION_NOT_FOUND`를 반환하고 영상을 만들지 않는다. ADMIN도 자기 세션에만 넣을 수 있다. | US-3 |
| R-10 | IF 세션에 "삭제"가 아닌 영상이 이미 100개 있으면, THEN THE media-service SHALL 그 세션으로 온 업로드 자리 발급 요청에 409 `MEDIA_SESSION_FULL`을 반환하고 영상을 만들지 않는다. | US-1 |
| R-11 | WHEN 세션에 속한 영상이 "업로드 완료"로 바뀌면, THE media-service SHALL `video.uploaded`에 세션 ID(`sessionId`)와 역할(`role`)을 담는다. | US-1 |
| R-12 | WHERE 영상이 세션에 속하지 않으면, THE media-service SHALL `video.uploaded`에 `sessionId`와 `role`을 넣지 않는다. | US-1 |
| R-13 | THE media-service SHALL 영상 응답(상세, 목록, 업로드 자리 발급, 업로드 완료)에 속한 세션 ID와 역할을 담고, 세션이 없으면 null을 담는다. | US-2 |

### 비기능 요구사항

| ID | 요구사항 |
| --- | --- |
| NFR-1 | THE media-service SHALL 세션 만들기, 목록, 상세 요청의 p95 응답 시간을 300ms 이하로 유지한다(세션당 영상 100개 기준). |
| NFR-2 | THE media-service SHALL 같은 세션으로 업로드 자리 발급 요청이 동시에 와도 세션의 "삭제"가 아닌 영상 수가 100개를 넘지 않게 한다(여러 Pod 포함). |

## 5. 영향 범위

| 레포 / 서비스 | 변경 개요 | 담당 요구사항 |
| --- | --- | --- |
| backend / media-service | 세션 저장·API, 업로드 자리 발급의 세션 확인, 영상 응답·`video.uploaded`의 세션 필드 | R-1~R-13, NFR-1, NFR-2 |
| docs | 계약(`media-service.yaml`, `video.uploaded`), overview API·이벤트 표, v4 전환 문서 D-7·F-1 | R-11, R-12 |
| ai / aggregator | (이후) 세션 직전 영상의 초기 상태. aggregator spec에서 다룬다. | — |
| frontend | (이후) 세션 화면. 별도 spec | — |
| backend / pipeline, ai / normalize | 바뀌지 않는다. `video.uploaded`의 새 필드는 선택 항목이라 무시해도 된다. | — |

## 6. 계약 변경

| 계약 파일 | 변경 | 하위호환 |
| --- | --- | --- |
| `service-contracts/openapi/media-service.yaml` | `POST · GET /api/v1/media/sessions`, `GET /api/v1/media/sessions/{sessionId}` 추가. `CreateVideoRequest`에 선택 항목 `sessionId`·`role`, `VideoResponse`에 `session`. 오류 코드 `MEDIA_SESSION_NOT_FOUND`·`MEDIA_SESSION_FULL` | 예(엔드포인트·선택 필드·응답 필드 추가) |
| `service-contracts/events/video.uploaded.schema.json` | 선택 필드 `sessionId`·`role`(둘은 함께 있다) | 예(선택 필드 추가, `schemaVersion` 1 유지) |
| `service-contracts/asyncapi/media-service.yaml` | `video.uploaded` 설명에 세션 필드 | 예 |

## 7. 성공 지표

- 로컬 compose에서 세션을 만들고 `AFTER`·`BEFORE` 순으로 영상을 올리면, 세션 상세가 `BEFORE`를 먼저 보여 주고 두 `video.uploaded`에 같은 세션 ID와 각 역할이 실린다.

## 8. 미결 사항

- 해당 없음
