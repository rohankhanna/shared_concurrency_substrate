# Shared Concurrency Substrate VM Setup Bundle (QEMU/KVM)

> **Note:** Prefer `gate up` from the repo root for a one-command end-to-end
> setup with logs.

Date: 2025-12-20

## Goal
Create a reproducible VM image that boots Ubuntu 22.04 or Debian 12 and auto-installs the Gate lock broker + FUSE mount, so host editors can work through an enforced lock gateway.

## Host prerequisites
Install QEMU tools and cloud-init helpers:
```
sudo apt-get update
sudo apt-get install -y qemu-system-x86 qemu-utils cloud-image-utils
```

## Build the VM image (host)
```
./scripts/build_vm_image.sh \
  --base ubuntu-22.04 \
  --vm-dir ./vm_build \
  --vm-name gate-vm \
  --repo-url <git-repo-url> \
  --repo-branch main \
  --ssh-key ~/.ssh/id_rsa.pub \
  --disk-size 20G
```

## Run the VM (host)
```
./scripts/run_vm_qemu.sh --vm-dir ./vm_build --vm-name gate-vm --ssh-port 2222
```

## Mount VM view on the host
```
mkdir -p /mnt/gate_host_gate-vm
sshfs gate@127.0.0.1:/mnt/gate /mnt/gate_host_gate-vm -p 2222
```
Then open `/mnt/gate_host_gate-vm` in your editor. Locking and wait behavior is enforced inside the VM.

## Base OS selection
- `--base ubuntu-22.04` (default)
- `--base debian-12`

## Notes
- The VM auto-clones the repo into `/opt/gate` and installs requirements.
- Systemd units `gate-broker.service` and `gate-fuse.service` are installed and started on first boot.
- Environment file: `/etc/gate/gate.env` (uses `GATE_*` variables).
