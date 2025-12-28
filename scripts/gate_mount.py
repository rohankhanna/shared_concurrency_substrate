#!/usr/bin/env python3
"""Mount the Gate FUSE filesystem (shared concurrency substrate)."""

from __future__ import annotations

import argparse
import os
import socket
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SRC = ROOT / "src"
sys.path.insert(0, str(SRC))

from gate.client import BrokerEndpoint, LockBrokerClient  # noqa: E402
from gate.config import BrokerConfig  # noqa: E402
from gate.fuse_fs import mount_fuse  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", required=True, help="Real repo root (read-only to users)")
    parser.add_argument("--mount", required=True, help="Mount point for the FUSE view")
    parser.add_argument("--broker-host", default=BrokerConfig().host)
    parser.add_argument("--broker-port", type=int, default=BrokerConfig().port)
    parser.add_argument("--lease-ms", type=int, default=BrokerConfig().lease_ms)
    parser.add_argument("--max-hold-ms", type=int, default=BrokerConfig().max_hold_ms)
    parser.add_argument("--acquire-timeout-ms", type=int, default=BrokerConfig().acquire_timeout_ms)
    parser.add_argument("--foreground", action="store_true")
    parser.add_argument("--owner", default=None)
    args = parser.parse_args()

    owner = args.owner
    if owner is None:
        owner = f"{socket.gethostname()}:{os.getpid()}"

    endpoint = BrokerEndpoint(host=args.broker_host, port=args.broker_port)
    client = LockBrokerClient(endpoint, timeout_seconds=None)

    mount_fuse(
        root=args.root,
        mountpoint=args.mount,
        broker=client,
        owner=owner,
        lease_ms=args.lease_ms,
        acquire_timeout_ms=args.acquire_timeout_ms,
        max_hold_ms=args.max_hold_ms,
        foreground=args.foreground,
    )


if __name__ == "__main__":
    main()
