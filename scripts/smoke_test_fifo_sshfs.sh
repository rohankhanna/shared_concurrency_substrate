#!/usr/bin/env bash
set -euo pipefail

usage() {
  cat <<'USAGE'
Usage: smoke_test_fifo_sshfs.sh [mount-path]

Default mount path: /mnt/gate_host
USAGE
}

MOUNT_PATH="${1:-/mnt/gate_host}"
if [[ "$MOUNT_PATH" == "-h" || "$MOUNT_PATH" == "--help" ]]; then
  usage
  exit 0
fi

if [[ ! -d "$MOUNT_PATH" ]]; then
  echo "Mount path not found: $MOUNT_PATH" >&2
  exit 1
fi

TEST_FILE="$MOUNT_PATH/.gate_fifo_lock_test.txt"
export TEST_FILE

python3 - <<'PY'
import multiprocessing as mp
import os
import time
import sys

path = os.environ["TEST_FILE"]

hold_seconds = 5


def writer():
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("lock-holder")
        handle.flush()
        time.sleep(hold_seconds)


def contender(queue: mp.Queue):
    start = time.time()
    with open(path, "w", encoding="utf-8") as handle:
        handle.write("contender")
        handle.flush()
    queue.put(time.time() - start)


if __name__ == "__main__":
    os.makedirs(os.path.dirname(path), exist_ok=True)
    queue = mp.Queue()

    p1 = mp.Process(target=writer)
    p1.start()
    time.sleep(1)

    p2 = mp.Process(target=contender, args=(queue,))
    p2.start()
    p2.join()
    p1.join()

    elapsed = queue.get()
    print(f"Contender open elapsed: {elapsed:.2f}s")
    if elapsed < hold_seconds - 1:
        print("FAIL: lock did not block long enough")
        sys.exit(1)

    print("PASS: FIFO lock blocking observed")
PY
