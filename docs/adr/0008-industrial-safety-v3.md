---
id: ADR-0008
title: 산업안전 v3 구조(19개 배포 단위)를 채택하고 모델·플랫폼을 설정으로 교체할 수 있게 한다
status: Accepted
date: 2026-11-03
deciders: [팀]
related: [ADR-0001, ADR-0002, ADR-0005, ADR-0006]
---

# ADR-0008 산업안전 v3 구조(19개 배포 단위)를 채택하고 모델·플랫폼을 설정으로 교체할 수 있게 한다

## 맥락

[ADR-0005](0005-search-and-event-paths.md)는 일반 CCTV를 대상으로 검색 경로와 이벤트 경로를 나누고 17개 배포 단위를 정했다. 이후 팀은 대상 도메인을 산업안전 CCTV로 좁히고, 연구용 프로토타입 `vlm_project`의 인코더·탐지기 선택, 판정 규칙, 정직성 원칙을 MSA 구조에 옮긴 설계(v3)를 만들었다. 설계 원본은 루트 `references/검색·이벤트 VLM 아키텍처_v2.md`다(파일 이름은 v2지만 내용은 v3).

v3가 ADR-0005와 다른 점은 다음과 같다.

- 도메인: 산업안전 이벤트 6종(쓰러짐, 화재·연기, 보호구 미착용, 물건 제거, 방호 미복구, 위험구역 접근)과 위험 상태(활성·해소), 상태 스냅샷을 다룬다.
- 배포 단위: Quality(Spring)와 Grounding Worker(Python)를 더해 19개다.
- 검색 단위: 1fps 키프레임 대신 10초 창·5초 간격 구간마다 프레임 4장의 평균 벡터 하나를 쓴다. 토픽이 `keyframe.ready`·`frame.*`에서 `segment.*`로 바뀐다.
- 기본 모델: 이미지·질의 인코더가 SigLIP 2에서 MobileCLIP2-S0로 바뀌고, 탐지기는 YOLO26n·YOLO-pose·YOLOE(텍스트 클래스)를 MVP부터 쓴다. 질의 해석은 규칙 사전이 먼저다.

설계를 검토하면서 확인한 사실은 다음과 같다.

- OpenAI API에 `gpt-6-luna`, `gpt-6.1-terra`, `gpt-6.1-sol`이 있다(2026-11-03 확인).
- Ultralytics YOLO 계열(YOLO26, YOLOE)은 AGPL-3.0이고 상용 배포에는 Enterprise License가 필요하다. MobileCLIP2 가중치는 Apple AMLR 라이선스로, 연구 목적 중심의 제한된 라이선스다.
- 원본 설계에는 계약과 맞지 않거나 빠진 부분이 있다: 라우팅 경로에 `/api/v1`이 없고, Re-ID가 아직 만들어지지 않았을 수 있는 크롭 벡터에 기대며, 로컬 텍스트 임베딩 모델의 차원이 운영(1536)과 달라 Search 적재가 실패하고, Event Analyzer가 Quality 검토 큐에 넣는 통로가 없다.

## 결정 요인

- 6명 팀이 최종 프로젝트 기간 안에 산업안전 시나리오(검색, 이벤트 판정, 위험 상태, 클릭 조회)를 시연해야 한다.
- GPU 노드를 쓸 수 없다. 자체 서빙 모델은 CPU에서 돌아야 하고 VLM은 외부 API에 기댄다.
- 기본 모델의 라이선스(AGPL-3.0, AMLR)는 비상용 시연에는 문제가 없지만, 상용화나 정책 변경 때 다른 모델로 바꿀 수 있어야 한다.
- VLM·임베딩 모델은 세대 교체가 잦다. 모델을 바꿀 때마다 코드와 DB 스키마를 고치면 재분석 비용과 위험이 커진다.
- 로컬(Ollama, SeaweedFS)과 운영(OpenAI, S3)이 같은 코드로 돌아야 한다([ADR-0006](0006-local-s3-seaweedfs.md)).
- Chunk Processor는 다른 작업자가 맡고, Track Stitcher를 포함한 나머지 Python 서비스는 ai 레포 담당자가 맡는다. 두 사람 사이의 경계는 이벤트 계약이다.

## 검토한 선택지

### 1. ADR-0005(v2) 유지

- 장점: 이미 문서와 폴더 구조가 있다. 추가 서비스가 없다.
- 단점: 산업안전 이벤트를 정의하지 않아 시연 시나리오가 없다. 위험 상태가 없다. 키프레임 단위 검색은 장면 병합 단계가 필요하다.

### 2. v3를 원본 그대로 채택 (모델을 코드에 고정)

- 장점: 원본과 1:1이라 해석 차이가 없다. 구현이 가장 빠르다.
- 단점: 모델 ID·차원·체크포인트가 코드와 스키마에 박혀, 라이선스나 모델 교체 때 여러 서비스와 Search 마이그레이션을 함께 고쳐야 한다. 로컬 임베딩 차원 문제가 남는다.

### 3. v3를 채택하고, 모델·플랫폼은 인터페이스 뒤에 두어 설정으로 교체

- 장점: 모델 교체가 "프로필 변경 → 재처리 → 활성 버전 전환"으로 끝나고 코드·스키마 변경이 없다. 라이선스 위험을 프로필 교체로 피할 수 있다. 로컬과 운영이 다른 모델(차원)을 써도 같은 스키마로 돈다.
- 단점: 인터페이스와 프로필 검증 코드가 늘어난다. 모델별 벡터 인덱스를 관리해야 한다.

## 결정

**선택지 3**을 택한다. 이유: v3로 시연 시나리오를 확보하면서, 자주 바뀌고 라이선스 제약이 있는 모델과 환경마다 다른 플랫폼을 설정으로 갈아 끼울 수 있게 해 교체 비용을 재처리 비용만으로 줄인다.

### 구조 (v3)

- 배포 단위 19개: Spring 9개(api-gateway, auth, media, pipeline, analysis-api, analysis-loader, search, notification, quality), Python 10개(ai-gateway, normalize, chunk-processor, track-stitcher, frame-encoder, grounding-worker, event-analyzer, track-analyzer, embedding-worker, aggregator).
- 이벤트 정의 목록 v1(산업안전 6종 + `other`)과 탐지기 능력 선언(`supported_events`, `unsupported_events`), `VLMAnalysis` 출력 스키마, 위험 상태와 상태 스냅샷은 원본 설계를 따른다.
- 검색 단위는 구간(segment)이고, 토픽은 `segment.ready`·`segment.embedded`·`segment.indexed`·`segment.annotated`로 바꾼다. Grounding Worker를 위해 `grounding.requested`·`grounding.completed`를 더한다.
- 상세 흐름과 규칙은 [아키텍처 v5](../architecture/architecture.md), 서비스 목록은 [서비스 카탈로그](../architecture/service-catalog.md)에 둔다.

### 모델 교체 원칙

| 대상 | 인터페이스 | 기본값(2026-11) | 교체 방법 |
| --- | --- | --- | --- |
| VLM | ai-gateway Adapter(`openai`, `openai_compatible`, `mock`) | `gpt-6.1-terra`(판정·재순위화), `gpt-6.1-sol`(상향), `gpt-6-luna`(속성·질의·RAG·요약) | taskType별 모델을 프로필에서 바꿈. 다른 공급자는 Adapter 추가 |
| 텍스트 임베딩 | ai-gateway Adapter | `text-embedding-3-small` | 프로필의 모델 이름과 차원 |
| 이미지·질의 인코더 | `ImageTextEncoder`(이미지·텍스트 벡터, 차원 조회) | `open_clip:MobileCLIP2-S0:dfndr2b`(512차원) | 모델 ID 문자열만 바꿈. 같은 ID를 frame-encoder와 ai-gateway가 함께 읽음 |
| 탐지기 | `Detector`(검출, 클래스, 능력 선언) | YOLO26n, YOLO-pose, YOLOE 텍스트 클래스 | 탐지 프로필의 가중치 경로·클래스·`supported_events` |
| VLM 서빙 | `openai_compatible` Adapter | 로컬 Ollama(Qwen3-VL) | 주소와 모델 이름만 바꾸면 vLLM·호스팅 서빙도 같음 |

- 모델 ID, 차원, 체크포인트, 프롬프트 버전, 기준값은 코드 상수가 아니라 Git으로 관리하는 프로필 값이다. 결과마다 쓴 모델과 버전을 기록한다(`embedding_model`, `model_id`, `prompt_version`, `detector_profile`).
- 기동할 때 프로필을 검증한다. 모델을 못 불러오거나 차원이 프로필과 다르면 기동에 실패하고, Mock으로 넘어가지 않는다. `mock`은 CI·단위 테스트 전용이고 운영 프로필에서 고를 수 없다.
- 교체 절차: 새 프로필 → evals(Golden Set) 비교 → Shadow → `REANALYZE`·`REEMBED`로 새 분석 버전 생성 → 활성 버전 전환. 코드와 스키마는 바꾸지 않는다.
- 벡터 스키마는 차원을 고정하지 않는다. 벡터 행마다 `embedding_model`을 두고, 모델마다 그 차원으로 캐스팅한 부분 HNSW 인덱스(`WHERE embedding_model = …`)를 만든다. 모델 추가는 인덱스 추가이고, 검색은 활성 모델의 벡터만 본다. 그래서 로컬(Ollama 임베딩)과 운영(OpenAI 1536차원)이 같은 스키마를 쓴다.

### 플랫폼 교체 원칙

| 대상 | 인터페이스 | 로컬 | 운영 |
| --- | --- | --- | --- |
| 객체 저장소 | S3 API(주소·path-style 설정) | SeaweedFS | S3 |
| 메시징 | ai `libs/messaging`, backend `libs/common-messaging` | Kafka(KRaft 단일) | Kafka |
| 모델 가중치 | 저장소 경로(`models/<모델>/<버전>/`), 기동 시 내려받기 | SeaweedFS | S3 모델 버킷 |
| 외부 AI | ai-gateway Adapter | Ollama · Mock(CI) | OpenAI |

서비스 코드는 공급자 SDK를 직접 부르지 않고 위 인터페이스만 쓴다. 공급자 SDK는 인터페이스 구현 한 곳에만 둔다.

### 라이선스

기본 탐지기(Ultralytics, AGPL-3.0)와 기본 인코더(MobileCLIP2, Apple AMLR)는 비상용 시연·학습 목적으로만 쓴다. 상용 배포가 필요해지면 Enterprise License를 받거나, 위 원칙대로 다른 모델(예: Apache-2.0 인코더)로 프로필을 바꾸고 evals로 확인한다. 모델 가중치와 Ultralytics 코드는 이미지에 넣지 않고 기동 시 내려받는다.

### 원본 설계에서 고쳐 반영하는 점

| 항목 | 원본 | 반영 |
| --- | --- | --- |
| API 경로 | `/api/media/...` 등 버전 없음 | 계약 규칙대로 `/api/v1/<서비스>/...`. 구현된 media 계약을 기준으로 함 |
| Re-ID 순서 | Stitcher가 `chunk.boundary`를 받으면 Frame Encoder가 만든 크롭 벡터를 읽음(아직 없을 수 있음) | 경계 연결은 겹치는 5초의 IoU와 클래스만으로 한다. 재등장 연결(Re-ID)은 Stitcher가 `segment.embedded`도 받아 영상의 모든 청크 크롭 벡터가 모인 뒤 실행하고, 그다음 `track.manifest`를 낸다 |
| 텍스트 임베딩 차원 | 운영 1536 고정, 로컬은 다른 모델 | 차원 비고정 스키마 + 모델별 부분 인덱스(위) |
| 검토 큐 | Event Analyzer가 Quality 검토 큐에 넣음(통로 없음) | `event.analyzed`에 `reviewRequired`(terra·sol 불일치 등)를 싣고 Quality가 구독해 큐에 넣음 |
| 로컬 메모리 | 19개 + Ollama, 약 13.5GB + 4~8GB | compose 프로필로 작업에 필요한 서비스만 띄움 |

## 결과

- 좋아지는 점:
  - 산업안전 시연 시나리오(이벤트 6종, 위험 상태, 문장 검색과 bbox 주석, Video RAG)가 생긴다.
  - 모델·플랫폼 교체가 프로필 변경과 재처리로 끝나 라이선스·세대 교체 위험이 줄어든다.
  - 로컬과 운영이 같은 코드·스키마로 돈다.
- 감수할 점:
  - 배포 단위가 19개로 늘어 운영 부담이 커진다. Grounding Worker와 Quality는 필요할 때 0개로 줄일 수 있게 한다.
  - 모델 교체는 코드 변경이 없어도 재처리(`REANALYZE`·`REEMBED`) 비용이 든다.
  - 산업안전 이벤트의 후보 재현율이 탐지기(YOLOE 텍스트 클래스·파인튜닝)에 묶인다. 능력 선언으로 "판정하지 않음"을 드러내고 evals로 재현율을 잰다.
  - MVP 목록이 넓다(Quality, Re-ID, Grounding, Video RAG, 파인튜닝, 외부 로그인). 착수 순서는 의존성 기준으로 정하고, 범위 조정이 필요하면 별도로 결정한다.
- 후속 작업:
  - [아키텍처 v5](../architecture/architecture.md)와 [서비스 카탈로그](../architecture/service-catalog.md)를 이 결정 기준으로 갱신(이 ADR과 같은 PR)
  - ai 레포: `AGENTS.md` 구조 갱신, `vlm-worker` 폴더 제거, `frame-encoder`·`grounding-worker` 폴더 추가
  - 이벤트 계약(`docs/contracts/events/`), ai-gateway 계약(`openapi/ai-gateway.yaml`), 분류 체계 v1·이벤트 정의 목록·질의 사전(`docs/contracts/taxonomy/`)은 각 기능 spec에서 작성. 토픽 이름 변경(`segment.*`)은 Pipeline·Search·Chunk Processor 담당자와 계약 PR에서 맞춘다
  - PoC에서 검색 단계별 지연(p50·p95), 이미지 토큰 비용, YOLOE 후보 재현율 실측

## 참고

- [ADR-0005 분석을 검색 경로와 이벤트 경로로 나누고 17개 배포 단위를 다시 구성한다](0005-search-and-event-paths.md) (이 ADR로 대체)
- [ADR-0001 ai 레포를 uv workspace로 구성한다](0001-ai-uv-workspace.md)
- [ADR-0006 로컬 개발과 테스트의 S3 대체 저장소로 SeaweedFS를 쓴다](0006-local-s3-seaweedfs.md)
- 설계 원본: 루트 `references/검색·이벤트 VLM 아키텍처_v2.md`
- OpenAI 모델 목록: <https://developers.openai.com/api/docs/models/all>
- Ultralytics 라이선스: <https://www.ultralytics.com/license>
- MobileCLIP2-S0 OpenCLIP 모델 카드(apple-amlr): <https://huggingface.co/timm/MobileCLIP2-S0-OpenCLIP>
