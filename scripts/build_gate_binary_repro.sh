#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Best-effort reproducible build settings
export TZ=UTC
export PYTHONHASHSEED=0
if [[ -z "${SOURCE_DATE_EPOCH:-}" ]]; then
  # Use last git commit time if available, else current time
  if command -v git >/dev/null 2>&1; then
    SOURCE_DATE_EPOCH=$(git -C "$ROOT_DIR" log -1 --format=%ct 2>/dev/null || date +%s)
  else
    SOURCE_DATE_EPOCH=$(date +%s)
  fi
fi
export SOURCE_DATE_EPOCH

"$ROOT_DIR/scripts/build_gate_binary.sh" "$@"
