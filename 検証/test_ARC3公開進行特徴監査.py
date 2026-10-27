from __future__ import annotations

import numpy as np

from 検証.ARC3公開進行特徴監査 import (
    action_features,
    average_precision,
    board_features,
    grouped_folds,
    rows_from_events,
)


def test_visual_features_ignore_color_label_permutation() -> None:
    board = [[0, 0, 1, 1], [0, 2, 2, 1], [3, 3, 2, 1]]
    renamed = [
        [17 if value == 0 else 5 if value == 1 else 29 if value == 2 else 11 for value in row]
        for row in board
    ]
    assert np.allclose(board_features(board), board_features(renamed))


def test_training_observation_is_pre_action_board_and_public_level_transition_label() -> None:
    initial_board = [[0, 0], [0, 1]]
    after_board = [[1, 1], [1, 0]]
    after_second_action = [[1, 0], [0, 0]]
    events = [
        {"type": "initial", "board": initial_board, "level": 1},
        {"type": "analysis", "board": [[9, 9], [9, 9]], "level": 99},
        {"type": "action", "board": after_board, "level": 2, "action_name": "ACTION3"},
        {"type": "action", "board": after_second_action, "level": 2, "action_name": "ACTION6"},
    ]
    rows = rows_from_events(events, group=4)
    assert len(rows) == 2
    assert np.allclose(rows[0]["visual"], board_features(initial_board))
    assert np.allclose(rows[1]["visual"], board_features(after_board))
    assert [row["advanced"] for row in rows] == [1, 0]
    assert [row["group"] for row in rows] == [4, 4]


def test_action_encoder_ignores_display_arguments() -> None:
    action_only = action_features("ACTION6")
    with_display = action_features("ACTION6(row=4,col=9)")
    assert action_only.sum() == 1
    assert with_display.sum() == 1
    assert not np.array_equal(action_only, with_display)


def test_group_folds_hold_out_whole_runs_and_keep_positive_examples() -> None:
    groups = np.repeat(np.arange(10), 2)
    labels = np.tile(np.asarray([1, 0]), 10)
    folds = grouped_folds(groups, labels, n_splits=5, seed=20261024)
    assert len(folds) == 5
    for train_mask, test_mask in folds:
        assert set(groups[train_mask]).isdisjoint(set(groups[test_mask]))
        assert labels[test_mask].sum() > 0


def test_average_precision_groups_tied_scores_at_one_threshold() -> None:
    labels = np.asarray([1, 0, 0, 1])
    scores = np.ones(4)
    assert average_precision(labels, scores) == 0.5
