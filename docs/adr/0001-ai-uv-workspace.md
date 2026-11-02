---
id: ADR-0001
title: ai 레포를 uv workspace로 구성한다
status: Proposed
date: 2026-11-02
deciders: [팀]
related: []
---

# ADR-0001 ai 레포를 uv workspace로 구성한다

## 맥락
ai 레포의 Python 배포 단위가 9개(ai-gateway와 Kafka 소비 워커 8개)다. 워커마다 의존성이 크게 다르다. chunk-processor는 YOLO와 FFmpeg를, normalize는 FFmpeg를 쓰고, 나머지 워커는 HTTP 클라이언트 정도만 쓴다. ai `AGENTS.md`는 서비스가 2개 이상이 되면 uv workspace로 전환하고 ADR을 쓰도록 정했다.

## 결정 요인
- 서비스마다 독립 이미지로 배포하고, 무거운 의존성이 다른 이미지에 섞이지 않아야 한다.
- Kafka 소비, 재시도, 이벤트 모델, ai-gateway 호출 같은 공통 코드를 한 곳에서 관리해야 한다.
- 의존성 버전은 레포 전체에서 하나의 lock 파일로 맞춘다.

## 검토한 선택지
### 1. uv workspace (`services/<서비스>` + `libs/<라이브러리>`)
- 장점: 서비스별 의존성과 이미지가 분리된다. 공통 코드는 workspace 멤버로 공유한다. lock 파일은 하나다.
- 단점: 루트와 멤버의 `pyproject.toml`을 함께 관리해야 한다.

### 2. 단일 패키지 + 진입점 분리
- 장점: 구조가 단순하다.
- 단점: 모든 이미지에 YOLO, FFmpeg 같은 무거운 의존성이 들어간다. 서비스 경계가 import 수준에서 강제되지 않는다.

## 결정
**uv workspace**를 택한다. 이유: 워커별 의존성 차이가 커서 이미지 분리가 필요하고, 공통 코드는 `libs/`로 공유할 수 있다.

## 결과
- 좋아지는 점: 서비스별 이미지 크기와 빌드 시간이 줄어든다. 서비스 경계가 패키지 단위로 드러난다.
- 감수할 점: 새 서비스를 추가할 때 workspace 멤버 등록과 Dockerfile이 필요하다.
- 후속 작업: ai `AGENTS.md`의 구조·명령어 섹션 갱신, 서비스별 Dockerfile과 CI matrix 작성

## 참고
- [서비스 카탈로그](../architecture/service-catalog.md)
