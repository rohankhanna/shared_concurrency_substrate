# Shared Concurrency Substrate: Gate FUSE Lock Broker Guide (2025-12-20)

> **Note:** Prefer the one-command workflow in `README.md` using `gate up`.
> Host-direct is the default and provides reliable locking on the host.

## Goal
Provide a broker-enforced filesystem mount that applies FIFO read/write locks for all editors and agents. This is a shared concurrency substrate for humans, LLM CLIs, code generators, and automated systems working on the same repo.

## Prerequisites
- FUSE enabled on the host.
- Python dependency: `fusepy==3.0.1`.
- A system-level state directory (default: `/var/lib/gate/`).

## Setup (system-level state)
```
sudo mkdir -p /var/lib/gate
sudo chown $USER:$USER /var/lib/gate
```

## Install scripts (recommended)
Inside the VM:
```
./scripts/setup_vm_gate.sh --repo-path /path/to/repo --start
```

On the host:
```
./scripts/setup_host_gate.sh --vm-user <user> --vm-host <vm-ip> --mount-method sshfs
```

## Start the broker (manual)
```
python3 scripts/gate_broker.py --state-dir /var/lib/gate --host 127.0.0.1 --port 8787
```

## Mount the repo view (manual)
```
mkdir -p /mnt/gate
python3 scripts/gate_mount.py --root /path/to/real/repo --mount /mnt/gate --broker-host 127.0.0.1 --broker-port 8787 --foreground
```

## Use any editor
Point your editor at the mounted view (e.g., `/mnt/gate_host`). Locking and wait behavior is enforced by the broker.

## Host → VM mirror workflow (optional)
If you already have a repo on the host and want to mirror it into the VM:
1) On the host, sync the repo into the VM path:
```
./scripts/setup_host_gate.sh --vm-user <user> --vm-host <vm-ip> --sync --repo-path /path/to/host/repo --vm-repo-path /path/to/vm/repo
```
2) Inside the VM, run the broker and mount using the VM repo path.
3) On the host, mount the VM view with **sshfs** and edit through it.
   (For reliable host locking, prefer the host-direct flow in `README.md`.)

## Notes
- Reads will wait if a writer is queued ahead (strict FIFO).
- Locks are global across runs (system-level state).
- Environment variables use `GATE_*` (e.g., `GATE_STATE_DIR`, `GATE_MAX_HOLD_MS`).
- `GATE_MAX_HOLD_MS` caps how long a read/write lock can be held contiguously (default: 3600000).

## VM setup bundle (QEMU/KVM)
For a fully packaged VM workflow, see:
`systems/gate_vm/README.md` (use a unique host mount path per VM, e.g., `/mnt/gate_host_gate-vm`)

## VM setup bundle (Firecracker)
For the Firecracker variant, see:
`systems/gate_vm_firecracker/README.md` (use a unique host mount path per VM, e.g., `/mnt/gate_host_gate-fc`)

## Smoke test
Run `tests/manual/lock_demo_run.py` against the host-direct mount.

## Scaling options (later)
- Replace SSHFS with VirtioFS for lower latency and higher throughput.
- Replace the HTTP broker with a Unix socket or gRPC transport.
- Re-implement the broker in Rust for performance and stronger concurrency control.
