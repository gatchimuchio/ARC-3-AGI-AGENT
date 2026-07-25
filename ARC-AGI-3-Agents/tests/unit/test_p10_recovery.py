from __future__ import annotations

import unittest

import numpy as np
from arc_agi import OperationMode
from arc_agi.local_wrapper import LocalEnvironmentWrapper
from arcengine import FrameDataRaw, GameAction, GameState

from agents.templates.p10_sample_agent import (
    P10CycleAuditRecord,
    P10SampleAgent,
)
from arc3_agi_agent.adapters.in_memory import EmissionResult
from arc3_agi_agent.ir import CandidateIR
from arc3_agi_agent.memory import PassiveMemory
from arc3_agi_agent.p10_runtime import (
    P10_MEMORY_HISTORY_LIMIT,
    P10OfflineSampleRuntime,
)
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
    levels_completed: int = 0,
    win_levels: int = 3,
) -> FrameDataRaw:
    result = FrameDataRaw(
        game_id="external-test-identity",
        state=state,
        levels_completed=levels_completed,
        win_levels=win_levels,
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
        self._last_response = reset_result
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
            self._last_response = self.reset_result
            return self.reset_result
        if not self.action_results:
            raise AssertionError("unexpected action")
        self._last_response = self.action_results.pop(0)
        return self._last_response


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

    def test_runtime_replaces_working_memory_without_losing_versioning(
        self,
    ) -> None:
        initial = frame(
            [
                [0, 0, 0, 0],
                [0, 8, 8, 0],
                [0, 8, 8, 0],
                [0, 0, 0, 0],
            ]
        )
        after_first = frame(
            [
                [0, 0, 0, 0],
                [0, 9, 9, 0],
                [0, 9, 9, 0],
                [0, 0, 0, 0],
            ]
        )
        after_second = frame(
            [
                [0, 0, 0, 0],
                [0, 10, 10, 0],
                [0, 10, 10, 0],
                [0, 0, 0, 0],
            ]
        )
        environment = SequencedOfflineEnvironment(
            [after_first, after_second],
            initial,
        )
        runtime = P10OfflineSampleRuntime(
            environment=environment,
            operation_mode=OperationMode.OFFLINE,
            max_actions=8,
        )

        first = runtime.run_cycle(initial, action_count=0)
        second = runtime.run_cycle(after_first, action_count=1)

        assert first.kernel_result.memory_result is not None
        assert second.kernel_result.memory_result is not None
        self.assertEqual(first.kernel_result.memory_result.operation, "ADD")
        self.assertEqual(second.kernel_result.memory_result.operation, "REPLACE")
        self.assertFalse(first.kernel_result.memory_influenced_decision)
        self.assertTrue(second.kernel_result.memory_influenced_decision)
        memory = runtime.components.memory
        assert memory is not None
        snapshot = memory.view()
        self.assertEqual(snapshot.version, 2)
        self.assertEqual(len(snapshot.entries), 1)
        self.assertEqual(snapshot.entries[0].operation, "REPLACE")
        self.assertEqual(
            memory.max_history_snapshots,
            P10_MEMORY_HISTORY_LIMIT,
        )
        self.assertEqual(
            runtime.components.hds.retained_compute_binding_count,
            0,
        )

    def test_agent_retains_compact_cycle_audit_and_latest_frame_only(
        self,
    ) -> None:
        initial = frame(
            [
                [0, 0, 0, 0],
                [0, 8, 8, 0],
                [0, 8, 8, 0],
                [0, 0, 0, 0],
            ]
        )
        complete = frame(
            [
                [0, 0, 0, 0],
                [0, 9, 9, 0],
                [0, 9, 9, 0],
                [0, 0, 0, 0],
            ],
            state=GameState.WIN,
            levels_completed=3,
            win_levels=3,
        )
        environment = SequencedOfflineEnvironment([complete], initial)
        agent = P10SampleAgent(
            card_id="local-card",
            game_id="external-report-identity",
            agent_name="p10sample",
            ROOT_URL="",
            record=False,
            arc_env=environment,
            operation_mode=OperationMode.OFFLINE,
            max_actions=2,
        )

        agent.main()
        report = agent.report()

        self.assertEqual(len(agent.frames), 1)
        self.assertEqual(len(agent.cycles), 1)
        self.assertIsInstance(agent.cycles[0], P10CycleAuditRecord)
        self.assertEqual(report.actions, 1)
        self.assertEqual(report.levels_completed, 3)
        self.assertEqual(report.terminal_state, "WIN")
        self.assertEqual(len(report.trace_events), 1)
        self.assertEqual(
            agent.runtime.components.hds.retained_compute_binding_count,
            0,
        )

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

    def test_level_checkpoint_survives_bounded_history_compaction(self) -> None:
        initial = frame([[0, 0], [0, 8]])
        progressed = frame(
            [[0, 0], [0, 9]],
            levels_completed=1,
        )
        safe = frame(
            [[0, 0], [0, 9]],
            levels_completed=1,
        )
        failed = frame(
            [[9, 9], [9, 9]],
            state=GameState.GAME_OVER,
            levels_completed=1,
        )
        reset = frame(
            [[0, 0], [0, 9]],
            levels_completed=1,
        )
        environment = SequencedOfflineEnvironment(
            [progressed, safe, failed],
            reset,
        )
        runtime = P10OfflineSampleRuntime(
            environment=environment,
            operation_mode=OperationMode.OFFLINE,
            max_actions=8,
        )

        runtime.run_cycle(initial, action_count=0)
        runtime.run_cycle(progressed, action_count=1)
        failed_cycle = runtime.run_cycle(safe, action_count=2)
        memory = runtime.components.memory
        assert memory is not None

        self.assertEqual(runtime.level_checkpoint_version, 1)
        self.assertIn(1, memory.retained_snapshot_versions)
        self.assertEqual(failed_cycle.after_frame, failed)

        recovered = runtime.recover(failed_cycle, failed)

        assert recovered.execution.rollback_result is not None
        self.assertEqual(
            recovered.execution.rollback_result.rollback_to_version,
            1,
        )
        self.assertIn(1, memory.retained_snapshot_versions)


if __name__ == "__main__":
    unittest.main()
