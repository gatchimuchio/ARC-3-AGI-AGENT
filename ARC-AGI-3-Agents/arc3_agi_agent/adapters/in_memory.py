"""In-memory emission boundary used to verify authority without a live runner."""

from __future__ import annotations

from dataclasses import dataclass, field

from ..ir import CandidateIR, ObservationIR
from ..protocol import AuthorityViolation, EmissionDirective, HDSDecision
from ..roles import ACTION_MODES
from ..schema import TERMINAL_STATES, digest_object

EMISSION_RESULT_STATUSES = frozenset(
    {"EMITTED_IN_MEMORY", "EMITTED_OFFLINE_SAMPLE"}
)


def emission_result_signature(
    *,
    candidate_id: str,
    action_id: int,
    status: str,
    command_id: str,
    decision_id: str,
    closure_signature: str,
    observation_signature: str,
    result_observation_signature: str,
    directive_signature: str,
    visible_effects: tuple[str, ...],
    terminal_state: str,
    levels_completed: int,
) -> str:
    """Digest every observable and provenance field in an emission result."""

    return "emission-result:" + digest_object(
        {
            "candidate_id": candidate_id,
            "action_id": action_id,
            "status": status,
            "command_id": command_id,
            "decision_id": decision_id,
            "closure_signature": closure_signature,
            "observation_signature": observation_signature,
            "result_observation_signature": result_observation_signature,
            "directive_signature": directive_signature,
            "visible_effects": visible_effects,
            "terminal_state": terminal_state,
            "levels_completed": levels_completed,
        }
    )


@dataclass(frozen=True, slots=True)
class EmissionResult:
    candidate_id: str
    action_id: int
    status: str
    result_signature: str
    command_id: str = ""
    decision_id: str = ""
    closure_signature: str = ""
    observation_signature: str = ""
    result_observation_signature: str = ""
    directive_signature: str = ""
    visible_effects: tuple[str, ...] = ()
    terminal_state: str = "UNKNOWN"
    levels_completed: int = 0
    _authorization_receipt: object | None = field(
        default=None,
        repr=False,
        compare=False,
        metadata={"serialize": False},
    )

    def validate(
        self,
        directive: EmissionDirective,
        decision: HDSDecision,
        candidate: CandidateIR,
        observation: ObservationIR,
    ) -> tuple[str, ...]:
        failures: list[str] = []
        if self.command_id != directive.command_id:
            failures.append("EMISSION_RESULT_COMMAND_MISMATCH")
        if self.decision_id != directive.decision_id:
            failures.append("EMISSION_RESULT_DECISION_MISMATCH")
        if self.candidate_id != candidate.candidate_id:
            failures.append("EMISSION_RESULT_CANDIDATE_MISMATCH")
        if self.action_id != directive.action_id:
            failures.append("EMISSION_RESULT_ACTION_MISMATCH")
        if self.closure_signature != decision.closure_signature:
            failures.append("EMISSION_RESULT_CLOSURE_MISMATCH")
        if self.observation_signature != observation.frame_signature:
            failures.append("EMISSION_RESULT_OBSERVATION_MISMATCH")
        if not self.result_observation_signature:
            failures.append("EMISSION_RESULT_REOBSERVATION_SIGNATURE_MISSING")
        if self.directive_signature != digest_object(directive):
            failures.append("EMISSION_RESULT_DIRECTIVE_MISMATCH")
        if not directive.owns_receipt(
            self._authorization_receipt,
            self.result_signature,
        ):
            failures.append("EMISSION_RESULT_AUTHORIZATION_RECEIPT_INVALID")
        if (
            not isinstance(self.status, str)
            or self.status not in EMISSION_RESULT_STATUSES
        ):
            failures.append("EMISSION_RESULT_STATUS_INVALID")
        if (
            isinstance(self.action_id, bool)
            or not isinstance(self.action_id, int)
            or not 1 <= self.action_id <= 7
        ):
            failures.append("EMISSION_RESULT_ACTION_INVALID")
        if (
            not isinstance(self.visible_effects, tuple)
            or any(
                not isinstance(effect, str) or not effect.strip()
                for effect in self.visible_effects
            )
            or self.visible_effects
            != tuple(sorted(set(self.visible_effects)))
        ):
            failures.append("EMISSION_RESULT_VISIBLE_EFFECTS_INVALID")
        if not isinstance(self.result_signature, str) or not self.result_signature.strip():
            failures.append("EMISSION_RESULT_SIGNATURE_MISSING")
        else:
            expected_signature = emission_result_signature(
                candidate_id=self.candidate_id,
                action_id=self.action_id,
                status=self.status,
                command_id=self.command_id,
                decision_id=self.decision_id,
                closure_signature=self.closure_signature,
                observation_signature=self.observation_signature,
                result_observation_signature=self.result_observation_signature,
                directive_signature=self.directive_signature,
                visible_effects=self.visible_effects,
                terminal_state=self.terminal_state,
                levels_completed=self.levels_completed,
            )
            if self.result_signature != expected_signature:
                failures.append("EMISSION_RESULT_SIGNATURE_MISMATCH")
        if (
            not isinstance(self.terminal_state, str)
            or self.terminal_state not in TERMINAL_STATES
        ):
            failures.append("EMISSION_RESULT_TERMINAL_STATE_INVALID")
        if (
            isinstance(self.levels_completed, bool)
            or not isinstance(self.levels_completed, int)
            or self.levels_completed < 0
        ):
            failures.append("EMISSION_RESULT_LEVEL_COUNT_INVALID")
        return tuple(sorted(set(failures)))


def validate_authorized_emission(
    directive: EmissionDirective,
    decision: HDSDecision,
    candidate: CandidateIR,
    observation: ObservationIR,
    *,
    executor: str,
) -> tuple[int, object]:
    """Consume one HDS grant and return its action ID plus execution receipt."""

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
    if directive.observation_signature != observation.frame_signature:
        failures.append("EMISSION_OBSERVATION_MISMATCH")
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
    receipt = directive.consume(decision)
    return action_id, receipt


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
        action_id, receipt = validate_authorized_emission(
            directive,
            decision,
            candidate,
            observation,
            executor=executor,
        )

        status = "EMITTED_IN_MEMORY"
        directive_signature = digest_object(directive)
        result_observation_signature = "in-memory-observation:" + digest_object(
            {
                "action_id": action_id,
                "observation_signature": observation.frame_signature,
            }
        )
        result_signature = emission_result_signature(
            candidate_id=candidate.candidate_id,
            action_id=action_id,
            status=status,
            command_id=directive.command_id,
            decision_id=directive.decision_id,
            closure_signature=directive.closure_signature,
            observation_signature=observation.frame_signature,
            result_observation_signature=result_observation_signature,
            directive_signature=directive_signature,
            visible_effects=(),
            terminal_state="UNKNOWN",
            levels_completed=0,
        )
        directive.bind_receipt(receipt, result_signature)
        result = EmissionResult(
            candidate_id=candidate.candidate_id,
            action_id=action_id,
            status=status,
            result_signature=result_signature,
            command_id=directive.command_id,
            decision_id=directive.decision_id,
            closure_signature=directive.closure_signature,
            observation_signature=observation.frame_signature,
            result_observation_signature=result_observation_signature,
            directive_signature=directive_signature,
            _authorization_receipt=receipt,
        )
        self._emissions.append(result)
        return result

    def results(self) -> tuple[EmissionResult, ...]:
        return tuple(self._emissions)


__all__ = [
    "EmissionResult",
    "InMemoryEmissionInterface",
    "emission_result_signature",
    "validate_authorized_emission",
]
