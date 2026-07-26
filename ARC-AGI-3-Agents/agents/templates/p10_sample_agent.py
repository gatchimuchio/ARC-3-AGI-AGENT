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
    P10InstructionLifecycle,
    P10InstructionVariant,
    P10OfflineSampleRuntime,
    P10RecoveryResult,
    P10SearchResetResult,
)
from arc3_agi_agent.p_update import (
    CandidatePBundle,
    HDSPUpdateAuthority,
    PUpdateDecision,
)
from arc3_agi_agent.protocol import AuthorityViolation
from arc3_agi_agent.sample_runtime import SampleCycleResult

from ..agent import Agent


@dataclass(frozen=True, slots=True)
class P10CycleAuditRecord:
    """Compact complete report material for one already-closed cycle."""

    memory_operation: str | None
    memory_influenced_decision: bool
    instruction_body_format: str
    instruction_body_version: str
    instruction_body_digest: str
    instruction_query_digest: str
    decision_status: str
    verification_status: str | None
    emitted_steps: tuple[dict[str, object], ...]
    emitted_provenance: tuple[str, ...]
    emitted_level_count: int | None
    trace_digest: str
    trace_events: tuple[dict[str, object], ...]


@dataclass(frozen=True, slots=True)
class P10SampleAgentReport:
    game_id: str
    instruction_variant: P10InstructionVariant
    instruction_lifecycle: P10InstructionLifecycle
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
    emitted_steps: tuple[tuple[dict[str, object], ...], ...]
    emitted_provenance: tuple[tuple[str, ...], ...]
    emitted_level_counts: tuple[int, ...]
    trace_digests: tuple[str, ...]
    trace_events: tuple[tuple[dict[str, object], ...], ...]
    rollback_decision_ids: tuple[str, ...]
    rollback_memory_versions: tuple[tuple[int, int], ...]
    failure_payload_digests: tuple[str, ...]
    search_reset_decision_ids: tuple[str, ...]
    search_reset_memory_versions: tuple[tuple[int, int], ...]
    search_reset_payload_digests: tuple[str, ...]
    search_reset_evidence_signatures: tuple[str, ...]
    development_transition_probe: dict[str, object]
    development_prospective_relation_probe: dict[str, object]


class P10SampleAgent(Agent):
    """Run one retained sample only through the P10 Trinity boundaries."""

    def __init__(
        self,
        *args: Any,
        operation_mode: OperationMode,
        max_actions: int = 4096,
        instruction_variant: P10InstructionVariant = "hybrid",
        instruction_lifecycle: P10InstructionLifecycle = "active",
        p_update_authority: HDSPUpdateAuthority | None = None,
        p_update_decision: PUpdateDecision | None = None,
        candidate_bundle: CandidatePBundle | None = None,
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
        self.cycles: list[P10CycleAuditRecord] = []
        self.recoveries: list[P10RecoveryResult] = []
        self.search_resets: list[P10SearchResetResult] = []
        self.final_status = "NOT_STARTED"
        self.max_action_exhausted = False
        self.runtime = P10OfflineSampleRuntime(
            environment=self.arc_env,
            operation_mode=operation_mode,
            max_actions=max_actions,
            instruction_variant=instruction_variant,
            instruction_lifecycle=instruction_lifecycle,
            p_update_authority=p_update_authority,
            p_update_decision=p_update_decision,
            candidate_bundle=candidate_bundle,
        )

    @property
    def name(self) -> str:
        return f"{super().name}.{self.MAX_ACTIONS}"

    def append_frame(self, frame: FrameData) -> None:
        """Record when requested, but retain only the latest rendered frame."""

        super().append_frame(frame)
        if len(self.frames) > 1:
            del self.frames[:-1]

    @staticmethod
    def _audit_cycle(cycle: SampleCycleResult) -> P10CycleAuditRecord:
        result = cycle.kernel_result
        emission = result.emission_result
        emitted_steps: tuple[dict[str, object], ...] = ()
        emitted_provenance: tuple[str, ...] = ()
        emitted_level_count: int | None = None
        if emission is not None:
            selected = next(
                (
                    candidate
                    for candidate in result.candidates
                    if candidate.candidate_id == emission.candidate_id
                ),
                None,
            )
            if selected is None:
                raise RuntimeError(
                    "P10_REPORT_EMITTED_CANDIDATE_MISSING"
                )
            emitted_steps = tuple(dict(step) for step in selected.steps)
            emitted_provenance = selected.provenance
            emitted_level_count = emission.levels_completed
        return P10CycleAuditRecord(
            memory_operation=(
                None
                if result.memory_result is None
                else result.memory_result.operation
            ),
            memory_influenced_decision=result.memory_influenced_decision,
            instruction_body_format=result.instruction_body_format,
            instruction_body_version=result.instruction_body_version,
            instruction_body_digest=result.instruction_body_digest,
            instruction_query_digest=result.instruction_query_digest,
            decision_status=result.decision.status,
            verification_status=(
                None
                if cycle.verification is None
                else cycle.verification.status
            ),
            emitted_steps=emitted_steps,
            emitted_provenance=emitted_provenance,
            emitted_level_count=emitted_level_count,
            trace_digest=result.trace_digest,
            trace_events=tuple(
                dataclasses.asdict(event) for event in result.trace
            ),
        )

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
                self.cycles.append(self._audit_cycle(cycle))
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
            cycle.memory_influenced_decision
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
            instruction_lifecycle=self.runtime.instruction_lifecycle,
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
                cycle.memory_operation
                for cycle in self.cycles
                if cycle.memory_operation is not None
            ),
            context_version=context.version,
            context_actions_used=context.actions_used,
            memory_influenced_cycle_count=memory_influenced,
            visual_operator_version=VISUAL_OPERATOR_VERSION,
            instruction_body_formats=tuple(
                cycle.instruction_body_format
                for cycle in self.cycles
            ),
            instruction_body_versions=tuple(
                cycle.instruction_body_version
                for cycle in self.cycles
            ),
            instruction_body_digests=tuple(
                cycle.instruction_body_digest
                for cycle in self.cycles
            ),
            instruction_query_digests=tuple(
                cycle.instruction_query_digest
                for cycle in self.cycles
            ),
            decision_statuses=tuple(
                cycle.decision_status for cycle in self.cycles
            ),
            verification_statuses=tuple(
                cycle.verification_status
                for cycle in self.cycles
                if cycle.verification_status is not None
            ),
            emitted_steps=tuple(
                cycle.emitted_steps
                for cycle in self.cycles
                if cycle.emitted_level_count is not None
            ),
            emitted_provenance=tuple(
                cycle.emitted_provenance
                for cycle in self.cycles
                if cycle.emitted_level_count is not None
            ),
            emitted_level_counts=tuple(
                cycle.emitted_level_count
                for cycle in self.cycles
                if cycle.emitted_level_count is not None
            ),
            trace_digests=tuple(
                cycle.trace_digest for cycle in self.cycles
            ),
            trace_events=tuple(
                cycle.trace_events for cycle in self.cycles
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
            development_transition_probe=(
                self.runtime.transition_probe.to_payload()
            ),
            development_prospective_relation_probe=(
                self.runtime.prospective_relation_probe.to_payload()
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


__all__ = [
    "P10CycleAuditRecord",
    "P10SampleAgent",
    "P10SampleAgentReport",
]
