---
id: SPEC-030
title: quality-service 외부 데이터셋 가져오기·라벨 3종·매칭 규칙·특징 내보내기·성능 Gate
status: Approved
owner: <이름>
repos: [backend, ai, docs]
created: 2026-11-06
updated: 2026-11-06
related: [ADR-0010, ADR-0011, SPEC-013, SPEC-027, SPEC-028, SPEC-029]
---

# SPEC-030 quality-service 외부 데이터셋 가져오기·라벨 3종·매칭 규칙·특징 내보내기·성능 Gate

> 이 문서에는 **무엇을, 왜**만 쓴다. 클래스, 테이블, 라이브러리 같은 구현 방법은 각 레포의 plan.md에 쓴다.

## 1. 배경과 목적

[ADR-0010](../../adr/0010-v4-evaluation-readiness.md) ⑨·⑩은 다음을 서버 쪽 준비로 정했다.

- Golden Set을 검토 큐 라벨(SPEC-029)만으로 만들면 2차 목표(행동·장면 구간 평가)와 3차 목표(상태 변화)의 라벨을 넣을 자리가 없다. 그래서 라벨을 bbox 검출·시간 구간 이벤트·상태 변화 세 종류로 두고, 외부 데이터셋을 매니페스트로 가져온다. 가져올 때 media 등록, 라벨 적재, 개발·평가 분할을 함께 한다.
- 평가 잡이 예측과 라벨을 같은 규칙으로 맞추도록 시간 구간 매칭 규칙(temporal IoU)을 정한다.
- 예측 모델 학습에 쓸 특징을 내보낸다. 정답은 aggregator가 확정 이벤트로 계산한 노출 지표다(SPEC-027, overview 노출 지표 행).
- 처리 단계 성능 Gate: 벤치마크 영상 세트의 단계 p95가 기준선보다 일정 비율 이상 느려지면 실패한다(overview "성능 측정").

데이터셋 고르기·라벨링·학습은 AI 담당자 몫이다. 이 spec은 그 데이터가 들어오고 나가는 자리를 만든다.

## 2. 범위

### 포함

- 계약
  - 가져오기 매니페스트 `quality/v1/dataset-import-manifest`(라벨 3종)
  - Golden Set 매니페스트에 데이터셋 항목(`origin`·`datasetItems`·`datasetOrigin`)
  - 특징 행 `quality/v1/feature-row`
  - `openapi/quality-service.yaml` 1.1.0(가져오기 3개, 내보내기 2개, 내부 성능 Gate 1개, `GoldenSet.origin`)
  - `openapi/media-service.yaml` 1.4.0(내부 데이터셋 영상 등록)
- quality-service
  - 가져오기: 매니페스트 검증, 영상 등록, 분할, `<이름>-dev`·`<이름>-eval` Golden Set 버전 확정, 진행 상태
  - `source.completed` 소비(영상별 최신 결과 파일 경로 기록)
  - 특징 내보내기, 성능 Gate 계산
- media-service: 데이터셋 영상 등록(멱등, 보존 등급 `dataset`, `video.uploaded` 발행)
- ai `evals/`: 시간 구간·bbox·상태 변화 매칭 규칙 구현, 성능 Gate 호출 스크립트

### 제외

- 실제 데이터셋 선택·내려받기·라벨 변환 스크립트: AI 담당자 몫이다.
- 가져오기·내보내기 화면: frontend spec(SPEC-031 이후)
- 검토 큐에서 bbox·상태 변화 라벨을 직접 그리기: 이후 spec이다. 검토 큐 라벨은 SPEC-029 형식 그대로 둔다.

## 3. 사용자 시나리오

### US-1 외부 데이터셋으로 평가 세트 만들기 (P1)

AI 담당자로서 공개 데이터셋 영상과 라벨을 한 번에 가져와 개발·평가 Golden Set으로 쓰고 싶다. 왜냐하면 검토 큐만으로는 행동·상태 변화 라벨이 쌓이지 않기 때문이다.

#### 인수 조건

- Given 영상 2개와 라벨 3종이 든 매니페스트, When 가져오기를 요청하면, Then 영상 2개가 media에 등록돼 분석이 시작되고, 분할 결과에 따라 `<이름>-dev`·`<이름>-eval` Golden Set에 새 버전이 생긴다.
- Given 같은 매니페스트를 다시 가져옴, When 처리하면, Then 같은 videoId가 다시 쓰이고 영상이 두 번 등록되지 않는다.
- Given 매니페스트의 영상 하나가 버킷에 없음, When 처리하면, Then 그 영상만 오류에 남고 가져오기는 `COMPLETED`다.

### US-2 같은 규칙으로 평가 (P1)

AI 담당자로서 평가 잡이 예측 이벤트와 구간 라벨을 같은 규칙으로 맞추기를 원한다. 왜냐하면 규칙이 실행마다 다르면 지표를 비교할 수 없기 때문이다.

#### 인수 조건

- Given 라벨 [10s, 20s] `fall`과 예측 [12s, 22s] `fall`, When 매칭하면, Then temporal IoU 0.667로 짝지어진다.
- Given 같은 라벨에 예측 두 개, When 매칭하면, Then IoU가 큰 하나만 짝지어지고 다른 하나는 오탐이다.

### US-3 예측 학습 특징 (P2)

AI 담당자로서 위험 상태별 특징과 노출 지표를 파일로 받아 예측 모델을 학습하고 싶다.

#### 인수 조건

- Given `source.completed`를 받은 영상이 든 Golden Set, When 특징 내보내기를 요청하면, Then 위험 상태 하나가 한 줄인 JSON Lines 파일이 생기고 줄마다 계약을 통과한다.

### US-4 처리 단계 성능 Gate (P2)

개발자로서 변경 뒤 벤치마크 영상의 단계 p95가 기준선보다 20% 넘게 느려지면 CI가 실패하기를 원한다.

#### 인수 조건

- Given 기준 p95 3,400ms, 후보 p95 4,300ms, 허용 비율 0.2인 단계, When Gate를 계산하면, Then 그 단계가 `failed`이고 결과가 `passed: false`다.
- Given 한쪽 기록이 최소 개수보다 적은 단계, When 계산하면, Then 그 단계는 `skipped`이고 결과에 영향을 주지 않는다.

## 4. 요구사항

### 기능 요구사항 (EARS)

| ID | 요구사항 | 시나리오 |
| --- | --- | --- |
| R-1 | WHEN 운영자가 가져오기를 요청하면, THE quality-service SHALL 가져오기를 `PENDING`으로 만들어 202로 돌려주고 비동기로 처리한다. 같은 매니페스트 경로의 가져오기가 진행 중이면 409 `QUALITY_IMPORT_IN_PROGRESS`다. | US-1 |
| R-2 | IF 매니페스트가 없거나 계약(`quality/v1/dataset-import-manifest`)에 맞지 않거나 `taxonomyVersion`이 지원 버전이 아니면, THEN THE quality-service SHALL 영상을 등록하지 않고 가져오기를 `FAILED`로 끝내며 오류에 이유를 남긴다. | US-1 |
| R-3 | THE quality-service SHALL 영상마다 `sha256(splitSeed, externalId)`를 [0, 1)로 바꾼 값이 `evalRatio`보다 작으면 `eval`, 아니면 `dev`로 나눈다. | US-1 |
| R-4 | THE quality-service SHALL 영상마다 media-service `POST /internal/v1/media/dataset-videos`를 importId·externalId·요청 운영자로 부르고 받은 videoId를 항목의 sourceId로 쓴다. | US-1 |
| R-5 | THE media-service SHALL 데이터셋 영상 등록 요청을 받으면 가져오기 버킷의 파일을 media 저장소로 복사하고, (importId, externalId)로 결정적인 videoId의 영상을 보존 등급 `dataset`, 상태 `UPLOADED`로 만들며 같은 트랜잭션에서 `video.uploaded`를 Outbox에 넣는다. | US-1 |
| R-6 | IF 같은 (importId, externalId)의 영상이 이미 있으면, THEN THE media-service SHALL 복사·발행 없이 그 영상을 200으로 돌려준다. 파일이 없으면 404 `MEDIA_IMPORT_OBJECT_NOT_FOUND`, 허용 호출자가 아니면 403 `MEDIA_CALLER_NOT_ALLOWED`다. | US-1 |
| R-7 | IF 영상 하나의 등록이 실패하면, THEN THE quality-service SHALL 그 영상을 오류(처음 100건)에 남기고 나머지를 계속 처리한다. 등록된 영상이 하나도 없으면 `FAILED`, 아니면 `COMPLETED`로 끝낸다. | US-1 |
| R-8 | WHEN 영상 등록이 끝나면, THE quality-service SHALL 등록된 영상의 라벨을 분할에 맞는 `<이름>-dev`·`<이름>-eval` Golden Set(없으면 `origin: import`로 만듦)의 데이터셋 항목으로 넣고, 각 Golden Set을 새 버전으로 확정한 뒤 버전 번호를 가져오기에 기록한다. 항목이 없는 분할은 확정하지 않는다. | US-1 |
| R-9 | THE quality-service SHALL 가져오기 상태 조회에 상태, 영상·등록·실패·라벨·분할별 개수, 만든 Golden Set 버전, 오류를 담는다. | US-1 |
| R-10 | THE quality-service SHALL 데이터셋 Golden Set 확정 매니페스트에 `origin: import`, 출처·사용 조건(`datasetOrigin`), 항목별 sourceId·externalId·라벨을 담는다. 데이터셋 Golden Set에는 검토 항목을 넣지 않는다(409 `QUALITY_GOLDEN_ORIGIN_MISMATCH`). | US-1 |
| R-11 | THE evals 평가 잡 SHALL 시간 구간 라벨과 예측 이벤트를 같은 이벤트 유형끼리만 비교하고, temporal IoU(겹친 길이 / 합친 길이)가 설정 기준(기본 0.3) 이상인 쌍을 IoU가 큰 순서(같으면 라벨 시작이 이른 순)로 일대일로 짝짓는다. | US-2 |
| R-12 | THE evals 평가 잡 SHALL bbox 라벨은 같은 클래스이고 표시 시각 차가 프레임 간격의 절반 이하이며 박스 IoU가 설정 기준(기본 0.5) 이상인 검출과, 상태 변화 라벨은 같은 클래스·같은 변화 종류이고 시각 차가 설정 기준(기본 5초) 이하인 재고 변화와 R-11과 같은 순서 규칙으로 일대일로 짝짓는다. | US-2 |
| R-13 | WHEN quality-service가 `source.completed`를 받으면, THE quality-service SHALL 영상별로 가장 최근에 받은 결과 파일 경로와 jobId를 기록한다. | US-3 |
| R-14 | WHEN 운영자가 특징 내보내기를 요청하면, THE quality-service SHALL goldenSetId(최신 확정 버전의 영상)나 기간(`source.completed`를 받은 UTC 날짜, 최대 90일) 중 하나로 영상을 고르고, 결과 파일의 위험 상태마다 `quality/v1/feature-row` 한 줄을 `exports/<exportId>/features.jsonl`에 쓴다. | US-3 |
| R-15 | IF 내보내기 요청에 goldenSetId와 기간이 둘 다 있거나 둘 다 없거나 기간이 90일을 넘으면, THEN THE quality-service SHALL 400 `QUALITY_INVALID_REQUEST`를 돌려준다. | US-3 |
| R-16 | WHEN 평가 잡이 `POST /internal/v1/quality/stage-gates`를 부르면, THE quality-service SHALL 기준·후보 영상 목록의 원본 측정 기록으로 단계별 p95를 계산하고, 후보 p95 / 기준 p95 − 1이 `maxRegressionRatio`(기본 0.2)를 넘는 단계를 `failed`로 표시한다. | US-4 |
| R-17 | IF 한 단계의 기준이나 후보 기록 수가 `minSamples`(기본 5)보다 적으면, THEN THE quality-service SHALL 그 단계를 `skipped`로 표시하고 Gate 결과에서 뺀다. | US-4 |
| R-18 | THE quality-service SHALL `failed` 단계가 없으면 `passed: true`를 돌려주고, 성능 Gate 계산 결과를 저장하지 않는다. | US-4 |
| R-19 | THE evals SHALL 성능 Gate 결과가 `passed: false`이면 0이 아닌 종료 코드로 끝나는 CI용 명령을 제공한다. | US-4 |

### 비기능 요구사항

| ID | 요구사항 |
| --- | --- |
| NFR-1 | THE quality-service SHALL 영상 1,000개·라벨 100,000개인 매니페스트의 검증을 로컬에서 10초 안에 끝낸다. |
| NFR-2 | THE quality-service SHALL 영상 1,000개 가져오기 중에도 다른 API의 p95를 SPEC-029 NFR 안으로 유지한다(가져오기는 별도 작업 스레드). |
| NFR-3 | THE quality-service SHALL 영상 200개 기준·후보 성능 Gate를 로컬 p95 2초 안에 계산한다. |

## 5. 영향 범위

| 레포 / 서비스 | 변경 개요 | 담당 요구사항 |
| --- | --- | --- |
| backend / quality-service | 가져오기, Golden Set 데이터셋 항목, `source.completed` 소비, 특징 내보내기, 성능 Gate | R-1~R-4, R-7~R-10, R-13~R-18, NFR-1~NFR-3 |
| backend / media-service | 내부 데이터셋 영상 등록, 보존 등급 `dataset` | R-5, R-6 |
| ai / evals | 매칭 규칙, 성능 Gate CI 명령 | R-11, R-12, R-19 |
| docs | 계약, 서비스 카탈로그(quality 입력에 `source.completed`) | R-10, R-14 |
| docs / local | 로컬 compose에 가져오기 버킷 | R-4 |

## 6. 계약 변경

| 계약 파일 | 변경 | 하위호환 |
| --- | --- | --- |
| `service-contracts/quality/v1/dataset-import-manifest.schema.json` | 새 파일 형식(라벨 3종) | 예(추가) |
| `service-contracts/quality/v1/golden-manifest.schema.json` | 선택 필드 `origin`·`datasetItems`·`datasetOrigin`, `entries` 최소 개수 0(둘 중 하나는 1개 이상) | 예(선택 필드 추가, 제약 완화) |
| `service-contracts/quality/v1/feature-row.schema.json` | 새 파일 형식 | 예(추가) |
| `service-contracts/openapi/quality-service.yaml` | 작업 6개, `GoldenSet.origin`(응답 필드), 1.0.0 → 1.1.0 | 예(추가) |
| `service-contracts/openapi/media-service.yaml` | `POST /internal/v1/media/dataset-videos`, 1.3.1 → 1.4.0 | 예(추가) |

계약 묶음 3.9.0 → 3.10.0

## 7. 성공 지표

- 로컬 compose에서 영상 2개짜리 샘플 매니페스트를 가져오면 두 영상이 분석 흐름을 타고, 두 Golden Set 버전이 생기며, 평가 잡이 그 버전으로 매칭 규칙을 돌려 결과를 제출한다.

## 8. 미결 사항

- 해당 없음
