from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

from arc3_agi_agent.product_governance import (
    ARC3_CURRENT_SELECTOR_PATH,
    ARC3_DEVELOPMENT_ACTION_BUDGET,
    ARC3_KNOWN_SUCCESS_ACTION_CEILING,
    ARC3_LEGACY_REV3_IS_CURRENT,
    ARC3_OFFICIAL_SAMPLE_GAME_TARGET,
    ARC3_OFFICIAL_SAMPLE_LEVEL_TARGET,
    ARC3_PRODUCT_ACTIVE_MILESTONE,
    ARC3_PRODUCT_ENDPOINT,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected object: {path}")
    return value


def _complete_report() -> dict[str, object]:
    progress = [8] * 8 + [7] * 17
    assert sum(progress) == 183
    return {
        "advertised_game_count": 25,
        "completed_game_count": 25,
        "failed_game_count": 0,
        "lifecycle_failure_count": 0,
        "active_agent_peak": 1,
        "scorecard_open_count": 1,
        "scorecard_close_count": 1,
        "scorecard_closed": True,
        "results": [
            {
                "game_index": index,
                "progress_count": progress[index],
                "final_state": "WIN",
            }
            for index in range(25)
        ],
    }


def test_product_governance_constants_match_endpoint() -> None:
    assert ARC3_CURRENT_SELECTOR_PATH == "control/rev4/CURRENT_TASK.json"
    assert ARC3_PRODUCT_ACTIVE_MILESTONE == ("M0_PRODUCT_BASELINE_AND_BLOCKER_CLOSURE")
    assert ARC3_OFFICIAL_SAMPLE_GAME_TARGET == 25
    assert ARC3_OFFICIAL_SAMPLE_LEVEL_TARGET == 183
    assert ARC3_DEVELOPMENT_ACTION_BUDGET == 4096
    assert ARC3_KNOWN_SUCCESS_ACTION_CEILING == 1519
    assert ARC3_LEGACY_REV3_IS_CURRENT is False
    assert ARC3_PRODUCT_ENDPOINT.validate() == ()


def test_product_endpoint_accepts_only_the_full_measured_result() -> None:
    metrics = ARC3_PRODUCT_ENDPOINT.metrics(_complete_report())

    assert metrics["product_endpoint_failure_count"] == 0
    assert metrics["product_endpoint_failures"] == ()
    assert metrics["product_game_win_count"] == 25
    assert metrics["product_level_completion_count"] == 183
    assert metrics["product_completion_established"] is True
    assert metrics["product_status"] == "COMPLETE"


def test_product_endpoint_rejects_duplicate_index_and_open_scorecard() -> None:
    report = _complete_report()
    results = report["results"]
    assert isinstance(results, list)
    results[-1]["game_index"] = 0
    report["scorecard_closed"] = False

    metrics = ARC3_PRODUCT_ENDPOINT.metrics(report)
    endpoint_failures = metrics["product_endpoint_failures"]

    assert metrics["product_completion_established"] is False
    assert isinstance(endpoint_failures, tuple)
    assert "PRODUCT_GAME_INDEX_COVERAGE_MISMATCH" in endpoint_failures
    assert "PRODUCT_SCORECARD_NOT_CLOSED" in endpoint_failures


def test_rev4_current_task_and_legacy_boundary_are_explicit() -> None:
    current = _json(REPOSITORY_ROOT / ARC3_CURRENT_SELECTOR_PATH)
    classification = _json(
        REPOSITORY_ROOT / "control" / "rev4" / "LEGACY_REV3_CLASSIFICATION.json"
    )

    assert current["schema_version"] == "arc3-product-current-task-v2"
    assert current["active_milestone"] == ARC3_PRODUCT_ACTIVE_MILESTONE
    assert current["legacy_rev3"]["current_selector"] is False
    assert classification["classification"] == "HISTORICAL_REUSE_ONLY"
    assert classification["current_selector"] is False
    assert classification["runtime_activation_eligible"] is False
    assert classification["phase_authority_eligible"] is False


def test_rev4_product_governance_validator_passes() -> None:
    script = REPOSITORY_ROOT / "scripts" / "validate_rev4_product_governance.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=REPOSITORY_ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    report = json.loads(result.stdout)
    assert report["status"] == "PASS"
    assert report["failure_count"] == 0
    assert report["check_count"] >= 20
