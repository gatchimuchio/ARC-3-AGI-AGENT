"""Content-bound schema for the source/hidden-state-free S4 graph."""

from __future__ import annotations

import json
import re
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..schema import digest_object
from .s2_role_selector import validate_role_relative_selector

S4_POLICY_GRAPH_SCHEMA_VERSION = (
    "arc3-teacher-s4-source-hidden-free-policy-graph-v1"
)
S4_POLICY_GRAPH_DIGEST_PREFIX = (
    "arc3_teacher_s4_source_hidden_free_policy_graph:"
)
S4_ACTION_SIGNATURE_PREFIX = "arc3_teacher_s4_action:"

_GAME_ID_PATTERN = re.compile(r"^[a-z0-9]{4}-[0-9a-f]{8}$")
_FORBIDDEN_GRAPH_KEYS = frozenset(
    {
        "absolute_horizontal_index",
        "absolute_vertical_index",
        "action_data",
        "action_ordinal",
        "after_levels_completed",
        "before_levels_completed",
        "column",
        "coordinate",
        "current_level_data",
        "cursor",
        "custom_hidden_state",
        "environment_id",
        "game_class",
        "game_id",
        "games",
        "hidden_state",
        "level_id",
        "levels_completed",
        "replay_index",
        "row",
        "source_fields",
        "source_order",
        "source_state_digest",
        "source_step",
        "step",
        "target_levels",
        "task_id",
        "x",
        "y",
    }
)


def all_mapping_keys(value: object) -> set[str]:
    """Collect nested mapping keys for privilege audits."""

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


def identity_literal_values(value: object) -> set[str]:
    """Find concrete retained sample IDs anywhere in the policy."""

    if isinstance(value, Mapping):
        mapping_output: set[str] = set()
        for item in value.values():
            mapping_output.update(identity_literal_values(item))
        return mapping_output
    if isinstance(value, list):
        list_output: set[str] = set()
        for item in value:
            list_output.update(identity_literal_values(item))
        return list_output
    if isinstance(value, str) and _GAME_ID_PATTERN.fullmatch(value):
        return {value}
    return set()


def _validate_action(raw_action: object, failures: list[str]) -> None:
    if not isinstance(raw_action, Mapping):
        failures.append("S4_POLICY_ACTION_INVALID")
        return
    raw_id = raw_action.get("action_id")
    if (
        isinstance(raw_id, bool)
        or not isinstance(raw_id, int)
        or not 0 <= raw_id <= 7
    ):
        failures.append("S4_POLICY_ACTION_ID_INVALID")
        return
    selector = raw_action.get("target_selector")
    if raw_id == 6:
        if not isinstance(selector, Mapping):
            failures.append("S4_POINTER_SELECTOR_MISSING")
            return
        try:
            validate_role_relative_selector(selector)
        except (TypeError, ValueError):
            failures.append("S4_POINTER_SELECTOR_INVALID")
    elif selector is not None:
        failures.append("S4_NON_POINTER_SELECTOR_PRESENT")


def load_s4_policy_graph(
    path: Path,
    *,
    require_complete: bool = True,
) -> dict[str, Any]:
    """Load and fail closed on source/hidden or identity leakage."""

    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("S4_POLICY_GRAPH_INVALID")
    body = dict(value)
    claimed = body.pop("content_digest", None)
    failures: list[str] = []
    if claimed != S4_POLICY_GRAPH_DIGEST_PREFIX + digest_object(body):
        failures.append("S4_POLICY_GRAPH_DIGEST_INVALID")
    if value.get("schema_version") != S4_POLICY_GRAPH_SCHEMA_VERSION:
        failures.append("S4_POLICY_GRAPH_SCHEMA_INVALID")
    if value.get("development_only") is not True:
        failures.append("S4_POLICY_GRAPH_BOUNDARY_INVALID")
    if value.get("runtime_use") != "FORBIDDEN":
        failures.append("S4_POLICY_GRAPH_RUNTIME_USE_INVALID")
    if value.get("privilege_stage") != "S4":
        failures.append("S4_POLICY_GRAPH_STAGE_INVALID")
    if (
        value.get("policy_partition_count") != 1
        or value.get("identity_routing_key_count") != 0
        or value.get("source_hidden_decision_key_count") != 0
        or value.get(
            "target_environment_source_or_hidden_read_count"
        )
        != 0
        or value.get("source_state_digest_stored") is not False
        or value.get("hidden_state_stored") is not False
    ):
        failures.append("S4_POLICY_GRAPH_PRIVILEGED_ROUTING_PRESENT")
    dependencies = value.get("remaining_privilege_dependencies")
    if not isinstance(dependencies, Mapping):
        failures.append("S4_POLICY_GRAPH_DEPENDENCIES_INVALID")
    elif (
        dependencies.get("task_game_level_identity") is not False
        or dependencies.get("source_or_hidden_state") is not False
        or dependencies.get("fixed_action_sequence") is not False
        or dependencies.get("literal_coordinate") is not False
    ):
        failures.append("S4_POLICY_GRAPH_SUBTRACTION_INCOMPLETE")
    if require_complete and (
        value.get("complete_inventory") is not True
        or value.get("environment_count") != 25
        or value.get("level_count") != 183
        or value.get("source_transition_witness_count") != 10733
        or value.get("state_node_count") != 10758
        or value.get("edge_count") != 10733
        or value.get("initial_state_signature_count") != 25
        or value.get("goal_state_signature_count") != 25
        or value.get("role_selector_witness_count") != 3112
        or value.get("absolute_pointer_payload_count") != 0
        or value.get("strict_progress_policy") is not True
    ):
        failures.append("S4_POLICY_GRAPH_NOT_COMPLETE")
    forbidden = all_mapping_keys(value).intersection(
        _FORBIDDEN_GRAPH_KEYS
    )
    if forbidden:
        failures.append(
            "S4_POLICY_GRAPH_FORBIDDEN_KEY:"
            + ",".join(sorted(forbidden))
        )
    identity_literals = identity_literal_values(value)
    if identity_literals:
        failures.append(
            "S4_POLICY_GRAPH_IDENTITY_LITERAL:"
            + ",".join(sorted(identity_literals))
        )
    raw_initial = value.get("initial_state_signatures")
    if not isinstance(raw_initial, list) or not raw_initial:
        failures.append("S4_POLICY_GRAPH_INITIAL_STATES_INVALID")
        raw_initial = []
    elif (
        len(raw_initial) != len(set(str(item) for item in raw_initial))
        or value.get("initial_state_signature_count")
        != len(raw_initial)
    ):
        failures.append("S4_POLICY_GRAPH_INITIAL_STATES_INVALID")
    raw_goals = value.get("goal_state_signatures")
    if not isinstance(raw_goals, list) or not raw_goals:
        failures.append("S4_POLICY_GRAPH_GOAL_STATES_INVALID")
        raw_goals = []
    elif (
        len(raw_goals) != len(set(str(item) for item in raw_goals))
        or value.get("goal_state_signature_count") != len(raw_goals)
    ):
        failures.append("S4_POLICY_GRAPH_GOAL_STATES_INVALID")
    raw_nodes = value.get("nodes")
    if not isinstance(raw_nodes, list) or not raw_nodes:
        failures.append("S4_POLICY_GRAPH_NODES_INVALID")
        raw_nodes = []
    seen_signatures: set[str] = set()
    observed_edge_count = 0
    for raw_node in raw_nodes:
        if not isinstance(raw_node, Mapping):
            failures.append("S4_POLICY_GRAPH_NODE_INVALID")
            continue
        signature = raw_node.get("state_signature")
        if (
            not isinstance(signature, str)
            or not signature
            or signature in seen_signatures
        ):
            failures.append("S4_POLICY_GRAPH_NODE_ID_INVALID")
            continue
        seen_signatures.add(signature)
        raw_edges = raw_node.get("outgoing_edges")
        if not isinstance(raw_edges, list):
            failures.append("S4_POLICY_GRAPH_EDGES_INVALID")
            continue
        observed_edge_count += len(raw_edges)
        for raw_edge in raw_edges:
            if not isinstance(raw_edge, Mapping):
                failures.append("S4_POLICY_GRAPH_EDGE_INVALID")
                continue
            _validate_action(raw_edge.get("action"), failures)
    if value.get("state_node_count") != len(raw_nodes):
        failures.append("S4_POLICY_GRAPH_NODE_COUNT_INVALID")
    if value.get("edge_count") != observed_edge_count:
        failures.append("S4_POLICY_GRAPH_EDGE_COUNT_INVALID")
    if failures:
        raise ValueError(";".join(sorted(set(failures))))
    return value


__all__ = [
    "S4_ACTION_SIGNATURE_PREFIX",
    "S4_POLICY_GRAPH_DIGEST_PREFIX",
    "S4_POLICY_GRAPH_SCHEMA_VERSION",
    "all_mapping_keys",
    "identity_literal_values",
    "load_s4_policy_graph",
]
