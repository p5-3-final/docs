#!/usr/bin/env bash
# docs/architecture/architecture.md를 같은 폴더의 architecture.html로 변환한다.
# md를 고치면 이 스크립트를 실행해 html을 같이 갱신한다. --check는 생성 결과가 저장된 html과 같은지만 확인한다(CI용).
# Mermaid 그림은 html을 여는 브라우저가 그린다(CDN). pandoc 3 이상이 필요하다.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
SRC="$ROOT/docs/architecture/architecture.md"
OUT="$ROOT/docs/architecture/architecture.html"
ASSETS="$ROOT/scripts/architecture-html"
PANDOC="${PANDOC:-pandoc}"

if ! command -v "$PANDOC" >/dev/null 2>&1; then
  echo "pandoc이 없다. brew install pandoc 또는 PANDOC=<경로>로 지정한다." >&2
  exit 1
fi

render() {
  "$PANDOC" "$SRC" \
    --from gfm+yaml_metadata_block --to html5 \
    --template "$ASSETS/template.html" --include-in-header "$ASSETS/header.html" \
    --lua-filter "$ASSETS/mermaid.lua" --toc --toc-depth=3 \
    --metadata title="VLM 영상 분석 아키텍처 v5" \
    -o "$1"
}

if [[ "${1:-}" == "--check" ]]; then
  tmp="$(mktemp)"
  trap 'rm -f "$tmp"' EXIT
  render "$tmp"
  if cmp -s "$tmp" "$OUT"; then
    echo "architecture.html이 최신이다."
  else
    echo "architecture.html이 architecture.md와 다르다. scripts/render-architecture-html.sh를 실행한다." >&2
    exit 1
  fi
else
  render "$OUT"
  echo "생성: $OUT"
fi
