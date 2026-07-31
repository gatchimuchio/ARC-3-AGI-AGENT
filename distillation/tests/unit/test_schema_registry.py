from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path
from typing import Any, cast

import pytest

import hds_distill.schema_registry as schema_registry
from hds_distill.operator_registry import build_operator_registry
from hds_distill.schema_registry import (
    HDS_STATE_AXES,
    INVALID_CASES,
    SCHEMA_BY_FILENAME,
    SCHEMA_BY_NAME,
    SCHEMA_DEFINITIONS,
    SchemaRegistry,
    SchemaValidationError,
    build_multi_causal_example_bundle,
    build_multi_selection_suspend_example_bundle,
    build_phase_d02b_artifacts,
    build_schema_contract,
    build_schema_payloads,
    build_valid_example_set,
    build_zero_selection_multi_causal_example_bundle,
    load_schema_documents,
    materialize_invalid_case,
    validate_json_schema_instance,
)
from hds_distill.verification import build_valid_ir_vector_artifact

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DISTILLATION_ROOT = REPOSITORY_ROOT / "distillation"
SCHEMA_ROOT = DISTILLATION_ROOT / "schemas"
CONTRACT_PATH = DISTILLATION_ROOT / "input" / "schema_contract.json"
VALID_EXAMPLES_PATH = (
    DISTILLATION_ROOT
    / "artifacts/test_vectors/schema_examples/valid_schema_examples.json"
)
INVALID_EXAMPLES_PATH = (
    DISTILLATION_ROOT
    / "artifacts/test_vectors/schema_examples/invalid_schema_bundles.json"
)
CONFORMANCE_PATH = DISTILLATION_ROOT / "artifacts/reports/schema_conformance.json"
D02B_ARTIFACT_MANIFEST_PATH = (
    REPOSITORY_ROOT
    / "control"
    / "rev3"
    / "HISTORICAL_PRE_AUDIT"
    / "PH-D02B"
    / "OWNER_REVIEW_PACKAGE"
    / "artifact_manifest.json"
)
PH_D01B_DOWNSTREAM_INVALIDATION_PATH = (
    DISTILLATION_ROOT
    / "artifacts"
    / "reports"
    / "ph_d01b_downstream_invalidation.json"
)

AUTHORITY_SCHEMA_NAMES = (
    "DependencyLock",
    "SourceProfile",
    "SourceContentManifest",
    "AcquisitionRecord",
    "EnvironmentManifest",
    "RunManifest",
    "ResourceProfile",
    "OperatorRegistry",
    "ARC2TeacherCase",
    "ARC3TeacherTrajectory",
    "ARC3ActionRecord",
    "RawObservation",
    "DeterministicDerivation",
    "InterpretationHypothesis",
    "EvidenceRecord",
    "DistillationFrame",
    "HypothesisIR",
    "CounterfactualInterventionPlan",
    "InterventionResult",
    "LLMCaptureRecord",
    "ModelRecord",
    "GateResult",
    "DecisionRecord",
    "HDSCausalRecord",
    "RuleAtom",
    "RuleFamily",
    "BoundaryRecord",
    "CounterexampleRecord",
    "FailureSignature",
    "NormalizationCertificate",
    "PromotionDecision",
    "ApprovalRecord",
    "OpenTermRecord",
    "ClaimRecord",
    "DistillationAudit",
    "CoverageReport",
    "CompletionStateRegistry",
    "FrozenArtifactManifest",
)


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return cast(dict[str, Any], value)


@pytest.fixture(scope="module")
def schema_payloads() -> dict[str, bytes]:
    return build_schema_payloads(SCHEMA_ROOT)


@pytest.fixture(scope="module")
def registry(schema_payloads: dict[str, bytes]) -> SchemaRegistry:
    documents = {
        SCHEMA_BY_FILENAME[filename].name: cast(
            dict[str, schema_registry.JsonValue],
            json.loads(payload),
        )
        for filename, payload in schema_payloads.items()
    }
    return SchemaRegistry(documents, build_schema_contract())


@pytest.fixture(scope="module")
def valid_example_set() -> dict[str, Any]:
    return cast(dict[str, Any], build_valid_example_set(REPOSITORY_ROOT))


@pytest.fixture(scope="module")
def valid_envelopes(
    valid_example_set: dict[str, Any],
) -> list[dict[str, Any]]:
    return cast(list[dict[str, Any]], valid_example_set["examples"])


def test_catalog_matches_authority_order_one_to_one() -> None:
    assert tuple(item.name for item in SCHEMA_DEFINITIONS) == (AUTHORITY_SCHEMA_NAMES)
    assert tuple(item.index for item in SCHEMA_DEFINITIONS) == tuple(range(1, 39))
    assert len(SCHEMA_BY_NAME) == 38
    assert len(SCHEMA_BY_FILENAME) == 38


def test_disk_inventory_is_exactly_thirty_eight_schema_files() -> None:
    expected = {definition.filename for definition in SCHEMA_DEFINITIONS}
    actual = {path.name for path in SCHEMA_ROOT.glob("*.schema.json")}

    assert actual == expected
    assert len(actual) == 38


def test_five_prior_phase_schema_bytes_are_preserved(
    schema_payloads: dict[str, bytes],
) -> None:
    preserved = [
        definition for definition in SCHEMA_DEFINITIONS if definition.preserved
    ]

    assert len(preserved) == 5
    for definition in preserved:
        assert (
            hashlib.sha256(schema_payloads[definition.filename]).hexdigest()
            == definition.preserved_sha256
        )


def test_d02c_refines_exactly_two_d02b_schema_documents(
    schema_payloads: dict[str, bytes],
) -> None:
    manifest = _json(D02B_ARTIFACT_MANIFEST_PATH)
    prior_hashes = {
        Path(cast(str, item["path"])).name: cast(str, item["sha256"])
        for item in cast(list[dict[str, Any]], manifest["artifacts"])
        if cast(str, item["path"]).startswith("distillation/schemas/")
        and cast(str, item["path"]).endswith(".schema.json")
    }
    refined = {
        "hypothesis_ir.schema.json",
        "operator_registry.schema.json",
    }

    generated_filenames = {
        definition.filename
        for definition in SCHEMA_DEFINITIONS
        if not definition.preserved
    }
    assert set(prior_hashes) == generated_filenames
    for filename in generated_filenames:
        payload = schema_payloads[filename]
        current = hashlib.sha256(payload).hexdigest()
        if filename in refined:
            assert current != prior_hashes[filename]
        else:
            assert current == prior_hashes[filename]


def test_d02c_ir_schema_refinements_are_closed_and_executable(
    schema_payloads: dict[str, bytes],
) -> None:
    hypothesis = cast(
        dict[str, Any],
        json.loads(schema_payloads["hypothesis_ir.schema.json"]),
    )
    operator_registry = cast(
        dict[str, Any],
        json.loads(schema_payloads["operator_registry.schema.json"]),
    )
    hypothesis_properties = cast(dict[str, Any], hypothesis["properties"])
    node = cast(
        dict[str, Any],
        hypothesis_properties["operator_graph"]["items"],
    )
    entry = cast(
        dict[str, Any],
        operator_registry["properties"]["entries"]["items"],
    )

    assert hypothesis["additionalProperties"] is False
    assert node["additionalProperties"] is False
    assert {
        "abi",
        "claim_scope",
        "inputs",
        "output_refs",
        "resource_limit",
    } <= set(hypothesis_properties)
    assert {
        "commutes_with",
        "content_digest",
        "execution_semantics",
        "selector_cardinality",
    } <= set(entry["properties"])
    assert "EXECUTABLE_TYPED_SUBSET_IN_PH_D02C" in (hypothesis["x-hds-semantic-rules"])


def test_d02c_executable_program_and_registry_match_refined_schemas(
    schema_payloads: dict[str, bytes],
) -> None:
    vectors = build_valid_ir_vector_artifact()
    first = cast(list[dict[str, Any]], vectors["vectors"])[0]
    hypothesis_schema = cast(
        dict[str, schema_registry.JsonValue],
        json.loads(schema_payloads["hypothesis_ir.schema.json"]),
    )
    registry_schema = cast(
        dict[str, schema_registry.JsonValue],
        json.loads(schema_payloads["operator_registry.schema.json"]),
    )

    validate_json_schema_instance(
        hypothesis_schema,
        cast(dict[str, schema_registry.JsonValue], first["program"]),
    )
    validate_json_schema_instance(
        registry_schema,
        build_operator_registry("ARC2"),
    )


def test_thirty_three_generated_schemas_are_closed_and_bound(
    schema_payloads: dict[str, bytes],
) -> None:
    generated = [
        definition for definition in SCHEMA_DEFINITIONS if not definition.preserved
    ]

    assert len(generated) == 33
    for definition in generated:
        document = cast(
            dict[str, Any],
            json.loads(schema_payloads[definition.filename]),
        )
        assert document["additionalProperties"] is False
        assert document["x-hds-schema-name"] == definition.name
        assert document["x-hds-primary-id-field"] == (definition.id_field)
        assert document["x-hds-digest-field"] == (definition.digest_field)
        assert set(document["required"]) == set(definition.required_fields)


def test_schema_contract_binds_inventory_axes_and_phase_boundaries() -> None:
    contract = build_schema_contract()

    assert contract == _json(CONTRACT_PATH)
    assert contract["inventory_count"] == 38
    assert len(cast(list[Any], contract["schema_entries"])) == 38
    entries = cast(list[dict[str, Any]], contract["schema_entries"])
    assert {entry["filename"]: entry["schema_sha256"] for entry in entries} == {
        definition.filename: hashlib.sha256(
            (SCHEMA_ROOT / definition.filename).read_bytes()
        ).hexdigest()
        for definition in SCHEMA_DEFINITIONS
    }
    assert contract["hds_state_axes"] == {
        axis: list(values) for axis, values in sorted(HDS_STATE_AXES.items())
    }
    boundaries = cast(dict[str, Any], contract["phase_boundaries"])
    assert boundaries["ph_d02c_typed_causal_ir_started"] is True
    assert boundaries["interpreter_started"] is True
    assert boundaries["real_trajectory_normalization_count"] == 0
    assert boundaries["rule_promotion_count"] == 0
    assert boundaries["official_access_count"] == 0
    assert boundaries["kaggle_mutation_count"] == 0


def test_valid_fixture_has_one_digest_bound_example_per_schema(
    valid_example_set: dict[str, Any],
    valid_envelopes: list[dict[str, Any]],
) -> None:
    assert valid_example_set["example_count"] == 38
    assert valid_example_set["owner_approval_generated"] is False
    assert valid_example_set["synthetic_fixture_only"] is True
    assert [item["schema_name"] for item in valid_envelopes] == list(
        AUTHORITY_SCHEMA_NAMES
    )


def test_full_positive_bundle_resolves_all_typed_references(
    registry: SchemaRegistry,
    valid_envelopes: list[dict[str, Any]],
) -> None:
    records = registry.validate_bundle(
        cast(
            list[dict[str, schema_registry.JsonValue]],
            valid_envelopes,
        )
    )

    assert len(records) == 38
    assert {record.schema_name for record in records} == set(AUTHORITY_SCHEMA_NAMES)


@pytest.mark.parametrize(
    ("case_id", "expected_code"),
    INVALID_CASES,
)
def test_negative_bundles_fail_with_stable_codes(
    registry: SchemaRegistry,
    valid_envelopes: list[dict[str, Any]],
    case_id: str,
    expected_code: str,
) -> None:
    invalid = materialize_invalid_case(
        cast(
            list[dict[str, schema_registry.JsonValue]],
            valid_envelopes,
        ),
        case_id,
    )

    with pytest.raises(SchemaValidationError) as captured:
        registry.validate_bundle(invalid)

    assert captured.value.code == expected_code


def test_multi_causal_accepts_two_models_without_single_choice(
    registry: SchemaRegistry,
    valid_envelopes: list[dict[str, Any]],
) -> None:
    bundle = build_multi_causal_example_bundle(
        cast(
            list[dict[str, schema_registry.JsonValue]],
            valid_envelopes,
        )
    )

    records = registry.validate_bundle(bundle)
    decision = next(
        record for record in records if record.schema_name == "DecisionRecord"
    )

    assert decision.instance["decision_mode"] == "MULTI_CAUSAL"
    assert (
        len(
            cast(
                list[schema_registry.JsonValue],
                decision.instance["selected_model_refs"],
            )
        )
        == 2
    )


def test_multi_causal_accepts_zero_selected_models(
    registry: SchemaRegistry,
    valid_envelopes: list[dict[str, Any]],
) -> None:
    bundle = build_zero_selection_multi_causal_example_bundle(
        cast(
            list[dict[str, schema_registry.JsonValue]],
            valid_envelopes,
        )
    )

    records = registry.validate_bundle(bundle)
    decision = next(
        record for record in records if record.schema_name == "DecisionRecord"
    )

    assert decision.instance["decision_mode"] == "MULTI_CAUSAL"
    assert decision.instance["selected_model_refs"] == []


def test_suspend_accepts_multiple_models_and_independent_state_axes(
    registry: SchemaRegistry,
    valid_envelopes: list[dict[str, Any]],
) -> None:
    bundle = build_multi_selection_suspend_example_bundle(
        cast(
            list[dict[str, schema_registry.JsonValue]],
            valid_envelopes,
        )
    )

    records = registry.validate_bundle(bundle)
    decision = next(
        record for record in records if record.schema_name == "DecisionRecord"
    )

    assert decision.instance["decision_mode"] == "SUSPEND"
    assert (
        len(
            cast(
                list[schema_registry.JsonValue],
                decision.instance["selected_model_refs"],
            )
        )
        == 2
    )
    assert {axis: decision.instance[axis] for axis in HDS_STATE_AXES} == {
        "adoption_state": "QUARANTINE",
        "assertion_state": "FAIL",
        "closure_state": "REOPENED",
        "evidence_state": "FALSIFIED",
        "mechanism_support_state": "FALSIFIED",
        "operation_state": "PROBE",
        "update_state": "REJECTED",
    }


def test_suspend_fixture_has_no_selected_model_and_stays_held(
    registry: SchemaRegistry,
    valid_envelopes: list[dict[str, Any]],
) -> None:
    records = registry.validate_bundle(
        cast(
            list[dict[str, schema_registry.JsonValue]],
            valid_envelopes,
        )
    )
    decision = next(
        record for record in records if record.schema_name == "DecisionRecord"
    )

    assert decision.instance["decision_mode"] == "SUSPEND"
    assert decision.instance["selected_model_refs"] == []
    assert decision.instance["assertion_state"] == "SUSPEND"
    assert decision.instance["operation_state"] == "HOLD"


def test_fixture_never_fabricates_owner_approval_or_rule_promotion(
    valid_envelopes: list[dict[str, Any]],
) -> None:
    by_name = {
        item["schema_name"]: cast(dict[str, Any], item["instance"])
        for item in valid_envelopes
    }

    assert by_name["ApprovalRecord"]["approval_mode"] == ("SCHEMA_TEMPLATE")
    assert by_name["ApprovalRecord"]["authoritative"] is False
    assert by_name["ApprovalRecord"]["decision"] == "SUSPEND"
    assert by_name["PromotionDecision"]["decision"] == "PROPOSE"
    assert by_name["PromotionDecision"]["approval_ref"] is None
    assert by_name["RuleAtom"]["adoption_state"] == "PROPOSED"
    assert by_name["RuleAtom"]["approval_ref"] is None
    assert by_name["RuleFamily"]["adoption_state"] == "PROPOSED"


def test_content_id_and_digest_tampering_fail_closed(
    registry: SchemaRegistry,
    valid_envelopes: list[dict[str, Any]],
) -> None:
    resource = next(
        item for item in valid_envelopes if item["schema_name"] == "ResourceProfile"
    )
    instance = cast(dict[str, Any], copy.deepcopy(resource["instance"]))
    instance["resource_profile_id"] = "hds-resource-profile-id:" + ("0" * 64)

    with pytest.raises(
        SchemaValidationError,
        match="D02B_CONTENT_ID_MISMATCH",
    ):
        registry.validate_instance(
            "ResourceProfile",
            cast(dict[str, schema_registry.JsonValue], instance),
        )

    instance = cast(dict[str, Any], copy.deepcopy(resource["instance"]))
    instance["content_digest"] = "hds-resource-profile:" + "0" * 64
    with pytest.raises(
        SchemaValidationError,
        match="D02B_CONTENT_DIGEST_MISMATCH",
    ):
        registry.validate_instance(
            "ResourceProfile",
            cast(dict[str, schema_registry.JsonValue], instance),
        )


def test_json_schema_subset_is_strict_about_bool_integer_and_datetime() -> None:
    with pytest.raises(
        SchemaValidationError,
        match="D02B_SCHEMA_TYPE",
    ):
        validate_json_schema_instance(True, {"type": "integer"})
    with pytest.raises(
        SchemaValidationError,
        match="D02B_SCHEMA_DATETIME",
    ):
        validate_json_schema_instance(
            "not-a-timestamp",
            {"format": "date-time", "type": "string"},
        )


def test_rule_and_ir_schemas_expose_no_identity_lookup_fields(
    schema_payloads: dict[str, bytes],
) -> None:
    forbidden = {
        "answer_map",
        "fixed_action_sequence",
        "game_id",
        "level_id",
        "replay_route",
        "task_id",
    }
    for name in ("HypothesisIR", "RuleAtom", "RuleFamily"):
        definition = SCHEMA_BY_NAME[name]
        document = cast(
            dict[str, Any],
            json.loads(schema_payloads[definition.filename]),
        )
        properties = cast(dict[str, Any], document["properties"])
        assert forbidden.isdisjoint(properties)


def test_checked_artifacts_match_except_declared_d01b_invalidation() -> None:
    rebuilt = build_phase_d02b_artifacts(REPOSITORY_ROOT)
    invalidation = _json(PH_D01B_DOWNSTREAM_INVALIDATION_PATH)
    body = {
        key: value
        for key, value in invalidation.items()
        if key not in invalidation["digest_excluded_fields"]
    }
    assert invalidation["content_digest"] == (
        "hds-ph-d01b-downstream-invalidation:"
        + hashlib.sha256(
            json.dumps(
                body,
                allow_nan=False,
                ensure_ascii=False,
                separators=(",", ":"),
                sort_keys=True,
            ).encode("utf-8")
        ).hexdigest()
    )
    declared = {
        str(record["path"]): record
        for record in cast(
            list[dict[str, Any]],
            invalidation["invalidated_artifacts"],
        )
    }
    observed: dict[str, dict[str, str]] = {}

    assert len(rebuilt) == 42
    for relative_path, expected in rebuilt.items():
        checked = (REPOSITORY_ROOT / relative_path).read_bytes()
        if checked == expected:
            continue
        observed[relative_path] = {
            "checked_sha256": hashlib.sha256(checked).hexdigest(),
            "expected_rebuild_sha256": hashlib.sha256(expected).hexdigest(),
        }

    assert set(observed) == set(declared)
    assert len(observed) == invalidation["invalidated_artifact_count"] == 3
    assert len(rebuilt) - len(observed) == (
        invalidation["unaffected_rebuild_artifact_count"]
    )
    for relative_path, digests in observed.items():
        assert digests["checked_sha256"] == (
            declared[relative_path]["checked_sha256"]
        )
        assert digests["expected_rebuild_sha256"] == (
            declared[relative_path]["expected_rebuild_sha256"]
        )
        assert declared[relative_path]["owner_phase"] == "PH-D02B"
    assert invalidation["phase_order"] == {
        "current_phase": "PH-D01B",
        "next_phase": "PH-D02A",
        "invalidated_artifact_owner_phase": "PH-D02B",
        "ph_d02a_started": False,
        "ph_d02b_started": False,
        "current_phase_rebuild_permitted": False,
    }


def test_three_independent_rebuilds_are_byte_identical() -> None:
    first = build_phase_d02b_artifacts(REPOSITORY_ROOT)
    second = build_phase_d02b_artifacts(REPOSITORY_ROOT)
    third = build_phase_d02b_artifacts(REPOSITORY_ROOT)

    assert first == second == third


def test_load_from_checked_contract_and_schema_directory() -> None:
    documents = load_schema_documents(
        SCHEMA_ROOT,
        cast(
            dict[str, schema_registry.JsonValue],
            _json(CONTRACT_PATH),
        ),
    )
    registry = SchemaRegistry.from_directory(
        SCHEMA_ROOT,
        CONTRACT_PATH,
    )

    assert tuple(documents) == AUTHORITY_SCHEMA_NAMES
    assert registry.schema_names == AUTHORITY_SCHEMA_NAMES


def test_deterministically_encoded_generated_schema_drift_fails_closed(
    tmp_path: Path,
    schema_payloads: dict[str, bytes],
) -> None:
    for filename, payload in schema_payloads.items():
        (tmp_path / filename).write_bytes(payload)
    target = tmp_path / "raw_observation.schema.json"
    document = cast(dict[str, Any], json.loads(target.read_bytes()))
    document["additionalProperties"] = True
    target.write_bytes(
        json.dumps(
            document,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )

    with pytest.raises(
        SchemaValidationError,
        match="D02B_GENERATED_SCHEMA_CONTRACT_MISMATCH",
    ):
        load_schema_documents(
            tmp_path,
            build_schema_contract(),
        )


def test_checked_conformance_report_records_all_gates_and_cases() -> None:
    report = _json(CONFORMANCE_PATH)
    invalid_examples = _json(INVALID_EXAMPLES_PATH)
    valid_examples = _json(VALID_EXAMPLES_PATH)

    assert report["inventory_count"] == 38
    assert report["preserved_schema_count"] == 5
    assert report["generated_schema_count"] == 33
    assert report["positive_bundle_result"] == "PASS"
    assert report["positive_bundle_record_count"] == 38
    assert report["invalid_case_count"] == len(INVALID_CASES)
    assert report["invalid_case_pass_count"] == len(INVALID_CASES)
    assert report["multi_causal_no_single_choice_result"] == "PASS"
    assert report["multi_causal_zero_selection_result"] == "PASS"
    assert report["suspend_multiple_selection_result"] == "PASS"
    assert report["suspend_no_selected_model_result"] == "PASS"
    assert report["owner_approval_generated"] is False
    assert report["valid_example_set_digest"] == (valid_examples["content_digest"])
    assert report["invalid_example_set_digest"] == (invalid_examples["content_digest"])
    assert report["gate_results"] == {
        "DG-00": "PASS",
        "DG-01": "PASS",
        "DG-02": "PASS",
        "DG-03": "PASS_EXECUTABLE_SCHEMA_CONTRACT",
        "DG-08": "PASS_IDENTITY_ROUTING_SCHEMA_GUARD",
        "DG-09": "PASS_CLAIM_SCOPE_SCHEMA_BOUNDARY",
        "DG-12": "PASS_RESOURCE_LIMIT_SCHEMA_BOUNDARY",
        "DG-14": "PASS_SCHEMA_BOUNDARY_ONLY_NO_APPROVAL",
    }


def test_invalid_fixture_manifest_is_bound_to_expected_error_codes() -> None:
    artifact = _json(INVALID_EXAMPLES_PATH)
    cases = cast(list[dict[str, Any]], artifact["cases"])

    assert artifact["case_count"] == len(INVALID_CASES)
    assert [(case["case_id"], case["expected_error_code"]) for case in cases] == list(
        INVALID_CASES
    )
    assert artifact["owner_approval_generated"] is False
