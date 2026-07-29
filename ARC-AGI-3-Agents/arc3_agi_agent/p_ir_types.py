"""Frozen P-IR v1 types and opcode signatures for the fixed L0 interpreter."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, TypeAlias

PIR_SCHEMA_VERSION: Final = "arc3-p-ir-schema-v1"
PIR_TYPE_VERSION: Final = "arc3-p-ir-types-v1"
PIR_OPCODE_VERSION: Final = "arc3-p-ir-opcodes-v1"

PIR_GRAPH_KINDS: Final = frozenset(
    {"REPRESENTATION", "MODEL", "CANDIDATE"}
)
PIR_VALUE_TYPES: Final = frozenset(
    {
        "DecisionObservation",
        "Grid",
        "GridHistory",
        "GridDelta",
        "Mask",
        "RegionSet",
        "ObjectSet",
        "TrackSet",
        "FeatureSet",
        "RelationGraph",
        "Representation",
        "StateVector",
        "Predicate",
        "ActionSet",
        "ActionBinding",
        "EffectDistribution",
        "GoalScore",
        "HazardScore",
        "UncertaintyScore",
        "CandidateSet",
        "ScalarI64",
        "ScalarPPM",
        "Bool",
    }
)

PIRScalar: TypeAlias = str | int | bool | None
PIRParameterValue: TypeAlias = PIRScalar | tuple[PIRScalar, ...]


@dataclass(frozen=True, slots=True)
class PIROpcodeSpec:
    opcode: str
    graph_kind: str
    input_signatures: tuple[tuple[str, ...], ...]
    output_types: tuple[str, ...]
    base_cost: int


def _opcode(
    opcode: str,
    graph_kind: str,
    input_signatures: tuple[tuple[str, ...], ...],
    output_types: tuple[str, ...],
    base_cost: int,
) -> PIROpcodeSpec:
    return PIROpcodeSpec(
        opcode=opcode,
        graph_kind=graph_kind,
        input_signatures=input_signatures,
        output_types=output_types,
        base_cost=base_cost,
    )


PIR_OPCODE_SPECS: Final[dict[str, PIROpcodeSpec]] = {
    "GRID_INPUT": _opcode(
        "GRID_INPUT",
        "REPRESENTATION",
        (("DecisionObservation",),),
        ("Grid",),
        8,
    ),
    "HISTORY_INPUT": _opcode(
        "HISTORY_INPUT",
        "REPRESENTATION",
        (("GridHistory",),),
        ("GridHistory",),
        8,
    ),
    "TEMPORAL_DIFF": _opcode(
        "TEMPORAL_DIFF",
        "REPRESENTATION",
        (("GridHistory",),),
        ("GridDelta",),
        32,
    ),
    "COLOR_PARTITION": _opcode(
        "COLOR_PARTITION",
        "REPRESENTATION",
        (("Grid",),),
        ("RegionSet",),
        32,
    ),
    "REGION_PARTITION": _opcode(
        "REGION_PARTITION",
        "REPRESENTATION",
        (("Grid",),),
        ("RegionSet",),
        48,
    ),
    "CONNECTED_COMPONENTS": _opcode(
        "CONNECTED_COMPONENTS",
        "REPRESENTATION",
        (("Grid",), ("Mask",)),
        ("ObjectSet",),
        96,
    ),
    "OBJECT_FEATURES": _opcode(
        "OBJECT_FEATURES",
        "REPRESENTATION",
        (("ObjectSet",),),
        ("FeatureSet",),
        48,
    ),
    "OBJECT_TRACK": _opcode(
        "OBJECT_TRACK",
        "REPRESENTATION",
        (("ObjectSet", "GridHistory"),),
        ("TrackSet",),
        96,
    ),
    "RELATION_GRAPH": _opcode(
        "RELATION_GRAPH",
        "REPRESENTATION",
        (("ObjectSet",), ("TrackSet",)),
        ("RelationGraph",),
        64,
    ),
    "ROLE_NORMALIZE": _opcode(
        "ROLE_NORMALIZE",
        "REPRESENTATION",
        (("ObjectSet", "FeatureSet"),),
        ("ObjectSet",),
        32,
    ),
    "TRANSFORM_CANONICALIZE": _opcode(
        "TRANSFORM_CANONICALIZE",
        "REPRESENTATION",
        (("ObjectSet",),),
        ("ObjectSet",),
        64,
    ),
    "FEATURE_PROJECT": _opcode(
        "FEATURE_PROJECT",
        "REPRESENTATION",
        (
            ("ObjectSet", "FeatureSet"),
            ("ObjectSet", "FeatureSet", "RelationGraph"),
        ),
        ("Representation",),
        96,
    ),
    "STATE_BUILD": _opcode(
        "STATE_BUILD",
        "MODEL",
        (("Representation",),),
        ("StateVector",),
        24,
    ),
    "PRECONDITION": _opcode(
        "PRECONDITION",
        "MODEL",
        (("StateVector",),),
        ("Predicate",),
        16,
    ),
    "TRANSITION": _opcode(
        "TRANSITION",
        "MODEL",
        (("StateVector", "ActionBinding"),),
        ("EffectDistribution",),
        64,
    ),
    "DELAY_MODEL": _opcode(
        "DELAY_MODEL",
        "MODEL",
        (
            ("EffectDistribution", "GridHistory"),
            ("EffectDistribution",),
        ),
        ("EffectDistribution",),
        32,
    ),
    "GOAL_MODEL": _opcode(
        "GOAL_MODEL",
        "MODEL",
        (("StateVector",), ("EffectDistribution",)),
        ("GoalScore",),
        24,
    ),
    "HAZARD_MODEL": _opcode(
        "HAZARD_MODEL",
        "MODEL",
        (("StateVector",), ("EffectDistribution",)),
        ("HazardScore",),
        24,
    ),
    "COUNTER_MODEL": _opcode(
        "COUNTER_MODEL",
        "MODEL",
        (),
        (
            "EffectDistribution",
            "GoalScore",
            "HazardScore",
            "UncertaintyScore",
            "Predicate",
        ),
        24,
    ),
    "COMPOSE_MODEL": _opcode(
        "COMPOSE_MODEL",
        "MODEL",
        (),
        (
            "EffectDistribution",
            "GoalScore",
            "HazardScore",
            "UncertaintyScore",
            "Predicate",
        ),
        48,
    ),
    "UNCERTAINTY_MODEL": _opcode(
        "UNCERTAINTY_MODEL",
        "MODEL",
        (
            ("FeatureSet",),
            ("StateVector",),
            ("EffectDistribution",),
        ),
        ("UncertaintyScore",),
        24,
    ),
    "ENUM_ACTIONS": _opcode(
        "ENUM_ACTIONS",
        "CANDIDATE",
        (("ActionSet",),),
        ("ActionSet",),
        8,
    ),
    "BIND_ROLE": _opcode(
        "BIND_ROLE",
        "CANDIDATE",
        (("ActionSet", "ObjectSet"),),
        ("ActionBinding",),
        64,
    ),
    "BIND_COORD_CURRENT_RENDER": _opcode(
        "BIND_COORD_CURRENT_RENDER",
        "CANDIDATE",
        (("ActionBinding", "Grid"),),
        ("ActionBinding",),
        64,
    ),
    "FILTER_PRECONDITION": _opcode(
        "FILTER_PRECONDITION",
        "CANDIDATE",
        (
            ("ActionBinding", "Predicate"),
            ("CandidateSet", "Predicate"),
        ),
        ("CandidateSet",),
        32,
    ),
    "SCORE_CANDIDATE": _opcode(
        "SCORE_CANDIDATE",
        "CANDIDATE",
        (
            (
                "ActionBinding",
                "GoalScore",
                "HazardScore",
                "UncertaintyScore",
            ),
            (
                "CandidateSet",
                "GoalScore",
                "HazardScore",
                "UncertaintyScore",
            ),
        ),
        ("CandidateSet",),
        64,
    ),
    "MAKE_PROBE": _opcode(
        "MAKE_PROBE",
        "CANDIDATE",
        (("CandidateSet", "UncertaintyScore"),),
        ("CandidateSet",),
        24,
    ),
    "TOPK": _opcode(
        "TOPK",
        "CANDIDATE",
        (("CandidateSet",),),
        ("CandidateSet",),
        16,
    ),
}

PIR_EXTERNAL_INPUT_TYPES: Final[dict[str, str]] = {
    "$observation": "DecisionObservation",
    "$history": "GridHistory",
    "$representation": "Representation",
    "$grid": "Grid",
    "$objects": "ObjectSet",
    "$features": "FeatureSet",
    "$relations": "RelationGraph",
    "$state": "StateVector",
    "$effects": "EffectDistribution",
    "$goal_score": "GoalScore",
    "$hazard_score": "HazardScore",
    "$uncertainty_score": "UncertaintyScore",
    "$predicate": "Predicate",
    "$legal_actions": "ActionSet",
    "$memory_features": "FeatureSet",
}


@dataclass(frozen=True, slots=True)
class PIRNode:
    node_id: str
    opcode: str
    inputs: tuple[str, ...]
    output_type: str
    parameters: tuple[tuple[str, PIRParameterValue], ...] = ()

    def parameter_map(self) -> dict[str, PIRParameterValue]:
        return dict(self.parameters)


@dataclass(frozen=True, slots=True)
class TypedDAG:
    graph_id: str
    graph_kind: str
    nodes: tuple[PIRNode, ...]
    outputs: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class TensorParameterSpec:
    name: str
    dtype: str
    shape: tuple[int, ...]
    logical_digest: str
    byte_length: int


@dataclass(frozen=True, slots=True)
class ParameterManifest:
    tensors: tuple[TensorParameterSpec, ...] = ()
    scalar_parameters: tuple[tuple[str, int], ...] = ()


@dataclass(frozen=True, slots=True)
class PIRResourceManifest:
    max_nodes: int
    max_tensor_bytes: int
    max_objects: int
    max_relations: int
    max_candidates: int
    max_memory_citations: int
    worst_case_operation_cost: int


@dataclass(frozen=True, slots=True)
class ProvenanceManifest:
    source_digests: tuple[str, ...]
    evidence_manifest_digest: str
    identity_free: bool = True


@dataclass(frozen=True, slots=True)
class PIRProgram:
    schema_version: str
    l0_abi_version: str
    opcode_version: str
    type_version: str
    semantics_digest: str
    program_id: str
    representation_graph: TypedDAG
    model_graph: TypedDAG
    candidate_graph: TypedDAG
    parameter_manifest: ParameterManifest
    resource_manifest: PIRResourceManifest
    provenance: ProvenanceManifest


@dataclass(frozen=True, slots=True)
class PIRValue:
    value_type: str
    value: object


@dataclass(frozen=True, slots=True)
class PIRGraphTrace:
    graph_id: str
    ordered_node_ids: tuple[str, ...]
    output_digests: tuple[str, ...]
    operation_cost: int


@dataclass(frozen=True, slots=True)
class PIRResourceUsage:
    node_count: int
    tensor_bytes: int
    object_count: int
    relation_count: int
    candidate_count: int
    memory_citation_count: int
    operation_cost: int


__all__ = [
    "PIR_EXTERNAL_INPUT_TYPES",
    "PIR_GRAPH_KINDS",
    "PIR_OPCODE_SPECS",
    "PIR_OPCODE_VERSION",
    "PIR_SCHEMA_VERSION",
    "PIR_TYPE_VERSION",
    "PIR_VALUE_TYPES",
    "PIRGraphTrace",
    "PIRNode",
    "PIROpcodeSpec",
    "PIRParameterValue",
    "PIRProgram",
    "PIRResourceManifest",
    "PIRResourceUsage",
    "PIRScalar",
    "PIRValue",
    "ParameterManifest",
    "ProvenanceManifest",
    "TensorParameterSpec",
    "TypedDAG",
]
