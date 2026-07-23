"""P10 OFFLINE sample agent with visual computation and HDS recovery."""

from __future__ import annotations

import dataclasses
import time
from dataclasses import dataclass
from typing import Any

from arc_agi import OperationMode  # type: ignore[import-untyped]
from arcengine import FrameData, FrameDataRaw, GameAction, GameState

from arc3_agi_agent.p10_compute import VISUAL_OPERATOR_VERSION
from arc3_agi_agent.p10_runtime import (
    P10InstructionVariant,
    P10OfflineSampleRuntime,
    P10RecoveryResult,
    P10SearchResetResult,
)
from arc3_agi_agent.protocol import AuthorityViolation
from arc3_agi_agent.sample_runtime import SampleCycleResult

from ..agent import Agent


@dataclass(frozen=True, slots=True)
class P10SampleAgentReport:
    game_id: str
    instruction_variant: P10InstructionVariant
    actions: int
    recoveries: int
    search_resets: int
    levels_completed: int
    win_levels: int
    terminal_state: str
    final_status: str
    complete: bool
    max_action_exhausted: bool
    memory_version: int
    memory_operations: tuple[str, ...]
    context_version: int
    context_actions_used: int
    memory_influenced_cycle_count: int
    visual_operator_version: str
    instruction_body_formats: tuple[str, ...]
    instruction_body_versions: tuple[str, ...]
    instruction_body_digests: tuple[str, ...]
    instruction_query_digests: tuple[str, ...]
    decision_statuses: tuple[str, ...]
    verification_statuses: tuple[str, ...]
    trace_digests: tuple[str, ...]
    trace_events: tuple[tuple[dict[str, object], ...], ...]
    rollback_decision_ids: tuple[str, ...]
    rollback_memory_versions: tuple[tuple[int, int], ...]
    failure_payload_digests: tuple[str, ...]
    search_reset_decision_ids: tuple[str, ...]
    search_reset_memory_versions: tuple[tuple[int, int], ...]
    search_reset_payload_digests: tuple[str, ...]
    search_reset_evidence_signatures: tuple[str, ...]


class P10SampleAgent(Agent):
    """Run one retained sample only through the P10 Trinity boundaries."""

    def __init__(
        self,
        *args: Any,
        operation_mode: OperationMode,
        max_actions: int = 4096,
        instruction_variant: P10InstructionVariant = "hybrid",
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
        self.recoveries: list[P10RecoveryResult] = []
        self.search_resets: list[P10SearchResetResult] = []
        self.final_status = "NOT_STARTED"
        self.max_action_exhausted = False
        self.runtime = P10OfflineSampleRuntime(
            environment=self.arc_env,
            operation_mode=operation_mode,
            max_actions=max_actions,
            instruction_variant=instruction_variant,
        )

    @property
    def name(self) -> str:
        return f"{super().name}.{self.MAX_ACTIONS}"

    def main(self) -> None:
        """Run actions and RESET only through capability-checked boundaries."""

        self.timer = time.time()
        try:
            current = self.arc_env.observation_space
            if not isinstance(current, FrameDataRaw) or current.is_empty():
                raise RuntimeError("OFFLINE_SAMPLE_INITIAL_OBSERVATION_MISSING")
            self.append_frame(self._convert_raw_frame_data(current))

            while self.action_counter < self.MAX_ACTIONS:
                if current.state is GameState.WIN:
                    self.final_status = "STOP"
                    break
                cycle = self.runtime.run_cycle(
                    current,
                    action_count=self.action_counter,
                )
                self.cycles.append(cycle)
                self.final_status = cycle.kernel_result.status
                if cycle.after_frame is None:
                    search_reset = self.runtime.search_reset(
                        cycle,
                        current,
                        action_count=self.action_counter,
                    )
                    if search_reset is None:
                        break
                    self.search_resets.append(search_reset)
                    self.action_counter += 1
                    current = search_reset.execution.reset_frame
                    self.append_frame(self._convert_raw_frame_data(current))
                    self.final_status = "ROLLBACK"
                    continue

                self.action_counter += 1
                current = cycle.after_frame
                self.append_frame(self._convert_raw_frame_data(current))

                if current.state is GameState.GAME_OVER:
                    if self.action_counter >= self.MAX_ACTIONS:
                        self.max_action_exhausted = True
                        self.final_status = "MAX_ACTION_STOP"
                        break
                    recovered = self.runtime.recover(cycle, current)
                    self.recoveries.append(recovered)
                    self.action_counter += 1
                    current = recovered.execution.reset_frame
                    self.append_frame(self._convert_raw_frame_data(current))
                    self.final_status = "ROLLBACK"
                elif current.state is GameState.WIN:
                    self.final_status = "STOP"
                    break
            else:
                self.max_action_exhausted = True
                self.final_status = "MAX_ACTION_STOP"
        finally:
            self.cleanup()

    def report(self) -> P10SampleAgentReport:
        context = self.runtime.context_state.snapshot()
        memory = self.runtime.components.memory
        if memory is None:
            raise RuntimeError("P10_MEMORY_SUBJECT_REQUIRED")
        snapshot = memory.view()
        latest = (
            self.frames[-1]
            if self.frames
            else FrameData(levels_completed=0, win_levels=0)
        )
        memory_influenced = sum(
            cycle.kernel_result.memory_influenced_decision
            for cycle in self.cycles
        )
        rollback_versions = tuple(
            (
                recovery.execution.memory_version_before,
                recovery.execution.memory_version_after,
            )
            for recovery in self.recoveries
        )
        search_reset_versions = tuple(
            (
                reset.execution.memory_version_before,
                reset.execution.memory_version_after,
            )
            for reset in self.search_resets
        )
        return P10SampleAgentReport(
            game_id=self.game_id,
            instruction_variant=self.runtime.instruction_variant,
            actions=self.action_counter,
            recoveries=len(self.recoveries),
            search_resets=len(self.search_resets),
            levels_completed=int(latest.levels_completed),
            win_levels=int(latest.win_levels),
            terminal_state=str(latest.state.value),
            final_status=self.final_status,
            complete=latest.state is GameState.WIN,
            max_action_exhausted=self.max_action_exhausted,
            memory_version=snapshot.version,
            memory_operations=tuple(
                cycle.kernel_result.memory_result.operation
                for cycle in self.cycles
                if cycle.kernel_result.memory_result is not None
            ),
            context_version=context.version,
            context_actions_used=context.actions_used,
            memory_influenced_cycle_count=memory_influenced,
            visual_operator_version=VISUAL_OPERATOR_VERSION,
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
            trace_digests=tuple(
                cycle.kernel_result.trace_digest for cycle in self.cycles
            ),
            trace_events=tuple(
                tuple(
                    dataclasses.asdict(event)
                    for event in cycle.kernel_result.trace
                )
                for cycle in self.cycles
            ),
            rollback_decision_ids=tuple(
                recovery.rollback_decision_id
                for recovery in self.recoveries
            ),
            rollback_memory_versions=rollback_versions,
            failure_payload_digests=tuple(
                recovery.failure_payload_digest
                for recovery in self.recoveries
            ),
            search_reset_decision_ids=tuple(
                reset.reset_decision_id for reset in self.search_resets
            ),
            search_reset_memory_versions=search_reset_versions,
            search_reset_payload_digests=tuple(
                reset.memory_payload_digest for reset in self.search_resets
            ),
            search_reset_evidence_signatures=tuple(
                reset.evidence_signature for reset in self.search_resets
            ),
        )

    def is_done(self, frames: list[FrameData], latest_frame: FrameData) -> bool:
        del frames
        return latest_frame.state is GameState.WIN

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


__all__ = ["P10SampleAgent", "P10SampleAgentReport"]
