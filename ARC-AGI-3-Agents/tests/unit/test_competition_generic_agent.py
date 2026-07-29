from __future__ import annotations

import numpy as np
import pytest
from arc_agi import EnvironmentWrapper
from arc_agi.local_wrapper import LocalEnvironmentWrapper
from arcengine import FrameDataRaw, GameAction, GameState

from agents.templates.generic_agi_agent import GenericAGIAgent
from arc3_agi_agent.generic_compute import HybridRelationalInstructionBody
from arc3_agi_agent.generic_env import CompetitionGenericEnvironment
from arc3_agi_agent.generic_session import (
    ResourceContract,
    create_cognitive_session,
)
from arc3_agi_agent.schema import forbidden_runtime_paths


def _frame(
    values: list[list[int]],
    *,
    state: GameState = GameState.NOT_FINISHED,
    levels_completed: int = 0,
    available_actions: list[int] | None = None,
) -> FrameDataRaw:
    result = FrameDataRaw(
        game_id="orchestration-only-identity",
        state=state,
        levels_completed=levels_completed,
        win_levels=1,
        available_actions=available_actions or [1, 2],
    )
    result.frame = [np.asarray(values, dtype=np.int8)]
    return result


class _FakeCompetitionEnvironment(EnvironmentWrapper):
    def __init__(
        self,
        before: FrameDataRaw,
        after: FrameDataRaw,
    ) -> None:
        self._last_response = before
        self.after = after
        self.calls: list[
            tuple[GameAction, dict[str, int], dict[str, object]]
        ] = []

    def step(
        self,
        action: GameAction,
        data: dict[str, int] | None = None,
        reasoning: dict[str, object] | None = None,
    ) -> FrameDataRaw:
        self.calls.append((action, data or {}, reasoning or {}))
        self._last_response = self.after
        return self.after


class _FakeLocalEnvironment(LocalEnvironmentWrapper):
    def __init__(self, frame: FrameDataRaw) -> None:
        self._last_response = frame


def test_competition_adapter_projects_identity_free_frame_and_emits_once() -> None:
    before = _frame([[0, 1], [1, 0]], available_actions=[6])
    after = _frame(
        [[0, 1], [0, 1]],
        state=GameState.WIN,
        levels_completed=1,
        available_actions=[6],
    )
    environment = _FakeCompetitionEnvironment(before, after)
    adapter = CompetitionGenericEnvironment(environment)

    observation = adapter.observe()
    result = adapter.step(
        6,
        payload={"x": 1, "y": 0},
        request_id="request:one",
    )

    assert forbidden_runtime_paths(observation) == ()
    assert observation.available_actions == (6,)
    assert result.terminal_state == "WIN"
    assert result.progress_count == 1
    assert environment.calls == [
        (
            GameAction.ACTION6,
            {"x": 1, "y": 0},
            {
                "authority": "HDS",
                "runtime": "GenericAGIRuntime",
                "request_id": "request:one",
            },
        )
    ]
    with pytest.raises(
        RuntimeError, match="GENERIC_COMPETITION_DUPLICATE_REQUEST"
    ):
        adapter.step(
            6,
            payload={"x": 1, "y": 0},
            request_id="request:one",
        )


def test_competition_adapter_rejects_local_wrapper() -> None:
    with pytest.raises(
        TypeError, match="GENERIC_COMPETITION_REMOTE_WRAPPER_REQUIRED"
    ):
        CompetitionGenericEnvironment(
            _FakeLocalEnvironment(_frame([[0]], available_actions=[1]))
        )


def test_generic_competition_agent_runs_only_generic_runtime() -> None:
    before = _frame([[0, 0], [0, 1]])
    after = _frame(
        [[0, 1], [0, 1]],
        state=GameState.WIN,
        levels_completed=1,
    )
    environment = _FakeCompetitionEnvironment(before, after)
    session = create_cognitive_session(
        p_bundle=HybridRelationalInstructionBody(),
        mode="COMPETITION",
        resource_contract=ResourceContract(action_budget_per_episode=8),
    )
    episode_handle = session.begin_episode()
    agent = GenericAGIAgent(
        card_id="card:test",
        game_id="orchestration-only-identity",
        agent_name="genericagi",
        ROOT_URL="http://gateway:8001",
        record=False,
        arc_env=environment,
        max_actions=8,
        cognitive_session=session,
        episode_handle=episode_handle,
    )

    agent.main()

    assert agent.runtime_report is not None
    assert agent.runtime_report.actions_executed == 1
    assert agent.runtime_report.progress_count == 1
    assert agent.runtime_report.final_state == "WIN"
    assert agent.runtime_report.no_fallback_used is True
    assert agent.runtime_report.runtime_identity_received is True
    assert agent.runtime_report.identity_boundary_passed is True
    assert len(environment.calls) == 1
    assert environment.calls[0][2]["authority"] == "HDS"
