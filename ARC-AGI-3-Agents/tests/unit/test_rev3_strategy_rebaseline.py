from __future__ import annotations

import ast
import hashlib
import json
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
    assert REV3_ACTIVE_PHASE == "PH-D00A"
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
            "c2697a07c2c002680bd11240dcf4960108cdb248ba1e1fa84e44c95ecd18d6c8"
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
    assert manifest["current_phase"] == "PH-D00A"
    assert manifest["phase_effect"] == "PH_D00A_INPUT_SET_CLOSED"
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
        _sha256(REPOSITORY_ROOT / item["path"]) == item["sha256"]
        for item in artifact_manifest["artifacts"]
    )
