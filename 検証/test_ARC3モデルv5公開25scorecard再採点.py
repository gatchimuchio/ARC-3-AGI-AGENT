from __future__ import annotations

import pytest

from ARC3モデルv5公開25scorecard再採点 import _candidate_score, _paired_summary


def test_candidate_score_uses_official_weighting_cap_and_uncompleted_levels() -> None:
    run = {
        "actions_per_level": [10, 10, 3],
        "base_actions_per_level": [5, 20, 5],
        "levels_completed": 2,
        "number_of_levels": 3,
    }

    assert _candidate_score(run) == pytest.approx(42.5)


def test_candidate_score_rejects_inconsistent_level_arrays() -> None:
    run = {
        "actions_per_level": [10, 10],
        "base_actions_per_level": [5],
        "levels_completed": 1,
        "number_of_levels": 2,
    }

    with pytest.raises(ValueError, match="arrays do not match"):
        _candidate_score(run)


def test_paired_summary_counts_improvements_ties_and_regressions() -> None:
    result = _paired_summary([1.0, 2.0, 3.0], [2.0, 2.0, 1.0])

    assert result["paired_environments"] == 3
    assert result["improved_environments"] == 1
    assert result["unchanged_environments"] == 1
    assert result["regressed_environments"] == 1
    assert result["mean_delta"] == pytest.approx(-1.0 / 3.0)
