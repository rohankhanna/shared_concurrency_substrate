# Workflows

## Host-Direct vs. SSHFS

### Host-Direct (Recommended)
Host-direct mode provides reliable locking by running the broker in the VM but mounting the FUSE filesystem directly on the host using a forwarded port.
*   **Pros:** FUSE locks are enforced directly on the host kernel interface.
*   **Mechanism:** Uses an SSH tunnel to the VM broker. If port 8787 is in use, Gate automatically picks the next free local port.
*   **Usage:** `gate up ... --host-mount-method host-direct` (Default)

### SSHFS
Mounts the VM's filesystem (which is already a FUSE mount) onto the host using SSHFS.
*   **Cons:** Not recommended for strict lock correctness due to SSHFS caching and behavior.
*   **Usage:** `gate up ... --host-mount-method sshfs`
*   **Note:** SSHFS runs in the background. Unmount with `gate down` or `fusermount3 -u <mount>`.
