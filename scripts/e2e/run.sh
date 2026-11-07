#!/usr/bin/env bash
# 로컬 compose 스택에 E2E를 돌린다. 사용법은 scripts/e2e/README.md를 본다.
set -euo pipefail

E2E_DIR="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$E2E_DIR/../.." && pwd)"
AI_REPO="$ROOT/repos/ai"
FRONTEND_REPO="$ROOT/repos/frontend"
export E2E_OUT="${E2E_OUT:-$E2E_DIR/out}"
export E2E_VIDEO="${E2E_VIDEO:-$ROOT/video.mp4}"
mkdir -p "$E2E_OUT"

usage() {
  echo "사용법: $0 {up|upload|workers|measure|quality|ui|record|all}" >&2
  exit 2
}

# local/.env를 읽도록 --env-file 없이 띄우고, E2E 전용 덮어쓰기만 더한다.
# E2E_REAL_MODELS=1이면 frame-encoder·ai-gateway를 실제 모델 프로필로 띄운다(호스트 Ollama, 가중치 업로드 필요).
up() {
  local files=(-f "$ROOT/local/docker-compose.yml" -f "$E2E_DIR/compose.e2e.yml")
  if [[ "${E2E_REAL_MODELS:-}" == "1" ]]; then
    export AI_GATEWAY_PROFILE_PATH=/app/profiles/local.toml FRAME_ENCODER_PROFILE_PATH=/app/profiles/local.toml \
      GROUNDING_WORKER_PROFILE_PATH=/app/profiles/local.toml
  fi
  # E2E_VLM_MODEL을 주면 이미지의 local.toml에서 VLM 모델 이름만 바꾼 사본을 마운트한다.
  # ai 레포 프로필은 평가를 거쳐 바꾸므로 E2E에서는 고치지 않는다.
  if [[ -n "${E2E_VLM_MODEL:-}" ]]; then
    docker run --rm --entrypoint cat vlm/ai-gateway:local /app/profiles/local.toml \
      | sed "s/qwen3-vl:4b-instruct/${E2E_VLM_MODEL}/g" > "$E2E_OUT/ai-gateway-profile.toml"
    cat > "$E2E_OUT/compose.model.yml" <<YML
services:
  ai-gateway:
    environment:
      AI_GATEWAY_PROFILE_PATH: /app/profiles/e2e.toml
    volumes:
      - $E2E_OUT/ai-gateway-profile.toml:/app/profiles/e2e.toml:ro
YML
    files+=(-f "$E2E_OUT/compose.model.yml")
  fi
  docker compose "${files[@]}" --profile '*' up -d
}

ai_python() {
  uv run --project "$AI_REPO" python "$@"
}

upload() {
  [[ -f "$E2E_VIDEO" ]] || { echo "영상이 없다: $E2E_VIDEO (E2E_VIDEO로 지정)" >&2; exit 1; }
  ai_python "$E2E_DIR/upload.py" "$E2E_VIDEO" "$E2E_OUT/upload-result.json"
}

# 다른 담당자 서비스가 만들 메시지·파일은 ai 레포 테스트 도우미로 만들어 넣는다.
# 다른 담당자 서비스가 만들 메시지·파일은 ai 레포 테스트 도우미로 만들어 넣는다.
# 인자: 실행할 스크립트, 자리 표시 analysis-api가 돌려줄 이벤트 수, 스크립트에 더 넘길 인자
run_with_helpers() {
  [[ -f "$E2E_OUT/upload-result.json" ]] || { echo "upload를 먼저 실행한다" >&2; exit 1; }
  local script="$1" events="$2"
  shift 2
  (
    cd "$AI_REPO"
    local t=services
    export PYTHONPATH="$t/frame-encoder/tests:$t/track-stitcher/tests:$t/track-analyzer/tests:$t/grounding-worker/tests:$t/aggregator/tests:$t/embedding-worker/tests:$t/event-analyzer/tests"
    # 테스트 데이터를 넣는 쓰기 키(local/seaweedfs/s3.json의 로컬 전용 샘플값)
    export S3_BUCKET=vlm-media S3_ENDPOINT_URL=http://localhost:8333 S3_PATH_STYLE=true
    export AWS_ACCESS_KEY_ID=local-media-key AWS_SECRET_ACCESS_KEY=local-media-secret AWS_REGION=us-east-1
    # 위험 이벤트 1건 + 일반 이벤트(나머지)를 30초 간격으로 둔다.
    uv run python - "$E2E_OUT/scenario.json" "$events" <<'PY'
import json, sys
from agg_support import ZONES, event, job_event_json, risk_event
count = int(sys.argv[2])
events = [job_event_json(risk_event(1, 30_000, detected=True))]
events += [job_event_json(event(n, start=(n - 2) * 30_000)) for n in range(2, count + 1)]
zones = [{"zoneId": str(z.zone_id), "name": z.name, "kind": z.kind} for z in ZONES]
json.dump({"events": events, "zones": zones}, open(sys.argv[1], "w"), default=str)
PY
    # aggregator가 읽는 analysis-api 자리 표시 서버(compose.e2e.yml이 8085를 가리킨다)
    ANALYSIS_API_SCENARIO="$E2E_OUT/scenario.json" ANALYSIS_API_HOST=0.0.0.0 ANALYSIS_API_PORT=8085 \
      uv run python -m vlm_testing.analysis_api > "$E2E_OUT/analysis-api.log" 2>&1 &
    local server=$!
    trap 'kill "$server"' EXIT
    until curl -s -o /dev/null localhost:8085/docs; do sleep 1; done
    E2E_AGG_EVENTS="$events" uv run python "$E2E_DIR/$script" "$E2E_OUT/upload-result.json" "$@"
  )
}

workers() {
  run_with_helpers workers.py 2 | tee "$E2E_OUT/workers-result.txt"
}

# 성공 지표·비기능 요구사항 측정(mock 프로필). 인자로 측정 함수 이름을 주면 그것만 돈다.
measure() {
  run_with_helpers measure.py "${E2E_MEASURE_EVENTS:-2000}" "$@" | tee "$E2E_OUT/measure-result.txt"
}

quality() {
  ai_python "$E2E_DIR/quality.py" | tee "$E2E_OUT/quality-result.txt"
}

# 스펙 파일 옆에서 @playwright/test를 찾도록 frontend 레포의 의존성을 연결한다.
playwright() {
  [[ -d "$FRONTEND_REPO/node_modules" ]] || { echo "repos/frontend에서 npm ci를 먼저 실행한다" >&2; exit 1; }
  ln -sfn "$FRONTEND_REPO/node_modules" "$E2E_DIR/pw/node_modules"
  (cd "$E2E_DIR/pw" && ./node_modules/.bin/playwright test --reporter=line "$@")
}

ui() {
  # 세션 화면 시연(SPEC-034)은 작업 전·후 두 번 올리므로 영상 앞 5초만 쓴다.
  export E2E_SHORT_VIDEO="$E2E_OUT/short-5s.mp4"
  ffmpeg -y -loglevel error -i "$E2E_VIDEO" -t 5 -c copy "$E2E_SHORT_VIDEO"
  playwright --config playwright.config.mjs
}

record() {
  python3 "$E2E_DIR/results_page.py" "$E2E_OUT"
  playwright --config record.config.mjs
  local webm
  webm="$(find "$E2E_OUT/recording" -name video.webm | head -1)"
  ffmpeg -y -loglevel error -i "$webm" -c:v libx264 -pix_fmt yuv420p -movflags +faststart "$E2E_OUT/flow-recording.mp4"
  echo "녹화: $E2E_OUT/flow-recording.mp4"
}

case "${1:-}" in
  up) up ;;
  upload) upload ;;
  workers) workers ;;
  measure) shift; measure "$@" ;;
  quality) quality ;;
  ui) ui ;;
  record) record ;;
  all) upload && workers && quality && ui && record ;;
  *) usage ;;
esac
