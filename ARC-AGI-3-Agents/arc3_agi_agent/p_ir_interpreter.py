"""Deterministic fixed-code interpreter for validated P-IR v1 programs."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Sequence

from .generic_compute import (
    _components,
    action_descriptors,
    represent_observation,
)
from .generic_memory import SemanticRecord
from .generic_types import (
    ActionDescriptor,
    GenericObservation,
    RelationalRepresentation,
)
from .p_ir import p_ir_program_logical_digest
from .p_ir_resource import (
    require_runtime_resources,
    runtime_resource_usage,
)
from .p_ir_types import (
    PIR_OPCODE_SPECS,
    PIRGraphTrace,
    PIRNode,
    PIRProgram,
    PIRResourceUsage,
    PIRValue,
    TypedDAG,
)
from .p_ir_validator import require_valid_p_ir_program, stable_topological_order
from .schema import digest_object
from .taint import COORDINATE_PROVENANCE_CURRENT_RENDER

PIR_INTERPRETER_VERSION = "arc3-p-ir-interpreter-v1"


@dataclass(frozen=True, slots=True)
class PIRExecutionContext:
    observation: GenericObservation
    goal_tokens: tuple[str, ...]
    history: tuple[GenericObservation, ...] = ()
    memory_records: tuple[SemanticRecord, ...] = ()


@dataclass(frozen=True, slots=True)
class PIRRepresentationExecution:
    representation: RelationalRepresentation
    values: tuple[tuple[str, PIRValue], ...]
    trace: PIRGraphTrace


@dataclass(frozen=True, slots=True)
class PIRExecutionResult:
    representation: RelationalRepresentation
    action_bindings: tuple[ActionDescriptor, ...]
    traces: tuple[PIRGraphTrace, ...]
    resource_usage: PIRResourceUsage
    program_logical_digest: str
    execution_digest: str


def _grid_history(
    context: PIRExecutionContext,
) -> tuple[tuple[tuple[int, ...], ...], ...]:
    prior_composites = tuple(
        item.composited_view for item in context.history[-15:]
    )
    current_action_frames = (
        context.observation.rendered_action_frames
        if context.observation.rendered_action_frames
        else (context.observation.composited_view,)
    )
    return (*prior_composites, *current_action_frames)[-16:]


def _project_representation(
    context: PIRExecutionContext,
    *,
    mode: str,
) -> RelationalRepresentation:
    base = represent_observation(
        context.observation,
        goal_tokens=context.goal_tokens,
    )
    if mode == "spatial-relational":
        return base
    if mode == "topology-minimal":
        topology = tuple(
            item
            for item in base.topology_tokens
            if item.startswith(
                (
                    "action-count:",
                    "object-count:",
                    "terminal:",
                )
            )
        )
        relations: tuple[str, ...] = ()
    elif mode == "shape-centric":
        topology = tuple(
            item
            for item in base.topology_tokens
            if item.startswith(
                (
                    "action-count:",
                    "area:",
                    "object-count:",
                    "shape:",
                    "terminal:",
                )
            )
        )
        relations = tuple(
            item for item in base.relations if ":near:" in item
        )
    else:
        raise ValueError("P_IR_PROJECTION_MODE_UNSUPPORTED")
    digest_value = "generic-representation:" + digest_object(
        {
            "observation_signature": base.observation_signature,
            "roles": base.roles,
            "relations": relations,
            "topology_tokens": topology,
            "goal_tokens": base.goal_tokens,
        }
    )
    projected = RelationalRepresentation(
        observation_signature=base.observation_signature,
        roles=base.roles,
        relations=relations,
        topology_tokens=topology,
        goal_tokens=base.goal_tokens,
        digest_value=digest_value,
    )
    failures = projected.validate()
    if failures:
        raise RuntimeError(";".join(failures))
    return projected


def _state_tokens(representation: RelationalRepresentation) -> tuple[str, ...]:
    return tuple(
        sorted(
            set(
                (
                    *representation.topology_tokens,
                    *representation.relations,
                    *representation.goal_tokens,
                )
            )
        )
    )


def _score_ppm(value: object) -> int:
    if isinstance(value, bool):
        return 1_000_000 if value else 0
    if isinstance(value, int) and not isinstance(value, bool):
        return max(0, min(1_000_000, value))
    return 500_000


def _integer_parameter(
    node: PIRNode,
    key: str,
    default: int,
) -> int:
    value = node.parameter_map().get(key, default)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("P_IR_INTEGER_PARAMETER_REQUIRED:" + key)
    return value


def _execute_node(
    node: PIRNode,
    inputs: tuple[PIRValue, ...],
    context: PIRExecutionContext,
    representation: RelationalRepresentation | None,
) -> PIRValue:
    opcode = node.opcode
    parameters = node.parameter_map()
    values: tuple[Any, ...] = tuple(item.value for item in inputs)
    value: Any
    if opcode == "GRID_INPUT":
        value = (
            context.observation.rendered_layers[-1]
            if context.observation.rendered_layers
            else ()
        )
    elif opcode == "HISTORY_INPUT":
        value = _grid_history(context)
    elif opcode == "TEMPORAL_DIFF":
        history = values[0]
        if not isinstance(history, Sequence) or len(history) < 2:
            value = ()
        else:
            before = history[-2]
            after = history[-1]
            value = tuple(
                (y, x, before[y][x], after[y][x])
                for y in range(min(len(before), len(after)))
                for x in range(min(len(before[y]), len(after[y])))
                if before[y][x] != after[y][x]
            )
    elif opcode in {"COLOR_PARTITION", "REGION_PARTITION"}:
        grid = values[0]
        colors = tuple(
            sorted(
                {
                    cell
                    for row in grid
                    for cell in row
                    if isinstance(cell, int)
                }
            )
        )
        value = tuple(
            (
                color,
                tuple(
                    (y, x)
                    for y, row in enumerate(grid)
                    for x, cell in enumerate(row)
                    if cell == color
                ),
            )
            for color in colors
        )
    elif opcode == "CONNECTED_COMPONENTS":
        value = _components(values[0])[
            : _integer_parameter(node, "max_objects", 64)
        ]
    elif opcode == "OBJECT_FEATURES":
        objects = values[0]
        value = tuple(
            (
                f"object:{index:02d}",
                len(cells),
                min((y for y, _ in cells), default=0),
                min((x for _, x in cells), default=0),
                max((y for y, _ in cells), default=0),
                max((x for _, x in cells), default=0),
            )
            for index, cells in enumerate(objects)
        )
    elif opcode == "OBJECT_TRACK":
        objects, history = values
        value = tuple(
            (index, cells, len(history))
            for index, cells in enumerate(objects)
        )
    elif opcode == "RELATION_GRAPH":
        current = represent_observation(
            context.observation,
            goal_tokens=context.goal_tokens,
        )
        value = current.relations[
            : _integer_parameter(
                node,
                "max_relations",
                len(current.relations),
            )
        ]
    elif opcode == "ROLE_NORMALIZE":
        value = tuple(
            sorted(
                values[0],
                key=lambda cells: (
                    -len(cells),
                    cells,
                ),
            )
        )
    elif opcode == "TRANSFORM_CANONICALIZE":
        value = tuple(sorted(values[0]))
    elif opcode == "FEATURE_PROJECT":
        mode = str(
            parameters.get("projection_mode", "spatial-relational")
        )
        value = _project_representation(context, mode=mode)
    elif opcode == "STATE_BUILD":
        source = values[0]
        if not isinstance(source, RelationalRepresentation):
            raise TypeError("P_IR_STATE_REPRESENTATION_REQUIRED")
        value = _state_tokens(source)
    elif opcode == "PRECONDITION":
        required = str(parameters.get("required_token", ""))
        value = not required or required in values[0]
    elif opcode == "TRANSITION":
        value = (
            ("state_digest", digest_object(values[0])),
            ("binding_digest", digest_object(values[1])),
            ("delay_steps", _integer_parameter(node, "delay_steps", 0)),
        )
    elif opcode == "DELAY_MODEL":
        value = (
            *tuple(values[0]),
            ("history_depth", len(values[1]) if len(values) > 1 else 0),
        )
    elif opcode == "GOAL_MODEL":
        terminal = context.observation.terminal_state
        value = (
            1_000_000
            if terminal == "WIN"
            else min(
                900_000,
                250_000
                + context.observation.progress_count * 100_000
                + len(context.goal_tokens) * 25_000,
            )
        )
    elif opcode == "HAZARD_MODEL":
        value = (
            1_000_000
            if context.observation.terminal_state == "GAME_OVER"
            else 50_000
            if any(
                "hazard" in item.casefold()
                or "failure" in item.casefold()
                for item in context.observation.visible_effects
            )
            else 0
        )
    elif opcode == "COUNTER_MODEL":
        source = values[0]
        if isinstance(source, bool):
            value = not source
        elif isinstance(source, int) and not isinstance(source, bool):
            value = 1_000_000 - _score_ppm(source)
        else:
            value = source
    elif opcode == "COMPOSE_MODEL":
        if all(
            isinstance(item, int) and not isinstance(item, bool)
            for item in values
        ):
            value = sum(int(item) for item in values) // len(values)
        elif all(isinstance(item, bool) for item in values):
            value = all(bool(item) for item in values)
        else:
            value = tuple(
                sorted(
                    {
                        str(part)
                        for item in values
                        for part in (
                            item
                            if isinstance(item, Sequence)
                            and not isinstance(item, (str, bytes))
                            else (item,)
                        )
                    }
                )
            )
    elif opcode == "UNCERTAINTY_MODEL":
        value = min(
            950_000,
            700_000
            if not context.memory_records
            else max(100_000, 700_000 // (len(context.memory_records) + 1)),
        )
    elif opcode == "ENUM_ACTIONS":
        value = tuple(values[0])
    elif opcode == "BIND_ROLE":
        if representation is None:
            raise RuntimeError("P_IR_REPRESENTATION_REQUIRED")
        allowed = set(values[0])
        value = tuple(
            item
            for item in action_descriptors(
                context.observation,
                representation,
            )
            if item.action_id in allowed
        )
    elif opcode == "BIND_COORD_CURRENT_RENDER":
        descriptors: tuple[ActionDescriptor, ...] = tuple(values[0])
        for descriptor in descriptors:
            failures = descriptor.validate(context.observation)
            if failures:
                raise ValueError(";".join(failures))
            if descriptor.payload_items and (
                descriptor.coordinate_provenance
                != COORDINATE_PROVENANCE_CURRENT_RENDER
            ):
                raise PermissionError(
                    "P_IR_DYNAMIC_COORDINATE_PROVENANCE_INVALID"
                )
        value = descriptors
    elif opcode == "FILTER_PRECONDITION":
        value = tuple(values[0]) if bool(values[1]) else ()
    elif opcode == "SCORE_CANDIDATE":
        bindings: tuple[ActionDescriptor, ...] = tuple(values[0])
        reverse = parameters.get("order_mode") == "reverse-surface"
        value = tuple(
            sorted(
                bindings,
                key=lambda item: (
                    item.surface_ordinal,
                    item.semantic_key,
                    item.payload_items,
                ),
                reverse=reverse,
            )
        )
    elif opcode == "MAKE_PROBE":
        value = tuple(values[0])
    elif opcode == "TOPK":
        value = tuple(values[0])[: _integer_parameter(node, "k", 0)]
    else:
        raise ValueError("P_IR_UNKNOWN_OPCODE:" + opcode)
    return PIRValue(value_type=node.output_type, value=value)


def _execute_graph(
    graph: TypedDAG,
    *,
    external_values: dict[str, PIRValue],
    context: PIRExecutionContext,
    representation: RelationalRepresentation | None,
) -> tuple[dict[str, PIRValue], PIRGraphTrace]:
    node_map = {node.node_id: node for node in graph.nodes}
    values: dict[str, PIRValue] = {}
    ordered = stable_topological_order(graph)
    operation_cost = 0
    for node_id in ordered:
        node = node_map[node_id]
        inputs = tuple(
            external_values[ref] if ref.startswith("$") else values[ref]
            for ref in node.inputs
        )
        output = _execute_node(
            node,
            inputs,
            context,
            representation,
        )
        if output.value_type != node.output_type:
            raise TypeError("P_IR_INTERPRETER_OUTPUT_TYPE_MISMATCH:" + node_id)
        values[node_id] = output
        operation_cost += PIR_OPCODE_SPECS[node.opcode].base_cost
    trace = PIRGraphTrace(
        graph_id=graph.graph_id,
        ordered_node_ids=ordered,
        output_digests=tuple(
            digest_object(values[item]) for item in graph.outputs
        ),
        operation_cost=operation_cost,
    )
    return values, trace


def _latest_type(
    values: dict[str, PIRValue],
    ordered: Sequence[str],
    value_type: str,
) -> PIRValue | None:
    for node_id in reversed(tuple(ordered)):
        value = values[node_id]
        if value.value_type == value_type:
            return value
    return None


@dataclass(frozen=True, slots=True)
class FixedL0PIRInterpreter:
    interpreter_version: str = PIR_INTERPRETER_VERSION

    def execute_representation(
        self,
        program: PIRProgram,
        context: PIRExecutionContext,
    ) -> PIRRepresentationExecution:
        require_valid_p_ir_program(program)
        external = {
            "$observation": PIRValue(
                "DecisionObservation", context.observation
            ),
            "$history": PIRValue("GridHistory", _grid_history(context)),
        }
        values, trace = _execute_graph(
            program.representation_graph,
            external_values=external,
            context=context,
            representation=None,
        )
        output = values[program.representation_graph.outputs[0]]
        if not isinstance(output.value, RelationalRepresentation):
            raise TypeError("P_IR_REPRESENTATION_OUTPUT_REQUIRED")
        return PIRRepresentationExecution(
            representation=output.value,
            values=tuple(sorted(values.items())),
            trace=trace,
        )

    def execute(
        self,
        program: PIRProgram,
        context: PIRExecutionContext,
        *,
        representation_execution: PIRRepresentationExecution | None = None,
    ) -> PIRExecutionResult:
        representation_result = (
            representation_execution
            if representation_execution is not None
            else self.execute_representation(program, context)
        )
        if (
            representation_result.representation.observation_signature
            != context.observation.signature
        ):
            raise ValueError("P_IR_REUSED_REPRESENTATION_BINDING_INVALID")
        representation_values = dict(representation_result.values)
        representation_order = (
            representation_result.trace.ordered_node_ids
        )
        grid = _latest_type(
            representation_values,
            representation_order,
            "Grid",
        )
        objects = _latest_type(
            representation_values,
            representation_order,
            "ObjectSet",
        )
        features = _latest_type(
            representation_values,
            representation_order,
            "FeatureSet",
        )
        relations = _latest_type(
            representation_values,
            representation_order,
            "RelationGraph",
        )
        if grid is None or objects is None:
            raise RuntimeError("P_IR_REQUIRED_REPRESENTATION_VALUE_MISSING")
        external = {
            "$observation": PIRValue(
                "DecisionObservation", context.observation
            ),
            "$history": PIRValue("GridHistory", _grid_history(context)),
            "$representation": PIRValue(
                "Representation", representation_result.representation
            ),
            "$grid": grid,
            "$objects": objects,
            "$features": features or PIRValue("FeatureSet", ()),
            "$relations": relations or PIRValue("RelationGraph", ()),
            "$legal_actions": PIRValue(
                "ActionSet", context.observation.available_actions
            ),
            "$memory_features": PIRValue(
                "FeatureSet",
                tuple(item.citation() for item in context.memory_records),
            ),
        }
        model_values, model_trace = _execute_graph(
            program.model_graph,
            external_values=external,
            context=context,
            representation=representation_result.representation,
        )
        model_order = model_trace.ordered_node_ids
        model_external_names = {
            "StateVector": "$state",
            "EffectDistribution": "$effects",
            "GoalScore": "$goal_score",
            "HazardScore": "$hazard_score",
            "UncertaintyScore": "$uncertainty_score",
            "Predicate": "$predicate",
        }
        for value_type, name in model_external_names.items():
            item = _latest_type(model_values, model_order, value_type)
            if item is not None:
                external[name] = item
        for name, value_type, default in (
            ("$goal_score", "GoalScore", 0),
            ("$hazard_score", "HazardScore", 0),
            ("$uncertainty_score", "UncertaintyScore", 1_000_000),
            ("$predicate", "Predicate", True),
        ):
            external.setdefault(name, PIRValue(value_type, default))
        candidate_values, candidate_trace = _execute_graph(
            program.candidate_graph,
            external_values=external,
            context=context,
            representation=representation_result.representation,
        )
        output = candidate_values[program.candidate_graph.outputs[0]]
        descriptors: tuple[ActionDescriptor, ...] = tuple(output.value)  # type: ignore[arg-type]
        if not all(isinstance(item, ActionDescriptor) for item in descriptors):
            raise TypeError("P_IR_CANDIDATE_OUTPUT_REQUIRED")
        all_values = {
            **representation_values,
            **{
                "model:" + key: value
                for key, value in model_values.items()
            },
            **{
                "candidate:" + key: value
                for key, value in candidate_values.items()
            },
        }
        traces = (
            representation_result.trace,
            model_trace,
            candidate_trace,
        )
        usage = runtime_resource_usage(
            program=program,
            values=all_values,
            memory_citation_count=len(context.memory_records),
            operation_cost=sum(item.operation_cost for item in traces),
        )
        require_runtime_resources(usage, program.resource_manifest)
        logical_digest = p_ir_program_logical_digest(program)
        execution_digest = "p-ir-execution:" + digest_object(
            {
                "interpreter_version": self.interpreter_version,
                "program": logical_digest,
                "observation": context.observation.digest(),
                "memory": tuple(
                    item.citation().content_digest
                    for item in context.memory_records
                ),
                "traces": traces,
                "representation": representation_result.representation,
                "action_bindings": descriptors,
                "usage": usage,
            }
        )
        return PIRExecutionResult(
            representation=representation_result.representation,
            action_bindings=descriptors,
            traces=traces,
            resource_usage=usage,
            program_logical_digest=logical_digest,
            execution_digest=execution_digest,
        )


__all__ = [
    "PIR_INTERPRETER_VERSION",
    "FixedL0PIRInterpreter",
    "PIRExecutionContext",
    "PIRExecutionResult",
    "PIRRepresentationExecution",
]
