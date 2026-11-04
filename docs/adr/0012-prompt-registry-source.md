---
id: ADR-0012
title: Prompt Registry 원본을 ai 레포에 두고 버전을 고정한 묶음으로 배포한다
status: Accepted
date: 2026-11-04
deciders: [팀]
related: [ADR-0010, SPEC-009, SPEC-012]
---

# ADR-0012 Prompt Registry 원본을 ai 레포에 두고 버전을 고정한 묶음으로 배포한다

> 분류 체계를 ai 레포 사본으로 두고 docs main과 비교하는 방식은 [ADR-0013](0013-service-contracts-release.md)의 버전 릴리스·잠금 파일로 바뀌었다.

## 맥락

ai-gateway는 실행 중에 Prompt Registry(프롬프트, 입력·출력 스키마, 분류 체계)를 읽어 요청과 모델 응답을 검증한다. 지금은 원본이 docs 레포(`docs/contracts/prompts/`, `docs/contracts/taxonomy/`)에 있고, ai CI가 빌드하는 순간의 docs main을 받아 이미지에 복사한다([SPEC-009](../specs/SPEC-009-ai-gateway-analyze/spec.md)).

이 방식에서 확인한 문제는 다음과 같다.

- 재현이 안 된다. 이미지에 들어가는 프롬프트를 ai 커밋이 아니라 빌드 시점의 docs main이 정한다. 같은 ai 커밋을 다시 빌드하면 다른 프롬프트가 들어갈 수 있다.
- 반영 시점이 어긋난다. docs에서 프롬프트를 고쳐도 ai를 다시 빌드할 때까지 반영되지 않고, 관계없는 ai 변경이 프롬프트 변경을 함께 싣고 나간다.
- 계약과 검증 코드가 다른 레포에 있어 변경 순서를 맞춰야 한다. 분류 체계를 v2로 옮길 때 ai 테스트를 먼저 고쳐야 했다(ai #24, docs #70).
- 빌드와 테스트가 docs 레포 checkout(`--build-context`, `CONTRACTS_DIR`)에 기댄다.

[ADR-0010](0010-v4-evaluation-readiness.md) ⑦은 프롬프트·분류 체계 묶음과 프로필을 저장소 버전 경로에서 기동 시 받기로 했지만, 묶음의 원본을 어디에 둘지는 정하지 않았다.

프롬프트·입력 스키마·질의 사전은 ai 레포 안에서만 주고받는다(event-analyzer 등 → ai-gateway). 레포 경계를 넘는 것은 분류 체계(backend·frontend도 쓰는 어휘)와, 앞으로 이벤트로 나갈 출력 형식이다.

## 결정 요인

- 같은 ai 커밋은 항상 같은 Prompt Registry로 이어져야 한다.
- 프롬프트를 바꿀 때 이미지 재배포 없이 반영하고 되돌릴 수 있어야 한다(ADR-0010 ⑦).
- 분류 체계는 여러 레포가 같은 원본을 봐야 한다(계약 우선 원칙).
- 프롬프트 변경과 그것을 검증하는 코드·테스트가 같은 PR에서 바뀌어야 한다.

## 검토한 선택지

### 1. docs에 두고 docs CI가 묶음을 만들어 올림

- 장점: AI 담당자가 docs 레포만 다루면 된다. 문서와 계약이 한 곳에 있다.
- 단점: 프롬프트와 검증 코드가 계속 다른 레포에서 바뀐다. docs 레포에 배포용 CI와 저장소 쓰기 권한이 생긴다.

### 2. ai 레포에 두고, 분류 체계만 고정한 docs 커밋에서 사본으로 가져옴

- 장점: 프롬프트·검증 코드·테스트가 한 PR에서 바뀐다. 묶음 내용이 ai 커밋 하나로 정해진다. 빌드와 테스트가 docs checkout 없이 돈다.
- 단점: 분류 체계 사본을 docs 원본과 맞춰야 한다. AI 담당자가 ai 레포에서 프롬프트를 고친다.

### 3. 지금처럼 빌드 때 docs main을 복사

- 장점: 바꿀 것이 없다.
- 단점: 위 "맥락"의 문제가 그대로 남는다.

## 결정

**선택지 2**를 택한다. 이유: Prompt Registry가 ai 커밋 하나로 정해져 재현과 되돌리기가 되고, 레포 경계를 넘는 분류 체계만 docs를 원본으로 둔다.

| 항목 | 위치·방식 |
| --- | --- |
| 프롬프트(`_prefix.md`, `<taskType>/prompt.md`), 입력·출력 스키마, 질의 사전 | ai 레포 `services/ai-gateway/registry/`가 원본 |
| 분류 체계 | docs `docs/contracts/taxonomy/`가 원본. ai 레포 `registry/taxonomy/`에 사본을 두고, 가져온 docs 커밋을 함께 기록한다. 사본은 스크립트로만 갱신하고, ai CI가 사본이 docs main과 같은지 검사한다. |
| 다른 레포로 나가는 출력 형식 | 이벤트 계약(예: `event.analyzed`의 `VLMAnalysis`)을 쓸 때 docs `events/`에 두고, ai의 출력 스키마는 그 사본을 참조한다. 그때까지 출력 스키마는 ai 레포에 둔다. |
| 배포 | ai main 머지 시 CI가 registry를 버전·체크섬이 붙은 묶음으로 만들어 저장소 `registry/<버전>/`에 올린다. 운영 설정(gitops)은 쓸 버전만 가리키고, ai-gateway는 기동할 때 받아 체크섬을 확인한다(ADR-0010 ② 로더 공유). 로컬은 같은 묶음을 SeaweedFS에 올리거나 레포 폴더를 그대로 읽는다. |
| 결과 기록 | 호출 로그와 결과에 프롬프트 버전 ID(내용 해시)와 묶음 버전을 남긴다. |

이 ADR은 ADR-0010의 두 부분을 바꾼다.

- ⑦ "프롬프트·분류 체계 묶음과 프로필은 저장소 버전 경로에서 기동 시 받는다"의 원본 위치를 위 표로 정한다.
- ① "분류 체계 v2는 클래스 대응표 형식을 담는다"를 없앤다. 라벨은 팀이 정의한 데이터셋에서 분류 체계의 클래스 이름으로 바로 달기 때문에 외부 데이터셋 라벨 대응표가 필요 없다(docs #70).

## 결과

- 좋아지는 점:
  - 같은 ai 커밋은 같은 Prompt Registry 묶음을 만든다. 묶음 버전으로 반영·되돌리기를 하고, 결과에서 어떤 프롬프트를 썼는지 찾을 수 있다.
  - 프롬프트 변경이 검증 코드·테스트와 같은 PR에서 바뀐다.
  - ai 빌드와 테스트가 docs 레포 checkout 없이 돈다(분류 체계 사본 검사만 docs를 읽는다).
- 감수할 점:
  - 분류 체계를 바꾸면 docs PR 뒤에 ai 레포에서 사본을 갱신하는 PR이 따라야 한다. 그 사이 ai CI의 사본 검사가 실패해 갱신이 필요하다는 것을 알린다.
  - AI 담당자는 프롬프트를 ai 레포에서 고친다.
  - 묶음 업로드와 운영 설정은 저장소 쓰기 권한과 gitops 설정이 필요하다(infra·gitops).
- 후속 작업: [아키텍처 v4 전환 작업 목록](../architecture/v4-transition.md) A-0, A-2
  - ai: `services/ai-gateway/registry/`로 이전, 분류 체계 사본과 동기화 스크립트·CI 검사, 빌드의 docs 의존 제거
  - docs: `docs/contracts/prompts/` 삭제, SPEC-009·overview·계약 README 갱신
  - ai: 묶음 생성·업로드와 기동 시 받기(A-2, 저장소 권한은 infra 지시 후)

## 참고

- [ADR-0010 v3 구조를 유지하고 평가·상태 변화·예측을 받칠 확장 자리(v4)를 더한다](0010-v4-evaluation-readiness.md) (⑦ 원본 위치, ① 클래스 대응표를 이 ADR로 대체)
- [SPEC-009 ai-gateway 분석 호출](../specs/SPEC-009-ai-gateway-analyze/spec.md)
