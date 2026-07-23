"""Strict OFFLINE emission boundary for bundled ARC-AGI-3 samples."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from arc_agi import OperationMode  # type: ignore[import-untyped]
from arc_agi.local_wrapper import (  # type: ignore[import-untyped]
    LocalEnvironmentWrapper,
)
from arcengine import FrameDataRaw, GameAction

from ..ir import CandidateIR, ObservationIR
from ..protocol import AuthorityViolation, EmissionDirective, HDSDecision
from ..recovery import (
    HDSRecoveryDecision,
    RecoveryDirective,
    require_recovery_directive,
)
from ..sample_observation import SampleFrameAdapter
from ..schema import digest_object
from ..search_reset import (
    HDSSearchResetDecision,
    SearchResetDirective,
    require_search_reset_directive,
)
from .in_memory import (
    EmissionResult,
    emission_result_signature,
    validate_authorized_emission,
)


@dataclass(slots=True)
class OfflineArcadeEmissionInterface:
    """Execute only capability-checked actions against an OFFLINE wrapper."""

    environment: Any
    operation_mode: OperationMode
    frame_adapter: SampleFrameAdapter = field(default_factory=SampleFrameAdapter)
    _before: FrameDataRaw | None = field(default=None, init=False, repr=False)
    _after: FrameDataRaw | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        if self.operation_mode is not OperationMode.OFFLINE:
            raise AuthorityViolation("OFFLINE_SAMPLE_MODE_REQUIRED")
        if not isinstance(self.environment, LocalEnvironmentWrapper):
            raise AuthorityViolation("OFFLINE_LOCAL_WRAPPER_REQUIRED")
        step = getattr(self.environment, "step", None)
        if not callable(step):
            raise TypeError("OFFLINE_SAMPLE_ENVIRONMENT_STEP_MISSING")

    def bind(self, frame: FrameDataRaw) -> None:
        if not isinstance(frame, FrameDataRaw):
            raise TypeError("OFFLINE_SAMPLE_FRAME_REQUIRED")
        self._before = frame
        self._after = None

    @property
    def last_frame(self) -> FrameDataRaw | None:
        return self._after

    def emit(
        self,
        directive: EmissionDirective,
        decision: HDSDecision,
        candidate: CandidateIR,
        observation: ObservationIR,
        *,
        executor: str,
    ) -> EmissionResult:
        if self.operation_mode is not OperationMode.OFFLINE:
            raise AuthorityViolation("OFFLINE_SAMPLE_MODE_CHANGED")
        if self._before is None:
            raise AuthorityViolation("OFFLINE_SAMPLE_OBSERVATION_NOT_BOUND")

        action_id, receipt = validate_authorized_emission(
            directive,
            decision,
            candidate,
            observation,
            executor=executor,
        )
        action = GameAction.from_id(action_id)
        step = candidate.steps[0]
        data: dict[str, int] = {}
        if action_id == 6:
            data = {"x": int(step["x"]), "y": int(step["y"])}

        reasoning = {
            "authority": "HDS",
            "candidate": candidate.candidate_id,
            "decision": decision.decision_id,
            "closure": decision.closure_signature,
        }
        raw = self.environment.step(action, data=data, reasoning=reasoning)
        if not isinstance(raw, FrameDataRaw):
            raise RuntimeError("OFFLINE_SAMPLE_STEP_FAILED")
        self._after = raw
        visible_effects = self.frame_adapter.visible_effects(raw, self._before)
        status = "EMITTED_OFFLINE_SAMPLE"
        directive_signature = digest_object(directive)
        terminal_state = str(raw.state.value).upper()
        result_observation_signature = "offline-observation:" + digest_object(
            self.frame_adapter.runtime_observation(raw, self._before)
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
            visible_effects=visible_effects,
            terminal_state=terminal_state,
            levels_completed=raw.levels_completed,
        )
        directive.bind_receipt(receipt, result_signature)
        return EmissionResult(
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
            visible_effects=visible_effects,
            terminal_state=terminal_state,
            levels_completed=raw.levels_completed,
            _authorization_receipt=receipt,
        )

    def recover(
        self,
        directive: RecoveryDirective,
        decision: HDSRecoveryDecision,
        *,
        executor: str,
    ) -> FrameDataRaw:
        """Execute RESET only under a single-use HDS rollback capability."""

        if self.operation_mode is not OperationMode.OFFLINE:
            raise AuthorityViolation("OFFLINE_SAMPLE_MODE_CHANGED")
        if self._after is None:
            raise AuthorityViolation("RECOVERY_FAILURE_RESULT_NOT_BOUND")
        if str(self._after.state.value).upper() != "GAME_OVER":
            raise AuthorityViolation("RECOVERY_REQUIRES_GAME_OVER_FRAME")
        require_recovery_directive(
            directive,
            decision,
            executor=executor,
        )
        raw = self.environment.step(
            GameAction.RESET,
            data={},
            reasoning={
                "authority": "HDS",
                "recovery_decision": decision.decision_id,
                "rollback_reference": decision.rollback_reference,
            },
        )
        if not isinstance(raw, FrameDataRaw):
            raise RuntimeError("OFFLINE_SAMPLE_RECOVERY_STEP_FAILED")
        self._before = self._after
        self._after = raw
        return raw

    def search_reset(
        self,
        directive: SearchResetDirective,
        decision: HDSSearchResetDecision,
        *,
        executor: str,
    ) -> FrameDataRaw:
        """RESET one active branch only under a single-use HDS capability."""

        if self.operation_mode is not OperationMode.OFFLINE:
            raise AuthorityViolation("OFFLINE_SAMPLE_MODE_CHANGED")
        if self._before is None:
            raise AuthorityViolation("SEARCH_RESET_OBSERVATION_NOT_BOUND")
        if self._after is not None:
            raise AuthorityViolation("SEARCH_RESET_REQUIRES_NO_EMISSION_RESULT")
        if str(self._before.state.value).upper() != "NOT_FINISHED":
            raise AuthorityViolation("SEARCH_RESET_REQUIRES_ACTIVE_FRAME")
        if self.frame_adapter.signature(self._before) != decision.observation_signature:
            raise AuthorityViolation("SEARCH_RESET_OBSERVATION_MISMATCH")
        require_search_reset_directive(
            directive,
            decision,
            executor=executor,
        )
        raw = self.environment.step(
            GameAction.RESET,
            data={},
            reasoning={
                "authority": "HDS",
                "search_reset_decision": decision.decision_id,
                "reset_reference": decision.reset_reference,
            },
        )
        if not isinstance(raw, FrameDataRaw):
            raise RuntimeError("OFFLINE_SAMPLE_SEARCH_RESET_STEP_FAILED")
        self._after = raw
        return raw


__all__ = ["OfflineArcadeEmissionInterface"]
