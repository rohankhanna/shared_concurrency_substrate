#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: build_gate_bundle.sh [options]

Options:
  --binary PATH       Path to Gate binary (default: ./dist/gate)
  --out-dir PATH      Output directory (default: ./dist)
  --name NAME         Bundle filename (default: gate_bundle.tar.gz)
USAGE
}

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BINARY="$ROOT_DIR/dist/gate"
OUT_DIR="$ROOT_DIR/dist"
NAME="gate_bundle.tar.gz"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --binary)
      BINARY="$2"
      shift 2
      ;;
    --out-dir)
      OUT_DIR="$2"
      shift 2
      ;;
    --name)
      NAME="$2"
      shift 2
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

if [[ ! -x "$BINARY" ]]; then
  echo "Gate binary not found or not executable: $BINARY" >&2
  exit 1
fi

TMP_DIR="$(mktemp -d)"
trap 'rm -rf "$TMP_DIR"' EXIT

mkdir -p "$TMP_DIR/bin" "$TMP_DIR/systemd" "$TMP_DIR/config" "$TMP_DIR/scripts"

cp "$BINARY" "$TMP_DIR/bin/gate"
cp "$ROOT_DIR/systems/gate_vm/systemd/gate-broker.service" "$TMP_DIR/systemd/"
cp "$ROOT_DIR/systems/gate_vm/systemd/gate-fuse.service" "$TMP_DIR/systemd/"
cp "$ROOT_DIR/systems/gate_vm/systemd/gate.env" "$TMP_DIR/config/gate.env"
cp "$ROOT_DIR/scripts/install_gate_bundle.sh" "$TMP_DIR/scripts/"

mkdir -p "$OUT_DIR"
tar -czf "$OUT_DIR/$NAME" -C "$TMP_DIR" .

echo "Built bundle: $OUT_DIR/$NAME"
