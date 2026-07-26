"""Compile S1 execution into a literal-coordinate-free S2 policy graph.

The development compiler may read the privileged S1 graph, including its
absolute pointer evidence.  It immediately converts each pointer target into
a target-centred rendered relation selector.  The emitted S2 graph contains no
absolute target payload, replay position, or fixed action sequence.
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
from .s1_graph_schema import load_s1_policy_graph
from .s1_state import (
    S1_ACTION_EFFECT_HISTORY_LIMIT,
)
from .s1_state import (
    state_condition_signature as s1_state_condition_signature,
)
from .s1_state import (
    transition_effect_record as s1_transition_effect_record,
)
from .s2_graph_schema import (
    S2_ACTION_SIGNATURE_PREFIX,
    S2_GAME_GRAPH_DIGEST_PREFIX,
    S2_POLICY_GRAPH_DIGEST_PREFIX,
    S2_POLICY_GRAPH_SCHEMA_VERSION,
)
from .s2_role_selector import (
    compile_role_relative_selector,
    resolve_role_relative_selector,
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


class S2GraphCompilationError(RuntimeError):
    """Raised when S1 evidence cannot form a valid S2 graph."""


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


def _node_index(
    game_graph: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    output: dict[str, Mapping[str, Any]] = {}
    for raw_node in _sequence(game_graph.get("nodes"), "nodes"):
        node = _mapping(raw_node, "node")
        signature = str(node.get("state_signature", ""))
        if not signature or signature in output:
            raise S2GraphCompilationError("S2_SOURCE_NODE_ID_INVALID")
        output[signature] = node
    return output


def _selected_source_edge(
    node: Mapping[str, Any],
) -> Mapping[str, Any]:
    selected = node.get("selected_action_signature")
    if not isinstance(selected, str) or not selected:
        raise S2GraphCompilationError(
            "S2_SOURCE_SELECTED_ACTION_MISSING"
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
        raise S2GraphCompilationError(
            "S2_SOURCE_SELECTED_ACTION_NOT_UNIQUE"
        )
    if matches[0].get("strict_distance_decrease") is not True:
        raise S2GraphCompilationError(
            "S2_SOURCE_SELECTED_ACTION_NOT_PROGRESSIVE"
        )
    return matches[0]


def _compile_s2_action(
    *,
    frame: FrameDataRaw,
    source_action: Mapping[str, Any],
) -> dict[str, Any]:
    action_id = _integer(source_action.get("action_id"), "action_id")
    if not 0 <= action_id <= 7:
        raise S2GraphCompilationError("S2_ACTION_ID_INVALID")
    reset_scope = str(source_action.get("reset_scope", ""))
    if reset_scope not in {"RECORDED_ACTION", "LEVEL_COMPATIBILITY"}:
        raise S2GraphCompilationError("S2_RESET_SCOPE_INVALID")
    raw_payload = _mapping(
        source_action.get("action_data"),
        "source_action.action_data",
    )
    target_selector: dict[str, Any] | None = None
    if action_id == 6:
        target_horizontal = _integer(
            raw_payload.get("x"),
            "source_pointer.x",
        )
        target_vertical = _integer(
            raw_payload.get("y"),
            "source_pointer.y",
        )
        target_selector = compile_role_relative_selector(
            frame=frame,
            target_horizontal_index=target_horizontal,
            target_vertical_index=target_vertical,
        )
        resolved = resolve_role_relative_selector(
            selector=target_selector,
            frame=frame,
        )
        if (
            resolved.horizontal_index != target_horizontal
            or resolved.vertical_index != target_vertical
        ):
            raise S2GraphCompilationError(
                "S2_COMPILED_SELECTOR_TARGET_DIVERGED"
            )
    elif raw_payload:
        raise S2GraphCompilationError(
            "S2_NON_POINTER_SOURCE_PAYLOAD_PRESENT"
        )
    return {
        "action_id": action_id,
        "reset_scope": reset_scope,
        "target_selector": target_selector,
    }


def _execute_s2_action(
    *,
    environment: LocalEnvironmentWrapper,
    frame: FrameDataRaw,
    state_signature: str,
    action: Mapping[str, Any],
) -> FrameDataRaw:
    action_id = _integer(action.get("action_id"), "action_id")
    available = _available_action_ids(frame)
    if action_id != 0 and action_id not in available:
        raise S2GraphCompilationError(
            f"S2_COMPILED_ACTION_UNAVAILABLE:{action_id}"
        )
    target_selector = action.get("target_selector")
    transient_payload: dict[str, int] = {}
    target_selector_digest: str | None = None
    if action_id == 6:
        selector = _mapping(target_selector, "target_selector")
        resolved = resolve_role_relative_selector(
            selector=selector,
            frame=frame,
        )
        transient_payload = {
            "x": resolved.horizontal_index,
            "y": resolved.vertical_index,
        }
        target_selector_digest = str(
            selector.get("content_digest", "")
        )
    elif target_selector is not None:
        raise S2GraphCompilationError(
            "S2_NON_POINTER_SELECTOR_PRESENT"
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
                "authority": "S2_ROLE_SELECTOR_COMPILER",
                "runtime_use": "FORBIDDEN",
                "condition_signature": state_signature,
                "target_selector_digest": target_selector_digest,
                "target_payload_origin": (
                    "CURRENT_RENDER_ROLE_RESOLUTION"
                    if action_id == 6
                    else "NO_POINTER_PAYLOAD"
                ),
            },
        )
    finally:
        if reset_scope == "LEVEL_COMPATIBILITY":
            _restore_environment_variable(
                "ONLY_RESET_LEVELS",
                prior_reset_scope,
            )
    if not isinstance(result, FrameDataRaw):
        raise S2GraphCompilationError("S2_COMPILER_STEP_FAILED")
    return result


def _action_signature(action: Mapping[str, Any]) -> str:
    return S2_ACTION_SIGNATURE_PREFIX + digest_object(dict(action))


def _register_node(
    *,
    nodes: dict[str, dict[str, Any]],
    state_signature: str,
    condition: Mapping[str, object],
) -> dict[str, Any]:
    node = nodes.get(state_signature)
    if node is None:
        node = {
            "state_signature": state_signature,
            "condition": dict(condition),
            "observation_count": 0,
            "raw_edges": {},
        }
        nodes[state_signature] = node
    elif node["condition"] != dict(condition):
        raise S2GraphCompilationError(
            "S2_STATE_SIGNATURE_COLLISION:" + state_signature
        )
    node["observation_count"] = int(node["observation_count"]) + 1
    return node


def _add_edge(
    *,
    node: dict[str, Any],
    action: Mapping[str, Any],
    target_signature: str,
) -> None:
    action_signature = _action_signature(action)
    raw_edges = node["raw_edges"]
    if not isinstance(raw_edges, dict):
        raise TypeError("S2_COMPILER_EDGE_INDEX_INVALID")
    edge = raw_edges.get(action_signature)
    if edge is None:
        edge = {
            "action_signature": action_signature,
            "action": dict(action),
            "targets": Counter(),
        }
        raw_edges[action_signature] = edge
    elif edge["action"] != dict(action):
        raise S2GraphCompilationError(
            "S2_ACTION_SIGNATURE_COLLISION:" + action_signature
        )
    targets = edge["targets"]
    if not isinstance(targets, Counter):
        raise TypeError("S2_COMPILER_TARGET_COUNTER_INVALID")
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
                raise TypeError("S2_COMPILER_TARGETS_INVALID")
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


def _finalize_game_graph(
    *,
    game_id: str,
    target_levels: int,
    source_s1_game_graph_digest: object,
    initial_state_signature: str,
    nodes: dict[str, dict[str, Any]],
    transition_witness_count: int,
    role_selector_witness_count: int,
    boundary_selector_witness_count: int,
    relative_constraint_witness_count: int,
) -> dict[str, Any]:
    goal_signatures = sorted(
        signature
        for signature, node in nodes.items()
        if isinstance(node.get("condition"), Mapping)
        and node["condition"].get("terminal_state") == "WIN"
        and node["condition"].get("levels_completed") == target_levels
    )
    if not goal_signatures:
        raise S2GraphCompilationError(
            f"S2_GRAPH_GOAL_NODE_MISSING:{game_id}"
        )
    distance = _distance_to_goal(
        nodes=nodes,
        goal_signatures=goal_signatures,
    )
    unreachable = sorted(set(nodes).difference(distance))
    if unreachable:
        raise S2GraphCompilationError(
            f"S2_GRAPH_UNREACHABLE_NODE:{game_id}:{len(unreachable)}"
        )

    goal_set = set(goal_signatures)
    finalized_nodes: list[dict[str, Any]] = []
    branch_node_count = 0
    merged_state_node_count = 0
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
                raise TypeError("S2_COMPILER_TARGETS_INVALID")
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
                raise S2GraphCompilationError(
                    f"S2_GRAPH_GOAL_DISTANCE_INVALID:{game_id}"
                )
        else:
            if not selectable:
                raise S2GraphCompilationError(
                    "S2_GRAPH_NO_STRICT_PROGRESS_ACTION:"
                    f"{game_id}:{state_signature}"
                )
            selected_action_signature = min(selectable)[2]
            selected_policy_action_count += 1
        branch_node_count += int(len(outgoing) > 1)
        merged_state_node_count += int(
            int(raw_node["observation_count"]) > 1
        )
        finalized_nodes.append(
            {
                "state_signature": state_signature,
                "condition": dict(raw_node["condition"]),
                "observation_count": int(
                    raw_node["observation_count"]
                ),
                "distance_to_goal": node_distance,
                "goal_node": is_goal,
                "outgoing_edges": outgoing,
                "selected_action_signature": (
                    selected_action_signature
                ),
            }
        )

    initial_distance = distance.get(initial_state_signature)
    if initial_distance is None or initial_distance < 1:
        raise S2GraphCompilationError(
            f"S2_GRAPH_INITIAL_DISTANCE_INVALID:{game_id}"
        )
    body: dict[str, Any] = {
        "game_id": game_id,
        "target_levels": target_levels,
        "source_s1_game_graph_digest": source_s1_game_graph_digest,
        "initial_state_signature": initial_state_signature,
        "initial_distance_to_goal": initial_distance,
        "goal_state_signatures": goal_signatures,
        "state_node_count": len(finalized_nodes),
        "selected_policy_action_count": selected_policy_action_count,
        "edge_count": sum(
            len(node["outgoing_edges"]) for node in finalized_nodes
        ),
        "source_transition_witness_count": transition_witness_count,
        "role_selector_witness_count": role_selector_witness_count,
        "role_selector_edge_count": role_selector_edge_count,
        "boundary_selector_witness_count": (
            boundary_selector_witness_count
        ),
        "relative_constraint_witness_count": (
            relative_constraint_witness_count
        ),
        "branch_node_count": branch_node_count,
        "merged_state_node_count": merged_state_node_count,
        "nondeterministic_action_count": nondeterministic_action_count,
        "strict_progress_policy": True,
        "selection_rule": (
            "Match the recomputed coordinate-free state, select an edge "
            "whose targets strictly reduce reverse-BFS distance to WIN, "
            "and resolve pointer payloads from target-centred rendered "
            "relations."
        ),
        "nodes": finalized_nodes,
    }
    return {
        **body,
        "content_digest": (
            S2_GAME_GRAPH_DIGEST_PREFIX + digest_object(body)
        ),
    }


def _compile_game_graph(
    *,
    environment: LocalEnvironmentWrapper,
    source_game_graph: Mapping[str, Any],
) -> dict[str, Any]:
    game_id = str(source_game_graph.get("game_id", ""))
    target_levels = _integer(
        source_game_graph.get("target_levels"),
        "target_levels",
    )
    source_nodes = _node_index(source_game_graph)
    initial = environment.observation_space
    if not isinstance(initial, FrameDataRaw):
        raise S2GraphCompilationError(
            f"S2_COMPILER_INITIAL_FRAME_MISSING:{game_id}"
        )
    s1_signature, _ = s1_state_condition_signature(
        environment=environment,
        frame=initial,
        action_effect_history=(),
    )
    if s1_signature != source_game_graph.get("initial_state_signature"):
        raise S2GraphCompilationError(
            f"S2_SOURCE_INITIAL_CONDITION_DIVERGED:{game_id}"
        )
    s2_signature, s2_condition = s2_state_condition_signature(
        environment=environment,
        frame=initial,
        action_effect_history=(),
    )
    initial_s2_signature = s2_signature
    nodes: dict[str, dict[str, Any]] = {}
    _register_node(
        nodes=nodes,
        state_signature=s2_signature,
        condition=s2_condition,
    )

    frame = initial
    current_rendered_digest = rendered_frame_digest(initial)
    s1_history: list[dict[str, object]] = []
    s2_history: list[dict[str, object]] = []
    transition_witness_count = 0
    role_selector_witness_count = 0
    boundary_selector_witness_count = 0
    relative_constraint_witness_count = 0
    initial_source_distance = _integer(
        _mapping(
            source_nodes[s1_signature],
            "initial_source_node",
        ).get("distance_to_goal"),
        "distance_to_goal",
    )
    while _frame_state(frame) != "WIN":
        if transition_witness_count >= initial_source_distance:
            raise S2GraphCompilationError(
                f"S2_SOURCE_PROGRESS_BUDGET_EXHAUSTED:{game_id}"
            )
        source_node = source_nodes.get(s1_signature)
        if source_node is None:
            raise S2GraphCompilationError(
                f"S2_SOURCE_NODE_MISSING:{game_id}"
            )
        source_edge = _selected_source_edge(source_node)
        source_action = _mapping(
            source_edge.get("action"),
            "source_action",
        )
        action = _compile_s2_action(
            frame=frame,
            source_action=source_action,
        )
        raw_selector = action.get("target_selector")
        if isinstance(raw_selector, Mapping):
            role_selector_witness_count += 1
            boundary_selector_witness_count += int(
                _integer(
                    raw_selector.get("boundary_constraint_count"),
                    "boundary_constraint_count",
                )
                > 0
            )
            relative_constraint_witness_count += _integer(
                raw_selector.get("relative_constraint_count"),
                "relative_constraint_count",
            )
        result = _execute_s2_action(
            environment=environment,
            frame=frame,
            state_signature=s2_signature,
            action=action,
        )
        next_rendered_digest = rendered_frame_digest(result)

        s1_effect = s1_transition_effect_record(
            before=frame,
            action=source_action,
            after=result,
            before_rendered_frame_digest=current_rendered_digest,
            after_rendered_frame_digest=next_rendered_digest,
        )
        next_s1_history = [*s1_history, s1_effect][
            -S1_ACTION_EFFECT_HISTORY_LIMIT:
        ]
        next_s1_signature, _ = s1_state_condition_signature(
            environment=environment,
            frame=result,
            action_effect_history=next_s1_history,
            current_rendered_frame_digest=next_rendered_digest,
        )
        expected_source_targets = {
            str(item)
            for item in _sequence(
                source_edge.get("target_state_signatures"),
                "target_state_signatures",
            )
        }
        if next_s1_signature not in expected_source_targets:
            raise S2GraphCompilationError(
                f"S2_SOURCE_TRANSITION_DIVERGED:{game_id}"
            )

        selector_digest = (
            str(raw_selector.get("content_digest", ""))
            if isinstance(raw_selector, Mapping)
            else None
        )
        s2_effect = s2_transition_effect_record(
            before=frame,
            action_id=_integer(action.get("action_id"), "action_id"),
            reset_scope=str(action.get("reset_scope", "")),
            target_selector_digest=selector_digest,
            after=result,
            before_rendered_frame_digest=current_rendered_digest,
            after_rendered_frame_digest=next_rendered_digest,
        )
        next_s2_history = [*s2_history, s2_effect][
            -S2_ACTION_EFFECT_HISTORY_LIMIT:
        ]
        next_s2_signature, next_s2_condition = (
            s2_state_condition_signature(
                environment=environment,
                frame=result,
                action_effect_history=next_s2_history,
                current_rendered_frame_digest=next_rendered_digest,
            )
        )
        _register_node(
            nodes=nodes,
            state_signature=next_s2_signature,
            condition=next_s2_condition,
        )
        _add_edge(
            node=nodes[s2_signature],
            action=action,
            target_signature=next_s2_signature,
        )
        frame = result
        current_rendered_digest = next_rendered_digest
        s1_signature = next_s1_signature
        s2_signature = next_s2_signature
        s1_history = next_s1_history
        s2_history = next_s2_history
        transition_witness_count += 1

    if (
        _frame_state(frame) != "WIN"
        or _frame_levels(frame) != target_levels
    ):
        raise S2GraphCompilationError(
            f"S2_COMPILER_SOURCE_CLOSURE_FAILED:{game_id}"
        )
    return _finalize_game_graph(
        game_id=game_id,
        target_levels=target_levels,
        source_s1_game_graph_digest=source_game_graph.get(
            "content_digest"
        ),
        initial_state_signature=initial_s2_signature,
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


def compile_s2_policy_graph(
    *,
    environments_dir: Path,
    s1_policy_graph_path: Path,
    requested_games: Sequence[str] = (),
    recordings_dir: Path | None = None,
) -> dict[str, Any]:
    """Compile selected S1 successes into coordinate-free S2 graphs."""

    if os.getenv("OPERATION_MODE", "").strip().casefold() == "competition":
        raise AuthorityViolation("COMPETITION_MODE_FORBIDDEN_DURING_S2")
    environments_dir = environments_dir.resolve()
    if not environments_dir.is_dir():
        raise FileNotFoundError(
            f"sample environment directory not found: {environments_dir}"
        )
    source = load_s1_policy_graph(
        s1_policy_graph_path,
        require_complete=not requested_games,
    )
    raw_games = _sequence(source.get("games"), "games")
    requested = tuple(dict.fromkeys(str(item) for item in requested_games))
    known = {
        str(game.get("game_id"))
        for game in raw_games
        if isinstance(game, Mapping)
    }
    unknown = sorted(set(requested).difference(known))
    if unknown:
        raise ValueError(
            "S2_COMPILER_REQUESTED_GAME_UNKNOWN:" + ",".join(unknown)
        )
    selected = [
        game
        for game in raw_games
        if isinstance(game, Mapping)
        and (
            not requested
            or str(game.get("game_id")) in set(requested)
        )
    ]
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

    game_graphs: list[dict[str, Any]] = []
    for source_game_graph in selected:
        game_id = str(source_game_graph.get("game_id", ""))
        scorecard_id = arcade.open_scorecard(
            tags=["p10-r5", "s2-compiler", "development-only"]
        )
        try:
            environment = arcade.make(
                game_id,
                scorecard_id=scorecard_id,
                save_recording=False,
                include_frame_data=True,
            )
            if not isinstance(environment, LocalEnvironmentWrapper):
                raise S2GraphCompilationError(
                    f"S2_COMPILER_ENVIRONMENT_LOAD_FAILED:{game_id}"
                )
            game_graph = _compile_game_graph(
                environment=environment,
                source_game_graph=source_game_graph,
            )
            game_graphs.append(game_graph)
            print(
                json.dumps(
                    {
                        "event": "S2_GAME_GRAPH_COMPILED",
                        "game_id": game_id,
                        "state_node_count": game_graph[
                            "state_node_count"
                        ],
                        "source_transition_witness_count": game_graph[
                            "source_transition_witness_count"
                        ],
                        "role_selector_witness_count": game_graph[
                            "role_selector_witness_count"
                        ],
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
        finally:
            arcade.close_scorecard(scorecard_id)
            gc.collect()
    game_graphs.sort(key=lambda item: str(item["game_id"]))
    level_count = sum(
        _integer(game.get("target_levels"), "target_levels")
        for game in selected
    )
    body: dict[str, Any] = {
        "schema_version": S2_POLICY_GRAPH_SCHEMA_VERSION,
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "phase": "P10-R5-LITERAL-COORDINATE-SUBTRACTION",
        "privilege_stage": "S2",
        "operation_mode": "offline",
        "complete_inventory": (
            source.get("complete_inventory") is True and not requested
        ),
        "source_s1_policy_graph_digest": source.get("content_digest"),
        "game_count": len(game_graphs),
        "level_count": level_count,
        "source_transition_witness_count": sum(
            int(game["source_transition_witness_count"])
            for game in game_graphs
        ),
        "state_node_count": sum(
            int(game["state_node_count"]) for game in game_graphs
        ),
        "edge_count": sum(
            int(game["edge_count"]) for game in game_graphs
        ),
        "branch_node_count": sum(
            int(game["branch_node_count"]) for game in game_graphs
        ),
        "merged_state_node_count": sum(
            int(game["merged_state_node_count"])
            for game in game_graphs
        ),
        "nondeterministic_action_count": sum(
            int(game["nondeterministic_action_count"])
            for game in game_graphs
        ),
        "strict_progress_game_count": sum(
            int(game["strict_progress_policy"] is True)
            for game in game_graphs
        ),
        "role_selector_witness_count": sum(
            int(game["role_selector_witness_count"])
            for game in game_graphs
        ),
        "role_selector_edge_count": sum(
            int(game["role_selector_edge_count"])
            for game in game_graphs
        ),
        "boundary_selector_witness_count": sum(
            int(game["boundary_selector_witness_count"])
            for game in game_graphs
        ),
        "relative_constraint_witness_count": sum(
            int(game["relative_constraint_witness_count"])
            for game in game_graphs
        ),
        "absolute_pointer_payload_count": 0,
        "decision_basis": [
            "CURRENT_RENDERED_FINAL_FRAME_DIGEST",
            "CURRENT_AVAILABLE_ACTIONS",
            "CURRENT_LEVEL_COMPLETION_STATE",
            "CURRENT_PRIVILEGED_SOURCE_STATE_DIGEST",
            "CURRENT_PRIVILEGED_HIDDEN_STATE_DIGEST",
            "COORDINATE_FREE_BOUNDED_ACTION_EFFECT_HISTORY",
            "TARGET_CENTERED_RENDER_RELATIONS",
            "REVERSE_GRAPH_DISTANCE_TO_WIN",
        ],
        "forbidden_decision_basis": [
            "REPLAY_POSITION",
            "ACTION_ORDINAL",
            "FIXED_ACTION_LIST",
            "ABSOLUTE_POINTER_PAYLOAD",
            "LITERAL_TARGET_TABLE",
        ],
        "action_effect_history_limit": S2_ACTION_EFFECT_HISTORY_LIMIT,
        "remaining_privilege_dependencies": {
            "task_game_identity": True,
            "source_or_hidden_state": True,
            "answer_or_replay_graph": True,
            "literal_coordinate": False,
            "fixed_action_sequence": False,
            "rendered_only": False,
        },
        "games": game_graphs,
    }
    return {
        **body,
        "content_digest": (
            S2_POLICY_GRAPH_DIGEST_PREFIX + digest_object(body)
        ),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compile S1 execution into a role-relative S2 policy graph."
        )
    )
    parser.add_argument("--environments-dir", type=Path, required=True)
    parser.add_argument("--s1-policy-graph", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--game", action="append", default=[])
    parser.add_argument("--recordings-dir", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    graph = compile_s2_policy_graph(
        environments_dir=args.environments_dir,
        s1_policy_graph_path=args.s1_policy_graph,
        requested_games=tuple(args.game),
        recordings_dir=args.recordings_dir,
    )
    _write_json(args.output, graph)
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "game_count": graph["game_count"],
                "level_count": graph["level_count"],
                "state_node_count": graph["state_node_count"],
                "edge_count": graph["edge_count"],
                "role_selector_witness_count": graph[
                    "role_selector_witness_count"
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
    "S2GraphCompilationError",
    "compile_s2_policy_graph",
]
