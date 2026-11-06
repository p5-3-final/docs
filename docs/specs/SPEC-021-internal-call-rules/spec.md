---
id: SPEC-021
title: 내부 동기 호출 규약 적용 (ai-gateway 마감 시간, 생성 클라이언트, 재시도 규칙)
status: Approved
owner: <이름>
repos: [ai, docs]
created: 2026-11-06
updated: 2026-11-06
related: [ADR-0002, ADR-0014, SPEC-009, SPEC-011, SPEC-012, SPEC-016, SPEC-020]
---

# SPEC-021 내부 동기 호출 규약 적용 (ai-gateway 마감 시간, 생성 클라이언트, 재시도 규칙)

> 이 문서에는 **무엇을, 왜**만 쓴다. 클래스, 테이블, 라이브러리 같은 구현 방법은 각 레포의 plan.md에 쓴다.

## 1. 배경과 목적

[아키텍처 개요](../../architecture/overview.md) "통신 규칙"의 내부 동기 호출 규약(2026-11-06, docs #112·#115)이 내부 호출 방식을 정했다.

- 호출 방식은 HTTP/1.1과 JSON이다.
- 호출자는 `X-Request-Deadline`(epoch ms)을 넣는다. 받는 쪽은 남은 시간을 자기 제한 시간과 하위 호출에 넘기고, 남은 시간이 없으면 504로 답한다.
- 클라이언트는 OpenAPI 계약에서 빌드할 때 생성한다.
- 읽기 전용 호출(parse·embed)만 503과 연결 실패에 2회 재시도한다. analyze(VLM)는 요청이 도착하지 않은 연결 실패만 재시도한다.

지금 구현은 이 규약보다 먼저 만들어져 세 가지가 다르다.

- ai-gateway는 `X-Request-Deadline`을 모른다. 호출자가 이미 포기한 요청도 끝까지 외부 모델을 불러 비용과 처리량을 쓴다.
- `libs/ai-client`(SPEC-020, ai #38)는 요청·응답 모델을 손으로 썼다. 계약이 바뀌어도 코드가 따라가는지 검사하지 않는다.
- `libs/ai-client`는 analyze를 502·503·시간 초과에도 재시도한다(SPEC-020 이전 R-11). 같은 VLM 판정에 비용이 두 번 들 수 있다.

이 spec은 세 가지를 규약에 맞춘다. 그리고 다음 spec들(track-analyzer, embedding-worker, aggregator)이 쓸 `/v1/embed`·`/v1/parse` 호출을 클라이언트에 더한다.

## 2. 범위

### 포함

- ai-gateway: `/v1/analyze`·`/v1/embed`·`/v1/parse`가 `X-Request-Deadline`을 받아 남은 시간을 외부 모델 제한 시간에 반영한다. 남은 시간이 없으면 504 `AI_DEADLINE_EXCEEDED`로 답한다.
- `libs/ai-client`
  - 요청·응답 모델을 잠금 버전 계약 `openapi/ai-gateway.yaml`에서 생성한다. 생성 결과가 계약과 다르면 CI가 실패한다.
  - 모든 호출에 `X-Request-Deadline`을 싣는다.
  - 재시도 규칙을 호출 종류별로 나눈다.
  - `/v1/embed`·`/v1/parse` 호출을 더한다.
- event-analyzer: 바뀐 SPEC-020 R-11(연결 실패만 재시도)대로 동작하고, 504를 호출 실패로 기록한다.
- 계약: `openapi/ai-gateway.yaml`에 `X-Request-Deadline` 헤더와 504 응답을 더한다.

### 제외

- Java(backend) 클라이언트 생성: 호출하는 서비스의 spec에서 다룬다. search-service는 다른 담당자, quality-service는 SPEC-028이다.
- analysis-api 내부 읽기 API의 마감 처리: 그 API를 정하는 SPEC-027(aggregator)에서 계약에 넣는다.
- `/v1/inferences`(chunk-processor 추론 경계): ADR-0009 초안이고 다른 담당자 범위다.
- 재판정 job(`unknown` 후보 다시 보기): overview상 pipeline-service 범위다.

## 3. 사용자 시나리오

### US-1 포기한 호출에 비용을 쓰지 않음 (P1)

운영자로서 호출자가 이미 기다리지 않는 요청에 외부 모델 비용과 처리량이 쓰이지 않기를 원한다. 왜냐하면 VLM 호출은 비싸고 느려서, 버려질 결과를 만드는 동안 다른 요청이 밀리기 때문이다.

#### 인수 조건

- Given 마감이 이미 지난 `X-Request-Deadline`, When `/v1/analyze`를 부르면, Then 외부 모델을 부르지 않고 504 `AI_DEADLINE_EXCEEDED`를 돌려준다.
- Given 남은 시간이 프로필 제한 시간보다 짧은 마감, When `/v1/analyze`를 부르면, Then 외부 모델 호출은 남은 시간 안에서 끝나거나 504로 끝난다.
- Given `X-Request-Deadline`이 없는 요청, When 부르면, Then 지금처럼 프로필 제한 시간으로 처리한다.

### US-2 계약과 코드가 어긋나지 않음 (P1)

개발자로서 ai-gateway 계약이 바뀌면 클라이언트 코드가 함께 바뀌기를 원한다. 왜냐하면 손으로 맞춘 모델은 계약이 바뀌어도 테스트가 계속 통과해 운영에서야 틀린 것을 알기 때문이다.

#### 인수 조건

- Given 잠금 계약에서 생성한 클라이언트 모델, When 계약 잠금 버전을 올리고 다시 생성하지 않으면, Then CI가 실패한다.

### US-3 VLM 비용이 두 번 들지 않음 (P1)

운영자로서 일시 장애 때 같은 판정에 비용이 두 번 들지 않기를 원한다. 그러면서도 ai-gateway 재배포처럼 요청이 닿지 않은 경우에는 판정을 잃지 않기를 원한다.

#### 인수 조건

- Given ai-gateway가 analyze에 503을 돌려줌, When 클라이언트가 부르면, Then 다시 부르지 않고 오류로 끝난다.
- Given 첫 analyze 호출에 연결하지 못하고 다음에 성공, When 부르면, Then 성공한 결과를 받는다.
- Given ai-gateway가 parse에 503을 한 번 돌려주고 다음에 성공, When 부르면, Then 성공한 결과를 받는다.

## 4. 요구사항

### 기능 요구사항 (EARS)

| ID | 요구사항 | 시나리오 |
| --- | --- | --- |
| R-1 | WHEN `/v1/analyze`·`/v1/embed`·`/v1/parse` 요청에 `X-Request-Deadline`이 있으면, THE ai-gateway SHALL 받은 시각부터 마감까지 남은 시간과 그 taskType 프로필 제한 시간 중 짧은 것을 외부 모델 호출의 제한 시간으로 쓴다. | US-1 |
| R-2 | IF 요청을 받았을 때 마감까지 남은 시간이 0 이하이면, THEN THE ai-gateway SHALL 저장소·결과 캐시·예산·외부 모델을 부르지 않고 504와 오류 코드 `AI_DEADLINE_EXCEEDED`를 돌려준다. | US-1 |
| R-3 | IF 외부 모델 호출이 R-1의 남은 시간 안에 끝나지 않으면, THEN THE ai-gateway SHALL 504와 `AI_DEADLINE_EXCEEDED`를 돌려주고, 호출 로그·예산 정산은 공급자 시간 초과와 같게 처리한다(SPEC-009, SPEC-016). | US-1 |
| R-4 | IF `X-Request-Deadline`이 0 이상의 정수(epoch ms)가 아니면, THEN THE ai-gateway SHALL 400 `AI_INVALID_REQUEST`를 돌려준다. | US-1 |
| R-5 | WHERE 요청에 `X-Request-Deadline`이 없으면, THE ai-gateway SHALL 프로필 제한 시간만으로 처리한다. | US-1 |
| R-6 | THE ai-client SHALL ai-gateway 요청·응답 모델을 잠금 버전 계약 `openapi/ai-gateway.yaml`에서 생성한 코드로 쓰고, 손으로 쓴 요청·응답 모델을 두지 않는다. | US-2 |
| R-7 | IF 커밋된 생성 코드가 잠금 버전 계약에서 다시 생성한 결과와 다르면, THEN THE ai 레포 CI SHALL 실패한다. | US-2 |
| R-8 | THE ai-client SHALL 모든 호출에 `X-Request-Deadline`(첫 시도를 시작한 시각 + 설정한 제한 시간)을 싣고, 재시도에도 같은 마감을 쓴다. | US-1 |
| R-9 | IF analyze 호출이 연결 실패로 요청을 전달하지 못했으면, THEN THE ai-client SHALL 설정한 횟수(기본 2)까지 지수 대기 후 다시 시도하고, 502·503·504·시간 초과는 다시 시도하지 않는다. | US-3 |
| R-10 | IF embed·parse 호출이 503이나 연결 실패로 끝나면, THEN THE ai-client SHALL 설정한 횟수(기본 2)까지 지수 대기 후 다시 시도한다. | US-3 |
| R-11 | IF 다음 재시도까지 기다리면 R-8의 마감을 넘기면, THEN THE ai-client SHALL 다시 시도하지 않고 마지막 오류로 끝낸다. | US-1, US-3 |
| R-12 | THE ai-client SHALL 실패를 오류 코드 하나로 알린다. 코드는 ProblemDetail의 `code`(없으면 `AI_HTTP_<상태>`), 제한 시간 초과 `AI_TIMEOUT`, 연결 실패 `AI_CONNECTION_FAILED`, 계약과 맞지 않는 응답 `AI_INVALID_RESPONSE`다. | US-3 |
| R-13 | THE ai-client SHALL `/v1/embed`·`/v1/parse` 호출을 제공한다. | US-2 |
| R-14 | IF ai-gateway가 판정 호출에 504를 돌려주면, THEN THE event-analyzer SHALL 그 호출을 다시 시도하지 않고 실패로 기록한다(SPEC-020 R-12·R-13). | US-1, US-3 |

### 비기능 요구사항

| ID | 요구사항 |
| --- | --- |
| NFR-1 | THE ai-gateway SHALL 마감이 지난 요청(R-2)에 로컬 mock 프로필 기준 p95 20ms 안에 504로 답한다. |
| NFR-2 | THE ai-gateway SHALL 마감 검사를 더한 뒤에도 기존 성능 요구사항(SPEC-009 NFR, SPEC-011 NFR, SPEC-016 NFR)을 만족한다. |

## 5. 영향 범위

| 레포 / 서비스 | 변경 개요 | 담당 요구사항 |
| --- | --- | --- |
| ai / ai-gateway | 헤더 읽기·검증, 남은 시간을 Adapter 제한 시간에 반영, 504 | R-1~R-5, NFR-1, NFR-2 |
| ai / libs/ai-client | 계약에서 모델 생성과 CI 비교, 마감 헤더, 호출 종류별 재시도, embed·parse | R-6~R-13 |
| ai / event-analyzer | 504를 실패로 기록, 새 재시도 규칙 사용 | R-14 |
| docs | ai-gateway 계약 | R-1~R-4 |

## 6. 계약 변경

| 계약 파일 | 변경 | 하위호환 |
| --- | --- | --- |
| `service-contracts/openapi/ai-gateway.yaml` | 세 operation에 선택 헤더 `X-Request-Deadline` 추가, 504 `AI_DEADLINE_EXCEEDED` 응답 추가, 400 설명에 잘못된 마감 추가, 문서 버전 1.1.0 | 예(선택 헤더·오류 응답 추가) |

계약 묶음 3.0.0 → 3.1.0

## 7. 성공 지표

- 로컬 compose에서 지난 마감으로 `/v1/analyze`를 부르면 504가 나오고 ai-gateway 호출 로그에 외부 모델 호출이 없다.
- ai 레포 CI가 생성 코드와 계약을 비교한다.

## 8. 미결 사항

- 해당 없음
