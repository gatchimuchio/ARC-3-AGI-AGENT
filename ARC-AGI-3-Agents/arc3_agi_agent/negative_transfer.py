"""Fail-closed controls for irrelevant, adversarial, and contradicted memory."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .causal_record import (
    causal_record_from_semantic,
    is_typed_causal_record,
)
from .evidence_binding import EvidenceBindingKey
from .generic_memory import MemoryMutationProposal, SemanticRecord
from .schema import digest_object

NEGATIVE_TRANSFER_VERSION = "arc3-negative-transfer-v1"
NEGATIVE_TRANSFER_DECISIONS = frozenset(
    {"ACCEPT", "IGNORE", "VETO", "INVALIDATE", "REJECT"}
)


@dataclass(frozen=True, slots=True)
class NegativeTransferAssessment:
    record_id: str
    decision: str
    reasons: tuple[str, ...]
    assessment_digest: str

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not self.record_id:
            failures.append("NEGATIVE_TRANSFER_RECORD_ID_MISSING")
        if self.decision not in NEGATIVE_TRANSFER_DECISIONS:
            failures.append("NEGATIVE_TRANSFER_DECISION_INVALID")
        if not self.reasons:
            failures.append("NEGATIVE_TRANSFER_REASON_MISSING")
        expected = "negative-transfer-assessment:" + digest_object(
            {
                "record_id": self.record_id,
                "decision": self.decision,
                "reasons": self.reasons,
            }
        )
        if self.assessment_digest != expected:
            failures.append("NEGATIVE_TRANSFER_DIGEST_INVALID")
        return tuple(sorted(set(failures)))


def _assessment(
    record_id: str,
    decision: str,
    reasons: Sequence[str],
) -> NegativeTransferAssessment:
    normalized_reasons = tuple(sorted(set(reasons)))
    result = NegativeTransferAssessment(
        record_id=record_id,
        decision=decision,
        reasons=normalized_reasons,
        assessment_digest="negative-transfer-assessment:"
        + digest_object(
            {
                "record_id": record_id,
                "decision": decision,
                "reasons": normalized_reasons,
            }
        ),
    )
    failures = result.validate()
    if failures:
        raise ValueError(";".join(failures))
    return result


def assess_negative_transfer(
    record: SemanticRecord,
    *,
    candidate_key: EvidenceBindingKey | None = None,
) -> NegativeTransferAssessment:
    payload = record.payload()
    if not is_typed_causal_record(record):
        if payload.get("execute_eligibility") is True:
            return _assessment(
                record.memory_id,
                "REJECT",
                ("UNTYPED_EXECUTE_ELIGIBILITY",),
            )
        return _assessment(
            record.memory_id,
            "IGNORE",
            ("UNTYPED_NONCAUSAL_RECORD",),
        )
    try:
        causal = causal_record_from_semantic(record)
    except (KeyError, TypeError, ValueError):
        return _assessment(
            record.memory_id,
            "REJECT",
            ("TYPED_CAUSAL_SCHEMA_OR_POLICY_INVALID",),
        )
    if candidate_key is not None:
        if (
            causal.binding_key.action_relation_digest
            != candidate_key.action_relation_digest
        ):
            return _assessment(
                record.memory_id,
                "IGNORE",
                ("IRRELEVANT_ACTION_RELATION",),
            )
        if (
            causal.binding_key.precondition_digest
            != candidate_key.precondition_digest
        ):
            return _assessment(
                record.memory_id,
                "IGNORE",
                ("IRRELEVANT_PRECONDITION",),
            )
    if causal.hazard_count > 0:
        return _assessment(
            record.memory_id,
            "VETO",
            ("EXACT_HAZARD_EVIDENCE",),
        )
    if causal.state in {"SUSPENDED", "REJECTED"}:
        return _assessment(
            record.memory_id,
            "INVALIDATE",
            ("CONTRADICTION_POLICY_INVALIDATED",),
        )
    if causal.execute_eligibility and (
        causal.support_count < 2
        or causal.contradiction_count > 0
        or causal.hazard_count > 0
    ):
        return _assessment(
            record.memory_id,
            "REJECT",
            ("EXECUTE_ELIGIBILITY_INVARIANT_INVALID",),
        )
    return _assessment(record.memory_id, "ACCEPT", ("CAUSAL_POLICY_VALID",))


def invalidation_proposal(
    record: SemanticRecord,
    assessment: NegativeTransferAssessment,
) -> MemoryMutationProposal:
    if assessment.record_id != record.memory_id:
        raise ValueError("NEGATIVE_TRANSFER_ASSESSMENT_TARGET_MISMATCH")
    if assessment.decision not in {"INVALIDATE", "REJECT", "VETO"}:
        raise ValueError("NEGATIVE_TRANSFER_INVALIDATION_NOT_REQUIRED")
    return MemoryMutationProposal(
        operation="INVALIDATE",
        target_id=record.memory_id,
        record=None,
        evidence=(assessment.assessment_digest,),
        counter_evidence=assessment.reasons,
        scope=("negative-transfer-control",),
        falsification_condition=(
            "new independent causal support resolves every invalidation reason"
        ),
        reason="invalidate negative-transfer memory under HDS policy",
    )


__all__ = [
    "NEGATIVE_TRANSFER_DECISIONS",
    "NEGATIVE_TRANSFER_VERSION",
    "NegativeTransferAssessment",
    "assess_negative_transfer",
    "invalidation_proposal",
]
