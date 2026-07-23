from __future__ import annotations

import os
import unittest
from pathlib import Path
from unittest.mock import patch

import numpy as np
from arc_agi import OperationMode
from arc_agi.local_wrapper import LocalEnvironmentWrapper
from arcengine import FrameDataRaw, GameAction, GameState

import agents
from agents.templates.layer0_sample_agent import Layer0SampleAgent
from arc3_agi_agent.adapters.offline_arcade import (
    OfflineArcadeEmissionInterface,
)
from arc3_agi_agent.ir import CandidateIR
from arc3_agi_agent.protocol import (
    AuthorityViolation,
    EmissionDirective,
    HDSDecision,
)
from arc3_agi_agent.roles import DeterministicSymbolSpace
from arc3_agi_agent.sample_observation import SampleFrameAdapter
from arc3_agi_agent.sample_runtime import OfflineSampleRuntime
from arc3_agi_agent.schema import forbidden_runtime_paths
from sample_main import _default_environments_dir, run_offline_samples


def frame(
    values: list[list[int]],
    *,
    available_actions: list[int],
    levels_completed: int = 0,
    state: GameState = GameState.NOT_FINISHED,
) -> FrameDataRaw:
    result = FrameDataRaw(
        game_id="identity-must-not-enter-kernel",
        state=state,
        levels_completed=levels_completed,
        win_levels=3,
        available_actions=available_actions,
    )
    result.frame = [np.asarray(values, dtype=np.int8)]
    return result


class FakeOfflineEnvironment(LocalEnvironmentWrapper):
    def __init__(self, before: FrameDataRaw, after: FrameDataRaw) -> None:
        self._last_response = before
        self.after = after
        self.calls: list[
            tuple[GameAction, dict[str, int], dict[str, str]]
        ] = []

    def step(
        self,
        action: GameAction,
        *,
        data: dict[str, int],
        reasoning: dict[str, str],
    ) -> FrameDataRaw:
        self.calls.append((action, data, reasoning))
        self._last_response = self.after
        return self.after


class OfflineSampleRuntimeTests(unittest.TestCase):
    def test_default_sample_directory_resolves_repository_assets(self) -> None:
        self.assertTrue(_default_environments_dir().is_dir())
        self.assertEqual(_default_environments_dir().name, "environment_files")

    def test_sample_agent_is_exported_but_not_online_registry_selectable(
        self,
    ) -> None:
        self.assertIs(agents.Layer0SampleAgent, Layer0SampleAgent)
        self.assertNotIn("layer0sample", agents.AVAILABLE_AGENTS)

    def test_adapter_excludes_runtime_identity(self) -> None:
        current = frame([[0, 1], [1, 0]], available_actions=[1, 2])
        raw = SampleFrameAdapter().runtime_observation(current)

        self.assertEqual(forbidden_runtime_paths(raw), ())
        self.assertNotIn("game_id", raw)
        self.assertEqual(raw["available_actions"], (1, 2))

    def test_hds_emits_then_reobserves_into_persistent_state(self) -> None:
        before = frame([[0, 0], [0, 1]], available_actions=[1, 2])
        after = frame(
            [[0, 1], [0, 1]],
            available_actions=[1, 2],
            levels_completed=1,
        )
        environment = FakeOfflineEnvironment(before, after)
        runtime = OfflineSampleRuntime(
            environment=environment,
            operation_mode=OperationMode.OFFLINE,
            max_actions=1,
        )

        emitted = runtime.run_cycle(before, action_count=0)
        stopped = runtime.run_cycle(after, action_count=1)

        self.assertEqual(emitted.kernel_result.status, "PASS")
        self.assertIs(emitted.after_frame, after)
        self.assertIsNotNone(emitted.verification)
        self.assertEqual(emitted.verification.status, "PASS")
        self.assertEqual(stopped.kernel_result.decision.status, "STOP")
        self.assertIsNone(stopped.after_frame)
        self.assertEqual(len(environment.calls), 1)
        action, data, reasoning = environment.calls[0]
        self.assertIs(action, GameAction.ACTION2)
        self.assertEqual(data, {})
        self.assertEqual(reasoning["authority"], "HDS")
        self.assertNotIn("game_id", reasoning)

        context = runtime.context_state.snapshot()
        self.assertEqual(context.actions_used, 1)
        self.assertIsNotNone(context.previous_observation)
        self.assertEqual(
            context.current_observation.frame_signature,
            runtime.frame_adapter.signature(after),
        )
        self.assertEqual(runtime.components.memory.view().version, 1)
        for entry in runtime.components.memory.view().entries:
            self.assertEqual(forbidden_runtime_paths(entry.payload), ())

    def test_reobserved_state_changes_the_next_hds_candidate_identity(
        self,
    ) -> None:
        before = frame([[0, 0], [0, 1]], available_actions=[1, 2])
        after = frame(
            [[0, 1], [0, 1]],
            available_actions=[1, 2],
            levels_completed=1,
        )
        environment = FakeOfflineEnvironment(before, after)
        runtime = OfflineSampleRuntime(
            environment=environment,
            operation_mode=OperationMode.OFFLINE,
            max_actions=2,
        )

        first = runtime.run_cycle(before, action_count=0)
        second = runtime.run_cycle(after, action_count=1)
        stopped = runtime.run_cycle(after, action_count=2)

        self.assertEqual(len(environment.calls), 2)
        self.assertEqual(
            second.kernel_result.observation.frame_signature,
            runtime.frame_adapter.signature(after),
        )
        self.assertNotEqual(
            first.kernel_result.emission_result.candidate_id,
            second.kernel_result.emission_result.candidate_id,
        )
        self.assertEqual(runtime.context_state.snapshot().actions_used, 2)
        self.assertEqual(stopped.kernel_result.decision.status, "STOP")

    def test_sample_agent_stops_after_a_post_emission_win(self) -> None:
        before = frame([[0, 0], [0, 1]], available_actions=[1, 2])
        after = frame(
            [[0, 1], [0, 1]],
            available_actions=[1, 2],
            levels_completed=3,
            state=GameState.WIN,
        )
        environment = FakeOfflineEnvironment(before, after)
        agent = Layer0SampleAgent(
            card_id="local-card",
            game_id="external-report-identity",
            agent_name="layer0sample",
            ROOT_URL="",
            record=False,
            arc_env=environment,
            operation_mode=OperationMode.OFFLINE,
            max_actions=2,
        )

        agent.main()
        report = agent.report()

        self.assertEqual(len(environment.calls), 1)
        self.assertEqual(report.actions, 1)
        self.assertEqual(report.final_status, "STOP")
        self.assertEqual(report.decision_statuses, ("EMIT",))
        self.assertEqual(report.memory_version, 0)

    def test_action6_coordinates_come_from_current_dimensions(self) -> None:
        before = frame(
            [[0, 0, 0, 0, 0, 0] for _ in range(4)],
            available_actions=[6],
        )
        after = frame(
            [[0, 0, 1, 0, 0, 0] for _ in range(4)],
            available_actions=[6],
            levels_completed=1,
        )
        environment = FakeOfflineEnvironment(before, after)
        runtime = OfflineSampleRuntime(
            environment=environment,
            operation_mode=OperationMode.OFFLINE,
            max_actions=1,
        )

        runtime.run_cycle(before, action_count=0)

        action, data, _ = environment.calls[0]
        self.assertIs(action, GameAction.ACTION6)
        self.assertEqual(data, {"x": 3, "y": 2})

    def test_offline_adapter_rejects_forged_hds_labels_before_step(
        self,
    ) -> None:
        before = frame([[0, 1], [1, 0]], available_actions=[1])
        environment = FakeOfflineEnvironment(before, before)
        adapter = OfflineArcadeEmissionInterface(
            environment=environment,
            operation_mode=OperationMode.OFFLINE,
        )
        adapter.bind(before)
        observation = DeterministicSymbolSpace().encode(
            SampleFrameAdapter().runtime_observation(before)
        )
        candidate = CandidateIR(
            candidate_id="candidate:forged",
            mode="ACTION",
            steps=({"action_id": 1},),
            preconditions=("ACTION1_AVAILABLE",),
            expected_effects_by_hypothesis={
                "hypothesis:1": ("VISIBLE_STATE_CHANGE",)
            },
            provenance=("current-observation",),
            falsification_conditions=("unexpected rendered effect",),
        )
        decision = HDSDecision(
            command_id="command:forged",
            decision_id="decision:forged",
            status="EMIT",
            candidate_id=candidate.candidate_id,
            closure_signature="closure:forged",
            allow_external_emit=True,
        )
        directive = EmissionDirective(
            command_id=decision.command_id,
            decision_id=decision.decision_id,
            action_id=1,
            reasoning_digest="reason:forged",
            candidate_id=candidate.candidate_id,
            closure_signature=decision.closure_signature,
        )

        with self.assertRaisesRegex(
            AuthorityViolation,
            "HDS_DECISION_INVALID",
        ):
            adapter.emit(
                directive,
                decision,
                candidate,
                observation,
                executor="pure-llm",
            )
        self.assertEqual(environment.calls, [])

    def test_direct_agent_action_paths_are_forbidden(self) -> None:
        before = frame([[0, 1], [1, 0]], available_actions=[1])
        environment = FakeOfflineEnvironment(before, before)
        agent = Layer0SampleAgent(
            card_id="local-card",
            game_id="external-report-identity",
            agent_name="layer0sample",
            ROOT_URL="",
            record=False,
            arc_env=environment,
            operation_mode=OperationMode.OFFLINE,
            max_actions=1,
        )
        self.assertEqual(agent.headers, {})

        with self.assertRaisesRegex(
            AuthorityViolation,
            "DIRECT_ACTION_SELECTION_FORBIDDEN",
        ):
            agent.choose_action([], agent._convert_raw_frame_data(before))
        with self.assertRaisesRegex(
            AuthorityViolation,
            "DIRECT_ACTION_EMISSION_FORBIDDEN",
        ):
            agent.take_action(GameAction.ACTION1)
        with self.assertRaisesRegex(
            AuthorityViolation,
            "DIRECT_ENVIRONMENT_STEP_FORBIDDEN",
        ):
            agent.do_action_request(GameAction.ACTION1)

    def test_nonlocal_wrapper_is_rejected_even_when_mode_label_is_offline(
        self,
    ) -> None:
        class LabelOnlyEnvironment:
            def step(self, *_: object, **__: object) -> FrameDataRaw:
                raise AssertionError("must not execute")

        with self.assertRaisesRegex(
            AuthorityViolation,
            "OFFLINE_LOCAL_WRAPPER_REQUIRED",
        ):
            OfflineSampleRuntime(
                environment=LabelOnlyEnvironment(),
                operation_mode=OperationMode.OFFLINE,
                max_actions=1,
            )

    def test_competition_environment_is_rejected_before_arcade_construction(
        self,
    ) -> None:
        environments = Path(__file__).resolve().parents[3] / "environment_files"
        with patch.dict(
            os.environ,
            {"OPERATION_MODE": " competition "},
            clear=False,
        ):
            with self.assertRaisesRegex(
                AuthorityViolation,
                "COMPETITION_MODE_ENV_FORBIDDEN_DURING_P1",
            ):
                run_offline_samples(
                    environments_dir=environments,
                    all_samples=True,
                    max_actions=1,
                )


if __name__ == "__main__":
    unittest.main()
