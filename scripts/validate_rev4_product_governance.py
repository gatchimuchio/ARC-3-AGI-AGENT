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
ACTIVE_MILESTONE: Final = "M0_PRODUCT_BASELINE_AND_BLOCKER_CLOSURE"


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
    check(
        blocker_map.get("B-07", {}).get("status")
        == "PARTIAL_RUNNER_ADDED_BASELINE_PENDING",
        "current_task:B07_STATUS",
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
        baseline_path = evidence.get("baseline_report_path")
        baseline = root / str(baseline_path)
        check(
            baseline_path == "analysis/product/rev4/current_product_baseline.json",
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
                evidence.get("product_completion_established") is False,
                "current_task:ABSENT_BASELINE_COMPLETION_CLAIM",
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
            valid = isinstance(relative, str) and isinstance(expected_sha, str)
            check(valid, f"authority_manifest.entries[{index}]:INVALID")
            if not valid:
                continue
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
