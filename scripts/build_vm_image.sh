#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: build_vm_image.sh --repo-url URL --ssh-key PATH [options]

Options:
  --base BASE              ubuntu-22.04 (default) or debian-12
  --vm-dir PATH            Output directory for VM artifacts (default: ./vm_build)
  --vm-name NAME           VM name (default: gate-vm)
  --repo-url URL           Git repo URL to clone inside VM (required)
  --repo-branch BRANCH     Git branch (default: main)
  --ssh-key PATH           Public SSH key file to authorize (required)
  --disk-size SIZE         Resize root disk (e.g., 20G)
USAGE
}

BASE="ubuntu-22.04"
VM_DIR="./vm_build"
VM_NAME="gate-vm"
REPO_URL=""
REPO_BRANCH="main"
SSH_KEY_PATH=""
DISK_SIZE=""

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
    --disk-size)
      DISK_SIZE="$2"
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

if ! command -v cloud-localds >/dev/null 2>&1; then
  echo "cloud-localds not found. Install cloud-image-utils." >&2
  exit 1
fi

if ! command -v qemu-img >/dev/null 2>&1; then
  echo "qemu-img not found. Install qemu-utils." >&2
  exit 1
fi

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
ROOT_PATH="$VM_DIR/${VM_NAME}.qcow2"
SEED_PATH="$VM_DIR/${VM_NAME}-seed.img"
USER_DATA="$VM_DIR/user-data"
META_DATA="$VM_DIR/meta-data"

if [[ ! -f "$BASE_PATH" ]]; then
  echo "Downloading base image: $BASE_URL"
  curl -fsSL -o "$BASE_PATH" "$BASE_URL"
fi

cp "$BASE_PATH" "$ROOT_PATH"

if [[ -n "$DISK_SIZE" ]]; then
  qemu-img resize "$ROOT_PATH" "$DISK_SIZE"
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

echo "VM image ready: $ROOT_PATH"
echo "Seed image ready: $SEED_PATH"
echo "Run with:"
echo "  ./scripts/run_vm_qemu.sh --vm-dir \"$VM_DIR\" --vm-name \"$VM_NAME\" --ssh-port 2222"
