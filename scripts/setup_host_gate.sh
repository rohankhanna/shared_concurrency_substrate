#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: setup_host_gate.sh --vm-user USER --vm-host HOST [options]

Options:
  --vm-user USER           VM SSH user (required)
  --vm-host HOST           VM IP or hostname (required)
  --ssh-port PORT          SSH port (default: 22)
  --vm-mount PATH          VM FUSE mount path (default: /mnt/gate)
  --host-mount PATH        Host mount path (default: /mnt/gate_host)
  --install-sshfs          Install sshfs on host
  --install-nfs            Install NFS client tools on host
  --mount-method METHOD    sshfs or nfs (default: sshfs)
  --nfs-port PORT          NFS port forwarded to guest (default: 2049)
  --sync                  Rsync host repo to VM path
  --repo-path PATH         Host repo path for --sync
  --vm-repo-path PATH      VM repo path for --sync
  --bundle PATH            Gate bundle tar.gz to install in the VM
  --target-dir PATH        Repo root inside VM for gate-fuse (default: /opt/target)
  --start-gate             Start gate services after bundle install
USAGE
}

VM_USER=""
VM_HOST=""
SSH_PORT="22"
VM_MOUNT="/mnt/gate"
HOST_MOUNT="/mnt/gate_host"
INSTALL_SSHFS=0
INSTALL_NFS=0
MOUNT_METHOD="sshfs"
NFS_PORT="2049"
DO_SYNC=0
REPO_PATH=""
VM_REPO_PATH=""
BUNDLE_PATH=""
TARGET_DIR="/opt/target"
START_GATE=0

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
    --ssh-port)
      SSH_PORT="$2"
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
    --install-nfs)
      INSTALL_NFS=1
      shift
      ;;
    --mount-method)
      MOUNT_METHOD="$2"
      shift 2
      ;;
    --nfs-port)
      NFS_PORT="$2"
      shift 2
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
    --bundle)
      BUNDLE_PATH="$2"
      shift 2
      ;;
    --target-dir)
      TARGET_DIR="$2"
      shift 2
      ;;
    --start-gate)
      START_GATE=1
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

if [[ -z "$VM_USER" || -z "$VM_HOST" ]]; then
  echo "--vm-user and --vm-host are required" >&2
  usage
  exit 1
fi
if [[ "$MOUNT_METHOD" != "sshfs" && "$MOUNT_METHOD" != "nfs" ]]; then
  echo "--mount-method must be sshfs or nfs" >&2
  exit 1
fi

if [[ "$INSTALL_SSHFS" -eq 1 ]]; then
  sudo apt-get update
  sudo apt-get install -y sshfs
fi
if [[ "$INSTALL_NFS" -eq 1 ]]; then
  sudo apt-get update
  sudo apt-get install -y nfs-common
fi

if [[ "$DO_SYNC" -eq 1 ]]; then
  if [[ -z "$REPO_PATH" || -z "$VM_REPO_PATH" ]]; then
    echo "--repo-path and --vm-repo-path are required with --sync" >&2
    usage
    exit 1
  fi
  rsync -a --delete -e "ssh -p $SSH_PORT" "$REPO_PATH/" "$VM_USER@$VM_HOST:$VM_REPO_PATH/"
fi

if [[ -n "$BUNDLE_PATH" ]]; then
  if [[ ! -f "$BUNDLE_PATH" ]]; then
    echo "Bundle not found: $BUNDLE_PATH" >&2
    exit 1
  fi
  scp -P "$SSH_PORT" "$BUNDLE_PATH" "$VM_USER@$VM_HOST:/tmp/gate_bundle.tar.gz"
  START_FLAG=""
  if [[ "$START_GATE" -eq 1 ]]; then
    START_FLAG="--start"
  fi
  ssh -p "$SSH_PORT" "$VM_USER@$VM_HOST" \
    "sudo mkdir -p /opt/gate && sudo tar -xzf /tmp/gate_bundle.tar.gz -C /opt/gate && sudo chmod +x /opt/gate/bin/gate && sudo /opt/gate/bin/gate bundle-install --target-dir \"$TARGET_DIR\" $START_FLAG"
fi

mkdir -p "$HOST_MOUNT"
if [[ "$MOUNT_METHOD" == "nfs" ]]; then
  sudo mount -t nfs4 -o "vers=4,proto=tcp,port=$NFS_PORT" "$VM_HOST:/" "$HOST_MOUNT"
  echo "Mounted VM view via NFS at $HOST_MOUNT"
else
  sshfs -o "port=$SSH_PORT" "$VM_USER@$VM_HOST:$VM_MOUNT" "$HOST_MOUNT"
  echo "Mounted VM view via SSHFS at $HOST_MOUNT"
fi
