# Troubleshooting

## Common Issues

### FUSE permission denied
*   **Symptom:** Cannot access mount point.
*   **Fix:** Ensure FUSE is enabled and your user can mount.
    ```bash
    sudo usermod -aG fuse $USER
    # Log out and log back in
    ```

### Host mount stuck
*   **Symptom:** `gate down` fails or directory is busy.
*   **Fix:**
    ```bash
    fusermount3 -u <mount_path>
    ```

### `gate up` cannot find the binary
*   **Fix:** Build it first (`python3 scripts/gate_cli.py build-binary`) or pass `--binary /path/to/gate`.

### Need a clean repo sync
*   **Fix:** Re-run `gate up` with `--repo-path`. It uses rsync with `--delete` to ensure the VM matches the host.

### CI/Smoke Test
*   Run the automated smoke test:
    ```bash
    PYTHONPATH=src python3 tests/automated/test_broker_fairness.py
    ```
