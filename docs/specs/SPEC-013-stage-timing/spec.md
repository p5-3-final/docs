---
id: SPEC-013
title: 처리 단계 측정
status: Implementing
owner: <이름>
repos: [ai, docs]
created: 2026-11-04
updated: 2026-11-04
related: [ADR-0010, SPEC-007, SPEC-009]
---

# SPEC-013 처리 단계 측정

> 이 문서에는 **무엇을, 왜**만 쓴다. 클래스, 테이블, 라이브러리 같은 구현 방법은 각 레포의 plan.md에 쓴다.

## 1. 배경과 목적

영상 하나를 처리하는 데 어느 단계에서 시간이 드는지, 모델이나 설정을 바꾸면 속도가 어떻게 달라지는지를 정확도와 나란히 보고 싶다. 지금은 서비스마다 로그 몇 줄로만 남아 단계별로 나눠 볼 수 없다.

[ADR-0010](../../adr/0010-v4-evaluation-readiness.md) ⑩은 처리 단계를 계약으로 고정해 재기로 했다. 단계 ID 목록과 측정 기록 형식(`StageTiming`)을 계약으로 두고, 공통 메시징 라이브러리가 소비마다 큐 대기·처리 시간을 자동으로 잰다. 핸들러 안의 세부 단계는 서비스가 단계 블록으로 잰다. 핸들러 하나가 끝나면 기록을 묶어 `stage.timing`으로 보내고, 이후 quality-service가 적재·리포트한다([아키텍처 개요](../../architecture/overview.md) "처리 단계 측정").

이 spec은 ai 레포의 공통 메시징 라이브러리와 첫 적용 서비스인 normalize를 다룬다. 비즈니스 이벤트의 payload와 처리 흐름은 바뀌지 않는다.

## 2. 범위

### 포함

- 계약: 단계 ID 목록 v1, `StageTiming` 기록 형식, `stage.timing` 토픽 payload, 이벤트 봉투의 선택 필드 `producedAt`
- ai 공통 메시징 라이브러리
  - 이벤트를 발행할 때 봉투에 `producedAt`을 채운다.
  - 소비 그룹마다 큐 대기(`<group>.queue_wait`)와 핸들러 전체(`<group>.handle`)를 자동으로 잰다.
  - 핸들러 안의 세부 단계를 재는 단계 블록
  - 핸들러가 끝나면 기록을 한 메시지로 묶어 보낸다. 발행 설정이 켜져 있으면 `stage.timing`, 꺼져 있으면 JSON 로그다.
- normalize: `normalize.probe`, `normalize.transcode`, `normalize.hls`, `normalize.store` 단계 블록
- ai-gateway의 `video.deleted` 소비도 라이브러리를 쓰므로 자동 측정 대상이다(세부 단계 없음).

### 제외

- quality-service의 적재·리포트, 성능 회귀 CI Gate(quality spec에서 정한다)
- backend `libs/common-messaging`의 같은 기능(v4 전환 F-4, B-5 뒤에 한다)
- 다른 서비스의 세부 단계 ID(각 서비스 spec에서 목록에 더한다)
- 인프라: `stage.timing` 토픽 생성·보존 7일 설정, 운영 발행 설정(사용자 지시 시 infra·gitops에서 한다)

## 3. 사용자 시나리오

### US-1 영상 처리 시간을 단계별로 나눠 봄 (P1)

운영자로서 영상 하나의 정규화가 큐 대기, 메타데이터 읽기, 재인코딩, HLS 만들기, 업로드 중 어디서 오래 걸렸는지 보고 싶다. 왜냐하면 느려진 원인을 찾고 설정을 바꿀 근거가 필요하기 때문이다.

#### 인수 조건

- Given normalize가 영상 하나를 정규화하면, When 핸들러가 끝나면, Then 큐 대기·핸들러 전체·probe·transcode·hls·store 기록이 한 묶음으로 남는다.
- Given 재인코딩 중 실패하면, When 핸들러가 끝나면, Then 실패한 단계와 핸들러 전체가 `error`로 남고 메시지는 원래대로 재시도된다.

### US-2 측정 때문에 처리가 망가지지 않음 (P1)

서비스 담당자로서 측정 기록을 보내지 못해도 영상 처리는 그대로 끝나기를 원한다. 왜냐하면 측정은 부가 기능이기 때문이다.

#### 인수 조건

- Given `stage.timing` 발행이 실패하면, When 핸들러가 성공했으면, Then 입력 메시지는 그대로 커밋되고 경고 로그만 남는다.

### US-3 같은 메시지를 다시 처리해도 기록이 겹치지 않음 (P2)

quality 담당자로서 재배치 등으로 같은 메시지를 다시 처리해도 같은 기록 ID를 받고 싶다. 왜냐하면 upsert로 중복을 흡수해야 단계 통계가 부풀지 않기 때문이다.

#### 인수 조건

- Given 같은 메시지를 같은 시도 번호로 두 번 처리하면, When 기록을 비교하면, Then 묶음 ID와 기록 ID가 같다.

## 4. 요구사항

### 기능 요구사항 (EARS)

"라이브러리"는 ai 레포의 공통 메시징 라이브러리이고, 그것을 쓰는 서비스(normalize, ai-gateway)가 실행 주체다.

| ID | 요구사항 | 시나리오 |
| --- | --- | --- |
| R-1 | WHEN 소비 핸들러가 메시지를 받으면, THE 라이브러리 SHALL 발행 시각부터 받은 시각까지를 `<group>.queue_wait` 기록으로 남긴다. 발행 시각은 브로커가 붙인 적재 시각(LogAppendTime)이 있으면 그것, 없으면 봉투의 `producedAt`이다. | US-1 |
| R-2 | IF 브로커 적재 시각과 `producedAt`이 모두 없으면, THEN THE 라이브러리 SHALL `<group>.queue_wait` 기록을 남기지 않는다. | US-1 |
| R-3 | WHEN 소비 핸들러가 끝나면, THE 라이브러리 SHALL 핸들러 전체 시간을 `<group>.handle` 기록으로 남기고, 예외로 끝났으면 상태를 `error`, 아니면 `ok`로 둔다. | US-1 |
| R-4 | WHEN 서비스가 단계 블록을 실행하면, THE 라이브러리 SHALL 그 블록을 단계 ID, 바깥 단계부터 이은 경로, 처리 개수·단위(있으면)와 함께 기록한다. 블록이 예외로 끝나면 상태를 `error`로 두고 예외를 그대로 전한다. | US-1 |
| R-5 | WHEN 소비 핸들러가 끝나면(성공·실패 모두), THE 라이브러리 SHALL 그 핸들러의 기록을 한 묶음으로 만들어, 발행 설정이 켜져 있으면 `stage.timing` 토픽에, 꺼져 있으면 JSON 로그 한 줄로 보낸다. | US-1 |
| R-6 | IF 측정 묶음을 보내지 못하면, THEN THE 라이브러리 SHALL 입력 메시지의 처리 결과(커밋·재시도·DLQ)를 바꾸지 않고 경고 로그를 남긴다. | US-2 |
| R-7 | THE 라이브러리 SHALL 묶음 ID와 기록 ID를 메시지 위치·시도 번호·단계 경로·측정 대상에서 결정적으로 만들어, 같은 메시지를 같은 시도 번호로 다시 처리하면 같은 ID가 나오게 한다. | US-3 |
| R-8 | WHEN 이벤트를 발행하면, THE 라이브러리 SHALL 봉투의 `producedAt`에 발행 시각(UTC)을 채운다. | US-1 |
| R-9 | WHEN normalize가 `video.uploaded`를 처리하면, THE normalize SHALL 메타데이터 읽기·정규화 사본 만들기·HLS 만들기·저장소 업로드를 각각 `normalize.probe`·`normalize.transcode`·`normalize.hls`·`normalize.store` 단계로 기록하고, 업로드 단계에는 올린 파일 수를 남긴다. | US-1 |
| R-10 | THE 라이브러리와 normalize SHALL 계약의 단계 ID 목록에 있는 단계 ID만 기록한다. | US-1 |

### 비기능 요구사항

| ID | 요구사항 |
| --- | --- |
| NFR-1 | THE 라이브러리 SHALL 측정 기록에 영상 내용, 소유자 ID, 파일 경로를 싣지 않는다. 측정 대상은 sourceId·chunkId·candidateId·queryId만 쓴다. |
| NFR-2 | THE 라이브러리 SHALL 발행 설정이 꺼져 있을 때 측정 때문에 메시지 하나의 처리 시간을 p95 5ms 넘게 늘리지 않는다(단계 블록 10개 기준). |

## 5. 영향 범위

| 레포 / 서비스 | 변경 개요 | 담당 요구사항 |
| --- | --- | --- |
| ai / libs/messaging | 발행 시 `producedAt`, 자동 측정, 단계 블록, 묶음 발행(Kafka·로그) | R-1~R-8, R-10, NFR-1, NFR-2 |
| ai / libs/contracts | 봉투 `producedAt`, 측정 기록 모델 | R-8, R-10 |
| ai / normalize | 단계 블록 4개, 발행 설정 | R-9, R-10 |
| ai / ai-gateway | `video.deleted` 소비가 자동 측정 대상이 됨(코드 변경 없음, 발행 설정만) | R-1~R-6 |
| docs | 계약, overview "처리 단계 측정"의 기록 형식, v4 전환 D-6·A-4 | — |
| infra·gitops | (이후) `stage.timing` 토픽, 운영 발행 설정. 사용자 지시 시 진행한다. | — |

## 6. 계약 변경

| 계약 파일 | 변경 | 하위호환 |
| --- | --- | --- |
| `service-contracts/stages/v1/stages.schema.json` | 단계 ID 목록 v1(normalize 6개, ai-gateway 2개) | 예(새 파일) |
| `service-contracts/stages/v1/stage-timing.schema.json` | `StageTiming` 기록 형식 | 예(새 파일) |
| `service-contracts/events/stage.timing.schema.json` | `stage.timing` payload(`StageTimingBatch`) | 예(새 파일) |
| `service-contracts/asyncapi/stage-timing.yaml` | `stage.timing` 채널. 라이브러리가 발행하므로 발행 서비스별 파일 규칙의 예외 | 예(새 파일) |
| `service-contracts/events/_envelope.schema.json` | 선택 필드 `producedAt` 추가 | 예(선택 필드 추가) |

## 7. 성공 지표

- 로컬 compose에서 영상 하나를 올리면 normalize 로그에 큐 대기·핸들러·세부 단계 4개가 한 묶음으로 남는다.
- 발행 설정을 켜면 같은 묶음이 `stage.timing`에 계약 형식으로 들어간다.

## 8. 미결 사항

- 해당 없음
