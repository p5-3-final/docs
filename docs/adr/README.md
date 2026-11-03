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
