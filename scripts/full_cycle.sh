#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: full_cycle.sh [options]

Options:
  --vm-name NAME         VM name (default: gate-vm)
  --vm-dir PATH          VM dir (default: ./vm_build)
  --base BASE            Base image (default: ubuntu-24.04)
  --ssh-key PATH         SSH public key (required)
  --repo-path PATH       Host repo path (required)
  --skip-build           Skip vm-build if images already exist
  --keep-vm              Keep VM running after demo
  -h, --help             Show help
USAGE
}

VM_NAME="gate-vm"
VM_DIR="./vm_build"
BASE="ubuntu-24.04"
SSH_KEY=""
REPO_PATH=""
SKIP_BUILD=0
KEEP_VM=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --vm-name) VM_NAME="$2"; shift 2;;
    --vm-dir) VM_DIR="$2"; shift 2;;
    --base) BASE="$2"; shift 2;;
    --ssh-key) SSH_KEY="$2"; shift 2;;
    --repo-path) REPO_PATH="$2"; shift 2;;
    --skip-build) SKIP_BUILD=1; shift;;
    --keep-vm) KEEP_VM=1; shift;;
    -h|--help) usage; exit 0;;
    *) echo "Unknown arg: $1" >&2; usage; exit 1;;
  esac
done

if [[ -z "$SSH_KEY" || -z "$REPO_PATH" ]]; then
  echo "--ssh-key and --repo-path are required" >&2
  usage
  exit 1
fi

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
GATE_BIN="$ROOT_DIR/dist/gate"

if [[ ! -x "$GATE_BIN" ]]; then
  echo "gate binary not found at $GATE_BIN" >&2
  exit 1
fi

"$GATE_BIN" clean --vm-name "$VM_NAME"

UP_ARGS=(
  --base "$BASE"
  --vm-dir "$VM_DIR"
  --vm-name "$VM_NAME"
  --ssh-key "$SSH_KEY"
  --repo-path "$REPO_PATH"
)
if [[ "$SKIP_BUILD" -eq 1 ]]; then
  UP_ARGS+=(--skip-build)
fi

"$GATE_BIN" up "${UP_ARGS[@]}"

GATE_DEMO_MOUNT="$HOME/.local/state/gate/mounts/gate-host-direct" \
GATE_DEMO_FILE=README.md \
python3 "$ROOT_DIR/tests/manual/lock_demo_run.py"

if [[ "$KEEP_VM" -eq 0 ]]; then
  "$GATE_BIN" down --vm-name "$VM_NAME"
fi

printf '\nFull cycle completed for %s\n' "$VM_NAME"
