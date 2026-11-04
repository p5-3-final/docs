#!/usr/bin/env bash
# ai-gateway 이미지의 Prompt Registry(프롬프트·분류 체계)와 프로필을 묶음 하나로 만들어 로컬 모델 버킷
# (vlm-models)의 registry/<해시 앞 12자리>/registry.tar.gz에 올린다(SPEC-009 R-26).
#   local/scripts/upload-registry.sh
# 끝에 출력하는 세 줄을 local/.env에 넣고 ai-gateway를 다시 띄우면 이미지 대신 묶음으로 뜬다.
# 운영은 ai CI가 같은 방식(python -m ai_gateway.registry_bundle)으로 만들어 올린다(이후 infra 작업).
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
COMPOSE=(docker compose -f "$ROOT/local/docker-compose.yml")

# 키는 seaweedfs/s3.json의 로컬 전용 업로드 키(vlm-models 버킷만 쓸 수 있다)다.
"${COMPOSE[@]}" run --rm --no-deps \
  -e AWS_ACCESS_KEY_ID=local-models-key \
  -e AWS_SECRET_ACCESS_KEY=local-models-secret \
  --entrypoint python ai-gateway - <<'PY'
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

from ai_gateway.registry_bundle import build_bundle

BUCKET = "vlm-models"
out = Path("/tmp/registry.tar.gz")
sha256 = build_bundle(Path("/app/registry"), Path("/app/profiles"), out)
key = f"registry/{sha256[:12]}/registry.tar.gz"
s3 = boto3.client("s3", endpoint_url="http://seaweedfs:8333", region_name="us-east-1")
try:
    s3.head_object(Bucket=BUCKET, Key=key)
    print(f"already uploaded: s3://{BUCKET}/{key}")
except ClientError as e:
    if e.response["Error"]["Code"] not in ("404", "NoSuchKey"):
        raise
    # 한 번 올린 버전 경로는 덮어쓰지 않는다. 내용이 바뀌면 해시와 경로가 함께 바뀐다.
    s3.upload_file(str(out), BUCKET, key)
    print(f"uploaded: s3://{BUCKET}/{key}")
print(f"AI_GATEWAY_REGISTRY_BUNDLE={key}")
print(f"AI_GATEWAY_REGISTRY_BUNDLE_SHA256={sha256}")
print("AI_GATEWAY_PROFILE_PATH=profiles/local-mock.toml")
PY
