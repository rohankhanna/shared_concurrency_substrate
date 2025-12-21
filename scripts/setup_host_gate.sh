#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: setup_host_gate.sh --vm-user USER --vm-host HOST [options]

Options:
  --vm-user USER           VM SSH user (required)
  --vm-host HOST           VM IP or hostname (required)
  --vm-mount PATH          VM FUSE mount path (default: /mnt/gate)
  --host-mount PATH        Host mount path (default: /mnt/gate_host)
  --install-sshfs          Install sshfs on host
  --sync                  Rsync host repo to VM path
  --repo-path PATH         Host repo path for --sync
  --vm-repo-path PATH      VM repo path for --sync
USAGE
}

VM_USER=""
VM_HOST=""
VM_MOUNT="/mnt/gate"
HOST_MOUNT="/mnt/gate_host"
INSTALL_SSHFS=0
DO_SYNC=0
REPO_PATH=""
VM_REPO_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --vm-user)
      VM_USER="$2"
      shift 2
      ;;
    --vm-host)
      VM_HOST="$2"
      shift 2
      ;;
    --vm-mount)
      VM_MOUNT="$2"
      shift 2
      ;;
    --host-mount)
      HOST_MOUNT="$2"
      shift 2
      ;;
    --install-sshfs)
      INSTALL_SSHFS=1
      shift
      ;;
    --sync)
      DO_SYNC=1
      shift
      ;;
    --repo-path)
      REPO_PATH="$2"
      shift 2
      ;;
    --vm-repo-path)
      VM_REPO_PATH="$2"
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

if [[ -z "$VM_USER" || -z "$VM_HOST" ]]; then
  echo "--vm-user and --vm-host are required" >&2
  usage
  exit 1
fi

if [[ "$INSTALL_SSHFS" -eq 1 ]]; then
  sudo apt-get update
  sudo apt-get install -y sshfs
fi

if [[ "$DO_SYNC" -eq 1 ]]; then
  if [[ -z "$REPO_PATH" || -z "$VM_REPO_PATH" ]]; then
    echo "--repo-path and --vm-repo-path are required with --sync" >&2
    usage
    exit 1
  fi
  rsync -a --delete "$REPO_PATH/" "$VM_USER@$VM_HOST:$VM_REPO_PATH/"
fi

mkdir -p "$HOST_MOUNT"
sshfs "$VM_USER@$VM_HOST:$VM_MOUNT" "$HOST_MOUNT"

echo "Mounted VM view at $HOST_MOUNT"
