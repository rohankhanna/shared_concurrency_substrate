# VM Setup

## Recommended: QEMU/KVM Workflow

This workflow builds a VM, installs dependencies, and sets up the broker/mount in one command.

### 1. Create or choose an SSH key
```bash
ssh-keygen -t ed25519 -f ~/.ssh/gate_vm -N ""
```
`gate up` uses the public key for VM auth and the matching private key (`~/.ssh/gate_vm`) for SSH/scp/rsync.

### 2. Run `gate up`
```bash
./dist/gate up \
  --base ubuntu-24.04 \
  --vm-dir ./vm_build \
  --vm-name gate-vm \
  --ssh-key ~/.ssh/gate_vm.pub \
  --repo-path /path/to/host/repo
```

**Host-direct mode** (default) is recommended. The broker runs in the VM, and the gated view is mounted directly on the host via an SSH tunnel.

If your terminal stops echoing after `gate up`, run `stty echo`.

### Common Commands
*   **Status:** `./dist/gate status --vm-name gate-vm`
*   **Logs:** `./dist/gate logs --vm-name gate-vm --component vm-run`
*   **List VMs:** `./dist/gate vm-list`
*   **Shutdown:** `./dist/gate down --vm-name gate-vm`
*   **Cleanup:** `./dist/gate clean --vm-name gate-vm` (use if mount is stale or dir not empty)

## Firecracker VM (Optional)

The Firecracker flow uses specific scripts rather than the `gate` CLI.

1.  **Build and Launch:**
    ```bash
    ./scripts/build_vm_firecracker.sh \
      --base ubuntu-22.04 \
      --vm-dir ./vm_firecracker \
      --vm-name gate-fc \
      --repo-url <git-repo-url> \
      --repo-branch main \
      --ssh-key ~/.ssh/gate_vm.pub

    sudo ./scripts/run_vm_firecracker.sh --vm-dir ./vm_firecracker --vm-name gate-fc
    ```

2.  **Mount on Host:**
    ```bash
    sshfs gate@<guest-ip>:/mnt/gate /mnt/gate_host_gate-fc
    ```
