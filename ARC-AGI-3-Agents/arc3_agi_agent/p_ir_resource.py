"""Static and runtime resource accounting for P-IR v1."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from .p_ir_types import (
    PIR_OPCODE_SPECS,
    PIRProgram,
    PIRResourceManifest,
    PIRResourceUsage,
    PIRValue,
)


class PIRResourceExceeded(RuntimeError):
    """Raised before or during execution when a declared bound is exceeded."""


def validate_resource_manifest(
    manifest: PIRResourceManifest,
) -> tuple[str, ...]:
    failures: list[str] = []
    for name in (
        "max_nodes",
        "max_tensor_bytes",
        "max_objects",
        "max_relations",
        "max_candidates",
        "max_memory_citations",
        "worst_case_operation_cost",
    ):
        value = getattr(manifest, name)
        if (
            isinstance(value, bool)
            or not isinstance(value, int)
            or value < 0
        ):
            failures.append("P_IR_RESOURCE_FIELD_INVALID:" + name)
    if manifest.max_nodes < 1:
        failures.append("P_IR_RESOURCE_NODE_BOUND_EMPTY")
    if manifest.max_candidates < 1:
        failures.append("P_IR_RESOURCE_CANDIDATE_BOUND_EMPTY")
    return tuple(sorted(set(failures)))


def static_resource_usage(program: PIRProgram) -> PIRResourceUsage:
    nodes = tuple(
        node
        for graph in (
            program.representation_graph,
            program.model_graph,
            program.candidate_graph,
        )
        for node in graph.nodes
    )
    tensor_bytes = sum(
        item.byte_length for item in program.parameter_manifest.tensors
    )
    operation_cost = 0
    for node in nodes:
        spec = PIR_OPCODE_SPECS.get(node.opcode)
        if spec is not None:
            operation_cost += spec.base_cost
    return PIRResourceUsage(
        node_count=len(nodes),
        tensor_bytes=tensor_bytes,
        object_count=0,
        relation_count=0,
        candidate_count=0,
        memory_citation_count=0,
        operation_cost=operation_cost,
    )


def static_resource_failures(program: PIRProgram) -> tuple[str, ...]:
    failures = list(validate_resource_manifest(program.resource_manifest))
    usage = static_resource_usage(program)
    manifest = program.resource_manifest
    if usage.node_count > manifest.max_nodes:
        failures.append("P_IR_RESOURCE_MAX_NODES_EXCEEDED")
    if usage.tensor_bytes > manifest.max_tensor_bytes:
        failures.append("P_IR_RESOURCE_TENSOR_BYTES_EXCEEDED")
    if usage.operation_cost > manifest.worst_case_operation_cost:
        failures.append("P_IR_RESOURCE_OPERATION_COST_EXCEEDED")
    for graph in (
        program.representation_graph,
        program.model_graph,
        program.candidate_graph,
    ):
        for node in graph.nodes:
            parameters = node.parameter_map()
            value = parameters.get("k")
            if (
                node.opcode == "TOPK"
                and isinstance(value, int)
                and not isinstance(value, bool)
                and value > manifest.max_candidates
            ):
                failures.append("P_IR_RESOURCE_TOPK_EXCEEDS_CANDIDATES")
            declared_objects = parameters.get("max_objects")
            if (
                isinstance(declared_objects, int)
                and not isinstance(declared_objects, bool)
                and declared_objects > manifest.max_objects
            ):
                failures.append("P_IR_RESOURCE_OBJECT_BOUND_EXCEEDED")
            declared_relations = parameters.get("max_relations")
            if (
                isinstance(declared_relations, int)
                and not isinstance(declared_relations, bool)
                and declared_relations > manifest.max_relations
            ):
                failures.append("P_IR_RESOURCE_RELATION_BOUND_EXCEEDED")
    return tuple(sorted(set(failures)))


def _count_sequence(value: object) -> int:
    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        return len(value)
    if isinstance(value, Mapping):
        return len(value)
    return 0


def runtime_resource_usage(
    *,
    program: PIRProgram,
    values: Mapping[str, PIRValue],
    memory_citation_count: int,
    operation_cost: int,
) -> PIRResourceUsage:
    object_count = max(
        (
            _count_sequence(item.value)
            for item in values.values()
            if item.value_type in {"ObjectSet", "TrackSet"}
        ),
        default=0,
    )
    relation_count = max(
        (
            _count_sequence(item.value)
            for item in values.values()
            if item.value_type == "RelationGraph"
        ),
        default=0,
    )
    candidate_count = max(
        (
            _count_sequence(item.value)
            for item in values.values()
            if item.value_type in {"ActionBinding", "CandidateSet"}
        ),
        default=0,
    )
    grid_cells = sum(
        sum(len(row) for row in item.value)
        for item in values.values()
        if item.value_type == "Grid"
        and isinstance(item.value, Sequence)
    )
    static = static_resource_usage(program)
    return PIRResourceUsage(
        node_count=static.node_count,
        tensor_bytes=static.tensor_bytes + grid_cells * 8,
        object_count=object_count,
        relation_count=relation_count,
        candidate_count=candidate_count,
        memory_citation_count=memory_citation_count,
        operation_cost=operation_cost,
    )


def require_runtime_resources(
    usage: PIRResourceUsage,
    manifest: PIRResourceManifest,
) -> None:
    checks = (
        ("MAX_NODES", usage.node_count, manifest.max_nodes),
        ("TENSOR_BYTES", usage.tensor_bytes, manifest.max_tensor_bytes),
        ("OBJECTS", usage.object_count, manifest.max_objects),
        ("RELATIONS", usage.relation_count, manifest.max_relations),
        ("CANDIDATES", usage.candidate_count, manifest.max_candidates),
        (
            "MEMORY_CITATIONS",
            usage.memory_citation_count,
            manifest.max_memory_citations,
        ),
        (
            "OPERATION_COST",
            usage.operation_cost,
            manifest.worst_case_operation_cost,
        ),
    )
    exceeded = tuple(
        name for name, actual, limit in checks if actual > limit
    )
    if exceeded:
        raise PIRResourceExceeded(
            "P_IR_RUNTIME_RESOURCE_EXCEEDED:" + ",".join(exceeded)
        )


__all__ = [
    "PIRResourceExceeded",
    "require_runtime_resources",
    "runtime_resource_usage",
    "static_resource_failures",
    "static_resource_usage",
    "validate_resource_manifest",
]
