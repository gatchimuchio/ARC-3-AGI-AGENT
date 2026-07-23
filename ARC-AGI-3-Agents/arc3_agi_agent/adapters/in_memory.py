"""In-memory emission boundary used to verify authority without a live runner."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..ir import CandidateIR, ObservationIR
from ..protocol import AuthorityViolation, EmissionDirective, HDSDecision
from ..roles import ACTION_MODES
from ..schema import digest_object


@dataclass(frozen=True, slots=True)
class EmissionResult:
    candidate_id: str
    action_id: int
    status: str
    result_signature: str
    visible_effects: tuple[str, ...] = ()
    terminal_state: str = "UNKNOWN"
    levels_completed: int = 0


def validate_authorized_emission(
    directive: EmissionDirective,
    decision: HDSDecision,
    candidate: CandidateIR,
    observation: ObservationIR,
    *,
    executor: str,
) -> int:
    """Validate the shared HDS emission contract and return the action ID."""

    failures = list(directive.validate(decision))
    if executor != "pure-llm":
        failures.append("EMISSION_EXECUTOR_NOT_PURE_LLM")
    if candidate.candidate_id != directive.candidate_id:
        failures.append("EMISSION_CANDIDATE_OBJECT_MISMATCH")
    if candidate.mode not in ACTION_MODES:
        failures.append("EMISSION_CANDIDATE_MODE_INVALID")

    action_id: int | None = None
    step: dict[str, object] = {}
    if candidate.steps:
        step = candidate.steps[0]
        value = step.get("action_id")
        if isinstance(value, int) and not isinstance(value, bool):
            action_id = value
    if action_id != directive.action_id:
        failures.append("EMISSION_ACTION_CANDIDATE_MISMATCH")
    if directive.action_id not in observation.available_actions:
        failures.append("EMISSION_ACTION_NOT_AVAILABLE")
    if action_id == 6:
        for axis in ("x", "y"):
            value = step.get(axis)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or not 0 <= value <= 63
            ):
                failures.append(f"EMISSION_COMPLEX_ACTION_{axis.upper()}_INVALID")
    if failures:
        raise AuthorityViolation(";".join(sorted(set(failures))))
    if action_id is None:
        raise AuthorityViolation("EMISSION_ACTION_MISSING")
    return action_id


@dataclass(slots=True)
class InMemoryEmissionInterface:
    """Accept only an HDS-authorized, closed, currently available action."""

    role: str = "EMISSION_INTERFACE"
    _emissions: list[EmissionResult] = field(default_factory=list, init=False)

    def emit(
        self,
        directive: EmissionDirective,
        decision: HDSDecision,
        candidate: CandidateIR,
        observation: ObservationIR,
        *,
        executor: str,
    ) -> EmissionResult:
        action_id = validate_authorized_emission(
            directive,
            decision,
            candidate,
            observation,
            executor=executor,
        )

        result = EmissionResult(
            candidate_id=candidate.candidate_id,
            action_id=action_id,
            status="EMITTED_IN_MEMORY",
            result_signature="emission:"
            + digest_object(
                {
                    "candidate_id": candidate.candidate_id,
                    "action_id": directive.action_id,
                    "closure_signature": directive.closure_signature,
                    "observation_signature": observation.frame_signature,
                }
            )[:20],
        )
        self._emissions.append(result)
        return result

    def results(self) -> tuple[EmissionResult, ...]:
        return tuple(self._emissions)


__all__ = [
    "EmissionResult",
    "InMemoryEmissionInterface",
    "validate_authorized_emission",
]
