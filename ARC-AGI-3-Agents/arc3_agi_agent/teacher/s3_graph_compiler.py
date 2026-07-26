"""Compile S2 trajectories into one identity-routing-free S3 policy graph.

The development compiler may use S2 environment partitions to collect
successful transitions.  The emitted artifact has one global state index and
contains no task/game/level identity, per-environment graph partition, or
level-progress counter.  Source/hidden state and the answer-derived graph
remain explicit S3 privileges for subtraction at later stages.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
from collections import Counter, defaultdict, deque
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from arc_agi import Arcade, OperationMode  # type: ignore[import-untyped]
from arc_agi.local_wrapper import (  # type: ignore[import-untyped]
    LocalEnvironmentWrapper,
)
from arcengine import FrameDataRaw, GameAction

from ..protocol import AuthorityViolation
from ..schema import digest_object
from .render_state import rendered_frame_digest
from .s2_graph_schema import load_s2_policy_graph
from .s2_role_selector import (
    resolve_role_relative_selector,
    validate_role_relative_selector,
)
from .s2_state import (
    S2_ACTION_EFFECT_HISTORY_LIMIT,
)
from .s2_state import (
    state_condition_signature as s2_state_condition_signature,
)
from .s2_state import (
    transition_effect_record as s2_transition_effect_record,
)
from .s3_graph_schema import (
    S3_ACTION_SIGNATURE_PREFIX,
    S3_POLICY_GRAPH_DIGEST_PREFIX,
    S3_POLICY_GRAPH_SCHEMA_VERSION,
    identity_literal_values,
)
from .s3_state import (
    S3_ACTION_EFFECT_HISTORY_LIMIT,
)
from .s3_state import (
    state_condition_signature as s3_state_condition_signature,
)
from .s3_state import (
    transition_effect_record as s3_transition_effect_record,
)


class S3GraphCompilationError(RuntimeError):
    """Raised when S2 evidence cannot form a valid global S3 graph."""


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    return value


def _sequence(value: object, field_name: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(
        value,
        (str, bytes, bytearray),
    ):
        raise TypeError(f"{field_name} must be an array")
    return value


def _mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be an object")
    return value


def _frame_state(frame: FrameDataRaw) -> str:
    raw = getattr(frame.state, "value", frame.state)
    return str(raw).upper()


def _frame_levels(frame: FrameDataRaw) -> int:
    return _integer(frame.levels_completed, "levels_completed")


def _available_action_ids(frame: FrameDataRaw) -> list[int]:
    return [
        _integer(
            getattr(raw, "value", raw),
            "available_actions[]",
        )
        for raw in frame.available_actions
    ]


def _restore_environment_variable(name: str, prior: str | None) -> None:
    if prior is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = prior


def _source_node_index(
    source_graph: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    output: dict[str, Mapping[str, Any]] = {}
    for raw_node in _sequence(source_graph.get("nodes"), "nodes"):
        node = _mapping(raw_node, "node")
        signature = str(node.get("state_signature", ""))
        if not signature or signature in output:
            raise S3GraphCompilationError("S3_SOURCE_NODE_ID_INVALID")
        output[signature] = node
    return output


def _selected_source_edge(
    node: Mapping[str, Any],
) -> Mapping[str, Any]:
    selected = node.get("selected_action_signature")
    if not isinstance(selected, str) or not selected:
        raise S3GraphCompilationError(
            "S3_SOURCE_SELECTED_ACTION_MISSING"
        )
    matches = [
        edge
        for raw_edge in _sequence(
            node.get("outgoing_edges"),
            "outgoing_edges",
        )
        for edge in [_mapping(raw_edge, "outgoing_edge")]
        if edge.get("action_signature") == selected
    ]
    if len(matches) != 1:
        raise S3GraphCompilationError(
            "S3_SOURCE_SELECTED_ACTION_NOT_UNIQUE"
        )
    if matches[0].get("strict_distance_decrease") is not True:
        raise S3GraphCompilationError(
            "S3_SOURCE_SELECTED_ACTION_NOT_PROGRESSIVE"
        )
    return matches[0]


def _s3_action(
    *,
    frame: FrameDataRaw,
    source_action: Mapping[str, Any],
) -> dict[str, Any]:
    action_id = _integer(source_action.get("action_id"), "action_id")
    if not 0 <= action_id <= 7:
        raise S3GraphCompilationError("S3_ACTION_ID_INVALID")
    reset_scope = str(source_action.get("reset_scope", ""))
    if reset_scope not in {"RECORDED_ACTION", "LEVEL_COMPATIBILITY"}:
        raise S3GraphCompilationError("S3_RESET_SCOPE_INVALID")
    raw_selector = source_action.get("target_selector")
    selector: dict[str, Any] | None = None
    if action_id == 6:
        selector_mapping = _mapping(raw_selector, "target_selector")
        validate_role_relative_selector(selector_mapping)
        resolve_role_relative_selector(
            selector=selector_mapping,
            frame=frame,
        )
        selector = dict(selector_mapping)
    elif raw_selector is not None:
        raise S3GraphCompilationError(
            "S3_NON_POINTER_SELECTOR_PRESENT"
        )
    return {
        "action_id": action_id,
        "reset_scope": reset_scope,
        "target_selector": selector,
    }


def _execute_action(
    *,
    environment: LocalEnvironmentWrapper,
    frame: FrameDataRaw,
    state_signature: str,
    action: Mapping[str, Any],
) -> FrameDataRaw:
    action_id = _integer(action.get("action_id"), "action_id")
    available = _available_action_ids(frame)
    if action_id != 0 and action_id not in available:
        raise S3GraphCompilationError(
            f"S3_COMPILED_ACTION_UNAVAILABLE:{action_id}"
        )
    raw_selector = action.get("target_selector")
    transient_payload: dict[str, int] = {}
    selector_digest: str | None = None
    if action_id == 6:
        selector = _mapping(raw_selector, "target_selector")
        resolved = resolve_role_relative_selector(
            selector=selector,
            frame=frame,
        )
        transient_payload = {
            "x": resolved.horizontal_index,
            "y": resolved.vertical_index,
        }
        selector_digest = str(selector.get("content_digest", ""))
    elif raw_selector is not None:
        raise S3GraphCompilationError(
            "S3_NON_POINTER_SELECTOR_PRESENT"
        )

    reset_scope = str(action.get("reset_scope", ""))
    prior_reset_scope = os.environ.get("ONLY_RESET_LEVELS")
    if reset_scope == "LEVEL_COMPATIBILITY":
        os.environ["ONLY_RESET_LEVELS"] = "true"
    try:
        result = environment.step(
            GameAction.from_id(action_id),
            data=transient_payload,
            reasoning={
                "authority": "S3_GLOBAL_POLICY_COMPILER",
                "runtime_use": "FORBIDDEN",
                "condition_signature": state_signature,
                "target_selector_digest": selector_digest,
                "identity_routing_used": False,
                "policy_partition": "GLOBAL",
            },
        )
    finally:
        if reset_scope == "LEVEL_COMPATIBILITY":
            _restore_environment_variable(
                "ONLY_RESET_LEVELS",
                prior_reset_scope,
            )
    if not isinstance(result, FrameDataRaw):
        raise S3GraphCompilationError("S3_COMPILER_STEP_FAILED")
    return result


def _action_signature(action: Mapping[str, Any]) -> str:
    return S3_ACTION_SIGNATURE_PREFIX + digest_object(dict(action))


def _register_node(
    *,
    nodes: dict[str, dict[str, Any]],
    state_signature: str,
    condition: Mapping[str, object],
    source_environment_ordinal: int,
) -> dict[str, Any]:
    node = nodes.get(state_signature)
    if node is None:
        node = {
            "state_signature": state_signature,
            "condition": dict(condition),
            "observation_count": 0,
            "source_environment_ordinals": set(),
            "raw_edges": {},
        }
        nodes[state_signature] = node
    elif node["condition"] != dict(condition):
        raise S3GraphCompilationError(
            "S3_STATE_SIGNATURE_COLLISION:" + state_signature
        )
    node["observation_count"] = int(node["observation_count"]) + 1
    raw_origins = node.get("source_environment_ordinals")
    if not isinstance(raw_origins, set):
        raise TypeError("S3_COMPILER_ORIGIN_SET_INVALID")
    raw_origins.add(source_environment_ordinal)
    return node


def _add_edge(
    *,
    node: dict[str, Any],
    action: Mapping[str, Any],
    target_signature: str,
) -> None:
    action_signature = _action_signature(action)
    raw_edges = node.get("raw_edges")
    if not isinstance(raw_edges, dict):
        raise TypeError("S3_COMPILER_EDGE_INDEX_INVALID")
    edge = raw_edges.get(action_signature)
    if edge is None:
        edge = {
            "action_signature": action_signature,
            "action": dict(action),
            "targets": Counter(),
        }
        raw_edges[action_signature] = edge
    elif edge["action"] != dict(action):
        raise S3GraphCompilationError(
            "S3_ACTION_SIGNATURE_COLLISION:" + action_signature
        )
    targets = edge.get("targets")
    if not isinstance(targets, Counter):
        raise TypeError("S3_COMPILER_TARGET_COUNTER_INVALID")
    targets[target_signature] += 1


def _distance_to_goal(
    *,
    nodes: Mapping[str, Mapping[str, Any]],
    goal_signatures: Sequence[str],
) -> dict[str, int]:
    reverse: dict[str, set[str]] = defaultdict(set)
    for source_signature, node in nodes.items():
        raw_edges = _mapping(node.get("raw_edges"), "raw_edges")
        for raw_edge in raw_edges.values():
            edge = _mapping(raw_edge, "raw_edge")
            targets = edge.get("targets")
            if not isinstance(targets, Counter):
                raise TypeError("S3_COMPILER_TARGETS_INVALID")
            for target_signature in targets:
                reverse[str(target_signature)].add(source_signature)
    distance = {signature: 0 for signature in goal_signatures}
    pending: deque[str] = deque(sorted(goal_signatures))
    while pending:
        target = pending.popleft()
        next_distance = distance[target] + 1
        for source in sorted(reverse.get(target, ())):
            prior = distance.get(source)
            if prior is None or next_distance < prior:
                distance[source] = next_distance
                pending.append(source)
    return distance


def _finalize_global_graph(
    *,
    source_policy_digest: object,
    complete_inventory: bool,
    environment_count: int,
    level_count: int,
    initial_signatures: set[str],
    goal_signatures: set[str],
    nodes: dict[str, dict[str, Any]],
    transition_witness_count: int,
    role_selector_witness_count: int,
    boundary_selector_witness_count: int,
    relative_constraint_witness_count: int,
) -> dict[str, Any]:
    sorted_goals = sorted(goal_signatures)
    if not sorted_goals:
        raise S3GraphCompilationError("S3_GRAPH_GOAL_NODE_MISSING")
    distance = _distance_to_goal(
        nodes=nodes,
        goal_signatures=sorted_goals,
    )
    unreachable = sorted(set(nodes).difference(distance))
    if unreachable:
        raise S3GraphCompilationError(
            f"S3_GRAPH_UNREACHABLE_NODE:{len(unreachable)}"
        )

    goal_set = set(sorted_goals)
    finalized_nodes: list[dict[str, Any]] = []
    branch_node_count = 0
    merged_state_node_count = 0
    cross_environment_merged_state_node_count = 0
    nondeterministic_action_count = 0
    role_selector_edge_count = 0
    selected_policy_action_count = 0
    for state_signature in sorted(nodes):
        raw_node = nodes[state_signature]
        raw_edges = _mapping(raw_node.get("raw_edges"), "raw_edges")
        node_distance = distance[state_signature]
        outgoing: list[dict[str, Any]] = []
        selectable: list[tuple[int, int, str]] = []
        for action_signature in sorted(raw_edges):
            raw_edge = _mapping(
                raw_edges[action_signature],
                "raw_edge",
            )
            targets = raw_edge.get("targets")
            if not isinstance(targets, Counter):
                raise TypeError("S3_COMPILER_TARGETS_INVALID")
            target_signatures = sorted(str(item) for item in targets)
            target_distances = [distance[item] for item in target_signatures]
            strict_decrease = bool(target_distances) and all(
                item < node_distance for item in target_distances
            )
            if strict_decrease:
                selectable.append(
                    (
                        max(target_distances),
                        min(target_distances),
                        action_signature,
                    )
                )
            action = _mapping(raw_edge.get("action"), "action")
            role_selector_edge_count += int(
                action.get("target_selector") is not None
            )
            nondeterministic_action_count += int(
                len(target_signatures) > 1
            )
            outgoing.append(
                {
                    "action_signature": action_signature,
                    "action": dict(action),
                    "target_state_signatures": target_signatures,
                    "target_distance_to_goal": target_distances,
                    "strict_distance_decrease": strict_decrease,
                    "transition_witness_count": sum(
                        int(targets[item]) for item in targets
                    ),
                }
            )

        is_goal = state_signature in goal_set
        selected_action_signature: str | None = None
        if is_goal:
            if node_distance != 0:
                raise S3GraphCompilationError(
                    "S3_GRAPH_GOAL_DISTANCE_INVALID"
                )
        else:
            if not selectable:
                raise S3GraphCompilationError(
                    "S3_GRAPH_NO_STRICT_PROGRESS_ACTION:"
                    + state_signature
                )
            selected_action_signature = min(selectable)[2]
            selected_policy_action_count += 1
        branch_node_count += int(len(outgoing) > 1)
        merged_state_node_count += int(
            int(raw_node["observation_count"]) > 1
        )
        raw_origins = raw_node.get("source_environment_ordinals")
        if not isinstance(raw_origins, set):
            raise TypeError("S3_COMPILER_ORIGIN_SET_INVALID")
        cross_environment_merged_state_node_count += int(
            len(raw_origins) > 1
        )
        finalized_nodes.append(
            {
                "state_signature": state_signature,
                "condition": dict(raw_node["condition"]),
                "observation_count": int(raw_node["observation_count"]),
                "source_environment_count": len(raw_origins),
                "distance_to_goal": node_distance,
                "goal_node": is_goal,
                "outgoing_edges": outgoing,
                "selected_action_signature": selected_action_signature,
            }
        )

    sorted_initial = sorted(initial_signatures)
    if not sorted_initial:
        raise S3GraphCompilationError(
            "S3_GRAPH_INITIAL_STATE_MISSING"
        )
    if any(
        signature not in distance or distance[signature] < 1
        for signature in sorted_initial
    ):
        raise S3GraphCompilationError(
            "S3_GRAPH_INITIAL_DISTANCE_INVALID"
        )
    body: dict[str, Any] = {
        "schema_version": S3_POLICY_GRAPH_SCHEMA_VERSION,
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "phase": "P10-R5-IDENTITY-ROUTING-SUBTRACTION",
        "privilege_stage": "S3",
        "operation_mode": "offline",
        "complete_inventory": complete_inventory,
        "source_s2_policy_graph_digest": source_policy_digest,
        "environment_count": environment_count,
        "level_count": level_count,
        "policy_partition_count": 1,
        "identity_routing_key_count": 0,
        "explicit_identity_literal_count": 0,
        "initial_state_signatures": sorted_initial,
        "initial_state_signature_count": len(sorted_initial),
        "goal_state_signatures": sorted_goals,
        "goal_state_signature_count": len(sorted_goals),
        "source_transition_witness_count": transition_witness_count,
        "state_node_count": len(finalized_nodes),
        "selected_policy_action_count": selected_policy_action_count,
        "edge_count": sum(
            len(node["outgoing_edges"]) for node in finalized_nodes
        ),
        "branch_node_count": branch_node_count,
        "merged_state_node_count": merged_state_node_count,
        "cross_environment_merged_state_node_count": (
            cross_environment_merged_state_node_count
        ),
        "nondeterministic_action_count": nondeterministic_action_count,
        "strict_progress_policy": True,
        "role_selector_witness_count": role_selector_witness_count,
        "role_selector_edge_count": role_selector_edge_count,
        "boundary_selector_witness_count": (
            boundary_selector_witness_count
        ),
        "relative_constraint_witness_count": (
            relative_constraint_witness_count
        ),
        "absolute_pointer_payload_count": 0,
        "decision_basis": [
            "GLOBAL_STATE_SIGNATURE",
            "CURRENT_RENDERED_FINAL_FRAME_DIGEST",
            "CURRENT_AVAILABLE_ACTIONS",
            "CURRENT_TERMINAL_STATE",
            "CURRENT_PRIVILEGED_SOURCE_STATE_WITHOUT_IDENTITY",
            "CURRENT_PRIVILEGED_HIDDEN_STATE",
            "IDENTITY_FREE_BOUNDED_ACTION_EFFECT_HISTORY",
            "TARGET_CENTERED_RENDER_RELATIONS",
            "REVERSE_GRAPH_DISTANCE_TO_WIN",
        ],
        "forbidden_decision_basis": [
            "TASK_ID",
            "GAME_ID",
            "LEVEL_ID",
            "GAME_CLASS",
            "LEVEL_PROGRESS_COUNTER",
            "PER_GAME_GRAPH_PARTITION",
            "REPLAY_POSITION",
            "ACTION_ORDINAL",
            "FIXED_ACTION_LIST",
            "ABSOLUTE_POINTER_PAYLOAD",
            "LITERAL_TARGET_TABLE",
        ],
        "selection_rule": (
            "Match one identity-routing-free state in the global index, "
            "select an edge whose targets strictly reduce reverse-BFS "
            "distance to WIN, and resolve pointer payloads from current "
            "rendered role relations."
        ),
        "action_effect_history_limit": S3_ACTION_EFFECT_HISTORY_LIMIT,
        "remaining_privilege_dependencies": {
            "task_game_level_identity": False,
            "source_or_hidden_state": True,
            "answer_or_replay_graph": True,
            "literal_coordinate": False,
            "fixed_action_sequence": False,
            "rendered_only": False,
        },
        "nodes": finalized_nodes,
    }
    graph = {
        **body,
        "content_digest": (
            S3_POLICY_GRAPH_DIGEST_PREFIX + digest_object(body)
        ),
    }
    retained_identities = identity_literal_values(graph)
    if retained_identities:
        raise S3GraphCompilationError(
            "S3_GRAPH_IDENTITY_LITERAL_RETAINED:"
            + ",".join(sorted(retained_identities))
        )
    return graph


def compile_s3_policy_graph(
    *,
    environments_dir: Path,
    s2_policy_graph_path: Path,
    requested_games: Sequence[str] = (),
    recordings_dir: Path | None = None,
) -> dict[str, Any]:
    """Compile selected S2 successes into one global S3 graph."""

    if os.getenv("OPERATION_MODE", "").strip().casefold() == "competition":
        raise AuthorityViolation("COMPETITION_MODE_FORBIDDEN_DURING_S3")
    environments_dir = environments_dir.resolve()
    if not environments_dir.is_dir():
        raise FileNotFoundError(
            f"sample environment directory not found: {environments_dir}"
        )
    source = load_s2_policy_graph(
        s2_policy_graph_path,
        require_complete=not requested_games,
    )
    raw_sources = _sequence(source.get("games"), "games")
    requested = tuple(dict.fromkeys(str(item) for item in requested_games))
    known = {
        str(item.get("game_id"))
        for item in raw_sources
        if isinstance(item, Mapping)
    }
    unknown = sorted(set(requested).difference(known))
    if unknown:
        raise ValueError(
            "S3_COMPILER_REQUESTED_ENVIRONMENT_UNKNOWN:"
            + ",".join(unknown)
        )
    selected = [
        item
        for item in raw_sources
        if isinstance(item, Mapping)
        and (
            not requested
            or str(item.get("game_id")) in set(requested)
        )
    ]
    selected.sort(key=lambda item: str(item.get("game_id", "")))
    output_dir = (
        recordings_dir.resolve()
        if recordings_dir is not None
        else environments_dir.parent / "recordings"
    )
    arcade = Arcade(
        operation_mode=OperationMode.OFFLINE,
        environments_dir=str(environments_dir),
        recordings_dir=str(output_dir),
    )
    if arcade.operation_mode is not OperationMode.OFFLINE:
        raise AuthorityViolation("OFFLINE_SAMPLE_MODE_NOT_EFFECTIVE")

    nodes: dict[str, dict[str, Any]] = {}
    initial_signatures: set[str] = set()
    goal_signatures: set[str] = set()
    transition_witness_count = 0
    role_selector_witness_count = 0
    boundary_selector_witness_count = 0
    relative_constraint_witness_count = 0
    level_count = 0
    for source_environment_ordinal, source_graph in enumerate(selected):
        environment_identifier = str(source_graph.get("game_id", ""))
        target_level_count = _integer(
            source_graph.get("target_levels"),
            "target_levels",
        )
        level_count += target_level_count
        scorecard_id = arcade.open_scorecard(
            tags=["p10-r5", "s3-compiler", "development-only"]
        )
        try:
            environment = arcade.make(
                environment_identifier,
                scorecard_id=scorecard_id,
                save_recording=False,
                include_frame_data=True,
            )
            if not isinstance(environment, LocalEnvironmentWrapper):
                raise S3GraphCompilationError(
                    "S3_COMPILER_ENVIRONMENT_LOAD_FAILED"
                )
            source_nodes = _source_node_index(source_graph)
            frame = environment.observation_space
            if not isinstance(frame, FrameDataRaw):
                raise S3GraphCompilationError(
                    "S3_COMPILER_INITIAL_FRAME_MISSING"
                )
            s2_signature, _ = s2_state_condition_signature(
                environment=environment,
                frame=frame,
                action_effect_history=(),
            )
            if s2_signature != source_graph.get(
                "initial_state_signature"
            ):
                raise S3GraphCompilationError(
                    "S3_SOURCE_INITIAL_CONDITION_DIVERGED"
                )
            s3_signature, s3_condition = s3_state_condition_signature(
                environment=environment,
                frame=frame,
                action_effect_history=(),
            )
            initial_signatures.add(s3_signature)
            _register_node(
                nodes=nodes,
                state_signature=s3_signature,
                condition=s3_condition,
                source_environment_ordinal=source_environment_ordinal,
            )
            current_rendered_digest = rendered_frame_digest(frame)
            s2_history: list[dict[str, object]] = []
            s3_history: list[dict[str, object]] = []
            local_transition_count = 0
            initial_source_distance = _integer(
                _mapping(
                    source_nodes[s2_signature],
                    "initial_source_node",
                ).get("distance_to_goal"),
                "distance_to_goal",
            )
            while _frame_state(frame) != "WIN":
                if local_transition_count >= initial_source_distance:
                    raise S3GraphCompilationError(
                        "S3_SOURCE_PROGRESS_BUDGET_EXHAUSTED"
                    )
                source_node = source_nodes.get(s2_signature)
                if source_node is None:
                    raise S3GraphCompilationError(
                        "S3_SOURCE_NODE_MISSING"
                    )
                source_edge = _selected_source_edge(source_node)
                source_action = _mapping(
                    source_edge.get("action"),
                    "source_action",
                )
                action = _s3_action(
                    frame=frame,
                    source_action=source_action,
                )
                raw_selector = action.get("target_selector")
                if isinstance(raw_selector, Mapping):
                    role_selector_witness_count += 1
                    boundary_selector_witness_count += int(
                        _integer(
                            raw_selector.get(
                                "boundary_constraint_count"
                            ),
                            "boundary_constraint_count",
                        )
                        > 0
                    )
                    relative_constraint_witness_count += _integer(
                        raw_selector.get("relative_constraint_count"),
                        "relative_constraint_count",
                    )
                result = _execute_action(
                    environment=environment,
                    frame=frame,
                    state_signature=s3_signature,
                    action=action,
                )
                next_rendered_digest = rendered_frame_digest(result)
                selector_digest = (
                    str(raw_selector.get("content_digest", ""))
                    if isinstance(raw_selector, Mapping)
                    else None
                )

                s2_effect = s2_transition_effect_record(
                    before=frame,
                    action_id=_integer(
                        action.get("action_id"),
                        "action_id",
                    ),
                    reset_scope=str(action.get("reset_scope", "")),
                    target_selector_digest=selector_digest,
                    after=result,
                    before_rendered_frame_digest=(
                        current_rendered_digest
                    ),
                    after_rendered_frame_digest=next_rendered_digest,
                )
                next_s2_history = [*s2_history, s2_effect][
                    -S2_ACTION_EFFECT_HISTORY_LIMIT:
                ]
                next_s2_signature, _ = s2_state_condition_signature(
                    environment=environment,
                    frame=result,
                    action_effect_history=next_s2_history,
                    current_rendered_frame_digest=next_rendered_digest,
                )
                expected_source_targets = {
                    str(item)
                    for item in _sequence(
                        source_edge.get("target_state_signatures"),
                        "target_state_signatures",
                    )
                }
                if next_s2_signature not in expected_source_targets:
                    raise S3GraphCompilationError(
                        "S3_SOURCE_TRANSITION_DIVERGED"
                    )

                s3_effect = s3_transition_effect_record(
                    before=frame,
                    action_id=_integer(
                        action.get("action_id"),
                        "action_id",
                    ),
                    reset_scope=str(action.get("reset_scope", "")),
                    target_selector_digest=selector_digest,
                    after=result,
                    before_rendered_frame_digest=(
                        current_rendered_digest
                    ),
                    after_rendered_frame_digest=next_rendered_digest,
                )
                next_s3_history = [*s3_history, s3_effect][
                    -S3_ACTION_EFFECT_HISTORY_LIMIT:
                ]
                (
                    next_s3_signature,
                    next_s3_condition,
                ) = s3_state_condition_signature(
                    environment=environment,
                    frame=result,
                    action_effect_history=next_s3_history,
                    current_rendered_frame_digest=next_rendered_digest,
                )
                _register_node(
                    nodes=nodes,
                    state_signature=next_s3_signature,
                    condition=next_s3_condition,
                    source_environment_ordinal=(
                        source_environment_ordinal
                    ),
                )
                _add_edge(
                    node=nodes[s3_signature],
                    action=action,
                    target_signature=next_s3_signature,
                )
                frame = result
                current_rendered_digest = next_rendered_digest
                s2_signature = next_s2_signature
                s3_signature = next_s3_signature
                s2_history = next_s2_history
                s3_history = next_s3_history
                local_transition_count += 1
                transition_witness_count += 1

            if _frame_levels(frame) != target_level_count:
                raise S3GraphCompilationError(
                    "S3_COMPILER_SOURCE_CLOSURE_FAILED"
                )
            goal_signatures.add(s3_signature)
            print(
                json.dumps(
                    {
                        "event": "S3_SOURCE_ENVIRONMENT_COMPILED",
                        "source_environment_ordinal": (
                            source_environment_ordinal
                        ),
                        "completed_levels": target_level_count,
                        "transition_witness_count": (
                            local_transition_count
                        ),
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
        finally:
            arcade.close_scorecard(scorecard_id)
            gc.collect()

    return _finalize_global_graph(
        source_policy_digest=source.get("content_digest"),
        complete_inventory=(
            source.get("complete_inventory") is True and not requested
        ),
        environment_count=len(selected),
        level_count=level_count,
        initial_signatures=initial_signatures,
        goal_signatures=goal_signatures,
        nodes=nodes,
        transition_witness_count=transition_witness_count,
        role_selector_witness_count=role_selector_witness_count,
        boundary_selector_witness_count=(
            boundary_selector_witness_count
        ),
        relative_constraint_witness_count=(
            relative_constraint_witness_count
        ),
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compile S2 trajectories into one identity-free S3 graph."
        )
    )
    parser.add_argument("--environments-dir", type=Path, required=True)
    parser.add_argument("--s2-policy-graph", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--game", action="append", default=[])
    parser.add_argument("--recordings-dir", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    graph = compile_s3_policy_graph(
        environments_dir=args.environments_dir,
        s2_policy_graph_path=args.s2_policy_graph,
        requested_games=tuple(args.game),
        recordings_dir=args.recordings_dir,
    )
    _write_json(args.output, graph)
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "environment_count": graph["environment_count"],
                "level_count": graph["level_count"],
                "state_node_count": graph["state_node_count"],
                "edge_count": graph["edge_count"],
                "policy_partition_count": graph[
                    "policy_partition_count"
                ],
                "identity_routing_key_count": graph[
                    "identity_routing_key_count"
                ],
                "content_digest": graph["content_digest"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "S3GraphCompilationError",
    "compile_s3_policy_graph",
]
