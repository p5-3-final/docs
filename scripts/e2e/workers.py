"""로컬 compose E2E: ai 워커끼리 이어지는 흐름을 실제 컨테이너로 확인한다.

다른 담당자 서비스(chunk-processor, analysis-api, search 등)가 낼 메시지·파일은 ai 레포 테스트 도우미로 만들어 넣는다.
실행: run.sh workers (repos/ai에서 테스트 도우미 경로·저장소 환경변수를 넣고 부른다)
"""

import json
import re
import sys
import time
import uuid
from collections.abc import Callable
from pathlib import Path

from confluent_kafka import Consumer
from vlm_messaging.publisher import KafkaPublisher
from vlm_storage.s3 import S3Storage, StorageSettings

import agg_support
import ew_support
import fe_support
import gw_support
import stitcher_support
import ta_support

BOOTSTRAP = "localhost:9092"
RESULTS: list[tuple[str, bool, str]] = []
storage = S3Storage(StorageSettings())
publisher = KafkaPublisher(bootstrap=BOOTSTRAP, client_id="e2e")


def record(name: str, ok: bool, detail: object = "") -> bool:
    RESULTS.append((name, ok, str(detail)))
    print(f"[{'PASS' if ok else 'FAIL'}] {name} {detail}", flush=True)
    return ok


def collect(topic: str, match: Callable[[dict], bool], count: int, timeout_s: float) -> list[dict]:
    consumer = Consumer(
        {"bootstrap.servers": BOOTSTRAP, "group.id": f"e2e-{uuid.uuid4().hex}", "auto.offset.reset": "earliest"}
    )
    consumer.subscribe([topic])
    found: list[dict] = []
    deadline = time.monotonic() + timeout_s
    try:
        while time.monotonic() < deadline and len(found) < count:
            msg = consumer.poll(1.0)
            if msg is None or msg.error():
                continue
            body = json.loads(msg.value())
            if match(body):
                found.append(body)
    finally:
        consumer.close()
    return found


def by_source(source: object) -> Callable[[dict], bool]:
    return lambda body: body.get("sourceId") == str(source)


def put_jpegs(body: object) -> int:
    """메시지 안의 이미지 경로마다 테스트 이미지를 올린다(다른 담당자 서비스가 만들 파일 자리)."""
    keys = set(re.findall(r'"(sources/[^"]+\.jpg)"', json.dumps(body)))
    for key in keys:
        storage.put_bytes(key, fe_support.image_bytes(key), "image/jpeg")
    return len(keys)


def flow_vectors() -> None:
    """1. segment.ready → frame-encoder → segment.embedded (→ event.candidate.vector → event-analyzer → embedding-worker)."""
    source = uuid.uuid4()
    ready = fe_support.segment_ready(source=source, execution=uuid.uuid4(), event_id=uuid.uuid4())
    fe_support.put_images(storage, ready)
    publisher.publish("segment.ready", ready)
    embedded = collect("segment.embedded", by_source(source), 1, 120)
    if record("1. frame-encoder segment.embedded", len(embedded) == 1, f"{len(embedded)}건"):
        key = embedded[0]["vectorsKey"]
        record("1. 벡터 파일 저장", storage.exists(key), key)
    candidates = collect("event.candidate.vector", by_source(source), 1, 20)
    record("1. frame-encoder event.candidate.vector(mock 프로필은 후보가 없을 수 있음)", True, f"{len(candidates)}건")
    if candidates:
        analyzed = collect("event.analyzed", by_source(source), 1, 120)
        record("1. event-analyzer event.analyzed", len(analyzed) >= 1, f"{len(analyzed)}건")
        if analyzed:
            ready_events = collect("embedding.ready", by_source(source), 1, 120)
            record("1. embedding-worker embedding.ready(이벤트)", len(ready_events) >= 1, f"{len(ready_events)}건")


def flow_stitcher() -> None:
    """2. chunk.boundary + segment.embedded(청크 5개) → track-stitcher → track.detected 4건 + track.manifest."""
    source = uuid.uuid4()
    files = stitcher_support.crossing_chunks(source=source)
    for f in files:
        vf = stitcher_support.vector_file(f)
        stitcher_support.store_chunk(storage, f)
        stitcher_support.store_vectors(storage, vf)
        publisher.publish("chunk.boundary", stitcher_support.boundary_message(f))
        publisher.publish("segment.embedded", stitcher_support.embedded_message(vf))
    detected = collect("track.detected", by_source(source), 4, 120)
    record("2. track-stitcher track.detected", len(detected) == 4, f"{len(detected)}건(기대 4)")
    manifests = collect("track.manifest", by_source(source), 1, 120)
    if record("2. track-stitcher track.manifest", len(manifests) == 1, f"{len(manifests)}건"):
        m = manifests[0]
        record("2. 번역표 저장·완료", m.get("complete") is True and storage.exists(m["mappingKey"]), m["mappingKey"])


def flow_track_attributes() -> None:
    """3. attribute.requested → track-analyzer → track.analyzed → embedding-worker → embedding.ready(트랙)."""
    source = uuid.uuid4()
    message = ta_support.attribute_request("click")
    text = message.model_dump_json(by_alias=True).replace(str(ta_support.SOURCE), str(source))
    body = {**json.loads(text), "eventId": str(uuid.uuid4()), "requestId": str(uuid.uuid4())}
    images = put_jpegs(body)
    # embedding-worker가 트랙 시각·클래스를 읽는 번역표(track-stitcher가 만드는 파일 자리)
    mapping = ew_support.track_mapping(uuid.UUID(body["trackId"])).replace(
        str(ew_support.SOURCE).encode(), str(source).encode()
    ).replace(str(ew_support.JOB).encode(), body["jobId"].encode())
    storage.put_bytes(ew_support.mapping_key(source, uuid.UUID(body["jobId"])), mapping, "application/json")
    publisher.send_raw("attribute.requested", str(source), json.dumps(body).encode(), [])
    analyzed = collect("track.analyzed", by_source(source), 1, 120)
    ok = record("3. track-analyzer track.analyzed", len(analyzed) == 1, f"{len(analyzed)}건, 이미지 {images}장")
    if ok:
        record("3. 속성 분석 결과", analyzed[0].get("outcome") == "READY", analyzed[0].get("outcome"))
        ready = collect("embedding.ready", by_source(source), 1, 120)
        record("3. embedding-worker embedding.ready(트랙)", len(ready) == 1, f"{len(ready)}건")
        if ready:
            record("3. 텍스트 벡터 파일 저장", storage.exists(ready[0]["vectorKey"]), ready[0]["vectorKey"])


def flow_grounding(upload: dict) -> None:
    """4. 업로드한 실제 영상의 정규화 사본으로 grounding.requested → grounding-worker → grounding.completed."""
    video = upload["videoId"]
    keys = [k for k in storage.list_keys(f"sources/{video}/normalizations/") if k.endswith("normalized.mp4")]
    if not record("4. 실제 영상 정규화 사본 찾기", len(keys) == 1, keys):
        return
    normalized_key = keys[0]
    normalization = normalized_key.split("/")[3]
    message = gw_support.grounding_request([gw_support.segment(0, 40_000, 50_000)])
    text = (
        message.model_dump_json(by_alias=True)
        .replace(str(gw_support.SOURCE), video)
        .replace(str(gw_support.NORMALIZATION), normalization)
    )
    body = json.loads(text)
    body["normalizedKey"] = normalized_key
    body["segments"][0] |= {"groundingId": str(uuid.uuid4()), "segmentId": str(uuid.uuid4())}
    body |= {"eventId": str(uuid.uuid4()), "requestId": str(uuid.uuid4())}
    publisher.send_raw("grounding.requested", video, json.dumps(body).encode(), [])
    completed = collect("grounding.completed", by_source(video), 1, 180)
    if record("4. grounding-worker grounding.completed", len(completed) == 1, f"{len(completed)}건"):
        c = completed[0]
        ok = c.get("outcome") == "READY"
        record("4. 주석 클립 결과", ok, c.get("outcome") if ok else c)
        if ok:
            clip = storage.get_bytes(c["clipKey"])
            record("4. 클립 mp4 저장", clip[4:8] == b"ftyp", f"{c['clipKey']} {len(clip)}바이트, 프레임 {len(c['frames'])}개")


def flow_aggregator() -> None:
    """5. analysis.completed → aggregator(자리 표시 analysis-api 읽기) → source.completed + 결과 파일."""
    job = uuid.uuid4()
    agg_support.put_empty_inventory(storage, agg_support.CHUNK_A, job=job)
    message = agg_support.completed(job=job, events=2)
    body = {**json.loads(message.model_dump_json(by_alias=True)), "eventId": str(uuid.uuid4())}
    publisher.send_raw("analysis.completed", body["sourceId"], json.dumps(body).encode(), [])
    published = collect("source.completed", lambda b: b.get("jobId") == str(job), 1, 180)
    if record("5. aggregator source.completed", len(published) == 1, f"{len(published)}건"):
        p = published[0]
        record("5. 결과 파일 저장", storage.exists(p["resultKey"]), p["resultKey"])
        record("5. 집계 수", p["counts"]["inputEvents"] == 2, p["counts"])


def main() -> None:
    upload = json.loads(Path(sys.argv[1]).read_text())
    for flow in (flow_vectors, flow_stitcher, flow_track_attributes, lambda: flow_grounding(upload), flow_aggregator):
        try:
            flow()
        except Exception as e:  # noqa: BLE001  # 한 흐름이 깨져도 나머지 흐름 결과를 보려고 모두 받는다
            record(f"예외 {getattr(flow, '__name__', 'flow')}", False, repr(e)[:300])
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n합계 {len(RESULTS)}건, 실패 {len(failed)}건")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
