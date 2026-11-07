"""로컬 compose E2E: api-gateway를 거쳐 quality-service API를 확인한다.

quality 공개 API는 OPERATOR 전용이라(SPEC-029 R-4) 기본 관리자 계정 대신 역할별 계정을 새로 만든다.
auth에 역할 변경 API가 없어 OPERATOR 계정은 로컬 auth DB의 role을 직접 바꿔 만든다.
"""

import json
import subprocess
import sys
import urllib.error
import urllib.request
import uuid
from datetime import date, timedelta

GATEWAY = "http://localhost:8080"
RESULTS: list[bool] = []


def call(method, path, body=None, token=None):
    data = None if body is None else json.dumps(body).encode()
    req = urllib.request.Request(GATEWAY + path, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    if token:
        req.add_header("Authorization", f"Bearer {token}")
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            raw = res.read()
            return res.status, json.loads(raw) if raw else {}
    except urllib.error.HTTPError as e:
        raw = e.read()
        return e.code, json.loads(raw) if raw else {}


def check(name, ok, detail=""):
    RESULTS.append(ok)
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}", flush=True)


def user(role: str | None) -> str:
    email, password = f"e2e-q-{uuid.uuid4().hex[:8]}@example.com", "E2eUser1234"
    call("POST", "/api/v1/auth/signup", {"email": email, "password": password, "nickname": "e2e"})
    if role:
        sql = f"UPDATE users SET role = '{role}' WHERE email = '{email}'"
        subprocess.run(["docker", "exec", "vlm-postgres-1", "psql", "-U", "postgres", "-d", "auth_db", "-qc", sql], check=True)
    status, body = call("POST", "/api/v1/auth/login", {"email": email, "password": password})
    assert status == 200, (status, body)
    return body["accessToken"]


def main():
    plain = user(None)
    status, body = call("GET", "/api/v1/quality/review-items", token=plain)
    check("USER 역할은 403 QUALITY_FORBIDDEN (SPEC-029 R-4)", status == 403 and body.get("code") == "QUALITY_FORBIDDEN", (status, body.get("code")))
    status, _ = call("GET", "/api/v1/quality/review-items")
    check("토큰 없으면 401", status == 401, status)

    op = user("OPERATOR")
    status, body = call("GET", "/api/v1/auth/me", token=op)
    check("OPERATOR 토큰", "OPERATOR" in body.get("roles", []), body.get("roles"))
    status, body = call("GET", "/api/v1/quality/review-items", token=op)
    check("검토 큐 조회", status == 200 and "items" in body, (status, len(body.get("items", []))))
    name = f"e2e-{uuid.uuid4().hex[:8]}"
    status, body = call("POST", "/api/v1/quality/golden-sets", {"name": name, "split": "eval"}, op)
    check("Golden Set 만들기", status == 201, (status, body.get("code")))
    set_id = body.get("id") or body.get("setId")
    if set_id:
        status, body = call("GET", f"/api/v1/quality/golden-sets/{set_id}", token=op)
        check("Golden Set 조회", status == 200, status)
        status, body = call("POST", f"/api/v1/quality/golden-sets/{set_id}/versions", {}, op)
        check("빈 초안 확정은 409 QUALITY_GOLDEN_EMPTY", status == 409 and body.get("code") == "QUALITY_GOLDEN_EMPTY", (status, body.get("code")))
    status, body = call("GET", "/api/v1/quality/evaluation-runs", token=op)
    check("평가 실행 목록", status == 200, status)
    status, body = call("GET", f"/api/v1/quality/alert-reports?from={date.today() - timedelta(days=7)}&to={date.today()}", token=op)
    check("긴급 알림 리포트", status == 200, (status, body.get("code")))
    status, body = call("GET", f"/api/v1/quality/stage-reports/sources/{uuid.uuid4()}", token=op)
    check("측정 없는 영상은 404 QUALITY_SOURCE_NOT_FOUND", status == 404 and body.get("code") == "QUALITY_SOURCE_NOT_FOUND", (status, body.get("code")))
    status, _ = call("POST", "/internal/v1/quality/stage-gates", {}, op)
    check("내부 API는 게이트웨이로 노출하지 않음", status in (403, 404), status)
    print(f"\n합계 {len(RESULTS)}건, 실패 {RESULTS.count(False)}건")
    sys.exit(0 if all(RESULTS) else 1)


if __name__ == "__main__":
    main()
