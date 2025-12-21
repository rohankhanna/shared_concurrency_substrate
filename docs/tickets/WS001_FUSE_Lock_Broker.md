# Ticket: WS001 — FUSE Lock Broker MVP (Plan Only)
Status: Planned | Owner: TBD | Target: 2025-12

Objective
- Implement a DB-backed lock broker and FUSE mount that enforces FIFO read/write locks for all editors/agents.

Deliverables
- Broker daemon (Python) with SQLite lock queue and lease/heartbeat handling.
- FUSE filesystem (Python + fusepy) that routes file ops through the broker.
- CLI helpers: `gate broker`, `gate mount`, `gate status`.
- Documentation for mount usage and enforcement model.

Steps
1) Define DB schema for locks, leases, queue, and audit events.
2) Implement broker API (Unix socket or localhost HTTP).
3) Implement FIFO lock granting and timeouts.
4) Implement FUSE mount that blocks on lock acquisition for write/rename.
5) Enforce repo read-only permissions for non-broker users.
6) Add basic tests for queue fairness and crash recovery.

Definition of Done (DoD)
- Editors save through the mount and block when locks are held.
- Read locks never bypass queued writers.
- Broker restart preserves queue state and leases.

Dependencies
- fusepy (Python FUSE bindings).
- FUSE kernel support enabled on host.

Risks
- FUSE semantics with atomic save patterns (rename/write temp).
- Blocking behavior could degrade editor UX if lock scopes are too broad.
