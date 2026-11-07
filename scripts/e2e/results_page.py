"""E2E 결과를 녹화 화면에 띄울 HTML 한 장으로 만든다.

웹 화면은 분석·검색 결과를 analysis-service·search-service에서 읽는데 로컬에 아직 없어서, 워커가 남긴 결과물
(workers.py의 artifacts.json, 이미지, 저장소의 클립)을 이 페이지로 보여 준다.
실행: `python3 scripts/e2e/results_page.py <출력 폴더>` (run.sh record가 부른다)
"""

import html
import json
import sys
from pathlib import Path

FILER = "http://localhost:8888/buckets/vlm-media/"
STYLE = """
body{font:15px/1.55 -apple-system,"Apple SD Gothic Neo",sans-serif;background:#0f172a;color:#e2e8f0;margin:0;padding:32px 40px}
h1{font-size:24px;margin:0 0 4px} .sub{color:#94a3b8;margin:0 0 24px}
section{background:#111c33;border:1px solid #1e293b;border-radius:14px;padding:20px 24px;margin:0 0 22px}
h2{font-size:18px;margin:0 0 4px;color:#5eead4} .note{color:#94a3b8;font-size:13px;margin:0 0 14px}
.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:10px} .grid figure{margin:0}
.grid img{width:100%;border-radius:8px;display:block} figcaption{font-size:12px;color:#94a3b8;margin-top:4px}
table{border-collapse:collapse;width:100%;font-size:14px} td,th{padding:6px 10px;border-bottom:1px solid #1e293b;text-align:left}
th{color:#94a3b8;font-weight:500} .score{font-family:ui-monospace,monospace}
.row{display:flex;gap:20px;align-items:flex-start} .crops img{height:220px;border-radius:8px;margin-right:8px}
pre{background:#0b1222;padding:12px;border-radius:8px;white-space:pre-wrap;font-size:13px;margin:0}
.quote{font-size:17px;border-left:3px solid #5eead4;padding:6px 14px;margin:6px 0}
video{width:100%;max-width:960px;border-radius:10px}
ul{list-style:none;padding:0;margin:0} li{font-family:ui-monospace,monospace;font-size:12.5px;padding:3px 0;border-bottom:1px solid #1e293b;word-break:break-all}
.pass b{color:#4ade80} .fail b{color:#f87171} b{display:inline-block;width:44px} .sum{color:#facc15;font-weight:600}
"""


def e(value: object) -> str:
    return html.escape(str(value))


def search_section(a: dict) -> str:
    search = a.get("search")
    if not search:
        return ""
    figures = "".join(
        f'<figure><img src="{e(f["file"])}"><figcaption>{f["startMs"] // 1000}초 구간</figcaption></figure>'
        for f in search["frames"]
    )
    rows = "".join(
        f"<tr><td>{e(r['query'])}</td>"
        + "".join(f'<td class="score">{t["startMs"] // 1000}초 · {t["score"]:.3f}</td>' for t in r["top"])
        + "</tr>"
        for r in search["ranking"]
    )
    return f"""<section><h2>1. 구간 벡터와 검색 순위 (MobileCLIP2-S0)</h2>
<p class="note">관리자 영상에서 90초 간격 8구간의 실제 프레임을 벡터로 만들고, 검색 문장 벡터와 코사인 유사도로 순위를 낸다.</p>
<div class="grid">{figures}</div><br>
<table><tr><th>검색 문장</th><th>1위</th><th>2위</th><th>3위</th></tr>{rows}</table></section>"""


def attribute_section(a: dict) -> str:
    attr = a.get("attributes")
    if not attr:
        return ""
    crops = "".join(f'<img src="crop-{i}.jpg">' for i in range(attr.get("crops", 0)))
    body = json.dumps(attr.get("attributes"), ensure_ascii=False, indent=2)
    return f"""<section><h2>2. 트랙 속성 분석 ({e(attr.get('modelId'))})</h2>
<p class="note">110초 장면에서 카트를 미는 작업자 크롭 두 장. 기대값: 사람, 안전모·조끼 없음, 카트.</p>
<div class="row"><div class="crops">{crops}</div><pre>{e(body)}</pre></div></section>"""


def grounding_section(a: dict) -> str:
    g = a.get("grounding")
    if not g:
        return ""
    return f"""<section><h2>3. 주석 클립 (grounding-worker, mock 탐지기)</h2>
<p class="note">관리자 영상 40~50초 정규화 사본에 박스를 그린 클립. 실제 탐지기가 아직 없어 박스 위치에는 의미가 없다.</p>
<video id="clip" src="{FILER}{e(g['clipKey'])}" controls muted></video></section>"""


def aggregate_section(a: dict) -> str:
    agg = a.get("aggregate")
    if not agg:
        return ""
    return f"""<section><h2>4. 영상 단위 집계와 요약 ({e(agg.get('modelId'))})</h2>
<p class="note">입력 이벤트 2건(테스트 데이터)을 병합해 위험 상태를 만들고, 요약 문장을 생성한다.</p>
<p class="quote">{e(agg.get('summary'))}</p></section>"""


def checks_section(out: Path) -> str:
    items = []
    for name in ("workers-result.txt", "quality-result.txt"):
        path = out / name
        for line in path.read_text().splitlines() if path.exists() else []:
            if line.startswith(("[PASS]", "[FAIL]")):
                label = line[1:5]
                items.append(f'<li class="{label.lower()}"><b>{label}</b> {e(line[7:])}</li>')
            elif line.startswith("합계"):
                items.append(f'<li class="sum">{e(line)}</li>')
    return f'<section><h2>5. 검사 출력</h2><ul>{"".join(items)}</ul></section>'


def main() -> None:
    out = Path(sys.argv[1])
    path = out / "artifacts.json"
    a = json.loads(path.read_text()) if path.exists() else {}
    target = a.get("target", {})
    page = f"""<!doctype html><html lang="ko"><meta charset="utf-8"><title>E2E 분석 결과</title><style>{STYLE}</style>
<h1>로컬 compose E2E 분석 결과</h1>
<p class="sub">계정 {e(target.get('email', '-'))} · 영상 {e(target.get('videoId', '-'))}</p>
{search_section(a)}{attribute_section(a)}{grounding_section(a)}{aggregate_section(a)}{checks_section(out)}</html>"""
    (out / "results.html").write_text(page)


if __name__ == "__main__":
    main()
