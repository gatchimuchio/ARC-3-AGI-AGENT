"""Atomic in-memory and SQLite backends for the semantic event ledger."""

from __future__ import annotations

import json
import sqlite3
import threading
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import Protocol, Sequence

from .memory_event import (
    CommitReceipt,
    MemoryEvent,
    apply_memory_event,
)
from .memory_image import MemoryImage
from .schema import canonical_json, digest_object

MEMORY_BACKEND_SCHEMA_VERSION = 1
DEFAULT_CHECKPOINT_INTERVAL = 64
DEFAULT_RETAINED_CHECKPOINTS = 16
BACKEND_FAULT_PHASES = frozenset(
    {"BEFORE_COMMIT", "AFTER_EVENT_STAGE", "BEFORE_LIVE_SWAP"}
)


def _commit_request_digest(
    *,
    expected_version: int,
    event_batch: Sequence[MemoryEvent],
    next_image: MemoryImage,
    idempotency_key: str,
) -> str:
    return "memory-commit-request:" + digest_object(
        {
            "expected_version": expected_version,
            "event_batch": tuple(event.payload() for event in event_batch),
            "next_image": next_image.payload(),
            "idempotency_key": idempotency_key,
        }
    )


def _validate_commit(
    *,
    current: MemoryImage,
    expected_version: int,
    event_batch: Sequence[MemoryEvent],
    next_image: MemoryImage,
    idempotency_key: str,
) -> tuple[str, ...]:
    failures: list[str] = []
    if current.version != expected_version:
        failures.append("MEMORY_BACKEND_VERSION_CONFLICT")
    if not idempotency_key:
        failures.append("MEMORY_BACKEND_IDEMPOTENCY_KEY_REQUIRED")
    if not event_batch:
        failures.append("MEMORY_BACKEND_EVENT_BATCH_REQUIRED")
    replayed = current
    try:
        for event in event_batch:
            if event.idempotency_key != idempotency_key:
                failures.append("MEMORY_BACKEND_EVENT_IDEMPOTENCY_MISMATCH")
                break
            replayed = apply_memory_event(replayed, event)
    except (RuntimeError, ValueError) as error:
        failures.append(str(error))
    if (
        replayed.version != next_image.version
        or replayed.digest() != next_image.digest()
    ):
        failures.append("MEMORY_BACKEND_NEXT_IMAGE_MISMATCH")
    return tuple(sorted(set(failures)))


class MemoryBackend(Protocol):
    checkpoint_interval: int
    retained_checkpoints: int

    def initialize(self, image: MemoryImage) -> None: ...

    def replace_bootstrap(self, image: MemoryImage) -> None: ...

    def current_image(self) -> MemoryImage: ...

    def commit(
        self,
        *,
        expected_version: int,
        event_batch: tuple[MemoryEvent, ...],
        next_image: MemoryImage,
        idempotency_key: str,
    ) -> CommitReceipt: ...

    def events(self) -> tuple[MemoryEvent, ...]: ...

    def rebuild(self, target_version: int | None = None) -> MemoryImage: ...

    def checkpoint_count(self) -> int: ...


@dataclass(slots=True)
class InMemoryBackend:
    checkpoint_interval: int = DEFAULT_CHECKPOINT_INTERVAL
    retained_checkpoints: int = DEFAULT_RETAINED_CHECKPOINTS
    fault_phase: str | None = None
    _bootstrap: MemoryImage = field(
        default_factory=MemoryImage.empty,
        init=False,
        repr=False,
    )
    _current: MemoryImage = field(
        default_factory=MemoryImage.empty,
        init=False,
        repr=False,
    )
    _events: list[MemoryEvent] = field(
        default_factory=list,
        init=False,
        repr=False,
    )
    _receipts: dict[str, tuple[str, CommitReceipt]] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _checkpoints: list[tuple[int, int, MemoryImage]] = field(
        default_factory=list,
        init=False,
        repr=False,
    )
    _lock: threading.RLock = field(
        default_factory=threading.RLock,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        if self.checkpoint_interval <= 0:
            raise ValueError("MEMORY_CHECKPOINT_INTERVAL_INVALID")
        if self.retained_checkpoints <= 0:
            raise ValueError("MEMORY_CHECKPOINT_RETENTION_INVALID")
        if (
            self.fault_phase is not None
            and self.fault_phase not in BACKEND_FAULT_PHASES
        ):
            raise ValueError("MEMORY_BACKEND_FAULT_PHASE_INVALID")

    def initialize(self, image: MemoryImage) -> None:
        failures = image.validate()
        if failures:
            raise ValueError(";".join(failures))
        with self._lock:
            if self._events or self._current.version != 0:
                raise RuntimeError("MEMORY_BACKEND_ALREADY_INITIALIZED")
            self._bootstrap = image
            self._current = image

    def replace_bootstrap(self, image: MemoryImage) -> None:
        failures = image.validate()
        if failures:
            raise ValueError(";".join(failures))
        if image.version != 0:
            raise ValueError("MEMORY_BOOTSTRAP_VERSION_MUST_BE_ZERO")
        with self._lock:
            if self._events or self._current.version != 0:
                raise RuntimeError("MEMORY_BOOTSTRAP_REPLACEMENT_FORBIDDEN")
            self._bootstrap = image
            self._current = image

    def current_image(self) -> MemoryImage:
        with self._lock:
            return self._current

    def set_fault(self, phase: str | None) -> None:
        if phase is not None and phase not in BACKEND_FAULT_PHASES:
            raise ValueError("MEMORY_BACKEND_FAULT_PHASE_INVALID")
        self.fault_phase = phase

    def commit(
        self,
        *,
        expected_version: int,
        event_batch: tuple[MemoryEvent, ...],
        next_image: MemoryImage,
        idempotency_key: str,
    ) -> CommitReceipt:
        request_digest = _commit_request_digest(
            expected_version=expected_version,
            event_batch=event_batch,
            next_image=next_image,
            idempotency_key=idempotency_key,
        )
        with self._lock:
            prior = self._receipts.get(idempotency_key)
            if prior is not None:
                if prior[0] != request_digest:
                    raise RuntimeError(
                        "MEMORY_BACKEND_IDEMPOTENCY_PAYLOAD_CONFLICT"
                    )
                return replace(prior[1], idempotent_replay=True)
            failures = _validate_commit(
                current=self._current,
                expected_version=expected_version,
                event_batch=event_batch,
                next_image=next_image,
                idempotency_key=idempotency_key,
            )
            if failures:
                if "MEMORY_BACKEND_VERSION_CONFLICT" in failures:
                    raise RuntimeError("MEMORY_BACKEND_VERSION_CONFLICT")
                raise ValueError(";".join(failures))
            if self.fault_phase == "BEFORE_COMMIT":
                raise RuntimeError("MEMORY_BACKEND_INJECTED_FAILURE:BEFORE_COMMIT")
            staged_events = [*self._events, *event_batch]
            if self.fault_phase == "AFTER_EVENT_STAGE":
                raise RuntimeError(
                    "MEMORY_BACKEND_INJECTED_FAILURE:AFTER_EVENT_STAGE"
                )
            checkpoint_written = bool(
                len(staged_events) % self.checkpoint_interval == 0
            )
            staged_checkpoints = list(self._checkpoints)
            if checkpoint_written:
                staged_checkpoints.append(
                    (
                        next_image.version,
                        len(staged_events),
                        next_image,
                    )
                )
                staged_checkpoints = staged_checkpoints[
                    -self.retained_checkpoints :
                ]
            receipt = CommitReceipt(
                idempotency_key=idempotency_key,
                old_version=expected_version,
                new_version=next_image.version,
                event_digests=tuple(
                    event.digest() for event in event_batch
                ),
                image_digest=next_image.digest(),
                state_digest=next_image.state_digest(),
                checkpoint_written=checkpoint_written,
            )
            if self.fault_phase == "BEFORE_LIVE_SWAP":
                raise RuntimeError(
                    "MEMORY_BACKEND_INJECTED_FAILURE:BEFORE_LIVE_SWAP"
                )
            self._events = staged_events
            self._checkpoints = staged_checkpoints
            self._current = next_image
            self._receipts[idempotency_key] = (
                request_digest,
                receipt,
            )
            return receipt

    def events(self) -> tuple[MemoryEvent, ...]:
        with self._lock:
            return tuple(self._events)

    def rebuild(self, target_version: int | None = None) -> MemoryImage:
        with self._lock:
            selected = self._current.version if target_version is None else target_version
            if selected < 0 or selected > self._current.version:
                raise KeyError(selected)
            checkpoint = next(
                (
                    item
                    for item in reversed(self._checkpoints)
                    if item[0] <= selected
                ),
                None,
            )
            if checkpoint is None:
                image = self._bootstrap
                start_sequence = 0
            else:
                image = checkpoint[2]
                start_sequence = checkpoint[1]
            for event in self._events[start_sequence:]:
                if event.new_version > selected:
                    break
                image = apply_memory_event(image, event)
            if image.version != selected:
                raise RuntimeError("MEMORY_BACKEND_REBUILD_VERSION_MISSING")
            return image

    def checkpoint_count(self) -> int:
        with self._lock:
            return len(self._checkpoints)

    def full_copy_snapshot_count(self) -> int:
        return self.checkpoint_count()


@dataclass(slots=True)
class SQLiteEventBackend:
    path: Path
    checkpoint_interval: int = DEFAULT_CHECKPOINT_INTERVAL
    retained_checkpoints: int = DEFAULT_RETAINED_CHECKPOINTS
    fault_phase: str | None = None
    migration_applied: bool = field(default=False, init=False)
    _connection: sqlite3.Connection = field(init=False, repr=False)
    _lock: threading.RLock = field(
        default_factory=threading.RLock,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        self.path = Path(self.path)
        if self.checkpoint_interval <= 0:
            raise ValueError("MEMORY_CHECKPOINT_INTERVAL_INVALID")
        if self.retained_checkpoints <= 0:
            raise ValueError("MEMORY_CHECKPOINT_RETENTION_INVALID")
        if (
            self.fault_phase is not None
            and self.fault_phase not in BACKEND_FAULT_PHASES
        ):
            raise ValueError("MEMORY_BACKEND_FAULT_PHASE_INVALID")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = sqlite3.connect(
            str(self.path),
            isolation_level=None,
            check_same_thread=False,
        )
        self._connection.execute("PRAGMA foreign_keys=ON")
        self._connection.execute("PRAGMA journal_mode=WAL")
        self._connection.execute("PRAGMA synchronous=FULL")
        self._ensure_schema()

    @staticmethod
    def create_legacy_v0(path: Path, image: MemoryImage) -> None:
        selected = Path(path)
        selected.parent.mkdir(parents=True, exist_ok=True)
        connection = sqlite3.connect(str(selected))
        try:
            connection.execute(
                "CREATE TABLE legacy_state ("
                "singleton INTEGER PRIMARY KEY CHECK(singleton=1), "
                "image_json TEXT NOT NULL)"
            )
            connection.execute(
                "INSERT INTO legacy_state(singleton,image_json) VALUES(1,?)",
                (canonical_json(image.payload()),),
            )
            connection.execute("PRAGMA user_version=0")
            connection.commit()
        finally:
            connection.close()

    def _create_schema(self) -> None:
        self._connection.executescript(
            """
            CREATE TABLE IF NOT EXISTS metadata (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS events (
                sequence INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id TEXT NOT NULL UNIQUE,
                old_version INTEGER NOT NULL,
                new_version INTEGER NOT NULL,
                event_digest TEXT NOT NULL UNIQUE,
                event_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS receipts (
                idempotency_key TEXT PRIMARY KEY,
                request_digest TEXT NOT NULL,
                receipt_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS state (
                singleton INTEGER PRIMARY KEY CHECK(singleton=1),
                version INTEGER NOT NULL,
                image_digest TEXT NOT NULL,
                image_json TEXT NOT NULL
            );
            CREATE TABLE IF NOT EXISTS checkpoints (
                version INTEGER PRIMARY KEY,
                event_sequence INTEGER NOT NULL,
                image_digest TEXT NOT NULL,
                image_json TEXT NOT NULL
            );
            """
        )

    def _ensure_schema(self) -> None:
        legacy = self._connection.execute(
            "SELECT name FROM sqlite_master "
            "WHERE type='table' AND name='legacy_state'"
        ).fetchone()
        self._connection.execute("BEGIN IMMEDIATE")
        try:
            legacy_image: MemoryImage | None = None
            if legacy is not None:
                row = self._connection.execute(
                    "SELECT image_json FROM legacy_state WHERE singleton=1"
                ).fetchone()
                if row is None:
                    raise RuntimeError("MEMORY_LEGACY_STATE_MISSING")
                payload = json.loads(str(row[0]))
                if not isinstance(payload, dict):
                    raise TypeError("MEMORY_LEGACY_IMAGE_INVALID")
                legacy_image = MemoryImage.from_payload(payload)
            self._create_schema()
            row = self._connection.execute(
                "SELECT version FROM state WHERE singleton=1"
            ).fetchone()
            if row is None:
                image = legacy_image or MemoryImage.empty()
                self._connection.execute(
                    "INSERT INTO state"
                    "(singleton,version,image_digest,image_json)"
                    " VALUES(1,?,?,?)",
                    (
                        image.version,
                        image.digest(),
                        canonical_json(image.payload()),
                    ),
                )
                self._connection.execute(
                    "INSERT OR REPLACE INTO metadata(key,value)"
                    " VALUES('bootstrap_image',?)",
                    (canonical_json(image.payload()),),
                )
            if legacy is not None:
                self._connection.execute("DROP TABLE legacy_state")
                self.migration_applied = True
            self._connection.execute(
                f"PRAGMA user_version={MEMORY_BACKEND_SCHEMA_VERSION}"
            )
            self._connection.commit()
        except Exception:
            self._connection.rollback()
            raise

    @property
    def schema_version(self) -> int:
        row = self._connection.execute("PRAGMA user_version").fetchone()
        return int(row[0]) if row else 0

    @property
    def journal_mode(self) -> str:
        row = self._connection.execute("PRAGMA journal_mode").fetchone()
        return str(row[0]).upper() if row else ""

    def initialize(self, image: MemoryImage) -> None:
        self.replace_bootstrap(image)

    def replace_bootstrap(self, image: MemoryImage) -> None:
        failures = image.validate()
        if failures:
            raise ValueError(";".join(failures))
        if image.version != 0:
            raise ValueError("MEMORY_BOOTSTRAP_VERSION_MUST_BE_ZERO")
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                event_count = int(
                    self._connection.execute(
                        "SELECT COUNT(*) FROM events"
                    ).fetchone()[0]
                )
                current_version = int(
                    self._connection.execute(
                        "SELECT version FROM state WHERE singleton=1"
                    ).fetchone()[0]
                )
                if event_count or current_version != 0:
                    raise RuntimeError(
                        "MEMORY_BOOTSTRAP_REPLACEMENT_FORBIDDEN"
                    )
                image_json = canonical_json(image.payload())
                self._connection.execute(
                    "UPDATE state SET version=?, image_digest=?, image_json=? "
                    "WHERE singleton=1",
                    (0, image.digest(), image_json),
                )
                self._connection.execute(
                    "INSERT OR REPLACE INTO metadata(key,value)"
                    " VALUES('bootstrap_image',?)",
                    (image_json,),
                )
                self._connection.commit()
            except Exception:
                self._connection.rollback()
                raise

    def current_image(self) -> MemoryImage:
        with self._lock:
            row = self._connection.execute(
                "SELECT image_json FROM state WHERE singleton=1"
            ).fetchone()
            if row is None:
                raise RuntimeError("MEMORY_BACKEND_STATE_MISSING")
            payload = json.loads(str(row[0]))
            if not isinstance(payload, dict):
                raise TypeError("MEMORY_BACKEND_STATE_INVALID")
            return MemoryImage.from_payload(payload)

    def set_fault(self, phase: str | None) -> None:
        if phase is not None and phase not in BACKEND_FAULT_PHASES:
            raise ValueError("MEMORY_BACKEND_FAULT_PHASE_INVALID")
        self.fault_phase = phase

    def commit(
        self,
        *,
        expected_version: int,
        event_batch: tuple[MemoryEvent, ...],
        next_image: MemoryImage,
        idempotency_key: str,
    ) -> CommitReceipt:
        request_digest = _commit_request_digest(
            expected_version=expected_version,
            event_batch=event_batch,
            next_image=next_image,
            idempotency_key=idempotency_key,
        )
        with self._lock:
            self._connection.execute("BEGIN IMMEDIATE")
            try:
                prior = self._connection.execute(
                    "SELECT request_digest,receipt_json FROM receipts "
                    "WHERE idempotency_key=?",
                    (idempotency_key,),
                ).fetchone()
                if prior is not None:
                    if str(prior[0]) != request_digest:
                        raise RuntimeError(
                            "MEMORY_BACKEND_IDEMPOTENCY_PAYLOAD_CONFLICT"
                        )
                    payload = json.loads(str(prior[1]))
                    if not isinstance(payload, dict):
                        raise TypeError("MEMORY_BACKEND_RECEIPT_INVALID")
                    self._connection.commit()
                    return replace(
                        CommitReceipt.from_payload(payload),
                        idempotent_replay=True,
                    )
                current = self.current_image()
                failures = _validate_commit(
                    current=current,
                    expected_version=expected_version,
                    event_batch=event_batch,
                    next_image=next_image,
                    idempotency_key=idempotency_key,
                )
                if failures:
                    if "MEMORY_BACKEND_VERSION_CONFLICT" in failures:
                        raise RuntimeError("MEMORY_BACKEND_VERSION_CONFLICT")
                    raise ValueError(";".join(failures))
                if self.fault_phase == "BEFORE_COMMIT":
                    raise RuntimeError(
                        "MEMORY_BACKEND_INJECTED_FAILURE:BEFORE_COMMIT"
                    )
                for event in event_batch:
                    self._connection.execute(
                        "INSERT INTO events"
                        "(event_id,old_version,new_version,event_digest,event_json)"
                        " VALUES(?,?,?,?,?)",
                        (
                            event.event_id,
                            event.old_version,
                            event.new_version,
                            event.digest(),
                            canonical_json(event.payload()),
                        ),
                    )
                if self.fault_phase == "AFTER_EVENT_STAGE":
                    raise RuntimeError(
                        "MEMORY_BACKEND_INJECTED_FAILURE:AFTER_EVENT_STAGE"
                    )
                event_count = int(
                    self._connection.execute(
                        "SELECT COUNT(*) FROM events"
                    ).fetchone()[0]
                )
                checkpoint_written = bool(
                    event_count % self.checkpoint_interval == 0
                )
                image_json = canonical_json(next_image.payload())
                self._connection.execute(
                    "UPDATE state SET version=?,image_digest=?,image_json=? "
                    "WHERE singleton=1",
                    (
                        next_image.version,
                        next_image.digest(),
                        image_json,
                    ),
                )
                if checkpoint_written:
                    self._connection.execute(
                        "INSERT OR REPLACE INTO checkpoints"
                        "(version,event_sequence,image_digest,image_json)"
                        " VALUES(?,?,?,?)",
                        (
                            next_image.version,
                            event_count,
                            next_image.digest(),
                            image_json,
                        ),
                    )
                    rows = self._connection.execute(
                        "SELECT version FROM checkpoints "
                        "ORDER BY version DESC"
                    ).fetchall()
                    for row in rows[self.retained_checkpoints :]:
                        self._connection.execute(
                            "DELETE FROM checkpoints WHERE version=?",
                            (int(row[0]),),
                        )
                receipt = CommitReceipt(
                    idempotency_key=idempotency_key,
                    old_version=expected_version,
                    new_version=next_image.version,
                    event_digests=tuple(
                        event.digest() for event in event_batch
                    ),
                    image_digest=next_image.digest(),
                    state_digest=next_image.state_digest(),
                    checkpoint_written=checkpoint_written,
                )
                self._connection.execute(
                    "INSERT INTO receipts"
                    "(idempotency_key,request_digest,receipt_json)"
                    " VALUES(?,?,?)",
                    (
                        idempotency_key,
                        request_digest,
                        canonical_json(receipt.payload()),
                    ),
                )
                if self.fault_phase == "BEFORE_LIVE_SWAP":
                    raise RuntimeError(
                        "MEMORY_BACKEND_INJECTED_FAILURE:BEFORE_LIVE_SWAP"
                    )
                self._connection.commit()
                return receipt
            except Exception:
                self._connection.rollback()
                raise

    def events(self) -> tuple[MemoryEvent, ...]:
        with self._lock:
            rows = self._connection.execute(
                "SELECT event_json FROM events ORDER BY sequence"
            ).fetchall()
            output: list[MemoryEvent] = []
            for row in rows:
                payload = json.loads(str(row[0]))
                if not isinstance(payload, dict):
                    raise TypeError("MEMORY_BACKEND_EVENT_INVALID")
                output.append(MemoryEvent.from_payload(payload))
            return tuple(output)

    def rebuild(self, target_version: int | None = None) -> MemoryImage:
        with self._lock:
            current = self.current_image()
            selected = current.version if target_version is None else target_version
            if selected < 0 or selected > current.version:
                raise KeyError(selected)
            checkpoint_row = self._connection.execute(
                "SELECT event_sequence,image_json FROM checkpoints "
                "WHERE version<=? ORDER BY version DESC LIMIT 1",
                (selected,),
            ).fetchone()
            if checkpoint_row is None:
                bootstrap_row = self._connection.execute(
                    "SELECT value FROM metadata WHERE key='bootstrap_image'"
                ).fetchone()
                if bootstrap_row is None:
                    raise RuntimeError("MEMORY_BACKEND_BOOTSTRAP_MISSING")
                payload = json.loads(str(bootstrap_row[0]))
                start_sequence = 0
            else:
                payload = json.loads(str(checkpoint_row[1]))
                start_sequence = int(checkpoint_row[0])
            if not isinstance(payload, dict):
                raise TypeError("MEMORY_BACKEND_REBUILD_IMAGE_INVALID")
            image = MemoryImage.from_payload(payload)
            rows = self._connection.execute(
                "SELECT event_json FROM events WHERE sequence>? "
                "ORDER BY sequence",
                (start_sequence,),
            ).fetchall()
            for row in rows:
                event_payload = json.loads(str(row[0]))
                if not isinstance(event_payload, dict):
                    raise TypeError("MEMORY_BACKEND_EVENT_INVALID")
                event = MemoryEvent.from_payload(event_payload)
                if event.new_version > selected:
                    break
                image = apply_memory_event(image, event)
            if image.version != selected:
                raise RuntimeError("MEMORY_BACKEND_REBUILD_VERSION_MISSING")
            return image

    def checkpoint_count(self) -> int:
        with self._lock:
            return int(
                self._connection.execute(
                    "SELECT COUNT(*) FROM checkpoints"
                ).fetchone()[0]
            )

    def full_copy_snapshot_count(self) -> int:
        return self.checkpoint_count()

    def content_digest(self) -> str:
        return "sqlite-memory-ledger:" + digest_object(
            {
                "schema_version": self.schema_version,
                "events": tuple(event.payload() for event in self.events()),
                "current": self.current_image().payload(),
            }
        )

    def close(self) -> None:
        with self._lock:
            self._connection.close()


__all__ = [
    "BACKEND_FAULT_PHASES",
    "DEFAULT_CHECKPOINT_INTERVAL",
    "DEFAULT_RETAINED_CHECKPOINTS",
    "MEMORY_BACKEND_SCHEMA_VERSION",
    "InMemoryBackend",
    "MemoryBackend",
    "SQLiteEventBackend",
]
