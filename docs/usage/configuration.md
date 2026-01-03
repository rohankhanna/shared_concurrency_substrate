# Configuration

## Defaults and Environment Variables

*   **State Directory:** `/var/lib/gate`
    *   Flag: `--state-dir`
    *   Env: `GATE_STATE_DIR`
*   **Broker Host/Port:** `127.0.0.1:8787`
    *   Env: `GATE_BROKER_HOST`, `GATE_BROKER_PORT`
*   **Lease Time:**
    *   Flag: `--lease-ms`
    *   Env: `GATE_LEASE_MS`
*   **Max Hold Time:** Default 1 hour (3600000 ms).
    *   Flag: `--max-hold-ms`
    *   Env: `GATE_MAX_HOLD_MS`
*   **Acquire Timeout:**
    *   Flag: `--acquire-timeout-ms`
    *   Env: `GATE_ACQUIRE_TIMEOUT_MS`
*   **VM Workflow State Root:** `~/.local/state/gate/`
    *   Override with `XDG_STATE_HOME`
