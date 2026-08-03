from __future__ import annotations

import hashlib
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_ROOT = REPOSITORY_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from run_rev5_1_m3_p02_memory_causality import (  # noqa: E402
    OUTPUT_PATH,
    _canonical_json,
    _encoded,
    build_report,
)


def test_relevant_memory_is_causal_and_irrelevant_memory_is_invariant() -> None:
    report = build_report(REPOSITORY_ROOT)

    assert report["status"] == "M3_P02_PASS"
    assert (
        report["counterfactual_contract"][
            "byte_identical_observation_across_counterfactuals"
        ]
        is True
    )
    audit = report["causality_audit"]
    assert audit["baseline_action_id"] == 29
    assert audit["relevant_no_effect_action_id"] == 11
    assert audit["relevant_progress_action_id"] == 29
    assert audit["invalidated_action_id"] == 29
    assert audit["irrelevant_action_id"] == 29
    assert audit["relevant_M_addition_changes_decision"] is True
    assert audit["relevant_M_revision_changes_decision_consistently"] is True
    assert audit["relevant_M_invalidation_restores_baseline"] is True
    assert audit["irrelevant_M_action_invariance"] is True
    assert audit["non_J_authorized_action_count"] == 0


def test_m3_p02_artifact_is_current_and_logically_sealed() -> None:
    report = build_report(REPOSITORY_ROOT)
    artifact = REPOSITORY_ROOT / OUTPUT_PATH

    assert artifact.read_bytes() == _encoded(report)
    body = dict(report)
    claimed = body.pop("logical_content_sha256")
    assert claimed == hashlib.sha256(_canonical_json(body)).hexdigest()
