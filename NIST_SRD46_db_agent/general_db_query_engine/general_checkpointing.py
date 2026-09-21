"""Crash-safe checkpoint primitives shared by the SRD-46 agents.

The normal analysis artifacts are human-readable, but they are not sufficient
to resume an interrupted Python call: live dataclasses, NumPy arrays and ReAct
state can be lost between two artifact writes.  This module provides a small
transactional store for that internal state.

Checkpoints are deliberately local to one run directory and are bound to an
exact caller-supplied identity hash.  A checkpoint from a different prompt,
card, grid or code contract is rejected instead of being reused silently.
Values are committed as checksummed pickle or canonical JSON blobs in SQLite;
SQLite's transaction boundary is the durability boundary.  Pickle payloads
must therefore only be read from a trusted run directory created by this
application.
"""

from __future__ import annotations

import hashlib
import json
import os
import pickle
import sqlite3
import threading
import time
from pathlib import Path
from typing import Any, Iterable, Mapping, Optional


SCHEMA_VERSION = "srd46-durable-checkpoint/v1"


class CheckpointError(RuntimeError):
    """Base class for durable-checkpoint failures."""


class CheckpointIdentityError(CheckpointError):
    """Raised when a run attempts to reuse another run's checkpoint."""


class CheckpointCorruptionError(CheckpointError):
    """Raised when a committed blob no longer matches its receipt."""


def canonical_json_bytes(value: Any) -> bytes:
    """Return deterministic UTF-8 JSON bytes for an identity payload."""

    return json.dumps(
        value,
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
        default=str,
    ).encode("utf-8")


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def identity_sha256(value: Any) -> str:
    return sha256_bytes(canonical_json_bytes(value))


def file_sha256(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def artifact_receipts(paths: Iterable[str | Path]) -> list[dict[str, Any]]:
    """Return stable size/hash receipts for existing artifact files."""

    rows: list[dict[str, Any]] = []
    for value in paths:
        path = Path(value)
        if not path.is_file():
            continue
        stat = path.stat()
        rows.append({
            "path": str(path.absolute()),
            "size": int(stat.st_size),
            "sha256": file_sha256(path),
        })
    return rows


def validate_artifact_receipts(rows: Iterable[Mapping[str, Any]]) -> bool:
    """Fail closed when any artifact is missing, resized or changed."""

    rows = list(rows)
    if not rows:
        return False
    for row in rows:
        path = Path(str(row.get("path") or ""))
        if not path.is_file():
            return False
        try:
            expected_size = int(row.get("size"))
        except (TypeError, ValueError):
            return False
        if path.stat().st_size != expected_size:
            return False
        expected_hash = str(row.get("sha256") or "")
        if len(expected_hash) != 64 or file_sha256(path) != expected_hash:
            return False
    return True


def atomic_write_json(path: str | Path, payload: Any) -> None:
    """Replace *path* atomically after flushing the new JSON file."""

    data = json.dumps(payload, indent=2, ensure_ascii=False, default=str)
    atomic_write_text(path, data + "\n")


def atomic_write_text(path: str | Path, data: str) -> None:
    """Replace a UTF-8 text artifact atomically after flushing its bytes."""

    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    temporary = target.with_name(
        f".{target.name}.{os.getpid()}.{threading.get_ident()}.tmp"
    )
    try:
        with temporary.open("w", encoding="utf-8", newline="\n") as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(temporary, target)
    finally:
        try:
            temporary.unlink(missing_ok=True)
        except OSError:
            pass


class DurableCheckpointStore:
    """Transactional, identity-bound run state.

    A fresh SQLite connection is used for every operation.  This is slightly
    more expensive than retaining one connection, but it behaves predictably
    across the analysis pipeline's worker threads and spawned processes.
    """

    def __init__(
        self,
        path: str | Path,
        *,
        identity: Any,
        create: bool = True,
    ) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.identity = identity_sha256(identity)
        self._identity_payload = canonical_json_bytes(identity).decode("utf-8")
        self._lock = threading.RLock()
        if not create and not self.path.is_file():
            raise FileNotFoundError(self.path)
        self._initialise()

    def _connect(self) -> sqlite3.Connection:
        connection = sqlite3.connect(
            str(self.path),
            timeout=60.0,
            isolation_level=None,
        )
        connection.execute("PRAGMA busy_timeout=60000")
        # DELETE mode is more portable than WAL on mapped/network drives.
        connection.execute("PRAGMA journal_mode=DELETE")
        connection.execute("PRAGMA synchronous=FULL")
        connection.execute("PRAGMA foreign_keys=ON")
        return connection

    def _initialise(self) -> None:
        with self._lock, self._connect() as connection:
            connection.executescript(
                """
                CREATE TABLE IF NOT EXISTS checkpoint_meta (
                    name TEXT PRIMARY KEY,
                    value TEXT NOT NULL
                );
                CREATE TABLE IF NOT EXISTS checkpoint_values (
                    scope TEXT NOT NULL,
                    key TEXT NOT NULL,
                    serializer TEXT NOT NULL,
                    payload BLOB NOT NULL,
                    sha256 TEXT NOT NULL,
                    committed_at REAL NOT NULL,
                    PRIMARY KEY (scope, key)
                );
                CREATE TABLE IF NOT EXISTS checkpoint_events (
                    seq INTEGER PRIMARY KEY AUTOINCREMENT,
                    committed_at REAL NOT NULL,
                    event TEXT NOT NULL,
                    payload_json TEXT NOT NULL
                );
                """
            )
            existing = dict(connection.execute(
                "SELECT name, value FROM checkpoint_meta"
            ).fetchall())
            if existing:
                if existing.get("schema_version") != SCHEMA_VERSION:
                    raise CheckpointIdentityError(
                        "checkpoint schema mismatch: "
                        f"{existing.get('schema_version')!r}"
                    )
                if existing.get("identity_sha256") != self.identity:
                    raise CheckpointIdentityError(
                        "checkpoint identity does not match this run"
                    )
                return
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.executemany(
                    "INSERT INTO checkpoint_meta(name, value) VALUES (?, ?)",
                    [
                        ("schema_version", SCHEMA_VERSION),
                        ("identity_sha256", self.identity),
                        ("identity_json", self._identity_payload),
                        ("created_at", repr(time.time())),
                    ],
                )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise

    def _put(self, scope: str, key: str, serializer: str, data: bytes) -> str:
        digest = sha256_bytes(data)
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    """
                    INSERT INTO checkpoint_values
                        (scope, key, serializer, payload, sha256, committed_at)
                    VALUES (?, ?, ?, ?, ?, ?)
                    ON CONFLICT(scope, key) DO UPDATE SET
                        serializer=excluded.serializer,
                        payload=excluded.payload,
                        sha256=excluded.sha256,
                        committed_at=excluded.committed_at
                    """,
                    (
                        str(scope), str(key), serializer,
                        sqlite3.Binary(data), digest, time.time(),
                    ),
                )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise
        return digest

    def put_pickle(self, scope: str, key: str, value: Any) -> str:
        return self._put(
            scope,
            key,
            "pickle-v5",
            pickle.dumps(value, protocol=5),
        )

    def put_json(self, scope: str, key: str, value: Any) -> str:
        return self._put(scope, key, "json", canonical_json_bytes(value))

    def _get(self, scope: str, key: str) -> Optional[tuple[str, bytes]]:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                """
                SELECT serializer, payload, sha256
                FROM checkpoint_values WHERE scope=? AND key=?
                """,
                (str(scope), str(key)),
            ).fetchone()
        if row is None:
            return None
        serializer, payload, expected = row
        data = bytes(payload)
        actual = sha256_bytes(data)
        if actual != expected:
            raise CheckpointCorruptionError(
                f"checkpoint blob {scope}/{key} failed SHA-256 validation"
            )
        return str(serializer), data

    def get_pickle(self, scope: str, key: str, default: Any = None) -> Any:
        row = self._get(scope, key)
        if row is None:
            return default
        serializer, data = row
        if serializer != "pickle-v5":
            raise CheckpointCorruptionError(
                f"checkpoint blob {scope}/{key} is {serializer}, not pickle"
            )
        return pickle.loads(data)

    def get_json(self, scope: str, key: str, default: Any = None) -> Any:
        row = self._get(scope, key)
        if row is None:
            return default
        serializer, data = row
        if serializer != "json":
            raise CheckpointCorruptionError(
                f"checkpoint blob {scope}/{key} is {serializer}, not JSON"
            )
        return json.loads(data.decode("utf-8"))

    def contains(self, scope: str, key: str) -> bool:
        with self._lock, self._connect() as connection:
            row = connection.execute(
                "SELECT 1 FROM checkpoint_values WHERE scope=? AND key=?",
                (str(scope), str(key)),
            ).fetchone()
        return row is not None

    def keys(self, scope: str) -> list[str]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                "SELECT key FROM checkpoint_values WHERE scope=? ORDER BY key",
                (str(scope),),
            ).fetchall()
        return [str(row[0]) for row in rows]

    def delete_scope(self, scope: str) -> None:
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    "DELETE FROM checkpoint_values WHERE scope=?",
                    (str(scope),),
                )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise

    def event(self, event: str, **payload: Any) -> None:
        payload_json = canonical_json_bytes(payload).decode("utf-8")
        with self._lock, self._connect() as connection:
            connection.execute("BEGIN IMMEDIATE")
            try:
                connection.execute(
                    """
                    INSERT INTO checkpoint_events
                        (committed_at, event, payload_json)
                    VALUES (?, ?, ?)
                    """,
                    (time.time(), str(event), payload_json),
                )
                connection.execute("COMMIT")
            except Exception:
                connection.execute("ROLLBACK")
                raise

    def event_rows(self) -> list[dict[str, Any]]:
        with self._lock, self._connect() as connection:
            rows = connection.execute(
                """
                SELECT seq, committed_at, event, payload_json
                FROM checkpoint_events ORDER BY seq
                """
            ).fetchall()
        return [
            {
                "seq": int(seq),
                "committed_at": float(committed_at),
                "event": str(event),
                "payload": json.loads(payload_json),
            }
            for seq, committed_at, event, payload_json in rows
        ]


__all__ = [
    "CheckpointCorruptionError",
    "CheckpointError",
    "CheckpointIdentityError",
    "DurableCheckpointStore",
    "artifact_receipts",
    "atomic_write_json",
    "atomic_write_text",
    "canonical_json_bytes",
    "file_sha256",
    "identity_sha256",
    "validate_artifact_receipts",
]
