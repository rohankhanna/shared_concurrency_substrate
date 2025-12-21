#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARTIFACTS_DIR="$ROOT_DIR/artifacts"
FC_BIN="$ARTIFACTS_DIR/firecracker"
KERNEL_PATH="$ARTIFACTS_DIR/vmlinux"
ROOTFS_PATH="$ARTIFACTS_DIR/rootfs.ext4"
SOCK="/tmp/firecracker-${USER}.sock"
LOG_FILE="$ROOT_DIR/firecracker.log"
CONSOLE_FILE="$ROOT_DIR/console.log"
CONFIG_TEMPLATE="$ROOT_DIR/config.json"
CONFIG_RENDER="$ROOT_DIR/.firecracker_config.json"
MACHINE_JSON="$ROOT_DIR/.machine.json"
BOOT_JSON="$ROOT_DIR/.boot.json"
DRIVE_JSON="$ROOT_DIR/.drive.json"

if [[ ! -e /dev/kvm ]]; then
  echo "/dev/kvm not found. Enable KVM and retry." >&2
  exit 1
fi

if [[ ! -x "$FC_BIN" ]]; then
  echo "Firecracker binary not found or not executable at $FC_BIN" >&2
  exit 1
fi

if [[ ! -f "$KERNEL_PATH" ]]; then
  echo "Kernel image not found at $KERNEL_PATH" >&2
  exit 1
fi

if [[ ! -f "$ROOTFS_PATH" ]]; then
  echo "Rootfs image not found at $ROOTFS_PATH" >&2
  exit 1
fi

rm -f "$SOCK" "$CONSOLE_FILE"

"$FC_BIN" --api-sock "$SOCK" --log-path "$LOG_FILE" >"$CONSOLE_FILE" 2>&1 &
FC_PID=$!

cleanup() {
  kill "$FC_PID" >/dev/null 2>&1 || true
}
trap cleanup EXIT

for _ in {1..50}; do
  if [[ -S "$SOCK" ]]; then
    break
  fi
  sleep 0.1
done

if [[ ! -S "$SOCK" ]]; then
  echo "Firecracker API socket not ready: $SOCK" >&2
  exit 1
fi

export KERNEL_PATH ROOTFS_PATH CONFIG_TEMPLATE CONFIG_RENDER MACHINE_JSON BOOT_JSON DRIVE_JSON
python3 - <<'PY'
import json
import os
from pathlib import Path

template = Path(os.environ["CONFIG_TEMPLATE"]).read_text()
rendered = (
    template.replace("${KERNEL_PATH}", os.environ["KERNEL_PATH"])
    .replace("${ROOTFS_PATH}", os.environ["ROOTFS_PATH"])
)
Path(os.environ["CONFIG_RENDER"]).write_text(rendered)

cfg = json.loads(rendered)
Path(os.environ["MACHINE_JSON"]).write_text(json.dumps(cfg["machine-config"]))
Path(os.environ["BOOT_JSON"]).write_text(json.dumps(cfg["boot-source"]))
Path(os.environ["DRIVE_JSON"]).write_text(json.dumps(cfg["drives"][0]))
PY

curl --unix-socket "$SOCK" -s -X PUT "http://localhost/machine-config" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d "@$MACHINE_JSON" >/dev/null

curl --unix-socket "$SOCK" -s -X PUT "http://localhost/boot-source" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d "@$BOOT_JSON" >/dev/null

curl --unix-socket "$SOCK" -s -X PUT "http://localhost/drives/rootfs" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d "@$DRIVE_JSON" >/dev/null

curl --unix-socket "$SOCK" -s -X PUT "http://localhost/actions" \
  -H "Accept: application/json" \
  -H "Content-Type: application/json" \
  -d '{"action_type":"InstanceStart"}' >/dev/null

sleep 2
echo "Firecracker started. Check $LOG_FILE for VMM logs and $CONSOLE_FILE for guest output."
