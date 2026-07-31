from __future__ import annotations

import ast
import hashlib
import json
import subprocess
import sys
from pathlib import Path
from typing import Any
from zipfile import ZipFile

import pytest

from arc3_agi_agent.rev3_governance import (
    DISTILLED_RUNTIME_SOURCE_KIND,
    FORBIDDEN_PRODUCTION_IMPORT_ROOTS,
    QUARANTINED_RUNTIME_SOURCE_KINDS,
    REV3_ACTIVE_PHASE,
    REV3_CURRENT_WORK_CLASS,
    REV3_DISTILLED_INITIAL_STATE_BUNDLE_STATUS,
    REV3_INSTALLATION_STATUS,
    REV3_PH_D00A_STATUS,
    REV3_PH_D00B_STATUS,
    REV3_PH_D01A_STATUS,
    REV3_PH_R00_OWNER_AUTHORIZATION,
    REV3_PH_R00_STATUS,
    REV3_PH_R1_STATUS,
    REV3_PHASE_ORDER,
    REV3_RUNTIME_ACTIVATION_STATUS,
    REV3_STRATEGY_STATUS,
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
    assert REV3_STRATEGY_STATUS == "OWNER_APPROVED"
    assert REV3_INSTALLATION_STATUS == "INSTALLED"
    assert REV3_CURRENT_WORK_CLASS == (
        "PH-D01A_PRIMARY_SOURCE_INVENTORY_REBIND"
    )
    assert REV3_ACTIVE_PHASE == "PH-D01A"
    assert REV3_PH_R1_STATUS == "OWNER_APPROVED_PASS"
    assert REV3_PH_R00_STATUS == "OWNER_APPROVED_PASS"
    assert REV3_PH_R00_OWNER_AUTHORIZATION == "ESTABLISHED"
    assert REV3_PH_D00A_STATUS == "OWNER_APPROVED_PASS"
    assert REV3_PH_D00B_STATUS == "OWNER_APPROVED_PASS"
    assert REV3_PH_D01A_STATUS == "IN_PROGRESS"
    assert REV3_DISTILLED_INITIAL_STATE_BUNDLE_STATUS == "NOT_FROZEN"
    assert REV3_RUNTIME_ACTIVATION_STATUS == "SUSPEND"
    assert REV3_PHASE_ORDER[0] == "PH-R-1"
    assert REV3_PHASE_ORDER[1] == "PH-R00"
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


def test_rev3_audit_correction_selector_and_contracts_fail_closed() -> None:
    selector = _json(
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "REV3_CURRENT_SELECTOR.json"
    )
    assert selector["strategy_status"] == REV3_STRATEGY_STATUS
    assert selector["installation_status"] == REV3_INSTALLATION_STATUS
    assert selector["current_work_class"] == REV3_CURRENT_WORK_CLASS
    assert selector["active_phase"] == REV3_ACTIVE_PHASE
    assert selector["ph_r00_status"] == REV3_PH_R00_STATUS
    assert selector["ph_r1_status"] == REV3_PH_R1_STATUS
    assert selector["ph_r00_owner_authorization"] == (
        REV3_PH_R00_OWNER_AUTHORIZATION
    )
    assert selector["ph_d00a_status"] == REV3_PH_D00A_STATUS
    assert selector["ph_d00b_status"] == REV3_PH_D00B_STATUS
    assert selector["ph_d01a_status"] == REV3_PH_D01A_STATUS
    assert selector["distilled_initial_state_bundle_status"] == (
        REV3_DISTILLED_INITIAL_STATE_BUNDLE_STATUS
    )
    assert selector["runtime_activation_status"] == (
        REV3_RUNTIME_ACTIVATION_STATUS
    )
    assert selector["installation_approval"][
        "approval_artifact_digest"
    ] == (
        "owner-approval-record:"
        "32de1b2446b1dfc5fdecd187a65077cbb5f1569a115aa6dbebfc08ad3b1970b8"
    )
    assert (
        selector["historical_evidence"]["classification"]
        == "HISTORICAL_PRE_AUDIT_NONAUTHORITATIVE"
    )
    assert not selector["historical_evidence"][
        "eligible_for_current_activation"
    ]
    assert "docs/strategy/REV3_AUTHORITY_INPUT_MANIFEST.json" in (
        selector["historical_evidence"]["scope"]
    )
    assert "distillation/artifacts/reports/primary_source_provenance.json" in (
        selector["current_phase_candidates"]["paths"]
    )
    assert selector["current_phase_candidates"][
        "eligible_for_phase_exit"
    ] is False

    contract_root = (
        REPOSITORY_ROOT / "docs" / "strategy" / "contracts"
    )
    governance = _json(
        contract_root / "REV3_GOVERNANCE_CONTRACT_V1.json"
    )
    assert governance["git_evidence_model"]["self_reference_policy"] == (
        "REJECT"
    )
    assert governance["owner_decision_policy"][
        "codex_may_generate_decision"
    ] is False
    assert governance["source_blind_roles"]["DISTILLATION_EXECUTOR"][
        "environment_source_mount"
    ] is False

    bundle = _json(
        contract_root / "HDS_STRUCTURE_BUNDLE_CONTRACT_V1.json"
    )
    assert bundle["package_policy"]["unknown_file_policy"] == "REJECT"
    assert bundle["package_policy"]["partial_bundle_policy"] == "REJECT"
    mechanism = bundle["record_schemas"]["MechanismAssetRecord"]
    assert mechanism["single_primary_class"]
    assert mechanism["evidence_scoring"] == (
        "UNIQUE_EVIDENCE_REF_ONCE_ACROSS_ALL_PROJECTIONS"
    )

    profile = _json(contract_root / "AGI_BUILD_READY_PROFILE_V1.json")
    assert profile["profile_status"] == (
        "OWNER_APPROVED_CONTRACT_NOT_YET_EVALUATED"
    )
    assert profile["profile_approval_binding"][
        "evaluation_status"
    ] == "NOT_EVALUATED"
    assert not profile["owner_approval_may_bypass_hard_minimum"]
    assert all(
        category["hard_mandatory"]
        and category["allowed_unresolved_ratio"] == 0.0
        for category in profile["categories"]
    )

    cv_contract = _json(
        contract_root / "MECHANISM_FAMILY_CV_CONTRACT_V1.json"
    )
    assert cv_contract["required_global_invariants"][
        "distinct_runtime_identity_count"
    ] == "EQUALS_FOLD_COUNT"
    assert not cv_contract["claim_boundary"][
        "single_artifact_claim_allowed"
    ]


def test_ph_r1_owner_decision_and_approval_are_content_bound() -> None:
    capture = _json(
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "OWNER_DECISION_CAPTURES"
        / "REV3_DOC_FIX_TO_PH-R-1_20260731.json"
    )
    capture_body = dict(capture)
    for excluded in capture["digest_excluded_fields"]:
        capture_body.pop(str(excluded))
    assert capture["owner_decision_content_digest"] == (
        "sha256:" + digest_object(capture_body)
    )
    assert capture["source_instruction_digest"] == (
        "sha256:"
        + hashlib.sha256("全部承認".encode("utf-8")).hexdigest()
    )
    assert capture["target_evidence_commit"] == (
        "95c8fb0f1551716191769747d65816e273cf7640"
    )
    assert capture["target_artifact_digest"] == (
        "sha256:"
        "3fe2ae584a5df80ac80e6f44b66446f7ad11e926530a552a98b4d7643041e219"
    )

    approval = _json(
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "OWNER_APPROVAL_RECORDS"
        / "REV3_DOC_FIX_TO_PH-R-1_20260731.json"
    )
    approval_body = dict(approval)
    for excluded in approval["digest_excluded_fields"]:
        approval_body.pop(str(excluded))
    assert approval["approval_artifact_digest"] == (
        "owner-approval-record:" + digest_object(approval_body)
    )
    assert approval["owner_decision_capture_digest"] == (
        capture["owner_decision_content_digest"]
    )
    assert approval["next_phase_id"] == "PH-R-1"
    assert approval["next_phase_authorized"] is True
    assert approval["future_phase_approval_scope"] == "NONE"

    attestation = _json(
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "REV3_DOC_FIX_EVIDENCE_ATTESTATION.json"
    )
    assert attestation["evidence"]["commit"] == (
        capture["target_evidence_commit"]
    )
    assert attestation["evidence"]["payload_digest"] == (
        capture["target_artifact_digest"]
    )


def test_ph_r1_schemas_reject_unbound_or_self_referential_state() -> None:
    contract_root = (
        REPOSITORY_ROOT / "docs" / "strategy" / "contracts"
    )
    phase_schema = _json(contract_root / "PHASE_STATE_SCHEMA_V2.json")
    assert phase_schema["additionalProperties"] is False
    assert "evidence_commit" not in phase_schema["properties"]
    assert "evidence_tree" not in phase_schema["properties"]
    assert set(
        (
            "implementation_commit",
            "implementation_tree",
            "evidence_payload_digest",
        )
    ).issubset(phase_schema["required"])

    attestation_schema = _json(
        contract_root / "EVIDENCE_COMMIT_ATTESTATION_SCHEMA_V1.json"
    )
    assert attestation_schema["additionalProperties"] is False
    assert attestation_schema["properties"]["self_reference_avoided"][
        "const"
    ] is True

    approval_schema = _json(
        contract_root / "APPROVAL_RECORD_SCHEMA_V1.json"
    )
    assert approval_schema["additionalProperties"] is False
    assert "approval_commit" not in approval_schema["properties"]
    assert approval_schema["properties"]["digest_excluded_fields"][
        "const"
    ] == ["approval_artifact_digest"]

    selector_schema = _json(
        contract_root / "REV3_CURRENT_SELECTOR_SCHEMA_V7.json"
    )
    assert selector_schema["additionalProperties"] is False
    assert selector_schema["properties"]["active_phase"]["const"] == (
        "PH-D01A"
    )
    assert selector_schema["properties"][
        "ph_r00_owner_authorization"
    ]["const"] == "ESTABLISHED"

    standing_schema = _json(
        contract_root / "OWNER_STANDING_AUTHORIZATION_SCHEMA_V1.json"
    )
    assert standing_schema["additionalProperties"] is False
    scope = standing_schema["properties"]["authorization_scope"]
    assert scope["properties"]["artifact_binding_policy"]["const"] == (
        "EXACT_DIGEST_CAPTURE_REQUIRED"
    )
    assert scope["properties"]["external_irreversible_actions"][
        "const"
    ] == (
        "EXCLUDED_REQUIRES_SEPARATE_EXPLICIT_EXECUTION_INSTRUCTION"
    )

    capture_v2 = _json(
        contract_root / "OWNER_DECISION_CAPTURE_SCHEMA_V2.json"
    )
    assert capture_v2["additionalProperties"] is False
    assert capture_v2["properties"]["decision_basis"]["const"] == (
        "OWNER_STANDING_AUTHORIZATION"
    )
    assert capture_v2["properties"]["gate_status"]["const"] == "PASS"


def test_rev3_strategy_package_is_deterministic_and_ascii_safe(
    tmp_path: Path,
) -> None:
    first = tmp_path / "first.zip"
    second = tmp_path / "second.zip"
    script = REPOSITORY_ROOT / "scripts" / "package_rev3_strategy.py"
    for output in (first, second):
        subprocess.run(
            [sys.executable, str(script), "--output", str(output)],
            cwd=REPOSITORY_ROOT,
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

    assert first.read_bytes() == second.read_bytes()
    committed = (
        REPOSITORY_ROOT
        / "artifacts"
        / "rev3"
        / "arc3_hds_distillation_first_strategy_rev3_corrected.zip"
    )
    assert first.read_bytes() == committed.read_bytes()
    with ZipFile(first) as archive:
        names = archive.namelist()
        assert "MANIFEST.json" in names
        assert "SHA256SUMS" in names
        assert all(name.isascii() for name in names)
        assert len(names) == len(set(names))
        manifest = json.loads(archive.read("MANIFEST.json"))
        assert manifest["package_status"] == (
            "PROPOSED_PENDING_OWNER_APPROVAL"
        )
        assert manifest["installation_status"] == "NOT_INSTALLED"
        assert manifest["entry_count"] == len(names) - 2
        checksums = archive.read("SHA256SUMS").decode("ascii").splitlines()
        assert len(checksums) == len(names) - 1


def test_installed_rev3_governance_validator_passes() -> None:
    script = REPOSITORY_ROOT / "scripts" / "validate_rev3_governance.py"
    result = subprocess.run(
        [sys.executable, str(script)],
        cwd=REPOSITORY_ROOT,
        check=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )
    report = json.loads(result.stdout)
    assert report["status"] == "PASS"
    assert report["failure_count"] == 0
    assert report["check_count"] >= 12


def test_rev3_corrected_documents_close_audit_findings() -> None:
    document_paths = (
        REPOSITORY_ROOT / "AGENTS.md",
        REPOSITORY_ROOT
        / "docs"
        / "strategy"
        / "ARC3_HDS蒸留先行_汎用自律完遂主体_実装仕様書_rev3.md",
        REPOSITORY_ROOT
        / "docs"
        / "roadmap"
        / "ARC3_HDS蒸留先行_開発ロードマップ_rev3.md",
        REPOSITORY_ROOT
        / "docs"
        / "strategy"
        / "ARC3_HDS蒸留先行_戦略改定_INDEX_rev3.md",
        REPOSITORY_ROOT / "AUTHORITY_ORDER.md",
    )
    combined = "\n".join(
        path.read_text(encoding="utf-8") for path in document_paths
    )
    assert "Strategy = OWNER_APPROVED" in combined
    assert "Installation = INSTALLED" in combined
    assert (
        "Current work = PH-D00A_HDS_DEPENDENCY_AUTHORITY_REBIND"
        in combined
    )
    assert "PH-R00 Owner authorization = ESTABLISHED" in combined
    assert "PROPOSED_PENDING_OWNER_APPROVAL" not in combined
    assert "NOT_INSTALLED" not in combined
    for required in (
        "PH-R00 = OWNER_APPROVED_PASS",
        "PH-D00A = IN_PROGRESS",
        "Normative Authority",
        "Execution Control",
        "Implementation Commit",
        "Evidence Commit",
        "OwnerDecisionCapture",
        "Primary Teacher Source",
        "Derived Distillation Evidence",
        "Governance Artifacts",
        "Relevant Memory Causal Witness",
        "Irrelevant Memory Invariance",
        "target_projections",
        "J_CORE_OWNER_FROZEN",
        "fold-specific HDSStructureBundle",
        "LockedEvaluatorCustodian",
        "legal action mask",
        "MANIFEST.json",
        "SHA256SUMS",
    ):
        assert required in combined

    roadmap = document_paths[2].read_text(encoding="utf-8")
    for phase_id in (
        "PH-D01A",
        "PH-D01B",
        "PH-D02A",
        "PH-D02B",
        "PH-D02C",
        "PH-D03A",
        "PH-D03B",
        "PH-D07A",
        "PH-D07B",
        "PH-D09",
        "PH-D10",
        "PH-D11",
    ):
        assert f"## {phase_id} " in roadmap
    for forbidden in (
        "## PH-D01A/B",
        "## PH-D02A/B/C",
        "## PH-D03A/B",
        "## PH-D07A/B",
        "## PH-D09〜D11",
    ):
        assert forbidden not in roadmap


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


def test_distilled_selection_requires_bindings_and_runtime_gates() -> None:
    missing = Rev3ProductionSelection(
        source_kind=DISTILLED_RUNTIME_SOURCE_KIND,
        structure_bundle_digest="",
        initial_state_bundle_digest="initial:not-a-digest",
        owner_approval_digest="",
        runtime_artifact_digest="",
    )

    with pytest.raises(
        PermissionError,
        match="REV3_INITIAL_STATE_BUNDLE_NOT_FROZEN:NOT_FROZEN",
    ):
        require_rev3_production_selection(_valid_selection())
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
    historical_expected = {
        "AGENTS.md": (
            "7ad183110f39ffda02c6209be85fb1537872b23b018b20f8cea4e22a35313b5a"
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
    }
    selector = _json(
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "REV3_CURRENT_SELECTOR.json"
    )
    for path, expected_digest in historical_expected.items():
        assert (
            _git_blob_sha256(selector["audit_baseline_commit"], path)
            == expected_digest
        )

    expected = {
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
    assert manifest["current_phase"] == "PH-D03A"
    assert manifest["phase_effect"] == "PH_D03A_INPUT_SET_CLOSED"
    assert manifest["phase_transition"] == {
        "path": (
            "control/rev3/PHASE_TRANSITIONS/"
            "PH-D02C_TO_PH-D03A.json"
        ),
        "sha256": (
            "ed95b8f9c432a30c0a1f1980cf298d53fb0a2718ee52eb011152183f096df9cc"
        ),
        "content_digest": (
            "rev3-phase-transition:"
            "ca1c282e9c43f61cc41bd378862b3a0965096ab5e3e9877976dd82395dd93110"
        ),
    }
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
        / "HISTORICAL_PRE_AUDIT"
        / "PH-D00B"
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
        / "HISTORICAL_PRE_AUDIT"
        / "PH-D00B"
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
    transition = _json(
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "HISTORICAL_PRE_AUDIT"
        / "PH-D01A"
        / "PHASE_TRANSITIONS"
        / "PH-D01A_TO_PH-D01B.json"
    )
    transition_body = dict(transition)
    for excluded in transition["digest_excluded_fields"]:
        transition_body.pop(excluded)
    assert transition["content_digest"] == (
        "rev3-phase-transition:" + digest_object(transition_body)
    )
    assert transition["from_phase_state_digest"] == (
        "rev3-d01a-phase-state:"
        "00b10b0b2bdfe27506562a8ed1dd75fa9f3f0d463ee269084b5e26c4d0eab62a"
    )
    assert transition["from_phase_artifact_manifest_digest"] == (
        "rev3-d01a-owner-review-artifact-manifest:"
        "078fc8e6273bc4ab86888f3b51d5db4f48be71e7d1f787f4607706fded305ebe"
    )
    assert transition["to_phase_id"] == "PH-D01B"
    assert transition["hard_gates_crossed"] == []
    transition = _json(
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "PHASE_TRANSITIONS"
        / "PH-D01B_TO_PH-D02A.json"
    )
    transition_body = dict(transition)
    for excluded in transition["digest_excluded_fields"]:
        transition_body.pop(excluded)
    assert transition["content_digest"] == (
        "rev3-phase-transition:" + digest_object(transition_body)
    )
    assert transition["from_phase_state_digest"] == (
        "rev3-d01b-phase-state:"
        "68eea37dcce3d09d1e21b1a43ef5d92b091f1960ee5fffb42507c07e0fe25220"
    )
    assert transition["from_phase_artifact_manifest_digest"] == (
        "rev3-d01b-owner-review-artifact-manifest:"
        "71bb9d735a0b608ded78397e8d1620e0140aa7e27de000df7117ab12ca3069a8"
    )
    assert transition["to_phase_id"] == "PH-D02A"
    assert transition["hard_gates_crossed"] == []
    transition = _json(
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "PHASE_TRANSITIONS"
        / "PH-D02A_TO_PH-D02B.json"
    )
    transition_body = dict(transition)
    for excluded in transition["digest_excluded_fields"]:
        transition_body.pop(excluded)
    assert transition["content_digest"] == (
        "rev3-phase-transition:" + digest_object(transition_body)
    )
    assert transition["from_phase_state_digest"] == (
        "rev3-d02a-phase-state:"
        "ad044d4726bb26c5a097d651704f3e7454a5480173d05711ab21a70d5f137890"
    )
    assert transition["from_phase_artifact_manifest_digest"] == (
        "rev3-d02a-owner-review-artifact-manifest:"
        "3788baffae208894e511d7f0b2ca244befe8eacabcb21e8a459f99f226b9d0ba"
    )
    assert transition["to_phase_id"] == "PH-D02B"
    assert transition["hard_gates_crossed"] == []
    transition = _json(
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "PHASE_TRANSITIONS"
        / "PH-D02B_TO_PH-D02C.json"
    )
    transition_body = dict(transition)
    for excluded in transition["digest_excluded_fields"]:
        transition_body.pop(excluded)
    assert transition["content_digest"] == (
        "rev3-phase-transition:" + digest_object(transition_body)
    )
    assert transition["from_phase_state_digest"] == (
        "rev3-d02b-phase-state:"
        "3946f264bad10ffee665c8b378400a9630a57278bed173cdf5045249089082a2"
    )
    assert transition["from_phase_artifact_manifest_digest"] == (
        "rev3-d02b-owner-review-artifact-manifest:"
        "966d85f68980c476f78ab5bec4e92546eac0527e06c24feec39807cae671c21a"
    )
    assert transition["to_phase_id"] == "PH-D02C"
    assert transition["hard_gates_crossed"] == []
    transition = _json(
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "PHASE_TRANSITIONS"
        / "PH-D02C_TO_PH-D03A.json"
    )
    transition_body = dict(transition)
    for excluded in transition["digest_excluded_fields"]:
        transition_body.pop(excluded)
    assert transition["content_digest"] == (
        "rev3-phase-transition:" + digest_object(transition_body)
    )
    assert transition["from_phase_state_digest"] == (
        "rev3-d02c-phase-state:"
        "bd01666bf05b5e40a8fe896cc4078814d4ddbcbc63f47c7dd705d4ec5eeb66c8"
    )
    assert transition["from_phase_artifact_manifest_digest"] == (
        "rev3-d02c-owner-review-artifact-manifest:"
        "8d1dce7eb8385d8e72fdc2b8fd7ee24b1bc45ff5c9c6c4208d18d74bc7cf0361"
    )
    assert transition["to_phase_id"] == "PH-D03A"
    assert transition["to_phase_scope"] == (
        "GOLDEN_CANDIDATE_CONSTRUCTION_AND_VALIDATION_"
        "PENDING_CONTENT_SPECIFIC_OWNER_APPROVAL"
    )
    assert transition["hard_gates_crossed"] == []


def test_ph_d03a_candidate_preinventory_and_frame_are_content_bound() -> None:
    preinventory = _json(
        REPOSITORY_ROOT
        / "analysis"
        / "rev3"
        / "ph_d03a_golden_preinventory.json"
    )
    preinventory_body = dict(preinventory)
    for excluded in preinventory["digest_excluded_fields"]:
        preinventory_body.pop(str(excluded))
    assert preinventory["content_digest"] == (
        "rev3-ph-d03a-golden-preinventory:"
        + digest_object(preinventory_body)
    )
    assert preinventory["content_digest"] == (
        "rev3-ph-d03a-golden-preinventory:"
        "102465e690258f967061b70d2023ec9645818c6e68558c01ca6c74a6b7245104"
    )
    cases = preinventory["required_case_inventory"]
    assert len(cases) == 16
    assert sum(case["domain"] == "ARC2" for case in cases) == 8
    assert sum(case["domain"] == "ARC3" for case in cases) == 8
    assert len({case["case_id"] for case in cases}) == 16
    assert preinventory["required_gate_coverage"] == [
        f"DG-{index:02d}" for index in range(16)
    ]
    approval = preinventory["approval_boundary"]
    assert approval["existing_content_specific_golden_approval_count"] == 0
    assert approval["allowed_candidate_state"] == (
        "PROPOSED_PENDING_OWNER_APPROVAL"
    )
    assert approval["owner_recorded_approval_may_be_generated_by_codex"] is (
        False
    )
    assert approval[
        "golden_expected_artifact_freeze_allowed_without_owner_record"
    ] is False

    frame = _json(
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "PH-D03A_WORK_BLOCK_FRAME.json"
    )
    frame_body = dict(frame)
    for excluded in frame["digest_excluded_fields"]:
        frame_body.pop(str(excluded))
    assert frame["content_digest"] == (
        "rev3-work-block-frame:" + digest_object(frame_body)
    )
    assert frame["content_digest"] == (
        "rev3-work-block-frame:"
        "ce4de522b3e5d269d5f80b260e0b0bf24586f0965207149d2043742c2a7b9132"
    )
    assert frame["phase_id"] == "PH-D03A"
    assert frame["preinventory_digest"] == preinventory["content_digest"]
    budget = frame["resource_budget"]
    assert budget["required_arc2_case_count"] == 8
    assert budget["required_arc3_case_count"] == 8
    assert budget["required_total_case_count"] == 16
    assert budget["required_gate_count"] == 16
    assert budget["owner_approval_generation_count"] == 0
    assert budget["golden_expected_artifact_freeze_count"] == 0
    assert budget["sealed_corpus_artifact_count"] == 0
    assert budget["source_payload_read_count"] == 0
    assert budget["teacher_trajectory_read_count"] == 0
    assert budget["real_intervention_execution_count"] == 0
    assert budget["general_candidate_generation_count"] == 0
    assert budget["rule_promotion_count"] == 0
    assert budget["locked_final_access_count"] == 0
    assert budget["official_access_count"] == 0
    assert budget["network_submission_count"] == 0
    assert budget["kaggle_mutation_count"] == 0
    owner_review = frame["owner_review"]
    assert owner_review["content_specific_golden_approval_present"] is False
    assert owner_review[
        "content_specific_owner_decision_required_for_freeze"
    ] is True
    assert owner_review["hard_gate_approval_delegated"] is False
    assert owner_review["codex_may_generate_owner_recorded_approval"] is False
    assert owner_review["codex_may_freeze_golden_expectations"] is False
    assert owner_review[
        "codex_may_auto_update_approved_expectations"
    ] is False


def test_ph_d03a_checked_candidates_remain_non_authoritative() -> None:
    contract = _json(
        REPOSITORY_ROOT
        / "distillation"
        / "input"
        / "golden_conformance_contract.json"
    )
    candidate_set = _json(
        REPOSITORY_ROOT
        / "distillation"
        / "artifacts"
        / "golden"
        / "candidate_cases.json"
    )
    coverage = _json(
        REPOSITORY_ROOT
        / "distillation"
        / "artifacts"
        / "reports"
        / "golden_gate_coverage.json"
    )
    review = _json(
        REPOSITORY_ROOT
        / "distillation"
        / "artifacts"
        / "golden"
        / "owner_review_request.json"
    )

    assert contract["content_digest"] == (
        "hds-golden-conformance-contract:"
        "7596ae83f79b793e3c125bd3719b884d7e1a5be880e616e948c048714c8b1cf0"
    )
    assert candidate_set["content_digest"] == (
        "hds-golden-candidate-set:"
        "e59d869a1244fa1735bd0e8b07d16d9b61f607c2976c6165ab47145f12b8a2c1"
    )
    assert coverage["content_digest"] == (
        "hds-golden-gate-coverage:"
        "6e79e1111a1bb2ac17615be4aefc20ebac51a613f17d37c9d2458d45718a89d7"
    )
    assert review["content_digest"] == (
        "hds-golden-owner-review-request:"
        "40b39be4d53bd9fe2209853dc595fda16452c7d9b943a32907a3a9bb85284cc6"
    )
    assert contract["candidate_state"] == (
        "PROPOSED_PENDING_OWNER_APPROVAL"
    )
    assert candidate_set["case_count"] == 16
    assert candidate_set["arc2_case_count"] == 8
    assert candidate_set["arc3_case_count"] == 8
    assert candidate_set["content_specific_owner_approval_count"] == 0
    assert candidate_set["golden_frozen_case_count"] == 0
    assert candidate_set["sealed_case_count"] == 0
    cases = candidate_set["cases"]
    assert isinstance(cases, list)
    assert len(cases) == 16
    assert all(
        isinstance(case, dict)
        and case["candidate_state"]
        == "PROPOSED_PENDING_OWNER_APPROVAL"
        and case["approval_record_template"]["approval_mode"]
        == "SCHEMA_TEMPLATE"
        and case["approval_record_template"]["authoritative"] is False
        and case["approval_record_template"]["decision"] == "SUSPEND"
        and case["provisional_expected_artifact"]["state"]
        == "PROPOSED_NOT_FROZEN"
        for case in cases
    )
    assert coverage["covered_gate_count"] == 16
    assert coverage["missing_gate_ids"] == []
    assert coverage["pass_result_count"] == 15
    assert coverage["suspend_result_count"] == 1
    assert coverage["fail_result_count"] == 0
    assert review["target_count"] == 16
    assert review["owner_decision_present"] is False
    assert review["owner_approval_generated"] is False
    assert review["golden_freeze_started"] is False
    assert review["sealed_corpus_started"] is False
    assert review["automatic_expectation_update_allowed"] is False


def test_ph_d03a_candidate_state_binds_result_without_phase_pass() -> None:
    state = _json(
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "D03A_CANDIDATE_STATE.json"
    )
    body = dict(state)
    for excluded in state["digest_excluded_fields"]:
        body.pop(str(excluded))

    assert state["content_digest"] == (
        "rev3-d03a-candidate-state:" + digest_object(body)
    )
    assert state["content_digest"] == (
        "rev3-d03a-candidate-state:"
        "1da229969f24ebe3078a6a134602a92603c2298d312c7c1ef279d3ae13baaeeb"
    )
    assert state["phase_id"] == "PH-D03A"
    assert state["status"] == (
        "CODEX_IMPLEMENTATION_COMPLETE_PENDING_CONTENT_SPECIFIC_OWNER_APPROVAL"
    )
    assert state["phase_pass"] is False
    assert state["result_commit"] == (
        "bfbbe7d7c06f0ad076576de58cc18d5282d82e08"
    )
    assert state["result_tree"] == (
        "9e334300defe1bf1f985736065d97920d30623d4"
    )
    assert state["failed_implementation_requirement_ids"] == []
    assert state["phase_gate_pending_ids"] == [
        "D03A_CONTENT_SPECIFIC_OWNER_APPROVAL_REQUIRED",
        "D03A_GOLDEN_EXPECTATION_FREEZE_NOT_STARTED",
    ]
    assert state["owner_review_required"] is True
    assert state["owner_review_mode"] == "CONTENT_SPECIFIC_HARD_GATE"
    assert state["owner_decision_present"] is False
    assert state["owner_approval_generated_count"] == 0
    assert len(state["owner_decisions_required"]) == 1
    assert state["self_audit"]["decision"] == (
        "CODEX_CANDIDATE_IMPLEMENTATION_AUDIT_PASS"
    )
    assert state["self_audit"]["codex_implementation_audit_pass"] is True
    assert state["self_audit"]["phase_pass"] is False

    invariants = state["phase_invariants"]
    assert invariants["arc2_case_count"] == 8
    assert invariants["arc3_case_count"] == 8
    assert invariants["total_case_count"] == 16
    assert invariants["total_hypothesis_count"] == 36
    assert invariants["covered_gate_count"] == 16
    assert invariants["missing_gate_count"] == 0
    assert invariants["approval_schema_template_count"] == 16
    assert invariants["authoritative_approval_count"] == 0
    assert invariants["content_specific_owner_approval_count"] == 0
    assert invariants["golden_frozen_case_count"] == 0
    assert invariants["golden_expected_artifact_freeze_started"] is False
    assert invariants["sealed_corpus_started"] is False
    assert invariants["source_payload_read_count"] == 0
    assert invariants["teacher_trajectory_read_count"] == 0
    assert invariants["real_intervention_execution_count"] == 0
    assert invariants["general_candidate_generation_count"] == 0
    assert invariants["causal_mechanism_assertion_count"] == 0
    assert invariants["rule_promotion_count"] == 0
    assert invariants["locked_final_access_count"] == 0
    assert invariants["official_access_count"] == 0
    assert invariants["network_submission_count"] == 0
    assert invariants["kaggle_mutation_count"] == 0
    assert invariants["next_phase"] == "PH-D03B"
    assert invariants["next_phase_started"] is False
    assert invariants["hard_gate_approval_delegated"] is False

    assert state["tests"]["dedicated_golden_candidate"]["passed"] == 33
    assert state["tests"]["distillation_full"]["passed"] == 252
    assert state["tests"]["rev3_governance"]["passed"] == 29
    assert state["tests"]["full_unit"]["passed"] == 717
    assert state["tests"]["integration"]["passed"] == 8
    assert state["tests"]["artifact_rebuild"]["artifact_count"] == 4
    assert state["tests"]["independent_process_rebuild"][
        "process_count"
    ] == 3
    assert "PH_D03A_PASS" in state["claim_prohibited"]
    assert "GOLDEN_CONFORMANCE_CORPUS_FROZEN" in (
        state["claim_prohibited"]
    )

    result_commit = str(state["result_commit"])
    for artifact in state["artifacts"]:
        assert _git_blob_sha256(
            result_commit,
            str(artifact["path"]),
        ) == artifact["sha256"]


def test_ph_d03a_owner_review_package_is_complete_and_claim_limited(
) -> None:
    package_root = (
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "PH-D03A_OWNER_REVIEW_PACKAGE"
    )
    required = {
        "candidate_state_ref.json",
        "changed_files.json",
        "commands.json",
        "failed_requirements.json",
        "open_terms.json",
        "proposed_next_action.md",
        "self_audit.json",
        "summary.md",
        "test_results.json",
    }
    assert required <= {
        path.name for path in package_root.iterdir() if path.is_file()
    }

    state_ref = _json(package_root / "candidate_state_ref.json")
    failed = _json(package_root / "failed_requirements.json")
    open_terms = _json(package_root / "open_terms.json")
    self_audit = _json(package_root / "self_audit.json")
    tests = _json(package_root / "test_results.json")
    changed = _json(package_root / "changed_files.json")

    assert state_ref["state_digest"] == (
        "rev3-d03a-candidate-state:"
        "1da229969f24ebe3078a6a134602a92603c2298d312c7c1ef279d3ae13baaeeb"
    )
    assert state_ref["phase_pass"] is False
    assert failed["failed_implementation_requirement_count"] == 0
    assert failed["failed_implementation_requirements"] == []
    assert failed["phase_gate_pending_count"] == 2
    assert failed["phase_pass"] is False
    assert open_terms["required_authority_missing_count"] == 1
    assert len(open_terms["open_terms"]) == 1
    assert open_terms["open_terms"][0]["required_authority"] == "OWNER"
    assert open_terms["open_terms"][0]["target_count"] == 16
    assert open_terms["owner_decisions"][0]["status"] == "PENDING"
    assert open_terms["owner_decisions"][0]["codex_may_generate"] is False
    assert self_audit["decision"] == (
        "CODEX_CANDIDATE_IMPLEMENTATION_AUDIT_PASS"
    )
    assert self_audit["codex_implementation_audit_pass"] is True
    assert self_audit["phase_pass"] is False
    assert tests["new_product_regression_count"] == 0
    assert tests["active_product_regression_count"] == 0
    assert tests["active_environment_failure_count"] == 0
    assert tests["active_external_service_failure_count"] == 0
    assert tests["active_tool_failure_count"] == 0
    assert tests["phase_gate_pending_count"] == 2
    assert changed["changed_file_count"] == 12
    assert changed["changed_files"] == sorted(changed["changed_files"])
    assert changed["excluded_preexisting_dirty_state"]["mutation"] == "NONE"
    assert changed["excluded_preexisting_dirty_state"]["staging"] == "NONE"

    summary = (package_root / "summary.md").read_text(encoding="utf-8")
    next_action = (package_root / "proposed_next_action.md").read_text(
        encoding="utf-8"
    )
    assert "Phase PASS: **false**" in summary
    assert "trusted content-specific Owner approvals: 0" in summary
    assert "Codex cannot generate those" in summary
    assert "do not construct" in next_action
    assert "Sealed Audit Corpus" in next_action


def test_ph_d03a_artifact_manifest_binds_candidate_snapshot_bytes(
) -> None:
    manifest = _json(
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "PH-D03A_OWNER_REVIEW_PACKAGE"
        / "artifact_manifest.json"
    )
    body = dict(manifest)
    for excluded in manifest["digest_excluded_fields"]:
        body.pop(excluded)

    assert manifest["content_digest"] == (
        "rev3-d03a-owner-review-artifact-manifest:"
        + digest_object(body)
    )
    assert manifest["content_digest"] == (
        "rev3-d03a-owner-review-artifact-manifest:"
        "3d28855f28904a6b2d55f6198269211d45bfadd58c43af8d4f0749f4b4cc7321"
    )
    assert manifest["phase_id"] == "PH-D03A"
    assert manifest["status"] == (
        "CANDIDATE_ONLY_PENDING_CONTENT_SPECIFIC_OWNER_APPROVAL"
    )
    assert manifest["phase_pass"] is False
    assert manifest["owner_decision_present"] is False
    assert manifest["result_commit"] == (
        "bfbbe7d7c06f0ad076576de58cc18d5282d82e08"
    )
    assert manifest["result_tree"] == (
        "9e334300defe1bf1f985736065d97920d30623d4"
    )
    assert manifest["snapshot_commit"] == (
        "43650e65172f8cad1f770122fa1666d6e39218aa"
    )
    assert manifest["snapshot_tree"] == (
        "89c34ff992a0840d993c5c9079ad12eb1e7c041d"
    )
    assert manifest["manifest_excludes_self"] is True
    assert manifest["artifact_count"] == len(manifest["artifacts"]) == 26
    artifact_paths = [
        str(artifact["path"]) for artifact in manifest["artifacts"]
    ]
    assert artifact_paths == sorted(artifact_paths)
    assert len(artifact_paths) == len(set(artifact_paths))
    assert (
        "control/rev3/PH-D03A_OWNER_REVIEW_PACKAGE/artifact_manifest.json"
        not in artifact_paths
    )

    snapshot_commit = str(manifest["snapshot_commit"])
    for artifact in manifest["artifacts"]:
        assert _git_blob_sha256(
            snapshot_commit,
            str(artifact["path"]),
        ) == artifact["sha256"]


def test_ph_d03a_validator_hardening_addendum_is_bound_and_gate_safe(
) -> None:
    package_root = (
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "PH-D03A_OWNER_REVIEW_PACKAGE"
    )
    state = _json(package_root / "validator_hardening_state.json")
    body = dict(state)
    for excluded in state["digest_excluded_fields"]:
        body.pop(excluded)

    assert state["content_digest"] == (
        "rev3-d03a-validator-hardening-state:" + digest_object(body)
    )
    assert state["content_digest"] == (
        "rev3-d03a-validator-hardening-state:"
        "1fb641f0a1d4bf4b40b4008229020b8497d439ef3c35ed49d0b0e44095df3799"
    )
    assert state["status"] == (
        "CODEX_VALIDATOR_HARDENING_PASS_PENDING_CONTENT_SPECIFIC_OWNER_APPROVAL"
    )
    assert state["phase_pass"] is False
    assert state["hardening_result_commit"] == (
        "0bbb3d26284dacb8803ffdea77178091b443f1fd"
    )
    assert state["hardening_result_tree"] == (
        "0d9fc4c0b9d7761845f6381a1b3a93783062ad9b"
    )
    assert state["discovered_defect_count"] == 4
    assert len(state["discovered_defects"]) == 4
    assert state["red_test"]["failed_as_expected_count"] == 4
    assert state["validation"]["selected_green"]["passed"] == 4
    assert state["validation"]["dedicated_golden_candidate"]["passed"] == 37
    assert state["validation"]["distillation_full"]["passed"] == 256
    assert state["validation"]["historical_unit_full"]["passed"] == 720
    assert state["validation"]["rev3_governance"]["passed"] == 32
    assert state["validation"]["scope_guard"]["finding_count"] == 0
    assert state["checked_golden_artifacts"]["mutation_count"] == 0
    assert state["failure_accounting"]["active_product_regression_count"] == 0

    boundary = state["authority_boundary"]
    assert boundary["content_specific_owner_decision_present"] is False
    assert boundary["content_specific_owner_approval_count"] == 0
    assert boundary["golden_freeze_started"] is False
    assert boundary["sealed_corpus_started"] is False
    assert boundary["next_phase_started"] is False
    assert boundary["owner_record_generation_count"] == 0
    assert boundary["hard_gate_approval_delegated"] is False
    assert "PH_D03A_PASS" in state["claim_prohibited"]
    assert "PH_D03B_STARTED" in state["claim_prohibited"]

    result_commit = str(state["hardening_result_commit"])
    for artifact in state["result_artifacts"]:
        assert _git_blob_sha256(
            result_commit,
            str(artifact["path"]),
        ) == artifact["sha256"]
    for artifact in state["checked_golden_artifacts"]["artifacts"]:
        assert _git_blob_sha256(
            result_commit,
            str(artifact["path"]),
        ) == artifact["sha256"]

    summary = (
        package_root / "validator_hardening_summary.md"
    ).read_text(encoding="utf-8")
    assert "Phase PASS: **false**" in summary
    assert "No Owner decision was created" in summary
    assert "gate remains open" in summary


def test_ph_d03a_validator_hardening_manifest_binds_snapshot_bytes(
) -> None:
    manifest = _json(
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "PH-D03A_OWNER_REVIEW_PACKAGE"
        / "validator_hardening_manifest.json"
    )
    body = dict(manifest)
    for excluded in manifest["digest_excluded_fields"]:
        body.pop(excluded)

    assert manifest["content_digest"] == (
        "rev3-d03a-validator-hardening-manifest:"
        + digest_object(body)
    )
    assert manifest["content_digest"] == (
        "rev3-d03a-validator-hardening-manifest:"
        "c715a33caf6cc503da5b577633545884fa9935b4d680c916fa5e450dc0da3647"
    )
    assert manifest["status"] == (
        "VALIDATOR_HARDENING_PASS_PENDING_CONTENT_SPECIFIC_OWNER_APPROVAL"
    )
    assert manifest["phase_pass"] is False
    assert manifest["owner_decision_present"] is False
    assert manifest["hardening_result_commit"] == (
        "0bbb3d26284dacb8803ffdea77178091b443f1fd"
    )
    assert manifest["hardening_result_tree"] == (
        "0d9fc4c0b9d7761845f6381a1b3a93783062ad9b"
    )
    assert manifest["snapshot_commit"] == (
        "bea78fd6a330cba301499b4a8e6494d5843a0a3b"
    )
    assert manifest["snapshot_tree"] == (
        "88e9eab4b7c4a6963c1981d0595c4325b7adeddf"
    )
    assert manifest["manifest_excludes_self"] is True
    assert manifest["artifact_count"] == len(manifest["artifacts"]) == 12
    artifact_paths = [
        str(artifact["path"]) for artifact in manifest["artifacts"]
    ]
    assert artifact_paths == sorted(artifact_paths)
    assert len(artifact_paths) == len(set(artifact_paths))
    assert (
        "control/rev3/PH-D03A_OWNER_REVIEW_PACKAGE/"
        "validator_hardening_manifest.json"
        not in artifact_paths
    )

    snapshot_commit = str(manifest["snapshot_commit"])
    for artifact in manifest["artifacts"]:
        assert _git_blob_sha256(
            snapshot_commit,
            str(artifact["path"]),
        ) == artifact["sha256"]


def test_ph_d01b_phase_state_binds_result_and_manifest_freeze() -> None:
    state_path = (
        REPOSITORY_ROOT / "control" / "rev3" / "D01B_PHASE_STATE.json"
    )
    package_state_path = (
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "PH-D01B_OWNER_REVIEW_PACKAGE"
        / "phase_state.json"
    )
    state = _json(state_path)
    state_body = dict(state)
    claimed = str(state_body.pop("content_digest"))

    assert state == _json(package_state_path)
    assert claimed == "rev3-d01b-phase-state:" + digest_object(state_body)
    assert state["phase_id"] == "PH-D01B"
    assert state["status"] == "CODEX_SELF_AUDIT_PASS"
    assert state["result_commit"] == (
        "5c47bb5f1519f07ff74aa61ba6beff7fcc13dc6d"
    )
    assert state["result_tree"] == (
        "d64951234d55f2e83330255251c5f11caf562307"
    )
    assert state["owner_review_required"] is False
    assert state["owner_decisions_required"] == []
    assert state["failed_requirement_ids"] == []
    assert state["open_terms"] == []

    invariants = state["phase_invariants"]
    assert invariants["source_content_manifest_count"] == 8
    assert invariants["source_entry_count"] == 83
    assert invariants["acquisition_record_count"] == 8
    assert invariants["environment_manifest_count"] == 1
    assert invariants["run_manifest_count"] == 1
    assert invariants["raw_recording_verified_count"] == 25
    assert invariants["raw_recording_level_count"] == 183
    assert invariants["arc3_environment_source_count"] == 50
    assert invariants["arc3_distribution_alias_verified_count"] == 50
    assert invariants["runtime_wheel_verified_count"] == 2
    assert invariants["source_payload_parse_count"] == 0
    assert invariants["source_execution_count"] == 0
    assert invariants["replay_execution_count"] == 0
    assert invariants["compiler_network_call_count"] == 0
    assert invariants["trajectory_normalization_started"] is False
    assert invariants["canonical_schema_phase_started"] is False
    assert invariants["causal_ir_started"] is False
    assert invariants["official_access_count"] == 0
    assert invariants["kaggle_mutation_count"] == 0
    assert invariants["preexisting_dirty_file_count"] == 32
    assert invariants["preexisting_dirty_aggregate_sha256"] == (
        "3bb18c20566ad712e0cbf00604e83da9c7afdecf469d261974da046632a5d1f4"
    )
    assert invariants["next_phase"] == "PH-D02A"
    assert invariants["next_phase_started"] is False

    assert state["tests"]["dedicated_manifest_freeze"]["passed"] == 23
    assert state["tests"]["focused_distillation_and_rev3"]["passed"] == 92
    assert state["tests"]["full_unit"]["passed"] == 703
    assert state["tests"]["integration"]["passed"] == 8
    assert state["tests"]["determinism"]["aggregate_sha256"] == (
        "a48353aa3904f3917a4cf8669cc0ef2ca860575c8f5c344095dcd9ed4e9a68cb"
    )
    assert "PH_D01B_MANIFEST_FREEZE_PASS" in state["claim_allowed"]
    assert "ARC3_TEACHER_SOURCE_FROZEN" in state["claim_allowed"]
    assert "TRAJECTORY_NORMALIZATION_COMPLETE" in (
        state["claim_prohibited"]
    )
    assert "HDS_STRUCTURE_BUNDLE_OWNER_APPROVED" in (
        state["claim_prohibited"]
    )

    result_commit = str(state["result_commit"])
    for artifact in state["artifacts"]:
        path = artifact.get("path")
        expected_sha256 = artifact.get("sha256")
        if path is not None and expected_sha256 is not None:
            assert _git_blob_sha256(result_commit, str(path)) == (
                expected_sha256
            )


def test_ph_d01b_owner_review_package_is_complete_and_claim_limited(
) -> None:
    package_root = (
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "PH-D01B_OWNER_REVIEW_PACKAGE"
    )
    required = {
        "changed_files.json",
        "commands.json",
        "failed_requirements.json",
        "open_terms.json",
        "phase_state.json",
        "proposed_next_action.md",
        "self_audit.json",
        "summary.md",
        "test_results.json",
    }
    assert required <= {
        path.name for path in package_root.iterdir() if path.is_file()
    }

    failed = _json(package_root / "failed_requirements.json")
    open_terms = _json(package_root / "open_terms.json")
    self_audit = _json(package_root / "self_audit.json")
    tests = _json(package_root / "test_results.json")
    changed = _json(package_root / "changed_files.json")

    assert failed["failed_requirement_count"] == 0
    assert failed["failed_requirements"] == []
    assert open_terms["open_terms"] == []
    assert open_terms["owner_decisions"] == []
    assert self_audit["decision"] == "CODEX_SELF_AUDIT_PASS"
    assert self_audit["codex_self_audit_pass"] is True
    assert tests["active_product_regression_count"] == 0
    assert tests["active_environment_failure_count"] == 0
    assert tests["active_external_service_failure_count"] == 0
    assert changed["changed_file_count"] == 35
    assert changed["excluded_preexisting_dirty_state"]["mutation"] == "NONE"
    assert changed["excluded_preexisting_dirty_state"]["staging"] == "NONE"

    summary = (package_root / "summary.md").read_text(encoding="utf-8")
    next_action = (package_root / "proposed_next_action.md").read_text(
        encoding="utf-8"
    )
    assert "PH_D01B_MANIFEST_FREEZE_PASS" in summary
    assert "not started" in summary
    assert "Proceed to `PH-D02A`" in next_action
    assert "Do not enter PH-D02B" in next_action


def test_ph_d01b_artifact_manifest_binds_snapshot_bytes() -> None:
    manifest = _json(
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "PH-D01B_OWNER_REVIEW_PACKAGE"
        / "artifact_manifest.json"
    )
    body = dict(manifest)
    for excluded in manifest["digest_excluded_fields"]:
        body.pop(excluded)

    assert manifest["content_digest"] == (
        "rev3-d01b-owner-review-artifact-manifest:"
        + digest_object(body)
    )
    assert manifest["phase_id"] == "PH-D01B"
    assert manifest["result_commit"] == (
        "5c47bb5f1519f07ff74aa61ba6beff7fcc13dc6d"
    )
    assert manifest["result_tree"] == (
        "d64951234d55f2e83330255251c5f11caf562307"
    )
    assert manifest["snapshot_commit"] == (
        "eecfa4ad497a0379b5f9808edd7ecd140bcf6929"
    )
    assert manifest["snapshot_tree"] == (
        "512ab7821015fc7cd0a8ddc8428304d86f14cb51"
    )
    assert manifest["artifact_count"] == len(manifest["artifacts"]) == 46
    artifact_paths = [
        str(artifact["path"]) for artifact in manifest["artifacts"]
    ]
    assert artifact_paths == sorted(artifact_paths)
    assert len(artifact_paths) == len(set(artifact_paths))

    snapshot_commit = str(manifest["snapshot_commit"])
    for artifact in manifest["artifacts"]:
        assert _git_blob_sha256(
            snapshot_commit,
            str(artifact["path"]),
        ) == artifact["sha256"]


def test_ph_d02a_phase_state_binds_result_and_canonical_contract() -> None:
    state_path = (
        REPOSITORY_ROOT / "control" / "rev3" / "D02A_PHASE_STATE.json"
    )
    package_state_path = (
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "PH-D02A_OWNER_REVIEW_PACKAGE"
        / "phase_state.json"
    )
    state = _json(state_path)
    state_body = dict(state)
    claimed = str(state_body.pop("content_digest"))

    assert state == _json(package_state_path)
    assert claimed == "rev3-d02a-phase-state:" + digest_object(state_body)
    assert state["phase_id"] == "PH-D02A"
    assert state["status"] == "CODEX_SELF_AUDIT_PASS"
    assert state["result_commit"] == (
        "5ccde025b70cb462b477b428171a49bf2b857c09"
    )
    assert state["result_tree"] == (
        "998c35894efd1ac201fec3877cbd045e3ffce68a"
    )
    assert state["owner_review_required"] is False
    assert state["owner_decisions_required"] == []
    assert state["failed_requirement_ids"] == []
    assert state["open_terms"] == []

    invariants = state["phase_invariants"]
    assert invariants["canonical_contract_implemented"] is True
    assert invariants["canonical_json_implemented"] is True
    assert invariants["unicode_nfc_enforced"] is True
    assert invariants["explicit_unordered_array_normalization"] is True
    assert invariants["ordinary_array_order_preserved"] is True
    assert invariants["confidence_ppm_integer_contract"] is True
    assert invariants["content_derived_id_full_sha256"] is True
    assert invariants["explicit_top_level_digest_exclusions"] is True
    assert invariants["logical_physical_domains_separate"] is True
    assert invariants["canonical_zip_stored"] is True
    assert invariants["canonical_npy_npz_dependency_free"] is True
    assert invariants["raw_canonical_trajectory_domains_separate"] is True
    assert invariants["independent_process_rebuild_count"] == 3
    assert invariants["independent_process_byte_identical"] is True
    assert invariants["nan_infinity_rejected"] is True
    assert invariants["numpy_interoperability_verified"] is True
    assert invariants["frozen_d01b_artifact_unchanged_count"] == 40
    assert invariants["runtime_dependency_added_count"] == 0
    assert invariants["distillation_source_numpy_import_count"] == 0
    assert invariants["source_payload_read_count"] == 0
    assert invariants["source_execution_count"] == 0
    assert invariants["real_trajectory_normalization_count"] == 0
    assert invariants["ph_d02b_schema_count"] == 0
    assert invariants["causal_ir_started"] is False
    assert invariants["trajectory_normalization_started"] is False
    assert invariants["candidate_generation_started"] is False
    assert invariants["rule_promotion_count"] == 0
    assert invariants["bridge_implementation_file_count"] == 0
    assert invariants["runtime_implementation_file_count"] == 0
    assert invariants["official_access_count"] == 0
    assert invariants["kaggle_mutation_count"] == 0
    assert invariants["preexisting_dirty_file_count"] == 32
    assert invariants["preexisting_dirty_aggregate_sha256"] == (
        "3bb18c20566ad712e0cbf00604e83da9c7afdecf469d261974da046632a5d1f4"
    )
    assert invariants["next_phase"] == "PH-D02B"
    assert invariants["next_phase_started"] is False

    assert state["tests"]["dedicated_canonical"]["passed"] == 69
    assert state["tests"]["distillation_full"]["passed"] == 132
    assert state["tests"]["rev3_governance"]["passed"] == 18
    assert state["tests"]["full_unit"]["passed"] == 706
    assert state["tests"]["integration"]["passed"] == 8
    assert state["tests"]["determinism"]["aggregate_sha256"] == (
        "5848db9ca5c94280885c5980d65180f88114c1d2c2daf0880958aff20dbcec26"
    )
    assert "PH_D02A_CANONICAL_CONTRACT_PASS" in state["claim_allowed"]
    assert "PH_D02B_SCHEMA_SET_COMPLETE" in state["claim_prohibited"]
    assert "TRAJECTORY_NORMALIZATION_COMPLETE" in (
        state["claim_prohibited"]
    )
    assert "HDS_STRUCTURE_BUNDLE_OWNER_APPROVED" in (
        state["claim_prohibited"]
    )

    result_commit = str(state["result_commit"])
    for artifact in state["artifacts"]:
        path = artifact.get("path")
        expected_sha256 = artifact.get("sha256")
        if path is not None and expected_sha256 is not None:
            assert _git_blob_sha256(result_commit, str(path)) == (
                expected_sha256
            )


def test_ph_d02a_owner_review_package_is_complete_and_claim_limited(
) -> None:
    package_root = (
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "PH-D02A_OWNER_REVIEW_PACKAGE"
    )
    required = {
        "changed_files.json",
        "commands.json",
        "failed_requirements.json",
        "open_terms.json",
        "phase_state.json",
        "proposed_next_action.md",
        "self_audit.json",
        "summary.md",
        "test_results.json",
    }
    assert required <= {
        path.name for path in package_root.iterdir() if path.is_file()
    }

    failed = _json(package_root / "failed_requirements.json")
    open_terms = _json(package_root / "open_terms.json")
    self_audit = _json(package_root / "self_audit.json")
    tests = _json(package_root / "test_results.json")
    changed = _json(package_root / "changed_files.json")

    assert failed["failed_requirement_count"] == 0
    assert failed["failed_requirements"] == []
    assert open_terms["open_terms"] == []
    assert open_terms["owner_decisions"] == []
    assert self_audit["decision"] == "CODEX_SELF_AUDIT_PASS"
    assert self_audit["codex_self_audit_pass"] is True
    assert tests["active_product_regression_count"] == 0
    assert tests["active_environment_failure_count"] == 0
    assert tests["active_external_service_failure_count"] == 0
    assert tests["active_tool_failure_count"] == 0
    assert changed["changed_file_count"] == 15
    assert changed["excluded_preexisting_dirty_state"]["mutation"] == "NONE"
    assert changed["excluded_preexisting_dirty_state"]["staging"] == "NONE"

    summary = (package_root / "summary.md").read_text(encoding="utf-8")
    next_action = (package_root / "proposed_next_action.md").read_text(
        encoding="utf-8"
    )
    assert "PH_D02A_CANONICAL_CONTRACT_PASS" in summary
    assert "not started" in summary
    assert "Proceed to `PH-D02B`" in next_action
    assert "Do not enter PH-D02C" in next_action


def test_ph_d02a_artifact_manifest_binds_snapshot_bytes() -> None:
    manifest = _json(
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "PH-D02A_OWNER_REVIEW_PACKAGE"
        / "artifact_manifest.json"
    )
    body = dict(manifest)
    for excluded in manifest["digest_excluded_fields"]:
        body.pop(excluded)

    assert manifest["content_digest"] == (
        "rev3-d02a-owner-review-artifact-manifest:"
        + digest_object(body)
    )
    assert manifest["phase_id"] == "PH-D02A"
    assert manifest["result_commit"] == (
        "5ccde025b70cb462b477b428171a49bf2b857c09"
    )
    assert manifest["result_tree"] == (
        "998c35894efd1ac201fec3877cbd045e3ffce68a"
    )
    assert manifest["snapshot_commit"] == (
        "ffa11f1181fe0a63118eba83a9e3c90090a0abb5"
    )
    assert manifest["snapshot_tree"] == (
        "096709b5f59765a56f17e52caffcddbb7557fd7d"
    )
    assert manifest["manifest_excludes_self"] is True
    assert manifest["artifact_count"] == len(manifest["artifacts"]) == 26
    artifact_paths = [
        str(artifact["path"]) for artifact in manifest["artifacts"]
    ]
    assert artifact_paths == sorted(artifact_paths)
    assert len(artifact_paths) == len(set(artifact_paths))
    assert (
        "control/rev3/PH-D02A_OWNER_REVIEW_PACKAGE/artifact_manifest.json"
        not in artifact_paths
    )

    snapshot_commit = str(manifest["snapshot_commit"])
    for artifact in manifest["artifacts"]:
        assert _git_blob_sha256(
            snapshot_commit,
            str(artifact["path"]),
        ) == artifact["sha256"]


def test_ph_d02b_phase_state_binds_result_and_schema_contract() -> None:
    state_path = (
        REPOSITORY_ROOT / "control" / "rev3" / "D02B_PHASE_STATE.json"
    )
    package_state_path = (
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "PH-D02B_OWNER_REVIEW_PACKAGE"
        / "phase_state.json"
    )
    state = _json(state_path)
    state_body = dict(state)
    claimed = str(state_body.pop("content_digest"))

    assert state == _json(package_state_path)
    assert claimed == "rev3-d02b-phase-state:" + digest_object(state_body)
    assert state["phase_id"] == "PH-D02B"
    assert state["status"] == "CODEX_SELF_AUDIT_PASS"
    assert state["result_commit"] == (
        "108c5462c2c73bdd95953e9e9b0cbbce68ac5d02"
    )
    assert state["result_tree"] == (
        "63e3a2e9e2f1f8953bec7c6294ed8034349f6d9e"
    )
    assert state["owner_review_required"] is False
    assert state["owner_decisions_required"] == []
    assert state["failed_requirement_ids"] == []
    assert state["open_terms"] == []

    invariants = state["phase_invariants"]
    assert invariants["schema_inventory_count"] == 38
    assert invariants["schema_file_count"] == 38
    assert invariants["preserved_schema_count"] == 5
    assert invariants["generated_schema_count"] == 33
    assert invariants["schema_version_bound_count"] == 38
    assert invariants["schema_digest_bound_count"] == 38
    assert invariants["valid_example_count"] == 38
    assert invariants["invalid_case_count"] == 24
    assert invariants["invalid_case_pass_count"] == 24
    assert invariants["hds_state_axis_count"] == 7
    assert invariants["typed_reference_fail_closed"] is True
    assert invariants["raw_derivation_interpretation_separate"] is True
    assert invariants["identity_routing_fields_rejected"] is True
    assert invariants["multi_causal_zero_selection_accepted"] is True
    assert invariants["multi_causal_multiple_selection_accepted"] is True
    assert invariants["suspend_zero_selection_accepted"] is True
    assert invariants["suspend_multiple_selection_accepted"] is True
    assert invariants["initial_ruleatom_proposed_or_probation_only"] is True
    assert invariants["owner_approval_generated_count"] == 0
    assert invariants["rule_promotion_count"] == 0
    assert invariants["deterministic_artifact_count"] == 42
    assert invariants["deterministic_artifacts_byte_identical"] is True
    assert invariants["scope_guard_finding_count"] == 0
    assert invariants["frozen_d02a_artifact_unchanged_count"] == 8
    assert invariants["source_payload_read_count"] == 0
    assert invariants["source_execution_count"] == 0
    assert invariants["real_trajectory_normalization_count"] == 0
    assert invariants["ph_d02c_typed_causal_ir_started"] is False
    assert invariants["interpreter_started"] is False
    assert invariants["verifier_abi_started"] is False
    assert invariants["candidate_generation_started"] is False
    assert invariants["official_access_count"] == 0
    assert invariants["kaggle_mutation_count"] == 0
    assert invariants["preexisting_dirty_file_count"] == 32
    assert invariants["preexisting_dirty_aggregate_sha256"] == (
        "3bb18c20566ad712e0cbf00604e83da9c7afdecf469d261974da046632a5d1f4"
    )
    assert invariants["next_phase"] == "PH-D02C"
    assert invariants["next_phase_started"] is False

    assert state["tests"]["dedicated_schema_registry"]["passed"] == 45
    assert state["tests"]["distillation_full"]["passed"] == 177
    assert state["tests"]["rev3_governance"]["passed"] == 21
    assert state["tests"]["full_unit"]["passed"] == 709
    assert state["tests"]["integration"]["passed"] == 8
    assert state["tests"]["artifact_rebuild"]["artifact_count"] == 42
    assert state["tests"]["focused_distillation_rev3_evidence"]["passed"] == (
        214
    )
    assert "PH_D02B_SCHEMA_SET_PASS" in state["claim_allowed"]
    assert "DISTILLATION_IR_EXECUTABLE" in state["claim_prohibited"]
    assert "TRAJECTORY_NORMALIZATION_COMPLETE" in (
        state["claim_prohibited"]
    )
    assert "HDS_STRUCTURE_BUNDLE_OWNER_APPROVED" in (
        state["claim_prohibited"]
    )

    result_commit = str(state["result_commit"])
    for artifact in state["artifacts"]:
        path = artifact.get("path")
        expected_sha256 = artifact.get("sha256")
        if path is not None and expected_sha256 is not None:
            assert _git_blob_sha256(result_commit, str(path)) == (
                expected_sha256
            )


def test_ph_d02b_owner_review_package_is_complete_and_claim_limited(
) -> None:
    package_root = (
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "PH-D02B_OWNER_REVIEW_PACKAGE"
    )
    required = {
        "changed_files.json",
        "commands.json",
        "failed_requirements.json",
        "open_terms.json",
        "phase_state.json",
        "proposed_next_action.md",
        "self_audit.json",
        "summary.md",
        "test_results.json",
    }
    assert required <= {
        path.name for path in package_root.iterdir() if path.is_file()
    }

    failed = _json(package_root / "failed_requirements.json")
    open_terms = _json(package_root / "open_terms.json")
    self_audit = _json(package_root / "self_audit.json")
    tests = _json(package_root / "test_results.json")
    changed = _json(package_root / "changed_files.json")

    assert failed["failed_requirement_count"] == 0
    assert failed["failed_requirements"] == []
    assert open_terms["open_terms"] == []
    assert open_terms["owner_decisions"] == []
    assert self_audit["decision"] == "CODEX_SELF_AUDIT_PASS"
    assert self_audit["codex_self_audit_pass"] is True
    assert tests["active_product_regression_count"] == 0
    assert tests["active_environment_failure_count"] == 0
    assert tests["active_external_service_failure_count"] == 0
    assert tests["active_tool_failure_count"] == 0
    assert tests["resolved_environment_failure_count"] == 2
    assert changed["changed_file_count"] == 46
    assert changed["excluded_preexisting_dirty_state"]["mutation"] == "NONE"
    assert changed["excluded_preexisting_dirty_state"]["staging"] == "NONE"

    summary = (package_root / "summary.md").read_text(encoding="utf-8")
    next_action = (package_root / "proposed_next_action.md").read_text(
        encoding="utf-8"
    )
    assert "PH_D02B_SCHEMA_SET_PASS" in summary
    assert "not started" in summary
    assert "Proceed to `PH-D02C`" in next_action
    assert "Do not enter Golden or Sealed corpus freeze" in next_action


def test_ph_d02b_artifact_manifest_binds_snapshot_bytes() -> None:
    manifest = _json(
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "PH-D02B_OWNER_REVIEW_PACKAGE"
        / "artifact_manifest.json"
    )
    body = dict(manifest)
    for excluded in manifest["digest_excluded_fields"]:
        body.pop(excluded)

    assert manifest["content_digest"] == (
        "rev3-d02b-owner-review-artifact-manifest:"
        + digest_object(body)
    )
    assert manifest["phase_id"] == "PH-D02B"
    assert manifest["result_commit"] == (
        "108c5462c2c73bdd95953e9e9b0cbbce68ac5d02"
    )
    assert manifest["result_tree"] == (
        "63e3a2e9e2f1f8953bec7c6294ed8034349f6d9e"
    )
    assert manifest["snapshot_commit"] == (
        "b4db449881c0a8031d984498b5e4b216bcdf3ef1"
    )
    assert manifest["snapshot_tree"] == (
        "cf05f620f63e0cd6ad20a7beac5e234e8eefdce4"
    )
    assert manifest["manifest_excludes_self"] is True
    assert manifest["artifact_count"] == len(manifest["artifacts"]) == 57
    artifact_paths = [
        str(artifact["path"]) for artifact in manifest["artifacts"]
    ]
    assert artifact_paths == sorted(artifact_paths)
    assert len(artifact_paths) == len(set(artifact_paths))
    assert (
        "control/rev3/PH-D02B_OWNER_REVIEW_PACKAGE/artifact_manifest.json"
        not in artifact_paths
    )

    snapshot_commit = str(manifest["snapshot_commit"])
    for artifact in manifest["artifacts"]:
        assert _git_blob_sha256(
            snapshot_commit,
            str(artifact["path"]),
        ) == artifact["sha256"]


def test_ph_r00_current_rebind_and_historical_evidence_are_content_bound(
) -> None:
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
    assert classification["schema_version"] == (
        "arc3-rev3-asset-classification-v2"
    )
    assert classification["phase_status"] == "IN_PROGRESS"
    assert classification["source_commit"] == (
        "4dbb65c5d45cca3402f326b251c1de6ac4a2e554"
    )
    assert classification["source_tree"] == (
        "44ccb73437480daeaab71e6cb3119b5e6bc5d485"
    )
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
    assert frame["resource_budget"]["network_submission_count"] == 0
    assert frame["resource_budget"]["maximum_new_runtime_capabilities"] == 0
    assert frame["base_commit"] == classification["source_commit"]
    assert frame["base_tree"] == classification["source_tree"]

    transition = _json(
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "PHASE_TRANSITIONS"
        / "PH-R-1_TO_PH-R00.json"
    )
    transition_body = dict(transition)
    for excluded in transition["digest_excluded_fields"]:
        transition_body.pop(excluded)
    assert transition["content_digest"] == (
        "rev3-phase-transition:" + digest_object(transition_body)
    )
    assert transition["from_phase_id"] == "PH-R-1"
    assert transition["from_phase_status"] == "OWNER_APPROVED_PASS"
    assert transition["to_phase_id"] == "PH-R00"
    assert transition["to_phase_status"] == "IN_PROGRESS"
    assert transition["decision"] == "ENTRY_AUTHORIZED"
    assert transition["external_irreversible_action_authorized"] is False
    assert transition["verified_exit_conditions"][
        "failed_requirement_count"
    ] == 0

    # The pre-audit rework frame remains historical evidence only.
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
    assert baseline["schema_version"] == (
        "arc3-rev3-pre-distillation-infrastructure-baseline-v2"
    )
    assert baseline["status"] == (
        "CURRENT_HEAD_BOUND_IMPLEMENTATION_VALIDATION_PASS"
    )
    assert baseline["source_commit"] == frame["base_commit"]
    assert baseline["source_tree"] == frame["base_tree"]
    assert baseline["rev3_runtime"]["active_runtime_count"] == 0
    assert baseline["historical_capability_assets"][
        "production_parent_allowed"
    ] is False
    assert baseline["historical_capability_assets"][
        "fallback_allowed"
    ] is False
    assert baseline["missing_required_authorities"] == []
    assert baseline["preexisting_dirty_state"][
        "tracked_autonomous_completion_file_count"
    ] == 32
    assert baseline["failed_requirement_ids"] == []
    assert {
        result["status"]
        for result in baseline["validation"].values()
    } == {"PASS"}
    assert baseline["validation"]["full_unit"]["passed"] == 728
    assert baseline["validation"]["full_integration"]["passed"] == 8
    assert baseline["validation"]["package"]["byte_identical"] is True
    assert baseline["validation"]["notebook_regression"][
        "validator_checks_passed"
    ] == 25
    assert baseline["validation"]["production_import_boundary"][
        "quarantined_module_intersection"
    ] == []
    assert all(
        item["source_blob_verified"]
        for item in baseline["preserved_phase_states"]
    )

    # Every assertion below is about retained pre-audit evidence, never current
    # activation evidence.
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

    selector = _json(
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "REV3_CURRENT_SELECTOR.json"
    )
    assert (
        selector["historical_evidence"]["classification"]
        == "HISTORICAL_PRE_AUDIT_NONAUTHORITATIVE"
    )
    historical_package_root = (
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "OWNER_REVIEW_PACKAGE"
    )
    phase_state_path = historical_package_root / "phase_state.json"
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
    artifact_manifest = _json(
        historical_package_root / "artifact_manifest.json"
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


def test_ph_d00a_entry_and_historical_migration_are_content_bound() -> None:
    control_root = REPOSITORY_ROOT / "control" / "rev3"
    decision = _json(
        control_root
        / "OWNER_DECISION_CAPTURES"
        / "PH-R00_TO_PH-D00A_20260731.json"
    )
    decision_body = dict(decision)
    for excluded in decision["digest_excluded_fields"]:
        decision_body.pop(str(excluded))
    assert decision["owner_decision_content_digest"] == (
        "sha256:" + digest_object(decision_body)
    )

    approval = _json(
        control_root
        / "OWNER_APPROVAL_RECORDS"
        / "PH-R00_TO_PH-D00A_20260731.json"
    )
    approval_body = dict(approval)
    for excluded in approval["digest_excluded_fields"]:
        approval_body.pop(str(excluded))
    assert approval["approval_artifact_digest"] == (
        "owner-approval-record:" + digest_object(approval_body)
    )
    assert approval["owner_decision_capture_digest"] == (
        decision["owner_decision_content_digest"]
    )
    assert approval["next_phase_id"] == "PH-D00A"
    assert approval["next_phase_authorized"] is True

    attestation = _json(control_root / "PH-R00_EVIDENCE_ATTESTATION.json")
    assert decision["target_evidence_commit"] == (
        attestation["evidence_commit"]
    )
    assert decision["target_artifact_digest"] == (
        attestation["evidence_payload_digest"]
    )

    transition = _json(
        control_root / "PHASE_TRANSITIONS" / "PH-R00_TO_PH-D00A.json"
    )
    transition_body = dict(transition)
    for excluded in transition["digest_excluded_fields"]:
        transition_body.pop(str(excluded))
    assert transition["content_digest"] == (
        "rev3-phase-transition:" + digest_object(transition_body)
    )
    assert transition["from_phase_id"] == "PH-R00"
    assert transition["to_phase_id"] == "PH-D00A"
    assert transition["authorization_digest"] == (
        approval["approval_artifact_digest"]
    )
    assert transition["external_irreversible_action_authorized"] is False

    frame = _json(control_root / "PH-D00A_WORK_BLOCK_FRAME.json")
    frame_body = dict(frame)
    for excluded in frame["digest_excluded_fields"]:
        frame_body.pop(str(excluded))
    assert frame["content_digest"] == (
        "rev3-work-block-frame:" + digest_object(frame_body)
    )
    assert frame["phase_id"] == "PH-D00A"
    assert frame["owner_authority"]["entry_approval_digest"] == (
        approval["approval_artifact_digest"]
    )
    assert all(value == 0 for value in frame["resource_budget"].values())

    historical_root = (
        control_root / "HISTORICAL_PRE_AUDIT" / "PH-D00A"
    )
    frame_source_commit = "219ce1edcba91786ca0183f906c15df970d1df71"
    control_source_commit = "3af55820b05b0e8bf69f181c6e2790575380e2e0"
    path_pairs = [
        (
            frame_source_commit,
            "control/rev3/PH-D00A_WORK_BLOCK_FRAME.json",
            historical_root / "PH-D00A_WORK_BLOCK_FRAME.json",
        ),
        (
            control_source_commit,
            "control/rev3/D00A_PHASE_STATE.json",
            historical_root / "D00A_PHASE_STATE.json",
        ),
    ]
    for package_name in (
        "artifact_manifest.json",
        "changed_files.json",
        "commands.json",
        "failed_requirements.json",
        "open_terms.json",
        "phase_state.json",
        "proposed_next_action.md",
        "self_audit.json",
        "summary.md",
        "test_results.json",
    ):
        path_pairs.append(
            (
                control_source_commit,
                "control/rev3/PH-D00A_OWNER_REVIEW_PACKAGE/"
                + package_name,
                historical_root / "OWNER_REVIEW_PACKAGE" / package_name,
            )
        )
    assert len(path_pairs) == 12
    for source_commit, source_path, migrated_path in path_pairs:
        assert _git_blob_sha256(source_commit, source_path) == _sha256(
            migrated_path
        )


def test_ph_d00b_entry_and_historical_migration_are_content_bound() -> None:
    control_root = REPOSITORY_ROOT / "control" / "rev3"
    attestation = _json(
        control_root / "PH-D00A_EVIDENCE_ATTESTATION.json"
    )
    phase_state_path = control_root / "D00A_PHASE_STATE.json"
    assert _sha256(phase_state_path) == attestation["phase_state_sha256"]

    decision = _json(
        control_root
        / "OWNER_DECISION_CAPTURES"
        / "PH-D00A_TO_PH-D00B_20260731.json"
    )
    decision_body = dict(decision)
    for excluded in decision["digest_excluded_fields"]:
        decision_body.pop(str(excluded))
    assert decision["owner_decision_content_digest"] == (
        "sha256:" + digest_object(decision_body)
    )
    assert decision["target_evidence_commit"] == (
        attestation["evidence_commit"]
    )
    assert decision["target_artifact_digest"] == (
        attestation["evidence_payload_digest"]
    )

    approval = _json(
        control_root
        / "OWNER_APPROVAL_RECORDS"
        / "PH-D00A_TO_PH-D00B_20260731.json"
    )
    approval_body = dict(approval)
    for excluded in approval["digest_excluded_fields"]:
        approval_body.pop(str(excluded))
    assert approval["approval_artifact_digest"] == (
        "owner-approval-record:" + digest_object(approval_body)
    )
    assert approval["owner_decision_capture_digest"] == (
        decision["owner_decision_content_digest"]
    )
    assert approval["next_phase_id"] == "PH-D00B"
    assert approval["next_phase_authorized"] is True

    transition = _json(
        control_root / "PHASE_TRANSITIONS" / "PH-D00A_TO_PH-D00B.json"
    )
    transition_body = dict(transition)
    for excluded in transition["digest_excluded_fields"]:
        transition_body.pop(str(excluded))
    assert transition["content_digest"] == (
        "rev3-phase-transition:" + digest_object(transition_body)
    )
    assert transition["from_phase_id"] == "PH-D00A"
    assert transition["to_phase_id"] == "PH-D00B"
    assert transition["authorization_digest"] == (
        approval["approval_artifact_digest"]
    )
    assert transition["external_irreversible_action_authorized"] is False

    frame = _json(control_root / "PH-D00B_WORK_BLOCK_FRAME.json")
    frame_body = dict(frame)
    for excluded in frame["digest_excluded_fields"]:
        frame_body.pop(str(excluded))
    assert frame["content_digest"] == (
        "rev3-work-block-frame:" + digest_object(frame_body)
    )
    assert frame["phase_id"] == "PH-D00B"
    assert frame["owner_authority"]["entry_approval_digest"] == (
        approval["approval_artifact_digest"]
    )
    assert all(value == 0 for value in frame["resource_budget"].values())

    selector = _json(control_root / "REV3_CURRENT_SELECTOR.json")
    assert selector["active_phase"] == "PH-D01A"
    assert selector["ph_d00a_status"] == "OWNER_APPROVED_PASS"
    assert selector["ph_d00b_status"] == "OWNER_APPROVED_PASS"
    assert selector["ph_d01a_status"] == "IN_PROGRESS"

    historical_root = (
        control_root / "HISTORICAL_PRE_AUDIT" / "PH-D00B"
    )
    path_pairs = [
        (
            "65d0ba27e3137a670c76db13893c10b6ffebd7b2",
            "control/rev3/PH-D00B_WORK_BLOCK_FRAME.json",
            historical_root / "PH-D00B_WORK_BLOCK_FRAME.json",
        ),
        (
            "74a5c06fc2f4b0bc31e4ac4f6dd77aa06ed28dca",
            "control/rev3/D00B_PHASE_STATE.json",
            historical_root / "D00B_PHASE_STATE.json",
        ),
        (
            "4f149ea2730568e2af89efef136a696b829c0601",
            "control/rev3/PHASE_TRANSITIONS/PH-D00A_TO_PH-D00B.json",
            historical_root
            / "PHASE_TRANSITIONS"
            / "PH-D00A_TO_PH-D00B.json",
        ),
        (
            "25a4363fc1dfe78d47106f715db65c36d393210f",
            "control/rev3/PHASE_TRANSITIONS/PH-D00B_TO_PH-D01A.json",
            historical_root
            / "PHASE_TRANSITIONS"
            / "PH-D00B_TO_PH-D01A.json",
        ),
    ]
    for package_name in (
        "artifact_manifest.json",
        "changed_files.json",
        "commands.json",
        "failed_requirements.json",
        "open_terms.json",
        "phase_state.json",
        "proposed_next_action.md",
        "self_audit.json",
        "summary.md",
        "test_results.json",
    ):
        path_pairs.append(
            (
                "e7f99beff6e6fba343e6ce069434c6a28b040039",
                "control/rev3/PH-D00B_OWNER_REVIEW_PACKAGE/"
                + package_name,
                historical_root
                / "OWNER_REVIEW_PACKAGE"
                / package_name,
            )
        )
    assert len(path_pairs) == 14
    for source_commit, source_path, migrated_path in path_pairs:
        assert _git_blob_sha256(source_commit, source_path) == _sha256(
            migrated_path
        )


def test_ph_d02c_phase_state_binds_typed_ir_result_and_boundaries() -> None:
    state_path = (
        REPOSITORY_ROOT / "control" / "rev3" / "D02C_PHASE_STATE.json"
    )
    package_state_path = (
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "PH-D02C_OWNER_REVIEW_PACKAGE"
        / "phase_state.json"
    )
    state = _json(state_path)
    state_body = dict(state)
    claimed = str(state_body.pop("content_digest"))

    assert state == _json(package_state_path)
    assert claimed == "rev3-d02c-phase-state:" + digest_object(state_body)
    assert state["phase_id"] == "PH-D02C"
    assert state["status"] == "CODEX_SELF_AUDIT_PASS"
    assert state["result_commit"] == (
        "fbb36321a7ece68e2692e0c3a81c323b431e87c9"
    )
    assert state["result_tree"] == (
        "7300c53858f55f0c2ab4af9b523de77efcca0714"
    )
    assert state["owner_review_required"] is False
    assert state["owner_decisions_required"] == []
    assert state["failed_requirement_ids"] == []
    assert state["open_terms"] == []
    assert state["changed_files"] == sorted(state["changed_files"])
    assert len(state["changed_files"]) == 30

    invariants = state["phase_invariants"]
    assert invariants["common_type_count"] == 18
    assert invariants["arc2_opcode_count"] == 33
    assert invariants["arc3_opcode_count"] == 18
    assert invariants["total_domain_opcode_count"] == 51
    assert invariants["operator_metadata_complete_count"] == 51
    assert invariants["operator_type_resolution_count"] == 51
    assert invariants["operator_test_vector_count"] == 51
    assert invariants["valid_ir_vector_count"] == 51
    assert invariants["valid_ir_vector_pass_count"] == 51
    assert invariants["invalid_ir_vector_count"] == 15
    assert invariants["invalid_ir_vector_pass_count"] == 15
    assert invariants["schema_inventory_count"] == 38
    assert invariants["refined_schema_count"] == 2
    assert invariants["unchanged_schema_count"] == 36
    assert invariants["typed_ir_fail_closed"] is True
    assert invariants["unknown_opcode_fail_closed"] is True
    assert invariants["type_mismatch_fail_closed"] is True
    assert invariants["identity_routing_rejected"] is True
    assert invariants["answer_copy_rejected"] is True
    assert invariants["fixed_action_sequence_rejected"] is True
    assert invariants["ordinary_operator_order_preserved"] is True
    assert invariants["selector_zero_one_multiple_explicit"] is True
    assert invariants["causal_overclaim_rejected"] is True
    assert invariants["resource_overflow_suspends"] is True
    assert invariants["synthetic_opcode_execution_count"] == 51
    assert invariants["synthetic_intervention_execution_count"] == 1
    assert invariants["real_intervention_execution_count"] == 0
    assert invariants["causal_mechanism_assertion_count"] == 0
    assert invariants["independent_process_rebuild_count"] == 3
    assert invariants["deterministic_artifact_count"] == 51
    assert invariants["deterministic_artifacts_byte_identical"] is True
    assert invariants["scope_guard_finding_count"] == 0
    assert invariants["frozen_d02a_artifact_unchanged_count"] == 8
    assert invariants["source_payload_read_count"] == 0
    assert invariants["source_execution_count"] == 0
    assert invariants["real_trajectory_normalization_count"] == 0
    assert invariants["ph_d02c_typed_causal_ir_started"] is True
    assert invariants["interpreter_started"] is True
    assert invariants["verifier_abi_started"] is True
    assert invariants["golden_freeze_started"] is False
    assert invariants["sealed_corpus_started"] is False
    assert invariants["candidate_generation_started"] is False
    assert invariants["rule_promotion_count"] == 0
    assert invariants["owner_approval_generated_count"] == 0
    assert invariants["official_access_count"] == 0
    assert invariants["kaggle_mutation_count"] == 0
    assert invariants["preexisting_dirty_file_count"] == 32
    assert invariants["preexisting_dirty_aggregate_sha256"] == (
        "3bb18c20566ad712e0cbf00604e83da9c7afdecf469d261974da046632a5d1f4"
    )
    assert invariants["next_phase"] == "PH-D03A"
    assert invariants["next_phase_started"] is False

    conformance = state["tests"][
        "typed_causal_ir_contract_and_conformance"
    ]
    assert conformance["gates"] == {
        "DG-03": "PASS_TYPED_EXECUTABLE_IR_AND_STABLE_ERRORS",
        "DG-08": "PASS_PRIVILEGED_ROUTING_REJECTED",
        "DG-09": "PASS_PREDICTIVE_SCOPE_NO_CAUSAL_OVERCLAIM",
        "DG-12": "PASS_RESOURCE_OVERFLOW_SUSPENDS",
    }
    assert state["tests"]["dedicated_causal_ir_and_schema"]["passed"] == 87
    assert state["tests"]["distillation_full"]["passed"] == 219
    assert state["tests"]["rev3_governance"]["passed"] == 24
    assert state["tests"]["hds_dependency_audit"]["passed"] == 14
    assert state["tests"]["full_unit"]["passed"] == 712
    assert state["tests"]["integration"]["passed"] == 8
    assert state["tests"]["artifact_rebuild"]["artifact_count"] == 51
    assert state["tests"]["focused_distillation_rev3_evidence"][
        "passed"
    ] == 259
    assert "PH_D02C_SYNTHETIC_TYPED_IR_PASS" in state["claim_allowed"]
    assert "GOLDEN_CONFORMANCE_CORPUS_FROZEN" in (
        state["claim_prohibited"]
    )
    assert "CAUSAL_MECHANISM_ESTABLISHED" in state["claim_prohibited"]
    assert "HDS_STRUCTURE_BUNDLE_OWNER_APPROVED" in (
        state["claim_prohibited"]
    )

    result_commit = str(state["result_commit"])
    for artifact in state["artifacts"]:
        assert _git_blob_sha256(
            result_commit,
            str(artifact["path"]),
        ) == artifact["sha256"]


def test_ph_d02c_owner_review_package_is_complete_and_claim_limited(
) -> None:
    package_root = (
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "PH-D02C_OWNER_REVIEW_PACKAGE"
    )
    required = {
        "changed_files.json",
        "commands.json",
        "failed_requirements.json",
        "open_terms.json",
        "phase_state.json",
        "proposed_next_action.md",
        "self_audit.json",
        "summary.md",
        "test_results.json",
    }
    assert required <= {
        path.name for path in package_root.iterdir() if path.is_file()
    }

    failed = _json(package_root / "failed_requirements.json")
    open_terms = _json(package_root / "open_terms.json")
    self_audit = _json(package_root / "self_audit.json")
    tests = _json(package_root / "test_results.json")
    changed = _json(package_root / "changed_files.json")

    assert failed["failed_requirement_count"] == 0
    assert failed["failed_requirements"] == []
    assert open_terms["open_terms"] == []
    assert open_terms["owner_decisions"] == []
    assert self_audit["decision"] == "CODEX_SELF_AUDIT_PASS"
    assert self_audit["codex_self_audit_pass"] is True
    assert tests["active_product_regression_count"] == 0
    assert tests["active_environment_failure_count"] == 0
    assert tests["active_external_service_failure_count"] == 0
    assert tests["active_tool_failure_count"] == 0
    assert tests["resolved_evidence_failure_count"] == 1
    assert tests["resolved_tool_failure_count"] == 1
    assert tests["non_gate_preexisting_style_baseline_count"] == 1
    assert changed["changed_file_count"] == 30
    assert changed["changed_files"] == sorted(changed["changed_files"])
    assert changed["excluded_preexisting_dirty_state"]["mutation"] == "NONE"
    assert changed["excluded_preexisting_dirty_state"]["staging"] == "NONE"

    summary = (package_root / "summary.md").read_text(encoding="utf-8")
    next_action = (package_root / "proposed_next_action.md").read_text(
        encoding="utf-8"
    )
    assert "PH_D02C_SYNTHETIC_TYPED_IR_PASS" in summary
    assert "not started" in summary
    assert "Proceed to `PH-D03A`" in next_action
    assert "does not let Codex fabricate Owner approval" in next_action


def test_ph_d02c_artifact_manifest_binds_snapshot_bytes() -> None:
    manifest = _json(
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "PH-D02C_OWNER_REVIEW_PACKAGE"
        / "artifact_manifest.json"
    )
    body = dict(manifest)
    for excluded in manifest["digest_excluded_fields"]:
        body.pop(excluded)

    assert manifest["content_digest"] == (
        "rev3-d02c-owner-review-artifact-manifest:"
        + digest_object(body)
    )
    assert manifest["content_digest"] == (
        "rev3-d02c-owner-review-artifact-manifest:"
        "8d1dce7eb8385d8e72fdc2b8fd7ee24b1bc45ff5c9c6c4208d18d74bc7cf0361"
    )
    assert manifest["phase_id"] == "PH-D02C"
    assert manifest["result_commit"] == (
        "fbb36321a7ece68e2692e0c3a81c323b431e87c9"
    )
    assert manifest["result_tree"] == (
        "7300c53858f55f0c2ab4af9b523de77efcca0714"
    )
    assert manifest["snapshot_commit"] == (
        "c427376e34374a40f44334699fc1528c8b3dac9c"
    )
    assert manifest["snapshot_tree"] == (
        "dc2e69a1fa53f6bf4e31c697d551342071e8ef8d"
    )
    assert manifest["manifest_excludes_self"] is True
    assert manifest["artifact_count"] == len(manifest["artifacts"]) == 41
    artifact_paths = [
        str(artifact["path"]) for artifact in manifest["artifacts"]
    ]
    assert artifact_paths == sorted(artifact_paths)
    assert len(artifact_paths) == len(set(artifact_paths))
    assert (
        "control/rev3/PH-D02C_OWNER_REVIEW_PACKAGE/artifact_manifest.json"
        not in artifact_paths
    )

    snapshot_commit = str(manifest["snapshot_commit"])
    for artifact in manifest["artifacts"]:
        assert _git_blob_sha256(
            snapshot_commit,
            str(artifact["path"]),
        ) == artifact["sha256"]


def test_historical_d00b_phase_state_and_snapshot_manifest_are_bound() -> None:
    historical_root = (
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "HISTORICAL_PRE_AUDIT"
        / "PH-D00B"
    )
    phase_state_path = (
        historical_root / "D00B_PHASE_STATE.json"
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
        historical_root
        / "OWNER_REVIEW_PACKAGE"
        / "phase_state.json"
    ).read_bytes()

    artifact_manifest = _json(
        historical_root
        / "OWNER_REVIEW_PACKAGE"
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


def test_current_d01a_source_inventory_and_provenance_are_content_bound() -> None:
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
        "faed29f65eaa34fabc7a357d654a1514cc77d224db6e7bba318cc55f0e837eb4"
    )
    assert frame["phase_id"] == "PH-D01A"
    assert frame["base_commit"] == (
        "b3326dfb6c60a15387895a3bed1b5222bb622d6b"
    )
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

    provenance = _json(
        REPOSITORY_ROOT
        / "distillation"
        / "artifacts"
        / "reports"
        / "primary_source_provenance.json"
    )
    provenance_body = dict(provenance)
    for excluded in provenance["digest_excluded_fields"]:
        provenance_body.pop(str(excluded))
    assert provenance["content_digest"] == (
        "hds-primary-source-provenance-report:"
        + digest_object(provenance_body)
    )
    assert provenance["content_digest"] == (
        "hds-primary-source-provenance-report:"
        "5f874b46a83e47407f3caf92be5cab1f3c3214a9e1b4c3ea0d9b412b55ef94e9"
    )
    assert provenance["source_inventory_digest"] == report["content_digest"]
    assert provenance["raw_recording_provenance_count"] == 25
    assert provenance["canonical_corpus_source_count"] == 3
    assert provenance["provenance_relation_count"] == 75
    assert provenance["covered_level_count"] == 183
    assert provenance["raw_trajectory_to_s5_provenance_complete"] is True
    assert provenance["artifact_layer_policy"][
        "derived_distillation_evidence_admitted_source_count"
    ] == 0
    assert provenance["artifact_layer_policy"][
        "governance_artifact_admitted_source_count"
    ] == 0

    transition = _json(
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "PHASE_TRANSITIONS"
        / "PH-D00B_TO_PH-D01A.json"
    )
    transition_body = dict(transition)
    for excluded in transition["digest_excluded_fields"]:
        transition_body.pop(str(excluded))
    assert transition["content_digest"] == (
        "rev3-phase-transition:" + digest_object(transition_body)
    )
    assert transition["from_phase_id"] == "PH-D00B"
    assert transition["to_phase_id"] == "PH-D01A"
    assert transition["authorization_digest"] == (
        "owner-approval-record:"
        "1834f89329a513aacab72f84a7a1a137916fad2831b916c60990b39cd3405e95"
    )
    assert transition["external_irreversible_action_authorized"] is False

    selector = _json(
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "REV3_CURRENT_SELECTOR.json"
    )
    assert selector["active_phase"] == "PH-D01A"
    assert selector["ph_d00b_status"] == "OWNER_APPROVED_PASS"
    assert selector["ph_d01a_status"] == "IN_PROGRESS"
    assert selector["phase_entry_approval"]["target_evidence_commit"] == (
        "bdcc41f15b456d3735744df35308b9d559eff64c"
    )


def test_historical_d01a_control_artifacts_are_byte_identical() -> None:
    historical_root = (
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "HISTORICAL_PRE_AUDIT"
        / "PH-D01A"
    )
    path_pairs = [
        (
            "31a6f1eefabee1a19828c024b5619d11a835188f",
            "control/rev3/PH-D01A_WORK_BLOCK_FRAME.json",
            historical_root / "PH-D01A_WORK_BLOCK_FRAME.json",
        ),
        (
            "50b8259fce783fc2cc28158756a020575eb5e25d",
            "control/rev3/D01A_PHASE_STATE.json",
            historical_root / "D01A_PHASE_STATE.json",
        ),
        (
            "e7d14a12be4fef46854d08bef601f40a2da74941",
            "control/rev3/PHASE_TRANSITIONS/PH-D01A_TO_PH-D01B.json",
            historical_root
            / "PHASE_TRANSITIONS"
            / "PH-D01A_TO_PH-D01B.json",
        ),
    ]
    for package_name in (
        "changed_files.json",
        "commands.json",
        "failed_requirements.json",
        "open_terms.json",
        "phase_state.json",
        "proposed_next_action.md",
        "self_audit.json",
        "summary.md",
        "test_results.json",
    ):
        path_pairs.append(
            (
                "50b8259fce783fc2cc28158756a020575eb5e25d",
                "control/rev3/PH-D01A_OWNER_REVIEW_PACKAGE/"
                + package_name,
                historical_root
                / "OWNER_REVIEW_PACKAGE"
                / package_name,
            )
        )
    path_pairs.append(
        (
            "9eee596736cc917d399041f875639892efe55f08",
            "control/rev3/PH-D01A_OWNER_REVIEW_PACKAGE/"
            "artifact_manifest.json",
            historical_root
            / "OWNER_REVIEW_PACKAGE"
            / "artifact_manifest.json",
        )
    )
    assert len(path_pairs) == 13
    for source_commit, source_path, migrated_path in path_pairs:
        assert _git_blob_sha256(source_commit, source_path) == _sha256(
            migrated_path
        )

    artifact_manifest = _json(
        historical_root / "OWNER_REVIEW_PACKAGE" / "artifact_manifest.json"
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
