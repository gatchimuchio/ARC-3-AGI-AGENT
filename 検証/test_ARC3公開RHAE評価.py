from __future__ import annotations

from 検証.ARC3公開RHAE評価 import _スコアを計算する


def _実行結果(レベル変化: list[int]) -> dict:
    return {
        "actions": len(レベル変化),
        "initial_levels_completed": 0,
        "levels_completed": sum(max(0, value) for value in レベル変化),
        "action_responses": [{"level_delta": value} for value in レベル変化],
    }


def test_未完了runはscorecardで零点になる() -> None:
    score, events, _ = _スコアを計算する([10, 20], _実行結果([0, 0, 0]))

    assert score == 0.0
    assert events == 0


def test_level別行動数とlevel番号weightを公式calculatorへ渡す() -> None:
    # Level 1: baseline 10 / agent 20 -> 25 points.
    # Level 2: baseline 20 / agent 20 -> 100 points.
    result = _実行結果([0] * 19 + [1] + [0] * 19 + [1])
    score, events, levels = _スコアを計算する([10, 20], result)

    assert score == 75.0
    assert events == 2
    assert [level["actions"] for level in levels] == [20, 20]
    assert [level["completed"] for level in levels] == [True, True]


def test_single_level_shortcut_respects_game_reach_cap() -> None:
    score, events, levels = _スコアを計算する([10, 20], _実行結果([0, 0, 0, 0, 1]))

    assert abs(score - 100 / 3) < 1e-9
    assert events == 1
    assert [level["completed"] for level in levels] == [True, False]


def test_baseline不足時はscorecard既定の零点へfall_backする() -> None:
    score, events, levels = _スコアを計算する([], _実行結果([0, 1]))

    assert score == 0.0
    assert events == 1
    assert levels == []
