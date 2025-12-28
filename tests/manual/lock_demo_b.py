#!/usr/bin/env python3
"""Lock demo waiter (Terminal B)."""

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


def _wait_for_exists(path: str) -> None:
    retries = 50
    delay = 0.2
    for _ in range(retries):
        if os.path.exists(path):
            return
        _refresh_parent(path)
        time.sleep(delay)
    raise FileNotFoundError(path)


def _open_with_retry(path: str, flags: int) -> int:
    retries = 50
    delay = 0.2
    for _ in range(retries):
        try:
            return os.open(path, flags)
        except FileNotFoundError:
            _refresh_parent(path)
            time.sleep(delay)
    raise FileNotFoundError(path)


def main() -> None:
    path = _demo_path()
    print("B: about to open for write:", path, flush=True)
    _wait_for_exists(path)
    start = time.time()
    fd = _open_with_retry(path, os.O_WRONLY)
    elapsed = time.time() - start
    print(f"B: lock acquired after {elapsed:.2f}s, fd = {fd}", flush=True)
    print("B: closing fd", flush=True)
    os.close(fd)
    print("B: released", flush=True)


if __name__ == "__main__":
    main()
