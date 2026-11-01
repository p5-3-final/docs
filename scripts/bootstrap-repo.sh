#!/usr/bin/env bash
# repo-templates의 공통(_shared) + 레포별 템플릿을 repos/<name>에 복사한다.
# 이미 있는 파일은 덮어쓰지 않는다.
# 사용법: ./scripts/bootstrap-repo.sh <backend|ai|frontend|infra|gitops>
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
name="${1:?사용법: $0 <backend|ai|frontend|infra|gitops>}"
src="$ROOT/repo-templates/$name"
target="$ROOT/repos/$name"

[[ -d "$src" ]] || { echo "error: 템플릿 없음: $src" >&2; exit 1; }
mkdir -p "$target"

# 레포별 템플릿을 먼저 복사해 같은 경로의 _shared 파일보다 우선하게 한다.
rsync -a --ignore-existing "$src/" "$target/"
rsync -a --ignore-existing "$ROOT/repo-templates/_shared/" "$target/"

# Codex·Antigravity용 .agents/ 생성 (스크립트는 각 레포에서도 쓰도록 같이 복사)
mkdir -p "$target/scripts"
[[ -e "$target/scripts/sync-agent-config.sh" ]] || cp "$ROOT/scripts/sync-agent-config.sh" "$target/scripts/"
"$target/scripts/sync-agent-config.sh"

echo "bootstrap 완료: $target"
echo "다음: cd repos/$name && git status 로 추가된 파일을 확인하세요."
