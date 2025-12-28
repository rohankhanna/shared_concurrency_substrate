#!/usr/bin/env python3
"""Lock demo writer (Terminal A)."""

import os
import time

MOUNT_DIR = os.environ.get(
    "GATE_DEMO_MOUNT",
    "/home/kajsfasdfnaf/.local/state/gate/mounts/gate-vm",
)
REL_PATH = os.environ.get("GATE_DEMO_FILE", "tests/LOCK_DEMO.txt")


def _demo_path() -> str:
    return os.path.join(MOUNT_DIR, REL_PATH)


def _refresh_parent(path: str) -> None:
    parent = os.path.dirname(path)
    try:
        os.listdir(parent)
    except FileNotFoundError:
        pass


def _open_with_retry(path: str, flags: int, mode: int | None = None) -> int:
    retries = 50
    delay = 0.2
    for _ in range(retries):
        try:
            if mode is None:
                return os.open(path, flags)
            return os.open(path, flags, mode)
        except FileNotFoundError:
            _refresh_parent(path)
            time.sleep(delay)
    raise FileNotFoundError(path)


def main() -> None:
    path = _demo_path()
    print("A: opening (create) for write:", path, flush=True)
    fd = _open_with_retry(path, os.O_WRONLY | os.O_CREAT)
    print("A: lock acquired, fd =", fd, flush=True)
    for i in range(1, 6):
        print(f"A: holding lock... {i*3}s", flush=True)
        time.sleep(3)
    print("A: closing fd", flush=True)
    os.close(fd)
    print("A: released", flush=True)


if __name__ == "__main__":
    main()
