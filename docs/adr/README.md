# 아키텍처 결정 기록 (ADR)

새 ADR은 `/sdd-adr <주제>`로 만든다. 형식은 MADR 기반의 [../templates/adr.md](../templates/adr.md)다.

| ID | 제목 | 상태 | 날짜 |
| --- | --- | --- | --- |
| [ADR-0001](0001-ai-uv-workspace.md) | ai 레포를 uv workspace로 구성한다 | Accepted | 2026-11-02 |
| [ADR-0002](0002-kafka-message-broker.md) | 서비스 간 비동기 통신에 Kafka를 쓴다 | Accepted | 2026-11-02 |
| [ADR-0003](0003-service-composition.md) | 서비스를 17개 배포 단위로 나눈다 | Superseded by ADR-0005 | 2026-11-02 |
| [ADR-0004](0004-browser-token-storage.md) | 브라우저에서 접근 토큰은 메모리에, 재발급 토큰은 HttpOnly 쿠키에 둔다 | Accepted | 2026-11-02 |
| [ADR-0005](0005-search-and-event-paths.md) | 분석을 검색 경로와 이벤트 경로로 나누고 17개 배포 단위를 다시 구성한다 | Superseded by ADR-0008 | 2026-11-02 |
| [ADR-0006](0006-local-s3-seaweedfs.md) | 로컬 개발과 테스트의 S3 대체 저장소로 SeaweedFS를 쓴다 | Accepted | 2026-11-03 |
| [ADR-0007](0007-independent-pr-merge.md) | 팀원 Approve 대기 없이 검증 후 PR을 직접 머지한다 | Accepted | 2026-11-03 |
| [ADR-0008](0008-industrial-safety-v3.md) | 산업안전 v3 구조(19개 배포 단위)를 채택하고 모델·플랫폼을 설정으로 교체할 수 있게 한다 | Accepted | 2026-11-03 |
| [ADR-0009](0009-pipeline-dispatch-boundary.md) | 영상 처리 책임과 계획·배정·추론 경계를 분리한다 | Accepted | 2026-11-03 |
| [ADR-0010](0010-v4-evaluation-readiness.md) | v3 구조를 유지하고 평가·상태 변화·예측을 받칠 확장 자리(v4)를 더한다 | Accepted | 2026-11-04 |
| [ADR-0011](0011-derived-data-retention.md) | 영상 삭제 시 비식별 파생 데이터는 동의를 받아 1년 동안 학습용으로 보존한다 | Accepted | 2026-11-04 |
| [ADR-0012](0012-prompt-registry-source.md) | Prompt Registry 원본을 ai 레포에 두고 버전을 고정한 묶음으로 배포한다 | Accepted | 2026-11-04 |
| [ADR-0013](0013-service-contracts-release.md) | 서비스 간 계약을 버전 릴리스로 배포하고 쓰는 쪽은 잠금 파일로 고정한다 | Accepted | 2026-11-04 |
| [ADR-0014](0014-ai-gateway-extensible-task-type.md) | ai-gateway taskType을 늘어날 수 있는 열린 목록(x-extensible-enum)으로 둔다 | Accepted | 2026-11-06 |
| [ADR-0015](0015-realtime-window-pipeline.md) | 실시간 수집을 같은 파이프라인의 창 단위 처리로 통합하고 STREAM Job은 stream-service가 소유한다 | Accepted | 2026-11-06 |
| [ADR-0016](0016-aggregator-fold-and-deterministic-caps.md) | 상태 전이는 aggregator fold 한 곳에서 계산하고, 늦은 이벤트는 revision 재발행, 호출 carry·상한은 결정적 규칙으로 둔다 | Accepted | 2026-11-06 |
| [ADR-0017](0017-architecture-single-document.md) | 아키텍처 문서를 v5 단일 문서로 재편하고 html 사본을 같은 폴더에서 생성한다 | Accepted | 2026-11-06 |
| [ADR-0018](0018-quality-nullable-response-fields.md) | quality-service 응답의 결측 값을 null로 표현하고 major를 올린다 | Accepted | 2026-11-07 |
