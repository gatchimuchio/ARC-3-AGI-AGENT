from __future__ import annotations

from pathlib import Path

from arc3_agi_agent.teacher.s5_runtime_audit import (
    inspect_s5_policy_artifact,
    inspect_s5_runtime_boundary,
)

PACKAGE_DIR = Path(__file__).resolve().parents[2] / "arc3_agi_agent"


def test_s5_runtime_decision_boundary_is_teacher_free() -> None:
    report = inspect_s5_runtime_boundary(PACKAGE_DIR)

    assert report["status"] == "PASS"
    assert report["failures"] == []
    assert report["policy_predict_parameters"] == [
        "self",
        "observation",
        "context",
        "memory",
    ]
    assert report["source_render_digest_used_as_policy_feature"] is False


def test_s5_runtime_bundle_contains_only_parameter_arrays() -> None:
    report = inspect_s5_policy_artifact(
        manifest_path=(
            PACKAGE_DIR / "bundles" / "s5_rendered_policy_v1.json"
        ),
        weights_path=(
            PACKAGE_DIR / "bundles" / "s5_rendered_policy_v1.npz"
        ),
    )

    assert report["status"] == "PASS"
    assert report["failures"] == []
    assert report["training_examples_present"] is False
    assert report["forbidden_runtime_paths"] == []
