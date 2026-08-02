from __future__ import annotations

import json
import subprocess
from pathlib import Path
from typing import Any

from arc3_agi_agent.product_completion_audit import (
    evaluate_product_completion_evidence,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _json(relative: str) -> dict[str, Any]:
    value = json.loads(
        (REPOSITORY_ROOT / relative).read_text(encoding="utf-8")
    )
    assert isinstance(value, dict)
    return value


def _committed_json(relative: str) -> dict[str, Any]:
    payload = subprocess.run(
        ("git", "show", f"HEAD:{relative}"),
        cwd=REPOSITORY_ROOT,
        check=True,
        capture_output=True,
        text=True,
    ).stdout
    value = json.loads(payload)
    assert isinstance(value, dict)
    return value


def test_current_evidence_reopens_genericity_instead_of_claiming_completion() -> None:
    report = evaluate_product_completion_evidence(
        known_sample_report=_json(
            "analysis/product/rev4/m4_full_sample_product.json"
        ),
        clean_install_report=_json(
            "analysis/product/rev4/m5_clean_install_product.json"
        ),
        release_report=_json(
            "analysis/product/rev4/m5_product_release.json"
        ),
        product_descriptor=_json(
            "ARC-AGI-3-Agents/arc3_agi_agent/bundles/"
            "arc3_product_initial_state_v1.json"
        ),
        active_policy_manifest=_json(
            "ARC-AGI-3-Agents/arc3_agi_agent/bundles/"
            "generic_autonomous_policy_v1.json"
        ),
        teacher_policy_manifest=_json(
            "ARC-AGI-3-Agents/arc3_agi_agent/bundles/"
            "s5_rendered_policy_v1.json"
        ),
        cv_manifest=_committed_json(
            "analysis/autonomous_completion/cv_manifest.json"
        ),
        perturbation_report=_json(
            "analysis/runtime/S6_PERTURBATION_MEASUREMENT.json"
        ),
        active_transformation_report=_json(
            "analysis/product/rev4/m3_active_product_transformation.json"
        ),
        sealed_report=_json(
            "analysis/genericity/SEALED_CUSTOM_ENV_REPORT.json"
        ),
    )

    assert report["known_sample"]["regression_complete"] is True
    assert report["known_sample"]["clean_install_regression_complete"] is True
    assert report["active_policy"]["full_teacher_parameter_copy"] is True
    assert report["active_policy"]["teacher_action_record_count"] == 10733
    assert report["cv"]["execution_count"] == 25
    assert report["cv"]["completed_environment_count"] == 0
    assert report["cv"]["completed_level_count"] == 0
    assert report["cv"]["completion_established"] is False
    assert report["perturbation"]["semantic_completion_established"] is True
    assert report["sealed"]["same_active_artifact"] is False
    assert report["official"]["score"] is None
    assert report["product_completion_allowed"] is False
    assert report["status"] == "M3_GENERICITY_REOPENED"
    assert "AUT_006_ACTIVE_ARTIFACT_LOCKED_EVALUATOR" in report[
        "blocking_requirement_ids"
    ]
