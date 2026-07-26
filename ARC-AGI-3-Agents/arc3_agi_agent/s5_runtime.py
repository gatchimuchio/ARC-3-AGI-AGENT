"""Integrated rendered-only S5 OFFLINE Runtime Student."""

from __future__ import annotations

import functools
from dataclasses import dataclass, field

import numpy as np
from arc_agi import OperationMode  # type: ignore[import-untyped]
from arcengine import FrameDataRaw

from .adapters.offline_arcade import OfflineArcadeEmissionInterface
from .context import BoundedContextState
from .ir import CandidateIR
from .kernel import Layer0Components
from .memory import MemoryMutationResult, PassiveMemory
from .protocol import AuthorityViolation
from .s5_authority import (
    HDSOutcomeRetentionController,
    HDSPolicyResetController,
    PureLLMOutcomeRetentionExecutor,
    PureLLMPolicyResetExecutor,
    S5OutcomeRetentionDecision,
    S5PolicyResetDecision,
    S5PolicyResetExecution,
)
from .s5_compute import (
    S5RenderedCandidateSurface,
    S5RenderedPolicyCompute,
)
from .s5_policy import (
    S5_HISTORY_TARGET,
    S5_RESET_ACTION_ID,
    S5HistoryRecord,
    S5RenderedPolicyBody,
    load_s5_rendered_policy_body,
    s5_history_from_memory,
    s5_render_digest,
)
from .sample_runtime import OfflineSampleRuntime, SampleCycleResult
from .schema import digest_object

S5_MEMORY_HISTORY_SNAPSHOT_LIMIT = 3


def _s5_components(
    context: BoundedContextState,
    emission: OfflineArcadeEmissionInterface,
    *,
    instruction_body: S5RenderedPolicyBody,
) -> Layer0Components:
    return Layer0Components(
        context_state=context,
        candidate_surface=S5RenderedCandidateSurface(),
        instruction_body=instruction_body,
        emission_interface=emission,
        compute=S5RenderedPolicyCompute(),
        memory=PassiveMemory(
            max_entries=1,
            max_history_snapshots=S5_MEMORY_HISTORY_SNAPSHOT_LIMIT,
        ),
    )


def _selected_candidate(cycle: SampleCycleResult) -> CandidateIR:
    emission = cycle.kernel_result.emission_result
    if emission is None:
        raise ValueError("S5 emission result required")
    selected = next(
        (
            item
            for item in cycle.kernel_result.candidates
            if item.candidate_id == emission.candidate_id
        ),
        None,
    )
    if selected is None or not selected.steps:
        raise RuntimeError("S5_SELECTED_CANDIDATE_MISSING")
    return selected


def _candidate_integer(
    candidate: CandidateIR,
    key: str,
    *,
    default: int | None = None,
) -> int:
    value = candidate.steps[0].get(key)
    if value is None and default is not None:
        return default
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"S5_CANDIDATE_{key.upper()}_INVALID")
    return value


@dataclass(frozen=True, slots=True)
class S5StepResult:
    kernel_cycle: SampleCycleResult
    after_frame: FrameDataRaw
    action_id: int
    policy_reset: S5PolicyResetExecution | None = None
    outcome_retention: MemoryMutationResult | None = None
    authority_decision_id: str = ""
    follow_up_authority_decision: (
        S5OutcomeRetentionDecision | S5PolicyResetDecision | None
    ) = None


@dataclass(slots=True)
class S5OfflineSampleRuntime:
    """Compose C, J, M and P without accepting environment identity."""

    environment: object
    operation_mode: OperationMode
    max_actions: int = 4096
    instruction_body: S5RenderedPolicyBody | None = field(
        default=None,
        repr=False,
    )
    runtime: OfflineSampleRuntime = field(init=False)
    outcome_retention_controller: HDSOutcomeRetentionController = field(
        default_factory=HDSOutcomeRetentionController,
        init=False,
    )
    outcome_retention_executor: PureLLMOutcomeRetentionExecutor = field(
        default_factory=PureLLMOutcomeRetentionExecutor,
        init=False,
    )
    policy_reset_controller: HDSPolicyResetController = field(
        default_factory=HDSPolicyResetController,
        init=False,
    )
    policy_reset_executor: PureLLMPolicyResetExecutor = field(
        default_factory=PureLLMPolicyResetExecutor,
        init=False,
    )

    def __post_init__(self) -> None:
        if self.operation_mode is not OperationMode.OFFLINE:
            raise AuthorityViolation("S5_OFFLINE_MODE_REQUIRED")
        body = self.instruction_body or load_s5_rendered_policy_body()
        failures = body.validate()
        if failures:
            raise ValueError(";".join(failures))
        self.instruction_body = body
        self.runtime = OfflineSampleRuntime(
            environment=self.environment,
            operation_mode=self.operation_mode,
            max_actions=self.max_actions,
            component_factory=functools.partial(
                _s5_components,
                instruction_body=body,
            ),
        )

    @property
    def components(self) -> Layer0Components:
        return self.runtime.components

    @property
    def context_state(self) -> BoundedContextState:
        return self.runtime.context_state

    def _release(self, cycle: SampleCycleResult) -> None:
        self.components.hds.release_cycle_binding(
            cycle.kernel_result.decision,
            status=cycle.kernel_result.status,
        )
        if self.components.hds.retained_compute_binding_count:
            raise RuntimeError("S5_HDS_COMPUTE_BINDING_NOT_RELEASED")

    def _retain_failed_outcome(
        self,
        cycle: SampleCycleResult,
    ) -> tuple[MemoryMutationResult, S5OutcomeRetentionDecision]:
        emission = cycle.kernel_result.emission_result
        if emission is None or emission.terminal_state != "GAME_OVER":
            raise ValueError("S5_GAME_OVER_RESULT_REQUIRED")
        if cycle.kernel_result.status != "REJECT":
            raise AuthorityViolation("S5_GAME_OVER_HDS_REJECTION_REQUIRED")
        if cycle.kernel_result.memory_result is not None:
            raise AuthorityViolation("S5_REJECTED_MEMORY_WRITE_FORBIDDEN")
        memory = self.components.memory
        body = self.instruction_body
        if memory is None or body is None:
            raise RuntimeError("S5_MEMORY_AND_POLICY_REQUIRED")
        selected = _selected_candidate(cycle)
        after_frame = cycle.after_frame
        if after_frame is None:
            raise RuntimeError("S5_FAILED_OUTCOME_FRAME_MISSING")
        action_id = _candidate_integer(selected, "action_id")
        if action_id == S5_RESET_ACTION_ID:
            raise ValueError("S5_FAILURE_ACTION_INVALID")
        horizontal = _candidate_integer(
            selected,
            "x",
            default=-1,
        )
        vertical = _candidate_integer(
            selected,
            "y",
            default=-1,
        )
        palette = _candidate_integer(
            selected,
            "target_palette",
            default=0,
        )
        state = s5_history_from_memory(memory.view()).finalize_pending(
            cycle.kernel_result.observation
        )
        before_layers = cycle.kernel_result.observation.rendered_layers
        after_layers = self.runtime.frame_adapter.project(
            after_frame
        ).layers
        if not before_layers or not after_layers:
            raise RuntimeError("S5_FAILED_OUTCOME_RENDER_MISSING")
        rendered_changed = s5_render_digest(
            np.asarray(before_layers[-1], dtype=np.uint8)
        ) != s5_render_digest(
            np.asarray(after_layers[-1], dtype=np.uint8)
        )
        retained = state.retain_observed(
            S5HistoryRecord(
                action_id=action_id,
                horizontal=horizontal,
                vertical=vertical,
                target_palette=palette,
                visible_change=rendered_changed,
                compatibility_reset=False,
            )
        )
        payload = retained.to_payload(
            input_memory_digest=memory.view().digest,
            policy_digest=body.digest(),
            memory_influenced_decision=bool(retained.history),
        )
        decision = self.outcome_retention_controller.judge(
            observation_signature=emission.result_observation_signature,
            result_signature=emission.result_signature,
            candidate_digest=digest_object(selected),
            memory_version=memory.version,
        )
        directive = self.outcome_retention_controller.directive(
            decision,
            memory_target=S5_HISTORY_TARGET,
            memory_payload=payload,
        )
        result = self.outcome_retention_executor.execute(
            directive,
            decision,
            payload,
            memory,
        )
        return result, decision

    def _execute_policy_reset(
        self,
        cycle: SampleCycleResult,
        current: FrameDataRaw,
    ) -> tuple[S5PolicyResetExecution, S5PolicyResetDecision]:
        if cycle.kernel_result.emission_result is not None:
            raise ValueError("S5 reset requires no normal emission")
        permitted_status = (
            cycle.kernel_result.status == "SUSPEND"
            or (
                cycle.kernel_result.status == "REJECT"
                and str(current.state.value).upper() == "GAME_OVER"
                and "HAZARD_ACTION_VETO"
                in cycle.kernel_result.decision.reason_codes
            )
        )
        if not permitted_status:
            raise AuthorityViolation(
                "S5_RESET_REQUIRES_HDS_SUSPEND_OR_HAZARD_REJECTION"
            )
        memory = self.components.memory
        body = self.instruction_body
        if memory is None or body is None:
            raise RuntimeError("S5_MEMORY_AND_POLICY_REQUIRED")
        context = self.context_state.snapshot()
        policy_decision, state = body.predict(
            cycle.kernel_result.observation,
            context,
            memory.view(),
        )
        if (
            policy_decision.action_id != S5_RESET_ACTION_ID
            or policy_decision.compatibility_reset is not True
        ):
            raise AuthorityViolation(
                "S5_NO_EMISSION_FOR_POLICY_ACTION:"
                f"status={cycle.kernel_result.status}:"
                f"reasons={','.join(cycle.kernel_result.decision.reason_codes)}:"
                f"action={policy_decision.action_id}"
            )
        pending = state.with_pending(policy_decision.pending_record())
        payload = pending.to_payload(
            input_memory_digest=memory.view().digest,
            policy_digest=body.digest(),
            memory_influenced_decision=policy_decision.memory_influenced,
        )
        observation_signature = self.runtime.frame_adapter.signature(current)
        decision = self.policy_reset_controller.judge(
            observation_signature=observation_signature,
            terminal_state=str(current.state.value).upper(),
            policy_digest=body.digest(),
            query_digest=cycle.kernel_result.instruction_query_digest,
            policy_decision=policy_decision,
            memory_version=memory.version,
        )
        directive = self.policy_reset_controller.directive(
            decision,
            memory_target=S5_HISTORY_TARGET,
            memory_payload=payload,
        )
        execution = self.policy_reset_executor.execute(
            directive,
            decision,
            payload,
            memory,
            self.runtime.emission,
        )
        effects = self.runtime.frame_adapter.visible_effects(
            execution.reset_frame,
            current,
        )
        self.context_state.record_emission(
            S5_RESET_ACTION_ID,
            effects,
        )
        self.runtime.bind_recovery_observation(current)
        return execution, decision

    def run_cycle(
        self,
        current: FrameDataRaw,
        *,
        action_count: int,
    ) -> S5StepResult:
        cycle = self.runtime.run_cycle(
            current,
            action_count=action_count,
        )
        self._release(cycle)
        emission = cycle.kernel_result.emission_result
        if emission is not None:
            after = cycle.after_frame
            if after is None:
                raise RuntimeError("S5_REOBSERVATION_MISSING")
            retention: MemoryMutationResult | None = None
            authority_decision_id = cycle.kernel_result.decision.decision_id
            follow_up_decision: S5OutcomeRetentionDecision | None = None
            if emission.terminal_state == "GAME_OVER":
                retention, follow_up_decision = (
                    self._retain_failed_outcome(cycle)
                )
                authority_decision_id = follow_up_decision.decision_id
            return S5StepResult(
                kernel_cycle=cycle,
                after_frame=after,
                action_id=emission.action_id,
                outcome_retention=retention,
                authority_decision_id=authority_decision_id,
                follow_up_authority_decision=follow_up_decision,
            )

        reset, decision = self._execute_policy_reset(cycle, current)
        return S5StepResult(
            kernel_cycle=cycle,
            after_frame=reset.reset_frame,
            action_id=S5_RESET_ACTION_ID,
            policy_reset=reset,
            authority_decision_id=decision.decision_id,
            follow_up_authority_decision=decision,
        )


__all__ = [
    "S5_MEMORY_HISTORY_SNAPSHOT_LIMIT",
    "S5OfflineSampleRuntime",
    "S5StepResult",
]
