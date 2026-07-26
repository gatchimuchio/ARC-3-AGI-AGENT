"""Versioned semantic memory for the GenericAGIRuntime.

The memory is passive: it can query or apply a single-use HDS authorization,
but it cannot create hypotheses, choose actions, or initiate mutations.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Mapping, Sequence

from .generic_types import SemanticMemoryCitation
from .schema import digest_object

GENERIC_MEMORY_VERSION = "arc3-generic-semantic-memory-v1"
SEMANTIC_MEMORY_KINDS = frozenset(
    {
        "PURPOSE_BOUNDARY",
        "HYPOTHESIS",
        "COUNTER_HYPOTHESIS",
        "CONTRADICTION",
        "FAILURE_SIGNATURE",
        "PROCEDURE_CAPABILITY",
        "WORLD_MODEL",
        "DECISION_RATIONALE",
        "OPEN_TERM",
        "ROLLBACK_POINTER",
        "ACTION_EFFECT",
    }
)
SEMANTIC_MEMORY_STATES = frozenset(
    {
        "PROPOSED",
        "PROBATION",
        "ACTIVE",
        "SUSPENDED",
        "SUPERSEDED",
        "REJECTED",
        "ARCHIVED",
        "SEALED",
    }
)
SEMANTIC_MEMORY_MUTATIONS = frozenset(
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
SEMANTIC_MEMORY_READS = frozenset(
    {"READ", "QUERY", "VERSION", "SNAPSHOT", "PROVENANCE"}
)


def _valid_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _sorted_unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted(set(values)))


@dataclass(frozen=True, slots=True)
class SemanticRecord:
    memory_id: str
    kind: str
    statement: str
    semantic_tokens: tuple[str, ...]
    relations: tuple[str, ...] = ()
    evidence: tuple[str, ...] = ()
    counter_evidence: tuple[str, ...] = ()
    scope: tuple[str, ...] = ()
    falsification_condition: str = ""
    authority: str = "HDS"
    state: str = "ACTIVE"
    created_version: int = 0
    updated_version: int = 0
    rollback_pointer: int = 0
    payload_items: tuple[tuple[str, object], ...] = ()

    def payload(self) -> dict[str, object]:
        return dict(self.payload_items)

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not all(
            _valid_text(value)
            for value in (self.memory_id, self.statement, self.authority)
        ):
            failures.append("SEMANTIC_MEMORY_TEXT_INVALID")
        if self.kind not in SEMANTIC_MEMORY_KINDS:
            failures.append("SEMANTIC_MEMORY_KIND_INVALID")
        if self.state not in SEMANTIC_MEMORY_STATES:
            failures.append("SEMANTIC_MEMORY_STATE_INVALID")
        for name, values in (
            ("TOKENS", self.semantic_tokens),
            ("RELATIONS", self.relations),
            ("EVIDENCE", self.evidence),
            ("COUNTER_EVIDENCE", self.counter_evidence),
            ("SCOPE", self.scope),
        ):
            if (
                any(not _valid_text(item) for item in values)
                or values != _sorted_unique(values)
            ):
                failures.append(f"SEMANTIC_MEMORY_{name}_INVALID")
        if not _valid_text(self.falsification_condition):
            failures.append("SEMANTIC_MEMORY_FALSIFIER_MISSING")
        if (
            any(
                isinstance(item, bool) or not isinstance(item, int)
                for item in (
                    self.created_version,
                    self.updated_version,
                    self.rollback_pointer,
                )
            )
            or min(
                self.created_version,
                self.updated_version,
                self.rollback_pointer,
            )
            < 0
        ):
            failures.append("SEMANTIC_MEMORY_VERSION_INVALID")
        payload_keys = tuple(key for key, _ in self.payload_items)
        if payload_keys != tuple(sorted(set(payload_keys))):
            failures.append("SEMANTIC_MEMORY_PAYLOAD_INVALID")
        return tuple(sorted(set(failures)))

    def citation(self) -> SemanticMemoryCitation:
        return SemanticMemoryCitation(
            memory_id=self.memory_id,
            version=self.updated_version,
            kind=self.kind,
            semantic_tokens=self.semantic_tokens,
            content_digest="semantic-record:" + digest_object(self),
        )


@dataclass(frozen=True, slots=True)
class MemoryMutationProposal:
    operation: str
    target_id: str
    record: SemanticRecord | None
    evidence: tuple[str, ...]
    counter_evidence: tuple[str, ...]
    scope: tuple[str, ...]
    falsification_condition: str
    reason: str
    source_ids: tuple[str, ...] = ()
    rollback_version: int | None = None

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if self.operation not in SEMANTIC_MEMORY_MUTATIONS:
            failures.append("SEMANTIC_MEMORY_OPERATION_INVALID")
        if not _valid_text(self.target_id) or not _valid_text(self.reason):
            failures.append("SEMANTIC_MEMORY_PROPOSAL_TEXT_INVALID")
        if (
            self.operation
            in {"ADD", "REVISE", "SPLIT", "REPLACE", "REINDEX"}
            and self.record is None
        ):
            failures.append("SEMANTIC_MEMORY_PROPOSAL_RECORD_REQUIRED")
        if self.record is not None:
            failures.extend(self.record.validate())
        if not self.evidence:
            failures.append("SEMANTIC_MEMORY_EVIDENCE_REQUIRED")
        if not self.scope:
            failures.append("SEMANTIC_MEMORY_SCOPE_REQUIRED")
        if not _valid_text(self.falsification_condition):
            failures.append("SEMANTIC_MEMORY_FALSIFIER_REQUIRED")
        if self.operation == "MERGE" and not self.source_ids:
            failures.append("SEMANTIC_MEMORY_MERGE_SOURCE_REQUIRED")
        if (
            self.operation == "ROLLBACK"
            and (
                isinstance(self.rollback_version, bool)
                or not isinstance(self.rollback_version, int)
                or self.rollback_version < 0
            )
        ):
            failures.append("SEMANTIC_MEMORY_ROLLBACK_VERSION_REQUIRED")
        return tuple(sorted(set(failures)))


@dataclass(frozen=True, slots=True)
class MemoryAuthorization:
    authorization_id: str
    decision_id: str
    expected_version: int
    proposal_digest: str
    _authority_token: object = field(
        repr=False,
        compare=False,
        metadata={"serialize": False},
    )


@dataclass(frozen=True, slots=True)
class MemoryView:
    version: int
    active: tuple[SemanticRecord, ...]
    working: tuple[SemanticRecord, ...]
    sealed: tuple[SemanticRecord, ...]
    digest_value: str

    @property
    def digest(self) -> str:
        return self.digest_value


@dataclass(frozen=True, slots=True)
class SemanticMemoryQuery:
    query_id: str
    semantic_tokens: tuple[str, ...]
    kinds: tuple[str, ...] = ()
    limit: int = 16
    include_archive: bool = False

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not _valid_text(self.query_id):
            failures.append("SEMANTIC_MEMORY_QUERY_ID_MISSING")
        if (
            any(not _valid_text(item) for item in self.semantic_tokens)
            or self.semantic_tokens != _sorted_unique(self.semantic_tokens)
        ):
            failures.append("SEMANTIC_MEMORY_QUERY_TOKENS_INVALID")
        if any(item not in SEMANTIC_MEMORY_KINDS for item in self.kinds):
            failures.append("SEMANTIC_MEMORY_QUERY_KIND_INVALID")
        if (
            isinstance(self.limit, bool)
            or not isinstance(self.limit, int)
            or not 1 <= self.limit <= 256
        ):
            failures.append("SEMANTIC_MEMORY_QUERY_LIMIT_INVALID")
        return tuple(sorted(set(failures)))


@dataclass(frozen=True, slots=True)
class SemanticMemoryQueryResult:
    query_id: str
    memory_version: int
    records: tuple[SemanticRecord, ...]
    selected_scores: tuple[tuple[str, int], ...]
    archive_included: bool
    digest_value: str

    @property
    def digest(self) -> str:
        return self.digest_value


@dataclass(frozen=True, slots=True)
class MemoryProvenance:
    event_id: str
    operation: str
    target_id: str
    old_version: int
    new_version: int
    old_digest: str
    new_digest: str
    evidence: tuple[str, ...]
    counter_evidence: tuple[str, ...]
    scope: tuple[str, ...]
    falsification_condition: str
    authority: str
    rollback_pointer: int
    decision_id: str
    authorization_id: str
    reason: str

    def digest(self) -> str:
        return "semantic-memory-event:" + digest_object(self)


@dataclass(frozen=True, slots=True)
class MemoryMutationReceipt:
    operation: str
    target_id: str
    old_version: int
    new_version: int
    event_digest: str
    active_digest: str
    archive_digest: str


@dataclass(slots=True)
class SemanticMemory:
    """Passive semantic memory with active/working/archive/sealed regions."""

    authority_token: object = field(repr=False)
    max_active: int = 2048
    max_archive: int = 8192
    _version: int = field(default=0, init=False)
    _active: dict[str, SemanticRecord] = field(default_factory=dict, init=False)
    _working: dict[str, SemanticRecord] = field(default_factory=dict, init=False)
    _archive: dict[str, SemanticRecord] = field(default_factory=dict, init=False)
    _sealed: dict[str, SemanticRecord] = field(default_factory=dict, init=False)
    _snapshots: dict[int, dict[str, SemanticRecord]] = field(
        default_factory=lambda: {0: {}},
        init=False,
    )
    _provenance: list[MemoryProvenance] = field(
        default_factory=list,
        init=False,
    )
    _consumed_authorizations: set[str] = field(
        default_factory=set,
        init=False,
    )

    @property
    def version(self) -> int:
        return self._version

    def _active_digest(self) -> str:
        return "semantic-active:" + digest_object(
            tuple(self._active[key] for key in sorted(self._active))
        )

    def _archive_digest(self) -> str:
        return "semantic-archive:" + digest_object(
            tuple(self._archive[key] for key in sorted(self._archive))
        )

    def seed_sealed(self, records: Sequence[SemanticRecord]) -> None:
        """Seed constitutional memory before runtime; it is immutable thereafter."""

        if self._version != 0 or self._active or self._provenance:
            raise RuntimeError("SEMANTIC_MEMORY_SEAL_AFTER_START_FORBIDDEN")
        for record in records:
            failures = record.validate()
            if failures:
                raise ValueError(";".join(failures))
            if record.state != "SEALED":
                raise ValueError("SEMANTIC_MEMORY_SEALED_STATE_REQUIRED")
            if record.memory_id in self._sealed:
                raise ValueError("SEMANTIC_MEMORY_SEALED_DUPLICATE")
            self._sealed[record.memory_id] = record

    def seed_active(self, records: Sequence[SemanticRecord]) -> None:
        """Load compiler-authorized M0 before the first runtime cycle."""

        if self._version != 0 or self._active or self._provenance:
            raise RuntimeError("SEMANTIC_MEMORY_ACTIVE_SEED_AFTER_START_FORBIDDEN")
        for record in records:
            failures = record.validate()
            if failures:
                raise ValueError(";".join(failures))
            if record.state not in {"ACTIVE", "PROBATION"}:
                raise ValueError("SEMANTIC_MEMORY_ACTIVE_SEED_STATE_INVALID")
            if record.memory_id in self._active:
                raise ValueError("SEMANTIC_MEMORY_ACTIVE_SEED_DUPLICATE")
            self._active[record.memory_id] = record
        if len(self._active) > self.max_active:
            raise RuntimeError("SEMANTIC_MEMORY_ACTIVE_BUDGET_EXCEEDED")
        self._snapshots[0] = dict(self._active)

    def set_working(self, records: Sequence[SemanticRecord]) -> None:
        """Replace cycle-local working memory; it is never an active authority."""

        next_working: dict[str, SemanticRecord] = {}
        for record in records:
            failures = record.validate()
            if failures:
                raise ValueError(";".join(failures))
            next_working[record.memory_id] = record
        self._working = next_working

    def clear_working(self) -> None:
        self._working.clear()

    def view(self) -> MemoryView:
        active = tuple(self._active[key] for key in sorted(self._active))
        working = tuple(self._working[key] for key in sorted(self._working))
        sealed = tuple(self._sealed[key] for key in sorted(self._sealed))
        digest = "semantic-memory-view:" + digest_object(
            {
                "version": self._version,
                "active": active,
                "working": working,
                "sealed": sealed,
            }
        )
        return MemoryView(
            version=self._version,
            active=active,
            working=working,
            sealed=sealed,
            digest_value=digest,
        )

    def read(self, memory_id: str, *, include_archive: bool = False) -> SemanticRecord:
        if memory_id in self._active:
            return self._active[memory_id]
        if memory_id in self._sealed:
            return self._sealed[memory_id]
        if include_archive and memory_id in self._archive:
            return self._archive[memory_id]
        raise KeyError(memory_id)

    def query(self, query: SemanticMemoryQuery) -> SemanticMemoryQueryResult:
        failures = query.validate()
        if failures:
            raise ValueError(";".join(failures))
        query_tokens = set(query.semantic_tokens)
        records = list(self._active.values()) + list(self._sealed.values())
        if query.include_archive:
            records.extend(self._archive.values())
        scored: list[tuple[int, SemanticRecord]] = []
        for record in records:
            if query.kinds and record.kind not in query.kinds:
                continue
            score = len(query_tokens.intersection(record.semantic_tokens))
            score += len(query_tokens.intersection(record.relations))
            if score > 0 or not query_tokens:
                scored.append((score, record))
        scored.sort(
            key=lambda item: (
                -item[0],
                -item[1].updated_version,
                item[1].memory_id,
            )
        )
        selected = tuple(item[1] for item in scored[: query.limit])
        selected_scores = tuple(
            (item[1].memory_id, item[0]) for item in scored[: query.limit]
        )
        digest = "semantic-memory-query:" + digest_object(
            {
                "query": query,
                "memory_version": self._version,
                "records": selected,
                "scores": selected_scores,
                "archive_included": query.include_archive,
            }
        )
        return SemanticMemoryQueryResult(
            query_id=query.query_id,
            memory_version=self._version,
            records=selected,
            selected_scores=selected_scores,
            archive_included=query.include_archive,
            digest_value=digest,
        )

    def snapshot(self, version: int | None = None) -> tuple[SemanticRecord, ...]:
        selected = self._version if version is None else version
        if selected not in self._snapshots:
            raise KeyError(selected)
        values = self._snapshots[selected]
        return tuple(values[key] for key in sorted(values))

    def provenance(self) -> tuple[MemoryProvenance, ...]:
        return tuple(self._provenance)

    def _archive_record(
        self,
        record: SemanticRecord,
        *,
        state: str = "ARCHIVED",
    ) -> None:
        key = f"{record.memory_id}@v{record.updated_version}:{len(self._archive)}"
        self._archive[key] = replace(record, state=state)
        if len(self._archive) > self.max_archive:
            oldest = sorted(self._archive)[0]
            del self._archive[oldest]

    def _normalized_record(
        self,
        record: SemanticRecord,
        *,
        created_version: int,
        next_version: int,
        rollback_pointer: int,
        state: str | None = None,
    ) -> SemanticRecord:
        normalized = replace(
            record,
            semantic_tokens=_sorted_unique(record.semantic_tokens),
            relations=_sorted_unique(record.relations),
            evidence=_sorted_unique(record.evidence),
            counter_evidence=_sorted_unique(record.counter_evidence),
            scope=_sorted_unique(record.scope),
            state=state or record.state,
            created_version=created_version,
            updated_version=next_version,
            rollback_pointer=rollback_pointer,
        )
        failures = normalized.validate()
        if failures:
            raise ValueError(";".join(failures))
        return normalized

    def apply_authorized(
        self,
        proposal: MemoryMutationProposal,
        authorization: MemoryAuthorization,
    ) -> MemoryMutationReceipt:
        failures = proposal.validate()
        if failures:
            raise ValueError(";".join(failures))
        if authorization._authority_token is not self.authority_token:
            raise PermissionError("SEMANTIC_MEMORY_AUTHORITY_INVALID")
        if authorization.authorization_id in self._consumed_authorizations:
            raise PermissionError("SEMANTIC_MEMORY_AUTHORIZATION_REUSED")
        if authorization.expected_version != self._version:
            raise RuntimeError("SEMANTIC_MEMORY_VERSION_CONFLICT")
        if authorization.proposal_digest != digest_object(proposal):
            raise PermissionError("SEMANTIC_MEMORY_PROPOSAL_BINDING_INVALID")

        old_version = self._version
        old_active_digest = self._active_digest()
        next_version = old_version + 1
        old = self._active.get(proposal.target_id)
        operation = proposal.operation

        if operation == "ADD":
            if old is not None or proposal.record is None:
                raise ValueError("SEMANTIC_MEMORY_ADD_TARGET_EXISTS")
            self._active[proposal.target_id] = self._normalized_record(
                proposal.record,
                created_version=next_version,
                next_version=next_version,
                rollback_pointer=old_version,
            )
        elif operation in {"REVISE", "REINDEX"}:
            if old is None or proposal.record is None:
                raise KeyError(proposal.target_id)
            self._archive_record(old, state="SUPERSEDED")
            self._active[proposal.target_id] = self._normalized_record(
                proposal.record,
                created_version=old.created_version,
                next_version=next_version,
                rollback_pointer=old_version,
            )
        elif operation == "REPLACE":
            if old is None or proposal.record is None:
                raise KeyError(proposal.target_id)
            self._archive_record(old, state="SUPERSEDED")
            self._active[proposal.target_id] = self._normalized_record(
                proposal.record,
                created_version=next_version,
                next_version=next_version,
                rollback_pointer=old_version,
            )
        elif operation == "INVALIDATE":
            if old is None:
                raise KeyError(proposal.target_id)
            self._archive_record(old, state="SUSPENDED")
            self._active[proposal.target_id] = replace(
                old,
                state="SUSPENDED",
                updated_version=next_version,
                rollback_pointer=old_version,
                evidence=_sorted_unique((*old.evidence, *proposal.evidence)),
                counter_evidence=_sorted_unique(
                    (*old.counter_evidence, *proposal.counter_evidence)
                ),
            )
        elif operation in {"DELETE", "ARCHIVE"}:
            if old is None:
                raise KeyError(proposal.target_id)
            self._archive_record(old)
            del self._active[proposal.target_id]
        elif operation == "MERGE":
            source_records = []
            for source_id in proposal.source_ids:
                source = self._active.get(source_id)
                if source is None:
                    raise KeyError(source_id)
                source_records.append(source)
            if old is not None and old not in source_records:
                source_records.append(old)
            if not source_records:
                raise ValueError("SEMANTIC_MEMORY_MERGE_EMPTY")
            merged = proposal.record or source_records[0]
            for source in source_records:
                self._archive_record(source, state="SUPERSEDED")
                self._active.pop(source.memory_id, None)
            merged = replace(
                merged,
                memory_id=proposal.target_id,
                semantic_tokens=_sorted_unique(
                    tuple(
                        token
                        for source in source_records
                        for token in source.semantic_tokens
                    )
                ),
                relations=_sorted_unique(
                    tuple(
                        relation
                        for source in source_records
                        for relation in source.relations
                    )
                ),
                evidence=_sorted_unique(
                    (
                        *proposal.evidence,
                        *tuple(
                            evidence
                            for source in source_records
                            for evidence in source.evidence
                        ),
                    )
                ),
                counter_evidence=_sorted_unique(
                    (
                        *proposal.counter_evidence,
                        *tuple(
                            evidence
                            for source in source_records
                            for evidence in source.counter_evidence
                        ),
                    )
                ),
            )
            self._active[proposal.target_id] = self._normalized_record(
                merged,
                created_version=next_version,
                next_version=next_version,
                rollback_pointer=old_version,
            )
        elif operation == "SPLIT":
            if old is None or proposal.record is None:
                raise KeyError(proposal.target_id)
            children = proposal.record.payload().get("children")
            if (
                not isinstance(children, tuple)
                or not children
                or not all(isinstance(item, SemanticRecord) for item in children)
            ):
                raise ValueError("SEMANTIC_MEMORY_SPLIT_CHILDREN_INVALID")
            self._archive_record(old, state="SUPERSEDED")
            del self._active[proposal.target_id]
            for child in children:
                self._active[child.memory_id] = self._normalized_record(
                    child,
                    created_version=next_version,
                    next_version=next_version,
                    rollback_pointer=old_version,
                )
        elif operation == "ROLLBACK":
            target_version = proposal.rollback_version
            if target_version is None or target_version not in self._snapshots:
                raise KeyError(target_version)
            for record in self._active.values():
                self._archive_record(record, state="SUPERSEDED")
            self._active = dict(self._snapshots[target_version])
        else:
            raise ValueError("SEMANTIC_MEMORY_OPERATION_UNREACHABLE")

        if len(self._active) > self.max_active:
            raise RuntimeError("SEMANTIC_MEMORY_ACTIVE_BUDGET_EXCEEDED")
        self._version = next_version
        self._snapshots[next_version] = dict(self._active)
        self._consumed_authorizations.add(authorization.authorization_id)
        event = MemoryProvenance(
            event_id="memory-event:" + digest_object(
                {
                    "authorization": authorization.authorization_id,
                    "proposal": proposal,
                    "old_version": old_version,
                    "new_version": next_version,
                }
            )[:24],
            operation=operation,
            target_id=proposal.target_id,
            old_version=old_version,
            new_version=next_version,
            old_digest=old_active_digest,
            new_digest=self._active_digest(),
            evidence=_sorted_unique(proposal.evidence),
            counter_evidence=_sorted_unique(proposal.counter_evidence),
            scope=_sorted_unique(proposal.scope),
            falsification_condition=proposal.falsification_condition,
            authority="HDS",
            rollback_pointer=(
                proposal.rollback_version
                if proposal.rollback_version is not None
                else old_version
            ),
            decision_id=authorization.decision_id,
            authorization_id=authorization.authorization_id,
            reason=proposal.reason,
        )
        self._provenance.append(event)
        return MemoryMutationReceipt(
            operation=operation,
            target_id=proposal.target_id,
            old_version=old_version,
            new_version=next_version,
            event_digest=event.digest(),
            active_digest=self._active_digest(),
            archive_digest=self._archive_digest(),
        )


def semantic_record(
    *,
    memory_id: str,
    kind: str,
    statement: str,
    semantic_tokens: Sequence[str],
    evidence: Sequence[str],
    counter_evidence: Sequence[str] = (),
    relations: Sequence[str] = (),
    scope: Sequence[str] = ("runtime",),
    falsification_condition: str = "future observation contradicts record",
    state: str = "ACTIVE",
    payload: Mapping[str, object] | None = None,
) -> SemanticRecord:
    """Build one normalized record without granting mutation authority."""

    return SemanticRecord(
        memory_id=memory_id,
        kind=kind,
        statement=statement,
        semantic_tokens=_sorted_unique(tuple(semantic_tokens)),
        relations=_sorted_unique(tuple(relations)),
        evidence=_sorted_unique(tuple(evidence)),
        counter_evidence=_sorted_unique(tuple(counter_evidence)),
        scope=_sorted_unique(tuple(scope)),
        falsification_condition=falsification_condition,
        state=state,
        payload_items=tuple(sorted((payload or {}).items())),
    )


__all__ = [
    "GENERIC_MEMORY_VERSION",
    "MemoryAuthorization",
    "MemoryMutationProposal",
    "MemoryMutationReceipt",
    "MemoryProvenance",
    "MemoryView",
    "SEMANTIC_MEMORY_KINDS",
    "SEMANTIC_MEMORY_MUTATIONS",
    "SEMANTIC_MEMORY_READS",
    "SEMANTIC_MEMORY_STATES",
    "SemanticMemory",
    "SemanticMemoryQuery",
    "SemanticMemoryQueryResult",
    "SemanticRecord",
    "semantic_record",
]
