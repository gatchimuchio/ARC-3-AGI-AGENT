from 検証.ARC3NoopAction集合監査 import 集計する, 応答を分類する


def _response(**overrides):
    response = {
        "before_state": "NOT_FINISHED",
        "after_state": "NOT_FINISHED",
        "before_actions": (1, 2, 6),
        "after_actions": (1, 6),
        "before_full_reset": False,
        "after_full_reset": False,
        "before_frame_count": 1,
        "after_frame_count": 1,
        "changed_cells": 0,
        "level_delta": 0,
    }
    response.update(overrides)
    return response


def test_noop_with_available_action_change_is_distinguished_from_state_change():
    features = 応答を分類する(_response())

    assert features["no_op"] is True
    assert features["action_set_changed"] is True
    assert features["same_state_action_set_change"] is True
    assert 集計する([_response()]) == {
        "responses": 1,
        "no_op_actions": 1,
        "no_op_with_action_set_change": 1,
        "no_op_with_action_set_change_same_state": 1,
        "no_op_with_state_change": 0,
        "no_op_with_full_reset_change": 0,
        "no_op_with_frame_count_change": 0,
    }


def test_non_noop_and_terminal_transition_are_not_counted_as_same_state_action_change():
    progress = _response(level_delta=1)
    terminal = _response(after_state="GAME_OVER", after_actions=())

    assert 応答を分類する(progress)["no_op"] is False
    assert 応答を分類する(terminal)["no_op"] is True
    assert 応答を分類する(terminal)["state_changed"] is True
    assert 応答を分類する(terminal)["same_state_action_set_change"] is False
