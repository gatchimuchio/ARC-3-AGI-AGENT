"""Typed, task-identity-free intermediate representation for ARC-3."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class EntityIR:
    entity_id: str
    features: tuple[str, ...] = ()
    role_hypotheses: tuple[dict[str, Any], ...] = ()


@dataclass(frozen=True, slots=True)
class ObservationIR:
    frame_signature: str
    structural_signature: str
    mechanic_signature: str
    dimensions: tuple[int, int] | None
    available_actions: tuple[int, ...]
    visible_effects: tuple[str, ...] = ()
    entities: tuple[EntityIR, ...] = ()
    relations: tuple[str, ...] = ()
    resources: tuple[str, ...] = ()
    phase_hypotheses: tuple[str, ...] = ()
    feature_tokens: tuple[str, ...] = ()
    terminal_state: str = "UNKNOWN"
    rendered_layers: tuple[tuple[tuple[int, ...], ...], ...] = field(
        default=(),
        repr=False,
        compare=False,
        metadata={"serialize": False},
    )


@dataclass(frozen=True, slots=True)
class TransitionIR:
    before: str
    after: str | None
    action_class: str
    effects: tuple[str, ...] = ()
    progress_evidence: tuple[str, ...] = ()
    hazard_evidence: tuple[str, ...] = ()
    no_effect: bool = False
    delayed_visibility: bool = False
    confidence: float = 0.0


@dataclass(frozen=True, slots=True)
class MechanicRuleIR:
    rule_id: str
    preconditions: tuple[str, ...] = ()
    action_pattern: dict[str, Any] = field(default_factory=dict)
    predicted_effects: tuple[str, ...] = ()
    goal_relevance: tuple[str, ...] = ()
    hazard_conditions: tuple[str, ...] = ()
    contradictions: tuple[str, ...] = ()
    support_count: int = 0
    confidence: float = 0.0
    revalidation_policy: str = "ALWAYS"
    runtime_safe: bool = True


@dataclass(frozen=True, slots=True)
class HypothesisIR:
    hypothesis_id: str
    hypothesis_type: str
    claims: tuple[str, ...] = ()
    predictions: tuple[str, ...] = ()
    falsification_conditions: tuple[str, ...] = ()
    support: tuple[str, ...] = ()
    contradictions: tuple[str, ...] = ()
    confidence: float = 0.0
    state: str = "ACTIVE"


@dataclass(frozen=True, slots=True)
class ActionPredictionIR:
    action_id: int
    predicted_effects: tuple[str, ...]
    progress_likelihood: float
    hazard_likelihood: float
    information_gain: float
    candidate_prior: float
    uncertainty: float
    evidence_refs: tuple[str, ...] = ()
    instruction_refs: tuple[str, ...] = ()
    preconditions: tuple[str, ...] = ()
    falsification_conditions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class OutputProposalIR:
    proposal_id: str
    proposal_type: str
    payload_items: tuple[tuple[str, object], ...]
    provenance: tuple[str, ...] = ()

    def payload(self) -> dict[str, object]:
        return dict(self.payload_items)


@dataclass(frozen=True, slots=True)
class CandidateIR:
    candidate_id: str
    mode: str
    steps: tuple[dict[str, Any], ...] = ()
    preconditions: tuple[str, ...] = ()
    expected_effects_by_hypothesis: dict[str, tuple[str, ...]] = field(
        default_factory=dict
    )
    expected_progress: float = 0.0
    expected_information_gain: float = 0.0
    expected_risk: float = 0.0
    repetition_cost: float = 0.0
    rollback_cost: float = 0.0
    provenance: tuple[str, ...] = ()
    falsification_conditions: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ClosureIR:
    candidate_id: str
    x: dict[str, Any]
    r: dict[str, Any]
    mc: dict[str, Any]
    status: str
    reason_codes: tuple[str, ...] = ()
    missing_terms: tuple[str, ...] = ()
    confidence: float = 0.0


@dataclass(frozen=True, slots=True)
class ProofObligationIR:
    obligation_id: str
    kind: str
    status: str
    missing_terms: tuple[str, ...] = ()
    reopen_condition: str = ""
    evidence_boundary: str = ""


@dataclass(frozen=True, slots=True)
class CompiledRecord:
    observation: ObservationIR
    transition: TransitionIR | None = None
    hypotheses: tuple[HypothesisIR, ...] = ()
    candidates: tuple[CandidateIR, ...] = ()
    closures: tuple[ClosureIR, ...] = ()
    proof_obligations: tuple[ProofObligationIR, ...] = ()
    evidence_state: str = "UNKNOWN"
    source_provenance_digest: str = ""


@dataclass(frozen=True, slots=True)
class KnowledgeIndexEntry:
    entry_id: str
    selectors: dict[str, Any]
    payload_type: str
    payload: dict[str, Any]
    support: int
    contradiction: int
    confidence: float
    source_provenance_digest: str
    runtime_identity_free: bool = True


__all__ = [
    "ActionPredictionIR",
    "CandidateIR",
    "ClosureIR",
    "CompiledRecord",
    "EntityIR",
    "HypothesisIR",
    "KnowledgeIndexEntry",
    "MechanicRuleIR",
    "ObservationIR",
    "OutputProposalIR",
    "ProofObligationIR",
    "TransitionIR",
]
