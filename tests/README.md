# Tests

This repository organizes tests as:
- `tests/automated/`: automated checks that can run headless.
- `tests/manual/`: manual, interactive demos and workflows.

## Manual tests
- `tests/manual/lock_demo_a.py`: lock holder for two-terminal demo.
- `tests/manual/lock_demo_b.py`: lock waiter for two-terminal demo.

Both scripts accept:
- `GATE_DEMO_MOUNT` (default: `~/.local/state/gate/mounts/gate-vm`)
- `GATE_DEMO_FILE` (default: `LOCK_DEMO.txt`)
