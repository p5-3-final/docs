#!/usr/bin/env bash
# 계약 파일을 바꾼 PR이 VERSION을 올렸는지 검사한다(ADR-0013).
#   scripts/check-service-contracts-version.sh <base 커밋>
# README만 바꾼 경우는 설명 변경이라 버전을 올리지 않아도 된다.
set -euo pipefail

base="${1:?base 커밋을 넘긴다}"
source_dir="service-contracts"

changed="$(git diff --name-only "${base}...HEAD" -- "${source_dir}" ":(exclude)${source_dir}/README.md")"
if [[ -z "${changed}" ]]; then
  echo "계약 파일 변경 없음"
  exit 0
fi

semver='^[0-9]+\.[0-9]+\.[0-9]+$'
new="$(tr -d '[:space:]' < "${source_dir}/VERSION")"
old="$(git show "${base}:${source_dir}/VERSION" 2>/dev/null | tr -d '[:space:]' || true)"
old="${old:-0.0.0}"

if [[ ! "${new}" =~ ${semver} ]]; then
  echo "::error file=${source_dir}/VERSION::SemVer 형식이 아니다: '${new}'"
  exit 1
fi
if [[ "${new}" == "${old}" ]] || [[ "$(printf '%s\n%s\n' "${old}" "${new}" | sort -V | tail -n1)" != "${new}" ]]; then
  echo "::error file=${source_dir}/VERSION::계약을 바꿨으면 VERSION을 ${old}보다 올린다(추가 minor, 설명 patch, 하위호환 파괴 major)"
  printf '바뀐 계약 파일:\n%s\n' "${changed}"
  exit 1
fi
echo "VERSION ${old} → ${new}"
