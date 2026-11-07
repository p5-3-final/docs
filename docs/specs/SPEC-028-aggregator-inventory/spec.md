---
id: SPEC-028
title: aggregator 정적 객체 재고 비교·장비 방치·위험 노출 예측
status: Implementing
owner: <이름>
repos: [ai, docs]
created: 2026-11-06
updated: 2026-11-07
related: [ADR-0008, SPEC-013, SPEC-017, SPEC-021, SPEC-027, ADR-0015, ADR-0016]
---

# SPEC-028 aggregator 정적 객체 재고 비교·장비 방치·위험 노출 예측

> 이 문서에는 **무엇을, 왜**만 쓴다. 클래스, 테이블, 라이브러리 같은 구현 방법은 각 레포의 plan.md에 쓴다.

## 1. 배경과 목적

방호벽 제거·이동, 작업 후 방호 미복구, 통로에 방치된 장비처럼 청크 하나만 봐서는 알 수 없는 변화가 있다. [아키텍처 v5](../../architecture/architecture.md) "이벤트 정의 목록"은 v2 유형 `object_moved`·`equipment_abandoned`를 aggregator가 만든다고 정한다. 처리 흐름 11단계 (e)도 청크별 정적 객체 재고(`chunk.manifest`)를 시간순으로 비교해 제거·등장·이동·미복구 후보를 `state_compare`로 판정하게 한다.

이 spec은 SPEC-027(aggregator 핵심)에 다음을 더한다.

- `chunk.manifest`의 정적 객체 재고를 청크마다 저장하고, job이 끝나면 시간순으로 이어 맞춘다(v4 ⑤).
- 재고가 사라지거나 옮겨졌거나 세션 직전 영상에 있던 방호 시설이 돌아오지 않은 후보를 `state_compare`로 판정한다. 확정되면 이벤트로 만들어 SPEC-027 상태 계산에 넣는다.
- 장비 방치 시간 규칙: 장비가 사람 없이 오래 멈춰 있으면 템플릿 이벤트를 만든다. 통로·위험구역이면 `event_judge`로 판정한다.
- 영상 끝에 활성인 위험마다 `risk_forecast`로 다음 구간 노출 확률을 낸다(overview AI Gateway 표 `risk_forecast` 행, 1단계 규칙 점수).

입력 `chunk.manifest`는 chunk-processor(다른 담당자)가 낸다. 계약이 없어 이 spec이 아키텍처 문서대로 소비 쪽에서 정한다(2026-11-06 사용자 결정, [handoff](../../handoff.md) 2.1). 재고 클래스·기준값·프롬프트·예측 모델은 AI 담당자 몫이고, 이 spec은 프로필 자리와 기본값만 둔다.

v5.1([아키텍처 v5.1](../../architecture/architecture.md) 6.2절, [ADR-0015](../../adr/0015-realtime-window-pipeline.md)): 실시간 세션은 창마다가 아니라 주기마다 재고·방치·예측을 계산한다.

## 2. 범위

### 포함

- 계약
  - `chunk.manifest`(생산자 확인 필요)
  - 청크 재고 파일 `aggregates/v1/chunk-inventory`
  - 결과 파일 `aggregates/v1/source-result` 확장(`inventory`·`inventoryChanges`·`inventoryEvents`·`forecasts`, 선택 필드)
  - `source.completed` 개수 확장
  - analysis-api 내부 API `final-state`의 `staticObjects`(0.2.0)
  - ai-gateway taskType `state_compare`·`risk_forecast`와 출력 `events/_state-compare`·`events/_risk-forecast`(1.4.0)
  - AsyncAPI(`aggregator` 1.1.0, `chunk-processor` 1.4.0)
  - 단계 ID
- 청크 재고 저장(청크마다 처음 받은 실행), 재고 이어 맞추기, 변화 후보(제거·등장·이동·미복구)
- `state_compare` 판정과 재고 이벤트, 호출 수 상한
- 장비 방치 규칙과 통로·위험구역 판정
- `risk_forecast` 호출
- ai-gateway: `state_compare`(VLM)·`risk_forecast`(predictor Adapter, 1단계 규칙 점수) 레지스트리·프로필·mock

### 제외

- 재고 탐지(정적 객체 판별, 대표 프레임·기준 프레임 저장): chunk-processor(다른 담당자) 몫이다.
- 예측 모델 학습과 교체: AI 담당자 몫이다. 이 spec은 규칙 점수만 둔다.
- 결과 저장·화면 표시: analysis-api·frontend 몫이다(frontend는 SPEC-030 이후).

## 3. 사용자 시나리오

### US-1 안전시설 이동·제거 알기 (P1)

안전관리자로서 방호벽이 옮겨지거나 치워진 순간을 알고 싶다. 왜냐하면 방호가 풀린 채 작업하면 사고 위험이 커지는데 영상을 다 볼 수는 없기 때문이다.

#### 인수 조건

- Given 첫 청크에 있던 방호벽이 다음 청크에서 다른 자리(같은 클래스, 겹침 없음)에 나타남, When 집계하면, Then 변화 `moved` 하나가 `state_compare`로 판정되고, 확정이면 `object_moved` 재고 이벤트와 타임라인 항목이 나온다.
- Given 방호벽이 사라지고 영상 끝까지 다시 나타나지 않음, When 집계하면, Then 변화 `removed`와 `object_removed` 재고 이벤트(판정 결과에 따라)가 나온다.

### US-2 작업 후 방호 미복구 (P1)

안전관리자로서 작업 전 영상에 있던 방호 시설이 작업 후 영상에 없으면 알고 싶다.

#### 인수 조건

- Given 세션 직전 영상의 끝 재고에 방호벽이 있고 이번 영상 어느 청크에도 같은 자리의 방호벽이 없음, When 집계하면, Then 변화 `not_restored`가 판정되고, 확정이면 `barrier_not_restored` 이벤트가 상태 계산에 들어간다.

### US-3 장비 방치 (P2)

안전관리자로서 통로에 사람 없이 오래 세워 둔 지게차를 알고 싶다.

#### 인수 조건

- Given 일반 구역에 사람 없이 12분 멈춘 지게차(기준 10분), When 집계하면, Then 템플릿 설명의 `equipment_abandoned` 이벤트(`judgmentMethod: rule`)가 나온다.
- Given 같은 상황이 통로 구역에서 일어남, When 집계하면, Then `event_judge` 판정을 거친 `rule+vlm` 이벤트가 나온다.

### US-4 위험 노출 예측 (P3)

안전관리자로서 영상 끝에도 해소되지 않은 위험이 다음 10분·30분 안에 사람을 노출시킬 가능성을 보고 싶다.

#### 인수 조건

- Given 영상 끝에 활성인 위험 하나, When 집계하면, Then 그 위험의 `forecasts` 항목(규칙 점수, `method: rule`)이 나온다.
- Given 예측 Adapter 미설정, When 집계하면, Then `status: not_configured`이고 나머지 결과는 그대로 발행된다.

## 4. 요구사항

### 기능 요구사항 (EARS)

| ID | 요구사항 | 시나리오 |
| --- | --- | --- |
| R-1 | WHEN aggregator가 `chunk.manifest`를 받으면, THE aggregator SHALL 그 청크의 재고 파일(`sources/<sourceId>/jobs/<jobId>/aggregate/inventory/<chunkId>.json`)이 없을 때만 정적 객체 재고와 기준 프레임을 저장한다. 이미 있으면 아무것도 하지 않는다. | US-1 |
| R-2 | IF `analysis.completed`를 처리할 때 재고 파일 수가 `counts.chunks`보다 적으면, THEN THE aggregator SHALL 결과를 발행하지 않고 메시지를 재시도 토픽으로 보낸다. | US-1 |
| R-3 | THE aggregator SHALL 청크 재고를 소유 범위 시작 순으로 놓고, 이웃한 두 청크의 같은 클래스 객체를 박스 IoU가 프로필 기준(기본 0.5) 이상인 쌍부터 하나씩 짝지어 같은 객체로 잇는다. | US-1 |
| R-4 | THE aggregator SHALL 짝이 없는 앞 청크 객체를 `removed` 후보(직전 시각은 그 객체의 마지막 관측)로, 짝이 없는 뒤 청크 객체를 `appeared` 후보(이후 시각은 처음 관측)로 만든다. | US-1 |
| R-5 | THE aggregator SHALL 같은 클래스의 `removed`와 `appeared` 후보가 프로필 이동 창(기본 120초) 안이면 시간이 가까운 쌍부터 `moved` 후보 하나로 합친다. | US-1 |
| R-6 | WHERE 세션 직전 영상의 끝 재고(`final-state`의 `staticObjects`)가 있으면, THE aggregator SHALL 그것을 첫 청크 앞의 재고로 놓고 R-3~R-5를 적용하며, 프로필 방호 클래스의 `removed` 후보 중 영상 끝까지 `appeared`와 짝지어지지 않은 것을 `not_restored`로 바꾼다. | US-2 |
| R-7 | THE aggregator SHALL `removed`·`moved`·`not_restored` 후보마다 직전 객체의 대표 프레임(직전 영상의 프레임이면 이 job 폴더 `aggregate/frames/`로 복사한 사본, 2026-11-07 결정 D-17 A)과 이후 시각에 가장 가까운 기준 프레임(`moved`는 이후 객체의 대표 프레임) 두 장, 기대 객체 클래스·구역 이름으로 ai-gateway `state_compare`를 부른다. `appeared` 후보는 부르지 않고 기록만 한다. | US-1, US-2 |
| R-8 | IF job의 판정 호출 수가 프로필 상한(기본 20)에 이르면, THEN THE aggregator SHALL 남은 후보를 판정하지 않고 `eventId`·`verificationStatus` null로 기록한다. 후보는 직전 시각 순으로 판정한다. | US-1 |
| R-9 | THE aggregator SHALL 판정한 후보마다 `moved`는 `object_moved`, `removed`는 `object_removed`, `not_restored`는 `barrier_not_restored` 유형의 재고 이벤트를 `state_compare`의 VLMAnalysis로 만들고, `verificationStatus`가 `confirmed`이면 SPEC-027 상태 계산·노출 지표·타임라인에 넣는다. | US-1, US-2 |
| R-10 | IF `state_compare` 호출이 SPEC-021 R-9 재시도 뒤에도 오류로 끝나면, THEN THE aggregator SHALL 그 재고 이벤트를 `verificationStatus: unknown`인 분석으로 기록하고 상태 계산에 넣지 않는다. | US-1 |
| R-11 | THE aggregator SHALL 프로필 장비 클래스 객체가 이어 맞춘 재고에서 프로필 방치 기준(기본 10분) 이상 머물고, 그동안 같은 구역에 사람 트랙이 없으면 `equipment_abandoned` 이벤트를 만든다. 구역이 없는 객체는 대상이 아니다. | US-3 |
| R-12 | WHERE 장비 방치 구역의 종류가 `aisle`·`hazard`이면, THE aggregator SHALL 그 객체의 대표 프레임으로 `event_judge`를 불러 `rule+vlm` 이벤트로 만들고, 아니면 템플릿 설명의 `rule`·`confirmed` 이벤트로 만든다. 이 호출도 R-8 상한에 센다. | US-3 |
| R-13 | THE aggregator SHALL 영상 끝 재고(이어 맞춘 마지막 객체 목록)를 결과 파일 `inventory`에 담는다. | US-2 |
| R-14 | WHEN SPEC-027 노출 지표 계산이 끝나면, THE aggregator SHALL 영상 끝에 활성인 위험마다 위험 유형·구역 종류·활성 시간·노출 지표·구역 분당 진입 수를 변수로 ai-gateway `risk_forecast`를 부르고 결과를 `forecasts`에 담는다. | US-4 |
| R-15 | IF `risk_forecast`가 미설정 결과(`modelId: null`)를 돌려주거나 오류로 끝나면, THEN THE aggregator SHALL 그 항목을 `not_configured`·`failed`로 두고 나머지 결과를 그대로 발행한다. | US-4 |
| R-16 | THE ai-gateway SHALL `risk_forecast`를 predictor Adapter로 처리하고, 1단계 규칙 점수는 활성 시간과 구역 분당 진입 수만으로 정해지는 결정적 값으로 낸다. | US-4 |
| R-17 | THE aggregator SHALL 변화·재고 이벤트·예측 ID를 jobId와 객체·위험 ID로 결정적으로 만들고, 같은 입력·프로필이면 판정·예측 결과를 뺀 내용이 같게 만든다. | US-1 |
| R-18 | THE aggregator SHALL 처리 시간을 단계 `aggregate.inventory_store`·`aggregate.inventory_compare`·`aggregate.judge`·`aggregate.forecast`로 남긴다(SPEC-013). | US-1 |
| R-19 | WHERE job이 `STREAM`이면, THE aggregator SHALL 재고 비교(R-4~R-7)·장비 방치(R-11~R-12)·예측(R-15)을 창마다 하지 않고 프로필 주기(기본 10분)마다 그때까지의 `chunk.manifest` 재고와 세션 현재 상태로 계산해 결과를 다음 `state.updated`에 담는다. R-8 상한은 세션당으로 센다. | US-1 |

### 비기능 요구사항

| ID | 요구사항 |
| --- | --- |
| NFR-1 | THE aggregator SHALL 청크 60개·청크당 정적 객체 100개인 job의 재고 이어 맞추기(`aggregate.inventory_compare`)를 로컬에서 p95 2초 안에 끝낸다. |
| NFR-2 | THE aggregator SHALL `chunk.manifest` 하나를 p95 300ms 안에 처리한다(로컬 compose). |
| NFR-3 | THE ai-gateway SHALL 규칙 점수 Adapter로 처리하는 `risk_forecast` 호출에 로컬에서 p95 20ms 안에 답한다. |

## 5. 영향 범위

| 레포 / 서비스 | 변경 개요 | 담당 요구사항 |
| --- | --- | --- |
| ai / aggregator | `chunk.manifest` 소비·재고 저장, 이어 맞추기, 변화 후보, 판정, 장비 방치, 예측 | R-1~R-15, R-17, R-18, NFR-1, NFR-2 |
| ai / ai-gateway | `state_compare` 레지스트리(VLM), `risk_forecast` predictor Adapter와 규칙 점수, 프로필·mock | R-7, R-14, R-16, NFR-3 |
| ai / libs | 계약 모델(`ChunkManifest`, 재고 파일, 결과 파일 확장), 단계 ID | R-1, R-13, R-18 |
| docs | 계약, overview 토픽 표 | R-1, R-13 |
| docs / local | 로컬 compose 토픽 `chunk.manifest` | R-1 |
| backend / chunk-processor·analysis-api (다른 담당자) | (이후) `chunk.manifest` 재고 발행, 끝 재고 저장·`final-state` 제공 | — |

## 6. 계약 변경

| 계약 파일 | 변경 | 하위호환 |
| --- | --- | --- |
| `service-contracts/events/chunk.manifest.schema.json` | 새 이벤트(생산자 확인 필요) | 예(추가) |
| `service-contracts/aggregates/v1/chunk-inventory.schema.json` | 새 파일 형식 | 예(추가) |
| `service-contracts/aggregates/v1/source-result.schema.json` | 선택 필드 `inventory`·`inventoryChanges`·`inventoryEvents`·`forecasts`, 타임라인 종류 `inventory_event` | 예(선택 필드·열거값 추가, 아직 소비자 구현 없음) |
| `service-contracts/events/source.completed.schema.json` | `counts`에 선택 필드 `inventoryEvents`·`forecasts` | 예(선택 필드 추가) |
| `service-contracts/events/_state-compare.schema.json`, `_risk-forecast.schema.json` | 새 공용 형식 | 예(추가) |
| `service-contracts/openapi/analysis-service.yaml` | `FinalState.staticObjects`(0.1.0 → 0.2.0) | 예(응답 필드 추가) |
| `service-contracts/openapi/ai-gateway.yaml` | TaskType `state_compare`·`risk_forecast`(1.3.0 → 1.4.0) | 예(열린 목록 값 추가, ADR-0014) |
| `service-contracts/asyncapi/aggregator.yaml` | `chunk.manifest` 소비 채널(1.0.0 → 1.1.0) | 예(추가) |
| `service-contracts/asyncapi/chunk-processor.yaml` | `chunk.manifest` 발행 채널(1.3.0 → 1.4.0, 생산자 확인 필요) | 예(추가) |
| `service-contracts/stages/v1/stages.schema.json` | `aggregate.inventory_store`·`aggregate.inventory_compare`·`aggregate.judge`·`aggregate.forecast` | 예(추가) |
| `service-contracts/events/chunk.manifest.schema.json` | v5.1: 선택 필드 `jobType`·`trackIdEpoch`·`last`·`gapMs`(생산자 stream-ingestor 추가, SPEC-037) | 예(선택 필드 추가) |

계약 묶음 3.7.0 → 3.8.0. v5.1 변경은 3.15.0 → 4.0.0(quality-service 응답 enum을 열린 목록으로 바꾼 하위호환 파괴 1회, ADR-0016. 나머지는 선택 필드·값 추가) 4.0.0 → 4.1.0(2026-11-07): `_risk-forecast.horizons` 최소 0개(모델 미설정 대체 결과, R-15). R-7의 직전 영상 프레임은 이 job 폴더로 복사해 보낸다(결정 D-17 A, 계약 변경 없음).

## 7. 성공 지표

- 로컬 compose에서 방호벽 이동이 담긴 `chunk.manifest` 두 건과 `analysis.completed`가 `object_moved` 재고 이벤트가 든 `source.completed`로 이어지고, 결과 파일이 계약 스키마를 통과한다.

## 8. 미결 사항

- 해당 없음
