#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: build_vm_firecracker.sh --repo-url URL --ssh-key PATH [options]

Options:
  --base BASE              ubuntu-22.04 (default) or debian-12
  --vm-dir PATH            Output directory for VM artifacts (default: ./vm_firecracker)
  --vm-name NAME           VM name (default: gate-fc)
  --repo-url URL           Git repo URL to clone inside VM (required)
  --repo-branch BRANCH     Git branch (default: main)
  --ssh-key PATH           Public SSH key file to authorize (required)
USAGE
}

BASE="ubuntu-22.04"
VM_DIR="./vm_firecracker"
VM_NAME="gate-fc"
REPO_URL=""
REPO_BRANCH="main"
SSH_KEY_PATH=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --base)
      BASE="$2"
      shift 2
      ;;
    --vm-dir)
      VM_DIR="$2"
      shift 2
      ;;
    --vm-name)
      VM_NAME="$2"
      shift 2
      ;;
    --repo-url)
      REPO_URL="$2"
      shift 2
      ;;
    --repo-branch)
      REPO_BRANCH="$2"
      shift 2
      ;;
    --ssh-key)
      SSH_KEY_PATH="$2"
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

if [[ -z "$REPO_URL" || -z "$SSH_KEY_PATH" ]]; then
  echo "--repo-url and --ssh-key are required" >&2
  usage
  exit 1
fi

if [[ ! -f "$SSH_KEY_PATH" ]]; then
  echo "SSH key not found: $SSH_KEY_PATH" >&2
  exit 1
fi

for cmd in cloud-localds qemu-img guestmount guestunmount; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing $cmd. Install cloud-image-utils, qemu-utils, and libguestfs-tools." >&2
    exit 1
  fi
done

BASE_URL=""
BASE_FILE=""
case "$BASE" in
  ubuntu-22.04)
    BASE_URL="https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img"
    BASE_FILE="ubuntu-22.04-base.qcow2"
    ;;
  debian-12)
    BASE_URL="https://cloud.debian.org/images/cloud/bookworm/latest/debian-12-genericcloud-amd64.qcow2"
    BASE_FILE="debian-12-base.qcow2"
    ;;
  *)
    echo "Unsupported base: $BASE" >&2
    exit 1
    ;;
 esac

mkdir -p "$VM_DIR"
BASE_PATH="$VM_DIR/$BASE_FILE"
ROOT_RAW="$VM_DIR/${VM_NAME}-rootfs.raw"
SEED_PATH="$VM_DIR/${VM_NAME}-seed.img"
VMLINUX_PATH="$VM_DIR/${VM_NAME}-vmlinux"
INITRD_PATH="$VM_DIR/${VM_NAME}-initrd"
USER_DATA="$VM_DIR/user-data"
META_DATA="$VM_DIR/meta-data"

if [[ ! -f "$BASE_PATH" ]]; then
  echo "Downloading base image: $BASE_URL"
  curl -fsSL -o "$BASE_PATH" "$BASE_URL"
fi

SSH_KEY=$(cat "$SSH_KEY_PATH")

TEMPLATE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../systems/gate_vm/cloud_init" && pwd)"
USER_TEMPLATE="$TEMPLATE_DIR/user-data.template"
META_TEMPLATE="$TEMPLATE_DIR/meta-data.template"

sed \
  -e "s|__VM_NAME__|$VM_NAME|g" \
  "$META_TEMPLATE" > "$META_DATA"

sed \
  -e "s|__SSH_KEY__|$SSH_KEY|g" \
  -e "s|__REPO_URL__|$REPO_URL|g" \
  -e "s|__REPO_BRANCH__|$REPO_BRANCH|g" \
  "$USER_TEMPLATE" > "$USER_DATA"

cloud-localds "$SEED_PATH" "$USER_DATA" "$META_DATA"

if [[ ! -f "$ROOT_RAW" ]]; then
  qemu-img convert -O raw "$BASE_PATH" "$ROOT_RAW"
fi

MOUNT_DIR=$(mktemp -d)
trap 'guestunmount "$MOUNT_DIR" >/dev/null 2>&1 || true; rmdir "$MOUNT_DIR" >/dev/null 2>&1 || true' EXIT

guestmount -a "$BASE_PATH" -i "$MOUNT_DIR"
VMLINUX_SRC=$(ls "$MOUNT_DIR"/boot/vmlinuz-* 2>/dev/null | sort | tail -n 1)
INITRD_SRC=$(ls "$MOUNT_DIR"/boot/initrd.img-* 2>/dev/null | sort | tail -n 1)
if [[ -z "$VMLINUX_SRC" || -z "$INITRD_SRC" ]]; then
  echo "Failed to find kernel or initrd in cloud image." >&2
  exit 1
fi
cp "$VMLINUX_SRC" "$VMLINUX_PATH"
cp "$INITRD_SRC" "$INITRD_PATH"

echo "Firecracker artifacts ready in $VM_DIR"
echo "Rootfs: $ROOT_RAW"
echo "Kernel: $VMLINUX_PATH"
echo "Initrd: $INITRD_PATH"
echo "Seed: $SEED_PATH"
