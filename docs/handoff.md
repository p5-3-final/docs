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
| `references/` | 설계 원본(`검색·이벤트 VLM 아키텍처_v2.md`·`.html`). overview·ADR-0008이 이 문서에서 왔다 |
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
- 이 서비스와 맞물리는 계약은 아키텍처 문서(`overview.md`)와 머지된 계약을 기준으로 맞춘다. 어긋나면 사용자에게만 보고한다.
- **2026-11-06 결정**: 이 서비스들이 생산하는 이벤트·API 중 내 서비스가 입력으로 쓰는 것은 내가 아키텍처 문서대로 계약을 먼저 작성한다. 계약 설명에 "생산자 담당자 확인 필요"를 적는다. 생산자가 나중에 바꾸면 소비 쪽을 맞춘다.

### 2.2 내 담당 (사용자가 진행)

그 밖의 모든 서비스다. docs의 ADR-0009·서비스 카탈로그가 normalize를 "backend" 담당으로 적었어도 normalize는 내 범위다.

| 서비스 | 레포 | 상태(2026-11-06) |
| --- | --- | --- |
| api-gateway, auth-service, media-service | backend | SPEC-001·003·006·017·018 Implementing |
| frontend | frontend | SPEC-002·005·006·007 화면 Implementing. 나머지 화면은 7절 |
| normalize | ai | SPEC-007 Implementing |
| ai-gateway | ai | SPEC-009·011·012·016 Implementing, SPEC-020 R-20(`event_judge_escalate`) 완료 |
| frame-encoder | ai | SPEC-019 Implementing |
| event-analyzer | ai | SPEC-020 벡터 후보 경로 구현·머지(ai #38). 탐지기 후보 경로는 7절 |
| track-stitcher, track-analyzer, embedding-worker, grounding-worker, aggregator | ai | 문서 작성 중(7절) |
| quality-service | backend | 문서 작성 중(7절) |
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
| 하위호환 안 남김 | 개발 단계라 계약·설정 형식을 바꿀 때 이전 버전을 남기지 않고 새 형식으로 바로 옮긴다. 다른 레포 CI가 깨지지 않게 변경 순서(소비 쪽 먼저)만 맞춘다. 근거 `architecture/v4-transition.md` 결정 6 | 2026-11-04 |
| gRPC 안 씀 | 서비스 간 동기 호출은 HTTP/1.1 + JSON(ADR-0002, overview "통신 규칙" 내부 동기 호출 규약). gRPC를 다시 제안하지 않는다 | 2026-11-06 |
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
- 메모리 상한은 overview "로컬 개발 환경" 표를 따른다(나머지 워커 256M).
- SeaweedFS 키는 `local/seaweedfs/s3.json`의 로컬 전용 샘플값이다(비밀값 아님).

## 5. 구현 완료 기록 (2026-11-06 기준)

| 영역 | 내용 | 레포 PR |
| --- | --- | --- |
| 계약 묶음 | 3.0.0 (ai-gateway OpenAPI 1.0.0, `event.analyzed`, `_vlm-analysis`) | docs #109 |
| event-analyzer | 벡터 후보 판정·재판정·발행, 재시도, DLQ, 단계 측정 | ai #38, #39 |
| libs/ai-client | `/v1/analyze` REST 클라이언트(재시도 포함). `/v1/embed`·`/v1/parse` 메서드는 아직 없음 | ai #38 |
| 로컬 compose | event-analyzer, 토픽 | docs #113 |

## 6. 이어서 할 일

7절의 문서를 모두 머지한 뒤 아래 순서로 구현한다. 앞의 것이 뒤의 입력을 만든다.

1. ai-gateway 새 taskType(track_attribute, object_question, source_summary, state_compare, risk_forecast)과 `libs/ai-client` `/v1/embed`
2. track-analyzer → embedding-worker → event-analyzer 탐지기 경로 → track-stitcher → grounding-worker → aggregator
3. quality-service(backend)
4. frontend 화면
5. 각 서비스 로컬 compose 추가와 측정
6. 운영 배포(infra·gitops)는 사용자 지시 후

## 7. 문서 작성 현황

2026-11-06에 사용자가 "담당 서비스 전부 문서부터 작성하고 한 번에 구현"하기로 했다. 범위: ai 워커 6개, quality-service, frontend 나머지 화면. 깊이: spec + 계약 + 각 레포 plan·tasks.

| spec | 대상 | 상태 |
| --- | --- | --- |
| SPEC-021 | 내부 동기 호출 규약 적용(ai-gateway `X-Request-Deadline`·504, ai-client 생성 모델·재시도 규칙·embed·parse) | Approved |
| SPEC-022 | track-stitcher(`chunk.boundary`·`track.detected`·`track.manifest`, 트랙 파일 2종 계약 포함) | Approved |
| SPEC-023 | event-analyzer 탐지기·규칙 후보(`event.candidate`·`event.manifest`, `event.analyzed` 판정 방식 `rule*`) | Approved |
| SPEC-024 | track-analyzer(`attribute.requested`·`track.analyzed`, ai-gateway `track_attribute`·`object_question`, 트랙 요약 파일 대표 크롭) | Approved |
| SPEC-025 | embedding-worker(`segment.annotated`·`embedding.ready`, 텍스트 벡터 파일) | Approved |
| SPEC-026 | grounding-worker(`grounding.requested`·`grounding.completed`, 결과 파일 `groundings/v1`) | Approved |
| SPEC-027 | aggregator 핵심(`analysis.completed`·`source.completed`, analysis-api 내부 읽기 API, 결과 파일, `source_summary`) | Approved |
| SPEC-028 | aggregator 정적 객체 재고 비교·장비 방치·예측(`chunk.manifest`, 청크 재고 파일, ai-gateway `state_compare`·`risk_forecast`) | Approved |
| SPEC-029 | quality-service 핵심(검토 큐, Golden Set 버전, 평가 실행·CI Gate, 처리 단계 리포트, `openapi/quality-service.yaml`) | Approved |
| SPEC-030 | quality-service 데이터셋 가져오기·라벨 3종·temporal IoU·특징 내보내기·성능 Gate(media 내부 등록 API 포함) | Approved |
| SPEC-031 | frontend 분석 결과(요약·이벤트·위험·스냅샷, 이벤트 메뉴)와 실시간 알림. analysis-api 공개 API 1부·notification SSE 계약 초안 | Approved |
| SPEC-032 | frontend 클릭 조회·오버레이·객체 질문·위험구역 편집. analysis-api 공개 API 2부 계약 초안 | Approved |
| SPEC-033 | frontend 검색·RAG·주석 클립. search-service 공개 API 계약 초안 | Approved |
| SPEC-034 | frontend 작업 세션·분석 이력·설정(학습용 보존). 계약 변경 없음 | Approved |
| SPEC-035 | frontend 품질 화면(운영자) | 작성 예정 |

plan 단계에서 사용자에게 먼저 확인할 것(새 라이브러리 도입 규칙):

- grounding-worker(SPEC-026)의 개방 어휘 탐지기 실행 라이브러리. YOLOE의 공식 구현인 `ultralytics`는 AGPL-3.0이라 배포 형태에 따라 소스 공개 의무가 생긴다. 대안(ONNX로 내보낸 가중치를 `onnxruntime`으로 실행)과 함께 물어본다.
- quality-service(SPEC-029)는 backend의 새 서비스 모듈이다. catalog와 ADR-0008에 이미 있는 배포 단위라 새 서비스 결정은 아니다. 다만 모듈 뼈대(Flyway `quality_db`, 생성 코드 설정)는 기존 서비스와 같은 방식인지 plan에서 확인한다.
- aggregator(SPEC-027)는 analysis-api가 아직 없어 로컬에서 계약 예시로 응답하는 자리 표시 서버가 필요하다. 도구(예: 계약 기반 mock 서버)를 새로 들일지 테스트용 작은 HTTP 서버를 직접 둘지 확인한다.
- 영상 디코딩·인코딩. normalize는 FFmpeg·ffprobe 프로세스를 부르므로 같은 방식(새 라이브러리 없음)을 기본안으로 제안한다.

번호는 작성하면서 바뀔 수 있다. 실제 번호와 상태는 [spec 목록](specs/README.md)이 원본이다.
