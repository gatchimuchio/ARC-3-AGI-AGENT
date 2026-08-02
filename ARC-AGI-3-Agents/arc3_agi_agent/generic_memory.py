"""Versioned semantic memory for the GenericAGIRuntime.

The memory is passive: it can query or apply a single-use HDS authorization,
but it cannot create hypotheses, choose actions, or initiate mutations.
"""

from __future__ import annotations

import hashlib
import json
import threading
from dataclasses import dataclass, field, replace
from functools import lru_cache
from typing import TYPE_CHECKING, Iterator, Mapping, Sequence

from .authority_state import AuthorityState
from .generic_types import ActionEffectRecord, SemanticMemoryCitation
from .memory_backend import InMemoryBackend, MemoryBackend
from .memory_event import MemoryDelta, MemoryEvent
from .memory_image import MemoryImage
from .memory_transaction import StagedMemoryTransition
from .schema import canonical_json, digest_object

if TYPE_CHECKING:
    from .memory_retrieval import RetrievalScoreBreakdown

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
        "STATE_MODEL",
        "TRANSITION_RULE",
        "DECISION_RATIONALE",
        "OPEN_TERM",
        "ROLLBACK_POINTER",
        "ACTION_EFFECT",
        "GOAL_MODEL",
        "HAZARD_MODEL",
        "OBJECT_SCHEMA",
        "RELATION_SCHEMA",
        "EXPLORATION_POLICY",
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
ACTION_EFFECT_HISTORY_LIMIT = 16


def _valid_text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _sorted_unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted(set(values)))


class _FrozenPayloadMapping(Mapping[str, object]):
    """Minimal immutable Mapping used inside cached semantic records."""

    __slots__ = ("_items",)

    def __init__(self, items: Sequence[tuple[str, object]]) -> None:
        self._items = tuple(sorted(items))

    def __getitem__(self, key: str) -> object:
        for candidate, value in self._items:
            if candidate == key:
                return value
        raise KeyError(key)

    def __iter__(self) -> Iterator[str]:
        return (key for key, _ in self._items)

    def __len__(self) -> int:
        return len(self._items)


def _freeze_payload(value: object) -> object:
    if isinstance(value, Mapping):
        return _FrozenPayloadMapping(
            tuple((str(key), _freeze_payload(item)) for key, item in value.items())
        )
    if isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        return tuple(_freeze_payload(item) for item in value)
    return value


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
    _canonical_blob_cache: str | None = field(
        default=None,
        init=False,
        repr=False,
        compare=False,
        hash=False,
        metadata={"serialize": False},
    )
    _citation_cache: SemanticMemoryCitation | None = field(
        default=None,
        init=False,
        repr=False,
        compare=False,
        hash=False,
        metadata={"serialize": False},
    )

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
            if any(
                not _valid_text(item) for item in values
            ) or values != _sorted_unique(values):
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
        cached = self._citation_cache
        if cached is None:
            blob = _record_blob(self)
            cached = SemanticMemoryCitation(
                memory_id=self.memory_id,
                version=self.updated_version,
                kind=self.kind,
                semantic_tokens=self.semantic_tokens,
                content_digest="semantic-record:"
                + hashlib.sha256(blob.encode("utf-8")).hexdigest(),
            )
            object.__setattr__(self, "_citation_cache", cached)
        return cached


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
            self.operation in {"ADD", "REVISE", "SPLIT", "REPLACE", "REINDEX"}
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
        if self.operation == "ROLLBACK" and (
            isinstance(self.rollback_version, bool)
            or not isinstance(self.rollback_version, int)
            or self.rollback_version < 0
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
class ActionHistoryAuthorization:
    """Single-use HDS capability for one bounded action/effect M append."""

    authorization_id: str
    decision_id: str
    before_observation_signature: str
    after_observation_signature: str
    expected_version: int
    record_digest: str
    _authority_token: object = field(
        repr=False,
        compare=False,
        metadata={"serialize": False},
    )


@dataclass(frozen=True, slots=True)
class ActionHistoryEvent:
    """Append-only event from which the bounded episode view is rebuilt."""

    version: int
    decision_id: str
    authorization_id: str
    before_observation_signature: str
    after_observation_signature: str
    record: ActionEffectRecord
    previous_event_digest: str
    event_digest: str

    def validate(self) -> tuple[str, ...]:
        failures = list(self.record.validate())
        if (
            self.version <= 0
            or not self.decision_id
            or not self.authorization_id
            or not self.before_observation_signature
            or not self.after_observation_signature
        ):
            failures.append("ACTION_EFFECT_HISTORY_EVENT_INVALID")
        expected = "action-history-event:" + digest_object(
            {
                "version": self.version,
                "decision_id": self.decision_id,
                "authorization_id": self.authorization_id,
                "before": self.before_observation_signature,
                "after": self.after_observation_signature,
                "record": self.record,
                "previous": self.previous_event_digest,
            }
        )
        if self.event_digest != expected:
            failures.append("ACTION_EFFECT_HISTORY_EVENT_DIGEST_INVALID")
        return tuple(sorted(set(failures)))


def action_history_authorization_binding(
    *,
    decision_id: str,
    before_observation_signature: str,
    after_observation_signature: str,
    expected_version: int,
    record_digest: str,
) -> str:
    return digest_object(
        {
            "decision": decision_id,
            "before": before_observation_signature,
            "after": after_observation_signature,
            "expected_version": expected_version,
            "record_digest": record_digest,
        }
    )


@dataclass(slots=True)
class BoundedActionEffectMemory:
    """Passive, event-sourced episode M with a deterministic bounded view."""

    authority_state: AuthorityState = field(repr=False)
    limit: int = ACTION_EFFECT_HISTORY_LIMIT
    _version: int = field(default=0, init=False, repr=False)
    _active: tuple[ActionEffectRecord, ...] = field(
        default=(),
        init=False,
        repr=False,
    )
    _events: list[ActionHistoryEvent] = field(
        default_factory=list,
        init=False,
        repr=False,
    )
    _episode_open: bool = field(default=False, init=False, repr=False)
    _lock: threading.RLock = field(
        default_factory=threading.RLock,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        if (
            isinstance(self.limit, bool)
            or not isinstance(self.limit, int)
            or not 1 <= self.limit <= 256
        ):
            raise ValueError("ACTION_EFFECT_HISTORY_LIMIT_INVALID")

    @property
    def version(self) -> int:
        return self._version

    def begin_episode(self) -> None:
        with self._lock:
            if self._episode_open:
                raise RuntimeError("ACTION_EFFECT_HISTORY_EPISODE_ALREADY_OPEN")
            self._episode_open = True
            self._active = ()

    def end_episode(self) -> None:
        with self._lock:
            if not self._episode_open:
                raise RuntimeError("ACTION_EFFECT_HISTORY_EPISODE_NOT_OPEN")
            self._active = ()
            self._episode_open = False

    def view(self) -> tuple[ActionEffectRecord, ...]:
        with self._lock:
            return tuple(self._active)

    def events(self) -> tuple[ActionHistoryEvent, ...]:
        with self._lock:
            return tuple(self._events)

    def digest(self) -> str:
        with self._lock:
            return "bounded-action-effect-memory:" + digest_object(
                {
                    "version": self._version,
                    "active": self._active,
                    "event_digests": tuple(
                        event.event_digest for event in self._events
                    ),
                    "episode_open": self._episode_open,
                }
            )

    def append_authorized(
        self,
        record: ActionEffectRecord,
        authorization: ActionHistoryAuthorization,
    ) -> ActionHistoryEvent:
        failures = record.validate()
        if failures:
            raise ValueError(";".join(failures))
        with self._lock:
            if not self._episode_open:
                raise RuntimeError("ACTION_EFFECT_HISTORY_EPISODE_NOT_OPEN")
            self.authority_state.require_live_token(
                authorization._authority_token,
                error="ACTION_EFFECT_HISTORY_AUTHORITY_INVALID",
            )
            if (
                authorization.expected_version != self._version
                or authorization.record_digest != record.digest()
            ):
                raise RuntimeError("ACTION_EFFECT_HISTORY_VERSION_OR_BINDING_INVALID")
            binding = action_history_authorization_binding(
                decision_id=authorization.decision_id,
                before_observation_signature=(
                    authorization.before_observation_signature
                ),
                after_observation_signature=(authorization.after_observation_signature),
                expected_version=authorization.expected_version,
                record_digest=authorization.record_digest,
            )
            self.authority_state.consume(
                authorization.authorization_id,
                kind="HDS_ACTION_HISTORY",
                binding_digest=binding,
                unknown_error="ACTION_EFFECT_HISTORY_AUTHORIZATION_NOT_ISSUED",
                reused_error="ACTION_EFFECT_HISTORY_AUTHORIZATION_REUSED",
                binding_error="ACTION_EFFECT_HISTORY_AUTHORIZATION_BINDING_INVALID",
            )
            next_version = self._version + 1
            previous = (
                self._events[-1].event_digest
                if self._events
                else "action-history-event:GENESIS"
            )
            event_digest = "action-history-event:" + digest_object(
                {
                    "version": next_version,
                    "decision_id": authorization.decision_id,
                    "authorization_id": authorization.authorization_id,
                    "before": authorization.before_observation_signature,
                    "after": authorization.after_observation_signature,
                    "record": record,
                    "previous": previous,
                }
            )
            event = ActionHistoryEvent(
                version=next_version,
                decision_id=authorization.decision_id,
                authorization_id=authorization.authorization_id,
                before_observation_signature=(
                    authorization.before_observation_signature
                ),
                after_observation_signature=(authorization.after_observation_signature),
                record=record,
                previous_event_digest=previous,
                event_digest=event_digest,
            )
            event_failures = event.validate()
            if event_failures:
                raise RuntimeError(";".join(event_failures))
            self._events.append(event)
            self._active = (*self._active, record)[-self.limit :]
            self._version = next_version
            return event


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
        if any(
            not _valid_text(item) for item in self.semantic_tokens
        ) or self.semantic_tokens != _sorted_unique(self.semantic_tokens):
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
    score_breakdowns: tuple[RetrievalScoreBreakdown, ...] = ()

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
    idempotency_key: str = ""
    batch_size: int = 1


_MEMORY_BATCH_PRIORITY = {
    "FAILURE_SIGNATURE": 1,
    "ROLLBACK_POINTER": 1,
    "TRANSITION_RULE": 2,
    "ACTION_EFFECT": 2,
    "HYPOTHESIS": 3,
    "COUNTER_HYPOTHESIS": 3,
    "CONTRADICTION": 3,
    "WORLD_MODEL": 4,
    "GOAL_MODEL": 4,
    "HAZARD_MODEL": 4,
    "DECISION_RATIONALE": 5,
    "OPEN_TERM": 5,
}


def _record_blob(record: SemanticRecord) -> str:
    cached = record._canonical_blob_cache
    if cached is not None:
        return cached
    failures = record.validate()
    if failures:
        raise ValueError(";".join(failures))
    cached = canonical_json(record)
    object.__setattr__(record, "_canonical_blob_cache", cached)
    return cached


@lru_cache(maxsize=32_768)
def _record_from_blob(payload: str) -> SemanticRecord:
    value = json.loads(payload)
    if not isinstance(value, Mapping):
        raise TypeError("SEMANTIC_MEMORY_RECORD_BLOB_INVALID")

    def texts(name: str) -> tuple[str, ...]:
        selected = value.get(name, ())
        if isinstance(selected, (str, bytes)) or not isinstance(selected, Sequence):
            raise TypeError("SEMANTIC_MEMORY_RECORD_SEQUENCE_INVALID:" + name)
        return tuple(str(item) for item in selected)

    payload_value = value.get("payload_items", ())
    if isinstance(payload_value, (str, bytes)) or not isinstance(
        payload_value, Sequence
    ):
        raise TypeError("SEMANTIC_MEMORY_RECORD_PAYLOAD_INVALID")
    payload_items: list[tuple[str, object]] = []
    for item in payload_value:
        if (
            isinstance(item, (str, bytes))
            or not isinstance(item, Sequence)
            or len(item) != 2
        ):
            raise TypeError("SEMANTIC_MEMORY_RECORD_PAYLOAD_INVALID")
        payload_items.append((str(item[0]), _freeze_payload(item[1])))
    record = SemanticRecord(
        memory_id=str(value["memory_id"]),
        kind=str(value["kind"]),
        statement=str(value["statement"]),
        semantic_tokens=texts("semantic_tokens"),
        relations=texts("relations"),
        evidence=texts("evidence"),
        counter_evidence=texts("counter_evidence"),
        scope=texts("scope"),
        falsification_condition=str(value["falsification_condition"]),
        authority=str(value.get("authority", "HDS")),
        state=str(value.get("state", "ACTIVE")),
        created_version=int(value.get("created_version", 0)),
        updated_version=int(value.get("updated_version", 0)),
        rollback_pointer=int(value.get("rollback_pointer", 0)),
        payload_items=tuple(payload_items),
    )
    failures = record.validate()
    if failures:
        raise ValueError(";".join(failures))
    object.__setattr__(record, "_canonical_blob_cache", payload)
    return record


def _provenance_from_blob(payload: str) -> MemoryProvenance:
    value = json.loads(payload)
    if not isinstance(value, Mapping):
        raise TypeError("SEMANTIC_MEMORY_PROVENANCE_BLOB_INVALID")

    def texts(name: str) -> tuple[str, ...]:
        selected = value.get(name, ())
        if isinstance(selected, (str, bytes)) or not isinstance(selected, Sequence):
            raise TypeError("SEMANTIC_MEMORY_PROVENANCE_SEQUENCE_INVALID:" + name)
        return tuple(str(item) for item in selected)

    return MemoryProvenance(
        event_id=str(value["event_id"]),
        operation=str(value["operation"]),
        target_id=str(value["target_id"]),
        old_version=int(value["old_version"]),
        new_version=int(value["new_version"]),
        old_digest=str(value["old_digest"]),
        new_digest=str(value["new_digest"]),
        evidence=texts("evidence"),
        counter_evidence=texts("counter_evidence"),
        scope=texts("scope"),
        falsification_condition=str(value["falsification_condition"]),
        authority=str(value["authority"]),
        rollback_pointer=int(value["rollback_pointer"]),
        decision_id=str(value["decision_id"]),
        authorization_id=str(value["authorization_id"]),
        reason=str(value["reason"]),
    )


@dataclass(slots=True)
class SemanticMemory:
    """Passive memory whose ledger/image commit is atomic and event-sourced."""

    authority_state: AuthorityState = field(repr=False)
    backend: MemoryBackend = field(
        default_factory=InMemoryBackend,
        repr=False,
    )
    max_active: int = 2048
    max_archive: int = 8192
    max_batch_size: int = 64
    _image: MemoryImage = field(init=False, repr=False)
    _working: dict[str, SemanticRecord] = field(
        default_factory=dict,
        init=False,
        repr=False,
    )
    _provenance: list[MemoryProvenance] = field(
        default_factory=list,
        init=False,
        repr=False,
    )
    _committed_batches: dict[
        str,
        tuple[str, tuple[MemoryMutationReceipt, ...]],
    ] = field(default_factory=dict, init=False, repr=False)
    _lock: threading.RLock = field(
        default_factory=threading.RLock,
        init=False,
        repr=False,
    )

    def __post_init__(self) -> None:
        if self.max_active <= 0 or self.max_archive <= 0:
            raise ValueError("SEMANTIC_MEMORY_BUDGET_INVALID")
        if not 1 <= self.max_batch_size <= 256:
            raise ValueError("SEMANTIC_MEMORY_BATCH_BUDGET_INVALID")
        current = self.backend.current_image()
        rebuilt = self.backend.rebuild(current.version)
        if current.digest() != rebuilt.digest():
            raise RuntimeError("SEMANTIC_MEMORY_RESTART_DIGEST_MISMATCH")
        self._image = rebuilt
        for event in self.backend.events():
            self._provenance.extend(
                _provenance_from_blob(item) for item in event.audit_payloads
            )

    @property
    def version(self) -> int:
        return self._image.version

    @property
    def authority_token(self) -> object:
        """Compatibility view; AuthorityState remains the sole token owner."""

        return self.authority_state.live_token

    def _active_records(self) -> dict[str, SemanticRecord]:
        return {
            key: _record_from_blob(payload) for key, payload in self._image.active_items
        }

    def _archive_records(self) -> dict[str, SemanticRecord]:
        return {
            key: _record_from_blob(payload)
            for key, payload in self._image.archive_items
        }

    def _sealed_records(self) -> dict[str, SemanticRecord]:
        return {
            key: _record_from_blob(payload) for key, payload in self._image.sealed_items
        }

    @staticmethod
    def _active_digest_for(
        active: Mapping[str, SemanticRecord],
    ) -> str:
        canonical_records = (
            "[" + ",".join(_record_blob(active[key]) for key in sorted(active)) + "]"
        )
        return (
            "semantic-active:"
            + hashlib.sha256(canonical_records.encode("utf-8")).hexdigest()
        )

    @staticmethod
    def _archive_digest_for(
        archive: Mapping[str, SemanticRecord],
    ) -> str:
        canonical_records = (
            "[" + ",".join(_record_blob(archive[key]) for key in sorted(archive)) + "]"
        )
        return (
            "semantic-archive:"
            + hashlib.sha256(canonical_records.encode("utf-8")).hexdigest()
        )

    def _active_digest(self) -> str:
        return self._active_digest_for(self._active_records())

    def _archive_digest(self) -> str:
        return self._archive_digest_for(self._archive_records())

    def _replace_bootstrap(
        self,
        *,
        active: Mapping[str, SemanticRecord] | None = None,
        sealed: Mapping[str, SemanticRecord] | None = None,
    ) -> None:
        current_active = self._active_records() if active is None else dict(active)
        current_sealed = self._sealed_records() if sealed is None else dict(sealed)
        image = MemoryImage.build(
            version=0,
            active={
                key: _record_blob(record) for key, record in current_active.items()
            },
            archive=(),
            sealed={
                key: _record_blob(record) for key, record in current_sealed.items()
            },
        )
        self.backend.replace_bootstrap(image)
        self._image = image

    def seed_sealed(self, records: Sequence[SemanticRecord]) -> None:
        """Seed constitutional memory before runtime; it is immutable thereafter."""

        if self.version != 0 or self._provenance:
            raise RuntimeError("SEMANTIC_MEMORY_SEAL_AFTER_START_FORBIDDEN")
        sealed = self._sealed_records()
        for record in records:
            failures = record.validate()
            if failures:
                raise ValueError(";".join(failures))
            if record.state != "SEALED":
                raise ValueError("SEMANTIC_MEMORY_SEALED_STATE_REQUIRED")
            if record.memory_id in sealed:
                raise ValueError("SEMANTIC_MEMORY_SEALED_DUPLICATE")
            sealed[record.memory_id] = record
        self._replace_bootstrap(sealed=sealed)

    def seed_active(self, records: Sequence[SemanticRecord]) -> None:
        """Load compiler-authorized M0 before the first runtime cycle."""

        if self.version != 0 or self._active_records() or self._provenance:
            raise RuntimeError("SEMANTIC_MEMORY_ACTIVE_SEED_AFTER_START_FORBIDDEN")
        active: dict[str, SemanticRecord] = {}
        for record in records:
            failures = record.validate()
            if failures:
                raise ValueError(";".join(failures))
            if record.state not in {"ACTIVE", "PROBATION"}:
                raise ValueError("SEMANTIC_MEMORY_ACTIVE_SEED_STATE_INVALID")
            if record.memory_id in active:
                raise ValueError("SEMANTIC_MEMORY_ACTIVE_SEED_DUPLICATE")
            active[record.memory_id] = record
        if len(active) > self.max_active:
            raise RuntimeError("SEMANTIC_MEMORY_ACTIVE_BUDGET_EXCEEDED")
        self._replace_bootstrap(active=active)

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
        active_records = self._active_records()
        sealed_records = self._sealed_records()
        active = tuple(active_records[key] for key in sorted(active_records))
        working = tuple(self._working[key] for key in sorted(self._working))
        sealed = tuple(sealed_records[key] for key in sorted(sealed_records))
        digest = "semantic-memory-view:" + digest_object(
            {
                "version": self.version,
                "active": active,
                "working": working,
                "sealed": sealed,
            }
        )
        return MemoryView(
            version=self.version,
            active=active,
            working=working,
            sealed=sealed,
            digest_value=digest,
        )

    def read(self, memory_id: str, *, include_archive: bool = False) -> SemanticRecord:
        active = self._active_records()
        sealed = self._sealed_records()
        if memory_id in active:
            return active[memory_id]
        if memory_id in sealed:
            return sealed[memory_id]
        if include_archive:
            archive = self._archive_records()
            if memory_id in archive:
                return archive[memory_id]
        raise KeyError(memory_id)

    def query(self, query: SemanticMemoryQuery) -> SemanticMemoryQueryResult:
        from .memory_retrieval import rank_memory_records

        failures = query.validate()
        if failures:
            raise ValueError(";".join(failures))
        records = list(self._active_records().values()) + list(
            self._sealed_records().values()
        )
        if query.include_archive:
            records.extend(self._archive_records().values())
        selected, score_breakdowns = rank_memory_records(
            records=records,
            query_tokens=query.semantic_tokens,
            kinds=query.kinds,
            current_version=self.version,
            limit=query.limit,
        )
        selected_scores = tuple(
            (item.record_id, item.total_score) for item in score_breakdowns
        )
        digest = "semantic-memory-query:" + digest_object(
            {
                "query": query,
                "memory_version": self.version,
                "records": selected,
                "scores": selected_scores,
                "score_breakdowns": score_breakdowns,
                "archive_included": query.include_archive,
            }
        )
        return SemanticMemoryQueryResult(
            query_id=query.query_id,
            memory_version=self.version,
            records=selected,
            selected_scores=selected_scores,
            archive_included=query.include_archive,
            digest_value=digest,
            score_breakdowns=score_breakdowns,
        )

    def snapshot(self, version: int | None = None) -> tuple[SemanticRecord, ...]:
        image = self.backend.rebuild(version)
        values = {
            key: _record_from_blob(payload) for key, payload in image.active_items
        }
        return tuple(values[key] for key in sorted(values))

    def provenance(self) -> tuple[MemoryProvenance, ...]:
        return tuple(self._provenance)

    @staticmethod
    def _archive_record(
        archive: dict[str, SemanticRecord],
        record: SemanticRecord,
        *,
        state: str = "ARCHIVED",
    ) -> None:
        key = f"{record.memory_id}@v{record.updated_version}:{len(archive)}"
        archive[key] = replace(record, state=state)

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

    def _validate_authorized_pair(
        self,
        proposal: MemoryMutationProposal,
        authorization: MemoryAuthorization,
        *,
        expected_version: int,
    ) -> None:
        failures = proposal.validate()
        if failures:
            raise ValueError(";".join(failures))
        self.authority_state.require_live_token(
            authorization._authority_token,
            error="SEMANTIC_MEMORY_AUTHORITY_INVALID",
        )
        if authorization.proposal_digest != digest_object(proposal):
            raise PermissionError("SEMANTIC_MEMORY_PROPOSAL_BINDING_INVALID")
        capability_binding = digest_object(
            {
                "decision": authorization.decision_id,
                "proposal": proposal,
                "version": authorization.expected_version,
            }
        )
        self.authority_state.require_available(
            authorization.authorization_id,
            kind="HDS_MEMORY_UPDATE",
            binding_digest=capability_binding,
            unknown_error="SEMANTIC_MEMORY_AUTHORIZATION_NOT_ISSUED",
            reused_error="SEMANTIC_MEMORY_AUTHORIZATION_REUSED",
            binding_error="SEMANTIC_MEMORY_PROPOSAL_BINDING_INVALID",
        )
        if authorization.expected_version != expected_version:
            raise RuntimeError("SEMANTIC_MEMORY_VERSION_CONFLICT")

    def _apply_to_staged_maps(
        self,
        *,
        proposal: MemoryMutationProposal,
        active: dict[str, SemanticRecord],
        archive: dict[str, SemanticRecord],
        old_version: int,
        next_version: int,
    ) -> None:
        old = active.get(proposal.target_id)
        operation = proposal.operation
        if operation == "ADD":
            if old is not None or proposal.record is None:
                raise ValueError("SEMANTIC_MEMORY_ADD_TARGET_EXISTS")
            active[proposal.target_id] = self._normalized_record(
                proposal.record,
                created_version=next_version,
                next_version=next_version,
                rollback_pointer=old_version,
            )
        elif operation in {"REVISE", "REINDEX"}:
            if old is None or proposal.record is None:
                raise KeyError(proposal.target_id)
            self._archive_record(archive, old, state="SUPERSEDED")
            active[proposal.target_id] = self._normalized_record(
                proposal.record,
                created_version=old.created_version,
                next_version=next_version,
                rollback_pointer=old_version,
            )
        elif operation == "REPLACE":
            if old is None or proposal.record is None:
                raise KeyError(proposal.target_id)
            self._archive_record(archive, old, state="SUPERSEDED")
            active[proposal.target_id] = self._normalized_record(
                proposal.record,
                created_version=next_version,
                next_version=next_version,
                rollback_pointer=old_version,
            )
        elif operation == "INVALIDATE":
            if old is None:
                raise KeyError(proposal.target_id)
            self._archive_record(archive, old, state="SUSPENDED")
            active[proposal.target_id] = replace(
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
            self._archive_record(archive, old)
            del active[proposal.target_id]
        elif operation == "MERGE":
            source_records = []
            for source_id in proposal.source_ids:
                source = active.get(source_id)
                if source is None:
                    raise KeyError(source_id)
                source_records.append(source)
            if old is not None and old not in source_records:
                source_records.append(old)
            if not source_records:
                raise ValueError("SEMANTIC_MEMORY_MERGE_EMPTY")
            merged = proposal.record or source_records[0]
            for source in source_records:
                self._archive_record(archive, source, state="SUPERSEDED")
                active.pop(source.memory_id, None)
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
            active[proposal.target_id] = self._normalized_record(
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
            self._archive_record(archive, old, state="SUPERSEDED")
            del active[proposal.target_id]
            for child in children:
                active[child.memory_id] = self._normalized_record(
                    child,
                    created_version=next_version,
                    next_version=next_version,
                    rollback_pointer=old_version,
                )
        elif operation == "ROLLBACK":
            target_version = proposal.rollback_version
            if target_version is None:
                raise KeyError(target_version)
            target_image = self.backend.rebuild(target_version)
            active.clear()
            active.update(
                {
                    key: _record_from_blob(payload)
                    for key, payload in target_image.active_items
                }
            )
            archive.clear()
            archive.update(
                {
                    key: _record_from_blob(payload)
                    for key, payload in target_image.archive_items
                }
            )
        else:
            raise ValueError("SEMANTIC_MEMORY_OPERATION_UNREACHABLE")

        if len(active) > self.max_active:
            raise RuntimeError("SEMANTIC_MEMORY_ACTIVE_BUDGET_EXCEEDED")
        while len(archive) > self.max_archive:
            del archive[sorted(archive)[0]]

    def prepare_batch(
        self,
        *,
        expected_version: int,
        proposals: Sequence[MemoryMutationProposal],
        authorizations: Sequence[MemoryAuthorization],
        idempotency_key: str,
        mandatory: bool = True,
    ) -> StagedMemoryTransition:
        """Validate and stage a full batch without changing live state."""

        with self._lock:
            if expected_version != self.version:
                raise RuntimeError("SEMANTIC_MEMORY_VERSION_CONFLICT")
            if not idempotency_key:
                raise ValueError("SEMANTIC_MEMORY_IDEMPOTENCY_KEY_REQUIRED")
            if (
                not proposals
                or len(proposals) != len(authorizations)
                or len(proposals) > self.max_batch_size
            ):
                raise RuntimeError("SEMANTIC_MEMORY_MANDATORY_BATCH_SUSPEND")
            if len({item.target_id for item in proposals}) != len(proposals):
                raise ValueError("SEMANTIC_MEMORY_BATCH_TARGET_DUPLICATE")
            if len({item.authorization_id for item in authorizations}) != len(
                authorizations
            ):
                raise ValueError("SEMANTIC_MEMORY_BATCH_AUTHORIZATION_DUPLICATE")
            pairs = list(zip(proposals, authorizations))
            pairs.sort(
                key=lambda item: (
                    _MEMORY_BATCH_PRIORITY.get(
                        (
                            item[0].record.kind
                            if item[0].record is not None
                            else item[0].operation
                        ),
                        6,
                    ),
                    item[0].target_id,
                    item[1].authorization_id,
                )
            )
            ordered_proposals = tuple(item[0] for item in pairs)
            ordered_authorizations = tuple(item[1] for item in pairs)
            for proposal, authorization in pairs:
                self._validate_authorized_pair(
                    proposal,
                    authorization,
                    expected_version=expected_version,
                )

            active = self._active_records()
            archive = self._archive_records()
            old_version = self.version
            next_version = old_version + 1
            provenance: list[MemoryProvenance] = []
            for index, (proposal, authorization) in enumerate(pairs):
                old_digest = self._active_digest_for(active)
                self._apply_to_staged_maps(
                    proposal=proposal,
                    active=active,
                    archive=archive,
                    old_version=old_version,
                    next_version=next_version,
                )
                provenance.append(
                    MemoryProvenance(
                        event_id="memory-provenance:"
                        + digest_object(
                            {
                                "idempotency_key": idempotency_key,
                                "index": index,
                                "proposal": proposal,
                                "authorization": (authorization.authorization_id),
                            }
                        )[:24],
                        operation=proposal.operation,
                        target_id=proposal.target_id,
                        old_version=old_version,
                        new_version=next_version,
                        old_digest=old_digest,
                        new_digest=self._active_digest_for(active),
                        evidence=_sorted_unique(proposal.evidence),
                        counter_evidence=_sorted_unique(proposal.counter_evidence),
                        scope=_sorted_unique(proposal.scope),
                        falsification_condition=(proposal.falsification_condition),
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
                )
            preliminary = MemoryImage.build(
                version=next_version,
                active={key: _record_blob(record) for key, record in active.items()},
                archive={key: _record_blob(record) for key, record in archive.items()},
                sealed=self._image.sealed_items,
                last_event_digest=(
                    self._image.last_event_digest or "PREPARED_EVENT_TAIL"
                ),
            )
            proposal_digests = tuple(
                sorted(digest_object(item) for item in ordered_proposals)
            )
            if len(set(proposal_digests)) != len(proposal_digests):
                raise ValueError("SEMANTIC_MEMORY_BATCH_PROPOSAL_DUPLICATE")
            delta = MemoryDelta.between(self._image, preliminary)
            provenance_payloads = tuple(canonical_json(item) for item in provenance)
            event = MemoryEvent(
                event_id="memory-event:"
                + digest_object(
                    {
                        "idempotency_key": idempotency_key,
                        "old_version": old_version,
                        "proposal_digests": proposal_digests,
                        "next_state_digest": preliminary.state_digest(),
                    }
                )[:32],
                old_version=old_version,
                new_version=next_version,
                idempotency_key=idempotency_key,
                proposal_digests=proposal_digests,
                delta=delta,
                previous_event_digest=self._image.last_event_digest,
                next_state_digest=preliminary.state_digest(),
                audit_payloads=provenance_payloads,
            )
            event_digest = event.digest()
            next_image = MemoryImage.build(
                version=next_version,
                active=preliminary.active_items,
                archive=preliminary.archive_items,
                sealed=preliminary.sealed_items,
                last_event_digest=event_digest,
            )
            staged = StagedMemoryTransition(
                expected_version=old_version,
                next_version=next_version,
                idempotency_key=idempotency_key,
                proposal_digests=proposal_digests,
                target_ids=tuple(item.target_id for item in ordered_proposals),
                event_batch=(event,),
                next_image=next_image,
                provenance_payloads=provenance_payloads,
                mandatory=mandatory,
                prepared_from_digest=self._image.digest(),
                _proposals=ordered_proposals,
                _authorizations=ordered_authorizations,
            )
            staged_failures = staged.validate()
            if staged_failures:
                raise ValueError(";".join(staged_failures))
            return staged

    def commit_prepared(
        self,
        staged: StagedMemoryTransition,
    ) -> tuple[MemoryMutationReceipt, ...]:
        """Atomically commit ledger+image, then swap the live immutable image."""

        with self._lock:
            staged_failures = staged.validate()
            if staged_failures:
                raise ValueError(";".join(staged_failures))
            staged_digest = staged.digest()
            prior = self._committed_batches.get(staged.idempotency_key)
            if prior is not None:
                if prior[0] != staged_digest:
                    raise RuntimeError("SEMANTIC_MEMORY_IDEMPOTENCY_PAYLOAD_CONFLICT")
                return prior[1]
            if (
                self.version != staged.expected_version
                or self._image.digest() != staged.prepared_from_digest
            ):
                raise RuntimeError("SEMANTIC_MEMORY_VERSION_CONFLICT")
            proposals: list[MemoryMutationProposal] = []
            authorizations: list[MemoryAuthorization] = []
            for proposal, authorization in zip(
                staged._proposals,
                staged._authorizations,
            ):
                if not isinstance(proposal, MemoryMutationProposal):
                    raise TypeError("SEMANTIC_MEMORY_STAGED_PROPOSAL_INVALID")
                if not isinstance(authorization, MemoryAuthorization):
                    raise TypeError("SEMANTIC_MEMORY_STAGED_AUTHORIZATION_INVALID")
                self._validate_authorized_pair(
                    proposal,
                    authorization,
                    expected_version=staged.expected_version,
                )
                proposals.append(proposal)
                authorizations.append(authorization)
            backend_receipt = self.backend.commit(
                expected_version=staged.expected_version,
                event_batch=staged.event_batch,
                next_image=staged.next_image,
                idempotency_key=staged.idempotency_key,
            )
            for proposal, authorization in zip(
                proposals,
                authorizations,
            ):
                capability_binding = digest_object(
                    {
                        "decision": authorization.decision_id,
                        "proposal": proposal,
                        "version": authorization.expected_version,
                    }
                )
                self.authority_state.consume(
                    authorization.authorization_id,
                    kind="HDS_MEMORY_UPDATE",
                    binding_digest=capability_binding,
                    unknown_error="SEMANTIC_MEMORY_AUTHORIZATION_NOT_ISSUED",
                    reused_error="SEMANTIC_MEMORY_AUTHORIZATION_REUSED",
                    binding_error="SEMANTIC_MEMORY_PROPOSAL_BINDING_INVALID",
                )
            self._image = staged.next_image
            committed_provenance = tuple(
                _provenance_from_blob(item) for item in staged.provenance_payloads
            )
            self._provenance.extend(committed_provenance)
            active_digest = self._active_digest()
            archive_digest = self._archive_digest()
            event_digest = backend_receipt.event_digests[-1]
            receipts = tuple(
                MemoryMutationReceipt(
                    operation=proposal.operation,
                    target_id=proposal.target_id,
                    old_version=staged.expected_version,
                    new_version=staged.next_version,
                    event_digest=event_digest,
                    active_digest=active_digest,
                    archive_digest=archive_digest,
                    idempotency_key=staged.idempotency_key,
                    batch_size=len(proposals),
                )
                for proposal in proposals
            )
            self._committed_batches[staged.idempotency_key] = (
                staged_digest,
                receipts,
            )
            return receipts

    def apply_authorized_batch(
        self,
        proposals: Sequence[MemoryMutationProposal],
        authorizations: Sequence[MemoryAuthorization],
        *,
        idempotency_key: str,
        mandatory: bool = True,
    ) -> tuple[MemoryMutationReceipt, ...]:
        staged = self.prepare_batch(
            expected_version=self.version,
            proposals=proposals,
            authorizations=authorizations,
            idempotency_key=idempotency_key,
            mandatory=mandatory,
        )
        return self.commit_prepared(staged)

    def apply_authorized(
        self,
        proposal: MemoryMutationProposal,
        authorization: MemoryAuthorization,
    ) -> MemoryMutationReceipt:
        receipts = self.apply_authorized_batch(
            (proposal,),
            (authorization,),
            idempotency_key=authorization.authorization_id,
        )
        return receipts[0]

    def event_ledger(self) -> tuple[MemoryEvent, ...]:
        return self.backend.events()

    @property
    def full_copy_snapshot_per_version(self) -> bool:
        return False


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
        payload_items=tuple(
            sorted(
                (str(key), _freeze_payload(value))
                for key, value in (payload or {}).items()
            )
        ),
    )


__all__ = [
    "ACTION_EFFECT_HISTORY_LIMIT",
    "ActionHistoryAuthorization",
    "ActionHistoryEvent",
    "BoundedActionEffectMemory",
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
    "action_history_authorization_binding",
    "semantic_record",
]
