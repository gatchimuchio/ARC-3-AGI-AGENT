from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from arc3_agi_agent.s5_policy import S5HistoryRecord
from arc3_agi_agent.schema import digest_object
from arc3_agi_agent.teacher.s6_generalization import (
    S6_GENERALIZATION_DIGEST_PREFIX,
    S6_GENERALIZATION_SCHEMA_VERSION,
    S6_REQUIRED_FAMILIES,
    load_s6_generalization_report,
    perturb_s6_frame,
    perturb_s6_history,
    select_s6_measurement_indices,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
CANONICAL_REPORT = (
    REPOSITORY_ROOT
    / "analysis"
    / "runtime"
    / "S6_PERTURBATION_MEASUREMENT.json"
)


def _small_arrays() -> dict[str, np.ndarray]:
    return {
        "actions": np.asarray(
            [6, 1, 2, 3, 0, 4, 6, 1, 2, 3, 4, 5],
            dtype=np.uint8,
        ),
        "game_ordinal": np.asarray(
            [0, 0, 0, 0, 0, 0, 1, 1, 1, 1, 1, 1],
            dtype=np.uint8,
        ),
        "levels_completed": np.asarray(
            [0, 0, 0, 1, 1, 1, 0, 0, 0, 1, 1, 1],
            dtype=np.uint8,
        ),
        "level_compatibility_reset": np.asarray(
            [0, 0, 0, 0, 1, 0, 0, 0, 0, 0, 0, 0],
            dtype=np.uint8,
        ),
    }


def test_selection_is_exact_deterministic_and_covers_each_level() -> None:
    arrays = _small_arrays()

    first = select_s6_measurement_indices(arrays, sample_size=9)
    second = select_s6_measurement_indices(arrays, sample_size=9)

    assert np.array_equal(first, second)
    assert len(first) == 9
    covered = {
        (
            int(arrays["game_ordinal"][index]),
            int(arrays["levels_completed"][index]),
        )
        for index in first
    }
    assert covered == {(0, 0), (0, 1), (1, 0), (1, 1)}
    assert 4 in first


def test_selection_rejects_insufficient_coverage_budget() -> None:
    with pytest.raises(
        ValueError,
        match="S6_SAMPLE_SIZE_BELOW_REQUIRED_COVERAGE",
    ):
        select_s6_measurement_indices(
            _small_arrays(),
            sample_size=4,
        )


def test_frame_perturbations_have_pinned_geometry_and_palette() -> None:
    frame = np.zeros((64, 64), dtype=np.uint8)
    frame[10, 20] = 2
    frame[30, 40] = 4
    frame[30, 41] = 4

    color = perturb_s6_frame(frame, "COLOR")
    rotation = perturb_s6_frame(frame, "ROTATION")
    reflection = perturb_s6_frame(frame, "REFLECTION")
    layout = perturb_s6_frame(frame, "LAYOUT")
    count = perturb_s6_frame(frame, "OBJECT_COUNT")

    assert int(color[10, 20]) == 13
    assert int(color[0, 0]) == 3
    assert int(rotation[43, 10]) == 2
    assert int(reflection[10, 43]) == 2
    assert int(layout[13, 25]) == 2
    assert int(count[10, 20]) == 0
    assert int(count[30, 40]) == 4
    assert int(count[30, 41]) == 4


def test_history_perturbation_transforms_pointer_and_order() -> None:
    history = (
        S5HistoryRecord(
            action_id=1,
            visible_change=True,
        ),
        S5HistoryRecord(
            action_id=6,
            horizontal=20,
            vertical=10,
            target_palette=2,
            visible_change=True,
        ),
    )

    rotation = perturb_s6_history(history, "ROTATION")
    composition = perturb_s6_history(
        history,
        "UNSEEN_COMPOSITION",
    )

    assert rotation[1].horizontal == 10
    assert rotation[1].vertical == 43
    assert composition[0].action_id == 6
    assert composition[0].horizontal == 10
    assert composition[0].vertical == 43
    assert composition[0].target_palette == 13


def test_report_loader_rejects_tampering(tmp_path: Path) -> None:
    body: dict[str, object] = {
        "schema_version": S6_GENERALIZATION_SCHEMA_VERSION,
        "status": "COMPLETE",
        "generalization_claim": "MEASURED_NOT_PROVEN",
        "semantic_ground_truth_available": False,
        "full_environment_completion_executed": False,
        "exception_count": 0,
        "families": [
            {"family_id": family_id}
            for family_id in S6_REQUIRED_FAMILIES
        ],
    }
    report = {
        **body,
        "content_digest": (
            S6_GENERALIZATION_DIGEST_PREFIX + digest_object(body)
        ),
    }
    path = tmp_path / "report.json"
    path.write_text(
        json.dumps(report, sort_keys=True),
        encoding="utf-8",
    )
    assert load_s6_generalization_report(path)["status"] == "COMPLETE"

    report["status"] = "INCOMPLETE"
    path.write_text(
        json.dumps(report, sort_keys=True),
        encoding="utf-8",
    )
    with pytest.raises(
        ValueError,
        match="S6_REPORT_CONTENT_DIGEST_INVALID",
    ):
        load_s6_generalization_report(path)


def test_canonical_report_measures_all_families_without_claim_inflation() -> None:
    report = load_s6_generalization_report(CANONICAL_REPORT)

    assert report["selected_record_count"] == 2048
    assert report["covered_game_count"] == 25
    assert report["covered_level_count"] == 183
    assert report["total_measurement_count"] == 14_336
    assert report["baseline_policy_action_error_count"] == 0
    assert report["baseline_policy_pointer_error_count"] == 0
    assert report["exception_count"] == 0
    assert report["generalization_claim"] == "MEASURED_NOT_PROVEN"
    assert report["semantic_ground_truth_available"] is False
    assert report["full_environment_completion_executed"] is False
