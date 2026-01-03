#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: stability_run.sh [options]

Options:
  --iterations N         Number of cycles (default: 10)
  --vm-name NAME         VM name (default: gate-vm)
  --vm-dir PATH          VM dir (default: ./vm_build)
  --base BASE            Base image (default: ubuntu-24.04)
  --ssh-key PATH         SSH public key (required)
  --repo-path PATH       Host repo path (required)
  --skip-build           Skip vm-build if images already exist
  -h, --help             Show help
USAGE
}

ITERATIONS=10
VM_NAME="gate-vm"
VM_DIR="./vm_build"
BASE="ubuntu-24.04"
SSH_KEY=""
REPO_PATH=""
SKIP_BUILD=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --iterations) ITERATIONS="$2"; shift 2;;
    --vm-name) VM_NAME="$2"; shift 2;;
    --vm-dir) VM_DIR="$2"; shift 2;;
    --base) BASE="$2"; shift 2;;
    --ssh-key) SSH_KEY="$2"; shift 2;;
    --repo-path) REPO_PATH="$2"; shift 2;;
    --skip-build) SKIP_BUILD=1; shift;;
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
CYCLE="$ROOT_DIR/scripts/full_cycle.sh"

for i in $(seq 1 "$ITERATIONS"); do
  echo "---- Cycle $i/$ITERATIONS ----"
  args=(
    --vm-name "$VM_NAME"
    --vm-dir "$VM_DIR"
    --base "$BASE"
    --ssh-key "$SSH_KEY"
    --repo-path "$REPO_PATH"
  )
  if [[ "$SKIP_BUILD" -eq 1 ]]; then
    args+=(--skip-build)
  fi
  "$CYCLE" "${args[@]}"
  echo
  sleep 1
done

printf '\nStability run completed: %s cycles\n' "$ITERATIONS"
