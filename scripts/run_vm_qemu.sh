#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: run_vm_qemu.sh --vm-dir PATH --vm-name NAME [options]

Options:
  --vm-dir PATH      Directory containing <name>.qcow2 and <name>-seed.img
  --vm-name NAME     VM name used in filenames
  --ssh-port PORT    Host port forwarded to guest 22 (default: 2222)
  --memory MB        Memory size in MB (default: 4096)
  --cpus N           Number of vCPUs (default: 2)
USAGE
}

VM_DIR=""
VM_NAME=""
SSH_PORT="2222"
MEMORY="4096"
CPUS="2"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --vm-dir)
      VM_DIR="$2"
      shift 2
      ;;
    --vm-name)
      VM_NAME="$2"
      shift 2
      ;;
    --ssh-port)
      SSH_PORT="$2"
      shift 2
      ;;
    --memory)
      MEMORY="$2"
      shift 2
      ;;
    --cpus)
      CPUS="$2"
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

if [[ -z "$VM_DIR" || -z "$VM_NAME" ]]; then
  echo "--vm-dir and --vm-name are required" >&2
  usage
  exit 1
fi

ROOT_DISK="$VM_DIR/${VM_NAME}.qcow2"
SEED_IMG="$VM_DIR/${VM_NAME}-seed.img"

if [[ ! -f "$ROOT_DISK" || ! -f "$SEED_IMG" ]]; then
  echo "Missing root disk or seed image in $VM_DIR" >&2
  exit 1
fi

if ! command -v qemu-system-x86_64 >/dev/null 2>&1; then
  echo "qemu-system-x86_64 not found. Install qemu-system-x86." >&2
  exit 1
fi

qemu-system-x86_64 \
  -enable-kvm \
  -m "$MEMORY" \
  -smp "$CPUS" \
  -drive file="$ROOT_DISK",if=virtio,format=qcow2 \
  -drive file="$SEED_IMG",if=virtio,format=raw \
  -netdev user,id=net0,hostfwd=tcp::"$SSH_PORT"-:22 \
  -device virtio-net-pci,netdev=net0 \
  -nographic
