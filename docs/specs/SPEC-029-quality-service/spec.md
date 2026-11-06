---
id: SPEC-029
title: quality-service 검토 큐·Golden Set·평가 실행·처리 단계 리포트
status: Approved
owner: <이름>
repos: [backend, docs]
created: 2026-11-06
updated: 2026-11-06
related: [ADR-0007, ADR-0008, ADR-0010, ADR-0011, SPEC-001, SPEC-013, SPEC-020, SPEC-023]
---

# SPEC-029 quality-service 검토 큐·Golden Set·평가 실행·처리 단계 리포트

> 이 문서에는 **무엇을, 왜**만 쓴다. 클래스, 테이블, 라이브러리 같은 구현 방법은 각 레포의 plan.md에 쓴다.

## 1. 배경과 목적

판정 품질은 로컬 결과로 판단하지 않고 Golden Set 평가로만 판단한다([아키텍처 v5](../../architecture/architecture.md) "로컬 개발"). 그러려면 다음이 필요하다.

1. 판정이 애매한 이벤트(`reviewRequired`)와 무작위 표본을 사람이 검토하는 큐
2. 검토 라벨을 모아 버전으로 고정하는 Golden Set. 평가 실행마다 같은 데이터를 쓴다.
3. 평가 잡 결과를 저장하고 기준 실행과 비교하는 CI Gate
4. 모든 소비자가 보내는 `stage.timing`(SPEC-013)의 적재와 영상별·일별 리포트

catalog의 quality-service(backend, 포트 8088, `quality_db`)가 이 일을 맡는다. 할당은 조건부 갱신으로 한 검토자만 가져가고(overview 다중 Pod 표 quality-service 행), Golden Set 확정 버전은 영구 보존하며 삭제 전파에서 뺀다(ADR-0011, overview 보존 표). Golden Set에는 블러 사본만 넣는다(overview "개인정보").

## 2. 범위

### 포함

- 계약: `openapi/quality-service.yaml` 1.0.0, Golden Set 매니페스트 `quality/v1/golden-manifest`
- `event.analyzed` 소비: `reviewRequired` 항목과 유형별 표본을 검토 큐에 넣기
- 검토 큐: 목록·상세, 맡기·내려놓기(조건부), 라벨 저장, 오래 맡은 항목 되돌리기
- Golden Set: 만들기, 초안 항목 넣기·빼기, 버전 확정(프레임 복사·매니페스트), 기준 실행 지정
- 평가 실행: 내부 제출(멱등), CI Gate 비교, 목록·상세
- `stage.timing` 적재(timingId upsert), 영상별 단계 분해, 일 단위 집계와 추이, 원본 90일 보존
- `video.deleted` 소비: 그 영상의 검토 항목·초안 항목 삭제
- api-gateway `/api/v1/quality/**` 라우팅, 로컬 compose에 quality-service와 `quality_db`

### 제외

- 평가 잡 자체(지표 계산, temporal IoU 매칭): ai 레포 evals이고, 이 spec은 결과를 받는 API만 정한다. 매칭 규칙은 SPEC-030에서 정한다.
- 외부 데이터셋 가져오기, bbox·상태 변화 라벨, 특징 내보내기, 처리 단계 성능 Gate: SPEC-030
- 검토·Golden Set·리포트 화면: frontend spec(SPEC-031 이후)
- 이벤트 확인 상태(분석 화면의 확인·기각) 갱신: analysis-api `PUT /events/{id}/review`(다른 담당자) 몫이다. 검토 라벨은 품질 평가용이고 이벤트를 바꾸지 않는다.

## 3. 사용자 시나리오

### US-1 애매한 판정 검토 (P1)

운영자로서 두 판정이 엇갈린 이벤트를 큐에서 하나씩 맡아 정답 라벨을 붙이고 싶다. 왜냐하면 그 라벨이 판정 모델·프롬프트를 고칠 근거이자 평가 데이터가 되기 때문이다.

#### 인수 조건

- Given `reviewRequired: true`인 `event.analyzed`, When quality-service가 받으면, Then 검토 큐에 `UNASSIGNED` 항목(사유 `review_required`)이 하나 생긴다. 같은 메시지를 다시 받아도 하나뿐이다.
- Given 두 운영자가 같은 항목을 동시에 맡기 요청, When 처리하면, Then 한 명만 200이고 다른 한 명은 409 `QUALITY_REVIEW_ALREADY_ASSIGNED`다.
- Given 맡은 항목, When 맡은 사람이 라벨을 저장하면, Then 상태가 `LABELED`이고 라벨이 저장된다. 다른 사람이 저장하면 403 `QUALITY_REVIEW_NOT_ASSIGNEE`다.

### US-2 Golden Set 버전으로 평가 고정 (P1)

운영자로서 검토 라벨을 Golden Set에 모아 버전으로 고정하고 싶다. 왜냐하면 평가 실행마다 데이터가 달라지면 모델 비교를 믿을 수 없기 때문이다.

#### 인수 조건

- Given 라벨이 붙은 항목 3개를 초안에 넣은 Golden Set, When 버전을 확정하면, Then 버전 1이 생기고 매니페스트와 근거 프레임 사본이 Golden Set 저장소에 저장된다.
- Given 확정 버전에 든 영상이 삭제됨(`video.deleted`), When 처리하면, Then 그 영상의 검토 항목과 초안 항목은 지워지고 확정 버전의 매니페스트·프레임은 남는다.

### US-3 CI Gate (P1)

개발자로서 판정 모델·프롬프트를 바꾼 PR의 평가 결과가 기준보다 나빠지면 CI가 실패하기를 원한다.

#### 인수 조건

- Given 기준 실행의 `judge_precision`이 0.78이고 허용 하락폭이 0.02, When 0.74인 실행을 제출하면, Then Gate 결과가 `passed: false`이고 실패 지표에 `judge_precision`이 있다.
- Given 기준 실행이 없는 Golden Set, When 실행을 제출하면, Then `passed: null`이다.

### US-4 처리 단계 리포트 (P2)

운영자로서 영상 하나가 어느 단계에서 오래 걸렸는지, 단계별 p95가 날짜·버전마다 어떻게 바뀌는지 보고 싶다.

#### 인수 조건

- Given 한 영상의 측정 기록, When 영상별 리포트를 조회하면, Then 단계 경로별 개수·합계·p50·p95·오류 수가 나온다.
- Given 일 단위 집계, When `stageId`와 기간으로 추이를 조회하면, Then 날짜별 p50·p95가 나온다.

## 4. 요구사항

### 기능 요구사항 (EARS)

| ID | 요구사항 | 시나리오 |
| --- | --- | --- |
| R-1 | WHEN quality-service가 `reviewRequired: true`인 `event.analyzed`를 받으면, THE quality-service SHALL eventId로 결정적인 itemId의 검토 항목을 사유 `review_required`, 상태 `UNASSIGNED`로 만든다. | US-1 |
| R-2 | WHEN quality-service가 `reviewRequired: false`이고 `analysis.verificationStatus`가 `confirmed`·`rejected`인 `event.analyzed`를 받으면, THE quality-service SHALL eventId 해시가 그 유형의 표본 비율(설정, 기본 0.05) 안에 들 때만 사유 `sample`인 검토 항목을 만든다. | US-1 |
| R-3 | IF 같은 eventId의 검토 항목이 이미 있으면, THEN THE quality-service SHALL 새 항목을 만들지 않고 기존 항목을 바꾸지 않는다. | US-1 |
| R-4 | IF 요청자의 `X-User-Roles`에 `OPERATOR`가 없으면, THEN THE quality-service SHALL `/api/v1/quality/**` 요청을 403 `QUALITY_FORBIDDEN`으로 거절한다. | US-1 |
| R-5 | THE quality-service SHALL 검토 항목 목록을 상태·사유·유형으로 거르고 createdAt·itemId 순으로 쪽 나눠 돌려주며, 상세에 근거 프레임 경로·판정 결과·라벨을 담는다. | US-1 |
| R-6 | WHEN 운영자가 `UNASSIGNED` 항목 맡기를 요청하면, THE quality-service SHALL 조건부 갱신으로 그 운영자에게 `ASSIGNED`로 바꾸고, 갱신이 실패하면 409 `QUALITY_REVIEW_ALREADY_ASSIGNED`(라벨이 끝난 항목은 `QUALITY_REVIEW_ALREADY_LABELED`)를 돌려준다. | US-1 |
| R-7 | WHEN 맡은 사람이 내려놓기를 요청하면, THE quality-service SHALL 항목을 `UNASSIGNED`로 되돌리고, 맡은 사람이 아니면 403 `QUALITY_REVIEW_NOT_ASSIGNEE`, 맡은 상태가 아니면 409 `QUALITY_REVIEW_NOT_ASSIGNED`를 돌려준다. | US-1 |
| R-8 | WHEN 맡은 사람이 라벨을 저장하면, THE quality-service SHALL 라벨과 저장 시각을 기록하고 상태를 `LABELED`로 바꾼다. 이미 `LABELED`인 항목을 같은 사람이 다시 저장하면 덮어쓴다. | US-1 |
| R-9 | IF 라벨의 `eventPresent`가 true인데 `eventType`·`startMs`·`endMs` 중 하나가 없거나 `endMs`가 `startMs` 이하이면, THEN THE quality-service SHALL 400 `QUALITY_INVALID_REQUEST`를 돌려준다. `eventPresent`가 false인데 `eventType`이 있어도 같다. | US-1 |
| R-10 | WHILE 항목이 설정한 시간(기본 24시간) 넘게 라벨 없이 `ASSIGNED`이면, THE quality-service SHALL 주기 작업으로 그 항목을 `UNASSIGNED`로 되돌린다. 주기 작업은 한 Pod만 실행한다. | US-1 |
| R-11 | THE quality-service SHALL Golden Set을 유일한 이름과 분할(`dev`·`eval`)로 만들고, 같은 이름이면 409 `QUALITY_GOLDEN_SET_DUPLICATED`를 돌려준다. | US-2 |
| R-12 | WHEN 운영자가 검토 항목을 초안에 넣으면, THE quality-service SHALL `LABELED`이고 verdict가 `uncertain`이 아닌 항목만 그때의 라벨을 복사해 넣는다. 아니면 409 `QUALITY_REVIEW_NOT_LABELED`, 이미 든 항목이면 409 `QUALITY_GOLDEN_ENTRY_DUPLICATED`다. | US-2 |
| R-13 | THE quality-service SHALL 초안 항목을 빼는 요청을 초안에만 적용하고 확정 버전은 바꾸지 않는다. | US-2 |
| R-14 | WHEN 운영자가 버전 확정을 요청하면, THE quality-service SHALL 초안 항목의 근거 프레임을 Golden Set 저장소 `golden/<setId>/v<버전>/frames/<entryId>/`로 복사하고, 매니페스트(`quality/v1/golden-manifest`)를 쓴 뒤, 마지막 버전 + 1인 버전 행을 만든다. | US-2 |
| R-15 | IF 초안이 비었거나 같은 Golden Set의 확정이 진행 중이면, THEN THE quality-service SHALL 409 `QUALITY_GOLDEN_EMPTY`·`QUALITY_GOLDEN_FREEZE_IN_PROGRESS`를 돌려주고 버전을 만들지 않는다. | US-2 |
| R-16 | WHEN quality-service가 `video.deleted`를 받으면, THE quality-service SHALL 그 영상의 검토 항목과 초안 항목을 지우고, 확정 버전의 매니페스트·프레임 사본은 남긴다. | US-2 |
| R-17 | WHEN 평가 잡이 `POST /internal/v1/quality/evaluation-runs`로 결과를 내면, THE quality-service SHALL Golden Set 버전이 있는지 확인하고 저장해 201을 돌려준다. 같은 runId를 다시 내면 처음 저장한 실행을 200으로 돌려준다. | US-3 |
| R-18 | THE quality-service SHALL 실행을 받을 때 그 Golden Set의 기준 실행과 같은 이름·유형의 지표를 비교해, 기준보다 허용 하락폭(설정, 기본 0.02)보다 더 나쁘거나 기준에만 있는 지표를 실패로 기록하고, 실패가 없으면 `passed: true`, 기준이 없으면 `passed: null`로 Gate 결과를 붙인다. | US-3 |
| R-19 | WHEN 운영자가 기준 실행을 지정하면, THE quality-service SHALL 그 실행이 같은 Golden Set으로 잰 것일 때만 지정하고, 아니면 409 `QUALITY_RUN_SET_MISMATCH`를 돌려준다. | US-3 |
| R-20 | THE quality-service SHALL 평가 실행 목록(Golden Set으로 거르기, 받은 시각 내림차순)과 상세를 돌려준다. | US-3 |
| R-21 | WHEN quality-service가 `stage.timing`을 받으면, THE quality-service SHALL 기록마다 timingId로 upsert해 원본을 저장한다. | US-4 |
| R-22 | THE quality-service SHALL 영상별 리포트를 원본 기록에서 단계 경로별 개수·합계·p50·p95·오류 수로 계산하고, 음수 `durationMs`는 개수에만 넣고 합계·백분위에서 뺀다. | US-4 |
| R-23 | THE quality-service SHALL 매일 한 번 한 Pod에서 전날(UTC) 원본을 `stageId`별, `stageId`·버전 키·값별로 집계해 개수·p50·p95·오류 수를 영구 저장한다. | US-4 |
| R-24 | IF 추이 조회 기간이 90일을 넘거나 `from`이 `to`보다 늦거나 `versionValue`만 있으면, THEN THE quality-service SHALL 400 `QUALITY_INVALID_REQUEST`를 돌려준다. | US-4 |
| R-25 | THE quality-service SHALL 90일이 지난 원본 측정 기록을 월 단위로 지운다. 일 단위 집계는 지우지 않는다. | US-4 |
| R-26 | THE api-gateway SHALL `/api/v1/quality/**`를 quality-service로 라우팅하고 `/internal/**`은 라우팅하지 않는다. | US-1 |

### 비기능 요구사항

| ID | 요구사항 |
| --- | --- |
| NFR-1 | THE quality-service SHALL 같은 항목에 맡기 요청 10개를 동시에 보내면 정확히 1개만 성공시킨다. |
| NFR-2 | THE quality-service SHALL 검토 항목 10,000개에서 목록 조회를 로컬 p95 300ms 안에 돌려준다. |
| NFR-3 | THE quality-service SHALL `stage.timing` 기록을 Pod 하나에서 초당 200건 이상 적재한다(로컬 compose). |
| NFR-4 | THE quality-service SHALL 영상별 리포트를 기록 5,000건인 영상에서 로컬 p95 500ms 안에 돌려준다. |

## 5. 영향 범위

| 레포 / 서비스 | 변경 개요 | 담당 요구사항 |
| --- | --- | --- |
| backend / quality-service | 새 서비스: 소비 3종, 검토 큐, Golden Set, 평가 실행, 단계 리포트, 주기 작업 | R-1~R-25, NFR-1~NFR-4 |
| backend / api-gateway | `/api/v1/quality/**` 라우트 | R-26 |
| backend / libs | 이벤트 모델(`event.analyzed`, `stage.timing`, `video.deleted`) 사용, OpenAPI 생성 코드 | R-1, R-21 |
| docs | 계약, 서비스 카탈로그(계약 파일 "예정" 해제) | R-14, R-17 |
| docs / local | 로컬 compose에 quality-service, `quality_db`, Golden Set 버킷 | R-14 |

## 6. 계약 변경

| 계약 파일 | 변경 | 하위호환 |
| --- | --- | --- |
| `service-contracts/openapi/quality-service.yaml` | 새 파일(작업 19개, 1.0.0) | 예(추가) |
| `service-contracts/quality/v1/golden-manifest.schema.json` | 새 파일 형식 | 예(추가) |

quality-service는 이벤트를 발행하지 않아 AsyncAPI 파일이 없다. 소비하는 `event.analyzed`·`stage.timing`·`video.deleted`는 기존 계약 그대로다.

계약 묶음 3.8.0 → 3.9.0

## 7. 성공 지표

- 로컬 compose에서 SPEC-020 흐름으로 나온 `reviewRequired` 이벤트가 검토 큐에 나타나고, 라벨 → 초안 → 버전 확정 → 평가 실행 제출 → Gate 결과까지 API로 이어진다.

## 8. 미결 사항

- 해당 없음
