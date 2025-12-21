#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: run_vm_firecracker.sh --vm-dir PATH --vm-name NAME [options]

Options:
  --vm-dir PATH     Directory containing artifacts
  --vm-name NAME    VM name used in filenames
  --tap-dev DEV     Tap device name (default: fc-tap0)
  --host-ip IP      Host tap IP (default: 172.16.0.1)
  --guest-ip IP     Guest IP (default: 172.16.0.2)
  --mac MAC         Guest MAC (default: AA:FC:00:00:00:01)
  --memory MB       Memory size in MB (default: 2048)
  --cpus N          Number of vCPUs (default: 2)
  --api-sock PATH   API socket path (default: /tmp/firecracker.sock)
USAGE
}

VM_DIR=""
VM_NAME=""
TAP_DEV="fc-tap0"
HOST_IP="172.16.0.1"
GUEST_IP="172.16.0.2"
GUEST_MAC="AA:FC:00:00:00:01"
MEMORY="2048"
CPUS="2"
API_SOCK="/tmp/firecracker.sock"

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
    --tap-dev)
      TAP_DEV="$2"
      shift 2
      ;;
    --host-ip)
      HOST_IP="$2"
      shift 2
      ;;
    --guest-ip)
      GUEST_IP="$2"
      shift 2
      ;;
    --mac)
      GUEST_MAC="$2"
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
    --api-sock)
      API_SOCK="$2"
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

if [[ $EUID -ne 0 ]]; then
  echo "This script needs sudo/root to create tap and configure networking." >&2
  exit 1
fi

for cmd in firecracker dnsmasq ip; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "Missing $cmd. Install firecracker, dnsmasq, iproute2." >&2
    exit 1
  fi
done

VMLINUX="$VM_DIR/${VM_NAME}-vmlinux"
INITRD="$VM_DIR/${VM_NAME}-initrd"
ROOTFS="$VM_DIR/${VM_NAME}-rootfs.raw"
SEED="$VM_DIR/${VM_NAME}-seed.img"

for file in "$VMLINUX" "$INITRD" "$ROOTFS" "$SEED"; do
  if [[ ! -f "$file" ]]; then
    echo "Missing file: $file" >&2
    exit 1
  fi
done

ip tuntap add "$TAP_DEV" mode tap
ip addr add "$HOST_IP/24" dev "$TAP_DEV"
ip link set "$TAP_DEV" up

DNSMASQ_PID="$VM_DIR/dnsmasq.pid"
dnsmasq --interface="$TAP_DEV" \
  --bind-interfaces \
  --dhcp-range="$GUEST_IP","$GUEST_IP",255.255.255.0,12h \
  --dhcp-host="$GUEST_MAC","$GUEST_IP" \
  --pid-file="$DNSMASQ_PID"

CONFIG="$VM_DIR/${VM_NAME}-fc-config.json"
cat > "$CONFIG" <<JSON
{
  "boot-source": {
    "kernel_image_path": "$VMLINUX",
    "initrd_path": "$INITRD",
    "boot_args": "console=ttyS0 reboot=k panic=1 pci=off"
  },
  "drives": [
    {
      "drive_id": "rootfs",
      "path_on_host": "$ROOTFS",
      "is_root_device": true,
      "is_read_only": false
    },
    {
      "drive_id": "seed",
      "path_on_host": "$SEED",
      "is_root_device": false,
      "is_read_only": true
    }
  ],
  "network-interfaces": [
    {
      "iface_id": "eth0",
      "host_dev_name": "$TAP_DEV",
      "guest_mac": "$GUEST_MAC"
    }
  ],
  "machine-config": {
    "vcpu_count": $CPUS,
    "mem_size_mib": $MEMORY,
    "smt": false
  }
}
JSON

rm -f "$API_SOCK"
firecracker --api-sock "$API_SOCK" --config-file "$CONFIG" --log-path "$VM_DIR/firecracker.log" >"$VM_DIR/console.log" 2>&1 &

sleep 2

echo "Firecracker started. Guest IP: $GUEST_IP"
echo "SSH with: ssh gate@$GUEST_IP"
