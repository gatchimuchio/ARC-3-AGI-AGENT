from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pytest

from hds_distill.post_audit_schema_bundle import (
    BUNDLE_SCHEMA_NAMES,
    HDS_REV2_SCHEMA_NAMES,
    REQUIRED_BUNDLE_FILE_INVENTORY,
    PostAuditSchemaRegistry,
    build_post_audit_contract,
    validate_bundle_file_inventory,
)
from hds_distill.schema_registry import SchemaValidationError

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCHEMA_ROOT = (
    REPOSITORY_ROOT / "distillation/schema_sets/ph_d02b_v1"
)
CONTRACT_PATH = (
    REPOSITORY_ROOT
    / "distillation/input/post_audit_schema_bundle_contract.json"
)
EXAMPLES_PATH = (
    REPOSITORY_ROOT
    / (
        "distillation/artifacts/test_vectors/"
        "post_audit_schema_bundle_examples.json"
    )
)
INVALID_CASES_PATH = (
    REPOSITORY_ROOT
    / (
        "distillation/artifacts/test_vectors/"
        "post_audit_schema_bundle_invalid_cases.json"
    )
)
CONFORMANCE_PATH = (
    REPOSITORY_ROOT
    / (
        "distillation/artifacts/reports/"
        "post_audit_schema_bundle_conformance.json"
    )
)
DOCUMENT_CONTRACT_PATH = (
    REPOSITORY_ROOT
    / "docs/strategy/contracts/HDS_STRUCTURE_BUNDLE_CONTRACT_V1.json"
)


def _json(path: Path) -> dict[str, Any]:
    decoded = json.loads(path.read_bytes())
    assert isinstance(decoded, dict)
    return cast(dict[str, Any], decoded)


def _registry() -> PostAuditSchemaRegistry:
    return PostAuditSchemaRegistry.from_repository(REPOSITORY_ROOT)


def _examples() -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], _json(EXAMPLES_PATH)["examples"])


def _by_name() -> dict[str, dict[str, Any]]:
    return {
        item["schema_name"]: cast(dict[str, Any], item["instance"])
        for item in _examples()
    }


def _error_code(exc: pytest.ExceptionInfo[SchemaValidationError]) -> str:
    return str(exc.value).split(":", 1)[0]


def test_post_audit_contract_is_exact_and_phase_bounded() -> None:
    checked = _json(CONTRACT_PATH)
    assert checked == build_post_audit_contract(REPOSITORY_ROOT)
    assert checked["phase_id"] == "PH-D02B"
    assert checked["base_hds_schema_count"] == 38
    assert checked["bundle_schema_count"] == 7
    assert checked["total_schema_count"] == 45
    assert checked["hds_rev2_mapping_count"] == 38
    assert set(checked["hds_rev2_one_to_one_mapping"]) == set(
        HDS_REV2_SCHEMA_NAMES
    )
    boundaries = checked["phase_boundaries"]
    assert boundaries["ph_d02c_typed_causal_ir_started"] is False
    assert boundaries["interpreter_started"] is False
    assert boundaries["real_trajectory_normalization_count"] == 0
    assert boundaries["hypothesis_generation_count"] == 0
    assert boundaries["rule_promotion_count"] == 0


def test_document_contract_matches_implementation_inventory() -> None:
    checked = _json(DOCUMENT_CONTRACT_PATH)
    inventory = checked["schema_inventory"]
    assert inventory["hds_rev2_schema_count"] == len(
        HDS_REV2_SCHEMA_NAMES
    )
    assert inventory["bundle_schema_count"] == len(BUNDLE_SCHEMA_NAMES)
    assert inventory["total_schema_count"] == (
        len(HDS_REV2_SCHEMA_NAMES) + len(BUNDLE_SCHEMA_NAMES)
    )
    assert tuple(inventory["hds_rev2_schema_names"]) == (
        HDS_REV2_SCHEMA_NAMES
    )
    assert tuple(inventory["bundle_schema_names"]) == BUNDLE_SCHEMA_NAMES

    mapping = checked["hds_rev2_schema_mapping"]
    assert set(mapping) == set(BUNDLE_SCHEMA_NAMES)
    flattened = [
        schema_name
        for bundle_schema_name in BUNDLE_SCHEMA_NAMES
        for schema_name in mapping[bundle_schema_name]
    ]
    assert len(flattened) == len(HDS_REV2_SCHEMA_NAMES)
    assert len(set(flattened)) == len(flattened)
    assert set(flattened) == set(HDS_REV2_SCHEMA_NAMES)

    assert set(checked["record_schemas"]) == set(BUNDLE_SCHEMA_NAMES)
    assert tuple(checked["required_file_inventory"]) == (
        REQUIRED_BUNDLE_FILE_INVENTORY
    )


def test_schema_directory_is_one_to_one_at_forty_five() -> None:
    contract = _json(CONTRACT_PATH)
    entries = [
        *contract["hds_rev2_schema_entries"],
        *contract["bundle_schema_entries"],
    ]
    expected = {entry["filename"] for entry in entries}
    actual = {path.name for path in SCHEMA_ROOT.glob("*.schema.json")}
    assert len(expected) == len(actual) == 45
    assert expected == actual
    assert tuple(
        entry["name"] for entry in contract["hds_rev2_schema_entries"]
    ) == HDS_REV2_SCHEMA_NAMES
    assert tuple(
        entry["name"] for entry in contract["bundle_schema_entries"]
    ) == BUNDLE_SCHEMA_NAMES


def test_pre_audit_d02c_refinements_are_not_in_audited_d02b_set() -> None:
    audited_operator = SCHEMA_ROOT / "operator_registry.schema.json"
    audited_hypothesis = SCHEMA_ROOT / "hypothesis_ir.schema.json"
    live_candidate_root = REPOSITORY_ROOT / "distillation/schemas"
    assert hashlib.sha256(audited_operator.read_bytes()).hexdigest() == (
        "a1f2f2296351beafdd1b21cd66ffb39fa85fe55517af37dd9cdb77d7d012abf8"
    )
    assert hashlib.sha256(audited_hypothesis.read_bytes()).hexdigest() == (
        "8d74d1b22ccc0e8167c96209e82c9f94585dceab47d2dcbd72b5e9a3c6bfa2be"
    )
    assert audited_operator.read_bytes() != (
        live_candidate_root / "operator_registry.schema.json"
    ).read_bytes()
    assert audited_hypothesis.read_bytes() != (
        live_candidate_root / "hypothesis_ir.schema.json"
    ).read_bytes()


def test_all_forty_five_examples_validate_with_version_and_digest() -> None:
    registry = _registry()
    examples = _examples()
    records = registry.validate_bundle(examples)
    assert len(records) == 45
    assert {record.schema_name for record in records} == set(
        registry.schema_names
    )
    for item in examples:
        instance = item["instance"]
        assert isinstance(instance["schema_version"], str)
        digest_fields = (
            "acquisition_digest",
            "run_digest",
            "approval_artifact_digest",
            "content_digest",
        )
        assert any(
            isinstance(instance.get(field), str)
            for field in digest_fields
        )


def test_unknown_schema_rejects() -> None:
    registry = _registry()
    with pytest.raises(SchemaValidationError) as exc:
        registry.validate_instance("UnknownSchema", {})
    assert _error_code(exc) == "D02B_POST_AUDIT_UNKNOWN_SCHEMA"


def test_duplicate_primary_id_rejects() -> None:
    registry = _registry()
    examples = _examples()
    examples.append(copy.deepcopy(examples[-1]))
    with pytest.raises(SchemaValidationError) as exc:
        registry.validate_bundle(examples)
    assert _error_code(exc) == (
        "D02B_POST_AUDIT_DUPLICATE_PRIMARY_ID"
    )


def test_dangling_and_wrong_target_references_reject() -> None:
    registry = _registry()
    for replacement, expected in (
        (
            "hds-hypothesis-i-r-id:" + "f" * 64,
            "D02B_POST_AUDIT_DANGLING_REFERENCE",
        ),
        (
            _by_name()["ModelRecord"]["model_id"],
            "D02B_POST_AUDIT_REFERENCE_TARGET",
        ),
    ):
        examples = _examples()
        mechanism = next(
            item
            for item in examples
            if item["schema_name"] == "MechanismAssetRecord"
        )
        instance = copy.deepcopy(mechanism["instance"])
        instance["hypothesis_ir_ref"] = replacement
        mechanism["instance"] = registry.refinalize_instance(
            "MechanismAssetRecord",
            instance,
        )
        with pytest.raises(SchemaValidationError) as exc:
            registry.validate_bundle(examples)
        assert _error_code(exc) == expected


def test_raw_inference_and_semantic_derivation_reject() -> None:
    registry = _registry()
    by_name = _by_name()
    raw = copy.deepcopy(by_name["RawObservation"])
    raw["raw_value"]["inferred_goal"] = "not-observed"
    raw = registry.refinalize_instance("RawObservation", raw)
    with pytest.raises(SchemaValidationError) as exc:
        registry.validate_instance("RawObservation", raw)
    assert _error_code(exc) == "D02B_POST_AUDIT_RAW_INFERENCE"

    derivation = copy.deepcopy(by_name["DeterministicDerivation"])
    derivation["output"]["semantic_label"] = "not-deterministic"
    derivation = registry.refinalize_instance(
        "DeterministicDerivation",
        derivation,
    )
    with pytest.raises(SchemaValidationError) as exc:
        registry.validate_instance(
            "DeterministicDerivation",
            derivation,
        )
    assert _error_code(exc) == (
        "D02B_POST_AUDIT_DERIVATION_SEMANTIC"
    )


def test_suspend_allows_zero_or_multiple_but_not_exactly_one() -> None:
    registry = _registry()
    by_name = _by_name()
    original = by_name["DecisionRecord"]
    assert original["decision_mode"] == "SUSPEND"
    assert original["selected_model_refs"] == []
    registry.validate_instance("DecisionRecord", original)

    single = copy.deepcopy(original)
    single["selected_model_refs"] = [
        by_name["ModelRecord"]["model_id"]
    ]
    single["held_model_refs"] = []
    single = registry.refinalize_instance("DecisionRecord", single)
    with pytest.raises(SchemaValidationError) as exc:
        registry.validate_instance("DecisionRecord", single)
    assert _error_code(exc) == (
        "D02B_POST_AUDIT_NON_SINGLE_FORBIDS_ONE"
    )

    second_model = copy.deepcopy(by_name["ModelRecord"])
    second_model["statement"] = "Second synthetic retained model."
    second_model = registry.refinalize_instance(
        "ModelRecord",
        second_model,
    )
    multiple = copy.deepcopy(original)
    multiple["decision_mode"] = "MULTI_CAUSAL"
    multiple["selected_model_refs"] = [
        by_name["ModelRecord"]["model_id"],
        second_model["model_id"],
    ]
    multiple["held_model_refs"] = []
    multiple = registry.refinalize_instance("DecisionRecord", multiple)
    registry.validate_instance("DecisionRecord", multiple)


def test_initial_ruleatom_active_rejects() -> None:
    registry = _registry()
    rule = copy.deepcopy(_by_name()["RuleAtom"])
    rule["adoption_state"] = "ACTIVE"
    rule = registry.refinalize_instance("RuleAtom", rule)
    with pytest.raises(SchemaValidationError) as exc:
        registry.validate_instance("RuleAtom", rule)
    assert _error_code(exc) == "D02B_SCHEMA_ENUM"


def test_bundle_approval_fixture_cannot_impersonate_owner() -> None:
    registry = _registry()
    approval = copy.deepcopy(_by_name()["BundleApprovalRecord"])
    approval["owner_decision_capture_ref"] = "fake-owner-decision"
    approval = registry.refinalize_instance(
        "BundleApprovalRecord",
        approval,
    )
    with pytest.raises(SchemaValidationError) as exc:
        registry.validate_instance("BundleApprovalRecord", approval)
    assert _error_code(exc) == (
        "D02B_POST_AUDIT_APPROVAL_TEMPLATE_DRIFT"
    )


def test_bundle_file_inventory_rejects_partial_unknown_and_lock_drift() -> None:
    manifest = _by_name()["HDSStructureBundleManifest"]
    dependency = manifest["dependency_lock_digest"]
    validate_bundle_file_inventory(
        manifest,
        REQUIRED_BUNDLE_FILE_INVENTORY,
        expected_dependency_lock_digest=dependency,
    )

    with pytest.raises(SchemaValidationError) as exc:
        validate_bundle_file_inventory(
            manifest,
            REQUIRED_BUNDLE_FILE_INVENTORY[:-1],
            expected_dependency_lock_digest=dependency,
        )
    assert _error_code(exc) == "D02B_POST_AUDIT_PARTIAL_BUNDLE"

    with pytest.raises(SchemaValidationError) as exc:
        validate_bundle_file_inventory(
            manifest,
            (*REQUIRED_BUNDLE_FILE_INVENTORY, "unknown.bin"),
            expected_dependency_lock_digest=dependency,
        )
    assert _error_code(exc) == "D02B_POST_AUDIT_UNKNOWN_FILE"

    with pytest.raises(SchemaValidationError) as exc:
        validate_bundle_file_inventory(
            manifest,
            REQUIRED_BUNDLE_FILE_INVENTORY,
            expected_dependency_lock_digest="hds-dependency-lock:" + "0" * 64,
        )
    assert _error_code(exc) == (
        "D02B_POST_AUDIT_DEPENDENCY_LOCK_MISMATCH"
    )


def test_checked_invalid_manifest_and_conformance_are_bound() -> None:
    invalid = _json(INVALID_CASES_PATH)
    report = _json(CONFORMANCE_PATH)
    assert invalid["case_count"] == 9
    assert len(invalid["cases"]) == 9
    assert report["result"] == "PH_D02B_SCHEMA_SET_PASS"
    assert report["base_hds_schema_count"] == 38
    assert report["bundle_schema_count"] == 7
    assert report["total_schema_count"] == 45
    assert report["positive_record_count"] == 45
    assert report["one_to_one_hds_mapping_count"] == 38
    assert report["cross_file_reference_integrity"] == "PASS"
    assert report["unknown_file_rejection"] == "PASS"
    assert report["partial_bundle_rejection"] == "PASS"
    assert report["dependency_lock_rejection"] == "PASS"
    assert report["owner_approval_generated_count"] == 0
    assert report["rule_promotion_count"] == 0
    assert report["ph_d02c_execution_count"] == 0
