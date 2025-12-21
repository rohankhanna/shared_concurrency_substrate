#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARTIFACTS_DIR="$ROOT_DIR/artifacts"
WORK_DIR="$ROOT_DIR/.build_rootfs"
ROOTFS_IMG="$ARTIFACTS_DIR/rootfs.ext4"

mkdir -p "$ARTIFACTS_DIR" "$WORK_DIR"

if ! command -v busybox >/dev/null 2>&1; then
  echo "busybox not found. Please install busybox and retry." >&2
  exit 1
fi

if ! command -v mkfs.ext4 >/dev/null 2>&1; then
  echo "mkfs.ext4 not found. Please install e2fsprogs and retry." >&2
  exit 1
fi

ROOTFS_DIR="$WORK_DIR/rootfs"
rm -rf "$ROOTFS_DIR"
mkdir -p "$ROOTFS_DIR"/{bin,sbin,etc,proc,sys,dev,tmp,usr/bin,usr/sbin}

cp "$(command -v busybox)" "$ROOTFS_DIR/bin/busybox"
chmod +x "$ROOTFS_DIR/bin/busybox"
( cd "$ROOTFS_DIR/bin" && ./busybox --install -s . )

cat <<'INIT' > "$ROOTFS_DIR/sbin/init"
#!/bin/sh
mount -t proc none /proc
mount -t sysfs none /sys

echo "hello from firecracker"

poweroff -f || /bin/busybox poweroff -f
INIT
chmod +x "$ROOTFS_DIR/sbin/init"

# Create an ext4 image populated from the rootfs directory.
rm -f "$ROOTFS_IMG"
truncate -s 64M "$ROOTFS_IMG"
mkfs.ext4 -d "$ROOTFS_DIR" -F "$ROOTFS_IMG" >/dev/null

echo "Created rootfs image at $ROOTFS_IMG"
