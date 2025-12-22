# Scripts (Shared Concurrency Substrate)

Date: 2025-12-21

These scripts are legacy helpers. Prefer the Gate executable subcommands:
`gate build-binary`, `gate vm-build`, `gate vm-run`, `gate host-provision`,
`gate host-mount`, `gate up`.

## Runtime
- `gate_broker.py`: run the lock broker server.
- `gate_mount.py`: mount the FUSE filesystem view.

## VM bundles
- `build_vm_image.sh`, `run_vm_qemu.sh`: QEMU/KVM flow (legacy; prefer `gate up`).
- `build_vm_firecracker.sh`, `run_vm_firecracker.sh`: Firecracker flow (legacy).
- `build_gate_binary.sh`: build a single Gate executable (legacy; prefer `gate build-binary`).
- `build_gate_bundle.sh`: deprecated (bundle flow replaced by `gate up`).
- `install_gate_bundle.sh`: deprecated (bundle flow replaced by `gate up`).

## Host/VM helpers
- `setup_vm_gate.sh`: legacy installer for VM.
- `setup_host_gate.sh`: legacy host helper (use `gate up` instead).
- `export_shared_substrate.sh`: export this folder into a standalone repo tree.

## Tests
- `smoke_test_fifo_sshfs.sh`: end-to-end FIFO blocking check over SSHFS.
