from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from arc3_agi_agent.p22_evaluator import (
    build_active_compiled_p_bundle,
    run_memory_ablation,
    run_transformation_stress,
)
from arc3_agi_agent.p_bundle import PBundle
from arc3_agi_agent.schema import canonical_json
from arc3_agi_agent.teacher.p22_cross_validation import (
    deterministic_cv_folds,
)


@pytest.fixture(scope="module")
def active_bundle() -> PBundle:
    return build_active_compiled_p_bundle()


def _assert_content_bound(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    expected = str(value.pop("content_digest"))
    actual = "p22-evidence:" + hashlib.sha256(
        canonical_json(value).encode("utf-8")
    ).hexdigest()
    assert expected == actual
    return value


def test_transformation_completion_is_environment_execution(
    tmp_path: Path,
    active_bundle: PBundle,
) -> None:
    path = tmp_path / "transformation_completion.json"

    report = run_transformation_stress(
        output_path=path,
        bundle=active_bundle,
    )
    persisted = _assert_content_bound(path)

    assert report["status"] == persisted["status"] == "PASS"
    assert report["transformation_completion"] == {
        "completed": 7,
        "required": 7,
    }
    assert len(report["results"]) == 7
    assert all(item["completed"] for item in report["results"])
    assert report["final_generic_claim"] == "NOT_AUTHORIZED"


def test_all_memory_ablations_measure_degradation(
    tmp_path: Path,
    active_bundle: PBundle,
) -> None:
    path = tmp_path / "memory_ablation.json"

    report = run_memory_ablation(
        output_path=path,
        bundle=active_bundle,
    )
    persisted = _assert_content_bound(path)

    assert report["status"] == persisted["status"] == "PASS"
    assert report["memory_ablation_degrades"] is True
    assert report["memory_causal_witness_count"] == 5
    assert set(report["results"]) == {
        "read",
        "write",
        "consolidation",
        "rollback",
        "session_global",
    }
    assert all(
        item["degraded"] for item in report["results"].values()
    )


def test_cv_partition_is_disjoint_and_complete() -> None:
    folds = deterministic_cv_folds()
    flattened = [ordinal for fold in folds for ordinal in fold]

    assert len(folds) == 5
    assert all(len(fold) == 5 for fold in folds)
    assert sorted(flattened) == list(range(25))
    assert len(flattened) == len(set(flattened))
