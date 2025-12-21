"""Shared config defaults for the Gate lock broker and FUSE mount."""

from __future__ import annotations

import os
from dataclasses import dataclass

DEFAULT_STATE_DIR = os.environ.get("GATE_STATE_DIR", "/var/lib/gate")
DEFAULT_DB_FILENAME = "locks.db"
DEFAULT_BROKER_HOST = os.environ.get("GATE_BROKER_HOST", "127.0.0.1")
DEFAULT_BROKER_PORT = int(os.environ.get("GATE_BROKER_PORT", "8787"))
DEFAULT_LEASE_MS = int(os.environ.get("GATE_LEASE_MS", "3600000"))
DEFAULT_ACQUIRE_TIMEOUT_MS = os.environ.get("GATE_ACQUIRE_TIMEOUT_MS")


def _parse_timeout(value: str | None) -> int | None:
    if value is None:
        return None
    try:
        return int(value)
    except ValueError:
        return None


DEFAULT_ACQUIRE_TIMEOUT_MS_VALUE = _parse_timeout(DEFAULT_ACQUIRE_TIMEOUT_MS)


@dataclass(frozen=True)
class BrokerConfig:
    state_dir: str = DEFAULT_STATE_DIR
    host: str = DEFAULT_BROKER_HOST
    port: int = DEFAULT_BROKER_PORT
    lease_ms: int = DEFAULT_LEASE_MS
    acquire_timeout_ms: int | None = DEFAULT_ACQUIRE_TIMEOUT_MS_VALUE
