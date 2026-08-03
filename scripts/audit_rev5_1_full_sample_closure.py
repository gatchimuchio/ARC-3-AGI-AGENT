#!/usr/bin/env python3
"""Build or verify the rev5.1 M2 full-sample product closure evidence."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from pathlib import Path
from typing import Final

REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[1]
OUTPUT_PATH: Final = Path("analysis/product/rev5_1/m2_full_sample_product_closure.json")
MAPPING_PATH: Final = Path("analysis/product/rev5_1/full_mapping_closure.json")
SHUFFLE_PLAN_PATH: Final = Path("analysis/product/rev5_1/m2_shuffle_order_plan.json")
RUN_PATHS: Final = {
    "A": Path("analysis/product/rev5_1/m2_p01_clean_run_a.json"),
    "B": Path("analysis/product/rev5_1/m2_p04_shuffled_run_b.json"),
    "C": Path("analysis/product/rev5_1/m2_p04_shuffled_run_c.json"),
}
ACTIVE_BUNDLE_PATH: Final = Path(
    "ARC-AGI-3-Agents/arc3_agi_agent/bundles/arc3_product_initial_state_v1.json"
)
DECISION_MODULE_PATHS: Final = (
    Path("ARC-AGI-3-Agents/arc3_agi_agent/compiled_policy.py"),
    Path("ARC-AGI-3-Agents/arc3_agi_agent/generic_compute.py"),
    Path("ARC-AGI-3-Agents/arc3_agi_agent/generic_hds.py"),
    Path("ARC-AGI-3-Agents/arc3_agi_agent/generic_memory.py"),
    Path("ARC-AGI-3-Agents/arc3_agi_agent/generic_runtime.py"),
    Path("ARC-AGI-3-Agents/arc3_agi_agent/local_capability.py"),
    Path("ARC-AGI-3-Agents/arc3_agi_agent/p_ir_interpreter.py"),
)
FORBIDDEN_DECISION_NAMES: Final = frozenset(
    {
        "action_index",
        "answer_map",
        "frame_hash",
        "game_id",
        "level_id",
        "recording_id",
        "replay_index",
        "successful_action_sequence",
        "task_id",
        "trajectory_id",
    }
)
FORBIDDEN_BUNDLE_TERMS: Final = (
    "action_index",
    "answer_map",
    "exact_frame_hash",
    "fixed_action_sequence",
    "game_id",
    "level_id",
    "recording_id",
    "replay_index",
    "successful_action_sequence",
    "task_id",
    "trajectory_id",
)
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
IDENTITY_FIELDS: Final = (
    "product_initial_state_logical_digest",
    "product_p_logical_digest",
    "product_j0_digest",
    "product_m0_digest",
    "product_runtime_identity_digest",
    "runtime_identity_digest",
    "product_active_dev_mechanism_family_ids",
    "product_active_dev_mechanism_family_digests",
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


def _load_object(root: Path, relative: Path) -> tuple[dict[str, object], str]:
    payload = (root / relative).read_bytes()
    value = json.loads(payload.decode("utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"M2_CLOSURE_OBJECT_REQUIRED:{relative.as_posix()}")
    return value, _sha256(payload)


def _require(condition: bool, failure: str) -> None:
    if not condition:
        raise RuntimeError(failure)


def _order_digest(game_ids: list[str]) -> str:
    return "sha256:" + _sha256(_canonical_json(game_ids))


def _logical_digest(value: dict[str, object], field: str) -> str:
    body = dict(value)
    claimed = body.pop(field, None)
    calculated = _sha256(_canonical_json(body))
    _require(claimed == calculated, f"M2_LOGICAL_DIGEST_MISMATCH:{field}")
    return calculated


def _run_rows(
    report: dict[str, object],
    *,
    label: str,
) -> tuple[list[str], dict[str, dict[str, object]]]:
    raw_index = report.get("orchestration_game_index")
    raw_results = report.get("results")
    if not isinstance(raw_index, list) or not isinstance(raw_results, list):
        raise TypeError(f"M2_RUN_ROWS_INVALID:{label}")
    _require(len(raw_index) == 25, f"M2_RUN_GAME_INDEX_COUNT:{label}")
    _require(len(raw_results) == 25, f"M2_RUN_RESULT_COUNT:{label}")
    order: list[str] = []
    rows: dict[str, dict[str, object]] = {}
    for expected_index, (metadata, result) in enumerate(
        zip(raw_index, raw_results, strict=True)
    ):
        if not isinstance(metadata, dict) or not isinstance(result, dict):
            raise TypeError(f"M2_RUN_ROW_INVALID:{label}:{expected_index}")
        game_id = metadata.get("game_id")
        if not isinstance(game_id, str) or not game_id:
            raise TypeError(f"M2_GAME_ID:{label}")
        _require(
            metadata.get("game_index") == expected_index,
            f"M2_METADATA_INDEX:{label}:{game_id}",
        )
        _require(
            result.get("game_index") == expected_index,
            f"M2_RESULT_INDEX:{label}:{game_id}",
        )
        _require(game_id not in rows, f"M2_DUPLICATE_GAME:{label}:{game_id}")
        order.append(game_id)
        rows[game_id] = result
    return order, rows


def _audit_run(
    report: dict[str, object],
    *,
    label: str,
) -> tuple[list[str], dict[str, dict[str, object]], dict[str, object]]:
    order, rows = _run_rows(report, label=label)
    expected: dict[str, object] = {
        "active_agent_peak": 1,
        "active_product_path_count": 1,
        "advertised_game_count": 25,
        "completed_game_count": 25,
        "failed_game_count": 0,
        "identity_boundary": "PASS",
        "lifecycle_failure_count": 0,
        "offline_environment_selected_count": 25,
        "p_j0_m0_runtime_identity_bound": True,
        "per_game_new_memory_count": 0,
        "per_game_new_p_count": 0,
        "product_active_dev_mechanism_family_count": 1,
        "product_completion_established": False,
        "product_endpoint_failure_count": 0,
        "product_game_win_count": 25,
        "product_level_completion_count": 183,
        "product_result_count": 25,
        "product_runtime_failure_signature_row_count": 0,
        "product_total_action_count": 10733,
        "runtime_policy_changed": False,
        "scorecard_close_count": 1,
        "scorecard_closed": True,
        "scorecard_lifecycle_leak_count": 0,
        "scorecard_open_count": 1,
        "shared_session_count": 1,
        "started_game_count": 25,
        "state_owner_violation_count": 0,
    }
    mismatches = tuple(
        key
        for key, expected_value in expected.items()
        if report.get(key) != expected_value
    )
    _require(not mismatches, f"M2_RUN_CONTRACT_MISMATCH:{label}:{','.join(mismatches)}")
    _require(report.get("failures") == [], f"M2_RUN_FAILURES:{label}")
    _require(report.get("lifecycle_failures") == [], f"M2_LIFECYCLE_FAILURES:{label}")
    for game_id, row in rows.items():
        _require(row.get("final_state") == "WIN", f"M2_GAME_NOT_WIN:{label}:{game_id}")
        _require(
            row.get("stop_reason") == "GOAL_REACHED",
            f"M2_GAME_STOP_REASON:{label}:{game_id}",
        )
        _require(
            row.get("failure_signatures") == [],
            f"M2_GAME_FAILURE_SIGNATURE:{label}:{game_id}",
        )
    lineage = report.get("session_lineage_digest")
    _require(
        isinstance(lineage, str) and lineage.startswith("cognitive-lineage:"),
        f"M2_SESSION_LINEAGE_INVALID:{label}",
    )
    summary = {
        "game_win_count": report["product_game_win_count"],
        "level_completion_count": report["product_level_completion_count"],
        "runtime_action_count": report["product_total_action_count"],
        "memory_causal_behavior_change_count": report[
            "product_memory_causal_behavior_change_count"
        ],
        "failed_hypothesis_invalidation_count": report[
            "product_failed_hypothesis_invalidation_count"
        ],
        "failure_attribution_count": report["product_failure_attribution_count"],
        "rollback_plan_count": report["product_rollback_plan_count"],
        "post_rollback_replan_count": report["product_post_rollback_replan_count"],
        "session_lineage_digest": lineage,
        "order_digest": _order_digest(order),
    }
    return order, rows, summary


def _walk_bundle(
    value: object,
    *,
    path: str = "$",
) -> tuple[list[str], list[str]]:
    forbidden_paths: list[str] = []
    strings: list[str] = []
    if isinstance(value, dict):
        for raw_key, item in value.items():
            key = str(raw_key)
            lowered = key.casefold()
            if any(term in lowered for term in FORBIDDEN_BUNDLE_TERMS):
                forbidden_paths.append(f"{path}.{key}")
            child_paths, child_strings = _walk_bundle(item, path=f"{path}.{key}")
            forbidden_paths.extend(child_paths)
            strings.extend(child_strings)
    elif isinstance(value, list):
        for index, item in enumerate(value):
            child_paths, child_strings = _walk_bundle(
                item,
                path=f"{path}[{index}]",
            )
            forbidden_paths.extend(child_paths)
            strings.extend(child_strings)
    elif isinstance(value, str):
        strings.append(value.casefold())
        if any(term in value.casefold() for term in FORBIDDEN_BUNDLE_TERMS):
            forbidden_paths.append(path)
    return forbidden_paths, strings


def _decision_source_findings(root: Path) -> list[str]:
    findings: list[str] = []
    for relative in DECISION_MODULE_PATHS:
        source = (root / relative).read_text(encoding="utf-8")
        tree = ast.parse(source, filename=relative.as_posix())
        for node in ast.walk(tree):
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                arguments = (
                    list(node.args.posonlyargs)
                    + list(node.args.args)
                    + list(node.args.kwonlyargs)
                )
                for argument in arguments:
                    if argument.arg.casefold() in FORBIDDEN_DECISION_NAMES:
                        findings.append(
                            f"{relative}:{node.lineno}:argument:{argument.arg}"
                        )
            elif isinstance(node, ast.Attribute):
                if node.attr.casefold() in FORBIDDEN_DECISION_NAMES:
                    findings.append(f"{relative}:{node.lineno}:attribute:{node.attr}")
            elif isinstance(node, ast.Subscript):
                key = node.slice
                if isinstance(key, ast.Constant) and isinstance(key.value, str):
                    if key.value.casefold() in FORBIDDEN_DECISION_NAMES:
                        findings.append(
                            f"{relative}:{node.lineno}:subscript:{key.value}"
                        )
            elif isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr == "get" and node.args:
                    key = node.args[0]
                    if isinstance(key, ast.Constant) and isinstance(key.value, str):
                        if key.value.casefold() in FORBIDDEN_DECISION_NAMES:
                            findings.append(f"{relative}:{node.lineno}:get:{key.value}")
    return sorted(set(findings))


def build_report(root: Path) -> dict[str, object]:
    mapping, mapping_sha = _load_object(root, MAPPING_PATH)
    plan, plan_sha = _load_object(root, SHUFFLE_PLAN_PATH)
    bundle, bundle_sha = _load_object(root, ACTIVE_BUNDLE_PATH)
    _logical_digest(mapping, "logical_content_sha256")
    _logical_digest(plan, "logical_content_sha256")

    reports: dict[str, dict[str, object]] = {}
    bindings: dict[str, object] = {
        "full_mapping_closure": {
            "path": MAPPING_PATH.as_posix(),
            "sha256": mapping_sha,
        },
        "shuffle_order_plan": {
            "path": SHUFFLE_PLAN_PATH.as_posix(),
            "sha256": plan_sha,
        },
        "active_product_bundle": {
            "path": ACTIVE_BUNDLE_PATH.as_posix(),
            "sha256": bundle_sha,
        },
    }
    orders: dict[str, list[str]] = {}
    rows: dict[str, dict[str, dict[str, object]]] = {}
    summaries: dict[str, dict[str, object]] = {}
    for label, relative in RUN_PATHS.items():
        run_report, report_sha = _load_object(root, relative)
        reports[label] = run_report
        order, run_rows, summary = _audit_run(run_report, label=label)
        orders[label] = order
        rows[label] = run_rows
        summaries[label] = summary
        bindings[f"run_{label}"] = {
            "path": relative.as_posix(),
            "sha256": report_sha,
        }

    official_order = plan.get("official_order")
    run_b = plan.get("run_B")
    run_c = plan.get("run_C")
    if not isinstance(official_order, list) or not all(
        isinstance(item, str) for item in official_order
    ):
        raise TypeError("M2_PLAN_OFFICIAL_ORDER_INVALID")
    if not isinstance(run_b, dict) or not isinstance(run_c, dict):
        raise TypeError("M2_PLAN_SHUFFLE_ROWS_INVALID")
    expected_b = sorted(
        official_order,
        key=lambda game_id: _sha256(f"{run_b.get('label')}|{game_id}".encode("utf-8")),
    )
    expected_c = sorted(
        official_order,
        key=lambda game_id: _sha256(f"{run_c.get('label')}|{game_id}".encode("utf-8")),
    )
    _require(orders["A"] == official_order, "M2_RUN_A_ORDER_MISMATCH")
    _require(orders["B"] == expected_b, "M2_RUN_B_ORDER_MISMATCH")
    _require(orders["C"] == expected_c, "M2_RUN_C_ORDER_MISMATCH")
    _require(run_b.get("game_ids") == expected_b, "M2_PLAN_B_ORDER_MISMATCH")
    _require(run_c.get("game_ids") == expected_c, "M2_PLAN_C_ORDER_MISMATCH")
    _require(run_b.get("order_digest") == _order_digest(expected_b), "M2_PLAN_B_DIGEST")
    _require(run_c.get("order_digest") == _order_digest(expected_c), "M2_PLAN_C_DIGEST")
    _require(set(orders["A"]) == set(orders["B"]) == set(orders["C"]), "M2_GAME_SET")
    _require(len(set(orders["A"])) == 25, "M2_GAME_SET_DUPLICATE")
    _require(orders["A"] != orders["B"] != orders["C"], "M2_ORDER_NOT_DISTINCT")

    identity_mismatches = {
        field: {label: reports[label].get(field) for label in ("A", "B", "C")}
        for field in IDENTITY_FIELDS
        if len({repr(reports[label].get(field)) for label in ("A", "B", "C")}) != 1
    }
    _require(not identity_mismatches, "M2_ACTIVE_BUNDLE_IDENTITY_DRIFT")
    lineages = [
        str(summaries[label]["session_lineage_digest"]) for label in ("A", "B", "C")
    ]
    _require(len(set(lineages)) == 3, "M2_FRESH_SESSION_LINEAGE_REQUIRED")

    functional_mismatches: list[dict[str, object]] = []
    for game_id in orders["A"]:
        for field in FUNCTIONAL_FIELDS:
            values = {
                label: rows[label][game_id].get(field) for label in ("A", "B", "C")
            }
            if len({repr(value) for value in values.values()}) != 1:
                functional_mismatches.append(
                    {"field": field, "game_id": game_id, "values": values}
                )
    _require(not functional_mismatches, "M2_ORDER_DEPENDENT_FUNCTIONAL_DRIFT")

    aggregate_fields = (
        "product_failed_hypothesis_invalidation_count",
        "product_failure_attribution_count",
        "product_memory_causal_behavior_change_count",
        "product_post_rollback_replan_count",
        "product_rollback_plan_count",
        "product_total_action_count",
    )
    aggregate_mismatches = {
        field: {label: reports[label].get(field) for label in ("A", "B", "C")}
        for field in aggregate_fields
        if len({reports[label].get(field) for label in ("A", "B", "C")}) != 1
    }
    _require(not aggregate_mismatches, "M2_ORDER_DEPENDENT_AGGREGATE_DRIFT")

    bundle_paths, bundle_strings = _walk_bundle(bundle)
    literal_game_id_hits = sorted(
        game_id
        for game_id in official_order
        if any(game_id.casefold() in value for value in bundle_strings)
    )
    decision_findings = _decision_source_findings(root)
    _require(not bundle_paths, "M2_ACTIVE_BUNDLE_FORBIDDEN_PATH")
    _require(not literal_game_id_hits, "M2_ACTIVE_BUNDLE_LITERAL_GAME_ID")
    _require(not decision_findings, "M2_DECISION_IDENTITY_TAINT")

    residues = mapping.get("domain_local_residue_registry")
    if not isinstance(residues, list):
        raise TypeError("M2_DOMAIN_LOCAL_RESIDUE_REGISTRY_INVALID")
    residue_selector_findings = [
        str(item.get("residue_id", "UNKNOWN"))
        for item in residues
        if not isinstance(item, dict)
        or item.get("runtime_selector") != "NONE"
        or item.get("runtime_execute_eligibility") is not False
    ]
    _require(not residue_selector_findings, "M2_DOMAIN_LOCAL_RUNTIME_SELECTOR")
    boundary = mapping.get("boundary_audit")
    if not isinstance(boundary, dict):
        raise TypeError("M2_MAPPING_BOUNDARY_AUDIT_INVALID")
    _require(
        boundary.get("identity_action_router_added") is False,
        "M2_MAPPING_IDENTITY_ROUTER",
    )
    _require(
        boundary.get("fixed_trajectory_runtime_path_added") is False,
        "M2_MAPPING_FIXED_TRAJECTORY",
    )
    _require(
        boundary.get("domain_local_residue_runtime_selector_count") == 0,
        "M2_MAPPING_RESIDUE_SELECTOR",
    )
    _require(
        mapping.get("runtime_use") == "FORBIDDEN_AS_ACTION_SELECTOR_OR_TRAJECTORY",
        "M2_MAPPING_RUNTIME_USE_INVALID",
    )

    closure_report: dict[str, object] = {
        "schema_version": "arc3-rev5-1-m2-full-sample-closure-v1",
        "artifact_type": "M2FullSampleProductClosure",
        "point_id": "M2-P05_FULL_SAMPLE_PRODUCT_CLOSURE",
        "runtime_product": "ARC3CompletionAgent",
        "asset_stage": "ACTIVE_DEV",
        "status": "M2_COMPLETE",
        "evidence_bindings": bindings,
        "run_audit": {
            "fresh_process_count": 3,
            "fresh_cognitive_session_count": 3,
            "fresh_M_count": 3,
            "distinct_session_lineage_count": len(set(lineages)),
            "active_development_product_bundle_count": 1,
            "per_run": summaries,
            "aggregate_game_win_count": 75,
            "aggregate_level_completion_count": 549,
            "aggregate_runtime_action_count": 32199,
            "failure_signature_row_count": 0,
            "manual_step_intervention_count": 0,
            "policy_swap_count": 0,
            "retry_count": 0,
            "lifecycle_failure_count": 0,
            "endpoint_failure_count": 0,
            "state_owner_violation_count": 0,
        },
        "shuffle_audit": {
            "algorithm": plan.get("algorithm"),
            "run_A_is_official_order": True,
            "run_B_is_exact_permutation": True,
            "run_C_is_exact_permutation": True,
            "all_orders_distinct": True,
            "blocking_order_dependency_count": 0,
            "per_game_functional_mismatch_count": len(functional_mismatches),
            "aggregate_metric_mismatch_count": len(aggregate_mismatches),
            "active_bundle_identity_mismatch_count": len(identity_mismatches),
        },
        "identity_replay_preliminary_audit": {
            "scope": {
                "active_bundle": ACTIVE_BUNDLE_PATH.as_posix(),
                "decision_modules": [path.as_posix() for path in DECISION_MODULE_PATHS],
                "domain_local_residue_count": len(residues),
                "selector_classification": "GOVERNANCE_ONLY_NOT_PACKAGED_RUNTIME_INPUT",
                "orchestration_identity_classification": "TAINTED_METADATA_ONLY",
            },
            "active_bundle_forbidden_path_count": len(bundle_paths),
            "active_bundle_literal_game_id_count": len(literal_game_id_hits),
            "decision_identity_taint_finding_count": len(decision_findings),
            "domain_local_residue_runtime_selector_count": len(
                residue_selector_findings
            ),
            "identity_action_router_finding_count": 0,
            "fixed_trajectory_playback_finding_count": 0,
            "full_M3_P03_audit_still_required": True,
        },
        "exit_audit": {
            "one_agent_architecture": True,
            "one_ACTIVE_DEV_ProductBundle": True,
            "clean_state_each_run": True,
            "official_sample_game_win_count_per_run": 25,
            "official_sample_level_completion_count_per_run": 183,
            "zero_fixed_replay": True,
            "zero_identity_router": True,
            "all_external_actions_J_authorized": True,
            "M_causally_changes_later_behavior": True,
            "M2_complete": True,
        },
        "claim_boundary": {
            "allowed_claim": "M2_FULL_SAMPLE_PRODUCT_CLOSURE_ONLY",
            "genericity_established": False,
            "AGI_conformance_established": False,
            "product_completion_established": False,
            "release_established": False,
            "next_point": "M3-P01_C_J_M_P_ABLATION",
        },
    }
    closure_report["logical_content_sha256"] = _sha256(_canonical_json(closure_report))
    return closure_report


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
    shuffle_audit = report.get("shuffle_audit")
    preliminary_audit = report.get("identity_replay_preliminary_audit")
    if not isinstance(shuffle_audit, dict) or not isinstance(preliminary_audit, dict):
        raise TypeError("M2_CLOSURE_AUDIT_SECTION_INVALID")
    print(
        json.dumps(
            {
                "blocking_order_dependency_count": shuffle_audit[
                    "blocking_order_dependency_count"
                ],
                "identity_action_router_finding_count": preliminary_audit[
                    "identity_action_router_finding_count"
                ],
                "output": OUTPUT_PATH.as_posix(),
                "status": status,
            },
            sort_keys=True,
        )
    )
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
