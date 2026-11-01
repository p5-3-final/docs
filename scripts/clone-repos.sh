#!/usr/bin/env bash
# repos.conf 목록대로 repos/ 아래에 하위 레포를 클론한다. 이미 있는 레포는 건너뛴다.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CONF="$ROOT/repos.conf"

mkdir -p "$ROOT/repos"

while read -r name url; do
  [[ -z "${name:-}" || "$name" == \#* ]] && continue

  target="$ROOT/repos/$name"
  if [[ -d "$target/.git" ]]; then
    echo "skip: $name (이미 존재)"
    continue
  fi

  echo "clone: $name <- $url"
  git clone "$url" "$target"
done < "$CONF"
