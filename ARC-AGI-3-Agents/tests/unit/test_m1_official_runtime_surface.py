from __future__ import annotations

import os

import numpy as np
import pytest
from arc_agi.local_wrapper import LocalEnvironmentWrapper
from arcengine import FrameDataRaw, GameAction, GameState

from arc3_agi_agent.experience_ledger import EventSourcedExperienceLedger
from arc3_agi_agent.generic_compute import (
    HybridRelationalInstructionBody,
    action_descriptors,
    represent_observation,
)
from arc3_agi_agent.generic_env import OfflineGenericEnvironment
from arc3_agi_agent.generic_runtime import _action_effect_record
from arc3_agi_agent.generic_session import (
    ResourceContract,
    create_cognitive_session,
)
from arc3_agi_agent.generic_types import GenericObservation


def _frame(
    action_frames: list[list[list[int]]],
    *,
    available_actions: list[int],
    action: GameAction = GameAction.RESET,
    payload: dict[str, int] | None = None,
    levels_completed: int = 0,
    full_reset: bool = False,
) -> FrameDataRaw:
    result = FrameDataRaw(
        game_id="orchestration-only",
        state=GameState.NOT_FINISHED,
        levels_completed=levels_completed,
        win_levels=3,
        available_actions=available_actions,
        action_input={"id": action, "data": payload or {}},
        full_reset=full_reset,
    )
    result.frame = [np.asarray(item, dtype=np.int8) for item in action_frames]
    return result


class _TemporalLocalEnvironment(LocalEnvironmentWrapper):
    def __init__(self, before: FrameDataRaw, after: FrameDataRaw) -> None:
        self._last_response = before
        self.after = after

    def step(
        self,
        action: GameAction,
        *,
        data: dict[str, int],
        reasoning: dict[str, object],
    ) -> FrameDataRaw:
        assert action is GameAction.ACTION1
        assert data == {}
        assert reasoning["authority"] == "HDS"
        self._last_response = self.after
        return self.after


class _LevelResetLocalEnvironment(LocalEnvironmentWrapper):
    def __init__(self, before: FrameDataRaw, after: FrameDataRaw) -> None:
        self._last_response = before
        self.after = after
        self.observed_reset_scope: str | None = None

    def step(
        self,
        action: GameAction,
        *,
        data: dict[str, int],
        reasoning: dict[str, object],
    ) -> FrameDataRaw:
        assert action is GameAction.RESET
        assert data == {}
        assert reasoning["scope"] == "level"
        self.observed_reset_scope = os.environ.get("ONLY_RESET_LEVELS")
        self._last_response = self.after
        return self.after


def test_temporal_action_frames_and_cycle_history_are_preserved() -> None:
    stable = [[0, 0, 0], [0, 1, 0], [0, 0, 0]]
    transient = [[0, 0, 0], [0, 2, 0], [0, 0, 0]]
    before = _frame(
        [stable],
        available_actions=[1],
        full_reset=True,
    )
    after = _frame(
        [transient, stable],
        available_actions=[1],
        action=GameAction.ACTION1,
    )
    environment = OfflineGenericEnvironment(_TemporalLocalEnvironment(before, after))

    initial = environment.observe()
    repeated = environment.observe()
    result = environment.step(1, payload={}, request_id="m1-temporal")

    assert initial == repeated
    assert initial.observation_history == (initial.signature,)
    assert initial.control_actions == (0,)
    assert initial.legal_action_surface == (0, 1)
    assert initial.full_reset is True
    assert {"ACTION_COMPLETE", "FULL_RESET", "INITIAL_OBSERVATION"} <= set(
        initial.visible_effects
    )
    assert result.action_frame_count == 2
    assert result.composited_view == initial.composited_view
    assert result.observation_history == (initial.signature, result.signature)
    assert result.last_action_id == 1
    assert result.action_complete is True
    assert {
        "ACTION_COMPLETE",
        "ANIMATION_OBSERVED",
        "NO_VISIBLE_CHANGE",
        "TRANSIENT_ANIMATION_CHANGE",
    } <= set(result.visible_effects)
    representation = represent_observation(result, goal_tokens=("goal:progress",))
    assert "action-frame-count:2" in representation.topology_tokens
    assert "animation-observed:true" in representation.topology_tokens
    assert any(
        "action-frame:0:changed-cells:1" in item for item in representation.relations
    )
    assert (
        _action_effect_record(
            action_id=1,
            payload={},
            before=initial,
            after=result,
        ).visible_change
        is False
    )


def test_offline_reset_is_scoped_to_current_level(monkeypatch: pytest.MonkeyPatch) -> None:
    matrix = [[0, 0], [0, 1]]
    before = _frame(
        [matrix],
        available_actions=[1],
        levels_completed=2,
    )
    before.state = GameState.GAME_OVER
    after = _frame(
        [matrix],
        available_actions=[1],
        levels_completed=2,
    )
    local = _LevelResetLocalEnvironment(before, after)
    environment = OfflineGenericEnvironment(local)
    monkeypatch.setenv("ONLY_RESET_LEVELS", "prior-value")

    result = environment.reset_level(request_id="m1-level-only-reset")

    assert result.progress_count == 2
    assert local.observed_reset_scope == "true"
    assert os.environ["ONLY_RESET_LEVELS"] == "prior-value"


def test_action6_covers_general_spatial_affordance_surface() -> None:
    matrix = [[0 for _ in range(16)] for _ in range(16)]
    for y, x, value in ((3, 3, 2), (3, 4, 2), (11, 10, 3), (12, 10, 3)):
        matrix[y][x] = value
    rendered = tuple(tuple(row) for row in matrix)
    observation = GenericObservation(
        signature="m1-pointer-surface",
        available_actions=(6,),
        rendered_layers=(rendered,),
        terminal_state="NOT_FINISHED",
        action_payload_schema=((6, ("x", "y")),),
        control_actions=(0,),
        observation_history=("m1-pointer-surface",),
    )
    representation = represent_observation(
        observation,
        goal_tokens=("goal:progress",),
    )

    descriptors = action_descriptors(observation, representation)
    categories = {
        descriptor.semantic_key.split(":category:", 1)[1].split(":", 1)[0]
        for descriptor in descriptors
    }

    assert categories >= {
        "object",
        "cell",
        "region",
        "boundary",
        "path",
        "ui",
        "candidate-position",
    }
    assert len(descriptors) <= 112
    assert len({descriptor.payload_items for descriptor in descriptors}) == len(
        descriptors
    )
    assert all(descriptor.action_id == 6 for descriptor in descriptors)
    assert all(descriptor.validate(observation) == () for descriptor in descriptors)
    assert observation.legal_action_surface == (0, 6)


def test_level_success_and_reset_rotate_level_local_memory_scope() -> None:
    ledger = EventSourcedExperienceLedger()
    session = create_cognitive_session(
        p_bundle=HybridRelationalInstructionBody(),
        ledger=ledger,
        enable_cross_game_promotion=False,
        resource_contract=ResourceContract(action_budget_per_episode=4),
    )
    handle = session.begin_episode()
    transaction = session._active_transaction
    assert transaction is not None
    initial_level_handle = transaction.level_handle_digest

    session.bind_level_scope(
        handle,
        progress_count=0,
        observation_digest="observation:initial",
    )
    transition_event = session.record_level_transition(
        handle,
        before_progress=0,
        after_progress=1,
        observation_digest="observation:progress",
        cycle_index=0,
    )
    successful_level_handle = transaction.level_handle_digest
    reset_event = session.record_level_reset(
        handle,
        progress_count=1,
        observation_digest="observation:failure",
        cycle_index=1,
        reason="GAME_OVER",
    )

    assert initial_level_handle != successful_level_handle
    assert successful_level_handle != transaction.level_handle_digest
    assert transition_event != reset_event
    assert session.overlay.episode_active is True
    assert session.overlay.level_active is True
    assert [event.event_type for event in ledger.events()] == [
        "EPISODE_BEGIN",
        "LEVEL_SCOPE_BEGIN",
        "LEVEL_SCOPE_TRANSITION",
        "LEVEL_SCOPE_RESET",
    ]
    with pytest.raises(
        ValueError,
        match="COGNITIVE_SESSION_LEVEL_TRANSITION_INVALID",
    ):
        session.record_level_transition(
            handle,
            before_progress=0,
            after_progress=2,
            observation_digest="observation:stale",
            cycle_index=2,
        )
    session.end_episode(handle, succeeded=False, reason="bounded-test")
