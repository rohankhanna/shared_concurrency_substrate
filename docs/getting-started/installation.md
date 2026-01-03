# Installation

## 1. Install system packages (Ubuntu/Debian)

### Local + build requirements
```bash
sudo apt-get update
sudo apt-get install -y \
  python3 python3-pip python3-venv \
  fuse3 libfuse3-3 libfuse2 \
  openssh-client rsync
```

### Host mount tools
```bash
sudo apt-get install -y sshfs
```

### VM host tools (QEMU/KVM)
```bash
sudo apt-get update
sudo apt-get install -y qemu-system-x86 qemu-utils cloud-image-utils
```

### Firecracker host tools (optional)
```bash
sudo apt-get update
sudo apt-get install -y cloud-image-utils qemu-utils libguestfs-tools dnsmasq iproute2
```

## 2. Clone the repository
```bash
git clone <repo-url>
cd shared_concurrency_substrate
```

## 3. Create a Python venv
Required for Python mode and for building the binary.
```bash
python3 -m venv .venv
. .venv/bin/activate
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

## 4. Build the Gate binary (recommended)
```bash
python3 scripts/gate_cli.py build-binary
```
This produces `dist/gate`.
Version is stamped from `src/gate/VERSION` (update it for releases).

### Best‑effort reproducible build
```bash
./scripts/build_gate_binary_repro.sh
```

If you prefer Python-only operation, skip this step and run `scripts/gate_broker.py` and `scripts/gate_mount.py` directly.

## 5. Prepare the Gate state directory
```bash
sudo mkdir -p /var/lib/gate
sudo chown $USER:$USER /var/lib/gate
```

