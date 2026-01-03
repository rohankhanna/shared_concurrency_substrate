# Scripts (Shared Concurrency Substrate)

Date: 2025-12-21

These scripts are helpers. Prefer the Gate executable subcommands for most workflows:
`gate build-binary`, `gate vm-build`, `gate vm-run`, `gate host-provision`,
`gate host-mount`, `gate up`, `gate vm-list`, `gate down`.

## Runtime
- `gate_broker.py`: run the lock broker server (supports `--max-hold-ms`).
- `gate_mount.py`: mount the FUSE filesystem view (supports `--max-hold-ms`).

## VM bundles
- `build_vm_image.sh`, `run_vm_qemu.sh`: QEMU/KVM flow (prefer `gate up`).
- `build_vm_firecracker.sh`, `run_vm_firecracker.sh`: Firecracker flow.
- `build_gate_binary.sh`: build a single Gate executable (prefer `gate build-binary`).
- `build_gate_binary_repro.sh`: best-effort reproducible build wrapper.
- `build_gate_bundle.sh`: deprecated (bundle flow replaced by `gate up`).
- `install_gate_bundle.sh`: deprecated (bundle flow replaced by `gate up`).

## Host/VM helpers
- `setup_vm_gate.sh`: VM installer helper.
- `setup_host_gate.sh`: host helper (use `gate up` for end-to-end). Supports `--mount-method nfs` or `sshfs`.
- `export_shared_substrate.sh`: exports a copy of this folder into a new tree.

## Tests
- `full_cycle.sh`: run `gate up` -> demo -> `gate down` in one command.
- `stability_run.sh`: run the full cycle N times (default: 10).
- `smoke_test_fifo_sshfs.sh`: legacy FIFO check over SSHFS.
Manual lock demo scripts now live in `tests/manual/`.
