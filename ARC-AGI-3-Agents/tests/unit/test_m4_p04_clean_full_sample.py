from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
RUN_PATH = (
    REPOSITORY_ROOT
    / "analysis"
    / "product"
    / "rev5_1"
    / "m4_p04_clean_full_sample_run.json"
)
CLOSURE_PATH = (
    REPOSITORY_ROOT
    / "analysis"
    / "product"
    / "rev5_1"
    / "m4_p04_clean_full_sample_closure.json"
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def test_m4_p04_clean_installed_full_sample_is_sealed_and_complete() -> None:
    run_payload = RUN_PATH.read_bytes()
    run = json.loads(run_payload)
    closure = json.loads(CLOSURE_PATH.read_text(encoding="utf-8"))
    claimed = closure.pop("logical_content_sha256")
    canonical = json.dumps(
        closure,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")

    assert claimed == _sha256(canonical)
    assert closure["status"] == "M4_P04_PASS"
    assert closure["source_bindings"]["clean_installed_run"]["sha256"] == _sha256(
        run_payload
    )
    assert closure["clean_execution"] == {
        **closure["clean_execution"],
        "product_process_exit_code": 0,
        "console_entrypoint_count": 1,
        "stdout_json_equal_to_report": True,
        "development_tree_path_exposure_count": 0,
        "credential_environment_count": 0,
        "same_clean_install_as_M4_P03": True,
        "same_release_artifact_as_M4_P02": True,
        "source_tree_module_invocation_count": 0,
        "manual_step_intervention_count": 0,
        "network_service_count": 0,
    }
    assert closure["release_identity"]["release_bundle_count"] == 1
    assert closure["release_identity"]["active_dev_bundle_count"] == 0
    assert closure["release_identity"]["runtime_policy_changed"] is False
    assert closure["full_sample_audit"] == {
        **closure["full_sample_audit"],
        "official_sample_game_count": 25,
        "game_WIN_count": 25,
        "level_completion_count": 183,
        "total_action_count": 10733,
        "game_failure_count": 0,
        "lifecycle_failure_count": 0,
        "adapter_crash_count": 0,
        "runtime_failure_signature_count": 0,
        "J_plan_commit_count": 10733,
        "executed_plan_count": 10733,
        "unauthorized_action_count": 0,
    }
    assert closure["equivalence_audit"]["functional_mismatch_count"] == 0
    assert closure["equivalence_audit"]["functional_equivalence"] is True
    assert closure["equivalence_audit"]["independent_session_lineage"] is True
    assert closure["exit_audit"]["status"] == "M4_P04_PASS"
    assert closure["claim_boundary"]["Kaggle_normal_run_complete"] is False

    assert run["product_game_win_count"] == 25
    assert run["product_level_completion_count"] == 183
    assert run["product_total_action_count"] == 10733
    assert run["product_hds_plan_commit_count"] == 10733
    assert run["product_executed_plan_count"] == 10733
    assert run["failed_game_count"] == 0
    assert run["lifecycle_failure_count"] == 0
    assert run["adapter_crash_count"] == 0
    assert run["product_bundle_stage"] == "RELEASE_FROZEN"
    assert run["product_release_bundle_loaded"] is True
    assert run["product_active_dev_mechanism_family_count"] == 0
    assert run["product_release_frozen_mechanism_family_count"] == 1
    assert len(run["results"]) == 25
    assert all(row["final_state"] == "WIN" for row in run["results"])
    assert all(row["stop_reason"] == "GOAL_REACHED" for row in run["results"])

    encoded_closure = json.dumps(closure, ensure_ascii=False)
    assert "install_root" not in encoded_closure
    assert "C:\\\\Users" not in encoded_closure
