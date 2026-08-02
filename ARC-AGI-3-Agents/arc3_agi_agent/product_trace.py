"""Streaming plan and memory evidence for ARC3CompletionAgent."""

from __future__ import annotations

from dataclasses import dataclass, field

from .generic_types import GenericCycleTrace


@dataclass(slots=True)
class ProductTraceSummarySink:
    """Summarize every executed plan without retaining rendered cycle data."""

    citation_count: int = 0
    citation_ids: set[str] = field(default_factory=set)
    executed_plan_count: int = 0
    hds_plan_commit_count: int = 0
    initial_plan_count: int = 0
    revised_plan_count: int = 0
    rollback_plan_count: int = 0
    failed_hypothesis_invalidation_count: int = 0
    post_rollback_replan_count: int = 0
    memory_bound_plan_count: int = 0
    competing_hypothesis_plan_count: int = 0
    multi_representation_plan_count: int = 0
    subgoal_plan_count: int = 0
    max_plan_step_count: int = 0
    failure_attribution_count: int = 0

    def append(self, trace: GenericCycleTrace) -> None:
        citations = trace.compute_result.memory_citations
        self.citation_count += len(citations)
        self.citation_ids.update(item.memory_id for item in citations)
        if trace.attribution is None:
            return
        plan = (
            trace.selected_candidate.plan
            if trace.selected_candidate is not None
            else trace.compute_result.control_plan
        )
        if plan is None:
            raise RuntimeError("PRODUCT_EXECUTED_PLAN_MISSING")
        if trace.decision.selected_plan_id != plan.plan_id:
            raise RuntimeError("PRODUCT_HDS_PLAN_COMMIT_MISMATCH")
        self.executed_plan_count += 1
        self.hds_plan_commit_count += 1
        if plan.revision_reason == "INITIAL_ONLINE_PLAN":
            self.initial_plan_count += 1
        if plan.predecessor_plan_id:
            self.revised_plan_count += 1
        if plan.mode == "ROLLBACK_PLAN":
            self.rollback_plan_count += 1
        if plan.invalidated_hypothesis_refs:
            self.failed_hypothesis_invalidation_count += 1
        if plan.revision_reason == "ROLLBACK_RECOVERY_REPLAN":
            self.post_rollback_replan_count += 1
        if plan.memory_refs:
            self.memory_bound_plan_count += 1
        if len(plan.hypothesis_refs) >= 2:
            self.competing_hypothesis_plan_count += 1
        if len(plan.representation_refs) >= 2:
            self.multi_representation_plan_count += 1
        if plan.subgoal:
            self.subgoal_plan_count += 1
        self.max_plan_step_count = max(
            self.max_plan_step_count,
            len(plan.steps),
        )
        if trace.attribution.category == "FAILURE":
            self.failure_attribution_count += 1


__all__ = ["ProductTraceSummarySink"]
