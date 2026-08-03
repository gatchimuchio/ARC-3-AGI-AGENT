from __future__ import annotations

import hashlib
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_ROOT = REPOSITORY_ROOT / "scripts"
if str(SCRIPTS_ROOT) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_ROOT))

from run_rev5_1_m3_p05_runtime_version_learning import (  # noqa: E402
    CANDIDATE_PACKAGE_PATH,
    OUTPUT_PATH,
    _canonical_json,
    _encoded,
    build_outputs,
)


def test_runtime_learning_precedes_multi_run_version_candidate() -> None:
    report, _ = build_outputs(REPOSITORY_ROOT)

    assert report["status"] == "M3_P05_PASS"
    runtime = report["runtime_learning"]
    assert runtime["run_count"] == 3
    assert runtime["runtime_experience_updates_M_first"] is True
    assert runtime["first_run_global_causal_state"] == "PROBATION"
    assert runtime["first_run_version_candidate_created"] is False
    assert report["one_success_gate"]["candidate_record_count"] == 0
    assert report["one_success_gate"]["decision"] == "HOLD_RUNTIME_M"
    assert report["multi_run_gate"]["candidate_record_count"] == 1
    assert report["multi_run_gate"]["decision"] == "PROMOTE_TO_VERSION_CANDIDATE"


def test_false_learning_rollback_and_compiled_restart_are_causal() -> None:
    report, _ = build_outputs(REPOSITORY_ROOT)

    false_learning = report["false_learning_control"]
    assert false_learning["negative_transfer_decision"] == "INVALIDATE"
    assert false_learning["false_record_suspended_after_invalidation"] is True
    assert false_learning["false_record_execute_eligible_after_invalidation"] is False
    assert false_learning["false_record_absent_after_rollback"] is True
    assert false_learning["pre_injection_active_memory_restored"] is True
    assert false_learning["admitted_to_candidate_input"] is False
    candidate = report["next_version_candidate"]
    assert candidate["status"] == "CANDIDATE_PENDING_M3_P06"
    assert candidate["activation_performed"] is False
    assert candidate["package_roundtrip_byte_identical"] is True
    assert candidate["candidate_M0_record_count"] == (
        candidate["parent_M0_record_count"] + 1
    )
    restart = report["restart_evidence"]
    assert restart["same_observation"] is True
    assert restart["acquired_capability_changes_restart_behavior"] is True
    assert restart["acquired_record_retrieved"] is True
    assert restart["acquired_record_bound_to_selected_candidate"] is True
    assert restart["training_SemanticMemory_object_reused"] is False


def test_m3_p05_artifacts_are_current_and_logically_sealed() -> None:
    report, package = build_outputs(REPOSITORY_ROOT)
    artifact = REPOSITORY_ROOT / OUTPUT_PATH
    candidate = REPOSITORY_ROOT / CANDIDATE_PACKAGE_PATH

    assert artifact.read_bytes() == _encoded(report)
    assert candidate.read_bytes() == package
    assert (
        hashlib.sha256(package).hexdigest()
        == report["next_version_candidate"]["package_sha256"]
    )
    body = dict(report)
    claimed = body.pop("logical_content_sha256")
    assert claimed == hashlib.sha256(_canonical_json(body)).hexdigest()
