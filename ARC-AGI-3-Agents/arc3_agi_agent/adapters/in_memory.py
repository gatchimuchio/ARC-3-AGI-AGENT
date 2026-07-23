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
        failures = list(directive.validate(decision))
        if executor != "pure-llm":
            failures.append("EMISSION_EXECUTOR_NOT_PURE_LLM")
        if candidate.candidate_id != directive.candidate_id:
            failures.append("EMISSION_CANDIDATE_OBJECT_MISMATCH")
        if candidate.mode not in ACTION_MODES:
            failures.append("EMISSION_CANDIDATE_MODE_INVALID")

        action_id: int | None = None
        if candidate.steps:
            value = candidate.steps[0].get("action_id")
            if isinstance(value, int):
                action_id = value
        if action_id != directive.action_id:
            failures.append("EMISSION_ACTION_CANDIDATE_MISMATCH")
        if directive.action_id not in observation.available_actions:
            failures.append("EMISSION_ACTION_NOT_AVAILABLE")
        if failures:
            raise AuthorityViolation(";".join(sorted(set(failures))))

        result = EmissionResult(
            candidate_id=candidate.candidate_id,
            action_id=directive.action_id,
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


__all__ = ["EmissionResult", "InMemoryEmissionInterface"]
