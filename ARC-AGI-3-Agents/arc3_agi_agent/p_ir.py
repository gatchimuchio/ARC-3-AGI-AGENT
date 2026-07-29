"""P-IR v1 construction, canonical serialization, and logical identity."""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from typing import Any

from .p_ir_abi import L0_ABI_VERSION, PIR_SEMANTICS_DIGEST
from .p_ir_types import (
    PIR_OPCODE_VERSION,
    PIR_SCHEMA_VERSION,
    PIR_TYPE_VERSION,
    ParameterManifest,
    PIRNode,
    PIRParameterValue,
    PIRProgram,
    PIRResourceManifest,
    ProvenanceManifest,
    TensorParameterSpec,
    TypedDAG,
)
from .p_ir_validator import require_valid_p_ir_program
from .schema import canonical_json, digest_object

PIR_DEFAULT_MAX_NODES = 64
PIR_DEFAULT_MAX_TENSOR_BYTES = 16 * 1024 * 1024
PIR_DEFAULT_MAX_OBJECTS = 64
PIR_DEFAULT_MAX_RELATIONS = 4096
PIR_DEFAULT_MAX_CANDIDATES = 2048
PIR_DEFAULT_MAX_MEMORY_CITATIONS = 128
PIR_DEFAULT_WORST_CASE_COST = 200_000


def compatibility_p_ir_program(
    *,
    projection_mode: str = "spatial-relational",
) -> PIRProgram:
    """Represent the historical fixed path as a bounded P-IR program."""

    representation = TypedDAG(
        graph_id="representation.v1",
        graph_kind="REPRESENTATION",
        nodes=(
            PIRNode(
                node_id="grid",
                opcode="GRID_INPUT",
                inputs=("$observation",),
                output_type="Grid",
            ),
            PIRNode(
                node_id="regions",
                opcode="REGION_PARTITION",
                inputs=("grid",),
                output_type="RegionSet",
            ),
            PIRNode(
                node_id="objects",
                opcode="CONNECTED_COMPONENTS",
                inputs=("grid",),
                output_type="ObjectSet",
                parameters=(("connectivity", 4), ("max_objects", 64)),
            ),
            PIRNode(
                node_id="features",
                opcode="OBJECT_FEATURES",
                inputs=("objects",),
                output_type="FeatureSet",
            ),
            PIRNode(
                node_id="normalized_objects",
                opcode="ROLE_NORMALIZE",
                inputs=("objects", "features"),
                output_type="ObjectSet",
            ),
            PIRNode(
                node_id="relations",
                opcode="RELATION_GRAPH",
                inputs=("normalized_objects",),
                output_type="RelationGraph",
                parameters=(("max_relations", 4096),),
            ),
            PIRNode(
                node_id="representation",
                opcode="FEATURE_PROJECT",
                inputs=(
                    "normalized_objects",
                    "features",
                    "relations",
                ),
                output_type="Representation",
                parameters=(("projection_mode", projection_mode),),
            ),
        ),
        outputs=("representation",),
    )
    model = TypedDAG(
        graph_id="model.v1",
        graph_kind="MODEL",
        nodes=(
            PIRNode(
                node_id="state",
                opcode="STATE_BUILD",
                inputs=("$representation",),
                output_type="StateVector",
            ),
            PIRNode(
                node_id="goal",
                opcode="GOAL_MODEL",
                inputs=("state",),
                output_type="GoalScore",
            ),
            PIRNode(
                node_id="hazard",
                opcode="HAZARD_MODEL",
                inputs=("state",),
                output_type="HazardScore",
            ),
            PIRNode(
                node_id="uncertainty",
                opcode="UNCERTAINTY_MODEL",
                inputs=("state",),
                output_type="UncertaintyScore",
            ),
        ),
        outputs=("goal", "hazard", "uncertainty"),
    )
    candidate = TypedDAG(
        graph_id="candidate.v1",
        graph_kind="CANDIDATE",
        nodes=(
            PIRNode(
                node_id="actions",
                opcode="ENUM_ACTIONS",
                inputs=("$legal_actions",),
                output_type="ActionSet",
            ),
            PIRNode(
                node_id="bindings",
                opcode="BIND_ROLE",
                inputs=("actions", "$objects"),
                output_type="ActionBinding",
            ),
            PIRNode(
                node_id="current_coordinates",
                opcode="BIND_COORD_CURRENT_RENDER",
                inputs=("bindings", "$grid"),
                output_type="ActionBinding",
            ),
            PIRNode(
                node_id="scored",
                opcode="SCORE_CANDIDATE",
                inputs=(
                    "current_coordinates",
                    "$goal_score",
                    "$hazard_score",
                    "$uncertainty_score",
                ),
                output_type="CandidateSet",
            ),
            PIRNode(
                node_id="bounded",
                opcode="TOPK",
                inputs=("scored",),
                output_type="CandidateSet",
                parameters=(("k", 2048),),
            ),
        ),
        outputs=("bounded",),
    )
    program = PIRProgram(
        schema_version=PIR_SCHEMA_VERSION,
        l0_abi_version=L0_ABI_VERSION,
        opcode_version=PIR_OPCODE_VERSION,
        type_version=PIR_TYPE_VERSION,
        semantics_digest=PIR_SEMANTICS_DIGEST,
        program_id="generic.compatibility." + projection_mode,
        representation_graph=representation,
        model_graph=model,
        candidate_graph=candidate,
        parameter_manifest=ParameterManifest(),
        resource_manifest=PIRResourceManifest(
            max_nodes=PIR_DEFAULT_MAX_NODES,
            max_tensor_bytes=PIR_DEFAULT_MAX_TENSOR_BYTES,
            max_objects=PIR_DEFAULT_MAX_OBJECTS,
            max_relations=PIR_DEFAULT_MAX_RELATIONS,
            max_candidates=PIR_DEFAULT_MAX_CANDIDATES,
            max_memory_citations=PIR_DEFAULT_MAX_MEMORY_CITATIONS,
            worst_case_operation_cost=PIR_DEFAULT_WORST_CASE_COST,
        ),
        provenance=ProvenanceManifest(
            source_digests=(
                "generic-compute-compatibility-fixture-v1",
                "rev2-p-ir-authority",
            ),
            evidence_manifest_digest=(
                "p-ir-evidence:" + digest_object(projection_mode)
            ),
            identity_free=True,
        ),
    )
    require_valid_p_ir_program(program)
    return program


def p_ir_program_logical_digest(program: PIRProgram) -> str:
    require_valid_p_ir_program(program)
    return "p-ir-logical:" + digest_object(program)


def p_ir_program_to_dict(program: PIRProgram) -> dict[str, Any]:
    require_valid_p_ir_program(program)
    value = json.loads(canonical_json(program))
    if not isinstance(value, dict):
        raise TypeError("P_IR_PROGRAM_SERIALIZATION_INVALID")
    return value


def _parameter_value(value: object) -> PIRParameterValue:
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, Sequence) and not isinstance(
        value, (str, bytes, bytearray)
    ):
        converted = tuple(_parameter_value(item) for item in value)
        if any(isinstance(item, tuple) for item in converted):
            raise TypeError("P_IR_PARAMETER_NESTING_INVALID")
        return converted  # type: ignore[return-value]
    raise TypeError("P_IR_PARAMETER_VALUE_INVALID")


def _node_from_dict(value: Mapping[str, object]) -> PIRNode:
    parameter_values = value.get("parameters", ())
    if not isinstance(parameter_values, Sequence) or isinstance(
        parameter_values, (str, bytes, bytearray)
    ):
        raise TypeError("P_IR_NODE_PARAMETERS_INVALID")
    parameters: list[tuple[str, PIRParameterValue]] = []
    for item in parameter_values:
        if not isinstance(item, Sequence) or isinstance(
            item, (str, bytes, bytearray)
        ):
            raise TypeError("P_IR_NODE_PARAMETER_INVALID")
        pair = tuple(item)
        if len(pair) != 2:
            raise TypeError("P_IR_NODE_PARAMETER_PAIR_INVALID")
        parameters.append((str(pair[0]), _parameter_value(pair[1])))
    inputs_value = value.get("inputs", ())
    if not isinstance(inputs_value, Sequence) or isinstance(
        inputs_value, (str, bytes, bytearray)
    ):
        raise TypeError("P_IR_NODE_INPUTS_INVALID")
    return PIRNode(
        node_id=str(value["node_id"]),
        opcode=str(value["opcode"]),
        inputs=tuple(str(item) for item in inputs_value),
        output_type=str(value["output_type"]),
        parameters=tuple(parameters),
    )


def _graph_from_dict(value: Mapping[str, object]) -> TypedDAG:
    nodes = value.get("nodes", ())
    if not isinstance(nodes, Sequence) or isinstance(
        nodes, (str, bytes, bytearray)
    ):
        raise TypeError("P_IR_GRAPH_NODES_INVALID")
    outputs_value = value.get("outputs", ())
    if not isinstance(outputs_value, Sequence) or isinstance(
        outputs_value, (str, bytes, bytearray)
    ):
        raise TypeError("P_IR_GRAPH_OUTPUTS_INVALID")
    return TypedDAG(
        graph_id=str(value["graph_id"]),
        graph_kind=str(value["graph_kind"]),
        nodes=tuple(
            _node_from_dict(item)
            for item in nodes
            if isinstance(item, Mapping)
        ),
        outputs=tuple(str(item) for item in outputs_value),
    )


def p_ir_program_from_dict(value: Mapping[str, object]) -> PIRProgram:
    parameter_value = value.get("parameter_manifest")
    resource_value = value.get("resource_manifest")
    provenance_value = value.get("provenance")
    if not isinstance(parameter_value, Mapping):
        raise TypeError("P_IR_PARAMETER_MANIFEST_INVALID")
    if not isinstance(resource_value, Mapping):
        raise TypeError("P_IR_RESOURCE_MANIFEST_INVALID")
    if not isinstance(provenance_value, Mapping):
        raise TypeError("P_IR_PROVENANCE_MANIFEST_INVALID")
    tensors_value = parameter_value.get("tensors", ())
    scalars_value = parameter_value.get("scalar_parameters", ())
    if not isinstance(tensors_value, Sequence) or isinstance(
        tensors_value, (str, bytes, bytearray)
    ):
        raise TypeError("P_IR_TENSOR_MANIFEST_INVALID")
    if not isinstance(scalars_value, Sequence) or isinstance(
        scalars_value, (str, bytes, bytearray)
    ):
        raise TypeError("P_IR_SCALAR_MANIFEST_INVALID")
    tensors = tuple(
        TensorParameterSpec(
            name=str(item["name"]),
            dtype=str(item["dtype"]),
            shape=tuple(int(part) for part in item.get("shape", ())),
            logical_digest=str(item["logical_digest"]),
            byte_length=int(item["byte_length"]),
        )
        for item in tensors_value
        if isinstance(item, Mapping)
    )
    scalars: list[tuple[str, int]] = []
    for item in scalars_value:
        if not isinstance(item, Sequence) or isinstance(
            item, (str, bytes, bytearray)
        ):
            raise TypeError("P_IR_SCALAR_PARAMETER_INVALID")
        pair = tuple(item)
        if len(pair) != 2:
            raise TypeError("P_IR_SCALAR_PARAMETER_PAIR_INVALID")
        scalars.append((str(pair[0]), int(pair[1])))
    representation = value.get("representation_graph")
    model = value.get("model_graph")
    candidate = value.get("candidate_graph")
    if not all(
        isinstance(item, Mapping)
        for item in (representation, model, candidate)
    ):
        raise TypeError("P_IR_REQUIRED_GRAPH_INVALID")
    program = PIRProgram(
        schema_version=str(value["schema_version"]),
        l0_abi_version=str(value["l0_abi_version"]),
        opcode_version=str(value["opcode_version"]),
        type_version=str(value["type_version"]),
        semantics_digest=str(value["semantics_digest"]),
        program_id=str(value["program_id"]),
        representation_graph=_graph_from_dict(representation),  # type: ignore[arg-type]
        model_graph=_graph_from_dict(model),  # type: ignore[arg-type]
        candidate_graph=_graph_from_dict(candidate),  # type: ignore[arg-type]
        parameter_manifest=ParameterManifest(
            tensors=tensors,
            scalar_parameters=tuple(scalars),
        ),
        resource_manifest=PIRResourceManifest(
            max_nodes=int(resource_value["max_nodes"]),
            max_tensor_bytes=int(resource_value["max_tensor_bytes"]),
            max_objects=int(resource_value["max_objects"]),
            max_relations=int(resource_value["max_relations"]),
            max_candidates=int(resource_value["max_candidates"]),
            max_memory_citations=int(
                resource_value["max_memory_citations"]
            ),
            worst_case_operation_cost=int(
                resource_value["worst_case_operation_cost"]
            ),
        ),
        provenance=ProvenanceManifest(
            source_digests=tuple(
                str(item)
                for item in provenance_value.get("source_digests", ())
            ),
            evidence_manifest_digest=str(
                provenance_value["evidence_manifest_digest"]
            ),
            identity_free=bool(provenance_value.get("identity_free", False)),
        ),
    )
    require_valid_p_ir_program(program)
    return program


__all__ = [
    "PIR_DEFAULT_MAX_CANDIDATES",
    "PIR_DEFAULT_MAX_MEMORY_CITATIONS",
    "PIR_DEFAULT_MAX_NODES",
    "PIR_DEFAULT_MAX_OBJECTS",
    "PIR_DEFAULT_MAX_RELATIONS",
    "PIR_DEFAULT_MAX_TENSOR_BYTES",
    "PIR_DEFAULT_WORST_CASE_COST",
    "compatibility_p_ir_program",
    "p_ir_program_from_dict",
    "p_ir_program_logical_digest",
    "p_ir_program_to_dict",
]
