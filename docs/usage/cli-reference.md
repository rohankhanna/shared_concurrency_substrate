# CLI Reference

## `gate up` Flags

*   `--host-mount /path/to/mount`: Specify host mount path.
*   `--host-mount-method host-direct|sshfs`: Default is `host-direct`.
*   `--binary /path/to/gate`: Path to gate binary (defaults to `which gate`).
*   `--redownload`: Force base image re-download.
*   `--max-hold-ms <milliseconds>`: Hard cap for lock holds (default 3600000 / 1 hour).
*   `--verbose`: Stream logs to console.
*   `--dry-run`: Print commands without executing.
*   `--keep-vm-on-error`: Do not stop the VM if setup fails.

## Log and State Directories
*   **Logs:** `~/.local/state/gate/logs/<vm-name>/`
*   **VM state:** `~/.local/state/gate/state/<vm-name>/`
*   **Host mount:** `~/.local/state/gate/mounts/<vm-name>/`
*   **Host-direct mount:** `~/.local/state/gate/mounts/gate-host-direct`
