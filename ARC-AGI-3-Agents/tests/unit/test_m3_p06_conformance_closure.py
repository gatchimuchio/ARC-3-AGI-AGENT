from __future__ import annotations

import hashlib
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_ROOT = REPOSITORY_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from audit_rev5_1_m3_conformance_closure import (  # noqa: E402
    OUTPUT_PATH,
    _canonical_json,
    _encoded,
    build_report,
)


def test_m3_conformance_closure_binds_all_gates_and_fresh_full_run() -> None:
    report = build_report(REPOSITORY_ROOT)

    assert report["status"] == "M3_COMPLETE"
    gates = report["conformance_gate_audit"]
    assert gates["required_point_count"] == gates["passing_point_count"] == 5
    assert gates["failed_point_count"] == 0
    full = report["fresh_full_sample_regression"]
    assert full["fresh_game_WIN_count"] == 25
    assert full["fresh_level_completion_count"] == 183
    assert full["fresh_failure_count"] == 0
    assert full["fresh_lifecycle_failure_count"] == 0
    assert full["fresh_runtime_failure_signature_count"] == 0
    assert full["all_external_actions_J_authorized"] is True
    bundle = report["product_bundle_audit"]
    assert bundle["active_development_product_bundle_count"] == 1
    assert bundle["active_bundle_unchanged"] is True
    assert bundle["P05_candidate_activation_count"] == 0


def test_m3_closure_artifact_is_current_and_logically_sealed() -> None:
    report = build_report(REPOSITORY_ROOT)
    artifact = REPOSITORY_ROOT / OUTPUT_PATH

    assert artifact.read_bytes() == _encoded(report)
    body = dict(report)
    claimed = body.pop("logical_content_sha256")
    assert claimed == hashlib.sha256(_canonical_json(body)).hexdigest()
