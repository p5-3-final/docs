---
status: In Progress
updated: 2026-11-04
---

# 아키텍처 v4 전환 작업 목록

아키텍처 v4(평가·상태 변화·예측 준비)를 반영하면서 할 일을 한 곳에 모은 목록이다. 작업 하나를 끝낼 때마다 상태와 PR 번호를 갱신한다.

- 근거: 참고 문서 "검색·이벤트 VLM 아키텍처 v4"의 "v4 변경: 평가·상태 변화·예측 준비" ①~⑩. v4는 v3 구조([ADR-0008](../adr/0008-industrial-safety-v3.md))를 유지하고 확장 자리를 더하는 변경이다.
- 범위: 이 작업 공간 담당 서비스(ai 레포 전체, backend의 api-gateway·auth-service·media-service와 공통 라이브러리, frontend)와 docs. pipeline-service·analysis·search-service·notification-service·chunk-processor는 다른 담당자 몫이라 계약 필드만 정의하고 구현은 넣지 않는다(5절).
- 진행 순서: 설계 문서·계약(1절) → backend 구조 정리(2절) → ai 구조 변경(3절) → backend v4 기능(4절) → 보류했던 spec 재개(6절)

상태 표시: `대기` · `진행` · `완료` · `보류`

## 1. 설계 문서·계약 (docs)

| ID | 작업 | v4 | 상태 | PR |
| --- | --- | --- | --- | --- |
| D-1 | ADR: v4 채택 1건([ADR-0010](../adr/0010-v4-evaluation-readiness.md), ①~⑦·⑨·⑩)과 파생 데이터 보존 등급 1건([ADR-0011](../adr/0011-derived-data-retention.md), ⑧) | 전체 | 완료 | #65, #66 |
| D-2 | `overview.md` v4 반영: 새 토픽 `stage.timing`·`event.candidate.vector`, `chunk.manifest`·`source.completed`·`video.uploaded`·`video.deleted` 확장, AI Gateway 확장점(taskType 등록, `predictor` Adapter, `state_compare`·`risk_forecast`), 이벤트 유형 8종, Quality 확장, 보존 등급. 모델 원문은 지금처럼 호출 로그 DB에 둔다([SPEC-009](../specs/SPEC-009-ai-gateway-analyze/spec.md)). | 전체 | 완료 | #68 |
| D-3 | `service-catalog.md` 갱신: 토픽 발행·구독, Quality 역할 | 전체 | 완료 | #68 |
| D-4 | 분류 체계 v2: 이벤트 유형 8종(`equipment_abandoned`, `object_moved` 추가), 탐지 프로필 스키마(버전·학습 출처·체크섬·`supported_events`). v1과 클래스 대응표는 지우고 `event_judge`를 v2로 옮긴다(7절 결정 6·7) | ① | 완료 | #69, #70 |
| D-5 | 모델 산출물 규약: `models/<종류>/<버전>/manifest.json` 스키마(`service-contracts/models/manifest.schema.json`, 파일 체크섬·크기, 차원·클래스, 학습 출처, 라이선스). SPEC-011 R-15·R-16·R-18 갱신, 로컬 업로드 스크립트가 manifest를 올림 | ② | 완료 | #78 |
| D-6 | 처리 단계 계약: 단계 ID 목록(`contracts/stages/`), `StageTiming` 스키마, `stage.timing` 토픽, 봉투 `producedAt`(하위호환 추가) | ⑩ | 대기 | |
| D-7 | Media 계약: 작업 세션 API, `video.uploaded`의 `sessionId`·`role`, `video.deleted`의 보존 등급·보존 키, 동의 철회 이벤트, 영상별 동의·계정 기본값 API | ④⑧ | 대기 | |

## 1-1. 서비스 간 계약 배포 ([ADR-0013](../adr/0013-service-contracts-release.md))

| ID | 작업 | 상태 | PR |
| --- | --- | --- | --- |
| C-1 | docs: `VERSION`, 묶음 스크립트, PR 버전 검사·main 릴리스 워크플로, 첫 릴리스 `service-contracts-v1.0.0` | 완료 | #73 |
| C-2 | ai: `service-contracts.lock`·받기 스크립트, CI가 잠금 버전 사용(A-0과 함께) | 완료 | ai #25 |
| C-3 | frontend: 잠금 파일과 CI 전환 | 완료 | frontend #32 |
| C-4 | backend: 잠금 파일과 CI 전환(공유 CI 파일만, 서비스 코드는 그대로) | 완료 | backend #41 |
| C-5 | docs: `docs/contracts/` → 루트 `service-contracts/` 이동, 링크·규칙 파일·각 레포 로컬 기본 경로 갱신 | 완료 | docs #75, ai #26, frontend #33, backend #42 |

## 2. backend 구조 정리 (동작 불변 리팩터링)

v4 기능을 넣기 전에 한다. 옮길 파일이 적을 때 정리해야 비용이 작다.

| ID | 작업 | 상태 | PR |
| --- | --- | --- | --- |
| B-1 | 패키지 규칙 변경: 최상위를 기능으로 나누고 그 안에 `api`·`application`·`domain`·`infra`를 둔다. 기능끼리는 `application`을 통해서만 부른다(ArchUnit). backend `AGENTS.md`와 아키텍처 테스트 갱신. 적용 범위는 7절 결정 1 | 완료 | backend #43 |
| B-2 | media-service를 기능 패키지로 재배치: `video`(업로드·완료·조회·삭제), `normalization`, `playback`, `shared`. Kafka 소비자(`NormalizationEventListener` 등)를 `api`에서 `infra/messaging`으로 옮긴다. | 완료 | backend #43 |
| B-3 | auth-service를 기능 패키지로 재배치: `account`(가입·내 정보), `session`(로그인·재발급·로그아웃·감사), `token`(JWT·JWKS·알림 연결 티켓) | 완료 | backend #44 |
| B-4 | 중복 공통화: 사용자 헤더 읽기(auth `UserIdHeader`, media `UserHeaders`)와 `TimeConfig`를 `libs/common-web`(`UserHeaders`, `ClockAutoConfiguration`)으로 모은다. gateway `ProblemResponseWriter`는 WebFlux라 서블릿용 `common-web`에 넣지 않고 그대로 둔다(겹치는 부분은 `code` 필드 몇 줄). | 완료 | backend #45 |
| B-5 | 이벤트 봉투를 `common-messaging`이 채우게 바꾼다. 서비스는 payload만 정의한다(4절 F-4의 `producedAt` 선행 작업). 7절 결정 5 | 보류 | |
| B-6 | (선택) docs JSON Schema에서 이벤트 record 생성. 새 빌드 도구라 7절 결정 3 | 보류 | |

api-gateway는 파일이 16개라 지금 구조를 유지한다.

## 3. ai 구조 변경

| ID | 작업 | v4 | 상태 | PR |
| --- | --- | --- | --- | --- |
| A-0 | Prompt Registry 원본을 ai 레포 `services/ai-gateway/registry/`로 이전([ADR-0012](../adr/0012-prompt-registry-source.md)): 프롬프트 이동, 분류 체계는 잠금 파일 버전에서 받음(C-2), 이전 뒤 `service-contracts/prompts/` 삭제 | ⑦ | 완료 | ai #25, docs #74 |
| A-1 | 가중치 전달을 manifest 규약으로: 프로필이 manifest 경로와 manifest SHA-256을 가리키고, 파일 체크섬은 manifest에서 읽는다. 프로필의 모델 ID·차원은 기대값으로 두고 manifest와 다르면 기동에 실패한다. `libs/encoders`, ai-gateway 프로필, 로컬 업로드 스크립트·버킷 경로, SPEC-011 R-15·R-16·R-18 갱신. frame-encoder보다 먼저 한다. | ② | 완료 | ai #27, docs #78 |
| A-2 | taskType을 Prompt Registry 등록만으로 추가: 출력 검증 실패 시 대체 결과(`output.py` `_FALLBACKS`)와 mock Adapter 출력을 taskType 코드에서 떼어 낸다. 프롬프트·프로필 전달 방식은 7절 결정 4 | ⑦ | 진행 | |
| A-3 | 결과에 분류 체계 버전 기록: `/v1/analyze` 응답과 호출 로그에 `taxonomy_version` | ① | 대기 | |
| A-4 | `libs/messaging` 처리 시간 측정: 큐 대기·핸들러 시간 자동 측정, `stage()` 블록, `stage.timing` 발행, 발행 시 `producedAt`. normalize에 `normalize.probe`·`transcode`·`hls`·`store` 블록 | ⑩ | 대기 | |
| A-5 | `predictor` Adapter(ONNX 등 CPU 실행). 새 의존성이라 실제 예측 모델이 생길 때 한다. | ⑦ | 보류 | |

바꿀 필요 없는 것: `video.uploaded`·`video.deleted`의 새 필드는 이벤트 모델이 모르는 필드를 무시해 그대로 받는다. ai-gateway가 지우는 모델 원문은 보존 등급 (a)라 삭제 동작도 같다.

## 4. backend v4 기능

| ID | 작업 | v4 | 상태 | PR |
| --- | --- | --- | --- | --- |
| F-1 | media 작업 세션: `work_session` 테이블·API, `video.uploaded`에 `sessionId`·`role` | ④ | 대기 | |
| F-2 | media 보존 등급(ADR-0011): 영상별 동의·계정 기본값 저장, 삭제 영상 최소 기록(1년), 보존 키 계산, `video.deleted`에 등급·보존 키, 동의 철회 이벤트 | ⑧ | 대기 | |
| F-3 | media 외부 데이터셋 가져오기: Quality의 매니페스트 대량 등록 경로, 데이터셋 영상은 삭제 전파 제외 | ⑨ | 대기 | |
| F-4 | `common-messaging` 처리 시간 측정: 발행 시 `producedAt`, 공통 소비 래퍼로 큐 대기·처리 시간, `stage.timing` 발행. media `media.upload` 단계. 7절 결정 5 | ⑩ | 보류 | |
| F-5 | api-gateway Quality 라우트와 `OPERATOR` 제한(Quality를 만들 때) | ⑨ | 보류 | |

auth-service는 v4 변경이 없다. 외부 로그인(OIDC)은 v3부터의 남은 범위로 v4와 별개다.

## 5. 아직 만들지 않은 담당 서비스 (각 spec에서 반영)

| 서비스 | 반영할 항목 |
| --- | --- |
| frame-encoder | ③ 유형별 텍스트 프로토타입 비교 후 `event.candidate.vector` 발행, ② manifest, ⑩ `encoder.*` 단계 |
| event-analyzer | `event.candidate`·`event.candidate.vector` 두 토픽 구독, 판정 방식 `vector+vlm` 기록 |
| aggregator | ④ 세션 초기 상태, ⑤ 재고 비교와 `state_compare`, ⑥ 노출 지표, 새 유형 2종, `risk_forecast`(1단계 규칙 점수) |
| quality | ⑨ 라벨 3종·외부 데이터셋 가져오기·특징 내보내기, ⑩ `stage_timing` 적재·리포트·성능 회귀 CI Gate |
| frontend | ④ 세션 화면, ⑥ 노출 표시, ⑩ 처리 시간 분해 |
| track-stitcher, grounding-worker | ⑩ 단계 ID만 |

다른 담당자와 맞물리는 계약(필드 정의만 하고 구현은 각 담당): `chunk.manifest`의 정적 객체 재고(chunk-processor), pipeline-service의 `common-messaging` 업그레이드, search-service의 `search.*` 단계.

## 6. 보류한 작업

| 작업 | 재개 조건 |
| --- | --- |
| SPEC-012 ai-gateway 질의 해석(초안 작성 중) | D-4 이후. 사전에 새 유형 2종 표현 추가, 응답에 분류 체계 버전 |
| SPEC-013 결과 캐시·예산·토큰 버킷·단계 상향 | SPEC-012 이후 |

## 7. 결정할 것

| 번호 | 질문 | 결정 |
| --- | --- | --- |
| 1 | backend 패키지 규칙(B-1)을 pipeline-service에도 적용할지, 담당 서비스에만 적용할지 | 규칙은 레포 전체에 둔다. 재배치는 담당 서비스(media·auth)만 하고, pipeline-service는 기존 레이어 구조를 허용해 담당자가 정한다. |
| 2 | ADR을 v4 하나로 묶을지, ③⑤⑧ 3건으로 나눌지 | v4 채택 1건(ADR-0010)과 보존 등급 1건 |
| 3 | 이벤트 계약 코드 생성(B-6)을 할지 | 미정(B-6 보류) |
| 4 | 프롬프트·프로필을 이미지에 넣는 지금 방식을 실행 중 읽기(S3 버전 경로 또는 gitops ConfigMap)로 바꿀지 | 저장소 버전 경로에서 기동 시 받는다(ADR-0010 ⑦). |
| 5 | pipeline-service도 쓰는 `common-messaging` 변경(B-5, F-4)을 이 작업 공간에서 할지 | 진행 중인 다른 담당자 코드가 머지된 뒤 이 작업 공간에서 한다(그때까지 보류). |
| 6 | 개발 단계에서 계약의 이전 버전을 남길지 | 남기지 않는다. 분류 체계는 v2로 바로 옮긴다(2026-11-04). |
| 7 | 외부 데이터셋 라벨 대응표(ADR-0010 ①)를 둘지 | 두지 않는다. 팀이 정의한 데이터셋을 이 분류 체계의 클래스 이름으로 라벨링한다(2026-11-04). |
| 8 | Prompt Registry 원본 위치 | ai 레포(ADR-0012). 분류 체계는 잠금 파일 버전에서 받는다(ADR-0013) |
| 9 | 서비스 간 계약 관리 방식과 위치 | 버전 릴리스 + 잠금 파일, 폴더는 루트 `service-contracts/`(ADR-0013). C-1~C-4 다음에 C-5로 폴더를 옮겼다. |
