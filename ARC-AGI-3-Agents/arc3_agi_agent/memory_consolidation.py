"""HDS-reviewable level/episode to session-global causal consolidation."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping, Sequence

from .causal_record import (
    CausalRecord,
    causal_record,
    causal_record_from_semantic,
    causal_record_id,
    is_typed_causal_record,
)
from .evidence_policy import EvidencePolicy
from .generic_memory import MemoryMutationProposal, SemanticRecord
from .schema import digest_object

MEMORY_CONSOLIDATION_VERSION = "arc3-memory-consolidation-v1"


@dataclass(frozen=True, slots=True)
class ConsolidationPlan:
    source_record_ids: tuple[str, ...]
    rejected_record_ids: tuple[str, ...]
    proposals: tuple[MemoryMutationProposal, ...]
    probation_record_count: int
    active_record_count: int
    suspended_record_count: int
    plan_digest: str

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        for name in ("source_record_ids", "rejected_record_ids"):
            values = getattr(self, name)
            if values != tuple(sorted(set(values))):
                failures.append("CONSOLIDATION_RECORD_IDS_INVALID:" + name)
        targets = tuple(item.target_id for item in self.proposals)
        if targets != tuple(sorted(set(targets))):
            failures.append("CONSOLIDATION_TARGETS_INVALID")
        for proposal in self.proposals:
            failures.extend(proposal.validate())
            if proposal.record is None:
                failures.append("CONSOLIDATION_RECORD_REQUIRED")
                continue
            try:
                typed = causal_record_from_semantic(proposal.record)
            except (KeyError, TypeError, ValueError):
                failures.append("CONSOLIDATION_TYPED_RECORD_INVALID")
                continue
            if typed.scope_class != "SESSION_GLOBAL":
                failures.append("CONSOLIDATION_GLOBAL_SCOPE_REQUIRED")
            if (
                typed.state == "ACTIVE"
                and typed.distinct_episode_support < 2
            ):
                failures.append(
                    "CONSOLIDATION_INDEPENDENT_SUPPORT_REQUIRED"
                )
        expected = "consolidation-plan:" + digest_object(
            {
                "source_record_ids": self.source_record_ids,
                "rejected_record_ids": self.rejected_record_ids,
                "proposals": self.proposals,
                "probation_record_count": self.probation_record_count,
                "active_record_count": self.active_record_count,
                "suspended_record_count": self.suspended_record_count,
            }
        )
        if self.plan_digest != expected:
            failures.append("CONSOLIDATION_PLAN_DIGEST_INVALID")
        return tuple(sorted(set(failures)))


@dataclass(frozen=True, slots=True)
class MemoryConsolidator:
    """Pure planner. HDS remains the sole mutation authorization authority."""

    policy: EvidencePolicy = EvidencePolicy()
    version: str = MEMORY_CONSOLIDATION_VERSION

    def _globalize(
        self,
        local: CausalRecord,
        existing: CausalRecord | None,
    ) -> CausalRecord:
        groups = {
            item.group_id: item
            for item in (
                *((existing.evidence_groups) if existing is not None else ()),
                *local.evidence_groups,
            )
        }
        payload = dict(existing.payload()) if existing is not None else {}
        local_payload = local.payload()
        for key, value in local_payload.items():
            if key in {"progress_count", "visible_change_count"}:
                old_value = payload.get(key, 0)
                payload[key] = (
                    (old_value if isinstance(old_value, int) else 0)
                    + (value if isinstance(value, int) else 0)
                )
            elif key == "learned_effects":
                old_effects = payload.get(key, ())
                payload[key] = tuple(
                    sorted(
                        {
                            *(
                                str(item)
                                for item in old_effects
                                if isinstance(item, str)
                            ),
                            *(
                                str(item)
                                for item in value
                                if isinstance(item, str)
                            ),
                        }
                    )
                ) if isinstance(old_effects, (tuple, list)) and isinstance(
                    value,
                    (tuple, list),
                ) else value
            else:
                payload[key] = value
        payload.pop("observation_signature", None)
        payload.pop("game_id", None)
        payload.pop("level_id", None)
        payload.pop("task_id", None)
        return causal_record(
            kind=local.kind,
            binding_key=local.binding_key,
            scope_class="SESSION_GLOBAL",
            statement=local.statement,
            semantic_tokens=local.semantic_tokens,
            relations=local.relations,
            applicability_predicates=local.applicability_predicates,
            evidence_groups=tuple(groups.values()),
            falsification_condition=local.falsification_condition,
            policy=self.policy,
            created_version=(
                existing.created_version if existing is not None else 0
            ),
            updated_version=max(
                local.updated_version,
                existing.updated_version if existing is not None else 0,
            ),
            rollback_pointer=(
                existing.rollback_pointer if existing is not None else 0
            ),
            usage_count=(
                local.usage_count
                + (existing.usage_count if existing is not None else 0)
            ),
            last_verified_cycle=max(
                local.last_verified_cycle,
                (
                    existing.last_verified_cycle
                    if existing is not None
                    else 0
                ),
            ),
            payload=payload,
        )

    def plan(
        self,
        *,
        base_records: Sequence[SemanticRecord],
        episode_records: Sequence[SemanticRecord],
        succeeded: bool,
    ) -> ConsolidationPlan:
        if not succeeded:
            return _plan((), (), ())
        base_by_id: Mapping[str, SemanticRecord] = {
            item.memory_id: item for item in base_records
        }
        candidates: list[tuple[CausalRecord, SemanticRecord]] = []
        rejected: list[str] = []
        for record in episode_records:
            if not is_typed_causal_record(record):
                continue
            try:
                local = causal_record_from_semantic(
                    record,
                    policy=self.policy,
                )
            except (KeyError, TypeError, ValueError):
                rejected.append(record.memory_id)
                continue
            if local.scope_class not in {
                "LEVEL_OVERLAY",
                "EPISODE_OVERLAY",
            }:
                continue
            global_id = causal_record_id(
                kind=local.kind,
                binding_key=local.binding_key,
                scope_class="SESSION_GLOBAL",
            )
            existing: CausalRecord | None = None
            existing_semantic = base_by_id.get(global_id)
            if existing_semantic is not None:
                try:
                    existing = causal_record_from_semantic(
                        existing_semantic,
                        policy=self.policy,
                    )
                except (KeyError, TypeError, ValueError):
                    rejected.append(existing_semantic.memory_id)
                    continue
            try:
                global_record = self._globalize(local, existing)
            except (TypeError, ValueError):
                rejected.append(record.memory_id)
                continue
            candidates.append((global_record, record))

        merged_by_id: dict[str, CausalRecord] = {}
        source_by_id: dict[str, set[str]] = {}
        for candidate, source in candidates:
            prior = merged_by_id.get(candidate.record_id)
            if prior is not None:
                candidate = self._globalize(candidate, prior)
            merged_by_id[candidate.record_id] = candidate
            source_by_id.setdefault(candidate.record_id, set()).add(
                source.memory_id
            )

        proposals: list[MemoryMutationProposal] = []
        for record_id in sorted(merged_by_id):
            typed = merged_by_id[record_id]
            semantic = typed.to_semantic_record()
            evidence = semantic.evidence
            counter_evidence = semantic.counter_evidence or (
                "no-counter-evidence-in-consolidated-scope",
            )
            proposals.append(
                MemoryMutationProposal(
                    operation=(
                        "REVISE" if record_id in base_by_id else "ADD"
                    ),
                    target_id=record_id,
                    record=semantic,
                    evidence=evidence,
                    counter_evidence=counter_evidence,
                    scope=("SESSION_GLOBAL",),
                    falsification_condition=(
                        typed.falsification_condition
                    ),
                    reason=(
                        "consolidate normalized independent causal evidence "
                        "after successful episode"
                    ),
                    source_ids=tuple(
                        sorted(source_by_id.get(record_id, ()))
                    ),
                )
            )
        return _plan(
            tuple(
                sorted(
                    {
                        source_id
                        for values in source_by_id.values()
                        for source_id in values
                    }
                )
            ),
            tuple(sorted(set(rejected))),
            tuple(proposals),
        )


def _plan(
    source_record_ids: Sequence[str],
    rejected_record_ids: Sequence[str],
    proposals: Sequence[MemoryMutationProposal],
) -> ConsolidationPlan:
    ordered_proposals = tuple(
        sorted(proposals, key=lambda item: item.target_id)
    )
    states = tuple(
        item.record.state
        for item in ordered_proposals
        if item.record is not None
    )
    normalized_sources = tuple(sorted(set(source_record_ids)))
    normalized_rejected = tuple(sorted(set(rejected_record_ids)))
    payload = {
        "source_record_ids": normalized_sources,
        "rejected_record_ids": normalized_rejected,
        "proposals": ordered_proposals,
        "probation_record_count": states.count("PROBATION"),
        "active_record_count": states.count("ACTIVE"),
        "suspended_record_count": states.count("SUSPENDED"),
    }
    plan = ConsolidationPlan(
        source_record_ids=normalized_sources,
        rejected_record_ids=normalized_rejected,
        proposals=ordered_proposals,
        probation_record_count=states.count("PROBATION"),
        active_record_count=states.count("ACTIVE"),
        suspended_record_count=states.count("SUSPENDED"),
        plan_digest="consolidation-plan:" + digest_object(payload),
    )
    failures = plan.validate()
    if failures:
        raise ValueError(";".join(failures))
    return plan


__all__ = [
    "MEMORY_CONSOLIDATION_VERSION",
    "ConsolidationPlan",
    "MemoryConsolidator",
]
