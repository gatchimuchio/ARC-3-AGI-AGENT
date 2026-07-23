"""P10 OFFLINE runtime with visual compute and integrated rollback."""

from __future__ import annotations

from dataclasses import dataclass, field

from arc_agi import OperationMode  # type: ignore[import-untyped]
from arcengine import FrameDataRaw

from .adapters.offline_arcade import OfflineArcadeEmissionInterface
from .context import BoundedContextState
from .kernel import Layer0Components
from .p10_compute import (
    P10VisualCandidateSurface,
    P10VisualCompute,
    compile_visual_failure_payload,
)
from .recovery import (
    HDSRecoveryController,
    PureLLMRecoveryExecutor,
    RecoveryExecutionResult,
)
from .sample_runtime import OfflineSampleRuntime, SampleCycleResult
from .schema import digest_object


def _p10_components(
    context: BoundedContextState,
    emission: OfflineArcadeEmissionInterface,
) -> Layer0Components:
    return Layer0Components(
        context_state=context,
        candidate_surface=P10VisualCandidateSurface(),
        emission_interface=emission,
        compute=P10VisualCompute(),
    )


@dataclass(frozen=True, slots=True)
class P10RecoveryResult:
    execution: RecoveryExecutionResult
    failure_payload_digest: str
    rollback_decision_id: str


@dataclass(slots=True)
class P10OfflineSampleRuntime:
    """Compose the P1 kernel with P10-only compute and recovery components."""

    environment: object
    operation_mode: OperationMode
    max_actions: int = 4096
    runtime: OfflineSampleRuntime = field(init=False)
    recovery_controller: HDSRecoveryController = field(
        default_factory=HDSRecoveryController,
        init=False,
    )
    recovery_executor: PureLLMRecoveryExecutor = field(
        default_factory=PureLLMRecoveryExecutor,
        init=False,
    )
    level_checkpoint_version: int = field(default=0, init=False)
    _observed_progress_count: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        self.runtime = OfflineSampleRuntime(
            environment=self.environment,
            operation_mode=self.operation_mode,
            max_actions=self.max_actions,
            component_factory=_p10_components,
        )

    @property
    def components(self) -> Layer0Components:
        return self.runtime.components

    @property
    def context_state(self) -> BoundedContextState:
        return self.runtime.context_state

    def run_cycle(
        self,
        current: FrameDataRaw,
        *,
        action_count: int,
    ) -> SampleCycleResult:
        memory = self.components.memory
        if memory is None:
            raise RuntimeError("P10_MEMORY_SUBJECT_REQUIRED")
        if current.levels_completed > self._observed_progress_count:
            self.level_checkpoint_version = memory.version
            self._observed_progress_count = current.levels_completed
        return self.runtime.run_cycle(
            current,
            action_count=action_count,
        )

    def recover(
        self,
        failed_cycle: SampleCycleResult,
        failed_frame: FrameDataRaw,
    ) -> P10RecoveryResult:
        result = failed_cycle.kernel_result.emission_result
        if result is None or result.terminal_state != "GAME_OVER":
            raise ValueError("P10 recovery requires GAME_OVER emission result")
        selected = next(
            (
                candidate
                for candidate in failed_cycle.kernel_result.candidates
                if candidate.candidate_id == result.candidate_id
            ),
            None,
        )
        if selected is None:
            raise RuntimeError("P10 recovery candidate missing")
        memory = self.components.memory
        if memory is None:
            raise RuntimeError("P10_MEMORY_SUBJECT_REQUIRED")
        before = memory.view()
        failure_payload = compile_visual_failure_payload(
            before,
            selected,
            result.result_signature,
        )
        rollback_version = min(
            self.level_checkpoint_version,
            before.version,
        )
        decision = self.recovery_controller.judge(
            result,
            selected,
            rollback_version=rollback_version,
            memory_version=before.version,
        )
        failure_target = "visual-recovery:" + digest_object(
            {
                "result": result.result_signature,
                "rollback_version": rollback_version,
            }
        )[:24]
        directive = self.recovery_controller.directive(
            decision,
            memory_version=before.version,
            failure_target=failure_target,
            failure_payload=failure_payload,
        )
        execution = self.recovery_executor.execute(
            directive,
            decision,
            failure_payload,
            memory,
            self.runtime.emission,
        )
        self.context_state.record_failure(
            "P10_ROLLBACK:" + result.result_signature
        )
        self.runtime.bind_recovery_observation(failed_frame)
        return P10RecoveryResult(
            execution=execution,
            failure_payload_digest=digest_object(failure_payload),
            rollback_decision_id=decision.decision_id,
        )


__all__ = [
    "P10OfflineSampleRuntime",
    "P10RecoveryResult",
]
