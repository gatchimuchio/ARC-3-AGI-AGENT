"""Post-audit PH-D02C schema derivation and migration tests."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, cast

import pytest

from hds_distill.ir_types import JsonObject
from hds_distill.operator_registry import (
    build_operator_registry,
    definitions_for_domain,
)
from hds_distill.post_audit_causal_ir_schema import (
    CHANGED_SCHEMAS,
    EXPECTED_SCHEMA_CONTRACT_DIGEST,
    HISTORICAL_SOURCES,
    SCHEMA_VERSIONS,
    build_derived_schema_payloads,
    build_historical_snapshot_artifacts,
    build_post_audit_causal_ir_schema_artifacts,
    build_schema_contract,
)
from hds_distill.schema_registry import (
    SchemaValidationError,
    validate_json_schema_instance,
)
from hds_distill.verification import _build_one_opcode_program

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


def _json(payload: bytes) -> dict[str, Any]:
    value = json.loads(payload)
    assert isinstance(value, dict)
    return cast(dict[str, Any], value)


def test_schema_derivation_changes_exactly_two_versioned_schemas() -> None:
    payloads = build_derived_schema_payloads(REPOSITORY_ROOT)
    contract = build_schema_contract(REPOSITORY_ROOT)

    assert len(payloads) == 45
    assert contract["content_digest"] == EXPECTED_SCHEMA_CONTRACT_DIGEST
    assert contract["changed_schema_count"] == 2
    assert contract["unchanged_schema_count"] == 43
    assert contract["changed_schema_names"] == list(CHANGED_SCHEMAS)
    assert contract["immutability"] == {
        "ph_d02b_schema_byte_changes": 0,
        "identity_field_changes": 0,
        "digest_field_changes": 0,
        "reference_contract_changes": 0,
    }
    entries = cast(list[dict[str, Any]], contract["schema_entries"])
    changed = {entry["name"] for entry in entries if entry["changed"]}
    assert changed == set(CHANGED_SCHEMAS)
    for entry in entries:
        if entry["name"] in CHANGED_SCHEMAS:
            assert entry["schema_version"] == SCHEMA_VERSIONS[entry["name"]]
        else:
            assert (
                entry["base_schema_sha256"]
                == entry["derived_schema_sha256"]
            )


def test_refined_schemas_validate_current_ir_and_registry() -> None:
    payloads = build_derived_schema_payloads(REPOSITORY_ROOT)
    hypothesis_schema = _json(payloads["hypothesis_ir.schema.json"])
    registry_schema = _json(payloads["operator_registry.schema.json"])
    definition = definitions_for_domain("ARC2")[0]
    program = _build_one_opcode_program(definition)
    registry = build_operator_registry("ARC2")

    validate_json_schema_instance(program, hypothesis_schema)
    validate_json_schema_instance(registry, registry_schema)
    old_program = cast(JsonObject, dict(program))
    old_program["schema_version"] = "hds-causal-ir-v1"
    with pytest.raises(SchemaValidationError):
        validate_json_schema_instance(old_program, hypothesis_schema)


def test_historical_snapshot_is_exact_and_non_authoritative() -> None:
    artifacts = build_historical_snapshot_artifacts(REPOSITORY_ROOT)
    manifest = _json(
        artifacts[
            "distillation/input/historical_pre_audit/PH-D02C/"
            "SNAPSHOT_MANIFEST.json"
        ]
    )

    assert manifest["artifact_count"] == len(HISTORICAL_SOURCES) == 12
    assert manifest["eligible_for_current_activation"] is False
    assert len(artifacts) == 13


def test_complete_schema_artifact_set_is_deterministic_and_closed() -> None:
    first = build_post_audit_causal_ir_schema_artifacts(REPOSITORY_ROOT)
    second = build_post_audit_causal_ir_schema_artifacts(REPOSITORY_ROOT)

    assert first == second
    assert len(first) == 60
    schema_paths = [
        path
        for path in first
        if path.startswith("distillation/schema_sets/ph_d02c_v1/")
        and path.endswith(".schema.json")
    ]
    assert len(schema_paths) == 45
