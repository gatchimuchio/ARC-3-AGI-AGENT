"""Candidate-specific evidence keys and fail-closed matching predicates."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Mapping, Protocol, Sequence

from .schema import digest_object

EVIDENCE_BINDING_VERSION = "arc3-candidate-evidence-binding-v1"
MIN_EXECUTE_SUPPORT = 2
MIN_EXECUTE_CONFIDENCE_PPM = 750_000
EVIDENCE_MATCH_TIERS = frozenset(
    {"TIER_0_EXACT", "TIER_1_NORMALIZED", "TIER_2_CAUSAL", "TIER_3_SEMANTIC"}
)


class EvidenceRecord(Protocol):
    @property
    def memory_id(self) -> str: ...

    @property
    def kind(self) -> str: ...

    @property
    def state(self) -> str: ...

    def payload(self) -> dict[str, object]: ...

    def citation(self) -> object: ...


@dataclass(frozen=True, slots=True)
class EvidenceBindingKey:
    normalized_state_pattern_digest: str
    action_relation_digest: str
    precondition_digest: str
    predicted_effect_digest: str
    applicability_scope_digest: str

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        for name in (
            "normalized_state_pattern_digest",
            "action_relation_digest",
            "precondition_digest",
            "predicted_effect_digest",
            "applicability_scope_digest",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                failures.append("EVIDENCE_BINDING_KEY_MISSING:" + name)
        return tuple(failures)

    def digest(self) -> str:
        failures = self.validate()
        if failures:
            raise ValueError(";".join(failures))
        return "evidence-binding-key:" + digest_object(self)

    def payload(self) -> dict[str, str]:
        return {
            "normalized_state_pattern_digest": (
                self.normalized_state_pattern_digest
            ),
            "action_relation_digest": self.action_relation_digest,
            "precondition_digest": self.precondition_digest,
            "predicted_effect_digest": self.predicted_effect_digest,
            "applicability_scope_digest": self.applicability_scope_digest,
        }


@dataclass(frozen=True, slots=True)
class CandidateEvidenceBinding:
    key: EvidenceBindingKey
    record_id: str
    record_digest: str
    match_tier: str
    precondition_match: bool
    effect_compatible: bool
    scope_applicable: bool
    support_count: int
    contradiction_count: int
    hazard_count: int
    confidence_ppm: int
    execute_eligible: bool
    rejection_reasons: tuple[str, ...] = ()

    def validate(self) -> tuple[str, ...]:
        failures = list(self.key.validate())
        if not self.record_id or not self.record_digest:
            failures.append("CANDIDATE_EVIDENCE_RECORD_REF_MISSING")
        if self.match_tier not in EVIDENCE_MATCH_TIERS:
            failures.append("CANDIDATE_EVIDENCE_MATCH_TIER_INVALID")
        for name in (
            "support_count",
            "contradiction_count",
            "hazard_count",
            "confidence_ppm",
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
            ):
                failures.append("CANDIDATE_EVIDENCE_COUNTER_INVALID:" + name)
        if self.confidence_ppm > 1_000_000:
            failures.append("CANDIDATE_EVIDENCE_CONFIDENCE_INVALID")
        if self.execute_eligible and (
            not self.precondition_match
            or not self.effect_compatible
            or not self.scope_applicable
            or self.hazard_count != 0
            or self.contradiction_count != 0
            or self.support_count < MIN_EXECUTE_SUPPORT
            or self.confidence_ppm < MIN_EXECUTE_CONFIDENCE_PPM
        ):
            failures.append("CANDIDATE_EVIDENCE_EXECUTE_INVARIANT_INVALID")
        if self.rejection_reasons != tuple(sorted(set(self.rejection_reasons))):
            failures.append("CANDIDATE_EVIDENCE_REJECTIONS_INVALID")
        return tuple(sorted(set(failures)))


@dataclass(frozen=True, slots=True)
class TypedCandidateProvenance:
    p_instruction_refs: tuple[str, ...]
    representation_refs: tuple[str, ...]
    prediction_refs: tuple[str, ...]
    memory_binding_refs: tuple[str, ...]
    counter_evidence_refs: tuple[str, ...]
    runtime_version: str

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        for name in (
            "p_instruction_refs",
            "representation_refs",
            "prediction_refs",
            "memory_binding_refs",
            "counter_evidence_refs",
        ):
            values = getattr(self, name)
            if values != tuple(sorted(set(values))):
                failures.append("CANDIDATE_PROVENANCE_INVALID:" + name)
        if not self.p_instruction_refs:
            failures.append("CANDIDATE_PROVENANCE_P_REF_MISSING")
        if not self.representation_refs:
            failures.append("CANDIDATE_PROVENANCE_REPRESENTATION_REF_MISSING")
        if not self.prediction_refs:
            failures.append("CANDIDATE_PROVENANCE_PREDICTION_REF_MISSING")
        if not self.runtime_version:
            failures.append("CANDIDATE_PROVENANCE_RUNTIME_MISSING")
        return tuple(sorted(set(failures)))


def _relation_without_surface_ordinal(value: str) -> str:
    return re.sub(r"^surface:\d+:", "surface:dynamic:", value)


def build_evidence_binding_key(
    *,
    topology_tokens: Sequence[str],
    relations: Sequence[str],
    descriptor_semantic_key: str,
    action_id: int,
    target_role: str | None,
    payload_fields: Sequence[str],
    predicted_effects: Sequence[str],
    scope_class: str = "EPISODE_OVERLAY",
) -> EvidenceBindingKey:
    """Build an identity-free key without literal coordinate values."""

    normalized_topology = tuple(sorted(set(topology_tokens)))
    normalized_relations = tuple(sorted(set(relations)))
    normalized_payload_fields = tuple(sorted(set(payload_fields)))
    normalized_effects = tuple(sorted(set(predicted_effects)))
    normalized_state_pattern_digest = "state-pattern:" + digest_object(
        {
            "topology_tokens": normalized_topology,
            "relations": normalized_relations,
        }
    )
    action_relation_digest = "action-relation:" + digest_object(
        {
            "current_legal_action": action_id,
            "semantic_relation": _relation_without_surface_ordinal(
                descriptor_semantic_key
            ),
            "target_role": target_role or "UNTARGETED",
            "dynamic_anchor_class": (
                "CURRENT_RENDER_ROLE_ANCHOR"
                if {"x", "y"}.issubset(normalized_payload_fields)
                else "NO_COORDINATE_ANCHOR"
            ),
            "payload_fields": normalized_payload_fields,
            "effect_binding_class": (
                "PREDICTED_EFFECT_FAMILY" if normalized_effects else "OPEN_EFFECT"
            ),
        }
    )
    precondition_digest = "precondition:" + digest_object(
        {
            "state_pattern": normalized_state_pattern_digest,
            "target_role": target_role or "UNTARGETED",
            "payload_fields": normalized_payload_fields,
        }
    )
    predicted_effect_digest = "predicted-effect:" + digest_object(
        normalized_effects
    )
    applicability_scope_digest = "applicability-scope:" + digest_object(
        {
            "scope_class": scope_class,
            "targeted": target_role is not None,
            "payload_fields": normalized_payload_fields,
        }
    )
    return EvidenceBindingKey(
        normalized_state_pattern_digest=normalized_state_pattern_digest,
        action_relation_digest=action_relation_digest,
        precondition_digest=precondition_digest,
        predicted_effect_digest=predicted_effect_digest,
        applicability_scope_digest=applicability_scope_digest,
    )


def binding_key_from_payload(
    payload: Mapping[str, object],
) -> EvidenceBindingKey | None:
    names = (
        "normalized_state_pattern_digest",
        "action_relation_digest",
        "precondition_digest",
        "predicted_effect_digest",
        "applicability_scope_digest",
    )
    values = {name: payload.get(name) for name in names}
    if not all(isinstance(value, str) and value for value in values.values()):
        return None
    return EvidenceBindingKey(
        normalized_state_pattern_digest=str(
            values["normalized_state_pattern_digest"]
        ),
        action_relation_digest=str(values["action_relation_digest"]),
        precondition_digest=str(values["precondition_digest"]),
        predicted_effect_digest=str(values["predicted_effect_digest"]),
        applicability_scope_digest=str(
            values["applicability_scope_digest"]
        ),
    )


def record_matches_binding_prefix(
    record: EvidenceRecord,
    key: EvidenceBindingKey,
) -> bool:
    record_key = binding_key_from_payload(record.payload())
    return bool(
        record_key is not None
        and record_key.normalized_state_pattern_digest
        == key.normalized_state_pattern_digest
        and record_key.action_relation_digest == key.action_relation_digest
        and record_key.precondition_digest == key.precondition_digest
        and record_key.applicability_scope_digest
        == key.applicability_scope_digest
    )


def _counter(payload: Mapping[str, object], name: str) -> int:
    value = payload.get(name, 0)
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return 0


def bind_candidate_records(
    *,
    key: EvidenceBindingKey,
    records: Sequence[EvidenceRecord],
) -> tuple[CandidateEvidenceBinding, ...]:
    bindings: list[CandidateEvidenceBinding] = []
    for record in records:
        payload = record.payload()
        record_key = binding_key_from_payload(payload)
        if (
            record_key is None
            or record_key.action_relation_digest
            != key.action_relation_digest
        ):
            continue
        state_match = (
            record_key.normalized_state_pattern_digest
            == key.normalized_state_pattern_digest
        )
        precondition_match = (
            state_match
            and record_key.precondition_digest == key.precondition_digest
        )
        effect_compatible = (
            record_key.predicted_effect_digest
            == key.predicted_effect_digest
        )
        scope_applicable = (
            record_key.applicability_scope_digest
            == key.applicability_scope_digest
        )
        support_count = _counter(payload, "support_count")
        contradiction_count = _counter(payload, "contradiction_count")
        hazard_count = _counter(payload, "hazard_count")
        confidence_ppm = min(
            1_000_000,
            _counter(payload, "confidence_ppm"),
        )
        rejection_reasons: list[str] = []
        if not state_match:
            rejection_reasons.append("STATE_PATTERN_MISMATCH")
        if not precondition_match:
            rejection_reasons.append("PRECONDITION_MISMATCH")
        if not effect_compatible:
            rejection_reasons.append("EFFECT_MISMATCH")
        if not scope_applicable:
            rejection_reasons.append("SCOPE_MISMATCH")
        if record.state != "ACTIVE":
            rejection_reasons.append("RECORD_NOT_ACTIVE")
        if hazard_count:
            rejection_reasons.append("HAZARD_EXACT_MATCH")
        if contradiction_count:
            rejection_reasons.append("CONTRADICTION_PRESENT")
        if support_count < MIN_EXECUTE_SUPPORT:
            rejection_reasons.append("SUPPORT_INSUFFICIENT")
        if confidence_ppm < MIN_EXECUTE_CONFIDENCE_PPM:
            rejection_reasons.append("CONFIDENCE_INSUFFICIENT")
        requested_execute = payload.get("execute_eligibility") is True
        execute_eligible = bool(
            requested_execute
            and record.state == "ACTIVE"
            and precondition_match
            and effect_compatible
            and scope_applicable
            and hazard_count == 0
            and contradiction_count == 0
            and support_count >= MIN_EXECUTE_SUPPORT
            and confidence_ppm >= MIN_EXECUTE_CONFIDENCE_PPM
        )
        citation = record.citation()
        record_digest = getattr(citation, "content_digest", "")
        if not isinstance(record_digest, str) or not record_digest:
            raise ValueError("CANDIDATE_EVIDENCE_CITATION_DIGEST_MISSING")
        if precondition_match and effect_compatible and scope_applicable:
            match_tier = "TIER_0_EXACT"
        elif precondition_match and scope_applicable:
            match_tier = "TIER_1_NORMALIZED"
        elif state_match or effect_compatible:
            match_tier = "TIER_2_CAUSAL"
        else:
            match_tier = "TIER_3_SEMANTIC"
        binding = CandidateEvidenceBinding(
            key=key,
            record_id=record.memory_id,
            record_digest=record_digest,
            match_tier=match_tier,
            precondition_match=precondition_match,
            effect_compatible=effect_compatible,
            scope_applicable=scope_applicable,
            support_count=support_count,
            contradiction_count=contradiction_count,
            hazard_count=hazard_count,
            confidence_ppm=confidence_ppm,
            execute_eligible=execute_eligible,
            rejection_reasons=tuple(sorted(set(rejection_reasons))),
        )
        failures = binding.validate()
        if failures:
            raise ValueError(";".join(failures))
        bindings.append(binding)
    return tuple(
        sorted(
            bindings,
            key=lambda item: (
                not item.execute_eligible,
                item.hazard_count > 0,
                -item.support_count,
                -item.confidence_ppm,
                item.record_id,
            ),
        )
    )


def candidate_reproduced(
    bindings: Sequence[CandidateEvidenceBinding],
    *,
    retrieved_citation_digests: Sequence[str],
) -> bool:
    citations = set(retrieved_citation_digests)
    return any(
        binding.record_digest in citations
        and binding.precondition_match
        and binding.effect_compatible
        and binding.scope_applicable
        and binding.execute_eligible
        and binding.hazard_count == 0
        and binding.contradiction_count == 0
        for binding in bindings
    )


def candidate_hazard_veto(
    bindings: Sequence[CandidateEvidenceBinding],
) -> bool:
    return any(
        binding.precondition_match
        and binding.effect_compatible
        and binding.scope_applicable
        and binding.hazard_count > 0
        for binding in bindings
    )


__all__ = [
    "EVIDENCE_BINDING_VERSION",
    "EVIDENCE_MATCH_TIERS",
    "MIN_EXECUTE_CONFIDENCE_PPM",
    "MIN_EXECUTE_SUPPORT",
    "CandidateEvidenceBinding",
    "EvidenceBindingKey",
    "TypedCandidateProvenance",
    "bind_candidate_records",
    "binding_key_from_payload",
    "build_evidence_binding_key",
    "candidate_hazard_veto",
    "candidate_reproduced",
    "record_matches_binding_prefix",
]
