#!/usr/bin/env python3
"""Run the lock demo in a single terminal by spawning A then B."""

from __future__ import annotations

import argparse
import os
import subprocess
import sys
import time
from pathlib import Path


def _parse_args() -> argparse.Namespace:
    default_mount = os.environ.get(
        "GATE_DEMO_MOUNT",
        os.path.join(
            os.path.expanduser("~"),
            ".local",
            "state",
            "gate",
            "mounts",
            "gate-host-direct",
        ),
    )
    default_file = os.environ.get("GATE_DEMO_FILE", "LOCK_DEMO.txt")

    parser = argparse.ArgumentParser(
        description="Run lock_demo_a then lock_demo_b in one terminal.",
    )
    parser.add_argument(
        "--mount",
        default=default_mount,
        help="Mount directory for the demo (env: GATE_DEMO_MOUNT).",
    )
    parser.add_argument(
        "--file",
        default=default_file,
        help="Relative path under the mount (env: GATE_DEMO_FILE).",
    )
    parser.add_argument(
        "--delay-secs",
        type=float,
        default=2.0,
        help="Delay before starting B (seconds).",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    base_dir = Path(__file__).resolve().parent
    script_a = base_dir / "lock_demo_a.py"
    script_b = base_dir / "lock_demo_b.py"

    if not script_a.exists() or not script_b.exists():
        print("Missing lock demo scripts.")
        return 2

    env = os.environ.copy()
    env["GATE_DEMO_MOUNT"] = args.mount
    env["GATE_DEMO_FILE"] = args.file
    env["PYTHONUNBUFFERED"] = "1"

    print(f"Launching A: {script_a}")
    proc_a = subprocess.Popen([sys.executable, "-u", str(script_a)], env=env)
    time.sleep(max(0.0, args.delay_secs))
    print(f"Launching B: {script_b}")
    proc_b = subprocess.Popen([sys.executable, "-u", str(script_b)], env=env)

    code_a = proc_a.wait()
    code_b = proc_b.wait()

    if code_a != 0 or code_b != 0:
        print(f"Demo failed: A={code_a}, B={code_b}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
