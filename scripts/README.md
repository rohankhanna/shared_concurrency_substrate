# Scripts (Shared Concurrency Substrate)

Date: 2025-12-21

## Runtime
- `gate_broker.py`: run the lock broker server.
- `gate_mount.py`: mount the FUSE filesystem view.

## VM bundles
- `build_vm_image.sh`, `run_vm_qemu.sh`: QEMU/KVM flow.
- `build_vm_firecracker.sh`, `run_vm_firecracker.sh`: Firecracker flow.

## Host/VM helpers
- `setup_vm_gate.sh`: install deps inside VM and start broker/mount.
- `setup_host_gate.sh`: install SSHFS and mount VM view on host (use `--host-mount` to choose a unique mountpoint per VM).
- `export_shared_substrate.sh`: export this folder into a standalone repo tree.

## Tests
- `smoke_test_fifo_sshfs.sh`: end-to-end FIFO blocking check over SSHFS.
