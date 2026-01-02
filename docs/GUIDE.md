# Shared Concurrency Substrate Guide

Date: 2025-12-21

## Goal
Provide a broker-enforced filesystem view that guarantees FIFO read/write locking for any editor or automation (humans, LLM CLIs, code-gen systems).

## Architecture (short)
- **Gate broker**: HTTP server that owns lock state in a SQLite DB.
- **FUSE mount**: filesystem view that routes every open/read/write to the broker.
- **Mount bridge** (optional): SSHFS or VirtioFS mount on the host.

All writes go through the broker. FIFO fairness blocks reads if a writer is queued ahead.

## Re‑entrant locks (per handle)
The broker treats repeated lock requests from the same **handle owner** and path as re‑entrant. The FUSE layer
assigns a unique owner token per open handle, reuses that token for follow‑up metadata operations on the same
path when a handle already exists (for example, `touch` calling `utimens` while the FD is open), and always
uses a fresh owner token for new opens. The broker maintains a per‑owner hold count and releases the lock only
when the count returns to zero.

## Local setup (single machine)
```
python3 -m pip install -r requirements.txt
sudo mkdir -p /var/lib/gate
sudo chown $USER:$USER /var/lib/gate

python3 scripts/gate_broker.py --state-dir /var/lib/gate --host 127.0.0.1 --port 8787
mkdir -p /mnt/gate
python3 scripts/gate_mount.py --root /path/to/repo --mount /mnt/gate --broker-host 127.0.0.1 --broker-port 8787 --foreground
```
Add `--max-hold-ms` (or set `GATE_MAX_HOLD_MS`) to change the default 1-hour lock cap.

## VM setup (recommended for stronger enforcement)
Use the one-command workflow: `gate up --vm-name <name> --vm-dir <dir> --ssh-key <pubkey> --repo-path <repo>`. The matching private key must exist alongside the public key (same path without `.pub`).
Logs live in `$XDG_STATE_HOME/gate/logs/<vm-name>/`. List and stop VMs with `gate vm-list` and `gate down`.
SSHFS is the supported host mount method; VirtioFS is a future option for performance.

If your terminal stops echoing after `gate up`, run `stty echo`.

## FIFO smoke test (over SSHFS)
```
./scripts/smoke_test_fifo_sshfs.sh /mnt/gate_host
```

## Config defaults
- State dir: `/var/lib/gate`
- Broker host/port: `127.0.0.1:8787`
- Max hold cap: `GATE_MAX_HOLD_MS` (default: 3600000; applies to read/write locks)
- Env vars: `GATE_STATE_DIR`, `GATE_BROKER_HOST`, `GATE_BROKER_PORT`, `GATE_MAX_HOLD_MS`

## Roadmap
- Replace SSHFS with VirtioFS for performance.
- Swap HTTP for Unix socket or gRPC.
- Move broker to Rust for stronger isolation.
