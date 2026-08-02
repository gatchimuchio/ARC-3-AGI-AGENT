#!/usr/bin/env python3
"""Fail closed when rev4 product authority and endpoint code diverge."""

from __future__ import annotations

import ast
import hashlib
import json
from pathlib import Path
from typing import Any, Final

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
CURRENT_TASK_PATH: Final = Path("control/rev4/CURRENT_TASK.json")
CONTRACT_PATH: Final = Path(
    "docs/strategy/contracts/REV4_PRODUCT_GOVERNANCE_CONTRACT_V1.json"
)
CLASSIFICATION_PATH: Final = Path("control/rev4/LEGACY_REV3_CLASSIFICATION.json")
MANIFEST_PATH: Final = Path("docs/strategy/REV4_CURRENT_AUTHORITY_MANIFEST.json")
RESOURCE_BOUNDS_PATH: Final = Path("analysis/product/rev4/product_resource_bounds.json")
BASELINE_PATH: Final = Path("analysis/product/rev4/current_product_baseline.json")
M1_RUNTIME_SURFACE_PATH: Final = Path(
    "analysis/product/rev4/m1_official_runtime_surface.json"
)
M2_PRODUCT_CAPABILITY_PATH: Final = Path(
    "analysis/product/rev4/m2_product_capability_bundle.json"
)
M2_PRODUCT_DESCRIPTOR_PATH: Final = Path(
    "ARC-AGI-3-Agents/arc3_agi_agent/bundles/arc3_product_initial_state_v1.json"
)
M2_PRODUCT_PACKAGE_PATH: Final = Path(
    "ARC-AGI-3-Agents/arc3_agi_agent/bundles/arc3_product_initial_state_v1.zip"
)
M4_PRODUCT_PATH: Final = Path("analysis/product/rev4/m4_full_sample_product.json")
M5_CLEAN_PRODUCT_PATH: Final = Path(
    "analysis/product/rev4/m5_clean_install_product.json"
)
M5_RELEASE_PATH: Final = Path("analysis/product/rev4/m5_product_release.json")
COMPLETION_AUDIT_PATH: Final = Path(
    "analysis/product/rev4/product_completion_audit.json"
)
M3_TRANSFORMATION_PATH: Final = Path(
    "analysis/product/rev4/m3_active_product_transformation.json"
)
NOTEBOOK_VALIDATION_PATH: Final = Path(
    "analysis/official/KAGGLE_NOTEBOOK_VALIDATION.json"
)
RELEASE_MANIFEST_PATH: Final = Path("release/ARC3CompletionAgent-v1.0/MANIFEST.json")
RELEASE_WHEEL_PATH: Final = Path(
    "release/ARC3CompletionAgent-v1.0/arc3_completion_agent-1.0.0-py3-none-any.whl"
)
RELEASE_SUMS_PATH: Final = Path("release/ARC3CompletionAgent-v1.0/SHA256SUMS")
RELEASE_DEPENDENCY_LOCK_PATH: Final = Path(
    "release/ARC3CompletionAgent-v1.0/requirements-lock.txt"
)
PRODUCT_GOVERNANCE_PATH: Final = Path(
    "ARC-AGI-3-Agents/arc3_agi_agent/product_governance.py"
)
PRODUCT_RUNNER_PATH: Final = Path("ARC-AGI-3-Agents/arc3_agi_agent/product_runner.py")
PRODUCT_ENTRYPOINT_PATH: Final = Path(
    "ARC-AGI-3-Agents/agents/templates/arc3_completion_agent.py"
)
GENERIC_RUNNER_PATH: Final = Path(
    "ARC-AGI-3-Agents/arc3_agi_agent/generic_competition_runner.py"
)
REV3_GOVERNANCE_PATH: Final = Path("ARC-AGI-3-Agents/arc3_agi_agent/rev3_governance.py")
PRODUCT_ID: Final = "ARC3_COMPLETION_AGI_AGENT_PRODUCT_REV4"
PRODUCT_NAME: Final = "ARC3CompletionAgent"
ACTIVE_MILESTONE: Final = "M3_INTEGRATED_AGI_CAPABILITY"


def _load_object(root: Path, relative: Path) -> dict[str, Any]:
    value = json.loads((root / relative).read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"OBJECT_REQUIRED:{relative.as_posix()}")
    return value


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _literal_constants(path: Path) -> dict[str, object]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    values: dict[str, object] = {}
    for node in tree.body:
        target: ast.expr | None = None
        value: ast.expr | None = None
        if isinstance(node, ast.AnnAssign):
            target = node.target
            value = node.value
        elif isinstance(node, ast.Assign) and len(node.targets) == 1:
            target = node.targets[0]
            value = node.value
        if not isinstance(target, ast.Name) or value is None:
            continue
        try:
            values[target.id] = ast.literal_eval(value)
        except (ValueError, TypeError):
            continue
    return values


def validate_repository(root: Path) -> dict[str, object]:
    failures: list[str] = []
    check_count = 0

    def check(condition: bool, failure: str) -> None:
        nonlocal check_count
        check_count += 1
        if not condition:
            failures.append(failure)

    current = _load_object(root, CURRENT_TASK_PATH)
    contract = _load_object(root, CONTRACT_PATH)
    classification = _load_object(root, CLASSIFICATION_PATH)
    manifest = _load_object(root, MANIFEST_PATH)
    resource_bounds = _load_object(root, RESOURCE_BOUNDS_PATH)
    m1_runtime_surface = _load_object(root, M1_RUNTIME_SURFACE_PATH)
    m2_product_capability = _load_object(root, M2_PRODUCT_CAPABILITY_PATH)
    m2_product_descriptor = _load_object(root, M2_PRODUCT_DESCRIPTOR_PATH)
    m4_product = _load_object(root, M4_PRODUCT_PATH)
    m5_clean_product = _load_object(root, M5_CLEAN_PRODUCT_PATH)
    m5_release = _load_object(root, M5_RELEASE_PATH)
    completion_audit = _load_object(root, COMPLETION_AUDIT_PATH)
    m3_transformation = _load_object(root, M3_TRANSFORMATION_PATH)
    notebook_validation = _load_object(root, NOTEBOOK_VALIDATION_PATH)
    release_manifest = _load_object(root, RELEASE_MANIFEST_PATH)

    check(
        current.get("schema_version") == "arc3-product-current-task-v2",
        "current_task:SCHEMA_VERSION_MISMATCH",
    )
    check(current.get("product_id") == PRODUCT_ID, "current_task:PRODUCT_ID")
    check(
        current.get("product_name") == PRODUCT_NAME,
        "current_task:PRODUCT_NAME",
    )
    check(
        current.get("active_milestone") == ACTIVE_MILESTONE,
        "current_task:ACTIVE_MILESTONE",
    )
    check(
        current.get("product_status") == "M3_GENERICITY_REOPENED",
        "current_task:PRODUCT_STATUS",
    )
    check(
        current.get("current_work_class")
        == "ACTIVE_PRODUCT_GENERICITY_AND_LOCKED_EVALUATION_REPAIR",
        "current_task:WORK_CLASS",
    )
    check(
        contract.get("active_milestone") == ACTIVE_MILESTONE,
        "contract:ACTIVE_MILESTONE",
    )
    exit_conditions = current.get("exit_conditions")
    expected_exit_conditions: dict[str, object] = {
        "known_sample_regression_complete": True,
        "local_package_regression_complete": True,
        "m3_active_product_transformation_complete": True,
        "m3_same_active_artifact_genericity_complete": False,
        "active_artifact_locked_evaluator_complete": False,
        "external_kaggle_normal_run_complete": False,
        "official_full_complete": False,
        "product_released": False,
        "status": "M3_GENERICITY_REOPENED",
    }
    check(isinstance(exit_conditions, dict), "current_task:EXIT_CONDITIONS_MISSING")
    if isinstance(exit_conditions, dict):
        for key, expected in expected_exit_conditions.items():
            check(
                exit_conditions.get(key) == expected,
                f"current_task:EXIT_{key.upper()}_MISMATCH",
            )
    check(
        manifest.get("active_milestone") == ACTIVE_MILESTONE,
        "authority_manifest:ACTIVE_MILESTONE",
    )
    check(
        current.get("current_validator")
        == "scripts/validate_rev4_product_governance.py",
        "current_task:VALIDATOR_PATH",
    )
    check(
        current.get("governance_contract") == CONTRACT_PATH.as_posix(),
        "current_task:CONTRACT_PATH",
    )

    endpoint = current.get("endpoint")
    check(isinstance(endpoint, dict), "current_task:ENDPOINT_MISSING")
    if isinstance(endpoint, dict):
        check(
            endpoint.get("official_sample_game_target") == 25,
            "current_task:GAME_TARGET",
        )
        check(
            endpoint.get("official_sample_level_target") == 183,
            "current_task:LEVEL_TARGET",
        )
        check(
            endpoint.get("required_final_state") == "WIN",
            "current_task:FINAL_STATE",
        )
        check(
            endpoint.get("manual_step_intervention_allowed") is False,
            "current_task:MANUAL_INTERVENTION_ENABLED",
        )
        check(
            endpoint.get("fixed_trajectory_playback_allowed") is False,
            "current_task:FIXED_PLAYBACK_ENABLED",
        )
    official_contract = current.get("verified_official_contract")
    check(
        isinstance(official_contract, dict),
        "current_task:OFFICIAL_CONTRACT_MISSING",
    )
    if isinstance(official_contract, dict):
        check(
            official_contract.get("frame_list_semantics")
            == ("TEMPORAL_CAMERA_RENDERS_WITH_FINAL_ACTION_COMPLETE_COMPOSITE"),
            "current_task:FRAME_LIST_SEMANTICS",
        )

    check(contract.get("product_id") == PRODUCT_ID, "contract:PRODUCT_ID")
    check(
        contract.get("current_selector_path") == CURRENT_TASK_PATH.as_posix(),
        "contract:SELECTOR_PATH",
    )
    check(
        contract.get("current_validator_path")
        == "scripts/validate_rev4_product_governance.py",
        "contract:VALIDATOR_PATH",
    )
    check(
        contract.get("authority_manifest_path") == MANIFEST_PATH.as_posix(),
        "contract:MANIFEST_PATH",
    )
    expected_authority_order = [
        "OWNER_CURRENT_EXPLICIT_INSTRUCTION",
        "AGI_TRINITY_ARCHITECTURE",
        "HDS_INTERNAL_SPECIFICATION",
        "ENGINEERING_AGI_SPECIFICATION",
        "ARC3_PRODUCT_SPECIFICATION_REV4",
        "ARC3_PRODUCT_ROADMAP_REV4",
        "REV4_CURRENT_TASK",
    ]
    check(
        contract.get("authority_order") == expected_authority_order,
        "contract:AUTHORITY_ORDER",
    )
    contract_endpoint = contract.get("endpoint")
    check(isinstance(contract_endpoint, dict), "contract:ENDPOINT_MISSING")
    if isinstance(contract_endpoint, dict):
        check(
            contract_endpoint.get("official_sample_game_target") == 25,
            "contract:GAME_TARGET",
        )
        check(
            contract_endpoint.get("official_sample_level_target") == 183,
            "contract:LEVEL_TARGET",
        )
        check(
            contract_endpoint.get("product_action_budget_per_game") == 4096,
            "contract:ACTION_BUDGET",
        )
        check(
            contract_endpoint.get("known_success_action_ceiling") == 1519,
            "contract:KNOWN_SUCCESS_CEILING",
        )
        check(
            contract_endpoint.get("known_success_no_progress_ceiling") == 644,
            "contract:KNOWN_NO_PROGRESS_CEILING",
        )
        check(
            contract_endpoint.get("product_no_progress_limit") == 650,
            "contract:NO_PROGRESS_LIMIT",
        )
    selector_invariants = contract.get("current_selector_invariants")
    expected_selector_invariants: dict[str, object] = {
        "current_selector_count": 1,
        "legacy_rev3_is_current": False,
        "legacy_rev3_runtime_activation_eligible": False,
        "product_completion_requires_measured_endpoint": True,
        "external_kaggle_write_requires_current_owner_authorization": True,
    }
    check(
        isinstance(selector_invariants, dict),
        "contract:SELECTOR_INVARIANTS_MISSING",
    )
    if isinstance(selector_invariants, dict):
        for key, expected in expected_selector_invariants.items():
            check(
                selector_invariants.get(key) == expected,
                f"contract:{key.upper()}_MISMATCH",
            )

    resource_body = dict(resource_bounds)
    resource_digest = resource_body.pop("content_digest", None)
    calculated_resource_digest = (
        "arc3-product-resource-bounds:"
        + hashlib.sha256(_canonical_json(resource_body).encode("utf-8")).hexdigest()
    )
    check(
        resource_digest == calculated_resource_digest,
        "resource_bounds:CONTENT_DIGEST_MISMATCH",
    )
    check(
        resource_bounds.get("schema_version") == "arc3-product-resource-bounds-v1",
        "resource_bounds:SCHEMA_VERSION",
    )
    check(
        resource_bounds.get("product_id") == PRODUCT_NAME,
        "resource_bounds:PRODUCT_ID",
    )
    check(
        resource_bounds.get("game_count") == 25,
        "resource_bounds:GAME_COUNT",
    )
    check(
        resource_bounds.get("level_count") == 183,
        "resource_bounds:LEVEL_COUNT",
    )
    check(
        resource_bounds.get("known_success_action_ceiling") == 1519,
        "resource_bounds:ACTION_CEILING",
    )
    check(
        resource_bounds.get("known_success_no_progress_ceiling") == 644,
        "resource_bounds:NO_PROGRESS_CEILING",
    )
    check(
        resource_bounds.get("recommended_no_progress_limit") == 650,
        "resource_bounds:NO_PROGRESS_LIMIT",
    )
    teacher_manifest_path = resource_bounds.get("source_manifest_path")
    check(
        teacher_manifest_path
        == "distillation/artifacts/teacher/arc3/ph_d05_v1/manifest.json",
        "resource_bounds:SOURCE_MANIFEST_PATH",
    )
    if isinstance(teacher_manifest_path, str):
        teacher_manifest = root / teacher_manifest_path
        check(teacher_manifest.is_file(), "resource_bounds:SOURCE_MANIFEST_MISSING")
        if teacher_manifest.is_file():
            check(
                hashlib.sha256(teacher_manifest.read_bytes()).hexdigest()
                == resource_bounds.get("source_manifest_sha256"),
                "resource_bounds:SOURCE_MANIFEST_SHA256",
            )
    resource_games = resource_bounds.get("games")
    check(isinstance(resource_games, list), "resource_bounds:GAMES_MISSING")
    if isinstance(resource_games, list):
        game_ids = [
            item.get("game_id") for item in resource_games if isinstance(item, dict)
        ]
        check(len(resource_games) == 25, "resource_bounds:GAME_ROWS")
        check(len(game_ids) == 25, "resource_bounds:GAME_ROW_TYPES")
        check(len(set(game_ids)) == 25, "resource_bounds:DUPLICATE_GAME_ID")
    baseline_acceptance = contract.get("baseline_acceptance")
    check(
        isinstance(baseline_acceptance, dict),
        "contract:BASELINE_ACCEPTANCE_MISSING",
    )
    if isinstance(baseline_acceptance, dict):
        check(
            baseline_acceptance.get("started_game_count") == 25,
            "contract:BASELINE_STARTED_COUNT",
        )
        check(
            baseline_acceptance.get("bounded_report_count") == 25,
            "contract:BASELINE_REPORT_COUNT",
        )
        check(
            baseline_acceptance.get("requires_win_count") is False,
            "contract:BASELINE_WIN_REQUIREMENT",
        )
        check(
            baseline_acceptance.get("status") == "PRODUCT_BASELINE_EXECUTABLE",
            "contract:BASELINE_STATUS",
        )

    m1_acceptance = contract.get("m1_runtime_surface_acceptance")
    check(isinstance(m1_acceptance, dict), "contract:M1_ACCEPTANCE_MISSING")
    if isinstance(m1_acceptance, dict):
        check(
            m1_acceptance.get("path") == M1_RUNTIME_SURFACE_PATH.as_posix(),
            "contract:M1_PATH",
        )
        check(
            m1_acceptance.get("status") == "OFFICIAL_RUNTIME_SURFACE_COMPLETE",
            "contract:M1_STATUS",
        )
        check(
            m1_acceptance.get("game_count") == 25,
            "contract:M1_GAME_COUNT",
        )
        check(
            m1_acceptance.get("level_count") == 183,
            "contract:M1_LEVEL_COUNT",
        )
        check(
            m1_acceptance.get("hds_authorized_game_count") == 25,
            "contract:M1_HDS_AUTHORIZATION_COUNT",
        )
        check(
            m1_acceptance.get("external_action_game_count") == 25,
            "contract:M1_EXTERNAL_ACTION_COUNT",
        )
        check(
            m1_acceptance.get("reobserved_game_count") == 25,
            "contract:M1_REOBSERVATION_COUNT",
        )
    check(
        m1_runtime_surface.get("schema_version")
        == "arc3-product-m1-runtime-surface-v1",
        "m1_runtime_surface:SCHEMA_VERSION",
    )
    check(
        m1_runtime_surface.get("exit_status") == "OFFICIAL_RUNTIME_SURFACE_COMPLETE",
        "m1_runtime_surface:EXIT_STATUS",
    )
    check(
        m1_runtime_surface.get("failure_reasons") == [],
        "m1_runtime_surface:FAILURES_PRESENT",
    )
    expected_m1_metrics: dict[str, object] = {
        "advertised_game_count": 25,
        "inspected_game_count": 25,
        "total_win_level_count": 183,
        "normal_action_union": list(range(1, 8)),
        "legal_action_union": list(range(8)),
        "hds_authorized_game_count": 25,
        "external_action_game_count": 25,
        "reobserved_game_count": 25,
        "single_cognitive_session_count": 1,
        "episode_count": 25,
        "scorecard_closed": True,
    }
    for key, expected in expected_m1_metrics.items():
        check(
            m1_runtime_surface.get(key) == expected,
            f"m1_runtime_surface:{key.upper()}_MISMATCH",
        )
    check(
        set(m1_runtime_surface.get("pointer_categories", []))
        == {
            "boundary",
            "candidate-position",
            "cell",
            "object",
            "path",
            "region",
            "ui",
        },
        "m1_runtime_surface:POINTER_CATEGORY_MISMATCH",
    )
    check(
        m1_runtime_surface.get("multi_frame_initial_game_count", 0) >= 2,
        "m1_runtime_surface:MULTI_FRAME_COVERAGE",
    )
    m1_rows = m1_runtime_surface.get("rows")
    check(isinstance(m1_rows, list), "m1_runtime_surface:ROWS_MISSING")
    if isinstance(m1_rows, list):
        check(len(m1_rows) == 25, "m1_runtime_surface:ROW_COUNT")
        check(
            [row.get("game_ordinal") for row in m1_rows if isinstance(row, dict)]
            == list(range(25)),
            "m1_runtime_surface:ROW_ORDINALS",
        )
        check(
            all(
                isinstance(row, dict)
                and row.get("external_action_executed") is True
                and row.get("reobservation_valid") is True
                and row.get("hds_authorization_valid") is True
                for row in m1_rows
            ),
            "m1_runtime_surface:ROW_RUNTIME_GATE",
        )
    check(
        '"game_id"' not in (root / M1_RUNTIME_SURFACE_PATH).read_text(encoding="utf-8"),
        "m1_runtime_surface:GAME_ID_LEAK",
    )

    m2_acceptance = contract.get("m2_product_capability_acceptance")
    check(isinstance(m2_acceptance, dict), "contract:M2_ACCEPTANCE_MISSING")
    if isinstance(m2_acceptance, dict):
        expected_contract_m2: dict[str, object] = {
            "path": M2_PRODUCT_CAPABILITY_PATH.as_posix(),
            "descriptor_path": M2_PRODUCT_DESCRIPTOR_PATH.as_posix(),
            "package_path": M2_PRODUCT_PACKAGE_PATH.as_posix(),
            "controlled_game_id": "ft09-0d8bbf25",
            "controlled_action_budget": 128,
            "product_actions": 75,
            "product_level_count": 6,
            "product_final_state": "WIN",
            "p_removal_actions": 128,
            "p_removal_level_count": 0,
            "p_removal_final_state": "NOT_FINISHED",
            "acceptance_gate_count": 14,
            "failure_count": 0,
            "status": "PRODUCT_CAPABILITY_BUNDLE_ACTIVE",
        }
        for key, expected in expected_contract_m2.items():
            check(
                m2_acceptance.get(key) == expected,
                f"contract:M2_{key.upper()}_MISMATCH",
            )
    m3_acceptance = contract.get("m3_integrated_agi_acceptance")
    expected_contract_m3: dict[str, object] = {
        "path": COMPLETION_AUDIT_PATH.as_posix(),
        "known_sample_regression_complete": True,
        "cv_holdout_execution_count": 25,
        "cv_holdout_completed_environment_count": 0,
        "cv_holdout_completed_level_count": 0,
        "active_product_transformation_completion_count": 7,
        "active_product_transformation_status": "PASS",
        "same_active_artifact_locked_completion": False,
        "completion_allowed": False,
        "status": "M3_GENERICITY_REOPENED",
    }
    check(isinstance(m3_acceptance, dict), "contract:M3_ACCEPTANCE_MISSING")
    if isinstance(m3_acceptance, dict):
        for key, expected in expected_contract_m3.items():
            check(
                m3_acceptance.get(key) == expected,
                f"contract:M3_{key.upper()}_MISMATCH",
            )
    m4_acceptance = contract.get("m4_full_sample_acceptance")
    expected_contract_m4: dict[str, object] = {
        "path": M4_PRODUCT_PATH.as_posix(),
        "game_win_count": 25,
        "level_completion_count": 183,
        "action_count": 10733,
        "runtime_failure_signature_row_count": 0,
        "adapter_crash_count": 0,
        "lifecycle_failure_count": 0,
        "shared_session_count": 1,
        "status": "KNOWN_SAMPLE_REGRESSION_COMPLETE",
    }
    check(isinstance(m4_acceptance, dict), "contract:M4_ACCEPTANCE_MISSING")
    if isinstance(m4_acceptance, dict):
        for key, expected in expected_contract_m4.items():
            check(
                m4_acceptance.get(key) == expected,
                f"contract:M4_{key.upper()}_MISMATCH",
            )
    m5_acceptance = contract.get("m5_local_closure_acceptance")
    expected_contract_m5: dict[str, object] = {
        "path": M5_RELEASE_PATH.as_posix(),
        "clean_install_path": M5_CLEAN_PRODUCT_PATH.as_posix(),
        "wheel_manifest_path": RELEASE_MANIFEST_PATH.as_posix(),
        "dependency_lock_path": RELEASE_DEPENDENCY_LOCK_PATH.as_posix(),
        "notebook_validation_path": NOTEBOOK_VALIDATION_PATH.as_posix(),
        "clean_install_functional_result_exact": True,
        "product_logical_identity_preserved": True,
        "wheel_byte_reproducible": True,
        "dependency_lock_matches_fresh_install": True,
        "local_acceptance_failure_count": 0,
        "status": "LOCAL_PACKAGE_REGRESSION_COMPLETE",
        "external_kaggle_normal_run_status": (
            "NOT_EXECUTED_REQUIRES_CURRENT_OWNER_AUTHORIZATION"
        ),
    }
    check(isinstance(m5_acceptance, dict), "contract:M5_ACCEPTANCE_MISSING")
    if isinstance(m5_acceptance, dict):
        for key, expected in expected_contract_m5.items():
            check(
                m5_acceptance.get(key) == expected,
                f"contract:M5_{key.upper()}_MISMATCH",
            )
    completion_audit_body = dict(completion_audit)
    completion_audit_digest = completion_audit_body.pop("content_digest", None)
    check(
        completion_audit_digest
        == "arc3-product-completion-audit:"
        + hashlib.sha256(
            _canonical_json(completion_audit_body).encode("utf-8")
        ).hexdigest(),
        "completion_audit:CONTENT_DIGEST_MISMATCH",
    )
    expected_completion_audit: dict[str, object] = {
        "schema_version": "arc3-product-completion-audit-v1",
        "evaluation_role": "PRODUCT_COMPLETION_AUTHORITY_GATE",
        "status": "M3_GENERICITY_REOPENED",
        "product_completion_allowed": False,
    }
    for key, expected in expected_completion_audit.items():
        check(
            completion_audit.get(key) == expected,
            f"completion_audit:{key.upper()}_MISMATCH",
        )
    transformation_body = dict(m3_transformation)
    transformation_digest = transformation_body.pop("content_digest", None)
    check(
        transformation_digest
        == "arc3-product-active-genericity:"
        + hashlib.sha256(
            _canonical_json(transformation_body).encode("utf-8")
        ).hexdigest(),
        "m3_transformation:CONTENT_DIGEST_MISMATCH",
    )
    transformation_completion = m3_transformation.get(
        "transformation_completion"
    )
    check(
        m3_transformation.get("status") == "PASS"
        and m3_transformation.get("semantic_environment_completion_executed")
        is True
        and m3_transformation.get("product_p_j0_m0_identity_bound") is True
        and m3_transformation.get(
            "same_runtime_identity_for_all_environments"
        )
        is True
        and transformation_completion == {"completed": 7, "required": 7},
        "m3_transformation:ACTIVE_PRODUCT_COMPLETION_FAILURE",
    )
    completion_gates = completion_audit.get("gates")
    check(isinstance(completion_gates, dict), "completion_audit:GATES_MISSING")
    if isinstance(completion_gates, dict):
        required_completion_gates = (
            "KNOWN_SAMPLE_REGRESSION",
            "LOCAL_PACKAGE_REGRESSION",
            "GEN_CV_HOLDOUT_COMPLETION",
            "GEN_SEMANTIC_TRANSFORMATION_COMPLETION",
            "AUT_006_ACTIVE_ARTIFACT_LOCKED_EVALUATOR",
            "OFF_004_OUTPUT_BYTES",
            "OFF_005_SCORE_RETURNED",
            "OFF_007_SAME_RUNTIME_IDENTITY",
            "OFFICIAL_FULL_COMPLETE",
        )
        for gate in required_completion_gates:
            check(
                isinstance(completion_gates.get(gate), bool),
                f"completion_audit:{gate}_BOOLEAN_REQUIRED",
            )
        failed_completion_gates = tuple(
            gate
            for gate in required_completion_gates
            if completion_gates.get(gate) is not True
        )
        check(
            tuple(completion_audit.get("blocking_requirement_ids", ()))
            == failed_completion_gates,
            "completion_audit:BLOCKING_REQUIREMENTS_DO_NOT_MATCH_GATES",
        )
        check(
            completion_audit.get("product_completion_allowed")
            is (not failed_completion_gates),
            "completion_audit:COMPLETION_BOOLEAN_MISMATCH",
        )
    m2_body = dict(m2_product_capability)
    m2_claimed_digest = m2_body.pop("content_digest", None)
    check(
        m2_claimed_digest
        == "arc3-product-m2-acceptance:"
        + hashlib.sha256(_canonical_json(m2_body).encode("utf-8")).hexdigest(),
        "m2_product_capability:CONTENT_DIGEST_MISMATCH",
    )
    check(
        m2_product_capability.get("exit_status") == "PRODUCT_CAPABILITY_BUNDLE_ACTIVE",
        "m2_product_capability:EXIT_STATUS",
    )
    check(
        m2_product_capability.get("failure_reasons") == [],
        "m2_product_capability:FAILURES_PRESENT",
    )
    m2_gates = m2_product_capability.get("gates")
    check(
        isinstance(m2_gates, dict)
        and len(m2_gates) == 14
        and set(m2_gates.values()) == {True},
        "m2_product_capability:ACCEPTANCE_GATES",
    )
    m2_product_result = m2_product_capability.get("product_result")
    check(
        isinstance(m2_product_result, dict)
        and m2_product_result.get("actions_executed") == 75
        and m2_product_result.get("progress_count") == 6
        and m2_product_result.get("final_state") == "WIN"
        and m2_product_result.get("teacher_seed_citation_count") == 7,
        "m2_product_capability:PRODUCT_RESULT",
    )
    m2_ablation = m2_product_capability.get("p_removal_ablation")
    check(
        isinstance(m2_ablation, dict)
        and m2_ablation.get("actions_executed") == 128
        and m2_ablation.get("progress_count") == 0
        and m2_ablation.get("final_state") == "NOT_FINISHED"
        and m2_ablation.get("product_j0_retained") is True
        and m2_ablation.get("product_m0_retained") is True,
        "m2_product_capability:P_REMOVAL_RESULT",
    )
    descriptor_body = dict(m2_product_descriptor)
    descriptor_claimed_digest = descriptor_body.pop("content_digest", None)
    check(
        descriptor_claimed_digest
        == "product-capability-descriptor:"
        + hashlib.sha256(_canonical_json(descriptor_body).encode("utf-8")).hexdigest(),
        "m2_product_descriptor:CONTENT_DIGEST_MISMATCH",
    )
    package_path = root / M2_PRODUCT_PACKAGE_PATH
    check(
        m2_product_descriptor.get("package_sha256")
        == hashlib.sha256(package_path.read_bytes()).hexdigest(),
        "m2_product_descriptor:PACKAGE_SHA256",
    )
    check(
        m2_product_descriptor.get("package_size_bytes") == package_path.stat().st_size,
        "m2_product_descriptor:PACKAGE_SIZE",
    )
    check(
        m2_product_descriptor.get("p_compiler_mode") == "PRODUCT"
        and m2_product_descriptor.get("p_program_id") == "arc3.product.capability.v1"
        and m2_product_descriptor.get("m0_record_count") == 8
        and m2_product_descriptor.get("identity_free") is True
        and m2_product_descriptor.get("contains_identity_router") is False
        and m2_product_descriptor.get("contains_fixed_trajectory") is False,
        "m2_product_descriptor:PRODUCT_CONTRACT",
    )

    release_body = dict(m5_release)
    release_claimed_digest = release_body.pop("content_digest", None)
    check(
        release_claimed_digest
        == "arc3-product-release-evidence:"
        + hashlib.sha256(_canonical_json(release_body).encode("utf-8")).hexdigest(),
        "m5_release:CONTENT_DIGEST_MISMATCH",
    )
    implementation_commit = m5_release.get("implementation_commit")
    check(
        isinstance(implementation_commit, str) and len(implementation_commit) == 40,
        "m5_release:IMPLEMENTATION_COMMIT_INVALID",
    )
    run_evidence_rows = (
        ("m4_product", m4_product, "M4_CANONICAL_FULL_SAMPLE"),
        (
            "m5_clean_product",
            m5_clean_product,
            "M5_CLEAN_INSTALL_FULL_SAMPLE",
        ),
    )
    for label, value, stage in run_evidence_rows:
        body = dict(value)
        claimed_digest = body.pop("content_digest", None)
        check(
            claimed_digest
            == "arc3-product-run-evidence:"
            + hashlib.sha256(_canonical_json(body).encode("utf-8")).hexdigest(),
            f"{label}:CONTENT_DIGEST_MISMATCH",
        )
        expected_run_values: dict[str, object] = {
            "evidence_stage": stage,
            "implementation_commit": implementation_commit,
            "product_status": "COMPLETE",
            "product_completion_established": True,
            "product_endpoint_failure_count": 0,
            "product_endpoint_failures": [],
            "product_game_win_count": 25,
            "product_level_completion_count": 183,
            "product_total_action_count": 10733,
            "product_plan_integrity_row_count": 25,
            "product_runtime_failure_signature_row_count": 0,
            "product_executed_plan_count": 10733,
            "product_hds_plan_commit_count": 10733,
            "product_initial_plan_count": 25,
            "product_max_plan_step_count": 4,
            "product_failure_attribution_count": 12,
            "product_rollback_plan_count": 42,
            "product_post_rollback_replan_count": 42,
            "per_game_reference_exact": True,
            "scorecard_closed": True,
            "shared_session_count": 1,
            "state_owner_violation_count": 0,
            "identity_boundary": "PASS",
            "runtime_policy_changed": False,
        }
        for key, expected in expected_run_values.items():
            check(
                value.get(key) == expected,
                f"{label}:{key.upper()}_MISMATCH",
            )
    check(
        m4_product.get("results") == m5_clean_product.get("results")
        and m4_product.get("orchestration_game_index")
        == m5_clean_product.get("orchestration_game_index"),
        "m5_clean_product:FUNCTIONAL_RESULT_MISMATCH",
    )
    for logical_field in (
        "product_initial_state_logical_digest",
        "product_p_logical_digest",
        "product_p_program_id",
        "product_p_body_format",
        "product_p_body_version",
        "product_p_compiler_mode",
        "product_bundle_j0_digest",
        "product_j0_digest",
        "product_m0_digest",
        "product_m0_record_count",
    ):
        check(
            m4_product.get(logical_field) == m5_clean_product.get(logical_field),
            f"m5_clean_product:{logical_field.upper()}_MISMATCH",
        )

    release_wheel = root / RELEASE_WHEEL_PATH
    release_manifest_path = root / RELEASE_MANIFEST_PATH
    release_sums = root / RELEASE_SUMS_PATH
    release_dependency_lock = root / RELEASE_DEPENDENCY_LOCK_PATH
    notebook_path = root / NOTEBOOK_VALIDATION_PATH
    check(
        release_manifest.get("wheel_sha256")
        == hashlib.sha256(release_wheel.read_bytes()).hexdigest(),
        "release_manifest:WHEEL_SHA256_MISMATCH",
    )
    expected_release_manifest: dict[str, object] = {
        "product_id": PRODUCT_NAME,
        "product_version": "1.0.0",
        "byte_reproducible": True,
        "teacher_included": False,
        "fixed_action_trajectory_included": False,
        "runtime_identity_routing_included": False,
        "literal_coordinate_table_included": False,
        "compiled_identity_free_product_policy_included": True,
    }
    for key, expected in expected_release_manifest.items():
        check(
            release_manifest.get(key) == expected,
            f"release_manifest:{key.upper()}_MISMATCH",
        )
    check(
        notebook_validation.get("status") == "PASS"
        and notebook_validation.get("failed_check_ids") == []
        and notebook_validation.get("tracked_secret_findings") == []
        and notebook_validation.get("notebook_secret_findings") == []
        and notebook_validation.get("submission_api_call_count") == 0,
        "notebook_validation:RELEASE_CONTRACT_FAILURE",
    )
    expected_release_values: dict[str, object] = {
        "local_release_status": "LOCAL_PRODUCT_CLOSURE_COMPLETE",
        "external_kaggle_normal_run_status": (
            "NOT_EXECUTED_REQUIRES_CURRENT_OWNER_AUTHORIZATION"
        ),
        "product_released": False,
        "clean_install_functional_result_exact": True,
        "product_logical_identity_preserved": True,
        "wheel_byte_reproducible": True,
        "dependency_lock_matches_fresh_install": True,
        "notebook_validation_status": "PASS",
        "notebook_submission_api_call_count": 0,
        "notebook_secret_finding_count": 0,
        "local_acceptance_failure_count": 0,
        "remaining_release_gate_count": 1,
    }
    for key, expected in expected_release_values.items():
        check(
            m5_release.get(key) == expected,
            f"m5_release:{key.upper()}_MISMATCH",
        )
    check(
        m5_release.get("m4_evidence_sha256")
        == hashlib.sha256((root / M4_PRODUCT_PATH).read_bytes()).hexdigest()
        and m5_release.get("m5_clean_evidence_sha256")
        == hashlib.sha256((root / M5_CLEAN_PRODUCT_PATH).read_bytes()).hexdigest()
        and m5_release.get("release_manifest_sha256")
        == hashlib.sha256(release_manifest_path.read_bytes()).hexdigest()
        and m5_release.get("release_sums_sha256")
        == hashlib.sha256(release_sums.read_bytes()).hexdigest()
        and m5_release.get("dependency_lock_sha256")
        == hashlib.sha256(release_dependency_lock.read_bytes()).hexdigest()
        and m5_release.get("notebook_validation_sha256")
        == hashlib.sha256(notebook_path.read_bytes()).hexdigest(),
        "m5_release:BOUND_ARTIFACT_DIGEST_MISMATCH",
    )

    check(
        classification.get("classification") == "HISTORICAL_REUSE_ONLY",
        "classification:ROLE",
    )
    check(
        classification.get("current_selector") is False,
        "classification:CURRENT_SELECTOR",
    )
    check(
        classification.get("runtime_activation_eligible") is False,
        "classification:RUNTIME_ELIGIBLE",
    )
    check(
        classification.get("phase_authority_eligible") is False,
        "classification:PHASE_ELIGIBLE",
    )
    superseded = classification.get("superseded_by")
    check(isinstance(superseded, dict), "classification:SUPERSESSION_MISSING")
    if isinstance(superseded, dict):
        check(
            superseded.get("product_id") == PRODUCT_ID,
            "classification:SUPERSESSION_PRODUCT",
        )
        check(
            superseded.get("selector_path") == CURRENT_TASK_PATH.as_posix(),
            "classification:SUPERSESSION_SELECTOR",
        )

    blockers = current.get("verified_product_blockers")
    blocker_map = (
        {item.get("id"): item for item in blockers if isinstance(item, dict)}
        if isinstance(blockers, list)
        else {}
    )
    check(
        blocker_map.get("B-01", {}).get("status") == "CLOSED_PRODUCT_PATH",
        "current_task:B01_STATUS",
    )
    for blocker_id in ("B-02", "B-03"):
        check(
            blocker_map.get(blocker_id, {}).get("status")
            == "CLOSED_M2_PRODUCT_CAPABILITY_BUNDLE",
            f"current_task:{blocker_id.replace('-', '')}_STATUS",
        )
        check(
            blocker_map.get(blocker_id, {}).get("evidence")
            == M2_PRODUCT_CAPABILITY_PATH.as_posix(),
            f"current_task:{blocker_id.replace('-', '')}_EVIDENCE",
        )
    for blocker_id in ("B-04", "B-05"):
        check(
            blocker_map.get(blocker_id, {}).get("status")
            == "CLOSED_M1_OFFICIAL_RUNTIME_SURFACE",
            f"current_task:{blocker_id.replace('-', '')}_STATUS",
        )
        check(
            blocker_map.get(blocker_id, {}).get("evidence")
            == M1_RUNTIME_SURFACE_PATH.as_posix(),
            f"current_task:{blocker_id.replace('-', '')}_EVIDENCE",
        )
    check(
        blocker_map.get("B-06", {}).get("status")
        == "REOPENED_M3_GENERICITY_NOT_ESTABLISHED",
        "current_task:B06_STATUS",
    )
    check(
        blocker_map.get("B-06", {}).get("evidence")
        == COMPLETION_AUDIT_PATH.as_posix(),
        "current_task:B06_EVIDENCE",
    )
    check(
        blocker_map.get("B-07", {}).get("status")
        == "CLOSED_KNOWN_SAMPLE_REGRESSION",
        "current_task:B07_STATUS",
    )
    check(
        blocker_map.get("B-07", {}).get("evidence") == M4_PRODUCT_PATH.as_posix(),
        "current_task:B07_EVIDENCE",
    )
    check(
        blocker_map.get("B-08", {}).get("status")
        == "AWAITING_CURRENT_OWNER_AUTHORIZATION",
        "current_task:B08_STATUS",
    )
    check(
        blocker_map.get("B-08", {}).get("evidence") == M5_RELEASE_PATH.as_posix(),
        "current_task:B08_EVIDENCE",
    )
    check(
        blocker_map.get("B-09", {}).get("status") == "OPEN_M3_BLOCKING",
        "current_task:B09_STATUS",
    )
    check(
        blocker_map.get("B-09", {}).get("evidence")
        == COMPLETION_AUDIT_PATH.as_posix(),
        "current_task:B09_EVIDENCE",
    )

    constants = _literal_constants(root / PRODUCT_GOVERNANCE_PATH)
    expected_constants: dict[str, object] = {
        "ARC3_PRODUCT_ID": PRODUCT_NAME,
        "ARC3_PRODUCT_ACTIVE_MILESTONE": ACTIVE_MILESTONE,
        "ARC3_OFFICIAL_SAMPLE_GAME_TARGET": 25,
        "ARC3_OFFICIAL_SAMPLE_LEVEL_TARGET": 183,
        "ARC3_KNOWN_SUCCESS_ACTION_CEILING": 1519,
        "ARC3_KNOWN_SUCCESS_NO_PROGRESS_CEILING": 644,
        "ARC3_PRODUCT_NO_PROGRESS_LIMIT": 650,
        "ARC3_DEVELOPMENT_ACTION_BUDGET": 4096,
        "ARC3_CURRENT_SELECTOR_PATH": CURRENT_TASK_PATH.as_posix(),
        "ARC3_LEGACY_REV3_IS_CURRENT": False,
    }
    for name, expected in expected_constants.items():
        check(constants.get(name) == expected, f"product_governance:{name}")

    runner_source = (root / PRODUCT_RUNNER_PATH).read_text(encoding="utf-8")
    entrypoint_source = (root / PRODUCT_ENTRYPOINT_PATH).read_text(encoding="utf-8")
    entrypoint_constants = _literal_constants(root / PRODUCT_ENTRYPOINT_PATH)
    rev3_source = (root / REV3_GOVERNANCE_PATH).read_text(encoding="utf-8")
    generic_runner_source = (root / GENERIC_RUNNER_PATH).read_text(encoding="utf-8")
    check(
        ".product_governance import" in runner_source,
        "product_runner:GOVERNANCE_IMPORT_MISSING",
    )
    check(
        "ARC3_PRODUCT_ENDPOINT.metrics(report)" in runner_source,
        "product_runner:ENDPOINT_GATE_MISSING",
    )
    check(
        "def run_arc3_completion_offline(" in runner_source,
        "product_runner:OFFLINE_ENTRYPOINT_MISSING",
    )
    check(
        "rev3_governance" not in runner_source + entrypoint_source,
        "product_runtime:LEGACY_REV3_IMPORT",
    )
    check(
        "class ARC3CompletionAgent(GenericAGIAgent)" in entrypoint_source,
        "product_entrypoint:CLASS_MISSING",
    )
    check(
        entrypoint_constants.get("ARC3_COMPLETION_AGENT_PRODUCT_VERSION")
        == "arc3-completion-agent-product-v1.0",
        "product_entrypoint:PRODUCT_VERSION_MISMATCH",
    )
    check(
        "OfflineGenericEnvironment" in entrypoint_source,
        "product_entrypoint:OFFLINE_ADAPTER_MISSING",
    )
    check(
        '"started_game_count": started_game_count' in generic_runner_source,
        "generic_runner:STARTED_COUNT_MISSING",
    )
    check(
        '"resource_action_budget_per_episode"' in generic_runner_source,
        "generic_runner:OBSERVED_BUDGET_MISSING",
    )
    check(
        "REV3_IS_CURRENT: Final = False" in rev3_source,
        "rev3_governance:HISTORICAL_MARKER_MISSING",
    )

    agents = (root / "AGENTS.md").read_text(encoding="utf-8")
    authority_markers = [
        "Ownerの現在の明示指示",
        "docs/architecture/AGI三主体統合設計正本_v0_2.md",
        "docs/references/HDS_FRAMEWORK_rev3_1a_INTERNAL.md",
        "docs/architecture/工学的AGI実装仕様書_v0_2.md",
        "docs/strategy/ARC3_AGIエージェント_製品仕様書_rev4.md",
        "docs/roadmap/ARC3_AGIエージェント_製品開発ロードマップ_rev4.md",
        "control/rev4/CURRENT_TASK.json",
    ]
    marker_positions = [agents.find(marker) for marker in authority_markers]
    check(
        all(position >= 0 for position in marker_positions),
        "agents:AUTHORITY_MARKER_MISSING",
    )
    check(
        marker_positions == sorted(marker_positions),
        "agents:AUTHORITY_ORDER_MISMATCH",
    )

    required_files = contract.get("required_product_files")
    check(isinstance(required_files, list), "contract:PRODUCT_FILES_MISSING")
    if isinstance(required_files, list):
        for relative in required_files:
            check(
                isinstance(relative, str) and (root / relative).is_file(),
                f"contract:PRODUCT_FILE_MISSING:{relative}",
            )

    evidence = current.get("current_evidence")
    check(isinstance(evidence, dict), "current_task:EVIDENCE_MISSING")
    if isinstance(evidence, dict):
        check(
            evidence.get("m1_report_path") == M1_RUNTIME_SURFACE_PATH.as_posix(),
            "current_task:M1_REPORT_PATH",
        )
        check(
            evidence.get("m1_report_sha256")
            == hashlib.sha256(
                (root / M1_RUNTIME_SURFACE_PATH).read_bytes()
            ).hexdigest(),
            "current_task:M1_REPORT_SHA256",
        )
        expected_current_m1: dict[str, object] = {
            "m1_exit_status": "OFFICIAL_RUNTIME_SURFACE_COMPLETE",
            "m1_failure_reasons": [],
            "m1_inspected_game_count": 25,
            "m1_total_win_level_count": 183,
            "m1_hds_authorized_game_count": 25,
            "m1_external_action_game_count": 25,
            "m1_reobserved_game_count": 25,
            "m1_scorecard_closed": True,
        }
        for key, expected in expected_current_m1.items():
            check(
                evidence.get(key) == expected,
                f"current_task:{key.upper()}_MISMATCH",
            )
        check(
            evidence.get("m2_report_path") == M2_PRODUCT_CAPABILITY_PATH.as_posix(),
            "current_task:M2_REPORT_PATH",
        )
        check(
            evidence.get("m2_report_sha256")
            == hashlib.sha256(
                (root / M2_PRODUCT_CAPABILITY_PATH).read_bytes()
            ).hexdigest(),
            "current_task:M2_REPORT_SHA256",
        )
        check(
            evidence.get("m2_descriptor_path") == M2_PRODUCT_DESCRIPTOR_PATH.as_posix(),
            "current_task:M2_DESCRIPTOR_PATH",
        )
        check(
            evidence.get("m2_descriptor_sha256")
            == hashlib.sha256(
                (root / M2_PRODUCT_DESCRIPTOR_PATH).read_bytes()
            ).hexdigest(),
            "current_task:M2_DESCRIPTOR_SHA256",
        )
        check(
            evidence.get("m2_package_path") == M2_PRODUCT_PACKAGE_PATH.as_posix(),
            "current_task:M2_PACKAGE_PATH",
        )
        check(
            evidence.get("m2_package_sha256")
            == hashlib.sha256(
                (root / M2_PRODUCT_PACKAGE_PATH).read_bytes()
            ).hexdigest(),
            "current_task:M2_PACKAGE_SHA256",
        )
        expected_current_m2: dict[str, object] = {
            "m2_exit_status": "PRODUCT_CAPABILITY_BUNDLE_ACTIVE",
            "m2_failure_reasons": [],
            "m2_acceptance_gate_count": 14,
            "m2_controlled_game_id": "ft09-0d8bbf25",
            "m2_product_actions": 75,
            "m2_product_level_completion_count": 6,
            "m2_product_final_state": "WIN",
            "m2_p_removal_actions": 128,
            "m2_p_removal_level_completion_count": 0,
            "m2_p_removal_final_state": "NOT_FINISHED",
            "m2_teacher_seed_citation_count": 7,
        }
        for key, expected in expected_current_m2.items():
            check(
                evidence.get(key) == expected,
                f"current_task:{key.upper()}_MISMATCH",
            )
        baseline_path = evidence.get("baseline_report_path")
        baseline = root / str(baseline_path)
        check(
            baseline_path == BASELINE_PATH.as_posix(),
            "current_task:BASELINE_PATH",
        )
        if baseline.is_file():
            baseline_value = _load_object(root, Path(str(baseline_path)))
            check(
                evidence.get("baseline_report_status") == "EXECUTED",
                "current_task:BASELINE_STATUS",
            )
            check(
                evidence.get("baseline_report_complete") is True,
                "current_task:BASELINE_COMPLETENESS",
            )
            check(
                baseline_value.get("product_id") == PRODUCT_NAME,
                "baseline:PRODUCT_ID",
            )
            check(
                baseline_value.get("official_sample_game_target") == 25,
                "baseline:GAME_TARGET",
            )
            check(
                baseline_value.get("product_action_budget_per_game") == 4096,
                "baseline:ACTION_BUDGET",
            )
            check(
                evidence.get("baseline_report_sha256")
                == hashlib.sha256(baseline.read_bytes()).hexdigest(),
                "current_task:BASELINE_SHA256",
            )
            expected_baseline_metrics: dict[str, object] = {
                "product_baseline_status": "PRODUCT_BASELINE_EXECUTABLE",
                "product_baseline_executable": True,
                "baseline_report_complete": True,
                "advertised_game_count": 25,
                "started_game_count": 25,
                "completed_game_count": 25,
                "product_bounded_report_count": 25,
                "budget_impossible_game_count": 0,
                "adapter_crash_count": 0,
                "failed_game_count": 0,
                "scorecard_lifecycle_leak_count": 0,
                "active_product_path_count": 1,
                "product_game_win_count": 0,
                "product_level_completion_count": 3,
                "product_completion_established": False,
                "product_status": "INCOMPLETE",
            }
            for key, expected in expected_baseline_metrics.items():
                check(
                    baseline_value.get(key) == expected,
                    f"baseline:{key.upper()}_MISMATCH",
                )
            check(
                evidence.get("m0_exit_status")
                == baseline_value.get("product_baseline_status"),
                "current_task:M0_EXIT_STATUS",
            )
            check(
                evidence.get("m0_product_game_win_count")
                == baseline_value.get("product_game_win_count"),
                "current_task:BASELINE_WIN_COUNT",
            )
            check(
                evidence.get("m0_product_level_completion_count")
                == baseline_value.get("product_level_completion_count"),
                "current_task:BASELINE_LEVEL_COUNT",
            )
            check(
                evidence.get("m0_product_completion_established")
                == baseline_value.get("product_completion_established"),
                "current_task:BASELINE_COMPLETION_CLAIM",
            )
            check(
                evidence.get("m0_product_endpoint_failures")
                == baseline_value.get("product_endpoint_failures"),
                "current_task:BASELINE_ENDPOINT_FAILURES",
            )
        else:
            check(
                evidence.get("baseline_report_status") == "NOT_EXECUTED",
                "current_task:ABSENT_BASELINE_STATUS",
            )
            check(
                evidence.get("baseline_report_complete") is False,
                "current_task:ABSENT_BASELINE_COMPLETENESS",
            )
            check(
                evidence.get("m0_product_completion_established") is False,
                "current_task:ABSENT_BASELINE_COMPLETION_CLAIM",
            )
        expected_current_product: dict[str, object] = {
            "implementation_commit": implementation_commit,
            "m4_report_path": M4_PRODUCT_PATH.as_posix(),
            "m4_report_sha256": hashlib.sha256(
                (root / M4_PRODUCT_PATH).read_bytes()
            ).hexdigest(),
            "m4_exit_status": "KNOWN_SAMPLE_REGRESSION_COMPLETE",
            "m5_clean_report_path": M5_CLEAN_PRODUCT_PATH.as_posix(),
            "m5_clean_report_sha256": hashlib.sha256(
                (root / M5_CLEAN_PRODUCT_PATH).read_bytes()
            ).hexdigest(),
            "m5_release_report_path": M5_RELEASE_PATH.as_posix(),
            "m5_release_report_sha256": hashlib.sha256(
                (root / M5_RELEASE_PATH).read_bytes()
            ).hexdigest(),
            "m5_local_exit_status": "LOCAL_PACKAGE_REGRESSION_COMPLETE",
            "product_game_win_count": 25,
            "product_level_completion_count": 183,
            "product_total_action_count": 10733,
            "product_completion_established": False,
            "product_endpoint_failures": [],
            "completion_audit_path": COMPLETION_AUDIT_PATH.as_posix(),
            "completion_audit_sha256": hashlib.sha256(
                (root / COMPLETION_AUDIT_PATH).read_bytes()
            ).hexdigest(),
            "completion_audit_status": "M3_GENERICITY_REOPENED",
            "completion_audit_blocking_requirement_count": len(
                completion_audit.get("blocking_requirement_ids", ())
            ),
            "active_product_transformation_report_path": (
                M3_TRANSFORMATION_PATH.as_posix()
            ),
            "active_product_transformation_report_sha256": hashlib.sha256(
                (root / M3_TRANSFORMATION_PATH).read_bytes()
            ).hexdigest(),
            "active_product_transformation_status": "PASS",
            "active_product_transformation_completion_count": 7,
            "cv_holdout_execution_count": 25,
            "cv_holdout_completed_environment_count": 0,
            "cv_holdout_completed_level_count": 0,
            "same_active_artifact_locked_completion": False,
            "wheel_path": RELEASE_WHEEL_PATH.as_posix(),
            "wheel_sha256": release_manifest.get("wheel_sha256"),
            "wheel_size_bytes": release_manifest.get("wheel_size_bytes"),
            "dependency_lock_path": RELEASE_DEPENDENCY_LOCK_PATH.as_posix(),
            "dependency_lock_sha256": hashlib.sha256(
                (root / RELEASE_DEPENDENCY_LOCK_PATH).read_bytes()
            ).hexdigest(),
            "notebook_validation_path": NOTEBOOK_VALIDATION_PATH.as_posix(),
            "notebook_validation_sha256": hashlib.sha256(
                (root / NOTEBOOK_VALIDATION_PATH).read_bytes()
            ).hexdigest(),
            "external_kaggle_normal_run_status": (
                "NOT_EXECUTED_REQUIRES_CURRENT_OWNER_AUTHORIZATION"
            ),
        }
        for key, expected in expected_current_product.items():
            check(
                evidence.get(key) == expected,
                f"current_task:{key.upper()}_MISMATCH",
            )

    manifest_body = dict(manifest)
    claimed_digest = manifest_body.pop("content_digest", None)
    calculated_digest = (
        "rev4-current-authority-manifest:"
        + hashlib.sha256(_canonical_json(manifest_body).encode("utf-8")).hexdigest()
    )
    check(
        claimed_digest == calculated_digest,
        "authority_manifest:CONTENT_DIGEST_MISMATCH",
    )
    entries = manifest.get("entries")
    check(isinstance(entries, list), "authority_manifest:ENTRIES_MISSING")
    if isinstance(entries, list):
        check(
            manifest.get("entry_count") == len(entries),
            "authority_manifest:ENTRY_COUNT_MISMATCH",
        )
        paths: list[str] = []
        for index, entry in enumerate(entries):
            if not isinstance(entry, dict):
                check(False, f"authority_manifest.entries[{index}]:TYPE")
                continue
            relative = entry.get("path")
            expected_sha = entry.get("sha256")
            if not isinstance(relative, str) or not isinstance(expected_sha, str):
                check(False, f"authority_manifest.entries[{index}]:INVALID")
                continue
            check(True, f"authority_manifest.entries[{index}]:INVALID")
            paths.append(relative)
            artifact = root / relative
            check(
                artifact.is_file(),
                f"authority_manifest.entries[{index}]:MISSING",
            )
            if artifact.is_file():
                check(
                    hashlib.sha256(artifact.read_bytes()).hexdigest() == expected_sha,
                    f"authority_manifest.entries[{index}]:SHA256_MISMATCH",
                )
        check(len(paths) == len(set(paths)), "authority_manifest:DUPLICATE_PATH")
        for required in (
            CURRENT_TASK_PATH.as_posix(),
            CONTRACT_PATH.as_posix(),
            CLASSIFICATION_PATH.as_posix(),
            PRODUCT_GOVERNANCE_PATH.as_posix(),
            PRODUCT_RUNNER_PATH.as_posix(),
            PRODUCT_ENTRYPOINT_PATH.as_posix(),
            GENERIC_RUNNER_PATH.as_posix(),
            RESOURCE_BOUNDS_PATH.as_posix(),
            M1_RUNTIME_SURFACE_PATH.as_posix(),
            M2_PRODUCT_CAPABILITY_PATH.as_posix(),
            M2_PRODUCT_DESCRIPTOR_PATH.as_posix(),
            M2_PRODUCT_PACKAGE_PATH.as_posix(),
            M4_PRODUCT_PATH.as_posix(),
            M5_CLEAN_PRODUCT_PATH.as_posix(),
            M5_RELEASE_PATH.as_posix(),
            NOTEBOOK_VALIDATION_PATH.as_posix(),
            "release/ARC3CompletionAgent-v1.0/README.md",
            RELEASE_DEPENDENCY_LOCK_PATH.as_posix(),
            RELEASE_MANIFEST_PATH.as_posix(),
            RELEASE_WHEEL_PATH.as_posix(),
            RELEASE_SUMS_PATH.as_posix(),
        ):
            check(required in paths, f"authority_manifest:UNBOUND:{required}")

    return {
        "check_count": check_count,
        "failure_count": len(set(failures)),
        "failures": sorted(set(failures)),
        "status": "PASS" if not failures else "FAIL",
    }


def main() -> int:
    try:
        report = validate_repository(REPOSITORY_ROOT)
    except Exception as error:
        report = {
            "check_count": 0,
            "failure_count": 1,
            "failures": [f"VALIDATOR_EXCEPTION:{type(error).__name__}:{error}"],
            "status": "FAIL",
        }
    print(json.dumps(report, ensure_ascii=True, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
