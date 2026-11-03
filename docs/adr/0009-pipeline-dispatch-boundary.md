---
id: ADR-0009
title: 영상 처리 책임과 계획·배정·추론 경계를 분리한다
status: Accepted
date: 2026-11-03
deciders: [사용자]
related: [ADR-0002, ADR-0008, SPEC-004, SPEC-007]
---

# ADR-0009 영상 처리 책임과 계획·배정·추론 경계를 분리한다

## 맥락

사용자가 backend는 normalize·chunk-processor를 포함한 영상 처리를, AI팀은 추론을 담당하도록 확정했다. 기존 SPEC-006 Pipeline 초안(PR #40)은 영상 재생 SPEC-006과 번호가 충돌하여 SPEC-007로 이동했다.

ADR-0008은 산업안전 v3·19개 배포 단위·모델 교체 원칙을 채택했다. 이 결정은 그 검색·이벤트 알고리즘을 대체하지 않는다. 책임 분담·시간 표현·배정 경계는 이번 결정이 우선한다. 기존 Accepted ADR 본문은 이력으로 보존한다.

## 결정 요인

- 계획 계산과 실제 영상 추출을 분리
- 공정성·동시 처리 상한의 단일 소유자 유지
- 불변 정규화 결과와 실행 시도로 중복·지연 결과를 구분
- 기존 Kafka·공통 Outbox와 AI Gateway를 근거 없이 교체하지 않음

## 검토한 선택지

### 1. 계획 생성 때 전체 청크 요청을 Outbox에 적재

- 장점: 단순한 시작 흐름이다.
- 단점: 기존 Publisher가 그대로 발행하면 배정·슬롯 제한을 우회한다.

### 2. 계획은 저장만 하고 배정 때 실행·슬롯·Outbox를 함께 커밋

- 장점: 최초 실행과 재시도에 같은 제한을 적용하고 원자성을 보장한다.
- 단점: 실행 임대·슬롯 원장과 장애 복구가 추가로 필요하다.

## 결정

선택지 2를 채택한다. 사용자 지시에 따라 normalize·chunk-processor와 Kafka·계획·배정은 backend 소관, 모델 추론은 AI팀 소관이다. 담당 변경은 언어·레포 경로·배포 단위를 자동 변경한다는 의미가 아니다.

- 이번 구현 범위는 video.normalized 수신과 수신 기록·Job·Chunk의 원자적 저장이다. chunk.requested 기록·발행은 배정기 후속 작업이다.
- 배정은 실행 시도·배정 상태·슬롯 점유·요청 Outbox를 같은 pipeline DB 트랜잭션으로 저장한다. Publisher는 발행만 하며 슬롯을 획득하지 않는다.
- 이벤트에는 객체 참조·작업 정보만 전달한다. sourceId Kafka 키와 공통 envelope·traceparent를 유지한다.
- 정규화 결과는 불변이다. eventId는 Job ID가 아니다. 같은 normalizationId와 같은 분석 설정은 Job을 재사용한다.
- 연동 시간은 정규화 영상 시작 기준 정수 밀리초, 구간은 시작 포함·끝 제외다. 기존 SPEC-004의 소수 초 저장은 아직 구현 사실로 보존하고 경계 변환·마이그레이션은 후속 설계로 구분한다.
- AI HTTP 기본안은 준비된 청크 객체 참조를 전달하고 읽기 권한을 부여하는 POST /v1/inferences다. 실제 Gateway/서버 배치와 결과 스키마를 이 ADR로 확정하지 않는다.

## 결과

- 기존 아키텍처의 chunkId Kafka 키 표기와 공통 envelope의 sourceId 키 규칙이 충돌하므로 해당 처리 경로는 sourceId로 정리한다. 청크별 실행 병렬성은 offset 연속 커밋·워커 동시 처리 설계로 해결하며 키를 몰래 바꾸지 않는다.
- Python 워커의 PostgreSQL 직접 쓰기 금지 설명은 backend 소유 normalize·chunk-processor의 실행/결과 원장 요구와 충돌한다. 후속 worker 소유 저장소를 허용하는 설계로 구분하고 pipeline DB에 직접 쓰지는 않는다.
- AI Gateway의 기존 /v1/analyze·/v1/embed·/v1/parse는 유지한다. /v1/inferences를 기존 Gateway의 호환 facade로 제공하는 안과 별도 추론 서버 adapter 안을 비교한 후 계약으로 확정한다. 새 배포 단위는 이번에 추가하지 않는다.
- SDK·영상 추출·추론 모델·계약 스키마·마이그레이션은 이번 문서 수정에서 바꾸지 않는다.

## 참고

- [아키텍처](../architecture/overview.md)
- [SPEC-007](../specs/SPEC-007-normalized-intake/spec.md)
- backend specs/SPEC-007-normalized-intake/plan.md
