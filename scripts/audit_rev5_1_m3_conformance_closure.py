#!/usr/bin/env python3
"""Build or verify the rev5.1 M3 full conformance closure."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
from typing import Final

REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[1]
OUTPUT_PATH: Final = Path("analysis/product/rev5_1/m3_conformance_closure.json")
FULL_RUN_PATH: Final = Path(
    "analysis/product/rev5_1/m3_p06_clean_full_regression_run.json"
)
TEST_RUN_PATH: Final = Path("analysis/product/rev5_1/m3_p06_conformance_test_run.json")
ACTIVE_DESCRIPTOR_PATH: Final = Path(
    "ARC-AGI-3-Agents/arc3_agi_agent/bundles/arc3_product_initial_state_v1.json"
)
ACTIVE_PACKAGE_PATH: Final = Path(
    "ARC-AGI-3-Agents/arc3_agi_agent/bundles/arc3_product_initial_state_v1.zip"
)
CANDIDATE_PACKAGE_PATH: Final = Path(
    "analysis/product/rev5_1/m3_p05_next_initial_state_candidate.zip"
)
M2_CLOSURE_PATH: Final = Path(
    "analysis/product/rev5_1/m2_full_sample_product_closure.json"
)
M2_RUN_A_PATH: Final = Path("analysis/product/rev5_1/m2_p01_clean_run_a.json")
CONFORMANCE_PATHS: Final = {
    "M3-P01": Path("analysis/product/rev5_1/m3_p01_cjmp_ablation.json"),
    "M3-P02": Path("analysis/product/rev5_1/m3_p02_memory_causality.json"),
    "M3-P03": Path("analysis/product/rev5_1/m3_p03_identity_replay_audit.json"),
    "M3-P04": Path("analysis/product/rev5_1/m3_p04_applicability_counterfactual.json"),
    "M3-P05": Path("analysis/product/rev5_1/m3_p05_runtime_version_learning.json"),
}
EXPECTED_STATUSES: Final = {
    "M3-P01": "M3_P01_PASS",
    "M3-P02": "M3_P02_PASS",
    "M3-P03": "M3_P03_PASS",
    "M3-P04": "M3_P04_PASS",
    "M3-P05": "M3_P05_PASS",
}
FUNCTIONAL_FIELDS: Final = (
    "action_id_counts",
    "actions_executed",
    "failed_hypothesis_invalidation_count",
    "failure_attribution_count",
    "failure_signatures",
    "final_state",
    "memory_causal_behavior_change_count",
    "post_rollback_replan_count",
    "progress_count",
    "rollback_plan_count",
    "stop_reason",
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _encoded(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _require(condition: bool, failure: str) -> None:
    if not condition:
        raise RuntimeError(failure)


def _load_object(root: Path, relative: Path) -> tuple[dict[str, object], str]:
    payload = (root / relative).read_bytes()
    value = json.loads(payload.decode("utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"M3_CLOSURE_OBJECT_REQUIRED:{relative.as_posix()}")
    return value, _sha256(payload)


def _verify_logical_seal(value: dict[str, object], *, label: str) -> None:
    body = dict(value)
    claimed = body.pop("logical_content_sha256", None)
    _require(
        claimed == _sha256(_canonical_json(body)),
        f"M3_CLOSURE_LOGICAL_SEAL_INVALID:{label}",
    )


def _rows(
    report: dict[str, object],
    *,
    label: str,
) -> tuple[list[str], dict[str, dict[str, object]]]:
    index = report.get("orchestration_game_index")
    results = report.get("results")
    if not isinstance(index, list) or not isinstance(results, list):
        raise TypeError(f"M3_CLOSURE_RUN_ROWS_INVALID:{label}")
    _require(len(index) == len(results) == 25, f"M3_CLOSURE_RUN_COUNT:{label}")
    order: list[str] = []
    rows: dict[str, dict[str, object]] = {}
    for ordinal, (metadata, result) in enumerate(zip(index, results, strict=True)):
        if not isinstance(metadata, dict) or not isinstance(result, dict):
            raise TypeError(f"M3_CLOSURE_RUN_ROW_INVALID:{label}:{ordinal}")
        game_id = metadata.get("game_id")
        if not isinstance(game_id, str) or not game_id:
            raise TypeError(f"M3_CLOSURE_GAME_ID_INVALID:{label}:{ordinal}")
        _require(
            metadata.get("game_index") == ordinal
            and result.get("game_index") == ordinal,
            f"M3_CLOSURE_GAME_INDEX_INVALID:{label}:{game_id}",
        )
        _require(game_id not in rows, f"M3_CLOSURE_GAME_DUPLICATE:{label}")
        order.append(game_id)
        rows[game_id] = result
    return order, rows


def _audit_full_run(
    run: dict[str, object],
    baseline: dict[str, object],
) -> dict[str, object]:
    expected: dict[str, object] = {
        "active_agent_peak": 1,
        "active_product_path_count": 1,
        "adapter_crash_count": 0,
        "advertised_game_count": 25,
        "completed_game_count": 25,
        "failed_game_count": 0,
        "identity_boundary": "PASS",
        "known_sample_regression_established": True,
        "known_sample_regression_status": "KNOWN_SAMPLE_REGRESSION_COMPLETE",
        "lifecycle_failure_count": 0,
        "offline_environment_available_count": 25,
        "offline_environment_selected_count": 25,
        "operation_mode": "offline",
        "p_j0_m0_runtime_identity_bound": True,
        "per_game_new_memory_count": 0,
        "per_game_new_p_count": 0,
        "product_active_dev_mechanism_family_count": 1,
        "product_endpoint_failure_count": 0,
        "product_game_started_count": 25,
        "product_game_win_count": 25,
        "product_level_completion_count": 183,
        "product_result_count": 25,
        "product_runtime_failure_signature_row_count": 0,
        "runtime_policy_changed": False,
        "scorecard_close_count": 1,
        "scorecard_closed": True,
        "scorecard_lifecycle_leak_count": 0,
        "scorecard_open_count": 1,
        "shared_session_count": 1,
        "started_game_count": 25,
        "state_owner_violation_count": 0,
    }
    mismatches = tuple(key for key, value in expected.items() if run.get(key) != value)
    _require(
        not mismatches,
        "M3_CLOSURE_FULL_RUN_CONTRACT:" + ",".join(mismatches),
    )
    _require(run.get("failures") == [], "M3_CLOSURE_FULL_RUN_FAILURES")
    _require(
        run.get("lifecycle_failures") == [],
        "M3_CLOSURE_FULL_RUN_LIFECYCLE_FAILURES",
    )
    action_count = run.get("product_total_action_count")
    _require(
        isinstance(action_count, int)
        and not isinstance(action_count, bool)
        and action_count > 0,
        "M3_CLOSURE_ACTION_COUNT_INVALID",
    )
    _require(
        run.get("product_hds_plan_commit_count") == action_count
        and run.get("product_executed_plan_count") == action_count,
        "M3_CLOSURE_NON_J_AUTHORIZED_ACTION",
    )
    order, rows = _rows(run, label="M3-P06")
    baseline_order, baseline_rows = _rows(baseline, label="M2-A")
    _require(order == baseline_order, "M3_CLOSURE_OFFICIAL_ORDER_DRIFT")
    functional_mismatches: list[str] = []
    for game_id in order:
        row = rows[game_id]
        baseline_row = baseline_rows[game_id]
        _require(
            row.get("final_state") == "WIN"
            and row.get("stop_reason") == "GOAL_REACHED"
            and row.get("failure_signatures") == [],
            f"M3_CLOSURE_GAME_NOT_COMPLETE:{game_id}",
        )
        _require(
            row.get("hds_plan_commit_count") == row.get("actions_executed")
            and row.get("executed_plan_count") == row.get("actions_executed"),
            f"M3_CLOSURE_GAME_ACTION_AUTHORITY:{game_id}",
        )
        for field in FUNCTIONAL_FIELDS:
            if row.get(field) != baseline_row.get(field):
                functional_mismatches.append(f"{game_id}:{field}")
    _require(
        not functional_mismatches,
        "M3_CLOSURE_FUNCTIONAL_REGRESSION:" + ",".join(functional_mismatches),
    )
    lineage = run.get("session_lineage_digest")
    _require(
        isinstance(lineage, str) and lineage.startswith("cognitive-lineage:"),
        "M3_CLOSURE_SESSION_LINEAGE_INVALID",
    )
    return {
        "fresh_official_game_count": len(order),
        "fresh_game_WIN_count": run["product_game_win_count"],
        "fresh_level_completion_count": run["product_level_completion_count"],
        "fresh_runtime_action_count": action_count,
        "fresh_failure_count": run["failed_game_count"],
        "fresh_lifecycle_failure_count": run["lifecycle_failure_count"],
        "fresh_runtime_failure_signature_count": run[
            "product_runtime_failure_signature_row_count"
        ],
        "all_external_actions_J_authorized": True,
        "all_executed_plans_J_committed": True,
        "functional_field_count_per_game": len(FUNCTIONAL_FIELDS),
        "functional_mismatch_count_vs_M2_A": 0,
        "session_lineage_digest": lineage,
    }


def _verify_test_bindings(root: Path, report: dict[str, object]) -> None:
    for section in (
        "test_file_bindings",
        "implementation_file_bindings",
        "conformance_artifact_bindings",
    ):
        bindings = report.get(section)
        if not isinstance(bindings, list):
            raise TypeError(f"M3_CLOSURE_TEST_BINDINGS_INVALID:{section}")
        for item in bindings:
            if not isinstance(item, dict):
                raise TypeError(f"M3_CLOSURE_TEST_BINDING_INVALID:{section}")
            path = item.get("path")
            claimed = item.get("sha256")
            if not isinstance(path, str) or not isinstance(claimed, str):
                raise TypeError(f"M3_CLOSURE_TEST_BINDING_FIELDS:{section}")
            base = (
                root / "ARC-AGI-3-Agents"
                if section != "conformance_artifact_bindings"
                else root
            )
            _require(
                _sha256((base / path).read_bytes()) == claimed,
                f"M3_CLOSURE_TEST_BINDING_STALE:{path}",
            )


def build_report(root: Path = REPOSITORY_ROOT) -> dict[str, object]:
    full_run, full_run_sha = _load_object(root, FULL_RUN_PATH)
    test_run, test_run_sha = _load_object(root, TEST_RUN_PATH)
    descriptor, descriptor_sha = _load_object(root, ACTIVE_DESCRIPTOR_PATH)
    m2_closure, m2_closure_sha = _load_object(root, M2_CLOSURE_PATH)
    m2_run_a, m2_run_a_sha = _load_object(root, M2_RUN_A_PATH)
    _verify_logical_seal(test_run, label="M3-TESTS")
    _verify_logical_seal(m2_closure, label="M2-CLOSURE")
    _require(test_run.get("status") == "PASS", "M3_CLOSURE_TEST_RUN_FAILED")
    passed_test_count = test_run.get("passed_test_count")
    _require(
        test_run.get("failed_test_count") == 0
        and test_run.get("error_test_count") == 0
        and isinstance(passed_test_count, int)
        and not isinstance(passed_test_count, bool)
        and passed_test_count > 0,
        "M3_CLOSURE_TEST_COUNTS_INVALID",
    )
    _verify_test_bindings(root, test_run)
    conformance: dict[str, dict[str, object]] = {}
    conformance_bindings: dict[str, dict[str, str]] = {}
    for point, path in CONFORMANCE_PATHS.items():
        artifact, artifact_sha = _load_object(root, path)
        _verify_logical_seal(artifact, label=point)
        _require(
            artifact.get("status") == EXPECTED_STATUSES[point],
            f"M3_CLOSURE_CONFORMANCE_STATUS:{point}",
        )
        conformance[point] = artifact
        conformance_bindings[point] = {
            "path": path.as_posix(),
            "sha256": artifact_sha,
        }
    p01 = conformance["M3-P01"]
    p02 = conformance["M3-P02"]
    p03 = conformance["M3-P03"]
    p04 = conformance["M3-P04"]
    p05 = conformance["M3-P05"]
    p01_exit = cast_dict(p01.get("exit_audit"))
    p02_exit = cast_dict(p02.get("exit_audit"))
    p03_summary = cast_dict(p03.get("finding_summary"))
    p04_summary = cast_dict(p04.get("summary"))
    p05_summary = cast_dict(p05.get("summary"))
    _require(
        p01_exit.get("functional_equivalent_leak_count") == 0,
        "M3_CLOSURE_P01_ABLATION_LEAK",
    )
    _require(
        p02_exit.get("relevant_M_addition_changes_decision") is True
        and p02_exit.get("irrelevant_M_action_invariance") is True,
        "M3_CLOSURE_P02_MEMORY_CAUSALITY",
    )
    _require(
        p03_summary.get("identity_action_router_finding_count") == 0
        and p03_summary.get("fixed_trajectory_playback_finding_count") == 0,
        "M3_CLOSURE_P03_IDENTITY_REPLAY",
    )
    _require(
        p04_summary.get("applicability_maintained_when_conditions_hold") is True
        and p04_summary.get("non_applicable_when_condition_breaks") is True,
        "M3_CLOSURE_P04_APPLICABILITY",
    )
    _require(
        p05_summary.get("one_success_release_candidate_count") == 0
        and p05_summary.get("stable_multi_run_candidate_count") == 1
        and p05_summary.get("false_learning_invalidated") is True
        and p05_summary.get("false_learning_rollback_effective") is True
        and p05_summary.get("restart_acquired_capability_causal") is True,
        "M3_CLOSURE_P05_VERSION_LEARNING",
    )
    active_package_payload = (root / ACTIVE_PACKAGE_PATH).read_bytes()
    candidate_package_payload = (root / CANDIDATE_PACKAGE_PATH).read_bytes()
    _require(
        descriptor.get("package_sha256") == _sha256(active_package_payload),
        "M3_CLOSURE_ACTIVE_PACKAGE_DESCRIPTOR_MISMATCH",
    )
    candidate = p05.get("next_version_candidate")
    if not isinstance(candidate, dict):
        raise TypeError("M3_CLOSURE_P05_CANDIDATE_INVALID")
    _require(
        candidate.get("status") == "CANDIDATE_PENDING_M3_P06"
        and candidate.get("activation_performed") is False
        and candidate.get("package_sha256") == _sha256(candidate_package_payload),
        "M3_CLOSURE_P05_CANDIDATE_BOUNDARY",
    )
    _require(
        full_run.get("product_initial_state_logical_digest")
        == descriptor.get("initial_state_logical_digest")
        and full_run.get("product_p_logical_digest")
        == descriptor.get("p_logical_digest")
        and full_run.get("product_j0_digest") == descriptor.get("j0_digest")
        and full_run.get("product_m0_digest") == descriptor.get("m0_digest"),
        "M3_CLOSURE_ACTIVE_BUNDLE_RUN_BINDING",
    )
    _require(
        full_run.get("product_m0_digest") != candidate.get("candidate_M0_digest"),
        "M3_CLOSURE_CANDIDATE_ACTIVATION_LEAK",
    )
    full_run_audit = _audit_full_run(full_run, m2_run_a)
    m2_run_audit = cast_dict(m2_closure.get("run_audit"))
    m2_per_run = cast_dict(m2_run_audit.get("per_run"))
    previous_lineages = {
        str(item.get("session_lineage_digest"))
        for item in m2_per_run.values()
        if isinstance(item, dict)
    }
    _require(
        full_run_audit["session_lineage_digest"] not in previous_lineages,
        "M3_CLOSURE_FRESH_SESSION_REQUIRED",
    )
    report: dict[str, object] = {
        "schema_version": "arc3-rev5-1-m3-conformance-closure-v1",
        "artifact_type": "M3ConformanceClosureEvidence",
        "point_id": "M3-P06_CONFORMANCE_FULL_REGRESSION",
        "runtime_product": "ARC3CompletionAgent",
        "asset_stage": "ACTIVE_DEV",
        "status": "M3_COMPLETE",
        "evidence_bindings": {
            "fresh_full_run": {
                "path": FULL_RUN_PATH.as_posix(),
                "sha256": full_run_sha,
            },
            "focused_conformance_tests": {
                "path": TEST_RUN_PATH.as_posix(),
                "sha256": test_run_sha,
                "passed_test_count": passed_test_count,
            },
            "active_product_descriptor": {
                "path": ACTIVE_DESCRIPTOR_PATH.as_posix(),
                "sha256": descriptor_sha,
            },
            "active_product_package": {
                "path": ACTIVE_PACKAGE_PATH.as_posix(),
                "sha256": _sha256(active_package_payload),
            },
            "inactive_P05_candidate_package": {
                "path": CANDIDATE_PACKAGE_PATH.as_posix(),
                "sha256": _sha256(candidate_package_payload),
            },
            "M2_closure": {
                "path": M2_CLOSURE_PATH.as_posix(),
                "sha256": m2_closure_sha,
            },
            "M2_official_order_baseline": {
                "path": M2_RUN_A_PATH.as_posix(),
                "sha256": m2_run_a_sha,
            },
            "conformance_points": conformance_bindings,
        },
        "conformance_gate_audit": {
            "required_point_count": len(CONFORMANCE_PATHS),
            "passing_point_count": len(CONFORMANCE_PATHS),
            "failed_point_count": 0,
            "focused_test_pass_count": passed_test_count,
            "focused_test_failure_count": 0,
            "C_J_M_P_ablation_passed": True,
            "relevant_M_causality_passed": True,
            "irrelevant_M_invariance_passed": True,
            "identity_action_router_finding_count": 0,
            "fixed_trajectory_playback_finding_count": 0,
            "applicability_counterfactual_passed": True,
            "runtime_version_learning_separation_passed": True,
        },
        "fresh_full_sample_regression": full_run_audit,
        "product_bundle_audit": {
            "active_development_product_bundle_count": 1,
            "active_bundle_unchanged": True,
            "P05_candidate_activation_count": 0,
            "P05_candidate_status": "CANDIDATE_PENDING_M3_P06",
            "runtime_policy_changed_during_P06": False,
        },
        "exit_audit": {
            "all_M3_P01_through_P05_conformance_tests": "PASS",
            "fresh_official_sample_game_WIN_count": 25,
            "fresh_official_sample_level_completion_count": 183,
            "fresh_failure_count": 0,
            "fresh_lifecycle_failure_count": 0,
            "fresh_runtime_failure_signature_count": 0,
            "active_runtime_bundle_unchanged": True,
            "P05_candidate_activation_count": 0,
            "active_development_product_bundle_count": 1,
            "status": "M3_COMPLETE",
        },
        "claim_boundary": {
            "allowed_claim": "M3_GENERIC_AGI_CONFORMANCE_COMPLETE",
            "M3_complete": True,
            "product_release_frozen": False,
            "ARC3_PRODUCT_COMPLETE": False,
            "next_point": "M4-P01_RELEASE_BUNDLE_COMPILATION",
        },
    }
    report["logical_content_sha256"] = _sha256(_canonical_json(report))
    return report


def cast_dict(value: object) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError("M3_CLOSURE_MAPPING_REQUIRED")
    return value


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=REPOSITORY_ROOT)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    report = build_report(root)
    expected = _encoded(report)
    path = root / OUTPUT_PATH
    if arguments.write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(expected)
        status = "WRITTEN"
        success = True
    else:
        success = path.is_file() and path.read_bytes() == expected
        status = "PASS" if success else "STALE"
    print(
        json.dumps(
            {
                "output": OUTPUT_PATH.as_posix(),
                "point_status": report["status"],
                "status": status,
            },
            sort_keys=True,
        )
    )
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
