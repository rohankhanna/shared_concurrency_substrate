#!/usr/bin/env python3
"""Run the Gate lock broker server (shared concurrency substrate)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from gate.broker import LockBrokerServer  # noqa: E402
from gate.config import BrokerConfig  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--state-dir", default=BrokerConfig().state_dir)
    parser.add_argument("--host", default=BrokerConfig().host)
    parser.add_argument("--port", type=int, default=BrokerConfig().port)
    parser.add_argument("--lease-ms", type=int, default=BrokerConfig().lease_ms)
    parser.add_argument("--acquire-timeout-ms", type=int, default=BrokerConfig().acquire_timeout_ms)
    args = parser.parse_args()

    config = BrokerConfig(
        state_dir=args.state_dir,
        host=args.host,
        port=args.port,
        lease_ms=args.lease_ms,
        acquire_timeout_ms=args.acquire_timeout_ms,
    )
    try:
        server = LockBrokerServer(config)
    except PermissionError as exc:
        print(f"Permission error creating state dir or DB: {exc}")
        print("Ensure the state directory exists and is writable (e.g., /var/lib/gate).")
        raise SystemExit(1)
    server.serve_forever()


if __name__ == "__main__":
    main()
