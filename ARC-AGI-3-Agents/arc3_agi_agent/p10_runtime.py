"""P10 OFFLINE runtime with visual compute and integrated rollback."""

from __future__ import annotations

import functools
from dataclasses import dataclass, field
from typing import Literal

from arc_agi import OperationMode  # type: ignore[import-untyped]
from arcengine import FrameDataRaw

from .adapters.offline_arcade import OfflineArcadeEmissionInterface
from .context import BoundedContextState
from .instruction_body import (
    InstructionBody,
    load_p10_candidate_hybrid_instruction_body,
    load_p10_candidate_parametric_instruction_body,
    load_p10_candidate_symbolic_instruction_body,
    load_p10_hybrid_instruction_body,
    load_p10_parametric_instruction_body,
    load_p10_symbolic_instruction_body,
)
from .kernel import Layer0Components
from .p10_compute import (
    P10VisualCandidateSurface,
    P10VisualCompute,
    compile_visual_failure_payload,
    prepare_visual_search_reset,
)
from .p_update import CandidatePBundle, HDSPUpdateAuthority, PUpdateDecision
from .protocol import AuthorityViolation
from .recovery import (
    HDSRecoveryController,
    PureLLMRecoveryExecutor,
    RecoveryExecutionResult,
)
from .sample_runtime import OfflineSampleRuntime, SampleCycleResult
from .schema import digest_object
from .search_reset import (
    HDSSearchResetController,
    PureLLMSearchResetExecutor,
    SearchResetExecutionResult,
)
from .visual_explorer import last_rendered_grid

_RESET_ACTION_ID = 0
P10InstructionVariant = Literal["P-A", "P-B", "hybrid"]
P10InstructionLifecycle = Literal["active", "candidate"]


def _candidate_component(variant: P10InstructionVariant) -> str:
    return {
        "P-A": "P-A",
        "P-B": "P-B",
        "hybrid": "hybrid-P-B",
    }[variant]


def _validate_candidate_probe_authorization(
    *,
    instruction_variant: P10InstructionVariant,
    authority: HDSPUpdateAuthority | None,
    decision: PUpdateDecision | None,
    candidate_bundle: CandidatePBundle | None,
) -> CandidatePBundle:
    if authority is None or decision is None or candidate_bundle is None:
        raise AuthorityViolation("P10_CANDIDATE_PROBE_HDS_AUTHORIZATION_REQUIRED")
    failures = [
        *decision.validate(),
        *candidate_bundle.validate(),
    ]
    if not decision.is_owned_by(authority):
        failures.append("P10_CANDIDATE_PROBE_DECISION_NOT_HDS_OWNED")
    if decision.status != "PROBE":
        failures.append("P10_CANDIDATE_PROBE_DECISION_STATUS_INVALID")
    if decision.proposal_digest != candidate_bundle.proposal_digest:
        failures.append("P10_CANDIDATE_PROBE_PROPOSAL_MISMATCH")
    if decision.candidate_bundle_digest != candidate_bundle.digest:
        failures.append("P10_CANDIDATE_PROBE_BUNDLE_MISMATCH")
    if candidate_bundle.lifecycle != "CANDIDATE":
        failures.append("P10_CANDIDATE_PROBE_LIFECYCLE_INVALID")
    if candidate_bundle.target_component != _candidate_component(
        instruction_variant
    ):
        failures.append("P10_CANDIDATE_PROBE_COMPONENT_MISMATCH")
    if failures:
        raise AuthorityViolation(";".join(sorted(set(failures))))
    return candidate_bundle


def _p10_components(
    context: BoundedContextState,
    emission: OfflineArcadeEmissionInterface,
    *,
    instruction_variant: P10InstructionVariant,
    instruction_lifecycle: P10InstructionLifecycle,
    candidate_bundle: CandidatePBundle | None,
) -> Layer0Components:
    instruction_body: InstructionBody
    if instruction_lifecycle == "candidate":
        if instruction_variant == "P-A":
            instruction_body = load_p10_candidate_symbolic_instruction_body()
        elif instruction_variant == "P-B":
            instruction_body = load_p10_candidate_parametric_instruction_body()
        else:
            instruction_body = load_p10_candidate_hybrid_instruction_body()
        if candidate_bundle is None:
            raise AuthorityViolation("P10_CANDIDATE_PROBE_BUNDLE_REQUIRED")
        if instruction_body.body_version != candidate_bundle.body_version:
            raise AuthorityViolation("P10_CANDIDATE_PROBE_VERSION_MISMATCH")
        if instruction_body.digest() != candidate_bundle.body_digest:
            raise AuthorityViolation("P10_CANDIDATE_PROBE_DIGEST_MISMATCH")
    else:
        if instruction_variant == "P-A":
            instruction_body = load_p10_symbolic_instruction_body()
        elif instruction_variant == "P-B":
            instruction_body = load_p10_parametric_instruction_body()
        else:
            instruction_body = load_p10_hybrid_instruction_body()
    return Layer0Components(
        context_state=context,
        candidate_surface=P10VisualCandidateSurface(),
        instruction_body=instruction_body,
        emission_interface=emission,
        compute=P10VisualCompute(),
    )


@dataclass(frozen=True, slots=True)
class P10RecoveryResult:
    execution: RecoveryExecutionResult
    failure_payload_digest: str
    rollback_decision_id: str


@dataclass(frozen=True, slots=True)
class P10SearchResetResult:
    execution: SearchResetExecutionResult
    memory_payload_digest: str
    reset_decision_id: str
    evidence_signature: str


@dataclass(slots=True)
class P10OfflineSampleRuntime:
    """Compose the P1 kernel with P10-only compute and recovery components."""

    environment: object
    operation_mode: OperationMode
    max_actions: int = 4096
    instruction_variant: P10InstructionVariant = "hybrid"
    instruction_lifecycle: P10InstructionLifecycle = "active"
    p_update_authority: HDSPUpdateAuthority | None = field(
        default=None,
        repr=False,
    )
    p_update_decision: PUpdateDecision | None = field(
        default=None,
        repr=False,
    )
    candidate_bundle: CandidatePBundle | None = field(
        default=None,
        repr=False,
    )
    runtime: OfflineSampleRuntime = field(init=False)
    recovery_controller: HDSRecoveryController = field(
        default_factory=HDSRecoveryController,
        init=False,
    )
    recovery_executor: PureLLMRecoveryExecutor = field(
        default_factory=PureLLMRecoveryExecutor,
        init=False,
    )
    search_reset_controller: HDSSearchResetController = field(
        default_factory=HDSSearchResetController,
        init=False,
    )
    search_reset_executor: PureLLMSearchResetExecutor = field(
        default_factory=PureLLMSearchResetExecutor,
        init=False,
    )
    level_checkpoint_version: int = field(default=0, init=False)
    _observed_progress_count: int = field(default=0, init=False)

    def __post_init__(self) -> None:
        if self.instruction_variant not in {"P-A", "P-B", "hybrid"}:
            raise ValueError("P10_INSTRUCTION_VARIANT_INVALID")
        if self.instruction_lifecycle not in {"active", "candidate"}:
            raise ValueError("P10_INSTRUCTION_LIFECYCLE_INVALID")
        if self.instruction_lifecycle == "candidate":
            self.candidate_bundle = _validate_candidate_probe_authorization(
                instruction_variant=self.instruction_variant,
                authority=self.p_update_authority,
                decision=self.p_update_decision,
                candidate_bundle=self.candidate_bundle,
            )
        elif any(
            item is not None
            for item in (
                self.p_update_authority,
                self.p_update_decision,
                self.candidate_bundle,
            )
        ):
            raise AuthorityViolation("P10_ACTIVE_RUNTIME_REJECTS_PROBE_BINDING")
        self.runtime = OfflineSampleRuntime(
            environment=self.environment,
            operation_mode=self.operation_mode,
            max_actions=self.max_actions,
            component_factory=functools.partial(
                _p10_components,
                instruction_variant=self.instruction_variant,
                instruction_lifecycle=self.instruction_lifecycle,
                candidate_bundle=self.candidate_bundle,
            ),
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
        reset_effects = self.runtime.frame_adapter.visible_effects(
            execution.reset_frame,
            failed_frame,
        )
        self.context_state.record_emission(
            _RESET_ACTION_ID,
            reset_effects,
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

    def search_reset(
        self,
        stalled_cycle: SampleCycleResult,
        current_frame: FrameDataRaw,
        *,
        action_count: int,
    ) -> P10SearchResetResult | None:
        """RESET only when C proves a disconnected initial-state frontier."""

        if stalled_cycle.kernel_result.emission_result is not None:
            raise ValueError("P10 search reset requires a no-emission cycle")
        if stalled_cycle.after_frame is not None:
            raise ValueError("P10 search reset requires no action result")
        if stalled_cycle.kernel_result.status != "SUSPEND":
            return None
        memory = self.components.memory
        if memory is None:
            raise RuntimeError("P10_MEMORY_SUBJECT_REQUIRED")
        before = memory.view()
        grid = last_rendered_grid(current_frame.frame)
        if not grid:
            raise RuntimeError("P10_SEARCH_RESET_RENDERED_GRID_MISSING")
        available_actions = tuple(
            sorted(
                {
                    int(action)
                    for action in current_frame.available_actions
                    if isinstance(action, int)
                    and not isinstance(action, bool)
                    and 1 <= int(action) <= 7
                }
            )
        )
        preparation = prepare_visual_search_reset(
            before,
            grid,
            available_actions,
            terminal_state=str(current_frame.state.value).upper(),
        )
        if preparation is None:
            return None
        observation_signature = self.runtime.frame_adapter.signature(
            current_frame
        )
        decision = self.search_reset_controller.judge(
            observation_signature=observation_signature,
            reason=preparation.reason,
            action_count=action_count,
            memory_version=before.version,
            evidence_signature=preparation.evidence_signature,
        )
        directive = self.search_reset_controller.directive(
            decision,
            memory_target=preparation.memory_target,
            memory_payload=preparation.memory_payload,
        )
        execution = self.search_reset_executor.execute(
            directive,
            decision,
            preparation.memory_payload,
            memory,
            self.runtime.emission,
        )
        reset_effects = self.runtime.frame_adapter.visible_effects(
            execution.reset_frame,
            current_frame,
        )
        self.context_state.record_emission(
            _RESET_ACTION_ID,
            reset_effects,
        )
        self.context_state.record_failure(
            "P10_SEARCH_RESET:" + preparation.evidence_signature
        )
        self.runtime.bind_recovery_observation(current_frame)
        return P10SearchResetResult(
            execution=execution,
            memory_payload_digest=digest_object(
                preparation.memory_payload
            ),
            reset_decision_id=decision.decision_id,
            evidence_signature=preparation.evidence_signature,
        )


__all__ = [
    "P10InstructionLifecycle",
    "P10InstructionVariant",
    "P10OfflineSampleRuntime",
    "P10RecoveryResult",
    "P10SearchResetResult",
]
