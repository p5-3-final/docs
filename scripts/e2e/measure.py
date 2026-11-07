"""로컬 compose에서 v5.1 spec의 성공 지표와 비기능 요구사항을 잰다(mock 프로필).

결과는 PASS/FAIL 줄과 measure-result.json(spec별 수치)으로 남긴다. tasks.md "측정 기록"의 근거다.
실행: run.sh measure (upload를 먼저 해서 관리자 계정 영상·계정 ID가 있어야 한다)
"""

import json
import os
import random
import subprocess
import sys
import threading
import time
import urllib.error
import urllib.request
import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path

import agg_support
import ea_support
import ew_support
import inv_support
import stitcher_support
import ta_support
from e2e_common import (
    AI_GATEWAY,
    OUT,
    RESULTS,
    Target,
    collect,
    collect_timed,
    now_ms,
    p95,
    put_fake_images,
    stage_durations,
    record,
    rstore,
    send,
    storage,
    to_body,
)
from vlm_testing.contracts import body_event_errors, schema_errors

METRICS: dict[str, dict[str, object]] = {}
ROUNDS = 20
# analysis-api 자리 표시 서버가 돌려주는 이벤트 수(run.sh measure가 같은 수로 시나리오를 만든다).
# analysis.completed의 counts.events가 이 값과 같아야 대조가 맞는다.
AGG_EVENTS = int(os.environ.get("E2E_AGG_EVENTS", "2"))


def metric(spec: str, **values: object) -> None:
    METRICS.setdefault(spec, {}).update(values)


def schema_ok(name: str, bodies: list[dict]) -> bool:
    errors = [e for b in bodies for e in body_event_errors(b)]
    return record(f"{name} 계약 스키마", not errors, errors[:3] or f"{len(bodies)}건")


def ai_call_count() -> int:
    out = subprocess.run(
        ["docker", "exec", "vlm-postgres-1", "psql", "-U", "postgres", "-d", "ai_db", "-Atc",
         "select count(*) from ai.ai_call_log"],
        capture_output=True, text=True, check=True,
    )
    return int(out.stdout.strip())


def spec021_deadline() -> None:
    """SPEC-021 T030·NFR-1: 지난 마감이면 504·AI_DEADLINE_EXCEEDED, 호출 로그 없음, p95 20ms."""
    before = ai_call_count()
    body = json.dumps({"taskType": "event_judge", "sourceId": Target.video, "images": [], "variables": {}}).encode()
    latencies, codes = [], set()
    for _ in range(50):
        past = str(now_ms() - 1_000)
        req = urllib.request.Request(
            f"{AI_GATEWAY}/v1/analyze", data=body, method="POST",
            headers={"Content-Type": "application/json", "X-Caller": "event-analyzer", "X-Request-Deadline": past},
        )
        started = time.perf_counter()
        try:
            urllib.request.urlopen(req, timeout=5)
            codes.add(200)
        except urllib.error.HTTPError as e:
            codes.add((e.code, json.loads(e.read()).get("code")))
        latencies.append((time.perf_counter() - started) * 1000)
    added = ai_call_count() - before
    record("SPEC-021 지난 마감 응답", codes == {(504, "AI_DEADLINE_EXCEEDED")}, codes)
    record("SPEC-021 호출 로그 추가 0건", added == 0, f"{added}건")
    record("SPEC-021 NFR-1 p95 20ms 이하", p95(latencies) <= 20, f"p95 {p95(latencies):.1f}ms (50회, 왕복 포함)")
    metric("SPEC-021", requests=50, p95_ms=round(p95(latencies), 1), call_log_added=added)


def _stitch(job: uuid.UUID, order: Callable[[list], list]) -> tuple[list[dict], dict | None]:
    since = now_ms()
    messages = []
    for f in stitcher_support.crossing_chunks(source=uuid.UUID(Target.video), job=job):
        vf = stitcher_support.vector_file(f)
        stitcher_support.store_chunk(rstore, f)
        stitcher_support.store_vectors(rstore, vf)
        messages += [("chunk.boundary", stitcher_support.boundary_message(f)),
                     ("segment.embedded", stitcher_support.embedded_message(vf))]
    for topic, message in order(messages):
        send(topic, message)
    by_job = lambda b: b.get("jobId") == str(job)  # noqa: E731
    detected = collect("track.detected", by_job, 4, 120, since)
    manifests = collect("track.manifest", by_job, 1, 120, since)
    mapping = json.loads(storage.get_bytes(manifests[0]["mappingKey"])) if manifests else None
    return detected + manifests, mapping


def _reset_stitcher_job(job: uuid.UUID) -> None:
    """track-stitcher의 job 상태(Redis db 2)를 지워 같은 메시지를 처음 받는 상태로 되돌린다.

    manifest를 발행한 job은 다시 받아도 다시 발행하지 않으므로(SPEC-022 R-17), 순서를 섞은 재입력을
    처음 입력처럼 보게 하려면 상태를 먼저 지운다.
    """
    prefix = f"ts:{{{Target.video}}}:"
    script = "for _,k in ipairs(redis.call('KEYS', ARGV[1])) do redis.call('DEL', k) end return 1"
    commands = [
        ["EVAL", script, "0", f"{prefix}job:{job}:*"],
        ["ZREM", "ts:due", f"{Target.video}:{job}"],
        ["SREM", f"{prefix}jobs", str(job)],
        ["ZREM", f"{prefix}jobs", str(job)],
    ]
    for command in commands:
        # jobs 키 자료형을 몰라 SREM·ZREM을 모두 보낸다. 맞지 않는 쪽은 WRONGTYPE으로 끝나고 무시한다.
        subprocess.run(["docker", "exec", "vlm-redis-1", "redis-cli", "-n", "2", *command], capture_output=True)


def _normalized(mapping: dict) -> dict:
    """같은 입력이면 같아야 하는 내용만 남긴다(만든 시각처럼 실행마다 다른 값 제외)."""
    return {k: v for k, v in mapping.items() if k not in ("createdAt", "producedAt", "generatedAt")}


def spec022_stitcher() -> None:
    """SPEC-022 T034: 경계 쌍마다 track.detected 4 + manifest 1, 계약 통과, 순서를 섞어도 같은 번역표."""
    job = uuid.uuid4()
    events, mapping = _stitch(job, lambda m: m)
    detected = [e for e in events if e["eventType"] == "track.detected"]
    record("SPEC-022 track.detected 4건·manifest 1건", len(detected) == 4 and len(events) == 5, f"{len(events)}건")
    schema_ok("SPEC-022 이벤트", events)
    if mapping:
        record("SPEC-022 번역표 계약", not schema_errors("tracks/v1/track-mapping.schema.json", mapping))
    rng = random.Random(7)
    # 같은 job의 같은 메시지를 순서만 섞어 처음부터 다시 넣는다(성공 지표 원문).
    _reset_stitcher_job(job)
    _, shuffled = _stitch(job, lambda m: rng.sample(m, len(m)))
    same = mapping is not None and shuffled is not None and _normalized(mapping) == _normalized(shuffled)
    detail = "번역표가 같다" if same else ("다시 넣은 뒤 manifest 없음" if shuffled is None else "다름")
    record("SPEC-022 섞은 순서의 같은 번역표", same, detail)
    metric("SPEC-022", events=len(events), shuffled_same_mapping=same)


def _fresh_execution(body: dict) -> dict:
    """도우미의 실행·청크 ID를 새 값으로 바꾼다. 근거 프레임 경로도 같은 실행 폴더로 함께 바뀐다."""
    text = json.dumps(body)
    for helper in (ea_support.EXECUTION, ea_support.CHUNK):
        text = text.replace(str(helper), str(uuid.uuid4()))
    fresh = json.loads(text)
    put_fake_images(fresh)
    return fresh


def _detector(*candidates, **kwargs) -> dict:
    """event.candidate 본문. 실행마다 새 실행 ID를 쓰고 근거 프레임 자리에 테스트 이미지를 올린다."""
    return _fresh_execution(to_body(ea_support.detector_message(*candidates, **kwargs)))


def spec023_detector() -> None:
    """SPEC-023 성공 지표·NFR-1·T035(긴급 pending p95, 창 넘김 carry)."""
    d = ea_support.detected
    since = now_ms()
    body = send("event.candidate", _detector(
        d(1, start_s=0, track="t1"), d(2, start_s=3, track="t1"), d(3, start_s=6, track="t1"),
        d(4, start_s=40, track="t2"), d(5, "fire_or_smoke", start_s=80, track="t3"),
        d(6, "hazard_zone_access", start_s=100, judgment="rule", zone_name="A동 크레인 하부", track="t4"),
    ))
    by_exec = lambda b: b.get("executionId") == body["executionId"]  # noqa: E731
    analyzed = collect("event.analyzed", by_exec, 4, 60, since)
    manifests = collect("event.manifest", by_exec, 1, 60, since)
    merged = manifests[0].get("mergedCount") if manifests else None
    record("SPEC-023 성공 지표 event.analyzed 4건·mergedCount 2", len(analyzed) == 4 and merged == 2,
           f"{len(analyzed)}건, mergedCount {merged}")
    schema_ok("SPEC-023 이벤트", analyzed + manifests)

    since = now_ms()
    fifty = [d(100 + i, start_s=i * 2, track=f"n{i}") for i in range(50)]
    body = send("event.candidate", _detector(*fifty))
    by_exec = lambda b: b.get("executionId") == body["executionId"]  # noqa: E731
    done = collect_timed("event.manifest", by_exec, 1, 60, since)
    elapsed = (done[0][0] - since) / 1000 if done else None
    record("SPEC-023 NFR-1 VLM 후보 50개 10초 안", elapsed is not None and elapsed <= 10, f"{elapsed}초")

    latencies = []
    for _ in range(ROUNDS):
        sent_at = now_ms()
        alert = _fresh_execution(to_body(ea_support.alert_candidate()) | {"candidateId": str(uuid.uuid4())})
        alert = send("alert.candidate", alert)
        pending = collect_timed("alert.raised", lambda b, c=alert["candidateId"]: b.get("candidateId") == c
                                and b.get("status") == "pending", 1, 20, sent_at)
        if pending:
            latencies.append(pending[0][0] - sent_at)
    ok = len(latencies) == ROUNDS and p95(latencies) <= 500
    record("SPEC-023 T035 긴급 pending p95 500ms", ok, f"p95 {p95(latencies) if latencies else '-'}ms ({len(latencies)}/{ROUNDS})")

    since = now_ms()
    track = f"c{uuid.uuid4().hex[:6]}"
    first = send("event.candidate", _detector(d(201, start_s=5, track=track), job_type="STREAM", owned_ms=(0, 20_000)))
    collect("event.analyzed", lambda b: b.get("executionId") == first["executionId"], 1, 60, since)
    second = send("event.candidate", _detector(d(202, start_s=25, track=track), job_type="STREAM", owned_ms=(20_000, 40_000)))
    carried = collect("event.analyzed", lambda b: b.get("executionId") == second["executionId"], 1, 60, since)
    method = carried[0].get("judgmentMethod") if carried else None
    record("SPEC-023 T035 창 2개에 걸친 carry", method == "rule+carry", method)
    metric("SPEC-023", success_analyzed=len(analyzed), merged_count=merged, nfr1_50_candidates_s=elapsed,
           alert_pending_p95_ms=p95(latencies) if latencies else None, carry=method)


def spec024_track() -> None:
    """SPEC-024 성공 지표(click 1, question 1 → 2건)·NFR-1(발행부터 track.analyzed까지 p95 2초)."""
    since = now_ms()
    sent = []
    for reason in ("click", "question"):
        body = to_body(ta_support.attribute_request(reason, request_id=uuid.uuid4()))
        put_fake_images(body)
        sent.append(send("attribute.requested", body))
    ids = {b["requestId"] for b in sent}
    got = collect("track.analyzed", lambda b: b.get("requestId") in ids, 2, 60, since)
    record("SPEC-024 성공 지표 track.analyzed 2건", len(got) == 2, f"{len(got)}건")
    schema_ok("SPEC-024 이벤트", got)
    latencies = []
    for _ in range(ROUNDS):
        sent_at = now_ms()
        body = to_body(ta_support.attribute_request("click", request_id=uuid.uuid4()))
        put_fake_images(body)
        body = send("attribute.requested", body)
        done = collect_timed("track.analyzed", lambda b, r=body["requestId"]: b.get("requestId") == r, 1, 20, sent_at)
        if done:
            latencies.append(done[0][0] - sent_at)
    ok = len(latencies) == ROUNDS and p95(latencies) <= 2000
    record("SPEC-024 NFR-1 p95 2초", ok, f"p95 {p95(latencies) if latencies else '-'}ms ({len(latencies)}/{ROUNDS})")
    metric("SPEC-024", success=len(got), p95_ms=p95(latencies) if latencies else None)


def spec025_embedding() -> None:
    """SPEC-025 성공 지표(event.analyzed → embedding.ready, 파일 계약)·NFR-1(메시지 하나 p95 500ms)."""
    started = datetime.now(UTC)
    since = now_ms()
    sent = [send("event.analyzed", ew_support.event_analyzed()) for _ in range(ROUNDS)]
    ready = collect("embedding.ready", lambda b: b.get("itemKind") == "event", ROUNDS, 60, since)
    record("SPEC-025 event.analyzed → embedding.ready", len(ready) == ROUNDS, f"{len(ready)}/{ROUNDS}건")
    schema_ok("SPEC-025 이벤트", ready)
    file_errors = [e for r in ready[:3] for e in schema_errors(
        "vectors/v1/text-vector-file.schema.json", json.loads(storage.get_bytes(r["vectorKey"])))]
    record("SPEC-025 텍스트 벡터 파일 계약", not file_errors, file_errors[:2] or "3건 확인")
    handle = wait_durations("vlm-embedding-worker-1", "embedding-worker.handle", started, ROUNDS)
    ok = len(handle) >= ROUNDS and p95(handle) <= 500
    record("SPEC-025 NFR-1 handle p95 500ms", ok, f"p95 {p95(handle) if handle else '-'}ms ({len(handle)}건)")
    metric("SPEC-025", messages=len(sent), ready=len(ready), handle_p95_ms=p95(handle) if handle else None)


def wait_durations(container: str, stage: str, since: datetime, expected: int, with_stage: str | None = None) -> list[float]:
    """처리 시간 로그는 묶어서 늦게 기록되므로 기대 건수가 모일 때까지(최대 60초) 기다린다."""
    deadline = time.monotonic() + 60
    durations = stage_durations(container, stage, since, with_stage)
    while len(durations) < expected and time.monotonic() < deadline:
        time.sleep(3)
        durations = stage_durations(container, stage, since, with_stage)
    return durations


def memory_peak_mib(container: str, stop: Callable[[], bool]) -> float:
    peak = 0.0
    while not stop():
        out = subprocess.run(["docker", "stats", "--no-stream", "--format", "{{.MemUsage}}", container],
                             capture_output=True, text=True).stdout.split("/")[0].strip()
        value = float(out[:-3]) * (1024 if out.endswith("GiB") else 1 / 1024 if out.endswith("KiB") else 1)
        peak = max(peak, value)
    return peak


def spec027_aggregate() -> None:
    """SPEC-027 T043: analysis.completed → source.completed와 결과 파일 계약, aggregate.compute·메모리."""
    started = datetime.now(UTC)
    since = now_ms()
    job = uuid.uuid4()
    agg_support.put_empty_inventory(rstore, agg_support.CHUNK_A, job=job)
    send("analysis.completed", agg_support.completed(job=job, events=AGG_EVENTS))
    done: list[dict] = []
    waiter = threading.Thread(target=lambda: done.extend(
        collect("source.completed", lambda b: b.get("jobId") == str(job), 1, 300, since)))
    waiter.start()
    peak = memory_peak_mib("vlm-aggregator-1", lambda: not waiter.is_alive())
    waiter.join()
    if not record("SPEC-027 source.completed", len(done) == 1, f"{len(done)}건"):
        return
    schema_ok("SPEC-027 이벤트", done)
    result = json.loads(storage.get_bytes(done[0]["resultKey"]))
    errors = schema_errors("aggregates/v1/source-result.schema.json", result)
    record("SPEC-027 결과 파일 계약", not errors, errors[:2] or "통과")
    compute = stage_durations("vlm-aggregator-1", "aggregate.compute", started)
    record("SPEC-027 NFR-2 메모리 256MB 안", peak <= 256, f"최대 {peak:.0f}MiB, 입력 이벤트 {done[0]['counts']['inputEvents']}건")
    metric("SPEC-027", input_events=done[0]["counts"]["inputEvents"], memory_peak_mib=round(peak),
           compute_ms=compute[-1] if compute else None)


def spec028_inventory() -> None:
    """SPEC-028 성공 지표(방호벽 이동 → object_moved)·NFR-2(chunk.manifest 하나 p95 300ms)."""
    started = datetime.now(UTC)
    since = now_ms()
    job = uuid.uuid4()
    a = inv_support.chunk_inventory(agg_support.CHUNK_A, 0, 60_000,
                                    inv_support.static("s1", agg_support.CHUNK_A, zone=agg_support.AISLE, last=41_000))
    b = inv_support.chunk_inventory(agg_support.CHUNK_B, 60_000, 120_000,
                                    inv_support.static("s2", agg_support.CHUNK_B, box=(0.7, 0.1, 0.2, 0.15),
                                                       zone=agg_support.AISLE, first=70_000))
    for inv in (a, b):
        send("chunk.manifest", inv_support.manifest_of(inv), jobId=str(job))
    time.sleep(2)
    completed = to_body(agg_support.completed(job=job))
    completed["counts"] |= {"chunks": 2, "segments": 2, "events": AGG_EVENTS, "tracks": 0}
    send("analysis.completed", completed)
    done = collect("source.completed", lambda m: m.get("jobId") == str(job), 1, 300, since)
    moved = []
    if done:
        result = json.loads(storage.get_bytes(done[0]["resultKey"]))
        moved = [e for e in result.get("inventoryEvents", result.get("events", [])) if e.get("eventType") == "object_moved"]
        errors = schema_errors("aggregates/v1/source-result.schema.json", result)
        record("SPEC-028 결과 파일 계약", not errors, errors[:2] or "통과")
    record("SPEC-028 성공 지표 object_moved 재고 이벤트", len(moved) >= 1, f"{len(moved)}건")
    for i in range(ROUNDS):
        chunk = uuid.uuid4()
        inv = inv_support.chunk_inventory(chunk, i * 60_000, (i + 1) * 60_000,
                                          inv_support.static(f"m{i}", chunk, zone=agg_support.AISLE))
        send("chunk.manifest", inv_support.manifest_of(inv), jobId=str(uuid.uuid4()))
    handle = wait_durations("vlm-aggregator-1", "aggregator.handle", started, ROUNDS + 2, "aggregate.inventory_store")
    ok = len(handle) >= ROUNDS and p95(handle) <= 300
    record("SPEC-028 NFR-2 chunk.manifest p95 300ms", ok, f"p95 {p95(handle) if handle else '-'}ms ({len(handle)}건)")
    metric("SPEC-028", object_moved=len(moved), handle_p95_ms=p95(handle) if handle else None)


def main() -> None:
    Target.load(Path(sys.argv[1]))
    steps = [spec021_deadline, spec022_stitcher, spec023_detector, spec024_track, spec025_embedding,
             spec027_aggregate, spec028_inventory]
    only = set(sys.argv[2:])
    for step in steps:
        if only and step.__name__ not in only:
            continue
        try:
            step()
        except Exception as e:  # noqa: BLE001  # 한 측정이 깨져도 나머지 측정 결과를 보려고 모두 받는다
            record(f"예외 {step.__name__}", False, repr(e)[:300])
    (OUT / "measure-result.json").write_text(json.dumps(METRICS, ensure_ascii=False, indent=2, default=str))
    failed = [r for r in RESULTS if not r[1]]
    print(f"\n합계 {len(RESULTS)}건, 실패 {len(failed)}건")
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
