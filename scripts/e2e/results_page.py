"""workers·quality 결과 출력(PASS/FAIL 줄)을 녹화 화면에 띄울 HTML 한 장으로 만든다.

실행: `python3 scripts/e2e/results_page.py <출력 폴더>` (run.sh record가 부른다)
"""

import html
import sys
from pathlib import Path

STYLE = """body{font:15px/1.5 -apple-system,"Apple SD Gothic Neo",sans-serif;background:#0f172a;color:#e2e8f0;margin:32px}
h1{font-size:22px} h2{font-size:17px;margin-top:28px;color:#5eead4} ul{list-style:none;padding:0}
li{padding:4px 8px;border-bottom:1px solid #1e293b;font-family:ui-monospace,monospace;font-size:13px;word-break:break-all}
b{display:inline-block;width:48px} .pass b{color:#4ade80} .fail b{color:#f87171} .sum{color:#facc15;font-weight:600}"""


def rows(path: Path) -> str:
    if not path.exists():
        return '<li class="fail"><b>없음</b> 결과 파일이 없다. run.sh로 먼저 실행한다.</li>'
    out = []
    for line in path.read_text().splitlines():
        if line.startswith(("[PASS]", "[FAIL]")):
            ok = line.startswith("[PASS]")
            label = "PASS" if ok else "FAIL"
            out.append(f'<li class="{label.lower()}"><b>{label}</b> {html.escape(line[7:])}</li>')
        elif line.startswith("합계"):
            out.append(f'<li class="sum">{html.escape(line)}</li>')
    return "\n".join(out)


def main() -> None:
    out = Path(sys.argv[1])
    page = f"""<!doctype html><html lang="ko"><meta charset="utf-8"><title>compose E2E 결과</title>
<style>{STYLE}</style>
<h1>로컬 compose E2E 실행 결과</h1>
<h2>워커 흐름 다섯 갈래 (Kafka → 워커 → 저장소)</h2><ul>{rows(out / "workers-result.txt")}</ul>
<h2>quality API (api-gateway 경유)</h2><ul>{rows(out / "quality-result.txt")}</ul></html>"""
    (out / "results.html").write_text(page)


if __name__ == "__main__":
    main()
