"""fullvideo.py 결과를 녹화 화면에 띄울 HTML 한 장으로 만든다.

검색어마다 질의 해석 결과, 영상 전체 구간의 유사도 곡선(상위 3구간 표시), 상위 3구간의 주석 클립을 보여 준다.
실행: `python3 scripts/e2e/fullvideo_page.py <출력 폴더>` (run.sh record-full이 부른다)
"""

import html
import json
import sys
from pathlib import Path

from results_page import FILER, STYLE

EXTRA_STYLE = """
.clips{display:grid;grid-template-columns:repeat(3,1fr);gap:12px} .clips video,.clips img{width:100%;border-radius:8px}
.clips figure{margin:0}
.meta{font-family:ui-monospace,monospace;font-size:13px;color:#cbd5e1;margin:0 0 10px}
.chart{width:100%;height:120px;background:#0b1222;border-radius:8px;margin:0 0 12px}
"""
CHART_W, CHART_H = 1000, 120


def e(value: object) -> str:
    return html.escape(str(value))


def mmss(ms: int) -> str:
    return f"{ms // 60_000}:{ms // 1000 % 60:02d}"


def chart(q: dict, duration_ms: int) -> str:
    """영상 전체 구간의 유사도를 선으로 그리고 상위 3구간을 점으로 찍는다."""
    scores = [p["score"] for p in q["timeline"]]
    low, high = min(scores), max(scores)
    span = (high - low) or 1

    def x(ms: int) -> float:
        return ms / duration_ms * CHART_W

    def y(score: float) -> float:
        return CHART_H - 10 - (score - low) / span * (CHART_H - 20)

    line = " ".join(f"{x(p['startMs']):.1f},{y(p['score']):.1f}" for p in q["timeline"])
    dots = "".join(
        f'<circle cx="{x(t["startMs"]):.1f}" cy="{y(t["score"]):.1f}" r="6" fill="#facc15"/>'
        f'<text x="{x(t["startMs"]) + 8:.1f}" y="{16 + 14 * i}" fill="#facc15" font-size="13">'
        f'{i + 1}위 {mmss(t["startMs"])}</text>'
        for i, t in enumerate(q["top"])
    )
    return (f'<svg class="chart" viewBox="0 0 {CHART_W} {CHART_H}" preserveAspectRatio="none">'
            f'<polyline points="{line}" fill="none" stroke="#5eead4" stroke-width="2"/>{dots}</svg>')


def clip_figure(rank: int, t: dict) -> str:
    if not t.get("clipKey"):
        return f'<figure><img src="{e(t["thumb"])}"><figcaption>{rank + 1}위 클립 없음</figcaption></figure>'
    return (f'<figure><video src="{FILER}{e(t["clipKey"])}" poster="{e(t["thumb"])}" muted></video>'
            f'<figcaption>{rank + 1}위 · {mmss(t["startMs"])}~{mmss(t["startMs"] + 10_000)} · 유사도 {t["score"]:.3f}'
            f' · 박스 {t["boxes"]}개(샘플 10장 합)</figcaption></figure>')


def query_section(i: int, q: dict, duration_ms: int) -> str:
    clips = "".join(clip_figure(rank, t) for rank, t in enumerate(q["top"]))
    return f"""<section><h2>{i + 1}. "{e(q['query'])}"</h2>
<p class="meta">질의 해석({e(q['parseMethod'])}) → 대상어 {e(', '.join(q['targets']))} · 검색 문장 "{e(q['visualQuery'])}"</p>
{chart(q, duration_ms)}<div class="clips">{clips}</div></section>"""


def main() -> None:
    out = Path(sys.argv[1])
    r = json.loads((out / "fullvideo.json").read_text())
    sections = "".join(query_section(i, q, r["durationMs"]) for i, q in enumerate(r["queries"]))
    page = f"""<!doctype html><html lang="ko"><meta charset="utf-8"><title>전체 영상 검색 결과</title>
<style>{STYLE}{EXTRA_STYLE}</style>
<h1>전체 영상 검색과 박스 주석</h1>
<p class="sub">계정 {e(r['email'])} · 영상 {e(r['videoId'])} · 길이 {mmss(r['durationMs'])} · 구간 {r['segments']}개(10초 창, 5초 간격)
· 구간 벡터 MobileCLIP2-S0 · 박스 OWL-ViT base patch32</p>
<p class="note">선은 영상 전체 구간의 검색 문장 유사도, 노란 점은 겹치지 않는 상위 3구간이다. 아래 클립은 그 3구간에 대상어 박스를 그린 결과다.</p>
{sections}</html>"""
    (out / "fullvideo.html").write_text(page, encoding="utf-8")
    print(f"페이지: {out / 'fullvideo.html'}")


if __name__ == "__main__":
    main()
