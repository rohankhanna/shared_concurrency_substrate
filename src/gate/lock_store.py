"""SQLite-backed lock store with FIFO fairness for read/write locks."""

from __future__ import annotations

import sqlite3
import threading
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path


@dataclass(frozen=True)
class LockInfo:
    lock_id: str
    path: str
    mode: str
    owner: str
    acquired_at: str
    lease_expires_at: str
    max_hold_ms: int | None
    hold_count: int


@dataclass(frozen=True)
class QueueInfo:
    req_id: int
    path: str
    mode: str
    owner: str
    requested_at: str


class LockStore:
    def __init__(self, db_path: str | Path) -> None:
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")
        self._cond = threading.Condition()
        self._init_schema()

    def _init_schema(self) -> None:
        cur = self._conn.cursor()
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS locks (
                lock_id TEXT PRIMARY KEY,
                path TEXT NOT NULL,
                mode TEXT NOT NULL,
                owner TEXT NOT NULL,
                acquired_at TEXT NOT NULL,
                lease_expires_at TEXT NOT NULL,
                max_hold_ms INTEGER,
                hold_count INTEGER NOT NULL DEFAULT 1
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS queue (
                req_id INTEGER PRIMARY KEY AUTOINCREMENT,
                path TEXT NOT NULL,
                mode TEXT NOT NULL,
                owner TEXT NOT NULL,
                requested_at TEXT NOT NULL
            )
            """
        )
        cur.execute("CREATE INDEX IF NOT EXISTS idx_queue_path ON queue(path)")
        cur.execute("CREATE INDEX IF NOT EXISTS idx_locks_path ON locks(path)")
        self._conn.commit()
        self._ensure_lock_columns()

    def _ensure_lock_columns(self) -> None:
        columns = {
            row[1] for row in self._conn.execute("PRAGMA table_info(locks)").fetchall()
        }
        if "max_hold_ms" not in columns:
            self._conn.execute("ALTER TABLE locks ADD COLUMN max_hold_ms INTEGER")
            self._conn.commit()
        if "hold_count" not in columns:
            self._conn.execute(
                "ALTER TABLE locks ADD COLUMN hold_count INTEGER NOT NULL DEFAULT 1"
            )
            self._conn.commit()

    @staticmethod
    def _now() -> datetime:
        return datetime.now(timezone.utc)

    def _cleanup_expired(self) -> None:
        now_iso = self._now().isoformat()
        self._conn.execute(
            "DELETE FROM locks WHERE lease_expires_at <= ?",
            (now_iso,),
        )
        rows = self._conn.execute(
            "SELECT lock_id, acquired_at, max_hold_ms FROM locks WHERE max_hold_ms IS NOT NULL",
        ).fetchall()
        now = self._now()
        for lock_id, acquired_at, max_hold_ms in rows:
            if max_hold_ms is None:
                continue
            try:
                acquired = datetime.fromisoformat(acquired_at)
            except ValueError:
                continue
            held_ms = (now - acquired).total_seconds() * 1000
            if held_ms >= max_hold_ms:
                self._conn.execute("DELETE FROM locks WHERE lock_id = ?", (lock_id,))
        self._conn.commit()

    def _has_write_lock(self, path: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM locks WHERE path = ? AND mode = 'write' LIMIT 1",
            (path,),
        ).fetchone()
        return row is not None

    def _has_any_lock(self, path: str) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM locks WHERE path = ? LIMIT 1",
            (path,),
        ).fetchone()
        return row is not None

    def _writer_ahead(self, path: str, req_id: int) -> bool:
        row = self._conn.execute(
            "SELECT 1 FROM queue WHERE path = ? AND mode = 'write' AND req_id < ? LIMIT 1",
            (path, req_id),
        ).fetchone()
        return row is not None

    def _earliest_req(self, path: str) -> int | None:
        row = self._conn.execute(
            "SELECT MIN(req_id) FROM queue WHERE path = ?",
            (path,),
        ).fetchone()
        if row is None:
            return None
        return row[0]

    def acquire(
        self,
        path: str,
        mode: str,
        owner: str,
        timeout_ms: int | None,
        lease_ms: int,
        max_hold_ms: int | None,
    ) -> LockInfo | None:
        if mode not in {"read", "write"}:
            raise ValueError("mode must be 'read' or 'write'")

        reentrant = self._conn.execute(
            "SELECT lock_id, mode, owner, acquired_at, lease_expires_at, max_hold_ms, hold_count "
            "FROM locks WHERE path = ? AND owner = ? LIMIT 1",
            (path, owner),
        ).fetchone()
        if reentrant is not None:
            (
                lock_id,
                existing_mode,
                existing_owner,
                acquired_at,
                lease_expires_at,
                existing_max_hold,
                hold_count,
            ) = reentrant
            can_reenter = existing_mode == "write" or existing_mode == mode
            if can_reenter:
                new_lease = (self._now() + timedelta(milliseconds=lease_ms)).isoformat()
                self._conn.execute(
                    "UPDATE locks SET lease_expires_at = ?, hold_count = hold_count + 1 WHERE lock_id = ?",
                    (new_lease, lock_id),
                )
                self._conn.commit()
                return LockInfo(
                    lock_id=lock_id,
                    path=path,
                    mode=existing_mode,
                    owner=existing_owner,
                    acquired_at=acquired_at,
                    lease_expires_at=new_lease,
                    max_hold_ms=existing_max_hold,
                    hold_count=hold_count + 1,
                )

            if existing_mode == "read" and mode == "write":
                other = self._conn.execute(
                    "SELECT 1 FROM locks WHERE path = ? AND owner != ? LIMIT 1",
                    (path, owner),
                ).fetchone()
                if other is None:
                    new_lease = (self._now() + timedelta(milliseconds=lease_ms)).isoformat()
                    self._conn.execute(
                        "UPDATE locks SET mode = 'write', lease_expires_at = ?, hold_count = hold_count + 1 "
                        "WHERE lock_id = ?",
                        (new_lease, lock_id),
                    )
                    self._conn.commit()
                    return LockInfo(
                        lock_id=lock_id,
                        path=path,
                        mode="write",
                        owner=existing_owner,
                        acquired_at=acquired_at,
                        lease_expires_at=new_lease,
                        max_hold_ms=existing_max_hold,
                        hold_count=hold_count + 1,
                    )

        requested_at = self._now().isoformat()
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO queue(path, mode, owner, requested_at) VALUES (?, ?, ?, ?)",
            (path, mode, owner, requested_at),
        )
        req_id = cur.lastrowid
        self._conn.commit()

        start = time.monotonic()
        with self._cond:
            while True:
                self._cleanup_expired()
                if self._can_grant(path, mode, req_id):
                    lock_id = str(uuid.uuid4())
                    acquired_at = self._now()
                    lease_expires_at = acquired_at + timedelta(milliseconds=lease_ms)
                    self._conn.execute(
                        "INSERT INTO locks(lock_id, path, mode, owner, acquired_at, lease_expires_at, max_hold_ms, hold_count) "
                        "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (
                            lock_id,
                            path,
                            mode,
                            owner,
                            acquired_at.isoformat(),
                            lease_expires_at.isoformat(),
                            max_hold_ms,
                            1,
                        ),
                    )
                    self._conn.execute("DELETE FROM queue WHERE req_id = ?", (req_id,))
                    self._conn.commit()
                    self._cond.notify_all()
                    return LockInfo(
                        lock_id=lock_id,
                        path=path,
                        mode=mode,
                        owner=owner,
                        acquired_at=acquired_at.isoformat(),
                        lease_expires_at=lease_expires_at.isoformat(),
                        max_hold_ms=max_hold_ms,
                        hold_count=1,
                    )

                if timeout_ms is not None:
                    elapsed_ms = int((time.monotonic() - start) * 1000)
                    remaining_ms = timeout_ms - elapsed_ms
                    if remaining_ms <= 0:
                        self._conn.execute("DELETE FROM queue WHERE req_id = ?", (req_id,))
                        self._conn.commit()
                        self._cond.notify_all()
                        return None
                    wait_time = remaining_ms / 1000.0
                else:
                    wait_time = 1.0

                self._cond.wait(timeout=wait_time)

    def _can_grant(self, path: str, mode: str, req_id: int) -> bool:
        if mode == "write":
            earliest = self._earliest_req(path)
            if earliest != req_id:
                return False
            if self._has_any_lock(path):
                return False
            return True

        if self._has_write_lock(path):
            return False
        if self._writer_ahead(path, req_id):
            return False
        return True

    def release(self, lock_id: str, owner: str) -> bool:
        row = self._conn.execute(
            "SELECT owner, hold_count FROM locks WHERE lock_id = ?",
            (lock_id,),
        ).fetchone()
        if row is None:
            return False
        if row[0] != owner:
            raise PermissionError("lock owner mismatch")
        hold_count = row[1] or 1
        if hold_count > 1:
            self._conn.execute(
                "UPDATE locks SET hold_count = hold_count - 1 WHERE lock_id = ?",
                (lock_id,),
            )
            self._conn.commit()
            with self._cond:
                self._cond.notify_all()
            return True
        self._conn.execute("DELETE FROM locks WHERE lock_id = ?", (lock_id,))
        self._conn.commit()
        with self._cond:
            self._cond.notify_all()
        return True

    def heartbeat(self, lock_id: str, owner: str, lease_ms: int) -> bool:
        row = self._conn.execute(
            "SELECT owner, acquired_at, max_hold_ms FROM locks WHERE lock_id = ?",
            (lock_id,),
        ).fetchone()
        if row is None:
            return False
        if row[0] != owner:
            raise PermissionError("lock owner mismatch")
        acquired_at = row[1]
        max_hold_ms = row[2]
        if max_hold_ms is not None:
            try:
                acquired = datetime.fromisoformat(acquired_at)
                held_ms = (self._now() - acquired).total_seconds() * 1000
                if held_ms >= max_hold_ms:
                    self._conn.execute("DELETE FROM locks WHERE lock_id = ?", (lock_id,))
                    self._conn.commit()
                    with self._cond:
                        self._cond.notify_all()
                    return False
            except ValueError:
                pass
        lease_expires_at = (self._now() + timedelta(milliseconds=lease_ms)).isoformat()
        self._conn.execute(
            "UPDATE locks SET lease_expires_at = ? WHERE lock_id = ?",
            (lease_expires_at, lock_id),
        )
        self._conn.commit()
        return True

    def status(self, path: str | None = None) -> dict:
        if path:
            locks = self._conn.execute(
                "SELECT lock_id, path, mode, owner, acquired_at, lease_expires_at, max_hold_ms, hold_count "
                "FROM locks WHERE path = ?",
                (path,),
            ).fetchall()
            queue = self._conn.execute(
                "SELECT req_id, path, mode, owner, requested_at FROM queue WHERE path = ? ORDER BY req_id",
                (path,),
            ).fetchall()
        else:
            locks = self._conn.execute(
                "SELECT lock_id, path, mode, owner, acquired_at, lease_expires_at, max_hold_ms, hold_count "
                "FROM locks",
            ).fetchall()
            queue = self._conn.execute(
                "SELECT req_id, path, mode, owner, requested_at FROM queue ORDER BY req_id",
            ).fetchall()

        return {
            "locks": [LockInfo(*row).__dict__ for row in locks],
            "queue": [QueueInfo(*row).__dict__ for row in queue],
        }
