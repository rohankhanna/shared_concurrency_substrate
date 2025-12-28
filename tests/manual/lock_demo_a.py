#!/usr/bin/env python3
"""Lock demo writer (Terminal A)."""

import os
import time


def main() -> None:
    path = "/home/kajsfasdfnaf/.local/state/gate/mounts/gate-vm/LOCK_DEMO.txt"
    print("A: opening (create) for write:", path, flush=True)
    fd = os.open(path, os.O_WRONLY | os.O_CREAT)
    print("A: lock acquired, fd =", fd, flush=True)
    for i in range(1, 6):
        print(f"A: holding lock... {i*3}s", flush=True)
        time.sleep(3)
    print("A: closing fd", flush=True)
    os.close(fd)
    print("A: released", flush=True)


if __name__ == "__main__":
    main()
