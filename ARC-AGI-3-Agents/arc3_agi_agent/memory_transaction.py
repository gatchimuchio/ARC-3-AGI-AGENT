"""Immutable prepare result for all-or-nothing semantic-memory commits."""

from __future__ import annotations

from dataclasses import dataclass, field

from .memory_event import MemoryEvent
from .memory_image import MemoryImage
from .schema import digest_object

MEMORY_TRANSACTION_VERSION = "arc3-memory-transaction-v1"


@dataclass(frozen=True, slots=True)
class StagedMemoryTransition:
    expected_version: int
    next_version: int
    idempotency_key: str
    proposal_digests: tuple[str, ...]
    target_ids: tuple[str, ...]
    event_batch: tuple[MemoryEvent, ...]
    next_image: MemoryImage
    provenance_payloads: tuple[str, ...]
    mandatory: bool
    prepared_from_digest: str
    _proposals: tuple[object, ...] = field(
        repr=False,
        compare=False,
        metadata={"serialize": False},
    )
    _authorizations: tuple[object, ...] = field(
        repr=False,
        compare=False,
        metadata={"serialize": False},
    )

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if self.next_version != self.expected_version + 1:
            failures.append("MEMORY_STAGED_VERSION_INVALID")
        if not self.idempotency_key:
            failures.append("MEMORY_STAGED_IDEMPOTENCY_KEY_MISSING")
        if (
            not self.proposal_digests
            or self.proposal_digests
            != tuple(sorted(set(self.proposal_digests)))
        ):
            failures.append("MEMORY_STAGED_PROPOSALS_INVALID")
        if len(self.target_ids) != len(self._proposals):
            failures.append("MEMORY_STAGED_TARGET_COUNT_INVALID")
        if len(self._proposals) != len(self._authorizations):
            failures.append("MEMORY_STAGED_AUTHORIZATION_COUNT_INVALID")
        if len(self.provenance_payloads) != len(self._proposals):
            failures.append("MEMORY_STAGED_PROVENANCE_COUNT_INVALID")
        if len(self.event_batch) != 1:
            failures.append("MEMORY_STAGED_AGGREGATE_EVENT_REQUIRED")
        if self.next_image.version != self.next_version:
            failures.append("MEMORY_STAGED_IMAGE_VERSION_INVALID")
        if not self.prepared_from_digest:
            failures.append("MEMORY_STAGED_BASE_DIGEST_MISSING")
        return tuple(sorted(set(failures)))

    def digest(self) -> str:
        failures = self.validate()
        if failures:
            raise ValueError(";".join(failures))
        return "staged-memory-transition:" + digest_object(self)


__all__ = [
    "MEMORY_TRANSACTION_VERSION",
    "StagedMemoryTransition",
]
