---
id: ADR-0002
title: 서비스 간 비동기 통신에 Kafka를 쓴다
status: Accepted
date: 2026-11-02
deciders: [팀]
related: [ADR-0001]
---

# ADR-0002 서비스 간 비동기 통신에 Kafka를 쓴다

## 맥락

영상 분석은 업로드 → 정규화 → 청크 처리 → 구간·트랙·이벤트 분석 → 요약 → 검색 색인 순서로 여러 서비스를 거친다. Spring 서비스와 Python 워커가 상태 변경을 이벤트로만 주고받는다. 서비스끼리 REST로 쓰기 요청을 하지 않는다. 이 흐름에는 다음이 필요하다.

- 토픽 약 20개. 한 토픽을 여러 서비스가 각자 소비한다(예: `segment.analyzed`를 Analysis, Embedding, Pipeline이 구독).
- 일부 흐름의 순서 보장. 경계 트랙 연결과 엔티티 상태는 `sourceId` 단위로 묶고, 세그먼트와 트랙은 각자의 ID로 흩어 병렬 처리한다.
- 소비 그룹별 retry 토픽과 DLQ, 운영자 재처리
- 비동기 동시 처리에서 연속 완료된 위치까지만 커밋
- 전 토픽을 장기 보관해 분석과 복제 데이터 재구축에 쓰기

## 결정 요인

- 6명 팀, 최종 프로젝트 기간 안에 로컬과 dev(EKS)에서 같은 구조로 동작해야 한다.
- Spring(spring-kafka)과 Python 양쪽에 성숙한 클라이언트가 있어야 한다.
- 로컬 개발 머신(Docker 합계 약 11~12GB)에서 단일 노드로 띄울 수 있어야 한다.
- 재처리와 이벤트 이력 보관이 설계의 일부다(재분석, 분석 데이터 아카이브).

## 검토한 선택지

### 1. Kafka

- 장점: 파티션 키로 순서를 보장하면서 다른 키는 병렬 처리한다. 소비 그룹마다 독립적으로 같은 토픽을 읽는다. offset으로 재생(replay)할 수 있다. Kafka Connect S3 Sink로 전 토픽을 아카이브할 수 있다. 로컬은 KRaft 단일 노드로 ZooKeeper 없이 띄운다.
- 단점: 운영 개념(파티션, 소비 그룹, 리밸런싱)의 학습 비용이 있다. 지연 재시도는 기본 기능이 아니어서 retry 토픽을 직접 설계해야 한다. 운영 환경 비용이 다른 선택지보다 크다.

### 2. RabbitMQ

- 장점: 작업 큐와 지연 재시도(TTL + dead letter exchange)가 쉽다. 단일 노드 운영이 가볍다.
- 단점: 소비하면 메시지가 사라지므로 재생과 장기 보관을 따로 만들어야 한다. 키 단위 순서 보장과 병렬 처리를 함께 얻기 어렵다. 여러 서비스가 같은 이벤트를 읽으려면 exchange와 큐를 서비스마다 구성해야 한다.

### 3. Amazon SNS + SQS

- 장점: 완전 관리형이라 운영 부담이 가장 적다. 사용한 만큼만 과금된다.
- 단점: 로컬은 LocalStack 같은 에뮬레이터가 필요해 운영과 동작이 달라질 수 있다. 순서 보장은 FIFO 큐에 한정되고 처리량 제한이 있다. 재생이 없어 아카이브를 따로 만들어야 한다.

## 결정

**Kafka**를 택한다. 이유: 파티션 키 순서 보장, 소비 그룹별 독립 소비, 재생, S3 Sink 아카이브가 모두 이 설계의 전제다. 다른 선택지는 이 기능들을 직접 만들어야 해서 단순성 원칙(V)에서 오히려 불리하다.

## 결과

- 좋아지는 점: 워커를 늘려도 파티션 단위로 처리량이 늘어난다. 재분석과 복제 데이터 재구축에 이벤트 이력을 다시 쓸 수 있다.
- 감수할 점: retry 토픽, DLQ, 멱등 소비(eventId)를 공통 라이브러리(backend `libs/common-messaging`, ai `libs/messaging`)로 직접 구현해야 한다. 토픽과 파티션 수를 계약처럼 관리해야 한다.
- 후속 작업:
  - 운영(EKS) Kafka 제공 방식(Amazon MSK 또는 Strimzi)을 비용 확인 후 별도 ADR로 결정
  - 로컬 `local/` docker-compose에 KRaft 단일 노드 추가
  - 이벤트 payload JSON Schema(`docs/contracts/events/`)와 AsyncAPI 계약 작성
  - 토픽 이름, 키, 파티션 수, 보존 기간 규칙을 `docs/contracts/README.md`에 정리

## 참고

- [아키텍처 v5](../architecture/architecture.md)
- [서비스 카탈로그](../architecture/service-catalog.md)
