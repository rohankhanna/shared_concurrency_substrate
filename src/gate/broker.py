"""Lock broker HTTP server backed by SQLite."""

from __future__ import annotations

import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs, urlparse

from .config import BrokerConfig
from .lock_store import LockStore


class LockBrokerServer:
    def __init__(self, config: BrokerConfig) -> None:
        self.config = config
        db_path = os.path.join(config.state_dir, "locks.db")
        self.store = LockStore(db_path)

    def serve_forever(self) -> None:
        server = ThreadingHTTPServer(
            (self.config.host, self.config.port),
            self._make_handler(self.store, self.config),
        )
        server.serve_forever()

    @staticmethod
    def _make_handler(store: LockStore, config: BrokerConfig):
        class Handler(BaseHTTPRequestHandler):
            def _send_json(self, status: int, payload: dict) -> None:
                body = json.dumps(payload).encode("utf-8")
                self.send_response(status)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)

            def _read_json(self) -> dict:
                length = int(self.headers.get("Content-Length", "0"))
                if length <= 0:
                    return {}
                data = self.rfile.read(length)
                try:
                    return json.loads(data.decode("utf-8"))
                except json.JSONDecodeError:
                    return {}

            def log_message(self, format: str, *args) -> None:
                return

            def do_POST(self) -> None:  # noqa: N802
                if self.path == "/v1/locks/acquire":
                    payload = self._read_json()
                    path = payload.get("path")
                    mode = payload.get("mode")
                    owner = payload.get("owner")
                    timeout_ms = payload.get("timeout_ms", config.acquire_timeout_ms)
                    lease_ms = payload.get("lease_ms", config.lease_ms)
                    max_hold_ms = payload.get("max_hold_ms", config.max_hold_ms)
                    if not path or mode not in {"read", "write"} or not owner:
                        self._send_json(400, {"error": "invalid request"})
                        return
                    lock = store.acquire(path, mode, owner, timeout_ms, lease_ms, max_hold_ms)
                    if lock is None:
                        self._send_json(408, {"status": "timeout"})
                        return
                    self._send_json(200, {"status": "granted", "lock": lock.__dict__})
                    return

                if self.path == "/v1/locks/release":
                    payload = self._read_json()
                    lock_id = payload.get("lock_id")
                    owner = payload.get("owner")
                    if not lock_id or not owner:
                        self._send_json(400, {"error": "invalid request"})
                        return
                    try:
                        ok = store.release(lock_id, owner)
                    except PermissionError:
                        self._send_json(403, {"error": "owner mismatch"})
                        return
                    if not ok:
                        self._send_json(404, {"error": "lock not found"})
                        return
                    self._send_json(200, {"status": "released"})
                    return

                if self.path == "/v1/locks/heartbeat":
                    payload = self._read_json()
                    lock_id = payload.get("lock_id")
                    owner = payload.get("owner")
                    lease_ms = payload.get("lease_ms", config.lease_ms)
                    if not lock_id or not owner:
                        self._send_json(400, {"error": "invalid request"})
                        return
                    try:
                        ok = store.heartbeat(lock_id, owner, lease_ms)
                    except PermissionError:
                        self._send_json(403, {"error": "owner mismatch"})
                        return
                    if not ok:
                        self._send_json(404, {"error": "lock not found"})
                        return
                    self._send_json(200, {"status": "ok"})
                    return

                self._send_json(404, {"error": "not found"})

            def do_GET(self) -> None:  # noqa: N802
                parsed = urlparse(self.path)
                if parsed.path == "/v1/locks/status":
                    params = parse_qs(parsed.query)
                    path = params.get("path", [None])[0]
                    status = store.status(path)
                    self._send_json(200, status)
                    return
                self._send_json(404, {"error": "not found"})

        return Handler
