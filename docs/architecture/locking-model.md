# Locking Model

## Core Principles

*   **FIFO Fairness:** Reads block behind queued writers. Writers wait for earlier readers/writers. This prevents starvation and ensures strict serialization.
*   **System-Wide:** Locks are global across all clients using the same broker.

## Re-entrancy
The broker treats repeated lock requests from the same **handle owner** and path as re‑entrant.
*   **Handle Owner:** The FUSE layer assigns a unique owner token per open handle.
*   **Behavior:** It reuses that token for follow‑up metadata operations on the same path when a handle already exists (e.g., `touch` calling `utimens` while the FD is open).
*   **New Opens:** Always use a fresh owner token, so unrelated writers still block.
*   **Hold Count:** The broker maintains a per‑owner hold count and releases the lock only when the count returns to zero.

## Lock Lifecycle
*   **Acquire:** On `open()`, `mkdir()`, `rename()`, etc.
*   **Release:** Locks are held until the handle is released (`close()`), **not** on flush.
    *   *Legacy Mode:* Set `GATE_RELEASE_ON_FLUSH=1` to release on flush.
*   **Timeouts:**
    *   **Lease:** Locks must be heartbeated to prevent expiry (automatic in FUSE client).
    *   **Max Hold:** Default cap of 1 hour (3600000 ms) to prevent indefinite blocking. Configurable via `--max-hold-ms`.
