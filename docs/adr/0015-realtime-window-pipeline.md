---
id: ADR-0015
title: 실시간 수집을 같은 파이프라인의 창 단위 처리로 통합하고 STREAM Job은 stream-service가 소유한다
status: Accepted
date: 2026-11-06
deciders: [사용자]
related: [ADR-0008, ADR-0009, ADR-0010, ADR-0016, SPEC-036, SPEC-037]
---

# ADR-0015 실시간 수집을 같은 파이프라인의 창 단위 처리로 통합하고 STREAM Job은 stream-service가 소유한다

## 맥락

v3·v4 구조(ADR-0008, ADR-0010)는 업로드 영상만 다루고, 실시간 카메라 스트림은 "Phase 2에 Stream·Stream Ingestor를 추가한다"로만 적혀 있었다. 실시간이 들어오면 탐지·추적·판정·상태 전이를 두 벌로 둘지, 한 벌로 둘지 정해야 한다. 두 벌이면 같은 이벤트 정의·같은 VLM 판정·같은 위험 상태 규칙이 두 코드에 갈라져 결과가 달라질 위험이 있다.

v5 초안은 실시간 Job(`STREAM`)의 창 단위 완료 판정을 pipeline-service에 맡겼다. 재검토에서 세 가지 문제가 드러났다.

- pipeline-service는 다른 담당자 서비스라 실시간 기능 전체가 그 담당자의 변경에 묶인다.
- pipeline-service의 Job 모델은 "계획 때 청크 수가 정해지는" 업로드 Job이라 끝이 없는 세션을 억지로 끼워야 한다.
- 세션이 무한히 길어지면 분석 버전·결과 파일·상태 스냅샷이 한 소스에 끝없이 쌓인다.

## 결정 요인

- 6명 팀에서 실시간 담당자는 1명이다. 다른 담당자 서비스의 변경 없이 실시간을 끝까지 만들 수 있어야 한다.
- 업로드와 실시간의 이벤트·위험 상태 결과가 같은 규칙에서 나와야 한다. 품질 평가(Golden Set)도 한 벌이어야 한다.
- 기존 워커(frame-encoder, event-analyzer, embedding-worker, aggregator)와 계약(3.15.0)을 깨지 않아야 한다.
- 카메라 100대 기준 CPU·S3 비용이 외부 AI 비용보다 크다(아키텍처 17.4절). 창 길이·fps·보존 기간이 프로필 값이어야 한다.

## 검토한 선택지

### 1. 실시간 전용 파이프라인을 따로 둔다

- 장점: 업로드 파이프라인을 건드리지 않는다. 프레임 단위 지연이 가장 짧다.
- 단점: 탐지·추적·판정·상태 전이가 두 벌이 된다. 이벤트 유형을 하나 추가할 때 두 곳을 고치고 두 번 평가해야 한다.

### 2. 창(20초)을 청크로 보고 같은 파이프라인을 쓰되, STREAM Job을 pipeline-service가 소유한다 (v5 초안)

- 장점: 워커 한 벌. 완료 판정 코드를 pipeline-service에서 재사용한다.
- 단점: 실시간이 다른 담당자 서비스의 변경에 묶인다. 업로드 Job 모델과 끝없는 세션이 맞지 않는다. `job.status`·`COMPLETED_WITH_ERRORS` 같은 업로드 전용 상태가 실시간에 섞인다.

### 3. 창을 청크로 보고 같은 파이프라인을 쓰되, STREAM Job을 stream-service가 소유한다

- 장점: 워커 한 벌을 유지하면서 실시간의 Job·창 완료·라이브 읽기 모델이 실시간 담당자 서비스 안에 있다. pipeline-service는 `jobType: STREAM` 메시지를 무시하기만 하면 된다. 세션을 24시간마다 회전해 소스 크기를 묶는다.
- 단점: 완료 판정 코드가 pipeline-service와 stream-service에 각각 있다(규칙은 같고 대상이 다르다). stream-service가 Kafka 소비자가 된다.

## 결정

**선택지 3**을 택한다. 이유:

- stream-ingestor는 chunk-processor와 같은 다섯 토픽(`segment.ready`·`event.candidate`·`track.detected`·`chunk.boundary`·`chunk.manifest`)을 같은 필드로 내고 선택 필드 `jobType: STREAM`만 더한다. frame-encoder부터 analysis-api까지는 입력이 청크인지 창인지 모른다.
- 식별자는 업로드와 같은 계층(`sourceId → normalizationId → jobId → chunkId → executionId`)을 쓴다. 카메라 세션 1개가 소스 1개, 창이 청크, `normalizationId`는 세션 ID를 재사용한다.
- stream-service가 카메라·구역·세션·`STREAM` Job·창 완료 판정·라이브 읽기 모델을 소유한다. 창의 적재 신호(`segment.indexed`·`event.manifest`)가 모이면 `analysis.completed(scope: chunk)`를 내고, stop 또는 24시간 회전 때 `scope: job`을 낸다. 세션 시작에 `version.activated`를 1건 낸다.
- 세션 시작은 Kafka `stream.command`, stop·프로필 재적용·활성 위험 구역은 Redis 세션 키로 전달한다. Ingestor는 창마다 그 키를 읽는다.
- 긴급 후보(severity high 유형, 활성 위험 구역 진입)는 `alert.candidate`로 창 종료를 기다리지 않고 나간다. 알림만 만들고 이벤트는 같은 candidateId의 창 후보가 캐시 적중으로 저장한다(ADR-0016).
- 세션은 24시간마다 새 소스로 회전하고 `previousSourceId`로 상태를 잇는다. 작업 세션과 같은 장치다.
- track-stitcher는 `jobType: STREAM`이면 건너뛴다. Ingestor가 세션 전체에서 같은 트랙 ID를 유지하고 재시작은 `trackIdEpoch`로 구분한다.

## 결과

- 좋아지는 점: 이벤트 정의·판정·상태 전이·품질 평가가 한 벌이다. 실시간 기능이 다른 담당자 서비스의 변경 없이 동작한다(pipeline-service의 "STREAM 무시"가 없으면 DLQ가 쌓일 뿐 기능은 동작한다). 소스 크기가 24시간으로 묶인다.
- 감수할 점: 완료 판정 규칙이 두 서비스에 있다. 창 20초만큼 판정 지연이 있다(긴급 경로가 보완한다). 카메라당 CPU 0.4~0.8 vCPU와 S3 PUT 비용이 든다.
- 후속 작업: SPEC-036(stream-service), SPEC-037(stream-ingestor), 계약 묶음 4.0.0(`stream.command`·`alert.candidate`·`alert.raised`·`state.updated`, 산출물 토픽의 `jobType`), 서비스 카탈로그 21개 갱신.

## 참고

- [아키텍처 v5.1](../architecture/architecture.md) 1, 4, 6, 12, 17.4절
- [ADR-0016](0016-aggregator-fold-and-deterministic-caps.md)
