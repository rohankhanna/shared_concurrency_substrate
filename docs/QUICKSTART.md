# Gate Quickstart (Host‑Direct)

This is the shortest verified path to a working end‑to‑end setup with correct locking.

## 1) Build the binary
```
PYTHONPATH=./src python3 -m gate.cli build-binary
```

## 2) Bring everything up
```
./dist/gate up \
  --base ubuntu-24.04 \
  --vm-dir ./vm_build \
  --vm-name gate-vm \
  --ssh-key ~/.ssh/shared_concurrency_substrate_test.pub \
  --repo-path /path/to/host/repo
```

## 3) Verify locking (single command)
```
GATE_DEMO_MOUNT=$HOME/.local/state/gate/mounts/gate-host-direct \
GATE_DEMO_FILE=README.md \
python3 tests/manual/lock_demo_run.py
```

## 4) Shutdown
```
./dist/gate down --vm-name gate-vm
```

## Troubleshooting
- **Mount dir not empty**: `./dist/gate clean --vm-name gate-vm`
- **Terminal not echoing after `gate up`**: `stty echo`
- **Mount stale / not connected**: `./dist/gate clean --vm-name gate-vm` then re‑run `gate up`
- **Lock demo doesn’t block**: run `./dist/gate status --vm-name gate-vm` and confirm
  `Host direct: running` + `Host direct mount: mounted`.

## Reproducible build (best effort)
```
./scripts/build_gate_binary_repro.sh
```

Version stamping is taken from `src/gate/VERSION`.
