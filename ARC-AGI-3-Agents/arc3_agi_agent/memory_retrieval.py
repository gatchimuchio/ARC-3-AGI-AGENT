"""Tiered causal-memory retrieval with auditable score decomposition."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .causal_record import (
    causal_record_from_semantic,
    is_typed_causal_record,
)
from .generic_memory import SemanticRecord
from .schema import digest_object

MEMORY_RETRIEVAL_VERSION = "arc3-memory-retrieval-v1"
_GENERIC_QUERY_TOKENS = frozenset(
    {"goal:progress", "value:information", "boundary:reversible"}
)


@dataclass(frozen=True, slots=True)
class RetrievalScoreBreakdown:
    record_id: str
    match_tier: str
    relevance: int
    precondition_fit: int
    effect_compatibility: int
    scope_fitness: int
    support: int
    confidence: int
    recency: int
    historical_utility: int
    contradiction_penalty: int
    hazard_penalty: int
    stale_penalty: int
    total_score: int
    applicability_passed: bool
    execute_eligible: bool
    probe_only: bool
    rejection_reasons: tuple[str, ...]

    def digest(self) -> str:
        return "memory-retrieval-score:" + digest_object(self)


def _counter(record: SemanticRecord, name: str) -> int:
    value = record.payload().get(name, 0)
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return 0


def rank_memory_records(
    *,
    records: Sequence[SemanticRecord],
    query_tokens: Sequence[str],
    kinds: Sequence[str],
    current_version: int,
    limit: int,
) -> tuple[
    tuple[SemanticRecord, ...],
    tuple[RetrievalScoreBreakdown, ...],
]:
    """Rank records without using identity, game order, or episode nonce."""

    query_set = set(query_tokens)
    informative_query = query_set.difference(_GENERIC_QUERY_TOKENS)
    selected_kinds = set(kinds)
    ranked: list[tuple[RetrievalScoreBreakdown, SemanticRecord]] = []
    for record in records:
        if selected_kinds and record.kind not in selected_kinds:
            continue
        semantic_overlap = informative_query.intersection(
            record.semantic_tokens
        )
        relation_overlap = query_set.intersection(record.relations)
        causal = is_typed_causal_record(record)
        if not semantic_overlap and not relation_overlap:
            # A generic goal token alone cannot make an unrelated prior
            # retrievable.
            if informative_query:
                continue
            if not query_set.intersection(record.semantic_tokens):
                continue

        rejection_reasons: list[str] = []
        applicability_passed = True
        execute_eligible = False
        support_count = _counter(record, "support_count")
        contradiction_count = _counter(record, "contradiction_count")
        hazard_count = _counter(record, "hazard_count")
        confidence_ppm = _counter(record, "confidence_ppm")
        usage_count = _counter(record, "usage_count")
        if causal:
            try:
                typed = causal_record_from_semantic(record)
            except (KeyError, TypeError, ValueError):
                rejection_reasons.append("TYPED_CAUSAL_RECORD_INVALID")
                continue
            support_count = typed.support_count
            contradiction_count = typed.contradiction_count
            hazard_count = typed.hazard_count
            confidence_ppm = typed.confidence_ppm
            usage_count = typed.usage_count
            execute_eligible = typed.execute_eligibility
            if typed.state == "REJECTED":
                rejection_reasons.append("RECORD_REJECTED")
                continue
            if typed.state == "SUSPENDED" and typed.hazard_count == 0:
                # Invalidated negative transfer remains in history but cannot
                # perturb candidate ranking.
                rejection_reasons.append("NEGATIVE_TRANSFER_SUSPENDED")
                continue
            if typed.scope_class not in {
                "LEVEL_OVERLAY",
                "EPISODE_OVERLAY",
                "SESSION_GLOBAL",
            }:
                applicability_passed = False
                rejection_reasons.append("SCOPE_NOT_APPLICABLE")
        else:
            if record.payload().get("execute_eligibility") is True:
                # P19 forbids untyped records from claiming action authority.
                continue
            if record.state in {"REJECTED", "ARCHIVED", "SUPERSEDED"}:
                continue

        if relation_overlap and semantic_overlap:
            tier = "TIER_0_EXACT"
        elif relation_overlap or len(semantic_overlap) >= 2:
            tier = "TIER_1_NORMALIZED"
        elif causal and semantic_overlap:
            tier = "TIER_2_CAUSAL"
        else:
            tier = "TIER_3_SEMANTIC"
        relevance = 120 * len(semantic_overlap) + 180 * len(
            relation_overlap
        )
        precondition_fit = (
            300 if tier in {"TIER_0_EXACT", "TIER_1_NORMALIZED"} else 0
        )
        effect_compatibility = (
            220
            if causal
            and record.payload().get("predicted_effect_program_digest")
            else 0
        )
        scope_value = record.payload().get("scope_class")
        scope_fitness = (
            220
            if scope_value == "SESSION_GLOBAL"
            else 160
            if scope_value in {"EPISODE_OVERLAY", "LEVEL_OVERLAY"}
            else 40
        )
        support = min(400, support_count * 80)
        confidence = min(200, confidence_ppm // 5_000)
        recency = max(0, 80 - max(0, current_version - record.updated_version))
        historical_utility = min(100, usage_count * 10)
        contradiction_penalty = contradiction_count * 240
        hazard_penalty = hazard_count * 800
        stale_penalty = max(0, current_version - record.updated_version - 64)
        total_score = (
            relevance
            + precondition_fit
            + effect_compatibility
            + scope_fitness
            + support
            + confidence
            + recency
            + historical_utility
            - contradiction_penalty
            - hazard_penalty
            - stale_penalty
        )
        probe_only = bool(
            tier == "TIER_3_SEMANTIC"
            or record.state in {"PROPOSED", "PROBATION"}
            or not execute_eligible
        )
        breakdown = RetrievalScoreBreakdown(
            record_id=record.memory_id,
            match_tier=tier,
            relevance=relevance,
            precondition_fit=precondition_fit,
            effect_compatibility=effect_compatibility,
            scope_fitness=scope_fitness,
            support=support,
            confidence=confidence,
            recency=recency,
            historical_utility=historical_utility,
            contradiction_penalty=contradiction_penalty,
            hazard_penalty=hazard_penalty,
            stale_penalty=stale_penalty,
            total_score=total_score,
            applicability_passed=applicability_passed,
            execute_eligible=execute_eligible,
            probe_only=probe_only,
            rejection_reasons=tuple(sorted(set(rejection_reasons))),
        )
        ranked.append((breakdown, record))
    ranked.sort(
        key=lambda item: (
            -item[0].total_score,
            item[0].probe_only,
            -item[1].updated_version,
            item[1].memory_id,
        )
    )
    bounded = tuple(ranked[:limit])
    return (
        tuple(record for _, record in bounded),
        tuple(breakdown for breakdown, _ in bounded),
    )


__all__ = [
    "MEMORY_RETRIEVAL_VERSION",
    "RetrievalScoreBreakdown",
    "rank_memory_records",
]
