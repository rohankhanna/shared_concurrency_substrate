# Firecracker Hello-World (microVM)

Date: 2025-12-20

## Goal
Boot a minimal Firecracker microVM and print a single “hello” line via the serial console.

## Directory Layout
- `artifacts/`
  - `firecracker` (binary)
  - `vmlinux` (kernel image)
  - `rootfs.ext4` (root filesystem image)
- `scripts/`
  - `make_rootfs.sh` (builds a tiny rootfs using busybox)
  - `run_firecracker.sh` (configures and boots Firecracker)
- `config.json` (Firecracker boot configuration template)

## Prerequisites
- KVM available (`/dev/kvm`).
- `firecracker` binary placed at `artifacts/firecracker` (chmod +x).
- Kernel image at `artifacts/vmlinux` (uncompressed vmlinux).
- `busybox` installed for rootfs build.
- `mkfs.ext4` available (e2fsprogs).

## Build a Minimal RootFS
```
./systems/firecracker_hello/scripts/make_rootfs.sh
```
This creates `artifacts/rootfs.ext4` with a tiny init that prints “hello”.

## Run the microVM
```
./systems/firecracker_hello/scripts/run_firecracker.sh
```
Check `systems/firecracker_hello/console.log` for the “hello” line.

## Notes
- If Firecracker fails, plan is to fallback to a KVM/QEMU VM using the same rootfs.
- All configuration is local; no network is required.
