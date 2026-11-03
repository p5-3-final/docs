#!/usr/bin/env bash
# 로컬 SeaweedFS 모델 버킷(vlm-models)에 인코더 가중치를 올린다(SPEC-011). 한 번만 하면 된다.
#   local/scripts/upload-models.sh
# 가중치는 Hugging Face timm/MobileCLIP2-S0-OpenCLIP(Apple AMLR, 비상용)이다. 키와 sha256은
# repos/ai/services/ai-gateway/profiles/local.toml의 [encoder]와 같아야 한다. 이미 있으면 건너뛴다.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
COMPOSE=(docker compose -f "$ROOT/local/docker-compose.yml")

# ai-gateway 이미지에 huggingface_hub·boto3가 들어 있어 호스트에 따로 설치하지 않는다.
# 키는 seaweedfs/s3.json의 로컬 전용 업로드 키(vlm-models 버킷만 쓸 수 있다)다.
"${COMPOSE[@]}" run --rm --no-deps \
  -e AWS_ACCESS_KEY_ID=local-models-key \
  -e AWS_SECRET_ACCESS_KEY=local-models-secret \
  -e HF_HOME=/tmp/hf \
  --entrypoint python ai-gateway - <<'PY'
import hashlib
import boto3
from boto3.s3.transfer import TransferConfig
from botocore.exceptions import ClientError
from huggingface_hub import hf_hub_download

BUCKET = "vlm-models"
KEY = "open_clip/MobileCLIP2-S0/dfndr2b/open_clip_model.safetensors"
SHA256 = "ab91a1a0c4330d6b1913e24d5035dfdea15423316aaec649610c6b1c6ddd0e95"

s3 = boto3.client("s3", endpoint_url="http://seaweedfs:8333", region_name="us-east-1")
try:
    s3.head_object(Bucket=BUCKET, Key=KEY)
    print(f"already uploaded: s3://{BUCKET}/{KEY}")
    raise SystemExit(0)
except ClientError as e:
    if e.response["Error"]["Code"] not in ("404", "NoSuchKey"):
        raise
path = hf_hub_download("timm/MobileCLIP2-S0-OpenCLIP", "open_clip_model.safetensors")
digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
if digest != SHA256:
    raise SystemExit(f"sha256 mismatch: {digest}")
# 조각을 동시에 여러 개 올리면 로컬 SeaweedFS(메모리 상한 384M)가 OOM으로 죽는다. 하나씩 올린다.
s3.upload_file(path, BUCKET, KEY, Config=TransferConfig(max_concurrency=1))
print(f"uploaded: s3://{BUCKET}/{KEY}")
PY
