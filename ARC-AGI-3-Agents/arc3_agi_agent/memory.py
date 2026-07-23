"""Passive, bounded memory changed only by HDS-authorized execution."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Mapping

from .protocol import AuthorityViolation, HDSDecision, MemoryDirective
from .schema import canonical_json, digest_object, forbidden_runtime_paths


@dataclass(frozen=True, slots=True)
class MemoryEntry:
    target: str
    operation: str
    lifecycle: str
    evidence_signature: str
    payload_json: str
    version: int

    @property
    def payload(self) -> dict[str, object]:
        value = json.loads(self.payload_json)
        if not isinstance(value, dict):
            raise TypeError("memory payload must decode to an object")
        return value


@dataclass(frozen=True, slots=True)
class MemorySnapshot:
    version: int
    entries: tuple[MemoryEntry, ...]

    @property
    def digest(self) -> str:
        return digest_object(self)


@dataclass(frozen=True, slots=True)
class MemoryMutationResult:
    target: str
    operation: str
    version: int
    snapshot_digest: str


@dataclass(slots=True)
class PassiveMemory:
    """State holder with no autonomous compute, update, or emission path."""

    max_entries: int = 32
    _entries: dict[str, MemoryEntry] = field(default_factory=dict, init=False)
    _order: list[str] = field(default_factory=list, init=False)
    _version: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        if self.max_entries < 1:
            raise ValueError("max_entries must be positive")

    def view(self) -> MemorySnapshot:
        entries = tuple(
            self._entries[target]
            for target in self._order
            if target in self._entries
        )
        return MemorySnapshot(version=self._version, entries=entries)

    def apply_authorized(
        self,
        directive: MemoryDirective,
        decision: HDSDecision,
        payload: Mapping[str, object],
        *,
        executor: str,
    ) -> MemoryMutationResult:
        failures = list(directive.validate(decision))
        if executor != "pure-llm":
            failures.append("MEMORY_EXECUTOR_NOT_PURE_LLM")
        forbidden = forbidden_runtime_paths(payload)
        failures.extend(
            f"MEMORY_RUNTIME_IDENTITY_FORBIDDEN:{path}" for path in forbidden
        )
        if failures:
            raise AuthorityViolation(";".join(sorted(set(failures))))

        self._version += 1
        if directive.operation == "DELETE":
            self._entries.pop(directive.target, None)
            if directive.target in self._order:
                self._order.remove(directive.target)
        else:
            entry = MemoryEntry(
                target=directive.target,
                operation=directive.operation,
                lifecycle=directive.lifecycle,
                evidence_signature=directive.evidence_signature,
                payload_json=canonical_json(dict(payload)),
                version=self._version,
            )
            self._entries[directive.target] = entry
            if directive.target in self._order:
                self._order.remove(directive.target)
            self._order.append(directive.target)

        while len(self._order) > self.max_entries:
            oldest = self._order.pop(0)
            self._entries.pop(oldest, None)

        snapshot = self.view()
        return MemoryMutationResult(
            target=directive.target,
            operation=directive.operation,
            version=self._version,
            snapshot_digest=snapshot.digest,
        )


__all__ = [
    "MemoryEntry",
    "MemoryMutationResult",
    "MemorySnapshot",
    "PassiveMemory",
]
