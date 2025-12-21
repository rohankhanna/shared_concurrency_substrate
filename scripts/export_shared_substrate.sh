#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: export_shared_substrate.sh --out-dir PATH [--force]

Exports the shared_concurrency_substrate folder into a standalone tree.
USAGE
}

OUT_DIR=""
FORCE=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --out-dir)
      OUT_DIR="$2"
      shift 2
      ;;
    --force)
      FORCE=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "Unknown arg: $1" >&2
      usage
      exit 1
      ;;
  esac
done

if [[ -z "$OUT_DIR" ]]; then
  echo "--out-dir is required" >&2
  usage
  exit 1
fi

if [[ -e "$OUT_DIR" && -n "$(ls -A "$OUT_DIR" 2>/dev/null)" && "$FORCE" -ne 1 ]]; then
  echo "Output dir not empty. Use --force to overwrite: $OUT_DIR" >&2
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
mkdir -p "$OUT_DIR"

rsync -a --delete "$ROOT_DIR/" "$OUT_DIR/"

chmod +x "$OUT_DIR/scripts/gate_broker.py" \
  "$OUT_DIR/scripts/gate_mount.py" \
  "$OUT_DIR/scripts/smoke_test_fifo_sshfs.sh" \
  "$OUT_DIR/scripts/build_vm_image.sh" \
  "$OUT_DIR/scripts/run_vm_qemu.sh" \
  "$OUT_DIR/scripts/build_vm_firecracker.sh" \
  "$OUT_DIR/scripts/run_vm_firecracker.sh" \
  "$OUT_DIR/scripts/setup_vm_gate.sh" \
  "$OUT_DIR/scripts/setup_host_gate.sh" \
  "$OUT_DIR/scripts/export_shared_substrate.sh"

echo "Exported shared_concurrency_substrate to: $OUT_DIR"
