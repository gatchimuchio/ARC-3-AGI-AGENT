from __future__ import annotations

import importlib
from pathlib import Path
import subprocess
import sys

from 接続.ARC3境界 import 観測

評価器 = importlib.import_module("検証.ARC3探索Actionローカル評価")


def test_policy_seed_defaults_to_environment_seed_for_compatibility() -> None:
    assert 評価器._policy_seed(31, None) == 31


def test_explicit_policy_seed_is_independent() -> None:
    assert 評価器._policy_seed(31, 73) == 73


def test_help_command_succeeds_and_lists_seed_options() -> None:
    runner = Path(__file__).with_name("ARC3探索Actionローカル評価.py")
    result = subprocess.run(
        [sys.executable, "-X", "utf8", str(runner), "--help"],
        capture_output=True,
        encoding="utf-8",
        check=False,
    )

    assert result.returncode == 0, result.stderr
    assert "--seed" in result.stdout
    assert "--policy-seed" in result.stdout
    assert "--hash-seed-from-initial-observation" in result.stdout
    assert "--reset-action-ucb-stats-each-level" in result.stdout


def _観測(
    *,
    game_id: str,
    board: tuple[tuple[int, ...], ...],
    actions: tuple[int, ...] = (1, 6),
    completed_levels: int = 0,
) -> 観測:
    return 観測(
        ゲーム識別子=game_id,
        観測通番=0,
        状態="NOT_FINISHED",
        完了レベル数=completed_levels,
        全レベル数=max(1, completed_levels + 1),
        作用可能番号=actions,
        盤面列=(board,),
        全初期化=False,
        実行識別子=None,
        指紋=f"fingerprint-{game_id}",
    )


def test_hash_seed_uses_only_public_state_board_and_available_actions() -> None:
    board = ((0, 1), (1, 0))
    first = _観測(game_id="first", board=board)
    same_public_state = _観測(game_id="second", board=board)
    changed_public_state = _観測(game_id="first", board=((0, 0), (1, 1)))
    changed_actions = _観測(game_id="first", board=board, actions=(1,))

    assert 評価器._初期公開観測seed(first) == 評価器._初期公開観測seed(same_public_state)
    assert 評価器._初期公開観測seed(first) != 評価器._初期公開観測seed(changed_public_state)
    assert 評価器._初期公開観測seed(first) != 評価器._初期公開観測seed(changed_actions)


def test_hash_seed_makes_first_action_independent_of_unseeded_policy_rng() -> None:
    observation_a = _観測(game_id="same", board=((0, 1), (1, 0)))
    observation_b = _観測(game_id="same", board=((0, 1), (1, 0)))
    policy_a = 評価器._初期観測hashseedablation(乱数種=7)
    policy_b = 評価器._初期観測hashseedablation(乱数種=101)

    action_a = policy_a.選ぶ(observation_a)
    action_b = policy_b.選ぶ(observation_b)

    assert action_a == action_b
    assert policy_a._初期観測seed適用済み is True
    assert policy_b._初期観測seed適用済み is True


def test_action_ucb_level_reset_preserves_color_stats_and_progress_response() -> None:
    observation_before = _観測(
        game_id="same-game",
        board=((0, 1), (1, 0)),
        actions=(6,),
    )
    observation_after = _観測(
        game_id="same-game",
        board=((1, 0), (0, 1)),
        actions=(6,),
        completed_levels=1,
    )
    policy = 評価器._レベル進行時ActionUCB統計resetablation(乱数種=7)
    action = policy.選ぶ(observation_before)
    assert action is not None

    response = policy.応答を記録する(observation_before, action, observation_after)

    assert response["完了レベル増分"] == 1
    assert response["公開応答報酬"] >= 4.0
    assert policy._回数 == {}
    assert policy._報酬合計 == {}
    assert policy._総作用数 == 0
    assert sum(policy._色回数.values()) == 1
    assert sum(policy._色報酬合計.values()) == response["公開応答報酬"]
