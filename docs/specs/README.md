# 기능 스펙 목록

새 spec은 `/sdd-spec <기능 설명>`으로 만든다. 템플릿은 [../templates/spec.md](../templates/spec.md)다.

| ID | 제목 | 상태 | 레포 | 담당 | 갱신일 |
| --- | --- | --- | --- | --- | --- |
| [SPEC-001](SPEC-001-auth-and-gateway/spec.md) | 회원가입·로그인과 인증된 요청 | Implementing | backend | | 2026-11-02 |
| [SPEC-002](SPEC-002-frontend-auth-shell/spec.md) | 인증 화면과 앱 기본 레이아웃 | Implementing | frontend | | 2026-11-02 |
| [SPEC-003](SPEC-003-video-upload/spec.md) | 영상 업로드와 관리 | Implementing | backend | | 2026-11-03 |
| [SPEC-004](SPEC-004-pipeline-job-planning/spec.md) | Pipeline 청크 구간 계산과 작업 계획 저장 | Implementing | backend | backend 담당자 | 2026-11-03 |
| [SPEC-005](SPEC-005-frontend-video-upload/spec.md) | 영상 업로드 화면과 내 영상 목록 | Implementing | frontend, docs | | 2026-11-03 |
| [SPEC-006](SPEC-006-video-playback/spec.md) | 원본 영상 재생 | Implementing | backend, frontend, docs | | 2026-11-03 |
| [SPEC-007](SPEC-007-video-normalize/spec.md) | 영상 정규화 | Implementing | ai, backend, frontend, docs | | 2026-11-03 |
| [SPEC-008](SPEC-008-normalized-intake/spec.md) | 정규화 완료 수신과 계획 저장 | Implementing | backend | backend 담당자 | 2026-11-03 |
| [SPEC-009](SPEC-009-ai-gateway-analyze/spec.md) | ai-gateway 분석 호출 | Implementing | ai, docs | | 2026-11-03 |
| [SPEC-010](SPEC-010-chunk-dispatch/spec.md) | Pipeline 공정 배정과 실행 슬롯·요청 발행 | Implementing | backend, docs | backend 담당자 | 2026-11-05 |
| [SPEC-011](SPEC-011-ai-gateway-embed/spec.md) | ai-gateway 벡터 생성 | Implementing | ai, docs | | 2026-11-03 |
| [SPEC-012](SPEC-012-ai-gateway-parse/spec.md) | ai-gateway 질의 해석 | Implementing | ai, docs | | 2026-11-06 |
| [SPEC-013](SPEC-013-stage-timing/spec.md) | 처리 단계 측정 | Implementing | ai, docs | | 2026-11-04 |
| [SPEC-014](SPEC-014-execution-results/spec.md) | 청크 실행 종료 결과와 슬롯 자동 반환 | Implementing | backend, ai, docs | backend 담당자 | 2026-11-05 |

| [SPEC-015](SPEC-015-job-execution-status/spec.md) | Job 실행 집계와 소유자 상태 조회 | Implementing | backend, docs | backend 담당자 | 2026-11-05 |
| [SPEC-016](SPEC-016-ai-gateway-cache-budget/spec.md) | ai-gateway 결과 캐시·예산·호출 한도 | Implementing | ai, docs | | 2026-11-06 |
| [SPEC-017](SPEC-017-media-work-session/spec.md) | 작업 세션 | Implementing | backend, docs | | 2026-11-06 |
| [SPEC-018](SPEC-018-media-retention-consent/spec.md) | 학습용 보존 동의와 보존 키 | Implementing | backend, docs | | 2026-11-06 |
| [SPEC-019](SPEC-019-frame-encoder/spec.md) | frame-encoder 구간·크롭 벡터와 프로토타입 후보 | Implementing | ai, docs | | 2026-11-06 |
| [SPEC-020](SPEC-020-event-analyzer-vector/spec.md) | event-analyzer 벡터 후보 판정 | Implementing | ai, docs | | 2026-11-06 |
| [SPEC-021](SPEC-021-internal-call-rules/spec.md) | 내부 동기 호출 규약 적용 (ai-gateway 마감 시간, 생성 클라이언트, 재시도 규칙) | Approved | ai, docs | | 2026-11-06 |
| [SPEC-022](SPEC-022-track-stitcher/spec.md) | track-stitcher 경계 트랙 연결과 재등장 연결(Re-ID) | Approved | ai, docs | | 2026-11-06 |
| [SPEC-023](SPEC-023-event-analyzer-detector/spec.md) | event-analyzer 탐지기·규칙 후보 판정과 event.manifest | Approved | ai, docs | | 2026-11-06 |
| [SPEC-024](SPEC-024-track-analyzer/spec.md) | track-analyzer 트랙 속성 분석과 객체 자유 질문 | Approved | ai, docs | | 2026-11-06 |
| [SPEC-025](SPEC-025-embedding-worker/spec.md) | embedding-worker 이벤트·트랙·구간 주석 텍스트 벡터 | Approved | ai, docs | | 2026-11-06 |
| [SPEC-026](SPEC-026-grounding-worker/spec.md) | grounding-worker 검색 상위 구간 bbox 주석 클립 | Approved | ai, docs | | 2026-11-06 |
| [SPEC-027](SPEC-027-aggregator/spec.md) | aggregator 영상 단위 병합·시간 규칙·위험 상태·노출 지표·요약 | Approved | ai, docs | | 2026-11-06 |
| [SPEC-028](SPEC-028-aggregator-inventory/spec.md) | aggregator 정적 객체 재고 비교·장비 방치·위험 노출 예측 | Approved | ai, docs | | 2026-11-06 |
| [SPEC-029](SPEC-029-quality-service/spec.md) | quality-service 검토 큐·Golden Set·평가 실행·처리 단계 리포트 | Approved | backend, docs | | 2026-11-06 |

상태: `Draft` → `Review` → `Approved` → `Implementing` → `Done` (대체되면 `Superseded`)
