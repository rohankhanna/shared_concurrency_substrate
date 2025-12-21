"""HTTP client for the Gate lock broker."""

from __future__ import annotations

import json
import http.client
from dataclasses import dataclass


@dataclass(frozen=True)
class BrokerEndpoint:
    host: str
    port: int


class LockBrokerClient:
    def __init__(self, endpoint: BrokerEndpoint, timeout_seconds: float | None = None) -> None:
        self.endpoint = endpoint
        self.timeout_seconds = timeout_seconds

    def _request(self, method: str, path: str, payload: dict | None = None) -> dict:
        body = None
        headers = {"Accept": "application/json"}
        if payload is not None:
            body = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
            headers["Content-Length"] = str(len(body))
        conn = http.client.HTTPConnection(
            self.endpoint.host, self.endpoint.port, timeout=self.timeout_seconds
        )
        conn.request(method, path, body=body, headers=headers)
        resp = conn.getresponse()
        data = resp.read()
        conn.close()
        try:
            payload = json.loads(data.decode("utf-8")) if data else {}
        except json.JSONDecodeError:
            payload = {}
        if resp.status >= 400:
            error = payload.get("error") or payload.get("status") or "request failed"
            raise RuntimeError(f"broker error {resp.status}: {error}")
        return payload

    def acquire(
        self,
        path: str,
        mode: str,
        owner: str,
        timeout_ms: int | None,
        lease_ms: int,
    ) -> dict:
        payload = {
            "path": path,
            "mode": mode,
            "owner": owner,
            "timeout_ms": timeout_ms,
            "lease_ms": lease_ms,
        }
        return self._request("POST", "/v1/locks/acquire", payload)

    def release(self, lock_id: str, owner: str) -> dict:
        payload = {"lock_id": lock_id, "owner": owner}
        return self._request("POST", "/v1/locks/release", payload)

    def heartbeat(self, lock_id: str, owner: str, lease_ms: int) -> dict:
        payload = {"lock_id": lock_id, "owner": owner, "lease_ms": lease_ms}
        return self._request("POST", "/v1/locks/heartbeat", payload)

    def status(self, path: str | None = None) -> dict:
        if path:
            return self._request("GET", f"/v1/locks/status?path={path}")
        return self._request("GET", "/v1/locks/status")
