"""PH-D02C exact comparison and bounded synthetic intervention interfaces."""

from __future__ import annotations

import copy
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, cast

from .canonical import (
    DigestExclusionPolicy,
    JsonValue,
    canonical_json_bytes,
    canonical_json_document_bytes,
    content_derived_id,
    logical_content_digest,
    verify_canonical_json_document_bytes,
)
from .causal_ir import (
    DEFAULT_STEP_LIMIT,
    IRNode,
    TypedInput,
    build_abi_artifact,
    build_causal_ir_contract,
    build_program,
    build_resource_cost_model,
    type_check_program,
)
from .interpreter import ExecutionResult, execute_program
from .ir_types import (
    IRContractError,
    JsonObject,
    build_type_system_artifact,
    fail,
    validate_typed_value,
)
from .operator_registry import (
    ARC2_DEFINITIONS,
    ARC3_DEFINITIONS,
    OpcodeDefinition,
    build_operator_registry,
    definition_by_opcode,
)
from .post_audit_causal_ir_schema import (
    build_post_audit_causal_ir_schema_artifacts,
)


@dataclass(frozen=True, slots=True)
class ExactComparison:
    equal: bool
    expected_digest: str
    actual_digest: str

    def as_json(self) -> JsonObject:
        return {
            "actual_digest": self.actual_digest,
            "equal": self.equal,
            "expected_digest": self.expected_digest,
        }


class ExactComparatorInterface(Protocol):
    def compare(
        self,
        *,
        type_name: str,
        expected: object,
        actual: object,
    ) -> ExactComparison: ...


class CanonicalExactComparator:
    """Compare typed canonical bytes with no tolerance or repair."""

    def compare(
        self,
        *,
        type_name: str,
        expected: object,
        actual: object,
    ) -> ExactComparison:
        expected_value = validate_typed_value(type_name, expected)
        actual_value = validate_typed_value(type_name, actual)
        expected_bytes = canonical_json_bytes(expected_value)
        actual_bytes = canonical_json_bytes(actual_value)
        return ExactComparison(
            equal=expected_bytes == actual_bytes,
            expected_digest=logical_content_digest(
                "hds-exact-comparator-value",
                {"type": type_name, "value": expected_value},
                policy=DigestExclusionPolicy(),
            ),
            actual_digest=logical_content_digest(
                "hds-exact-comparator-value",
                {"type": type_name, "value": actual_value},
                policy=DigestExclusionPolicy(),
            ),
        )


@dataclass(frozen=True, slots=True)
class SyntheticIntervention:
    input_name: str
    replacement_value: JsonValue


@dataclass(frozen=True, slots=True)
class SyntheticInterventionOutcome:
    baseline_result: ExecutionResult
    intervened_result: ExecutionResult
    changed_input_names: tuple[str, ...]
    execution_scope: str = "SYNTHETIC_ONLY"
    causal_claim: None = None

    def as_json(self) -> JsonObject:
        return {
            "baseline_result_digest": self.baseline_result.result_digest,
            "causal_claim": self.causal_claim,
            "changed_input_names": list(self.changed_input_names),
            "execution_scope": self.execution_scope,
            "intervened_result_digest": self.intervened_result.result_digest,
        }


class InterventionRunnerInterface(Protocol):
    def run(
        self,
        program: Mapping[str, object],
        interventions: Sequence[SyntheticIntervention],
    ) -> SyntheticInterventionOutcome: ...


def _rebind_program(program: JsonObject) -> JsonObject:
    policy = DigestExclusionPolicy(
        id_fields=frozenset({"hypothesis_ir_id"}),
        digest_fields=frozenset({"content_digest"}),
    )
    program["hypothesis_ir_id"] = ""
    program["content_digest"] = ""
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
    return program


class BoundedSyntheticInterventionRunner:
    """Replace declared synthetic inputs only, under a fixed intervention cap."""

    def __init__(self, *, intervention_budget: int = 8) -> None:
        if type(intervention_budget) is not int or intervention_budget < 1:
            fail("IR_INVALID_OPERATION", "INTERVENTION_BUDGET")
        self._intervention_budget = intervention_budget

    def run(
        self,
        program: Mapping[str, object],
        interventions: Sequence[SyntheticIntervention],
    ) -> SyntheticInterventionOutcome:
        if len(interventions) > self._intervention_budget:
            fail("SUSPEND_RESOURCE", "INTERVENTION_BUDGET")
        names = [item.input_name for item in interventions]
        if len(names) != len(set(names)):
            fail("IR_INVALID_OPERATION", "DUPLICATE_INTERVENTION")
        checked = type_check_program(program)
        by_name = {item.name: item for item in checked.inputs}
        for name in names:
            if name not in by_name:
                fail("IR_INVALID_OPERATION", "INTERVENTION_INPUT:" + name)
        baseline = execute_program(program)
        modified = cast(
            JsonObject,
            copy.deepcopy(dict(program)),
        )
        raw_inputs = modified["inputs"]
        if not isinstance(raw_inputs, list):
            fail("IR_TYPE_ERROR", "INPUTS")
        replacements = {
            item.input_name: item.replacement_value for item in interventions
        }
        for raw in raw_inputs:
            if not isinstance(raw, dict):
                fail("IR_TYPE_ERROR", "INPUT")
            raw_name = raw.get("name")
            if isinstance(raw_name, str) and raw_name in replacements:
                type_name = by_name[raw_name].type_name
                raw["value"] = validate_typed_value(
                    type_name,
                    replacements[raw_name],
                )
                raw["provenance"] = "OBSERVED"
        _rebind_program(modified)
        intervened = execute_program(modified)
        return SyntheticInterventionOutcome(
            baseline_result=baseline,
            intervened_result=intervened,
            changed_input_names=tuple(names),
        )


def _json(value: object) -> JsonValue:
    return cast(JsonValue, value)


def _sample_object(
    *,
    cells: list[list[int]],
    color: int,
    node_id: str,
    score: int,
) -> JsonObject:
    return cast(
        JsonObject,
        validate_typed_value(
            "ObjectCandidate",
            {
                "attributes": {
                    "node_id": node_id,
                    "score": score,
                    "size": len(cells),
                },
                "cells": cells,
                "color": color,
            },
        ),
    )


def _sample_value(
    type_name: str,
    *,
    opcode: str,
    index: int,
) -> JsonValue:
    first_object = _sample_object(
        cells=[[0, 0]],
        color=1,
        node_id="object_0",
        score=1,
    )
    second_object = _sample_object(
        cells=[[0, 0], [0, 1]],
        color=2,
        node_id="object_1",
        score=2,
    )
    if type_name == "Grid":
        value: object = (
            [[0, 3], [4, 0]] if opcode == "OVERLAY" and index == 1 else [[1, 0], [0, 2]]
        )
    elif type_name == "Cell":
        value = [index, index]
    elif type_name == "CellSet":
        value = [[0, 0]] if opcode == "SELECT_BY_SHAPE" else [[0, 0], [0, 1]]
    elif type_name == "Region":
        value = {"height": 1, "left": 0, "top": 0, "width": 2}
    elif type_name == "ObjectCandidate":
        value = first_object
    elif type_name == "ObjectSet":
        value = (
            [first_object, second_object]
            if opcode in {"ARGMIN", "ARGMAX"}
            else [first_object]
        )
    elif type_name == "RelationGraph":
        value = {
            "edges": [
                {
                    "relation": "touches",
                    "source": "object_0",
                    "target": "object_1",
                }
            ],
            "nodes": ["object_0", "object_1"],
        }
    elif type_name == "Scalar":
        value = {
            "TRACK_ENTITY": 0,
            "SELECT_BY_SIZE": 1,
            "PAD": 1,
            "COUNT_ENCODE": 3,
            "MATCH_ACTION_ID": 2,
        }.get(opcode, 2)
    elif type_name == "Color":
        value = 3
    elif type_name == "Vector":
        value = [2, 2] if opcode == "TILE" else [1, 0]
    elif type_name == "Sequence":
        value = [1, "marker"]
    elif type_name == "Boolean":
        value = True
    elif type_name == "State":
        if opcode == "MATCH_ACTION_PAYLOAD" and index == 1:
            value = {"kind": "move"}
        else:
            value = {
                "entities": [first_object],
                "initial_state": {"status": "initial", "x": 0},
                "status": "ready",
                "terminal_contribution": {"WIN": 4},
                "x": 1,
            }
    elif type_name == "ActionRecord":
        value = {
            "action_id": 2,
            "available_actions": [0, 1, 2, 3],
            "payload": {"kind": "move", "set": {"x": 2}},
        }
    elif type_name == "Trajectory":
        value = [
            {
                "action_id": 2,
                "available_actions": [0, 1, 2, 3],
                "payload": {"kind": "move"},
            }
        ]
    elif type_name == "Event":
        value = {
            "kind": "observed",
            "payload": {"index": index},
            "step": index + 1,
        }
    elif type_name == "Effect":
        value = {"changes": {"status": "changed", "x": 2}, "delay": 0}
    elif type_name == "TerminalState":
        value = "WIN"
    else:
        fail("IR_TYPE_ERROR", "SAMPLE_TYPE:" + type_name)
    return validate_typed_value(type_name, value)


def _sample_parameters(definition: OpcodeDefinition) -> JsonObject:
    by_opcode: dict[str, JsonObject] = {
        "ARGMAX": {"field": "score"},
        "ARGMIN": {"field": "score"},
        "DERIVE_STATE_FIELD": {"field": "status"},
        "GOAL_PREDICATE": {"field": "status", "value": "ready"},
        "HAZARD_PREDICATE": {"field": "status", "value": "ready"},
        "OVERLAY": {"precedence": "TOP_NONZERO"},
        "REPEAT_UNTIL_OBSERVED": {"max_repeats": 3},
        "SELECT_CELLS": {"colors": [1, 2]},
        "TRANSLATE": {"collision_policy": "FAIL"},
    }
    return by_opcode.get(definition.opcode, {})


def _build_one_opcode_program(
    definition: OpcodeDefinition,
    *,
    input_overrides: Sequence[object] | None = None,
    parameter_override: Mapping[str, JsonValue] | None = None,
    resource_limit: int = DEFAULT_STEP_LIMIT,
) -> JsonObject:
    if input_overrides is not None and len(input_overrides) != len(
        definition.input_types
    ):
        fail("IR_TYPE_ERROR", "VECTOR_OVERRIDE_ARITY")
    inputs = tuple(
        TypedInput(
            name="input_" + str(index),
            type_name=type_name,
            value=validate_typed_value(
                type_name,
                (
                    input_overrides[index]
                    if input_overrides is not None
                    else _sample_value(
                        type_name,
                        opcode=definition.opcode,
                        index=index,
                    )
                ),
            ),
            provenance="OBSERVED",
        )
        for index, type_name in enumerate(definition.input_types)
    )
    node = IRNode(
        node_id="result",
        opcode=definition.opcode,
        input_refs=tuple(item.name for item in inputs),
        parameters=(
            dict(parameter_override)
            if parameter_override is not None
            else _sample_parameters(definition)
        ),
        declared_output_type=definition.output_type,
    )
    return build_program(
        domain=definition.domain,
        inputs=inputs,
        operator_nodes=(node,),
        output_refs=(node.node_id,),
        resource_limit=resource_limit,
    )


def _artifact_policy(id_field: str) -> DigestExclusionPolicy:
    return DigestExclusionPolicy(
        id_fields=frozenset({id_field}),
        digest_fields=frozenset({"content_digest"}),
    )


def _bind_artifact(
    artifact: JsonObject,
    *,
    namespace: str,
    id_field: str,
) -> JsonObject:
    policy = _artifact_policy(id_field)
    artifact[id_field] = ""
    artifact["content_digest"] = ""
    artifact[id_field] = content_derived_id(
        namespace + "-id",
        artifact,
        policy=policy,
    )
    artifact["content_digest"] = logical_content_digest(
        namespace,
        artifact,
        policy=policy,
    )
    return artifact


def build_valid_ir_vector_artifact() -> JsonObject:
    vectors: list[JsonValue] = []
    for definition in (*ARC2_DEFINITIONS, *ARC3_DEFINITIONS):
        program = _build_one_opcode_program(definition)
        result = execute_program(program)
        if result.status != "PASS":
            fail(
                "IR_INVALID_OPERATION",
                "VALID_VECTOR_SUSPENDED:" + definition.opcode,
            )
        vectors.append(
            {
                "domain": definition.domain,
                "expected_result": result.as_json(),
                "opcode": definition.opcode,
                "program": program,
                "vector_id": (
                    "D02C-" + definition.domain + "-" + definition.opcode + "-V1"
                ),
            }
        )
    artifact: JsonObject = {
        "schema_version": "hds-valid-ir-vector-set-v2",
        "vector_set_id": "",
        "phase_id": "PH-D02C",
        "synthetic_fixture_only": True,
        "vector_count": len(vectors),
        "vectors": vectors,
        "digest_excluded_fields": ["content_digest", "vector_set_id"],
        "content_digest": "",
    }
    return _bind_artifact(
        artifact,
        namespace="hds-valid-ir-vector-set",
        id_field="vector_set_id",
    )


def _rebound_copy(program: JsonObject) -> JsonObject:
    return _rebind_program(copy.deepcopy(program))


def _set_program_field(
    program: JsonObject,
    key: str,
    value: JsonValue,
    *,
    rebind: bool = True,
) -> JsonObject:
    modified = copy.deepcopy(program)
    modified[key] = value
    return _rebind_program(modified) if rebind else modified


def _operator_node(program: JsonObject) -> JsonObject:
    graph = program["operator_graph"]
    if not isinstance(graph, list) or len(graph) != 1:
        fail("IR_INVALID_OPERATION", "VECTOR_OPERATOR_GRAPH")
    node = graph[0]
    if not isinstance(node, dict):
        fail("IR_INVALID_OPERATION", "VECTOR_OPERATOR_NODE")
    return node


def _base_program(domain: str, opcode: str) -> JsonObject:
    return _build_one_opcode_program(definition_by_opcode(domain, opcode))


def _build_invalid_programs() -> tuple[tuple[str, str, JsonObject], ...]:
    copy_program = _base_program("ARC2", "COPY")

    unknown_opcode = _rebound_copy(copy_program)
    _operator_node(unknown_opcode)["opcode"] = "UNKNOWN_OPCODE"
    _rebind_program(unknown_opcode)

    type_mismatch = _rebound_copy(copy_program)
    raw_inputs = type_mismatch["inputs"]
    if not isinstance(raw_inputs, list) or not isinstance(raw_inputs[0], dict):
        fail("IR_INVALID_OPERATION", "VECTOR_INPUT")
    raw_inputs[0]["type"] = "Scalar"
    raw_inputs[0]["value"] = 1
    type_mismatch["input_types"] = ["Scalar"]
    _rebind_program(type_mismatch)

    version_mismatch = _rebound_copy(copy_program)
    _operator_node(version_mismatch)["opcode_version"] = "9.9.9"
    _rebind_program(version_mismatch)

    precondition_false = _build_one_opcode_program(
        definition_by_opcode("ARC3", "PRECONDITION"),
        input_overrides=(False,),
    )
    invalid_operation = _build_one_opcode_program(
        definition_by_opcode("ARC2", "CONNECT"),
        input_overrides=([0, 0], [1, 2]),
    )
    cardinality = _build_one_opcode_program(
        definition_by_opcode("ARC2", "UNIQUE"),
        input_overrides=([],),
    )

    abi_mismatch = _rebound_copy(copy_program)
    abi = abi_mismatch["abi"]
    if not isinstance(abi, dict):
        fail("IR_ABI_MISMATCH", "VECTOR_ABI")
    abi["serialization_version"] = "unsupported"
    _rebind_program(abi_mismatch)

    identity_routing = _set_program_field(
        copy_program,
        "task_id",
        "synthetic-task",
        rebind=False,
    )
    answer_copy = _set_program_field(
        copy_program,
        "answer_grid",
        [[1]],
        rebind=False,
    )
    causal_overclaim = _set_program_field(
        copy_program,
        "claim_scope",
        "CAUSAL_MECHANISM",
    )

    forward_reference = _rebound_copy(copy_program)
    _operator_node(forward_reference)["input_refs"] = ["future_result"]
    _rebind_program(forward_reference)

    fixed_action_sequence = _rebound_copy(copy_program)
    fixed_inputs = fixed_action_sequence["inputs"]
    if not isinstance(fixed_inputs, list):
        fail("IR_TYPE_ERROR", "VECTOR_INPUTS")
    fixed_inputs.append(
        {
            "name": "planned_action_sequence",
            "provenance": "GENERAL_RULE_CONSTANT",
            "type": "Sequence",
            "value": [0, 1, 2],
        }
    )

    missing_parameter = _base_program("ARC2", "ARGMIN")
    _operator_node(missing_parameter)["parameters"] = {}
    _rebind_program(missing_parameter)

    resource_declaration = _set_program_field(
        copy_program,
        "resource_cost",
        999,
    )

    digest_mismatch = _rebound_copy(copy_program)
    digest_inputs = digest_mismatch["inputs"]
    if not isinstance(digest_inputs, list) or not isinstance(digest_inputs[0], dict):
        fail("IR_TYPE_ERROR", "VECTOR_INPUTS")
    digest_inputs[0]["value"] = [[9]]

    return (
        ("unknown_opcode", "IR_UNKNOWN_OPCODE", unknown_opcode),
        ("type_mismatch", "IR_TYPE_ERROR", type_mismatch),
        ("opcode_version_mismatch", "IR_UNKNOWN_OPCODE", version_mismatch),
        (
            "precondition_false",
            "IR_PRECONDITION_UNSATISFIED",
            precondition_false,
        ),
        ("invalid_operation", "IR_INVALID_OPERATION", invalid_operation),
        ("selector_cardinality", "IR_CARDINALITY_ERROR", cardinality),
        ("abi_mismatch", "IR_ABI_MISMATCH", abi_mismatch),
        (
            "identity_routing",
            "IR_IDENTITY_ROUTING_FORBIDDEN",
            identity_routing,
        ),
        ("answer_copy", "IR_ANSWER_COPY_FORBIDDEN", answer_copy),
        ("causal_overclaim", "IR_CAUSAL_OVERCLAIM", causal_overclaim),
        ("forward_reference", "IR_TYPE_ERROR", forward_reference),
        (
            "fixed_action_sequence",
            "IR_ANSWER_COPY_FORBIDDEN",
            fixed_action_sequence,
        ),
        ("missing_parameter", "IR_INVALID_OPERATION", missing_parameter),
        (
            "resource_cost_declaration",
            "IR_INVALID_OPERATION",
            resource_declaration,
        ),
        ("program_digest_mismatch", "IR_INVALID_OPERATION", digest_mismatch),
    )


def build_invalid_ir_vector_artifact() -> JsonObject:
    cases: list[JsonValue] = [
        {
            "expected_error_code": expected,
            "program": program,
            "vector_id": "D02C-INVALID-" + name.upper() + "-V1",
        }
        for name, expected, program in _build_invalid_programs()
    ]
    artifact: JsonObject = {
        "schema_version": "hds-invalid-ir-vector-set-v2",
        "vector_set_id": "",
        "phase_id": "PH-D02C",
        "synthetic_fixture_only": True,
        "vector_count": len(cases),
        "vectors": cases,
        "digest_excluded_fields": ["content_digest", "vector_set_id"],
        "content_digest": "",
    }
    return _bind_artifact(
        artifact,
        namespace="hds-invalid-ir-vector-set",
        id_field="vector_set_id",
    )


def _resource_suspension_result() -> ExecutionResult:
    program = _build_one_opcode_program(
        definition_by_opcode("ARC2", "SELECT_COMPONENTS_4"),
        resource_limit=1,
    )
    return execute_program(program)


def build_causal_ir_conformance_report(
    valid_vectors: JsonObject,
    invalid_vectors: JsonObject,
) -> JsonObject:
    raw_valid = valid_vectors.get("vectors")
    raw_invalid = invalid_vectors.get("vectors")
    if not isinstance(raw_valid, list) or not isinstance(raw_invalid, list):
        fail("IR_TYPE_ERROR", "VECTOR_SET")

    valid_results: list[JsonValue] = []
    for raw in raw_valid:
        if not isinstance(raw, Mapping):
            fail("IR_TYPE_ERROR", "VALID_VECTOR")
        program = raw.get("program")
        expected = raw.get("expected_result")
        vector_id = raw.get("vector_id")
        if not isinstance(program, Mapping) or not isinstance(expected, Mapping):
            fail("IR_TYPE_ERROR", "VALID_VECTOR_FIELDS")
        first = execute_program(program)
        second = execute_program(program)
        passed = (
            first.as_json() == dict(expected) and first.as_json() == second.as_json()
        )
        valid_results.append(
            {
                "passed": passed,
                "result_digest": first.result_digest,
                "vector_id": vector_id,
            }
        )

    invalid_results: list[JsonValue] = []
    for raw in raw_invalid:
        if not isinstance(raw, Mapping):
            fail("IR_TYPE_ERROR", "INVALID_VECTOR")
        program = raw.get("program")
        expected_code = raw.get("expected_error_code")
        vector_id = raw.get("vector_id")
        if not isinstance(program, Mapping) or not isinstance(expected_code, str):
            fail("IR_TYPE_ERROR", "INVALID_VECTOR_FIELDS")
        try:
            execute_program(program)
        except IRContractError as exc:
            actual_code = exc.code
        else:
            actual_code = "ACCEPTED_INVALID_IR"
        invalid_results.append(
            {
                "actual_error_code": actual_code,
                "expected_error_code": expected_code,
                "passed": actual_code == expected_code,
                "vector_id": vector_id,
            }
        )

    if not all(cast(JsonObject, item)["passed"] is True for item in valid_results):
        fail("IR_INVALID_OPERATION", "VALID_CONFORMANCE")
    if not all(cast(JsonObject, item)["passed"] is True for item in invalid_results):
        fail("IR_INVALID_OPERATION", "INVALID_CONFORMANCE")

    comparator = CanonicalExactComparator()
    equal_comparison = comparator.compare(
        type_name="Grid",
        expected=[[1, 0]],
        actual=[[1, 0]],
    )
    unequal_comparison = comparator.compare(
        type_name="Grid",
        expected=[[1, 0]],
        actual=[[0, 1]],
    )
    intervention_program = _base_program("ARC2", "COPY")
    intervention = BoundedSyntheticInterventionRunner().run(
        intervention_program,
        (
            SyntheticIntervention(
                input_name="input_0",
                replacement_value=_json([[9]]),
            ),
        ),
    )
    suspension = _resource_suspension_result()
    if suspension.status != "SUSPEND_RESOURCE":
        fail("IR_INVALID_OPERATION", "RESOURCE_SUSPENSION")
    if intervention.causal_claim is not None:
        fail("IR_CAUSAL_OVERCLAIM", "INTERVENTION_RESULT")

    report: JsonObject = {
        "schema_version": "hds-causal-ir-conformance-report-v2",
        "report_id": "",
        "phase_id": "PH-D02C",
        "valid_vector_set_digest": valid_vectors["content_digest"],
        "invalid_vector_set_digest": invalid_vectors["content_digest"],
        "valid_vector_count": len(valid_results),
        "valid_vector_pass_count": sum(
            cast(JsonObject, item)["passed"] is True for item in valid_results
        ),
        "invalid_vector_count": len(invalid_results),
        "invalid_vector_pass_count": sum(
            cast(JsonObject, item)["passed"] is True for item in invalid_results
        ),
        "valid_results": valid_results,
        "invalid_results": invalid_results,
        "exact_comparator": {
            "equal_case": equal_comparison.as_json(),
            "unequal_case": unequal_comparison.as_json(),
        },
        "synthetic_intervention": intervention.as_json(),
        "resource_suspension": suspension.as_json(),
        "gate_results": {
            "DG-03": "PASS_TYPED_EXECUTABLE_IR_AND_STABLE_ERRORS",
            "DG-08": "PASS_PRIVILEGED_ROUTING_REJECTED",
            "DG-09": "PASS_PREDICTIVE_SCOPE_NO_CAUSAL_OVERCLAIM",
            "DG-12": "PASS_RESOURCE_OVERFLOW_SUSPENDS",
        },
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
        "owner_approval_generated": False,
        "synthetic_fixture_only": True,
        "digest_excluded_fields": ["content_digest", "report_id"],
        "content_digest": "",
    }
    return _bind_artifact(
        report,
        namespace="hds-causal-ir-conformance",
        id_field="report_id",
    )


def build_phase_d02c_artifacts(
    project_root: Path,
) -> dict[str, bytes]:
    """Build every deterministic PH-D02C IR artifact in memory."""

    encoded = build_post_audit_causal_ir_schema_artifacts(project_root)
    valid_vectors = build_valid_ir_vector_artifact()
    invalid_vectors = build_invalid_ir_vector_artifact()
    conformance = build_causal_ir_conformance_report(
        valid_vectors,
        invalid_vectors,
    )
    artifacts: dict[str, JsonObject] = {
        "distillation/input/causal_ir_contract.json": (build_causal_ir_contract()),
        "distillation/artifacts/registries/common_type_system.json": (
            build_type_system_artifact()
        ),
        "distillation/artifacts/registries/arc2_operator_registry.json": (
            build_operator_registry("ARC2")
        ),
        "distillation/artifacts/registries/arc3_operator_registry.json": (
            build_operator_registry("ARC3")
        ),
        "distillation/artifacts/registries/resource_cost_model.json": (
            build_resource_cost_model()
        ),
        "distillation/artifacts/registries/code_ir_abi.json": (build_abi_artifact()),
        (
            "distillation/artifacts/test_vectors/causal_ir/valid_ir_vectors.json"
        ): valid_vectors,
        (
            "distillation/artifacts/test_vectors/causal_ir/invalid_ir_vectors.json"
        ): invalid_vectors,
        "distillation/artifacts/reports/causal_ir_conformance.json": (conformance),
    }
    generated = {
        path: canonical_json_document_bytes(value)
        for path, value in sorted(artifacts.items())
    }
    if set(encoded) & set(generated):
        fail("IR_INVALID_OPERATION", "D02C_ARTIFACT_PATH_COLLISION")
    for payload in generated.values():
        verify_canonical_json_document_bytes(payload)
    encoded.update(generated)
    return dict(sorted(encoded.items()))


def write_phase_d02c_artifacts(project_root: Path) -> dict[str, str]:
    """Write only the deterministic paths owned by PH-D02C."""

    import hashlib

    artifacts = build_phase_d02c_artifacts(project_root)
    digests: dict[str, str] = {}
    for relative_path, payload in artifacts.items():
        path = project_root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)
        digests[relative_path] = hashlib.sha256(payload).hexdigest()
    return digests


__all__ = [
    "BoundedSyntheticInterventionRunner",
    "CanonicalExactComparator",
    "ExactComparatorInterface",
    "ExactComparison",
    "InterventionRunnerInterface",
    "SyntheticIntervention",
    "SyntheticInterventionOutcome",
    "build_causal_ir_conformance_report",
    "build_invalid_ir_vector_artifact",
    "build_phase_d02c_artifacts",
    "build_valid_ir_vector_artifact",
    "write_phase_d02c_artifacts",
]
