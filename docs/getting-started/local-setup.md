# Local Setup (Single Machine)

This mode runs the broker and mount on your local machine without a VM.

## Start the broker
```bash
./dist/gate broker --state-dir /var/lib/gate --host 127.0.0.1 --port 8787
```

## Mount the repo view
In another terminal:
```bash
mkdir -p /mnt/gate
./dist/gate mount \
  --root /path/to/repo \
  --mount /mnt/gate \
  --broker-host 127.0.0.1 \
  --broker-port 8787 \
  --foreground
```

Open `/mnt/gate` in your editor. All reads and writes are brokered.

### Python-only alternative
```bash
python3 scripts/gate_broker.py --state-dir /var/lib/gate --host 127.0.0.1 --port 8787
python3 scripts/gate_mount.py --root /path/to/repo --mount /mnt/gate --broker-host 127.0.0.1 --broker-port 8787 --foreground
```

## Unmount
```bash
fusermount3 -u /mnt/gate
```
