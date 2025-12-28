"""FUSE passthrough filesystem with broker-enforced locks."""

from __future__ import annotations

import errno
import os
import sys
import threading
from typing import Dict

from fuse import FUSE, FuseOSError, Operations

from .client import LockBrokerClient


class GateFuse(Operations):
    def __init__(
        self,
        root: str,
        broker: LockBrokerClient,
        owner: str,
        lease_ms: int,
        acquire_timeout_ms: int | None = None,
        max_hold_ms: int | None = None,
    ) -> None:
        self.root = os.path.realpath(root)
        self.broker = broker
        self.owner = owner
        self.lease_ms = lease_ms
        self.acquire_timeout_ms = acquire_timeout_ms
        self.max_hold_ms = max_hold_ms
        self._fd_lock = threading.Lock()
        self._next_fh = 0
        self._handle_locks: Dict[int, str] = {}
        self._handle_paths: Dict[int, str] = {}
        self._handle_fds: Dict[int, int] = {}

    def _finalize_handle(self, fh: int, path: str, reason: str) -> None:
        with self._fd_lock:
            lock_id = self._handle_locks.pop(fh, None)
            self._handle_paths.pop(fh, None)
            fd = self._handle_fds.pop(fh, None)
        if os.environ.get("GATE_FUSE_DEBUG") == "1":
            print(
                f"gate-fuse finalize reason={reason} path={path!r} fh={fh} lock_id={lock_id!r}",
                file=sys.stderr,
                flush=True,
            )
        if fd is not None:
            os.close(fd)
        if lock_id:
            self._release(lock_id)

    @staticmethod
    def _is_write_flags(flags: int) -> bool:
        write_flags = os.O_WRONLY | os.O_RDWR | os.O_TRUNC | os.O_APPEND
        return (flags & write_flags) != 0

    def _full_path(self, path: str) -> str:
        path = path.lstrip("/")
        return os.path.join(self.root, path)

    @staticmethod
    def _lock_key(path: str) -> str:
        path = path.lstrip("/")
        return path or "."

    def _acquire(self, path: str, mode: str) -> str:
        payload = self.broker.acquire(
            path=path,
            mode=mode,
            owner=self.owner,
            timeout_ms=self.acquire_timeout_ms,
            lease_ms=self.lease_ms,
            max_hold_ms=self.max_hold_ms,
        )
        return payload["lock"]["lock_id"]

    def _release(self, lock_id: str) -> None:
        self.broker.release(lock_id=lock_id, owner=self.owner)

    def _heartbeat(self, lock_id: str) -> None:
        self.broker.heartbeat(lock_id=lock_id, owner=self.owner, lease_ms=self.lease_ms)

    def _acquire_multi(self, paths: list[str]) -> list[str]:
        lock_ids = []
        for path in sorted(paths):
            lock_ids.append(self._acquire(path, "write"))
        return lock_ids

    def _release_multi(self, lock_ids: list[str]) -> None:
        for lock_id in reversed(lock_ids):
            self._release(lock_id)

    def access(self, path, mode):
        full_path = self._full_path(path)
        if not os.access(full_path, mode):
            raise FuseOSError(errno.EACCES)

    def chmod(self, path, mode):
        lock_id = self._acquire(self._lock_key(path), "write")
        try:
            return os.chmod(self._full_path(path), mode)
        finally:
            self._release(lock_id)

    def chown(self, path, uid, gid):
        lock_id = self._acquire(self._lock_key(path), "write")
        try:
            return os.chown(self._full_path(path), uid, gid)
        finally:
            self._release(lock_id)

    def getattr(self, path, fh=None):
        full_path = self._full_path(path)
        if os.environ.get("GATE_FUSE_DEBUG") == "1":
            print(f"gate-fuse getattr path={path!r} full_path={full_path!r}", file=sys.stderr, flush=True)
        try:
            st = os.lstat(full_path)
        except FileNotFoundError:
            if os.environ.get("GATE_FUSE_DEBUG") == "1":
                print(f"gate-fuse getattr ENOENT path={path!r} full_path={full_path!r}", file=sys.stderr, flush=True)
            raise
        return {key: getattr(st, key) for key in (
            "st_atime",
            "st_ctime",
            "st_gid",
            "st_mode",
            "st_mtime",
            "st_nlink",
            "st_size",
            "st_uid",
        )}

    def readdir(self, path, fh):
        full_path = self._full_path(path)
        if os.environ.get("GATE_FUSE_DEBUG") == "1":
            print(f"gate-fuse readdir path={path!r} full_path={full_path!r}", file=sys.stderr, flush=True)
        dirents = [".", ".."]
        if os.path.isdir(full_path):
            dirents.extend(os.listdir(full_path))
        for entry in dirents:
            yield entry

    def readlink(self, path):
        pathname = os.readlink(self._full_path(path))
        if pathname.startswith("/"):
            return os.path.relpath(pathname, self.root)
        return pathname

    def mknod(self, path, mode, dev):
        lock_id = self._acquire(self._lock_key(path), "write")
        try:
            return os.mknod(self._full_path(path), mode, dev)
        finally:
            self._release(lock_id)

    def rmdir(self, path):
        lock_id = self._acquire(self._lock_key(path), "write")
        try:
            return os.rmdir(self._full_path(path))
        finally:
            self._release(lock_id)

    def mkdir(self, path, mode):
        lock_id = self._acquire(self._lock_key(path), "write")
        try:
            return os.mkdir(self._full_path(path), mode)
        finally:
            self._release(lock_id)

    def statfs(self, path):
        full_path = self._full_path(path)
        stv = os.statvfs(full_path)
        return {key: getattr(stv, key) for key in (
            "f_bavail",
            "f_bfree",
            "f_blocks",
            "f_bsize",
            "f_favail",
            "f_ffree",
            "f_files",
            "f_flag",
            "f_frsize",
            "f_namemax",
        )}

    def unlink(self, path):
        lock_id = self._acquire(self._lock_key(path), "write")
        try:
            return os.unlink(self._full_path(path))
        finally:
            self._release(lock_id)

    def symlink(self, name, target):
        lock_ids = self._acquire_multi([self._lock_key(name), self._lock_key(target)])
        try:
            return os.symlink(name, self._full_path(target))
        finally:
            self._release_multi(lock_ids)

    def rename(self, old, new):
        lock_ids = self._acquire_multi([self._lock_key(old), self._lock_key(new)])
        try:
            return os.rename(self._full_path(old), self._full_path(new))
        finally:
            self._release_multi(lock_ids)

    def link(self, target, name):
        lock_ids = self._acquire_multi([self._lock_key(target), self._lock_key(name)])
        try:
            return os.link(self._full_path(target), self._full_path(name))
        finally:
            self._release_multi(lock_ids)

    def utimens(self, path, times=None):
        lock_id = self._acquire(self._lock_key(path), "write")
        try:
            return os.utime(self._full_path(path), times)
        finally:
            self._release(lock_id)

    def open(self, path, flags):
        mode = "write" if self._is_write_flags(flags) else "read"
        try:
            lock_id = self._acquire(self._lock_key(path), mode)
        except Exception as exc:
            if os.environ.get("GATE_FUSE_DEBUG") == "1":
                print(
                    f"gate-fuse acquire error path={path!r} mode={mode} err={exc!r}",
                    file=sys.stderr,
                    flush=True,
                )
            raise
        full_path = self._full_path(path)
        if os.environ.get("GATE_FUSE_DEBUG") == "1":
            print(f"gate-fuse open path={path!r} full_path={full_path!r}", file=sys.stderr, flush=True)
        try:
            fd = os.open(full_path, flags)
        except FileNotFoundError:
            if os.environ.get("GATE_FUSE_DEBUG") == "1":
                print(f"gate-fuse open ENOENT path={path!r} full_path={full_path!r}", file=sys.stderr, flush=True)
            raise
        with self._fd_lock:
            self._next_fh += 1
            fh = self._next_fh
            self._handle_locks[fh] = lock_id
            self._handle_paths[fh] = self._lock_key(path)
            self._handle_fds[fh] = fd
        return fh

    def create(self, path, mode, fi=None):
        lock_id = self._acquire(self._lock_key(path), "write")
        full_path = self._full_path(path)
        fd = os.open(full_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, mode)
        with self._fd_lock:
            self._next_fh += 1
            fh = self._next_fh
            self._handle_locks[fh] = lock_id
            self._handle_paths[fh] = self._lock_key(path)
            self._handle_fds[fh] = fd
        return fh

    def read(self, path, length, offset, fh):
        with self._fd_lock:
            fd = self._handle_fds.get(fh)
        if fd is None:
            raise FuseOSError(errno.EBADF)
        os.lseek(fd, offset, os.SEEK_SET)
        return os.read(fd, length)

    def write(self, path, buf, offset, fh):
        with self._fd_lock:
            lock_id = self._handle_locks.get(fh)
        if lock_id:
            self._heartbeat(lock_id)
        with self._fd_lock:
            fd = self._handle_fds.get(fh)
        if fd is None:
            raise FuseOSError(errno.EBADF)
        os.lseek(fd, offset, os.SEEK_SET)
        return os.write(fd, buf)

    def truncate(self, path, length, fh=None):
        lock_id = self._acquire(self._lock_key(path), "write")
        try:
            full_path = self._full_path(path)
            with open(full_path, "r+b") as f:
                f.truncate(length)
        finally:
            self._release(lock_id)

    def flush(self, path, fh):
        if os.environ.get("GATE_RELEASE_ON_FLUSH", "1") == "1":
            self._finalize_handle(fh, path, reason="flush")
            return 0
        with self._fd_lock:
            lock_id = self._handle_locks.get(fh)
        if lock_id:
            self._heartbeat(lock_id)
        return 0

    def release(self, path, fh):
        self._finalize_handle(fh, path, reason="release")
        return 0

    def fsync(self, path, fdatasync, fh):
        with self._fd_lock:
            lock_id = self._handle_locks.get(fh)
        if lock_id:
            self._heartbeat(lock_id)
        return 0


def mount_fuse(
    root: str,
    mountpoint: str,
    broker: LockBrokerClient,
    owner: str,
    lease_ms: int,
    acquire_timeout_ms: int | None,
    max_hold_ms: int | None,
    foreground: bool,
    allow_other: bool = False,
) -> None:
    if os.environ.get("GATE_FUSE_DEBUG") == "1":
        print(f"gate-fuse starting root={root!r} mountpoint={mountpoint!r}", file=sys.stderr, flush=True)
    fuse = GateFuse(root, broker, owner, lease_ms, acquire_timeout_ms, max_hold_ms)
    FUSE(fuse, mountpoint, foreground=foreground, allow_other=allow_other)
