#!/usr/bin/env python3
"""Lock demo waiter (Terminal B)."""

import os
import time


def main() -> None:
    path = "/home/kajsfasdfnaf/.local/state/gate/mounts/gate-vm/LOCK_DEMO.txt"
    print("B: about to open for write:", path, flush=True)
    start = time.time()
    fd = os.open(path, os.O_WRONLY)
    elapsed = time.time() - start
    print(f"B: lock acquired after {elapsed:.2f}s, fd = {fd}", flush=True)
    print("B: closing fd", flush=True)
    os.close(fd)
    print("B: released", flush=True)


if __name__ == "__main__":
    main()
