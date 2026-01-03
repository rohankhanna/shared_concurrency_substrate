# Contributing

## Development Setup

1.  Follow the [Installation](../getting-started/installation.md) guide.
2.  Install dev dependencies (if any).

## Testing

### Manual Demo
Run the lock verification demo:
```bash
GATE_DEMO_MOUNT=$HOME/.local/state/gate/mounts/gate-host-direct \
GATE_DEMO_FILE=README.md \
python3 tests/manual/lock_demo_run.py
```

### Automated Tests
(Placeholder for automated test instructions)

```
