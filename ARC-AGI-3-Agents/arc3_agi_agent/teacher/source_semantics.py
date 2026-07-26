"""Extract source-grounded causal contracts for the privileged S0 Teacher.

The environment sources are deliberately obfuscated, so this compiler does
not pretend to recover author-intended natural-language names.  It records the
exact level object inventory, action-control predicates, terminal predicates,
source-state dependencies, and hidden-state export boundary.  Development
analysis labels are retained as hypotheses and are always distinguished from
direct source evidence.

Everything emitted by this module is development-only and forbidden as a
Runtime Student input.
"""

from __future__ import annotations

import ast
import hashlib
import json
from collections import Counter, defaultdict, deque
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ..schema import digest_object

SOURCE_SEMANTICS_SCHEMA_VERSION = "arc3-source-causal-semantics-v1"
GAME_SOURCE_CONTRACT_SCHEMA_VERSION = "arc3-game-source-causal-contract-v1"
LEVEL_SOURCE_CONTRACT_SCHEMA_VERSION = "arc3-level-source-causal-contract-v1"

SOURCE_SEMANTICS_DIGEST_PREFIX = "arc3_source_causal_semantics:"
GAME_SOURCE_CONTRACT_DIGEST_PREFIX = "arc3_game_source_causal_contract:"
LEVEL_SOURCE_CONTRACT_DIGEST_PREFIX = "arc3_level_source_causal_contract:"
DIRECT_SOURCE_EVIDENCE_DIGEST_PREFIX = "arc3_direct_source_evidence:"

DEVELOPMENT_LEDGER_SCHEMA_VERSION = "arc3-p10-development-analysis-v1"
DEVELOPMENT_LEDGER_DIGEST_PREFIX = (
    "arc3_p10_legacy_level_analysis_ledger:"
)

_TERMINAL_CALLS = {
    "next_level": "GOAL_ADVANCE",
    "lose": "HAZARD_TERMINATION",
    "complete_action": "ACTION_COMMIT",
}
_OBJECT_QUERY_CALLS = {
    "add_sprite",
    "collides_with",
    "get_data",
    "get_sprite_at",
    "get_sprites",
    "get_sprites_by_name",
    "get_sprites_by_tag",
    "remove_sprite",
    "try_move_sprite",
}
_LEVEL_TRANSFORMS = {
    "clone",
    "color_remap",
    "set_mirror_lr",
    "set_mirror_ud",
    "set_position",
    "set_rotation",
    "set_scale",
    "set_visible",
}
_FRAMEWORK_STATE = {
    "_action_count",
    "_available_actions",
    "_clean_levels",
    "_current_level_index",
    "_levels",
    "action",
    "current_level",
    "height",
    "level_index",
    "width",
}


def _json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def _without_digest(value: Mapping[str, Any]) -> dict[str, Any]:
    body = dict(value)
    body.pop("content_digest", None)
    return body


def load_development_level_ledger(path: Path) -> dict[str, Any]:
    """Load the 183-row development analysis ledger with fail-closed checks."""

    ledger = _json_object(path)
    failures: list[str] = []
    actual_digest = DEVELOPMENT_LEDGER_DIGEST_PREFIX + digest_object(
        _without_digest(ledger)
    )
    if ledger.get("content_digest") != actual_digest:
        failures.append("DEVELOPMENT_LEVEL_LEDGER_DIGEST_INVALID")
    if ledger.get("schema_version") != DEVELOPMENT_LEDGER_SCHEMA_VERSION:
        failures.append("DEVELOPMENT_LEVEL_LEDGER_SCHEMA_INVALID")
    if ledger.get("development_only") is not True:
        failures.append("DEVELOPMENT_LEVEL_LEDGER_BOUNDARY_INVALID")
    if ledger.get("runtime_use") != "FORBIDDEN":
        failures.append("DEVELOPMENT_LEVEL_LEDGER_RUNTIME_USE_INVALID")
    raw_rows = ledger.get("rows")
    if not isinstance(raw_rows, list):
        failures.append("DEVELOPMENT_LEVEL_LEDGER_ROWS_INVALID")
        raw_rows = []
    keys = {
        (str(row.get("game_id")), row.get("level"))
        for row in raw_rows
        if isinstance(row, dict)
    }
    if len(raw_rows) != 183 or len(keys) != 183:
        failures.append("DEVELOPMENT_LEVEL_LEDGER_COVERAGE_INVALID")
    if failures:
        raise ValueError(";".join(sorted(set(failures))))
    return ledger


def _sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _node_digest(node: ast.AST) -> str:
    return digest_object(
        {
            "ast": ast.dump(
                node,
                annotate_fields=True,
                include_attributes=False,
            )
        }
    )


def _source_expression(node: ast.AST | None) -> str:
    if node is None:
        return ""
    return ast.unparse(node)


def _source_location(node: ast.AST) -> dict[str, int]:
    return {
        "line": int(getattr(node, "lineno", 0)),
        "end_line": int(getattr(node, "end_lineno", 0)),
        "column": int(getattr(node, "col_offset", 0)),
        "end_column": int(getattr(node, "end_col_offset", 0)),
    }


def _literal_string(node: ast.AST | None) -> str | None:
    if isinstance(node, ast.Constant) and isinstance(node.value, str):
        return node.value
    return None


def _keyword(call: ast.Call, name: str) -> ast.AST | None:
    for item in call.keywords:
        if item.arg == name:
            return item.value
    return None


def _call_attribute(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Attribute):
        return call.func.attr
    if isinstance(call.func, ast.Name):
        return call.func.id
    return None


def _self_call_attribute(call: ast.Call) -> str | None:
    if (
        isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id == "self"
    ):
        return call.func.attr
    return None


def _assignment_value(module: ast.Module, name: str) -> ast.AST:
    for statement in module.body:
        if not isinstance(statement, (ast.Assign, ast.AnnAssign)):
            continue
        targets = (
            statement.targets
            if isinstance(statement, ast.Assign)
            else [statement.target]
        )
        if any(
            isinstance(target, ast.Name) and target.id == name
            for target in targets
        ):
            if statement.value is None:
                break
            return statement.value
    raise ValueError(f"SOURCE_ASSIGNMENT_NOT_FOUND:{name}")


def _game_class(module: ast.Module) -> ast.ClassDef:
    matches = [
        item
        for item in module.body
        if isinstance(item, ast.ClassDef)
        and any(
            isinstance(base, ast.Name) and base.id == "ARCBaseGame"
            for base in item.bases
        )
    ]
    if len(matches) != 1:
        raise ValueError(
            "SOURCE_GAME_CLASS_COUNT_INVALID:"
            f"expected=1:actual={len(matches)}"
        )
    return matches[0]


def _parent_edges(root: ast.AST) -> dict[ast.AST, tuple[ast.AST, str]]:
    edges: dict[ast.AST, tuple[ast.AST, str]] = {}
    for parent in ast.walk(root):
        for field_name, value in ast.iter_fields(parent):
            if isinstance(value, ast.AST):
                edges[value] = (parent, field_name)
            elif isinstance(value, list):
                for child in value:
                    if isinstance(child, ast.AST):
                        edges[child] = (parent, field_name)
    return edges


def _ancestor_predicates(
    node: ast.AST,
    parents: Mapping[ast.AST, tuple[ast.AST, str]],
) -> list[dict[str, Any]]:
    predicates: list[dict[str, Any]] = []
    current = node
    while current in parents:
        parent, field_name = parents[current]
        if isinstance(parent, ast.If):
            branch = "FALSE" if field_name == "orelse" else "TRUE"
            predicates.append(
                {
                    "expression": _source_expression(parent.test),
                    "branch": branch,
                    "source_location": _source_location(parent.test),
                    "predicate_digest": _node_digest(parent.test),
                }
            )
        elif isinstance(parent, ast.While):
            predicates.append(
                {
                    "expression": _source_expression(parent.test),
                    "branch": "LOOP_BODY",
                    "source_location": _source_location(parent.test),
                    "predicate_digest": _node_digest(parent.test),
                }
            )
        current = parent
    predicates.reverse()
    return predicates


def _self_attributes(node: ast.AST) -> list[str]:
    called_attributes = {
        item.func
        for item in ast.walk(node)
        if isinstance(item, ast.Call)
        and isinstance(item.func, ast.Attribute)
    }
    return sorted(
        {
            item.attr
            for item in ast.walk(node)
            if isinstance(item, ast.Attribute)
            and isinstance(item.value, ast.Name)
            and item.value.id == "self"
            and item not in called_attributes
        }
    )


def _ancestor_source_state(
    node: ast.AST,
    parents: Mapping[ast.AST, tuple[ast.AST, str]],
) -> list[str]:
    state: set[str] = set()
    current = node
    while current in parents:
        parent, _ = parents[current]
        if isinstance(parent, (ast.If, ast.While)):
            state.update(_self_attributes(parent.test))
        current = parent
    return sorted(state)


def _string_constants(node: ast.AST) -> list[str]:
    return sorted(
        {
            item.value
            for item in ast.walk(node)
            if isinstance(item, ast.Constant)
            and isinstance(item.value, str)
            and item.value
        }
    )


def _method_map(game_class: ast.ClassDef) -> dict[str, ast.FunctionDef]:
    return {
        item.name: item
        for item in game_class.body
        if isinstance(item, ast.FunctionDef)
    }


def _call_graph(
    methods: Mapping[str, ast.FunctionDef],
) -> tuple[
    dict[str, set[str]],
    dict[tuple[str, str], list[ast.Call]],
]:
    graph: dict[str, set[str]] = {
        method_name: set() for method_name in methods
    }
    sites: defaultdict[tuple[str, str], list[ast.Call]] = defaultdict(list)
    for caller, method in methods.items():
        for node in ast.walk(method):
            if not isinstance(node, ast.Call):
                continue
            callee = _self_call_attribute(node)
            if callee is None or callee not in methods:
                continue
            graph[caller].add(callee)
            sites[(caller, callee)].append(node)
    return graph, dict(sites)


def _reachable_methods(
    graph: Mapping[str, set[str]],
    root: str,
) -> set[str]:
    if root not in graph:
        raise ValueError(f"SOURCE_ENTRY_METHOD_MISSING:{root}")
    reached: set[str] = set()
    pending = [root]
    while pending:
        current = pending.pop()
        if current in reached:
            continue
        reached.add(current)
        pending.extend(sorted(graph[current].difference(reached)))
    return reached


def _shortest_method_path(
    graph: Mapping[str, set[str]],
    *,
    root: str,
    target: str,
) -> list[str]:
    pending: deque[list[str]] = deque([[root]])
    visited = {root}
    while pending:
        path = pending.popleft()
        current = path[-1]
        if current == target:
            return path
        for successor in sorted(graph.get(current, set())):
            if successor in visited:
                continue
            visited.add(successor)
            pending.append([*path, successor])
    return []


def _call_path_evidence(
    path: Sequence[str],
    *,
    call_sites: Mapping[tuple[str, str], list[ast.Call]],
    parents: Mapping[ast.AST, tuple[ast.AST, str]],
) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    for caller, callee in zip(path, path[1:]):
        sites = sorted(
            call_sites.get((caller, callee), []),
            key=lambda item: (
                int(getattr(item, "lineno", 0)),
                int(getattr(item, "col_offset", 0)),
            ),
        )
        evidence.append(
            {
                "caller": caller,
                "callee": callee,
                "call_sites": [
                    {
                        "source_location": _source_location(site),
                        "path_predicates": _ancestor_predicates(
                            site,
                            parents,
                        ),
                        "condition_source_state": (
                            _ancestor_source_state(site, parents)
                        ),
                        "call_digest": _node_digest(site),
                    }
                    for site in sites
                ],
            }
        )
    return evidence


def _terminal_witnesses(
    *,
    methods: Mapping[str, ast.FunctionDef],
    graph: Mapping[str, set[str]],
    call_sites: Mapping[tuple[str, str], list[ast.Call]],
    reachable: set[str],
    parents: Mapping[ast.AST, tuple[ast.AST, str]],
) -> dict[str, list[dict[str, Any]]]:
    witnesses: dict[str, list[dict[str, Any]]] = {
        event: [] for event in _TERMINAL_CALLS.values()
    }
    for method_name in sorted(reachable):
        method = methods[method_name]
        for node in ast.walk(method):
            if not isinstance(node, ast.Call):
                continue
            call_name = _self_call_attribute(node)
            if call_name not in _TERMINAL_CALLS:
                continue
            event = _TERMINAL_CALLS[call_name]
            path = _shortest_method_path(
                graph,
                root="step",
                target=method_name,
            )
            predicates = _ancestor_predicates(node, parents)
            condition_state = sorted(
                {
                    state
                    for predicate in predicates
                    for state in _self_attributes(
                        next(
                            (
                                item
                                for item in ast.walk(method)
                                if isinstance(item, (ast.If, ast.While))
                                and _node_digest(item.test)
                                == predicate["predicate_digest"]
                            ),
                            method,
                        )
                    )
                }
            )
            body: dict[str, Any] = {
                "event": event,
                "source_call": f"self.{call_name}()",
                "method": method_name,
                "method_reachable_from_step": bool(path),
                "method_path_from_step": path,
                "method_path_evidence": _call_path_evidence(
                    path,
                    call_sites=call_sites,
                    parents=parents,
                ),
                "source_location": _source_location(node),
                "path_predicates": predicates,
                "condition_source_state": condition_state,
                "method_source_state": _self_attributes(method),
                "method_source_digest": _node_digest(method),
            }
            witnesses[event].append(
                {
                    **body,
                    "witness_digest": digest_object(body),
                }
            )
    for rows in witnesses.values():
        rows.sort(
            key=lambda item: (
                str(item["method"]),
                int(item["source_location"]["line"]),
                int(item["source_location"]["column"]),
            )
        )
    return witnesses


def _contains_action_reference(node: ast.AST) -> bool:
    for item in ast.walk(node):
        if (
            isinstance(item, ast.Attribute)
            and isinstance(item.value, ast.Name)
            and item.value.id == "GameAction"
        ):
            return True
        if (
            isinstance(item, ast.Attribute)
            and isinstance(item.value, ast.Name)
            and item.value.id == "self"
            and item.attr == "action"
        ):
            return True
        if isinstance(item, ast.Name) and (
            item.id in {"action", "action_id"} or "action" in item.id.casefold()
        ):
            return True
    return False


def _action_ids(node: ast.AST) -> list[int]:
    ids: set[int] = set()
    for item in ast.walk(node):
        if (
            isinstance(item, ast.Attribute)
            and isinstance(item.value, ast.Name)
            and item.value.id == "GameAction"
        ):
            if item.attr == "RESET":
                ids.add(0)
            elif item.attr.startswith("ACTION"):
                suffix = item.attr.removeprefix("ACTION")
                if suffix.isdecimal() and 1 <= int(suffix) <= 7:
                    ids.add(int(suffix))
        if isinstance(item, ast.Compare) and _contains_action_reference(item):
            for candidate in [item.left, *item.comparators]:
                if (
                    isinstance(candidate, ast.Constant)
                    and isinstance(candidate.value, int)
                    and not isinstance(candidate.value, bool)
                    and 0 <= candidate.value <= 7
                ):
                    ids.add(candidate.value)
    return sorted(ids)


def _action_handlers(
    methods: Mapping[str, ast.FunctionDef],
    reachable: set[str],
) -> list[dict[str, Any]]:
    handlers: list[dict[str, Any]] = []
    for method_name in sorted(reachable):
        method = methods[method_name]
        for node in ast.walk(method):
            if not isinstance(node, (ast.If, ast.While)):
                continue
            if not _contains_action_reference(node.test):
                continue
            called_methods = sorted(
                {
                    call_name
                    for item in ast.walk(node)
                    if isinstance(item, ast.Call)
                    and (call_name := _self_call_attribute(item)) is not None
                    and call_name in methods
                }
            )
            body: dict[str, Any] = {
                "method": method_name,
                "source_location": _source_location(node.test),
                "predicate": _source_expression(node.test),
                "action_ids": _action_ids(node.test),
                "source_state": _self_attributes(node),
                "called_source_methods": called_methods,
                "control_kind": type(node).__name__,
                "source_ast_digest": _node_digest(node),
            }
            handlers.append(
                {
                    **body,
                    "handler_digest": digest_object(body),
                }
            )
    handlers.sort(
        key=lambda item: (
            str(item["method"]),
            int(item["source_location"]["line"]),
        )
    )
    return handlers


def _method_role(
    method_name: str,
    *,
    goal_methods: set[str],
    hazard_methods: set[str],
) -> list[str]:
    roles = ["ACTION_EFFECT_SOURCE_QUERY"]
    if method_name in goal_methods:
        roles.append("GOAL_CONTROL_PATH_SOURCE_QUERY")
    if method_name in hazard_methods:
        roles.append("HAZARD_CONTROL_PATH_SOURCE_QUERY")
    return roles


def _object_queries(
    methods: Mapping[str, ast.FunctionDef],
    reachable: set[str],
    *,
    goal_methods: set[str],
    hazard_methods: set[str],
) -> list[dict[str, Any]]:
    queries: list[dict[str, Any]] = []
    for method_name in sorted(reachable):
        method = methods[method_name]
        for node in ast.walk(method):
            if not isinstance(node, ast.Call):
                continue
            query = _call_attribute(node)
            if query not in _OBJECT_QUERY_CALLS:
                continue
            body: dict[str, Any] = {
                "method": method_name,
                "query": query,
                "arguments": [
                    _source_expression(argument) for argument in node.args
                ],
                "literal_symbols": _string_constants(node),
                "source_location": _source_location(node),
                "causal_roles": _method_role(
                    method_name,
                    goal_methods=goal_methods,
                    hazard_methods=hazard_methods,
                ),
                "source_ast_digest": _node_digest(node),
            }
            queries.append(
                {
                    **body,
                    "query_digest": digest_object(body),
                }
            )
    queries.sort(
        key=lambda item: (
            str(item["method"]),
            int(item["source_location"]["line"]),
            str(item["query"]),
        )
    )
    return queries


def _hidden_state_model(
    methods: Mapping[str, ast.FunctionDef],
) -> dict[str, Any]:
    method = methods.get("_get_hidden_state")
    if method is None:
        return {
            "status": "EXPLICIT_NO_CUSTOM_HIDDEN_STATE_EXPORT",
            "method_present": False,
            "exported_source_state": [],
            "return_expressions": [],
            "source_location": None,
            "method_source_digest": None,
        }
    returns = [
        _source_expression(item.value)
        for item in ast.walk(method)
        if isinstance(item, ast.Return) and item.value is not None
    ]
    return {
        "status": "CUSTOM_HIDDEN_STATE_EXPORT_SOURCE_BOUND",
        "method_present": True,
        "exported_source_state": _self_attributes(method),
        "return_expressions": returns,
        "source_location": _source_location(method),
        "method_source_digest": _node_digest(method),
    }


def _state_variable_inventory(
    methods: Mapping[str, ast.FunctionDef],
    reachable: set[str],
    *,
    goal_witnesses: Sequence[Mapping[str, Any]],
    hazard_witnesses: Sequence[Mapping[str, Any]],
    hidden_model: Mapping[str, Any],
) -> list[dict[str, Any]]:
    goal_state = {
        str(value)
        for witness in goal_witnesses
        for field in ("condition_source_state", "method_source_state")
        for value in witness.get(field, [])
    }
    hazard_state = {
        str(value)
        for witness in hazard_witnesses
        for field in ("condition_source_state", "method_source_state")
        for value in witness.get(field, [])
    }
    hidden_state = {
        str(value)
        for value in hidden_model.get("exported_source_state", [])
    }
    references: defaultdict[str, list[ast.Attribute]] = defaultdict(list)
    for method_name in sorted(reachable):
        method = methods[method_name]
        called_attributes = {
            item.func
            for item in ast.walk(method)
            if isinstance(item, ast.Call)
            and isinstance(item.func, ast.Attribute)
        }
        for item in ast.walk(method):
            if (
                isinstance(item, ast.Attribute)
                and isinstance(item.value, ast.Name)
                and item.value.id == "self"
                and item not in called_attributes
            ):
                references[item.attr].append(item)
    variables: list[dict[str, Any]] = []
    for name in sorted(references):
        roles = ["ACTION_TRANSITION_STATE"]
        if name in goal_state:
            roles.append("GOAL_CAUSAL_STATE")
        if name in hazard_state:
            roles.append("HAZARD_CAUSAL_STATE")
        if name in hidden_state:
            roles.append("HIDDEN_STATE_EXPORT")
        if name in _FRAMEWORK_STATE:
            roles.append("FRAMEWORK_CONTROL_STATE")
        nodes = references[name]
        variables.append(
            {
                "source_symbol": f"self.{name}",
                "causal_roles": roles,
                "reference_count": len(nodes),
                "source_lines": sorted(
                    {
                        int(getattr(node, "lineno", 0))
                        for node in nodes
                    }
                ),
            }
        )
    return variables


def _sprite_catalog(value: ast.AST) -> dict[str, dict[str, Any]]:
    if not isinstance(value, ast.Dict):
        raise TypeError("SOURCE_SPRITES_MUST_BE_DICT")
    catalog: dict[str, dict[str, Any]] = {}
    for key_node, value_node in zip(value.keys, value.values):
        key = _literal_string(key_node)
        if key is None:
            raise TypeError("SOURCE_SPRITE_KEY_MUST_BE_STRING")
        name: str | None = None
        tags: list[str] = []
        visible: bool | None = None
        collidable: bool | None = None
        if isinstance(value_node, ast.Call):
            name = _literal_string(_keyword(value_node, "name"))
            raw_tags = _keyword(value_node, "tags")
            if isinstance(raw_tags, (ast.List, ast.Tuple)):
                for item in raw_tags.elts:
                    tag_value = _literal_string(item)
                    if tag_value is not None:
                        tags.append(tag_value)
            for field_name in ("visible", "collidable"):
                raw = _keyword(value_node, field_name)
                if (
                    isinstance(raw, ast.Constant)
                    and isinstance(raw.value, bool)
                ):
                    if field_name == "visible":
                        visible = raw.value
                    else:
                        collidable = raw.value
        catalog[key] = {
            "source_sprite_key": key,
            "declared_name": name,
            "declared_tags": sorted(set(tags)),
            "declared_visible": visible,
            "declared_collidable": collidable,
            "definition_source_location": _source_location(value_node),
            "definition_digest": _node_digest(value_node),
        }
    return catalog


def _small_literal(node: ast.AST) -> object | None:
    try:
        value = ast.literal_eval(node)
    except (ValueError, TypeError, SyntaxError, MemoryError, RecursionError):
        return None
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, (list, tuple, dict)) and len(value) <= 16:
        serialized = json.dumps(value, ensure_ascii=False, default=str)
        if len(serialized) <= 512:
            return value
    return None


def _level_data_fields(level_call: ast.Call) -> list[dict[str, Any]]:
    raw_data = _keyword(level_call, "data")
    if raw_data is None:
        return []
    if not isinstance(raw_data, ast.Dict):
        return [
            {
                "source_key": "DYNAMIC_DATA_EXPRESSION",
                "value_kind": type(raw_data).__name__,
                "value_preview": None,
                "value_expression": _source_expression(raw_data),
                "value_digest": _node_digest(raw_data),
            }
        ]
    fields: list[dict[str, Any]] = []
    for key_node, value_node in zip(raw_data.keys, raw_data.values):
        key = _literal_string(key_node)
        fields.append(
            {
                "source_key": (
                    key if key is not None else _source_expression(key_node)
                ),
                "value_kind": type(value_node).__name__,
                "value_preview": _small_literal(value_node),
                "value_expression": _source_expression(value_node),
                "value_digest": _node_digest(value_node),
            }
        )
    return fields


def _level_object_families(
    level_call: ast.Call,
    *,
    catalog: Mapping[str, Mapping[str, Any]],
    query_roles_by_symbol: Mapping[str, set[str]],
) -> list[dict[str, Any]]:
    counts: Counter[str] = Counter()
    for node in ast.walk(level_call):
        if (
            isinstance(node, ast.Subscript)
            and isinstance(node.value, ast.Name)
            and node.value.id == "sprites"
        ):
            key = _literal_string(node.slice)
            if key is not None:
                counts[key] += 1
    families: list[dict[str, Any]] = []
    for key in sorted(counts):
        if key not in catalog:
            raise ValueError(f"SOURCE_LEVEL_UNKNOWN_SPRITE:{key}")
        definition = catalog[key]
        symbols = {
            key,
            str(definition.get("declared_name") or ""),
            *(
                str(tag)
                for tag in definition.get("declared_tags", [])
            ),
        }
        roles = {"LEVEL_STATE_OBJECT"}
        if "sys_click" in definition.get("declared_tags", []):
            roles.add("POINTER_AFFORDANCE")
        if definition.get("declared_collidable") is True:
            roles.add("COLLISION_PARTICIPANT")
        if definition.get("declared_visible") is False:
            roles.add("SOURCE_HIDDEN_OBJECT")
        for symbol in symbols:
            roles.update(query_roles_by_symbol.get(symbol, set()))
        body: dict[str, Any] = {
            "source_sprite_key": key,
            "instance_count": counts[key],
            "declared_name": definition.get("declared_name"),
            "declared_tags": definition.get("declared_tags", []),
            "definition_digest": definition.get("definition_digest"),
            "causal_roles": sorted(roles),
        }
        families.append(
            {
                **body,
                "object_family_digest": digest_object(body),
            }
        )
    return families


def _query_roles_by_symbol(
    queries: Sequence[Mapping[str, Any]],
) -> dict[str, set[str]]:
    roles: defaultdict[str, set[str]] = defaultdict(set)
    for query in queries:
        for raw_symbol in query.get("literal_symbols", []):
            symbol = str(raw_symbol)
            for raw_role in query.get("causal_roles", []):
                roles[symbol].add(str(raw_role))
    return dict(roles)


def _level_contracts(
    value: ast.AST,
    *,
    catalog: Mapping[str, Mapping[str, Any]],
    queries: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    if not isinstance(value, (ast.List, ast.Tuple)):
        raise TypeError("SOURCE_LEVELS_MUST_BE_LIST")
    query_roles = _query_roles_by_symbol(queries)
    contracts: list[dict[str, Any]] = []
    for level, item in enumerate(value.elts, start=1):
        if not isinstance(item, ast.Call) or _call_attribute(item) != "Level":
            raise TypeError(f"SOURCE_LEVEL_CALL_INVALID:{level}")
        grid_node = _keyword(item, "grid_size")
        grid_literal = _small_literal(grid_node) if grid_node else None
        transforms = sorted(
            {
                node.attr
                for node in ast.walk(item)
                if isinstance(node, ast.Attribute)
                and node.attr in _LEVEL_TRANSFORMS
            }
        )
        body: dict[str, Any] = {
            "schema_version": LEVEL_SOURCE_CONTRACT_SCHEMA_VERSION,
            "development_only": True,
            "runtime_use": "FORBIDDEN",
            "level": level,
            "source_location": _source_location(item),
            "source_level_ast_digest": _node_digest(item),
            "grid_size": grid_literal,
            "grid_size_expression": _source_expression(grid_node),
            "level_data_fields": _level_data_fields(item),
            "object_families": _level_object_families(
                item,
                catalog=catalog,
                query_roles_by_symbol=query_roles,
            ),
            "source_transform_operations": transforms,
        }
        contracts.append(
            {
                **body,
                "content_digest": (
                    LEVEL_SOURCE_CONTRACT_DIGEST_PREFIX
                    + digest_object(body)
                ),
            }
        )
    return contracts


def _event_method_closure(
    witnesses: Sequence[Mapping[str, Any]],
) -> set[str]:
    return {
        str(method)
        for witness in witnesses
        for method in witness.get("method_path_from_step", [])
    }


def _legacy_rows_by_key(
    ledger: Mapping[str, Any],
) -> dict[tuple[str, int], Mapping[str, Any]]:
    rows: dict[tuple[str, int], Mapping[str, Any]] = {}
    raw_rows = ledger.get("rows")
    if not isinstance(raw_rows, list):
        raise TypeError("DEVELOPMENT_LEVEL_LEDGER_ROWS_INVALID")
    for raw_row in raw_rows:
        if not isinstance(raw_row, Mapping):
            raise TypeError("DEVELOPMENT_LEVEL_LEDGER_ROW_INVALID")
        level = raw_row.get("level")
        if isinstance(level, bool) or not isinstance(level, int):
            raise TypeError("DEVELOPMENT_LEVEL_LEDGER_LEVEL_INVALID")
        key = (str(raw_row.get("game_id", "")), level)
        if key in rows:
            raise ValueError(f"DEVELOPMENT_LEVEL_LEDGER_DUPLICATE:{key}")
        rows[key] = raw_row
    return rows


def _development_mechanic_model(
    row: Mapping[str, Any],
    *,
    direct_source_evidence_digest: str,
    direct_source_level_evidence_digest: str,
) -> dict[str, Any]:
    return {
        "mechanics_id": str(row.get("mechanics_id", "")),
        "mechanics_id_basis": str(row.get("mechanics_id_basis", "")),
        "operation_type": str(row.get("operation_type", "")),
        "transition_relation": str(
            row.get("legacy_transition_relation", "")
        ),
        "semantic_state_variables": sorted(
            str(item) for item in row.get("state_variables", [])
        ),
        "local_effect_classes": sorted(
            str(item) for item in row.get("local_effect_classes", [])
        ),
        "failure_signature": str(row.get("failure_signature", "")),
        "progress_condition": str(
            row.get("legacy_progress_condition", "")
        ),
        "hazard_condition": str(
            row.get("legacy_hazard_condition", "")
        ),
        "evidence_refs": sorted(
            str(item) for item in row.get("evidence_refs", [])
        ),
        "legacy_validation_status": str(
            row.get("current_validation_status", "")
        ),
        "authority": (
            "DEVELOPMENT_HYPOTHESIS_BOUND_TO_DIRECT_SOURCE_AND_S0_SUCCESS;"
            "NOT_A_RUNTIME_RULE"
        ),
        "direct_source_evidence_digest": direct_source_evidence_digest,
        "direct_source_level_evidence_digest": (
            direct_source_level_evidence_digest
        ),
    }


def _compile_game_source_contract(
    *,
    metadata_path: Path,
    environments_dir: Path,
    legacy_rows: Mapping[tuple[str, int], Mapping[str, Any]],
) -> dict[str, Any]:
    metadata = _json_object(metadata_path)
    game_id = str(metadata.get("game_id", ""))
    if not game_id:
        raise ValueError(f"SOURCE_METADATA_GAME_ID_MISSING:{metadata_path}")
    source_files = sorted(metadata_path.parent.glob("*.py"))
    if len(source_files) != 1:
        raise ValueError(
            f"SOURCE_GAME_FILE_COUNT_INVALID:{game_id}:{len(source_files)}"
        )
    source_path = source_files[0]
    source_bytes = source_path.read_bytes()
    source_text = source_bytes.decode("utf-8")
    module = ast.parse(source_text, filename=str(source_path))
    game_class = _game_class(module)
    methods = _method_map(game_class)
    graph, call_sites = _call_graph(methods)
    reachable = _reachable_methods(graph, "step")
    parents = _parent_edges(game_class)
    terminal = _terminal_witnesses(
        methods=methods,
        graph=graph,
        call_sites=call_sites,
        reachable=reachable,
        parents=parents,
    )
    goals = terminal["GOAL_ADVANCE"]
    hazards = terminal["HAZARD_TERMINATION"]
    commits = terminal["ACTION_COMMIT"]
    if not goals:
        raise ValueError(f"SOURCE_GOAL_WITNESS_MISSING:{game_id}")
    if not hazards:
        raise ValueError(f"SOURCE_HAZARD_WITNESS_MISSING:{game_id}")
    if any(
        witness.get("method_reachable_from_step") is not True
        for witness in [*goals, *hazards]
    ):
        raise ValueError(f"SOURCE_TERMINAL_WITNESS_UNREACHABLE:{game_id}")
    goal_methods = _event_method_closure(goals)
    hazard_methods = _event_method_closure(hazards)
    queries = _object_queries(
        methods,
        reachable,
        goal_methods=goal_methods,
        hazard_methods=hazard_methods,
    )
    hidden_model = _hidden_state_model(methods)
    state_variables = _state_variable_inventory(
        methods,
        reachable,
        goal_witnesses=goals,
        hazard_witnesses=hazards,
        hidden_model=hidden_model,
    )
    levels = _level_contracts(
        _assignment_value(module, "levels"),
        catalog=_sprite_catalog(_assignment_value(module, "sprites")),
        queries=queries,
    )
    expected_keys = {(game_id, level) for level in range(1, len(levels) + 1)}
    if not expected_keys.issubset(legacy_rows):
        missing = sorted(expected_keys.difference(legacy_rows))
        raise ValueError(
            f"SOURCE_DEVELOPMENT_SEMANTICS_MISSING:{game_id}:{missing}"
        )
    relative_path = source_path.relative_to(environments_dir.parent).as_posix()
    source_body: dict[str, Any] = {
        "schema_version": GAME_SOURCE_CONTRACT_SCHEMA_VERSION,
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "game_id": game_id,
        "source_path": relative_path,
        "source_sha256": _sha256_bytes(source_bytes),
        "source_line_count": len(source_text.splitlines()),
        "game_class": game_class.name,
        "game_class_source_location": _source_location(game_class),
        "game_class_source_digest": _node_digest(game_class),
        "level_count": len(levels),
        "reachable_method_count": len(reachable),
        "reachable_methods": sorted(reachable),
        "action_transition_entry": {
            "method": "step",
            "source_location": _source_location(methods["step"]),
            "source_state": _self_attributes(methods["step"]),
            "called_source_methods": sorted(graph["step"]),
            "method_source_digest": _node_digest(methods["step"]),
        },
        "action_handlers": _action_handlers(methods, reachable),
        "source_object_queries": queries,
        "source_state_variables": state_variables,
        "hidden_state_model": hidden_model,
        "goal_witnesses": goals,
        "hazard_witnesses": hazards,
        "action_commit_witnesses": commits,
        "levels": levels,
        "source_causal_complete": True,
        "source_causal_completion_basis": [
            "PINNED_SOURCE_SHA256",
            "LEVEL_OBJECT_AND_DATA_AST",
            "STEP_REACHABLE_ACTION_CONTROL_FLOW",
            "STEP_REACHABLE_NEXT_LEVEL_WITNESS",
            "STEP_REACHABLE_LOSE_WITNESS",
            "SOURCE_STATE_ROLE_INVENTORY",
            "HIDDEN_STATE_EXPORT_OR_EXPLICIT_NONE",
        ],
    }
    direct_source_evidence_digest = (
        DIRECT_SOURCE_EVIDENCE_DIGEST_PREFIX + digest_object(source_body)
    )
    enriched_levels: list[dict[str, Any]] = []
    for level_contract in levels:
        level = int(level_contract["level"])
        direct_level_digest = str(level_contract["content_digest"])
        enriched_body = _without_digest(level_contract)
        enriched_body["direct_source_level_evidence_digest"] = (
            direct_level_digest
        )
        enriched_body["development_mechanic_model"] = (
            _development_mechanic_model(
                legacy_rows[(game_id, level)],
                direct_source_evidence_digest=(
                    direct_source_evidence_digest
                ),
                direct_source_level_evidence_digest=direct_level_digest,
            )
        )
        enriched_levels.append(
            {
                **enriched_body,
                "content_digest": (
                    LEVEL_SOURCE_CONTRACT_DIGEST_PREFIX
                    + digest_object(enriched_body)
                ),
            }
        )
    source_body["levels"] = enriched_levels
    source_body["direct_source_evidence_digest"] = (
        direct_source_evidence_digest
    )
    return {
        **source_body,
        "content_digest": (
            GAME_SOURCE_CONTRACT_DIGEST_PREFIX
            + digest_object(source_body)
        ),
    }


def compile_source_causal_semantics(
    *,
    environments_dir: Path,
    development_level_ledger_path: Path,
) -> dict[str, Any]:
    """Compile all 25 source files and 183 level definitions."""

    ledger = load_development_level_ledger(
        development_level_ledger_path
    )
    legacy_rows = _legacy_rows_by_key(ledger)
    metadata_paths = sorted(environments_dir.glob("*/*/metadata.json"))
    games = [
        _compile_game_source_contract(
            metadata_path=metadata_path,
            environments_dir=environments_dir,
            legacy_rows=legacy_rows,
        )
        for metadata_path in metadata_paths
    ]
    games.sort(key=lambda item: str(item["game_id"]))
    level_count = sum(int(game["level_count"]) for game in games)
    if len(games) != 25 or level_count != 183:
        raise ValueError(
            "SOURCE_CAUSAL_COVERAGE_INVALID:"
            f"games={len(games)}:levels={level_count}"
        )
    source_paths = [str(game["source_path"]) for game in games]
    if len(source_paths) != len(set(source_paths)):
        raise ValueError("SOURCE_CAUSAL_SOURCE_PATH_DUPLICATE")
    custom_hidden = sum(
        int(game["hidden_state_model"]["method_present"] is True)
        for game in games
    )
    body: dict[str, Any] = {
        "schema_version": SOURCE_SEMANTICS_SCHEMA_VERSION,
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "phase": "P10-R2-SOURCE-CAUSAL-SEMANTICS",
        "extraction_kind": (
            "DIRECT_STATIC_SOURCE_CAUSAL_EVIDENCE_PLUS_"
            "NONAUTHORITATIVE_DEVELOPMENT_LABELS"
        ),
        "development_level_ledger_digest": ledger.get("content_digest"),
        "game_count": len(games),
        "level_count": level_count,
        "source_causal_complete_game_count": sum(
            int(game["source_causal_complete"] is True) for game in games
        ),
        "source_causal_complete_level_count": level_count,
        "goal_witness_count": sum(
            len(game["goal_witnesses"]) for game in games
        ),
        "hazard_witness_count": sum(
            len(game["hazard_witnesses"]) for game in games
        ),
        "custom_hidden_state_export_game_count": custom_hidden,
        "explicit_no_custom_hidden_state_export_game_count": (
            len(games) - custom_hidden
        ),
        "games": games,
    }
    return {
        **body,
        "content_digest": SOURCE_SEMANTICS_DIGEST_PREFIX + digest_object(body),
    }


def source_contract_index(
    source_semantics: Mapping[str, Any],
) -> dict[tuple[str, int], tuple[Mapping[str, Any], Mapping[str, Any]]]:
    """Index validated game/level source contracts for graph compilation."""

    if source_semantics.get("schema_version") != SOURCE_SEMANTICS_SCHEMA_VERSION:
        raise ValueError("SOURCE_CAUSAL_SEMANTICS_SCHEMA_INVALID")
    if source_semantics.get("development_only") is not True:
        raise ValueError("SOURCE_CAUSAL_SEMANTICS_BOUNDARY_INVALID")
    if source_semantics.get("runtime_use") != "FORBIDDEN":
        raise ValueError("SOURCE_CAUSAL_SEMANTICS_RUNTIME_USE_INVALID")
    claimed = source_semantics.get("content_digest")
    actual = SOURCE_SEMANTICS_DIGEST_PREFIX + digest_object(
        _without_digest(source_semantics)
    )
    if claimed != actual:
        raise ValueError("SOURCE_CAUSAL_SEMANTICS_DIGEST_INVALID")
    raw_games = source_semantics.get("games")
    if not isinstance(raw_games, Sequence) or isinstance(
        raw_games,
        (str, bytes, bytearray),
    ):
        raise TypeError("SOURCE_CAUSAL_SEMANTICS_GAMES_INVALID")
    index: dict[
        tuple[str, int],
        tuple[Mapping[str, Any], Mapping[str, Any]],
    ] = {}
    for raw_game in raw_games:
        if not isinstance(raw_game, Mapping):
            raise TypeError("SOURCE_CAUSAL_GAME_INVALID")
        expected_game_digest = (
            GAME_SOURCE_CONTRACT_DIGEST_PREFIX
            + digest_object(_without_digest(raw_game))
        )
        if raw_game.get("content_digest") != expected_game_digest:
            raise ValueError("SOURCE_CAUSAL_GAME_DIGEST_INVALID")
        game_id = str(raw_game.get("game_id", ""))
        raw_levels = raw_game.get("levels")
        if not isinstance(raw_levels, Sequence) or isinstance(
            raw_levels,
            (str, bytes, bytearray),
        ):
            raise TypeError("SOURCE_CAUSAL_LEVELS_INVALID")
        for raw_level in raw_levels:
            if not isinstance(raw_level, Mapping):
                raise TypeError("SOURCE_CAUSAL_LEVEL_INVALID")
            expected_level_digest = (
                LEVEL_SOURCE_CONTRACT_DIGEST_PREFIX
                + digest_object(_without_digest(raw_level))
            )
            if raw_level.get("content_digest") != expected_level_digest:
                raise ValueError("SOURCE_CAUSAL_LEVEL_DIGEST_INVALID")
            level = raw_level.get("level")
            if isinstance(level, bool) or not isinstance(level, int):
                raise TypeError("SOURCE_CAUSAL_LEVEL_NUMBER_INVALID")
            key = (game_id, level)
            if key in index:
                raise ValueError(f"SOURCE_CAUSAL_LEVEL_DUPLICATE:{key}")
            index[key] = (raw_game, raw_level)
    if len(index) != 183:
        raise ValueError(
            f"SOURCE_CAUSAL_INDEX_COVERAGE_INVALID:{len(index)}"
        )
    return index


__all__ = [
    "GAME_SOURCE_CONTRACT_DIGEST_PREFIX",
    "LEVEL_SOURCE_CONTRACT_DIGEST_PREFIX",
    "SOURCE_SEMANTICS_DIGEST_PREFIX",
    "compile_source_causal_semantics",
    "load_development_level_ledger",
    "source_contract_index",
]
