# Shared Concurrency Substrate Release Checklist

Date: 2025-12-21

## Pre-release
- [ ] Ensure `scripts/gate_broker.py` and `scripts/gate_mount.py` run locally.
- [ ] Confirm `/var/lib/gate/locks.db` is created on first broker start.
- [ ] Validate FIFO behavior with `scripts/smoke_test_fifo_sshfs.sh` (or NFS host mount if enabled).
- [ ] Verify VM bundles build/run (QEMU and Firecracker).
- [ ] Update docs for any CLI or config changes.

## Publish
- [ ] Initialize git and push to GitHub.
- [ ] Tag release with date (YYYY-MM-DD).
