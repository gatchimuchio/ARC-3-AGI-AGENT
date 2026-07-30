"""PH-D02B schema inventory, deterministic artifacts, and bundle validation.

This module is deliberately offline and standard-library-only.  It defines
the thirty-eight authority schema names, generates the thirty-three missing
closed JSON Schema documents, preserves the five earlier phase schemas by
exact bytes, and validates synthetic or future static record bundles.

It does not execute HypothesisIR, normalize teacher trajectories, promote a
RuleAtom, produce an Owner decision, or expose a runtime/solver entrypoint.
"""

from __future__ import annotations

import copy
import hashlib
import json
import math
import re
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Never, cast

from .canonical import (
    DigestExclusionPolicy,
    canonical_json_bytes,
    content_derived_id,
    logical_content_digest,
    verify_canonical_json_bytes,
)

JsonValue = None | bool | int | float | str | list["JsonValue"] | dict[str, "JsonValue"]
JsonObject = dict[str, JsonValue]

SCHEMA_DRAFT = "https://json-schema.org/draft/2020-12/schema"
SCHEMA_ID_BASE = "https://local.arc3.invalid/schemas/"
SCHEMA_CONTRACT_VERSION = "hds-schema-contract-v1"
SCHEMA_CONTRACT_ID = "HDS-PH-D02B-SCHEMA-CONTRACT-V1"
VALID_EXAMPLE_SET_ID = "HDS-PH-D02B-VALID-SCHEMA-EXAMPLES-V1"
INVALID_EXAMPLE_SET_ID = "HDS-PH-D02B-INVALID-SCHEMA-BUNDLES-V1"

CONTENT_DIGEST_PATTERN = r"^[a-z][a-z0-9-]*:[0-9a-f]{64}$"
CONTENT_ID_PATTERN = r"^[a-z][a-z0-9]*(?:[._-][a-z0-9]+)*:[0-9a-f]{64}$"
LEGACY_ID_PATTERN = r"^[a-z0-9][a-z0-9._-]+$"
SHA256_PATTERN = r"^[0-9a-f]{64}$"

ASSERTION_STATES = (
    "ASSERT",
    "SUSPEND",
    "FAIL",
    "OUT_OF_SCOPE",
)
OPERATION_STATES = (
    "CONTINUE",
    "PROBE",
    "HOLD",
    "COMMIT",
    "EXECUTE",
    "ROLLBACK",
    "STOP",
    "ABORT",
)
ADOPTION_STATES = (
    "PROPOSED",
    "PROBATION",
    "ACTIVE",
    "DEFAULT_DISABLED",
    "QUARANTINE",
    "REJECTED",
    "SUPERSEDED",
    "ARCHIVED",
)
EVIDENCE_STATES = (
    "OBSERVED",
    "REPRODUCED",
    "LOCAL_FIT",
    "STRUCTURAL_RECURRENCE",
    "GENERALIZATION_CANDIDATE",
    "UNOBSERVED_EXTRAPOLATION",
    "FALSIFIED",
    "INCONCLUSIVE",
)
MECHANISM_SUPPORT_STATES = (
    "OBSERVED_COMPATIBLE",
    "LOCAL_EXACT_FIT",
    "STRUCTURAL_RECURRENCE",
    "BOUNDARY_OBSERVED",
    "COUNTERFACTUAL_SUPPORTED",
    "REPRODUCIBLE_CONTROL",
    "FALSIFIED",
    "INCONCLUSIVE",
)
CLOSURE_STATES = (
    "OPEN",
    "PARTIALLY_CLOSED",
    "CLOSED_FOR_OPERATION",
    "CLOSED_FOR_ASSERTION",
    "REOPENED",
)
UPDATE_STATES = (
    "PROPOSED",
    "AUTHORIZED",
    "APPLIED",
    "REJECTED",
    "ROLLED_BACK",
)

HDS_STATE_AXES: dict[str, tuple[str, ...]] = {
    "adoption_state": ADOPTION_STATES,
    "assertion_state": ASSERTION_STATES,
    "closure_state": CLOSURE_STATES,
    "evidence_state": EVIDENCE_STATES,
    "mechanism_support_state": MECHANISM_SUPPORT_STATES,
    "operation_state": OPERATION_STATES,
    "update_state": UPDATE_STATES,
}

IDENTITY_ROUTING_KEYS = frozenset(
    {
        "answer_map",
        "fixed_action_sequence",
        "fixed_actions",
        "game_id",
        "hidden_state_route",
        "level_id",
        "literal_coordinate_map",
        "replay_id",
        "replay_route",
        "source_code_route",
        "task_id",
    }
)
RAW_INFERENCE_KEYS = frozenset(
    {
        "causal_role",
        "goal_hypothesis",
        "interpretation",
        "semantic_label",
        "strategy",
    }
)
DERIVATION_SEMANTIC_KEYS = frozenset(
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


class SchemaValidationError(ValueError):
    """Stable fail-closed PH-D02B schema or reference error."""

    def __init__(self, code: str, path: str = "") -> None:
        self.code = code
        self.path = path
        super().__init__(code + (":" + path if path else ""))


def _raise(code: str, path: str = "") -> Never:
    raise SchemaValidationError(code, path)


@dataclass(frozen=True, slots=True)
class ReferenceSpec:
    """One typed reference field declared by the schema contract."""

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
class SchemaDefinition:
    """Content needed to generate and validate one inventory entry."""

    index: int
    name: str
    filename: str
    schema_version: str
    id_field: str
    digest_field: str
    digest_namespace: str
    id_namespace: str
    properties: Mapping[str, Mapping[str, JsonValue]]
    required_fields: tuple[str, ...]
    references: tuple[ReferenceSpec, ...] = ()
    timestamp_fields: tuple[str, ...] = ()
    preserved_sha256: str | None = None
    legacy_id: bool = False
    semantic_rules: tuple[str, ...] = ()

    @property
    def preserved(self) -> bool:
        return self.preserved_sha256 is not None

    @property
    def digest_excluded_fields(self) -> tuple[str, ...]:
        if self.preserved:
            return (self.digest_field,)
        return tuple(
            sorted(
                {
                    self.id_field,
                    self.digest_field,
                    *self.timestamp_fields,
                }
            )
        )

    @property
    def _digest_policy(self) -> DigestExclusionPolicy:
        return DigestExclusionPolicy(
            id_fields=(frozenset() if self.preserved else frozenset({self.id_field})),
            digest_fields=frozenset({self.digest_field}),
            timestamp_fields=frozenset(self.timestamp_fields),
        )

    def as_contract_entry(self) -> JsonObject:
        schema_sha256 = self.preserved_sha256
        if schema_sha256 is None:
            schema_sha256 = hashlib.sha256(
                _stable_schema_json_bytes(build_generated_schema(self))
            ).hexdigest()
        return {
            "digest_excluded_fields": list(self.digest_excluded_fields),
            "digest_field": self.digest_field,
            "digest_namespace": self.digest_namespace,
            "filename": self.filename,
            "id_derivation": (
                "LEGACY_PHASE_STABLE_ID_CONTENT_BOUND_BY_DIGEST"
                if self.preserved
                else "HDS_CONTENT_ID_V1"
            ),
            "id_field": self.id_field,
            "id_namespace": self.id_namespace,
            "index": self.index,
            "name": self.name,
            "preserved_sha256": self.preserved_sha256,
            "references": [reference.as_json() for reference in self.references],
            "schema_sha256": schema_sha256,
            "schema_version": self.schema_version,
            "semantic_rules": list(self.semantic_rules),
            "timestamp_fields": list(self.timestamp_fields),
        }


def _string(
    *,
    pattern: str | None = None,
    min_length: int = 1,
) -> dict[str, JsonValue]:
    value: dict[str, JsonValue] = {
        "minLength": min_length,
        "type": "string",
    }
    if pattern is not None:
        value["pattern"] = pattern
    return value


def _datetime_string() -> dict[str, JsonValue]:
    return {
        "format": "date-time",
        "minLength": 1,
        "type": "string",
    }


def _enum(values: Iterable[str]) -> dict[str, JsonValue]:
    return {"enum": list(values)}


def _integer(
    *,
    minimum: int | None = None,
    maximum: int | None = None,
) -> dict[str, JsonValue]:
    value: dict[str, JsonValue] = {"type": "integer"}
    if minimum is not None:
        value["minimum"] = minimum
    if maximum is not None:
        value["maximum"] = maximum
    return value


def _boolean() -> dict[str, JsonValue]:
    return {"type": "boolean"}


def _array(
    items: Mapping[str, JsonValue] | None = None,
    *,
    min_items: int = 0,
    unique: bool = False,
) -> dict[str, JsonValue]:
    value: dict[str, JsonValue] = {
        "items": dict(items or {}),
        "minItems": min_items,
        "type": "array",
    }
    if unique:
        value["uniqueItems"] = True
    return value


def _strings(
    *,
    min_items: int = 0,
    unique: bool = True,
) -> dict[str, JsonValue]:
    return _array(
        _string(),
        min_items=min_items,
        unique=unique,
    )


def _object(
    *,
    properties: Mapping[str, Mapping[str, JsonValue]] | None = None,
    required: Sequence[str] = (),
    additional: bool = True,
) -> dict[str, JsonValue]:
    return {
        "additionalProperties": additional,
        "properties": {key: dict(value) for key, value in (properties or {}).items()},
        "required": list(required),
        "type": "object",
    }


def _nullable_string() -> dict[str, JsonValue]:
    return {"type": ["string", "null"]}


def _nullable_ref() -> dict[str, JsonValue]:
    return {"type": ["string", "null"]}


def _digest(pattern: str = CONTENT_DIGEST_PATTERN) -> dict[str, JsonValue]:
    return _string(pattern=pattern)


def _identifier(*, legacy: bool = False) -> dict[str, JsonValue]:
    return _string(pattern=LEGACY_ID_PATTERN if legacy else CONTENT_ID_PATTERN)


def _confidence() -> dict[str, JsonValue]:
    return _integer(minimum=0, maximum=1_000_000)


def _state(axis: str) -> dict[str, JsonValue]:
    return _enum(HDS_STATE_AXES[axis])


def _json_any() -> dict[str, JsonValue]:
    return {}


def _closed_within() -> dict[str, JsonValue]:
    return _object(
        properties={
            "candidate_budget": _integer(minimum=0),
            "evidence_boundary": _string(),
            "hypothesis_language_version": _string(),
            "intervention_set_digest": _digest(),
            "limitations": _strings(),
            "observed_case_set_digest": _digest(),
            "resource_profile_id": _string(),
        },
        required=(
            "hypothesis_language_version",
            "observed_case_set_digest",
            "intervention_set_digest",
            "candidate_budget",
            "resource_profile_id",
            "evidence_boundary",
            "limitations",
        ),
        additional=False,
    )


def _common_properties(
    *,
    version: str,
    id_field: str,
    digest_field: str,
    digest_namespace: str,
    excluded_fields: Sequence[str],
    legacy_id: bool,
) -> dict[str, Mapping[str, JsonValue]]:
    return {
        "digest_excluded_fields": {"const": list(excluded_fields)},
        digest_field: _digest(rf"^{re.escape(digest_namespace)}:[0-9a-f]{{64}}$"),
        id_field: _identifier(legacy=legacy_id),
        "schema_version": {"const": version},
    }


def _new_definition(
    *,
    index: int,
    name: str,
    filename: str,
    version: str,
    id_field: str,
    digest_namespace: str,
    properties: Mapping[str, Mapping[str, JsonValue]],
    required: Sequence[str],
    references: Sequence[ReferenceSpec] = (),
    timestamp_fields: Sequence[str] = (),
    semantic_rules: Sequence[str] = (),
    digest_field: str = "content_digest",
) -> SchemaDefinition:
    id_namespace = "hds-" + re.sub(r"(?<!^)(?=[A-Z])", "-", name).lower() + "-id"
    excluded = tuple(sorted({id_field, digest_field, *timestamp_fields}))
    merged = _common_properties(
        version=version,
        id_field=id_field,
        digest_field=digest_field,
        digest_namespace=digest_namespace,
        excluded_fields=excluded,
        legacy_id=False,
    )
    merged.update(properties)
    return SchemaDefinition(
        index=index,
        name=name,
        filename=filename,
        schema_version=version,
        id_field=id_field,
        digest_field=digest_field,
        digest_namespace=digest_namespace,
        id_namespace=id_namespace,
        properties=merged,
        required_fields=tuple(
            [
                "schema_version",
                id_field,
                *required,
                "digest_excluded_fields",
                digest_field,
            ]
        ),
        references=tuple(references),
        timestamp_fields=tuple(timestamp_fields),
        semantic_rules=tuple(semantic_rules),
    )


def _preserved_definition(
    *,
    index: int,
    name: str,
    filename: str,
    version: str,
    id_field: str,
    digest_field: str,
    digest_namespace: str,
    sha256: str,
    references: Sequence[ReferenceSpec] = (),
) -> SchemaDefinition:
    return SchemaDefinition(
        index=index,
        name=name,
        filename=filename,
        schema_version=version,
        id_field=id_field,
        digest_field=digest_field,
        digest_namespace=digest_namespace,
        id_namespace=digest_namespace + "-id",
        properties={},
        required_fields=(),
        references=tuple(references),
        preserved_sha256=sha256,
        legacy_id=True,
        semantic_rules=("PRESERVE_EARLIER_PHASE_SCHEMA_BYTES",),
    )


def _definitions() -> tuple[SchemaDefinition, ...]:
    """Return the authority-ordered immutable schema catalog."""

    definitions: list[SchemaDefinition] = [
        _new_definition(
            index=1,
            name="DependencyLock",
            filename="dependency_lock.schema.json",
            version="hds-dependency-lock-v1",
            id_field="lock_id",
            digest_namespace="hds-dependency-lock",
            properties={
                "authority_digests": _strings(min_items=1),
                "dependency_digests": _strings(min_items=1),
                "environment_manifest_ref": _string(),
                "interpreter_version": _string(),
                "python_version": _string(),
            },
            required=(
                "authority_digests",
                "dependency_digests",
                "environment_manifest_ref",
                "interpreter_version",
                "python_version",
            ),
            references=(
                ReferenceSpec(
                    "/environment_manifest_ref",
                    ("EnvironmentManifest",),
                ),
            ),
        ),
        _preserved_definition(
            index=2,
            name="SourceProfile",
            filename="source_profile.schema.json",
            version="hds-distillation-source-profile-v1",
            id_field="profile_id",
            digest_field="content_digest",
            digest_namespace="hds-source-profile",
            sha256=("c5f7208ef930ab86271a4d7829fb6283e4c3b9ffd80aba62eab4e948b3169e73"),
        ),
        _preserved_definition(
            index=3,
            name="SourceContentManifest",
            filename="source_content_manifest.schema.json",
            version="hds-source-content-manifest-v1",
            id_field="manifest_id",
            digest_field="content_digest",
            digest_namespace="hds-source-content-manifest",
            sha256=("252508886f21390b3fd728d68f597b57a1cef30ef385c4f5548ba14e8c2cdea8"),
            references=(
                ReferenceSpec(
                    "/source_profile/profile_id",
                    ("SourceProfile",),
                ),
                ReferenceSpec(
                    "/source_profile/profile_digest",
                    ("SourceProfile",),
                    reference_kind="DIGEST",
                ),
            ),
        ),
        _preserved_definition(
            index=4,
            name="AcquisitionRecord",
            filename="acquisition_record.schema.json",
            version="hds-acquisition-record-v1",
            id_field="acquisition_id",
            digest_field="acquisition_digest",
            digest_namespace="hds-acquisition-record",
            sha256=("c7dd1e32731ae0a9f88451a582a509ab89c2ddb339313063438fca091b514cf5"),
            references=(
                ReferenceSpec(
                    "/source_content_manifest_id",
                    ("SourceContentManifest",),
                ),
                ReferenceSpec(
                    "/source_content_digest",
                    ("SourceContentManifest",),
                    reference_kind="DIGEST",
                ),
            ),
        ),
        _preserved_definition(
            index=5,
            name="EnvironmentManifest",
            filename="environment_manifest.schema.json",
            version="hds-environment-manifest-v1",
            id_field="manifest_id",
            digest_field="content_digest",
            digest_namespace="hds-environment-manifest",
            sha256=("a4b9280feb7d90dcedea8d55ff82846414d9d7d85c4d40bc44072431713fd271"),
            references=(
                ReferenceSpec(
                    "/environment_source/source_content_manifest_id",
                    ("SourceContentManifest",),
                ),
                ReferenceSpec(
                    "/environment_source/source_content_digest",
                    ("SourceContentManifest",),
                    reference_kind="DIGEST",
                ),
            ),
        ),
        _preserved_definition(
            index=6,
            name="RunManifest",
            filename="run_manifest.schema.json",
            version="hds-run-manifest-v1",
            id_field="run_id",
            digest_field="run_digest",
            digest_namespace="hds-run-manifest",
            sha256=("888c33520b2d5b75bc1f3bab863d55954d4e001a1ac19549af578a2083714bb6"),
            references=(
                ReferenceSpec(
                    "/input_profile_ids/*",
                    ("SourceProfile",),
                ),
                ReferenceSpec(
                    "/input_content_digests/*",
                    ("SourceContentManifest",),
                    reference_kind="DIGEST",
                ),
                ReferenceSpec(
                    "/environment_manifest_digest",
                    ("EnvironmentManifest",),
                    reference_kind="DIGEST",
                ),
            ),
        ),
        _new_definition(
            index=7,
            name="ResourceProfile",
            filename="resource_profile.schema.json",
            version="hds-resource-profile-v1",
            id_field="resource_profile_id",
            digest_namespace="hds-resource-profile",
            properties={
                "arc2_intervention_budget": _integer(minimum=0),
                "arc3_intervention_budget": _integer(minimum=0),
                "candidate_count_budget": _integer(minimum=1),
                "candidate_graph_node_limit": _integer(minimum=1),
                "interpreter_step_limit": _integer(minimum=1),
                "llm_call_budget": _integer(minimum=0),
                "memory_limit_mb": _integer(minimum=1),
                "per_case_wall_seconds": _integer(minimum=1),
                "unification_timeout_ms": _integer(minimum=1),
            },
            required=(
                "candidate_count_budget",
                "candidate_graph_node_limit",
                "arc2_intervention_budget",
                "arc3_intervention_budget",
                "interpreter_step_limit",
                "unification_timeout_ms",
                "per_case_wall_seconds",
                "memory_limit_mb",
                "llm_call_budget",
            ),
            semantic_rules=("RESOURCE_LIMITS_ARE_VERSIONED_AND_EXPLICIT",),
        ),
        _new_definition(
            index=8,
            name="OperatorRegistry",
            filename="operator_registry.schema.json",
            version="hds-operator-registry-v1",
            id_field="operator_registry_id",
            digest_namespace="hds-operator-registry",
            properties={
                "dependency_lock_ref": _string(),
                "domain": _enum(("ARC2", "ARC3", "COMMON")),
                "entries": _array(
                    _object(
                        properties={
                            "canonicalization_rule": _string(),
                            "deterministic": _boolean(),
                            "domain": _enum(("ARC2", "ARC3", "COMMON")),
                            "input_types": _strings(),
                            "invalid_operation_semantics": _string(),
                            "opcode": _string(pattern=r"^[A-Z][A-Z0-9_]*$"),
                            "opcode_version": _string(),
                            "output_type": _string(),
                            "parameter_schema": _json_any(),
                            "preconditions": _strings(),
                            "resource_cost": _integer(minimum=0),
                            "side_effect_free": _boolean(),
                            "test_vector_refs": _strings(),
                        },
                        required=(
                            "opcode",
                            "opcode_version",
                            "domain",
                            "input_types",
                            "output_type",
                            "parameter_schema",
                            "preconditions",
                            "invalid_operation_semantics",
                            "deterministic",
                            "side_effect_free",
                            "resource_cost",
                            "canonicalization_rule",
                            "test_vector_refs",
                        ),
                        additional=False,
                    ),
                    min_items=1,
                ),
                "registry_version": _string(),
            },
            required=(
                "registry_version",
                "domain",
                "dependency_lock_ref",
                "entries",
            ),
            references=(
                ReferenceSpec(
                    "/dependency_lock_ref",
                    ("DependencyLock",),
                ),
            ),
        ),
        _new_definition(
            index=9,
            name="ARC2TeacherCase",
            filename="arc2_teacher_case.schema.json",
            version="hds-arc2-teacher-case-v1",
            id_field="teacher_case_id",
            digest_namespace="hds-arc2-teacher-case",
            properties={
                "answer_visibility": _enum(("ANSWER_VISIBLE", "ANSWER_UNAVAILABLE")),
                "domain": {"const": "ARC2"},
                "input_grid": _array(_array(_integer(minimum=0))),
                "output_grid": {
                    "type": ["array", "null"],
                },
                "raw_observation_refs": _strings(),
                "source_content_manifest_ref": _string(),
                "source_profile_ref": _string(),
                "split_role": _string(),
            },
            required=(
                "domain",
                "source_profile_ref",
                "source_content_manifest_ref",
                "split_role",
                "answer_visibility",
                "input_grid",
                "output_grid",
                "raw_observation_refs",
            ),
            references=(
                ReferenceSpec(
                    "/source_profile_ref",
                    ("SourceProfile",),
                ),
                ReferenceSpec(
                    "/source_content_manifest_ref",
                    ("SourceContentManifest",),
                ),
                ReferenceSpec(
                    "/raw_observation_refs/*",
                    ("RawObservation",),
                ),
            ),
        ),
        _new_definition(
            index=10,
            name="ARC3TeacherTrajectory",
            filename="arc3_teacher_trajectory.schema.json",
            version="hds-arc3-teacher-trajectory-v1",
            id_field="trajectory_id",
            digest_namespace="hds-arc3-teacher-trajectory",
            properties={
                "action_record_refs": _strings(min_items=1),
                "canonical_trajectory_digest": _digest(
                    r"^hds-canonical-trajectory:[0-9a-f]{64}$"
                ),
                "domain": {"const": "ARC3"},
                "environment_manifest_ref": _string(),
                "level_count": _integer(minimum=1),
                "raw_observation_refs": _strings(),
                "raw_trajectory_digest": _digest(r"^hds-raw-trajectory:[0-9a-f]{64}$"),
                "source_profile_ref": _string(),
                "terminal_state": _enum(("WIN", "GAME_OVER", "INCOMPLETE")),
            },
            required=(
                "domain",
                "source_profile_ref",
                "environment_manifest_ref",
                "raw_trajectory_digest",
                "canonical_trajectory_digest",
                "action_record_refs",
                "raw_observation_refs",
                "level_count",
                "terminal_state",
            ),
            references=(
                ReferenceSpec(
                    "/source_profile_ref",
                    ("SourceProfile",),
                ),
                ReferenceSpec(
                    "/environment_manifest_ref",
                    ("EnvironmentManifest",),
                ),
                ReferenceSpec(
                    "/action_record_refs/*",
                    ("ARC3ActionRecord",),
                ),
                ReferenceSpec(
                    "/raw_observation_refs/*",
                    ("RawObservation",),
                ),
            ),
            semantic_rules=("RAW_AND_CANONICAL_TRAJECTORY_DIGESTS_DIFFER",),
        ),
        _new_definition(
            index=11,
            name="ARC3ActionRecord",
            filename="arc3_action_record.schema.json",
            version="hds-arc3-action-record-v1",
            id_field="action_record_id",
            digest_namespace="hds-arc3-action-record",
            properties={
                "action_id": _integer(minimum=1, maximum=7),
                "action_payload": _json_any(),
                "available_actions_before": _array(
                    _integer(minimum=1, maximum=7),
                    min_items=1,
                    unique=True,
                ),
                "canonical_frame_after_digest": _digest(),
                "canonical_frame_before_digest": _digest(),
                "progress_delta": _integer(),
                "step_index": _integer(minimum=0),
                "terminal_state_after": _enum(("CONTINUE", "WIN", "GAME_OVER")),
                "visible_diff": _json_any(),
            },
            required=(
                "step_index",
                "action_id",
                "action_payload",
                "available_actions_before",
                "canonical_frame_before_digest",
                "canonical_frame_after_digest",
                "terminal_state_after",
                "visible_diff",
                "progress_delta",
            ),
        ),
        _new_definition(
            index=12,
            name="RawObservation",
            filename="raw_observation.schema.json",
            version="hds-raw-observation-v1",
            id_field="observation_id",
            digest_namespace="hds-raw-observation",
            properties={
                "available_actions": _array(
                    _integer(minimum=1, maximum=7),
                    unique=True,
                ),
                "domain": _enum(("ARC2", "ARC3")),
                "evidence_origin": {"const": "DIRECT_OBSERVATION"},
                "observed_fields": _strings(min_items=1),
                "progress": _integer(),
                "raw_value": _json_any(),
                "source_pointer": _string(),
                "terminal": _boolean(),
            },
            required=(
                "domain",
                "evidence_origin",
                "raw_value",
                "available_actions",
                "terminal",
                "progress",
                "source_pointer",
                "observed_fields",
            ),
            semantic_rules=(
                "DIRECT_VALUES_ONLY",
                "INFERENCE_AND_INTERPRETATION_FIELDS_FORBIDDEN",
            ),
        ),
        _new_definition(
            index=13,
            name="DeterministicDerivation",
            filename="deterministic_derivation.schema.json",
            version="hds-deterministic-derivation-v1",
            id_field="derivation_id",
            digest_namespace="hds-deterministic-derivation",
            properties={
                "algorithm_id": _string(),
                "algorithm_version": _string(),
                "configuration": _json_any(),
                "derivation_origin": {"const": "DETERMINISTIC_ALGORITHM"},
                "input_evidence_refs": _strings(min_items=1),
                "output": _json_any(),
                "output_type": _enum(
                    (
                        "CELL_DELTA",
                        "COLOR_HISTOGRAM",
                        "COMPONENTS_4",
                        "COMPONENTS_8",
                        "BOUNDING_BOX",
                        "EXACT_SHAPE_SIGNATURE",
                        "FRAME_DIFF",
                        "ACTION_EFFECT_DELTA",
                    )
                ),
            },
            required=(
                "derivation_origin",
                "algorithm_id",
                "algorithm_version",
                "configuration",
                "input_evidence_refs",
                "output",
                "output_type",
            ),
            references=(
                ReferenceSpec(
                    "/input_evidence_refs/*",
                    ("RawObservation", "DeterministicDerivation"),
                ),
            ),
            semantic_rules=(
                "DETERMINISTIC_PROVENANCE_REQUIRED",
                "SEMANTIC_LABELS_FORBIDDEN",
            ),
        ),
        _new_definition(
            index=14,
            name="InterpretationHypothesis",
            filename="interpretation_hypothesis.schema.json",
            version="hds-interpretation-hypothesis-v1",
            id_field="interpretation_id",
            digest_namespace="hds-interpretation-hypothesis",
            properties={
                "confidence_ppm": _confidence(),
                "evidence_refs": _strings(min_items=1),
                "hypothesis_kind": _enum(
                    (
                        "OBJECT_CANDIDATE",
                        "CONTROLLABLE_ENTITY",
                        "MOVEMENT_CANDIDATE",
                        "COPIED_STRUCTURE",
                        "GOAL_CANDIDATE",
                        "ACTION_SEMANTICS",
                        "CAUSAL_ROLE",
                        "ORDER_NECESSITY",
                        "IRREVERSIBILITY",
                    )
                ),
                "statement": _string(),
                "status": _enum(("PROPOSED", "HELD", "REJECTED", "FALSIFIED")),
            },
            required=(
                "hypothesis_kind",
                "statement",
                "evidence_refs",
                "confidence_ppm",
                "status",
            ),
            references=(
                ReferenceSpec(
                    "/evidence_refs/*",
                    ("RawObservation", "DeterministicDerivation"),
                ),
            ),
            semantic_rules=("INTERPRETATION_IS_NOT_DIRECT_EVIDENCE",),
        ),
        _new_definition(
            index=15,
            name="EvidenceRecord",
            filename="evidence_record.schema.json",
            version="hds-evidence-record-v1",
            id_field="evidence_id",
            digest_namespace="hds-evidence-record",
            properties={
                "evidence_origin": _enum(
                    (
                        "RAW_OBSERVATION",
                        "DETERMINISTIC_DERIVATION",
                    )
                ),
                "evidence_ref": _string(),
                "evidence_state": _state("evidence_state"),
                "limitations": _strings(),
                "provenance": _object(),
            },
            required=(
                "evidence_origin",
                "evidence_ref",
                "evidence_state",
                "limitations",
                "provenance",
            ),
            references=(
                ReferenceSpec(
                    "/evidence_ref",
                    ("RawObservation", "DeterministicDerivation"),
                ),
            ),
            semantic_rules=("EVIDENCE_ORIGIN_MUST_MATCH_REFERENCE_TYPE",),
        ),
        _new_definition(
            index=16,
            name="DistillationFrame",
            filename="distillation_frame.schema.json",
            version="hds-distillation-frame-v1",
            id_field="frame_id",
            digest_namespace="hds-distillation-frame",
            properties={
                "Mc": _object(),
                "R_observable": _object(),
                "X": _object(),
                "authority_boundary": _strings(min_items=1),
                "candidate_budget": _integer(minimum=1),
                "domain": _enum(("ARC2", "ARC3")),
                "evidence_boundary": _string(),
                "hds_dependency_digest": _digest(),
                "hypothesis_language_version": _string(),
                "intervention_budget": _integer(minimum=0),
                "non_goals": _strings(min_items=1),
                "purpose": _string(),
                "resource_profile_ref": _string(),
                "rollback_conditions": _strings(min_items=1),
                "source_scope_refs": _strings(min_items=1),
                "spec_version": _string(),
                "stop_conditions": _strings(min_items=1),
                "unresolved_term_refs": _strings(),
            },
            required=(
                "spec_version",
                "hds_dependency_digest",
                "domain",
                "purpose",
                "X",
                "R_observable",
                "Mc",
                "source_scope_refs",
                "evidence_boundary",
                "hypothesis_language_version",
                "candidate_budget",
                "intervention_budget",
                "resource_profile_ref",
                "authority_boundary",
                "non_goals",
                "stop_conditions",
                "rollback_conditions",
                "unresolved_term_refs",
            ),
            references=(
                ReferenceSpec(
                    "/resource_profile_ref",
                    ("ResourceProfile",),
                ),
                ReferenceSpec(
                    "/source_scope_refs/*",
                    ("SourceProfile",),
                ),
                ReferenceSpec(
                    "/unresolved_term_refs/*",
                    ("OpenTermRecord",),
                ),
            ),
            semantic_rules=(
                "DG_00_FRAME_COORDINATE",
                "DG_01_OPEN_TERM",
                "DG_02_X_R_MC_SCOPE_CLOSURE",
            ),
        ),
    ]

    definitions.extend(_remaining_definitions())
    ordered = tuple(definitions)
    if tuple(item.index for item in ordered) != tuple(range(1, 39)):
        raise AssertionError("D02B_INTERNAL_SCHEMA_INDEX_DRIFT")
    if len({item.name for item in ordered}) != 38:
        raise AssertionError("D02B_INTERNAL_SCHEMA_NAME_DUPLICATE")
    if len({item.filename for item in ordered}) != 38:
        raise AssertionError("D02B_INTERNAL_SCHEMA_FILENAME_DUPLICATE")
    return ordered


def _remaining_definitions() -> list[SchemaDefinition]:
    """Definitions 17-38, split only to keep the catalog readable."""

    return [
        _new_definition(
            index=17,
            name="HypothesisIR",
            filename="hypothesis_ir.schema.json",
            version="hds-causal-ir-v1",
            id_field="hypothesis_ir_id",
            digest_namespace="hds-hypothesis-ir",
            properties={
                "domain": _enum(("ARC2", "ARC3")),
                "exclusions": _strings(),
                "falsification_procedures": _array(_object()),
                "frame_ref": _string(),
                "input_types": _strings(min_items=1),
                "invariants": _array(_object()),
                "ir_version": _string(),
                "operator_graph": _array(_object(), min_items=1),
                "operator_registry_ref": _string(),
                "ordering_constraints": _array(_object()),
                "preconditions": _array(_object()),
                "predicted_effects": _array(_object(), min_items=1),
                "resource_cost": _integer(minimum=0),
                "selector_graph": _array(_object(), min_items=1),
                "stop_conditions": _array(_object()),
            },
            required=(
                "ir_version",
                "domain",
                "frame_ref",
                "operator_registry_ref",
                "input_types",
                "selector_graph",
                "preconditions",
                "operator_graph",
                "ordering_constraints",
                "stop_conditions",
                "predicted_effects",
                "invariants",
                "exclusions",
                "falsification_procedures",
                "resource_cost",
            ),
            references=(
                ReferenceSpec(
                    "/frame_ref",
                    ("DistillationFrame",),
                ),
                ReferenceSpec(
                    "/operator_registry_ref",
                    ("OperatorRegistry",),
                ),
            ),
            semantic_rules=(
                "SCHEMA_ONLY_NOT_EXECUTABLE_IN_PH_D02B",
                "IDENTITY_ROUTING_FIELDS_FORBIDDEN",
            ),
        ),
        _new_definition(
            index=18,
            name="CounterfactualInterventionPlan",
            filename="counterfactual_intervention_plan.schema.json",
            version="hds-counterfactual-intervention-plan-v1",
            id_field="intervention_plan_id",
            digest_namespace="hds-counterfactual-intervention-plan",
            properties={
                "domain": _enum(("ARC2", "ARC3")),
                "freeze_state": {"const": "PRE_RESULT_FROZEN"},
                "hypothesis_ir_ref": _string(),
                "intervention_kind": _string(),
                "predicted_outcomes": _array(_object(), min_items=2),
                "resource_profile_ref": _string(),
                "reversibility": _enum(("REVERSIBLE", "RESET_BOUND", "NOT_EXECUTABLE")),
                "safety_constraints": _strings(min_items=1),
            },
            required=(
                "domain",
                "hypothesis_ir_ref",
                "intervention_kind",
                "predicted_outcomes",
                "reversibility",
                "safety_constraints",
                "resource_profile_ref",
                "freeze_state",
            ),
            references=(
                ReferenceSpec(
                    "/hypothesis_ir_ref",
                    ("HypothesisIR",),
                ),
                ReferenceSpec(
                    "/resource_profile_ref",
                    ("ResourceProfile",),
                ),
            ),
            semantic_rules=("PLAN_PRECEDES_RESULT",),
        ),
        _new_definition(
            index=19,
            name="InterventionResult",
            filename="intervention_result.schema.json",
            version="hds-intervention-result-v1",
            id_field="intervention_result_id",
            digest_namespace="hds-intervention-result",
            properties={
                "evidence_refs": _strings(min_items=1),
                "intervention_plan_ref": _string(),
                "observed_outcome": _json_any(),
                "operation_state": _state("operation_state"),
                "reason_codes": _strings(),
                "result_state": _enum(
                    (
                        "OBSERVED",
                        "SUSPEND_RESOURCE",
                        "NOT_EXECUTABLE",
                        "FAILED_SAFE",
                    )
                ),
            },
            required=(
                "intervention_plan_ref",
                "result_state",
                "observed_outcome",
                "evidence_refs",
                "operation_state",
                "reason_codes",
            ),
            references=(
                ReferenceSpec(
                    "/intervention_plan_ref",
                    ("CounterfactualInterventionPlan",),
                ),
                ReferenceSpec(
                    "/evidence_refs/*",
                    ("EvidenceRecord",),
                ),
            ),
        ),
        _new_definition(
            index=20,
            name="LLMCaptureRecord",
            filename="llm_capture_record.schema.json",
            version="hds-llm-capture-record-v1",
            id_field="capture_id",
            digest_namespace="hds-llm-capture-record",
            properties={
                "captured_at": _datetime_string(),
                "model": _string(),
                "parameters": _object(),
                "prompt_digest": _digest(),
                "raw_response_sha256": _digest(SHA256_PATTERN),
                "request_digest": _digest(),
                "run_manifest_ref": _string(),
            },
            required=(
                "run_manifest_ref",
                "prompt_digest",
                "model",
                "parameters",
                "request_digest",
                "raw_response_sha256",
                "captured_at",
            ),
            references=(
                ReferenceSpec(
                    "/run_manifest_ref",
                    ("RunManifest",),
                ),
            ),
            timestamp_fields=("captured_at",),
            semantic_rules=("CAPTURE_ONLY_NO_LIVE_LLM_REBUILD",),
        ),
        _new_definition(
            index=21,
            name="ModelRecord",
            filename="model_record.schema.json",
            version="hds-model-record-v1",
            id_field="model_id",
            digest_namespace="hds-model-record",
            properties={
                "assumptions": _strings(),
                "confidence_ppm": _confidence(),
                "contradicting_evidence_refs": _strings(),
                "expected_observations": _array(_object()),
                "falsification_procedure": _object(),
                "frame_ref": _string(),
                "hypothesis_ir_ref": _string(),
                "model_type": _enum(
                    (
                        "BASELINE",
                        "ALTERNATIVE",
                        "COUNTER_HYPOTHESIS",
                        "NULL_MODEL",
                        "NO_OP",
                        "OBSERVATION_ERROR",
                        "DELAYED_EFFECT",
                        "DIFFERENT_GOAL",
                        "WRONG_TARGET",
                        "WRONG_ORDER",
                        "OVERFIT",
                        "SURFACE_CORRELATION",
                        "ANSWER_COPY_ADVERSARIAL",
                        "TRAJECTORY_LOOKUP_ADVERSARIAL",
                    )
                ),
                "resource_requirement": _object(),
                "risks": _strings(),
                "statement": _string(),
                "status": _enum(("PROPOSED", "HELD", "REJECTED", "FALSIFIED")),
                "supporting_evidence_refs": _strings(),
                "valid_scope": _object(),
            },
            required=(
                "frame_ref",
                "model_type",
                "statement",
                "hypothesis_ir_ref",
                "assumptions",
                "supporting_evidence_refs",
                "contradicting_evidence_refs",
                "expected_observations",
                "falsification_procedure",
                "valid_scope",
                "resource_requirement",
                "risks",
                "confidence_ppm",
                "status",
            ),
            references=(
                ReferenceSpec("/frame_ref", ("DistillationFrame",)),
                ReferenceSpec("/hypothesis_ir_ref", ("HypothesisIR",)),
                ReferenceSpec(
                    "/supporting_evidence_refs/*",
                    ("EvidenceRecord",),
                ),
                ReferenceSpec(
                    "/contradicting_evidence_refs/*",
                    ("EvidenceRecord",),
                ),
            ),
            semantic_rules=("MODEL_SELECTOR_IDENTITY_FIELDS_FORBIDDEN",),
        ),
        _new_definition(
            index=22,
            name="GateResult",
            filename="gate_result.schema.json",
            version="hds-gate-result-v1",
            id_field="gate_result_id",
            digest_namespace="hds-gate-result",
            properties={
                "evidence_refs": _strings(),
                "evidence_state": _state("evidence_state"),
                "frame_ref": _string(),
                "gate_id": _string(pattern=r"^DG-(0[0-9]|1[0-5])$"),
                "mechanism_support_state": _state("mechanism_support_state"),
                "model_refs": _strings(),
                "reason_codes": _strings(),
                "result": _enum(("PASS", "FAIL", "SUSPEND")),
            },
            required=(
                "gate_id",
                "frame_ref",
                "model_refs",
                "evidence_refs",
                "evidence_state",
                "mechanism_support_state",
                "result",
                "reason_codes",
            ),
            references=(
                ReferenceSpec("/frame_ref", ("DistillationFrame",)),
                ReferenceSpec("/model_refs/*", ("ModelRecord",)),
                ReferenceSpec(
                    "/evidence_refs/*",
                    ("EvidenceRecord",),
                ),
            ),
        ),
        _new_definition(
            index=23,
            name="DecisionRecord",
            filename="decision_record.schema.json",
            version="hds-decision-record-v1",
            id_field="decision_id",
            digest_namespace="hds-decision-record",
            properties={
                "adoption_state": _state("adoption_state"),
                "assertion_state": _state("assertion_state"),
                "closure_state": _state("closure_state"),
                "decision_mode": _enum(("SINGLE", "MULTI_CAUSAL", "SUSPEND")),
                "evidence_state": _state("evidence_state"),
                "expected_outcome": _object(),
                "falsification_condition": _object(),
                "frame_ref": _string(),
                "gate_result_refs": _strings(min_items=1),
                "held_model_refs": _strings(),
                "mechanism_support_state": _state("mechanism_support_state"),
                "operation_state": _state("operation_state"),
                "reason_codes": _strings(min_items=1),
                "rejected_model_refs": _strings(),
                "rollback_condition": _object(),
                "selected_model_refs": _strings(),
                "stop_condition": _object(),
                "update_state": _state("update_state"),
            },
            required=(
                "frame_ref",
                "decision_mode",
                "selected_model_refs",
                "held_model_refs",
                "rejected_model_refs",
                "gate_result_refs",
                "reason_codes",
                "expected_outcome",
                "falsification_condition",
                "rollback_condition",
                "stop_condition",
                "assertion_state",
                "operation_state",
                "adoption_state",
                "evidence_state",
                "mechanism_support_state",
                "closure_state",
                "update_state",
            ),
            references=(
                ReferenceSpec("/frame_ref", ("DistillationFrame",)),
                ReferenceSpec(
                    "/gate_result_refs/*",
                    ("GateResult",),
                ),
                ReferenceSpec(
                    "/selected_model_refs/*",
                    ("ModelRecord",),
                ),
                ReferenceSpec(
                    "/held_model_refs/*",
                    ("ModelRecord",),
                ),
                ReferenceSpec(
                    "/rejected_model_refs/*",
                    ("ModelRecord",),
                ),
            ),
            semantic_rules=(
                "STATE_AXES_INDEPENDENT",
                "MULTI_CAUSAL_OR_SUSPEND_DOES_NOT_FORCE_SINGLE_CHOICE",
                "MODEL_REFERENCE_SETS_DISJOINT",
            ),
        ),
        _new_definition(
            index=24,
            name="HDSCausalRecord",
            filename="hds_causal_record.schema.json",
            version="hds-causal-record-v1",
            id_field="record_id",
            digest_namespace="hds-causal-record",
            properties={
                "adoption_state": _state("adoption_state"),
                "assertion_state": _state("assertion_state"),
                "claim_refs": _strings(),
                "closed_within": _closed_within(),
                "closure_state": _state("closure_state"),
                "decision_ref": _string(),
                "deterministic_derivation_refs": _strings(),
                "evidence_state": _state("evidence_state"),
                "failure_signature_refs": _strings(),
                "frame_ref": _string(),
                "gate_result_refs": _strings(min_items=1),
                "held_model_refs": _strings(),
                "interpretation_hypothesis_refs": _strings(),
                "intervention_result_refs": _strings(),
                "mechanism_support_state": _state("mechanism_support_state"),
                "model_refs": _strings(min_items=1),
                "open_term_refs": _strings(),
                "operation_state": _state("operation_state"),
                "raw_observation_refs": _strings(min_items=1),
                "record_version": _integer(minimum=1),
                "rejected_model_refs": _strings(),
                "selected_model_refs": _strings(),
                "summary": _string(),
                "update_proposal_refs": _strings(),
                "update_state": _state("update_state"),
            },
            required=(
                "record_version",
                "frame_ref",
                "raw_observation_refs",
                "deterministic_derivation_refs",
                "interpretation_hypothesis_refs",
                "model_refs",
                "selected_model_refs",
                "held_model_refs",
                "rejected_model_refs",
                "gate_result_refs",
                "decision_ref",
                "intervention_result_refs",
                "failure_signature_refs",
                "open_term_refs",
                "assertion_state",
                "operation_state",
                "adoption_state",
                "evidence_state",
                "mechanism_support_state",
                "closure_state",
                "update_state",
                "closed_within",
                "claim_refs",
                "update_proposal_refs",
                "summary",
            ),
            references=(
                ReferenceSpec("/frame_ref", ("DistillationFrame",)),
                ReferenceSpec(
                    "/raw_observation_refs/*",
                    ("RawObservation",),
                ),
                ReferenceSpec(
                    "/deterministic_derivation_refs/*",
                    ("DeterministicDerivation",),
                ),
                ReferenceSpec(
                    "/interpretation_hypothesis_refs/*",
                    ("InterpretationHypothesis",),
                ),
                ReferenceSpec("/model_refs/*", ("ModelRecord",)),
                ReferenceSpec(
                    "/selected_model_refs/*",
                    ("ModelRecord",),
                ),
                ReferenceSpec(
                    "/held_model_refs/*",
                    ("ModelRecord",),
                ),
                ReferenceSpec(
                    "/rejected_model_refs/*",
                    ("ModelRecord",),
                ),
                ReferenceSpec(
                    "/gate_result_refs/*",
                    ("GateResult",),
                ),
                ReferenceSpec("/decision_ref", ("DecisionRecord",)),
                ReferenceSpec(
                    "/intervention_result_refs/*",
                    ("InterventionResult",),
                ),
                ReferenceSpec(
                    "/failure_signature_refs/*",
                    ("FailureSignature",),
                ),
                ReferenceSpec(
                    "/open_term_refs/*",
                    ("OpenTermRecord",),
                ),
                ReferenceSpec("/claim_refs/*", ("ClaimRecord",)),
                ReferenceSpec(
                    "/closed_within/resource_profile_id",
                    ("ResourceProfile",),
                ),
                ReferenceSpec(
                    "/update_proposal_refs/*",
                    ("PromotionDecision",),
                ),
            ),
            semantic_rules=(
                "STATE_AXES_INDEPENDENT",
                "NATURAL_LANGUAGE_SUMMARY_NON_AUTHORITATIVE",
            ),
        ),
        _new_definition(
            index=25,
            name="RuleAtom",
            filename="rule_atom.schema.json",
            version="hds-rule-atom-v1",
            id_field="rule_id",
            digest_namespace="hds-rule-atom",
            properties={
                "adoption_state": _enum(("PROPOSED", "PROBATION")),
                "alternative_adequacy": _object(),
                "approval_ref": _nullable_ref(),
                "closure_boundary": _object(),
                "counterexample_refs": _strings(),
                "domain": _enum(("ARC2", "ARC3")),
                "effect": _object(),
                "evidence_state": _state("evidence_state"),
                "exclusions": _array(_object()),
                "intervention_coverage": _object(),
                "invariants": _array(_object()),
                "mechanism_support_state": _state("mechanism_support_state"),
                "mechanism_template_ir_ref": _string(),
                "near_miss_case_refs": _strings(),
                "negative_pool_case_refs": _strings(),
                "normalization_certificate_refs": _strings(),
                "preconditions": _array(_object()),
                "promotion_decision_ref": _nullable_ref(),
                "provenance": _object(),
                "rule_version": _integer(minimum=1),
                "support_case_refs": _strings(min_items=1),
                "support_selection_method": _string(),
                "trigger": _object(),
                "valid_scope": _object(),
            },
            required=(
                "rule_version",
                "domain",
                "mechanism_template_ir_ref",
                "trigger",
                "preconditions",
                "effect",
                "invariants",
                "exclusions",
                "valid_scope",
                "support_case_refs",
                "negative_pool_case_refs",
                "near_miss_case_refs",
                "counterexample_refs",
                "support_selection_method",
                "alternative_adequacy",
                "intervention_coverage",
                "evidence_state",
                "mechanism_support_state",
                "adoption_state",
                "closure_boundary",
                "provenance",
                "normalization_certificate_refs",
                "promotion_decision_ref",
                "approval_ref",
            ),
            references=(
                ReferenceSpec(
                    "/mechanism_template_ir_ref",
                    ("HypothesisIR",),
                ),
                ReferenceSpec(
                    "/support_case_refs/*",
                    ("ARC2TeacherCase", "ARC3TeacherTrajectory"),
                ),
                ReferenceSpec(
                    "/negative_pool_case_refs/*",
                    ("ARC2TeacherCase", "ARC3TeacherTrajectory"),
                ),
                ReferenceSpec(
                    "/near_miss_case_refs/*",
                    ("ARC2TeacherCase", "ARC3TeacherTrajectory"),
                ),
                ReferenceSpec(
                    "/counterexample_refs/*",
                    ("CounterexampleRecord",),
                ),
                ReferenceSpec(
                    "/normalization_certificate_refs/*",
                    ("NormalizationCertificate",),
                ),
                ReferenceSpec(
                    "/promotion_decision_ref",
                    ("PromotionDecision",),
                    required_resolution=False,
                ),
                ReferenceSpec(
                    "/approval_ref",
                    ("ApprovalRecord",),
                    required_resolution=False,
                ),
            ),
            semantic_rules=(
                "INITIAL_ADOPTION_PROPOSED_OR_PROBATION_ONLY",
                "NO_IDENTITY_OR_ANSWER_LOOKUP_ROUTING",
                "NO_AUTOMATIC_PROMOTION",
            ),
        ),
        _new_definition(
            index=26,
            name="RuleFamily",
            filename="rule_family.schema.json",
            version="hds-rule-family-v1",
            id_field="rule_family_id",
            digest_namespace="hds-rule-family",
            properties={
                "adoption_state": _enum(("PROPOSED", "PROBATION")),
                "approval_ref": _nullable_ref(),
                "domain": _enum(("ARC2", "ARC3")),
                "family_statement": _string(),
                "promotion_decision_ref": _nullable_ref(),
                "provenance": _object(),
                "rule_atom_refs": _strings(min_items=1),
                "unification_constraints": _array(_object()),
                "valid_scope": _object(),
            },
            required=(
                "domain",
                "family_statement",
                "rule_atom_refs",
                "unification_constraints",
                "valid_scope",
                "adoption_state",
                "provenance",
                "promotion_decision_ref",
                "approval_ref",
            ),
            references=(
                ReferenceSpec(
                    "/rule_atom_refs/*",
                    ("RuleAtom",),
                ),
                ReferenceSpec(
                    "/promotion_decision_ref",
                    ("PromotionDecision",),
                    required_resolution=False,
                ),
                ReferenceSpec(
                    "/approval_ref",
                    ("ApprovalRecord",),
                    required_resolution=False,
                ),
            ),
            semantic_rules=(
                "CROSS_DOMAIN_RULE_FAMILY_FORBIDDEN",
                "INITIAL_ADOPTION_PROPOSED_OR_PROBATION_ONLY",
            ),
        ),
        _new_definition(
            index=27,
            name="BoundaryRecord",
            filename="boundary_record.schema.json",
            version="hds-boundary-record-v1",
            id_field="boundary_id",
            digest_namespace="hds-boundary-record",
            properties={
                "affected_scope": _object(),
                "boundary_kind": _string(),
                "evidence_refs": _strings(min_items=1),
                "near_miss_case_refs": _strings(),
                "target_ref": _string(),
                "unaffected_scope": _object(),
            },
            required=(
                "target_ref",
                "boundary_kind",
                "affected_scope",
                "unaffected_scope",
                "near_miss_case_refs",
                "evidence_refs",
            ),
            references=(
                ReferenceSpec(
                    "/target_ref",
                    ("ModelRecord", "RuleAtom", "RuleFamily"),
                ),
                ReferenceSpec(
                    "/near_miss_case_refs/*",
                    ("ARC2TeacherCase", "ARC3TeacherTrajectory"),
                ),
                ReferenceSpec(
                    "/evidence_refs/*",
                    ("EvidenceRecord",),
                ),
            ),
        ),
        _new_definition(
            index=28,
            name="CounterexampleRecord",
            filename="counterexample_record.schema.json",
            version="hds-counterexample-record-v1",
            id_field="counterexample_id",
            digest_namespace="hds-counterexample-record",
            properties={
                "case_ref": _string(),
                "contradiction": _object(),
                "evidence_refs": _strings(min_items=1),
                "target_ref": _string(),
            },
            required=(
                "target_ref",
                "case_ref",
                "contradiction",
                "evidence_refs",
            ),
            references=(
                ReferenceSpec(
                    "/target_ref",
                    ("ModelRecord", "RuleAtom", "RuleFamily"),
                ),
                ReferenceSpec(
                    "/case_ref",
                    ("ARC2TeacherCase", "ARC3TeacherTrajectory"),
                ),
                ReferenceSpec(
                    "/evidence_refs/*",
                    ("EvidenceRecord",),
                ),
            ),
        ),
        _new_definition(
            index=29,
            name="FailureSignature",
            filename="failure_signature.schema.json",
            version="hds-failure-signature-v1",
            id_field="signature_id",
            digest_namespace="hds-failure-signature",
            properties={
                "affected_scope": _object(),
                "attempted_hypothesis_ref": _nullable_ref(),
                "cognition_stage": _string(),
                "domain_failure_code": _string(),
                "evidence_state": _state("evidence_state"),
                "hds_failure_class": _string(),
                "next_probe_axes": _strings(),
                "provenance": _object(),
                "public_local_boundary": _string(),
                "recurrence_count": _integer(minimum=1),
                "recovery": _object(),
                "regression_risk": _string(),
                "repair_requirement": _string(),
                "reusable_check": _string(),
                "status": _enum(("ACTIVE", "RESOLVED", "QUARANTINED")),
                "structural_cause": _string(),
                "surface_symptom": _string(),
                "target_ref": _string(),
                "target_version": _string(),
                "trigger": _object(),
                "unaffected_scope": _object(),
                "violated_assumption": _string(),
            },
            required=(
                "target_ref",
                "target_version",
                "attempted_hypothesis_ref",
                "hds_failure_class",
                "domain_failure_code",
                "cognition_stage",
                "surface_symptom",
                "structural_cause",
                "trigger",
                "affected_scope",
                "unaffected_scope",
                "violated_assumption",
                "evidence_state",
                "public_local_boundary",
                "repair_requirement",
                "recovery",
                "next_probe_axes",
                "reusable_check",
                "regression_risk",
                "recurrence_count",
                "status",
                "provenance",
            ),
            references=(
                ReferenceSpec(
                    "/target_ref",
                    (
                        "ModelRecord",
                        "RuleAtom",
                        "RuleFamily",
                        "HDSCausalRecord",
                    ),
                ),
                ReferenceSpec(
                    "/attempted_hypothesis_ref",
                    ("HypothesisIR",),
                    required_resolution=False,
                ),
            ),
        ),
        _new_definition(
            index=30,
            name="NormalizationCertificate",
            filename="normalization_certificate.schema.json",
            version="hds-normalization-certificate-v1",
            id_field="certificate_id",
            digest_namespace="hds-normalization-certificate",
            properties={
                "canonical_record_digest": _digest(),
                "equivalence_evidence_refs": _strings(),
                "information_loss": _enum(
                    ("NONE", "CONDITIONAL", "GENERALIZATION_ADDED")
                ),
                "inverse_mapping": _object(),
                "normalization_class": _enum(
                    (
                        "LOSSLESS_NORMALIZATION",
                        "SEMANTIC_REWRITE",
                        "GENERALIZATION_CANDIDATE",
                    )
                ),
                "required_assumptions": _strings(),
                "rewrite_rule_ref": _nullable_ref(),
                "source_record_digest": _digest(),
                "status": _enum(("PROPOSED", "VERIFIED", "REJECTED", "SUSPEND")),
                "variable_mapping": _object(),
            },
            required=(
                "normalization_class",
                "source_record_digest",
                "canonical_record_digest",
                "rewrite_rule_ref",
                "variable_mapping",
                "inverse_mapping",
                "required_assumptions",
                "equivalence_evidence_refs",
                "information_loss",
                "status",
            ),
            references=(
                ReferenceSpec(
                    "/rewrite_rule_ref",
                    ("RuleAtom",),
                    required_resolution=False,
                ),
                ReferenceSpec(
                    "/equivalence_evidence_refs/*",
                    ("EvidenceRecord",),
                ),
            ),
            semantic_rules=(
                "NORMALIZATION_CLASSES_SEPARATE",
                "NO_CROSS_DOMAIN_PROMOTION",
            ),
        ),
        _new_definition(
            index=31,
            name="PromotionDecision",
            filename="promotion_decision.schema.json",
            version="hds-promotion-decision-v1",
            id_field="promotion_decision_id",
            digest_namespace="hds-promotion-decision",
            properties={
                "approval_ref": _nullable_ref(),
                "decision": _enum(("PROPOSE", "PROMOTE", "REJECT", "SUSPEND")),
                "evidence_refs": _strings(),
                "gate_result_refs": _strings(min_items=1),
                "previous_adoption_state": _state("adoption_state"),
                "proposed_adoption_state": _state("adoption_state"),
                "reason_codes": _strings(min_items=1),
                "target_ref": _string(),
            },
            required=(
                "target_ref",
                "previous_adoption_state",
                "proposed_adoption_state",
                "decision",
                "gate_result_refs",
                "evidence_refs",
                "reason_codes",
                "approval_ref",
            ),
            references=(
                ReferenceSpec(
                    "/target_ref",
                    ("RuleAtom", "RuleFamily"),
                ),
                ReferenceSpec(
                    "/gate_result_refs/*",
                    ("GateResult",),
                ),
                ReferenceSpec(
                    "/evidence_refs/*",
                    ("EvidenceRecord",),
                ),
                ReferenceSpec(
                    "/approval_ref",
                    ("ApprovalRecord",),
                    required_resolution=False,
                ),
            ),
            semantic_rules=(
                "PROMOTE_REQUIRES_TRUSTED_OWNER_APPROVAL",
                "NO_AUTOMATIC_PROMOTION",
            ),
        ),
        _new_definition(
            index=32,
            name="ApprovalRecord",
            filename="approval_record.schema.json",
            version="hds-approval-record-v1",
            id_field="approval_id",
            digest_namespace="owner-approval-record",
            digest_field="approval_artifact_digest",
            properties={
                "approval_mode": _enum(("SCHEMA_TEMPLATE", "OWNER_RECORDED")),
                "approved_at": _datetime_string(),
                "authority": _string(),
                "authoritative": _boolean(),
                "decision": _enum(("APPROVE", "REJECT", "SUSPEND")),
                "evidence_refs": _strings(),
                "next_state": _string(),
                "previous_state": _string(),
                "reason_codes": _strings(min_items=1),
                "spec_version": _string(),
                "target_artifact_digest": _digest(),
            },
            required=(
                "approval_mode",
                "authoritative",
                "authority",
                "target_artifact_digest",
                "previous_state",
                "next_state",
                "decision",
                "reason_codes",
                "evidence_refs",
                "spec_version",
                "approved_at",
            ),
            references=(
                ReferenceSpec(
                    "/evidence_refs/*",
                    ("EvidenceRecord", "GateResult", "ClaimRecord"),
                ),
            ),
            timestamp_fields=("approved_at",),
            semantic_rules=(
                "SCHEMA_TEMPLATE_IS_NON_AUTHORITATIVE",
                "OWNER_RECORDED_REQUIRES_TRUSTED_EXTERNAL_DIGEST",
                "DG_14_AUTHORITY_APPROVAL",
            ),
        ),
        _new_definition(
            index=33,
            name="OpenTermRecord",
            filename="open_term_record.schema.json",
            version="hds-open-term-record-v1",
            id_field="open_term_id",
            digest_namespace="hds-open-term-record",
            properties={
                "blocking": _boolean(),
                "evidence_refs": _strings(),
                "frame_ref": _string(),
                "information_value": _string(),
                "question": _string(),
                "required_resolution": _string(),
                "status": _enum(("OPEN", "RESOLVED", "OUT_OF_SCOPE")),
                "term": _string(),
            },
            required=(
                "frame_ref",
                "term",
                "question",
                "required_resolution",
                "information_value",
                "blocking",
                "status",
                "evidence_refs",
            ),
            references=(
                ReferenceSpec("/frame_ref", ("DistillationFrame",)),
                ReferenceSpec(
                    "/evidence_refs/*",
                    ("EvidenceRecord",),
                ),
            ),
            semantic_rules=("MISSING_INFORMATION_REMAINS_EXPLICIT",),
        ),
        _new_definition(
            index=34,
            name="ClaimRecord",
            filename="claim_record.schema.json",
            version="hds-claim-record-v1",
            id_field="claim_id",
            digest_namespace="hds-claim-record",
            properties={
                "approval_ref": _nullable_ref(),
                "assertion_state": _state("assertion_state"),
                "claim_scope": _object(),
                "claim_text": _string(),
                "claim_type": _enum(
                    (
                        "FACT",
                        "INFERENCE",
                        "HYPOTHESIS",
                        "DESIGN_DECISION",
                        "RECOMMENDATION",
                        "BOUNDARY_DECLARATION",
                        "UNKNOWN",
                    )
                ),
                "confidence_ppm": _confidence(),
                "evidence_refs": _strings(),
                "limitations": _strings(),
            },
            required=(
                "claim_type",
                "claim_text",
                "claim_scope",
                "assertion_state",
                "evidence_refs",
                "confidence_ppm",
                "limitations",
                "approval_ref",
            ),
            references=(
                ReferenceSpec(
                    "/evidence_refs/*",
                    ("EvidenceRecord", "GateResult"),
                ),
                ReferenceSpec(
                    "/approval_ref",
                    ("ApprovalRecord",),
                    required_resolution=False,
                ),
            ),
            semantic_rules=("CLAIM_STRENGTH_CANNOT_EXCEED_EVIDENCE",),
        ),
        _new_definition(
            index=35,
            name="DistillationAudit",
            filename="distillation_audit.schema.json",
            version="hds-distillation-audit-v1",
            id_field="audit_id",
            digest_namespace="hds-distillation-audit",
            properties={
                "audited_artifact_digests": _strings(min_items=1),
                "causal_record_refs": _strings(),
                "failed_check_ids": _strings(),
                "finding_count": _integer(minimum=0),
                "gate_result_refs": _strings(min_items=1),
                "passed_check_ids": _strings(),
                "scope": _object(),
                "status": _enum(("PASS", "FAIL", "SUSPEND")),
            },
            required=(
                "scope",
                "audited_artifact_digests",
                "causal_record_refs",
                "gate_result_refs",
                "passed_check_ids",
                "failed_check_ids",
                "finding_count",
                "status",
            ),
            references=(
                ReferenceSpec(
                    "/causal_record_refs/*",
                    ("HDSCausalRecord",),
                ),
                ReferenceSpec(
                    "/gate_result_refs/*",
                    ("GateResult",),
                ),
            ),
        ),
        _new_definition(
            index=36,
            name="CoverageReport",
            filename="coverage_report.schema.json",
            version="hds-coverage-report-v1",
            id_field="coverage_report_id",
            digest_namespace="hds-coverage-report",
            properties={
                "boundary_observed_count": _integer(minimum=0),
                "counterfactual_supported_count": _integer(minimum=0),
                "coverage_by_domain": _object(),
                "coverage_by_source_profile": _object(),
                "falsified_count": _integer(minimum=0),
                "local_exact_fit_count": _integer(minimum=0),
                "multi_causal_count": _integer(minimum=0),
                "observed_compatible_count": _integer(minimum=0),
                "open_term_count": _integer(minimum=0),
                "open_term_refs": _strings(),
                "partial_count": _integer(minimum=0),
                "processed_case_count": _integer(minimum=0),
                "promoted_rule_count": _integer(minimum=0),
                "promoted_rule_refs": _strings(),
                "provenance_complete_count": _integer(minimum=0),
                "reproducible_control_count": _integer(minimum=0),
                "resource_suspension_count": _integer(minimum=0),
                "source_case_count": _integer(minimum=0),
                "structural_recurrence_count": _integer(minimum=0),
                "suspend_count": _integer(minimum=0),
            },
            required=(
                "source_case_count",
                "processed_case_count",
                "observed_compatible_count",
                "local_exact_fit_count",
                "structural_recurrence_count",
                "boundary_observed_count",
                "counterfactual_supported_count",
                "reproducible_control_count",
                "multi_causal_count",
                "partial_count",
                "suspend_count",
                "falsified_count",
                "promoted_rule_count",
                "provenance_complete_count",
                "coverage_by_domain",
                "coverage_by_source_profile",
                "resource_suspension_count",
                "open_term_count",
                "promoted_rule_refs",
                "open_term_refs",
            ),
            references=(
                ReferenceSpec(
                    "/promoted_rule_refs/*",
                    ("RuleAtom", "RuleFamily"),
                ),
                ReferenceSpec(
                    "/open_term_refs/*",
                    ("OpenTermRecord",),
                ),
            ),
            semantic_rules=(
                "COUNTERS_CANNOT_IMPLY_COMPLETION_OR_APPROVAL",
                "COUNTERS_MUST_NOT_EXCEED_SOURCE_CASE_COUNT",
            ),
        ),
        _new_definition(
            index=37,
            name="CompletionStateRegistry",
            filename="completion_state_registry.schema.json",
            version="hds-completion-state-registry-v1",
            id_field="completion_registry_id",
            digest_namespace="hds-completion-state-registry",
            properties={
                "approval_ref": _nullable_ref(),
                "coverage_report_ref": _string(),
                "states": _object(
                    properties={
                        "CAUSAL_ASSET_COVERAGE_REPORTED": _enum(
                            ("NOT_ESTABLISHED", "ESTABLISHED")
                        ),
                        "CORPUS_PROCESSING_COMPLETE": _enum(
                            ("NOT_ESTABLISHED", "ESTABLISHED")
                        ),
                        "DISTILLATION_COVERAGE_ACCEPTED": _enum(
                            ("NOT_ESTABLISHED", "OWNER_ACCEPTED")
                        ),
                        "FROZEN_ARTIFACT_COMPLETE": _enum(
                            ("NOT_ESTABLISHED", "ESTABLISHED")
                        ),
                        "PIPELINE_IMPLEMENTATION_COMPLETE": _enum(
                            ("NOT_ESTABLISHED", "ESTABLISHED")
                        ),
                        "PROMOTED_RULESET_AVAILABLE": _enum(
                            ("NOT_ESTABLISHED", "ESTABLISHED")
                        ),
                    },
                    required=(
                        "PIPELINE_IMPLEMENTATION_COMPLETE",
                        "CORPUS_PROCESSING_COMPLETE",
                        "CAUSAL_ASSET_COVERAGE_REPORTED",
                        "PROMOTED_RULESET_AVAILABLE",
                        "DISTILLATION_COVERAGE_ACCEPTED",
                        "FROZEN_ARTIFACT_COMPLETE",
                    ),
                    additional=False,
                ),
            },
            required=(
                "coverage_report_ref",
                "approval_ref",
                "states",
            ),
            references=(
                ReferenceSpec(
                    "/coverage_report_ref",
                    ("CoverageReport",),
                ),
                ReferenceSpec(
                    "/approval_ref",
                    ("ApprovalRecord",),
                    required_resolution=False,
                ),
            ),
            semantic_rules=(
                "COMPLETION_STATES_INDEPENDENT",
                "COVERAGE_ACCEPTED_REQUIRES_TRUSTED_OWNER_APPROVAL",
                "SUSPEND_CASES_DO_NOT_BLOCK_PROCESSING_COUNT_ONLY",
            ),
        ),
        _new_definition(
            index=38,
            name="FrozenArtifactManifest",
            filename="frozen_artifact_manifest.schema.json",
            version="hds-frozen-artifact-manifest-v1",
            id_field="frozen_manifest_id",
            digest_namespace="hds-frozen-artifact-manifest",
            properties={
                "artifact_count": _integer(minimum=1),
                "artifacts": _array(
                    _object(
                        properties={
                            "logical_content_digest": _digest(),
                            "path": _string(
                                pattern=(
                                    r"^(?!/)(?!.*(?:^|/)\.\.(?:/|$))"
                                    r"[^\\]+$"
                                )
                            ),
                            "physical_package_digest": _nullable_string(),
                            "sha256": _digest(SHA256_PATTERN),
                        },
                        required=(
                            "path",
                            "sha256",
                            "logical_content_digest",
                            "physical_package_digest",
                        ),
                        additional=False,
                    ),
                    min_items=1,
                ),
                "input_manifest_digests": _strings(min_items=1),
                "rebuild_count": _integer(minimum=1),
                "rebuilds_byte_identical": _boolean(),
            },
            required=(
                "input_manifest_digests",
                "artifact_count",
                "artifacts",
                "rebuild_count",
                "rebuilds_byte_identical",
            ),
            semantic_rules=(
                "ARTIFACT_COUNT_MATCHES_LIST",
                "PATHS_REPOSITORY_RELATIVE_POSIX",
            ),
        ),
    ]


SCHEMA_DEFINITIONS = _definitions()
SCHEMA_BY_NAME = {item.name: item for item in SCHEMA_DEFINITIONS}
SCHEMA_BY_FILENAME = {item.filename: item for item in SCHEMA_DEFINITIONS}


def build_generated_schema(definition: SchemaDefinition) -> JsonObject:
    """Build one closed Draft 2020-12 schema for a new PH-D02B type."""

    if definition.preserved:
        raise ValueError("D02B_PRESERVED_SCHEMA_NOT_GENERATED")
    return {
        "$id": SCHEMA_ID_BASE + definition.filename,
        "$schema": SCHEMA_DRAFT,
        "additionalProperties": False,
        "properties": {
            key: cast(JsonValue, dict(value))
            for key, value in definition.properties.items()
        },
        "required": list(definition.required_fields),
        "title": "PH-D02B " + definition.name,
        "type": "object",
        "x-hds-digest-field": definition.digest_field,
        "x-hds-primary-id-field": definition.id_field,
        "x-hds-reference-fields": [
            reference.as_json() for reference in definition.references
        ],
        "x-hds-schema-name": definition.name,
        "x-hds-semantic-rules": list(definition.semantic_rules),
    }


def build_schema_contract() -> JsonObject:
    """Build the content-bound thirty-eight-entry schema contract."""

    contract: JsonObject = {
        "authority": {
            "canonical_contract_digest": (
                "hds-canonicalization-contract:"
                "bd37cc6aa0f41021448a83358c9db409b3695cdf88b2eb6ab6eec"
                "0068c137257"
            ),
            "hds_roadmap_digest": (
                "sha256:"
                "64640eff883f417baeb2d70716e1904c1fd765a3d1a5a5eacb8bba"
                "82e3500518"
            ),
            "hds_spec_digest": (
                "sha256:"
                "79bc7169550c94ea8d86d5004989f9d7c1d93fa173e5fad2d4df02"
                "d88fb6fc93"
            ),
            "input_phase_state_digest": (
                "rev3-d02a-phase-state:"
                "ad044d4726bb26c5a097d651704f3e7454a5480173d05711ab21a70"
                "d5f137890"
            ),
            "work_block_frame_digest": (
                "rev3-work-block-frame:"
                "fcc339cd5867f698b76c420df7b701a572a2b3f18250701c381fa0b"
                "35979d071"
            ),
        },
        "contract_id": SCHEMA_CONTRACT_ID,
        "digest_excluded_fields": [
            "content_digest",
            "contract_id",
        ],
        "gates": ["DG-00", "DG-01", "DG-02", "DG-14"],
        "hds_state_axes": {
            axis: list(values) for axis, values in sorted(HDS_STATE_AXES.items())
        },
        "inventory_count": 38,
        "phase_boundaries": {
            "bridge_started": False,
            "candidate_generation_started": False,
            "golden_freeze_started": False,
            "interpreter_started": False,
            "kaggle_mutation_count": 0,
            "locked_final_access_count": 0,
            "official_access_count": 0,
            "ph_d02c_typed_causal_ir_started": False,
            "real_trajectory_normalization_count": 0,
            "rule_promotion_count": 0,
            "runtime_started": False,
        },
        "phase_id": "PH-D02B",
        "references": {
            "duplicate_id": "FAIL_CLOSED",
            "dangling_id": "FAIL_CLOSED",
            "unknown_schema": "FAIL_CLOSED",
            "wrong_target_schema": "FAIL_CLOSED",
        },
        "schema_entries": [
            definition.as_contract_entry() for definition in SCHEMA_DEFINITIONS
        ],
        "schema_version": SCHEMA_CONTRACT_VERSION,
        "semantic_invariants": [
            "RAW_DERIVATION_INTERPRETATION_SEPARATED",
            "SEVEN_HDS_STATE_AXES_INDEPENDENT",
            "MULTI_CAUSAL_AND_SUSPEND_NO_SINGLE_CHOICE_REQUIREMENT",
            "INITIAL_RULEATOM_PROPOSED_OR_PROBATION_ONLY",
            "OWNER_RECORDED_APPROVAL_REQUIRES_TRUSTED_EXTERNAL_DIGEST",
            "COVERAGE_DOES_NOT_IMPLY_COMPLETION_ACCEPTANCE",
            "NO_PHASE_D02C_EXECUTION_OR_PROMOTION",
        ],
        "supported_json_schema_keywords": [
            "$defs",
            "$id",
            "$ref",
            "$schema",
            "additionalProperties",
            "const",
            "enum",
            "format",
            "items",
            "maxItems",
            "maximum",
            "minItems",
            "minLength",
            "minimum",
            "oneOf",
            "pattern",
            "properties",
            "required",
            "title",
            "type",
            "uniqueItems",
            "x-hds-digest-field",
            "x-hds-primary-id-field",
            "x-hds-reference-fields",
            "x-hds-schema-name",
            "x-hds-semantic-rules",
        ],
    }
    policy = DigestExclusionPolicy(
        id_fields=frozenset({"contract_id"}),
        digest_fields=frozenset({"content_digest"}),
    )
    contract["content_digest"] = logical_content_digest(
        "hds-schema-contract",
        contract,
        policy=policy,
    )
    return contract


def _pointer(path: Sequence[str]) -> str:
    if not path:
        return ""
    return "/" + "/".join(part.replace("~", "~0").replace("/", "~1") for part in path)


def _as_object(value: object, code: str, path: str = "") -> JsonObject:
    if not isinstance(value, dict):
        _raise(code, path)
    if not all(isinstance(key, str) for key in value):
        _raise(code, path)
    return cast(JsonObject, value)


def _read_json_object(path: Path, code: str) -> JsonObject:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SchemaValidationError(code, path.as_posix()) from exc
    return _as_object(value, code, path.as_posix())


def _schema_mapping(
    value: object,
    code: str,
    path: Sequence[str],
) -> Mapping[str, JsonValue]:
    if not isinstance(value, dict):
        _raise(code, _pointer(path))
    return cast(Mapping[str, JsonValue], value)


def _json_equal(left: object, right: object) -> bool:
    try:
        return canonical_json_bytes(left) == canonical_json_bytes(right)
    except (TypeError, ValueError):
        return False


def _schema_type_matches(value: object, expected: str) -> bool:
    if expected == "null":
        return value is None
    if expected == "boolean":
        return type(value) is bool
    if expected == "integer":
        return type(value) is int
    if expected == "number":
        return type(value) in {int, float} and math.isfinite(cast(float, value))
    if expected == "string":
        return isinstance(value, str)
    if expected == "array":
        return isinstance(value, list)
    if expected == "object":
        return isinstance(value, dict)
    _raise("D02B_SCHEMA_UNSUPPORTED_TYPE", expected)


_RFC3339_PATTERN = re.compile(
    r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}"
    r"(?:\.\d+)?(?:Z|[+-]\d{2}:\d{2})$"
)


def _validate_datetime(value: str, path: Sequence[str]) -> None:
    if _RFC3339_PATTERN.fullmatch(value) is None:
        _raise("D02B_SCHEMA_DATETIME", _pointer(path))
    try:
        parsed = datetime.fromisoformat(
            value.removesuffix("Z") + ("+00:00" if value.endswith("Z") else "")
        )
    except ValueError as exc:
        raise SchemaValidationError(
            "D02B_SCHEMA_DATETIME",
            _pointer(path),
        ) from exc
    if parsed.utcoffset() is None:
        _raise("D02B_SCHEMA_DATETIME", _pointer(path))


def _resolve_local_schema_ref(
    root_schema: Mapping[str, JsonValue],
    reference: str,
    path: Sequence[str],
) -> Mapping[str, JsonValue]:
    prefix = "#/$defs/"
    if not reference.startswith(prefix):
        _raise("D02B_SCHEMA_EXTERNAL_REF_FORBIDDEN", _pointer(path))
    name = reference.removeprefix(prefix)
    definitions = _schema_mapping(
        root_schema.get("$defs"),
        "D02B_SCHEMA_DEFS_REQUIRED",
        path,
    )
    if name not in definitions:
        _raise("D02B_SCHEMA_REF_UNKNOWN", _pointer(path))
    return _schema_mapping(
        definitions[name],
        "D02B_SCHEMA_REF_NOT_OBJECT",
        path,
    )


def validate_json_schema_instance(
    instance: object,
    schema: Mapping[str, JsonValue],
    *,
    root_schema: Mapping[str, JsonValue] | None = None,
    path: Sequence[str] = (),
) -> None:
    """Validate the dependency-free JSON Schema subset used by PH-D02B."""

    root = schema if root_schema is None else root_schema
    reference = schema.get("$ref")
    if reference is not None:
        if not isinstance(reference, str):
            _raise("D02B_SCHEMA_REF_STRING_REQUIRED", _pointer(path))
        validate_json_schema_instance(
            instance,
            _resolve_local_schema_ref(root, reference, path),
            root_schema=root,
            path=path,
        )
        return

    variants = schema.get("oneOf")
    if variants is not None:
        if not isinstance(variants, list):
            _raise("D02B_SCHEMA_ONE_OF_ARRAY_REQUIRED", _pointer(path))
        matches = 0
        for variant in variants:
            try:
                validate_json_schema_instance(
                    instance,
                    _schema_mapping(
                        variant,
                        "D02B_SCHEMA_ONE_OF_OBJECT_REQUIRED",
                        path,
                    ),
                    root_schema=root,
                    path=path,
                )
            except SchemaValidationError:
                continue
            matches += 1
        if matches != 1:
            _raise("D02B_SCHEMA_ONE_OF", _pointer(path))

    expected_type = schema.get("type")
    if expected_type is not None:
        if isinstance(expected_type, str):
            expected_types = [expected_type]
        elif isinstance(expected_type, list) and all(
            isinstance(item, str) for item in expected_type
        ):
            expected_types = cast(list[str], expected_type)
        else:
            _raise("D02B_SCHEMA_TYPE_DECLARATION", _pointer(path))
        if not any(_schema_type_matches(instance, item) for item in expected_types):
            _raise("D02B_SCHEMA_TYPE", _pointer(path))

    if "const" in schema and not _json_equal(instance, schema["const"]):
        _raise("D02B_SCHEMA_CONST", _pointer(path))

    enum = schema.get("enum")
    if enum is not None:
        if not isinstance(enum, list):
            _raise("D02B_SCHEMA_ENUM_DECLARATION", _pointer(path))
        if not any(_json_equal(instance, item) for item in enum):
            _raise("D02B_SCHEMA_ENUM", _pointer(path))

    if isinstance(instance, str):
        minimum_length = schema.get("minLength")
        if minimum_length is not None:
            if type(minimum_length) is not int:
                _raise(
                    "D02B_SCHEMA_MIN_LENGTH_DECLARATION",
                    _pointer(path),
                )
            if len(instance) < minimum_length:
                _raise("D02B_SCHEMA_MIN_LENGTH", _pointer(path))
        pattern = schema.get("pattern")
        if pattern is not None:
            if not isinstance(pattern, str):
                _raise(
                    "D02B_SCHEMA_PATTERN_DECLARATION",
                    _pointer(path),
                )
            try:
                matched = re.search(pattern, instance)
            except re.error as exc:
                raise SchemaValidationError(
                    "D02B_SCHEMA_PATTERN_INVALID",
                    _pointer(path),
                ) from exc
            if matched is None:
                _raise("D02B_SCHEMA_PATTERN", _pointer(path))
        if schema.get("format") == "date-time":
            _validate_datetime(instance, path)

    if type(instance) in {int, float}:
        numeric = cast(int | float, instance)
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if minimum is not None and numeric < cast(int | float, minimum):
            _raise("D02B_SCHEMA_MINIMUM", _pointer(path))
        if maximum is not None and numeric > cast(int | float, maximum):
            _raise("D02B_SCHEMA_MAXIMUM", _pointer(path))

    if isinstance(instance, list):
        minimum_items = schema.get("minItems")
        maximum_items = schema.get("maxItems")
        if minimum_items is not None and len(instance) < cast(
            int,
            minimum_items,
        ):
            _raise("D02B_SCHEMA_MIN_ITEMS", _pointer(path))
        if maximum_items is not None and len(instance) > cast(
            int,
            maximum_items,
        ):
            _raise("D02B_SCHEMA_MAX_ITEMS", _pointer(path))
        if schema.get("uniqueItems") is True:
            keys = [canonical_json_bytes(item) for item in instance]
            if len(keys) != len(set(keys)):
                _raise("D02B_SCHEMA_UNIQUE_ITEMS", _pointer(path))
        items = schema.get("items")
        if items is not None:
            item_schema = _schema_mapping(
                items,
                "D02B_SCHEMA_ITEMS_OBJECT_REQUIRED",
                path,
            )
            for index, item in enumerate(instance):
                validate_json_schema_instance(
                    item,
                    item_schema,
                    root_schema=root,
                    path=(*path, str(index)),
                )

    if isinstance(instance, dict):
        required = schema.get("required", [])
        if not isinstance(required, list) or not all(
            isinstance(item, str) for item in required
        ):
            _raise("D02B_SCHEMA_REQUIRED_DECLARATION", _pointer(path))
        for field in cast(list[str], required):
            if field not in instance:
                _raise(
                    "D02B_SCHEMA_REQUIRED",
                    _pointer((*path, field)),
                )
        properties_value = schema.get("properties", {})
        properties = _schema_mapping(
            properties_value,
            "D02B_SCHEMA_PROPERTIES_OBJECT_REQUIRED",
            path,
        )
        additional = schema.get("additionalProperties", True)
        for field, value in instance.items():
            if field in properties:
                validate_json_schema_instance(
                    value,
                    _schema_mapping(
                        properties[field],
                        "D02B_SCHEMA_PROPERTY_OBJECT_REQUIRED",
                        (*path, field),
                    ),
                    root_schema=root,
                    path=(*path, field),
                )
                continue
            if additional is False:
                _raise(
                    "D02B_SCHEMA_UNKNOWN_PROPERTY",
                    _pointer((*path, field)),
                )
            if isinstance(additional, dict):
                validate_json_schema_instance(
                    value,
                    cast(Mapping[str, JsonValue], additional),
                    root_schema=root,
                    path=(*path, field),
                )


def _legacy_content_digest(
    definition: SchemaDefinition,
    instance: Mapping[str, JsonValue],
) -> str:
    body = {
        key: value for key, value in instance.items() if key != definition.digest_field
    }
    return (
        definition.digest_namespace
        + ":"
        + hashlib.sha256(canonical_json_bytes(body)).hexdigest()
    )


def _stable_schema_json_bytes(value: Mapping[str, JsonValue]) -> bytes:
    """Serialize a schema without interpreting field-name constraint keys.

    The PH-D02A value codec validates every ``confidence_ppm`` key as an
    instance value.  A JSON Schema necessarily stores a schema object below
    that property name, so schema documents use the same deterministic JSON
    surface encoding without applying instance-value semantics.
    """

    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _verify_stable_schema_json_bytes(payload: bytes) -> JsonObject:
    try:
        decoded = json.loads(payload)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SchemaValidationError("D02B_SCHEMA_JSON_INVALID") from exc
    document = _as_object(decoded, "D02B_SCHEMA_NOT_OBJECT")
    if _stable_schema_json_bytes(document) != payload:
        _raise("D02B_SCHEMA_JSON_NOT_DETERMINISTIC")
    return document


def _finalize_new_instance(
    schema_name: str,
    body: Mapping[str, JsonValue],
) -> JsonObject:
    definition = SCHEMA_BY_NAME[schema_name]
    if definition.preserved:
        raise ValueError("D02B_NEW_INSTANCE_REQUIRED")
    instance = copy.deepcopy(dict(body))
    instance["schema_version"] = definition.schema_version
    instance["digest_excluded_fields"] = list(definition.digest_excluded_fields)
    instance.pop(definition.id_field, None)
    instance.pop(definition.digest_field, None)
    instance[definition.id_field] = content_derived_id(
        definition.id_namespace,
        instance,
        policy=definition._digest_policy,
    )
    instance[definition.digest_field] = logical_content_digest(
        definition.digest_namespace,
        instance,
        policy=definition._digest_policy,
    )
    return instance


def _refinalize_new_instance(
    schema_name: str,
    instance: Mapping[str, JsonValue],
) -> JsonObject:
    return _finalize_new_instance(schema_name, instance)


def build_schema_payloads(schema_root: Path) -> dict[str, bytes]:
    """Return exact bytes for all schemas, preserving prior phase files."""

    payloads: dict[str, bytes] = {}
    for definition in SCHEMA_DEFINITIONS:
        if definition.preserved:
            path = schema_root / definition.filename
            try:
                payload = path.read_bytes()
            except OSError as exc:
                raise SchemaValidationError(
                    "D02B_PRESERVED_SCHEMA_UNREADABLE",
                    path.as_posix(),
                ) from exc
            actual = hashlib.sha256(payload).hexdigest()
            if actual != definition.preserved_sha256:
                _raise(
                    "D02B_PRESERVED_SCHEMA_SHA256_MISMATCH",
                    definition.filename,
                )
            _as_object(
                json.loads(payload),
                "D02B_PRESERVED_SCHEMA_NOT_OBJECT",
                definition.filename,
            )
        else:
            payload = _stable_schema_json_bytes(build_generated_schema(definition))
            _verify_stable_schema_json_bytes(payload)
        payloads[definition.filename] = payload
    return payloads


def load_schema_documents(
    schema_root: Path,
    contract: Mapping[str, JsonValue] | None = None,
) -> dict[str, JsonObject]:
    """Load and bind the exact 38-file schema inventory."""

    expected_contract = build_schema_contract()
    actual_contract = expected_contract if contract is None else dict(contract)
    if not _json_equal(actual_contract, expected_contract):
        _raise("D02B_SCHEMA_CONTRACT_MISMATCH")
    expected_files = {definition.filename for definition in SCHEMA_DEFINITIONS}
    actual_files = {path.name for path in schema_root.glob("*.schema.json")}
    if actual_files != expected_files:
        missing = sorted(expected_files - actual_files)
        extra = sorted(actual_files - expected_files)
        _raise(
            "D02B_SCHEMA_INVENTORY_MISMATCH",
            f"missing={missing};extra={extra}",
        )
    documents: dict[str, JsonObject] = {}
    for definition in SCHEMA_DEFINITIONS:
        path = schema_root / definition.filename
        try:
            payload = path.read_bytes()
        except OSError as exc:
            raise SchemaValidationError(
                "D02B_SCHEMA_UNREADABLE",
                path.as_posix(),
            ) from exc
        if definition.preserved:
            if hashlib.sha256(payload).hexdigest() != (definition.preserved_sha256):
                _raise(
                    "D02B_PRESERVED_SCHEMA_SHA256_MISMATCH",
                    definition.filename,
                )
        else:
            _verify_stable_schema_json_bytes(payload)
            if payload != _stable_schema_json_bytes(build_generated_schema(definition)):
                _raise(
                    "D02B_GENERATED_SCHEMA_CONTRACT_MISMATCH",
                    definition.filename,
                )
        try:
            decoded = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SchemaValidationError(
                "D02B_SCHEMA_JSON_INVALID",
                definition.filename,
            ) from exc
        document = _as_object(
            decoded,
            "D02B_SCHEMA_NOT_OBJECT",
            definition.filename,
        )
        if document.get("$id") != SCHEMA_ID_BASE + definition.filename:
            _raise("D02B_SCHEMA_ID_MISMATCH", definition.filename)
        if document.get("$schema") != SCHEMA_DRAFT:
            _raise("D02B_SCHEMA_DRAFT_MISMATCH", definition.filename)
        documents[definition.name] = document
    return documents


def _pointer_values(
    instance: Mapping[str, JsonValue],
    pointer: str,
) -> list[JsonValue]:
    if not pointer.startswith("/"):
        _raise("D02B_REFERENCE_POINTER_INVALID", pointer)
    segments = pointer[1:].split("/")
    current: list[JsonValue] = [cast(JsonValue, dict(instance))]
    for segment in segments:
        decoded = segment.replace("~1", "/").replace("~0", "~")
        following: list[JsonValue] = []
        for value in current:
            if decoded == "*":
                if not isinstance(value, list):
                    _raise("D02B_REFERENCE_POINTER_ARRAY_REQUIRED", pointer)
                following.extend(value)
            else:
                if not isinstance(value, dict) or decoded not in value:
                    _raise("D02B_REFERENCE_POINTER_MISSING", pointer)
                following.append(value[decoded])
        current = following
    return current


def _first_forbidden_nested_key(
    value: JsonValue,
    forbidden_keys: frozenset[str],
    *,
    forbidden_prefixes: tuple[str, ...] = (),
    path: tuple[str, ...] = (),
) -> str | None:
    if isinstance(value, dict):
        for key, item in value.items():
            if key in forbidden_keys or key.startswith(forbidden_prefixes):
                return _pointer((*path, key))
            nested = _first_forbidden_nested_key(
                item,
                forbidden_keys,
                forbidden_prefixes=forbidden_prefixes,
                path=(*path, key),
            )
            if nested is not None:
                return nested
    elif isinstance(value, list):
        for index, item in enumerate(value):
            nested = _first_forbidden_nested_key(
                item,
                forbidden_keys,
                forbidden_prefixes=forbidden_prefixes,
                path=(*path, str(index)),
            )
            if nested is not None:
                return nested
    return None


@dataclass(frozen=True, slots=True)
class ValidatedRecord:
    """One schema-bound record after structural and identity validation."""

    schema_name: str
    instance: JsonObject
    primary_id: str
    content_digest: str


class SchemaRegistry:
    """Fail-closed structural, identity, reference, and semantic validator."""

    def __init__(
        self,
        documents: Mapping[str, Mapping[str, JsonValue]],
        contract: Mapping[str, JsonValue],
    ) -> None:
        expected_names = set(SCHEMA_BY_NAME)
        if set(documents) != expected_names:
            _raise("D02B_REGISTRY_SCHEMA_SET_MISMATCH")
        if not _json_equal(contract, build_schema_contract()):
            _raise("D02B_SCHEMA_CONTRACT_MISMATCH")
        for definition in SCHEMA_DEFINITIONS:
            if definition.preserved:
                continue
            if _stable_schema_json_bytes(
                documents[definition.name]
            ) != _stable_schema_json_bytes(build_generated_schema(definition)):
                _raise(
                    "D02B_GENERATED_SCHEMA_CONTRACT_MISMATCH",
                    definition.filename,
                )
        self._documents = {name: dict(document) for name, document in documents.items()}
        self._contract = dict(contract)

    @classmethod
    def from_directory(
        cls,
        schema_root: Path,
        contract_path: Path,
    ) -> SchemaRegistry:
        contract = _read_json_object(
            contract_path,
            "D02B_SCHEMA_CONTRACT_UNREADABLE",
        )
        documents = load_schema_documents(schema_root, contract)
        return cls(documents, contract)

    @property
    def schema_names(self) -> tuple[str, ...]:
        return tuple(item.name for item in SCHEMA_DEFINITIONS)

    def validate_instance(
        self,
        schema_name: str,
        instance: Mapping[str, JsonValue],
    ) -> ValidatedRecord:
        if schema_name not in SCHEMA_BY_NAME:
            _raise("D02B_UNKNOWN_SCHEMA", schema_name)
        definition = SCHEMA_BY_NAME[schema_name]
        document = self._documents[schema_name]
        copied = copy.deepcopy(dict(instance))
        validate_json_schema_instance(copied, document)
        primary_id = copied.get(definition.id_field)
        content_digest = copied.get(definition.digest_field)
        if not isinstance(primary_id, str):
            _raise("D02B_PRIMARY_ID_STRING_REQUIRED", definition.id_field)
        if not isinstance(content_digest, str):
            _raise(
                "D02B_CONTENT_DIGEST_STRING_REQUIRED",
                definition.digest_field,
            )
        if definition.preserved:
            expected_digest = _legacy_content_digest(
                definition,
                copied,
            )
        else:
            expected_id = content_derived_id(
                definition.id_namespace,
                copied,
                policy=definition._digest_policy,
            )
            if primary_id != expected_id:
                _raise("D02B_CONTENT_ID_MISMATCH", definition.id_field)
            expected_digest = logical_content_digest(
                definition.digest_namespace,
                copied,
                policy=definition._digest_policy,
            )
        if content_digest != expected_digest:
            _raise(
                "D02B_CONTENT_DIGEST_MISMATCH",
                definition.digest_field,
            )
        return ValidatedRecord(
            schema_name=schema_name,
            instance=copied,
            primary_id=primary_id,
            content_digest=content_digest,
        )

    def validate_bundle(
        self,
        envelopes: Sequence[Mapping[str, JsonValue]],
        *,
        trusted_owner_approval_digests: frozenset[str] = frozenset(),
    ) -> tuple[ValidatedRecord, ...]:
        records: list[ValidatedRecord] = []
        for index, envelope in enumerate(envelopes):
            if set(envelope) != {"schema_name", "instance"}:
                _raise(
                    "D02B_ENVELOPE_FIELDS",
                    _pointer((str(index),)),
                )
            schema_name = envelope.get("schema_name")
            instance = envelope.get("instance")
            if not isinstance(schema_name, str):
                _raise(
                    "D02B_ENVELOPE_SCHEMA_NAME",
                    _pointer((str(index), "schema_name")),
                )
            record_instance = _as_object(
                instance,
                "D02B_ENVELOPE_INSTANCE",
                _pointer((str(index), "instance")),
            )
            records.append(self.validate_instance(schema_name, record_instance))

        by_id: dict[str, ValidatedRecord] = {}
        by_digest: dict[str, ValidatedRecord] = {}
        for record in records:
            if record.primary_id in by_id:
                _raise("D02B_DUPLICATE_PRIMARY_ID", record.primary_id)
            if record.content_digest in by_digest:
                _raise(
                    "D02B_DUPLICATE_CONTENT_DIGEST",
                    record.content_digest,
                )
            by_id[record.primary_id] = record
            by_digest[record.content_digest] = record

        for record in records:
            definition = SCHEMA_BY_NAME[record.schema_name]
            for reference in definition.references:
                target_index = (
                    by_digest if reference.reference_kind == "DIGEST" else by_id
                )
                other_index = (
                    by_id if reference.reference_kind == "DIGEST" else by_digest
                )
                for value in _pointer_values(
                    record.instance,
                    reference.pointer,
                ):
                    if value is None and not reference.required_resolution:
                        continue
                    if not isinstance(value, str):
                        _raise(
                            "D02B_REFERENCE_STRING_REQUIRED",
                            reference.pointer,
                        )
                    target = target_index.get(value)
                    if target is None:
                        if value in other_index:
                            _raise(
                                "D02B_REFERENCE_KIND_MISMATCH",
                                reference.pointer,
                            )
                        _raise(
                            "D02B_DANGLING_REFERENCE",
                            reference.pointer,
                        )
                    if target.schema_name not in reference.targets:
                        _raise(
                            "D02B_WRONG_REFERENCE_TARGET",
                            reference.pointer,
                        )

        self._validate_semantics(
            records,
            by_id=by_id,
            trusted_owner_approval_digests=(trusted_owner_approval_digests),
        )
        return tuple(records)

    def _validate_semantics(
        self,
        records: Sequence[ValidatedRecord],
        *,
        by_id: Mapping[str, ValidatedRecord],
        trusted_owner_approval_digests: frozenset[str],
    ) -> None:
        for record in records:
            instance = record.instance
            if record.schema_name == "RawObservation":
                contaminated_path = _first_forbidden_nested_key(
                    instance["raw_value"],
                    RAW_INFERENCE_KEYS,
                    forbidden_prefixes=(
                        "hypothesized_",
                        "inferred_",
                        "interpreted_",
                    ),
                )
                if contaminated_path is not None:
                    _raise(
                        "D02B_RAW_INFERENCE_CONTAMINATION",
                        contaminated_path,
                    )

            if record.schema_name == "DeterministicDerivation":
                for field in ("configuration", "output"):
                    semantic_path = _first_forbidden_nested_key(
                        instance[field],
                        DERIVATION_SEMANTIC_KEYS,
                        path=(field,),
                    )
                    if semantic_path is not None:
                        _raise(
                            "D02B_DERIVATION_SEMANTIC_LABEL",
                            semantic_path,
                        )

            identity_fields_by_schema = {
                "HypothesisIR": (
                    "selector_graph",
                    "preconditions",
                    "operator_graph",
                    "ordering_constraints",
                    "stop_conditions",
                    "predicted_effects",
                    "invariants",
                    "exclusions",
                    "falsification_procedures",
                ),
                "ModelRecord": (
                    "assumptions",
                    "expected_observations",
                    "falsification_procedure",
                    "valid_scope",
                ),
                "RuleAtom": (
                    "trigger",
                    "preconditions",
                    "effect",
                    "invariants",
                    "exclusions",
                    "valid_scope",
                    "closure_boundary",
                ),
                "RuleFamily": (
                    "unification_constraints",
                    "valid_scope",
                ),
            }
            for field in identity_fields_by_schema.get(
                record.schema_name,
                (),
            ):
                routing_path = _first_forbidden_nested_key(
                    instance[field],
                    IDENTITY_ROUTING_KEYS,
                    path=(field,),
                )
                if routing_path is not None:
                    _raise(
                        "D02B_IDENTITY_ROUTING_FORBIDDEN",
                        routing_path,
                    )

            if record.schema_name == "EvidenceRecord":
                evidence_ref = cast(str, instance["evidence_ref"])
                target_name = by_id[evidence_ref].schema_name
                expected_origin = {
                    "RawObservation": "RAW_OBSERVATION",
                    "DeterministicDerivation": ("DETERMINISTIC_DERIVATION"),
                }[target_name]
                if instance["evidence_origin"] != expected_origin:
                    _raise("D02B_EVIDENCE_ORIGIN_MISMATCH")

            if record.schema_name == "ARC3ActionRecord":
                if instance["action_id"] not in cast(
                    list[JsonValue],
                    instance["available_actions_before"],
                ):
                    _raise("D02B_ACTION_NOT_AVAILABLE")

            if record.schema_name == "ARC3TeacherTrajectory":
                raw_digest = cast(
                    str,
                    instance["raw_trajectory_digest"],
                )
                canonical_digest = cast(
                    str,
                    instance["canonical_trajectory_digest"],
                )
                if (
                    raw_digest.rsplit(":", 1)[-1]
                    == canonical_digest.rsplit(
                        ":",
                        1,
                    )[-1]
                ):
                    _raise("D02B_TRAJECTORY_DIGEST_DOMAIN_COLLISION")

            if record.schema_name == "DecisionRecord":
                selected = cast(list[JsonValue], instance["selected_model_refs"])
                held = cast(list[JsonValue], instance["held_model_refs"])
                rejected = cast(list[JsonValue], instance["rejected_model_refs"])
                selected_set = set(cast(list[str], selected))
                held_set = set(cast(list[str], held))
                rejected_set = set(cast(list[str], rejected))
                if (
                    selected_set & held_set
                    or selected_set & rejected_set
                    or held_set & rejected_set
                ):
                    _raise("D02B_DECISION_MODEL_SETS_OVERLAP")
                mode = instance["decision_mode"]
                if mode == "SINGLE" and len(selected_set) != 1:
                    _raise("D02B_SINGLE_DECISION_REQUIRES_ONE_MODEL")
                if mode in {"MULTI_CAUSAL", "SUSPEND"} and len(selected_set) == 1:
                    _raise("D02B_NON_SINGLE_DECISION_FORBIDS_SINGLE_MODEL")

            if record.schema_name == "RuleFamily":
                family_domain = instance["domain"]
                for rule_ref in cast(
                    list[str],
                    instance["rule_atom_refs"],
                ):
                    if by_id[rule_ref].instance["domain"] != family_domain:
                        _raise("D02B_RULE_FAMILY_CROSS_DOMAIN")

            if (
                record.schema_name == "ClaimRecord"
                and instance["assertion_state"] == "ASSERT"
            ):
                evidence_refs = cast(
                    list[str],
                    instance["evidence_refs"],
                )
                if not evidence_refs:
                    _raise("D02B_ASSERTED_CLAIM_REQUIRES_EVIDENCE")
                for evidence_ref in evidence_refs:
                    evidence_record = by_id[evidence_ref]
                    if evidence_record.schema_name == "EvidenceRecord":
                        if evidence_record.instance["evidence_state"] in {
                            "FALSIFIED",
                            "INCONCLUSIVE",
                            "UNOBSERVED_EXTRAPOLATION",
                        }:
                            _raise("D02B_ASSERTED_CLAIM_EXCEEDS_EVIDENCE")
                    elif evidence_record.instance[
                        "result"
                    ] != "PASS" or evidence_record.instance["evidence_state"] in {
                        "FALSIFIED",
                        "INCONCLUSIVE",
                        "UNOBSERVED_EXTRAPOLATION",
                    }:
                        _raise("D02B_ASSERTED_CLAIM_EXCEEDS_EVIDENCE")

            if record.schema_name == "ApprovalRecord":
                self._validate_approval(
                    record,
                    trusted_owner_approval_digests,
                )

            if record.schema_name == "PromotionDecision":
                self._validate_promotion(
                    record,
                    by_id,
                    trusted_owner_approval_digests,
                )

            if record.schema_name == "CoverageReport":
                source_count = cast(int, instance["source_case_count"])
                count_fields = (
                    "processed_case_count",
                    "observed_compatible_count",
                    "local_exact_fit_count",
                    "structural_recurrence_count",
                    "boundary_observed_count",
                    "counterfactual_supported_count",
                    "reproducible_control_count",
                    "multi_causal_count",
                    "partial_count",
                    "suspend_count",
                    "falsified_count",
                    "provenance_complete_count",
                    "resource_suspension_count",
                )
                if any(
                    cast(int, instance[field]) > source_count for field in count_fields
                ):
                    _raise("D02B_COVERAGE_COUNT_EXCEEDS_SOURCE")
                if instance["promoted_rule_count"] != len(
                    cast(list[JsonValue], instance["promoted_rule_refs"])
                ):
                    _raise("D02B_PROMOTED_RULE_COUNT_MISMATCH")
                if instance["open_term_count"] != len(
                    cast(list[JsonValue], instance["open_term_refs"])
                ):
                    _raise("D02B_OPEN_TERM_COUNT_MISMATCH")

            if record.schema_name == "CompletionStateRegistry":
                states = cast(JsonObject, instance["states"])
                if states["DISTILLATION_COVERAGE_ACCEPTED"] == "OWNER_ACCEPTED":
                    approval_ref = instance["approval_ref"]
                    if not isinstance(approval_ref, str):
                        _raise("D02B_COMPLETION_ACCEPTANCE_REQUIRES_APPROVAL")
                    approval = by_id[approval_ref]
                    if approval.content_digest not in (trusted_owner_approval_digests):
                        _raise("D02B_COMPLETION_APPROVAL_NOT_TRUSTED")
                    if approval.instance["decision"] != "APPROVE":
                        _raise("D02B_COMPLETION_APPROVAL_NOT_APPROVE")
                    coverage = by_id[cast(str, instance["coverage_report_ref"])]
                    if (
                        approval.instance["target_artifact_digest"]
                        != coverage.content_digest
                    ):
                        _raise("D02B_COMPLETION_APPROVAL_TARGET_MISMATCH")
                    if approval.instance["next_state"] != (
                        "DISTILLATION_COVERAGE_ACCEPTED"
                    ):
                        _raise("D02B_COMPLETION_APPROVAL_STATE_MISMATCH")

            if record.schema_name == "DistillationAudit":
                failed = cast(list[JsonValue], instance["failed_check_ids"])
                if instance["finding_count"] != len(failed):
                    _raise("D02B_AUDIT_FINDING_COUNT_MISMATCH")
                expected_status = "PASS" if not failed else "FAIL"
                if instance["status"] != expected_status:
                    _raise("D02B_AUDIT_STATUS_MISMATCH")

            if record.schema_name == "FrozenArtifactManifest":
                artifacts = cast(list[JsonValue], instance["artifacts"])
                if instance["artifact_count"] != len(artifacts):
                    _raise("D02B_ARTIFACT_COUNT_MISMATCH")
                paths = [cast(JsonObject, artifact)["path"] for artifact in artifacts]
                if len(paths) != len(set(cast(list[str], paths))):
                    _raise("D02B_ARTIFACT_PATH_DUPLICATE")

    @staticmethod
    def _validate_approval(
        record: ValidatedRecord,
        trusted_owner_approval_digests: frozenset[str],
    ) -> None:
        instance = record.instance
        if instance["approval_mode"] == "SCHEMA_TEMPLATE":
            if (
                instance["authoritative"] is not False
                or instance["authority"] != "UNBOUND_SCHEMA_TEMPLATE"
                or instance["decision"] != "SUSPEND"
            ):
                _raise("D02B_TEMPLATE_APPROVAL_MUST_BE_NONAUTHORITATIVE")
            if record.content_digest in trusted_owner_approval_digests:
                _raise("D02B_TEMPLATE_APPROVAL_CANNOT_BE_TRUSTED")
            return
        if instance["authoritative"] is not True or instance["authority"] != "OWNER":
            _raise("D02B_OWNER_APPROVAL_AUTHORITY_INVALID")
        if record.content_digest not in trusted_owner_approval_digests:
            _raise("D02B_OWNER_APPROVAL_DIGEST_NOT_TRUSTED")

    @staticmethod
    def _validate_promotion(
        record: ValidatedRecord,
        by_id: Mapping[str, ValidatedRecord],
        trusted_owner_approval_digests: frozenset[str],
    ) -> None:
        instance = record.instance
        if instance["decision"] != "PROMOTE":
            return
        approval_ref = instance["approval_ref"]
        if not isinstance(approval_ref, str):
            _raise("D02B_PROMOTION_REQUIRES_APPROVAL")
        approval = by_id[approval_ref]
        if (
            approval.content_digest not in trusted_owner_approval_digests
            or approval.instance["approval_mode"] != "OWNER_RECORDED"
            or approval.instance["decision"] != "APPROVE"
        ):
            _raise("D02B_PROMOTION_APPROVAL_NOT_TRUSTED")
        target = by_id[cast(str, instance["target_ref"])]
        if approval.instance["target_artifact_digest"] != target.content_digest:
            _raise("D02B_PROMOTION_APPROVAL_TARGET_MISMATCH")
        if approval.instance["previous_state"] != (instance["previous_adoption_state"]):
            _raise("D02B_PROMOTION_APPROVAL_PREVIOUS_STATE_MISMATCH")
        if approval.instance["next_state"] != (instance["proposed_adoption_state"]):
            _raise("D02B_PROMOTION_APPROVAL_NEXT_STATE_MISMATCH")


def _load_preserved_example_records(
    project_root: Path,
) -> dict[str, JsonObject]:
    distillation_root = project_root / "distillation"
    records = {
        "SourceProfile": _read_json_object(
            distillation_root / "profiles/source/arc3-environment-source-bundle.json",
            "D02B_EXAMPLE_SOURCE_PROFILE_UNREADABLE",
        ),
        "SourceContentManifest": _read_json_object(
            distillation_root
            / ("manifests/source_content/arc3-environment-source-bundle.json"),
            "D02B_EXAMPLE_SOURCE_MANIFEST_UNREADABLE",
        ),
        "AcquisitionRecord": _read_json_object(
            distillation_root
            / ("manifests/acquisition/arc3-environment-source-bundle.json"),
            "D02B_EXAMPLE_ACQUISITION_UNREADABLE",
        ),
        "EnvironmentManifest": _read_json_object(
            distillation_root / "manifests/environment/arc3-replay.json",
            "D02B_EXAMPLE_ENVIRONMENT_UNREADABLE",
        ),
    }
    source_profile = records["SourceProfile"]
    source_manifest = records["SourceContentManifest"]
    environment = records["EnvironmentManifest"]
    run: JsonObject = {
        "capture_tool_sha256": "0" * 64,
        "command": ["PH-D02B_SCHEMA_FIXTURE_ONLY"],
        "digest_excluded_fields": ["run_digest"],
        "ended_at": "2000-01-01T00:00:00Z",
        "environment_manifest_digest": environment["content_digest"],
        "exit_code": 0,
        "input_content_digests": [source_manifest["content_digest"]],
        "input_profile_ids": [source_profile["profile_id"]],
        "network_scope": "NONE",
        "purpose": ("Non-executable synthetic PH-D02B schema reference fixture"),
        "run_digest": "",
        "run_id": "ph-d02b-schema-reference-fixture",
        "schema_version": "hds-run-manifest-v1",
        "started_at": "2000-01-01T00:00:00Z",
        "stderr_sha256": "0" * 64,
        "stdout_sha256": "0" * 64,
        "working_directory": "/non-executable/schema-fixture",
    }
    run_definition = SCHEMA_BY_NAME["RunManifest"]
    run["run_digest"] = _legacy_content_digest(run_definition, run)
    records["RunManifest"] = run
    return records


def build_valid_example_envelopes(
    project_root: Path,
) -> list[JsonObject]:
    """Build one mutually resolvable, non-executable example per schema."""

    records = _load_preserved_example_records(project_root)

    def record_id(name: str) -> str:
        definition = SCHEMA_BY_NAME[name]
        value = records[name][definition.id_field]
        if not isinstance(value, str):
            _raise("D02B_EXAMPLE_ID_INVALID", name)
        return value

    def record_digest(name: str) -> str:
        definition = SCHEMA_BY_NAME[name]
        value = records[name][definition.digest_field]
        if not isinstance(value, str):
            _raise("D02B_EXAMPLE_DIGEST_INVALID", name)
        return value

    records["ResourceProfile"] = _finalize_new_instance(
        "ResourceProfile",
        {
            "arc2_intervention_budget": 0,
            "arc3_intervention_budget": 0,
            "candidate_count_budget": 4,
            "candidate_graph_node_limit": 64,
            "interpreter_step_limit": 128,
            "llm_call_budget": 0,
            "memory_limit_mb": 256,
            "per_case_wall_seconds": 30,
            "unification_timeout_ms": 1000,
        },
    )
    records["RawObservation"] = _finalize_new_instance(
        "RawObservation",
        {
            "available_actions": [1],
            "domain": "ARC3",
            "evidence_origin": "DIRECT_OBSERVATION",
            "observed_fields": ["grid"],
            "progress": 0,
            "raw_value": {"grid": [[0]]},
            "source_pointer": "synthetic-schema-fixture/frame/0",
            "terminal": False,
        },
    )
    records["ARC3ActionRecord"] = _finalize_new_instance(
        "ARC3ActionRecord",
        {
            "action_id": 1,
            "action_payload": {"kind": "SCHEMA_FIXTURE_ACTION"},
            "available_actions_before": [1],
            "canonical_frame_after_digest": "fixture-frame:" + "2" * 64,
            "canonical_frame_before_digest": "fixture-frame:" + "1" * 64,
            "progress_delta": 0,
            "step_index": 0,
            "terminal_state_after": "CONTINUE",
            "visible_diff": {},
        },
    )
    records["DependencyLock"] = _finalize_new_instance(
        "DependencyLock",
        {
            "authority_digests": [cast(str, build_schema_contract()["content_digest"])],
            "dependency_digests": ["fixture-dependency:" + "3" * 64],
            "environment_manifest_ref": record_id("EnvironmentManifest"),
            "interpreter_version": "NOT_STARTED_IN_PH_D02B",
            "python_version": "3.12.13",
        },
    )
    records["OperatorRegistry"] = _finalize_new_instance(
        "OperatorRegistry",
        {
            "dependency_lock_ref": record_id("DependencyLock"),
            "domain": "COMMON",
            "entries": [
                {
                    "canonicalization_rule": "HDS_CANONICAL_JSON_V1",
                    "deterministic": True,
                    "domain": "COMMON",
                    "input_types": ["JsonValue"],
                    "invalid_operation_semantics": "FAIL_CLOSED",
                    "opcode": "IDENTITY_FIXTURE",
                    "opcode_version": "1",
                    "output_type": "JsonValue",
                    "parameter_schema": {},
                    "preconditions": [],
                    "resource_cost": 0,
                    "side_effect_free": True,
                    "test_vector_refs": ["schema-fixture-only"],
                }
            ],
            "registry_version": "ph-d02b-schema-only-v1",
        },
    )
    records["ARC2TeacherCase"] = _finalize_new_instance(
        "ARC2TeacherCase",
        {
            "answer_visibility": "ANSWER_VISIBLE",
            "domain": "ARC2",
            "input_grid": [[0]],
            "output_grid": [[0]],
            "raw_observation_refs": [record_id("RawObservation")],
            "source_content_manifest_ref": record_id("SourceContentManifest"),
            "source_profile_ref": record_id("SourceProfile"),
            "split_role": "SYNTHETIC_SCHEMA_FIXTURE",
        },
    )
    records["ARC3TeacherTrajectory"] = _finalize_new_instance(
        "ARC3TeacherTrajectory",
        {
            "action_record_refs": [record_id("ARC3ActionRecord")],
            "canonical_trajectory_digest": ("hds-canonical-trajectory:" + "5" * 64),
            "domain": "ARC3",
            "environment_manifest_ref": record_id("EnvironmentManifest"),
            "level_count": 1,
            "raw_observation_refs": [record_id("RawObservation")],
            "raw_trajectory_digest": ("hds-raw-trajectory:" + "4" * 64),
            "source_profile_ref": record_id("SourceProfile"),
            "terminal_state": "INCOMPLETE",
        },
    )
    records["DeterministicDerivation"] = _finalize_new_instance(
        "DeterministicDerivation",
        {
            "algorithm_id": "fixture-frame-diff",
            "algorithm_version": "1",
            "configuration": {},
            "derivation_origin": "DETERMINISTIC_ALGORITHM",
            "input_evidence_refs": [record_id("RawObservation")],
            "output": {"changed_cells": 0},
            "output_type": "FRAME_DIFF",
        },
    )
    records["InterpretationHypothesis"] = _finalize_new_instance(
        "InterpretationHypothesis",
        {
            "confidence_ppm": 500_000,
            "evidence_refs": [record_id("DeterministicDerivation")],
            "hypothesis_kind": "ACTION_SEMANTICS",
            "statement": "Synthetic schema-only interpretation",
            "status": "HELD",
        },
    )
    records["EvidenceRecord"] = _finalize_new_instance(
        "EvidenceRecord",
        {
            "evidence_origin": "DETERMINISTIC_DERIVATION",
            "evidence_ref": record_id("DeterministicDerivation"),
            "evidence_state": "INCONCLUSIVE",
            "limitations": ["SCHEMA_FIXTURE_ONLY"],
            "provenance": {"synthetic": True},
        },
    )
    records["DistillationFrame"] = _finalize_new_instance(
        "DistillationFrame",
        {
            "Mc": {"memory": "PASSIVE_ONLY"},
            "R_observable": {"source": "SYNTHETIC_FIXTURE"},
            "X": {"domain": "SCHEMA_CONFORMANCE"},
            "authority_boundary": [
                "NO_OWNER_APPROVAL_GENERATED",
                "NO_PHASE_D02C_EXECUTION",
            ],
            "candidate_budget": 4,
            "domain": "ARC3",
            "evidence_boundary": "SYNTHETIC_SCHEMA_ONLY",
            "hds_dependency_digest": "hds-dependency:" + "6" * 64,
            "hypothesis_language_version": "schema-only-v1",
            "intervention_budget": 0,
            "non_goals": ["TRAJECTORY_NORMALIZATION"],
            "purpose": "Validate PH-D02B schema topology",
            "resource_profile_ref": record_id("ResourceProfile"),
            "rollback_conditions": ["SCHEMA_CONFORMANCE_FAILURE"],
            "source_scope_refs": [record_id("SourceProfile")],
            "spec_version": "rev3",
            "stop_conditions": ["SCHEMA_CONTRACT_MISMATCH"],
            "unresolved_term_refs": [],
        },
    )
    records["HypothesisIR"] = _finalize_new_instance(
        "HypothesisIR",
        {
            "domain": "ARC3",
            "exclusions": ["EXECUTION_IN_PH_D02B"],
            "falsification_procedures": [{"kind": "SCHEMA_CHECK"}],
            "frame_ref": record_id("DistillationFrame"),
            "input_types": ["RawObservation"],
            "invariants": [{"kind": "NO_IDENTITY_ROUTING"}],
            "ir_version": "schema-only-v1",
            "operator_graph": [{"opcode": "IDENTITY_FIXTURE"}],
            "operator_registry_ref": record_id("OperatorRegistry"),
            "ordering_constraints": [],
            "preconditions": [],
            "predicted_effects": [{"kind": "NO_EXECUTION"}],
            "resource_cost": 0,
            "selector_graph": [{"selector": "SYNTHETIC"}],
            "stop_conditions": [],
        },
    )
    records["CounterfactualInterventionPlan"] = _finalize_new_instance(
        "CounterfactualInterventionPlan",
        {
            "domain": "ARC3",
            "freeze_state": "PRE_RESULT_FROZEN",
            "hypothesis_ir_ref": record_id("HypothesisIR"),
            "intervention_kind": "SCHEMA_ONLY_NOT_EXECUTABLE",
            "predicted_outcomes": [
                {"branch": "A"},
                {"branch": "B"},
            ],
            "resource_profile_ref": record_id("ResourceProfile"),
            "reversibility": "NOT_EXECUTABLE",
            "safety_constraints": ["NO_ENVIRONMENT_ACTION"],
        },
    )
    records["InterventionResult"] = _finalize_new_instance(
        "InterventionResult",
        {
            "evidence_refs": [record_id("EvidenceRecord")],
            "intervention_plan_ref": record_id("CounterfactualInterventionPlan"),
            "observed_outcome": {"executed": False},
            "operation_state": "HOLD",
            "reason_codes": ["PH_D02B_SCHEMA_ONLY"],
            "result_state": "NOT_EXECUTABLE",
        },
    )
    records["LLMCaptureRecord"] = _finalize_new_instance(
        "LLMCaptureRecord",
        {
            "captured_at": "2000-01-01T00:00:00Z",
            "model": "NO_LIVE_MODEL_SCHEMA_FIXTURE",
            "parameters": {},
            "prompt_digest": "fixture-prompt:" + "7" * 64,
            "raw_response_sha256": "8" * 64,
            "request_digest": "fixture-request:" + "9" * 64,
            "run_manifest_ref": record_id("RunManifest"),
        },
    )
    records["ModelRecord"] = _finalize_new_instance(
        "ModelRecord",
        {
            "assumptions": ["SYNTHETIC_SCHEMA_FIXTURE"],
            "confidence_ppm": 0,
            "contradicting_evidence_refs": [],
            "expected_observations": [],
            "falsification_procedure": {"kind": "SCHEMA_CHECK"},
            "frame_ref": record_id("DistillationFrame"),
            "hypothesis_ir_ref": record_id("HypothesisIR"),
            "model_type": "NULL_MODEL",
            "resource_requirement": {"llm_calls": 0},
            "risks": ["NOT_EMPIRICAL_EVIDENCE"],
            "statement": "No empirical claim; schema fixture only",
            "status": "HELD",
            "supporting_evidence_refs": [record_id("EvidenceRecord")],
            "valid_scope": {"fixture_only": True},
        },
    )
    records["GateResult"] = _finalize_new_instance(
        "GateResult",
        {
            "evidence_refs": [record_id("EvidenceRecord")],
            "evidence_state": "INCONCLUSIVE",
            "frame_ref": record_id("DistillationFrame"),
            "gate_id": "DG-00",
            "mechanism_support_state": "INCONCLUSIVE",
            "model_refs": [record_id("ModelRecord")],
            "reason_codes": ["SCHEMA_FIXTURE_NO_EMPIRICAL_CLAIM"],
            "result": "SUSPEND",
        },
    )
    records["DecisionRecord"] = _finalize_new_instance(
        "DecisionRecord",
        {
            "adoption_state": "PROPOSED",
            "assertion_state": "SUSPEND",
            "closure_state": "OPEN",
            "decision_mode": "SUSPEND",
            "evidence_state": "INCONCLUSIVE",
            "expected_outcome": {"kind": "NONE"},
            "falsification_condition": {"kind": "NOT_APPLICABLE"},
            "frame_ref": record_id("DistillationFrame"),
            "gate_result_refs": [record_id("GateResult")],
            "held_model_refs": [record_id("ModelRecord")],
            "mechanism_support_state": "INCONCLUSIVE",
            "operation_state": "HOLD",
            "reason_codes": ["SCHEMA_FIXTURE_ONLY"],
            "rejected_model_refs": [],
            "rollback_condition": {"kind": "SCHEMA_FAILURE"},
            "selected_model_refs": [],
            "stop_condition": {"kind": "PHASE_BOUNDARY"},
            "update_state": "PROPOSED",
        },
    )
    records["RuleAtom"] = _finalize_new_instance(
        "RuleAtom",
        {
            "adoption_state": "PROPOSED",
            "alternative_adequacy": {"status": "NOT_EVALUATED"},
            "approval_ref": None,
            "closure_boundary": {"status": "OPEN"},
            "counterexample_refs": [],
            "domain": "ARC3",
            "effect": {"kind": "SCHEMA_FIXTURE_EFFECT"},
            "evidence_state": "LOCAL_FIT",
            "exclusions": [],
            "intervention_coverage": {"executed": False},
            "invariants": [],
            "mechanism_support_state": "LOCAL_EXACT_FIT",
            "mechanism_template_ir_ref": record_id("HypothesisIR"),
            "near_miss_case_refs": [],
            "negative_pool_case_refs": [],
            "normalization_certificate_refs": [],
            "preconditions": [],
            "promotion_decision_ref": None,
            "provenance": {"synthetic": True},
            "rule_version": 1,
            "support_case_refs": [record_id("ARC3TeacherTrajectory")],
            "support_selection_method": "SYNTHETIC_SCHEMA_FIXTURE",
            "trigger": {"kind": "SCHEMA_FIXTURE_TRIGGER"},
            "valid_scope": {"fixture_only": True},
        },
    )
    records["RuleFamily"] = _finalize_new_instance(
        "RuleFamily",
        {
            "adoption_state": "PROPOSED",
            "approval_ref": None,
            "domain": "ARC3",
            "family_statement": "Synthetic schema-only rule family",
            "promotion_decision_ref": None,
            "provenance": {"synthetic": True},
            "rule_atom_refs": [record_id("RuleAtom")],
            "unification_constraints": [],
            "valid_scope": {"fixture_only": True},
        },
    )
    records["BoundaryRecord"] = _finalize_new_instance(
        "BoundaryRecord",
        {
            "affected_scope": {"fixture": "inside"},
            "boundary_kind": "SYNTHETIC_FIXTURE_BOUNDARY",
            "evidence_refs": [record_id("EvidenceRecord")],
            "near_miss_case_refs": [record_id("ARC3TeacherTrajectory")],
            "target_ref": record_id("ModelRecord"),
            "unaffected_scope": {"fixture": "outside"},
        },
    )
    records["CounterexampleRecord"] = _finalize_new_instance(
        "CounterexampleRecord",
        {
            "case_ref": record_id("ARC3TeacherTrajectory"),
            "contradiction": {"kind": "SYNTHETIC"},
            "evidence_refs": [record_id("EvidenceRecord")],
            "target_ref": record_id("ModelRecord"),
        },
    )
    records["FailureSignature"] = _finalize_new_instance(
        "FailureSignature",
        {
            "affected_scope": {"fixture_only": True},
            "attempted_hypothesis_ref": record_id("HypothesisIR"),
            "cognition_stage": "SCHEMA_VALIDATION",
            "domain_failure_code": "SYNTHETIC_FIXTURE",
            "evidence_state": "INCONCLUSIVE",
            "hds_failure_class": "NOT_AN_EMPIRICAL_FAILURE",
            "next_probe_axes": [],
            "provenance": {"synthetic": True},
            "public_local_boundary": "LOCAL_SCHEMA_FIXTURE",
            "recurrence_count": 1,
            "recovery": {"kind": "NONE"},
            "regression_risk": "NONE",
            "repair_requirement": "NONE",
            "reusable_check": "SCHEMA_CONFORMANCE",
            "status": "QUARANTINED",
            "structural_cause": "SYNTHETIC_EXAMPLE",
            "surface_symptom": "NONE",
            "target_ref": record_id("ModelRecord"),
            "target_version": "1",
            "trigger": {"kind": "SYNTHETIC"},
            "unaffected_scope": {"all_real_cases": True},
            "violated_assumption": "NONE",
        },
    )
    records["NormalizationCertificate"] = _finalize_new_instance(
        "NormalizationCertificate",
        {
            "canonical_record_digest": "fixture-record:" + "b" * 64,
            "equivalence_evidence_refs": [record_id("EvidenceRecord")],
            "information_loss": "CONDITIONAL",
            "inverse_mapping": {},
            "normalization_class": "GENERALIZATION_CANDIDATE",
            "required_assumptions": ["SCHEMA_FIXTURE_ONLY"],
            "rewrite_rule_ref": None,
            "source_record_digest": "fixture-record:" + "a" * 64,
            "status": "SUSPEND",
            "variable_mapping": {},
        },
    )
    records["PromotionDecision"] = _finalize_new_instance(
        "PromotionDecision",
        {
            "approval_ref": None,
            "decision": "PROPOSE",
            "evidence_refs": [record_id("EvidenceRecord")],
            "gate_result_refs": [record_id("GateResult")],
            "previous_adoption_state": "PROPOSED",
            "proposed_adoption_state": "PROBATION",
            "reason_codes": ["NO_PROMOTION_IN_PH_D02B"],
            "target_ref": record_id("RuleAtom"),
        },
    )
    records["ApprovalRecord"] = _finalize_new_instance(
        "ApprovalRecord",
        {
            "approval_mode": "SCHEMA_TEMPLATE",
            "approved_at": "2000-01-01T00:00:00Z",
            "authority": "UNBOUND_SCHEMA_TEMPLATE",
            "authoritative": False,
            "decision": "SUSPEND",
            "evidence_refs": [],
            "next_state": "UNBOUND",
            "previous_state": "UNBOUND",
            "reason_codes": ["NON_AUTHORITATIVE_SCHEMA_TEMPLATE"],
            "spec_version": "rev3",
            "target_artifact_digest": record_digest("RuleAtom"),
        },
    )
    records["OpenTermRecord"] = _finalize_new_instance(
        "OpenTermRecord",
        {
            "blocking": False,
            "evidence_refs": [record_id("EvidenceRecord")],
            "frame_ref": record_id("DistillationFrame"),
            "information_value": "SCHEMA_FIXTURE_ONLY",
            "question": "No empirical question is answered by this fixture",
            "required_resolution": "OUTSIDE_PH_D02B",
            "status": "OPEN",
            "term": "schema_fixture_empirical_meaning",
        },
    )
    records["ClaimRecord"] = _finalize_new_instance(
        "ClaimRecord",
        {
            "approval_ref": None,
            "assertion_state": "SUSPEND",
            "claim_scope": {"fixture_only": True},
            "claim_text": "This record makes no empirical claim",
            "claim_type": "BOUNDARY_DECLARATION",
            "confidence_ppm": 1_000_000,
            "evidence_refs": [record_id("GateResult")],
            "limitations": ["SCHEMA_CONFORMANCE_ONLY"],
        },
    )
    records["HDSCausalRecord"] = _finalize_new_instance(
        "HDSCausalRecord",
        {
            "adoption_state": "PROPOSED",
            "assertion_state": "SUSPEND",
            "claim_refs": [record_id("ClaimRecord")],
            "closed_within": {
                "candidate_budget": 4,
                "evidence_boundary": "SYNTHETIC_SCHEMA_ONLY",
                "hypothesis_language_version": "schema-only-v1",
                "intervention_set_digest": ("fixture-intervention-set:" + "c" * 64),
                "limitations": ["NOT_EMPIRICAL"],
                "observed_case_set_digest": ("fixture-observed-set:" + "d" * 64),
                "resource_profile_id": record_id("ResourceProfile"),
            },
            "closure_state": "OPEN",
            "decision_ref": record_id("DecisionRecord"),
            "deterministic_derivation_refs": [record_id("DeterministicDerivation")],
            "evidence_state": "INCONCLUSIVE",
            "failure_signature_refs": [record_id("FailureSignature")],
            "frame_ref": record_id("DistillationFrame"),
            "gate_result_refs": [record_id("GateResult")],
            "held_model_refs": [record_id("ModelRecord")],
            "interpretation_hypothesis_refs": [record_id("InterpretationHypothesis")],
            "intervention_result_refs": [record_id("InterventionResult")],
            "mechanism_support_state": "INCONCLUSIVE",
            "model_refs": [record_id("ModelRecord")],
            "open_term_refs": [record_id("OpenTermRecord")],
            "operation_state": "HOLD",
            "raw_observation_refs": [record_id("RawObservation")],
            "record_version": 1,
            "rejected_model_refs": [],
            "selected_model_refs": [],
            "summary": "Non-authoritative synthetic schema fixture",
            "update_proposal_refs": [],
            "update_state": "PROPOSED",
        },
    )
    records["DistillationAudit"] = _finalize_new_instance(
        "DistillationAudit",
        {
            "audited_artifact_digests": [
                cast(str, build_schema_contract()["content_digest"])
            ],
            "causal_record_refs": [record_id("HDSCausalRecord")],
            "failed_check_ids": [],
            "finding_count": 0,
            "gate_result_refs": [record_id("GateResult")],
            "passed_check_ids": [
                "SCHEMA_STRUCTURE",
                "REFERENCE_RESOLUTION",
            ],
            "scope": {"fixture_only": True},
            "status": "PASS",
        },
    )
    records["CoverageReport"] = _finalize_new_instance(
        "CoverageReport",
        {
            "boundary_observed_count": 0,
            "counterfactual_supported_count": 0,
            "coverage_by_domain": {"ARC3": 1},
            "coverage_by_source_profile": {record_id("SourceProfile"): 1},
            "falsified_count": 0,
            "local_exact_fit_count": 0,
            "multi_causal_count": 0,
            "observed_compatible_count": 0,
            "open_term_count": 1,
            "open_term_refs": [record_id("OpenTermRecord")],
            "partial_count": 0,
            "processed_case_count": 1,
            "promoted_rule_count": 0,
            "promoted_rule_refs": [],
            "provenance_complete_count": 1,
            "reproducible_control_count": 0,
            "resource_suspension_count": 0,
            "source_case_count": 1,
            "structural_recurrence_count": 0,
            "suspend_count": 1,
        },
    )
    records["CompletionStateRegistry"] = _finalize_new_instance(
        "CompletionStateRegistry",
        {
            "approval_ref": None,
            "coverage_report_ref": record_id("CoverageReport"),
            "states": {
                "CAUSAL_ASSET_COVERAGE_REPORTED": "NOT_ESTABLISHED",
                "CORPUS_PROCESSING_COMPLETE": "NOT_ESTABLISHED",
                "DISTILLATION_COVERAGE_ACCEPTED": "NOT_ESTABLISHED",
                "FROZEN_ARTIFACT_COMPLETE": "NOT_ESTABLISHED",
                "PIPELINE_IMPLEMENTATION_COMPLETE": "NOT_ESTABLISHED",
                "PROMOTED_RULESET_AVAILABLE": "NOT_ESTABLISHED",
            },
        },
    )
    records["FrozenArtifactManifest"] = _finalize_new_instance(
        "FrozenArtifactManifest",
        {
            "artifact_count": 1,
            "artifacts": [
                {
                    "logical_content_digest": cast(
                        str,
                        build_schema_contract()["content_digest"],
                    ),
                    "path": "distillation/input/schema_contract.json",
                    "physical_package_digest": None,
                    "sha256": "e" * 64,
                }
            ],
            "input_manifest_digests": [record_digest("SourceContentManifest")],
            "rebuild_count": 1,
            "rebuilds_byte_identical": False,
        },
    )

    missing = set(SCHEMA_BY_NAME) - set(records)
    extra = set(records) - set(SCHEMA_BY_NAME)
    if missing or extra:
        _raise(
            "D02B_EXAMPLE_SCHEMA_SET_MISMATCH",
            f"missing={sorted(missing)};extra={sorted(extra)}",
        )
    return [
        {
            "instance": records[definition.name],
            "schema_name": definition.name,
        }
        for definition in SCHEMA_DEFINITIONS
    ]


def _artifact_digest(
    namespace: str,
    artifact: JsonObject,
    *,
    id_field: str,
) -> str:
    policy = DigestExclusionPolicy(
        id_fields=frozenset({id_field}),
        digest_fields=frozenset({"content_digest"}),
    )
    return logical_content_digest(namespace, artifact, policy=policy)


def build_valid_example_set(project_root: Path) -> JsonObject:
    examples = build_valid_example_envelopes(project_root)
    artifact: JsonObject = {
        "artifact_kind": "PH_D02B_VALID_SCHEMA_EXAMPLES",
        "content_digest": "",
        "digest_excluded_fields": [
            "content_digest",
            "example_set_id",
        ],
        "example_count": len(examples),
        "example_set_id": VALID_EXAMPLE_SET_ID,
        "examples": cast(JsonValue, examples),
        "owner_approval_generated": False,
        "phase_boundaries": {
            "ph_d02c_execution_count": 0,
            "real_trajectory_normalization_count": 0,
            "rule_promotion_count": 0,
        },
        "phase_id": "PH-D02B",
        "schema_contract_digest": cast(
            str,
            build_schema_contract()["content_digest"],
        ),
        "schema_version": "hds-valid-schema-examples-v1",
        "synthetic_fixture_only": True,
    }
    artifact["content_digest"] = _artifact_digest(
        "hds-valid-schema-examples",
        artifact,
        id_field="example_set_id",
    )
    return artifact


INVALID_CASES: tuple[tuple[str, str], ...] = (
    ("UNKNOWN_SCHEMA", "D02B_UNKNOWN_SCHEMA"),
    ("UNKNOWN_TOP_LEVEL_PROPERTY", "D02B_SCHEMA_UNKNOWN_PROPERTY"),
    (
        "RAW_INFERENCE_CONTAMINATION",
        "D02B_RAW_INFERENCE_CONTAMINATION",
    ),
    (
        "DERIVATION_SEMANTIC_LABEL",
        "D02B_DERIVATION_SEMANTIC_LABEL",
    ),
    (
        "HYPOTHESIS_IDENTITY_ROUTING",
        "D02B_IDENTITY_ROUTING_FORBIDDEN",
    ),
    ("EVIDENCE_DANGLING_REFERENCE", "D02B_DANGLING_REFERENCE"),
    ("EVIDENCE_WRONG_TARGET", "D02B_WRONG_REFERENCE_TARGET"),
    ("REFERENCE_KIND_MISMATCH", "D02B_REFERENCE_KIND_MISMATCH"),
    ("EVIDENCE_ORIGIN_MISMATCH", "D02B_EVIDENCE_ORIGIN_MISMATCH"),
    ("ACTION_NOT_AVAILABLE", "D02B_ACTION_NOT_AVAILABLE"),
    ("DUPLICATE_PRIMARY_ID", "D02B_DUPLICATE_PRIMARY_ID"),
    (
        "SINGLE_WITHOUT_SELECTION",
        "D02B_SINGLE_DECISION_REQUIRES_ONE_MODEL",
    ),
    (
        "SUSPEND_WITH_SELECTION",
        "D02B_NON_SINGLE_DECISION_FORBIDS_SINGLE_MODEL",
    ),
    (
        "MULTI_CAUSAL_SINGLE_SELECTION",
        "D02B_NON_SINGLE_DECISION_FORBIDS_SINGLE_MODEL",
    ),
    (
        "DECISION_REFERENCE_OVERLAP",
        "D02B_DECISION_MODEL_SETS_OVERLAP",
    ),
    ("RULE_FAMILY_DOMAIN_MISMATCH", "D02B_RULE_FAMILY_CROSS_DOMAIN"),
    (
        "ASSERTED_CLAIM_WITHOUT_EVIDENCE",
        "D02B_ASSERTED_CLAIM_REQUIRES_EVIDENCE",
    ),
    (
        "TRAJECTORY_DIGEST_DOMAIN_COLLISION",
        "D02B_TRAJECTORY_DIGEST_DOMAIN_COLLISION",
    ),
    (
        "AUTHORITATIVE_SCHEMA_TEMPLATE",
        "D02B_TEMPLATE_APPROVAL_MUST_BE_NONAUTHORITATIVE",
    ),
    (
        "UNTRUSTED_OWNER_APPROVAL",
        "D02B_OWNER_APPROVAL_DIGEST_NOT_TRUSTED",
    ),
    ("PROMOTION_WITHOUT_APPROVAL", "D02B_PROMOTION_REQUIRES_APPROVAL"),
    ("COVERAGE_COUNT_OVERFLOW", "D02B_COVERAGE_COUNT_EXCEEDS_SOURCE"),
    (
        "COMPLETION_ACCEPTED_WITHOUT_APPROVAL",
        "D02B_COMPLETION_ACCEPTANCE_REQUIRES_APPROVAL",
    ),
    ("FROZEN_ARTIFACT_COUNT_MISMATCH", "D02B_ARTIFACT_COUNT_MISMATCH"),
)


def _envelope_for(
    envelopes: Sequence[JsonObject],
    schema_name: str,
) -> JsonObject:
    for envelope in envelopes:
        if envelope.get("schema_name") == schema_name:
            return envelope
    _raise("D02B_EXAMPLE_ENVELOPE_MISSING", schema_name)


def _mutate_and_refinalize(
    envelopes: list[JsonObject],
    schema_name: str,
    updates: Mapping[str, JsonValue],
) -> None:
    envelope = _envelope_for(envelopes, schema_name)
    instance = _as_object(
        envelope["instance"],
        "D02B_EXAMPLE_INSTANCE_INVALID",
        schema_name,
    )
    instance.update(copy.deepcopy(dict(updates)))
    envelope["instance"] = _refinalize_new_instance(
        schema_name,
        instance,
    )


def _dependency_closure(
    envelopes: Sequence[JsonObject],
    root_schema_names: Sequence[str],
) -> list[JsonObject]:
    by_id: dict[str, JsonObject] = {}
    by_digest: dict[str, JsonObject] = {}
    by_schema: dict[str, JsonObject] = {}
    for envelope in envelopes:
        schema_name = cast(str, envelope["schema_name"])
        instance = _as_object(
            envelope["instance"],
            "D02B_EXAMPLE_INSTANCE_INVALID",
            schema_name,
        )
        definition = SCHEMA_BY_NAME[schema_name]
        by_schema[schema_name] = envelope
        by_id[cast(str, instance[definition.id_field])] = envelope
        by_digest[cast(str, instance[definition.digest_field])] = envelope

    pending = [by_schema[schema_name] for schema_name in root_schema_names]
    selected: dict[str, JsonObject] = {}
    while pending:
        envelope = pending.pop()
        schema_name = cast(str, envelope["schema_name"])
        if schema_name in selected:
            continue
        selected[schema_name] = envelope
        instance = _as_object(
            envelope["instance"],
            "D02B_EXAMPLE_INSTANCE_INVALID",
            schema_name,
        )
        definition = SCHEMA_BY_NAME[schema_name]
        for reference in definition.references:
            index = by_digest if reference.reference_kind == "DIGEST" else by_id
            for value in _pointer_values(instance, reference.pointer):
                if value is None:
                    continue
                if isinstance(value, str) and value in index:
                    pending.append(index[value])
    return [
        copy.deepcopy(envelope)
        for envelope in envelopes
        if cast(str, envelope["schema_name"]) in selected
    ]


def materialize_invalid_case(
    valid_examples: Sequence[Mapping[str, JsonValue]],
    scenario_name: str,
) -> list[JsonObject]:
    """Materialize one deterministic negative bundle from the base fixture."""

    envelopes = cast(
        list[JsonObject],
        copy.deepcopy(list(valid_examples)),
    )
    model_id = cast(
        str,
        _as_object(
            _envelope_for(envelopes, "ModelRecord")["instance"],
            "D02B_EXAMPLE_INSTANCE_INVALID",
        )["model_id"],
    )
    interpretation_id = cast(
        str,
        _as_object(
            _envelope_for(
                envelopes,
                "InterpretationHypothesis",
            )["instance"],
            "D02B_EXAMPLE_INSTANCE_INVALID",
        )["interpretation_id"],
    )
    roots_by_case: dict[str, tuple[str, ...]] = {
        "UNKNOWN_SCHEMA": ("RawObservation",),
        "UNKNOWN_TOP_LEVEL_PROPERTY": ("RawObservation",),
        "RAW_INFERENCE_CONTAMINATION": ("RawObservation",),
        "DERIVATION_SEMANTIC_LABEL": ("DeterministicDerivation",),
        "HYPOTHESIS_IDENTITY_ROUTING": ("HypothesisIR",),
        "EVIDENCE_DANGLING_REFERENCE": ("EvidenceRecord",),
        "EVIDENCE_WRONG_TARGET": (
            "EvidenceRecord",
            "InterpretationHypothesis",
        ),
        "REFERENCE_KIND_MISMATCH": ("DependencyLock",),
        "EVIDENCE_ORIGIN_MISMATCH": ("EvidenceRecord",),
        "ACTION_NOT_AVAILABLE": ("ARC3ActionRecord",),
        "DUPLICATE_PRIMARY_ID": ("ResourceProfile",),
        "SINGLE_WITHOUT_SELECTION": ("DecisionRecord",),
        "SUSPEND_WITH_SELECTION": ("DecisionRecord",),
        "MULTI_CAUSAL_SINGLE_SELECTION": ("DecisionRecord",),
        "DECISION_REFERENCE_OVERLAP": ("DecisionRecord",),
        "RULE_FAMILY_DOMAIN_MISMATCH": ("RuleFamily",),
        "ASSERTED_CLAIM_WITHOUT_EVIDENCE": ("ClaimRecord",),
        "TRAJECTORY_DIGEST_DOMAIN_COLLISION": ("ARC3TeacherTrajectory",),
        "AUTHORITATIVE_SCHEMA_TEMPLATE": ("ApprovalRecord",),
        "UNTRUSTED_OWNER_APPROVAL": ("ApprovalRecord",),
        "PROMOTION_WITHOUT_APPROVAL": ("PromotionDecision",),
        "COVERAGE_COUNT_OVERFLOW": ("CoverageReport",),
        "COMPLETION_ACCEPTED_WITHOUT_APPROVAL": ("CompletionStateRegistry",),
        "FROZEN_ARTIFACT_COUNT_MISMATCH": ("FrozenArtifactManifest",),
    }
    if scenario_name not in roots_by_case:
        _raise("D02B_INVALID_CASE_UNKNOWN", scenario_name)
    envelopes = _dependency_closure(
        envelopes,
        roots_by_case[scenario_name],
    )

    if scenario_name == "UNKNOWN_SCHEMA":
        _envelope_for(envelopes, "RawObservation")["schema_name"] = "UnknownSchema"
    elif scenario_name == "UNKNOWN_TOP_LEVEL_PROPERTY":
        instance = _as_object(
            _envelope_for(envelopes, "RawObservation")["instance"],
            "D02B_EXAMPLE_INSTANCE_INVALID",
        )
        instance["unexpected_property"] = "forbidden"
    elif scenario_name == "RAW_INFERENCE_CONTAMINATION":
        instance = _as_object(
            _envelope_for(envelopes, "RawObservation")["instance"],
            "D02B_EXAMPLE_INSTANCE_INVALID",
        )
        instance["raw_value"] = {"inferred_goal": "forbidden"}
        _envelope_for(envelopes, "RawObservation")["instance"] = (
            _refinalize_new_instance("RawObservation", instance)
        )
    elif scenario_name == "DERIVATION_SEMANTIC_LABEL":
        _mutate_and_refinalize(
            envelopes,
            "DeterministicDerivation",
            {"output": {"semantic_label": "forbidden"}},
        )
    elif scenario_name == "HYPOTHESIS_IDENTITY_ROUTING":
        _mutate_and_refinalize(
            envelopes,
            "HypothesisIR",
            {"selector_graph": [{"task_id": "forbidden"}]},
        )
    elif scenario_name == "EVIDENCE_DANGLING_REFERENCE":
        _mutate_and_refinalize(
            envelopes,
            "EvidenceRecord",
            {"evidence_ref": "missing-reference"},
        )
    elif scenario_name == "EVIDENCE_WRONG_TARGET":
        _mutate_and_refinalize(
            envelopes,
            "EvidenceRecord",
            {"evidence_ref": interpretation_id},
        )
    elif scenario_name == "REFERENCE_KIND_MISMATCH":
        environment = _as_object(
            _envelope_for(envelopes, "EnvironmentManifest")["instance"],
            "D02B_EXAMPLE_INSTANCE_INVALID",
        )
        _mutate_and_refinalize(
            envelopes,
            "DependencyLock",
            {"environment_manifest_ref": environment["content_digest"]},
        )
    elif scenario_name == "EVIDENCE_ORIGIN_MISMATCH":
        _mutate_and_refinalize(
            envelopes,
            "EvidenceRecord",
            {"evidence_origin": "RAW_OBSERVATION"},
        )
    elif scenario_name == "ACTION_NOT_AVAILABLE":
        _mutate_and_refinalize(
            envelopes,
            "ARC3ActionRecord",
            {
                "action_id": 2,
                "available_actions_before": [1],
            },
        )
    elif scenario_name == "DUPLICATE_PRIMARY_ID":
        envelopes.append(copy.deepcopy(_envelope_for(envelopes, "ResourceProfile")))
    elif scenario_name == "SINGLE_WITHOUT_SELECTION":
        _mutate_and_refinalize(
            envelopes,
            "DecisionRecord",
            {
                "decision_mode": "SINGLE",
                "held_model_refs": [model_id],
                "selected_model_refs": [],
            },
        )
    elif scenario_name == "SUSPEND_WITH_SELECTION":
        _mutate_and_refinalize(
            envelopes,
            "DecisionRecord",
            {
                "held_model_refs": [],
                "selected_model_refs": [model_id],
            },
        )
    elif scenario_name == "MULTI_CAUSAL_SINGLE_SELECTION":
        _mutate_and_refinalize(
            envelopes,
            "DecisionRecord",
            {
                "assertion_state": "ASSERT",
                "decision_mode": "MULTI_CAUSAL",
                "held_model_refs": [],
                "operation_state": "CONTINUE",
                "selected_model_refs": [model_id],
            },
        )
    elif scenario_name == "DECISION_REFERENCE_OVERLAP":
        _mutate_and_refinalize(
            envelopes,
            "DecisionRecord",
            {
                "decision_mode": "SINGLE",
                "held_model_refs": [model_id],
                "selected_model_refs": [model_id],
            },
        )
    elif scenario_name == "RULE_FAMILY_DOMAIN_MISMATCH":
        _mutate_and_refinalize(
            envelopes,
            "RuleFamily",
            {"domain": "ARC2"},
        )
    elif scenario_name == "ASSERTED_CLAIM_WITHOUT_EVIDENCE":
        _mutate_and_refinalize(
            envelopes,
            "ClaimRecord",
            {
                "assertion_state": "ASSERT",
                "evidence_refs": [],
            },
        )
    elif scenario_name == "TRAJECTORY_DIGEST_DOMAIN_COLLISION":
        envelope = _envelope_for(envelopes, "ARC3TeacherTrajectory")
        instance = _as_object(
            envelope["instance"],
            "D02B_EXAMPLE_INSTANCE_INVALID",
        )
        raw_digest = cast(str, instance["raw_trajectory_digest"])
        _mutate_and_refinalize(
            envelopes,
            "ARC3TeacherTrajectory",
            {
                "canonical_trajectory_digest": (
                    "hds-canonical-trajectory:" + raw_digest.rsplit(":", 1)[-1]
                )
            },
        )
    elif scenario_name == "AUTHORITATIVE_SCHEMA_TEMPLATE":
        _mutate_and_refinalize(
            envelopes,
            "ApprovalRecord",
            {"authoritative": True},
        )
    elif scenario_name == "UNTRUSTED_OWNER_APPROVAL":
        _mutate_and_refinalize(
            envelopes,
            "ApprovalRecord",
            {
                "approval_mode": "OWNER_RECORDED",
                "authoritative": True,
                "authority": "OWNER",
                "decision": "APPROVE",
                "next_state": "PROBATION",
            },
        )
    elif scenario_name == "PROMOTION_WITHOUT_APPROVAL":
        _mutate_and_refinalize(
            envelopes,
            "PromotionDecision",
            {
                "decision": "PROMOTE",
                "proposed_adoption_state": "ACTIVE",
            },
        )
    elif scenario_name == "COVERAGE_COUNT_OVERFLOW":
        _mutate_and_refinalize(
            envelopes,
            "CoverageReport",
            {"processed_case_count": 2},
        )
    elif scenario_name == "COMPLETION_ACCEPTED_WITHOUT_APPROVAL":
        envelope = _envelope_for(envelopes, "CompletionStateRegistry")
        instance = _as_object(
            envelope["instance"],
            "D02B_EXAMPLE_INSTANCE_INVALID",
        )
        states = _as_object(
            instance["states"],
            "D02B_EXAMPLE_STATES_INVALID",
        )
        states["DISTILLATION_COVERAGE_ACCEPTED"] = "OWNER_ACCEPTED"
        envelope["instance"] = _refinalize_new_instance(
            "CompletionStateRegistry",
            instance,
        )
    elif scenario_name == "FROZEN_ARTIFACT_COUNT_MISMATCH":
        _mutate_and_refinalize(
            envelopes,
            "FrozenArtifactManifest",
            {"artifact_count": 2},
        )
    else:
        _raise("D02B_INVALID_CASE_UNKNOWN", scenario_name)
    return envelopes


def _build_non_single_decision_bundle(
    valid_examples: Sequence[Mapping[str, JsonValue]],
    *,
    decision_mode: str,
    selected_count: int,
    state_overrides: Mapping[str, JsonValue],
) -> list[JsonObject]:
    base = cast(list[JsonObject], copy.deepcopy(list(valid_examples)))
    bundle = _dependency_closure(base, ("DecisionRecord",))
    model_envelope = _envelope_for(bundle, "ModelRecord")
    first_model = _as_object(
        model_envelope["instance"],
        "D02B_EXAMPLE_INSTANCE_INVALID",
        "ModelRecord",
    )
    selected_refs: list[JsonValue] = []
    if selected_count > 0:
        selected_refs.append(first_model["model_id"])
    for index in range(1, selected_count):
        additional_model_body = copy.deepcopy(first_model)
        additional_model_body["statement"] = "Independent synthetic model " + str(
            index + 1
        )
        additional_model = _refinalize_new_instance(
            "ModelRecord",
            additional_model_body,
        )
        bundle.append(
            {
                "instance": additional_model,
                "schema_name": "ModelRecord",
            }
        )
        selected_refs.append(additional_model["model_id"])
    decision_envelope = _envelope_for(bundle, "DecisionRecord")
    decision = _as_object(
        decision_envelope["instance"],
        "D02B_EXAMPLE_INSTANCE_INVALID",
        "DecisionRecord",
    )
    decision.update(
        {
            "decision_mode": decision_mode,
            "held_model_refs": ([] if selected_refs else [first_model["model_id"]]),
            "selected_model_refs": selected_refs,
        }
    )
    decision.update(copy.deepcopy(dict(state_overrides)))
    decision_envelope["instance"] = _refinalize_new_instance(
        "DecisionRecord",
        decision,
    )
    return bundle


def build_multi_causal_example_bundle(
    valid_examples: Sequence[Mapping[str, JsonValue]],
) -> list[JsonObject]:
    """Build a two-model MULTI_CAUSAL fixture without one-choice collapse."""

    return _build_non_single_decision_bundle(
        valid_examples,
        decision_mode="MULTI_CAUSAL",
        selected_count=2,
        state_overrides={
            "assertion_state": "ASSERT",
            "operation_state": "CONTINUE",
        },
    )


def build_zero_selection_multi_causal_example_bundle(
    valid_examples: Sequence[Mapping[str, JsonValue]],
) -> list[JsonObject]:
    """Build a zero-selection MULTI_CAUSAL fixture."""

    return _build_non_single_decision_bundle(
        valid_examples,
        decision_mode="MULTI_CAUSAL",
        selected_count=0,
        state_overrides={
            "assertion_state": "SUSPEND",
            "operation_state": "PROBE",
        },
    )


def build_multi_selection_suspend_example_bundle(
    valid_examples: Sequence[Mapping[str, JsonValue]],
) -> list[JsonObject]:
    """Build a two-selection SUSPEND fixture with independent state axes."""

    return _build_non_single_decision_bundle(
        valid_examples,
        decision_mode="SUSPEND",
        selected_count=2,
        state_overrides={
            "adoption_state": "QUARANTINE",
            "assertion_state": "FAIL",
            "closure_state": "REOPENED",
            "evidence_state": "FALSIFIED",
            "mechanism_support_state": "FALSIFIED",
            "operation_state": "PROBE",
            "update_state": "REJECTED",
        },
    )


def build_invalid_example_set(valid_example_set: JsonObject) -> JsonObject:
    cases: list[JsonValue] = [
        {
            "case_id": scenario_name,
            "expected_error_code": expected_code,
            "mutation_source": "DETERMINISTIC_MODULE_FUNCTION",
        }
        for scenario_name, expected_code in INVALID_CASES
    ]
    artifact: JsonObject = {
        "artifact_kind": "PH_D02B_INVALID_SCHEMA_BUNDLES",
        "base_valid_example_set_digest": valid_example_set["content_digest"],
        "case_count": len(cases),
        "cases": cases,
        "content_digest": "",
        "digest_excluded_fields": [
            "content_digest",
            "example_set_id",
        ],
        "example_set_id": INVALID_EXAMPLE_SET_ID,
        "owner_approval_generated": False,
        "phase_id": "PH-D02B",
        "schema_version": "hds-invalid-schema-bundles-v1",
    }
    artifact["content_digest"] = _artifact_digest(
        "hds-invalid-schema-bundles",
        artifact,
        id_field="example_set_id",
    )
    return artifact


def _documents_from_payloads(
    payloads: Mapping[str, bytes],
) -> dict[str, JsonObject]:
    if set(payloads) != set(SCHEMA_BY_FILENAME):
        _raise("D02B_SCHEMA_PAYLOAD_SET_MISMATCH")
    documents: dict[str, JsonObject] = {}
    for filename, payload in payloads.items():
        try:
            decoded = json.loads(payload)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise SchemaValidationError(
                "D02B_SCHEMA_JSON_INVALID",
                filename,
            ) from exc
        definition = SCHEMA_BY_FILENAME[filename]
        documents[definition.name] = _as_object(
            decoded,
            "D02B_SCHEMA_NOT_OBJECT",
            filename,
        )
    return documents


def build_schema_conformance_report(
    project_root: Path,
    schema_payloads: Mapping[str, bytes],
    valid_example_set: JsonObject,
    invalid_example_set: JsonObject,
) -> JsonObject:
    """Execute deterministic positive and negative schema conformance."""

    documents = _documents_from_payloads(schema_payloads)
    contract = build_schema_contract()
    registry = SchemaRegistry(documents, contract)
    examples_value = valid_example_set.get("examples")
    if not isinstance(examples_value, list):
        _raise("D02B_VALID_EXAMPLES_ARRAY_REQUIRED")
    examples = cast(list[Mapping[str, JsonValue]], examples_value)
    validated = registry.validate_bundle(examples)
    suspend_bundle = _dependency_closure(
        cast(list[JsonObject], copy.deepcopy(examples)),
        ("DecisionRecord",),
    )
    registry.validate_bundle(suspend_bundle)
    multi_causal_bundle = build_multi_causal_example_bundle(examples)
    registry.validate_bundle(multi_causal_bundle)
    zero_selection_multi_causal_bundle = (
        build_zero_selection_multi_causal_example_bundle(examples)
    )
    registry.validate_bundle(zero_selection_multi_causal_bundle)
    multi_selection_suspend_bundle = build_multi_selection_suspend_example_bundle(
        examples
    )
    registry.validate_bundle(multi_selection_suspend_bundle)

    negative_results: list[JsonValue] = []
    for scenario_name, expected_code in INVALID_CASES:
        try:
            registry.validate_bundle(materialize_invalid_case(examples, scenario_name))
        except SchemaValidationError as exc:
            actual_code = exc.code
        else:
            actual_code = "ACCEPTED_INVALID_BUNDLE"
        negative_results.append(
            {
                "actual_error_code": actual_code,
                "case_id": scenario_name,
                "expected_error_code": expected_code,
                "passed": actual_code == expected_code,
            }
        )
    if not all(
        cast(JsonObject, result)["passed"] is True for result in negative_results
    ):
        _raise("D02B_NEGATIVE_CONFORMANCE_FAILED")

    entries: list[JsonValue] = []
    for definition in SCHEMA_DEFINITIONS:
        payload = schema_payloads[definition.filename]
        entries.append(
            {
                "filename": definition.filename,
                "index": definition.index,
                "name": definition.name,
                "physical_sha256": hashlib.sha256(payload).hexdigest(),
                "preserved_from_prior_phase": definition.preserved,
                "schema_version": definition.schema_version,
            }
        )

    report: JsonObject = {
        "artifact_kind": "PH_D02B_SCHEMA_CONFORMANCE",
        "content_digest": "",
        "digest_excluded_fields": [
            "content_digest",
            "report_id",
        ],
        "gate_results": {
            "DG-00": "PASS",
            "DG-01": "PASS",
            "DG-02": "PASS",
            "DG-14": "PASS_SCHEMA_BOUNDARY_ONLY_NO_APPROVAL",
        },
        "generated_schema_count": sum(
            not definition.preserved for definition in SCHEMA_DEFINITIONS
        ),
        "hds_state_axis_count": len(HDS_STATE_AXES),
        "inventory_count": len(SCHEMA_DEFINITIONS),
        "invalid_case_count": len(negative_results),
        "invalid_case_pass_count": sum(
            cast(JsonObject, result)["passed"] is True for result in negative_results
        ),
        "invalid_example_set_digest": invalid_example_set["content_digest"],
        "negative_results": negative_results,
        "owner_approval_generated": False,
        "phase_boundaries": {
            "candidate_generation_started": False,
            "kaggle_mutation_count": 0,
            "locked_final_access_count": 0,
            "official_access_count": 0,
            "ph_d02c_execution_count": 0,
            "real_trajectory_normalization_count": 0,
            "rule_promotion_count": 0,
            "runtime_started": False,
        },
        "phase_id": "PH-D02B",
        "positive_bundle_record_count": len(validated),
        "positive_bundle_result": "PASS",
        "multi_causal_no_single_choice_result": "PASS",
        "multi_causal_zero_selection_result": "PASS",
        "preserved_schema_count": sum(
            definition.preserved for definition in SCHEMA_DEFINITIONS
        ),
        "report_id": "HDS-PH-D02B-SCHEMA-CONFORMANCE-V1",
        "schema_contract_digest": contract["content_digest"],
        "schema_entries": entries,
        "schema_version": "hds-schema-conformance-report-v1",
        "synthetic_fixture_only": True,
        "suspend_multiple_selection_result": "PASS",
        "suspend_no_selected_model_result": "PASS",
        "valid_example_set_digest": valid_example_set["content_digest"],
    }
    report["content_digest"] = _artifact_digest(
        "hds-schema-conformance",
        report,
        id_field="report_id",
    )
    del project_root
    return report


def build_phase_d02b_artifacts(
    project_root: Path,
) -> dict[str, bytes]:
    """Build every deterministic PH-D02B schema artifact in memory."""

    schema_root = project_root / "distillation/schemas"
    schema_payloads = build_schema_payloads(schema_root)
    contract = build_schema_contract()
    valid_examples = build_valid_example_set(project_root)
    invalid_examples = build_invalid_example_set(valid_examples)
    conformance = build_schema_conformance_report(
        project_root,
        schema_payloads,
        valid_examples,
        invalid_examples,
    )
    artifacts: dict[str, bytes] = {
        ("distillation/input/schema_contract.json"): canonical_json_bytes(contract),
        (
            "distillation/artifacts/test_vectors/schema_examples/"
            "valid_schema_examples.json"
        ): canonical_json_bytes(valid_examples),
        (
            "distillation/artifacts/test_vectors/schema_examples/"
            "invalid_schema_bundles.json"
        ): canonical_json_bytes(invalid_examples),
        (
            "distillation/artifacts/reports/schema_conformance.json"
        ): canonical_json_bytes(conformance),
    }
    for filename, payload in schema_payloads.items():
        artifacts["distillation/schemas/" + filename] = payload
    for path, payload in artifacts.items():
        if path.endswith(".schema.json"):
            definition = SCHEMA_BY_FILENAME[Path(path).name]
            if not definition.preserved:
                _verify_stable_schema_json_bytes(payload)
        else:
            verify_canonical_json_bytes(payload)
    return dict(sorted(artifacts.items()))


def write_phase_d02b_artifacts(project_root: Path) -> dict[str, str]:
    """Write only the deterministic artifact paths owned by PH-D02B."""

    artifacts = build_phase_d02b_artifacts(project_root)
    written_digests: dict[str, str] = {}
    for relative_path, payload in artifacts.items():
        path = project_root / relative_path
        if relative_path.endswith(".schema.json"):
            definition = SCHEMA_BY_FILENAME[path.name]
            if definition.preserved:
                if path.read_bytes() != payload:
                    _raise(
                        "D02B_PRESERVED_SCHEMA_WRITE_FORBIDDEN",
                        relative_path,
                    )
                written_digests[relative_path] = hashlib.sha256(payload).hexdigest()
                continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        written_digests[relative_path] = hashlib.sha256(payload).hexdigest()

    contract_path = project_root / ("distillation/input/schema_contract.json")
    registry = SchemaRegistry.from_directory(
        project_root / "distillation/schemas",
        contract_path,
    )
    valid = _read_json_object(
        project_root
        / (
            "distillation/artifacts/test_vectors/schema_examples/"
            "valid_schema_examples.json"
        ),
        "D02B_WRITTEN_VALID_EXAMPLES_UNREADABLE",
    )
    examples = valid.get("examples")
    if not isinstance(examples, list):
        _raise("D02B_WRITTEN_VALID_EXAMPLES_ARRAY_REQUIRED")
    registry.validate_bundle(cast(list[Mapping[str, JsonValue]], examples))
    return written_digests
