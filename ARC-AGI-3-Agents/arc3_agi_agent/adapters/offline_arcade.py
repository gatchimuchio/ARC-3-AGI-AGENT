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
from ..sample_observation import SampleFrameAdapter
from ..schema import digest_object
from .in_memory import EmissionResult, validate_authorized_emission


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

        action_id = validate_authorized_emission(
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
        return EmissionResult(
            candidate_id=candidate.candidate_id,
            action_id=action_id,
            status="EMITTED_OFFLINE_SAMPLE",
            result_signature="offline-emission:"
            + digest_object(
                {
                    "action_id": action_id,
                    "after": self.frame_adapter.signature(raw),
                    "before": self.frame_adapter.signature(self._before),
                    "decision": decision.decision_id,
                }
            )[:20],
            visible_effects=visible_effects,
            terminal_state=str(raw.state.value).upper(),
            levels_completed=raw.levels_completed,
        )


__all__ = ["OfflineArcadeEmissionInterface"]
