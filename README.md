# Shared Concurrency Substrate (Gate + FUSE)

## What this is
Gate provides a broker-enforced filesystem view that applies strict FIFO read/write locking to any editor or automation. You edit a mounted view, and the broker serializes access so writers cannot be skipped and readers block behind queued writers.

## Architecture (short)
- Gate broker: HTTP server with a SQLite-backed lock store.
- Gate FUSE mount: filesystem view that sends all open/read/write activity through the broker.
- Optional VM: run the broker + mount in a VM and mount the VM view on the host (SSHFS).

## Supported platforms
- Linux x86_64 with FUSE enabled. (macOS/Windows not supported directly; use a Linux VM.)
- For VM mode: hardware virtualization (KVM) and QEMU/KVM.

## Setup from scratch

### 1) Install system packages (Ubuntu/Debian)
Local + build requirements:
```
sudo apt-get update
sudo apt-get install -y \
  python3 python3-pip python3-venv \
  fuse3 libfuse3-3 libfuse2 \
  openssh-client rsync
```

Host mount tools:
```
sudo apt-get install -y sshfs
```

VM host tools (QEMU/KVM):
```
sudo apt-get update
sudo apt-get install -y qemu-system-x86 qemu-utils cloud-image-utils
```

Firecracker host tools (optional):
```
sudo apt-get update
sudo apt-get install -y cloud-image-utils qemu-utils libguestfs-tools dnsmasq iproute2
```

### 2) Clone the repo
```
git clone <repo-url>
cd shared_concurrency_substrate
```

### 3) Create a Python venv (needed for Python mode and for building the binary)
```
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

### 4) Build the Gate binary (recommended)
```
python3 scripts/gate_cli.py build-binary
```
This produces `dist/gate`.

If you prefer Python-only operation, skip this step and run `scripts/gate_broker.py` and `scripts/gate_mount.py` directly.

### 5) Prepare the Gate state directory
```
sudo mkdir -p /var/lib/gate
sudo chown $USER:$USER /var/lib/gate
```

### 6A) Local, single-machine run
Start the broker:
```
./dist/gate broker --state-dir /var/lib/gate --host 127.0.0.1 --port 8787
```

Mount the repo view (in another terminal):
```
mkdir -p /mnt/gate
./dist/gate mount \
  --root /path/to/repo \
  --mount /mnt/gate \
  --broker-host 127.0.0.1 \
  --broker-port 8787 \
  --foreground
```

Open `/mnt/gate` in your editor. All reads and writes are brokered.

Python-only alternative:
```
python3 scripts/gate_broker.py --state-dir /var/lib/gate --host 127.0.0.1 --port 8787
python3 scripts/gate_mount.py --root /path/to/repo --mount /mnt/gate --broker-host 127.0.0.1 --broker-port 8787 --foreground
```

Unmount:
```
fusermount3 -u /mnt/gate
```

### 6B) VM run (recommended for stronger enforcement)
1) Create or choose an SSH key:
```
ssh-keygen -t ed25519 -f ~/.ssh/gate_vm -N ""
```
`gate up` uses the public key for VM auth and the matching private key
(`~/.ssh/gate_vm`) for SSH/scp/rsync.

2) Run the one-command workflow (build VM if needed, boot VM, install deps, copy the binary, sync the repo, start broker + mount, host-mount the gated view):
```
./dist/gate up \
  --base ubuntu-24.04 \
  --vm-dir ./vm_build \
  --vm-name gate-vm \
  --ssh-key ~/.ssh/gate_vm.pub \
  --repo-path /path/to/host/repo
```

Host-direct mode (recommended for reliable locking): run the broker in the VM,
then mount the gated view directly on the host (no SSHFS).
```
./dist/gate up \
  --base ubuntu-24.04 \
  --vm-dir ./vm_build \
  --vm-name gate-vm \
  --ssh-key ~/.ssh/gate_vm.pub \
  --repo-path /path/to/host/repo \
  --host-mount-method host-direct
```

Supported bases: `ubuntu-22.04`, `ubuntu-24.04`, `debian-12`.

If your terminal stops echoing after `gate up`, run:
```
stty echo
```

Common VM commands:
```
./dist/gate status --vm-name gate-vm
./dist/gate logs --vm-name gate-vm --component vm-run
./dist/gate vm-list
./dist/gate down --vm-name gate-vm
```

Host mount notes:
- SSHFS runs in the background; unmount with `gate down` or `fusermount3 -u <mount>`.
- Host-direct uses a host FUSE mount and an SSH tunnel to the VM broker.

Logs and state directories (defaults):
- Logs: `~/.local/state/gate/logs/<vm-name>/`
- VM state: `~/.local/state/gate/state/<vm-name>/`
- Host mount: `~/.local/state/gate/mounts/<vm-name>/`
- Host-direct mount: `~/.local/state/gate/mounts/gate-host-direct`

Optional flags for `gate up`:
- `--host-mount /path/to/mount`
- `--host-mount-method host-direct` (host FUSE + VM broker)
- `--binary /path/to/gate` (defaults to `which gate`)
- `--redownload` (force base image re-download)
- `--max-hold-ms <milliseconds>` (hard cap for lock holds, default 3600000)
- `--verbose` (stream logs to console)
- `--dry-run` (print commands without executing)
- `--keep-vm-on-error` (do not stop the VM if setup fails)

Cleanup:
```
./dist/gate clean --vm-name gate-vm
```
Use this if a host mount is stale or a host-direct mount directory is not empty.

### 6C) Firecracker VM (optional)
The Firecracker flow uses scripts (the `gate up` workflow targets QEMU/KVM):
```
./scripts/build_vm_firecracker.sh \
  --base ubuntu-22.04 \
  --vm-dir ./vm_firecracker \
  --vm-name gate-fc \
  --repo-url <git-repo-url> \
  --repo-branch main \
  --ssh-key ~/.ssh/gate_vm.pub

sudo ./scripts/run_vm_firecracker.sh --vm-dir ./vm_firecracker --vm-name gate-fc
```

Mount the VM view on the host:
```
sshfs gate@<guest-ip>:/mnt/gate /mnt/gate_host_gate-fc
```

### 7) Verify locking behavior (manual demo)
Single-command manual demo (spawns A then B in one terminal):
```
GATE_DEMO_MOUNT=$HOME/.local/state/gate/mounts/gate-host-direct \
GATE_DEMO_FILE=README.md \
python3 tests/manual/lock_demo_run.py
```

If you want to run them separately in two terminals:
```
python3 tests/manual/lock_demo_a.py
python3 tests/manual/lock_demo_b.py
```

## Configuration and defaults
- State dir: `/var/lib/gate` (override with `--state-dir` or `GATE_STATE_DIR`)
- Broker host/port: `127.0.0.1:8787` (`GATE_BROKER_HOST`, `GATE_BROKER_PORT`)
- Lease and max hold: `--lease-ms`, `--max-hold-ms` (env: `GATE_LEASE_MS`, `GATE_MAX_HOLD_MS`)
- Acquire timeout: `--acquire-timeout-ms` (env: `GATE_ACQUIRE_TIMEOUT_MS`)
- VM workflow state root: `~/.local/state/gate/` (override with `XDG_STATE_HOME`)

## Lock behavior notes
- FIFO fairness: reads block behind queued writers.
- Re-entrant per handle: repeated lock requests from the same handle owner and path increment a hold count; the lock is released when the count returns to zero. New opens always use a fresh owner token, so unrelated writers still block; follow‑up metadata calls reuse the handle owner when a handle already exists.
- Locks are held until the handle is released (close), not on flush. Set `GATE_RELEASE_ON_FLUSH=1` to restore legacy behavior.
- Default max hold cap is 1 hour (3600000 ms). Increase or decrease with `--max-hold-ms`.

## Troubleshooting
- FUSE permission denied: ensure FUSE is enabled and your user can mount (`sudo usermod -aG fuse $USER`, then log out/in).
- Host mount stuck: run `fusermount3 -u <mount>` and re-run.
- `gate up` cannot find the binary: build it first or pass `--binary /path/to/gate`.
- Need a clean repo sync into the VM: re-run `gate up` with `--repo-path` (it uses rsync with `--delete`).

## Related docs
- `docs/GUIDE.md` for architecture details and manual flows.
- `systems/gate_vm/README.md` and `systems/gate_vm_firecracker/README.md` for VM internals.
- `systems/firecracker_hello/README.md` for the minimal Firecracker demo.
- `scripts/README.md` for helper script usage.
