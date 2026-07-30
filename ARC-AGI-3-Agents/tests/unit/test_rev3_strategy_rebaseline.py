from __future__ import annotations

import ast
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any

import pytest

from arc3_agi_agent.rev3_governance import (
    DISTILLED_RUNTIME_SOURCE_KIND,
    FORBIDDEN_PRODUCTION_IMPORT_ROOTS,
    QUARANTINED_RUNTIME_SOURCE_KINDS,
    REV3_ACTIVE_PHASE,
    REV3_PHASE_ORDER,
    Rev3ProductionSelection,
    audit_rev3_production_imports,
    require_rev3_production_selection,
)
from arc3_agi_agent.schema import digest_object

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_ROOT = REPOSITORY_ROOT / "ARC-AGI-3-Agents"


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _git_blob_sha256(commit: str, path: str) -> str:
    result = subprocess.run(
        ["git", "show", f"{commit}:{path}"],
        cwd=REPOSITORY_ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    return hashlib.sha256(result.stdout).hexdigest()


def _bound(label: str) -> str:
    return label + ":" + hashlib.sha256(label.encode("utf-8")).hexdigest()


def _valid_selection() -> Rev3ProductionSelection:
    return Rev3ProductionSelection(
        source_kind=DISTILLED_RUNTIME_SOURCE_KIND,
        structure_bundle_digest=_bound("structure"),
        initial_state_bundle_digest=_bound("initial"),
        owner_approval_digest=_bound("owner-approval"),
        runtime_artifact_digest=_bound("runtime"),
    )


def test_rev3_phase_order_and_hard_gates_are_fixed() -> None:
    assert REV3_ACTIVE_PHASE == "PH-D01A"
    assert REV3_PHASE_ORDER[0] == "PH-R00"
    assert REV3_PHASE_ORDER.index("PH-D14") < REV3_PHASE_ORDER.index(
        "PH-B00"
    )
    assert REV3_PHASE_ORDER.index("PH-B06") < REV3_PHASE_ORDER.index(
        "PH-A00"
    )
    assert REV3_PHASE_ORDER.index("PH-A08") < REV3_PHASE_ORDER.index(
        "PH-E00"
    )
    assert "PH-D04" not in REV3_PHASE_ORDER


@pytest.mark.parametrize(
    "source_kind",
    sorted(QUARANTINED_RUNTIME_SOURCE_KINDS),
)
def test_historical_sources_cannot_be_selected_or_used_as_fallback(
    source_kind: str,
) -> None:
    selection = Rev3ProductionSelection(
        source_kind=source_kind,
        structure_bundle_digest=_bound("structure"),
        initial_state_bundle_digest=_bound("initial"),
        owner_approval_digest=_bound("owner-approval"),
        runtime_artifact_digest=_bound("runtime"),
        fallback_source_kinds=("S5_RUNTIME",),
    )

    with pytest.raises(
        PermissionError,
        match="REV3_PRODUCTION_SELECTION_REJECTED",
    ):
        require_rev3_production_selection(selection)
    assert "REV3_QUARANTINED_SOURCE_SELECTED" in selection.validate()
    assert "REV3_PRODUCTION_FALLBACK_FORBIDDEN" in selection.validate()


def test_distilled_selection_requires_all_content_and_owner_bindings() -> None:
    missing = Rev3ProductionSelection(
        source_kind=DISTILLED_RUNTIME_SOURCE_KIND,
        structure_bundle_digest="",
        initial_state_bundle_digest="initial:not-a-digest",
        owner_approval_digest="",
        runtime_artifact_digest="",
    )

    assert require_rev3_production_selection(_valid_selection()) == (
        _valid_selection()
    )
    with pytest.raises(
        PermissionError,
        match="OWNER_APPROVAL_DIGEST_MISSING_OR_UNBOUND",
    ):
        require_rev3_production_selection(missing)


def test_production_import_boundary_rejects_all_historical_roots() -> None:
    findings = audit_rev3_production_imports(
        tuple(sorted(FORBIDDEN_PRODUCTION_IMPORT_ROOTS))
    )

    assert len(findings) == len(FORBIDDEN_PRODUCTION_IMPORT_ROOTS)
    assert audit_rev3_production_imports(
        (
            "generic_session",
            "generic_memory",
            "p_ir",
            "runtime_identity",
        )
    ) == ()


def test_rev3_guard_has_no_historical_runtime_import() -> None:
    source = (
        PACKAGE_ROOT / "arc3_agi_agent" / "rev3_governance.py"
    ).read_text(encoding="utf-8")
    tree = ast.parse(source)
    imported_roots = tuple(
        sorted(
            {
                alias.name.split(".", 1)[0]
                for node in ast.walk(tree)
                if isinstance(node, ast.Import)
                for alias in node.names
            }
            | {
                (node.module or "").lstrip(".").split(".", 1)[0]
                for node in ast.walk(tree)
                if isinstance(node, ast.ImportFrom)
            }
        )
    )

    assert audit_rev3_production_imports(imported_roots) == ()


def test_authority_sources_are_byte_bound_and_missing_inputs_are_explicit(
) -> None:
    manifest = _json(
        REPOSITORY_ROOT
        / "docs"
        / "strategy"
        / "REV3_AUTHORITY_INPUT_MANIFEST.json"
    )
    expected = {
        "AGENTS.md": (
            "89a12631099927a84098b688c677ec4958eeba0f584ff3cfd79b0484339d1b69"
        ),
        (
            "docs/strategy/"
            "ARC3_HDS蒸留先行_汎用自律完遂主体_実装仕様書_rev3.md"
        ): (
            "feea0ac2319e0776b8c34101379608a69ac6e59aefbf4f8943ee453a660ff29f"
        ),
        (
            "docs/roadmap/"
            "ARC3_HDS蒸留先行_開発ロードマップ_rev3.md"
        ): (
            "b210be684fd43c9f7a1f431e01c3cd5145e7c36301f2c55b9b2fcffc548652b2"
        ),
        "docs/architecture/AGI三主体統合設計正本_v0_2.md": (
            "2e553964fd7bfd3bc2221bc3ef70af5742c170ff29481c662bddcc983d10df44"
        ),
        "docs/architecture/工学的AGI実装仕様書_v0_2.md": (
            "a05160bba4fd2e4541d3b381fc09360bc478e1b6593decc86c299762366206f8"
        ),
        "docs/strategy/HDS蒸留仕様書_ARC2_ARC3_rev2.md": (
            "79bc7169550c94ea8d86d5004989f9d7c1d93fa173e5fad2d4df02d88fb6fc93"
        ),
        "docs/roadmap/HDS蒸留開発ロードマップ_ARC2_ARC3_rev2.md": (
            "64640eff883f417baeb2d70716e1904c1fd765a3d1a5a5eacb8bba82e3500518"
        ),
        "docs/references/HDS_FRAMEWORK_rev3_1a_INTERNAL.md": (
            "6f55471c0bb3b2b54d434ac05ac09ee24ef69fda3f2f024e5f762696e822216c"
        ),
        "docs/references/HDSフレーム_rev3_1_外向け仕様.md": (
            "d7cbbf4c981621509e124077ae66cc49bd29b2271fbf94194c6786d2a5a8724a"
        ),
        "docs/references/HDS_SelfContained_Prompt_v1_2_utf8bom.txt": (
            "33b8a35176a0cc2f18502befb4a53cfbbf378b35e36b911888fa534a8b377b50"
        ),
    }
    for path, expected_digest in expected.items():
        assert _sha256(REPOSITORY_ROOT / path) == expected_digest

    body = dict(manifest)
    claimed = str(body.pop("content_digest"))
    assert claimed == "rev3-authority-input-manifest:" + digest_object(body)
    assert manifest["missing_required_authority_count"] == 0
    assert manifest["current_phase"] == "PH-D01A"
    assert manifest["phase_effect"] == "PH_D01A_INPUT_SET_CLOSED"
    approval = _json(
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "OWNER_APPROVAL_RECORDS"
        / "PH-R00.json"
    )
    approval_body = dict(approval)
    for excluded in approval["digest_excluded_fields"]:
        approval_body.pop(excluded)
    assert approval["approval_artifact_digest"] == (
        "owner-approval-record:" + digest_object(approval_body)
    )
    assert approval["target_artifact_sha256"] == (
        "7ebd9db58f844d706f2c6cee307941250285e8871b2aa423bca60a48c6fa24eb"
    )
    assert approval["next_state"] == "OWNER_APPROVED_PASS"
    assert approval["authorization_scope"]["phase_order_must_be_preserved"]
    transition = _json(
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "PHASE_TRANSITIONS"
        / "PH-D00A_TO_PH-D00B.json"
    )
    transition_body = dict(transition)
    for excluded in transition["digest_excluded_fields"]:
        transition_body.pop(excluded)
    assert transition["content_digest"] == (
        "rev3-phase-transition:" + digest_object(transition_body)
    )
    assert transition["from_phase_state_digest"] == (
        "rev3-d00a-phase-state:"
        "bb17828cd495884a3e947f5897c4c3dec7f29fdde836889f2199be2c01449369"
    )
    assert transition["to_phase_id"] == "PH-D00B"
    assert transition["hard_gates_crossed"] == []
    transition = _json(
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "PHASE_TRANSITIONS"
        / "PH-D00B_TO_PH-D01A.json"
    )
    transition_body = dict(transition)
    for excluded in transition["digest_excluded_fields"]:
        transition_body.pop(excluded)
    assert transition["content_digest"] == (
        "rev3-phase-transition:" + digest_object(transition_body)
    )
    assert transition["from_phase_state_digest"] == (
        "rev3-d00b-phase-state:"
        "61b2108bdc0d1a9039c8ef1ddeb5eb973bd12133c53cbd0aa88477046da15d74"
    )
    assert transition["from_phase_artifact_manifest_digest"] == (
        "rev3-d00b-owner-review-artifact-manifest:"
        "864a5aebd3326dcd5b85e0127a943edc066987203c1bf5bd805327fd7710969b"
    )
    assert transition["to_phase_id"] == "PH-D01A"
    assert transition["hard_gates_crossed"] == []


def test_asset_classification_and_frame_are_content_bound() -> None:
    classification = _json(
        REPOSITORY_ROOT
        / "docs"
        / "strategy"
        / "ASSET_CLASSIFICATION_REV3.json"
    )
    classification_body = dict(classification)
    classification_digest = str(
        classification_body.pop("content_digest")
    )
    assert classification_digest == (
        "rev3-asset-classification:"
        + digest_object(classification_body)
    )
    assert classification["rev3_active_runtime_count"] == 0
    assert classification["historical_fallback_count"] == 0
    classes = {
        item["classification"]: item
        for item in classification["classifications"]
    }
    quarantine = classes["HISTORICAL_QUARANTINE"]
    assert quarantine["production_parent_allowed"] is False
    assert quarantine["fallback_allowed"] is False

    frame = _json(
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "PH-R00_WORK_BLOCK_FRAME.json"
    )
    frame_body = dict(frame)
    frame_digest = str(frame_body.pop("content_digest"))
    assert frame_digest == "rev3-work-block-frame:" + digest_object(
        frame_body
    )
    assert "analysis/autonomous_completion/**" in frame["forbidden_files"]
    assert frame["resource_budget"]["official_access_count"] == 0

    rework_frame = _json(
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "PH-R00_VALIDATION_REWORK_FRAME.json"
    )
    rework_body = dict(rework_frame)
    rework_digest = str(rework_body.pop("content_digest"))
    assert rework_digest == "rev3-work-block-frame:" + digest_object(
        rework_body
    )
    assert rework_frame["base_commit"] == (
        "8d53dcf82f39c3a38f650d57a1c14324205ed4cc"
    )
    assert "analysis/autonomous_completion/**" in rework_frame[
        "forbidden_files"
    ]
    assert rework_frame["resource_budget"]["network_submission_count"] == 0
    assert rework_frame["resource_budget"]["official_access_count"] == 0

    baseline = _json(
        REPOSITORY_ROOT
        / "analysis"
        / "rev3"
        / "pre_distillation_infrastructure_baseline.json"
    )
    baseline_body = dict(baseline)
    baseline_digest = str(baseline_body.pop("content_digest"))
    assert baseline_digest == (
        "rev3-pre-distillation-baseline:"
        + digest_object(baseline_body)
    )
    assert baseline["rev3_runtime"]["active_runtime_count"] == 0
    assert baseline["historical_p22_evidence"][
        "cv_completed_environment_count"
    ] == 0
    assert baseline["missing_required_authorities"] == []
    assert baseline["result_commit"] == (
        "e13a7f07dd7f8b9f4a23d2c4cea141a8fedb2938"
    )
    assert baseline["result_tree"] == (
        "b00d9dee4057fcc3848885fa947f77cdd0fb0ba9"
    )
    assert baseline["failed_requirement_ids"] == []
    assert baseline["validation"]["full_unit"]["status"] == "PASS"
    assert baseline["validation"]["notebook_regression"]["status"] == "PASS"
    assert baseline["validation"]["package"]["status"] == "PASS"
    assert baseline["validation"]["determinism"]["status"] == "PASS"

    rework = _json(
        REPOSITORY_ROOT
        / "analysis"
        / "rev3"
        / "ph_r00_validation_rework.json"
    )
    rework_body = dict(rework)
    rework_digest = str(rework_body.pop("content_digest"))
    assert rework_digest == (
        "rev3-r00-validation-rework:"
        + digest_object(rework_body)
    )
    assert rework["status"] == "CODEX_SELF_AUDIT_PASS"
    assert rework["failed_requirement_ids"] == []
    assert rework["implementation"]["runtime_module_count"] == 37
    assert rework["implementation"]["quarantined_module_intersection"] == []
    assert rework["validation"]["full_unit"]["passed"] == 687
    assert rework["validation"]["integration"]["passed"] == 8
    assert rework["validation"]["notebook_contract"][
        "passed_checks"
    ] == 25
    assert rework["validation"]["package"]["byte_identical"] is True
    assert rework["forbidden_activity_counts"]["official_access"] == 0
    assert rework["forbidden_activity_counts"]["network_submission"] == 0

    phase_state_path = (
        REPOSITORY_ROOT / "control" / "rev3" / "R00_PHASE_STATE.json"
    )
    approval = _json(
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "OWNER_APPROVAL_RECORDS"
        / "PH-R00.json"
    )
    phase_state = _json(phase_state_path)
    phase_state_body = dict(phase_state)
    phase_state_digest = str(phase_state_body.pop("content_digest"))
    assert phase_state_digest == (
        "rev3-r00-phase-state:"
        + digest_object(phase_state_body)
    )
    assert phase_state["status"] == "OWNER_APPROVED_PASS"
    assert phase_state["result_commit"] == rework["result_commit"]
    assert phase_state["result_tree"] == rework["result_tree"]
    assert phase_state["failed_requirement_ids"] == []
    assert phase_state["self_audit"]["codex_self_audit_pass"] is True
    phase_invariants = phase_state["phase_invariants"]
    assert phase_invariants["current_head_bound"] is True
    assert phase_invariants["uncommitted_phase_evidence_count"] == 0
    assert (
        phase_invariants["active_runtime_capability_claim"]
        == "NOT_ESTABLISHED"
    )
    assert phase_invariants[
        "quarantined_s5_dependency_in_production"
    ] == 0
    assert phase_invariants["next_phase"] == "PH-D00A"
    assert phase_invariants["next_phase_started"] is True
    assert phase_invariants["owner_approval"] == "recorded"
    assert phase_invariants["owner_approval_digest"] == (
        approval["approval_artifact_digest"]
    )
    assert phase_state_path.read_bytes() == (
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "OWNER_REVIEW_PACKAGE"
        / "phase_state.json"
    ).read_bytes()

    artifact_manifest = _json(
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "OWNER_REVIEW_PACKAGE"
        / "artifact_manifest.json"
    )
    artifact_manifest_body = dict(artifact_manifest)
    artifact_manifest_digest = str(
        artifact_manifest_body.pop("content_digest")
    )
    assert artifact_manifest_digest == (
        "rev3-r00-owner-review-artifact-manifest:"
        + digest_object(artifact_manifest_body)
    )
    assert artifact_manifest["manifest_excludes_self"] is True
    assert all(
        _git_blob_sha256(
            str(artifact_manifest["snapshot_commit"]),
            str(item["path"]),
        )
        == item["sha256"]
        for item in artifact_manifest["artifacts"]
    )


def test_d00b_phase_state_and_snapshot_manifest_are_content_bound() -> None:
    phase_state_path = (
        REPOSITORY_ROOT / "control" / "rev3" / "D00B_PHASE_STATE.json"
    )
    phase_state = _json(phase_state_path)
    phase_state_body = dict(phase_state)
    phase_state_digest = str(phase_state_body.pop("content_digest"))
    assert phase_state_digest == (
        "rev3-d00b-phase-state:" + digest_object(phase_state_body)
    )
    assert phase_state["status"] == "CODEX_SELF_AUDIT_PASS"
    assert phase_state["result_commit"] == (
        "cc189737ce93796936ca06f386da8aa0fc5af7f4"
    )
    assert phase_state["result_tree"] == (
        "0000051e891522a0ebd4c713557e2e220fd5b1df"
    )
    assert phase_state["failed_requirement_ids"] == []
    assert phase_state["phase_invariants"]["scope_guard_pass"] is True
    assert phase_state["phase_invariants"][
        "scope_guard_finding_count"
    ] == 0
    assert phase_state["phase_invariants"][
        "audited_source_execution_count"
    ] == 0
    assert phase_state_path.read_bytes() == (
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "PH-D00B_OWNER_REVIEW_PACKAGE"
        / "phase_state.json"
    ).read_bytes()

    artifact_manifest = _json(
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "PH-D00B_OWNER_REVIEW_PACKAGE"
        / "artifact_manifest.json"
    )
    artifact_manifest_body = dict(artifact_manifest)
    artifact_manifest_digest = str(
        artifact_manifest_body.pop("content_digest")
    )
    assert artifact_manifest_digest == (
        "rev3-d00b-owner-review-artifact-manifest:"
        + digest_object(artifact_manifest_body)
    )
    assert artifact_manifest["snapshot_commit"] == (
        "74a5c06fc2f4b0bc31e4ac4f6dd77aa06ed28dca"
    )
    assert artifact_manifest["snapshot_tree"] == (
        "0672784c121f0a3eddce5bd4d95246b439cc8c72"
    )
    assert artifact_manifest["artifact_count"] == 26
    assert artifact_manifest["manifest_excludes_self"] is True
    assert all(
        _git_blob_sha256(
            str(artifact_manifest["snapshot_commit"]),
            str(item["path"]),
        )
        == item["sha256"]
        for item in artifact_manifest["artifacts"]
    )


def test_d01a_source_inventory_and_phase_state_are_content_bound() -> None:
    frame = _json(
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "PH-D01A_WORK_BLOCK_FRAME.json"
    )
    frame_body = dict(frame)
    frame_digest = str(frame_body.pop("content_digest"))
    assert frame_digest == (
        "rev3-work-block-frame:" + digest_object(frame_body)
    )
    assert frame_digest == (
        "rev3-work-block-frame:"
        "c8ba581776540af64fec89f641d28334adc24c77d89d5ad4214e8c7a43ddc4d9"
    )
    assert frame["phase_id"] == "PH-D01A"
    assert frame["resource_budget"]["arc_source_payload_parse_count"] == 0
    assert frame["resource_budget"][
        "arc_environment_source_execution_count"
    ] == 0

    preinventory = _json(
        REPOSITORY_ROOT
        / "analysis"
        / "rev3"
        / "ph_d01a_source_preinventory.json"
    )
    preinventory_body = dict(preinventory)
    preinventory_digest = str(
        preinventory_body.pop("content_digest")
    )
    assert preinventory_digest == (
        "rev3-ph-d01a-source-preinventory:"
        + digest_object(preinventory_body)
    )
    assert preinventory_digest == (
        "rev3-ph-d01a-source-preinventory:"
        "33fccaaedb4c3eb0a5640176da27577c91a96c14a93d0abc69211bb32e014918"
    )

    plan = _json(
        REPOSITORY_ROOT
        / "distillation"
        / "input"
        / "source_inventory_plan.json"
    )
    plan_body = dict(plan)
    plan_digest = str(plan_body.pop("content_digest"))
    assert plan_digest == (
        "hds-source-inventory-plan:" + digest_object(plan_body)
    )
    assert plan_digest == (
        "hds-source-inventory-plan:"
        "ef0394a2389a0fdeec3402c9a7f227a14758964e61fadba25c41422f49ea0215"
    )

    profile_paths = sorted(
        (
            REPOSITORY_ROOT
            / "distillation"
            / "profiles"
            / "source"
        ).glob("*.json")
    )
    assert len(profile_paths) == 8
    profile_ids: set[str] = set()
    for path in profile_paths:
        profile = _json(path)
        profile_body = dict(profile)
        profile_digest = str(profile_body.pop("content_digest"))
        assert profile_digest == (
            "hds-source-profile:" + digest_object(profile_body)
        )
        profile_ids.add(str(profile["profile_id"]))
    assert len(profile_ids) == 8

    report = _json(
        REPOSITORY_ROOT
        / "distillation"
        / "artifacts"
        / "reports"
        / "source_inventory.json"
    )
    report_body = dict(report)
    for excluded in report["digest_excluded_fields"]:
        report_body.pop(str(excluded))
    assert report["content_digest"] == (
        "hds-source-inventory-report:" + digest_object(report_body)
    )
    assert report["content_digest"] == (
        "hds-source-inventory-report:"
        "ca27293b57737c743020ad19e063b08cd75d0d0c6d6571e67c6b5934c9f67d79"
    )
    assert report["phase_exit_claim"] == (
        "PH_D01A_SOURCE_INVENTORY_PASS"
    )
    assert report["source_count"] == 83
    assert report["profile_count"] == 8
    assert report["accounting"]["repository_candidate_file_count"] == 151
    assert report["accounting"]["repository_admitted_source_count"] == 53
    assert report["accounting"][
        "repository_excluded_non_source_count"
    ] == 98
    assert report["public_evaluation_consumed_source_count"] == 28
    assert report["policy_weight_admitted_source_count"] == 0
    assert report["environment_source_non_replay_access_count"] == 0
    assert report["duplicate_source_assignment_count"] == 0
    assert report["unassigned_admitted_source_count"] == 0
    assert report["unknown_answer_visibility_count"] == 0
    assert report["unknown_split_role_count"] == 0
    assert report["source_payload_access"] == {
        "payload_parse_count": 0,
        "replay_execution_count": 0,
        "source_execution_count": 0,
    }
    assert report["phase_boundaries"]["content_manifest_frozen"] is False
    assert report["phase_boundaries"][
        "environment_manifest_frozen"
    ] is False
    assert report["phase_boundaries"][
        "trajectory_normalization_started"
    ] is False

    phase_state_path = (
        REPOSITORY_ROOT / "control" / "rev3" / "D01A_PHASE_STATE.json"
    )
    phase_state = _json(phase_state_path)
    phase_state_body = dict(phase_state)
    phase_state_digest = str(phase_state_body.pop("content_digest"))
    assert phase_state_digest == (
        "rev3-d01a-phase-state:" + digest_object(phase_state_body)
    )
    assert phase_state["status"] == "CODEX_SELF_AUDIT_PASS"
    assert phase_state["result_commit"] == (
        "e71cdd45b7263c2ec77a8b6008140e2db774d286"
    )
    assert phase_state["result_tree"] == (
        "b811529a0aae10c3464282fabda9679113121dbd"
    )
    assert phase_state["failed_requirement_ids"] == []
    invariants = phase_state["phase_invariants"]
    assert invariants["source_count"] == 83
    assert invariants["duplicate_source_assignment_count"] == 0
    assert invariants["unassigned_admitted_source_count"] == 0
    assert invariants["unknown_answer_visibility_count"] == 0
    assert invariants["unknown_split_role_count"] == 0
    assert invariants["policy_weight_admitted_source_count"] == 0
    assert invariants["source_payload_parse_count"] == 0
    assert invariants["source_execution_count"] == 0
    assert invariants["replay_execution_count"] == 0
    assert invariants["next_phase"] == "PH-D01B"
    assert invariants["next_phase_started"] is False
    assert "PH_D01A_SOURCE_INVENTORY_PASS" in phase_state[
        "claim_allowed"
    ]
    assert "ARC3_TEACHER_SOURCE_FROZEN" in phase_state[
        "claim_prohibited"
    ]
    assert phase_state_path.read_bytes() == (
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "PH-D01A_OWNER_REVIEW_PACKAGE"
        / "phase_state.json"
    ).read_bytes()

    artifact_manifest = _json(
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "PH-D01A_OWNER_REVIEW_PACKAGE"
        / "artifact_manifest.json"
    )
    artifact_manifest_body = dict(artifact_manifest)
    artifact_manifest_digest = str(
        artifact_manifest_body.pop("content_digest")
    )
    assert artifact_manifest_digest == (
        "rev3-d01a-owner-review-artifact-manifest:"
        + digest_object(artifact_manifest_body)
    )
    assert artifact_manifest_digest == (
        "rev3-d01a-owner-review-artifact-manifest:"
        "078fc8e6273bc4ab86888f3b51d5db4f48be71e7d1f787f4607706fded305ebe"
    )
    assert artifact_manifest["snapshot_commit"] == (
        "50b8259fce783fc2cc28158756a020575eb5e25d"
    )
    assert artifact_manifest["snapshot_tree"] == (
        "caa5aed687475bd188b32863c61a0afcc66c3d34"
    )
    assert artifact_manifest["artifact_count"] == 30
    assert artifact_manifest["manifest_excludes_self"] is True
    assert all(
        _git_blob_sha256(
            str(artifact_manifest["snapshot_commit"]),
            str(item["path"]),
        )
        == item["sha256"]
        for item in artifact_manifest["artifacts"]
    )
