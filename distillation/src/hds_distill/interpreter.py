"""Pure deterministic PH-D02C Causal IR interpreter."""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, cast

from .canonical import (
    DigestExclusionPolicy,
    JsonValue,
    canonicalize,
    logical_content_digest,
)
from .causal_ir import IRNode, TypeCheckedProgram, type_check_program
from .ir_types import JsonObject, fail, validate_typed_value
from .operator_registry import OpcodeDefinition, definition_by_opcode

EXECUTION_RESULT_VERSION: Final = "hds-causal-ir-execution-result-v1"
TRACE_VERSION: Final = "hds-causal-ir-execution-trace-v1"


@dataclass(frozen=True, slots=True)
class TraceEntry:
    index: int
    node_id: str
    opcode: str
    opcode_version: str
    input_refs: tuple[str, ...]
    output_type: str
    output_digest: str
    resource_cost: int

    def as_json(self) -> JsonObject:
        return {
            "index": self.index,
            "input_refs": list(self.input_refs),
            "node_id": self.node_id,
            "opcode": self.opcode,
            "opcode_version": self.opcode_version,
            "output_digest": self.output_digest,
            "output_type": self.output_type,
            "resource_cost": self.resource_cost,
        }


@dataclass(frozen=True, slots=True)
class ExecutionResult:
    status: str
    assertion_state: str
    operation_state: str
    evidence_state: str
    reason_code: str | None
    outputs: Mapping[str, JsonValue]
    trace: tuple[TraceEntry, ...]
    resource_used: int
    resource_limit: int
    trace_digest: str
    result_digest: str

    def as_json(self) -> JsonObject:
        return {
            "schema_version": EXECUTION_RESULT_VERSION,
            "assertion_state": self.assertion_state,
            "evidence_state": self.evidence_state,
            "operation_state": self.operation_state,
            "outputs": dict(self.outputs),
            "reason_code": self.reason_code,
            "resource_limit": self.resource_limit,
            "resource_used": self.resource_used,
            "result_digest": self.result_digest,
            "status": self.status,
            "trace": [item.as_json() for item in self.trace],
            "trace_digest": self.trace_digest,
        }


def _as_grid(value: JsonValue) -> list[list[int]]:
    return cast(list[list[int]], value)


def _as_cells(value: JsonValue) -> list[list[int]]:
    return cast(list[list[int]], value)


def _as_objects(value: JsonValue) -> list[JsonObject]:
    return cast(list[JsonObject], value)


def _as_state(value: JsonValue) -> JsonObject:
    return cast(JsonObject, value)


def _as_sequence(value: JsonValue) -> list[JsonValue]:
    return cast(list[JsonValue], value)


def _parameters(node: IRNode) -> JsonObject:
    return node.parameters


def _json(value: object) -> JsonValue:
    """Mark a constructed, subsequently validated value as JSON-native."""

    return cast(JsonValue, value)


def _copy_grid(grid: list[list[int]]) -> list[list[int]]:
    return [list(row) for row in grid]


def _bounds(grid: list[list[int]], cell: Sequence[int]) -> bool:
    return len(cell) == 2 and 0 <= cell[0] < len(grid) and 0 <= cell[1] < len(grid[0])


def _component_objects(
    grid: list[list[int]],
    *,
    diagonal: bool,
) -> list[JsonValue]:
    offsets = (
        (
            (-1, -1),
            (-1, 0),
            (-1, 1),
            (0, -1),
            (0, 1),
            (1, -1),
            (1, 0),
            (1, 1),
        )
        if diagonal
        else ((-1, 0), (0, -1), (0, 1), (1, 0))
    )
    seen: set[tuple[int, int]] = set()
    objects: list[JsonValue] = []
    for row in range(len(grid)):
        for column in range(len(grid[0])):
            color = grid[row][column]
            seed = (row, column)
            if color == 0 or seed in seen:
                continue
            pending = deque([seed])
            seen.add(seed)
            cells: list[tuple[int, int]] = []
            while pending:
                current = pending.popleft()
                cells.append(current)
                for row_delta, column_delta in offsets:
                    neighbor = (
                        current[0] + row_delta,
                        current[1] + column_delta,
                    )
                    if (
                        0 <= neighbor[0] < len(grid)
                        and 0 <= neighbor[1] < len(grid[0])
                        and neighbor not in seen
                        and grid[neighbor[0]][neighbor[1]] == color
                    ):
                        seen.add(neighbor)
                        pending.append(neighbor)
            cells.sort()
            top = min(item[0] for item in cells)
            left = min(item[1] for item in cells)
            bottom = max(item[0] for item in cells)
            right = max(item[1] for item in cells)
            objects.append(
                {
                    "attributes": {
                        "height": bottom - top + 1,
                        "left": left,
                        "node_id": "object_" + str(len(objects)),
                        "size": len(cells),
                        "top": top,
                        "width": right - left + 1,
                    },
                    "cells": [[item[0], item[1]] for item in cells],
                    "color": color,
                }
            )
    return objects


def _normalized_shape(cells: Sequence[Sequence[int]]) -> tuple[tuple[int, int], ...]:
    if not cells:
        return ()
    top = min(item[0] for item in cells)
    left = min(item[1] for item in cells)
    return tuple(sorted((item[0] - top, item[1] - left) for item in cells))


def _select_extreme(
    objects: list[JsonObject],
    *,
    field: str,
    maximum: bool,
) -> JsonValue:
    if not objects:
        fail("IR_CARDINALITY_ERROR", "EXTREME_EMPTY")
    candidates: list[tuple[int, JsonObject]] = []
    for item in objects:
        attributes = item.get("attributes")
        if not isinstance(attributes, Mapping):
            fail("IR_INVALID_OPERATION", "OBJECT_ATTRIBUTES")
        value = attributes.get(field)
        if type(value) is not int:
            fail("IR_INVALID_OPERATION", "ARG_FIELD:" + field)
        candidates.append((value, item))
    target = (
        max(value for value, _ in candidates)
        if maximum
        else min(value for value, _ in candidates)
    )
    selected = [item for value, item in candidates if value == target]
    if len(selected) != 1:
        fail("IR_CARDINALITY_ERROR", "EXTREME_TIE")
    return selected[0]


def _region_bounds(region: Mapping[str, JsonValue]) -> tuple[int, int, int, int]:
    top = cast(int, region["top"])
    left = cast(int, region["left"])
    height = cast(int, region["height"])
    width = cast(int, region["width"])
    return top, left, top + height, left + width


def _require_region_in_bounds(
    grid: list[list[int]],
    region: Mapping[str, JsonValue],
) -> tuple[int, int, int, int]:
    top, left, bottom, right = _region_bounds(region)
    if bottom > len(grid) or right > len(grid[0]):
        fail("IR_INVALID_OPERATION", "REGION_OUT_OF_BOUNDS")
    return top, left, bottom, right


def _execute_arc2(
    definition: OpcodeDefinition,
    inputs: Sequence[JsonValue],
    parameters: Mapping[str, JsonValue],
) -> JsonValue:
    opcode = definition.opcode
    if opcode == "SELECT_CELLS":
        grid = _as_grid(inputs[0])
        raw_colors = parameters.get("colors")
        colors = (
            set(cast(list[int], raw_colors))
            if isinstance(raw_colors, list)
            else set(range(1, 10))
        )
        return [
            [row, column]
            for row, values in enumerate(grid)
            for column, color in enumerate(values)
            if color in colors
        ]
    if opcode in {"SELECT_COMPONENTS_4", "SELECT_COMPONENTS_8"}:
        return _component_objects(
            _as_grid(inputs[0]),
            diagonal=opcode.endswith("_8"),
        )
    if opcode == "SELECT_BY_COLOR":
        selected_color = cast(int, inputs[1])
        return [
            item
            for item in _as_objects(inputs[0])
            if item.get("color") == selected_color
        ]
    if opcode == "SELECT_BY_SIZE":
        size = cast(int, inputs[1])
        return [
            item
            for item in _as_objects(inputs[0])
            if len(cast(list[JsonValue], item["cells"])) == size
        ]
    if opcode == "SELECT_BY_SHAPE":
        target = _normalized_shape(_as_cells(inputs[1]))
        return [
            item
            for item in _as_objects(inputs[0])
            if _normalized_shape(cast(list[list[int]], item["cells"])) == target
        ]
    if opcode == "SELECT_BY_RELATION":
        graph = cast(JsonObject, inputs[1])
        participants = {
            cast(str, edge[key])
            for edge in cast(list[JsonObject], graph["edges"])
            for key in ("source", "target")
        }
        return [
            item
            for item in _as_objects(inputs[0])
            if cast(JsonObject, item["attributes"]).get("node_id") in participants
        ]
    if opcode == "UNIQUE":
        objects = _as_objects(inputs[0])
        if len(objects) != 1:
            fail("IR_CARDINALITY_ERROR", "UNIQUE:" + str(len(objects)))
        return objects[0]
    if opcode in {"ARGMIN", "ARGMAX"}:
        return _select_extreme(
            _as_objects(inputs[0]),
            field=cast(str, parameters["field"]),
            maximum=opcode == "ARGMAX",
        )
    if opcode == "IDENTITY":
        return list(_as_sequence(inputs[0]))
    if opcode in {"RECOLOR", "DELETE"}:
        grid = _copy_grid(_as_grid(inputs[0]))
        color = 0 if opcode == "DELETE" else cast(int, inputs[2])
        for cell in _as_cells(inputs[1]):
            if not _bounds(grid, cell):
                fail("IR_INVALID_OPERATION", "CELL_OUT_OF_BOUNDS")
            grid[cell[0]][cell[1]] = color
        return _json(grid)
    if opcode == "TRANSLATE":
        cells = _as_cells(inputs[0])
        vector = cast(list[int], inputs[1])
        policy = parameters.get("collision_policy", "FAIL")
        translated = [[cell[0] + vector[0], cell[1] + vector[1]] for cell in cells]
        if policy == "FAIL" and any(
            row < 0 or column < 0 for row, column in translated
        ):
            fail("IR_INVALID_OPERATION", "TRANSLATE_NEGATIVE")
        if policy == "CLIP":
            translated = [
                [row, column] for row, column in translated if row >= 0 and column >= 0
            ]
        translated.sort()
        if len(translated) != len({tuple(item) for item in translated}):
            fail("IR_INVALID_OPERATION", "TRANSLATE_COLLISION")
        return _json(translated)
    if opcode == "ROTATE_90":
        grid = _as_grid(inputs[0])
        return _json([list(row) for row in zip(*grid[::-1], strict=True)])
    if opcode == "ROTATE_180":
        return _json([list(reversed(row)) for row in reversed(_as_grid(inputs[0]))])
    if opcode == "ROTATE_270":
        grid = _as_grid(inputs[0])
        return _json([list(row) for row in zip(*grid, strict=True)][::-1])
    if opcode == "REFLECT_HORIZONTAL":
        return _json([list(reversed(row)) for row in _as_grid(inputs[0])])
    if opcode == "REFLECT_VERTICAL":
        return _json([list(row) for row in reversed(_as_grid(inputs[0]))])
    if opcode == "COPY":
        return _json(_copy_grid(_as_grid(inputs[0])))
    if opcode == "CROP":
        grid = _as_grid(inputs[0])
        crop_top, crop_left, crop_bottom, crop_right = _require_region_in_bounds(
            grid,
            cast(JsonObject, inputs[1]),
        )
        return _json([row[crop_left:crop_right] for row in grid[crop_top:crop_bottom]])
    if opcode == "PAD":
        grid = _as_grid(inputs[0])
        amount = cast(int, inputs[1])
        color = cast(int, inputs[2])
        if amount < 0:
            fail("IR_INVALID_OPERATION", "PAD_NEGATIVE")
        width = len(grid[0]) + 2 * amount
        pad_row = [color] * width
        return _json(
            [list(pad_row) for _ in range(amount)]
            + [[color] * amount + list(row) + [color] * amount for row in grid]
            + [list(pad_row) for _ in range(amount)]
        )
    if opcode == "TILE":
        grid = _as_grid(inputs[0])
        factors = cast(list[int], inputs[1])
        if factors[0] <= 0 or factors[1] <= 0:
            fail("IR_INVALID_OPERATION", "TILE_FACTOR")
        tiled_row = [
            value
            for row in grid
            for value in [item for _ in range(factors[1]) for item in row]
        ]
        width = len(grid[0]) * factors[1]
        source_rows = [
            tiled_row[index : index + width]
            for index in range(0, len(tiled_row), width)
        ]
        return _json([list(row) for row in source_rows for _ in range(factors[0])])
    if opcode == "FILL":
        grid = _copy_grid(_as_grid(inputs[0]))
        fill_top, fill_left, fill_bottom, fill_right = _require_region_in_bounds(
            grid,
            cast(JsonObject, inputs[1]),
        )
        color = cast(int, inputs[2])
        for row in range(fill_top, fill_bottom):
            for column in range(fill_left, fill_right):
                grid[row][column] = color
        return _json(grid)
    if opcode == "OUTLINE":
        top, left, bottom, right = _region_bounds(cast(JsonObject, inputs[0]))
        outline_cells = {
            (row, column)
            for row in range(top, bottom)
            for column in range(left, right)
            if row in {top, bottom - 1} or column in {left, right - 1}
        }
        return _json([[row, column] for row, column in sorted(outline_cells)])
    if opcode == "CONNECT":
        start = cast(list[int], inputs[0])
        end = cast(list[int], inputs[1])
        row_delta = end[0] - start[0]
        column_delta = end[1] - start[1]
        if row_delta == 0:
            step = (0, 1 if column_delta >= 0 else -1)
            length = abs(column_delta)
        elif column_delta == 0:
            step = (1 if row_delta >= 0 else -1, 0)
            length = abs(row_delta)
        elif abs(row_delta) == abs(column_delta):
            step = (
                1 if row_delta >= 0 else -1,
                1 if column_delta >= 0 else -1,
            )
            length = abs(row_delta)
        else:
            fail("IR_INVALID_OPERATION", "CONNECT_NOT_STRAIGHT")
        return _json(
            sorted(
                [
                    [start[0] + index * step[0], start[1] + index * step[1]]
                    for index in range(length + 1)
                ]
            )
        )
    if opcode == "MASK":
        grid = _as_grid(inputs[0])
        selected = {tuple(item) for item in _as_cells(inputs[1])}
        if any(not _bounds(grid, item) for item in selected):
            fail("IR_INVALID_OPERATION", "CELL_OUT_OF_BOUNDS")
        return [
            [
                value if (row, column) in selected else 0
                for column, value in enumerate(values)
            ]
            for row, values in enumerate(grid)
        ]
    if opcode == "OVERLAY":
        bottom_grid = _as_grid(inputs[0])
        top_grid = _as_grid(inputs[1])
        if len(bottom_grid) != len(top_grid) or any(
            len(left) != len(right)
            for left, right in zip(
                bottom_grid,
                top_grid,
                strict=True,
            )
        ):
            fail("IR_INVALID_OPERATION", "OVERLAY_SHAPE")
        precedence = parameters.get("precedence", "TOP_NONZERO")
        if precedence == "TOP_NONZERO":
            return _json(
                [
                    [
                        top_value if top_value != 0 else bottom_value
                        for bottom_value, top_value in zip(
                            bottom_row,
                            top_row,
                            strict=True,
                        )
                    ]
                    for bottom_row, top_row in zip(
                        bottom_grid,
                        top_grid,
                        strict=True,
                    )
                ]
            )
        return _json(
            [
                [
                    bottom_value if bottom_value != 0 else top_value
                    for bottom_value, top_value in zip(
                        bottom_row,
                        top_row,
                        strict=True,
                    )
                ]
                for bottom_row, top_row in zip(
                    bottom_grid,
                    top_grid,
                    strict=True,
                )
            ]
        )
    if opcode == "EXTRACT":
        grid = _as_grid(inputs[0])
        cells = _as_cells(inputs[1])
        if not cells or any(not _bounds(grid, cell) for cell in cells):
            fail("IR_INVALID_OPERATION", "EXTRACT_CELLS")
        extract_top = min(item[0] for item in cells)
        extract_left = min(item[1] for item in cells)
        extract_bottom = max(item[0] for item in cells) + 1
        extract_right = max(item[1] for item in cells) + 1
        return _json(
            [
                row[extract_left:extract_right]
                for row in grid[extract_top:extract_bottom]
            ]
        )
    if opcode == "COUNT":
        return len(_as_sequence(inputs[0]))
    if opcode == "COUNT_ENCODE":
        count = cast(int, inputs[0])
        color = cast(int, inputs[1])
        if count <= 0:
            fail("IR_PRECONDITION_UNSATISFIED", "COUNT_ENCODE")
        return _json([[color] * count])
    if opcode == "REPEAT_N":
        sequence = _as_sequence(inputs[0])
        count = cast(int, inputs[1])
        if count < 0:
            fail("IR_INVALID_OPERATION", "REPEAT_NEGATIVE")
        return [item for _ in range(count) for item in sequence]
    if opcode == "COMPOSE":
        return [*_as_sequence(inputs[0]), *_as_sequence(inputs[1])]
    raise AssertionError("D02C_INTERNAL_ARC2_DISPATCH_DRIFT:" + opcode)


def _state_subset(
    first: Mapping[str, JsonValue],
    second: Mapping[str, JsonValue],
) -> bool:
    return all(first.get(key) == value for key, value in second.items())


def _execute_arc3(
    definition: OpcodeDefinition,
    inputs: Sequence[JsonValue],
    parameters: Mapping[str, JsonValue],
) -> JsonValue:
    opcode = definition.opcode
    if opcode == "DERIVE_STATE_FIELD":
        state = _as_state(inputs[0])
        field = cast(str, parameters["field"])
        if field not in state:
            fail("IR_PRECONDITION_UNSATISFIED", "STATE_FIELD:" + field)
        return [state[field]]
    if opcode == "TRACK_ENTITY":
        state = _as_state(inputs[0])
        index = cast(int, inputs[1])
        entities = state.get("entities")
        if not isinstance(entities, list) or index < 0 or index >= len(entities):
            fail("IR_PRECONDITION_UNSATISFIED", "TRACK_ENTITY")
        return validate_typed_value("ObjectCandidate", entities[index])
    if opcode == "MATCH_ACTION_ID":
        action = cast(JsonObject, inputs[0])
        return action["action_id"] == inputs[1]
    if opcode == "MATCH_ACTION_PAYLOAD":
        action = cast(JsonObject, inputs[0])
        predicate = _as_state(inputs[1])
        payload = action["payload"]
        return isinstance(payload, Mapping) and _state_subset(
            cast(Mapping[str, JsonValue], payload),
            predicate,
        )
    if opcode == "PRECONDITION":
        if inputs[0] is not True:
            fail("IR_PRECONDITION_UNSATISFIED", "BOOLEAN_FALSE")
        return True
    if opcode == "PREDICT_EFFECT":
        state = dict(_as_state(inputs[0]))
        effect = cast(JsonObject, inputs[1])
        if effect["delay"] != 0:
            fail("IR_PRECONDITION_UNSATISFIED", "DELAYED_EFFECT")
        state.update(cast(JsonObject, effect["changes"]))
        return state
    if opcode == "PREDICT_TRANSITION":
        state = dict(_as_state(inputs[0]))
        action = cast(JsonObject, inputs[1])
        payload = action["payload"]
        if isinstance(payload, Mapping):
            update = payload.get("set")
            if isinstance(update, Mapping):
                state.update(cast(Mapping[str, JsonValue], update))
        return state
    if opcode == "DELAYED_EFFECT":
        effect = dict(cast(JsonObject, inputs[0]))
        delay = cast(int, inputs[1])
        if delay < 0:
            fail("IR_INVALID_OPERATION", "NEGATIVE_DELAY")
        effect["delay"] = delay
        return effect
    if opcode in {"GOAL_PREDICATE", "HAZARD_PREDICATE"}:
        state = _as_state(inputs[0])
        return state.get(cast(str, parameters["field"])) == parameters["value"]
    if opcode == "ORDER_BEFORE":
        first = cast(JsonObject, inputs[0])
        second = cast(JsonObject, inputs[1])
        return cast(int, first["step"]) < cast(int, second["step"])
    if opcode == "ORDER_ADJACENT":
        first = cast(JsonObject, inputs[0])
        second = cast(JsonObject, inputs[1])
        return cast(int, second["step"]) == cast(int, first["step"]) + 1
    if opcode == "REPEAT_N":
        sequence = _as_sequence(inputs[0])
        count = cast(int, inputs[1])
        if count < 0:
            fail("IR_INVALID_OPERATION", "REPEAT_NEGATIVE")
        return [item for _ in range(count) for item in sequence]
    if opcode == "REPEAT_UNTIL_OBSERVED":
        if inputs[1] is not True:
            fail("IR_PRECONDITION_UNSATISFIED", "NOT_OBSERVED")
        return list(_as_sequence(inputs[0]))
    if opcode == "RESET_EFFECT":
        state = _as_state(inputs[0])
        initial = state.get("initial_state")
        if not isinstance(initial, Mapping):
            fail("IR_PRECONDITION_UNSATISFIED", "INITIAL_STATE")
        return validate_typed_value("State", initial)
    if opcode == "TERMINAL_CONTRIBUTION":
        state = _as_state(inputs[0])
        contributions = state.get("terminal_contribution")
        terminal = cast(str, inputs[1])
        if not isinstance(contributions, Mapping):
            fail("IR_INVALID_OPERATION", "TERMINAL_CONTRIBUTION")
        value = contributions.get(terminal)
        if type(value) is not int:
            fail("IR_INVALID_OPERATION", "TERMINAL_CONTRIBUTION_VALUE")
        return value
    if opcode == "INVARIANT":
        return _state_subset(_as_state(inputs[0]), _as_state(inputs[1]))
    if opcode == "EXCLUSION":
        first = _as_state(inputs[0])
        second = _as_state(inputs[1])
        return all(
            key not in first or first[key] != value for key, value in second.items()
        )
    raise AssertionError("D02C_INTERNAL_ARC3_DISPATCH_DRIFT:" + opcode)


def _execute_node(
    program: TypeCheckedProgram,
    node: IRNode,
    values: Mapping[str, JsonValue],
) -> JsonValue:
    definition = definition_by_opcode(program.domain, node.opcode)
    inputs = [values[reference] for reference in node.input_refs]
    output = (
        _execute_arc2(definition, inputs, _parameters(node))
        if program.domain == "ARC2"
        else _execute_arc3(definition, inputs, _parameters(node))
    )
    return validate_typed_value(definition.output_type, output)


def _trace_digest(trace: Sequence[TraceEntry]) -> str:
    payload: JsonObject = {
        "schema_version": TRACE_VERSION,
        "entries": [item.as_json() for item in trace],
    }
    return logical_content_digest(
        "hds-causal-ir-execution-trace",
        payload,
        policy=DigestExclusionPolicy(),
    )


def _build_result(
    *,
    status: str,
    assertion_state: str,
    operation_state: str,
    evidence_state: str,
    reason_code: str | None,
    outputs: Mapping[str, JsonValue],
    trace: Sequence[TraceEntry],
    resource_used: int,
    resource_limit: int,
) -> ExecutionResult:
    trace_digest = _trace_digest(trace)
    body: JsonObject = {
        "schema_version": EXECUTION_RESULT_VERSION,
        "assertion_state": assertion_state,
        "evidence_state": evidence_state,
        "operation_state": operation_state,
        "outputs": dict(outputs),
        "reason_code": reason_code,
        "resource_limit": resource_limit,
        "resource_used": resource_used,
        "status": status,
        "trace_digest": trace_digest,
    }
    result_digest = logical_content_digest(
        "hds-causal-ir-execution-result",
        body,
        policy=DigestExclusionPolicy(),
    )
    return ExecutionResult(
        status=status,
        assertion_state=assertion_state,
        operation_state=operation_state,
        evidence_state=evidence_state,
        reason_code=reason_code,
        outputs=outputs,
        trace=tuple(trace),
        resource_used=resource_used,
        resource_limit=resource_limit,
        trace_digest=trace_digest,
        result_digest=result_digest,
    )


def execute_program(program: Mapping[str, object]) -> ExecutionResult:
    """Type-check and execute one program without side effects."""

    checked = type_check_program(program)
    values: dict[str, JsonValue] = {item.name: item.value for item in checked.inputs}
    trace: list[TraceEntry] = []
    used = 0
    for index, node in enumerate(checked.nodes):
        definition = definition_by_opcode(checked.domain, node.opcode)
        if used + definition.resource_cost > checked.resource_limit:
            prior_outputs = {
                reference: values[reference]
                for reference in checked.output_refs
                if reference in values
            }
            return _build_result(
                status="SUSPEND_RESOURCE",
                assertion_state="SUSPEND",
                operation_state="HOLD",
                evidence_state="INCONCLUSIVE",
                reason_code="SUSPEND_RESOURCE",
                outputs=prior_outputs,
                trace=trace,
                resource_used=used,
                resource_limit=checked.resource_limit,
            )
        output = _execute_node(checked, node, values)
        used += definition.resource_cost
        values[node.node_id] = canonicalize(output)
        output_digest = logical_content_digest(
            "hds-causal-ir-node-output",
            {
                "node_id": node.node_id,
                "output_type": definition.output_type,
                "value": values[node.node_id],
            },
            policy=DigestExclusionPolicy(),
        )
        trace.append(
            TraceEntry(
                index=index,
                node_id=node.node_id,
                opcode=node.opcode,
                opcode_version=node.opcode_version,
                input_refs=node.input_refs,
                output_type=definition.output_type,
                output_digest=output_digest,
                resource_cost=definition.resource_cost,
            )
        )
    outputs = {reference: values[reference] for reference in checked.output_refs}
    return _build_result(
        status="PASS",
        assertion_state="SUSPEND",
        operation_state="HOLD",
        evidence_state="LOCAL_FIT",
        reason_code=None,
        outputs=outputs,
        trace=trace,
        resource_used=used,
        resource_limit=checked.resource_limit,
    )


__all__ = [
    "ExecutionResult",
    "TraceEntry",
    "execute_program",
]
