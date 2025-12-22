#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: install_gate_bundle.sh [options]

Options:
  --prefix PATH      Install prefix (default: /opt/gate)
  --target-dir PATH  Repo root to mount (default: /opt/target)
  --state-dir PATH   Broker state dir (default: /var/lib/gate)
  --mount-dir PATH   FUSE mount dir (default: /mnt/gate)
  --start            Enable and start services after install
USAGE
}

PREFIX="/opt/gate"
TARGET_DIR="/opt/target"
STATE_DIR="/var/lib/gate"
MOUNT_DIR="/mnt/gate"
START=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --prefix)
      PREFIX="$2"
      shift 2
      ;;
    --target-dir)
      TARGET_DIR="$2"
      shift 2
      ;;
    --state-dir)
      STATE_DIR="$2"
      shift 2
      ;;
    --mount-dir)
      MOUNT_DIR="$2"
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

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

sudo mkdir -p "$PREFIX" /etc/gate "$STATE_DIR" "$MOUNT_DIR"

if [[ "$ROOT_DIR" != "$PREFIX" ]]; then
  sudo cp -a "$ROOT_DIR/bin" "$PREFIX/"
  sudo cp -a "$ROOT_DIR/systemd" "$PREFIX/"
  sudo cp -a "$ROOT_DIR/config" "$PREFIX/"
  sudo cp -a "$ROOT_DIR/scripts" "$PREFIX/"
fi

if [[ ! -x "$PREFIX/bin/gate" ]]; then
  echo "Gate binary not found at $PREFIX/bin/gate" >&2
  exit 1
fi

sudo install -m 0644 "$PREFIX/systemd/gate-broker.service" /etc/systemd/system/gate-broker.service
sudo install -m 0644 "$PREFIX/systemd/gate-fuse.service" /etc/systemd/system/gate-fuse.service
sudo install -m 0644 "$PREFIX/config/gate.env" /etc/gate/gate.env

sudo chmod +x "$PREFIX/bin/gate"

sudo sed -i "s|^GATE_STATE_DIR=.*|GATE_STATE_DIR=$STATE_DIR|" /etc/gate/gate.env
sudo sed -i "s|^GATE_MOUNT_DIR=.*|GATE_MOUNT_DIR=$MOUNT_DIR|" /etc/gate/gate.env
sudo sed -i "s|^GATE_REPO_DIR=.*|GATE_REPO_DIR=$TARGET_DIR|" /etc/gate/gate.env

sudo systemctl daemon-reload

if [[ "$START" -eq 1 ]]; then
  sudo systemctl enable --now gate-broker.service
  sudo systemctl enable --now gate-fuse.service
fi

echo "Gate bundle installed to $PREFIX"
echo "Target repo dir: $TARGET_DIR"
echo "Mount dir: $MOUNT_DIR"
