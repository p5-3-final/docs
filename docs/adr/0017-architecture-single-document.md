---
id: ADR-0017
title: 아키텍처 문서를 v5 단일 문서로 재편하고 html 사본을 같은 폴더에서 생성한다
status: Accepted
date: 2026-11-06
deciders: [사용자]
related: [ADR-0008, ADR-0010, ADR-0015, ADR-0016]
---

# ADR-0017 아키텍처 문서를 v5 단일 문서로 재편하고 html 사본을 같은 폴더에서 생성한다

## 맥락

아키텍처가 `docs/architecture/overview.md`(v3 기준), `v4-transition.md`(v4 차이), `references/`의 설계 원본(v2~v4 md·html), ADR-0008·0010에 나뉘어 있었다. 실시간 통합(v5)을 더하면 같은 내용이 네 곳에 쌓이고, spec·계약이 어느 문서를 기준으로 삼는지 흐려진다. 사용자는 "단일 기준 문서를 두고 변경될 때마다 spec·계약이 연결되어 수정되는 흐름"과 "html과 md를 같은 곳에 두고 같이 갱신"을 요구했다.

## 결정 요인

- spec·계약·ADR이 참조할 기준이 하나여야 한다.
- 문서는 git으로 리뷰한다(Markdown, Mermaid). html은 열람용이다.
- 기존 ADR의 Accepted 본문은 고치지 않는다(`docs-writing.md`).

## 검토한 선택지

### 1. overview.md를 고쳐 쓰고 v4-transition.md를 이어 간다

- 장점: 파일 경로가 바뀌지 않는다.
- 단점: 차이 문서가 또 하나 늘고, 전체 흐름을 한 번에 읽을 수 없다.

### 2. 단일 문서 `architecture.md`(v5)를 새로 쓰고 옛 문서를 `legacy/`로 옮긴다

- 장점: 기준이 하나다. 각 절이 spec과 계약에 대응된다(부록 B). 옛 문서는 이력으로 남는다.
- 단점: 링크를 모두 바꿔야 한다(ADR 10건, spec 25건). 문서가 길다(약 1,100줄).

## 결정

**선택지 2**를 택한다. 이유:

- `docs/architecture/architecture.md`가 아키텍처의 단일 기준이다. 서비스·토픽·API·AI 호출·운영 규칙은 여기서 정하고 spec과 계약은 이 문서를 세분화한다. 문서와 spec·계약이 다르면 먼저 이 문서를 고친다.
- `overview.md`·`v4-transition.md`는 `docs/architecture/legacy/`로 옮기고 머리말에 대체 사실을 적는다. ADR-0008·0010은 본문을 그대로 두고 새 문서가 둘을 합쳐 설명한다.
- 같은 폴더의 `architecture.html`은 `scripts/render-architecture-html.sh`가 md에서 만든다(pandoc + Mermaid). md를 고치면 스크립트를 실행해 html을 같은 커밋에 넣고, `--check`로 최신 여부를 확인한다.
- 단계별 상세 표는 `processing-flow.md`, 서비스별 포트·DB·담당은 `service-catalog.md`, 배포·저장은 `delivery-and-data.md`에 두고 architecture.md가 링크한다.
- 문서 버전은 frontmatter `version`으로 적고, 구조 재검토 결과를 반영하면 소수점을 올린다(v5 → v5.1).

## 결과

- 좋아지는 점: spec·계약·ADR이 한 문서의 절 번호로 연결된다. 옛 문서와의 혼동이 없다.
- 감수할 점: 문서 한 개가 길다. html은 생성본이라 diff가 크다(리뷰 대상은 md다).
- 후속 작업: 없음. 이 ADR 시점에 재편이 끝났다.

## 참고

- [아키텍처 v5.1](../architecture/architecture.md)
- [legacy/overview.md](../architecture/legacy/overview.md)
