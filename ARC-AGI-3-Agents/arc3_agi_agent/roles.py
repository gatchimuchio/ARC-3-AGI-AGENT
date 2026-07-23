"""Callable implementations of the ARC-native Layer-0 responsibilities."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .context import ContextSnapshot
from .instruction_body import InstructionQueryResult
from .ir import CandidateIR, ClosureIR, EntityIR, HypothesisIR, ObservationIR
from .memory import MemorySnapshot
from .schema import TERMINAL_STATES, digest_object, forbidden_runtime_paths
from .verification import HAZARD_EFFECTS

ROLE_FAILURE_REASONS = {
    "SYMBOL_SPACE": "SYMBOL_SPACE_REMOVED_INPUT_NOT_SYMBOLIZED",
    "CONTEXT_STATE": "CONTEXT_STATE_REMOVED_HISTORY_NOT_CONDITIONED",
    "TRANSFORM_OR_WORLD_MODEL": (
        "TRANSFORM_OR_WORLD_MODEL_REMOVED_NO_HYPOTHESIS_OR_PREDICTION"
    ),
    "CANDIDATE_SURFACE": "CANDIDATE_SURFACE_REMOVED_NO_COMPARABLE_CANDIDATES",
    "FITTING_OR_SUCCESS_CRITERION": (
        "FITTING_OR_SUCCESS_CRITERION_REMOVED_NO_CLOSURE_BASIS"
    ),
    "EMISSION_INTERFACE": "EMISSION_INTERFACE_REMOVED_NO_AUTHORIZED_BOUNDARY",
}

ACTION_MODES = frozenset({"ACTION", "BOUNDED_PROBE"})
CANDIDATE_MODES = frozenset(
    {
        "ACTION",
        "BOUNDED_PROBE",
        "REOBSERVE",
        "SUSPEND",
        "STOP",
        "ROLLBACK",
        "PLAN",
    }
)


class Layer0FunctionalLoss(RuntimeError):
    """Observable loss at one callable responsibility boundary."""

    def __init__(
        self,
        role: str,
        reason: str,
        *,
        stage: str,
        removed: bool,
    ) -> None:
        self.role = role
        self.reason = reason
        self.stage = stage
        self.removed = removed
        super().__init__(reason)


def _string_tuple(value: object) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return ()
    return tuple(str(item).strip() for item in value if str(item).strip())


def _dimensions(value: object) -> tuple[int, int] | None:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        return None
    converted = tuple(int(item) for item in value)
    if len(converted) != 2 or any(item <= 0 for item in converted):
        return None
    return (converted[0], converted[1])


@dataclass(frozen=True, slots=True)
class DeterministicSymbolSpace:
    """Normalize current rendered input into a stable, reusable alphabet."""

    role: str = "SYMBOL_SPACE"

    def encode(self, raw: Mapping[str, object]) -> ObservationIR:
        forbidden = forbidden_runtime_paths(raw)
        if forbidden:
            raise ValueError(
                "FORBIDDEN_RUNTIME_IDENTITY:" + ",".join(forbidden)
            )

        raw_frame = raw.get("frame")
        frame_signature = str(raw.get("frame_signature", "")).strip()
        if not frame_signature and raw_frame is not None:
            frame_signature = f"frame:{digest_object(raw_frame)[:20]}"

        dimensions = _dimensions(raw.get("dimensions"))
        relations = tuple(sorted(set(_string_tuple(raw.get("relations")))))
        resources = tuple(sorted(set(_string_tuple(raw.get("resources")))))
        visible_effects = tuple(
            sorted(str(item).upper() for item in _string_tuple(raw.get("effects")))
        )
        action_values = raw.get("available_actions", ())
        if not isinstance(action_values, Sequence) or isinstance(
            action_values,
            (str, bytes, bytearray),
        ):
            action_values = ()
        available_actions = tuple(
            sorted(
                {
                    int(action)
                    for action in action_values
                    if (
                        isinstance(action, int)
                        and not isinstance(action, bool)
                        and 1 <= int(action) <= 7
                    )
                }
            )
        )

        entities: list[EntityIR] = []
        entity_values = raw.get("objects", raw.get("entities", ()))
        if isinstance(entity_values, Sequence) and not isinstance(
            entity_values, (str, bytes, bytearray)
        ):
            for index, value in enumerate(entity_values):
                if isinstance(value, Mapping):
                    entity_id = str(
                        value.get("entity_id", value.get("object_id", f"entity:{index}"))
                    )
                    features = _string_tuple(value.get("features", ()))
                else:
                    entity_id = f"entity:{index}"
                    features = (str(value),)
                entities.append(
                    EntityIR(
                        entity_id=entity_id,
                        features=tuple(sorted(set(features))),
                    )
                )

        structural_signature = str(raw.get("structural_signature", "")).strip()
        if not structural_signature and any(
            (dimensions, entities, relations, resources)
        ):
            structural_signature = (
                "structure:"
                + digest_object(
                    {
                        "dimensions": dimensions,
                        "entities": entities,
                        "relations": relations,
                        "resources": resources,
                    }
                )[:20]
            )

        mechanic_signature = str(raw.get("mechanic_signature", "")).strip()
        if not mechanic_signature:
            mechanic_signature = "mechanic:unobserved"

        feature_tokens = tuple(
            sorted(
                set(_string_tuple(raw.get("feature_tokens")))
                | {f"effect:{effect}" for effect in visible_effects}
            )
        )
        terminal_state = str(raw.get("terminal_state", "UNKNOWN")).upper().strip()
        if terminal_state not in TERMINAL_STATES:
            terminal_state = "UNKNOWN"

        return ObservationIR(
            frame_signature=frame_signature,
            structural_signature=structural_signature,
            mechanic_signature=mechanic_signature,
            dimensions=dimensions,
            available_actions=available_actions,
            visible_effects=visible_effects,
            entities=tuple(entities),
            relations=relations,
            resources=resources,
            phase_hypotheses=tuple(
                sorted(set(_string_tuple(raw.get("phase_hypotheses"))))
            ),
            feature_tokens=feature_tokens,
            terminal_state=terminal_state,
        )


@dataclass(frozen=True, slots=True)
class DeterministicWorldModel:
    """Execute P-provided hypothesis material without embedded task knowledge."""

    role: str = "TRANSFORM_OR_WORLD_MODEL"

    def transform(
        self,
        observation: ObservationIR,
        context: ContextSnapshot,
        memory: MemorySnapshot,
        instruction_material: InstructionQueryResult,
    ) -> tuple[HypothesisIR, ...]:
        del context, memory
        if (
            not observation.frame_signature
            or not isinstance(instruction_material, InstructionQueryResult)
            or instruction_material.validate(observation)
        ):
            return ()
        return instruction_material.hypotheses


def _candidate_id(
    mode: str,
    observation: ObservationIR,
    action_id: int | None = None,
    *,
    instruction_digest: str = "",
) -> str:
    digest = digest_object(
        {
            "mode": mode,
            "observation": observation.frame_signature,
            "action_id": action_id,
            "instruction": instruction_digest,
        }
    )[:12]
    return f"candidate:{mode.casefold()}:{digest}"


def _action_step(
    action_id: int,
    observation: ObservationIR,
    *,
    limit: int | None = None,
) -> dict[str, int]:
    step = {"action_id": action_id}
    if limit is not None:
        step["limit"] = limit
    if action_id == 6:
        height, width = observation.dimensions or (64, 64)
        step["x"] = min(63, max(0, width // 2))
        step["y"] = min(63, max(0, height // 2))
    return step


@dataclass(frozen=True, slots=True)
class DeterministicCandidateSurface:
    """Convert P-provided priors and controls into typed candidates."""

    role: str = "CANDIDATE_SURFACE"

    def generate(
        self,
        observation: ObservationIR,
        context: ContextSnapshot,
        hypotheses: tuple[HypothesisIR, ...],
        instruction_material: InstructionQueryResult,
    ) -> tuple[CandidateIR, ...]:
        if (
            not isinstance(instruction_material, InstructionQueryResult)
            or instruction_material.validate(observation)
        ):
            return ()
        expected = {
            hypothesis.hypothesis_id: hypothesis.predictions
            for hypothesis in hypotheses
        }
        candidates: list[CandidateIR] = []
        prediction_by_action = {
            item.action_id: item for item in instruction_material.predictions
        }
        for action_id in observation.available_actions:
            prediction = prediction_by_action.get(action_id)
            if prediction is None:
                continue
            expected_progress = min(
                1.0,
                max(
                    0.0,
                    (prediction.progress_likelihood + prediction.candidate_prior)
                    / 2.0,
                ),
            )
            repetition_cost = min(
                1.0,
                context.action_history.count(action_id) / 4.0,
            )
            candidates.append(
                CandidateIR(
                    candidate_id=_candidate_id(
                        "ACTION",
                        observation,
                        action_id,
                        instruction_digest=instruction_material.query_digest,
                    ),
                    mode="ACTION",
                    steps=(_action_step(action_id, observation),),
                    preconditions=prediction.preconditions,
                    expected_effects_by_hypothesis=expected,
                    expected_progress=expected_progress,
                    expected_information_gain=prediction.information_gain,
                    expected_risk=prediction.hazard_likelihood,
                    repetition_cost=repetition_cost,
                    rollback_cost=prediction.hazard_likelihood / 2.0,
                    provenance=tuple(
                        sorted(
                            {
                                instruction_material.query_digest,
                                *instruction_material.provenance,
                                *prediction.instruction_refs,
                            }
                        )
                    ),
                    falsification_conditions=(
                        prediction.falsification_conditions
                    ),
                )
            )

        if instruction_material.predictions:
            probe_prediction = sorted(
                instruction_material.predictions,
                key=lambda item: (
                    -item.information_gain,
                    item.hazard_likelihood,
                    item.action_id,
                ),
            )[0]
            probe_action = probe_prediction.action_id
            candidates.append(
                CandidateIR(
                    candidate_id=_candidate_id(
                        "BOUNDED_PROBE",
                        observation,
                        probe_action,
                        instruction_digest=instruction_material.query_digest,
                    ),
                    mode="BOUNDED_PROBE",
                    steps=(
                        _action_step(
                            probe_action,
                            observation,
                            limit=1,
                        ),
                    ),
                    preconditions=tuple(
                        sorted(
                            {
                                *probe_prediction.preconditions,
                                "ACTION_BUDGET_REMAINING",
                            }
                        )
                    ),
                    expected_effects_by_hypothesis=expected,
                    expected_progress=probe_prediction.progress_likelihood,
                    expected_information_gain=probe_prediction.information_gain,
                    expected_risk=probe_prediction.hazard_likelihood,
                    repetition_cost=min(
                        1.0,
                        context.action_history.count(probe_action) / 4.0,
                    ),
                    rollback_cost=probe_prediction.hazard_likelihood / 2.0,
                    provenance=tuple(
                        sorted(
                            {
                                instruction_material.query_digest,
                                *instruction_material.provenance,
                                *probe_prediction.instruction_refs,
                            }
                        )
                    ),
                    falsification_conditions=tuple(
                        sorted(
                            {
                                *probe_prediction.falsification_conditions,
                                "probe budget exhausted",
                            }
                        )
                    ),
                )
            )

        for control in instruction_material.controls:
            step: dict[str, object] = {"operation": control.mode}
            if control.mode == "PLAN":
                step["horizon"] = 2
            candidates.append(
                CandidateIR(
                    candidate_id=_candidate_id(
                        control.mode,
                        observation,
                        instruction_digest=instruction_material.query_digest,
                    ),
                    mode=control.mode,
                    steps=(step,),
                    preconditions=control.preconditions,
                    expected_effects_by_hypothesis=(
                        expected if control.mode == "PLAN" else {}
                    ),
                    expected_progress=control.expected_progress,
                    expected_information_gain=control.information_gain,
                    expected_risk=control.expected_risk,
                    repetition_cost=control.repetition_cost,
                    rollback_cost=control.rollback_cost,
                    provenance=tuple(
                        sorted(
                            {
                                instruction_material.query_digest,
                                *instruction_material.provenance,
                                *control.provenance,
                            }
                        )
                    ),
                    falsification_conditions=control.falsification_conditions,
                )
            )
        return tuple(candidates)


def _candidate_action_id(candidate: CandidateIR) -> int | None:
    if not candidate.steps:
        return None
    value = candidate.steps[0].get("action_id")
    return (
        int(value)
        if isinstance(value, int) and not isinstance(value, bool)
        else None
    )


@dataclass(frozen=True, slots=True)
class DeterministicSuccessCriterion:
    """Construct W=(X,R,Mc) and conservatively close each candidate."""

    role: str = "FITTING_OR_SUCCESS_CRITERION"

    def evaluate(
        self,
        observation: ObservationIR,
        context: ContextSnapshot,
        hypotheses: tuple[HypothesisIR, ...],
        candidates: tuple[CandidateIR, ...],
    ) -> tuple[ClosureIR, ...]:
        closures: list[ClosureIR] = []
        hazard_observed = observation.terminal_state == "GAME_OVER" or any(
            effect in HAZARD_EFFECTS for effect in observation.visible_effects
        )

        for candidate in candidates:
            action_id = _candidate_action_id(candidate)
            expected_effects = {
                key: tuple(values)
                for key, values in candidate.expected_effects_by_hypothesis.items()
            }
            uncertainty = 1.0 - max(
                (hypothesis.confidence for hypothesis in hypotheses),
                default=0.0,
            )
            fit_score = round(
                candidate.expected_progress
                + (0.5 * candidate.expected_information_gain)
                - candidate.expected_risk
                - candidate.repetition_cost
                - candidate.rollback_cost
                - (0.25 * uncertainty),
                6,
            )
            evaluation_axes = {
                "progress": candidate.expected_progress,
                "goal_relevance": candidate.expected_progress,
                "hazard": "OBSERVED" if hazard_observed else "NOT_OBSERVED",
                "terminal_state": observation.terminal_state,
                "expected_effect_consistency": (
                    "PREDICTIONS_PRESENT" if expected_effects else "MISSING"
                ),
                "information_gain": candidate.expected_information_gain,
                "uncertainty": round(uncertainty, 6),
                "repetition_cost": candidate.repetition_cost,
                "rollback_cost": candidate.rollback_cost,
                "action_budget_remaining": context.remaining_actions,
            }
            x = {
                "observation_signature": observation.frame_signature,
                "structural_signature": observation.structural_signature,
                "terminal_state": observation.terminal_state,
                "candidate_id": candidate.candidate_id,
                "available_actions": observation.available_actions,
            }
            r = {
                "preconditions": candidate.preconditions,
                "expected_effects_by_hypothesis": expected_effects,
                "falsification_conditions": candidate.falsification_conditions,
                "hypothesis_ids": tuple(
                    hypothesis.hypothesis_id for hypothesis in hypotheses
                ),
                "evaluation_axes": evaluation_axes,
            }
            mc = {
                "identity": candidate.candidate_id,
                "boundary": "rendered-observation-only",
                "mode": candidate.mode,
                "provenance": candidate.provenance,
                "stop_on": ("hazard", "divergence", "budget-exhaustion"),
                "rollback_cost": candidate.rollback_cost,
                "fit_score": fit_score,
            }

            missing: list[str] = []
            reasons: list[str] = []
            if (
                not observation.frame_signature
                or not observation.structural_signature
                or not candidate.candidate_id
            ):
                missing.append("X")
            if (
                not candidate.preconditions
                or not candidate.falsification_conditions
                or (
                    candidate.mode in ACTION_MODES | {"PLAN"}
                    and not expected_effects
                )
            ):
                missing.append("R")
            if (
                not candidate.candidate_id
                or not candidate.provenance
                or candidate.mode not in CANDIDATE_MODES
            ):
                missing.append("Mc")

            if missing:
                status = "SUSPEND"
                reasons.append("CLOSURE_TERMS_MISSING")
            elif observation.terminal_state == "UNKNOWN":
                status = "SUSPEND"
                reasons.append("TERMINAL_UNOBSERVED")
            elif hazard_observed and candidate.mode in ACTION_MODES | {"PLAN"}:
                status = "REJECT"
                reasons.append("HAZARD_ACTION_VETO")
            elif observation.terminal_state == "WIN":
                status = "STOP"
                reasons.append("TERMINAL_WIN")
            elif context.remaining_actions == 0:
                status = "STOP"
                reasons.append("ACTION_BUDGET_EXHAUSTED")
            elif candidate.mode in ACTION_MODES:
                if action_id not in observation.available_actions:
                    status = "REJECT"
                    reasons.append("ACTION_NOT_AVAILABLE")
                else:
                    status = "PASS"
                    reasons.append("W_X_R_MC_CLOSED")
            elif candidate.mode == "REOBSERVE":
                status = "PROBE"
                reasons.append("REOBSERVATION_AVAILABLE")
            elif candidate.mode == "SUSPEND":
                status = "SUSPEND"
                reasons.append("BOUNDED_SUSPEND_AVAILABLE")
            elif candidate.mode == "STOP":
                status = "HOLD"
                reasons.append("STOP_CONDITION_NOT_MET")
            elif candidate.mode == "ROLLBACK":
                status = "PASS" if context.failures else "HOLD"
                reasons.append(
                    "REVERSIBLE_FAILURE_PRESENT"
                    if context.failures
                    else "ROLLBACK_EVIDENCE_MISSING"
                )
            else:
                status = "HOLD"
                reasons.append("PLAN_REQUIRES_FURTHER_CLOSURE")

            confidence = 0.9 if status == "PASS" else 0.6
            closures.append(
                ClosureIR(
                    candidate_id=candidate.candidate_id,
                    x=x,
                    r=r,
                    mc=mc,
                    status=status,
                    reason_codes=tuple(reasons),
                    missing_terms=tuple(sorted(set(missing))),
                    confidence=confidence,
                )
            )
        return tuple(closures)


__all__ = [
    "ACTION_MODES",
    "CANDIDATE_MODES",
    "ROLE_FAILURE_REASONS",
    "DeterministicCandidateSurface",
    "DeterministicSuccessCriterion",
    "DeterministicSymbolSpace",
    "DeterministicWorldModel",
    "Layer0FunctionalLoss",
]
