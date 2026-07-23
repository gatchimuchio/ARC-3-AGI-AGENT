"""Typed P6 view of P3 identity-free memory lifecycle fixtures."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .memory import MUTATING_MEMORY_OPERATIONS


def _mapping(value: object, name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{name} must be an object")
    return value


def _strings(value: object, name: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(
        value, (str, bytes, bytearray)
    ):
        raise TypeError(f"{name} must be an array")
    output = tuple(str(item).strip() for item in value)
    if any(not item for item in output):
        raise ValueError(f"{name} contains an empty value")
    return output


@dataclass(frozen=True, slots=True)
class MemoryLifecycleFixture:
    record_id: str
    lifecycle: str
    operation_candidates: tuple[str, ...]
    evidence: tuple[str, ...]
    version_policy: str
    archive_policy: str
    runtime_identity_free: bool

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not self.record_id:
            failures.append("MEMORY_FIXTURE_ID_MISSING")
        if not self.lifecycle:
            failures.append("MEMORY_FIXTURE_LIFECYCLE_MISSING")
        if (
            not self.operation_candidates
            or not set(self.operation_candidates) <= MUTATING_MEMORY_OPERATIONS
        ):
            failures.append("MEMORY_FIXTURE_OPERATION_INVALID")
        if not self.evidence:
            failures.append("MEMORY_FIXTURE_EVIDENCE_MISSING")
        if self.version_policy != "compare-and-swap":
            failures.append("MEMORY_FIXTURE_VERSION_POLICY_INVALID")
        if self.archive_policy != "non-authoritative-unless-reactivated":
            failures.append("MEMORY_FIXTURE_ARCHIVE_POLICY_INVALID")
        if self.runtime_identity_free is not True:
            failures.append("MEMORY_FIXTURE_IDENTITY_FLAG_INVALID")
        return tuple(sorted(set(failures)))


def memory_lifecycle_from_record(
    record: Mapping[str, Any],
) -> MemoryLifecycleFixture:
    if record.get("category") != "memory_lifecycles":
        raise ValueError("P6 fixture category must be memory_lifecycles")
    payload = _mapping(record.get("payload"), "payload")
    fixture = MemoryLifecycleFixture(
        record_id=str(record.get("record_id", "")),
        lifecycle=str(payload.get("lifecycle", "")),
        operation_candidates=_strings(
            payload.get("operation_candidates"),
            "payload.operation_candidates",
        ),
        evidence=_strings(payload.get("evidence"), "payload.evidence"),
        version_policy=str(payload.get("version_policy", "")),
        archive_policy=str(payload.get("archive_policy", "")),
        runtime_identity_free=record.get("runtime_identity_free") is True,
    )
    failures = fixture.validate()
    if failures:
        raise ValueError(";".join(failures))
    return fixture


def load_memory_lifecycle_fixtures(
    path: Path,
) -> tuple[MemoryLifecycleFixture, ...]:
    fixtures: list[MemoryLifecycleFixture] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        value = json.loads(line)
        if not isinstance(value, Mapping):
            raise TypeError("P6 fixture record must be an object")
        fixtures.append(memory_lifecycle_from_record(value))
    if not fixtures:
        raise ValueError("P6 fixture set is empty")
    return tuple(fixtures)


__all__ = [
    "MemoryLifecycleFixture",
    "load_memory_lifecycle_fixtures",
    "memory_lifecycle_from_record",
]
