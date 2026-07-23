"""Persistent Layer-0 runtime for one bundled ARC-AGI-3 sample episode."""

from __future__ import annotations

from dataclasses import dataclass, field

from arc_agi import OperationMode  # type: ignore[import-untyped]
from arcengine import FrameDataRaw

from .adapters.offline_arcade import OfflineArcadeEmissionInterface
from .context import BoundedContextState
from .kernel import KernelResult, Layer0Components, Layer0Kernel
from .sample_observation import SampleFrameAdapter
from .verification import VerificationResult, verify_rendered_transition


@dataclass(frozen=True, slots=True)
class SampleCycleResult:
    kernel_result: KernelResult
    after_frame: FrameDataRaw | None
    verification: VerificationResult | None


@dataclass(slots=True)
class OfflineSampleRuntime:
    """Keep context and passive memory alive across OFFLINE sample actions."""

    environment: object
    operation_mode: OperationMode
    max_actions: int = 8
    frame_adapter: SampleFrameAdapter = field(default_factory=SampleFrameAdapter)
    context_state: BoundedContextState = field(init=False)
    components: Layer0Components = field(init=False)
    kernel: Layer0Kernel = field(init=False)
    emission: OfflineArcadeEmissionInterface = field(init=False)
    _previous_frame: FrameDataRaw | None = field(
        default=None, init=False, repr=False
    )

    def __post_init__(self) -> None:
        if self.max_actions < 1:
            raise ValueError("max_actions must be positive")
        self.emission = OfflineArcadeEmissionInterface(
            environment=self.environment,
            operation_mode=self.operation_mode,
            frame_adapter=self.frame_adapter,
        )
        self.context_state = BoundedContextState(
            action_budget=self.max_actions
        )
        self.components = Layer0Components(
            context_state=self.context_state,
            emission_interface=self.emission,
        )
        self.kernel = Layer0Kernel(self.components)

    def run_cycle(
        self,
        current: FrameDataRaw,
        *,
        action_count: int,
    ) -> SampleCycleResult:
        before = self.frame_adapter.rendered_observation(
            current,
            self._previous_frame,
            action_count=action_count,
            max_actions=self.max_actions,
        )
        raw_observation = self.frame_adapter.runtime_observation(
            current,
            self._previous_frame,
        )
        self.emission.bind(current)
        kernel_result = self.kernel.run_cycle(raw_observation)
        after_frame = self.emission.last_frame
        verification: VerificationResult | None = None

        if kernel_result.emission_result is not None:
            if after_frame is None:
                raise RuntimeError("OFFLINE_SAMPLE_REOBSERVATION_MISSING")
            after = self.frame_adapter.rendered_observation(
                after_frame,
                current,
                action_count=action_count + 1,
                max_actions=self.max_actions,
            )
            selected = next(
                (
                    candidate
                    for candidate in kernel_result.candidates
                    if candidate.candidate_id
                    == kernel_result.emission_result.candidate_id
                ),
                None,
            )
            if selected is None:
                raise RuntimeError("OFFLINE_SAMPLE_SELECTED_CANDIDATE_MISSING")
            expected_effects = tuple(
                sorted(
                    {
                        effect
                        for values in selected.expected_effects_by_hypothesis.values()
                        for effect in values
                    }
                )
            )
            verification = verify_rendered_transition(
                before,
                after,
                kernel_result.emission_result.action_id,
                expected_effects,
            )
            if verification.status == "FAIL":
                self.context_state.record_failure(
                    "OFFLINE_VERIFICATION:"
                    + ",".join(verification.reason_codes)
                )

        self._previous_frame = current
        return SampleCycleResult(
            kernel_result=kernel_result,
            after_frame=after_frame,
            verification=verification,
        )


__all__ = ["OfflineSampleRuntime", "SampleCycleResult"]
