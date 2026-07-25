"""Passive versioned memory with explicit storage and authorized runtime seams."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace

from .protocol import (
    MEMORY_LIFECYCLES,
    AuthorityViolation,
    HDSDecision,
    MemoryDirective,
)
from .schema import canonical_json, digest_object, forbidden_runtime_paths

MUTATING_MEMORY_OPERATIONS = frozenset(
    {
        "ADD",
        "REVISE",
        "MERGE",
        "SPLIT",
        "REPLACE",
        "INVALIDATE",
        "DELETE",
        "REINDEX",
        "ROLLBACK",
        "ARCHIVE",
    }
)
READ_MEMORY_OPERATIONS = frozenset(
    {"READ", "QUERY", "VERSION", "SNAPSHOT", "PROVENANCE"}
)
ALL_MEMORY_OPERATIONS = MUTATING_MEMORY_OPERATIONS | READ_MEMORY_OPERATIONS
MEMORY_SUBJECT_REMOVAL_WITNESS = (
    "MEMORY_SUBJECT_REMOVED_NO_G3_VERSIONED_EXPERIENCE_RETENTION"
)
_FORBIDDEN_VALUE_PATTERNS = (
    re.compile(
        r"(?i)(?:^|[^a-z0-9])[a-z]{1,3}\d{2}-[0-9a-f]{8}"
        r"(?:$|[^a-z0-9])"
    ),
    re.compile(r"(?i)(?:^|[^a-z0-9])(?:game|task|level)[-_ ]?(?:id|\d+)"),
    re.compile(r"(?i)(?:/mnt/|[a-z]:\\|environment_files/|\.json\b|\.py\b)"),
)


class MemoryVersionConflict(RuntimeError):
    """Raised when compare-and-swap expected version is stale."""


class MemoryOperationError(ValueError):
    """Raised when an explicit operation violates its storage preconditions."""


@dataclass(frozen=True, slots=True)
class MemoryEntry:
    target: str
    operation: str
    lifecycle: str
    evidence_signature: str
    payload_json: str
    version: int
    provenance: tuple[str, ...] = ()
    valid: bool = True
    archived: bool = False
    index_terms: tuple[str, ...] = ()
    created_version: int = 0
    supersedes_version: int | None = None

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
    archive_entries: tuple[MemoryEntry, ...] = ()
    _digest_value: str = field(
        init=False,
        repr=False,
        compare=False,
        metadata={"serialize": False},
    )

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "_digest_value",
            digest_object(
                {
                    "version": self.version,
                    "entries": self.entries,
                    "archive_entries": self.archive_entries,
                }
            ),
        )

    @property
    def digest(self) -> str:
        return self._digest_value


@dataclass(frozen=True, slots=True)
class MemoryMutationResult:
    target: str
    operation: str
    version: int
    snapshot_digest: str
    affected_targets: tuple[str, ...] = ()
    archive_count: int = 0
    rollback_from_version: int | None = None
    rollback_to_version: int | None = None


@dataclass(frozen=True, slots=True)
class MemoryQuery:
    target_prefix: str = ""
    lifecycle: str | None = None
    terms: tuple[str, ...] = ()
    include_invalid: bool = False
    include_archive: bool = False
    limit: int = 32

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not isinstance(self.target_prefix, str):
            failures.append("MEMORY_QUERY_TARGET_PREFIX_INVALID")
        if self.lifecycle is not None and self.lifecycle not in MEMORY_LIFECYCLES:
            failures.append("MEMORY_QUERY_LIFECYCLE_INVALID")
        if not isinstance(self.terms, tuple) or any(
            not isinstance(term, str) or not term.strip() for term in self.terms
        ):
            failures.append("MEMORY_QUERY_TERMS_INVALID")
        if not isinstance(self.include_invalid, bool):
            failures.append("MEMORY_QUERY_INVALID_FLAG_INVALID")
        if not isinstance(self.include_archive, bool):
            failures.append("MEMORY_QUERY_ARCHIVE_FLAG_INVALID")
        if (
            isinstance(self.limit, bool)
            or not isinstance(self.limit, int)
            or self.limit < 1
        ):
            failures.append("MEMORY_QUERY_LIMIT_INVALID")
        return tuple(sorted(set(failures)))


@dataclass(frozen=True, slots=True)
class MemoryQueryResult:
    version: int
    query_digest: str
    entries: tuple[MemoryEntry, ...]

    @property
    def digest(self) -> str:
        return digest_object(self)


@dataclass(frozen=True, slots=True)
class MemoryProvenanceEvent:
    version: int
    operation: str
    targets: tuple[str, ...]
    evidence_signature: str
    provenance: tuple[str, ...]
    before_digest: str
    after_digest: str
    rollback_from_version: int | None = None
    rollback_to_version: int | None = None


@dataclass(frozen=True, slots=True)
class MemoryOperation:
    operation: str
    target: str = ""
    expected_version: int | None = None
    lifecycle: str = "PROPOSED"
    evidence_signature: str = ""
    payload_items: tuple[tuple[str, object], ...] = ()
    source_targets: tuple[str, ...] = ()
    destination_targets: tuple[str, ...] = ()
    rollback_version: int | None = None
    query: MemoryQuery | None = None
    provenance: tuple[str, ...] = ()

    def payload(self) -> dict[str, object]:
        return dict(self.payload_items)

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if self.operation not in ALL_MEMORY_OPERATIONS:
            failures.append("MEMORY_OPERATION_INVALID")
        if self.operation in MUTATING_MEMORY_OPERATIONS:
            if (
                isinstance(self.expected_version, bool)
                or not isinstance(self.expected_version, int)
                or self.expected_version < 0
            ):
                failures.append("MEMORY_EXPECTED_VERSION_INVALID")
            if not self.evidence_signature:
                failures.append("MEMORY_EVIDENCE_MISSING")
            if not self.provenance:
                failures.append("MEMORY_PROVENANCE_MISSING")
        if self.operation not in {"VERSION", "SNAPSHOT", "PROVENANCE", "QUERY"}:
            if not self.target:
                failures.append("MEMORY_TARGET_MISSING")
        if self.lifecycle not in MEMORY_LIFECYCLES:
            failures.append("MEMORY_LIFECYCLE_INVALID")
        if len(self.payload()) != len(self.payload_items):
            failures.append("MEMORY_PAYLOAD_DUPLICATE_KEYS")
        canonicalizable = True
        try:
            canonical_json(self.payload())
        except (TypeError, ValueError, RecursionError):
            canonicalizable = False
            failures.append("MEMORY_PAYLOAD_NOT_CANONICALIZABLE")
        if not isinstance(self.source_targets, tuple) or any(
            not isinstance(item, str) or not item for item in self.source_targets
        ):
            failures.append("MEMORY_SOURCE_TARGET_INVALID")
        if len(set(self.source_targets)) != len(self.source_targets):
            failures.append("MEMORY_SOURCE_TARGET_DUPLICATE")
        if not isinstance(self.destination_targets, tuple) or any(
            not isinstance(item, str) or not item
            for item in self.destination_targets
        ):
            failures.append("MEMORY_DESTINATION_TARGET_INVALID")
        if len(set(self.destination_targets)) != len(self.destination_targets):
            failures.append("MEMORY_DESTINATION_TARGET_DUPLICATE")
        if self.operation == "MERGE" and len(self.source_targets) < 2:
            failures.append("MEMORY_MERGE_SOURCE_COUNT_INVALID")
        if self.operation == "SPLIT" and len(self.destination_targets) < 2:
            failures.append("MEMORY_SPLIT_DESTINATION_COUNT_INVALID")
        if self.operation == "ROLLBACK" and (
            isinstance(self.rollback_version, bool)
            or not isinstance(self.rollback_version, int)
            or self.rollback_version < 0
        ):
            failures.append("MEMORY_ROLLBACK_VERSION_INVALID")
        if self.operation == "SNAPSHOT" and self.expected_version is not None and (
            isinstance(self.expected_version, bool)
            or not isinstance(self.expected_version, int)
            or self.expected_version < 0
        ):
            failures.append("MEMORY_SNAPSHOT_VERSION_INVALID")
        if (
            self.operation in {"READ", "QUERY", "VERSION", "PROVENANCE"}
            and self.expected_version is not None
        ):
            failures.append("MEMORY_READ_EXPECTED_VERSION_UNEXPECTED")
        if self.operation == "QUERY":
            if self.query is None:
                failures.append("MEMORY_QUERY_MISSING")
            else:
                failures.extend(self.query.validate())
        elif self.query is not None:
            failures.append("MEMORY_QUERY_UNEXPECTED")
        identity_value = {
            "target": self.target,
            "payload": self.payload(),
            "source_targets": self.source_targets,
            "destination_targets": self.destination_targets,
            "provenance": self.provenance,
        }
        if canonicalizable:
            failures.extend(
                f"MEMORY_RUNTIME_IDENTITY_FORBIDDEN:{path}"
                for path in forbidden_runtime_paths(
                    identity_value
                )
            )
        failures.extend(
            f"MEMORY_RUNTIME_IDENTITY_FORBIDDEN:{path}"
            for path in _forbidden_value_paths(identity_value)
        )
        return tuple(sorted(set(failures)))


def _index_terms(value: object) -> tuple[str, ...]:
    terms: set[str] = set()
    stack = [value]
    visited: set[int] = set()
    while stack:
        item = stack.pop()
        if isinstance(item, Mapping):
            identity = id(item)
            if identity in visited:
                continue
            visited.add(identity)
            for key, child in item.items():
                terms.update(
                    part
                    for part in re.split(r"[^a-z0-9]+", str(key).casefold())
                    if part
                )
                stack.append(child)
        elif isinstance(item, Sequence) and not isinstance(
            item, (str, bytes, bytearray)
        ):
            identity = id(item)
            if identity in visited:
                continue
            visited.add(identity)
            stack.extend(item)
        elif isinstance(item, str):
            terms.update(
                part
                for part in re.split(r"[^a-z0-9]+", item.casefold())
                if part
            )
    return tuple(sorted(terms))


def _forbidden_value_paths(value: object, path: str = "$") -> tuple[str, ...]:
    failures: list[str] = []
    stack: list[tuple[str, object]] = [(path, value)]
    visited: set[int] = set()
    while stack:
        current_path, item = stack.pop()
        if isinstance(item, Mapping):
            identity = id(item)
            if identity in visited:
                continue
            visited.add(identity)
            stack.extend(
                (f"{current_path}.{key}", child)
                for key, child in item.items()
            )
        elif isinstance(item, Sequence) and not isinstance(
            item, (str, bytes, bytearray)
        ):
            identity = id(item)
            if identity in visited:
                continue
            visited.add(identity)
            stack.extend(
                (f"{current_path}[{index}]", child)
                for index, child in enumerate(item)
            )
        elif isinstance(item, str) and any(
            pattern.search(item) for pattern in _FORBIDDEN_VALUE_PATTERNS
        ):
            failures.append(current_path)
    return tuple(sorted(set(failures)))


@dataclass(slots=True)
class PassiveMemory:
    """Storage subject that mutates only when an explicit caller invokes an API."""

    max_entries: int = 32
    max_history_snapshots: int | None = None
    _entries: dict[str, MemoryEntry] = field(default_factory=dict, init=False)
    _order: list[str] = field(default_factory=list, init=False)
    _archive: dict[str, MemoryEntry] = field(default_factory=dict, init=False)
    _archive_order: list[str] = field(default_factory=list, init=False)
    _version: int = field(default=0, init=False)
    _history: dict[int, MemorySnapshot] = field(default_factory=dict, init=False)
    _rollback_snapshot_version: int = field(default=0, init=False)
    _provenance: list[MemoryProvenanceEvent] = field(
        default_factory=list,
        init=False,
    )

    def __post_init__(self) -> None:
        if self.max_entries < 1:
            raise ValueError("max_entries must be positive")
        if self.max_history_snapshots is not None and (
            isinstance(self.max_history_snapshots, bool)
            or not isinstance(self.max_history_snapshots, int)
            or self.max_history_snapshots < 3
        ):
            raise ValueError("max_history_snapshots must be at least 3")
        self._history[0] = self.view()

    @property
    def version(self) -> int:
        return self._version

    @property
    def retained_snapshot_versions(self) -> tuple[int, ...]:
        """Expose retained rollback material without exposing mutable storage."""

        return tuple(sorted(self._history))

    def retain_rollback_snapshot(self, version: int) -> None:
        """Retain one explicit rollback anchor under a bounded storage policy.

        Retention changes neither active memory, version, digest, nor
        provenance.  It only selects which already-authorized historical
        snapshot survives physical compaction.
        """

        if (
            isinstance(version, bool)
            or not isinstance(version, int)
            or version < 0
        ):
            raise MemoryOperationError(
                "MEMORY_ROLLBACK_RETENTION_VERSION_INVALID"
            )
        if version not in self._history:
            raise MemoryOperationError(
                f"MEMORY_ROLLBACK_RETENTION_VERSION_NOT_FOUND:{version}"
            )
        self._rollback_snapshot_version = version
        self._prune_history()

    def _prune_history(self) -> None:
        limit = self.max_history_snapshots
        if limit is None:
            return
        protected = {
            0,
            self._version,
            self._rollback_snapshot_version,
        }
        for version in tuple(sorted(self._history)):
            if len(self._history) <= limit:
                break
            if version not in protected:
                del self._history[version]

    def view(self) -> MemorySnapshot:
        entries = tuple(
            self._entries[target]
            for target in self._order
            if target in self._entries
        )
        archive_entries = tuple(
            self._archive[target]
            for target in self._archive_order
            if target in self._archive
        )
        return MemorySnapshot(
            version=self._version,
            entries=entries,
            archive_entries=archive_entries,
        )

    def snapshot(self, version: int | None = None) -> MemorySnapshot:
        requested = self._version if version is None else version
        snapshot = self._history.get(requested)
        if snapshot is None:
            raise MemoryOperationError(
                f"MEMORY_SNAPSHOT_VERSION_NOT_FOUND:{requested}"
            )
        return snapshot

    def provenance(self) -> tuple[MemoryProvenanceEvent, ...]:
        return tuple(self._provenance)

    def read(
        self,
        target: str,
        *,
        include_archive: bool = False,
    ) -> MemoryEntry | None:
        entry = self._entries.get(target)
        if entry is None and include_archive:
            entry = self._archive.get(target)
        return entry

    def query(self, query: MemoryQuery) -> MemoryQueryResult:
        failures = query.validate()
        if failures:
            raise MemoryOperationError(";".join(failures))
        candidates = list(self.view().entries)
        if query.include_archive:
            candidates.extend(self.view().archive_entries)
        normalized_terms = {
            term.casefold().strip() for term in query.terms
        }
        selected = tuple(
            entry
            for entry in candidates
            if (
                (not query.target_prefix or entry.target.startswith(query.target_prefix))
                and (query.lifecycle is None or entry.lifecycle == query.lifecycle)
                and (query.include_invalid or entry.valid)
                and normalized_terms <= set(entry.index_terms)
            )
        )[: query.limit]
        return MemoryQueryResult(
            version=self._version,
            query_digest="memory-query:"
            + digest_object(
                {
                    "version": self._version,
                    "query": query,
                }
            )[:24],
            entries=selected,
        )

    def _require_expected_version(self, operation: MemoryOperation) -> None:
        if operation.expected_version != self._version:
            raise MemoryVersionConflict(
                "MEMORY_VERSION_CONFLICT:"
                f"expected={operation.expected_version}:actual={self._version}"
            )

    def _entry(
        self,
        *,
        target: str,
        operation: str,
        lifecycle: str,
        evidence_signature: str,
        payload: Mapping[str, object],
        provenance: tuple[str, ...],
        valid: bool = True,
        archived: bool = False,
        created_version: int,
        supersedes_version: int | None,
    ) -> MemoryEntry:
        return MemoryEntry(
            target=target,
            operation=operation,
            lifecycle=lifecycle,
            evidence_signature=evidence_signature,
            payload_json=canonical_json(dict(payload)),
            version=self._version + 1,
            provenance=provenance,
            valid=valid,
            archived=archived,
            index_terms=_index_terms(payload),
            created_version=created_version,
            supersedes_version=supersedes_version,
        )

    def _archive_entry(
        self,
        entry: MemoryEntry,
        *,
        evidence_signature: str,
        provenance: tuple[str, ...],
    ) -> MemoryEntry:
        return replace(
            entry,
            operation="ARCHIVE",
            lifecycle="ARCHIVED",
            evidence_signature=evidence_signature,
            version=self._version + 1,
            provenance=tuple(sorted({*entry.provenance, *provenance})),
            archived=True,
            supersedes_version=entry.version,
        )

    def _record_commit(
        self,
        operation: MemoryOperation,
        *,
        before: MemorySnapshot,
        targets: tuple[str, ...],
        rollback_from_version: int | None = None,
        rollback_to_version: int | None = None,
    ) -> MemoryMutationResult:
        self._version += 1
        while len(self._order) > self.max_entries:
            oldest = self._order.pop(0)
            entry = self._entries.pop(oldest)
            archived = replace(
                entry,
                operation="ARCHIVE",
                lifecycle="ARCHIVED",
                version=self._version,
                archived=True,
                supersedes_version=entry.version,
            )
            self._archive[oldest] = archived
            if oldest in self._archive_order:
                self._archive_order.remove(oldest)
            self._archive_order.append(oldest)
        after = self.view()
        self._history[self._version] = after
        self._prune_history()
        self._provenance.append(
            MemoryProvenanceEvent(
                version=self._version,
                operation=operation.operation,
                targets=targets,
                evidence_signature=operation.evidence_signature,
                provenance=operation.provenance,
                before_digest=before.digest,
                after_digest=after.digest,
                rollback_from_version=rollback_from_version,
                rollback_to_version=rollback_to_version,
            )
        )
        return MemoryMutationResult(
            target=operation.target,
            operation=operation.operation,
            version=self._version,
            snapshot_digest=after.digest,
            affected_targets=targets,
            archive_count=len(after.archive_entries),
            rollback_from_version=rollback_from_version,
            rollback_to_version=rollback_to_version,
        )

    def _apply_mutation(self, operation: MemoryOperation) -> MemoryMutationResult:
        self._require_expected_version(operation)
        before = self.view()
        payload = operation.payload()
        target = operation.target
        targets: tuple[str, ...] = (target,)

        if operation.operation == "ADD":
            if target in self._entries:
                raise MemoryOperationError(f"MEMORY_TARGET_ALREADY_EXISTS:{target}")
            self._archive.pop(target, None)
            if target in self._archive_order:
                self._archive_order.remove(target)
            self._entries[target] = self._entry(
                target=target,
                operation="ADD",
                lifecycle=operation.lifecycle,
                evidence_signature=operation.evidence_signature,
                payload=payload,
                provenance=operation.provenance,
                created_version=self._version + 1,
                supersedes_version=None,
            )
            self._order.append(target)
        elif operation.operation == "REVISE":
            current = self._entries.get(target)
            if current is None:
                raise MemoryOperationError(f"MEMORY_TARGET_NOT_ACTIVE:{target}")
            revised = current.payload
            revised.update(payload)
            self._entries[target] = self._entry(
                target=target,
                operation="REVISE",
                lifecycle=operation.lifecycle,
                evidence_signature=operation.evidence_signature,
                payload=revised,
                provenance=tuple(
                    sorted({*current.provenance, *operation.provenance})
                ),
                valid=current.valid,
                created_version=current.created_version,
                supersedes_version=current.version,
            )
        elif operation.operation == "REPLACE":
            current = self._entries.get(target)
            if current is None:
                raise MemoryOperationError(f"MEMORY_TARGET_NOT_ACTIVE:{target}")
            self._entries[target] = self._entry(
                target=target,
                operation="REPLACE",
                lifecycle=operation.lifecycle,
                evidence_signature=operation.evidence_signature,
                payload=payload,
                provenance=operation.provenance,
                created_version=current.created_version,
                supersedes_version=current.version,
            )
        elif operation.operation == "INVALIDATE":
            current = self._entries.get(target)
            if current is None:
                raise MemoryOperationError(f"MEMORY_TARGET_NOT_ACTIVE:{target}")
            invalidated_payload = current.payload
            invalidated_payload.update(payload)
            self._entries[target] = self._entry(
                target=target,
                operation="INVALIDATE",
                lifecycle="REJECTED",
                evidence_signature=operation.evidence_signature,
                payload=invalidated_payload,
                provenance=tuple(
                    sorted({*current.provenance, *operation.provenance})
                ),
                valid=False,
                created_version=current.created_version,
                supersedes_version=current.version,
            )
        elif operation.operation == "DELETE":
            found = self._entries.pop(target, None)
            if target in self._order:
                self._order.remove(target)
            archived = self._archive.pop(target, None)
            if target in self._archive_order:
                self._archive_order.remove(target)
            if found is None and archived is None:
                raise MemoryOperationError(f"MEMORY_TARGET_NOT_FOUND:{target}")
        elif operation.operation == "ARCHIVE":
            current = self._entries.pop(target, None)
            if current is None:
                raise MemoryOperationError(f"MEMORY_TARGET_NOT_ACTIVE:{target}")
            self._order.remove(target)
            self._archive[target] = self._archive_entry(
                current,
                evidence_signature=operation.evidence_signature,
                provenance=operation.provenance,
            )
            if target in self._archive_order:
                self._archive_order.remove(target)
            self._archive_order.append(target)
        elif operation.operation == "REINDEX":
            current = self._entries.get(target)
            if current is None:
                raise MemoryOperationError(f"MEMORY_TARGET_NOT_ACTIVE:{target}")
            self._entries[target] = replace(
                current,
                operation="REINDEX",
                evidence_signature=operation.evidence_signature,
                version=self._version + 1,
                provenance=tuple(
                    sorted({*current.provenance, *operation.provenance})
                ),
                index_terms=_index_terms(current.payload),
                supersedes_version=current.version,
            )
        elif operation.operation == "MERGE":
            missing = [
                source
                for source in operation.source_targets
                if source not in self._entries
            ]
            if missing:
                raise MemoryOperationError(
                    "MEMORY_MERGE_SOURCE_NOT_ACTIVE:" + ",".join(missing)
                )
            if (
                target in self._archive
                or target in self._entries
                and target not in operation.source_targets
            ):
                raise MemoryOperationError(
                    f"MEMORY_MERGE_TARGET_ALREADY_EXISTS:{target}"
                )
            merged: dict[str, object] = {}
            source_entries = [
                self._entries[source] for source in operation.source_targets
            ]
            for entry in source_entries:
                merged.update(entry.payload)
            merged.update(payload)
            for source in operation.source_targets:
                self._entries.pop(source)
                self._order.remove(source)
            self._entries[target] = self._entry(
                target=target,
                operation="MERGE",
                lifecycle=operation.lifecycle,
                evidence_signature=operation.evidence_signature,
                payload=merged,
                provenance=tuple(
                    sorted(
                        {
                            *operation.provenance,
                            *(
                                item
                                for entry in source_entries
                                for item in entry.provenance
                            ),
                        }
                    )
                ),
                created_version=self._version + 1,
                supersedes_version=max(
                    entry.version for entry in source_entries
                ),
            )
            self._order.append(target)
            targets = (*operation.source_targets, target)
        elif operation.operation == "SPLIT":
            current = self._entries.get(target)
            if current is None:
                raise MemoryOperationError(f"MEMORY_TARGET_NOT_ACTIVE:{target}")
            conflicts = [
                destination
                for destination in operation.destination_targets
                if destination in self._entries or destination in self._archive
            ]
            if conflicts:
                raise MemoryOperationError(
                    "MEMORY_SPLIT_DESTINATION_EXISTS:" + ",".join(conflicts)
                )
            parts = payload.get("parts")
            if not isinstance(parts, Mapping) or set(parts) != set(
                operation.destination_targets
            ):
                raise MemoryOperationError("MEMORY_SPLIT_PARTS_MISMATCH")
            destination_payloads: dict[str, Mapping[str, object]] = {}
            for destination in operation.destination_targets:
                part = parts[destination]
                if not isinstance(part, Mapping):
                    raise MemoryOperationError(
                        f"MEMORY_SPLIT_PART_INVALID:{destination}"
                    )
                destination_payloads[destination] = part
            self._entries.pop(target)
            self._order.remove(target)
            for destination in operation.destination_targets:
                self._entries[destination] = self._entry(
                    target=destination,
                    operation="SPLIT",
                    lifecycle=operation.lifecycle,
                    evidence_signature=operation.evidence_signature,
                    payload=destination_payloads[destination],
                    provenance=tuple(
                        sorted({*current.provenance, *operation.provenance})
                    ),
                    created_version=self._version + 1,
                    supersedes_version=current.version,
                )
                self._order.append(destination)
            targets = (target, *operation.destination_targets)
        elif operation.operation == "ROLLBACK":
            assert operation.rollback_version is not None
            historical = self._history.get(operation.rollback_version)
            if historical is None:
                raise MemoryOperationError(
                    "MEMORY_ROLLBACK_VERSION_NOT_FOUND:"
                    f"{operation.rollback_version}"
                )
            if operation.rollback_version >= self._version:
                raise MemoryOperationError(
                    "MEMORY_ROLLBACK_VERSION_NOT_HISTORICAL"
                )
            rollback_from = self._version
            self._entries = {
                entry.target: entry for entry in historical.entries
            }
            self._order = [entry.target for entry in historical.entries]
            self._archive = {
                entry.target: entry for entry in historical.archive_entries
            }
            self._archive_order = [
                entry.target for entry in historical.archive_entries
            ]
            return self._record_commit(
                operation,
                before=before,
                targets=tuple(
                    sorted({*self._entries, *self._archive})
                ),
                rollback_from_version=rollback_from,
                rollback_to_version=operation.rollback_version,
            )
        else:
            raise MemoryOperationError(
                f"MEMORY_MUTATION_NOT_IMPLEMENTED:{operation.operation}"
            )

        return self._record_commit(
            operation,
            before=before,
            targets=targets,
        )

    def execute_storage(
        self,
        operation: MemoryOperation,
    ) -> (
        MemoryMutationResult
        | MemoryEntry
        | MemoryQueryResult
        | MemorySnapshot
        | tuple[MemoryProvenanceEvent, ...]
        | int
        | None
    ):
        """Execute an explicitly requested low-level storage operation."""

        failures = operation.validate()
        if failures:
            raise MemoryOperationError(";".join(failures))
        if operation.operation in MUTATING_MEMORY_OPERATIONS:
            return self._apply_mutation(operation)
        if operation.operation == "READ":
            return self.read(operation.target)
        if operation.operation == "QUERY":
            assert operation.query is not None
            return self.query(operation.query)
        if operation.operation == "VERSION":
            return self.version
        if operation.operation == "SNAPSHOT":
            return self.snapshot(operation.expected_version)
        if operation.operation == "PROVENANCE":
            return self.provenance()
        raise MemoryOperationError(
            f"MEMORY_OPERATION_NOT_IMPLEMENTED:{operation.operation}"
        )

    def apply_authorized(
        self,
        directive: MemoryDirective,
        decision: HDSDecision,
        payload: Mapping[str, object],
        *,
        executor: str,
    ) -> MemoryMutationResult:
        """Runtime adapter: require an owner-bound HDS single-use grant."""

        failures = list(directive.validate(decision))
        if executor != "pure-llm":
            failures.append("MEMORY_EXECUTOR_NOT_PURE_LLM")
        payload_digest = digest_object(dict(payload))
        if directive.payload_digest != payload_digest:
            failures.append("MEMORY_PAYLOAD_MISMATCH")
        forbidden = forbidden_runtime_paths(payload)
        failures.extend(
            f"MEMORY_RUNTIME_IDENTITY_FORBIDDEN:{path}" for path in forbidden
        )
        failures.extend(
            f"MEMORY_RUNTIME_IDENTITY_FORBIDDEN:{path}"
            for path in _forbidden_value_paths(payload)
        )
        if directive.expected_version != self._version:
            failures.append("MEMORY_VERSION_CONFLICT")
        if failures:
            raise AuthorityViolation(";".join(sorted(set(failures))))
        directive.consume(decision)
        operation = MemoryOperation(
            operation=directive.operation,
            target=directive.target,
            expected_version=directive.expected_version,
            lifecycle=directive.lifecycle,
            evidence_signature=directive.evidence_signature,
            payload_items=tuple(sorted(dict(payload).items())),
            provenance=(
                f"hds-command:{directive.command_id}",
                f"hds-decision:{directive.decision_id}",
                directive.evidence_signature,
            ),
        )
        result = self.execute_storage(operation)
        if not isinstance(result, MemoryMutationResult):
            raise AuthorityViolation("MEMORY_AUTHORIZED_MUTATION_RESULT_INVALID")
        return result


@dataclass(frozen=True, slots=True)
class StandaloneMemoryHarness:
    memory_subject: PassiveMemory | None

    def view(self) -> MemorySnapshot:
        if self.memory_subject is None:
            raise RuntimeError(MEMORY_SUBJECT_REMOVAL_WITNESS)
        return self.memory_subject.view()


__all__ = [
    "ALL_MEMORY_OPERATIONS",
    "MEMORY_SUBJECT_REMOVAL_WITNESS",
    "MUTATING_MEMORY_OPERATIONS",
    "MemoryEntry",
    "MemoryMutationResult",
    "MemoryOperation",
    "MemoryOperationError",
    "MemoryProvenanceEvent",
    "MemoryQuery",
    "MemoryQueryResult",
    "MemorySnapshot",
    "MemoryVersionConflict",
    "PassiveMemory",
    "READ_MEMORY_OPERATIONS",
    "StandaloneMemoryHarness",
]
