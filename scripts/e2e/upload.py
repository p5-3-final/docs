"""로컬 compose E2E: 실제 영상으로 로그인 → 업로드(멀티파트) → 완료 → 정규화까지 확인한다.

실행: `uv run --project repos/ai python scripts/e2e/upload.py <영상 경로> <결과 JSON 경로>` (보통 run.sh가 부른다)
"""

import json
import os
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

GATEWAY = "http://localhost:8080"
VIDEO = Path(sys.argv[1])
OUT = Path(sys.argv[2])
TERMINAL = {"READY", "REJECTED", "EXPIRED"}


def call(method: str, path: str, body: object | None = None, token: str | None = None) -> tuple[int, dict]:
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(GATEWAY + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=60) as res:
            raw = res.read()
            return res.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, json.loads(raw) if raw else {}


def step(name: str, ok: bool, detail: object = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}", flush=True)
    if not ok:
        sys.exit(1)


def main() -> None:
    # 화면 로그인 칸에 미리 채워지는 샘플 관리자 계정(local/.env의 AUTH_ADMIN_*)과 같은 계정을 쓴다.
    email = os.environ.get("E2E_EMAIL", "admin@example.com")
    password = os.environ.get("E2E_PASSWORD", "admin1234")
    status, body = call("POST", "/api/v1/auth/login", {"email": email, "password": password})
    step("로그인", status == 200 and "accessToken" in body, status)
    token = body["accessToken"]
    status, me = call("GET", "/api/v1/auth/me", token=token)
    step("계정 확인", status == 200 and "id" in me, (status, me.get("roles")))

    size = VIDEO.stat().st_size
    status, body = call(
        "POST",
        "/api/v1/media/videos",
        {"fileName": VIDEO.name, "sizeBytes": size, "contentType": "video/mp4"},
        token,
    )
    step("업로드 자리 발급", status == 201, (status, body.get("upload", {}).get("method")))
    video_id = body["video"]["id"]
    upload = body["upload"]
    step("멀티파트 방식", upload["method"] == "MULTIPART", upload["method"])

    part_size = upload["partSizeBytes"]
    parts = []
    started = time.monotonic()
    with VIDEO.open("rb") as f:
        for part in upload["parts"]:
            chunk = f.read(part_size)
            req = urllib.request.Request(part["url"], data=chunk, method="PUT")
            with urllib.request.urlopen(req, timeout=300) as res:
                parts.append({"partNumber": part["partNumber"], "eTag": res.headers["ETag"]})
    step("조각 업로드", len(parts) == len(upload["parts"]), f"{len(parts)}개, {time.monotonic() - started:.1f}초")

    status, body = call("POST", f"/api/v1/media/videos/{video_id}/complete", {"parts": parts}, token)
    step("업로드 완료", status in (200, 202), (status, body.get("status")))

    deadline = time.monotonic() + 900
    seen = []
    started = time.monotonic()
    while time.monotonic() < deadline:
        status, body = call("GET", f"/api/v1/media/videos/{video_id}", token=token)
        current = body.get("status")
        if not seen or seen[-1] != current:
            seen.append(current)
            print(f"  상태 {current} ({time.monotonic() - started:.0f}초)", flush=True)
        if current in TERMINAL:
            break
        time.sleep(5)
    step("정규화 완료(READY)", seen[-1] == "READY", seen)

    status, body = call("GET", f"/api/v1/media/videos/{video_id}/playback", token=token)
    step("재생 주소 발급", status == 200 and bool(body.get("url")), status)
    # 워커 흐름이 같은 계정·영상으로 결과를 만들도록 소유자 ID를 함께 남긴다. 비밀번호는 남기지 않는다.
    OUT.write_text(json.dumps({"email": email, "ownerId": me["id"], "videoId": video_id}))


if __name__ == "__main__":
    main()
