"""PH-D02C content-bound ARC2 and ARC3 opcode registries."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, cast

from .canonical import (
    DigestExclusionPolicy,
    JsonValue,
    content_derived_id,
    logical_content_digest,
)
from .ir_types import (
    COMMON_TYPE_NAMES,
    IRContractError,
    JsonObject,
    fail,
)

OPCODE_VERSION: Final = "1.0.0"
OPERATOR_REGISTRY_SCHEMA_VERSION: Final = "hds-operator-registry-v2"
ARC2_REGISTRY_VERSION: Final = "hds-arc2-operator-registry-v2"
ARC3_REGISTRY_VERSION: Final = "hds-arc3-operator-registry-v2"
SYNTHETIC_DEPENDENCY_LOCK_REF: Final = (
    "hds-dependency-lock-id:"
    "e5efa35b6f3f5e5636352d778656f702108b0d9c3a66a18b6bf7708869ea8226"
)

ARC2_OPCODE_NAMES: Final = (
    "SELECT_CELLS",
    "SELECT_COMPONENTS_4",
    "SELECT_COMPONENTS_8",
    "SELECT_BY_COLOR",
    "SELECT_BY_SIZE",
    "SELECT_BY_SHAPE",
    "SELECT_BY_RELATION",
    "UNIQUE",
    "ARGMIN",
    "ARGMAX",
    "IDENTITY",
    "RECOLOR",
    "TRANSLATE",
    "ROTATE_90",
    "ROTATE_180",
    "ROTATE_270",
    "REFLECT_HORIZONTAL",
    "REFLECT_VERTICAL",
    "COPY",
    "CROP",
    "PAD",
    "TILE",
    "FILL",
    "OUTLINE",
    "CONNECT",
    "MASK",
    "OVERLAY",
    "DELETE",
    "EXTRACT",
    "COUNT",
    "COUNT_ENCODE",
    "REPEAT_N",
    "COMPOSE",
)

ARC3_OPCODE_NAMES: Final = (
    "DERIVE_STATE_FIELD",
    "TRACK_ENTITY",
    "MATCH_ACTION_ID",
    "MATCH_ACTION_PAYLOAD",
    "PRECONDITION",
    "PREDICT_EFFECT",
    "PREDICT_TRANSITION",
    "DELAYED_EFFECT",
    "GOAL_PREDICATE",
    "HAZARD_PREDICATE",
    "ORDER_BEFORE",
    "ORDER_ADJACENT",
    "REPEAT_N",
    "REPEAT_UNTIL_OBSERVED",
    "RESET_EFFECT",
    "TERMINAL_CONTRIBUTION",
    "INVARIANT",
    "EXCLUSION",
)

CARDINALITY_VALUES: Final = (
    "NOT_SELECTOR",
    "ZERO_OR_MORE",
    "EXACTLY_ONE",
    "AT_LEAST_ONE",
)


def _parameter_schema(
    *,
    properties: Mapping[str, JsonValue] | None = None,
    required: Sequence[str] = (),
) -> JsonObject:
    return {
        "additionalProperties": False,
        "properties": dict(properties or {}),
        "required": list(required),
        "type": "object",
    }


NO_PARAMETERS: Final = _parameter_schema()


@dataclass(frozen=True, slots=True)
class OpcodeDefinition:
    opcode: str
    domain: str
    input_types: tuple[str, ...]
    output_type: str
    execution_semantics: str
    invalid_operation_semantics: str = "IR_INVALID_OPERATION"
    parameter_schema: JsonObject | None = None
    preconditions: tuple[str, ...] = ()
    resource_cost: int = 1
    selector_cardinality: str = "NOT_SELECTOR"
    commutes_with: tuple[str, ...] = ()

    def as_json(self) -> JsonObject:
        entry: JsonObject = {
            "canonicalization_rule": "PRESERVE_DECLARED_NODE_ORDER",
            "commutes_with": list(self.commutes_with),
            "content_digest": "",
            "deterministic": True,
            "domain": self.domain,
            "execution_semantics": self.execution_semantics,
            "input_types": list(self.input_types),
            "invalid_operation_semantics": self.invalid_operation_semantics,
            "opcode": self.opcode,
            "opcode_version": OPCODE_VERSION,
            "output_type": self.output_type,
            "parameter_schema": self.parameter_schema or NO_PARAMETERS,
            "preconditions": list(self.preconditions),
            "resource_cost": self.resource_cost,
            "selector_cardinality": self.selector_cardinality,
            "side_effect_free": True,
            "test_vector_refs": ["D02C-" + self.domain + "-" + self.opcode + "-V1"],
        }
        entry["content_digest"] = logical_content_digest(
            "hds-operator-entry",
            entry,
            policy=DigestExclusionPolicy(digest_fields=frozenset({"content_digest"})),
        )
        return entry


def _arc2_definitions() -> tuple[OpcodeDefinition, ...]:
    color_parameter = _parameter_schema(
        properties={
            "colors": {
                "items": {"maximum": 9, "minimum": 0, "type": "integer"},
                "minItems": 1,
                "type": "array",
                "uniqueItems": True,
            }
        }
    )
    field_parameter = _parameter_schema(
        properties={"field": {"type": "string"}},
        required=("field",),
    )
    collision_parameter = _parameter_schema(
        properties={
            "collision_policy": {
                "enum": ["FAIL", "CLIP"],
                "type": "string",
            }
        }
    )
    precedence_parameter = _parameter_schema(
        properties={
            "precedence": {
                "enum": ["TOP_NONZERO", "BOTTOM_NONZERO"],
                "type": "string",
            }
        }
    )
    return (
        OpcodeDefinition(
            "SELECT_CELLS",
            "ARC2",
            ("Grid",),
            "CellSet",
            "Select cells whose colors match parameters.colors or all nonzero cells.",
            parameter_schema=color_parameter,
            selector_cardinality="ZERO_OR_MORE",
        ),
        OpcodeDefinition(
            "SELECT_COMPONENTS_4",
            "ARC2",
            ("Grid",),
            "ObjectSet",
            "Return nonzero four-connected components in lexical seed order.",
            resource_cost=2,
            selector_cardinality="ZERO_OR_MORE",
        ),
        OpcodeDefinition(
            "SELECT_COMPONENTS_8",
            "ARC2",
            ("Grid",),
            "ObjectSet",
            "Return nonzero eight-connected components in lexical seed order.",
            resource_cost=2,
            selector_cardinality="ZERO_OR_MORE",
        ),
        OpcodeDefinition(
            "SELECT_BY_COLOR",
            "ARC2",
            ("ObjectSet", "Color"),
            "ObjectSet",
            "Keep candidates whose declared color equals the input color.",
            selector_cardinality="ZERO_OR_MORE",
        ),
        OpcodeDefinition(
            "SELECT_BY_SIZE",
            "ARC2",
            ("ObjectSet", "Scalar"),
            "ObjectSet",
            "Keep candidates whose cell count equals the input scalar.",
            selector_cardinality="ZERO_OR_MORE",
        ),
        OpcodeDefinition(
            "SELECT_BY_SHAPE",
            "ARC2",
            ("ObjectSet", "CellSet"),
            "ObjectSet",
            "Keep candidates with the same translation-normalized cell shape.",
            selector_cardinality="ZERO_OR_MORE",
        ),
        OpcodeDefinition(
            "SELECT_BY_RELATION",
            "ARC2",
            ("ObjectSet", "RelationGraph"),
            "ObjectSet",
            "Keep candidates whose attributes.node_id occurs in a graph edge.",
            selector_cardinality="ZERO_OR_MORE",
        ),
        OpcodeDefinition(
            "UNIQUE",
            "ARC2",
            ("ObjectSet",),
            "ObjectCandidate",
            "Return the sole candidate and reject zero or multiple candidates.",
            selector_cardinality="EXACTLY_ONE",
        ),
        OpcodeDefinition(
            "ARGMIN",
            "ARC2",
            ("ObjectSet",),
            "ObjectCandidate",
            "Return the unique minimum by parameters.field without tie-breaking.",
            parameter_schema=field_parameter,
            selector_cardinality="EXACTLY_ONE",
        ),
        OpcodeDefinition(
            "ARGMAX",
            "ARC2",
            ("ObjectSet",),
            "ObjectCandidate",
            "Return the unique maximum by parameters.field without tie-breaking.",
            parameter_schema=field_parameter,
            selector_cardinality="EXACTLY_ONE",
        ),
        OpcodeDefinition(
            "IDENTITY",
            "ARC2",
            ("Sequence",),
            "Sequence",
            "Return the input sequence unchanged.",
        ),
        OpcodeDefinition(
            "RECOLOR",
            "ARC2",
            ("Grid", "CellSet", "Color"),
            "Grid",
            "Replace exactly the selected in-bounds cells with the input color.",
            preconditions=("all selected cells are in bounds",),
        ),
        OpcodeDefinition(
            "TRANSLATE",
            "ARC2",
            ("CellSet", "Vector"),
            "CellSet",
            "Add the vector to every cell with explicit FAIL or CLIP policy.",
            parameter_schema=collision_parameter,
        ),
        OpcodeDefinition(
            "ROTATE_90",
            "ARC2",
            ("Grid",),
            "Grid",
            "Rotate the grid clockwise by ninety degrees.",
        ),
        OpcodeDefinition(
            "ROTATE_180",
            "ARC2",
            ("Grid",),
            "Grid",
            "Rotate the grid by one hundred eighty degrees.",
        ),
        OpcodeDefinition(
            "ROTATE_270",
            "ARC2",
            ("Grid",),
            "Grid",
            "Rotate the grid clockwise by two hundred seventy degrees.",
        ),
        OpcodeDefinition(
            "REFLECT_HORIZONTAL",
            "ARC2",
            ("Grid",),
            "Grid",
            "Reflect each row left-to-right.",
        ),
        OpcodeDefinition(
            "REFLECT_VERTICAL",
            "ARC2",
            ("Grid",),
            "Grid",
            "Reflect the row order top-to-bottom.",
        ),
        OpcodeDefinition(
            "COPY",
            "ARC2",
            ("Grid",),
            "Grid",
            "Return a value copy of the grid.",
        ),
        OpcodeDefinition(
            "CROP",
            "ARC2",
            ("Grid", "Region"),
            "Grid",
            "Extract the exact in-bounds rectangular region.",
            preconditions=("region is fully in bounds",),
        ),
        OpcodeDefinition(
            "PAD",
            "ARC2",
            ("Grid", "Scalar", "Color"),
            "Grid",
            "Pad all sides by the non-negative scalar using the input color.",
        ),
        OpcodeDefinition(
            "TILE",
            "ARC2",
            ("Grid", "Vector"),
            "Grid",
            "Repeat the grid by positive row and column factors.",
        ),
        OpcodeDefinition(
            "FILL",
            "ARC2",
            ("Grid", "Region", "Color"),
            "Grid",
            "Fill the exact in-bounds region with the input color.",
            preconditions=("region is fully in bounds",),
        ),
        OpcodeDefinition(
            "OUTLINE",
            "ARC2",
            ("Region",),
            "CellSet",
            "Return the lexical perimeter cells of a region.",
        ),
        OpcodeDefinition(
            "CONNECT",
            "ARC2",
            ("Cell", "Cell"),
            "CellSet",
            "Return an inclusive straight horizontal, vertical, or diagonal line.",
        ),
        OpcodeDefinition(
            "MASK",
            "ARC2",
            ("Grid", "CellSet"),
            "Grid",
            "Keep selected cells and replace every other cell with zero.",
        ),
        OpcodeDefinition(
            "OVERLAY",
            "ARC2",
            ("Grid", "Grid"),
            "Grid",
            "Overlay equal-shape grids under an explicit nonzero precedence.",
            parameter_schema=precedence_parameter,
            preconditions=("grid shapes are equal",),
        ),
        OpcodeDefinition(
            "DELETE",
            "ARC2",
            ("Grid", "CellSet"),
            "Grid",
            "Replace exactly the selected in-bounds cells with zero.",
            preconditions=("all selected cells are in bounds",),
        ),
        OpcodeDefinition(
            "EXTRACT",
            "ARC2",
            ("Grid", "CellSet"),
            "Grid",
            "Extract the bounding box of a non-empty cell set.",
            preconditions=("cell set is non-empty and in bounds",),
        ),
        OpcodeDefinition(
            "COUNT",
            "ARC2",
            ("Sequence",),
            "Scalar",
            "Return the sequence length.",
        ),
        OpcodeDefinition(
            "COUNT_ENCODE",
            "ARC2",
            ("Scalar", "Color"),
            "Grid",
            "Encode a positive count as one row of the input color.",
            preconditions=("count is positive",),
        ),
        OpcodeDefinition(
            "REPEAT_N",
            "ARC2",
            ("Sequence", "Scalar"),
            "Sequence",
            "Concatenate the sequence a non-negative number of times.",
        ),
        OpcodeDefinition(
            "COMPOSE",
            "ARC2",
            ("Sequence", "Sequence"),
            "Sequence",
            "Concatenate two ordered sequences without reordering.",
        ),
    )


def _arc3_definitions() -> tuple[OpcodeDefinition, ...]:
    field_parameter = _parameter_schema(
        properties={"field": {"type": "string"}},
        required=("field",),
    )
    predicate_parameter = _parameter_schema(
        properties={
            "field": {"type": "string"},
            "value": {},
        },
        required=("field", "value"),
    )
    max_repeat_parameter = _parameter_schema(
        properties={"max_repeats": {"minimum": 1, "type": "integer"}},
        required=("max_repeats",),
    )
    return (
        OpcodeDefinition(
            "DERIVE_STATE_FIELD",
            "ARC3",
            ("State",),
            "Sequence",
            "Return a one-item sequence containing the exact named state field.",
            parameter_schema=field_parameter,
            preconditions=("field exists",),
        ),
        OpcodeDefinition(
            "TRACK_ENTITY",
            "ARC3",
            ("State", "Scalar"),
            "ObjectCandidate",
            "Return the indexed entry from state.entities without fallback.",
            preconditions=("state.entities exists and index is in bounds",),
            selector_cardinality="EXACTLY_ONE",
        ),
        OpcodeDefinition(
            "MATCH_ACTION_ID",
            "ARC3",
            ("ActionRecord", "Scalar"),
            "Boolean",
            "Compare the raw action ID exactly.",
        ),
        OpcodeDefinition(
            "MATCH_ACTION_PAYLOAD",
            "ARC3",
            ("ActionRecord", "State"),
            "Boolean",
            "Require every predicate key/value to match the action payload.",
        ),
        OpcodeDefinition(
            "PRECONDITION",
            "ARC3",
            ("Boolean",),
            "Boolean",
            "Return true or raise IR_PRECONDITION_UNSATISFIED.",
            invalid_operation_semantics="IR_PRECONDITION_UNSATISFIED",
            preconditions=("input is true",),
        ),
        OpcodeDefinition(
            "PREDICT_EFFECT",
            "ARC3",
            ("State", "Effect"),
            "State",
            "Apply effect.changes when effect.delay is zero.",
            preconditions=("effect delay is zero",),
        ),
        OpcodeDefinition(
            "PREDICT_TRANSITION",
            "ARC3",
            ("State", "ActionRecord"),
            "State",
            "Apply action payload.set to a copy of state.",
        ),
        OpcodeDefinition(
            "DELAYED_EFFECT",
            "ARC3",
            ("Effect", "Scalar"),
            "Effect",
            "Return the effect with a non-negative explicit delay.",
        ),
        OpcodeDefinition(
            "GOAL_PREDICATE",
            "ARC3",
            ("State",),
            "Boolean",
            "Compare one named state field with an explicit value.",
            parameter_schema=predicate_parameter,
        ),
        OpcodeDefinition(
            "HAZARD_PREDICATE",
            "ARC3",
            ("State",),
            "Boolean",
            "Compare one named state field with an explicit hazard value.",
            parameter_schema=predicate_parameter,
        ),
        OpcodeDefinition(
            "ORDER_BEFORE",
            "ARC3",
            ("Event", "Event"),
            "Boolean",
            "Compare event step indices using strict less-than.",
        ),
        OpcodeDefinition(
            "ORDER_ADJACENT",
            "ARC3",
            ("Event", "Event"),
            "Boolean",
            "Return true only when the second event is exactly one step later.",
        ),
        OpcodeDefinition(
            "REPEAT_N",
            "ARC3",
            ("Sequence", "Scalar"),
            "Sequence",
            "Concatenate the ordered sequence a non-negative number of times.",
        ),
        OpcodeDefinition(
            "REPEAT_UNTIL_OBSERVED",
            "ARC3",
            ("Sequence", "Boolean"),
            "Sequence",
            "Return the sequence only when the observation predicate is true.",
            parameter_schema=max_repeat_parameter,
            preconditions=("observation predicate is true",),
        ),
        OpcodeDefinition(
            "RESET_EFFECT",
            "ARC3",
            ("State",),
            "State",
            "Return state.initial_state exactly and reject if absent.",
            preconditions=("state.initial_state exists and is a State",),
        ),
        OpcodeDefinition(
            "TERMINAL_CONTRIBUTION",
            "ARC3",
            ("State", "TerminalState"),
            "Scalar",
            "Read state.terminal_contribution for the terminal-state key.",
        ),
        OpcodeDefinition(
            "INVARIANT",
            "ARC3",
            ("State", "State"),
            "Boolean",
            "Require every key/value in the second state to match the first.",
        ),
        OpcodeDefinition(
            "EXCLUSION",
            "ARC3",
            ("State", "State"),
            "Boolean",
            "Return true when no key has the same value in both states.",
        ),
    )


ARC2_DEFINITIONS: Final = _arc2_definitions()
ARC3_DEFINITIONS: Final = _arc3_definitions()

if tuple(item.opcode for item in ARC2_DEFINITIONS) != ARC2_OPCODE_NAMES:
    raise AssertionError("D02C_INTERNAL_ARC2_OPCODE_ORDER_DRIFT")
if tuple(item.opcode for item in ARC3_DEFINITIONS) != ARC3_OPCODE_NAMES:
    raise AssertionError("D02C_INTERNAL_ARC3_OPCODE_ORDER_DRIFT")


def definitions_for_domain(domain: str) -> tuple[OpcodeDefinition, ...]:
    if domain == "ARC2":
        return ARC2_DEFINITIONS
    if domain == "ARC3":
        return ARC3_DEFINITIONS
    fail("IR_UNKNOWN_OPCODE", "DOMAIN:" + domain)


def definition_by_opcode(domain: str, opcode: str) -> OpcodeDefinition:
    for definition in definitions_for_domain(domain):
        if definition.opcode == opcode:
            return definition
    fail("IR_UNKNOWN_OPCODE", domain + ":" + opcode)


def _validate_entry(entry: Mapping[str, object]) -> None:
    required = {
        "canonicalization_rule",
        "commutes_with",
        "content_digest",
        "deterministic",
        "domain",
        "execution_semantics",
        "input_types",
        "invalid_operation_semantics",
        "opcode",
        "opcode_version",
        "output_type",
        "parameter_schema",
        "preconditions",
        "resource_cost",
        "selector_cardinality",
        "side_effect_free",
        "test_vector_refs",
    }
    if set(entry) != required:
        fail("IR_INVALID_OPERATION", "OPERATOR_ENTRY_FIELDS")
    input_types = entry["input_types"]
    if not isinstance(input_types, list) or any(
        item not in COMMON_TYPE_NAMES for item in input_types
    ):
        fail("IR_TYPE_ERROR", "OPERATOR_INPUT_TYPES")
    if entry["output_type"] not in COMMON_TYPE_NAMES:
        fail("IR_TYPE_ERROR", "OPERATOR_OUTPUT_TYPE")
    if entry["selector_cardinality"] not in CARDINALITY_VALUES:
        fail("IR_CARDINALITY_ERROR", "REGISTRY")
    if entry["deterministic"] is not True or entry["side_effect_free"] is not True:
        fail("IR_INVALID_OPERATION", "NON_PURE_OPERATOR")
    test_vector_refs = entry["test_vector_refs"]
    if not isinstance(test_vector_refs, list) or not test_vector_refs:
        fail("IR_INVALID_OPERATION", "MISSING_TEST_VECTOR")
    body = dict(entry)
    claimed = body.pop("content_digest")
    expected = logical_content_digest(
        "hds-operator-entry",
        cast(Mapping[str, object], body),
        policy=DigestExclusionPolicy(),
    )
    if claimed != expected:
        fail("IR_INVALID_OPERATION", "OPERATOR_ENTRY_DIGEST")


def build_operator_registry(domain: str) -> JsonObject:
    definitions = definitions_for_domain(domain)
    registry_version = (
        ARC2_REGISTRY_VERSION if domain == "ARC2" else ARC3_REGISTRY_VERSION
    )
    artifact: JsonObject = {
        "schema_version": OPERATOR_REGISTRY_SCHEMA_VERSION,
        "operator_registry_id": "",
        "registry_version": registry_version,
        "domain": domain,
        "dependency_lock_ref": SYNTHETIC_DEPENDENCY_LOCK_REF,
        "entries": [definition.as_json() for definition in definitions],
        "digest_excluded_fields": [
            "content_digest",
            "operator_registry_id",
        ],
        "content_digest": "",
    }
    policy = DigestExclusionPolicy(
        id_fields=frozenset({"operator_registry_id"}),
        digest_fields=frozenset({"content_digest"}),
    )
    artifact["operator_registry_id"] = content_derived_id(
        "hds-operator-registry-id",
        artifact,
        policy=policy,
    )
    artifact["content_digest"] = logical_content_digest(
        "hds-operator-registry",
        artifact,
        policy=policy,
    )
    validate_operator_registry(artifact)
    return artifact


def validate_operator_registry(artifact: Mapping[str, object]) -> None:
    domain = artifact.get("domain")
    if domain not in {"ARC2", "ARC3"}:
        fail("IR_UNKNOWN_OPCODE", "REGISTRY_DOMAIN")
    entries = artifact.get("entries")
    if not isinstance(entries, list):
        fail("IR_INVALID_OPERATION", "REGISTRY_ENTRIES")
    expected_names = ARC2_OPCODE_NAMES if domain == "ARC2" else ARC3_OPCODE_NAMES
    names: list[str] = []
    by_name: dict[str, Mapping[str, object]] = {}
    for raw in entries:
        if not isinstance(raw, Mapping):
            fail("IR_INVALID_OPERATION", "REGISTRY_ENTRY")
        entry = cast(Mapping[str, object], raw)
        _validate_entry(entry)
        name = entry.get("opcode")
        if not isinstance(name, str):
            fail("IR_UNKNOWN_OPCODE", "REGISTRY_ENTRY_NAME")
        names.append(name)
        by_name[name] = entry
    if tuple(names) != expected_names or len(by_name) != len(names):
        fail("IR_UNKNOWN_OPCODE", "REGISTRY_INVENTORY")
    for name, entry in by_name.items():
        commutes = entry["commutes_with"]
        if not isinstance(commutes, list):
            fail("IR_INVALID_OPERATION", "COMMUTES_TYPE")
        for partner in commutes:
            if not isinstance(partner, str) or partner not in by_name:
                fail("IR_UNKNOWN_OPCODE", "COMMUTES:" + name)
            reverse = by_name[partner]["commutes_with"]
            if not isinstance(reverse, list) or name not in reverse:
                fail("IR_INVALID_OPERATION", "COMMUTES_ASYMMETRIC:" + name)
    body = dict(artifact)
    claimed_digest = body.pop("content_digest", None)
    body.pop("operator_registry_id", None)
    expected_digest = logical_content_digest(
        "hds-operator-registry",
        cast(Mapping[str, object], body),
        policy=DigestExclusionPolicy(),
    )
    if claimed_digest != expected_digest:
        fail("IR_INVALID_OPERATION", "REGISTRY_DIGEST")


def registry_digest_for_domain(domain: str) -> str:
    return cast(str, build_operator_registry(domain)["content_digest"])


__all__ = [
    "ARC2_DEFINITIONS",
    "ARC2_OPCODE_NAMES",
    "ARC3_DEFINITIONS",
    "ARC3_OPCODE_NAMES",
    "IRContractError",
    "OpcodeDefinition",
    "build_operator_registry",
    "definition_by_opcode",
    "definitions_for_domain",
    "registry_digest_for_domain",
    "validate_operator_registry",
]
