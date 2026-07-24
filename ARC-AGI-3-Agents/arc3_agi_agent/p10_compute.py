"""P10 rendered-state computation and candidate surface.

This module keeps the P1 kernel unchanged while replacing only the subordinate
compute/candidate components for complete-sample work.  The selected action is
derived from the current rendered scene and the latest HDS-approved passive
memory entry; game and level identity are neither accepted nor represented.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import cast

from .context import ContextSnapshot
from .instruction_body import InstructionBody, InstructionQueryResult
from .ir import CandidateIR, HypothesisIR, ObservationIR, OutputProposalIR
from .kernel import ComputeProposal, MemoryProposal, PureLLMCompute
from .memory import MemorySnapshot
from .p_b_learning import update_p_b_learning_memory
from .protocol import ComputeRequest
from .schema import digest_object
from .search_reset import SEARCH_RESET_REASON
from .semantic_operators import SemanticPlannerState
from .visual_explorer import (
    GLOBAL_EFFECT_DIVERSIFICATION_POLICY,
    DeterministicVisualExplorer,
    ExplorerDecision,
    Grid,
    PrototypePriorityMode,
    VisualAction,
    VisualScene,
    analyze_scene,
)

VISUAL_EXPLORER_MEMORY_FORMAT = "arc3-p10-visual-memory-v1"
VISUAL_OPERATOR_VERSION = "arc3-p10-visual-operator-v13"
VISUAL_RUNTIME_MEMORY_TARGET = "visual-runtime-state"


def _prototype_priority_mode(
    instruction_material: InstructionQueryResult,
) -> PrototypePriorityMode:
    return (
        "novelty-first"
        if any(
            instruction.operator_id
            == GLOBAL_EFFECT_DIVERSIFICATION_POLICY
            for instruction in instruction_material.operator_instructions
        )
        else "legacy"
    )


def _latest_visual_state(
    memory: MemorySnapshot,
) -> tuple[DeterministicVisualExplorer, SemanticPlannerState]:
    for entry in sorted(memory.entries, key=lambda item: item.version, reverse=True):
        payload = entry.payload
        if payload.get("format") != VISUAL_EXPLORER_MEMORY_FORMAT:
            continue
        raw_explorer = payload.get("visual_explorer")
        if not isinstance(raw_explorer, dict):
            raise ValueError("visual explorer memory payload invalid")
        raw_planner = payload.get("semantic_planner")
        if raw_planner is not None and not isinstance(raw_planner, dict):
            raise ValueError("semantic planner memory payload invalid")
        return (
            DeterministicVisualExplorer.from_payload(raw_explorer),
            (
                SemanticPlannerState()
                if raw_planner is None
                else SemanticPlannerState.from_payload(raw_planner)
            ),
        )
    return DeterministicVisualExplorer(), SemanticPlannerState()


def compile_visual_failure_payload(
    memory: MemorySnapshot,
    candidate: CandidateIR,
    result_signature: str,
) -> dict[str, object]:
    """Compile one observed hazard into identity-free passive-memory state."""

    if not candidate.steps:
        raise ValueError("failure candidate step missing")
    step = candidate.steps[0]
    raw_key = step.get("visual_action_key")
    raw_source = step.get("visual_source_signature")
    raw_action_id = step.get("action_id")
    if not isinstance(raw_key, str) or not raw_key:
        raise ValueError("failure visual action key missing")
    if not isinstance(raw_source, str) or not raw_source:
        raise ValueError("failure visual source signature missing")
    if (
        isinstance(raw_action_id, bool)
        or not isinstance(raw_action_id, int)
        or not 1 <= raw_action_id <= 7
    ):
        raise ValueError("failure visual action id invalid")
    x_value = step.get("x")
    y_value = step.get("y")
    x = x_value if isinstance(x_value, int) and not isinstance(x_value, bool) else None
    y = y_value if isinstance(y_value, int) and not isinstance(y_value, bool) else None
    action = VisualAction(
        key=raw_key,
        action_id=raw_action_id,
        group=0,
        x=x,
        y=y,
        evidence=("observed-irreversible-failure",),
    )
    explorer, semantic_planner = _latest_visual_state(memory)
    explorer.record_hazard(raw_source, action)
    target_hazard = semantic_planner.record_target_hazard()
    semantic_planner.invalidate_active_plan(
        block=target_hazard is not False
    )
    return {
        "format": VISUAL_EXPLORER_MEMORY_FORMAT,
        "input_memory_digest": memory.digest,
        "input_memory_version": memory.version,
        "memory_influenced_decision": True,
        "observed_failure_signature": result_signature,
        "operator_version": VISUAL_OPERATOR_VERSION,
        "semantic_planner": semantic_planner.to_payload(),
        "visual_explorer": explorer.to_payload(),
    }


@dataclass(frozen=True, slots=True)
class VisualSearchResetPreparation:
    """Identity-free C output consumed by the dedicated HDS reset judge."""

    reason: str
    evidence_signature: str
    memory_target: str
    memory_payload: dict[str, object]


def prepare_visual_search_reset(
    memory: MemorySnapshot,
    rendered_grid: Grid,
    available_actions: tuple[int, ...],
    *,
    terminal_state: str,
) -> VisualSearchResetPreparation | None:
    """Recompute and retain only a proven disconnected-frontier condition."""

    if terminal_state != "NOT_FINISHED":
        return None
    explorer, semantic_planner = _latest_visual_state(memory)
    fixed_mask = explorer.status_mask or None
    scene = analyze_scene(
        rendered_grid,
        available_actions,
        fixed_status_mask=fixed_mask,
    )
    explorer.observe(
        scene,
        terminal_state=terminal_state,
        level_progress=False,
    )
    decision = explorer.decide(scene)
    if decision.reason != SEARCH_RESET_REASON or decision.action is not None:
        return None
    memory_payload: dict[str, object] = {
        "format": VISUAL_EXPLORER_MEMORY_FORMAT,
        "input_memory_digest": memory.digest,
        "input_memory_version": memory.version,
        "memory_influenced_decision": decision.memory_influenced,
        "operator_version": VISUAL_OPERATOR_VERSION,
        "scene_signature": scene.signature,
        "search_reset_reason": decision.reason,
        "semantic_planner": semantic_planner.to_payload(),
        "visual_explorer": explorer.to_payload(),
    }
    evidence_signature = "search-frontier:" + digest_object(memory_payload)
    memory_target = "visual-search-reset:" + digest_object(
        {
            "memory": memory.digest,
            "scene": scene.signature,
            "evidence": evidence_signature,
        }
    )[:24]
    return VisualSearchResetPreparation(
        reason=decision.reason,
        evidence_signature=evidence_signature,
        memory_target=memory_target,
        memory_payload=memory_payload,
    )


def _expected_effects(
    hypotheses: tuple[HypothesisIR, ...],
) -> dict[str, tuple[str, ...]]:
    return {
        hypothesis.hypothesis_id: (
            hypothesis.predictions
            if hypothesis.predictions
            else ("VISIBLE_STATE_CHANGE", "NO_VISIBLE_CHANGE")
        )
        for hypothesis in hypotheses
    }


def _candidate_id(
    *,
    observation: ObservationIR,
    memory: MemorySnapshot,
    action: VisualAction,
    mode: str,
) -> str:
    return "candidate:p10-visual:" + digest_object(
        {
            "observation": observation.frame_signature,
            "memory": memory.digest,
            "action_key": action.key,
            "mode": mode,
            "operator": VISUAL_OPERATOR_VERSION,
        }
    )[:24]


@dataclass(frozen=True, slots=True)
class P10VisualCandidateSurface:
    """Materialize the explorer proposal; it owns no judgment authority."""

    role: str = "CANDIDATE_SURFACE"

    def generate(
        self,
        observation: ObservationIR,
        context: ContextSnapshot,
        hypotheses: tuple[HypothesisIR, ...],
        instruction_material: InstructionQueryResult,
    ) -> tuple[CandidateIR, ...]:
        """Reject use without the memory-bound visual planning inputs."""

        del observation, context, hypotheses, instruction_material
        return ()

    def generate_visual(
        self,
        observation: ObservationIR,
        context: ContextSnapshot,
        memory: MemorySnapshot,
        hypotheses: tuple[HypothesisIR, ...],
        instruction_material: InstructionQueryResult,
        scene: VisualScene,
        decision: ExplorerDecision,
    ) -> tuple[CandidateIR, ...]:
        action = decision.action
        if action is None:
            controls = tuple(
                control
                for control in instruction_material.controls
                if control.mode in {"SUSPEND", "STOP"}
            )
            return tuple(
                CandidateIR(
                    candidate_id="candidate:p10-control:"
                    + digest_object(
                        {
                            "observation": observation.frame_signature,
                            "memory": memory.digest,
                            "mode": control.mode,
                        }
                    )[:24],
                    mode=control.mode,
                    steps=({"operation": control.mode},),
                    preconditions=control.preconditions,
                    expected_progress=control.expected_progress,
                    expected_information_gain=control.information_gain,
                    expected_risk=control.expected_risk,
                    repetition_cost=control.repetition_cost,
                    rollback_cost=control.rollback_cost,
                    provenance=tuple(
                        sorted(
                            {
                                instruction_material.query_digest,
                                VISUAL_OPERATOR_VERSION,
                                decision.reason,
                                *control.provenance,
                            }
                        )
                    ),
                    falsification_conditions=control.falsification_conditions,
                )
                for control in controls
            )

        expected = _expected_effects(hypotheses)
        action_preconditions = (
            f"ACTION{action.action_id}_AVAILABLE",
            "RENDERED_CANDIDATE_PRESENT",
        )
        provenance = tuple(
            sorted(
                {
                    instruction_material.query_digest,
                    VISUAL_OPERATOR_VERSION,
                    decision.reason,
                    *action.evidence,
                }
            )
        )
        repetition_cost = min(
            1.0,
            context.action_history.count(action.action_id) / 16.0,
        )
        falsification_conditions = (
            "IRREVERSIBLE_FAILURE",
            "OBSERVED_EFFECT_CONTRADICTS_VISUAL_TRANSITION",
        )
        action_step: dict[str, object] = dict(action.step())
        action_step["visual_action_key"] = action.key
        action_step["visual_source_signature"] = scene.signature
        primary = CandidateIR(
            candidate_id=_candidate_id(
                observation=observation,
                memory=memory,
                action=action,
                mode="ACTION",
            ),
            mode="ACTION",
            steps=(dict(action_step),),
            preconditions=action_preconditions,
            expected_effects_by_hypothesis=expected,
            expected_progress=0.8,
            expected_information_gain=0.8,
            expected_risk=0.05,
            repetition_cost=repetition_cost,
            rollback_cost=0.1,
            provenance=provenance,
            falsification_conditions=falsification_conditions,
        )
        bounded_probe = CandidateIR(
            candidate_id=_candidate_id(
                observation=observation,
                memory=memory,
                action=action,
                mode="BOUNDED_PROBE",
            ),
            mode="BOUNDED_PROBE",
            steps=(dict(action_step),),
            preconditions=tuple(
                sorted(
                    {
                        *action_preconditions,
                        "ACTION_BUDGET_REMAINING",
                    }
                )
            ),
            expected_effects_by_hypothesis=expected,
            expected_progress=0.3,
            expected_information_gain=0.6,
            expected_risk=0.05,
            repetition_cost=repetition_cost,
            rollback_cost=0.1,
            provenance=provenance,
            falsification_conditions=falsification_conditions,
        )
        return (primary, bounded_probe)


@dataclass(frozen=True, slots=True)
class P10VisualCompute(PureLLMCompute):
    """Pure calculator that reads M and proposes one rendered-state action."""

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
        body_failures = instruction_body.validate()
        if body_failures:
            raise ValueError(";".join(body_failures))
        query = instruction_body.query(
            request,
            observation,
            context,
            memory,
        )
        if not isinstance(query, InstructionQueryResult):
            raise TypeError("instruction body query must return InstructionQueryResult")
        query_failures = query.validate(observation)
        if query_failures:
            raise ValueError(";".join(query_failures))

        transform = getattr(world_model, "transform", None)
        generate_visual = getattr(candidate_surface, "generate_visual", None)
        if not callable(transform):
            raise TypeError("world model must be callable")
        if not callable(generate_visual):
            raise TypeError("P10 visual candidate surface must be callable")
        hypotheses = transform(
            observation,
            context,
            memory,
            query,
        )
        if not isinstance(hypotheses, tuple):
            raise TypeError("world model hypotheses must be a tuple")
        if not observation.rendered_layers:
            raise ValueError("P10 rendered observation missing")

        explorer, semantic_planner = _latest_visual_state(memory)
        progress = "LEVEL_PROGRESS" in observation.visible_effects
        fixed_mask = (
            None
            if progress or not explorer.status_mask
            else explorer.status_mask
        )
        scene = analyze_scene(
            observation.rendered_layers[-1],
            observation.available_actions,
            fixed_status_mask=fixed_mask,
        )
        explorer.observe(
            scene,
            terminal_state=observation.terminal_state,
            level_progress=progress,
        )
        if progress:
            semantic_planner.reset_after_progress()
        terminal = observation.terminal_state in {"WIN", "GAME_OVER"}
        semantic_decision = (
            None
            if terminal
            else semantic_planner.decide(
                observation.rendered_layers[-1],
                observation.available_actions,
                query.operator_instructions,
                source_signature=scene.signature,
            )
        )
        if (
            semantic_decision is not None
            and semantic_decision.action is not None
            and explorer.stage_action(scene, semantic_decision.action)
        ):
            explorer_decision = ExplorerDecision(
                action=semantic_decision.action,
                reason=semantic_decision.reason,
                memory_influenced=semantic_decision.memory_influenced,
                frontier_distance=None,
            )
        else:
            if (
                semantic_decision is not None
                and semantic_decision.action is not None
            ):
                semantic_planner.invalidate_active_plan()
            explorer_decision = (
                ExplorerDecision(
                    action=None,
                    reason="TERMINAL_OBSERVATION",
                    memory_influenced=bool(memory.entries),
                    frontier_distance=None,
                )
                if terminal
                else explorer.decide(
                    scene,
                    prototype_priority_mode=_prototype_priority_mode(query),
                )
            )
        candidates = cast(
            tuple[CandidateIR, ...],
            generate_visual(
                observation,
                context,
                memory,
                hypotheses,
                query,
                scene,
                explorer_decision,
            ),
        )
        memory_proposal = MemoryProposal(
            target=VISUAL_RUNTIME_MEMORY_TARGET,
            payload_items=(
                ("format", VISUAL_EXPLORER_MEMORY_FORMAT),
                ("input_memory_digest", memory.digest),
                ("input_memory_version", memory.version),
                (
                    "memory_influenced_decision",
                    explorer_decision.memory_influenced,
                ),
                ("operator_version", VISUAL_OPERATOR_VERSION),
                (
                    "p_b_learning",
                    update_p_b_learning_memory(
                        memory,
                        observation,
                        context,
                        query,
                        selected_action_id=(
                            explorer_decision.action.action_id
                            if explorer_decision.action is not None
                            else None
                        ),
                    ),
                ),
                ("scene_signature", scene.signature),
                ("semantic_planner", semantic_planner.to_payload()),
                ("visual_explorer", explorer.to_payload()),
            ),
        )
        output_proposals: tuple[OutputProposalIR, ...] = ()
        if explorer_decision.action is not None:
            action = explorer_decision.action
            output_proposals = (
                OutputProposalIR(
                    proposal_id="output-proposal:p10-visual:"
                    + digest_object(
                        {
                            "query": query.query_digest,
                            "action": action.key,
                            "memory": memory.digest,
                        }
                    )[:20],
                    proposal_type="rendered-action-proposal",
                    payload_items=tuple(sorted(action.step().items())),
                    provenance=(
                        query.query_digest,
                        VISUAL_OPERATOR_VERSION,
                        explorer_decision.reason,
                    ),
                ),
            )
        return ComputeProposal(
            command_id=request.command_id,
            hypotheses=hypotheses,
            candidates=candidates,
            memory_proposal=memory_proposal,
            memory_view_digest=memory.digest,
            memory_view_version=memory.version,
            predictions=query.predictions,
            output_proposals=output_proposals,
            uncertainty=query.uncertainty,
            provenance=tuple(
                sorted(
                    {
                        *query.provenance,
                        VISUAL_OPERATOR_VERSION,
                        explorer_decision.reason,
                    }
                )
            ),
            instruction_body_format=query.body_format,
            instruction_body_version=query.body_version,
            instruction_body_digest=query.body_digest,
            instruction_query_digest=query.query_digest,
        )


__all__ = [
    "P10VisualCandidateSurface",
    "P10VisualCompute",
    "VISUAL_EXPLORER_MEMORY_FORMAT",
    "VISUAL_OPERATOR_VERSION",
    "VISUAL_RUNTIME_MEMORY_TARGET",
    "VisualSearchResetPreparation",
    "compile_visual_failure_payload",
    "prepare_visual_search_reset",
]
