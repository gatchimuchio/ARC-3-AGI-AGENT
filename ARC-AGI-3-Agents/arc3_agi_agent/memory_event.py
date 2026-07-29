"""Canonical append-only events and deltas for semantic memory."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .memory_image import MemoryImage, RecordBlob
from .schema import digest_object

MEMORY_EVENT_SCHEMA_VERSION = 1


def _payload_integer(
    payload: Mapping[str, object],
    name: str,
    *,
    default: int | None = None,
) -> int:
    if name in payload:
        value = payload[name]
    elif default is not None:
        value = default
    else:
        raise KeyError(name)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("MEMORY_EVENT_INTEGER_INVALID:" + name)
    return value


def _payload_text_sequence(
    payload: Mapping[str, object],
    name: str,
) -> tuple[str, ...]:
    value = payload.get(name, ())
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError("MEMORY_EVENT_TEXT_SEQUENCE_INVALID:" + name)
    if any(not isinstance(item, str) for item in value):
        raise TypeError("MEMORY_EVENT_TEXT_SEQUENCE_INVALID:" + name)
    return tuple(value)


def _sorted_unique_text(values: Sequence[str]) -> tuple[str, ...]:
    output = tuple(sorted(set(values)))
    if any(not isinstance(item, str) or not item for item in output):
        raise ValueError("MEMORY_EVENT_TEXT_SEQUENCE_INVALID")
    return output


@dataclass(frozen=True, slots=True)
class MemoryDelta:
    active_upserts: tuple[RecordBlob, ...] = ()
    active_deletes: tuple[str, ...] = ()
    archive_upserts: tuple[RecordBlob, ...] = ()
    archive_deletes: tuple[str, ...] = ()

    @classmethod
    def between(
        cls,
        before: MemoryImage,
        after: MemoryImage,
    ) -> MemoryDelta:
        before_active = before.active_map()
        after_active = after.active_map()
        before_archive = before.archive_map()
        after_archive = after.archive_map()
        return cls(
            active_upserts=tuple(
                sorted(
                    (key, payload)
                    for key, payload in after_active.items()
                    if before_active.get(key) != payload
                )
            ),
            active_deletes=tuple(
                sorted(set(before_active).difference(after_active))
            ),
            archive_upserts=tuple(
                sorted(
                    (key, payload)
                    for key, payload in after_archive.items()
                    if before_archive.get(key) != payload
                )
            ),
            archive_deletes=tuple(
                sorted(set(before_archive).difference(after_archive))
            ),
        )

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        for name in ("active_upserts", "archive_upserts"):
            values = getattr(self, name)
            if values != tuple(sorted(values)):
                failures.append("MEMORY_DELTA_UPSERT_ORDER_INVALID:" + name)
            keys = tuple(key for key, _ in values)
            if keys != tuple(sorted(set(keys))):
                failures.append("MEMORY_DELTA_UPSERT_KEY_INVALID:" + name)
        for name in ("active_deletes", "archive_deletes"):
            values = getattr(self, name)
            try:
                normalized = _sorted_unique_text(values)
            except ValueError:
                failures.append("MEMORY_DELTA_DELETE_INVALID:" + name)
                continue
            if normalized != values:
                failures.append("MEMORY_DELTA_DELETE_INVALID:" + name)
        if set(self.active_deletes).intersection(
            key for key, _ in self.active_upserts
        ):
            failures.append("MEMORY_DELTA_ACTIVE_CONFLICT")
        if set(self.archive_deletes).intersection(
            key for key, _ in self.archive_upserts
        ):
            failures.append("MEMORY_DELTA_ARCHIVE_CONFLICT")
        return tuple(sorted(set(failures)))

    def apply(
        self,
        image: MemoryImage,
        *,
        next_version: int,
        last_event_digest: str,
    ) -> MemoryImage:
        failures = self.validate()
        if failures:
            raise ValueError(";".join(failures))
        active = image.active_map()
        archive = image.archive_map()
        for key in self.active_deletes:
            active.pop(key, None)
        active.update(self.active_upserts)
        for key in self.archive_deletes:
            archive.pop(key, None)
        archive.update(self.archive_upserts)
        return MemoryImage.build(
            version=next_version,
            active=active,
            archive=archive,
            sealed=image.sealed_items,
            last_event_digest=last_event_digest,
        )

    def payload(self) -> dict[str, object]:
        return {
            "active_upserts": self.active_upserts,
            "active_deletes": self.active_deletes,
            "archive_upserts": self.archive_upserts,
            "archive_deletes": self.archive_deletes,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> MemoryDelta:
        def blobs(name: str) -> tuple[RecordBlob, ...]:
            value = payload.get(name, ())
            if (
                isinstance(value, (str, bytes))
                or not isinstance(value, Sequence)
            ):
                raise TypeError("MEMORY_DELTA_UPSERT_INVALID")
            output: list[RecordBlob] = []
            for item in value:
                if (
                    isinstance(item, (str, bytes))
                    or not isinstance(item, Sequence)
                    or len(item) != 2
                ):
                    raise TypeError("MEMORY_DELTA_UPSERT_INVALID")
                output.append((str(item[0]), str(item[1])))
            return tuple(output)

        def names(name: str) -> tuple[str, ...]:
            value = payload.get(name, ())
            if (
                isinstance(value, (str, bytes))
                or not isinstance(value, Sequence)
            ):
                raise TypeError("MEMORY_DELTA_DELETE_INVALID")
            return tuple(str(item) for item in value)

        delta = cls(
            active_upserts=blobs("active_upserts"),
            active_deletes=names("active_deletes"),
            archive_upserts=blobs("archive_upserts"),
            archive_deletes=names("archive_deletes"),
        )
        failures = delta.validate()
        if failures:
            raise ValueError(";".join(failures))
        return delta


@dataclass(frozen=True, slots=True)
class MemoryEvent:
    event_id: str
    old_version: int
    new_version: int
    idempotency_key: str
    proposal_digests: tuple[str, ...]
    delta: MemoryDelta
    previous_event_digest: str
    next_state_digest: str
    audit_payloads: tuple[str, ...]
    event_type: str = "MEMORY_BATCH_COMMIT"
    schema_version: int = MEMORY_EVENT_SCHEMA_VERSION

    def validate(self) -> tuple[str, ...]:
        failures = list(self.delta.validate())
        if not all(
            isinstance(value, str) and value
            for value in (
                self.event_id,
                self.idempotency_key,
                self.next_state_digest,
                self.event_type,
            )
        ):
            failures.append("MEMORY_EVENT_TEXT_INVALID")
        if self.old_version < 0 or self.new_version != self.old_version + 1:
            failures.append("MEMORY_EVENT_VERSION_INVALID")
        if (
            self.proposal_digests
            != tuple(sorted(set(self.proposal_digests)))
            or not self.proposal_digests
        ):
            failures.append("MEMORY_EVENT_PROPOSALS_INVALID")
        if not self.audit_payloads:
            failures.append("MEMORY_EVENT_AUDIT_PAYLOAD_MISSING")
        if self.schema_version != MEMORY_EVENT_SCHEMA_VERSION:
            failures.append("MEMORY_EVENT_SCHEMA_UNSUPPORTED")
        if self.old_version > 0 and not self.previous_event_digest:
            failures.append("MEMORY_EVENT_CHAIN_PREDECESSOR_MISSING")
        return tuple(sorted(set(failures)))

    def digest(self) -> str:
        failures = self.validate()
        if failures:
            raise ValueError(";".join(failures))
        return "memory-event:" + digest_object(self)

    def payload(self) -> dict[str, object]:
        return {
            "event_id": self.event_id,
            "old_version": self.old_version,
            "new_version": self.new_version,
            "idempotency_key": self.idempotency_key,
            "proposal_digests": self.proposal_digests,
            "delta": self.delta.payload(),
            "previous_event_digest": self.previous_event_digest,
            "next_state_digest": self.next_state_digest,
            "audit_payloads": self.audit_payloads,
            "event_type": self.event_type,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> MemoryEvent:
        delta_payload = payload["delta"]
        if not isinstance(delta_payload, Mapping):
            raise TypeError("MEMORY_EVENT_DELTA_INVALID")
        event = cls(
            event_id=str(payload["event_id"]),
            old_version=_payload_integer(payload, "old_version"),
            new_version=_payload_integer(payload, "new_version"),
            idempotency_key=str(payload["idempotency_key"]),
            proposal_digests=_payload_text_sequence(
                payload,
                "proposal_digests",
            ),
            delta=MemoryDelta.from_payload(delta_payload),
            previous_event_digest=str(
                payload.get("previous_event_digest", "")
            ),
            next_state_digest=str(payload["next_state_digest"]),
            audit_payloads=_payload_text_sequence(
                payload,
                "audit_payloads",
            ),
            event_type=str(
                payload.get("event_type", "MEMORY_BATCH_COMMIT")
            ),
            schema_version=_payload_integer(
                payload,
                "schema_version",
                default=MEMORY_EVENT_SCHEMA_VERSION,
            ),
        )
        failures = event.validate()
        if failures:
            raise ValueError(";".join(failures))
        return event


@dataclass(frozen=True, slots=True)
class CommitReceipt:
    idempotency_key: str
    old_version: int
    new_version: int
    event_digests: tuple[str, ...]
    image_digest: str
    state_digest: str
    checkpoint_written: bool
    idempotent_replay: bool = False

    def payload(self) -> dict[str, object]:
        return {
            "idempotency_key": self.idempotency_key,
            "old_version": self.old_version,
            "new_version": self.new_version,
            "event_digests": self.event_digests,
            "image_digest": self.image_digest,
            "state_digest": self.state_digest,
            "checkpoint_written": self.checkpoint_written,
            "idempotent_replay": self.idempotent_replay,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> CommitReceipt:
        return cls(
            idempotency_key=str(payload["idempotency_key"]),
            old_version=_payload_integer(payload, "old_version"),
            new_version=_payload_integer(payload, "new_version"),
            event_digests=_payload_text_sequence(
                payload,
                "event_digests",
            ),
            image_digest=str(payload["image_digest"]),
            state_digest=str(payload["state_digest"]),
            checkpoint_written=bool(payload["checkpoint_written"]),
            idempotent_replay=bool(
                payload.get("idempotent_replay", False)
            ),
        )


def apply_memory_event(image: MemoryImage, event: MemoryEvent) -> MemoryImage:
    if event.old_version != image.version:
        raise RuntimeError("MEMORY_EVENT_REPLAY_VERSION_CONFLICT")
    if event.previous_event_digest != image.last_event_digest:
        raise RuntimeError("MEMORY_EVENT_REPLAY_CHAIN_CONFLICT")
    event_digest = event.digest()
    rebuilt = event.delta.apply(
        image,
        next_version=event.new_version,
        last_event_digest=event_digest,
    )
    if rebuilt.state_digest() != event.next_state_digest:
        raise RuntimeError("MEMORY_EVENT_REPLAY_STATE_DIGEST_MISMATCH")
    return rebuilt


__all__ = [
    "MEMORY_EVENT_SCHEMA_VERSION",
    "CommitReceipt",
    "MemoryDelta",
    "MemoryEvent",
    "apply_memory_event",
]
