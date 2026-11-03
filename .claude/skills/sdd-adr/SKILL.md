---
name: sdd-adr
description: 아키텍처 결정을 ADR(MADR 형식)로 docs/adr에 기록한다. 새 서비스, 새 인프라 구성요소, 기술 교체, 하위호환을 깨는 계약 변경을 결정할 때 사용한다.
argument-hint: <결정할 주제>
---

# /sdd-adr: 아키텍처 결정 기록

입력: $ARGUMENTS (Claude Code에서는 인자로 치환된다. 다른 도구에서는 사용자 요청에서 파악한다)

1. `docs/adr/`의 가장 큰 번호에 1을 더해 `NNNN`을 정한다(4자리).
2. 관련된 기존 ADR과 `docs/principles.md`를 읽는다. 기존 결정을 뒤집는 것이라면 그 사실을 명시한다.
3. `docs/templates/adr.md`를 복사해서 `docs/adr/NNNN-<slug>.md`를 만든다.
   - 검토한 선택지는 최소 2개 이상 쓰고, 각각 장점과 단점을 적는다.
   - 결정 요인은 이 프로젝트의 실제 제약으로 쓴다. 예: 6명 팀, 기간, EKS 비용, 학습 곡선
   - 미확정 결정은 `Proposed`로 시작한다. 사용자가 이미 확정한 결정은 근거를 적고 `Accepted`로 기록한다.
4. 선택지 중 무엇을 고를지 미확정일 때만 사용자에게 확인받는다. 이미 확정된 결정이나 합의 범위의 작업은 같은 허락을 다시 묻지 않는다.
5. 기존 ADR을 대체하는 경우, 그 ADR의 상태를 `Superseded by ADR-NNNN`으로 바꾼다.
6. `docs/adr/README.md` 목록에 추가한다.
