"""Typed causal-memory records backed by independent evidence groups."""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Mapping, Sequence

from .evidence_binding import (
    EvidenceBindingKey,
    binding_key_from_payload,
)
from .evidence_policy import (
    CAUSAL_SCOPE_CLASSES,
    EvidenceGroup,
    EvidencePolicy,
)
from .generic_memory import SemanticRecord, semantic_record
from .schema import digest_object

CAUSAL_RECORD_SCHEMA_VERSION = 1
CAUSAL_RECORD_KINDS = frozenset(
    {
        "PROCEDURE_CAPABILITY",
        "WORLD_MODEL",
        "STATE_MODEL",
        "TRANSITION_RULE",
        "ACTION_EFFECT",
        "GOAL_MODEL",
        "HAZARD_MODEL",
        "OBJECT_SCHEMA",
        "RELATION_SCHEMA",
        "EXPLORATION_POLICY",
        "FAILURE_SIGNATURE",
    }
)
_FORBIDDEN_GLOBAL_FEATURE_TERMS = (
    "game_id",
    "level_id",
    "task_id",
    "replay",
    "answer_map",
    "source_code",
    "hidden_state",
    "observation_signature",
)


def _sorted_unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted(set(values)))


def causal_record_id(
    *,
    kind: str,
    binding_key: EvidenceBindingKey,
    scope_class: str,
) -> str:
    return (
        "causal:"
        + kind.casefold().replace("_", "-")
        + ":"
        + digest_object(
            {
                "kind": kind,
                "binding_key_digest": binding_key.digest(),
                "applicability_scope_digest": digest_object(scope_class),
            }
        )[:32]
    )


@dataclass(frozen=True, slots=True)
class CausalRecord:
    record_id: str
    schema_version: int
    kind: str
    state: str
    scope_class: str
    binding_key: EvidenceBindingKey
    statement: str
    semantic_tokens: tuple[str, ...]
    relations: tuple[str, ...]
    precondition_program_digest: str
    predicted_effect_program_digest: str
    delay_window: tuple[int, int]
    applicability_predicates: tuple[str, ...]
    evidence_event_ids: tuple[str, ...]
    counter_evidence_event_ids: tuple[str, ...]
    evidence_groups: tuple[EvidenceGroup, ...]
    support_group_ids: tuple[str, ...]
    contradiction_group_ids: tuple[str, ...]
    hazard_group_ids: tuple[str, ...]
    no_effect_group_ids: tuple[str, ...]
    support_count: int
    contradiction_count: int
    hazard_count: int
    no_effect_count: int
    distinct_episode_support: int
    confidence_ppm: int
    execute_eligibility: bool
    probe_eligibility: bool
    falsification_condition: str
    created_version: int
    updated_version: int
    rollback_pointer: int
    provenance_digest: str
    usage_count: int
    last_verified_cycle: int
    payload_items: tuple[tuple[str, object], ...] = ()

    def payload(self) -> dict[str, object]:
        return dict(self.payload_items)

    def validate(
        self,
        *,
        policy: EvidencePolicy | None = None,
    ) -> tuple[str, ...]:
        failures: list[str] = []
        selected_policy = policy or EvidencePolicy()
        if self.schema_version != CAUSAL_RECORD_SCHEMA_VERSION:
            failures.append("CAUSAL_RECORD_SCHEMA_UNSUPPORTED")
        if self.kind not in CAUSAL_RECORD_KINDS:
            failures.append("CAUSAL_RECORD_KIND_INVALID")
        if self.scope_class not in CAUSAL_SCOPE_CLASSES:
            failures.append("CAUSAL_RECORD_SCOPE_INVALID")
        if not self.statement or not self.falsification_condition:
            failures.append("CAUSAL_RECORD_TEXT_INVALID")
        expected_id = causal_record_id(
            kind=self.kind,
            binding_key=self.binding_key,
            scope_class=self.scope_class,
        )
        if self.record_id != expected_id:
            failures.append("CAUSAL_RECORD_ID_INVALID")
        failures.extend(self.binding_key.validate())
        for name in (
            "semantic_tokens",
            "relations",
            "applicability_predicates",
            "evidence_event_ids",
            "counter_evidence_event_ids",
            "support_group_ids",
            "contradiction_group_ids",
            "hazard_group_ids",
            "no_effect_group_ids",
        ):
            values = getattr(self, name)
            if (
                values != _sorted_unique(values)
                or any(not isinstance(item, str) or not item for item in values)
            ):
                failures.append("CAUSAL_RECORD_SEQUENCE_INVALID:" + name)
        if (
            len(self.delay_window) != 2
            or any(
                isinstance(item, bool) or not isinstance(item, int)
                for item in self.delay_window
            )
            or self.delay_window[0] < 0
            or self.delay_window[1] < self.delay_window[0]
        ):
            failures.append("CAUSAL_RECORD_DELAY_INVALID")
        for name in (
            "support_count",
            "contradiction_count",
            "hazard_count",
            "no_effect_count",
            "distinct_episode_support",
            "confidence_ppm",
            "created_version",
            "updated_version",
            "rollback_pointer",
            "usage_count",
            "last_verified_cycle",
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
            ):
                failures.append("CAUSAL_RECORD_INTEGER_INVALID:" + name)
        if self.confidence_ppm > 1_000_000:
            failures.append("CAUSAL_RECORD_CONFIDENCE_INVALID")
        group_ids = tuple(item.group_id for item in self.evidence_groups)
        if group_ids != tuple(sorted(set(group_ids))):
            failures.append("CAUSAL_RECORD_EVIDENCE_GROUPS_INVALID")
        if any(
            item.normalized_before_pattern_digest
            != self.binding_key.normalized_state_pattern_digest
            or item.action_relation_digest
            != self.binding_key.action_relation_digest
            for item in self.evidence_groups
        ):
            failures.append("CAUSAL_RECORD_EVIDENCE_BINDING_MISMATCH")
        try:
            evaluation = selected_policy.evaluate(
                self.evidence_groups,
                scope_class=self.scope_class,
            )
        except (TypeError, ValueError):
            failures.append("CAUSAL_RECORD_EVIDENCE_POLICY_INVALID")
        else:
            expected_values = {
                "state": evaluation.state,
                "support_group_ids": evaluation.support_group_ids,
                "contradiction_group_ids": (
                    evaluation.contradiction_group_ids
                ),
                "hazard_group_ids": evaluation.hazard_group_ids,
                "no_effect_group_ids": evaluation.no_effect_group_ids,
                "support_count": evaluation.support_count,
                "contradiction_count": evaluation.contradiction_count,
                "hazard_count": evaluation.hazard_count,
                "no_effect_count": evaluation.no_effect_count,
                "distinct_episode_support": (
                    evaluation.distinct_episode_support
                ),
                "confidence_ppm": evaluation.confidence_ppm,
                "execute_eligibility": evaluation.execute_eligibility,
                "probe_eligibility": evaluation.probe_eligibility,
            }
            for name, expected in expected_values.items():
                if getattr(self, name) != expected:
                    failures.append("CAUSAL_RECORD_POLICY_MISMATCH:" + name)
        if (
            not self.precondition_program_digest
            or not self.predicted_effect_program_digest
            or not self.provenance_digest
        ):
            failures.append("CAUSAL_RECORD_DIGEST_MISSING")
        payload_keys = tuple(key for key, _ in self.payload_items)
        if payload_keys != tuple(sorted(set(payload_keys))):
            failures.append("CAUSAL_RECORD_PAYLOAD_INVALID")
        if self.scope_class == "SESSION_GLOBAL":
            searchable = " ".join(
                (
                    self.statement,
                    *self.semantic_tokens,
                    *self.relations,
                    *self.applicability_predicates,
                    *(key for key, _ in self.payload_items),
                    *(
                        str(value)
                        for _, value in self.payload_items
                        if isinstance(value, str)
                    ),
                )
            ).casefold()
            if any(term in searchable for term in _FORBIDDEN_GLOBAL_FEATURE_TERMS):
                failures.append("CAUSAL_RECORD_GLOBAL_IDENTITY_FEATURE")
        return tuple(sorted(set(failures)))

    def digest(self) -> str:
        failures = self.validate()
        if failures:
            raise ValueError(";".join(failures))
        return "causal-record:" + digest_object(self)

    def to_semantic_record(self) -> SemanticRecord:
        failures = self.validate()
        if failures:
            raise ValueError(";".join(failures))
        group_payloads = tuple(
            {
                "group_id": item.group_id,
                "outcome": item.outcome,
                "normalized_before_pattern_digest": (
                    item.normalized_before_pattern_digest
                ),
                "action_relation_digest": item.action_relation_digest,
                "normalized_after_effect_digest": (
                    item.normalized_after_effect_digest
                ),
                "delay_min_steps": item.delay_min_steps,
                "delay_max_steps": item.delay_max_steps,
                "episode_nonce": item.episode_nonce,
                "event_ids": item.event_ids,
            }
            for item in self.evidence_groups
        )
        domain_payload = self.payload()
        payload: dict[str, object] = {
            **self.binding_key.payload(),
            "causal_schema_version": self.schema_version,
            "scope_class": self.scope_class,
            "precondition_program_digest": (
                self.precondition_program_digest
            ),
            "predicted_effect_program_digest": (
                self.predicted_effect_program_digest
            ),
            "delay_window": self.delay_window,
            "applicability_predicates": self.applicability_predicates,
            "evidence_event_ids": self.evidence_event_ids,
            "counter_evidence_event_ids": (
                self.counter_evidence_event_ids
            ),
            "evidence_groups": group_payloads,
            "support_group_ids": self.support_group_ids,
            "contradiction_group_ids": self.contradiction_group_ids,
            "hazard_group_ids": self.hazard_group_ids,
            "no_effect_group_ids": self.no_effect_group_ids,
            "support_count": self.support_count,
            "contradiction_count": self.contradiction_count,
            "hazard_count": self.hazard_count,
            "no_effect_count": self.no_effect_count,
            "distinct_episode_support": self.distinct_episode_support,
            "confidence_ppm": self.confidence_ppm,
            "execute_eligibility": self.execute_eligibility,
            "probe_eligibility": self.probe_eligibility,
            "provenance_digest": self.provenance_digest,
            "usage_count": self.usage_count,
            "last_verified_cycle": self.last_verified_cycle,
            "causal_payload_items": self.payload_items,
        }
        for key in (
            "decision_provenance_digest",
            "learned_effects",
            "progress_count",
            "visible_change_count",
        ):
            if key in domain_payload:
                payload[key] = domain_payload[key]
        # Compatibility counters remain derived values, never independent
        # mutable authorities.
        payload.setdefault(
            "success_count",
            domain_payload.get("progress_count", self.support_count),
        )
        payload.setdefault("visible_change_count", 0)
        return semantic_record(
            memory_id=self.record_id,
            kind=self.kind,
            statement=self.statement,
            semantic_tokens=self.semantic_tokens,
            relations=self.relations,
            evidence=self.evidence_event_ids
            or ("causal-record-without-observation-event",),
            counter_evidence=self.counter_evidence_event_ids,
            scope=(self.scope_class,),
            falsification_condition=self.falsification_condition,
            state=self.state,
            payload=payload,
        )


def _record_from_groups(
    *,
    kind: str,
    binding_key: EvidenceBindingKey,
    scope_class: str,
    statement: str,
    semantic_tokens: Sequence[str],
    relations: Sequence[str],
    applicability_predicates: Sequence[str],
    evidence_groups: Sequence[EvidenceGroup],
    falsification_condition: str,
    policy: EvidencePolicy,
    created_version: int,
    updated_version: int,
    rollback_pointer: int,
    usage_count: int,
    last_verified_cycle: int,
    payload: Mapping[str, object] | None,
) -> CausalRecord:
    ordered_groups = tuple(
        sorted(
            {item.group_id: item for item in evidence_groups}.values(),
            key=lambda item: item.group_id,
        )
    )
    evaluation = policy.evaluate(ordered_groups, scope_class=scope_class)
    event_ids = _sorted_unique(
        tuple(
            event_id
            for group in ordered_groups
            for event_id in group.event_ids
        )
    )
    counter_event_ids = _sorted_unique(
        tuple(
            event_id
            for group in ordered_groups
            if group.outcome in {"CONTRADICTION", "HAZARD", "NO_EFFECT"}
            for event_id in group.event_ids
        )
    )
    delay_window = (
        min((item.delay_min_steps for item in ordered_groups), default=0),
        max((item.delay_max_steps for item in ordered_groups), default=0),
    )
    record = CausalRecord(
        record_id=causal_record_id(
            kind=kind,
            binding_key=binding_key,
            scope_class=scope_class,
        ),
        schema_version=CAUSAL_RECORD_SCHEMA_VERSION,
        kind=kind,
        state=evaluation.state,
        scope_class=scope_class,
        binding_key=binding_key,
        statement=statement,
        semantic_tokens=_sorted_unique(tuple(semantic_tokens)),
        relations=_sorted_unique(tuple(relations)),
        precondition_program_digest=binding_key.precondition_digest,
        predicted_effect_program_digest=(
            binding_key.predicted_effect_digest
        ),
        delay_window=delay_window,
        applicability_predicates=_sorted_unique(
            tuple(applicability_predicates)
        ),
        evidence_event_ids=event_ids,
        counter_evidence_event_ids=counter_event_ids,
        evidence_groups=ordered_groups,
        support_group_ids=evaluation.support_group_ids,
        contradiction_group_ids=evaluation.contradiction_group_ids,
        hazard_group_ids=evaluation.hazard_group_ids,
        no_effect_group_ids=evaluation.no_effect_group_ids,
        support_count=evaluation.support_count,
        contradiction_count=evaluation.contradiction_count,
        hazard_count=evaluation.hazard_count,
        no_effect_count=evaluation.no_effect_count,
        distinct_episode_support=evaluation.distinct_episode_support,
        confidence_ppm=evaluation.confidence_ppm,
        execute_eligibility=evaluation.execute_eligibility,
        probe_eligibility=evaluation.probe_eligibility,
        falsification_condition=falsification_condition,
        created_version=created_version,
        updated_version=updated_version,
        rollback_pointer=rollback_pointer,
        provenance_digest="causal-provenance:"
        + digest_object(
            {
                "binding": binding_key,
                "scope": scope_class,
                "group_ids": tuple(item.group_id for item in ordered_groups),
                "policy": policy,
            }
        ),
        usage_count=usage_count,
        last_verified_cycle=last_verified_cycle,
        payload_items=tuple(sorted((payload or {}).items())),
    )
    failures = record.validate(policy=policy)
    if failures:
        raise ValueError(";".join(failures))
    return record


def causal_record(
    *,
    kind: str,
    binding_key: EvidenceBindingKey,
    scope_class: str,
    statement: str,
    semantic_tokens: Sequence[str],
    evidence_groups: Sequence[EvidenceGroup],
    falsification_condition: str,
    relations: Sequence[str] = (),
    applicability_predicates: Sequence[str] = (),
    policy: EvidencePolicy | None = None,
    created_version: int = 0,
    updated_version: int = 0,
    rollback_pointer: int = 0,
    usage_count: int = 0,
    last_verified_cycle: int = 0,
    payload: Mapping[str, object] | None = None,
) -> CausalRecord:
    selected_policy = policy or EvidencePolicy()
    return _record_from_groups(
        kind=kind,
        binding_key=binding_key,
        scope_class=scope_class,
        statement=statement,
        semantic_tokens=semantic_tokens,
        relations=relations,
        applicability_predicates=applicability_predicates,
        evidence_groups=evidence_groups,
        falsification_condition=falsification_condition,
        policy=selected_policy,
        created_version=created_version,
        updated_version=updated_version,
        rollback_pointer=rollback_pointer,
        usage_count=usage_count,
        last_verified_cycle=last_verified_cycle,
        payload=payload,
    )


def with_evidence_groups(
    record: CausalRecord,
    groups: Sequence[EvidenceGroup],
    *,
    policy: EvidencePolicy | None = None,
    scope_class: str | None = None,
) -> CausalRecord:
    selected_policy = policy or EvidencePolicy()
    merged = {
        item.group_id: item
        for item in (*record.evidence_groups, *tuple(groups))
    }
    return _record_from_groups(
        kind=record.kind,
        binding_key=record.binding_key,
        scope_class=scope_class or record.scope_class,
        statement=record.statement,
        semantic_tokens=record.semantic_tokens,
        relations=record.relations,
        applicability_predicates=record.applicability_predicates,
        evidence_groups=tuple(merged.values()),
        falsification_condition=record.falsification_condition,
        policy=selected_policy,
        created_version=record.created_version,
        updated_version=record.updated_version,
        rollback_pointer=record.rollback_pointer,
        usage_count=record.usage_count,
        last_verified_cycle=record.last_verified_cycle,
        payload=record.payload(),
    )


def _sequence(value: object, name: str) -> tuple[object, ...]:
    if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
        raise TypeError("CAUSAL_RECORD_SEQUENCE_INVALID:" + name)
    return tuple(value)


def _nonnegative_integer(value: object, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise TypeError("CAUSAL_RECORD_INTEGER_INVALID:" + name)
    return value


def causal_record_from_semantic(
    record: SemanticRecord,
    *,
    policy: EvidencePolicy | None = None,
) -> CausalRecord:
    payload = record.payload()
    if payload.get("causal_schema_version") != CAUSAL_RECORD_SCHEMA_VERSION:
        raise TypeError("SEMANTIC_RECORD_IS_NOT_TYPED_CAUSAL")
    binding_key = binding_key_from_payload(payload)
    if binding_key is None:
        raise TypeError("CAUSAL_RECORD_BINDING_KEY_MISSING")
    group_values = _sequence(payload.get("evidence_groups", ()), "groups")
    groups: list[EvidenceGroup] = []
    for value in group_values:
        if not isinstance(value, Mapping):
            raise TypeError("CAUSAL_RECORD_EVIDENCE_GROUP_INVALID")
        event_ids = _sequence(value.get("event_ids", ()), "event_ids")
        group = EvidenceGroup(
            group_id=str(value["group_id"]),
            outcome=str(value["outcome"]),
            normalized_before_pattern_digest=str(
                value["normalized_before_pattern_digest"]
            ),
            action_relation_digest=str(value["action_relation_digest"]),
            normalized_after_effect_digest=str(
                value["normalized_after_effect_digest"]
            ),
            delay_min_steps=int(value["delay_min_steps"]),
            delay_max_steps=int(value["delay_max_steps"]),
            episode_nonce=str(value["episode_nonce"]),
            event_ids=tuple(str(item) for item in event_ids),
        )
        groups.append(group)
    causal_payload_values = _sequence(
        payload.get("causal_payload_items", ()),
        "causal_payload_items",
    )
    causal_payload: dict[str, object] = {}
    for item in causal_payload_values:
        values = _sequence(item, "causal_payload_item")
        if len(values) != 2:
            raise TypeError("CAUSAL_RECORD_PAYLOAD_ITEM_INVALID")
        causal_payload[str(values[0])] = values[1]
    selected_policy = policy or EvidencePolicy()
    rebuilt = _record_from_groups(
        kind=record.kind,
        binding_key=binding_key,
        scope_class=str(payload["scope_class"]),
        statement=record.statement,
        semantic_tokens=record.semantic_tokens,
        relations=record.relations,
        applicability_predicates=tuple(
            str(item)
            for item in _sequence(
                payload.get("applicability_predicates", ()),
                "applicability_predicates",
            )
        ),
        evidence_groups=groups,
        falsification_condition=record.falsification_condition,
        policy=selected_policy,
        created_version=record.created_version,
        updated_version=record.updated_version,
        rollback_pointer=record.rollback_pointer,
        usage_count=_nonnegative_integer(
            payload.get("usage_count", 0),
            "usage_count",
        ),
        last_verified_cycle=_nonnegative_integer(
            payload.get("last_verified_cycle", 0),
            "last_verified_cycle",
        ),
        payload=causal_payload,
    )
    if rebuilt.record_id != record.memory_id or rebuilt.state != record.state:
        raise ValueError("SEMANTIC_CAUSAL_RECORD_CONTENT_MISMATCH")
    return replace(
        rebuilt,
        created_version=record.created_version,
        updated_version=record.updated_version,
        rollback_pointer=record.rollback_pointer,
    )


def is_typed_causal_record(record: SemanticRecord) -> bool:
    return (
        record.payload().get("causal_schema_version")
        == CAUSAL_RECORD_SCHEMA_VERSION
    )


__all__ = [
    "CAUSAL_RECORD_KINDS",
    "CAUSAL_RECORD_SCHEMA_VERSION",
    "CausalRecord",
    "causal_record",
    "causal_record_from_semantic",
    "causal_record_id",
    "is_typed_causal_record",
    "with_evidence_groups",
]
