"""PH-D02C executable HypothesisIR contract and static verifier."""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, cast

from .canonical import (
    CANONICAL_JSON_VERSION,
    DigestExclusionPolicy,
    JsonValue,
    content_derived_id,
    logical_content_digest,
)
from .ir_types import (
    COMMON_TYPE_NAMES,
    JsonObject,
    build_type_system_artifact,
    fail,
    validate_typed_value,
)
from .operator_registry import (
    ARC2_OPCODE_NAMES,
    ARC3_OPCODE_NAMES,
    NO_PARAMETERS,
    OPCODE_VERSION,
    build_operator_registry,
    definition_by_opcode,
)
from .post_audit_causal_ir_schema import (
    EXPECTED_SCHEMA_CONTRACT_DIGEST,
    PH_D02B_CONTRACT_DIGEST,
    PH_D02B_EVIDENCE_PAYLOAD_DIGEST,
    PH_D02B_PHASE_STATE_SHA256,
    PH_D02C_ENTRY_APPROVAL_DIGEST,
    PH_D02C_FRAME_DIGEST,
)

EXECUTABLE_IR_VERSION: Final = "hds-executable-causal-ir-v2"
INTERPRETER_VERSION: Final = "hds-causal-ir-interpreter-v2"
IR_SCHEMA_VERSION: Final = "hds-causal-ir-v2"
IR_CONTRACT_VERSION: Final = "hds-causal-ir-contract-v2"
IR_ABI_VERSION: Final = "hds-code-ir-abi-v2"
RESOURCE_COST_MODEL_VERSION: Final = "hds-resource-cost-model-v1"
DEFAULT_STEP_LIMIT: Final = 100_000
IR_SCHEMA_CONTRACT_DIGEST: Final = EXPECTED_SCHEMA_CONTRACT_DIGEST

SYNTHETIC_FRAME_REF: Final = (
    "hds-distillation-frame-id:"
    "cbcf5acc43204bb05983546f0574f9e6f0b7303a1db217dff3f3c9164419a501"
)

NODE_ID_RE: Final = re.compile(r"^[a-z][a-z0-9_]{0,63}$")
DIGEST_RE: Final = re.compile(r"^[a-z][a-z0-9-]*:[0-9a-f]{64}$")

ALLOWED_CLAIM_SCOPES: Final = (
    "PREDICTIVE_HYPOTHESIS",
    "COUNTERFACTUAL_CANDIDATE",
)

IDENTITY_ROUTING_KEYS: Final = frozenset(
    {
        "case_id",
        "full_input_digest",
        "full_input_digest_lookup",
        "game_id",
        "input_digest_lookup",
        "level_id",
        "replay_index",
        "replay_route",
        "source_filename",
        "source_path_route",
        "task_id",
        "trajectory_lookup",
    }
)

ANSWER_COPY_KEYS: Final = frozenset(
    {
        "answer",
        "answer_grid",
        "answer_map",
        "expected_output",
        "fixed_action_sequence",
        "full_answer_grid",
        "full_answer_literal",
        "output_coordinate_table",
        "output_coordinates",
        "output_grid",
        "successful_action_sequence",
        "target_grid",
    }
)

INPUT_PROVENANCE_VALUES: Final = (
    "OBSERVED",
    "DETERMINISTIC_DERIVATION",
    "GENERAL_RULE_CONSTANT",
)


@dataclass(frozen=True, slots=True)
class TypedInput:
    name: str
    type_name: str
    value: JsonValue
    provenance: str

    def as_json(self) -> JsonObject:
        return {
            "name": self.name,
            "provenance": self.provenance,
            "type": self.type_name,
            "value": self.value,
        }


@dataclass(frozen=True, slots=True)
class IRNode:
    node_id: str
    opcode: str
    input_refs: tuple[str, ...]
    parameters: JsonObject
    declared_output_type: str
    opcode_version: str = OPCODE_VERSION

    def as_json(self) -> JsonObject:
        return {
            "declared_output_type": self.declared_output_type,
            "input_refs": list(self.input_refs),
            "node_id": self.node_id,
            "opcode": self.opcode,
            "opcode_version": self.opcode_version,
            "parameters": self.parameters,
        }


@dataclass(frozen=True, slots=True)
class TypeCheckedProgram:
    domain: str
    inputs: tuple[TypedInput, ...]
    nodes: tuple[IRNode, ...]
    output_refs: tuple[str, ...]
    reference_types: Mapping[str, str]
    resource_cost: int
    resource_limit: int
    source: JsonObject


def _resource_policy() -> DigestExclusionPolicy:
    return DigestExclusionPolicy(
        id_fields=frozenset({"resource_cost_model_id"}),
        digest_fields=frozenset({"content_digest"}),
    )


def build_resource_cost_model() -> JsonObject:
    artifact: JsonObject = {
        "schema_version": RESOURCE_COST_MODEL_VERSION,
        "resource_cost_model_id": "",
        "interpreter_step_limit": DEFAULT_STEP_LIMIT,
        "cost_unit": "DECLARED_OPCODE_STEP",
        "overflow_assertion_state": "SUSPEND",
        "overflow_operation_state": "HOLD",
        "overflow_evidence_state": "INCONCLUSIVE",
        "overflow_reason_code": "SUSPEND_RESOURCE",
        "digest_excluded_fields": [
            "content_digest",
            "resource_cost_model_id",
        ],
        "content_digest": "",
    }
    artifact["resource_cost_model_id"] = content_derived_id(
        "hds-resource-cost-model-id",
        artifact,
        policy=_resource_policy(),
    )
    artifact["content_digest"] = logical_content_digest(
        "hds-resource-cost-model",
        artifact,
        policy=_resource_policy(),
    )
    return artifact


def build_code_ir_abi(domain: str) -> JsonObject:
    registry = build_operator_registry(domain)
    type_system = build_type_system_artifact()
    resource_model = build_resource_cost_model()
    return {
        "schema_version": IR_ABI_VERSION,
        "interpreter_version": INTERPRETER_VERSION,
        "interpreter_contract_digest": logical_content_digest(
            "hds-causal-ir-interpreter-contract",
            {
                "interpreter_version": INTERPRETER_VERSION,
                "execution_model": "PURE_REGISTERED_BUILTINS_IN_DECLARED_ORDER",
                "resource_overflow": "SUSPEND_RESOURCE",
            },
            policy=DigestExclusionPolicy(),
        ),
        "ir_schema_version": IR_SCHEMA_VERSION,
        "ir_schema_contract_digest": IR_SCHEMA_CONTRACT_DIGEST,
        "opcode_registry_digest": registry["content_digest"],
        "type_system_digest": type_system["content_digest"],
        "resource_cost_model_digest": resource_model["content_digest"],
        "serialization_version": CANONICAL_JSON_VERSION,
    }


def _abi_digest(domain: str) -> str:
    return logical_content_digest(
        "hds-code-ir-abi",
        build_code_ir_abi(domain),
        policy=DigestExclusionPolicy(),
    )


def build_abi_artifact() -> JsonObject:
    artifact: JsonObject = {
        "schema_version": IR_ABI_VERSION,
        "abi_id": "HDS-PH-D02C-CODE-IR-ABI-V1",
        "domain_abis": {
            domain: {
                **build_code_ir_abi(domain),
                "abi_digest": _abi_digest(domain),
            }
            for domain in ("ARC2", "ARC3")
        },
        "mismatch_policy": "IR_ABI_MISMATCH",
        "digest_excluded_fields": ["content_digest", "abi_id"],
        "content_digest": "",
    }
    artifact["content_digest"] = logical_content_digest(
        "hds-code-ir-abi-artifact",
        artifact,
        policy=DigestExclusionPolicy(
            id_fields=frozenset({"abi_id"}),
            digest_fields=frozenset({"content_digest"}),
        ),
    )
    return artifact


def verify_abi(domain: str, supplied: Mapping[str, object]) -> None:
    expected = build_code_ir_abi(domain)
    if dict(supplied) != expected:
        fail("IR_ABI_MISMATCH", domain)


def _walk_forbidden(value: object, path: tuple[str, ...] = ()) -> None:
    if isinstance(value, Mapping):
        for raw_key, item in value.items():
            if not isinstance(raw_key, str):
                fail("IR_IDENTITY_ROUTING_FORBIDDEN", "NON_STRING_KEY")
            key = raw_key.casefold()
            pointer = "/".join(path + (raw_key,))
            if key in IDENTITY_ROUTING_KEYS:
                fail("IR_IDENTITY_ROUTING_FORBIDDEN", pointer)
            if key in ANSWER_COPY_KEYS:
                fail("IR_ANSWER_COPY_FORBIDDEN", pointer)
            _walk_forbidden(item, path + (raw_key,))
        return
    if isinstance(value, list | tuple):
        for index, item in enumerate(value):
            _walk_forbidden(item, path + (str(index),))


def lint_privileged_structure(program: Mapping[str, object]) -> None:
    _walk_forbidden(program)
    inputs = program.get("inputs")
    if not isinstance(inputs, list):
        fail("IR_TYPE_ERROR", "INPUTS")
    for raw in inputs:
        if not isinstance(raw, Mapping):
            fail("IR_TYPE_ERROR", "INPUT")
        name = raw.get("name")
        type_name = raw.get("type")
        value = raw.get("value")
        provenance = raw.get("provenance")
        if (
            isinstance(name, str)
            and "action" in name.casefold()
            and "sequence" in name.casefold()
        ):
            fail("IR_ANSWER_COPY_FORBIDDEN", "INPUT:" + name)
        if type_name == "Grid" and provenance == "GENERAL_RULE_CONSTANT":
            fail("IR_ANSWER_COPY_FORBIDDEN", "CONSTANT_GRID")
        if (
            type_name == "Sequence"
            and provenance == "GENERAL_RULE_CONSTANT"
            and isinstance(value, list)
            and len(value) > 1
            and all(type(item) is int and 0 <= item <= 7 for item in value)
        ):
            fail("IR_ANSWER_COPY_FORBIDDEN", "CONSTANT_ACTION_SEQUENCE")
    claim_scope = program.get("claim_scope")
    if claim_scope not in ALLOWED_CLAIM_SCOPES:
        fail("IR_CAUSAL_OVERCLAIM", str(claim_scope))


def _validate_parameter_value(schema: Mapping[str, object], value: object) -> None:
    expected_type = schema.get("type")
    if expected_type == "integer":
        if type(value) is not int:
            fail("IR_INVALID_OPERATION", "PARAMETER_TYPE")
        minimum = schema.get("minimum")
        maximum = schema.get("maximum")
        if isinstance(minimum, int) and value < minimum:
            fail("IR_INVALID_OPERATION", "PARAMETER_MINIMUM")
        if isinstance(maximum, int) and value > maximum:
            fail("IR_INVALID_OPERATION", "PARAMETER_MAXIMUM")
    elif expected_type == "string":
        if not isinstance(value, str):
            fail("IR_INVALID_OPERATION", "PARAMETER_TYPE")
    elif expected_type == "array":
        if not isinstance(value, list):
            fail("IR_INVALID_OPERATION", "PARAMETER_TYPE")
        minimum_items = schema.get("minItems")
        if isinstance(minimum_items, int) and len(value) < minimum_items:
            fail("IR_INVALID_OPERATION", "PARAMETER_MIN_ITEMS")
        if schema.get("uniqueItems") is True:
            encoded = [repr(item) for item in value]
            if len(encoded) != len(set(encoded)):
                fail("IR_INVALID_OPERATION", "PARAMETER_DUPLICATE")
        item_schema = schema.get("items")
        if isinstance(item_schema, Mapping):
            for item in value:
                _validate_parameter_value(
                    cast(Mapping[str, object], item_schema),
                    item,
                )
    enum = schema.get("enum")
    if isinstance(enum, list) and value not in enum:
        fail("IR_INVALID_OPERATION", "PARAMETER_ENUM")


def validate_parameters(
    schema: Mapping[str, object],
    parameters: Mapping[str, object],
) -> None:
    if schema.get("type") != "object":
        fail("IR_INVALID_OPERATION", "PARAMETER_SCHEMA")
    properties = schema.get("properties")
    required = schema.get("required")
    if not isinstance(properties, Mapping) or not isinstance(required, list):
        fail("IR_INVALID_OPERATION", "PARAMETER_SCHEMA")
    if any(not isinstance(item, str) for item in required):
        fail("IR_INVALID_OPERATION", "PARAMETER_SCHEMA")
    missing = set(cast(list[str], required)) - set(parameters)
    if missing:
        fail("IR_INVALID_OPERATION", "PARAMETER_REQUIRED:" + sorted(missing)[0])
    if schema.get("additionalProperties") is False:
        unknown = set(parameters) - set(properties)
        if unknown:
            fail("IR_INVALID_OPERATION", "PARAMETER_UNKNOWN:" + sorted(unknown)[0])
    for name, value in parameters.items():
        child = properties.get(name)
        if isinstance(child, Mapping):
            _validate_parameter_value(cast(Mapping[str, object], child), value)


def _parse_input(raw: object) -> TypedInput:
    if not isinstance(raw, Mapping):
        fail("IR_TYPE_ERROR", "INPUT")
    required = {"name", "type", "value", "provenance"}
    if set(raw) != required:
        fail("IR_TYPE_ERROR", "INPUT_FIELDS")
    name = raw["name"]
    type_name = raw["type"]
    provenance = raw["provenance"]
    if not isinstance(name, str) or not NODE_ID_RE.fullmatch(name):
        fail("IR_TYPE_ERROR", "INPUT_NAME")
    if not isinstance(type_name, str) or type_name not in COMMON_TYPE_NAMES:
        fail("IR_TYPE_ERROR", "INPUT_TYPE")
    if provenance not in INPUT_PROVENANCE_VALUES:
        fail("IR_TYPE_ERROR", "INPUT_PROVENANCE")
    value = validate_typed_value(type_name, raw["value"])
    return TypedInput(name, type_name, value, cast(str, provenance))


def _parse_node(raw: object) -> IRNode:
    if not isinstance(raw, Mapping):
        fail("IR_TYPE_ERROR", "NODE")
    required = {
        "declared_output_type",
        "input_refs",
        "node_id",
        "opcode",
        "opcode_version",
        "parameters",
    }
    if set(raw) != required:
        fail("IR_TYPE_ERROR", "NODE_FIELDS")
    node_id = raw["node_id"]
    opcode = raw["opcode"]
    opcode_version = raw["opcode_version"]
    output_type = raw["declared_output_type"]
    input_refs = raw["input_refs"]
    parameters = raw["parameters"]
    if not isinstance(node_id, str) or not NODE_ID_RE.fullmatch(node_id):
        fail("IR_TYPE_ERROR", "NODE_ID")
    if not isinstance(opcode, str) or not opcode:
        fail("IR_UNKNOWN_OPCODE", "NODE_OPCODE")
    if opcode_version != OPCODE_VERSION:
        fail("IR_UNKNOWN_OPCODE", opcode + ":VERSION")
    if not isinstance(output_type, str) or output_type not in COMMON_TYPE_NAMES:
        fail("IR_TYPE_ERROR", "NODE_OUTPUT_TYPE")
    if not isinstance(input_refs, list) or any(
        not isinstance(item, str) for item in input_refs
    ):
        fail("IR_TYPE_ERROR", "NODE_INPUT_REFS")
    if not isinstance(parameters, Mapping):
        fail("IR_INVALID_OPERATION", "NODE_PARAMETERS")
    return IRNode(
        node_id=node_id,
        opcode=opcode,
        input_refs=tuple(cast(list[str], input_refs)),
        parameters=cast(JsonObject, dict(parameters)),
        declared_output_type=output_type,
        opcode_version=cast(str, opcode_version),
    )


def _program_policy() -> DigestExclusionPolicy:
    return DigestExclusionPolicy(
        id_fields=frozenset({"hypothesis_ir_id"}),
        digest_fields=frozenset({"content_digest"}),
    )


def type_check_program(program: Mapping[str, object]) -> TypeCheckedProgram:
    lint_privileged_structure(program)
    expected_fields = {
        "abi",
        "claim_scope",
        "content_digest",
        "digest_excluded_fields",
        "domain",
        "exclusions",
        "falsification_procedures",
        "frame_ref",
        "hypothesis_ir_id",
        "input_types",
        "inputs",
        "invariants",
        "ir_version",
        "operator_graph",
        "operator_registry_ref",
        "ordering_constraints",
        "output_refs",
        "preconditions",
        "predicted_effects",
        "resource_cost",
        "resource_limit",
        "schema_version",
        "selector_graph",
        "stop_conditions",
    }
    if set(program) != expected_fields:
        fail("IR_TYPE_ERROR", "PROGRAM_FIELDS")
    if program.get("schema_version") != IR_SCHEMA_VERSION:
        fail("IR_TYPE_ERROR", "SCHEMA_VERSION")
    if program.get("ir_version") != EXECUTABLE_IR_VERSION:
        fail("IR_TYPE_ERROR", "IR_VERSION")
    domain = program.get("domain")
    if domain not in {"ARC2", "ARC3"}:
        fail("IR_UNKNOWN_OPCODE", "DOMAIN")
    abi = program.get("abi")
    if not isinstance(abi, Mapping):
        fail("IR_ABI_MISMATCH", "MISSING")
    verify_abi(cast(str, domain), cast(Mapping[str, object], abi))
    expected_registry = build_operator_registry(cast(str, domain))
    if (
        program.get("operator_registry_ref")
        != expected_registry["operator_registry_id"]
    ):
        fail("IR_ABI_MISMATCH", "REGISTRY_REF")
    if program.get("frame_ref") != SYNTHETIC_FRAME_REF:
        fail("IR_IDENTITY_ROUTING_FORBIDDEN", "UNBOUND_FRAME")
    raw_inputs = program.get("inputs")
    if not isinstance(raw_inputs, list):
        fail("IR_TYPE_ERROR", "INPUTS")
    inputs = tuple(_parse_input(item) for item in raw_inputs)
    if not inputs:
        fail("IR_TYPE_ERROR", "INPUTS_EMPTY")
    if len({item.name for item in inputs}) != len(inputs):
        fail("IR_TYPE_ERROR", "DUPLICATE_INPUT")
    declared_input_types = program.get("input_types")
    expected_input_types = list(dict.fromkeys(item.type_name for item in inputs))
    if (
        not isinstance(declared_input_types, list)
        or declared_input_types != expected_input_types
    ):
        fail("IR_TYPE_ERROR", "INPUT_TYPE_DECLARATION")
    graph_fields = ("selector_graph", "preconditions", "operator_graph")
    nodes: list[IRNode] = []
    for graph_field in graph_fields:
        graph = program.get(graph_field)
        if not isinstance(graph, list):
            fail("IR_TYPE_ERROR", graph_field.upper())
        nodes.extend(_parse_node(item) for item in graph)
    if not nodes:
        fail("IR_TYPE_ERROR", "NODE_GRAPH_EMPTY")
    reference_types: dict[str, str] = {item.name: item.type_name for item in inputs}
    resource_cost = 0
    for node in nodes:
        if node.node_id in reference_types:
            fail("IR_TYPE_ERROR", "DUPLICATE_REFERENCE:" + node.node_id)
        definition = definition_by_opcode(cast(str, domain), node.opcode)
        if node.opcode_version != OPCODE_VERSION:
            fail("IR_UNKNOWN_OPCODE", node.opcode + ":VERSION")
        if len(node.input_refs) != len(definition.input_types):
            fail("IR_TYPE_ERROR", node.node_id + ":ARITY")
        actual_types: list[str] = []
        for reference in node.input_refs:
            if reference not in reference_types:
                fail("IR_TYPE_ERROR", node.node_id + ":FORWARD_REF:" + reference)
            actual_types.append(reference_types[reference])
        if tuple(actual_types) != definition.input_types:
            fail("IR_TYPE_ERROR", node.node_id + ":INPUT_TYPES")
        if node.declared_output_type != definition.output_type:
            fail("IR_TYPE_ERROR", node.node_id + ":OUTPUT_TYPE")
        validate_parameters(
            cast(
                Mapping[str, object],
                definition.parameter_schema or NO_PARAMETERS,
            ),
            cast(Mapping[str, object], node.parameters),
        )
        reference_types[node.node_id] = definition.output_type
        resource_cost += definition.resource_cost
    output_refs = program.get("output_refs")
    if (
        not isinstance(output_refs, list)
        or not output_refs
        or any(
            not isinstance(item, str) or item not in reference_types
            for item in output_refs
        )
    ):
        fail("IR_TYPE_ERROR", "OUTPUT_REFS")
    ordering = program.get("ordering_constraints")
    expected_ordering = [
        {"before": left.node_id, "after": right.node_id}
        for left, right in zip(nodes, nodes[1:], strict=False)
    ]
    if ordering != expected_ordering:
        fail("IR_INVALID_OPERATION", "OPERATOR_ORDER")
    declared_cost = program.get("resource_cost")
    resource_limit = program.get("resource_limit")
    if type(declared_cost) is not int or declared_cost != resource_cost:
        fail("IR_INVALID_OPERATION", "RESOURCE_COST_DECLARATION")
    if type(resource_limit) is not int or resource_limit < 1:
        fail("IR_INVALID_OPERATION", "RESOURCE_LIMIT")
    if resource_limit > DEFAULT_STEP_LIMIT:
        fail("IR_INVALID_OPERATION", "RESOURCE_LIMIT_ABOVE_PROFILE")
    policy = _program_policy()
    expected_id = content_derived_id(
        "hds-hypothesis-i-r-id",
        program,
        policy=policy,
    )
    expected_digest = logical_content_digest(
        "hds-hypothesis-ir",
        program,
        policy=policy,
    )
    if program.get("hypothesis_ir_id") != expected_id:
        fail("IR_INVALID_OPERATION", "PROGRAM_ID")
    if program.get("content_digest") != expected_digest:
        fail("IR_INVALID_OPERATION", "PROGRAM_DIGEST")
    if program.get("digest_excluded_fields") != [
        "content_digest",
        "hypothesis_ir_id",
    ]:
        fail("IR_INVALID_OPERATION", "PROGRAM_DIGEST_EXCLUSIONS")
    return TypeCheckedProgram(
        domain=cast(str, domain),
        inputs=inputs,
        nodes=tuple(nodes),
        output_refs=tuple(cast(list[str], output_refs)),
        reference_types=reference_types,
        resource_cost=resource_cost,
        resource_limit=resource_limit,
        source=cast(JsonObject, dict(program)),
    )


def build_program(
    *,
    domain: str,
    inputs: Sequence[TypedInput],
    selector_nodes: Sequence[IRNode] = (),
    precondition_nodes: Sequence[IRNode] = (),
    operator_nodes: Sequence[IRNode],
    output_refs: Sequence[str],
    claim_scope: str = "PREDICTIVE_HYPOTHESIS",
    resource_limit: int = DEFAULT_STEP_LIMIT,
) -> JsonObject:
    nodes = [*selector_nodes, *precondition_nodes, *operator_nodes]
    resource_cost = sum(
        definition_by_opcode(domain, node.opcode).resource_cost for node in nodes
    )
    registry = build_operator_registry(domain)
    program: JsonObject = {
        "schema_version": IR_SCHEMA_VERSION,
        "hypothesis_ir_id": "",
        "ir_version": EXECUTABLE_IR_VERSION,
        "domain": domain,
        "frame_ref": SYNTHETIC_FRAME_REF,
        "operator_registry_ref": registry["operator_registry_id"],
        "abi": build_code_ir_abi(domain),
        "claim_scope": claim_scope,
        "inputs": [item.as_json() for item in inputs],
        "input_types": list(dict.fromkeys(item.type_name for item in inputs)),
        "selector_graph": [item.as_json() for item in selector_nodes],
        "preconditions": [item.as_json() for item in precondition_nodes],
        "operator_graph": [item.as_json() for item in operator_nodes],
        "ordering_constraints": [
            {"after": right.node_id, "before": left.node_id}
            for left, right in zip(nodes, nodes[1:], strict=False)
        ],
        "stop_conditions": [],
        "predicted_effects": [{"output_ref": reference} for reference in output_refs],
        "invariants": [],
        "exclusions": [],
        "falsification_procedures": [],
        "output_refs": list(output_refs),
        "resource_cost": resource_cost,
        "resource_limit": resource_limit,
        "digest_excluded_fields": [
            "content_digest",
            "hypothesis_ir_id",
        ],
        "content_digest": "",
    }
    policy = _program_policy()
    program["hypothesis_ir_id"] = content_derived_id(
        "hds-hypothesis-i-r-id",
        program,
        policy=policy,
    )
    program["content_digest"] = logical_content_digest(
        "hds-hypothesis-ir",
        program,
        policy=policy,
    )
    type_check_program(program)
    return program


def build_causal_ir_contract() -> JsonObject:
    type_system = build_type_system_artifact()
    arc2_registry = build_operator_registry("ARC2")
    arc3_registry = build_operator_registry("ARC3")
    resource_model = build_resource_cost_model()
    abi_artifact = build_abi_artifact()
    contract: JsonObject = {
        "schema_version": IR_CONTRACT_VERSION,
        "contract_id": "HDS-PH-D02C-CAUSAL-IR-CONTRACT-V2",
        "phase_id": "PH-D02C",
        "authority": {
            "canonical_contract_digest": (
                "hds-canonicalization-contract:"
                "8ef686f3e30c2c773dff47637c9bb0d57dbb175d4fc6b7bd1c46a7820cf4068f"
            ),
            "ph_d02b_schema_contract_digest": PH_D02B_CONTRACT_DIGEST,
            "ph_d02b_evidence_payload_digest": (
                PH_D02B_EVIDENCE_PAYLOAD_DIGEST
            ),
            "ph_d02b_phase_state_sha256": (
                "sha256:" + PH_D02B_PHASE_STATE_SHA256
            ),
            "ph_d02c_entry_approval_digest": PH_D02C_ENTRY_APPROVAL_DIGEST,
            "schema_refinement_contract_digest": IR_SCHEMA_CONTRACT_DIGEST,
            "work_block_frame_digest": PH_D02C_FRAME_DIGEST,
        },
        "gates": ["DG-03", "DG-08", "DG-09", "DG-12"],
        "type_system_digest": type_system["content_digest"],
        "arc2_operator_registry_digest": arc2_registry["content_digest"],
        "arc3_operator_registry_digest": arc3_registry["content_digest"],
        "resource_cost_model_digest": resource_model["content_digest"],
        "code_ir_abi_digest": abi_artifact["content_digest"],
        "common_types": list(COMMON_TYPE_NAMES),
        "arc2_opcodes": list(ARC2_OPCODE_NAMES),
        "arc3_opcodes": list(ARC3_OPCODE_NAMES),
        "error_codes": [
            "IR_TYPE_ERROR",
            "IR_UNKNOWN_OPCODE",
            "IR_PRECONDITION_UNSATISFIED",
            "IR_INVALID_OPERATION",
            "IR_CARDINALITY_ERROR",
            "IR_ABI_MISMATCH",
            "IR_IDENTITY_ROUTING_FORBIDDEN",
            "IR_ANSWER_COPY_FORBIDDEN",
            "IR_CAUSAL_OVERCLAIM",
            "SUSPEND_RESOURCE",
        ],
        "phase_boundaries": {
            "candidate_generation_started": False,
            "causal_mechanism_assertion_count": 0,
            "golden_freeze_started": False,
            "kaggle_mutation_count": 0,
            "locked_final_access_count": 0,
            "official_access_count": 0,
            "real_intervention_execution_count": 0,
            "real_trajectory_normalization_count": 0,
            "rule_promotion_count": 0,
            "sealed_corpus_started": False,
            "source_payload_read_count": 0,
        },
        "digest_excluded_fields": ["content_digest", "contract_id"],
        "content_digest": "",
    }
    contract["content_digest"] = logical_content_digest(
        "hds-causal-ir-contract",
        contract,
        policy=DigestExclusionPolicy(
            id_fields=frozenset({"contract_id"}),
            digest_fields=frozenset({"content_digest"}),
        ),
    )
    return contract


__all__ = [
    "ALLOWED_CLAIM_SCOPES",
    "DEFAULT_STEP_LIMIT",
    "EXECUTABLE_IR_VERSION",
    "INTERPRETER_VERSION",
    "IR_SCHEMA_CONTRACT_DIGEST",
    "IRNode",
    "SYNTHETIC_FRAME_REF",
    "TypeCheckedProgram",
    "TypedInput",
    "build_abi_artifact",
    "build_causal_ir_contract",
    "build_code_ir_abi",
    "build_program",
    "build_resource_cost_model",
    "lint_privileged_structure",
    "type_check_program",
    "validate_parameters",
    "verify_abi",
]
