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
        available_actions=[1, 2, 3, 4, 5, 6, 7] if state is GameState.NOT_FINISHED else [],
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
        available_actions=[1, 2, 3, 4, 5, 6, 7] if state is GameState.NOT_FINISHED else [],
    )


class ARC3SubmissionAgentTests(unittest.TestCase):
    def setUp(self):
        self.agent = _AGENT.MyAgent(
            card_id="card", game_id="game", agent_name="agent",
            ROOT_URL="http://offline", record=False, arc_env=None
        )

    def test_not_played_protocol_reset_is_the_only_returned_action(self):
        frame = _frame(GameState.NOT_PLAYED)
        self.assertFalse(self.agent.is_done([frame], frame))
        self.assertIs(self.agent.choose_action([frame], frame), GameAction.RESET)

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
            self.assertTrue(self.agent.is_done([placeholder], placeholder))
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
            self.assertTrue(self.agent.is_done([frame], frame))
        query.assert_called_once()
        self.assertTrue(self.agent.last_hold["候補側申告実行許可"])
        self.assertEqual(self.agent.last_hold["状態"], "HOLD")
        self.assertNotIn("盤面", self.agent.last_hold)
        with self.assertRaises(境界違反):
            self.agent.choose_action([frame], frame)

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


if __name__ == "__main__":
    unittest.main()
