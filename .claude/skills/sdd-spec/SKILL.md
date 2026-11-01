---
name: sdd-spec
description: 새 기능 스펙(SPEC-NNN)을 docs/specs에 EARS 형식으로 작성한다. 새 기능을 시작하거나 기존 spec을 보완할 때 사용한다.
argument-hint: <기능 설명 또는 기존 SPEC-NNN>
---

# /sdd-spec: 기능 스펙 작성

입력: $ARGUMENTS (Claude Code에서는 인자로 치환된다. 다른 도구에서는 사용자 요청에서 파악한다)

1. **위치 확인**: 루트 docs 레포의 `docs/specs/`에서 작업한다. 하위 레포에서 실행했다면 상위의 `docs/specs/`를 쓴다.
2. **번호 결정**: 입력이 기존 `SPEC-NNN`이면 그 spec을 보완한다. 아니면 `docs/specs/`의 가장 큰 번호에 1을 더한다.
3. **맥락 수집**: 다음 문서를 읽는다.
   - `docs/principles.md`
   - `docs/product/prd.md`, `docs/product/glossary.md`
   - `docs/architecture/service-catalog.md`
   - 관련 계약 파일
4. **초안 작성**: `docs/templates/spec.md`를 복사해서 `docs/specs/SPEC-NNN-<slug>/spec.md`를 만든다.
   - 무엇·왜만 쓴다. 구현 방법은 쓰지 않는다.
   - 기능 요구사항은 모두 EARS 문법으로 쓴다(`.claude/rules/docs-writing.md` 참고).
   - 모르는 것은 `[NEEDS CLARIFICATION: 질문]`으로 표시한다. 그럴듯하게 채우지 않는다.
5. **명확화**: 미결 사항을 우선순위가 높은 것부터 최대 5개까지 한 번에 묻는다. 답을 받으면 spec에 반영하고 표시를 지운다.
6. **자체 검증**: 아래를 모두 만족하는지 확인한다.
   - 모든 R-*가 검증 가능하고, 조건을 하나만 담고 있다.
   - 모든 사용자 시나리오가 요구사항에 매핑되어 있다.
   - 영향 범위 표와 계약 변경 섹션이 채워져 있다.
7. **목록 갱신**: `docs/specs/README.md` 표에 행을 추가하거나 갱신한다.
8. **보고**: 만든 파일 경로, 남은 미결 사항, 다음 단계를 알린다. 다음 단계는 "docs 레포에 PR → 승인 → 각 레포에서 `/sdd-plan SPEC-NNN`"이다.

커밋과 PR은 사용자가 요청할 때만 한다.
