# Architecture Overview

## Goal
Provide a broker-enforced filesystem view that applies strict FIFO read/write locking to any editor or automation. You edit a mounted view, and the broker serializes access so writers cannot be skipped and readers block behind queued writers.

## Components
*   **Gate Broker:** An HTTP server with a SQLite-backed lock store. It manages the queue and grants locks.
*   **Gate FUSE Mount:** A filesystem view that intercepts all open, read, and write operations and routes them through the broker.
*   **VM Isolation (Optional):** Runs the broker and mount inside a VM, exposing the view to the host. This prevents host-side processes from bypassing the locks by accessing the underlying repo directly (if configured correctly).

## System Design
1.  **Broker:** Owns the `locks.db` (SQLite). Handles `acquire`, `release`, `heartbeat` requests.
2.  **FUSE Client:** Translates kernel VFS calls into HTTP requests to the broker. Blocks the calling process until the lock is granted.
3.  **Transport:** HTTP (currently). Planned move to Unix sockets or gRPC.
