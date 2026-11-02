---
id: ADR-0003
title: 서비스를 17개 배포 단위로 나눈다
status: Superseded by ADR-0005
date: 2026-11-02
deciders: [팀]
related: [ADR-0001, ADR-0002]
---

# ADR-0003 서비스를 17개 배포 단위로 나눈다

## 맥락

업로드한 영상을 정규화하고 청크 단위로 병렬 분석한 뒤, 구간 설명·트랙 속성·이벤트·요약·검색 벡터를 저장하고 문장 검색으로 장면을 찾아 주는 서비스를 만든다. 처리 단계마다 자원 특성이 크게 다르다.

- 영상 디코딩과 객체 추적: CPU와 메모리를 많이 쓴다(FFmpeg, YOLO).
- 구간 설명, 트랙 속성, 이벤트 판정, 요약: 외부 AI 호출을 기다리는 I/O 대기가 대부분이다.
- 사용자 요청(업로드, 조회, 검색, 알림): 지연 시간이 중요하다.

backend `AGENTS.md`는 새 서비스 모듈을 추가할 때 ADR을 요구한다. 이 ADR은 MVP 범위의 서비스 경계와 배포 단위를 정한다.

## 결정 요인

- 6명 팀, 최종 프로젝트 기간
- 단계별로 독립적으로 늘리고 줄일 수 있어야 한다(무거운 디코딩이 AI 호출 대기나 사용자 요청을 막지 않게).
- 외부 AI로 이미지를 보내는 지점을 하나로 모아 비용·보안을 통제해야 한다.
- 로컬 개발 머신에서 전체를 띄울 수 있어야 한다(Docker 합계 약 11~12GB).
- 서비스마다 자기 DB를 소유하고 상태 변경은 이벤트로만 전달한다(원칙 IV, ADR-0002).

## 검토한 선택지

### 1. 17개 배포 단위 (Spring 8 + Python 9)

- Spring: api-gateway, auth-service, media-service, pipeline-service, analysis-api, analysis-loader, search-service, notification-service
- Python: ai-gateway, normalize, chunk-processor, track-stitcher, track-analyzer, event-analyzer, vlm-worker, embedding-worker, aggregator
- 장점: 자원 특성이 다른 단계를 따로 확장한다. 외부 AI 호출은 ai-gateway 한 곳에서 모델 라우팅, 캐시, 예산, 토큰 버킷을 처리한다. 적재(analysis-loader)가 조회 API(analysis-api)의 지연에 영향을 주지 않는다.
- 단점: 배포 단위가 많아 CI, 매니페스트, 로컬 compose 관리량이 늘어난다. 이벤트 계약과 완료 판정(manifest) 설계가 필요하다.

### 2. 굵은 서비스 (Spring 1~2개 + Python 워커 1~2개)

- 장점: 배포·운영 대상이 적고 초기 개발이 빠르다.
- 단점: 디코딩과 AI 호출 대기가 같은 프로세스에서 자원을 다툰다. 단계별 확장이 불가능하다. 나중에 나누려면 경계를 다시 설계해야 한다.

### 3. 기능별 분리 + 워커 통합 (Spring 8 + ai-gateway + 워커 1개)

- 장점: 도메인 경계는 유지하면서 Python 배포 단위를 줄인다.
- 단점: 통합 워커 하나에 YOLO·FFmpeg 같은 무거운 의존성과 I/O 대기 작업이 섞여, 이미지가 커지고 확장 단위가 맞지 않는다.

## 결정

**17개 배포 단위**를 택한다. 이유: 처리 단계마다 자원 특성이 달라 따로 확장해야 하고, 외부 AI 호출을 ai-gateway 한 곳으로 모아야 한다. 배포 단위가 늘어나는 비용은 공통 빌드(build-logic, uv workspace), 공통 라이브러리(`libs/`), gitops의 서비스별 `apps/` 구조로 줄인다.

이후 단계 서비스(Quality, Stream, Stream Ingestor)는 이 ADR 범위 밖이며, 착수할 때 서비스 카탈로그와 함께 추가한다.

## 결과

- 좋아지는 점: 디코딩 워커만 늘리거나 AI 호출 워커만 늘리는 식으로 비용에 맞춰 확장한다. 외부 AI 호출 비용과 개인정보 전송 지점을 한 곳에서 통제한다.
- 감수할 점: 배포 단위마다 Dockerfile, CI workflow, gitops 매니페스트가 필요하다. 로컬에서는 컨테이너마다 리소스 상한을 최소로 걸어야 한다.
- 후속 작업:
  - 서비스 목록과 책임은 [서비스 카탈로그](../architecture/service-catalog.md)를 기준으로 유지
  - 서비스 모듈은 해당 서비스 구현을 시작할 때 추가(backend `settings.gradle.kts`, ai workspace 멤버)
  - 로컬 compose에 리소스 상한 설정

## 참고

- [서비스 카탈로그](../architecture/service-catalog.md)
- [아키텍처 개요](../architecture/overview.md)
