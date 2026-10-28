"""pinned SDKのplay分割と採点警告を検証する。"""

from types import SimpleNamespace
import logging

from arc_agi.models import EnvironmentInfo
from arc_agi.scorecard import EnvironmentScorecard, Scorecard
from arc_agi.wrapper import EnvironmentWrapper
from arcengine import GameState

from 検証.ARC3実Agent成分代表paired import _WarningCounter


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


def test_sdk_scorecard_update_failure_is_counted():
    class FailedScorecard:
        def add_game(self, card_id, guid):
            raise RuntimeError("synthetic scorecard failure")

    counter = _WarningCounter()
    logger = logging.getLogger("arc3-test-scorecard-failure")
    logger.handlers.clear()
    logger.addHandler(counter)
    logger.setLevel(logging.WARNING)
    logger.propagate = False
    wrapper = EnvironmentWrapper(
        EnvironmentInfo(game_id="synthetic-test"), logger, "synthetic-card", scorecard_manager=FailedScorecard()
    )
    wrapper._set_last_response(SimpleNamespace(guid="synthetic", frame=[[]], full_reset=True))
    assert counter.count == 1
