"""pinned SDKのplay分割と採点警告を検証する。"""

from types import SimpleNamespace

from arc_agi.models import EnvironmentInfo
from arc_agi.scorecard import EnvironmentScorecard, Scorecard
from arcengine import GameState


def _event(card, guid, action, completed=0, state=GameState.NOT_FINISHED, full_reset=False):
    data = SimpleNamespace(
        game_id="synthetic-test",
        action_input=SimpleNamespace(id=SimpleNamespace(value=action)),
        state=state,
        levels_completed=completed,
    )
    card.update_scorecard(guid, data, full_reset)


def test_full_reset_creates_new_play_and_uses_best_play_score():
    card = Scorecard()
    _event(card, "first", 0, full_reset=True)
    for index in range(4):
        _event(card, "first", 1, completed=int(index == 3))
    _event(card, "second", 0, full_reset=True)
    _event(card, "second", 1)
    _event(card, "second", 1, completed=1, state=GameState.WIN)
    scorecard = EnvironmentScorecard.from_scorecard(
        card, [EnvironmentInfo(game_id="synthetic-test", baseline_actions=[2])]
    )
    result = scorecard.find_environment("synthetic-test")
    assert result is not None
    assert len(result.runs) == 2
    assert [run.actions for run in result.runs] == [4, 2]
    assert [run.score for run in result.runs] == [25.0, 100.0]
    assert result.score == 100.0


def test_missing_baseline_emits_diagnostic_not_a_clean_zero_score():
    card = Scorecard()
    _event(card, "first", 0, full_reset=True)
    _event(card, "first", 1)
    result = EnvironmentScorecard.from_scorecard(
        card, [EnvironmentInfo(game_id="synthetic-test")]
    ).find_environment("synthetic-test")
    assert result is not None
    assert result.runs[0].score == 0.0
    assert result.runs[0].message
