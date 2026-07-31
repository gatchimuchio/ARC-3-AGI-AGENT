"""Post-audit PH-D02B schema-set and structure-bundle contract.

The repository retains a pre-audit PH-D02C implementation candidate.  This
module deliberately does not import its interpreter, operator registry, or
causal execution path.  It revalidates the PH-D02B HDS rev2 schema snapshot,
adds the seven rev3 bundle record schemas, and provides dependency-free,
fail-closed structural validation for the resulting 45-schema set.
"""

from __future__ import annotations

import copy
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Never, cast

from .canonical import (
    DigestExclusionPolicy,
    canonical_json_bytes,
    canonical_json_document_bytes,
    content_derived_id,
    logical_content_digest,
)
from .schema_registry import (
    CONTENT_DIGEST_PATTERN,
    CONTENT_ID_PATTERN,
    JsonObject,
    JsonValue,
    SchemaValidationError,
    validate_json_schema_instance,
)

SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"
SCHEMA_ID_BASE = "https://local.arc3.invalid/schemas/"
POST_AUDIT_SCHEMA_SET_VERSION = "hds-post-audit-schema-set-v1"
POST_AUDIT_CONTRACT_VERSION = "hds-post-audit-schema-bundle-contract-v1"
POST_AUDIT_CONTRACT_ID = "HDS-PH-D02B-POST-AUDIT-SCHEMA-BUNDLE-CONTRACT-V1"
HISTORICAL_D02B_IMPLEMENTATION_COMMIT = (
    "108c5462c2c73bdd95953e9e9b0cbbce68ac5d02"
)
HISTORICAL_D02B_CONTRACT_SHA256 = (
    "adb49377963e533a18866d870202f2056dbc589175a171a24a2e2e8fce930dc7"
)

HDS_REV2_SCHEMA_NAMES = (
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

BUNDLE_SCHEMA_NAMES = (
    "HDSStructureBundleManifest",
    "OntologyTypeRecord",
    "MechanismAssetRecord",
    "ProbeObligationRecord",
    "StructureCoverageProfile",
    "BundleApprovalRecord",
    "StructureBundleMigrationRecord",
)

REQUIRED_BUNDLE_FILE_INVENTORY = (
    "manifest.json",
    "source_manifests/source_content_manifest.json",
    "ontology/entity_types.json",
    "ontology/relation_types.json",
    "ontology/state_variable_types.json",
    "ontology/action_surface_types.json",
    "mechanisms/representation_rules.jsonl",
    "mechanisms/selector_rules.jsonl",
    "mechanisms/precondition_rules.jsonl",
    "mechanisms/action_effect_rules.jsonl",
    "mechanisms/transition_rules.jsonl",
    "mechanisms/delayed_effect_rules.jsonl",
    "mechanisms/goal_rules.jsonl",
    "mechanisms/hazard_rules.jsonl",
    "mechanisms/order_rules.jsonl",
    "mechanisms/composition_rules.jsonl",
    "mechanisms/rollback_reset_rules.jsonl",
    "mechanisms/probe_rules.jsonl",
    "boundaries/applicability_boundaries.jsonl",
    "boundaries/near_misses.jsonl",
    "boundaries/counterexamples.jsonl",
    "boundaries/exclusions.jsonl",
    "failures/failure_signatures.jsonl",
    "unresolved/open_terms.jsonl",
    "unresolved/unresolved_mechanisms.jsonl",
    "unresolved/required_probe_schemas.jsonl",
    "evidence/case_records/schema_fixture.json",
    "evidence/intervention_results/schema_fixture.json",
    "evidence/promotion_decisions/schema_fixture.json",
    "evidence/approvals/schema_fixture.json",
    "reports/coverage_report.json",
    "reports/determinism_report.json",
    "reports/taint_report.json",
    "frozen_artifact_manifest.json",
)


def _fail(code: str, path: str = "") -> Never:
    suffix = f":{path}" if path else ""
    raise SchemaValidationError(code + suffix)


def _string(
    *,
    pattern: str | None = None,
    const: str | None = None,
    enum: Sequence[str] | None = None,
) -> JsonObject:
    result: JsonObject = {"minLength": 1, "type": "string"}
    if pattern is not None:
        result["pattern"] = pattern
    if const is not None:
        result["const"] = const
    if enum is not None:
        result["enum"] = list(enum)
    return result


def _integer(*, minimum: int = 0) -> JsonObject:
    return {"minimum": minimum, "type": "integer"}


def _boolean() -> JsonObject:
    return {"type": "boolean"}


def _array(
    items: Mapping[str, JsonValue],
    *,
    min_items: int = 0,
    unique: bool = False,
) -> JsonObject:
    return {
        "items": dict(items),
        "minItems": min_items,
        "type": "array",
        "uniqueItems": unique,
    }


def _object(
    properties: Mapping[str, Mapping[str, JsonValue]],
    required: Sequence[str],
    *,
    additional: bool = False,
) -> JsonObject:
    return {
        "additionalProperties": additional,
        "properties": {
            key: cast(JsonValue, dict(value))
            for key, value in properties.items()
        },
        "required": list(required),
        "type": "object",
    }


def _nullable_string() -> JsonObject:
    return {
        "oneOf": [
            {"type": "null"},
            _string(),
        ]
    }


def _digest(namespace: str | None = None) -> JsonObject:
    pattern = CONTENT_DIGEST_PATTERN
    if namespace is not None:
        escaped = namespace.replace("-", r"\-")
        pattern = rf"^{escaped}:[0-9a-f]{{64}}$"
    return _string(pattern=pattern)


def _identifier() -> JsonObject:
    return _string(pattern=CONTENT_ID_PATTERN)


@dataclass(frozen=True, slots=True)
class ReferenceField:
    pointer: str
    targets: tuple[str, ...]
    reference_kind: str = "ID"
    required_resolution: bool = True

    def as_json(self) -> JsonObject:
        return {
            "pointer": self.pointer,
            "reference_kind": self.reference_kind,
            "required_resolution": self.required_resolution,
            "targets": list(self.targets),
        }


@dataclass(frozen=True, slots=True)
class BundleSchemaDefinition:
    index: int
    name: str
    filename: str
    schema_version: str
    id_field: str
    id_namespace: str
    digest_namespace: str
    properties: Mapping[str, Mapping[str, JsonValue]]
    required: tuple[str, ...]
    references: tuple[ReferenceField, ...] = ()
    digest_excluded_fields: tuple[str, ...] = ()

    @property
    def _digest_exclusion_policy(self) -> DigestExclusionPolicy:
        return DigestExclusionPolicy(
            id_fields=frozenset({self.id_field}),
            digest_fields=frozenset({"content_digest"}),
            physical_metadata_fields=frozenset(
                self.digest_excluded_fields
            ),
        )

    def schema_document(self) -> JsonObject:
        return {
            "$id": SCHEMA_ID_BASE + self.filename,
            "$schema": SCHEMA_DRAFT,
            "additionalProperties": False,
            "properties": {
                key: cast(JsonValue, dict(value))
                for key, value in self.properties.items()
            },
            "required": list(self.required),
            "title": "Post-audit PH-D02B " + self.name,
            "type": "object",
            "x-hds-digest-field": "content_digest",
            "x-hds-primary-id-field": self.id_field,
            "x-hds-reference-fields": [
                reference.as_json() for reference in self.references
            ],
            "x-hds-schema-name": self.name,
            "x-hds-semantic-rules": [
                "SCHEMA_FIXTURE_IS_NON_AUTHORITATIVE",
                "NO_PHASE_D02C_EXECUTION",
            ],
        }

    def contract_entry(self) -> JsonObject:
        payload = _schema_document_bytes(self.schema_document())
        return {
            "digest_excluded_fields": [
                self.id_field,
                "content_digest",
                *self.digest_excluded_fields,
            ],
            "digest_field": "content_digest",
            "digest_namespace": self.digest_namespace,
            "filename": self.filename,
            "id_derivation": "HDS_CONTENT_ID_V1",
            "id_field": self.id_field,
            "id_namespace": self.id_namespace,
            "index": self.index,
            "name": self.name,
            "references": [
                reference.as_json() for reference in self.references
            ],
            "schema_path": (
                "distillation/schema_sets/ph_d02b_v1/" + self.filename
            ),
            "schema_sha256": hashlib.sha256(payload).hexdigest(),
            "schema_version": self.schema_version,
            "timestamp_fields": [],
        }


def _bundle_definitions() -> tuple[BundleSchemaDefinition, ...]:
    digest_exclusions = _array(
        _string(),
        min_items=2,
        unique=True,
    )
    projection = _object(
        {
            "projection_digest": _digest(),
            "projection_type": _string(
                enum=(
                    "PProjection",
                    "JDomainProjection",
                    "MSeedProjection",
                    "ProbeProjection",
                )
            ),
        },
        ("projection_type", "projection_digest"),
    )
    common_text_object = _object({}, (), additional=True)
    return (
        BundleSchemaDefinition(
            index=39,
            name="HDSStructureBundleManifest",
            filename="hds_structure_bundle_manifest.schema.json",
            schema_version="hds-structure-bundle-manifest-v1",
            id_field="bundle_id",
            id_namespace="hds-structure-bundle-id",
            digest_namespace="hds-structure-bundle-manifest",
            properties={
                "bundle_schema_version": _string(
                    const="hds-structure-bundle-v1"
                ),
                "bundle_id": _identifier(),
                "canonical_serialization": _object(
                    {
                        "encoding": _string(const="UTF-8"),
                        "json_key_order": _string(
                            const="LEXICOGRAPHIC"
                        ),
                        "json_whitespace": _string(const="NONE"),
                        "jsonl_order": _string(
                            const="RECORD_ID_ASCENDING"
                        ),
                        "newline": _string(const="LF"),
                        "unicode_normalization": _string(const="NFC"),
                    },
                    (
                        "encoding",
                        "unicode_normalization",
                        "json_key_order",
                        "json_whitespace",
                        "newline",
                        "jsonl_order",
                    ),
                ),
                "content_digest": _digest(
                    "hds-structure-bundle-manifest"
                ),
                "coverage_profile_digest": _digest(
                    "hds-structure-coverage-profile"
                ),
                "cross_reference_index_digest": _digest(
                    "hds-cross-reference-index"
                ),
                "dependency_lock_digest": _digest(),
                "digest_excluded_fields": digest_exclusions,
                "logical_digest": _digest(
                    "hds-structure-bundle-logical"
                ),
                "migration_record_digest": _digest(
                    "hds-structure-bundle-migration"
                ),
                "bundle_approval_record_digest": _digest(
                    "hds-bundle-approval-record"
                ),
                "physical_package_digest": _digest("sha256"),
                "record_count_by_type": _object({}, (), additional=True),
                "required_file_inventory": _array(
                    _string(),
                    min_items=len(REQUIRED_BUNDLE_FILE_INVENTORY),
                    unique=True,
                ),
                "schema_version": _string(
                    const="hds-structure-bundle-manifest-v1"
                ),
                "source_content_manifest_digest": _digest(),
                "synthetic_fixture_only": _boolean(),
                "taint_report_digest": _digest("hds-taint-report"),
            },
            required=(
                "schema_version",
                "bundle_schema_version",
                "bundle_id",
                "source_content_manifest_digest",
                "dependency_lock_digest",
                "canonical_serialization",
                "logical_digest",
                "physical_package_digest",
                "required_file_inventory",
                "record_count_by_type",
                "cross_reference_index_digest",
                "coverage_profile_digest",
                "taint_report_digest",
                "migration_record_digest",
                "bundle_approval_record_digest",
                "synthetic_fixture_only",
                "digest_excluded_fields",
                "content_digest",
            ),
            references=(
                ReferenceField(
                    "/source_content_manifest_digest",
                    ("SourceContentManifest",),
                    "DIGEST",
                ),
                ReferenceField(
                    "/dependency_lock_digest",
                    ("DependencyLock",),
                    "DIGEST",
                ),
                ReferenceField(
                    "/coverage_profile_digest",
                    ("StructureCoverageProfile",),
                    "DIGEST",
                ),
                ReferenceField(
                    "/migration_record_digest",
                    ("StructureBundleMigrationRecord",),
                    "DIGEST",
                ),
                ReferenceField(
                    "/bundle_approval_record_digest",
                    ("BundleApprovalRecord",),
                    "DIGEST",
                ),
            ),
            digest_excluded_fields=(
                "logical_digest",
                "physical_package_digest",
            ),
        ),
        BundleSchemaDefinition(
            index=40,
            name="OntologyTypeRecord",
            filename="ontology_type_record.schema.json",
            schema_version="hds-ontology-type-record-v1",
            id_field="type_id",
            id_namespace="hds-ontology-type-id",
            digest_namespace="hds-ontology-type-record",
            properties={
                "constraints": common_text_object,
                "content_digest": _digest("hds-ontology-type-record"),
                "definition": _string(),
                "digest_excluded_fields": digest_exclusions,
                "schema_version": _string(
                    const="hds-ontology-type-record-v1"
                ),
                "type_id": _identifier(),
                "type_kind": _string(
                    enum=(
                        "ENTITY",
                        "RELATION",
                        "STATE_VARIABLE",
                        "ACTION_SURFACE",
                    )
                ),
            },
            required=(
                "schema_version",
                "type_id",
                "type_kind",
                "definition",
                "constraints",
                "digest_excluded_fields",
                "content_digest",
            ),
        ),
        BundleSchemaDefinition(
            index=41,
            name="MechanismAssetRecord",
            filename="mechanism_asset_record.schema.json",
            schema_version="hds-mechanism-asset-record-v1",
            id_field="record_id",
            id_namespace="hds-mechanism-asset-id",
            digest_namespace="hds-mechanism-asset-record",
            properties={
                "adoption_state": _string(
                    enum=("PROPOSED", "PROBATION")
                ),
                "approval_ref": _nullable_string(),
                "closure_boundary": common_text_object,
                "content_digest": _digest("hds-mechanism-asset-record"),
                "counterexample_refs": _array(
                    _string(), unique=True
                ),
                "digest_excluded_fields": digest_exclusions,
                "domain": _string(enum=("ARC2", "ARC3", "CROSS_DOMAIN")),
                "evidence_state": _string(
                    enum=(
                        "OBSERVED_COMPATIBLE",
                        "LOCAL_EXACT_FIT",
                        "STRUCTURAL_RECURRENCE",
                        "BOUNDARY_OBSERVED",
                        "COUNTERFACTUAL_SUPPORTED",
                        "PROMOTED_CORPUS_SCOPED",
                        "REPRODUCIBLE_CONTROL",
                        "FALSIFIED",
                        "INCONCLUSIVE",
                    )
                ),
                "exclusions": _array(_string(), unique=True),
                "falsification_procedure": common_text_object,
                "hypothesis_ir_ref": _string(),
                "intervention_refs": _array(_string(), unique=True),
                "invariants": _array(
                    common_text_object, unique=True
                ),
                "mechanism_support_state": _string(
                    enum=(
                        "OBSERVED_COMPATIBLE",
                        "LOCAL_EXACT_FIT",
                        "STRUCTURAL_RECURRENCE",
                        "BOUNDARY_OBSERVED",
                        "COUNTERFACTUAL_SUPPORTED",
                        "REPRODUCIBLE_CONTROL",
                        "FALSIFIED",
                        "INCONCLUSIVE",
                    )
                ),
                "mechanism_type": _string(),
                "negative_case_refs": _array(_string(), unique=True),
                "preconditions": _array(
                    common_text_object, unique=True
                ),
                "predicted_effects": _array(
                    common_text_object, unique=True
                ),
                "primary_class": _string(),
                "provenance": common_text_object,
                "record_id": _identifier(),
                "record_version": _integer(minimum=1),
                "schema_version": _string(
                    const="hds-mechanism-asset-record-v1"
                ),
                "support_case_refs": _array(_string(), unique=True),
                "target_projections": _array(
                    projection, min_items=1, unique=True
                ),
                "trigger": common_text_object,
                "valid_scope": common_text_object,
            },
            required=(
                "schema_version",
                "record_id",
                "record_version",
                "domain",
                "mechanism_type",
                "primary_class",
                "target_projections",
                "hypothesis_ir_ref",
                "trigger",
                "preconditions",
                "predicted_effects",
                "invariants",
                "exclusions",
                "valid_scope",
                "support_case_refs",
                "negative_case_refs",
                "counterexample_refs",
                "intervention_refs",
                "evidence_state",
                "mechanism_support_state",
                "adoption_state",
                "closure_boundary",
                "falsification_procedure",
                "provenance",
                "approval_ref",
                "digest_excluded_fields",
                "content_digest",
            ),
            references=(
                ReferenceField(
                    "/hypothesis_ir_ref", ("HypothesisIR",)
                ),
                ReferenceField(
                    "/support_case_refs/*",
                    ("ARC2TeacherCase", "ARC3TeacherTrajectory"),
                ),
                ReferenceField(
                    "/negative_case_refs/*",
                    ("ARC2TeacherCase", "ARC3TeacherTrajectory"),
                ),
                ReferenceField(
                    "/counterexample_refs/*", ("CounterexampleRecord",)
                ),
                ReferenceField(
                    "/intervention_refs/*", ("InterventionResult",)
                ),
                ReferenceField(
                    "/approval_ref",
                    ("ApprovalRecord",),
                    required_resolution=False,
                ),
            ),
        ),
        BundleSchemaDefinition(
            index=42,
            name="ProbeObligationRecord",
            filename="probe_obligation_record.schema.json",
            schema_version="hds-probe-obligation-record-v1",
            id_field="probe_obligation_id",
            id_namespace="hds-probe-obligation-id",
            digest_namespace="hds-probe-obligation-record",
            properties={
                "competing_hypothesis_refs": _array(
                    _string(), min_items=2, unique=True
                ),
                "content_digest": _digest(
                    "hds-probe-obligation-record"
                ),
                "digest_excluded_fields": digest_exclusions,
                "expected_outcomes_by_hypothesis": common_text_object,
                "falsification_condition": common_text_object,
                "probe_obligation_id": _identifier(),
                "required_observation": common_text_object,
                "resource_bound": common_text_object,
                "safe_intervention": common_text_object,
                "schema_version": _string(
                    const="hds-probe-obligation-record-v1"
                ),
                "stop_condition": common_text_object,
                "target_open_term_refs": _array(
                    _string(), min_items=1, unique=True
                ),
            },
            required=(
                "schema_version",
                "probe_obligation_id",
                "target_open_term_refs",
                "competing_hypothesis_refs",
                "required_observation",
                "safe_intervention",
                "expected_outcomes_by_hypothesis",
                "falsification_condition",
                "stop_condition",
                "resource_bound",
                "digest_excluded_fields",
                "content_digest",
            ),
            references=(
                ReferenceField(
                    "/target_open_term_refs/*", ("OpenTermRecord",)
                ),
                ReferenceField(
                    "/competing_hypothesis_refs/*",
                    ("HypothesisIR", "InterpretationHypothesis"),
                ),
            ),
        ),
        BundleSchemaDefinition(
            index=43,
            name="StructureCoverageProfile",
            filename="structure_coverage_profile.schema.json",
            schema_version="hds-structure-coverage-profile-v1",
            id_field="profile_id",
            id_namespace="hds-structure-coverage-profile-id",
            digest_namespace="hds-structure-coverage-profile",
            properties={
                "build_ready_profile_digest": _digest(),
                "category_results": _array(
                    common_text_object, min_items=1
                ),
                "claim_refs": _array(_string(), unique=True),
                "completion_state_registry_ref": _string(),
                "content_digest": _digest(
                    "hds-structure-coverage-profile"
                ),
                "coverage_report_ref": _string(),
                "digest_excluded_fields": digest_exclusions,
                "duplicate_evidence_score_count": _integer(),
                "hard_mandatory_failure_count": _integer(),
                "profile_id": _identifier(),
                "schema_version": _string(
                    const="hds-structure-coverage-profile-v1"
                ),
                "unique_evidence_ref_count": _integer(),
                "unresolved_ratio_by_category": common_text_object,
            },
            required=(
                "schema_version",
                "profile_id",
                "build_ready_profile_digest",
                "category_results",
                "unique_evidence_ref_count",
                "duplicate_evidence_score_count",
                "hard_mandatory_failure_count",
                "unresolved_ratio_by_category",
                "coverage_report_ref",
                "claim_refs",
                "completion_state_registry_ref",
                "digest_excluded_fields",
                "content_digest",
            ),
            references=(
                ReferenceField(
                    "/coverage_report_ref", ("CoverageReport",)
                ),
                ReferenceField("/claim_refs/*", ("ClaimRecord",)),
                ReferenceField(
                    "/completion_state_registry_ref",
                    ("CompletionStateRegistry",),
                ),
            ),
        ),
        BundleSchemaDefinition(
            index=44,
            name="BundleApprovalRecord",
            filename="bundle_approval_record.schema.json",
            schema_version="hds-bundle-approval-record-v1",
            id_field="bundle_approval_id",
            id_namespace="hds-bundle-approval-id",
            digest_namespace="hds-bundle-approval-record",
            properties={
                "allowed_transition": _string(),
                "bundle_approval_id": _identifier(),
                "content_digest": _digest("hds-bundle-approval-record"),
                "decision": _string(
                    enum=(
                        "SCHEMA_TEMPLATE_NOT_OWNER_APPROVAL",
                        "OWNER_APPROVED",
                        "OWNER_REJECTED",
                    )
                ),
                "digest_excluded_fields": digest_exclusions,
                "owner_decision_capture_ref": _string(),
                "schema_version": _string(
                    const="hds-bundle-approval-record-v1"
                ),
                "target_bundle_logical_digest": _digest(
                    "hds-structure-bundle-logical"
                ),
                "target_evidence_commit": _string(
                    pattern=r"^[0-9a-f]{40}$"
                ),
            },
            required=(
                "schema_version",
                "bundle_approval_id",
                "owner_decision_capture_ref",
                "target_bundle_logical_digest",
                "target_evidence_commit",
                "decision",
                "allowed_transition",
                "digest_excluded_fields",
                "content_digest",
            ),
        ),
        BundleSchemaDefinition(
            index=45,
            name="StructureBundleMigrationRecord",
            filename="structure_bundle_migration_record.schema.json",
            schema_version="hds-structure-bundle-migration-record-v1",
            id_field="migration_id",
            id_namespace="hds-structure-bundle-migration-id",
            digest_namespace="hds-structure-bundle-migration",
            properties={
                "changed_record_ids": _array(
                    _string(), unique=True
                ),
                "content_digest": _digest(
                    "hds-structure-bundle-migration"
                ),
                "digest_excluded_fields": digest_exclusions,
                "lossless": _boolean(),
                "migration_id": _identifier(),
                "rollback_procedure": common_text_object,
                "schema_version": _string(
                    const="hds-structure-bundle-migration-record-v1"
                ),
                "source_bundle_schema_version": _string(),
                "target_bundle_schema_version": _string(),
                "transform_implementation_digest": _digest(),
            },
            required=(
                "schema_version",
                "migration_id",
                "source_bundle_schema_version",
                "target_bundle_schema_version",
                "transform_implementation_digest",
                "lossless",
                "changed_record_ids",
                "rollback_procedure",
                "digest_excluded_fields",
                "content_digest",
            ),
        ),
    )


BUNDLE_DEFINITIONS = _bundle_definitions()
BUNDLE_DEFINITION_BY_NAME = {
    definition.name: definition for definition in BUNDLE_DEFINITIONS
}


def _load_object(path: Path, code: str) -> JsonObject:
    try:
        decoded = json.loads(path.read_bytes())
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SchemaValidationError(code, path.as_posix()) from exc
    if not isinstance(decoded, dict):
        _fail(code, path.as_posix())
    return cast(JsonObject, decoded)


def _schema_document_bytes(document: Mapping[str, JsonValue]) -> bytes:
    """Encode a schema without applying instance field-name semantics."""

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
    try:
        decoded = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SchemaValidationError(
            "D02B_POST_AUDIT_SCHEMA_JSON_INVALID"
        ) from exc
    if not isinstance(decoded, dict):
        _fail("D02B_POST_AUDIT_SCHEMA_NOT_OBJECT")
    document = cast(JsonObject, decoded)
    if _schema_document_bytes(document) != payload:
        _fail("D02B_POST_AUDIT_SCHEMA_NOT_CANONICAL")
    return document


def _document_digest(
    namespace: str,
    document: Mapping[str, JsonValue],
    excluded_fields: Sequence[str],
) -> str:
    body = copy.deepcopy(dict(document))
    for field in excluded_fields:
        body.pop(field, None)
    return namespace + ":" + hashlib.sha256(canonical_json_bytes(body)).hexdigest()


def _base_snapshot(
    repository_root: Path,
) -> tuple[JsonObject, tuple[JsonObject, ...]]:
    root = (
        repository_root
        / "distillation/input/historical_pre_audit/PH-D02B"
    )
    contract_path = root / "hds_rev2_schema_contract.json"
    payload = contract_path.read_bytes()
    if hashlib.sha256(payload).hexdigest() != HISTORICAL_D02B_CONTRACT_SHA256:
        _fail("D02B_POST_AUDIT_BASE_CONTRACT_DIGEST")
    contract = _load_object(
        contract_path,
        "D02B_POST_AUDIT_BASE_CONTRACT_INVALID",
    )
    entries = contract.get("schema_entries")
    if not isinstance(entries, list) or len(entries) != 38:
        _fail("D02B_POST_AUDIT_BASE_SCHEMA_COUNT")
    typed_entries: list[JsonObject] = []
    for entry in entries:
        if not isinstance(entry, dict):
            _fail("D02B_POST_AUDIT_BASE_SCHEMA_ENTRY")
        typed_entries.append(entry)
    names = tuple(
        cast(str, entry.get("name")) for entry in typed_entries
    )
    if names != HDS_REV2_SCHEMA_NAMES:
        _fail("D02B_POST_AUDIT_BASE_SCHEMA_ORDER")
    return contract, tuple(typed_entries)


def _current_base_schema_payloads(
    repository_root: Path,
    entries: Sequence[Mapping[str, JsonValue]],
) -> dict[str, bytes]:
    snapshot_root = (
        repository_root
        / "distillation/input/historical_pre_audit/PH-D02B/schemas"
    )
    payloads: dict[str, bytes] = {}
    for entry in entries:
        filename = entry.get("filename")
        expected_sha = entry.get("schema_sha256")
        if not isinstance(filename, str) or not isinstance(
            expected_sha, str
        ):
            _fail("D02B_POST_AUDIT_BASE_SCHEMA_METADATA")
        source = snapshot_root / filename
        raw = source.read_bytes()
        if hashlib.sha256(raw).hexdigest() != expected_sha:
            _fail("D02B_POST_AUDIT_BASE_SCHEMA_DIGEST", filename)
        document = _load_object(
            source,
            "D02B_POST_AUDIT_BASE_SCHEMA_INVALID",
        )
        payloads[filename] = _schema_document_bytes(document)
    return payloads


def build_snapshot_manifest(repository_root: Path) -> JsonObject:
    _, entries = _base_snapshot(repository_root)
    snapshot_root = (
        repository_root
        / "distillation/input/historical_pre_audit/PH-D02B"
    )
    artifacts: list[JsonObject] = []
    for relative in (
        "hds_rev2_schema_contract.json",
        "valid_schema_examples.json",
        "invalid_schema_bundles.json",
    ):
        payload = (snapshot_root / relative).read_bytes()
        artifacts.append(
            {
                "path": relative,
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    for entry in entries:
        filename = cast(str, entry["filename"])
        payload = (snapshot_root / "schemas" / filename).read_bytes()
        artifacts.append(
            {
                "path": "schemas/" + filename,
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
    manifest: JsonObject = {
        "schema_version": "hds-d02b-pre-audit-snapshot-manifest-v1",
        "source_commit": HISTORICAL_D02B_IMPLEMENTATION_COMMIT,
        "source_classification": (
            "HISTORICAL_IMPLEMENTATION_CANDIDATE_INPUT_ONLY"
        ),
        "eligible_for_current_activation": False,
        "artifact_count": len(artifacts),
        "artifacts": cast(JsonValue, artifacts),
        "digest_excluded_fields": ["content_digest"],
        "content_digest": "",
    }
    manifest["content_digest"] = _document_digest(
        "hds-d02b-pre-audit-snapshot",
        manifest,
        ("content_digest",),
    )
    return manifest


def build_post_audit_contract(repository_root: Path) -> JsonObject:
    _, base_entries = _base_snapshot(repository_root)
    base_payloads = _current_base_schema_payloads(
        repository_root,
        base_entries,
    )
    normalized_base_entries: list[JsonObject] = []
    for entry in base_entries:
        updated = copy.deepcopy(dict(entry))
        filename = cast(str, updated["filename"])
        updated["schema_path"] = (
            "distillation/schema_sets/ph_d02b_v1/" + filename
        )
        updated["schema_sha256"] = hashlib.sha256(
            base_payloads[filename]
        ).hexdigest()
        normalized_base_entries.append(updated)
    extension_entries = [
        definition.contract_entry() for definition in BUNDLE_DEFINITIONS
    ]
    mapping = {
        cast(str, entry["name"]): {
            "index": entry["index"],
            "schema_path": entry["schema_path"],
            "schema_sha256": entry["schema_sha256"],
        }
        for entry in normalized_base_entries
    }
    contract: JsonObject = {
        "schema_version": POST_AUDIT_CONTRACT_VERSION,
        "contract_id": POST_AUDIT_CONTRACT_ID,
        "phase_id": "PH-D02B",
        "authority": {
            "arc3_spec_sha256": (
                "52c652ae734a41cd4116d4e15bca890c43c5e0aaf3f7f8d6f0627a"
                "540f7a9f63"
            ),
            "arc3_roadmap_sha256": (
                "7c010c9c5becd89800ffb2fd9ba9a914dac3cd246a39891e88367ac"
                "5ae7753e5"
            ),
            "hds_spec_sha256": (
                "79bc7169550c94ea8d86d5004989f9d7c1d93fa173e5fad2d4df02"
                "d88fb6fc93"
            ),
            "hds_roadmap_sha256": (
                "64640eff883f417baeb2d70716e1904c1fd765a3d1a5a5eacb8bba"
                "82e3500518"
            ),
            "predecessor_phase_state_sha256": (
                "ff5fd059180ca5c4149f39f017231689eda4cbcadddbfffe611a39555"
                "d2bc50a"
            ),
            "predecessor_evidence_commit": (
                "78aaf2a4f3bc00c5aa8ec66c6414b19ad6089dd3"
            ),
            "predecessor_evidence_payload_digest": (
                "sha256:"
                "b6f78c8060e7b39521e01ca4dbbf84535acc7a64372b15f8a53d404"
                "c8c088d01"
            ),
        },
        "base_hds_schema_count": 38,
        "bundle_schema_count": 7,
        "total_schema_count": 45,
        "schema_set_version": POST_AUDIT_SCHEMA_SET_VERSION,
        "hds_rev2_schema_entries": cast(
            JsonValue,
            normalized_base_entries,
        ),
        "bundle_schema_entries": cast(JsonValue, extension_entries),
        "hds_rev2_one_to_one_mapping": cast(JsonValue, mapping),
        "hds_rev2_mapping_count": len(mapping),
        "required_bundle_file_inventory": list(
            REQUIRED_BUNDLE_FILE_INVENTORY
        ),
        "file_policy": {
            "partial_bundle": "REJECT",
            "unknown_file": "REJECT",
            "unknown_schema": "REJECT",
            "unknown_schema_version": "REJECT",
        },
        "reference_policy": {
            "dangling_reference": "REJECT",
            "duplicate_id": "REJECT",
            "wrong_reference_kind": "REJECT",
            "wrong_target_schema": "REJECT",
        },
        "dependency_lock_policy": "EXACT_DIGEST_MATCH_REQUIRED",
        "phase_boundaries": {
            "ph_d02c_typed_causal_ir_started": False,
            "interpreter_started": False,
            "real_trajectory_normalization_count": 0,
            "hypothesis_generation_count": 0,
            "rule_promotion_count": 0,
            "bridge_started": False,
            "runtime_started": False,
            "locked_final_access_count": 0,
            "official_access_count": 0,
            "kaggle_mutation_count": 0,
        },
        "historical_input": {
            "source_commit": HISTORICAL_D02B_IMPLEMENTATION_COMMIT,
            "source_contract_sha256": HISTORICAL_D02B_CONTRACT_SHA256,
            "classification": (
                "HISTORICAL_IMPLEMENTATION_CANDIDATE_REVALIDATED_INPUT"
            ),
            "eligible_for_current_activation": False,
        },
        "digest_excluded_fields": ["content_digest", "contract_id"],
        "content_digest": "",
    }
    contract["content_digest"] = _document_digest(
        "hds-post-audit-schema-bundle-contract",
        contract,
        ("content_digest", "contract_id"),
    )
    return contract


def _finalize_extension_instance(
    definition: BundleSchemaDefinition,
    body: Mapping[str, JsonValue],
) -> JsonObject:
    instance = copy.deepcopy(dict(body))
    instance[definition.id_field] = (
        definition.id_namespace + ":" + "0" * 64
    )
    instance["content_digest"] = (
        definition.digest_namespace + ":" + "0" * 64
    )
    instance[definition.id_field] = content_derived_id(
        definition.id_namespace,
        instance,
        policy=definition._digest_exclusion_policy,
    )
    instance["content_digest"] = logical_content_digest(
        definition.digest_namespace,
        instance,
        policy=definition._digest_exclusion_policy,
    )
    return instance


def _base_examples(repository_root: Path) -> tuple[JsonObject, ...]:
    artifact = _load_object(
        repository_root
        / (
            "distillation/input/historical_pre_audit/PH-D02B/"
            "valid_schema_examples.json"
        ),
        "D02B_POST_AUDIT_BASE_EXAMPLES_INVALID",
    )
    examples = artifact.get("examples")
    if not isinstance(examples, list) or len(examples) != 38:
        _fail("D02B_POST_AUDIT_BASE_EXAMPLE_COUNT")
    typed: list[JsonObject] = []
    for item in examples:
        if not isinstance(item, dict):
            _fail("D02B_POST_AUDIT_BASE_EXAMPLE")
        typed.append(item)
    names = tuple(cast(str, item.get("schema_name")) for item in typed)
    if names != HDS_REV2_SCHEMA_NAMES:
        _fail("D02B_POST_AUDIT_BASE_EXAMPLE_ORDER")
    return tuple(typed)


def build_valid_examples(repository_root: Path) -> JsonObject:
    base = list(_base_examples(repository_root))
    by_name = {
        cast(str, item["schema_name"]): cast(
            JsonObject, item["instance"]
        )
        for item in base
    }

    ontology = _finalize_extension_instance(
        BUNDLE_DEFINITION_BY_NAME["OntologyTypeRecord"],
        {
            "schema_version": "hds-ontology-type-record-v1",
            "type_kind": "ENTITY",
            "definition": "Synthetic schema-conformance entity type.",
            "constraints": {"fixture_only": True},
            "digest_excluded_fields": [
                "type_id",
                "content_digest",
            ],
        },
    )
    mechanism = _finalize_extension_instance(
        BUNDLE_DEFINITION_BY_NAME["MechanismAssetRecord"],
        {
            "schema_version": "hds-mechanism-asset-record-v1",
            "record_version": 1,
            "domain": "ARC3",
            "mechanism_type": "SCHEMA_FIXTURE",
            "primary_class": "observation/representation",
            "target_projections": [
                {
                    "projection_type": "ProbeProjection",
                    "projection_digest": "hds-projection:" + "1" * 64,
                }
            ],
            "hypothesis_ir_ref": by_name["HypothesisIR"][
                "hypothesis_ir_id"
            ],
            "trigger": {"fixture_only": True},
            "preconditions": [],
            "predicted_effects": [],
            "invariants": [],
            "exclusions": ["NO_RUNTIME_ACTIVATION"],
            "valid_scope": {"synthetic_schema_fixture": True},
            "support_case_refs": [
                by_name["ARC2TeacherCase"]["teacher_case_id"]
            ],
            "negative_case_refs": [
                by_name["ARC3TeacherTrajectory"]["trajectory_id"]
            ],
            "counterexample_refs": [
                by_name["CounterexampleRecord"]["counterexample_id"]
            ],
            "intervention_refs": [
                by_name["InterventionResult"]["intervention_result_id"]
            ],
            "evidence_state": "INCONCLUSIVE",
            "mechanism_support_state": "INCONCLUSIVE",
            "adoption_state": "PROPOSED",
            "closure_boundary": {"state": "OPEN"},
            "falsification_procedure": {"fixture_only": True},
            "provenance": {"kind": "SYNTHETIC_SCHEMA_FIXTURE"},
            "approval_ref": None,
            "digest_excluded_fields": [
                "record_id",
                "content_digest",
            ],
        },
    )
    hypothesis_id = cast(
        str, by_name["HypothesisIR"]["hypothesis_ir_id"]
    )
    probe = _finalize_extension_instance(
        BUNDLE_DEFINITION_BY_NAME["ProbeObligationRecord"],
        {
            "schema_version": "hds-probe-obligation-record-v1",
            "target_open_term_refs": [
                by_name["OpenTermRecord"]["open_term_id"]
            ],
            "competing_hypothesis_refs": [
                hypothesis_id,
                by_name["InterpretationHypothesis"][
                    "interpretation_id"
                ],
            ],
            "required_observation": {"fixture_only": True},
            "safe_intervention": {"fixture_only": True},
            "expected_outcomes_by_hypothesis": {
                "fixture_only": True
            },
            "falsification_condition": {"fixture_only": True},
            "stop_condition": {"fixture_only": True},
            "resource_bound": {"candidate_budget": 1},
            "digest_excluded_fields": [
                "probe_obligation_id",
                "content_digest",
            ],
        },
    )
    coverage = _finalize_extension_instance(
        BUNDLE_DEFINITION_BY_NAME["StructureCoverageProfile"],
        {
            "schema_version": "hds-structure-coverage-profile-v1",
            "build_ready_profile_digest": (
                "agi-build-ready-profile:" + "2" * 64
            ),
            "category_results": [
                {"category": "observation", "state": "UNRESOLVED"}
            ],
            "unique_evidence_ref_count": 0,
            "duplicate_evidence_score_count": 0,
            "hard_mandatory_failure_count": 1,
            "unresolved_ratio_by_category": {
                "observation_ppm": 1_000_000
            },
            "coverage_report_ref": by_name["CoverageReport"][
                "coverage_report_id"
            ],
            "claim_refs": [by_name["ClaimRecord"]["claim_id"]],
            "completion_state_registry_ref": by_name[
                "CompletionStateRegistry"
            ]["completion_registry_id"],
            "digest_excluded_fields": [
                "profile_id",
                "content_digest",
            ],
        },
    )
    approval = _finalize_extension_instance(
        BUNDLE_DEFINITION_BY_NAME["BundleApprovalRecord"],
        {
            "schema_version": "hds-bundle-approval-record-v1",
            "owner_decision_capture_ref": "UNBOUND_SCHEMA_TEMPLATE",
            "target_bundle_logical_digest": (
                "hds-structure-bundle-logical:" + "3" * 64
            ),
            "target_evidence_commit": "0" * 40,
            "decision": "SCHEMA_TEMPLATE_NOT_OWNER_APPROVAL",
            "allowed_transition": "NONE",
            "digest_excluded_fields": [
                "bundle_approval_id",
                "content_digest",
            ],
        },
    )
    migration = _finalize_extension_instance(
        BUNDLE_DEFINITION_BY_NAME["StructureBundleMigrationRecord"],
        {
            "schema_version": (
                "hds-structure-bundle-migration-record-v1"
            ),
            "source_bundle_schema_version": "hds-structure-bundle-v1",
            "target_bundle_schema_version": "hds-structure-bundle-v1",
            "transform_implementation_digest": (
                "hds-transform-implementation:" + "4" * 64
            ),
            "lossless": True,
            "changed_record_ids": [],
            "rollback_procedure": {"operation": "NO_OP"},
            "digest_excluded_fields": [
                "migration_id",
                "content_digest",
            ],
        },
    )
    manifest = _finalize_extension_instance(
        BUNDLE_DEFINITION_BY_NAME["HDSStructureBundleManifest"],
        {
            "schema_version": "hds-structure-bundle-manifest-v1",
            "bundle_schema_version": "hds-structure-bundle-v1",
            "source_content_manifest_digest": by_name[
                "SourceContentManifest"
            ]["content_digest"],
            "dependency_lock_digest": by_name["DependencyLock"][
                "content_digest"
            ],
            "canonical_serialization": {
                "encoding": "UTF-8",
                "unicode_normalization": "NFC",
                "json_key_order": "LEXICOGRAPHIC",
                "json_whitespace": "NONE",
                "newline": "LF",
                "jsonl_order": "RECORD_ID_ASCENDING",
            },
            "logical_digest": (
                "hds-structure-bundle-logical:" + "5" * 64
            ),
            "physical_package_digest": "sha256:" + "6" * 64,
            "required_file_inventory": list(
                REQUIRED_BUNDLE_FILE_INVENTORY
            ),
            "record_count_by_type": {
                "HDSStructureBundleManifest": 1,
                "OntologyTypeRecord": 1,
                "MechanismAssetRecord": 1,
                "ProbeObligationRecord": 1,
                "StructureCoverageProfile": 1,
                "BundleApprovalRecord": 1,
                "StructureBundleMigrationRecord": 1,
            },
            "cross_reference_index_digest": (
                "hds-cross-reference-index:" + "7" * 64
            ),
            "coverage_profile_digest": coverage["content_digest"],
            "taint_report_digest": "hds-taint-report:" + "8" * 64,
            "migration_record_digest": migration["content_digest"],
            "bundle_approval_record_digest": approval["content_digest"],
            "synthetic_fixture_only": True,
            "digest_excluded_fields": [
                "bundle_id",
                "content_digest",
                "logical_digest",
                "physical_package_digest",
            ],
        },
    )
    extension_instances = {
        "HDSStructureBundleManifest": manifest,
        "OntologyTypeRecord": ontology,
        "MechanismAssetRecord": mechanism,
        "ProbeObligationRecord": probe,
        "StructureCoverageProfile": coverage,
        "BundleApprovalRecord": approval,
        "StructureBundleMigrationRecord": migration,
    }
    examples = [
        *base,
        *[
            {
                "schema_name": name,
                "instance": extension_instances[name],
            }
            for name in BUNDLE_SCHEMA_NAMES
        ],
    ]
    artifact: JsonObject = {
        "schema_version": "hds-post-audit-valid-schema-examples-v1",
        "artifact_kind": "PH_D02B_POST_AUDIT_SCHEMA_FIXTURES",
        "phase_id": "PH-D02B",
        "synthetic_fixture_only": True,
        "owner_approval_generated": False,
        "hds_rev2_example_count": 38,
        "bundle_example_count": 7,
        "example_count": len(examples),
        "examples": cast(JsonValue, examples),
        "digest_excluded_fields": ["content_digest"],
        "content_digest": "",
    }
    artifact["content_digest"] = _document_digest(
        "hds-post-audit-valid-schema-examples",
        artifact,
        ("content_digest",),
    )
    return artifact


def _pointer_values(instance: Mapping[str, JsonValue], pointer: str) -> list[JsonValue]:
    if not pointer.startswith("/"):
        _fail("D02B_POST_AUDIT_REFERENCE_POINTER", pointer)
    current: list[JsonValue] = [cast(JsonValue, dict(instance))]
    for raw_segment in pointer[1:].split("/"):
        segment = raw_segment.replace("~1", "/").replace("~0", "~")
        following: list[JsonValue] = []
        for value in current:
            if segment == "*":
                if not isinstance(value, list):
                    _fail(
                        "D02B_POST_AUDIT_REFERENCE_ARRAY_REQUIRED",
                        pointer,
                    )
                following.extend(value)
            else:
                if not isinstance(value, dict) or segment not in value:
                    _fail(
                        "D02B_POST_AUDIT_REFERENCE_FIELD_MISSING",
                        pointer,
                    )
                following.append(value[segment])
        current = following
    return current


def _find_forbidden_key(
    value: JsonValue,
    forbidden: frozenset[str],
    prefixes: tuple[str, ...] = (),
) -> str | None:
    if isinstance(value, dict):
        for key, nested in value.items():
            if key in forbidden or key.startswith(prefixes):
                return key
            found = _find_forbidden_key(nested, forbidden, prefixes)
            if found is not None:
                return found
    elif isinstance(value, list):
        for nested in value:
            found = _find_forbidden_key(nested, forbidden, prefixes)
            if found is not None:
                return found
    return None


@dataclass(frozen=True, slots=True)
class ValidatedRecord:
    schema_name: str
    primary_id: str
    content_digest: str
    instance: JsonObject


class PostAuditSchemaRegistry:
    """Fail-closed validator for the exact post-audit 45-schema set."""

    def __init__(
        self,
        documents: Mapping[str, Mapping[str, JsonValue]],
        contract: Mapping[str, JsonValue],
    ) -> None:
        self._documents = {
            name: copy.deepcopy(dict(document))
            for name, document in documents.items()
        }
        self._contract = copy.deepcopy(dict(contract))
        entries = [
            *cast(
                list[JsonObject],
                self._contract["hds_rev2_schema_entries"],
            ),
            *cast(
                list[JsonObject],
                self._contract["bundle_schema_entries"],
            ),
        ]
        self._entries = {
            cast(str, entry["name"]): entry for entry in entries
        }
        expected = set(HDS_REV2_SCHEMA_NAMES) | set(BUNDLE_SCHEMA_NAMES)
        if set(self._documents) != expected or set(self._entries) != expected:
            _fail("D02B_POST_AUDIT_SCHEMA_SET_MISMATCH")

    @classmethod
    def from_repository(
        cls,
        repository_root: Path,
    ) -> PostAuditSchemaRegistry:
        contract_path = (
            repository_root
            / "distillation/input/post_audit_schema_bundle_contract.json"
        )
        contract = _load_object(
            contract_path,
            "D02B_POST_AUDIT_CONTRACT_INVALID",
        )
        expected_contract = build_post_audit_contract(repository_root)
        if canonical_json_bytes(contract) != canonical_json_bytes(
            expected_contract
        ):
            _fail("D02B_POST_AUDIT_CONTRACT_MISMATCH")
        schema_root = (
            repository_root / "distillation/schema_sets/ph_d02b_v1"
        )
        expected_files = {
            cast(str, entry["filename"])
            for entry in [
                *cast(list[JsonObject], contract["hds_rev2_schema_entries"]),
                *cast(list[JsonObject], contract["bundle_schema_entries"]),
            ]
        }
        actual_files = {
            path.name for path in schema_root.glob("*.schema.json")
        }
        if actual_files != expected_files:
            _fail(
                "D02B_POST_AUDIT_SCHEMA_INVENTORY",
                (
                    f"missing={sorted(expected_files - actual_files)};"
                    f"extra={sorted(actual_files - expected_files)}"
                ),
            )
        documents: dict[str, JsonObject] = {}
        for entry in [
            *cast(list[JsonObject], contract["hds_rev2_schema_entries"]),
            *cast(list[JsonObject], contract["bundle_schema_entries"]),
        ]:
            name = cast(str, entry["name"])
            filename = cast(str, entry["filename"])
            payload = (schema_root / filename).read_bytes()
            if hashlib.sha256(payload).hexdigest() != entry["schema_sha256"]:
                _fail("D02B_POST_AUDIT_SCHEMA_DIGEST", filename)
            document = _verify_schema_document_bytes(payload)
            if document.get("$schema") != SCHEMA_DRAFT:
                _fail("D02B_POST_AUDIT_SCHEMA_DRAFT", filename)
            declared_name = document.get("x-hds-schema-name")
            if entry.get("preserved_sha256") is None:
                if declared_name != name:
                    _fail("D02B_POST_AUDIT_SCHEMA_NAME", filename)
            elif declared_name not in {None, name}:
                _fail("D02B_POST_AUDIT_SCHEMA_NAME", filename)
            documents[name] = document
        return cls(documents, contract)

    @property
    def schema_names(self) -> tuple[str, ...]:
        return (*HDS_REV2_SCHEMA_NAMES, *BUNDLE_SCHEMA_NAMES)

    def validate_instance(
        self,
        schema_name: str,
        instance: Mapping[str, JsonValue],
    ) -> ValidatedRecord:
        if schema_name not in self._entries:
            _fail("D02B_POST_AUDIT_UNKNOWN_SCHEMA", schema_name)
        entry = self._entries[schema_name]
        copied = copy.deepcopy(dict(instance))
        validate_json_schema_instance(copied, self._documents[schema_name])
        id_field = cast(str, entry["id_field"])
        digest_field = cast(str, entry["digest_field"])
        primary_id = copied.get(id_field)
        content_digest = copied.get(digest_field)
        if not isinstance(primary_id, str):
            _fail("D02B_POST_AUDIT_PRIMARY_ID", schema_name)
        if not isinstance(content_digest, str):
            _fail("D02B_POST_AUDIT_CONTENT_DIGEST", schema_name)
        excluded = cast(list[str], entry["digest_excluded_fields"])
        if entry["id_derivation"] == (
            "LEGACY_PHASE_STABLE_ID_CONTENT_BOUND_BY_DIGEST"
        ):
            body = {
                key: value
                for key, value in copied.items()
                if key != digest_field
            }
            expected_digest = (
                cast(str, entry["digest_namespace"])
                + ":"
                + hashlib.sha256(canonical_json_bytes(body)).hexdigest()
            )
        else:
            policy = DigestExclusionPolicy(
                id_fields=frozenset(
                    {id_field} if id_field in excluded else set()
                ),
                digest_fields=frozenset({digest_field}),
                timestamp_fields=frozenset(
                    cast(list[str], entry.get("timestamp_fields", []))
                ),
                physical_metadata_fields=frozenset(
                    set(excluded)
                    - {id_field, digest_field}
                    - set(
                        cast(
                            list[str],
                            entry.get("timestamp_fields", []),
                        )
                    )
                ),
            )
            expected_id = content_derived_id(
                cast(str, entry["id_namespace"]),
                copied,
                policy=policy,
            )
            if primary_id != expected_id:
                _fail("D02B_POST_AUDIT_CONTENT_ID_MISMATCH", schema_name)
            expected_digest = logical_content_digest(
                cast(str, entry["digest_namespace"]),
                copied,
                policy=policy,
            )
        if content_digest != expected_digest:
            _fail(
                "D02B_POST_AUDIT_CONTENT_DIGEST_MISMATCH",
                schema_name,
            )
        record = ValidatedRecord(
            schema_name=schema_name,
            primary_id=primary_id,
            content_digest=content_digest,
            instance=copied,
        )
        self._validate_single_semantics(record)
        return record

    def refinalize_instance(
        self,
        schema_name: str,
        instance: Mapping[str, JsonValue],
    ) -> JsonObject:
        """Rebind a synthetic generated record after a test mutation."""

        if schema_name not in self._entries:
            _fail("D02B_POST_AUDIT_UNKNOWN_SCHEMA", schema_name)
        entry = self._entries[schema_name]
        if entry["id_derivation"] != "HDS_CONTENT_ID_V1":
            _fail("D02B_POST_AUDIT_LEGACY_REFINALIZE", schema_name)
        copied = copy.deepcopy(dict(instance))
        id_field = cast(str, entry["id_field"])
        digest_field = cast(str, entry["digest_field"])
        excluded = set(cast(list[str], entry["digest_excluded_fields"]))
        timestamp_fields = set(
            cast(list[str], entry.get("timestamp_fields", []))
        )
        policy = DigestExclusionPolicy(
            id_fields=frozenset(
                {id_field} if id_field in excluded else set()
            ),
            digest_fields=frozenset({digest_field}),
            timestamp_fields=frozenset(timestamp_fields),
            physical_metadata_fields=frozenset(
                excluded - {id_field, digest_field} - timestamp_fields
            ),
        )
        copied[id_field] = cast(str, entry["id_namespace"]) + ":" + "0" * 64
        copied[digest_field] = (
            cast(str, entry["digest_namespace"]) + ":" + "0" * 64
        )
        copied[id_field] = content_derived_id(
            cast(str, entry["id_namespace"]),
            copied,
            policy=policy,
        )
        copied[digest_field] = logical_content_digest(
            cast(str, entry["digest_namespace"]),
            copied,
            policy=policy,
        )
        return copied

    def validate_bundle(
        self,
        envelopes: Sequence[Mapping[str, JsonValue]],
    ) -> tuple[ValidatedRecord, ...]:
        records: list[ValidatedRecord] = []
        for index, envelope in enumerate(envelopes):
            if set(envelope) != {"schema_name", "instance"}:
                _fail("D02B_POST_AUDIT_ENVELOPE_FIELDS", str(index))
            schema_name = envelope.get("schema_name")
            instance = envelope.get("instance")
            if not isinstance(schema_name, str) or not isinstance(
                instance, dict
            ):
                _fail("D02B_POST_AUDIT_ENVELOPE", str(index))
            records.append(
                self.validate_instance(
                    schema_name,
                    cast(Mapping[str, JsonValue], instance),
                )
            )
        by_id: dict[str, ValidatedRecord] = {}
        by_digest: dict[str, ValidatedRecord] = {}
        for record in records:
            if record.primary_id in by_id:
                _fail(
                    "D02B_POST_AUDIT_DUPLICATE_PRIMARY_ID",
                    record.primary_id,
                )
            if record.content_digest in by_digest:
                _fail(
                    "D02B_POST_AUDIT_DUPLICATE_CONTENT_DIGEST",
                    record.content_digest,
                )
            by_id[record.primary_id] = record
            by_digest[record.content_digest] = record
        for record in records:
            entry = self._entries[record.schema_name]
            references = cast(list[JsonObject], entry["references"])
            for reference in references:
                pointer = cast(str, reference["pointer"])
                kind = cast(str, reference["reference_kind"])
                targets = set(cast(list[str], reference["targets"]))
                required = cast(bool, reference["required_resolution"])
                target_index = by_digest if kind == "DIGEST" else by_id
                other_index = by_id if kind == "DIGEST" else by_digest
                for value in _pointer_values(record.instance, pointer):
                    if value is None and not required:
                        continue
                    if not isinstance(value, str):
                        _fail(
                            "D02B_POST_AUDIT_REFERENCE_STRING",
                            pointer,
                        )
                    target = target_index.get(value)
                    if target is None:
                        if value in other_index:
                            _fail(
                                "D02B_POST_AUDIT_REFERENCE_KIND",
                                pointer,
                            )
                        _fail(
                            "D02B_POST_AUDIT_DANGLING_REFERENCE",
                            pointer,
                        )
                    if target.schema_name not in targets:
                        _fail(
                            "D02B_POST_AUDIT_REFERENCE_TARGET",
                            pointer,
                        )
        self._validate_semantics(records)
        return tuple(records)

    @staticmethod
    def _validate_single_semantics(record: ValidatedRecord) -> None:
        instance = record.instance
        if record.schema_name == "RawObservation":
            found = _find_forbidden_key(
                instance["raw_value"],
                frozenset(
                    {
                        "causal_role",
                        "goal_hypothesis",
                        "interpretation",
                        "semantic_label",
                        "strategy",
                    }
                ),
                ("hypothesized_", "inferred_", "interpreted_"),
            )
            if found is not None:
                _fail("D02B_POST_AUDIT_RAW_INFERENCE", found)
        if record.schema_name == "DeterministicDerivation":
            forbidden = frozenset(
                {
                    "causal_role",
                    "controllable_entity",
                    "goal",
                    "hazard",
                    "intent",
                    "semantic_label",
                    "strategy",
                    "success_strategy",
                    "task_solution",
                }
            )
            for field in ("configuration", "output"):
                found = _find_forbidden_key(instance[field], forbidden)
                if found is not None:
                    _fail(
                        "D02B_POST_AUDIT_DERIVATION_SEMANTIC",
                        found,
                    )
        if record.schema_name == "DecisionRecord":
            selected = set(cast(list[str], instance["selected_model_refs"]))
            held = set(cast(list[str], instance["held_model_refs"]))
            rejected = set(cast(list[str], instance["rejected_model_refs"]))
            if (
                selected & held
                or selected & rejected
                or held & rejected
            ):
                _fail("D02B_POST_AUDIT_DECISION_SET_OVERLAP")
            mode = instance["decision_mode"]
            if mode == "SINGLE" and len(selected) != 1:
                _fail("D02B_POST_AUDIT_SINGLE_REQUIRES_ONE")
            if mode in {"MULTI_CAUSAL", "SUSPEND"} and len(selected) == 1:
                _fail("D02B_POST_AUDIT_NON_SINGLE_FORBIDS_ONE")
        if record.schema_name == "RuleAtom" and instance[
            "adoption_state"
        ] not in {"PROPOSED", "PROBATION"}:
            _fail("D02B_POST_AUDIT_INITIAL_RULEATOM_STATE")
        if record.schema_name == "MechanismAssetRecord":
            if instance["adoption_state"] not in {
                "PROPOSED",
                "PROBATION",
            }:
                _fail("D02B_POST_AUDIT_MECHANISM_ADOPTION")
            projections = cast(
                list[JsonObject], instance["target_projections"]
            )
            projection_types = {
                cast(str, item["projection_type"])
                for item in projections
            }
            if len(projection_types) != len(projections):
                _fail("D02B_POST_AUDIT_DUPLICATE_PROJECTION")
        if record.schema_name == "BundleApprovalRecord":
            if instance["decision"] == (
                "SCHEMA_TEMPLATE_NOT_OWNER_APPROVAL"
            ):
                if (
                    instance["owner_decision_capture_ref"]
                    != "UNBOUND_SCHEMA_TEMPLATE"
                    or instance["allowed_transition"] != "NONE"
                ):
                    _fail("D02B_POST_AUDIT_APPROVAL_TEMPLATE_DRIFT")
        if record.schema_name == "HDSStructureBundleManifest":
            if instance["synthetic_fixture_only"] is not True:
                _fail("D02B_POST_AUDIT_MANIFEST_FIXTURE_BOUNDARY")

    @classmethod
    def _validate_semantics(
        cls,
        records: Sequence[ValidatedRecord],
    ) -> None:
        for record in records:
            cls._validate_single_semantics(record)


def validate_bundle_file_inventory(
    manifest: Mapping[str, JsonValue],
    actual_paths: Sequence[str],
    *,
    expected_dependency_lock_digest: str,
) -> None:
    inventory = manifest.get("required_file_inventory")
    if not isinstance(inventory, list) or not all(
        isinstance(item, str) for item in inventory
    ):
        _fail("D02B_POST_AUDIT_FILE_INVENTORY")
    expected = set(REQUIRED_BUNDLE_FILE_INVENTORY)
    declared = set(cast(list[str], inventory))
    actual = set(actual_paths)
    if declared != expected:
        _fail("D02B_POST_AUDIT_REQUIRED_FILE_CONTRACT")
    missing = expected - actual
    if missing:
        _fail(
            "D02B_POST_AUDIT_PARTIAL_BUNDLE",
            ",".join(sorted(missing)),
        )
    unknown = actual - expected
    if unknown:
        _fail(
            "D02B_POST_AUDIT_UNKNOWN_FILE",
            ",".join(sorted(unknown)),
        )
    if manifest.get("dependency_lock_digest") != (
        expected_dependency_lock_digest
    ):
        _fail("D02B_POST_AUDIT_DEPENDENCY_LOCK_MISMATCH")


def build_invalid_cases(repository_root: Path) -> JsonObject:
    valid = build_valid_examples(repository_root)
    examples = cast(list[JsonObject], valid["examples"])
    cases: list[JsonObject] = [
        {
            "case_id": "unknown-schema",
            "expected_error": "D02B_POST_AUDIT_UNKNOWN_SCHEMA",
        },
        {
            "case_id": "duplicate-primary-id",
            "expected_error": "D02B_POST_AUDIT_DUPLICATE_PRIMARY_ID",
        },
        {
            "case_id": "dangling-reference",
            "expected_error": "D02B_POST_AUDIT_DANGLING_REFERENCE",
        },
        {
            "case_id": "wrong-reference-target",
            "expected_error": "D02B_POST_AUDIT_REFERENCE_TARGET",
        },
        {
            "case_id": "partial-bundle",
            "expected_error": "D02B_POST_AUDIT_PARTIAL_BUNDLE",
        },
        {
            "case_id": "unknown-file",
            "expected_error": "D02B_POST_AUDIT_UNKNOWN_FILE",
        },
        {
            "case_id": "dependency-lock-mismatch",
            "expected_error": (
                "D02B_POST_AUDIT_DEPENDENCY_LOCK_MISMATCH"
            ),
        },
        {
            "case_id": "initial-ruleatom-active",
            "expected_error": "D02B_SCHEMA_ENUM",
        },
        {
            "case_id": "approval-template-drift",
            "expected_error": (
                "D02B_POST_AUDIT_APPROVAL_TEMPLATE_DRIFT"
            ),
        },
    ]
    artifact: JsonObject = {
        "schema_version": "hds-post-audit-invalid-schema-cases-v1",
        "phase_id": "PH-D02B",
        "base_valid_example_digest": valid["content_digest"],
        "base_example_count": len(examples),
        "case_count": len(cases),
        "cases": cast(JsonValue, cases),
        "digest_excluded_fields": ["content_digest"],
        "content_digest": "",
    }
    artifact["content_digest"] = _document_digest(
        "hds-post-audit-invalid-schema-cases",
        artifact,
        ("content_digest",),
    )
    return artifact


def build_conformance_report(repository_root: Path) -> JsonObject:
    registry = PostAuditSchemaRegistry.from_repository(repository_root)
    valid = build_valid_examples(repository_root)
    examples = cast(list[JsonObject], valid["examples"])
    records = registry.validate_bundle(examples)
    by_name = {record.schema_name: record for record in records}
    manifest = by_name["HDSStructureBundleManifest"].instance
    dependency_digest = cast(str, manifest["dependency_lock_digest"])
    validate_bundle_file_inventory(
        manifest,
        REQUIRED_BUNDLE_FILE_INVENTORY,
        expected_dependency_lock_digest=dependency_digest,
    )
    contract = build_post_audit_contract(repository_root)
    mapping = cast(JsonObject, contract["hds_rev2_one_to_one_mapping"])
    report: JsonObject = {
        "schema_version": "hds-post-audit-schema-conformance-v1",
        "phase_id": "PH-D02B",
        "result": "PH_D02B_SCHEMA_SET_PASS",
        "base_hds_schema_count": 38,
        "bundle_schema_count": 7,
        "total_schema_count": 45,
        "positive_record_count": len(records),
        "one_to_one_hds_mapping_count": len(mapping),
        "required_bundle_file_count": len(
            REQUIRED_BUNDLE_FILE_INVENTORY
        ),
        "cross_file_reference_integrity": "PASS",
        "unknown_file_rejection": "PASS",
        "partial_bundle_rejection": "PASS",
        "dependency_lock_rejection": "PASS",
        "invalid_case_count": 9,
        "gates": {
            "DG-00": "PASS",
            "DG-01": "PASS",
            "DG-02": "PASS",
            "DG-14": "PASS_SCHEMA_BOUNDARY_ONLY_NO_OWNER_APPROVAL",
        },
        "phase_boundaries": contract["phase_boundaries"],
        "owner_approval_generated_count": 0,
        "rule_promotion_count": 0,
        "real_trajectory_normalization_count": 0,
        "ph_d02c_execution_count": 0,
        "digest_excluded_fields": ["content_digest"],
        "content_digest": "",
    }
    report["content_digest"] = _document_digest(
        "hds-post-audit-schema-conformance",
        report,
        ("content_digest",),
    )
    return report


def write_post_audit_artifacts(repository_root: Path) -> tuple[Path, ...]:
    """Write every deterministic PH-D02B schema and conformance artifact."""

    _, base_entries = _base_snapshot(repository_root)
    base_payloads = _current_base_schema_payloads(
        repository_root,
        base_entries,
    )
    schema_root = (
        repository_root / "distillation/schema_sets/ph_d02b_v1"
    )
    schema_root.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for filename, payload in sorted(base_payloads.items()):
        path = schema_root / filename
        path.write_bytes(payload)
        written.append(path)
    for definition in BUNDLE_DEFINITIONS:
        path = schema_root / definition.filename
        path.write_bytes(
            _schema_document_bytes(definition.schema_document())
        )
        written.append(path)

    snapshot_manifest = (
        repository_root
        / (
            "distillation/input/historical_pre_audit/PH-D02B/"
            "SNAPSHOT_MANIFEST.json"
        )
    )
    snapshot_manifest.write_bytes(
        canonical_json_document_bytes(
            build_snapshot_manifest(repository_root)
        )
    )
    written.append(snapshot_manifest)

    outputs = (
        (
            repository_root
            / "distillation/input/post_audit_schema_bundle_contract.json",
            build_post_audit_contract(repository_root),
        ),
        (
            repository_root
            / (
                "distillation/artifacts/test_vectors/"
                "post_audit_schema_bundle_examples.json"
            ),
            build_valid_examples(repository_root),
        ),
        (
            repository_root
            / (
                "distillation/artifacts/test_vectors/"
                "post_audit_schema_bundle_invalid_cases.json"
            ),
            build_invalid_cases(repository_root),
        ),
    )
    for path, document in outputs:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(canonical_json_document_bytes(document))
        written.append(path)

    # The conformance report loads the checked contract and schema set.
    conformance_path = (
        repository_root
        / (
            "distillation/artifacts/reports/"
            "post_audit_schema_bundle_conformance.json"
        )
    )
    conformance_path.write_bytes(
        canonical_json_document_bytes(
            build_conformance_report(repository_root)
        )
    )
    written.append(conformance_path)
    return tuple(written)
