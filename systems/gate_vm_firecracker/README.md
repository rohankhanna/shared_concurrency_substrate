# Shared Concurrency Substrate VM Setup Bundle (Firecracker)

Date: 2025-12-20

## Goal
Build and run a Firecracker microVM that boots a cloud image, installs the Gate broker + FUSE services, and exposes SSH for host mounting.

## Host prerequisites
- firecracker binary in PATH
- cloud-image-utils (cloud-localds)
- qemu-utils (qemu-img)
- libguestfs-tools (guestmount)
- dnsmasq, iproute2

Install on Ubuntu:
```
sudo apt-get update
sudo apt-get install -y cloud-image-utils qemu-utils libguestfs-tools dnsmasq iproute2
```

## Build artifacts
```
./scripts/build_vm_firecracker.sh \
  --base ubuntu-22.04 \
  --vm-dir ./vm_firecracker \
  --vm-name gate-fc \
  --repo-url <git-repo-url> \
  --repo-branch main \
  --ssh-key ~/.ssh/id_rsa.pub
```

## Run the microVM (requires sudo)
```
sudo ./scripts/run_vm_firecracker.sh --vm-dir ./vm_firecracker --vm-name gate-fc
```

The script prints the guest IP. SSH in:
```
ssh gate@<guest-ip>
```

## Mount the VM view on the host
```
mkdir -p /mnt/gate_host
sshfs gate@<guest-ip>:/mnt/gate /mnt/gate_host
```

## Notes
- Firecracker uses a tap device with DHCP provided by dnsmasq.
- The VM auto-clones the repo into `/opt/gate` and enables `gate-broker.service` + `gate-fuse.service`.
- Environment file: `/etc/gate/gate.env` (uses `GATE_*` variables).
