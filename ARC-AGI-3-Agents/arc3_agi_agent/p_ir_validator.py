"""Fail-closed schema, type, DAG, ABI, taint, and resource validation."""

from __future__ import annotations

import re
from collections import deque
from collections.abc import Sequence

from .p_ir_abi import abi_compatibility_failures
from .p_ir_resource import static_resource_failures
from .p_ir_types import (
    PIR_EXTERNAL_INPUT_TYPES,
    PIR_GRAPH_KINDS,
    PIR_OPCODE_SPECS,
    PIR_SCHEMA_VERSION,
    PIR_VALUE_TYPES,
    PIRNode,
    PIRParameterValue,
    PIRProgram,
    TypedDAG,
)
from .schema import forbidden_executable_paths, forbidden_runtime_paths

_IDENTIFIER = re.compile(r"^[a-z][a-z0-9_.:-]{0,127}$")
_MODEL_VALUE_TYPES = frozenset(
    {
        "EffectDistribution",
        "GoalScore",
        "HazardScore",
        "UncertaintyScore",
        "Predicate",
    }
)
_PROJECTION_MODES = frozenset(
    {"spatial-relational", "topology-minimal", "shape-centric"}
)


def _parameter_value_valid(value: PIRParameterValue) -> bool:
    if value is None or isinstance(value, (str, bool)):
        return True
    if isinstance(value, int) and not isinstance(value, bool):
        return -(2**63) <= value < 2**63
    if isinstance(value, tuple):
        return all(
            item is None
            or isinstance(item, (str, bool))
            or (
                isinstance(item, int)
                and not isinstance(item, bool)
                and -(2**63) <= item < 2**63
            )
            for item in value
        )
    return False


def _special_signature_valid(
    node: PIRNode,
    input_types: tuple[str, ...],
) -> bool:
    if node.opcode == "COUNTER_MODEL":
        return (
            len(input_types) == 1
            and input_types[0] in _MODEL_VALUE_TYPES
            and node.output_type == input_types[0]
        )
    if node.opcode == "COMPOSE_MODEL":
        return (
            len(input_types) >= 2
            and all(item in _MODEL_VALUE_TYPES for item in input_types)
            and node.output_type in input_types
        )
    return False


def _graph_type_failures(graph: TypedDAG) -> tuple[str, ...]:
    failures: list[str] = []
    if graph.graph_kind not in PIR_GRAPH_KINDS:
        failures.append("P_IR_GRAPH_KIND_INVALID:" + graph.graph_id)
    if not _IDENTIFIER.fullmatch(graph.graph_id):
        failures.append("P_IR_GRAPH_ID_INVALID:" + graph.graph_id)
    ids = tuple(node.node_id for node in graph.nodes)
    if len(ids) != len(set(ids)):
        failures.append("P_IR_NODE_ID_DUPLICATE:" + graph.graph_id)
    node_map = {node.node_id: node for node in graph.nodes}
    dependencies: dict[str, set[str]] = {}
    output_types: dict[str, str] = dict(PIR_EXTERNAL_INPUT_TYPES)
    for node in graph.nodes:
        if not _IDENTIFIER.fullmatch(node.node_id):
            failures.append("P_IR_NODE_ID_INVALID:" + node.node_id)
        if node.output_type not in PIR_VALUE_TYPES:
            failures.append("P_IR_OUTPUT_TYPE_UNKNOWN:" + node.node_id)
        spec = PIR_OPCODE_SPECS.get(node.opcode)
        if spec is None:
            failures.append("P_IR_UNKNOWN_OPCODE:" + node.opcode)
        elif spec.graph_kind != graph.graph_kind:
            failures.append("P_IR_OPCODE_GRAPH_KIND_MISMATCH:" + node.node_id)
        keys = tuple(key for key, _ in node.parameters)
        if keys != tuple(sorted(set(keys))):
            failures.append("P_IR_PARAMETER_KEYS_INVALID:" + node.node_id)
        for key, value in node.parameters:
            if not _IDENTIFIER.fullmatch(key):
                failures.append("P_IR_PARAMETER_KEY_INVALID:" + node.node_id)
            if not _parameter_value_valid(value):
                failures.append("P_IR_PARAMETER_VALUE_INVALID:" + node.node_id)
        if node.opcode == "TOPK":
            value = node.parameter_map().get("k")
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 1
            ):
                failures.append("P_IR_TOPK_BOUND_INVALID:" + node.node_id)
        if node.opcode == "FEATURE_PROJECT":
            mode = node.parameter_map().get(
                "projection_mode", "spatial-relational"
            )
            if mode not in _PROJECTION_MODES:
                failures.append("P_IR_PROJECTION_MODE_INVALID:" + node.node_id)
        dependencies[node.node_id] = {
            ref for ref in node.inputs if not ref.startswith("$")
        }
        for ref in node.inputs:
            if ref.startswith("$") and ref not in PIR_EXTERNAL_INPUT_TYPES:
                failures.append("P_IR_EXTERNAL_INPUT_UNKNOWN:" + ref)
            elif not ref.startswith("$") and ref not in node_map:
                failures.append("P_IR_INPUT_NODE_UNKNOWN:" + ref)
        output_types[node.node_id] = node.output_type

    indegree = {
        node_id: len(
            {item for item in refs if item in node_map}
        )
        for node_id, refs in dependencies.items()
    }
    dependents: dict[str, list[str]] = {node_id: [] for node_id in node_map}
    for node_id, refs in dependencies.items():
        for ref in refs:
            if ref in dependents:
                dependents[ref].append(node_id)
    ready = deque(sorted(node_id for node_id, degree in indegree.items() if degree == 0))
    ordered: list[str] = []
    while ready:
        node_id = ready.popleft()
        ordered.append(node_id)
        for dependent in sorted(dependents[node_id]):
            indegree[dependent] -= 1
            if indegree[dependent] == 0:
                ready.append(dependent)
        ready = deque(sorted(ready))
    if len(ordered) != len(node_map):
        failures.append("P_IR_GRAPH_CYCLE:" + graph.graph_id)
    for node_id in ordered:
        node = node_map[node_id]
        spec = PIR_OPCODE_SPECS.get(node.opcode)
        if spec is None:
            continue
        input_types = tuple(output_types[ref] for ref in node.inputs)
        valid_signature = input_types in spec.input_signatures
        if not valid_signature:
            valid_signature = _special_signature_valid(node, input_types)
        if not valid_signature:
            failures.append("P_IR_TYPE_MISMATCH:" + node.node_id)
        if node.output_type not in spec.output_types:
            failures.append("P_IR_OUTPUT_TYPE_MISMATCH:" + node.node_id)
    if not graph.outputs:
        failures.append("P_IR_GRAPH_OUTPUT_MISSING:" + graph.graph_id)
    for output in graph.outputs:
        if output not in node_map:
            failures.append("P_IR_GRAPH_OUTPUT_UNKNOWN:" + output)
    return tuple(sorted(set(failures)))


def stable_topological_order(graph: TypedDAG) -> tuple[str, ...]:
    failures = _graph_type_failures(graph)
    blocking = tuple(
        item for item in failures if "CYCLE" in item or "UNKNOWN" in item
    )
    if blocking:
        raise ValueError(";".join(blocking))
    node_ids = {node.node_id for node in graph.nodes}
    dependencies = {
        node.node_id: {
            ref for ref in node.inputs if ref in node_ids
        }
        for node in graph.nodes
    }
    dependents: dict[str, set[str]] = {node_id: set() for node_id in node_ids}
    for node_id, refs in dependencies.items():
        for ref in refs:
            dependents[ref].add(node_id)
    ready = sorted(
        node_id for node_id, refs in dependencies.items() if not refs
    )
    ordered: list[str] = []
    while ready:
        node_id = ready.pop(0)
        ordered.append(node_id)
        for dependent in sorted(dependents[node_id]):
            dependencies[dependent].discard(node_id)
            if not dependencies[dependent] and dependent not in ready:
                ready.append(dependent)
        ready.sort()
    if len(ordered) != len(node_ids):
        raise ValueError("P_IR_GRAPH_CYCLE:" + graph.graph_id)
    return tuple(ordered)


def _program_security_failures(program: PIRProgram) -> tuple[str, ...]:
    failures: list[str] = []
    values: Sequence[object] = (
        program,
        program.provenance,
        program.parameter_manifest,
    )
    for value in values:
        failures.extend(
            "P_IR_IDENTITY_TAINT:" + path
            for path in forbidden_runtime_paths(value)
        )
        failures.extend(
            "P_IR_ARBITRARY_CODE_SURFACE:" + path
            for path in forbidden_executable_paths(value)
        )
    if program.provenance.identity_free is not True:
        failures.append("P_IR_PROVENANCE_NOT_IDENTITY_FREE")
    return tuple(sorted(set(failures)))


def validate_p_ir_program(program: PIRProgram) -> tuple[str, ...]:
    failures: list[str] = []
    if program.schema_version != PIR_SCHEMA_VERSION:
        failures.append("P_IR_SCHEMA_VERSION_UNSUPPORTED")
    if not _IDENTIFIER.fullmatch(program.program_id):
        failures.append("P_IR_PROGRAM_ID_INVALID")
    failures.extend(abi_compatibility_failures(program))
    failures.extend(_program_security_failures(program))
    for graph, expected_kind in (
        (program.representation_graph, "REPRESENTATION"),
        (program.model_graph, "MODEL"),
        (program.candidate_graph, "CANDIDATE"),
    ):
        failures.extend(_graph_type_failures(graph))
        if graph.graph_kind != expected_kind:
            failures.append("P_IR_REQUIRED_GRAPH_KIND_MISMATCH:" + graph.graph_id)
    representation_output_types = {
        node.node_id: node.output_type
        for node in program.representation_graph.nodes
    }
    if tuple(
        representation_output_types.get(item)
        for item in program.representation_graph.outputs
    ) != ("Representation",):
        failures.append("P_IR_REPRESENTATION_OUTPUT_INVALID")
    candidate_output_types = {
        node.node_id: node.output_type
        for node in program.candidate_graph.nodes
    }
    if tuple(
        candidate_output_types.get(item)
        for item in program.candidate_graph.outputs
    ) != ("CandidateSet",):
        failures.append("P_IR_CANDIDATE_OUTPUT_INVALID")
    failures.extend(static_resource_failures(program))
    return tuple(sorted(set(failures)))


def require_valid_p_ir_program(program: PIRProgram) -> None:
    failures = validate_p_ir_program(program)
    if failures:
        raise ValueError(";".join(failures))


__all__ = [
    "require_valid_p_ir_program",
    "stable_topological_order",
    "validate_p_ir_program",
]
