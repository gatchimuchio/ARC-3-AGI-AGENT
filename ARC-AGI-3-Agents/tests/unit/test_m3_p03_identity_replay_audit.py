from __future__ import annotations

import hashlib
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_ROOT = REPOSITORY_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from run_rev5_1_m3_p03_identity_replay_audit import (  # noqa: E402
    OUTPUT_PATH,
    _canonical_json,
    _encoded,
    build_report,
    scan_serialized,
    scan_source_text,
)


def test_identity_and_replay_routes_are_absent_from_the_product_path() -> None:
    report = build_report(REPOSITORY_ROOT)

    assert report["status"] == "M3_P03_PASS"
    findings = report["finding_summary"]
    assert findings["runtime_decision_identity_taint_finding_count"] == 0
    assert findings["active_bundle_forbidden_path_count"] == 0
    assert findings["active_bundle_official_game_literal_count"] == 0
    assert findings["domain_local_residue_runtime_selector_count"] == 0
    assert findings["identity_action_router_finding_count"] == 0
    assert findings["fixed_trajectory_playback_finding_count"] == 0
    boundary = report["orchestration_boundary_audit"]["identity_boundary"]
    assert boundary["rejected_probe_count"] == boundary["probe_count"] == 9
    assert boundary["clean_GenericObservation_accepted"] is True


def test_identity_and_replay_scanners_fail_closed_on_tampering() -> None:
    serialized_findings, _ = scan_serialized(
        {"policy": {"game_id": "ar25-0c556536", "replay_actions": [1, 2]}}
    )
    source_findings = scan_source_text(
        "def choose(game_id):\n    return action_table[game_id]\n",
        label="tampered.py",
    )

    assert serialized_findings
    assert any("game_id" in finding for finding in serialized_findings)
    assert any("argument:game_id" in finding for finding in source_findings)


def test_m3_p03_artifact_is_current_and_logically_sealed() -> None:
    report = build_report(REPOSITORY_ROOT)
    artifact = REPOSITORY_ROOT / OUTPUT_PATH

    assert artifact.read_bytes() == _encoded(report)
    body = dict(report)
    claimed = body.pop("logical_content_sha256")
    assert claimed == hashlib.sha256(_canonical_json(body)).hexdigest()
