from __future__ import annotations

import hashlib
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_ROOT = REPOSITORY_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from run_rev5_1_m3_p01_ablation import (  # noqa: E402
    OUTPUT_PATH,
    _canonical_json,
    _encoded,
    build_report,
)


def test_m3_p01_each_subject_removal_matches_the_trinity_contract() -> None:
    report = build_report(REPOSITORY_ROOT)

    assert report["status"] == "M3_P01_PASS"
    assert report["baseline"]["final_state"] == "WIN"
    assert report["baseline"]["action_sequence"] == [29, 11]
    assert report["baseline"]["all_actions_J_authorized"] is True
    assert report["baseline"]["all_memory_updates_J_authorized"] is True
    assert report["C_removal"]["witness"] == ("GENERIC_EFFECTIVE_SERIAL_DEPTH_REMOVED")
    assert report["C_removal"]["new_representation_hypothesis_plan_generated"] is False
    assert report["J_removal"]["external_action_count"] == 0
    assert report["J_removal"]["active_memory_commit_count"] == 0
    assert report["M_removal"]["action_sequence"] == [29] * 6
    assert report["M_removal"]["learning_delta_disappeared"] is True
    assert report["P_removal"]["ARC3_capability_available"] is False
    assert (
        report["functional_equivalent_audit"]["functional_equivalent_leak_count"] == 0
    )


def test_m3_p01_artifact_is_current_and_logically_sealed() -> None:
    report = build_report(REPOSITORY_ROOT)
    artifact = REPOSITORY_ROOT / OUTPUT_PATH

    assert artifact.read_bytes() == _encoded(report)
    body = dict(report)
    claimed = body.pop("logical_content_sha256")
    assert claimed == hashlib.sha256(_canonical_json(body)).hexdigest()
