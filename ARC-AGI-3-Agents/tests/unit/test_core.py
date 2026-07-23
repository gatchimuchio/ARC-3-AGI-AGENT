import subprocess
import sys
import textwrap
from pathlib import Path
from unittest.mock import Mock, patch

import numpy as np
import pytest
from arcengine import (
    ActionInput,
    FrameData,
    FrameDataRaw,
    GameAction,
    GameState,
)

from agents import AVAILABLE_AGENTS
from agents.templates.langgraph_random_agent import LangGraphRandom
from agents.templates.random_agent import Random


def make_random_agent(arc_env: Mock | None = None) -> Random:
    return Random(
        card_id="test-card",
        game_id="test-game",
        agent_name="test-agent",
        ROOT_URL="https://example.com",
        record=False,
        arc_env=arc_env or Mock(),
    )


def make_langgraph_random_agent(arc_env: Mock | None = None) -> LangGraphRandom:
    return LangGraphRandom(
        card_id="test-card",
        game_id="test-game",
        agent_name="test-agent",
        ROOT_URL="https://example.com",
        record=False,
        arc_env=arc_env or Mock(),
    )


@pytest.mark.unit
class TestGameActionCore:
    @pytest.mark.parametrize(
        "action,data,expected",
        [
            (GameAction.ACTION1, {"game_id": "test"}, {"game_id": "test"}),
            (
                GameAction.ACTION6,
                {"game_id": "test", "x": 32, "y": 45},
                {"x": 32, "y": 45, "game_id": "test"},
            ),
        ],
    )
    def test_action_data_validation(self, action, data, expected):
        action.set_data(data)

        assert action.action_data.game_id == expected["game_id"]
        if "x" in expected:
            assert action.action_data.x == expected["x"]
            assert action.action_data.y == expected["y"]

    @pytest.mark.parametrize(
        "invalid_data",
        [
            {"game_id": "test", "x": -1, "y": 0},
            {"game_id": "test", "x": 0, "y": 64},
            {"x": "not_a_number", "y": 10},
        ],
    )
    def test_coordinate_validation(self, invalid_data):
        with pytest.raises(Exception):
            GameAction.ACTION6.set_data(invalid_data)

    @pytest.mark.parametrize(
        "action_id,expected",
        [
            (0, GameAction.RESET),
            (6, GameAction.ACTION6),
            (7, GameAction.ACTION7),
        ],
    )
    def test_action_from_id(self, action_id, expected):
        assert GameAction.from_id(action_id) == expected

        with pytest.raises(ValueError):
            GameAction.from_id(999)

    @pytest.mark.parametrize(
        "action_name,expected",
        [
            ("RESET", GameAction.RESET),
            ("action6", GameAction.ACTION6),
            ("Action7", GameAction.ACTION7),
        ],
    )
    def test_action_from_name(self, action_name, expected):
        assert GameAction.from_name(action_name) == expected

        with pytest.raises(ValueError):
            GameAction.from_name("INVALID_ACTION")

    def test_action_classification(self):
        simple_actions = GameAction.all_simple()
        complex_actions = GameAction.all_complex()

        assert GameAction.RESET in simple_actions
        assert GameAction.ACTION1 in simple_actions
        assert GameAction.ACTION7 in simple_actions
        assert GameAction.ACTION6 in complex_actions
        assert GameAction.RESET.is_simple()
        assert not GameAction.RESET.is_complex()
        assert GameAction.ACTION6.is_complex()
        assert not GameAction.ACTION6.is_simple()


@pytest.mark.unit
class TestActionInput:
    def test_action_input_init(self):
        action_input = ActionInput()
        assert action_input.id == GameAction.RESET
        assert action_input.data == {}
        assert action_input.reasoning is None

        action_input = ActionInput(
            id=GameAction.ACTION6,
            data={"game_id": "test", "x": 10, "y": 20},
            reasoning={"model": "test", "tokens": 50},
        )

        assert action_input.id == GameAction.ACTION6
        assert action_input.data["x"] == 10
        assert action_input.reasoning["tokens"] == 50

    def test_reasoning_must_be_json_serializable(self):
        action_input = ActionInput(reasoning={"key": "value", "number": 42})
        assert action_input.reasoning["key"] == "value"

        with pytest.raises(Exception):
            ActionInput(reasoning=lambda value: value)


@pytest.mark.unit
class TestLazyAgentRegistry:
    def test_package_import_does_not_require_optional_agent_stacks(self):
        script = textwrap.dedent(
            """
            import builtins
            import sys

            blocked = {"langchain", "langgraph", "langsmith", "openai", "smolagents"}
            real_import = builtins.__import__

            def guarded_import(name, *args, **kwargs):
                if name.partition(".")[0] in blocked:
                    raise AssertionError(f"optional dependency imported: {name}")
                return real_import(name, *args, **kwargs)

            builtins.__import__ = guarded_import
            import agents
            from agents.recorder import Recorder

            assert Recorder is agents.Recorder
            assert not blocked.intersection(
                name.partition(".")[0] for name in sys.modules
            )
            """
        )

        result = subprocess.run(
            [sys.executable, "-c", script],
            cwd=Path(__file__).resolve().parents[2],
            capture_output=True,
            text=True,
            check=False,
        )

        assert result.returncode == 0, result.stderr

    def test_random_agent_is_loaded_without_optional_agent_imports(self):
        assert "random" in AVAILABLE_AGENTS
        assert AVAILABLE_AGENTS["random"] is Random

        with pytest.raises(KeyError):
            AVAILABLE_AGENTS["missing-agent"]


@pytest.mark.unit
class TestRandomAgent:
    def test_agent_init(self):
        agent = make_random_agent()

        assert agent.game_id == "test-game"
        assert agent.card_id == "test-card"
        assert agent.MAX_ACTIONS == 80
        assert agent.action_counter == 0
        assert agent.arc_env is not None
        assert agent.name == "test-game.random.80"

    def test_agent_action_and_stop_logic(self, sample_frame):
        agent = make_random_agent()

        sample_frame.state = GameState.NOT_PLAYED
        assert agent.choose_action([sample_frame], sample_frame) == GameAction.RESET

        sample_frame.state = GameState.GAME_OVER
        assert agent.choose_action([sample_frame], sample_frame) == GameAction.RESET

        sample_frame.state = GameState.NOT_FINISHED
        with patch(
            "agents.templates.random_agent.random.choice",
            return_value=GameAction.ACTION1,
        ):
            action = agent.choose_action([sample_frame], sample_frame)
        assert action == GameAction.ACTION1
        assert isinstance(action, GameAction)

        sample_frame.state = GameState.WIN
        assert agent.is_done([sample_frame], sample_frame) is True

        sample_frame.state = GameState.NOT_FINISHED
        assert agent.is_done([sample_frame], sample_frame) is False

    def test_environment_frame_conversion_and_action_request(self):
        arc_env = Mock()
        raw = FrameDataRaw(
            game_id="test-game",
            state=GameState.NOT_FINISHED,
            levels_completed=2,
            win_levels=5,
            available_actions=[1, 6],
        )
        raw.frame = [np.array([[1, 2], [3, 4]], dtype=np.uint8)]
        arc_env.step.return_value = raw
        agent = make_random_agent(arc_env)
        GameAction.ACTION1.set_data({"game_id": "test-game"})

        frame = agent.do_action_request(GameAction.ACTION1)

        assert frame.game_id == "test-game"
        assert frame.frame == [[[1, 2], [3, 4]]]
        assert frame.levels_completed == 2
        assert frame.win_levels == 5
        assert frame.available_actions == [1, 6]
        arc_env.step.assert_called_once_with(
            GameAction.ACTION1,
            data={"game_id": "test-game"},
            reasoning={},
        )


@pytest.mark.unit
class TestLangGraphRandomAgent:
    def test_agent_init(self):
        agent = make_langgraph_random_agent()

        assert agent.game_id == "test-game"
        assert agent.card_id == "test-card"
        assert agent.MAX_ACTIONS == 80
        assert agent.action_counter == 0
        assert agent.workflow is not None
        assert agent.name == "test-game.langgraphrandom.80"

    def test_agent_action_logic(self, sample_frame):
        agent = make_langgraph_random_agent()

        sample_frame.state = GameState.NOT_PLAYED
        assert agent.choose_action([sample_frame], sample_frame) == GameAction.RESET

        sample_frame.state = GameState.GAME_OVER
        assert agent.choose_action([sample_frame], sample_frame) == GameAction.RESET

        sample_frame.state = GameState.NOT_FINISHED
        with patch(
            "agents.templates.langgraph_random_agent.random.choice",
            return_value=GameAction.ACTION1,
        ):
            action = agent.choose_action([sample_frame], sample_frame)
        assert action == GameAction.ACTION1

        sample_frame.state = GameState.WIN
        assert agent.is_done([sample_frame], sample_frame) is True


@pytest.mark.unit
class TestFrameData:
    def test_frame_init(self):
        frame = FrameData(
            game_id="test",
            frame=[[[1, 2], [3, 4]]],
            state=GameState.NOT_FINISHED,
            levels_completed=10,
            win_levels=20,
            available_actions=[1, 6, 7],
        )

        assert frame.game_id == "test"
        assert frame.levels_completed == 10
        assert frame.win_levels == 20
        assert frame.available_actions == [1, 6, 7]
        assert frame.state == GameState.NOT_FINISHED
        assert not frame.is_empty()

        empty = FrameData()
        assert empty.game_id == ""
        assert empty.frame == []
        assert empty.state == GameState.NOT_PLAYED
        assert empty.levels_completed == 0
        assert empty.win_levels == 0
        assert empty.is_empty()
        assert empty.guid is None
        assert empty.full_reset is False

    @pytest.mark.parametrize(
        "levels_completed,should_pass",
        [
            (0, True),
            (254, True),
            (-1, False),
            (255, False),
        ],
    )
    def test_level_count_validation(self, levels_completed, should_pass):
        if should_pass:
            frame = FrameData(levels_completed=levels_completed)
            assert frame.levels_completed == levels_completed
        else:
            with pytest.raises(Exception):
                FrameData(levels_completed=levels_completed)

    def test_action_input_and_serialization(self):
        action_input = ActionInput(
            id=GameAction.ACTION1,
            data={"game_id": "test"},
            reasoning={"model": "test"},
        )
        frame = FrameData(
            game_id="test",
            action_input=action_input,
            guid="test-guid-123",
            full_reset=True,
        )

        assert frame.action_input.id == GameAction.ACTION1
        assert frame.action_input.data["game_id"] == "test"
        assert frame.guid == "test-guid-123"
        assert frame.full_reset is True

        json_data = frame.model_dump()
        assert json_data["game_id"] == "test"
        assert json_data["guid"] == "test-guid-123"
        assert json_data["full_reset"] is True

    def test_complex_frame_shape_is_preserved(self):
        complex_frame = [
            [[1, 2, 3], [4, 5, 6], [7, 8, 9]],
            [[9, 8, 7], [6, 5, 4], [3, 2, 1]],
        ]

        frame = FrameData(
            game_id="complex-test",
            frame=complex_frame,
            levels_completed=50,
        )

        assert frame.frame == complex_frame
        assert not frame.is_empty()
        assert len(frame.frame) == 2
        assert len(frame.frame[0]) == 3
        assert len(frame.frame[0][0]) == 3
