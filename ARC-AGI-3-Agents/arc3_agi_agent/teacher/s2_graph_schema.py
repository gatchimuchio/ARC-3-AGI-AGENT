"""Content-bound schema for the development-only S2 policy graph."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..schema import digest_object
from .s2_role_selector import validate_role_relative_selector

S2_POLICY_GRAPH_SCHEMA_VERSION = (
    "arc3-teacher-s2-role-relative-policy-graph-v1"
)
S2_POLICY_GRAPH_DIGEST_PREFIX = (
    "arc3_teacher_s2_role_relative_policy_graph:"
)
S2_GAME_GRAPH_DIGEST_PREFIX = "arc3_teacher_s2_game_policy_graph:"
S2_ACTION_SIGNATURE_PREFIX = "arc3_teacher_s2_action:"

_FORBIDDEN_GRAPH_KEYS = frozenset(
    {
        "absolute_horizontal_index",
        "absolute_vertical_index",
        "action_data",
        "action_ordinal",
        "column",
        "coordinate",
        "cursor",
        "replay_index",
        "row",
        "source_order",
        "source_step",
        "step",
        "x",
        "y",
    }
)


def all_mapping_keys(value: object) -> set[str]:
    """Collect nested keys for fail-closed privilege audits."""

    if isinstance(value, Mapping):
        mapping_output = {str(key) for key in value}
        for item in value.values():
            mapping_output.update(all_mapping_keys(item))
        return mapping_output
    if isinstance(value, list):
        list_output: set[str] = set()
        for item in value:
            list_output.update(all_mapping_keys(item))
        return list_output
    return set()


def _validate_action(raw_action: object, failures: list[str]) -> None:
    if not isinstance(raw_action, Mapping):
        failures.append("S2_POLICY_ACTION_INVALID")
        return
    raw_id = raw_action.get("action_id")
    if (
        isinstance(raw_id, bool)
        or not isinstance(raw_id, int)
        or not 0 <= raw_id <= 7
    ):
        failures.append("S2_POLICY_ACTION_ID_INVALID")
        return
    selector = raw_action.get("target_selector")
    if raw_id == 6:
        if not isinstance(selector, Mapping):
            failures.append("S2_POINTER_SELECTOR_MISSING")
            return
        try:
            validate_role_relative_selector(selector)
        except (TypeError, ValueError):
            failures.append("S2_POINTER_SELECTOR_INVALID")
    elif selector is not None:
        failures.append("S2_NON_POINTER_SELECTOR_PRESENT")


def load_s2_policy_graph(
    path: Path,
    *,
    require_complete: bool = True,
) -> dict[str, Any]:
    """Load and fail closed on a malformed S2 policy graph."""

    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("S2_POLICY_GRAPH_INVALID")
    body = dict(value)
    claimed = body.pop("content_digest", None)
    failures: list[str] = []
    if (
        claimed
        != S2_POLICY_GRAPH_DIGEST_PREFIX + digest_object(body)
    ):
        failures.append("S2_POLICY_GRAPH_DIGEST_INVALID")
    if value.get("schema_version") != S2_POLICY_GRAPH_SCHEMA_VERSION:
        failures.append("S2_POLICY_GRAPH_SCHEMA_INVALID")
    if value.get("development_only") is not True:
        failures.append("S2_POLICY_GRAPH_BOUNDARY_INVALID")
    if value.get("runtime_use") != "FORBIDDEN":
        failures.append("S2_POLICY_GRAPH_RUNTIME_USE_INVALID")
    if value.get("privilege_stage") != "S2":
        failures.append("S2_POLICY_GRAPH_STAGE_INVALID")
    dependencies = value.get("remaining_privilege_dependencies")
    if not isinstance(dependencies, Mapping):
        failures.append("S2_POLICY_GRAPH_DEPENDENCIES_INVALID")
    elif (
        dependencies.get("fixed_action_sequence") is not False
        or dependencies.get("literal_coordinate") is not False
    ):
        failures.append("S2_POLICY_GRAPH_SUBTRACTION_INCOMPLETE")
    if value.get("absolute_pointer_payload_count") != 0:
        failures.append("S2_POLICY_GRAPH_ABSOLUTE_POINTER_PRESENT")
    if require_complete and (
        value.get("complete_inventory") is not True
        or value.get("game_count") != 25
        or value.get("level_count") != 183
        or value.get("source_transition_witness_count") != 10733
        or value.get("strict_progress_game_count") != 25
    ):
        failures.append("S2_POLICY_GRAPH_NOT_COMPLETE")
    forbidden = all_mapping_keys(value).intersection(
        _FORBIDDEN_GRAPH_KEYS
    )
    if forbidden:
        failures.append(
            "S2_POLICY_GRAPH_FORBIDDEN_KEY:" + ",".join(sorted(forbidden))
        )
    raw_games = value.get("games")
    if not isinstance(raw_games, list) or not raw_games:
        failures.append("S2_POLICY_GRAPH_GAMES_INVALID")
        raw_games = []
    for raw_game in raw_games:
        if not isinstance(raw_game, Mapping):
            failures.append("S2_GAME_GRAPH_INVALID")
            continue
        game_body = dict(raw_game)
        game_claimed = game_body.pop("content_digest", None)
        if (
            game_claimed
            != S2_GAME_GRAPH_DIGEST_PREFIX + digest_object(game_body)
        ):
            failures.append("S2_GAME_GRAPH_DIGEST_INVALID")
        if raw_game.get("strict_progress_policy") is not True:
            failures.append("S2_GAME_GRAPH_PROGRESS_POLICY_INVALID")
        raw_nodes = raw_game.get("nodes")
        if not isinstance(raw_nodes, list):
            failures.append("S2_GAME_GRAPH_NODES_INVALID")
            continue
        for raw_node in raw_nodes:
            if not isinstance(raw_node, Mapping):
                failures.append("S2_GAME_GRAPH_NODE_INVALID")
                continue
            raw_edges = raw_node.get("outgoing_edges")
            if not isinstance(raw_edges, list):
                failures.append("S2_GAME_GRAPH_EDGES_INVALID")
                continue
            for raw_edge in raw_edges:
                if not isinstance(raw_edge, Mapping):
                    failures.append("S2_GAME_GRAPH_EDGE_INVALID")
                    continue
                _validate_action(raw_edge.get("action"), failures)
    if failures:
        raise ValueError(";".join(sorted(set(failures))))
    return value


__all__ = [
    "S2_ACTION_SIGNATURE_PREFIX",
    "S2_GAME_GRAPH_DIGEST_PREFIX",
    "S2_POLICY_GRAPH_DIGEST_PREFIX",
    "S2_POLICY_GRAPH_SCHEMA_VERSION",
    "all_mapping_keys",
    "load_s2_policy_graph",
]
