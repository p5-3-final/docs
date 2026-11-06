---
updated: 2026-11-06
---

# 작업 인수인계

> 다른 컴퓨터나 새 에이전트 세션이 이 프로젝트를 이어서 작업할 때 **가장 먼저** 읽는 문서다. 규칙의 원본은 루트 `AGENTS.md`와 `.claude/rules/`이고, 이 문서는 거기에 없는 담당 범위, 사용자 결정, 작업 요령, 진행 상태를 적는다. 상태가 바뀌면 이 문서를 같은 PR에서 고친다.

## 1. 새 컴퓨터 준비

### 1.1 도구

| 도구 | 용도 | 비고 |
| --- | --- | --- |
| git, `gh` (GitHub CLI) | 클론, PR 생성·확인·머지 | `gh auth login`으로 `p5-3-final` 조직 레포 권한 확인 |
| Docker Desktop 또는 OrbStack | 로컬 compose, testcontainers, 서비스 이미지 테스트 | 메모리 8GB 이상 할당 |
| uv | ai 레포(Python 3.12 workspace) | `uv sync --all-packages` |
| JDK 21, Gradle Wrapper | backend 레포 | 레포의 `./gradlew` 사용 |
| fnm, Node 24, pnpm | frontend 레포 | 기본 node가 다른 버전이면 `eval "$(fnm env)" && fnm use 24`를 먼저 실행 |
| Ollama | 로컬 VLM·텍스트 임베딩(선택) | `qwen3-vl:4b-instruct`, `bge-m3`. mock 프로필이면 필요 없음 |
| `npx markdownlint-cli2`, `lychee`, `npx @redocly/cli`, `oasdiff`, `shellcheck`, `hadolint`, `actionlint` | docs·계약·CI 검사 | 루트 `AGENTS.md` "docs 레포 명령" |

### 1.2 레포 받기

```bash
git clone git@github.com:p5-3-final/docs.git project   # 이 레포가 작업 공간 루트다
cd project
./scripts/clone-repos.sh                                 # repos/backend, ai, frontend, infra, gitops
cd repos/ai && uv sync --all-packages
```

- 계약 테스트는 작업 공간 구조(`project/repos/ai`의 두 단계 위 `service-contracts/`)를 기본으로 읽는다. 구조가 다르면 `CONTRACTS_DIR`을 준다.
- 로컬 비밀값 `local/.env`는 git에 없다. `local/.env.example`을 복사해 사용자가 직접 값을 채운다. **에이전트는 `.env`·`.env.*`를 읽지 않는다.**

### 1.3 git에 없는 사용자 파일 (직접 옮겨야 함)

아래는 사용자 개인 자료라 커밋하지 않는다. 새 컴퓨터에는 사용자가 직접 복사한다. 에이전트는 이 파일을 커밋하지 않는다.

| 경로 | 내용 |
| --- | --- |
| `references/` | 개인 작업 메모(검토 기록·작업 계획). 커밋하지 않는다. 설계 원본은 `architecture/legacy/design-origin-v2.md`·`.html`로 옮겼다 |
| `17서비스 VLM 아키텍처.md` | 이전 설계 원본 |
| `docs/architecture/rationale.md` | 사용자 작성 중 문서(추적하지 않음) |
| `docs/architecture/benchmarks/` | 측정 보고서(커밋하지 않음, 4.6절) |
| 루트의 `*.html` | 사용자 자료 |

## 2. 담당 범위

### 2.1 다른 담당자 서비스 (작업·제안·질문 금지)

| 서비스 | 레포 |
| --- | --- |
| pipeline-service | backend |
| analysis-api, analysis-loader | backend |
| search-service | backend |
| notification-service | backend |
| chunk-processor | ai (`services/chunk-processor`) |

- 이 서비스들의 작업을 제안하거나, 다음 단계를 안내하거나, 확인 질문을 하지 않는다(사용자 지시: "앞으로 나한테 묻지마").
- 이 서비스와 맞물리는 계약은 아키텍처 문서(`architecture.md`)와 머지된 계약을 기준으로 맞춘다. 어긋나면 사용자에게만 보고한다.
- **2026-11-06 결정**: 이 서비스들이 생산하는 이벤트·API 중 내 서비스가 입력으로 쓰는 것은 내가 아키텍처 문서대로 계약을 먼저 작성한다. 계약 설명에 "생산자 담당자 확인 필요"를 적는다. 생산자가 나중에 바꾸면 소비 쪽을 맞춘다.

### 2.2 내 담당 (사용자가 진행)

그 밖의 모든 서비스다. docs의 ADR-0009·서비스 카탈로그가 normalize를 "backend" 담당으로 적었어도 normalize는 내 범위다.

| 서비스 | 레포 | 상태(2026-11-06) |
| --- | --- | --- |
| api-gateway, auth-service, media-service | backend | SPEC-001·003·006·017·018 Implementing |
| frontend | frontend | SPEC-002·005·006 화면 Implementing. 나머지 화면(SPEC-031~035)은 plan·tasks까지 머지 |
| normalize | ai | SPEC-007 Implementing |
| ai-gateway | ai | SPEC-009·011·012·016 Implementing, SPEC-020 R-20(`event_judge_escalate`) 완료 |
| frame-encoder | ai | SPEC-019 Implementing |
| event-analyzer | ai | SPEC-020 벡터 후보 경로 구현·머지(ai #38). 탐지기 후보 경로(SPEC-023)는 plan·tasks까지 머지. v5.1 추가 요구(SPEC-020 R-21~22, SPEC-023 R-17~24)는 plan·tasks에 반영(ai #43) |
| track-stitcher, track-analyzer, embedding-worker, grounding-worker, aggregator | ai | spec·계약·plan·tasks 머지. v5.1 추가 요구(SPEC-022 R-23, SPEC-027 R-25~34, SPEC-028 R-19)는 plan·tasks에 반영(ai #43). 구현 전 결정은 6절 |
| quality-service | backend | spec·계약·plan·tasks 머지. v5.1 추가 요구(SPEC-029 R-27~28, 계약 2.0.0)는 plan·tasks에 반영(backend #53). 구현 전 결정은 6절 |
| stream-service | backend | SPEC-036 Approved(v5.1, ADR-0015). plan·구현은 Phase 2, 사용자 지시 뒤 |
| stream-ingestor | ai | SPEC-037 Approved(v5.1, ADR-0015). plan·구현은 Phase 2, 사용자 지시 뒤 |
| infra, gitops | infra, gitops | **사용자가 지시할 때만** 작업한다 |

### 2.3 AI 모델·학습은 별도 담당자

- 내 범위는 **서버 구조**다: 계약, 토픽, 프로필 스키마, 저장·보존 구조, 잡 실행 틀, 세션 모델, Adapter 인터페이스.
- 별도 AI 담당자 몫: 모델 선택, 탐지기 파인튜닝, 프로토타입 문장·임계값, 클래스 대응표 내용, 데이터셋 선정·라벨링, 평가 스위트 내용, **프롬프트 문안**.
- 문서에서는 "AI 담당자 몫"이라고 표시만 하고 내용을 제안하지 않는다. 프롬프트·프로필은 동작 확인용 자리값만 둔다.
- 프로젝트 목표 우선순위: 1차 기본 탐지 성능(Construction Safety·Warehouse·Fire/Smoke GT) → 2차 영상 기반 위험 이벤트 평가(Safe & Unsafe Behaviours 등) → 3차 작업 전후 안전시설 제거·이동·장비 방치·미복구·후속 위험 노출 → 최종 예측.

## 3. 사용자가 정한 작업 원칙

| 원칙 | 내용 | 정한 날 |
| --- | --- | --- |
| 단계마다 머지 | ADR, spec, 계약, plan, 구현 묶음마다 PR → CI 통과 → squash merge를 **직접** 한 뒤 다음 단계로 간다. 팀원 리뷰는 기다리지 않는다. 쌓인 브랜치는 앞 PR 머지 뒤 main을 merge해서(강제 push 없이) 다음 PR을 연다 | 2026-11-02 |
| 하위호환 안 남김 | 개발 단계라 계약·설정 형식을 바꿀 때 이전 버전을 남기지 않고 새 형식으로 바로 옮긴다. 다른 레포 CI가 깨지지 않게 변경 순서(소비 쪽 먼저)만 맞춘다. 근거 `architecture/legacy/v4-transition.md` 결정 6 | 2026-11-04 |
| gRPC 안 씀 | 서비스 간 동기 호출은 HTTP/1.1 + JSON(ADR-0002, 아키텍처 11.1절 내부 동기 호출 규약). gRPC를 다시 제안하지 않는다 | 2026-11-06 |
| 내부 호출 클라이언트는 생성 | 내부 호출 클라이언트는 OpenAPI 계약에서 빌드 때 생성한다. Python은 datamodel-code-generator(요청·응답 모델 생성) + 얇은 httpx 호출부, Java는 openapi-generator Gradle 플러그인. 손으로 쓴 요청·응답 모델은 두지 않는다. 지금의 `libs/ai-client` 손 작성 모델은 SPEC-021에서 생성 모델로 바꾼다(구현 전) | 2026-11-06 |
| 내부 호출 재시도·마감 | 호출자는 `X-Request-Deadline`(epoch ms)을 넣고 받는 쪽은 남은 시간이 없으면 504. 읽기 전용(parse·embed·analysis-api 읽기)은 503·연결 실패에 2회 지수 백오프 재시도. **analyze(VLM)는 연결 실패만 재시도**하고 502·503·시간 초과는 바로 `unknown`으로 기록 | 2026-11-06 |
| 측정 보고서는 커밋 안 함 | 벤치마크·성능 측정 보고서는 로컬 파일로만 쓰고 경로만 알린다. tasks.md의 짧은 "측정 기록" 절은 예외로 커밋한다(SPEC-019·020 선례) | 2026-11-06 |
| 질문은 꼭 필요할 때만 | 새 라이브러리, 계약 변경, DB 스키마 변경, 새 서비스 추가는 사용자에게 먼저 확인한다(루트 `AGENTS.md`). 합의된 범위 안의 커밋·push·PR·머지는 다시 묻지 않는다 | — |
| 답변은 한국어 | 사용자에게 보이는 답변은 모두 한국어다. 코드·명령·경로·로그 인용만 원문 | — |

## 4. 작업 요령 (이번까지 겪은 함정)

### 4.1 SDD 순서

1. docs: spec(`/sdd-spec`) + 계약 → PR → 상태 `Approved`로 머지
2. 계약을 바꿨으면 `service-contracts/VERSION`을 올린다(추가는 minor, 깨짐은 major + ADR). main 머지 후 CI가 릴리스 `service-contracts-v<버전>`을 만든다. `gh release list -R p5-3-final/docs`로 확인한다
3. 각 레포: `scripts/fetch-service-contracts.sh --update <버전>`(ai) 또는 레포의 같은 스크립트로 잠금 갱신 → plan·tasks(`/sdd-plan`) → TDD 구현(`/sdd-implement`) → PR → 머지
4. 첫 구현 PR을 열면 docs에서 spec 상태를 `Implementing`으로, 배포까지 끝나면 `Done`으로 바꾼다(`docs/specs/README.md` 목록도 같이). Done은 배포 후에만

### 4.2 TDD 보고

- Red는 기능이 없어서 실패한 것만 인정한다. import 오류·수집 오류는 Red가 아니다. 새 모듈은 인터페이스만 둔 뼈대(`raise NotImplementedError`)를 먼저 만들고 테스트를 돌린다.
- `pytest.mark.parametrize` 인자에서 아직 없는 함수를 부르면 수집 오류가 난다. 테스트 안에서 값을 만든다.
- 구현 뒤에 쓴 통합 테스트(Kafka e2e 등)는 "Red 없음"이라고 PR에 그대로 적는다.

### 4.3 ai 레포

- lefthook이 설치돼 있지 않으면 커밋 전에 `uv run ruff check . && uv run ruff format --check . && uv run mypy`를 직접 돌린다.
- 테스트 파일 이름은 레포 전체에서 겹치면 안 된다(mypy가 하이픈 폴더의 테스트 모듈을 파일 이름으로만 구분). `test_<서비스 약칭>_*.py`로 짓는다. 서비스 테스트에서 여러 파일이 쓰는 도우미는 `<약칭>_support.py`로 두고 루트 `pyproject.toml`의 `pythonpath`에 그 서비스 `tests/`를 더한다. 서비스 `tests/`에는 `conftest.py`를 두지 않는다(ai-gateway·libs는 예외로 이미 있음).
- 새 멤버는 루트 `pyproject.toml`의 `members`, `[tool.mypy] files`·`mypy_path`, `[tool.pytest.ini_options] pythonpath`에 모두 더한다.
- `# type: ignore`·`# noqa`는 코드와 **실제 이슈 번호**가 있을 때만 쓴다. 타입을 맞춰서 없애는 것이 먼저다.
- 외부 HTTP 테스트는 httpx 내장 `MockTransport`를 쓴다(respx는 추가하지 않았다).
- 서비스 이미지 테스트: `scripts/test-in-docker.sh <서비스>`. CI `service-images` job에 runtime 이미지 빌드 단계를 서비스마다 더한다.
- ai-gateway 새 taskType = `services/ai-gateway/registry/prompts/<taskType>/`(prompt.md, input·output 스키마와 예시, fallback.json) + 두 로컬 프로필의 `[tasks.<taskType>]` + 테스트 도우미 `gateway_support.profile()`의 tasks. 프로필과 Registry의 taskType 목록이 다르면 기동에 실패한다(`check_tasks`).
- 다른 레포로 나가는 출력 형식은 계약 `service-contracts/events/_*.schema.json`이 원본이고 Registry가 참조한다(`_vlm-analysis` 선례: 테스트 `conftest.py`의 registry 배치, `registry_bundle._REGISTRY_FOLDERS`, Dockerfile COPY 세 곳을 같이 고친다).

### 4.4 docs 레포

- 계약을 바꾸면 `oasdiff breaking`의 기준은 main 계약이다. 상대 `$ref` 때문에 스크래치 폴더에 파일 하나만 복사하면 읽지 못한다. `git archive origin/main service-contracts | tar -x -C <임시 폴더>`로 통째로 꺼내 비교한다.
- ai-gateway OpenAPI의 `TaskType`·`EmbedTaskType`은 `x-extensible-enum`이다(ADR-0014). 값 추가는 minor다. `pattern`을 더하면 요청 쪽 breaking으로 잡힌다.
- docs 레포 CI는 경로 필터가 있어 `local/`·`docs/specs/`만 바꾼 PR에는 체크가 하나도 붙지 않는다. 이때는 로컬에서 markdownlint·lychee를 돌리고 `gh pr view <번호> --json mergeStateStatus`가 `CLEAN`이면 머지한다.
- `sleep`은 막혀 있다. CI는 `gh pr checks <번호> --watch --interval 30`으로 기다린다.
- `.claude/rules/`·`.claude/skills/`를 고치면 `./scripts/sync-agent-config.sh`로 `.agents/`를 같이 갱신한다.

### 4.5 커밋·PR

- 커밋: `<type>(<scope>): <한국어 설명>`, 본문 끝에 `Refs: SPEC-NNN`, 그리고 `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- PR 본문: 요약, spec 링크, 충족한 요구사항 체크리스트, 판단한 점, 검증 결과(실패는 실패라고), TDD Red·Green 요약, 검사 예외, 마지막 줄 `🤖 Generated with [Claude Code](https://claude.com/claude-code)`.
- force push, main 직접 push, 보호 규칙 우회, 검사 기준 완화는 하지 않는다.

### 4.6 로컬 compose

- `docker compose -f local/docker-compose.yml up -d <서비스>`. 워커를 추가하면 `kafka-init` 토픽 목록(재시도 `{토픽}.{그룹}.retry`, DLQ `{그룹}.dlq` 포함)과 `local/README.md` 표를 같이 고친다.
- 메모리 상한은 아키텍처 18.1절 표를 따른다(나머지 워커 256M).
- SeaweedFS 키는 `local/seaweedfs/s3.json`의 로컬 전용 샘플값이다(비밀값 아님).

## 5. 이어서 할 일

문서는 모두 머지했다. 기준은 아키텍처 v5.1(ADR-0015~0017)과 계약 묶음 4.0.0이다. v5.1로 늘어난 요구사항은 각 레포 plan·tasks에 반영했다(ai #43, backend #53, frontend #35. SPEC-013·016·019·020은 구현이 끝난 spec이라 추가 태스크만 남았다). 계약 lock은 아직 ai 3.0.0, backend 2.9.1, frontend 2.0.1이고 각 plan의 첫 태스크(T001 또는 SPEC-021)가 깨지는 계약 테스트와 함께 4.0.0으로 올린다. 아래 순서로 구현한다. 앞의 것이 뒤의 입력을 만든다.

1. 6절의 사용자 결정(D-*)을 받고, "먼저 고칠 것"(C-1~C-4)과 정리할 계약 수정을 docs PR 하나로 반영한다(계약 묶음 minor·patch).
2. SPEC-021(ai): 계약 lock 4.0.0으로 올리기(기존 계약 테스트 4건을 같이 맞춤), ai-gateway 마감, 생성 클라이언트, 재시도 규칙, embed·parse
3. SPEC-024 track-analyzer → SPEC-025 embedding-worker → SPEC-023 event-analyzer 탐지기 경로 → SPEC-022 track-stitcher → SPEC-026 grounding-worker → SPEC-027·028 aggregator
4. SPEC-029·030 quality-service(backend), SPEC-030 evals(ai)
5. SPEC-031~035 frontend(SPEC-031 T001에서 lock·생성 코드 갱신)
6. 각 서비스 로컬 compose 추가와 측정
7. Phase 2 실시간: SPEC-036 stream-service(backend) → SPEC-037 stream-ingestor(ai). 사용자 지시 후
8. 운영 배포(infra·gitops)는 사용자 지시 후

- 레포마다 plan의 "의존" 절을 먼저 읽는다. 두 plan이 같은 준비 태스크(lock 올리기 등)를 가리키면 먼저 구현하는 쪽이 한다.
- 다른 담당자 서비스의 계약(생산자 확인 필요)을 생산자가 바꾸면 소비 쪽 plan·코드를 맞춘다.

## 6. 구현 전에 정할 사항

plan을 쓰며 나온 결정 사항과 spec·계약 불일치다.

- 각 plan에는 기본안이 이미 적혀 있다. 사용자가 다르게 정하지 않으면 기본안대로 구현한다.
- "계약·spec 수정"은 구현 전에 docs PR을 먼저 연다.
- 정한 항목은 이 표의 "결정" 칸을 채우고 해당 plan을 같은 흐름에서 고친다.

### 6.1 사용자 결정이 필요한 항목

| # | spec | 항목 | 기본안 | 결정 |
| --- | --- | --- | --- | --- |
| D-1 | SPEC-026 | grounding 탐지기 실행 라이브러리 | 미정. `ultralytics`(AGPL-3.0, 구현 가장 짧음), `onnxruntime`(ONNX 내보내기·가중치 라이선스 확인 필요, AI 담당자 작업), `transformers` OWLv2(CPU에서 느림) 중 선택. 결정 전에는 `MockDetector`로 R-1~R-18을 구현하고 실제 탐지기 태스크(T026~T028, T033)는 보류 | |
| D-2 | SPEC-026 | 영상 처리 | FFmpeg·ffprobe 프로세스 호출. runtime 이미지에 `ffmpeg`, `fonts-dejavu-core`(drawtext용)를 넣음 | |
| D-3 | SPEC-021 | 생성 코드의 `Any` | 계약의 자유 객체(`variables`, `output`)가 `dict[str, Any]`로 생성되면 생성 파일만 `Any` 금지의 예외로 문서화 | |
| D-4 | SPEC-021 | 생성 코드 검사 예외 | 생성 결과가 ruff·mypy를 통과하지 못하면 생성 파일 경로를 설정 단위 예외로 둠(`lint.md`에 추가 필요) | |
| D-5 | SPEC-021 | datamodel-code-generator 하위 의존성 | 개발 의존성으로만 lock에 추가 | |
| D-6 | SPEC-022 | numpy 직접 의존 | 표준 라이브러리로 계산하고, NFR-1(30초)을 넘으면 numpy를 직접 의존으로 씀(lock에는 있음) | |
| D-7 | SPEC-022 | Re-ID 끄기 설정(`reidSkippedReason: disabled`) | 두지 않음 | |
| D-8 | SPEC-023 | 규칙 템플릿 범위 | 기동할 때 탐지 가능 유형 8종 모두에 템플릿·기본 severity를 요구 | |
| D-9 | SPEC-023 | 구역 이름이 null일 때 템플릿 값 | 프로필 `[rule_text] missing_zone_name` | |
| D-10 | SPEC-023 | 근거 프레임 경로 검사 | `event.candidate` 근거 프레임이 메시지 실행 폴더 안인지 계약 모델에서 검사 | |
| D-11 | SPEC-024 | 이미지 하한 | ai-gateway 프로필 스키마에 `min_images`(기본 0)를 추가(프로필 스키마 변경). 결정 전 T009 보류 | |
| D-12 | SPEC-025 | 트랙 항목의 시각·클래스 출처 | track-stitcher 번역표(`tracks/v1/track-mapping`)를 읽음. 대안은 `track.analyzed`에 필드 추가(계약 변경) | |
| D-13 | SPEC-025 | 이벤트 시각 | spec R-7의 "초 단위 값은 ms로"는 계약에 늘 있는 `startMs`·`endMs`를 쓴다는 뜻으로 해석 | |
| D-14 | SPEC-025 | R-9에 없는 502·504·그 밖의 5xx | 재시도 토픽 | |
| D-15 | SPEC-027 | analysis-api 자리 표시 서버 | 미정. A 계약 기반 mock 도구(새 도구), B `libs/testing`에 작은 FastAPI 앱(기존 의존성), C 자리 표시 서버 없이 MockTransport 테스트만. 단위·e2e는 MockTransport라 구현을 막지 않음 | |
| D-16 | SPEC-027 | 직전 영상 `final-state`가 404 `ANALYSIS_SOURCE_NOT_FOUND` | 빈 초기 상태 | |
| D-17 | SPEC-028 | `not_restored` 판정 이미지(직전 영상 프레임을 ai-gateway가 받지 않음) | 미정. A aggregator가 프레임을 현재 job 폴더로 복사, B 계약 변경, C 이미지 1장 판정(spec 수정). 결정 전 T018 보류 | A(2026-11-07, 추천안으로 진행) |
| D-18 | SPEC-028 | `risk_forecast` 모델 미설정 결과 | `_risk-forecast`의 `horizons` 최소 개수를 0으로(계약 minor). 결정 전 T022 보류 | 기본안(4.1.0 반영) |
| D-19 | SPEC-028 | 규칙 점수 공식 | λ = 분당 진입 수/60 × min(1, 활성 초/saturation_s), p = 1 − exp(−λh). 실제 값·공식 교체는 AI 담당자 몫 | |
| D-20 | SPEC-028 | 호출 상한을 넘은 통로·위험구역 장비 방치 | `unverified`로 기록하고 상태 계산에서 뺌 | |
| D-21 | SPEC-030 | 상태 변화 종류 대응 | 라벨 `added`↔결과 `appeared`, `removed`↔`removed`, `moved`↔`moved`. `restored`·`not_restored`는 짝 없음 | |
| D-22 | SPEC-031 | SSE 처리 방식 | `fetch` 스트림 + 직접 만든 해석기(새 의존성 없음). 이유: `EventSource`는 `Last-Event-ID`를 못 넣고, 티켓이 1회용이라 자동 재연결이 실패함. 대안은 계약에 `lastEventId` 쿼리 추가 | |
| D-23 | SPEC-031·032 | 자체 플레이어 컨트롤 | 이벤트 표시·클릭 조회를 위해 기본 컨트롤 대신 직접 만듦(SPEC-006 화면 모양이 바뀜) | |
| D-24 | SPEC-032·035 | 다각형 편집·추이 그래프 | 새 라이브러리 없이 SVG로 직접 | |
| D-25 | frontend | 개발용 mock 모드 | `VITE_API_MOCKING=true`일 때만 MSW 브라우저 워커(기존 의존성), `public/mockServiceWorker.js` 커밋 | |
| D-26 | SPEC-030 | Resilience4j 도입(quality → media 첫 서비스 간 호출) | backend AGENTS.md는 서비스 간 호출에 Resilience4j를 쓰라고 하지만 아직 쓰는 곳이 없다. 결정 전에는 T009의 재시도 부분을 보류 | |
| D-27 | SPEC-029 | 생성 코드가 `-Werror`에 걸릴 때 | 생성 소스만 lint를 완화하는 설정 단위 예외(`lint.md`에 추가 필요). T003에서 실제로 걸리는지 확인한 뒤 묻는다 | |
| D-28 | SPEC-029 R-24 | 추이 조회에 `versionKey`만 있을 때 | 400 | |
| D-29 | SPEC-030 | media 보존 등급 `DATASET`의 삭제 동작 | 이번에는 등급만 저장한다. 운영자가 삭제할 때 `video.deleted`를 낼지 막을지는 미정 | |
| D-30 | SPEC-030 | 같은 매니페스트 다시 가져오기 | importId를 manifestKey로 결정적으로 만들어 같은 videoId를 보장한다. 대신 같은 경로의 가져오기 이력은 한 행에 덮어쓴다 | |

### 6.2 spec·계약 수정이 필요한 항목

먼저 고칠 것(구현을 막음)

| # | spec·계약 | 문제 | 수정안 |
| --- | --- | --- | --- |
| C-1(4.1.0 반영) | SPEC-022, `tracks/v1/chunk-tracks` | `boundaryBoxes`가 겹침 구간 박스만 담는다. 그래서 앞 청크 박스는 경계 뒤 5초에만, 뒤 청크 박스는 경계 앞 5초에만 있어 공통 관측이 거의 없다. IoU 연결(R-4·R-6)이 동작하지 않는다 | 박스를 경계 양쪽 창 전체로 넓힌다. 생산자가 chunk-processor라 생산자 확인 필요 표시를 유지한다. plan은 고친 계약을 전제로 쓰였다 |
| C-2(4.1.0 반영) | SPEC-022, `track.detected` `stitched` | "앞 청크에서 이미 이어진 구성원도 포함"이라는 설명 때문에 도착 순서에 따라 내용·trackId가 달라진다. US-1 AC3·NFR-2와 충돌한다 | 쌍의 두 구성원만 담는다. 여러 경계를 잇는 묶음은 manifest 번역표가 정한다 |
| C-3(4.1.0 반영) | SPEC-028 R-7 | 직전 영상 프레임(`sources/<previousSourceId>/`)을 ai-gateway가 받지 않는다(D-17) | D-17을 정한 뒤 spec이나 계약을 고친다 |
| C-4(4.1.0 반영) | `_risk-forecast` | `horizons` 최소 1개라 모델 미설정 `fallback.json`을 만들 수 없다(D-18) | `minItems: 0` |

정리할 것(구현은 기본안으로 진행)

| # | 대상 | 문제 | 수정안 |
| --- | --- | --- | --- |
| C-5 | SPEC-025 제외 항목 | "같은 항목·다른 모델이면 다른 파일"이라고 적었지만 경로·`vectorKey`에 모델이 없어 덮어쓴다 | spec을 "eventId만 다르고 파일은 마지막 모델 결과로 덮어씀. 모델 교체 중 공존은 REEMBED spec에서"로 고치거나 경로에 모델 단계를 넣는다(계약 변경) |
| C-6 | SPEC-025 R-9 | `AI_MODEL_NOT_CONFIGURED`는 503이라 ai-client가 2회 헛재시도한 뒤 DLQ로 간다 | 그대로 두거나 SPEC-021 R-10에서 이 코드를 재시도하지 않게 한다 |
| C-7 | 서비스 카탈로그 embedding-worker 행 | 저장소 "—", "묶음" 임베딩으로 적혀 spec(S3 저장, 묶음 제외)과 다르다 | 카탈로그를 고친다 |
| C-8 | SPEC-026 R-17 | `grounding.completed`에 기준 신뢰도를 기록하라고 하지만 계약에 필드가 없다 | R-17을 결과 파일만으로 줄인다 |
| C-9 | SPEC-026 R-9 | eventId가 groundingId·탐지기 버전뿐이라, FAILED 뒤 READY나 다른 requestId의 결과가 같은 eventId가 된다 | eventId에 requestId·outcome을 넣는다 |
| C-10 | SPEC-026 R-10 | 영상 길이 비교에 허용 오차가 없다 | 프레임 간격 하나만큼 넘는 것은 허용한다 |
| C-11 | `groundings/v1` `sampleFps` | 이름은 fps인데 설명은 "간격"이다 | 설명을 "초당 샘플 수"로 고친다(patch) |
| C-12 | 모델 manifest(`models/`) | `kind: detector`가 `classes` 1개 이상을 요구한다. 개방 어휘 탐지기 manifest를 어떻게 쓸지 정해지지 않았다 | AI 담당자와 정한다 |
| C-13(AsyncAPI 4.1.0 반영) | `event.manifest`·AsyncAPI·`detectorCandidate` 설명 | 요구사항 번호가 틀렸다(R-12→R-10, R-10→R-9) | 설명을 고친다(patch) |
| C-14 | `track.manifest` 설명 | "SPEC-022 R-10~R-14"가 spec과 맞지 않는다 | R-12·R-13으로 고친다 |
| C-15 | `event.manifest` 크기 | 후보 20,000개면 `analyzedEventIds`가 약 0.8MB라 Kafka 기본 상한 1MB에 가깝다 | 운영 토픽 `max.message.bytes`를 확인하거나 상한을 줄인다 |
| C-16 | SPEC-021 R-1·R-3 | 마감을 반영할 "외부 모델" 범위가 모호하다 | plan은 공급자 Adapter 경로에만 반영하고, 인코더 경로는 받을 때 검사만 한다. 마감 초과 504는 호출 로그에 남기지 않는다. 의도와 다르면 spec을 고친다 |
| C-17 | `openapi/ai-gateway.yaml` `/v1/parse` | 503 응답이 없는데 R-10은 parse 503 재시도를 요구한다 | 인프라 503으로 보고 재시도한다. 계약에 503을 더할지 정한다 |
| C-18 | quality-service `/internal/v1/quality/stage-gates` | `X-Request-Deadline` 헤더가 없다(내부 호출 규약) | 계약에 헤더를 더한다(minor) |
| C-19 | SPEC-029·SPEC-030 | 평가 잡 본체(Golden Set 읽기, 예측 모으기, 결과 제출)를 맡은 ai spec이 없다 | evals 평가 잡 spec을 새로 쓴다 |
| C-20 | `notifications/v1/notification-message` | OpenAPI가 참조하지 않아 생성 타입이 없다 | frontend는 Zod로 옮기고 예시 파싱 테스트를 한다. 생성하려면 계약에서 참조를 더한다 |
| C-21 | analysis·quality OpenAPI의 `type: object` 필드(`analysis`, `forecast`, `attributes`, `answer`) | 생성 타입이 비어 있다. 검사 도구가 `$id` 기준 상대 `$ref`를 풀지 못해 `object`로 둔 것이다 | frontend는 events JSON Schema를 Zod로 옮긴다. 계약을 `$ref`로 바꾸려면 검사 도구 문제를 먼저 푼다 |
| C-22 | SPEC-031 R-15 | 화면을 열 때 이미 분석 중이면 다음 `job.status`가 올 때까지 진행률을 알 수 없다 | 진행 상태 공개 API(pipeline, 다른 담당자)가 필요하다 |
| C-23 | 분석 결과 좌표·시각 | 정규화 사본 기준인데 플레이어는 원본을 재생한다 | 같은 타임라인·비율로 가정한다. 어긋나면 HLS(정규화) 재생으로 바꾼다 |
| C-24 | SPEC-031 | 진행 막대 표시가 요약 `timeline`에 모든 이벤트가 있다고 가정한다 | analysis 계약 설명에 명시한다 |
| C-25 | SPEC-033 R-7 | 검색 결과에 영상 이름이 없어 결과마다 `getVideo`를 부른다 | search 계약에 `fileName`을 더하는 것을 검토한다 |
| C-26 | SPEC-033 | "이 영상" 범위의 영상 고르기가 spec에 없고, 주석 `frames[].ptsMs` 기준(원본·클립)이 계약에 없다 | plan 기본안(내 READY 영상 고르기, 원본 기준)으로 진행하고 계약 설명을 고친다 |
| C-27 | SPEC-034 | "확정 이벤트"를 판정 `confirmed`로 가정했다. 규칙·재고 이벤트가 `confirmed`로 저장되는지 계약에 없다 | analysis 계약 설명에 명시한다 |
| C-28 | SPEC-035 R-17·R-19 | 특징 내보내기 목록 API가 없다 | quality 계약에 목록 API를 더한다(minor, 내 서비스) |
| C-29 | SPEC-035 | uncertain 라벨과 라벨 없음이 같은 409 코드다 | `QUALITY_REVIEW_UNCERTAIN` 코드를 나눈다 |
| C-30 | quality `GateResult.failures[].value` | 기준에만 있는 지표(R-18)는 값이 없는데 필드가 필수 number다 | `number`·`null`로 바꾼다(backend SPEC-029 T025 대기) |
| C-31 | 가져오기 매니페스트·`RegisterDatasetVideoRequest`의 `video/webm` | `video.uploaded`·media 파일 정책은 webm을 받지 않는다 | media가 400으로 거절하고 영상별 오류로 남긴다. 계약 enum에서 webm을 뺄지 정한다 |
| C-32 | media `registerDatasetVideo` 400 코드 이름 | 기존 코드는 `MEDIA_UNSUPPORTED_FORMAT`·`MEDIA_FILE_SIZE_INVALID`다 | 계약 설명을 기존 코드로 고친다 |
| C-33 | media `registerDatasetVideo` | `X-Request-Deadline`·504가 없다 | 계약에 더한다 |
| C-34 | quality 계약 설명의 요구사항 번호, `ReviewItem` 예시 | 번호가 틀렸다(R-8→R-9, R-12~R-15→R-13~R-15). 예시 `judgments_disagree`가 이벤트 enum `judgment_disagreement`와 다르다 | 설명과 예시를 고친다(patch) |
| C-35 | backend Docker 이미지 빌드 | 빌드 컨텍스트에 계약 파일이 없어 생성 코드를 빌드하지 못한다 | `CONTRACTS_DIR` 빌드 인자(SPEC-029 T037) |
