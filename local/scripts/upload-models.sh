#!/usr/bin/env bash
# 로컬 SeaweedFS 모델 버킷(vlm-models)에 모델 가중치와 manifest를 올린다(SPEC-011, SPEC-026, ADR-0010 ②).
# 한 번만 하면 된다. 이미 올린 모델은 건너뛴다.
#   local/scripts/upload-models.sh
# - 인코더: Hugging Face timm/MobileCLIP2-S0-OpenCLIP(Apple AMLR, 비상용). manifest 경로와 sha256은
#   repos/ai/services/ai-gateway·frame-encoder의 profiles/local.toml [encoder]와 같아야 한다.
# - grounding 탐지기: Hugging Face google/owlv2-base-patch16-ensemble(Apache-2.0). manifest 경로와 sha256은
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
OWLV2_REVISION = "cfd3195ba4ea9592eec887ded089f4c08eff231d"
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
        "prefix": "models/owlv2/owlv2-b16-ensemble",
        "repo": "google/owlv2-base-patch16-ensemble",
        "revision": OWLV2_REVISION,
        "manifest": {
            "kind": "detector",
            "modelId": "transformers:owlv2-base-patch16:ensemble",
            "version": "owlv2-b16-ensemble",
            "files": [
                {"name": name, "sha256": sha, "size": size}
                for name, sha, size in [
                    ("added_tokens.json", "e5dc0da35d20111e8ff3fdfc03682beca23d5f94ed74331bce81786b2636a24f", 67),
                    ("config.json", "ba9df8c25a4b8461887dd0a93d9252c9cd84697fe8d49a9d8794ce409af9acb2", 414),
                    ("merges.txt", "9fd691f7c8039210e0fced15865466c65820d09b63988b0174bfe25de299051a", 524619),
                    ("model.safetensors", "e1e130b9e404cf91a75ad45644c1da9d7fa5284085eecc864266a6923efb99e7", 619918824),
                    ("preprocessor_config.json", "cf3e396635b797ee1a464e1b2836e98748f8edac19e89aaa2c93b55ac15b0064", 425),
                    ("special_tokens_map.json", "d6e2b9cf664efbad2d22998b8d3da986abcbeed3e0825ad33605c9401f9cf73e", 121),
                    ("tokenizer_config.json", "b55cda6198e152ded427c8a9b3faf1cccf27a7fa080697a62f6ff143f511f44f", 1100),
                    ("vocab.json", "e089ad92ba36837a0d31433e555c8f45fe601ab5c221d4f607ded32d9f7a4349", 1059962),
                ]
            ],
            "openVocabulary": True,
            "source": {"type": "public", "origin": f"huggingface:google/owlv2-base-patch16-ensemble@{OWLV2_REVISION}"},
            "license": "Apache-2.0",
        },
        "manifest_sha256": "cac61432484358fe3b62d86ed861e2f7ffdc87f66fced40dbc812ed0f1e55682",
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
