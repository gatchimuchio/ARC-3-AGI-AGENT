"""Post-audit PH-D02C schema derivation and historical snapshot contract.

The approved PH-D02B schema set is immutable input.  PH-D02C derives a new
versioned 45-schema set, changing only ``HypothesisIR`` and
``OperatorRegistry``.  The two pre-audit refinements are treated as candidate
input and are accepted only after structural boundary checks.  Their v1 schema
versions are then bumped so the executable contract never silently replaces a
previous schema under the same version.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping
from pathlib import Path
from typing import Final, cast

from .canonical import (
    DigestExclusionPolicy,
    JsonValue,
    canonical_json_document_bytes,
    content_derived_id,
    logical_content_digest,
    verify_canonical_json_document_bytes,
)
from .post_audit_schema_bundle import (
    BUNDLE_SCHEMA_NAMES,
    HDS_REV2_SCHEMA_NAMES,
    PostAuditSchemaRegistry,
)
from .schema_registry import (
    SchemaRegistry,
    SchemaValidationError,
    ValidatedRecord,
    validate_json_schema_instance,
)

type JsonObject = dict[str, JsonValue]

PHASE_ID: Final = "PH-D02C"
SCHEMA_SET_VERSION: Final = "hds-post-audit-causal-ir-schema-set-v1"
SCHEMA_CONTRACT_VERSION: Final = (
    "hds-post-audit-causal-ir-schema-contract-v1"
)
SCHEMA_CONTRACT_ID: Final = (
    "HDS-PH-D02C-POST-AUDIT-CAUSAL-IR-SCHEMA-CONTRACT-V1"
)
SCHEMA_CONTRACT_NAMESPACE: Final = (
    "hds-post-audit-causal-ir-schema-contract"
)
EXPECTED_SCHEMA_CONTRACT_DIGEST: Final = (
    "hds-post-audit-causal-ir-schema-contract:"
    "8d4acb814448b2cba3dff39162a1191aaa490261247907151f9db0750a77b646"
)

PH_D02B_CONTRACT_DIGEST: Final = (
    "hds-post-audit-schema-bundle-contract:"
    "53a1ab5360575769156028999d9181643c06eff82a4ecd04abf138ceb137f052"
)
PH_D02B_EVIDENCE_PAYLOAD_DIGEST: Final = (
    "sha256:ffb42d78bea52d7db9941979eea28e4c1b2fe431532bf32cf1ae8c8b32abb8d4"
)
PH_D02B_PHASE_STATE_SHA256: Final = (
    "5d26a6c4fea0fbf7783db9ab9dc83e47a9d8aba6618494e5c2ea7f81c7823225"
)
PH_D02C_FRAME_DIGEST: Final = (
    "rev3-work-block-frame:"
    "8cf0eda845829c194d2572934105b8b7a5d1d43f04b7798f6277033ab9cd32b4"
)
PH_D02C_ENTRY_APPROVAL_DIGEST: Final = (
    "owner-approval-record:"
    "9d738ff10ede2a4b509230a128edf2b527eb442df0181a0b50729e0d94d026b5"
)

BASE_SCHEMA_ROOT: Final = Path("distillation/schema_sets/ph_d02b_v1")
DERIVED_SCHEMA_ROOT: Final = Path("distillation/schema_sets/ph_d02c_v1")
BASE_CONTRACT_PATH: Final = Path(
    "distillation/input/post_audit_schema_bundle_contract.json"
)
DERIVED_CONTRACT_PATH: Final = Path(
    "distillation/input/post_audit_causal_ir_schema_contract.json"
)
HISTORICAL_ROOT: Final = Path(
    "distillation/input/historical_pre_audit/PH-D02C"
)

CHANGED_SCHEMAS: Final = ("HypothesisIR", "OperatorRegistry")
SCHEMA_VERSIONS: Final = {
    "HypothesisIR": "hds-causal-ir-v2",
    "OperatorRegistry": "hds-operator-registry-v2",
}
CANDIDATE_PATHS: Final = {
    "HypothesisIR": Path("distillation/schemas/hypothesis_ir.schema.json"),
    "OperatorRegistry": Path(
        "distillation/schemas/operator_registry.schema.json"
    ),
}
CANDIDATE_SHA256: Final = {
    "HypothesisIR": (
        "78507270a7acb8e7ffd9d9e2cea60a01b6fddcaed94df72f78f131cde3267f3b"
    ),
    "OperatorRegistry": (
        "be0193585650d39c78400424e3aee9aeb388b25efb30f797e3c680f9ba347c32"
    ),
}

HISTORICAL_SOURCES: Final = (
    (
        "distillation/schemas/hypothesis_ir.schema.json",
        "schemas/hypothesis_ir.schema.json",
        CANDIDATE_SHA256["HypothesisIR"],
    ),
    (
        "distillation/schemas/operator_registry.schema.json",
        "schemas/operator_registry.schema.json",
        CANDIDATE_SHA256["OperatorRegistry"],
    ),
    (
        "distillation/input/schema_contract.json",
        "schema_contract.json",
        "a70d0bb4c9944d16c7be284d7fcd267f0ee7b37988713fa713a678efbca197cc",
    ),
    (
        "distillation/input/causal_ir_contract.json",
        "generated/causal_ir_contract.json",
        "f58989fab87bc080d09001c03fe4de8ea1f84a2d41d198fa42c4fc4c04fb2bb8",
    ),
    (
        "distillation/artifacts/registries/common_type_system.json",
        "generated/registries/common_type_system.json",
        "ea4c583da2de25512f7e9e488e6b0de6f30d89664f89b02c638550c4607fec95",
    ),
    (
        "distillation/artifacts/registries/arc2_operator_registry.json",
        "generated/registries/arc2_operator_registry.json",
        "ea5c1ec3081e0da46e4b7d0d98db3de24212072070df88b59de69c027f61495d",
    ),
    (
        "distillation/artifacts/registries/arc3_operator_registry.json",
        "generated/registries/arc3_operator_registry.json",
        "7687c0b34bef4cca54d0a7c1e42d50a70a051a1e27ca1da1dd564a076adb7861",
    ),
    (
        "distillation/artifacts/registries/resource_cost_model.json",
        "generated/registries/resource_cost_model.json",
        "81fbdb62ff5f270147fc78c70392bb3c52ba8b40c37d3e9953691a8b62cf1625",
    ),
    (
        "distillation/artifacts/registries/code_ir_abi.json",
        "generated/registries/code_ir_abi.json",
        "c244e0abc18314b651f4052471715e9e3d13614453dd811cc421104689b2160a",
    ),
    (
        "distillation/artifacts/test_vectors/causal_ir/valid_ir_vectors.json",
        "generated/test_vectors/valid_ir_vectors.json",
        "efcc716dc35a9f27c552678d0c04dbaa9ee475349d84dcc2b4b4f144f727ec03",
    ),
    (
        "distillation/artifacts/test_vectors/causal_ir/invalid_ir_vectors.json",
        "generated/test_vectors/invalid_ir_vectors.json",
        "9efad720be592a32b85eb449775852ddb77880f64dcbd6f982af3e6dfc5d333d",
    ),
    (
        "distillation/artifacts/reports/causal_ir_conformance.json",
        "generated/reports/causal_ir_conformance.json",
        "a7e2bc49bd7dfdd654779af8cba4330bebcbec73154430f09ba7238b3ee36d1b",
    ),
)


class CausalIRSchemaError(ValueError):
    """Stable fail-closed error for PH-D02C schema derivation."""


class PostAuditCausalIRSchemaRegistry:
    """Validate D02C migrations while delegating unchanged records to D02B."""

    _BINDINGS: Final = {
        "HypothesisIR": (
            "hypothesis_ir_id",
            "hds-hypothesis-i-r-id",
            "hds-hypothesis-ir",
        ),
        "OperatorRegistry": (
            "operator_registry_id",
            "hds-operator-registry-id",
            "hds-operator-registry",
        ),
    }

    def __init__(self, repository_root: Path) -> None:
        self._base_registry = SchemaRegistry.from_directory(
            repository_root / "distillation/schemas",
            repository_root / "distillation/input/schema_contract.json",
        )
        payloads = build_derived_schema_payloads(repository_root)
        self._changed_documents = {
            name: _verify_schema_document_bytes(
                payloads[
                    cast(
                        str,
                        _entry_by_name(_base_contract(repository_root))[name][
                            "filename"
                        ],
                    )
                ]
            )
            for name in CHANGED_SCHEMAS
        }

    @classmethod
    def from_repository(
        cls,
        repository_root: Path,
    ) -> PostAuditCausalIRSchemaRegistry:
        return cls(repository_root)

    def validate_instance(
        self,
        schema_name: str,
        instance: Mapping[str, JsonValue],
    ) -> ValidatedRecord:
        if schema_name not in self._changed_documents:
            return self._base_registry.validate_instance(
                schema_name,
                instance,
            )
        copied = copy.deepcopy(dict(instance))
        validate_json_schema_instance(
            copied,
            self._changed_documents[schema_name],
        )
        id_field, id_namespace, digest_namespace = self._BINDINGS[
            schema_name
        ]
        primary_id = copied.get(id_field)
        content_digest = copied.get("content_digest")
        if not isinstance(primary_id, str):
            raise SchemaValidationError(
                "D02C_PRIMARY_ID_STRING_REQUIRED",
                "/" + id_field,
            )
        if not isinstance(content_digest, str):
            raise SchemaValidationError(
                "D02C_CONTENT_DIGEST_STRING_REQUIRED",
                "/content_digest",
            )
        policy = DigestExclusionPolicy(
            id_fields=frozenset({id_field}),
            digest_fields=frozenset({"content_digest"}),
        )
        if primary_id != content_derived_id(
            id_namespace,
            copied,
            policy=policy,
        ):
            raise SchemaValidationError(
                "D02C_CONTENT_ID_MISMATCH",
                "/" + id_field,
            )
        if content_digest != logical_content_digest(
            digest_namespace,
            copied,
            policy=policy,
        ):
            raise SchemaValidationError(
                "D02C_CONTENT_DIGEST_MISMATCH",
                "/content_digest",
            )
        return ValidatedRecord(
            schema_name=schema_name,
            instance=copied,
            primary_id=primary_id,
            content_digest=content_digest,
        )


def _fail(code: str, detail: str = "") -> None:
    raise CausalIRSchemaError(code + (":" + detail if detail else ""))


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _object(payload: bytes, code: str) -> JsonObject:
    try:
        value = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise CausalIRSchemaError(code) from error
    if not isinstance(value, dict):
        _fail(code)
    return cast(JsonObject, value)


def _schema_document_bytes(document: Mapping[str, JsonValue]) -> bytes:
    """Encode schema syntax without applying instance field-name semantics."""

    return (
        json.dumps(
            document,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
        + b"\n"
    )


def _verify_schema_document_bytes(payload: bytes) -> JsonObject:
    document = _object(payload, "D02C_SCHEMA_JSON_INVALID")
    if _schema_document_bytes(document) != payload:
        _fail("D02C_SCHEMA_NOT_CANONICAL")
    return document


def _base_contract(repository_root: Path) -> JsonObject:
    # This validates the exact checked PH-D02B contract and every one of its
    # 45 schema files before any D02C derivation is considered.
    PostAuditSchemaRegistry.from_repository(repository_root)
    payload = (repository_root / BASE_CONTRACT_PATH).read_bytes()
    contract = cast(
        JsonObject,
        verify_canonical_json_document_bytes(payload),
    )
    if contract.get("content_digest") != PH_D02B_CONTRACT_DIGEST:
        _fail("D02C_BASE_CONTRACT_DIGEST")
    return contract


def _entry_by_name(contract: Mapping[str, JsonValue]) -> dict[str, JsonObject]:
    raw_entries = [
        *cast(list[JsonObject], contract["hds_rev2_schema_entries"]),
        *cast(list[JsonObject], contract["bundle_schema_entries"]),
    ]
    entries = {cast(str, item["name"]): item for item in raw_entries}
    expected = set(HDS_REV2_SCHEMA_NAMES) | set(BUNDLE_SCHEMA_NAMES)
    if set(entries) != expected or len(entries) != 45:
        _fail("D02C_BASE_SCHEMA_INVENTORY")
    return entries


def _base_schema_documents(
    repository_root: Path,
    contract: Mapping[str, JsonValue],
) -> tuple[dict[str, JsonObject], dict[str, bytes]]:
    documents: dict[str, JsonObject] = {}
    payloads: dict[str, bytes] = {}
    for name, entry in _entry_by_name(contract).items():
        filename = cast(str, entry["filename"])
        path = repository_root / BASE_SCHEMA_ROOT / filename
        payload = path.read_bytes()
        if _sha256(payload) != entry["schema_sha256"]:
            _fail("D02C_BASE_SCHEMA_DIGEST", filename)
        document = _verify_schema_document_bytes(payload)
        documents[name] = document
        payloads[filename] = payload
    return documents, payloads


def _candidate_document(repository_root: Path, name: str) -> JsonObject:
    path = repository_root / CANDIDATE_PATHS[name]
    payload = path.read_bytes()
    if _sha256(payload) != CANDIDATE_SHA256[name]:
        _fail("D02C_HISTORICAL_CANDIDATE_DIGEST", name)
    return _object(payload, "D02C_HISTORICAL_CANDIDATE_JSON")


def _assert_preserved_metadata(
    base: Mapping[str, JsonValue],
    candidate: Mapping[str, JsonValue],
    name: str,
) -> None:
    for key in (
        "$schema",
        "additionalProperties",
        "type",
        "x-hds-digest-field",
        "x-hds-primary-id-field",
        "x-hds-reference-fields",
        "x-hds-schema-name",
    ):
        if candidate.get(key) != base.get(key):
            _fail("D02C_SCHEMA_METADATA_DRIFT", name + ":" + key)


def _audit_operator_registry_candidate(
    base: Mapping[str, JsonValue],
    candidate: Mapping[str, JsonValue],
) -> None:
    _assert_preserved_metadata(base, candidate, "OperatorRegistry")
    base_properties = cast(JsonObject, base["properties"])
    candidate_properties = cast(JsonObject, candidate["properties"])
    if set(candidate_properties) != set(base_properties):
        _fail("D02C_OPERATOR_TOP_LEVEL_PROPERTY_DRIFT")
    for key in set(base_properties) - {"entries"}:
        if candidate_properties[key] != base_properties[key]:
            _fail("D02C_OPERATOR_TOP_LEVEL_FIELD_DRIFT", key)
    base_entries = cast(JsonObject, base_properties["entries"])
    candidate_entries = cast(JsonObject, candidate_properties["entries"])
    base_item = cast(JsonObject, base_entries["items"])
    candidate_item = cast(JsonObject, candidate_entries["items"])
    base_item_properties = cast(JsonObject, base_item["properties"])
    candidate_item_properties = cast(JsonObject, candidate_item["properties"])
    added = set(candidate_item_properties) - set(base_item_properties)
    if added != {
        "commutes_with",
        "content_digest",
        "execution_semantics",
        "selector_cardinality",
    }:
        _fail("D02C_OPERATOR_ENTRY_EXTENSION_DRIFT")
    for key, value in base_item_properties.items():
        if candidate_item_properties.get(key) != value:
            _fail("D02C_OPERATOR_ENTRY_FIELD_DRIFT", key)
    base_required = set(cast(list[str], base_item["required"]))
    candidate_required = set(cast(list[str], candidate_item["required"]))
    if candidate_required - base_required != added:
        _fail("D02C_OPERATOR_ENTRY_REQUIRED_DRIFT")


def _audit_hypothesis_candidate(
    base: Mapping[str, JsonValue],
    candidate: Mapping[str, JsonValue],
) -> None:
    _assert_preserved_metadata(base, candidate, "HypothesisIR")
    base_properties = cast(JsonObject, base["properties"])
    candidate_properties = cast(JsonObject, candidate["properties"])
    added = set(candidate_properties) - set(base_properties)
    if added != {"abi", "claim_scope", "inputs", "output_refs", "resource_limit"}:
        _fail("D02C_HYPOTHESIS_EXTENSION_DRIFT")
    preserved = {
        "content_digest",
        "digest_excluded_fields",
        "domain",
        "exclusions",
        "falsification_procedures",
        "frame_ref",
        "hypothesis_ir_id",
        "input_types",
        "invariants",
        "ir_version",
        "operator_registry_ref",
        "resource_cost",
        "stop_conditions",
    }
    for key in preserved:
        if candidate_properties.get(key) != base_properties.get(key):
            _fail("D02C_HYPOTHESIS_FIELD_DRIFT", key)
    base_required = set(cast(list[str], base["required"]))
    candidate_required = set(cast(list[str], candidate["required"]))
    if candidate_required - base_required != added:
        _fail("D02C_HYPOTHESIS_REQUIRED_DRIFT")
    rules = candidate.get("x-hds-semantic-rules")
    if rules != [
        "EXECUTABLE_TYPED_SUBSET_IN_PH_D02C",
        "IDENTITY_ROUTING_FIELDS_FORBIDDEN",
        "ANSWER_COPY_FIELDS_FORBIDDEN",
        "CAUSAL_ESTABLISHMENT_FROM_EXACT_FIT_FORBIDDEN",
    ]:
        _fail("D02C_HYPOTHESIS_SEMANTIC_RULE_DRIFT")
    for graph_name in (
        "selector_graph",
        "preconditions",
        "operator_graph",
    ):
        graph = cast(JsonObject, candidate_properties[graph_name])
        item = cast(JsonObject, graph["items"])
        if item.get("additionalProperties") is not False:
            _fail("D02C_HYPOTHESIS_GRAPH_NOT_CLOSED", graph_name)


def _derived_documents(
    repository_root: Path,
) -> tuple[JsonObject, dict[str, JsonObject], dict[str, bytes]]:
    contract = _base_contract(repository_root)
    base_documents, base_payloads = _base_schema_documents(
        repository_root,
        contract,
    )
    candidate_hypothesis = _candidate_document(repository_root, "HypothesisIR")
    candidate_operator = _candidate_document(
        repository_root,
        "OperatorRegistry",
    )
    _audit_hypothesis_candidate(
        base_documents["HypothesisIR"],
        candidate_hypothesis,
    )
    _audit_operator_registry_candidate(
        base_documents["OperatorRegistry"],
        candidate_operator,
    )
    documents = copy.deepcopy(base_documents)
    for name, candidate in (
        ("HypothesisIR", candidate_hypothesis),
        ("OperatorRegistry", candidate_operator),
    ):
        candidate["$id"] = (
            "https://local.arc3.invalid/schemas/ph_d02c_v1/"
            + cast(str, _entry_by_name(contract)[name]["filename"])
        )
        candidate["title"] = "Post-Audit PH-D02C " + name
        properties = cast(JsonObject, candidate["properties"])
        schema_version = cast(JsonObject, properties["schema_version"])
        schema_version["const"] = SCHEMA_VERSIONS[name]
        if name == "OperatorRegistry":
            entries_schema = cast(JsonObject, properties["entries"])
            entry_schema = cast(JsonObject, entries_schema["items"])
            entry_properties = cast(JsonObject, entry_schema["properties"])
            input_types = cast(JsonObject, entry_properties["input_types"])
            input_types["uniqueItems"] = False
            candidate["x-hds-semantic-rules"] = [
                "REPEATED_TYPE_SIGNATURES_ALLOWED",
                "ENTRY_CONTENT_DIGEST_REQUIRED",
                "COMMUTATIVITY_MUST_BE_SYMMETRIC",
            ]
        documents[name] = candidate
    return contract, documents, base_payloads


def build_derived_schema_payloads(
    repository_root: Path,
) -> dict[str, bytes]:
    contract, documents, _ = _derived_documents(repository_root)
    entries = _entry_by_name(contract)
    payloads = {
        cast(str, entries[name]["filename"]): _schema_document_bytes(document)
        for name, document in documents.items()
    }
    if len(payloads) != 45:
        _fail("D02C_DERIVED_SCHEMA_COUNT")
    return dict(sorted(payloads.items()))


def _schema_name_by_filename(
    contract: Mapping[str, JsonValue],
) -> dict[str, str]:
    return {
        cast(str, entry["filename"]): name
        for name, entry in _entry_by_name(contract).items()
    }


def build_schema_contract(repository_root: Path) -> JsonObject:
    base_contract, _, base_payloads = _derived_documents(repository_root)
    derived_payloads = build_derived_schema_payloads(repository_root)
    name_by_filename = _schema_name_by_filename(base_contract)
    entries: list[JsonValue] = []
    changed_names: list[str] = []
    for filename, payload in derived_payloads.items():
        name = name_by_filename[filename]
        base_sha = _sha256(base_payloads[filename])
        derived_sha = _sha256(payload)
        document = _verify_schema_document_bytes(payload)
        properties = cast(JsonObject, document["properties"])
        version_schema = properties.get("schema_version")
        schema_version = (
            version_schema.get("const")
            if isinstance(version_schema, dict)
            else None
        )
        changed = base_sha != derived_sha
        if changed:
            changed_names.append(name)
        entries.append(
            {
                "base_schema_sha256": base_sha,
                "changed": changed,
                "derived_schema_sha256": derived_sha,
                "filename": filename,
                "name": name,
                "schema_id": document["$id"],
                "schema_version": schema_version,
            }
        )
    if tuple(sorted(changed_names)) != tuple(sorted(CHANGED_SCHEMAS)):
        _fail("D02C_DERIVED_SCHEMA_DIFF_SET")
    contract: JsonObject = {
        "schema_version": SCHEMA_CONTRACT_VERSION,
        "contract_id": SCHEMA_CONTRACT_ID,
        "phase_id": PHASE_ID,
        "schema_set_version": SCHEMA_SET_VERSION,
        "authority": {
            "ph_d02b_contract_digest": PH_D02B_CONTRACT_DIGEST,
            "ph_d02b_evidence_payload_digest": PH_D02B_EVIDENCE_PAYLOAD_DIGEST,
            "ph_d02b_phase_state_sha256": PH_D02B_PHASE_STATE_SHA256,
            "ph_d02c_entry_approval_digest": PH_D02C_ENTRY_APPROVAL_DIGEST,
            "ph_d02c_work_block_frame_digest": PH_D02C_FRAME_DIGEST,
        },
        "base_schema_set_version": base_contract["schema_set_version"],
        "base_schema_count": 45,
        "derived_schema_count": 45,
        "changed_schema_count": 2,
        "unchanged_schema_count": 43,
        "changed_schema_names": list(CHANGED_SCHEMAS),
        "version_migration": {
            "HypothesisIR": {
                "from": "hds-causal-ir-v1",
                "to": SCHEMA_VERSIONS["HypothesisIR"],
            },
            "OperatorRegistry": {
                "from": "hds-operator-registry-v1",
                "to": SCHEMA_VERSIONS["OperatorRegistry"],
            },
        },
        "candidate_input_classification": (
            "HISTORICAL_PRE_AUDIT_NONAUTHORITATIVE_REVALIDATED"
        ),
        "candidate_sha256": dict(CANDIDATE_SHA256),
        "schema_entries": entries,
        "immutability": {
            "ph_d02b_schema_byte_changes": 0,
            "identity_field_changes": 0,
            "digest_field_changes": 0,
            "reference_contract_changes": 0,
        },
        "phase_boundaries": {
            "candidate_generation_started": False,
            "golden_freeze_started": False,
            "real_trajectory_normalization_count": 0,
            "rule_promotion_count": 0,
            "runtime_started": False,
        },
        "digest_excluded_fields": ["content_digest", "contract_id"],
        "content_digest": "",
    }
    contract["content_digest"] = logical_content_digest(
        SCHEMA_CONTRACT_NAMESPACE,
        contract,
        policy=DigestExclusionPolicy(
            id_fields=frozenset({"contract_id"}),
            digest_fields=frozenset({"content_digest"}),
        ),
    )
    if (
        EXPECTED_SCHEMA_CONTRACT_DIGEST
        and contract["content_digest"] != EXPECTED_SCHEMA_CONTRACT_DIGEST
    ):
        _fail("D02C_SCHEMA_CONTRACT_DIGEST_DRIFT")
    return contract


def _historical_source_payload(
    repository_root: Path,
    source: str,
    destination: str,
    expected_sha256: str,
) -> bytes:
    frozen_path = repository_root / HISTORICAL_ROOT / destination
    source_path = repository_root / source
    path = frozen_path if frozen_path.is_file() else source_path
    payload = path.read_bytes()
    if _sha256(payload) != expected_sha256:
        _fail("D02C_HISTORICAL_SOURCE_DIGEST", source)
    return payload


def build_historical_snapshot_artifacts(
    repository_root: Path,
) -> dict[str, bytes]:
    artifacts: dict[str, bytes] = {}
    manifest_entries: list[JsonValue] = []
    for source, destination, expected_sha256 in HISTORICAL_SOURCES:
        payload = _historical_source_payload(
            repository_root,
            source,
            destination,
            expected_sha256,
        )
        relative = (HISTORICAL_ROOT / destination).as_posix()
        artifacts[relative] = payload
        manifest_entries.append(
            {
                "byte_count": len(payload),
                "destination_path": relative,
                "sha256": expected_sha256,
                "source_path": source,
            }
        )
    manifest: JsonObject = {
        "schema_version": "hds-ph-d02c-historical-snapshot-v1",
        "phase_id": PHASE_ID,
        "source_commit": "9c9cf5a9790fae341ad1be45506c88e7a7f34b58",
        "classification": "HISTORICAL_PRE_AUDIT_NONAUTHORITATIVE",
        "artifact_count": len(HISTORICAL_SOURCES),
        "artifacts": manifest_entries,
        "eligible_for_current_activation": False,
        "digest_excluded_fields": ["content_digest"],
        "content_digest": "",
    }
    manifest["content_digest"] = logical_content_digest(
        "hds-ph-d02c-historical-snapshot",
        manifest,
        policy=DigestExclusionPolicy(
            digest_fields=frozenset({"content_digest"})
        ),
    )
    artifacts[(HISTORICAL_ROOT / "SNAPSHOT_MANIFEST.json").as_posix()] = (
        canonical_json_document_bytes(manifest)
    )
    return dict(sorted(artifacts.items()))


def build_post_audit_causal_ir_schema_artifacts(
    repository_root: Path,
) -> dict[str, bytes]:
    artifacts = build_historical_snapshot_artifacts(repository_root)
    schema_payloads = build_derived_schema_payloads(repository_root)
    for filename, payload in schema_payloads.items():
        artifacts[(DERIVED_SCHEMA_ROOT / filename).as_posix()] = payload
    readme = (
        b"# PH-D02C Post-Audit Typed Causal IR Schema Set\n\n"
        b"This directory derives from the approved PH-D02B 45-schema set.\n"
        b"Exactly HypothesisIR and OperatorRegistry change, and both use new\n"
        b"schema versions. PH-D02B schema bytes remain immutable.\n"
    )
    artifacts[(DERIVED_SCHEMA_ROOT / "README.md").as_posix()] = readme
    artifacts[DERIVED_CONTRACT_PATH.as_posix()] = (
        canonical_json_document_bytes(build_schema_contract(repository_root))
    )
    return dict(sorted(artifacts.items()))


def write_post_audit_causal_ir_schema_artifacts(
    repository_root: Path,
) -> tuple[Path, ...]:
    written: list[Path] = []
    for relative_path, payload in (
        build_post_audit_causal_ir_schema_artifacts(repository_root).items()
    ):
        path = repository_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        written.append(path)
    return tuple(written)


__all__ = [
    "CausalIRSchemaError",
    "CHANGED_SCHEMAS",
    "DERIVED_CONTRACT_PATH",
    "DERIVED_SCHEMA_ROOT",
    "EXPECTED_SCHEMA_CONTRACT_DIGEST",
    "PostAuditCausalIRSchemaRegistry",
    "SCHEMA_SET_VERSION",
    "SCHEMA_VERSIONS",
    "build_derived_schema_payloads",
    "build_historical_snapshot_artifacts",
    "build_post_audit_causal_ir_schema_artifacts",
    "build_schema_contract",
    "write_post_audit_causal_ir_schema_artifacts",
]
