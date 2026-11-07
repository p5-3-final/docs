# 로컬 compose E2E

`local/docker-compose.yml`로 띄운 전체 스택에 실제 영상을 넣고 서비스 사이 흐름을 확인하는 스크립트다. 단위·통합 테스트는 각 레포에 있고, 여기서는 레포 경계를 넘는 흐름만 본다.

## 준비

- `local/.env`를 `local/.env.example`에서 만든다. 테스트는 로그인 화면에 미리 채워지는 샘플 관리자 계정(`AUTH_ADMIN_*`, 기본 `admin@example.com`)으로 로그인한다. 값을 바꿨다면 `E2E_EMAIL`·`E2E_PASSWORD`로 같은 값을 넘긴다.
- `repos/ai`(uv), `repos/frontend`(`npm ci`, Playwright 브라우저)가 클론되어 있어야 한다.
- 영상: 기본값은 docs 레포 루트의 `video.mp4`다. git에 올리지 않으므로 각자 두거나 `E2E_VIDEO`로 경로를 넘긴다.
- 녹화에는 `ffmpeg`가 필요하다.

## 실행

```bash
scripts/e2e/run.sh up       # local/.env + compose.e2e.yml로 전체 프로필 기동
scripts/e2e/run.sh all      # upload → workers → quality → ui → record
```

| 단계 | 확인하는 것 |
| --- | --- |
| `upload` | 관리자 계정 로그인 → 멀티파트 업로드 → 정규화 완료(READY) → 재생 주소 |
| `workers` | ai 워커 다섯 흐름(벡터, 트랙 이어 붙이기, 트랙 속성, 주석 클립, 영상 단위 집계). 다른 담당자 서비스가 낼 메시지·파일은 ai 레포 테스트 도우미로 만든다 |
| `quality` | api-gateway를 거친 quality API 11건. OPERATOR 전용(SPEC-029 R-4)이라 역할별 계정을 새로 만든다 |
| `ui` | 화면에서 업로드 → 변환 → 상세 재생, OPERATOR 품질 검토 화면 |
| `record` | 화면 흐름과 워커 산출물을 녹화해 `out/flow-recording.mp4`로 저장 |

결과는 `scripts/e2e/out/`(git 제외)에 남는다. 다른 위치를 쓰려면 `E2E_OUT`을 지정한다.

- `workers`는 테스트 도우미의 고정 영상·소유자 ID를 `upload`에서 관리자 계정이 올린 영상과 그 계정 ID로 바꿔 넣는다. 같은 영상으로 여러 번 돌려도 흐름을 시작한 뒤의 메시지만 본다.
- `record`는 `upload`에서 분석한 영상을 웹에서 재생한 뒤 `out/results.html`(구간 프레임과 검색 순위, 트랙 속성, 주석 클립, 요약)을 보여 준다. 웹 화면은 분석 결과를 analysis-service·search-service에서 읽는데 로컬에 아직 없어서다.

## 실제 모델로 돌리기

기본은 모델 없이 흐름만 보는 mock 프로필이다. 실제 모델(MobileCLIP2-S0, 호스트 Ollama의 Qwen3-VL·bge-m3)로 돌리려면 `local/README.md`의 가중치 업로드와 `ollama pull`을 한 번 한 뒤 아래처럼 실행한다.

```bash
E2E_REAL_MODELS=1 scripts/e2e/run.sh up                                       # frame-encoder·ai-gateway를 local.toml로
E2E_REAL_MODELS=1 E2E_VLM_MODEL=qwen3-vl:8b-instruct scripts/e2e/run.sh up   # VLM만 다른 모델로(ollama pull 필요)
E2E_REAL_MODELS=1 scripts/e2e/run.sh all
```

- `E2E_REAL_MODELS=1`이면 `workers`가 테스트 도우미의 가짜 이미지 대신 영상에서 뽑은 실제 프레임(90초 간격 8구간, 110초 장면의 작업자 크롭)을 넣고, 검색 문장과 구간 벡터의 순위를 함께 낸다. 영상에서 프레임을 뽑는 chunk-processor가 아직 없어서다.
- `E2E_VLM_MODEL`은 이미지의 `local.toml`에서 VLM 모델 이름만 바꾼 사본을 `out/`에 만들어 ai-gateway에 마운트한다. ai 레포 프로필은 평가를 거쳐 바꾸므로 고치지 않는다.
- grounding-worker는 실제 탐지기가 아직 없어 mock이다(ai 레포 SPEC-026 T026~T028).

## 알려진 제약

- auth에 역할 변경 API가 없어 OPERATOR 계정은 로컬 auth DB의 role을 `docker exec`로 직접 바꾼다.
- analysis-api가 아직 없어 `compose.e2e.yml`이 aggregator를 호스트의 자리 표시 서버(8085)로 돌린다.
- 영상 목록은 정규화 완료 알림을 받지 않아 테스트가 새로 고침으로 상태를 확인한다.
