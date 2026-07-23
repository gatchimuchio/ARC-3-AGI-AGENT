"""Callable implementations of the ARC-native Layer-0 responsibilities."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .context import ContextSnapshot
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
                    if isinstance(action, int) and 1 <= int(action) <= 7
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
    """Generate competing, falsifiable hypotheses without hidden-state claims."""

    role: str = "TRANSFORM_OR_WORLD_MODEL"

    def transform(
        self,
        observation: ObservationIR,
        context: ContextSnapshot,
        memory: MemorySnapshot,
    ) -> tuple[HypothesisIR, ...]:
        if not observation.frame_signature:
            return ()

        basis = {
            "observation": observation.frame_signature,
            "previous": (
                context.previous_observation.frame_signature
                if context.previous_observation is not None
                else ""
            ),
            "memory": memory.digest,
        }
        suffix = digest_object(basis)[:12]
        visible_prediction = (
            observation.visible_effects[0]
            if observation.visible_effects
            else "VISIBLE_STATE_CHANGE"
        )
        support = (f"observation:{observation.frame_signature}",)
        if context.previous_observation is not None:
            support += (
                f"previous:{context.previous_observation.frame_signature}",
            )

        return (
            HypothesisIR(
                hypothesis_id=f"hypothesis:transition:{suffix}",
                hypothesis_type="rendered-transition",
                claims=("an available action may change rendered state",),
                predictions=(visible_prediction,),
                falsification_conditions=(
                    "same rendered signature after bounded action",
                ),
                support=support,
                confidence=0.55,
                state="PROPOSED",
            ),
            HypothesisIR(
                hypothesis_id=f"hypothesis:stasis:{suffix}",
                hypothesis_type="counter-hypothesis",
                claims=("an available action may have no immediately visible effect",),
                predictions=("NO_VISIBLE_CHANGE",),
                falsification_conditions=("visible effect follows bounded action",),
                support=support,
                confidence=0.45,
                state="PROPOSED",
            ),
        )


def _candidate_id(
    mode: str,
    observation: ObservationIR,
    action_id: int | None = None,
) -> str:
    digest = digest_object(
        {
            "mode": mode,
            "observation": observation.frame_signature,
            "action_id": action_id,
        }
    )[:12]
    return f"candidate:{mode.casefold()}:{digest}"


@dataclass(frozen=True, slots=True)
class DeterministicCandidateSurface:
    """Produce a bounded, comparable action/control/plan candidate surface."""

    role: str = "CANDIDATE_SURFACE"

    def generate(
        self,
        observation: ObservationIR,
        context: ContextSnapshot,
        hypotheses: tuple[HypothesisIR, ...],
    ) -> tuple[CandidateIR, ...]:
        expected = {
            hypothesis.hypothesis_id: hypothesis.predictions
            for hypothesis in hypotheses
        }
        actions = observation.available_actions
        candidates: list[CandidateIR] = []

        if actions:
            primary = actions[0]
            candidates.append(
                CandidateIR(
                    candidate_id=_candidate_id("ACTION", observation, primary),
                    mode="ACTION",
                    steps=({"action_id": primary},),
                    preconditions=(f"ACTION{primary}_AVAILABLE",),
                    expected_effects_by_hypothesis=expected,
                    expected_progress=0.5,
                    expected_information_gain=0.4,
                    expected_risk=0.2,
                    rollback_cost=0.2,
                    provenance=("current-observation", "world-model"),
                    falsification_conditions=(
                        "action unavailable",
                        "observed effect contradicts every hypothesis",
                    ),
                )
            )
            probe = actions[1] if len(actions) > 1 else primary
            candidates.append(
                CandidateIR(
                    candidate_id=_candidate_id("BOUNDED_PROBE", observation, probe),
                    mode="BOUNDED_PROBE",
                    steps=({"action_id": probe, "limit": 1},),
                    preconditions=(
                        f"ACTION{probe}_AVAILABLE",
                        "ACTION_BUDGET_REMAINING",
                    ),
                    expected_effects_by_hypothesis=expected,
                    expected_progress=0.3,
                    expected_information_gain=0.7,
                    expected_risk=0.15,
                    rollback_cost=0.1,
                    provenance=("current-observation", "world-model"),
                    falsification_conditions=(
                        "action unavailable",
                        "probe budget exhausted",
                    ),
                )
            )

        candidates.extend(
            (
                CandidateIR(
                    candidate_id=_candidate_id("REOBSERVE", observation),
                    mode="REOBSERVE",
                    steps=({"operation": "REOBSERVE"},),
                    preconditions=("OBSERVATION_CHANNEL_AVAILABLE",),
                    expected_information_gain=0.5,
                    expected_risk=0.0,
                    provenance=("current-observation",),
                    falsification_conditions=("observation channel unavailable",),
                ),
                CandidateIR(
                    candidate_id=_candidate_id("SUSPEND", observation),
                    mode="SUSPEND",
                    steps=({"operation": "SUSPEND"},),
                    preconditions=("OPEN_PROOF_OBLIGATION",),
                    expected_risk=0.0,
                    provenance=("closure-policy",),
                    falsification_conditions=("all closure terms become observed",),
                ),
                CandidateIR(
                    candidate_id=_candidate_id("STOP", observation),
                    mode="STOP",
                    steps=({"operation": "STOP"},),
                    preconditions=("TERMINAL_OR_BUDGET_BOUNDARY",),
                    expected_risk=0.0,
                    provenance=("stopping-policy",),
                    falsification_conditions=("safe bounded work remains",),
                ),
                CandidateIR(
                    candidate_id=_candidate_id("ROLLBACK", observation),
                    mode="ROLLBACK",
                    steps=({"operation": "ROLLBACK"},),
                    preconditions=("REVERSIBLE_FAILURE_EVIDENCE",),
                    expected_risk=0.1,
                    rollback_cost=0.3,
                    provenance=("context-failure-evidence",),
                    falsification_conditions=("no reversible checkpoint exists",),
                ),
                CandidateIR(
                    candidate_id=_candidate_id("PLAN", observation),
                    mode="PLAN",
                    steps=({"operation": "PLAN", "horizon": 2},),
                    preconditions=("MULTIPLE_HYPOTHESES_AVAILABLE",),
                    expected_effects_by_hypothesis=expected,
                    expected_progress=0.4,
                    expected_information_gain=0.4,
                    expected_risk=0.1,
                    repetition_cost=0.1,
                    rollback_cost=0.2,
                    provenance=("world-model", "bounded-planning"),
                    falsification_conditions=("no bounded plan can be grounded",),
                ),
            )
        )
        return tuple(candidates)


def _candidate_action_id(candidate: CandidateIR) -> int | None:
    if not candidate.steps:
        return None
    value = candidate.steps[0].get("action_id")
    return int(value) if isinstance(value, int) else None


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
