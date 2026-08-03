from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_ROOT = REPOSITORY_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from audit_rev5_1_full_sample_closure import (  # noqa: E402
    OUTPUT_PATH,
    _canonical_json,
    _encoded,
    build_report,
)


def test_m2_full_sample_closure_is_complete_and_fail_closed() -> None:
    report = build_report(REPOSITORY_ROOT)

    assert report["status"] == "M2_COMPLETE"
    assert report["run_audit"]["aggregate_game_win_count"] == 75
    assert report["run_audit"]["aggregate_level_completion_count"] == 549
    assert report["run_audit"]["aggregate_runtime_action_count"] == 32199
    assert report["run_audit"]["distinct_session_lineage_count"] == 3
    assert report["shuffle_audit"]["blocking_order_dependency_count"] == 0
    assert report["shuffle_audit"]["per_game_functional_mismatch_count"] == 0
    preliminary = report["identity_replay_preliminary_audit"]
    assert preliminary["active_bundle_forbidden_path_count"] == 0
    assert preliminary["active_bundle_literal_game_id_count"] == 0
    assert preliminary["decision_identity_taint_finding_count"] == 0
    assert preliminary["identity_action_router_finding_count"] == 0
    assert preliminary["fixed_trajectory_playback_finding_count"] == 0
    assert preliminary["full_M3_P03_audit_still_required"] is True
    assert report["claim_boundary"]["genericity_established"] is False
    assert report["claim_boundary"]["product_completion_established"] is False


def test_m2_full_sample_closure_artifact_is_current_and_logically_sealed() -> None:
    report = build_report(REPOSITORY_ROOT)
    artifact = REPOSITORY_ROOT / OUTPUT_PATH

    assert artifact.read_bytes() == _encoded(report)
    body = dict(report)
    claimed = body.pop("logical_content_sha256")
    assert claimed == hashlib.sha256(_canonical_json(body)).hexdigest()
    decoded = json.loads(artifact.read_text(encoding="utf-8"))
    assert decoded["exit_audit"]["M2_complete"] is True
