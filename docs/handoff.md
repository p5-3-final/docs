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

| 서비스 | 레포 | 상태(2026-11-07) |
| --- | --- | --- |
| api-gateway, auth-service, media-service | backend | SPEC-001·003·006·017·018 Implementing. media는 SPEC-030 데이터셋 영상 등록 구현(backend #55) |
| frontend | frontend | SPEC-002·005·006, SPEC-031~035 Implementing(frontend #36~#40). 계약 lock 5.0.0 |
| normalize | ai | SPEC-007 Implementing |
| ai-gateway | ai | SPEC-009·011·012·016·021 Implementing. SPEC-024 `min_images`, SPEC-027 `source_summary`, SPEC-028 `state_compare`·`risk_forecast`·`predictor` Adapter 반영 |
| frame-encoder | ai | SPEC-019 Implementing |
| event-analyzer | ai | SPEC-020·023 Implementing(ai #46) |
| track-stitcher, track-analyzer, embedding-worker, grounding-worker, aggregator | ai | SPEC-022·024·025·026·027·028 Implementing(ai #45~#50, #52). grounding 실제 탐지기(SPEC-026 T026~T028, T033)는 6절 D-1 대기 |
| quality-service | backend | SPEC-029·030 Implementing(backend #54·#55·#56). evals 매칭·Gate 명령은 ai #51 |
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

기준은 아키텍처 v5.1(ADR-0015~0018)과 계약 묶음 5.0.0이다. lock은 ai·backend·frontend 모두 5.0.0이다. SPEC-021~035의 구현 PR은 모두 머지했고 상태는 `Implementing`이다. 남은 일은 아래와 같다.

1. 로컬 compose 측정 태스크: SPEC-022 T034, SPEC-023 T025·T035, SPEC-024 T022, SPEC-025 T024·T025, SPEC-027 T043·T056 일부, SPEC-028 T030. compose 정의는 docs #142에 있다(`analysis`·`grounding`·`quality` profile). Docker Desktop 디스크가 차서 통합 실행을 하지 못했다.
2. 레포별 `.env.example` 갱신: 에이전트 권한 설정이 `.env*` 쓰기를 막아 각 README에만 적었다(ai embedding·grounding·track-analyzer·evals, backend quality·media, docs `local/` `QUALITY_DB_PASSWORD`).
3. 6절의 남은 결정과 계약 정리.
4. spec `Done`: 운영 배포(infra·gitops) 뒤. 사용자 지시 후.
5. Phase 2 실시간: SPEC-036 stream-service(backend) → SPEC-037 stream-ingestor(ai). 사용자 지시 후.

- 다른 담당자 서비스(chunk-processor, analysis-api·loader, search, notification)가 아직 생산하지 않는 이벤트가 있어 compose만으로 업로드 흐름이 끝까지 이어지지 않는다. 그 구간은 각 워커의 Kafka e2e 테스트(testcontainers, CI)로 확인한다.

## 6. 남은 결정과 계약 정리

plan을 쓰며 나온 결정 사항과 spec·계약 불일치다.

- 각 plan에는 기본안이 이미 적혀 있다. 사용자가 다르게 정하지 않으면 기본안대로 구현한다.
- "계약·spec 수정"은 구현 전에 docs PR을 먼저 연다.
- 정한 항목은 이 표의 "결정" 칸을 채우고 해당 plan을 같은 흐름에서 고친다.

### 6.1 사용자 결정이 필요한 항목

| # | spec | 항목 | 기본안 | 결정 |
| --- | --- | --- | --- | --- |
| D-29 | SPEC-030 | media 보존 등급 `DATASET`의 삭제 동작 | 등급만 저장했다(backend #55). 운영자가 삭제할 때 `video.deleted`를 낼지 막을지는 미정 | |

### 6.2 spec·계약 수정이 필요한 항목

구현은 기본안으로 진행했다. 아래는 계약·spec에 남은 정리 항목이다.

| # | 대상 | 문제 | 수정안 |
| --- | --- | --- | --- |
| C-11 | `groundings/v1` `sampleFps` | 이름은 fps인데 설명은 "간격"이다 | 설명을 "초당 샘플 수"로 고친다(patch) |
| C-12 | 모델 manifest(`models/`) | `kind: detector`가 `classes` 1개 이상을 요구한다. 개방 어휘 탐지기 manifest를 어떻게 쓸지 정해지지 않았다 | AI 담당자와 정한다 |
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
| C-31 | 가져오기 매니페스트·`RegisterDatasetVideoRequest`의 `video/webm` | `video.uploaded`·media 파일 정책은 webm을 받지 않는다 | media가 400으로 거절하고 영상별 오류로 남긴다. 계약 enum에서 webm을 뺄지 정한다 |
| C-32 | media `registerDatasetVideo` 400 코드 이름 | 기존 코드는 `MEDIA_UNSUPPORTED_FORMAT`·`MEDIA_FILE_SIZE_INVALID`다 | 계약 설명을 기존 코드로 고친다 |
| C-33 | media `registerDatasetVideo` | `X-Request-Deadline`·504가 없다 | 계약에 더한다 |
| C-34 | quality 계약 설명의 요구사항 번호, `ReviewItem` 예시 | 번호가 틀렸다(R-8→R-9, R-12~R-15→R-13~R-15). 예시 `judgments_disagree`가 이벤트 enum `judgment_disagreement`와 다르다 | 설명과 예시를 고친다(patch) |
