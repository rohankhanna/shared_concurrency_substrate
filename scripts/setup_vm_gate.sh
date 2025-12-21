#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: setup_vm_gate.sh --repo-path /path/to/repo [options]

Options:
  --repo-path PATH         Real repo path inside the VM (required)
  --state-dir PATH         State dir for broker DB (default: /var/lib/gate)
  --mount-path PATH        FUSE mount path (default: /mnt/gate)
  --broker-host HOST       Broker host (default: 127.0.0.1)
  --broker-port PORT       Broker port (default: 8787)
  --start                  Start broker and mount after install
USAGE
}

REPO_PATH=""
STATE_DIR="/var/lib/gate"
MOUNT_PATH="/mnt/gate"
BROKER_HOST="127.0.0.1"
BROKER_PORT="8787"
START=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --repo-path)
      REPO_PATH="$2"
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

if [[ -z "$REPO_PATH" ]]; then
  echo "--repo-path is required" >&2
  usage
  exit 1
fi

if [[ ! -d "$REPO_PATH" ]]; then
  echo "Repo path not found: $REPO_PATH" >&2
  exit 1
fi

sudo apt-get update
sudo apt-get install -y fuse openssh-server python3 python3-pip

sudo mkdir -p "$STATE_DIR"
sudo chown "$USER":"$USER" "$STATE_DIR"

python3 -m pip install -r "$REPO_PATH/requirements.txt"

sudo systemctl enable --now ssh

mkdir -p "$MOUNT_PATH"

if [[ "$START" -eq 1 ]]; then
  BROKER_LOG="$STATE_DIR/broker.log"
  FUSE_LOG="$STATE_DIR/fuse.log"
  nohup python3 "$REPO_PATH/scripts/gate_broker.py" \
    --state-dir "$STATE_DIR" \
    --host "$BROKER_HOST" \
    --port "$BROKER_PORT" \
    >"$BROKER_LOG" 2>&1 &

  nohup python3 "$REPO_PATH/scripts/gate_mount.py" \
    --root "$REPO_PATH" \
    --mount "$MOUNT_PATH" \
    --broker-host "$BROKER_HOST" \
    --broker-port "$BROKER_PORT" \
    >"$FUSE_LOG" 2>&1 &

  echo "Started broker and FUSE mount. Logs: $BROKER_LOG, $FUSE_LOG"
else
  cat <<'EOM'
Install complete. Start services with:
  python3 "$REPO_PATH/scripts/gate_broker.py" --state-dir "$STATE_DIR" --host "$BROKER_HOST" --port "$BROKER_PORT"
  python3 "$REPO_PATH/scripts/gate_mount.py" --root "$REPO_PATH" --mount "$MOUNT_PATH" --broker-host "$BROKER_HOST" --broker-port "$BROKER_PORT" --foreground
EOM
fi
