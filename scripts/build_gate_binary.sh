#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: build_gate_binary.sh [options]

Options:
  --name NAME         Output binary name (default: gate)
  --out-dir PATH      Output directory (default: ./dist)
  --python PATH       Python interpreter (default: python3)
  --build-dir PATH    Build working dir (default: ./.build_gate)
USAGE
}

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
NAME="gate"
OUT_DIR="$ROOT_DIR/dist"
PYTHON_BIN="python3"
BUILD_DIR="$ROOT_DIR/.build_gate"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --name)
      NAME="$2"
      shift 2
      ;;
    --out-dir)
      OUT_DIR="$2"
      shift 2
      ;;
    --python)
      PYTHON_BIN="$2"
      shift 2
      ;;
    --build-dir)
      BUILD_DIR="$2"
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

if ! command -v "$PYTHON_BIN" >/dev/null 2>&1; then
  echo "Python not found: $PYTHON_BIN" >&2
  exit 1
fi

ENTRYPOINT="$ROOT_DIR/scripts/gate_cli.py"
VENV_DIR="$BUILD_DIR/venv"
PYI_WORK="$BUILD_DIR/pyinstaller"
PYI_SPEC="$BUILD_DIR/spec"

mkdir -p "$BUILD_DIR" "$OUT_DIR"

"$PYTHON_BIN" -m venv "$VENV_DIR"
source "$VENV_DIR/bin/activate"
python -m pip install --upgrade pip >/dev/null
python -m pip install -r "$ROOT_DIR/requirements.txt" pyinstaller >/dev/null

pyinstaller \
  --onefile \
  --name "$NAME" \
  --distpath "$OUT_DIR" \
  --workpath "$PYI_WORK" \
  --specpath "$PYI_SPEC" \
  "$ENTRYPOINT"

deactivate

echo "Built binary: $OUT_DIR/$NAME"
