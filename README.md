# Shared Concurrency Substrate (Gate + FUSE)

Date: 2025-12-21

## Purpose
A broker-enforced filesystem gateway that applies strict FIFO read/write locking to any editor or automation. This package is the portable subset for a standalone repo.

## Prerequisites
### Local (single machine)
- Linux with FUSE enabled.
- Python 3.10+ (only needed if you run the Python scripts directly or build the binary).
- `fusepy` (in `requirements.txt`, only for Python mode).

Install dependencies (Ubuntu/Debian, Python mode):
```
sudo apt-get update
sudo apt-get install -y python3 python3-pip python3-venv fuse3
python3 -m pip install -r requirements.txt
sudo mkdir -p /var/lib/gate
sudo chown $USER:$USER /var/lib/gate
```

### Host + VM (recommended for stronger enforcement)
- QEMU/KVM (or Firecracker) on the host.
- `sshfs` on the host to mount the VM view.
- Cloud image tools: `cloud-image-utils` and `qemu-utils`.
- For Firecracker: `libguestfs-tools`, `dnsmasq`, `iproute2`, and a Firecracker binary in PATH.

Install host tools (Ubuntu/Debian):
```
sudo apt-get update
sudo apt-get install -y qemu-system-x86 qemu-utils cloud-image-utils sshfs
```

Install Firecracker host tools (Ubuntu/Debian):
```
sudo apt-get update
sudo apt-get install -y libguestfs-tools dnsmasq iproute2
```

Where missing files come from:
- **Cloud images** are downloaded automatically by the build scripts from the official Ubuntu or Debian cloud image mirrors.
- **Firecracker binary** (for `systems/gate_vm_firecracker` and the `firecracker_hello` demo) should be downloaded from the official Firecracker release artifacts or built from source, then placed on your PATH (e.g., `/usr/local/bin/firecracker`).
- **Kernel image (vmlinux)** for `systems/firecracker_hello` should be downloaded from the same Firecracker release bundle (look for `vmlinux`) or built locally.

Official download URLs (reference):
```
Ubuntu 22.04 cloud image (amd64):
https://cloud-images.ubuntu.com/jammy/current/jammy-server-cloudimg-amd64.img

Debian 12 (Bookworm) genericcloud image (amd64):
https://cloud.debian.org/images/cloud/bookworm/latest/debian-12-genericcloud-amd64.qcow2

Firecracker releases (download firecracker + vmlinux from the latest tag):
https://github.com/firecracker-microvm/firecracker/releases
```

## Quick start (local, executable)
If you already have the `gate` binary, skip to step 2.

1) Build the executable from source (no shell scripts):
```
PYTHONPATH=./src python3 -m gate.cli build-binary
```

2) Start the broker:
```
./dist/gate broker --state-dir /var/lib/gate --host 127.0.0.1 --port 8787
```

3) Mount the repo view:
```
mkdir -p /mnt/gate
./dist/gate mount --root /path/to/repo --mount /mnt/gate --broker-host 127.0.0.1 --broker-port 8787 --foreground
```

4) Open the mounted path in any editor. All writes go through the broker.

## Build a standalone Gate executable (no Python runtime needed)
This produces a single Linux executable (`./dist/gate`) that runs the broker and FUSE mount without Python.
```
PYTHONPATH=./src python3 -m gate.cli build-binary
```
If you don't have Python on the host, build the binary on another Linux x86_64 machine and copy `dist/gate` over, or publish it as a release artifact.

## Quick start (VM, one command)
This runs the full workflow (build VM if needed, boot VM, install deps, copy the binary, sync the repo, start broker+mount, and host‑mount the gated view), with logs in:
`$XDG_STATE_HOME/gate/logs/<vm-name>/` (default: `~/.local/state/gate/logs/<vm-name>/`).

```
./dist/gate up \
  --base ubuntu-24.04 \
  --vm-dir ./vm_build \
  --vm-name gate-vm \
  --ssh-key ~/.ssh/shared_concurrency_substrate_test.pub \
  --repo-path /path/to/host/repo
```

Optional flags:
- `--host-mount /path/to/mount` (defaults to `~/.local/state/gate/mounts/<vm-name>/`)
- `--binary /path/to/gate` (defaults to `which gate`)
- `--redownload` (force base image re-download)
- `--verbose` (stream logs to console)
- `--dry-run` (print the commands without executing)
- `--keep-vm-on-error` (don’t stop the VM if setup fails)

Check status and logs:
```
./dist/gate status --vm-name gate-vm
./dist/gate logs --vm-name gate-vm --component vm-run
```

### Firecracker
1) Ensure `firecracker` is installed and in PATH, then build artifacts:
```
./scripts/build_vm_firecracker.sh \
  --base ubuntu-22.04 \
  --vm-dir ./vm_firecracker \
  --vm-name gate-fc \
  --repo-url <git-repo-url> \
  --repo-branch main \
  --ssh-key ~/.ssh/id_rsa.pub
```

2) Run the microVM (requires sudo):
```
sudo ./scripts/run_vm_firecracker.sh --vm-dir ./vm_firecracker --vm-name gate-fc
```

3) Mount the VM view on the host with SSHFS using the guest IP printed by the script (choose a unique mountpoint per VM):
```
mkdir -p /mnt/gate_host_gate-fc
sshfs gate@<guest-ip>:/mnt/gate /mnt/gate_host_gate-fc
```

## Export from this repo
Use the export script to assemble a clean, standalone tree:
```
./scripts/export_shared_substrate.sh --out-dir /path/to/new-repo
```

The exported tree includes the broker, FUSE mount, VM build/run scripts, and docs.

## Notes
- Defaults use `/var/lib/gate` for state; override with `--state-dir` or `GATE_STATE_DIR`.
- Environment variables use `GATE_*` naming.

## Firecracker hello demo (optional)
The `systems/firecracker_hello` folder is a minimal microVM demo and does not ship binaries.
1) Download the Firecracker release bundle and copy:
   - `firecracker` to `systems/firecracker_hello/artifacts/firecracker`
   - `vmlinux` to `systems/firecracker_hello/artifacts/vmlinux`
2) Build a minimal rootfs (requires `busybox` and `mkfs.ext4`):
```
sudo apt-get update
sudo apt-get install -y busybox e2fsprogs
./systems/firecracker_hello/scripts/make_rootfs.sh
```
3) Run the demo:
```
./systems/firecracker_hello/scripts/run_firecracker.sh
```
4) Check `systems/firecracker_hello/console.log` for the “hello” line.
