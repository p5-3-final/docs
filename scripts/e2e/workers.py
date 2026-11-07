"""로컬 compose E2E: ai 워커끼리 이어지는 흐름을 실제 컨테이너로 확인한다.

다른 담당자 서비스(chunk-processor, analysis-api, search 등)가 낼 메시지·파일은 ai 레포 테스트 도우미로 만들어 넣는다.
도우미의 고정 영상·소유자 ID는 upload 단계에서 관리자 계정이 올린 영상과 그 계정 ID로 바꿔 넣는다.
실행: run.sh workers (repos/ai에서 테스트 도우미 경로·저장소 환경변수를 넣고 부른다)
"""

import json
import os
import subprocess
import sys
import urllib.request
import uuid
from pathlib import Path

import agg_support
import ew_support
import fe_support
import gw_support
import stitcher_support
import ta_support
from e2e_common import (
    AI_GATEWAY,
    OUT,
    RESULTS,
    Target,
    anything,
    collect,
    now_ms,
    put_fake_images,
    record,
    retarget,
    rstore,
    send,
    storage,
)

# 실제 모델 모드(run.sh가 E2E_REAL_MODELS=1로 부른다): 테스트 도우미의 가짜 이미지 바이트 대신
# 업로드한 영상에서 뽑은 실제 프레임을 넣는다. 영상에서 프레임을 뽑는 chunk-processor가 아직 없어서다.
REAL = os.environ.get("E2E_REAL_MODELS") == "1"
VIDEO = os.environ.get("E2E_VIDEO", "")
# 벡터 흐름 구간 수와 간격: 13분 영상 전체에서 장면이 다른 구간을 고른다.
REAL_SEGMENTS = 8
REAL_STRIDE_MS = 90_000
# 110초 장면에서 카트를 미는 작업자(1920x1080 픽셀, x·y·폭·높이). chunk-processor가 낼 크롭처럼 사람에 맞춰 자른다.
WORKER_BOX = (840, 160, 130, 190)
SEARCH_QUERIES = [
    "a worker pushing a cart loaded with boxes",
    "a forklift",
    "many people walking in a warehouse",
    "fire and smoke",
    "a person lying on the floor",
]
ARTIFACTS: dict[str, object] = {}


def video_jpeg(at_ms: int, box: tuple[int, int, int, int] | None = None) -> bytes:
    """영상의 at_ms 시점 프레임을 JPEG로 뽑는다. box가 있으면 그 영역만 자른다."""
    vf = f"crop={box[2]}:{box[3]}:{box[0]}:{box[1]}" if box else "scale=960:-2"
    return subprocess.run(
        ["ffmpeg", "-loglevel", "error", "-ss", f"{at_ms / 1000:.3f}", "-i", VIDEO, "-frames:v", "1",
         "-vf", vf, "-f", "image2", "-c:v", "mjpeg", "-"],
        check=True, capture_output=True,
    ).stdout


def segment_ready_body() -> dict:
    """segment.ready 본문. 실제 모델 모드는 구간을 영상 전체에 퍼뜨리고 프레임 자리에 실제 프레임을 올린다."""
    segments, crops = (REAL_SEGMENTS, 0) if REAL else (2, 3)
    ready = fe_support.segment_ready(segments=segments, crops=crops, execution=uuid.uuid4(), event_id=uuid.uuid4())
    body = json.loads(retarget(ready.model_dump_json(by_alias=True)))
    for index, segment in enumerate(body["segments"]):
        if REAL:
            shift = index * (REAL_STRIDE_MS - 10_000)
            segment |= {"startMs": segment["startMs"] + shift, "endMs": segment["endMs"] + shift, "static": False}
        for frame in segment["frames"]:
            if REAL:
                frame["ptsMs"] += shift
                storage.put_bytes(frame["key"], video_jpeg(frame["ptsMs"]), "image/jpeg")
            else:
                storage.put_bytes(frame["key"], fe_support.image_bytes(frame["key"]), "image/jpeg")
    for crop in body["crops"]:
        storage.put_bytes(crop["key"], fe_support.image_bytes(crop["key"]), "image/jpeg")
    return body


def flow_vectors() -> None:
    """1. segment.ready → frame-encoder → segment.embedded (→ event.candidate.vector → event-analyzer → embedding-worker)."""
    since = now_ms()
    body = send("segment.ready", segment_ready_body())
    execution = body["executionId"]
    embedded = collect("segment.embedded", lambda b: b.get("executionId") == execution, 1, 180, since)
    if record("1. frame-encoder segment.embedded", len(embedded) == 1, f"{len(embedded)}건"):
        key = embedded[0]["vectorsKey"]
        if record("1. 벡터 파일 저장", storage.exists(key), key) and REAL:
            search_check(json.loads(storage.get_bytes(key)))
    candidates = collect("event.candidate.vector", lambda b: b.get("executionId") == execution, 1, 20, since)
    record("1. frame-encoder event.candidate.vector(장면에 넘어짐·화재가 없으면 0건)", True, f"{len(candidates)}건")
    if candidates:
        analyzed = collect("event.analyzed", anything, 1, 180, since)
        record("1. event-analyzer event.analyzed", len(analyzed) >= 1, f"{len(analyzed)}건")


def search_check(vector_file: dict) -> None:
    """6. 실제 인코더로 검색 문장을 벡터로 바꿔 구간 벡터와 비교한다(검색 서비스가 할 순위 계산 자리)."""
    req = urllib.request.Request(
        f"{AI_GATEWAY}/v1/embed",
        data=json.dumps({"taskType": "embed_visual_text", "texts": SEARCH_QUERIES}).encode(),
        headers={"Content-Type": "application/json", "X-Caller": "search-service"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=60) as res:
        queries = json.loads(res.read())["vectors"]
    segments = vector_file["segments"]
    ranking = []
    for text, q in zip(SEARCH_QUERIES, queries, strict=True):
        scores = sorted(
            ((sum(a * b for a, b in zip(q, s["vector"], strict=True)), s["startMs"]) for s in segments), reverse=True
        )
        ranking.append({"query": text, "top": [{"startMs": ms, "score": round(sc, 3)} for sc, ms in scores[:3]]})
        top = ", ".join(f"{ms // 1000}s={sc:.3f}" for sc, ms in scores[:3])
        record(f"6. 검색 순위 '{text}'", True, f"상위 3구간 {top}")
    frames = []
    for segment in segments:
        name = f"segment-{segment['startMs'] // 1000:04d}s.jpg"
        (OUT / name).write_bytes(video_jpeg(segment["startMs"]))
        frames.append({"startMs": segment["startMs"], "file": name})
    ARTIFACTS["search"] = {"ranking": ranking, "frames": frames}


def flow_stitcher() -> None:
    """2. chunk.boundary + segment.embedded(청크 5개) → track-stitcher → track.detected 4건 + track.manifest."""
    since = now_ms()
    # 확정한 job은 다시 발행하지 않으므로(SPEC-022 R-17) 실행마다 새 job을 쓴다.
    for f in stitcher_support.crossing_chunks(source=uuid.UUID(Target.video), job=uuid.uuid4()):
        vf = stitcher_support.vector_file(f)
        stitcher_support.store_chunk(rstore, f)
        stitcher_support.store_vectors(rstore, vf)
        send("chunk.boundary", stitcher_support.boundary_message(f))
        send("segment.embedded", stitcher_support.embedded_message(vf))
    detected = collect("track.detected", anything, 4, 120, since)
    record("2. track-stitcher track.detected", len(detected) == 4, f"{len(detected)}건(기대 4)")
    manifests = collect("track.manifest", anything, 1, 120, since)
    if record("2. track-stitcher track.manifest", len(manifests) == 1, f"{len(manifests)}건"):
        m = manifests[0]
        record("2. 번역표 저장·완료", m.get("complete") is True and storage.exists(m["mappingKey"]), m["mappingKey"])


def flow_track_attributes() -> None:
    """3. attribute.requested → track-analyzer → track.analyzed → embedding-worker → embedding.ready(트랙)."""
    since = now_ms()
    message = json.loads(retarget(ta_support.attribute_request("click").model_dump_json(by_alias=True)))
    body = {**message, "eventId": str(uuid.uuid4()), "requestId": str(uuid.uuid4())}
    if REAL:
        for i, crop in enumerate(body["crops"]):
            image = video_jpeg(crop["ptsMs"], WORKER_BOX)
            storage.put_bytes(crop["key"], image, "image/jpeg")
            (OUT / f"crop-{i}.jpg").write_bytes(image)
        images = len(body["crops"])
    else:
        images = put_fake_images(body)
    # embedding-worker가 트랙 시각·클래스를 읽는 번역표(track-stitcher가 만드는 파일 자리)
    mapping = ew_support.track_mapping(uuid.UUID(body["trackId"])).replace(
        str(ew_support.JOB).encode(), body["jobId"].encode()
    )
    rstore.put_bytes(ew_support.mapping_key(job=uuid.UUID(body["jobId"])), mapping, "application/json")
    send("attribute.requested", body)
    analyzed = collect("track.analyzed", lambda b: b.get("requestId") == body["requestId"], 1, 300, since)
    if not record("3. track-analyzer track.analyzed", len(analyzed) == 1, f"{len(analyzed)}건, 이미지 {images}장"):
        return
    a = analyzed[0]
    ARTIFACTS["attributes"] = {k: a.get(k) for k in ("outcome", "attributes", "modelId")} | {"crops": images}
    record("3. 속성 분석 결과", a.get("outcome") == "READY", ARTIFACTS["attributes"] if REAL else a.get("outcome"))
    confirmed = (a.get("attributes") or {}).get("verificationStatus") == "confirmed"
    ready = collect("embedding.ready", lambda b: b.get("itemKind") == "track", 1, 120 if confirmed else 15, since)
    # 확인되지 않은 트랙은 embedding-worker가 건너뛴다(track_not_confirmed).
    record("3. embedding-worker embedding.ready(트랙)", len(ready) == (1 if confirmed else 0),
           f"{len(ready)}건, 판정 {'confirmed' if confirmed else '미확인이라 건너뜀'}")


def flow_grounding() -> None:
    """4. 업로드한 실제 영상의 정규화 사본으로 grounding.requested → grounding-worker → grounding.completed."""
    since = now_ms()
    keys = [k for k in storage.list_keys(f"sources/{Target.video}/normalizations/") if k.endswith("normalized.mp4")]
    if not record("4. 실제 영상 정규화 사본 찾기", len(keys) == 1, keys):
        return
    normalized_key = keys[0]
    message = gw_support.grounding_request([gw_support.segment(0, 40_000, 50_000)])
    body = json.loads(
        retarget(message.model_dump_json(by_alias=True)).replace(str(gw_support.NORMALIZATION), normalized_key.split("/")[3])
    )
    body["normalizedKey"] = normalized_key
    body["segments"][0] |= {"groundingId": str(uuid.uuid4()), "segmentId": str(uuid.uuid4())}
    body |= {"eventId": str(uuid.uuid4()), "requestId": str(uuid.uuid4())}
    send("grounding.requested", body)
    completed = collect("grounding.completed", lambda b: b.get("requestId") == body["requestId"], 1, 180, since)
    if record("4. grounding-worker grounding.completed", len(completed) == 1, f"{len(completed)}건"):
        c = completed[0]
        ok = c.get("outcome") == "READY"
        record("4. 주석 클립 결과", ok, c.get("outcome") if ok else c)
        if ok:
            clip = storage.get_bytes(c["clipKey"])
            record("4. 클립 mp4 저장", clip[4:8] == b"ftyp", f"{c['clipKey']} {len(clip)}바이트, 프레임 {len(c['frames'])}개")
            ARTIFACTS["grounding"] = {"clipKey": c["clipKey"], "targets": body["segments"][0].get("targets")}


def flow_aggregator() -> None:
    """5. analysis.completed → aggregator(자리 표시 analysis-api 읽기) → source.completed + 결과 파일."""
    since = now_ms()
    job = uuid.uuid4()
    agg_support.put_empty_inventory(rstore, agg_support.CHUNK_A, job=job)
    message = agg_support.completed(job=job, events=2)
    send("analysis.completed", {**json.loads(message.model_dump_json(by_alias=True)), "eventId": str(uuid.uuid4())})
    published = collect("source.completed", lambda b: b.get("jobId") == str(job), 1, 300, since)
    if not record("5. aggregator source.completed", len(published) == 1, f"{len(published)}건"):
        return
    p = published[0]
    record("5. 결과 파일 저장", storage.exists(p["resultKey"]), p["resultKey"])
    record("5. 집계 수", p["counts"]["inputEvents"] == 2, p["counts"])
    summary = json.loads(storage.get_bytes(p["resultKey"])).get("summary", {})
    ARTIFACTS["aggregate"] = {"resultKey": p["resultKey"], "summary": summary.get("text"), "modelId": summary.get("modelId")}
    if REAL:
        record("5. 영상 요약", summary.get("status") == "generated", summary.get("text"))


def main() -> None:
    Target.load(Path(sys.argv[1]))
    ARTIFACTS["target"] = {"videoId": Target.video, "ownerId": Target.owner, "email": Target.email}
    for flow in (flow_vectors, flow_stitcher, flow_track_attributes, flow_grounding, flow_aggregator):
        try:
            flow()
        except Exception as e:  # noqa: BLE001  # 한 흐름이 깨져도 나머지 흐름 결과를 보려고 모두 받는다
            record(f"예외 {flow.__name__}", False, repr(e)[:300])
    (OUT / "artifacts.json").write_text(json.dumps(ARTIFACTS, ensure_ascii=False, indent=2))
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n합계 {len(RESULTS)}건, 실패 {len(failed)}건")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
