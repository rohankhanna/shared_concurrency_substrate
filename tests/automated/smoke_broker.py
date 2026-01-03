#!/usr/bin/env python3
"""Automated smoke test for broker FIFO behavior (no FUSE)."""

from __future__ import annotations

import socket
import tempfile
import threading
import time

from gate.broker import LockBrokerServer
from gate.client import BrokerEndpoint, LockBrokerClient
from gate.config import BrokerConfig


def _pick_port() -> int:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind(("127.0.0.1", 0))
    _, port = sock.getsockname()
    sock.close()
    return port


def main() -> int:
    port = _pick_port()
    with tempfile.TemporaryDirectory() as state_dir:
        config = BrokerConfig(
            state_dir=state_dir,
            host="127.0.0.1",
            port=port,
            lease_ms=10_000,
            max_hold_ms=60_000,
            acquire_timeout_ms=5_000,
        )
        server = LockBrokerServer(config)
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()

        client = LockBrokerClient(BrokerEndpoint(host="127.0.0.1", port=port))

        lock_a = client.acquire(
            path="/smoke.txt",
            mode="write",
            owner="owner-A",
            timeout_ms=2_000,
            lease_ms=10_000,
            max_hold_ms=60_000,
        )["lock"]

        result = {"elapsed": None}

        def _acquire_b() -> None:
            start = time.time()
            lock_b = client.acquire(
                path="/smoke.txt",
                mode="write",
                owner="owner-B",
                timeout_ms=5_000,
                lease_ms=10_000,
                max_hold_ms=60_000,
            )["lock"]
            result["elapsed"] = time.time() - start
            client.release(lock_b["lock_id"], "owner-B")

        thread_b = threading.Thread(target=_acquire_b)
        thread_b.start()

        time.sleep(1.5)
        client.release(lock_a["lock_id"], "owner-A")

        thread_b.join(timeout=10)
        if result["elapsed"] is None:
            raise RuntimeError("Broker smoke test failed: lock B never acquired")
        if result["elapsed"] < 1.0:
            raise RuntimeError(
                f"Broker smoke test failed: lock B acquired too quickly ({result['elapsed']:.2f}s)"
            )

    print("smoke_broker: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
