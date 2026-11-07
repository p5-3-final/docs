#!/usr/bin/env bash
# 로컬 SeaweedFS 모델 버킷(vlm-models)에 모델 가중치와 manifest를 올린다(SPEC-011, SPEC-026, ADR-0010 ②).
# 한 번만 하면 된다. 이미 올린 모델은 건너뛴다.
#   local/scripts/upload-models.sh
# - 인코더: Hugging Face timm/MobileCLIP2-S0-OpenCLIP(Apple AMLR, 비상용). manifest 경로와 sha256은
#   repos/ai/services/ai-gateway·frame-encoder의 profiles/local.toml [encoder]와 같아야 한다.
# - grounding 탐지기: Hugging Face google/owlvit-base-patch32(Apache-2.0). manifest 경로와 sha256은
#   repos/ai/services/grounding-worker/profiles/local.toml의 [detector]와 같아야 한다.
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
OWLVIT_REVISION = "cbc355fb364588351c5d51c7f74465e8e7ec6f72"
# 항목마다 models/<종류>/<버전>/ 접두사(service-contracts/models/manifest.schema.json), Hugging Face 저장소와
# 리비전, manifest, 프로필이 고정한 manifest 바이트 해시. 직렬화 형식을 바꾸면 해시와 프로필을 함께 바꾼다.
MODELS = [
    {
        "prefix": "models/mobileclip2-s0/dfndr2b",
        "repo": "timm/MobileCLIP2-S0-OpenCLIP",
        "revision": None,
        "manifest": {
            "kind": "image_text_encoder",
            "modelId": "open_clip:MobileCLIP2-S0:dfndr2b",
            "version": "dfndr2b",
            "files": [
                {
                    "name": "open_clip_model.safetensors",
                    "sha256": "ab91a1a0c4330d6b1913e24d5035dfdea15423316aaec649610c6b1c6ddd0e95",
                    "size": 299663092,
                }
            ],
            "dimension": 512,
            "source": {"type": "public", "origin": "huggingface:timm/MobileCLIP2-S0-OpenCLIP"},
            "license": "Apple AMLR (non-commercial research)",
        },
        "manifest_sha256": "569e79292c638ca67fbe5318adb212c3e26c73fbacfc6453268abf95c9266131",
    },
    {
        "prefix": "models/owlvit/owlvit-b32",
        "repo": "google/owlvit-base-patch32",
        "revision": OWLVIT_REVISION,
        "manifest": {
            "kind": "detector",
            "modelId": "transformers:owlvit-base-patch32:base",
            "version": "owlvit-b32",
            "files": [
                {"name": name, "sha256": sha, "size": size}
                for name, sha, size in [
                    ("config.json", "b5934e0d2933194b8a85f93674e577feaa1a1ba2dc1d143b2d5e5305ff7a9d7c", 4418),
                    ("merges.txt", "9fd691f7c8039210e0fced15865466c65820d09b63988b0174bfe25de299051a", 524619),
                    ("model.safetensors", "4dbe0399f0b7d7c8dddf1535a98769cc30743bebc877aea681998c8d984ce52b", 612983940),
                    ("preprocessor_config.json", "2010d320cd2c68a8bb1de69aaa8f89daf173ef17cc22a30e4baf44b2f0e9bb6e", 392),
                    ("special_tokens_map.json", "f118ab3a983206e4f32583448de6bd6aae4ee21869135cef1f5848a753cdaab6", 460),
                    ("tokenizer_config.json", "da35aceebeda2adf44094a5867940b09379323b9390fa9197b57044e106bfb6e", 775),
                    ("vocab.json", "e089ad92ba36837a0d31433e555c8f45fe601ab5c221d4f607ded32d9f7a4349", 1059962),
                ]
            ],
            "openVocabulary": True,
            "source": {"type": "public", "origin": f"huggingface:google/owlvit-base-patch32@{OWLVIT_REVISION}"},
            "license": "Apache-2.0",
        },
        "manifest_sha256": "d61e583174e35fbce8264447cbb8e2864afb97f13489b491b718ba3bf61f1cc2",
    },
]

s3 = boto3.client("s3", endpoint_url="http://seaweedfs:8333", region_name="us-east-1")
# 조각을 동시에 여러 개 올리면 로컬 SeaweedFS가 OOM으로 죽을 수 있다. 하나씩 올린다.
transfer = TransferConfig(max_concurrency=1)


def uploaded(key: str) -> bool:
    try:
        s3.head_object(Bucket=BUCKET, Key=key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] not in ("404", "NoSuchKey"):
            raise
        return False


for model in MODELS:
    manifest = (json.dumps(model["manifest"], indent=2, ensure_ascii=False) + "\n").encode()
    if hashlib.sha256(manifest).hexdigest() != model["manifest_sha256"]:
        raise SystemExit(f"manifest sha256 changed: {hashlib.sha256(manifest).hexdigest()}")
    manifest_key = f"{model['prefix']}/manifest.json"
    if uploaded(manifest_key):
        print(f"already uploaded: s3://{BUCKET}/{manifest_key}")
        continue
    for file in model["manifest"]["files"]:
        path = hf_hub_download(model["repo"], file["name"], revision=model["revision"])
        with open(path, "rb") as f:
            digest = hashlib.file_digest(f, "sha256").hexdigest()
        if digest != file["sha256"]:
            raise SystemExit(f"sha256 mismatch for {file['name']}: {digest}")
        s3.upload_file(path, BUCKET, f"{model['prefix']}/{file['name']}", Config=transfer)
    # manifest를 마지막에 올려, manifest가 있으면 파일도 모두 있게 한다.
    s3.put_object(Bucket=BUCKET, Key=manifest_key, Body=manifest, ContentType="application/json")
    print(f"uploaded: s3://{BUCKET}/{manifest_key}")
PY
