from __future__ import annotations

import unittest

import numpy as np
from arc_agi import OperationMode
from arc_agi.local_wrapper import LocalEnvironmentWrapper
from arcengine import FrameDataRaw, GameAction, GameState

from arc3_agi_agent.adapters.in_memory import EmissionResult
from arc3_agi_agent.ir import CandidateIR
from arc3_agi_agent.memory import PassiveMemory
from arc3_agi_agent.p10_runtime import P10OfflineSampleRuntime
from arc3_agi_agent.protocol import AuthorityViolation
from arc3_agi_agent.recovery import (
    HDSRecoveryController,
    PureLLMRecoveryExecutor,
    RecoveryDirective,
    require_recovery_directive,
)


def frame(
    values: list[list[int]],
    *,
    state: GameState = GameState.NOT_FINISHED,
) -> FrameDataRaw:
    result = FrameDataRaw(
        game_id="external-test-identity",
        state=state,
        levels_completed=0,
        win_levels=3,
        available_actions=[1, 2, 6],
    )
    result.frame = [np.asarray(values, dtype=np.int8)]
    return result


class SequencedOfflineEnvironment(LocalEnvironmentWrapper):
    def __init__(
        self,
        action_results: list[FrameDataRaw],
        reset_result: FrameDataRaw,
    ) -> None:
        self.action_results = list(action_results)
        self.reset_result = reset_result
        self.calls: list[GameAction] = []

    def step(
        self,
        action: GameAction,
        *,
        data: dict[str, int],
        reasoning: dict[str, str],
    ) -> FrameDataRaw:
        del data, reasoning
        self.calls.append(action)
        if action is GameAction.RESET:
            return self.reset_result
        if not self.action_results:
            raise AssertionError("unexpected action")
        return self.action_results.pop(0)


class RecoveryBoundary:
    def __init__(self, reset_frame: FrameDataRaw) -> None:
        self.reset_frame = reset_frame
        self.calls = 0

    def recover(
        self,
        directive: RecoveryDirective,
        decision: object,
        *,
        executor: str,
    ) -> FrameDataRaw:
        require_recovery_directive(
            directive,
            decision,  # type: ignore[arg-type]
            executor=executor,
        )
        self.calls += 1
        return self.reset_frame


def hazardous_result() -> EmissionResult:
    return EmissionResult(
        candidate_id="candidate:visible-hazard",
        action_id=1,
        status="EMITTED_OFFLINE_SAMPLE",
        result_signature="emission-result:visible-hazard",
        visible_effects=("IRREVERSIBLE_FAILURE",),
        terminal_state="GAME_OVER",
    )


def hazardous_candidate() -> CandidateIR:
    return CandidateIR(
        candidate_id="candidate:visible-hazard",
        mode="ACTION",
        steps=(
            {
                "action_id": 1,
                "visual_action_key": "simple:1",
                "visual_source_signature": "visual-state:source",
            },
        ),
        provenance=("rendered-observation",),
    )


class P10RecoveryTests(unittest.TestCase):
    def test_hds_directive_is_single_use_and_retains_failure(self) -> None:
        memory = PassiveMemory()
        controller = HDSRecoveryController()
        result = hazardous_result()
        candidate = hazardous_candidate()
        payload = {
            "format": "arc3-p10-visual-memory-v1",
            "observed_failure_signature": result.result_signature,
        }
        decision = controller.judge(
            result,
            candidate,
            rollback_version=0,
            memory_version=0,
        )
        directive = controller.directive(
            decision,
            memory_version=0,
            failure_target="visual-recovery:observed-hazard",
            failure_payload=payload,
        )
        boundary = RecoveryBoundary(frame([[0, 0], [0, 1]]))

        execution = PureLLMRecoveryExecutor().execute(
            directive,
            decision,
            payload,
            memory,
            boundary,
        )

        self.assertEqual(boundary.calls, 1)
        self.assertIsNone(execution.rollback_result)
        self.assertEqual(execution.memory_version_before, 0)
        self.assertEqual(execution.memory_version_after, 1)
        retained = memory.view().entries[-1]
        self.assertEqual(retained.lifecycle, "REJECTED")
        self.assertEqual(retained.payload, payload)
        with self.assertRaisesRegex(
            AuthorityViolation,
            "RECOVERY_DIRECTIVE_ALREADY_CONSUMED",
        ):
            PureLLMRecoveryExecutor().execute(
                directive,
                decision,
                payload,
                memory,
                boundary,
            )
        self.assertEqual(boundary.calls, 1)

    def test_forged_directive_cannot_mutate_memory_or_reset(self) -> None:
        memory = PassiveMemory()
        controller = HDSRecoveryController()
        result = hazardous_result()
        decision = controller.judge(
            result,
            hazardous_candidate(),
            rollback_version=0,
            memory_version=0,
        )
        forged = RecoveryDirective(
            decision_id=decision.decision_id,
            result_signature=decision.result_signature,
            rollback_version=0,
            expected_memory_version=0,
            failure_target="visual-recovery:forged",
            failure_payload_digest="forged",
        )
        boundary = RecoveryBoundary(frame([[0, 0], [0, 1]]))

        with self.assertRaisesRegex(
            AuthorityViolation,
            "RECOVERY_DIRECTIVE_NOT_ISSUED_BY_HDS",
        ):
            PureLLMRecoveryExecutor().execute(
                forged,
                decision,
                {"format": "forged"},
                memory,
                boundary,
            )
        self.assertEqual(memory.version, 0)
        self.assertEqual(boundary.calls, 0)

    def test_runtime_rolls_back_then_memory_changes_next_action(self) -> None:
        initial = frame(
            [
                [0, 0, 0, 0],
                [0, 8, 8, 0],
                [0, 8, 8, 0],
                [0, 0, 0, 0],
            ]
        )
        safe = frame(
            [
                [0, 0, 0, 0],
                [0, 8, 8, 0],
                [0, 8, 8, 0],
                [0, 0, 0, 0],
            ]
        )
        failed = frame(
            [
                [9, 9, 9, 9],
                [9, 9, 9, 9],
                [9, 9, 9, 9],
                [9, 9, 9, 9],
            ],
            state=GameState.GAME_OVER,
        )
        reset = frame(
            [
                [0, 0, 0, 0],
                [0, 8, 8, 0],
                [0, 8, 8, 0],
                [0, 0, 0, 0],
            ]
        )
        environment = SequencedOfflineEnvironment(
            [safe, failed, safe],
            reset,
        )
        runtime = P10OfflineSampleRuntime(
            environment=environment,
            operation_mode=OperationMode.OFFLINE,
            max_actions=8,
        )

        first = runtime.run_cycle(initial, action_count=0)
        second = runtime.run_cycle(safe, action_count=1)
        assert first.kernel_result.emission_result is not None
        assert second.kernel_result.emission_result is not None
        failed_action = second.kernel_result.emission_result.action_id
        self.assertEqual(second.kernel_result.status, "REJECT")
        self.assertEqual(second.after_frame, failed)
        self.assertEqual(runtime.components.memory.view().version, 1)

        recovered = runtime.recover(second, failed)

        self.assertIs(environment.calls[-1], GameAction.RESET)
        self.assertIs(recovered.execution.reset_frame, reset)
        self.assertIsNotNone(recovered.execution.rollback_result)
        self.assertEqual(
            recovered.execution.rollback_result.rollback_to_version,
            0,
        )
        retained = runtime.components.memory.view().entries[-1]
        self.assertEqual(retained.lifecycle, "REJECTED")
        self.assertIn("visual_explorer", retained.payload)

        third = runtime.run_cycle(reset, action_count=2)
        assert third.kernel_result.emission_result is not None
        self.assertNotEqual(
            third.kernel_result.emission_result.action_id,
            failed_action,
        )


if __name__ == "__main__":
    unittest.main()
