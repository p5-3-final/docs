#!/usr/bin/env bash
# 로컬 SeaweedFS 모델 버킷(vlm-models)에 인코더 가중치와 manifest를 올린다(SPEC-011, ADR-0010 ②).
# 한 번만 하면 된다.
#   local/scripts/upload-models.sh
# 가중치는 Hugging Face timm/MobileCLIP2-S0-OpenCLIP(Apple AMLR, 비상용)이다. manifest 경로와 sha256은
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
import json
import boto3
from boto3.s3.transfer import TransferConfig
from botocore.exceptions import ClientError
from huggingface_hub import hf_hub_download

BUCKET = "vlm-models"
# models/<종류>/<버전>/ (service-contracts/models/manifest.schema.json)
PREFIX = "models/mobileclip2-s0/dfndr2b"
WEIGHTS = "open_clip_model.safetensors"
WEIGHTS_SHA256 = "ab91a1a0c4330d6b1913e24d5035dfdea15423316aaec649610c6b1c6ddd0e95"
MANIFEST = {
    "kind": "image_text_encoder",
    "modelId": "open_clip:MobileCLIP2-S0:dfndr2b",
    "version": "dfndr2b",
    "files": [{"name": WEIGHTS, "sha256": WEIGHTS_SHA256, "size": 299663092}],
    "dimension": 512,
    "source": {"type": "public", "origin": "huggingface:timm/MobileCLIP2-S0-OpenCLIP"},
    "license": "Apple AMLR (non-commercial research)",
}
# 프로필이 manifest 바이트의 해시로 고정하므로 직렬화 형식을 바꾸면 이 값과 프로필을 함께 바꾼다.
MANIFEST_SHA256 = "569e79292c638ca67fbe5318adb212c3e26c73fbacfc6453268abf95c9266131"

manifest = (json.dumps(MANIFEST, indent=2, ensure_ascii=False) + "\n").encode()
if hashlib.sha256(manifest).hexdigest() != MANIFEST_SHA256:
    raise SystemExit(f"manifest sha256 changed: {hashlib.sha256(manifest).hexdigest()}")

s3 = boto3.client("s3", endpoint_url="http://seaweedfs:8333", region_name="us-east-1")
manifest_key = f"{PREFIX}/manifest.json"
try:
    s3.head_object(Bucket=BUCKET, Key=manifest_key)
    print(f"already uploaded: s3://{BUCKET}/{manifest_key}")
    raise SystemExit(0)
except ClientError as e:
    if e.response["Error"]["Code"] not in ("404", "NoSuchKey"):
        raise
path = hf_hub_download("timm/MobileCLIP2-S0-OpenCLIP", WEIGHTS)
digest = hashlib.sha256(open(path, "rb").read()).hexdigest()
if digest != WEIGHTS_SHA256:
    raise SystemExit(f"sha256 mismatch: {digest}")
# 조각을 동시에 여러 개 올리면 로컬 SeaweedFS(메모리 상한 384M)가 OOM으로 죽는다. 하나씩 올린다.
s3.upload_file(path, BUCKET, f"{PREFIX}/{WEIGHTS}", Config=TransferConfig(max_concurrency=1))
# manifest를 마지막에 올려, manifest가 있으면 파일도 모두 있게 한다.
s3.put_object(Bucket=BUCKET, Key=manifest_key, Body=manifest, ContentType="application/json")
print(f"uploaded: s3://{BUCKET}/{manifest_key}")
PY
