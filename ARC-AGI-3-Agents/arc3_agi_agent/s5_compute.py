"""Pure-LLM calculation surface for the rendered-only S5 policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from .context import ContextSnapshot
from .instruction_body import InstructionBody
from .ir import CandidateIR, HypothesisIR, ObservationIR, OutputProposalIR
from .kernel import ComputeProposal, MemoryProposal, PureLLMCompute
from .memory import MemorySnapshot
from .protocol import ComputeRequest
from .s5_policy import (
    S5_HISTORY_TARGET,
    S5_POINTER_ACTION_ID,
    S5_RESET_ACTION_ID,
    S5InstructionQueryResult,
    S5RenderedPolicyBody,
)
from .schema import digest_object

S5_COMPUTE_VERSION = "arc3-s5-rendered-policy-compute-v1"


def _expected_effects(
    hypotheses: tuple[HypothesisIR, ...],
) -> dict[str, tuple[str, ...]]:
    return {
        item.hypothesis_id: (
            item.predictions
            if item.predictions
            else ("NO_VISIBLE_CHANGE", "VISIBLE_STATE_CHANGE")
        )
        for item in hypotheses
    }


def s5_memory_payload(
    *,
    query: S5InstructionQueryResult,
    memory: MemorySnapshot,
    policy_digest: str,
) -> dict[str, object]:
    decision = query.policy_decision
    if decision is None:
        raise ValueError("S5_POLICY_DECISION_MISSING")
    state = query.finalized_history.with_pending(
        decision.pending_record()
    )
    return state.to_payload(
        input_memory_digest=memory.digest,
        policy_digest=policy_digest,
        memory_influenced_decision=decision.memory_influenced,
    )


@dataclass(frozen=True, slots=True)
class S5RenderedCandidateSurface:
    """Materialize model output while retaining zero judgment authority."""

    role: str = "CANDIDATE_SURFACE"

    def generate(
        self,
        observation: ObservationIR,
        context: ContextSnapshot,
        hypotheses: tuple[HypothesisIR, ...],
        instruction_material: S5InstructionQueryResult,
    ) -> tuple[CandidateIR, ...]:
        del observation, context, hypotheses, instruction_material
        return ()

    def generate_policy(
        self,
        observation: ObservationIR,
        context: ContextSnapshot,
        memory: MemorySnapshot,
        hypotheses: tuple[HypothesisIR, ...],
        query: S5InstructionQueryResult,
    ) -> tuple[CandidateIR, ...]:
        decision = query.policy_decision
        if decision is None:
            raise ValueError("S5_POLICY_DECISION_MISSING")
        provenance = (
            query.query_digest,
            query.body_digest,
            decision.action_head_id,
            decision.feature_digest,
            S5_COMPUTE_VERSION,
        )
        if decision.action_id == S5_RESET_ACTION_ID:
            return tuple(
                CandidateIR(
                    candidate_id="candidate:s5-reset-control:"
                    + digest_object(
                        {
                            "observation": observation.frame_signature,
                            "memory": memory.digest,
                            "mode": mode,
                            "query": query.query_digest,
                        }
                    )[:24],
                    mode=mode,
                    steps=({"operation": mode},),
                    preconditions=(
                        "DEDICATED_HDS_RESET_CAPABILITY_REQUIRED",
                    ),
                    expected_progress=0.0,
                    expected_information_gain=0.0,
                    expected_risk=0.0,
                    repetition_cost=0.0,
                    rollback_cost=0.0,
                    provenance=provenance,
                    falsification_conditions=(
                        "rendered policy does not select compatibility reset",
                    ),
                )
                for mode in ("REOBSERVE", "SUSPEND")
            )

        action_id = decision.action_id
        if action_id not in observation.available_actions:
            raise ValueError("S5_POLICY_ACTION_UNAVAILABLE")
        step: dict[str, object] = {
            "action_id": action_id,
            "feature_digest": decision.feature_digest,
            "policy_action_head": decision.action_head_id,
            "target_palette": decision.target_palette,
        }
        if action_id == S5_POINTER_ACTION_ID:
            step.update(
                {
                    "x": decision.horizontal,
                    "y": decision.vertical,
                }
            )
        preconditions = (
            f"ACTION{action_id}_AVAILABLE",
            "RENDERED_POLICY_DECISION_PRESENT",
        )
        expected = _expected_effects(hypotheses)
        base = {
            "observation": observation.frame_signature,
            "memory": memory.digest,
            "feature": decision.feature_digest,
            "action": action_id,
        }
        primary = CandidateIR(
            candidate_id="candidate:s5-action:"
            + digest_object({**base, "mode": "ACTION"})[:24],
            mode="ACTION",
            steps=(dict(step),),
            preconditions=preconditions,
            expected_effects_by_hypothesis=expected,
            expected_progress=0.95,
            expected_information_gain=0.5,
            expected_risk=0.01,
            repetition_cost=0.0,
            rollback_cost=0.05,
            provenance=provenance,
            falsification_conditions=(
                "IRREVERSIBLE_FAILURE",
                "OBSERVED_EFFECT_CONTRADICTS_RENDERED_POLICY",
            ),
        )
        bounded_probe = CandidateIR(
            candidate_id="candidate:s5-action:"
            + digest_object({**base, "mode": "BOUNDED_PROBE"})[:24],
            mode="BOUNDED_PROBE",
            steps=(dict(step),),
            preconditions=(
                *preconditions,
                "ACTION_BUDGET_REMAINING",
            ),
            expected_effects_by_hypothesis=expected,
            expected_progress=0.4,
            expected_information_gain=0.4,
            expected_risk=0.01,
            repetition_cost=0.0,
            rollback_cost=0.05,
            provenance=provenance,
            falsification_conditions=(
                "IRREVERSIBLE_FAILURE",
                "OBSERVED_EFFECT_CONTRADICTS_RENDERED_POLICY",
            ),
        )
        del context
        return (primary, bounded_probe)


@dataclass(frozen=True, slots=True)
class S5RenderedPolicyCompute(PureLLMCompute):
    """Execute P as a subordinate calculator and proposal generator."""

    def _compute_from_request(
        self,
        request: ComputeRequest,
        observation: ObservationIR,
        context: ContextSnapshot,
        memory: MemorySnapshot,
        world_model: object,
        candidate_surface: object,
        instruction_body: InstructionBody,
    ) -> ComputeProposal:
        if not isinstance(instruction_body, S5RenderedPolicyBody):
            raise TypeError("S5 rendered policy body required")
        body_failures = instruction_body.validate()
        if body_failures:
            raise ValueError(";".join(body_failures))
        query = instruction_body.query(
            request,
            observation,
            context,
            memory,
        )
        if not isinstance(query, S5InstructionQueryResult):
            raise TypeError("S5 instruction query result required")
        query_failures = query.validate(observation)
        if query_failures:
            raise ValueError(";".join(query_failures))
        transform = getattr(world_model, "transform", None)
        generate = getattr(candidate_surface, "generate_policy", None)
        if not callable(transform):
            raise TypeError("S5 world model must be callable")
        if not callable(generate):
            raise TypeError("S5 candidate surface must be callable")
        hypotheses = transform(
            observation,
            context,
            memory,
            query,
        )
        if (
            not isinstance(hypotheses, tuple)
            or len(hypotheses) < 2
            or not all(isinstance(item, HypothesisIR) for item in hypotheses)
        ):
            raise TypeError("S5 world model hypotheses invalid")
        candidates = cast(
            tuple[CandidateIR, ...],
            generate(
                observation,
                context,
                memory,
                hypotheses,
                query,
            ),
        )
        decision = query.policy_decision
        if decision is None:
            raise ValueError("S5_POLICY_DECISION_MISSING")
        memory_payload = s5_memory_payload(
            query=query,
            memory=memory,
            policy_digest=instruction_body.digest(),
        )
        output_proposals: tuple[OutputProposalIR, ...] = ()
        if decision.action_id != S5_RESET_ACTION_ID:
            payload: dict[str, object] = {
                "action_id": decision.action_id,
                "feature_digest": decision.feature_digest,
            }
            if decision.action_id == S5_POINTER_ACTION_ID:
                payload.update(
                    {
                        "x": decision.horizontal,
                        "y": decision.vertical,
                    }
                )
            output_proposals = (
                OutputProposalIR(
                    proposal_id="output-proposal:s5:"
                    + digest_object(
                        {
                            "query": query.query_digest,
                            "memory": memory.digest,
                            "payload": payload,
                        }
                    )[:20],
                    proposal_type="rendered-policy-action-proposal",
                    payload_items=tuple(sorted(payload.items())),
                    provenance=(
                        query.query_digest,
                        instruction_body.digest(),
                        S5_COMPUTE_VERSION,
                    ),
                ),
            )
        return ComputeProposal(
            command_id=request.command_id,
            hypotheses=hypotheses,
            candidates=candidates,
            memory_proposal=MemoryProposal(
                target=S5_HISTORY_TARGET,
                payload_items=tuple(sorted(memory_payload.items())),
            ),
            memory_view_digest=memory.digest,
            memory_view_version=memory.version,
            predictions=query.predictions,
            output_proposals=output_proposals,
            uncertainty=query.uncertainty,
            provenance=(
                *query.provenance,
                S5_COMPUTE_VERSION,
            ),
            instruction_body_format=query.body_format,
            instruction_body_version=query.body_version,
            instruction_body_digest=query.body_digest,
            instruction_query_digest=query.query_digest,
        )


__all__ = [
    "S5_COMPUTE_VERSION",
    "S5RenderedCandidateSurface",
    "S5RenderedPolicyCompute",
    "s5_memory_payload",
]
