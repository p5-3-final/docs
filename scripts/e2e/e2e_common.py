"""로컬 compose E2E 공용: 메시지 보내기·모으기, 테스트 도우미 ID 바꾸기, 결과 기록.

workers.py(흐름 확인)와 measure.py(성능·성공 지표 측정)가 같이 쓴다.
"""

import json
import os
import re
import subprocess
import time
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

from confluent_kafka import Consumer
from pydantic import BaseModel
from vlm_messaging.publisher import KafkaPublisher
from vlm_storage.s3 import S3Storage, StorageSettings

import agg_support
import ea_support
import ew_support
import fe_support
import gw_support
import stitcher_support
import ta_support

BOOTSTRAP = "localhost:9092"
AI_GATEWAY = "http://localhost:8000"
OUT = Path(os.environ.get("E2E_OUT", "."))
_HELPERS = (fe_support, stitcher_support, agg_support, ta_support, gw_support, ew_support, ea_support)
HELPER_SOURCES = {str(m.SOURCE) for m in _HELPERS}
HELPER_OWNERS = {str(m.OWNER) for m in _HELPERS}

RESULTS: list[tuple[str, bool, str]] = []
storage = S3Storage(StorageSettings())
publisher = KafkaPublisher(bootstrap=BOOTSTRAP, client_id="e2e")


class Target:
    """도우미 ID 대신 쓸 관리자 계정 영상·소유자 ID(upload 단계 결과)."""

    video = ""
    owner = ""
    email = ""

    @classmethod
    def load(cls, upload_result: Path) -> None:
        upload = json.loads(upload_result.read_text())
        cls.video, cls.owner, cls.email = upload["videoId"], upload["ownerId"], upload["email"]


def retarget(text: str) -> str:
    for helper in HELPER_SOURCES:
        text = text.replace(helper, Target.video)
    for helper in HELPER_OWNERS:
        text = text.replace(helper, Target.owner)
    return text


class RetargetStorage:
    """도우미가 쓰는 파일의 경로와 JSON 안의 도우미 ID를 관리자 영상·계정 ID로 바꿔 저장한다."""

    def put_bytes(self, key: str, data: bytes, content_type: str) -> None:
        if data[:1] in (b"{", b"["):
            data = retarget(data.decode()).encode()
        storage.put_bytes(retarget(key), data, content_type)


rstore = RetargetStorage()


def to_body(message: BaseModel | dict) -> dict:
    text = message.model_dump_json(by_alias=True) if isinstance(message, BaseModel) else json.dumps(message)
    return json.loads(retarget(text))


def send(topic: str, message: BaseModel | dict, **overrides: object) -> dict:
    """도우미 메시지를 관리자 영상·계정 ID로 바꿔 보낸다. eventId는 매번 새로 만든다(중복 제거 회피)."""
    body = {**to_body(message), "eventId": str(uuid.uuid4()), **overrides}
    publisher.send_raw(topic, Target.video, json.dumps(body).encode(), [])
    return body


def record(name: str, ok: bool, detail: object = "") -> bool:
    RESULTS.append((name, ok, str(detail)))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}", flush=True)
    return ok


def now_ms() -> int:
    return int(time.time() * 1000)


def anything(_: dict) -> bool:
    return True


def collect_timed(
    topic: str, match: Callable[[dict], bool], count: int, timeout_s: float, since_ms: int
) -> list[tuple[int, dict]]:
    """since_ms 뒤에 들어온 관리자 영상의 메시지를 (Kafka 기록 시각 ms, 본문)으로 모은다."""
    consumer = Consumer(
        {"bootstrap.servers": BOOTSTRAP, "group.id": f"e2e-{uuid.uuid4().hex}", "auto.offset.reset": "earliest"}
    )
    consumer.subscribe([topic])
    found: list[tuple[int, dict]] = []
    deadline = time.monotonic() + timeout_s
    try:
        while time.monotonic() < deadline and len(found) < count:
            msg = consumer.poll(1.0)
            if msg is None or msg.error() or msg.timestamp()[1] < since_ms:
                continue
            body = json.loads(msg.value())
            if body.get("sourceId") == Target.video and match(body):
                found.append((msg.timestamp()[1], body))
    finally:
        consumer.close()
    return found


def collect(topic: str, match: Callable[[dict], bool], count: int, timeout_s: float, since_ms: int) -> list[dict]:
    """since_ms 뒤에 들어온 메시지만 본다. 같은 영상으로 여러 번 돌려도 이전 실행 결과를 잡지 않게 한다."""
    return [body for _, body in collect_timed(topic, match, count, timeout_s, since_ms)]


def p95(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[max(0, round(0.95 * len(ordered)) - 1)]


def stage_durations(container: str, stage: str, since: datetime, with_stage: str | None = None) -> list[float]:
    """워커가 남긴 처리 시간 로그(SPEC-013 stage timing)에서 단계 하나의 durationMs를 모은다.

    with_stage를 주면 그 단계가 함께 기록된 메시지(같은 묶음)만 센다. 한 워커가 여러 토픽을 받을 때
    토픽 하나의 처리 시간만 고르는 데 쓴다.
    """
    logs = subprocess.run(
        ["docker", "logs", "--since", since.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%SZ"), container],
        capture_output=True, text=True, check=True,
    )
    durations = []
    for line in (logs.stdout + logs.stderr).splitlines():
        if '"stage timing"' not in line:
            continue
        timings = json.loads(line)["stageTiming"]["timings"]
        if with_stage is not None and all(t["stageId"] != with_stage for t in timings):
            continue
        for timing in timings:
            if timing["stageId"] == stage:
                durations.append(float(timing["durationMs"]))
    return durations


def put_fake_images(body: dict) -> int:
    """메시지 안의 이미지 경로마다 테스트 이미지를 올린다(다른 담당자 서비스가 만들 파일 자리)."""
    keys = set(re.findall(r'"(sources/[^"]+\.jpg)"', json.dumps(body)))
    for key in keys:
        storage.put_bytes(key, fe_support.image_bytes(key), "image/jpeg")
    return len(keys)
