"""PH-D02C common type system for the executable HDS Causal IR.

The type system is deliberately JSON-native, dependency-free, and strict.
Validation never coerces values: notably ``bool`` is not accepted as a
``Scalar``, tuple/list shape mistakes fail closed, and dictionaries may not
carry non-string keys.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Final, Never, cast

from .canonical import (
    DigestExclusionPolicy,
    JsonValue,
    canonicalize,
    content_derived_id,
    logical_content_digest,
)

type JsonObject = dict[str, JsonValue]

TYPE_SYSTEM_VERSION: Final = "hds-common-type-system-v1"
TYPE_SYSTEM_DIGEST_NAMESPACE: Final = "hds-common-type-system"
TYPE_SYSTEM_ID_NAMESPACE: Final = "hds-common-type-system-id"

COMMON_TYPE_NAMES: Final = (
    "Grid",
    "Cell",
    "CellSet",
    "Region",
    "ObjectCandidate",
    "ObjectSet",
    "RelationGraph",
    "Scalar",
    "Color",
    "Vector",
    "Sequence",
    "Boolean",
    "State",
    "ActionRecord",
    "Trajectory",
    "Event",
    "Effect",
    "TerminalState",
)

TERMINAL_STATES: Final = (
    "RUNNING",
    "WIN",
    "GAME_OVER",
    "RESET",
    "INCOMPLETE",
)


class IRContractError(ValueError):
    """Stable fail-closed error shared by the PH-D02C IR modules."""

    def __init__(self, code: str, detail: str = "") -> None:
        self.code = code
        self.detail = detail
        super().__init__(code + (":" + detail if detail else ""))


def fail(code: str, detail: str = "") -> Never:
    raise IRContractError(code, detail)


@dataclass(frozen=True, slots=True)
class TypeDefinition:
    name: str
    json_shape: str
    constraints: tuple[str, ...]

    def as_json(self) -> JsonObject:
        return {
            "constraints": list(self.constraints),
            "json_shape": self.json_shape,
            "name": self.name,
        }


TYPE_DEFINITIONS: Final = (
    TypeDefinition(
        "Grid",
        "array<array<integer>>",
        ("non-empty", "rectangular", "cell values 0..9"),
    ),
    TypeDefinition(
        "Cell",
        "[row, column]",
        ("exactly two integers", "row and column are non-negative"),
    ),
    TypeDefinition(
        "CellSet",
        "array<Cell>",
        ("unique cells", "lexicographic order"),
    ),
    TypeDefinition(
        "Region",
        "object{top,left,height,width}",
        ("closed object", "non-negative origin", "positive size"),
    ),
    TypeDefinition(
        "ObjectCandidate",
        "object{cells,color,attributes}",
        ("closed object", "non-empty CellSet", "nullable Color"),
    ),
    TypeDefinition(
        "ObjectSet",
        "array<ObjectCandidate>",
        ("stable order",),
    ),
    TypeDefinition(
        "RelationGraph",
        "object{nodes,edges}",
        ("closed graph", "unique node IDs", "bound edge endpoints"),
    ),
    TypeDefinition("Scalar", "integer", ("bool is forbidden",)),
    TypeDefinition("Color", "integer", ("range 0..9", "bool is forbidden")),
    TypeDefinition(
        "Vector",
        "[row_delta,column_delta]",
        ("exactly two integers",),
    ),
    TypeDefinition("Sequence", "array<json>", ("stable order",)),
    TypeDefinition("Boolean", "boolean", ("no integer coercion",)),
    TypeDefinition("State", "object<string,json>", ("string keys",)),
    TypeDefinition(
        "ActionRecord",
        "object{action_id,payload,available_actions}",
        ("closed object", "action_id 0..7", "available actions unique"),
    ),
    TypeDefinition(
        "Trajectory",
        "array<ActionRecord>",
        ("stable action order",),
    ),
    TypeDefinition(
        "Event",
        "object{kind,step,payload}",
        ("closed object", "non-negative step"),
    ),
    TypeDefinition(
        "Effect",
        "object{changes,delay}",
        ("closed object", "non-negative delay"),
    ),
    TypeDefinition(
        "TerminalState",
        "enum",
        TERMINAL_STATES,
    ),
)

TYPE_BY_NAME: Final = {definition.name: definition for definition in TYPE_DEFINITIONS}

if tuple(TYPE_BY_NAME) != COMMON_TYPE_NAMES:
    raise AssertionError("D02C_INTERNAL_TYPE_ORDER_DRIFT")


def _sequence(value: object, detail: str) -> Sequence[object]:
    if not isinstance(value, list):
        fail("IR_TYPE_ERROR", detail)
    return value


def _mapping(value: object, detail: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        fail("IR_TYPE_ERROR", detail)
    for key in value:
        if not isinstance(key, str):
            fail("IR_TYPE_ERROR", detail + ":NON_STRING_KEY")
    return cast(Mapping[str, object], value)


def _closed_mapping(
    value: object,
    *,
    required: frozenset[str],
    detail: str,
) -> Mapping[str, object]:
    mapping = _mapping(value, detail)
    if frozenset(mapping) != required:
        fail("IR_TYPE_ERROR", detail + ":FIELDS")
    return mapping


def _integer(value: object, detail: str) -> int:
    if type(value) is not int:
        fail("IR_TYPE_ERROR", detail)
    return value


def _cell(value: object, detail: str) -> list[JsonValue]:
    raw = _sequence(value, detail)
    if len(raw) != 2:
        fail("IR_TYPE_ERROR", detail + ":LENGTH")
    row = _integer(raw[0], detail + ":ROW")
    column = _integer(raw[1], detail + ":COLUMN")
    if row < 0 or column < 0:
        fail("IR_TYPE_ERROR", detail + ":NEGATIVE")
    return [row, column]


def _vector(value: object, detail: str) -> list[JsonValue]:
    raw = _sequence(value, detail)
    if len(raw) != 2:
        fail("IR_TYPE_ERROR", detail + ":LENGTH")
    return [
        _integer(raw[0], detail + ":ROW_DELTA"),
        _integer(raw[1], detail + ":COLUMN_DELTA"),
    ]


def _cell_set(
    value: object,
    detail: str,
    *,
    non_empty: bool = False,
) -> list[JsonValue]:
    cells: list[list[JsonValue]] = [
        _cell(item, detail + ":CELL") for item in _sequence(value, detail)
    ]
    if non_empty and not cells:
        fail("IR_TYPE_ERROR", detail + ":EMPTY")
    coordinates = [(cast(int, item[0]), cast(int, item[1])) for item in cells]
    if len(coordinates) != len(set(coordinates)):
        fail("IR_TYPE_ERROR", detail + ":DUPLICATE")
    if coordinates != sorted(coordinates):
        fail("IR_TYPE_ERROR", detail + ":ORDER")
    return cast(list[JsonValue], cells)


def _grid(value: object, detail: str) -> list[JsonValue]:
    rows = _sequence(value, detail)
    if not rows:
        fail("IR_TYPE_ERROR", detail + ":EMPTY")
    normalized: list[JsonValue] = []
    width: int | None = None
    for row_index, row in enumerate(rows):
        raw_row = _sequence(row, detail + f":ROW_{row_index}")
        if not raw_row:
            fail("IR_TYPE_ERROR", detail + ":EMPTY_ROW")
        if width is None:
            width = len(raw_row)
        elif len(raw_row) != width:
            fail("IR_TYPE_ERROR", detail + ":NON_RECTANGULAR")
        output_row: list[JsonValue] = []
        for column_index, cell in enumerate(raw_row):
            color = _integer(
                cell,
                detail + f":CELL_{row_index}_{column_index}",
            )
            if not 0 <= color <= 9:
                fail("IR_TYPE_ERROR", detail + ":COLOR_RANGE")
            output_row.append(color)
        normalized.append(output_row)
    return normalized


def _region(value: object, detail: str) -> JsonObject:
    raw = _closed_mapping(
        value,
        required=frozenset({"top", "left", "height", "width"}),
        detail=detail,
    )
    top = _integer(raw["top"], detail + ":TOP")
    left = _integer(raw["left"], detail + ":LEFT")
    height = _integer(raw["height"], detail + ":HEIGHT")
    width = _integer(raw["width"], detail + ":WIDTH")
    if top < 0 or left < 0 or height <= 0 or width <= 0:
        fail("IR_TYPE_ERROR", detail + ":BOUNDS")
    return {
        "height": height,
        "left": left,
        "top": top,
        "width": width,
    }


def _object_candidate(value: object, detail: str) -> JsonObject:
    raw = _closed_mapping(
        value,
        required=frozenset({"cells", "color", "attributes"}),
        detail=detail,
    )
    cells = _cell_set(raw["cells"], detail + ":CELLS", non_empty=True)
    raw_color = raw["color"]
    color: JsonValue
    if raw_color is None:
        color = None
    else:
        color = validate_typed_value("Color", raw_color)
    attributes = validate_typed_value("State", raw["attributes"])
    return {
        "attributes": attributes,
        "cells": cells,
        "color": color,
    }


def _relation_graph(value: object, detail: str) -> JsonObject:
    raw = _closed_mapping(
        value,
        required=frozenset({"nodes", "edges"}),
        detail=detail,
    )
    node_values = _sequence(raw["nodes"], detail + ":NODES")
    if not all(isinstance(item, str) and item for item in node_values):
        fail("IR_TYPE_ERROR", detail + ":NODE")
    node_names = cast(list[str], list(node_values))
    if len(node_names) != len(set(node_names)):
        fail("IR_TYPE_ERROR", detail + ":DUPLICATE_NODE")
    nodes: list[JsonValue] = list(node_names)
    edges: list[JsonValue] = []
    for index, item in enumerate(_sequence(raw["edges"], detail + ":EDGES")):
        edge = _closed_mapping(
            item,
            required=frozenset({"source", "target", "relation"}),
            detail=detail + f":EDGE_{index}",
        )
        source = edge["source"]
        target = edge["target"]
        relation = edge["relation"]
        if (
            not isinstance(source, str)
            or not isinstance(target, str)
            or not isinstance(relation, str)
            or not relation
            or source not in node_names
            or target not in node_names
        ):
            fail("IR_TYPE_ERROR", detail + f":EDGE_{index}:BOUNDARY")
        edges.append(
            {
                "relation": relation,
                "source": source,
                "target": target,
            }
        )
    return {"edges": edges, "nodes": nodes}


def validate_typed_value(type_name: str, value: object) -> JsonValue:
    """Validate and return one canonical JSON-native typed value."""

    if type_name not in TYPE_BY_NAME:
        fail("IR_TYPE_ERROR", "UNKNOWN_TYPE:" + type_name)
    detail = type_name
    if type_name == "Grid":
        return _grid(value, detail)
    if type_name == "Cell":
        return _cell(value, detail)
    if type_name == "CellSet":
        return _cell_set(value, detail)
    if type_name == "Region":
        return _region(value, detail)
    if type_name == "ObjectCandidate":
        return _object_candidate(value, detail)
    if type_name == "ObjectSet":
        return [
            _object_candidate(item, detail + ":ITEM")
            for item in _sequence(value, detail)
        ]
    if type_name == "RelationGraph":
        return _relation_graph(value, detail)
    if type_name == "Scalar":
        return _integer(value, detail)
    if type_name == "Color":
        color = _integer(value, detail)
        if not 0 <= color <= 9:
            fail("IR_TYPE_ERROR", detail + ":RANGE")
        return color
    if type_name == "Vector":
        return _vector(value, detail)
    if type_name == "Sequence":
        return canonicalize(list(_sequence(value, detail)))
    if type_name == "Boolean":
        if type(value) is not bool:
            fail("IR_TYPE_ERROR", detail)
        return value
    if type_name == "State":
        return canonicalize(dict(_mapping(value, detail)))
    if type_name == "ActionRecord":
        raw = _closed_mapping(
            value,
            required=frozenset({"action_id", "payload", "available_actions"}),
            detail=detail,
        )
        action_id = _integer(raw["action_id"], detail + ":ACTION_ID")
        if not 0 <= action_id <= 7:
            fail("IR_TYPE_ERROR", detail + ":ACTION_ID_RANGE")
        available_actions = [
            _integer(item, detail + ":AVAILABLE_ACTION")
            for item in _sequence(
                raw["available_actions"],
                detail + ":AVAILABLE_ACTIONS",
            )
        ]
        if any(not 0 <= item <= 7 for item in available_actions):
            fail("IR_TYPE_ERROR", detail + ":AVAILABLE_ACTION_RANGE")
        if len(available_actions) != len(set(available_actions)):
            fail("IR_TYPE_ERROR", detail + ":AVAILABLE_ACTION_DUPLICATE")
        available: list[JsonValue] = list(available_actions)
        return {
            "action_id": action_id,
            "available_actions": available,
            "payload": canonicalize(raw["payload"]),
        }
    if type_name == "Trajectory":
        return [
            validate_typed_value("ActionRecord", item)
            for item in _sequence(value, detail)
        ]
    if type_name == "Event":
        raw = _closed_mapping(
            value,
            required=frozenset({"kind", "step", "payload"}),
            detail=detail,
        )
        kind = raw["kind"]
        step = _integer(raw["step"], detail + ":STEP")
        if not isinstance(kind, str) or not kind or step < 0:
            fail("IR_TYPE_ERROR", detail + ":FIELDS")
        return {
            "kind": kind,
            "payload": canonicalize(raw["payload"]),
            "step": step,
        }
    if type_name == "Effect":
        raw = _closed_mapping(
            value,
            required=frozenset({"changes", "delay"}),
            detail=detail,
        )
        delay = _integer(raw["delay"], detail + ":DELAY")
        if delay < 0:
            fail("IR_TYPE_ERROR", detail + ":DELAY")
        return {
            "changes": validate_typed_value("State", raw["changes"]),
            "delay": delay,
        }
    if type_name == "TerminalState":
        if not isinstance(value, str) or value not in TERMINAL_STATES:
            fail("IR_TYPE_ERROR", detail)
        return value
    raise AssertionError("D02C_INTERNAL_TYPE_DISPATCH_DRIFT:" + type_name)


def build_type_system_artifact() -> JsonObject:
    """Build the content-bound common type-system artifact."""

    artifact: JsonObject = {
        "schema_version": TYPE_SYSTEM_VERSION,
        "type_system_id": "",
        "type_count": len(TYPE_DEFINITIONS),
        "types": [definition.as_json() for definition in TYPE_DEFINITIONS],
        "coercion_policy": "FORBIDDEN",
        "unknown_type_policy": "IR_TYPE_ERROR",
        "digest_excluded_fields": [
            "content_digest",
            "type_system_id",
        ],
        "content_digest": "",
    }
    policy = DigestExclusionPolicy(
        id_fields=frozenset({"type_system_id"}),
        digest_fields=frozenset({"content_digest"}),
    )
    artifact["type_system_id"] = content_derived_id(
        TYPE_SYSTEM_ID_NAMESPACE,
        artifact,
        policy=policy,
    )
    artifact["content_digest"] = logical_content_digest(
        TYPE_SYSTEM_DIGEST_NAMESPACE,
        artifact,
        policy=policy,
    )
    return artifact
