"""Immutable canonical state image for the event-sourced semantic memory."""

from __future__ import annotations

import json
from dataclasses import dataclass
from functools import lru_cache
from typing import Mapping, Sequence

from .schema import digest_object

MEMORY_IMAGE_SCHEMA_VERSION = 1
RecordBlob = tuple[str, str]


@lru_cache(maxsize=65_536)
def _require_record_payload(payload: str) -> None:
    parsed = json.loads(payload)
    if not isinstance(parsed, dict):
        raise ValueError("MEMORY_IMAGE_RECORD_PAYLOAD_INVALID")


def _normalize_items(
    values: Mapping[str, str] | Sequence[RecordBlob],
) -> tuple[RecordBlob, ...]:
    items = tuple(values.items()) if isinstance(values, Mapping) else tuple(values)
    normalized = tuple(sorted(items))
    keys = tuple(key for key, _ in normalized)
    if keys != tuple(sorted(set(keys))):
        raise ValueError("MEMORY_IMAGE_RECORD_KEY_INVALID")
    for key, payload in normalized:
        if not isinstance(key, str) or not key:
            raise ValueError("MEMORY_IMAGE_RECORD_KEY_INVALID")
        if not isinstance(payload, str) or not payload:
            raise ValueError("MEMORY_IMAGE_RECORD_PAYLOAD_INVALID")
        _require_record_payload(payload)
    return normalized


@dataclass(frozen=True, slots=True)
class MemoryImage:
    """A cacheable state projection; the event ledger remains authoritative."""

    version: int
    active_items: tuple[RecordBlob, ...] = ()
    archive_items: tuple[RecordBlob, ...] = ()
    sealed_items: tuple[RecordBlob, ...] = ()
    last_event_digest: str = ""
    schema_version: int = MEMORY_IMAGE_SCHEMA_VERSION

    @classmethod
    def empty(cls) -> MemoryImage:
        return cls(version=0)

    @classmethod
    def build(
        cls,
        *,
        version: int,
        active: Mapping[str, str] | Sequence[RecordBlob] = (),
        archive: Mapping[str, str] | Sequence[RecordBlob] = (),
        sealed: Mapping[str, str] | Sequence[RecordBlob] = (),
        last_event_digest: str = "",
        schema_version: int = MEMORY_IMAGE_SCHEMA_VERSION,
    ) -> MemoryImage:
        image = cls(
            version=version,
            active_items=_normalize_items(active),
            archive_items=_normalize_items(archive),
            sealed_items=_normalize_items(sealed),
            last_event_digest=last_event_digest,
            schema_version=schema_version,
        )
        failures = image.validate()
        if failures:
            raise ValueError(";".join(failures))
        return image

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if (
            isinstance(self.version, bool)
            or not isinstance(self.version, int)
            or self.version < 0
        ):
            failures.append("MEMORY_IMAGE_VERSION_INVALID")
        if self.schema_version != MEMORY_IMAGE_SCHEMA_VERSION:
            failures.append("MEMORY_IMAGE_SCHEMA_UNSUPPORTED")
        for name in ("active_items", "archive_items", "sealed_items"):
            try:
                normalized = _normalize_items(getattr(self, name))
            except (TypeError, ValueError, json.JSONDecodeError):
                failures.append("MEMORY_IMAGE_REGION_INVALID:" + name)
                continue
            if normalized != getattr(self, name):
                failures.append("MEMORY_IMAGE_REGION_NONCANONICAL:" + name)
        if self.version > 0 and not self.last_event_digest:
            failures.append("MEMORY_IMAGE_EVENT_TAIL_MISSING")
        return tuple(sorted(set(failures)))

    def active_map(self) -> dict[str, str]:
        return dict(self.active_items)

    def archive_map(self) -> dict[str, str]:
        return dict(self.archive_items)

    def sealed_map(self) -> dict[str, str]:
        return dict(self.sealed_items)

    def state_digest(self) -> str:
        return "memory-state:" + digest_object(
            {
                "version": self.version,
                "active_items": self.active_items,
                "archive_items": self.archive_items,
                "sealed_items": self.sealed_items,
                "schema_version": self.schema_version,
            }
        )

    def digest(self) -> str:
        return "memory-image:" + digest_object(self)

    def payload(self) -> dict[str, object]:
        return {
            "version": self.version,
            "active_items": self.active_items,
            "archive_items": self.archive_items,
            "sealed_items": self.sealed_items,
            "last_event_digest": self.last_event_digest,
            "schema_version": self.schema_version,
        }

    @classmethod
    def from_payload(cls, payload: Mapping[str, object]) -> MemoryImage:
        def integer(name: str, default: int | None = None) -> int:
            if name in payload:
                value = payload[name]
            elif default is not None:
                value = default
            else:
                raise KeyError(name)
            if isinstance(value, bool) or not isinstance(value, int):
                raise TypeError("MEMORY_IMAGE_INTEGER_INVALID:" + name)
            return value

        def region(name: str) -> tuple[RecordBlob, ...]:
            value = payload.get(name, ())
            if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
                raise TypeError("MEMORY_IMAGE_REGION_INVALID:" + name)
            output: list[RecordBlob] = []
            for item in value:
                if (
                    isinstance(item, (str, bytes))
                    or not isinstance(item, Sequence)
                    or len(item) != 2
                ):
                    raise TypeError("MEMORY_IMAGE_REGION_INVALID:" + name)
                output.append((str(item[0]), str(item[1])))
            return tuple(output)

        return cls.build(
            version=integer("version"),
            active=region("active_items"),
            archive=region("archive_items"),
            sealed=region("sealed_items"),
            last_event_digest=str(payload.get("last_event_digest", "")),
            schema_version=integer(
                "schema_version",
                MEMORY_IMAGE_SCHEMA_VERSION,
            ),
        )


__all__ = [
    "MEMORY_IMAGE_SCHEMA_VERSION",
    "MemoryImage",
    "RecordBlob",
]
