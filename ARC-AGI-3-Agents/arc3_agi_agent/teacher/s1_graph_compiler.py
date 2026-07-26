"""Compile S0 success evidence into a fixed-action-free S1 state graph.

The compiler is development-only and may consume the privileged S0 corpus.
Its output is not an ordered action program: each node is keyed by a
recomputed current-state condition, each edge is an observed transition, and
the selected policy edge must strictly reduce graph distance to a WIN node.
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
from .human_replay_corpus import load_full_solution_corpus
from .s1_graph_schema import (
    S1_ACTION_SIGNATURE_PREFIX,
    S1_GAME_GRAPH_DIGEST_PREFIX,
    S1_POLICY_GRAPH_DIGEST_PREFIX,
    S1_POLICY_GRAPH_SCHEMA_VERSION,
)
from .s1_state import (
    S1_ACTION_EFFECT_HISTORY_LIMIT,
    rendered_frame_digest,
    state_condition_signature,
    transition_effect_record,
)


class S1GraphCompilationError(RuntimeError):
    """Raised when S0 evidence cannot form a strict-progress S1 graph."""


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


def _frame_state(frame: FrameDataRaw) -> str:
    raw = getattr(frame.state, "value", frame.state)
    return str(raw).upper()


def _frame_levels(frame: FrameDataRaw) -> int:
    return _integer(frame.levels_completed, "levels_completed")


def _available_action_ids(frame: FrameDataRaw) -> list[int]:
    output: list[int] = []
    for raw in frame.available_actions:
        output.append(
            _integer(
                getattr(raw, "value", raw),
                "available_actions[]",
            )
        )
    return output


def _action_payload(value: object) -> dict[str, int]:
    if not isinstance(value, Mapping):
        raise TypeError("S1_COMPILER_ACTION_DATA_INVALID")
    output: dict[str, int] = {}
    for key in ("x", "y"):
        raw = value.get(key)
        if raw is not None:
            output[key] = _integer(raw, f"action_data.{key}")
    return output


def _restore_environment_variable(name: str, prior: str | None) -> None:
    if prior is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = prior


def _action_descriptor(raw_action: Mapping[str, Any]) -> dict[str, object]:
    action_id = _integer(raw_action.get("action_id"), "action_id")
    if not 0 <= action_id <= 7:
        raise ValueError("S1_COMPILER_ACTION_ID_INVALID")
    action_data = _action_payload(raw_action.get("action_data"))
    reset_scope = (
        "LEVEL_COMPATIBILITY"
        if action_id == 0 and raw_action.get("full_reset") is not True
        else "RECORDED_ACTION"
    )
    return {
        "action_id": action_id,
        "action_data": action_data,
        "reset_scope": reset_scope,
    }


def _action_signature(action: Mapping[str, object]) -> str:
    return S1_ACTION_SIGNATURE_PREFIX + digest_object(dict(action))


def _execute_compiler_action(
    *,
    environment: LocalEnvironmentWrapper,
    action: Mapping[str, object],
    state_signature: str,
) -> FrameDataRaw:
    action_id = _integer(action.get("action_id"), "action_id")
    raw_data = action.get("action_data")
    if not isinstance(raw_data, Mapping):
        raise TypeError("S1_COMPILER_ACTION_DESCRIPTOR_INVALID")
    action_data = {
        str(key): _integer(value, f"action_data.{key}")
        for key, value in raw_data.items()
    }
    reset_scope = str(action.get("reset_scope", ""))
    prior_reset_scope = os.environ.get("ONLY_RESET_LEVELS")
    if reset_scope == "LEVEL_COMPATIBILITY":
        os.environ["ONLY_RESET_LEVELS"] = "true"
    try:
        frame = environment.step(
            GameAction.from_id(action_id),
            data=action_data,
            reasoning={
                "authority": "S1_GRAPH_COMPILER",
                "runtime_use": "FORBIDDEN",
                "condition_signature": state_signature,
            },
        )
    finally:
        if reset_scope == "LEVEL_COMPATIBILITY":
            _restore_environment_variable(
                "ONLY_RESET_LEVELS",
                prior_reset_scope,
            )
    if not isinstance(frame, FrameDataRaw):
        raise S1GraphCompilationError("S1_COMPILER_STEP_FAILED")
    return frame


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
        raise S1GraphCompilationError(
            "S1_STATE_SIGNATURE_COLLISION:" + state_signature
        )
    node["observation_count"] = int(node["observation_count"]) + 1
    return node


def _add_edge(
    *,
    node: dict[str, Any],
    action: Mapping[str, object],
    target_signature: str,
) -> None:
    action_signature = _action_signature(action)
    raw_edges = node["raw_edges"]
    if not isinstance(raw_edges, dict):
        raise TypeError("S1_COMPILER_EDGE_INDEX_INVALID")
    edge = raw_edges.get(action_signature)
    if edge is None:
        edge = {
            "action_signature": action_signature,
            "action": dict(action),
            "targets": Counter(),
        }
        raw_edges[action_signature] = edge
    elif edge["action"] != dict(action):
        raise S1GraphCompilationError(
            "S1_ACTION_SIGNATURE_COLLISION:" + action_signature
        )
    targets = edge["targets"]
    if not isinstance(targets, Counter):
        raise TypeError("S1_COMPILER_TARGET_COUNTER_INVALID")
    targets[target_signature] += 1


def _distance_to_goal(
    *,
    nodes: Mapping[str, Mapping[str, Any]],
    goal_signatures: Sequence[str],
) -> dict[str, int]:
    reverse: dict[str, set[str]] = defaultdict(set)
    for source_signature, node in nodes.items():
        raw_edges = node.get("raw_edges")
        if not isinstance(raw_edges, Mapping):
            raise TypeError("S1_COMPILER_RAW_EDGES_INVALID")
        for raw_edge in raw_edges.values():
            if not isinstance(raw_edge, Mapping):
                raise TypeError("S1_COMPILER_RAW_EDGE_INVALID")
            targets = raw_edge.get("targets")
            if not isinstance(targets, Counter):
                raise TypeError("S1_COMPILER_TARGETS_INVALID")
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
    source_solution_digest: object,
    initial_state_signature: str,
    nodes: dict[str, dict[str, Any]],
    transition_witness_count: int,
) -> dict[str, Any]:
    goal_signatures = sorted(
        signature
        for signature, node in nodes.items()
        if isinstance(node.get("condition"), Mapping)
        and node["condition"].get("terminal_state") == "WIN"
        and node["condition"].get("levels_completed") == target_levels
    )
    if not goal_signatures:
        raise S1GraphCompilationError(
            f"S1_GRAPH_GOAL_NODE_MISSING:{game_id}"
        )
    distance = _distance_to_goal(
        nodes=nodes,
        goal_signatures=goal_signatures,
    )
    unreachable = sorted(set(nodes).difference(distance))
    if unreachable:
        raise S1GraphCompilationError(
            f"S1_GRAPH_UNREACHABLE_NODE:{game_id}:{len(unreachable)}"
        )

    finalized_nodes: list[dict[str, Any]] = []
    branch_node_count = 0
    merged_state_node_count = 0
    nondeterministic_action_count = 0
    selected_policy_action_count = 0
    distinct_target_count = 0
    for state_signature in sorted(nodes):
        raw_node = nodes[state_signature]
        raw_edges = raw_node.get("raw_edges")
        if not isinstance(raw_edges, Mapping):
            raise TypeError("S1_COMPILER_RAW_NODE_EDGES_INVALID")
        node_distance = distance[state_signature]
        outgoing: list[dict[str, Any]] = []
        selectable: list[tuple[int, int, str]] = []
        for action_signature in sorted(raw_edges):
            raw_edge = raw_edges[action_signature]
            if not isinstance(raw_edge, Mapping):
                raise TypeError("S1_COMPILER_RAW_EDGE_INVALID")
            targets = raw_edge.get("targets")
            if not isinstance(targets, Counter):
                raise TypeError("S1_COMPILER_TARGETS_INVALID")
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
            nondeterministic_action_count += int(
                len(target_signatures) > 1
            )
            distinct_target_count += len(target_signatures)
            outgoing.append(
                {
                    "action_signature": action_signature,
                    "action": dict(raw_edge["action"]),
                    "target_state_signatures": target_signatures,
                    "target_distance_to_goal": target_distances,
                    "strict_distance_decrease": strict_decrease,
                    "transition_witness_count": sum(
                        int(targets[item]) for item in targets
                    ),
                }
            )

        is_goal = state_signature in set(goal_signatures)
        selected_action_signature: str | None = None
        if is_goal:
            if node_distance != 0:
                raise S1GraphCompilationError(
                    f"S1_GRAPH_GOAL_DISTANCE_INVALID:{game_id}"
                )
        else:
            if not outgoing:
                raise S1GraphCompilationError(
                    f"S1_GRAPH_DEAD_END:{game_id}:{state_signature}"
                )
            if not selectable:
                raise S1GraphCompilationError(
                    "S1_GRAPH_NO_STRICT_PROGRESS_ACTION:"
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
        raise S1GraphCompilationError(
            f"S1_GRAPH_INITIAL_DISTANCE_INVALID:{game_id}"
        )
    edge_count = sum(
        len(node["outgoing_edges"]) for node in finalized_nodes
    )
    body: dict[str, Any] = {
        "game_id": game_id,
        "target_levels": target_levels,
        "source_solution_digest": source_solution_digest,
        "initial_state_signature": initial_state_signature,
        "initial_distance_to_goal": initial_distance,
        "goal_state_signatures": goal_signatures,
        "state_node_count": len(finalized_nodes),
        "selected_policy_action_count": selected_policy_action_count,
        "edge_count": edge_count,
        "distinct_target_count": distinct_target_count,
        "source_transition_witness_count": transition_witness_count,
        "branch_node_count": branch_node_count,
        "merged_state_node_count": merged_state_node_count,
        "nondeterministic_action_count": nondeterministic_action_count,
        "strict_progress_policy": True,
        "selection_rule": (
            "For the recomputed current-state node, choose the "
            "lexicographically stable action whose every observed target "
            "strictly reduces reverse-BFS distance to a WIN node."
        ),
        "nodes": finalized_nodes,
    }
    return {
        **body,
        "content_digest": (
            S1_GAME_GRAPH_DIGEST_PREFIX + digest_object(body)
        ),
    }


def _compile_game_graph(
    *,
    environment: LocalEnvironmentWrapper,
    game_solution: Mapping[str, Any],
) -> dict[str, Any]:
    game_id = str(game_solution.get("game_id", ""))
    target_levels = _integer(
        game_solution.get("target_levels"),
        "target_levels",
    )
    raw_actions = _sequence(game_solution.get("actions"), "actions")
    initial = environment.observation_space
    if not isinstance(initial, FrameDataRaw):
        raise S1GraphCompilationError(
            f"S1_COMPILER_INITIAL_FRAME_MISSING:{game_id}"
        )
    initial_signature, initial_condition = state_condition_signature(
        environment=environment,
        frame=initial,
        action_effect_history=(),
    )
    nodes: dict[str, dict[str, Any]] = {}
    previous_signature = initial_signature
    previous = initial
    previous_rendered_digest = str(
        initial_condition["rendered_frame_digest"]
    )
    action_effect_history: list[dict[str, object]] = []
    _register_node(
        nodes=nodes,
        state_signature=initial_signature,
        condition=initial_condition,
    )
    transition_witness_count = 0
    for raw_action in raw_actions:
        if not isinstance(raw_action, Mapping):
            raise TypeError("S1_COMPILER_CORPUS_ACTION_INVALID")
        action = _action_descriptor(raw_action)
        action_id = _integer(action.get("action_id"), "action_id")
        available_before = _available_action_ids(previous)
        if action_id != 0 and action_id not in available_before:
            raise S1GraphCompilationError(
                f"S1_COMPILER_ACTION_UNAVAILABLE:{game_id}:{action_id}"
            )
        frame = _execute_compiler_action(
            environment=environment,
            action=action,
            state_signature=previous_signature,
        )
        expected_state = str(
            raw_action.get("expected_state", "")
        ).upper()
        expected_levels = _integer(
            raw_action.get("expected_levels_completed"),
            "expected_levels_completed",
        )
        if (
            _frame_state(frame) != expected_state
            or _frame_levels(frame) != expected_levels
        ):
            raise S1GraphCompilationError(
                "S1_COMPILER_SOURCE_OUTCOME_DIVERGED:"
                f"{game_id}:expected={expected_state}/{expected_levels}:"
                f"actual={_frame_state(frame)}/{_frame_levels(frame)}"
            )
        next_rendered_digest = rendered_frame_digest(frame)
        effect = transition_effect_record(
            before=previous,
            action=action,
            after=frame,
            before_rendered_frame_digest=previous_rendered_digest,
            after_rendered_frame_digest=next_rendered_digest,
        )
        next_history = [*action_effect_history, effect][
            -S1_ACTION_EFFECT_HISTORY_LIMIT:
        ]
        next_signature, next_condition = state_condition_signature(
            environment=environment,
            frame=frame,
            action_effect_history=next_history,
            current_rendered_frame_digest=next_rendered_digest,
        )
        action_effect_history = next_history
        _register_node(
            nodes=nodes,
            state_signature=next_signature,
            condition=next_condition,
        )
        source_node = nodes[previous_signature]
        _add_edge(
            node=source_node,
            action=action,
            target_signature=next_signature,
        )
        previous = frame
        previous_rendered_digest = next_rendered_digest
        previous_signature = next_signature
        transition_witness_count += 1

    if (
        _frame_state(previous) != "WIN"
        or _frame_levels(previous) != target_levels
    ):
        raise S1GraphCompilationError(
            "S1_COMPILER_SOURCE_CLOSURE_FAILED:"
            f"{game_id}:{_frame_state(previous)}/"
            f"{_frame_levels(previous)}/{target_levels}"
        )
    return _finalize_game_graph(
        game_id=game_id,
        target_levels=target_levels,
        source_solution_digest=game_solution.get("content_digest"),
        initial_state_signature=initial_signature,
        nodes=nodes,
        transition_witness_count=transition_witness_count,
    )


def compile_s1_policy_graph(
    *,
    environments_dir: Path,
    corpus_path: Path,
    requested_games: Sequence[str] = (),
    recordings_dir: Path | None = None,
) -> dict[str, Any]:
    """Compile selected OFFLINE successes into strict-progress state graphs."""

    if os.getenv("OPERATION_MODE", "").strip().casefold() == "competition":
        raise AuthorityViolation("COMPETITION_MODE_FORBIDDEN_DURING_S1")
    environments_dir = environments_dir.resolve()
    if not environments_dir.is_dir():
        raise FileNotFoundError(
            f"sample environment directory not found: {environments_dir}"
        )
    corpus = load_full_solution_corpus(corpus_path)
    raw_games = _sequence(corpus.get("games"), "games")
    requested = tuple(dict.fromkeys(str(item) for item in requested_games))
    known = {
        str(game.get("game_id"))
        for game in raw_games
        if isinstance(game, Mapping)
    }
    unknown = sorted(set(requested).difference(known))
    if unknown:
        raise ValueError(
            "S1_COMPILER_REQUESTED_GAME_UNKNOWN:" + ",".join(unknown)
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
    for game_solution in selected:
        game_id = str(game_solution.get("game_id", ""))
        scorecard_id = arcade.open_scorecard(
            tags=["p10-r4", "s1-compiler", "development-only"]
        )
        try:
            environment = arcade.make(
                game_id,
                scorecard_id=scorecard_id,
                save_recording=False,
                include_frame_data=True,
            )
            if not isinstance(environment, LocalEnvironmentWrapper):
                raise S1GraphCompilationError(
                    f"S1_COMPILER_ENVIRONMENT_LOAD_FAILED:{game_id}"
                )
            compiled_game = _compile_game_graph(
                environment=environment,
                game_solution=game_solution,
            )
            game_graphs.append(compiled_game)
            print(
                json.dumps(
                    {
                        "event": "S1_GAME_GRAPH_COMPILED",
                        "game_id": game_id,
                        "state_node_count": compiled_game[
                            "state_node_count"
                        ],
                        "source_transition_witness_count": compiled_game[
                            "source_transition_witness_count"
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
        "schema_version": S1_POLICY_GRAPH_SCHEMA_VERSION,
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "phase": "P10-R4-STRUCTURAL-EXECUTOR",
        "privilege_stage": "S1",
        "operation_mode": "offline",
        "complete_inventory": (
            corpus.get("complete_inventory") is True and not requested
        ),
        "source_corpus_digest": corpus.get("content_digest"),
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
        "decision_basis": [
            "CURRENT_RENDERED_FINAL_FRAME_DIGEST",
            "CURRENT_AVAILABLE_ACTIONS",
            "CURRENT_LEVEL_COMPLETION_STATE",
            "CURRENT_PRIVILEGED_SOURCE_STATE_DIGEST",
            "CURRENT_PRIVILEGED_HIDDEN_STATE_DIGEST",
            "BOUNDED_ACTION_EFFECT_HISTORY",
            "REVERSE_GRAPH_DISTANCE_TO_WIN",
        ],
        "action_effect_history_limit": S1_ACTION_EFFECT_HISTORY_LIMIT,
        "forbidden_decision_basis": [
            "REPLAY_POSITION",
            "ACTION_ORDINAL",
            "FIXED_ACTION_LIST",
            "SOURCE_REASONING_METADATA",
        ],
        "remaining_privilege_dependencies": {
            "task_game_identity": True,
            "source_or_hidden_state": True,
            "answer_or_replay_graph": True,
            "literal_coordinate": True,
            "fixed_action_sequence": False,
            "rendered_only": False,
        },
        "games": game_graphs,
    }
    return {
        **body,
        "content_digest": (
            S1_POLICY_GRAPH_DIGEST_PREFIX + digest_object(body)
        ),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Compile S0 successes into a state-conditioned S1 policy graph."
        )
    )
    parser.add_argument("--environments-dir", type=Path, required=True)
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--game", action="append", default=[])
    parser.add_argument("--recordings-dir", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    graph = compile_s1_policy_graph(
        environments_dir=args.environments_dir,
        corpus_path=args.corpus,
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
                "strict_progress_game_count": graph[
                    "strict_progress_game_count"
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
    "S1GraphCompilationError",
    "compile_s1_policy_graph",
]
