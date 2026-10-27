from __future__ import annotations

import importlib.util
from pathlib import Path
import sys
import types
import unittest
from unittest.mock import patch

import numpy as np
from arcengine import FrameData, GameAction, GameState

from 接続.ARC3境界 import 境界違反


class _FrameworkAgent:
    def __init__(self, *args, **kwargs):
        self.action_counter = 0
        self.arc_env = kwargs.get("arc_env")

    def _convert_raw_frame_data(self, raw):
        if isinstance(raw, FrameData):
            return raw
        return FrameData(
            game_id=raw.game_id,
            state=raw.state,
            frame=[arr.tolist() for arr in raw.frame],
            levels_completed=raw.levels_completed,
            win_levels=raw.win_levels,
            guid=raw.guid,
            full_reset=raw.full_reset,
            available_actions=raw.available_actions,
        )


def _load_agent_module():
    package = types.ModuleType("agents")
    package.__path__ = []
    base = types.ModuleType("agents.agent")
    base.Agent = _FrameworkAgent
    with patch.dict(sys.modules, {"agents": package, "agents.agent": base}):
        path = Path(__file__).resolve().parents[1] / "接続" / "ARC3提出agent.py"
        spec = importlib.util.spec_from_file_location("_arc3_submission_agent_test", path)
        assert spec and spec.loader
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
    return module


_AGENT = _load_agent_module()


def _frame(state: GameState) -> FrameData:
    return FrameData(
        game_id="public-fixture",
        state=state,
        frame=[[[0] * 8 for _ in range(8)]] if state is GameState.NOT_FINISHED else [],
        available_actions=(
            [1, 2, 3, 4, 5, 6, 7]
            if state is GameState.NOT_FINISHED
            else [6]
            if state is GameState.GAME_OVER
            else []
        ),
        win_levels=1,
        guid="fixture-guid",
    )


def _raw_frame(state: GameState):
    return types.SimpleNamespace(
        game_id="public-fixture",
        state=state,
        frame=[np.zeros((8, 8), dtype=np.int64)] if state is GameState.NOT_FINISHED else [],
        levels_completed=0,
        win_levels=1,
        guid="fixture-guid",
        full_reset=False,
        available_actions=(
            [1, 2, 3, 4, 5, 6, 7]
            if state is GameState.NOT_FINISHED
            else [6]
            if state is GameState.GAME_OVER
            else []
        ),
    )


class ARC3SubmissionAgentTests(unittest.TestCase):
    def test_prior_memory_is_loaded_in_isolated_hds_context_without_action_authority(self):
        stats = self.agent.hds_runtime_stats
        self.assertEqual(stats["事前記憶版"], "arc3-prior-context-v0.1")
        self.assertEqual(stats["事前記憶読込件数"], 5)
        self.assertEqual(stats["事前記憶HDS境界"], "ARC3事前記憶")
        self.assertFalse(stats["事前記憶Action認可"])
        self.assertEqual(stats["事前記憶反映可視変化係数"], 0.0)
        self.assertEqual(self.agent._policy._可視変化係数, 0.0)
        prior = self.agent._hds.エンジン._経験群("ARC3事前記憶")
        self.assertEqual(len(prior), 5)
        self.assertEqual(self.agent._hds.エンジン._経験群("ARC3公開作用応答"), ())
        self.assertTrue(all(record.原入力.get("因果確認済") is False and bool(record.原入力.get("原則")) for record in prior))
        initial_hds = self.agent._hds
        self.agent._HDS適用範囲を保つ(types.SimpleNamespace(ゲーム識別子="public-fixture"))
        self.agent._HDS適用範囲を保つ(types.SimpleNamespace(ゲーム識別子="second-public-fixture"))
        self.assertIsNot(self.agent._hds, initial_hds)
        self.assertEqual(len(self.agent._hds.エンジン._経験群("ARC3事前記憶")), 5)

    def setUp(self):
        self.agent = _AGENT.MyAgent(
            card_id="card", game_id="game", agent_name="agent",
            ROOT_URL="http://offline", record=False, arc_env=None
        )

    def test_not_played_protocol_reset_is_the_only_returned_action(self):
        frame = _frame(GameState.NOT_PLAYED)
        self.assertFalse(self.agent.is_done([frame], frame))
        action = self.agent.choose_action([frame], frame)
        self.assertEqual(action.作用番号, GameAction.RESET.value)
        self.assertEqual(action.出所, "SDKリセット")

    def test_initial_live_sdk_observation_is_held_before_choose_action(self):
        placeholder = _frame(GameState.NOT_PLAYED)
        current = _raw_frame(GameState.NOT_FINISHED)
        self.agent.arc_env = types.SimpleNamespace(observation_space=current)
        candidate = {
            "状態": "条件付き候補",
            "次作用候補群": [{"実行許可": False}],
            "実行許可": False,
        }
        with patch.object(_AGENT, "公開観測から候補を照会する", return_value=candidate) as query:
            self.assertFalse(self.agent.is_done([placeholder], placeholder))
        query.assert_called_once()
        self.assertEqual(self.agent.action_counter, 0)
        self.assertEqual(self.agent.last_hold["状態"], "HOLD")

    def test_candidate_claim_never_becomes_permission_or_action(self):
        frame = _frame(GameState.NOT_FINISHED)
        candidate = {
            "状態": "条件付き候補",
            "次作用候補群": [{"実行許可": False}],
            "実行許可": True,
        }
        with patch.object(_AGENT, "公開観測から候補を照会する", return_value=candidate) as query:
            self.assertFalse(self.agent.is_done([frame], frame))
        query.assert_called_once()
        self.assertTrue(self.agent.last_hold["候補側申告実行許可"])
        self.assertEqual(self.agent.last_hold["状態"], "HOLD")
        self.assertNotIn("盤面", self.agent.last_hold)
        action = self.agent.choose_action([frame], frame)
        self.assertEqual(action.出所, "観測駆動探索")
        self.assertIn(action.作用番号, frame.available_actions)

    def test_observation_or_hds_error_stops_without_fallback_action(self):
        malformed = FrameData(game_id="public-fixture", state=GameState.NOT_FINISHED, frame=[])
        with patch.object(_AGENT, "公開観測から候補を照会する") as query:
            self.assertTrue(self.agent.is_done([malformed], malformed))
        query.assert_not_called()
        self.assertEqual(self.agent.last_hold["状態"], "HOLD")
        self.assertEqual(self.agent.last_hold["理由"], "境界違反")

    def test_win_stops_without_query(self):
        frame = _frame(GameState.WIN)
        with patch.object(_AGENT, "公開観測から候補を照会する") as query:
            self.assertTrue(self.agent.is_done([frame], frame))
        query.assert_not_called()

    def test_not_played_after_first_action_does_not_reset_again(self):
        self.agent.action_counter = 1
        frame = _frame(GameState.NOT_PLAYED)
        self.assertTrue(self.agent.is_done([frame], frame))
        with self.assertRaises(境界違反):
            self.agent.choose_action([frame], frame)

    def test_game_over_allows_only_sdk_reset_even_outside_available_actions(self):
        frame = _frame(GameState.GAME_OVER)
        self.agent.action_counter = 4
        self.assertFalse(self.agent.is_done([frame], frame))
        action = self.agent.choose_action([frame], frame)
        self.assertEqual(action.作用番号, GameAction.RESET.value)
        self.assertEqual(action.出所, "SDKリセット")

        game_over = _raw_frame(GameState.GAME_OVER)
        restarted = _raw_frame(GameState.NOT_FINISHED)

        class Environment:
            observation_space = game_over

            def __init__(self):
                self.calls = []

            def step(self, sent_action, *, data, reasoning):
                self.calls.append((sent_action, data, reasoning))
                self.observation_space = restarted
                return restarted

        environment = Environment()
        self.agent.arc_env = environment
        response = self.agent.do_action_request(action)
        self.assertEqual(response.state, GameState.NOT_FINISHED)
        self.assertEqual(len(environment.calls), 1)
        sent_action, sent_data, reasoning = environment.calls[0]
        self.assertIs(sent_action, GameAction.RESET)
        self.assertEqual(sent_data, {})
        self.assertEqual(reasoning["Action出所"], "SDKリセット")

    def test_win_remains_terminal_and_does_not_reset(self):
        frame = _frame(GameState.WIN)
        self.assertTrue(self.agent.is_done([frame], frame))
        with self.assertRaises(境界違反):
            self.agent.choose_action([frame], frame)

    def test_sdk_step_rechecks_observation_and_keeps_action_provenance_separate(self):
        placeholder = _frame(GameState.NOT_PLAYED)
        board = np.zeros((8, 8), dtype=np.int64)
        board[2, 2:4] = 5
        current = _raw_frame(GameState.NOT_FINISHED)
        current.frame = [board]
        current.available_actions = [6]

        class Environment:
            observation_space = current

            def __init__(self):
                self.calls = []

            def step(self, action, *, data, reasoning):
                self.calls.append((action, data, reasoning))
                self.observation_space = _raw_frame(GameState.NOT_FINISHED)
                self.observation_space.frame = [board]
                self.observation_space.available_actions = [6]
                return self.observation_space

        env = Environment()
        self.agent.arc_env = env
        candidate = {"状態": "条件付き候補", "次作用候補群": [], "実行許可": True}
        with patch.object(_AGENT, "公開観測から候補を照会する", return_value=candidate):
            self.assertFalse(self.agent.is_done([placeholder], placeholder))
        frame = self.agent._convert_raw_frame_data(env.observation_space)
        action = self.agent.choose_action([placeholder], frame)
        old_action_data = _AGENT.GameAction.ACTION6.action_data.model_dump()
        with patch.object(self.agent._hds, "処理する", wraps=self.agent._hds.処理する) as hds_update:
            response = self.agent.do_action_request(action)
        self.assertEqual(len(env.calls), 1)
        sent_action, sent_data, reasoning = env.calls[0]
        self.assertIs(sent_action, _AGENT.GameAction.ACTION6)
        self.assertTrue(0 <= sent_data["x"] < 8 and 0 <= sent_data["y"] < 8)
        self.assertEqual(reasoning["Action出所"], "観測駆動探索")
        self.assertEqual(response.state, GameState.NOT_FINISHED)
        self.assertEqual(_AGENT.GameAction.ACTION6.action_data.model_dump(), old_action_data)
        self.assertEqual(self.agent.hds_runtime_stats["状態照会数"], 1)
        self.assertEqual(self.agent.hds_runtime_stats["観測更新数"], 1)
        self.assertIsNotNone(self.agent.hds_runtime_stats["最終学習状態"])
        hds_update.assert_called_once()
        transition = hds_update.call_args.args[0]
        self.assertEqual(transition.対象系境界, "ARC3公開作用応答")
        self.assertEqual(
            set(transition.内容),
            {"作用前公開状態", "作用", "公開応答区分"},
        )
        before_summary = transition.内容["作用前公開状態"]
        self.assertEqual(before_summary["作用可能数"], 1)
        self.assertEqual(
            set(before_summary), {"作用可能数", "色種類数", "最多色占有帯"}
        )
        self.assertEqual(transition.内容["作用"]["番号"], 6)
        self.assertIn(transition.内容["公開応答区分"], ("可視変化なし", "盤面変化", "レベル進行", "勝利"))
        self.assertNotIn("game_id", before_summary)
        self.assertNotIn("盤面", before_summary)
        with self.assertRaises(境界違反):
            self.agent.do_action_request(action)


if __name__ == "__main__":
    unittest.main()
