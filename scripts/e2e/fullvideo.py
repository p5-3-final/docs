"""로컬 compose E2E: 업로드한 영상 전체를 실제 모델로 검색하고 상위 구간에 박스 클립을 만든다.

영상을 구간으로 나누는 chunk-processor와 순위를 내는 search-service가 아직 없어서 이 스크립트가 그 자리를
대신한다. 나머지는 실제 서비스다.
- 구간: 10초 창·5초 간격, 창마다 2.5초 간격 프레임 4장(아키텍처 "검색 경로" 4단계와 같은 규칙), 60초 청크마다
  segment.ready 한 건 → frame-encoder(MobileCLIP2)가 구간 벡터를 만든다.
- 검색: 한국어 검색어 → ai-gateway /v1/parse(대상어·검색 문장) → /v1/embed → 구간 벡터와 코사인 유사도 →
  겹치지 않는 상위 3구간.
- 박스: 상위 3구간과 대상어로 grounding.requested → grounding-worker(OWL-ViT)가 주석 클립을 만든다.

결과는 fullvideo.json과 썸네일로 남기고 fullvideo_page.py가 녹화용 페이지로 만든다.
실행: run.sh full (E2E_REAL_MODELS=1로 띄운 스택, upload를 먼저 해서 관리자 영상이 있어야 한다)
"""

import json
import os
import subprocess
import sys
import tempfile
import urllib.request
import uuid
from pathlib import Path

import fe_support
import gw_support
from e2e_common import AI_GATEWAY, OUT, RESULTS, Target, collect, now_ms, record, retarget, send, storage

VIDEO = os.environ["E2E_VIDEO"]
WINDOW_MS = 10_000
STRIDE_MS = 5_000
FRAME_STEP_MS = 2_500
CHUNK_MS = 60_000
TOP = 3
QUERIES = ["카트를 미는 작업자", "상자가 쌓인 선반", "지게차", "안전모 안 쓴 작업자"]


def post(path: str, body: dict) -> dict:
    req = urllib.request.Request(
        f"{AI_GATEWAY}{path}", data=json.dumps(body).encode(), method="POST",
        headers={"Content-Type": "application/json", "X-Caller": "search-service"},
    )
    with urllib.request.urlopen(req, timeout=300) as res:
        return json.loads(res.read())


def duration_ms() -> int:
    out = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", VIDEO],
                         check=True, capture_output=True, text=True).stdout
    return int(float(out) * 1000)


def extract_frames(folder: Path) -> list[bytes]:
    """2.5초마다 한 장을 한 번에 뽑는다. i번째 파일이 i x 2.5초 시점이다."""
    subprocess.run(["ffmpeg", "-loglevel", "error", "-i", VIDEO, "-vf", f"fps=1000/{FRAME_STEP_MS},scale=960:-2",
                    "-q:v", "4", str(folder / "%05d.jpg")], check=True)
    return [p.read_bytes() for p in sorted(folder.glob("*.jpg"))]


def segment_messages(frames: list[bytes], total_ms: int) -> list[dict]:
    """60초 청크마다 그 청크에서 시작하는 창들을 segment.ready 한 건으로 만들고 프레임을 저장소에 올린다."""
    template = json.loads(retarget(fe_support.segment_ready(segments=1, crops=0).model_dump_json(by_alias=True)))
    starts = range(0, total_ms - WINDOW_MS + 1, STRIDE_MS)
    messages = []
    for chunk_start in range(0, total_ms, CHUNK_MS):
        chunk, execution = uuid.uuid4(), uuid.uuid4()
        prefix = f"sources/{Target.video}/jobs/{template['jobId']}/chunks/{chunk}/executions/{execution}/blurred/"
        segments = []
        for start in (s for s in starts if chunk_start <= s < chunk_start + CHUNK_MS):
            frame_refs = []
            for f in range(4):
                pts = start + f * FRAME_STEP_MS
                key = f"{prefix}s{start // 1000:04d}_f{f}.jpg"
                storage.put_bytes(key, frames[min(pts // FRAME_STEP_MS, len(frames) - 1)], "image/jpeg")
                frame_refs.append({"ptsMs": pts, "key": key})
            segments.append({"segmentId": str(uuid.uuid4()), "startMs": start, "endMs": start + WINDOW_MS,
                             "static": False, "frames": frame_refs})
        if segments:
            messages.append(template | {"chunkId": str(chunk), "executionId": str(execution),
                                        "segments": segments, "crops": []})
    return messages


def encode_whole_video(frames: list[bytes], total_ms: int) -> list[dict]:
    since = now_ms()
    bodies = [send("segment.ready", m) for m in segment_messages(frames, total_ms)]
    executions = {b["executionId"] for b in bodies}
    embedded = collect("segment.embedded", lambda b: b.get("executionId") in executions, len(bodies), 900, since)
    record("전체 영상 구간 벡터(frame-encoder)", len(embedded) == len(bodies),
           f"청크 {len(embedded)}/{len(bodies)}건, 구간 {sum(len(b['segments']) for b in bodies)}개")
    segments = []
    for e in embedded:
        segments += json.loads(storage.get_bytes(e["vectorsKey"]))["segments"]
    return sorted(segments, key=lambda s: s["startMs"])


def top_segments(scores: list[tuple[float, int]]) -> list[tuple[float, int]]:
    """점수가 높은 순으로, 이미 고른 구간과 겹치지 않는(시작 시각이 10초 이상 떨어진) 구간만 고른다."""
    chosen: list[tuple[float, int]] = []
    for score, start in sorted(scores, reverse=True):
        if all(abs(start - s) >= WINDOW_MS for _, s in chosen):
            chosen.append((score, start))
        if len(chosen) == TOP:
            break
    return chosen


def ground(parse: dict, tops: list[tuple[float, int]], normalized_key: str) -> list[dict]:
    since = now_ms()
    segments = [gw_support.segment(i, start, start + WINDOW_MS) for i, (_, start) in enumerate(tops)]
    message = gw_support.grounding_request(segments, targets=parse["targets"])
    body = json.loads(retarget(message.model_dump_json(by_alias=True))
                      .replace(str(gw_support.NORMALIZATION), normalized_key.split("/")[3]))
    for segment in body["segments"]:
        segment |= {"groundingId": str(uuid.uuid4()), "segmentId": str(uuid.uuid4())}
    body |= {"normalizedKey": normalized_key, "requestId": str(uuid.uuid4()), "canonicalQuery": parse["canonicalQuery"]}
    send("grounding.requested", body)
    done = collect("grounding.completed", lambda b: b.get("requestId") == body["requestId"], len(tops), 600, since)
    by_start = {c.get("startMs"): c for c in done}
    return [by_start.get(start, {}) for _, start in tops]


def search(query: str, segments: list[dict], frames: list[bytes], normalized_key: str, index: int) -> dict:
    parse = post("/v1/parse", {"query": query})
    [vector] = post("/v1/embed", {"taskType": "embed_visual_text", "texts": [parse["visualQuery"]]})["vectors"]
    scores = [(sum(a * b for a, b in zip(vector, s["vector"], strict=True)), s["startMs"]) for s in segments]
    tops = top_segments(scores)
    clips = ground(parse, tops, normalized_key)
    results = []
    for rank, ((score, start), clip) in enumerate(zip(tops, clips, strict=True)):
        thumb = f"full-{index}-{rank}.jpg"
        (OUT / thumb).write_bytes(frames[min((start + WINDOW_MS // 2) // FRAME_STEP_MS, len(frames) - 1)])
        boxes = sum(sum(f["counts"].values()) for f in clip.get("frames") or [])
        results.append({"startMs": start, "score": round(score, 3), "thumb": thumb, "outcome": clip.get("outcome"),
                        "clipKey": clip.get("clipKey"), "boxes": boxes})
    ok = all(r["outcome"] == "READY" for r in results)
    top = ", ".join(f"{r['startMs'] // 1000}초={r['score']:.3f}(박스 {r['boxes']})" for r in results)
    record(f"검색 '{query}' → {parse['targets']}", ok, f"상위 {top}")
    return {"query": query, "targets": parse["targets"], "visualQuery": parse["visualQuery"],
            "parseMethod": parse["parseMethod"], "top": results,
            "timeline": [{"startMs": ms, "score": round(sc, 4)} for sc, ms in sorted(scores, key=lambda x: x[1])]}


def main() -> None:
    Target.load(Path(sys.argv[1]))
    keys = [k for k in storage.list_keys(f"sources/{Target.video}/normalizations/") if k.endswith("normalized.mp4")]
    if not record("관리자 영상 정규화 사본", len(keys) == 1, keys):
        sys.exit(1)
    total = duration_ms()
    with tempfile.TemporaryDirectory() as tmp:
        frames = extract_frames(Path(tmp))
    record("영상 프레임 추출", len(frames) > 0, f"{total / 1000:.0f}초, 2.5초 간격 {len(frames)}장")
    segments = encode_whole_video(frames, total)
    queries = [search(q, segments, frames, keys[0], i) for i, q in enumerate(QUERIES)]
    result = {"videoId": Target.video, "email": Target.email, "durationMs": total, "segments": len(segments),
              "queries": queries}
    (OUT / "fullvideo.json").write_text(json.dumps(result, ensure_ascii=False, indent=2))
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n합계 {len(RESULTS)}건, 실패 {len(failed)}건")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
