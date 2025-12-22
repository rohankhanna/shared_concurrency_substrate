"""Shared concurrency substrate: lock broker + FUSE filesystem."""

from .lock_store import LockStore
from .broker import LockBrokerServer
from .client import BrokerEndpoint, LockBrokerClient

try:
    from .fuse_fs import GateFuse, mount_fuse
except Exception:  # pragma: no cover - allows broker-only usage without libfuse
    GateFuse = None  # type: ignore[assignment]
    mount_fuse = None  # type: ignore[assignment]
from .cli import main as gate_main

__all__ = [
    "LockStore",
    "LockBrokerServer",
    "BrokerEndpoint",
    "LockBrokerClient",
    "GateFuse",
    "mount_fuse",
    "gate_main",
]
