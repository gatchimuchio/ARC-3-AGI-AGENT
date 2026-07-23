"""HDS-controlled Layer-0 agent for bundled OFFLINE sample environments."""

from __future__ import annotations

import time
from dataclasses import dataclass
from typing import Any

from arc_agi import OperationMode  # type: ignore[import-untyped]
from arcengine import FrameData, FrameDataRaw, GameAction, GameState

from arc3_agi_agent.protocol import AuthorityViolation
from arc3_agi_agent.sample_runtime import OfflineSampleRuntime, SampleCycleResult

from ..agent import Agent


@dataclass(frozen=True, slots=True)
class SampleAgentReport:
    game_id: str
    actions: int
    levels_completed: int
    terminal_state: str
    final_status: str
    memory_version: int
    context_version: int
    context_actions_used: int
    previous_observation_present: bool
    trace_digests: tuple[str, ...]
    instruction_body_formats: tuple[str, ...]
    instruction_body_versions: tuple[str, ...]
    instruction_body_digests: tuple[str, ...]
    instruction_query_digests: tuple[str, ...]
    decision_statuses: tuple[str, ...]
    verification_statuses: tuple[str, ...]


class Layer0SampleAgent(Agent):
    """Run the existing six-responsibility kernel on one local sample."""

    def __init__(
        self,
        *args: Any,
        operation_mode: OperationMode,
        max_actions: int = 8,
        **kwargs: Any,
    ) -> None:
        if operation_mode is not OperationMode.OFFLINE:
            raise AuthorityViolation("OFFLINE_SAMPLE_MODE_REQUIRED")
        if max_actions < 1:
            raise ValueError("max_actions must be positive")
        super().__init__(*args, **kwargs)
        self.headers = {}
        self.MAX_ACTIONS = max_actions
        self.action_counter = 0
        self.frames: list[FrameData] = []
        self.cycles: list[SampleCycleResult] = []
        self.final_status = "NOT_STARTED"
        self.runtime = OfflineSampleRuntime(
            environment=self.arc_env,
            operation_mode=operation_mode,
            max_actions=max_actions,
        )

    @property
    def name(self) -> str:
        return f"{super().name}.{self.MAX_ACTIONS}"

    def main(self) -> None:
        """Execute only through the HDS-controlled OFFLINE emission adapter."""

        self.timer = time.time()
        try:
            current = self.arc_env.observation_space
            if not isinstance(current, FrameDataRaw) or current.is_empty():
                raise RuntimeError("OFFLINE_SAMPLE_INITIAL_OBSERVATION_MISSING")
            self.append_frame(self._convert_raw_frame_data(current))

            for _ in range(self.MAX_ACTIONS + 1):
                cycle = self.runtime.run_cycle(
                    current,
                    action_count=self.action_counter,
                )
                self.cycles.append(cycle)
                self.final_status = cycle.kernel_result.status
                if cycle.after_frame is None:
                    break
                self.action_counter += 1
                current = cycle.after_frame
                self.append_frame(self._convert_raw_frame_data(current))
                if self.final_status == "STOP":
                    break
            else:
                raise RuntimeError("OFFLINE_SAMPLE_CYCLE_BOUND_EXCEEDED")
        finally:
            self.cleanup()

    def report(self) -> SampleAgentReport:
        context = self.runtime.context_state.snapshot()
        memory_subject = self.runtime.components.memory
        if memory_subject is None:
            raise RuntimeError("P1_MEMORY_SUBJECT_REQUIRED")
        memory = memory_subject.view()
        latest = (
            self.frames[-1]
            if self.frames
            else FrameData(levels_completed=0, win_levels=0)
        )
        return SampleAgentReport(
            game_id=self.game_id,
            actions=self.action_counter,
            levels_completed=int(latest.levels_completed),
            terminal_state=str(latest.state.value),
            final_status=self.final_status,
            memory_version=memory.version,
            context_version=context.version,
            context_actions_used=context.actions_used,
            previous_observation_present=context.previous_observation is not None,
            trace_digests=tuple(
                cycle.kernel_result.trace_digest for cycle in self.cycles
            ),
            instruction_body_formats=tuple(
                cycle.kernel_result.instruction_body_format
                for cycle in self.cycles
            ),
            instruction_body_versions=tuple(
                cycle.kernel_result.instruction_body_version
                for cycle in self.cycles
            ),
            instruction_body_digests=tuple(
                cycle.kernel_result.instruction_body_digest
                for cycle in self.cycles
            ),
            instruction_query_digests=tuple(
                cycle.kernel_result.instruction_query_digest
                for cycle in self.cycles
            ),
            decision_statuses=tuple(
                cycle.kernel_result.decision.status for cycle in self.cycles
            ),
            verification_statuses=tuple(
                cycle.verification.status
                for cycle in self.cycles
                if cycle.verification is not None
            ),
        )

    def is_done(self, frames: list[FrameData], latest_frame: FrameData) -> bool:
        return latest_frame.state in {GameState.WIN, GameState.GAME_OVER}

    def choose_action(
        self,
        frames: list[FrameData],
        latest_frame: FrameData,
    ) -> GameAction:
        del frames, latest_frame
        raise AuthorityViolation("DIRECT_ACTION_SELECTION_FORBIDDEN")

    def take_action(self, action: GameAction) -> FrameData | None:
        del action
        raise AuthorityViolation("DIRECT_ACTION_EMISSION_FORBIDDEN")

    def do_action_request(self, action: GameAction) -> FrameData:
        del action
        raise AuthorityViolation("DIRECT_ENVIRONMENT_STEP_FORBIDDEN")


__all__ = ["Layer0SampleAgent", "SampleAgentReport"]
