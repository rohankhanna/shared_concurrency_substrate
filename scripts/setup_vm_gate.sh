#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: setup_vm_gate.sh [options]

Options:
  --target-dir PATH        Repo root to mount (default: /opt/target)
  --state-dir PATH         State dir for broker DB (default: /var/lib/gate)
  --mount-path PATH        FUSE mount path (default: /mnt/gate)
  --broker-host HOST       Broker host (default: 127.0.0.1)
  --broker-port PORT       Broker port (default: 8787)
  --start                  Start broker and mount after install
USAGE
}

TARGET_DIR="/opt/target"
STATE_DIR="/var/lib/gate"
MOUNT_PATH="/mnt/gate"
BROKER_HOST="127.0.0.1"
BROKER_PORT="8787"
START=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --target-dir)
      TARGET_DIR="$2"
      shift 2
      ;;
    --state-dir)
      STATE_DIR="$2"
      shift 2
      ;;
    --mount-path)
      MOUNT_PATH="$2"
      shift 2
      ;;
    --broker-host)
      BROKER_HOST="$2"
      shift 2
      ;;
    --broker-port)
      BROKER_PORT="$2"
      shift 2
      ;;
    --start)
      START=1
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

sudo apt-get update
sudo apt-get install -y fuse openssh-server python3 python3-pip

sudo mkdir -p "$STATE_DIR"
sudo chown "$USER":"$USER" "$STATE_DIR"

sudo mkdir -p "$TARGET_DIR"

sudo systemctl enable --now ssh

mkdir -p "$MOUNT_PATH"

if [[ -f "/opt/gate/requirements.txt" ]]; then
  python3 -m pip install -r /opt/gate/requirements.txt
fi

if [[ -x "/opt/gate/bin/gate" ]]; then
  BROKER_CMD="/opt/gate/bin/gate broker"
  MOUNT_CMD="/opt/gate/bin/gate mount"
elif [[ -f "/opt/gate/scripts/gate_broker.py" && -f "/opt/gate/scripts/gate_mount.py" ]]; then
  BROKER_CMD="python3 /opt/gate/scripts/gate_broker.py"
  MOUNT_CMD="python3 /opt/gate/scripts/gate_mount.py"
else
  echo "Gate not found in /opt/gate (no binary or Python scripts)." >&2
  exit 1
fi

if [[ "$START" -eq 1 ]]; then
  BROKER_LOG="$STATE_DIR/broker.log"
  FUSE_LOG="$STATE_DIR/fuse.log"
  nohup $BROKER_CMD \
    --state-dir "$STATE_DIR" \
    --host "$BROKER_HOST" \
    --port "$BROKER_PORT" \
    >"$BROKER_LOG" 2>&1 &

  nohup $MOUNT_CMD \
    --root "$TARGET_DIR" \
    --mount "$MOUNT_PATH" \
    --broker-host "$BROKER_HOST" \
    --broker-port "$BROKER_PORT" \
    >"$FUSE_LOG" 2>&1 &

  echo "Started broker and FUSE mount. Logs: $BROKER_LOG, $FUSE_LOG"
else
  cat <<EOM
Install complete. Start services with:
  $BROKER_CMD --state-dir "$STATE_DIR" --host "$BROKER_HOST" --port "$BROKER_PORT"
  $MOUNT_CMD --root "$TARGET_DIR" --mount "$MOUNT_PATH" --broker-host "$BROKER_HOST" --broker-port "$BROKER_PORT" --foreground
EOM
fi
