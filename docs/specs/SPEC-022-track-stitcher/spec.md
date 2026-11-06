---
id: SPEC-022
title: track-stitcher 경계 트랙 연결과 재등장 연결(Re-ID)
status: Approved
owner: <이름>
repos: [ai, docs]
created: 2026-11-06
updated: 2026-11-06
related: [ADR-0008, ADR-0009, ADR-0010, SPEC-013, SPEC-019]
---

# SPEC-022 track-stitcher 경계 트랙 연결과 재등장 연결(Re-ID)

> 이 문서에는 **무엇을, 왜**만 쓴다. 클래스, 테이블, 라이브러리 같은 구현 방법은 각 레포의 plan.md에 쓴다.

## 1. 배경과 목적

chunk-processor는 영상을 청크(기본 2분, 앞뒤 5초 겹침)로 나눠 따로 추적한다. 그래서 한 사람이 청크 경계를 지나면 트랙이 둘로 끊기고, 화면을 떠났다 돌아온 사람도 새 트랙이 된다. 트랙이 끊기면 세 가지가 틀어진다.

- 클릭 조회의 "이 사람의 다른 장면"
- 트랙 속성(보호구·역할)
- aggregator의 시간 기준 규칙(체류·배회·장비 방치)

track-stitcher는 두 단계로 트랙을 잇는다([아키텍처 v5](../../architecture/architecture.md) 분석 처리 흐름 7단계).

- 경계 연결: 인접 청크의 겹치는 5초에서 같은 클래스 트랙을 박스 IoU로 잇는다. 크롭 벡터를 기다리지 않아 빨리 끝난다.
- 재등장 연결(Re-ID): 영상의 모든 청크가 모이고 크롭 벡터(frame-encoder, [SPEC-019](../SPEC-019-frame-encoder/spec.md))도 모이면, 같은 클래스 트랙을 외형 유사도와 시간 간격으로 잇는다.

결과는 로컬 트랙 → 최종 트랙 번역표 하나다. 이를 `track.manifest`로 알리면 pipeline-service가 완료 판정에 세고, analysis-api가 최종 trackId를 정한다.

입력 `chunk.boundary`·`track.detected`(origin chunk)는 chunk-processor(다른 담당자)가 만든다. 아직 계약이 없어 이 spec이 아키텍처 문서대로 소비 쪽에서 계약을 정한다(2026-11-06 사용자 결정, [handoff](../../handoff.md) 2.1). 생산자가 바꾸면 소비 쪽을 맞춘다.

## 2. 범위

### 포함

- 계약: `chunk.boundary`, `track.detected`(origin `chunk`·`stitcher`), `track.manifest`, 파일 `tracks/v1/chunk-tracks`·`track-mapping`, AsyncAPI, 단계 ID
- `chunk.boundary` 소비: 청크 트랙 요약을 Job별로 모으고, 영상 전체를 덮었는지 판단한다.
- `segment.embedded` 소비: 실행별 크롭 벡터 파일 경로를 모은다.
- 경계 연결: 인접 청크 한 쌍이 모이면 바로 잇고 `track.detected`(origin `stitcher`)를 발행한다.
- Re-ID: Job의 모든 청크와 크롭 벡터가 모이면 실행한다.
- 번역표 저장과 `track.manifest` 발행(Job마다 한 번)
- 대기 제한 시간: 오지 않는 청크가 있어도 받은 것만으로 끝낸다.
- 여러 Pod: 상태는 Redis에 두고, 확정은 한 Pod만 한다.
- `video.deleted`: 그 영상의 대기 상태를 지운다.
- 처리 단계 측정 `stitcher.boundary`·`stitcher.reid`·`stitcher.finalize`
- 로컬 compose에 track-stitcher와 토픽 추가

### 제외

- chunk-processor의 `chunk.boundary`·`track.detected`·트랙 요약 파일 생성: 생산자(다른 담당자) 몫이다. 이 spec은 계약만 정한다.
- 번역표를 읽어 trackId를 바꾸는 저장(analysis-api), 검출 박스 적재(analysis-loader), 완료 판정(pipeline-service): 다른 담당자 몫이다.
- 잘못된 Re-ID 연결을 운영자가 분리하는 기능: analysis-api 화면·API 몫이다. 이 spec은 근거(`links`)만 남긴다.
- 연결 기준값(IoU 경계, 유사도 경계, 최대 간격)의 실제 값: AI 담당자가 평가로 정한다. 이 spec은 프로필 자리와 로컬 동작 확인용 기본값만 둔다.
- 영상을 넘는 연결(작업 세션의 전후 영상 사이 같은 사람): 이후 spec

## 3. 사용자 시나리오

### US-1 청크 경계에서 끊기지 않는 트랙 (P1)

안전관리자로서 한 작업자가 2분 경계를 지나도 같은 트랙으로 보이기를 원한다. 왜냐하면 트랙이 끊기면 같은 사람의 행동이 두 사람 것으로 나뉘어 체류 시간·보호구 판단이 틀리기 때문이다.

#### 인수 조건

- Given 청크 A의 뒤쪽 겹침 구간과 청크 B의 앞쪽 겹침 구간에서 같은 클래스 트랙의 박스가 겹침, When 두 청크의 `chunk.boundary`를 받으면, Then 두 로컬 트랙을 잇는 `track.detected`(origin `stitcher`)가 발행된다.
- Given 겹침 구간에서 클래스가 다른 두 트랙, When 처리하면, Then 잇지 않는다.
- Given B를 A보다 먼저 받음, When A를 받으면, Then 같은 결과가 나온다.

### US-2 화면을 떠났다 돌아온 사람 (P2)

안전관리자로서 화면 밖으로 나갔다 30초 뒤 돌아온 작업자가 같은 트랙으로 이어지기를 원한다. 왜냐하면 위험구역 출입 횟수와 체류 시간을 사람 단위로 봐야 하기 때문이다.

#### 인수 조건

- Given 같은 클래스 두 트랙이 시간상 겹치지 않고 간격이 프로필 최대 간격 안이며 크롭 외형 유사도가 경계값 이상, When Job의 모든 청크와 크롭 벡터가 모이면, Then 번역표에서 두 트랙이 같은 최종 trackId가 되고 연결 근거(유사도·간격)가 남는다.
- Given 유사도가 경계값 미만, When 처리하면, Then 따로 남는다.

### US-3 완료 판정과 번역표 (P1)

pipeline-service와 analysis-api 담당자로서 Job마다 트랙 연결이 끝났다는 신호와 번역표를 한 번 받고 싶다. 왜냐하면 완료 판정은 적재 신호를 세고, 저장은 최종 trackId로 해야 하기 때문이다.

#### 인수 조건

- Given 소유 범위가 영상 전체를 덮는 청크들과 그 크롭 벡터, When 모두 받으면, Then `complete: true`인 `track.manifest`가 한 번 발행되고 번역표에 모든 로컬 트랙이 정확히 한 번 나온다.
- Given 같은 입력을 다시 받음, When 처리하면, Then 같은 eventId·같은 최종 trackId가 나온다.

### US-4 오지 않는 청크와 잘못된 입력 (P2)

운영자로서 청크 하나가 실패해도 그 영상의 트랙 결과가 영영 나오지 않는 일이 없기를 원한다.

#### 인수 조건

- Given 한 청크의 `chunk.boundary`가 오지 않고 대기 제한 시간이 지남, When 주기 확인이 돌면, Then 받은 청크만으로 `complete: false`와 빠진 범위를 담은 `track.manifest`가 발행된다.
- Given 계약에 맞지 않는 메시지나 읽을 수 없는 트랙 요약 파일, When 받으면, Then 그 메시지는 DLQ로 가고 다른 Job은 계속 처리된다.

## 4. 요구사항

### 기능 요구사항 (EARS)

| ID | 요구사항 | 시나리오 |
| --- | --- | --- |
| R-1 | WHEN track-stitcher가 `chunk.boundary`를 받으면, THE track-stitcher SHALL 그 메시지의 트랙 요약 파일(`tracksKey`)을 읽어 Job(jobId)의 청크 목록에 소유 범위·처리 범위·실행 ID와 함께 기록한다. | US-1, US-3 |
| R-2 | IF 같은 Job·같은 청크(chunkId)의 `chunk.boundary`를 이미 기록했으면, THEN THE track-stitcher SHALL 먼저 기록한 실행을 유지하고 새 메시지는 기록하지 않는다(실행 ID가 같으면 중복, 다르면 경고 로그). | US-3 |
| R-3 | THE track-stitcher SHALL 앞 청크의 `ownedRange.endMs`가 뒤 청크의 `ownedRange.startMs`와 같은 두 청크를 인접 청크로 본다. | US-1 |
| R-4 | WHEN 인접 청크 한 쌍이 모두 기록되면, THE track-stitcher SHALL 앞 청크의 `touchesTail` 트랙과 뒤 청크의 `touchesHead` 트랙 중 클래스가 같은 쌍마다 겹침 구간 박스의 평균 IoU를 구하고, 평균 IoU가 프로필 경계값 이상이고 공통 관측이 프로필 최소 수 이상인 쌍을 IoU가 높은 순서로 일대일로 잇는다. | US-1 |
| R-5 | WHEN 인접 청크 한 쌍의 연결을 마치면, THE track-stitcher SHALL 그 쌍마다 `track.detected`(origin `stitcher`)를 한 번 발행한다. 이어진 트랙이 없으면 빈 `stitched`로 발행한다. eventId는 jobId와 두 chunkId로 결정적으로 만든다. | US-1 |
| R-6 | THE track-stitcher SHALL 박스의 공통 관측을 두 청크 박스의 시각 차가 프로필 허용 오차 안인 짝으로 정한다. | US-1 |
| R-7 | WHEN track-stitcher가 `segment.embedded`를 받으면, THE track-stitcher SHALL 그 실행의 벡터 파일 경로(`vectorsKey`)와 인코더 모델 ID를 Job에 기록한다. `chunk.boundary`보다 먼저 와도 기록한다. | US-2 |
| R-8 | WHEN Job의 소유 범위가 `[0, sourceDurationMs)`를 빈틈없이 덮고 기록한 모든 청크 실행의 `segment.embedded`가 모이면, THE track-stitcher SHALL 그 Job의 Re-ID를 한 번 실행한다. | US-2, US-3 |
| R-9 | THE track-stitcher SHALL Re-ID 후보를 경계 연결 뒤 트랙 중 클래스가 같고 시간이 겹치지 않으며 앞 트랙의 끝과 뒤 트랙의 시작 간격이 프로필 최대 간격 이하인 쌍으로 정하고, 두 트랙 크롭 벡터 평균의 코사인 유사도가 프로필 경계값 이상인 쌍을 유사도가 높은 순서로 이어, 한 트랙이 앞·뒤로 각각 최대 하나와만 이어지게 한다. | US-2 |
| R-10 | IF 트랙에 크롭 벡터가 없으면, THEN THE track-stitcher SHALL 그 트랙을 Re-ID 후보에서 빼고 경계 연결 결과만 쓴다. | US-2 |
| R-11 | IF Job 안 벡터 파일의 인코더 모델 ID가 둘 이상이면, THEN THE track-stitcher SHALL Re-ID를 하지 않고 `reidSkippedReason`을 `embedding_model_mismatch`로 기록한다. | US-2 |
| R-12 | WHEN Job의 연결을 마치면, THE track-stitcher SHALL 번역표(`tracks/v1/track-mapping`)를 `sources/<sourceId>/jobs/<jobId>/tracks/mapping.json`에 저장한 뒤 `track.manifest`를 한 번 발행한다. eventId는 jobId로 결정적으로 만든다. | US-3 |
| R-13 | THE track-stitcher SHALL 번역표에 받은 모든 로컬 트랙을 정확히 한 번 넣고, 연결마다 종류(`boundary`·`reid`)·점수·(Re-ID면) 간격을 남긴다. | US-2, US-3 |
| R-14 | THE track-stitcher SHALL 최종 trackId를 jobId와 그 트랙의 가장 이른 구성원(시작 시각, 같으면 chunkId·trackLocalId 순)으로 결정적으로 만든다. | US-3 |
| R-15 | IF Job의 마지막 입력 뒤 프로필 대기 제한 시간(기본 30분)이 지나도 R-8 조건이 채워지지 않으면, THEN THE track-stitcher SHALL 받은 청크만으로 경계 연결과 (벡터가 있는 트랙의) Re-ID를 마치고 `complete`를 소유 범위가 다 덮였는지로, `missingRanges`를 덮이지 않은 범위로 담아 R-12대로 발행한다. | US-4 |
| R-16 | THE track-stitcher SHALL R-15의 대기 제한 시간 확인과 Job 확정을 여러 Pod 중 한 Pod만 하게 해, Job마다 `track.manifest`가 한 번만 발행되게 한다. | US-3, US-4 |
| R-17 | IF Job의 `track.manifest`를 발행한 뒤 그 Job의 `chunk.boundary`·`segment.embedded`를 받으면, THEN THE track-stitcher SHALL 다시 발행하지 않고 경고 로그를 남긴다. | US-3 |
| R-18 | IF 메시지가 계약 스키마에 맞지 않거나 트랙 요약 파일이 없거나 계약에 맞지 않으면, THEN THE track-stitcher SHALL 그 메시지를 기록하지 않고 재시도 없이 DLQ로 보낸다. | US-4 |
| R-19 | WHEN track-stitcher가 `video.deleted`를 받으면, THE track-stitcher SHALL 그 영상의 모든 Job 대기 상태를 지우고, 그 뒤 그 영상의 입력은 기록하지 않는다. | US-4 |
| R-20 | IF 저장소·Redis·Kafka가 일시적으로 응답하지 않으면, THEN THE track-stitcher SHALL 메시지를 재시도 토픽으로 보내 다시 처리한다. | US-4 |
| R-21 | THE track-stitcher SHALL 핸들러 안의 처리 시간을 단계 `stitcher.boundary`(비교한 트랙 쌍 수), `stitcher.reid`(비교한 트랙 수), `stitcher.finalize`(최종 트랙 수)로 남긴다(SPEC-013). | US-3 |
| R-22 | IF 프로필이 없거나 기준값이 범위 밖(IoU·유사도 경계 0~1 밖, 간격·제한 시간 0 이하)이면, THEN THE track-stitcher SHALL 기동에 실패한다. | US-4 |

### 비기능 요구사항

| ID | 요구사항 |
| --- | --- |
| NFR-1 | THE track-stitcher SHALL 1시간 영상(청크 30개, 로컬 트랙 3,000개, 크롭 벡터 9,000개)의 Re-ID와 확정을 한 Pod에서 30초 안에 마친다. |
| NFR-2 | THE track-stitcher SHALL 여러 Pod가 같은 Job의 메시지를 나눠 받아도 단일 Pod와 같은 번역표를 만든다. |
| NFR-3 | THE track-stitcher SHALL Job 대기 상태를 마지막 입력 뒤 7일이 지나면 Redis에서 지운다. |
| NFR-4 | THE track-stitcher SHALL 트랙 요약·번역표·벡터 내용(좌표·벡터)을 로그에 남기지 않는다. |

## 5. 영향 범위

| 레포 / 서비스 | 변경 개요 | 담당 요구사항 |
| --- | --- | --- |
| ai / track-stitcher | 새 워커: 소비·기록, 경계 연결, Re-ID, 확정, 대기 제한 시간, 삭제, 단계 측정 | R-1~R-22, NFR-1~NFR-4 |
| ai / libs | 계약 모델(`ChunkBoundary`, `TrackDetected`, `TrackManifest`, 트랙 파일 2종), 단계 ID | R-1, R-5, R-12, R-21 |
| docs | 계약, overview 토픽 표, 서비스 카탈로그 | R-1, R-5, R-12 |
| docs / local | 로컬 compose에 track-stitcher, 토픽 `chunk.boundary`·`track.detected`·`track.manifest`와 재시도·DLQ | R-20 |
| ai / chunk-processor (다른 담당자) | (이후) `chunk.boundary`·`track.detected`·트랙 요약 파일 생성 | — |
| backend / analysis-api, analysis-loader, pipeline-service (다른 담당자) | (이후) `track.detected`·`track.manifest` 소비 | — |

## 6. 계약 변경

| 계약 파일 | 변경 | 하위호환 |
| --- | --- | --- |
| `service-contracts/events/chunk.boundary.schema.json` | 새 이벤트(생산자 확인 필요) | 예(추가) |
| `service-contracts/events/track.detected.schema.json` | 새 이벤트. origin `chunk`(생산자 확인 필요)·`stitcher` | 예(추가) |
| `service-contracts/events/track.manifest.schema.json` | 새 이벤트 | 예(추가) |
| `service-contracts/tracks/v1/chunk-tracks.schema.json` | 새 파일 형식: 실행의 로컬 트랙 요약과 경계 박스 | 예(추가) |
| `service-contracts/tracks/v1/track-mapping.schema.json` | 새 파일 형식: Job의 번역표와 연결 근거 | 예(추가) |
| `service-contracts/asyncapi/track-stitcher.yaml` | 새 파일 | 예(추가) |
| `service-contracts/asyncapi/chunk-processor.yaml` | `chunk.boundary`·`track.detected` 발행 채널(1.2.0) | 예(추가) |
| `service-contracts/stages/v1/stages.schema.json` | `track-stitcher.queue_wait`·`track-stitcher.handle`·`stitcher.boundary`·`stitcher.reid`·`stitcher.finalize` | 예(추가) |

계약 묶음 3.1.0 → 3.2.0

## 7. 성공 지표

- 로컬 compose에서 테스트용 `chunk.boundary` 5건(영상 전체)과 `segment.embedded` 5건을 넣으면 경계 쌍마다 `track.detected` 4건과 `track.manifest` 1건이 나오고, 모두 계약 스키마를 통과한다.
- 같은 메시지를 순서를 섞어 다시 넣어도 번역표가 같다.

## 8. 미결 사항

- 해당 없음. 기준값은 프로필 자리만 정했다(AI 담당자 몫).
