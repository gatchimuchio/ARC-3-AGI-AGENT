"""Execute a state-conditioned S1 graph without reading an action corpus.

Every decision is selected from the node matching the current recomputed
condition.  The executor has no replay position or action ordinal and rejects
any selected transition that does not strictly reduce graph distance to WIN.
This remains a privileged Teacher harness because the state condition still
contains identity and source/hidden-state digests.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
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
from .s1_graph_schema import (
    S1_GAME_GRAPH_DIGEST_PREFIX,
    load_s1_policy_graph,
)
from .s1_state import (
    S1_ACTION_EFFECT_HISTORY_LIMIT,
    rendered_frame_digest,
    state_condition_signature,
    transition_effect_record,
)

S1_CLOSURE_REPORT_SCHEMA_VERSION = (
    "arc3-teacher-s1-state-conditioned-closure-report-v2"
)
S1_CLOSURE_REPORT_DIGEST_PREFIX = (
    "arc3_teacher_s1_state_conditioned_closure:"
)


class S1PolicyDivergence(RuntimeError):
    """Raised when current state cannot follow the compiled S1 policy."""


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
    output: list[int] = []
    for raw in frame.available_actions:
        output.append(
            _integer(
                getattr(raw, "value", raw),
                "available_actions[]",
            )
        )
    return output


def _restore_environment_variable(name: str, prior: str | None) -> None:
    if prior is None:
        os.environ.pop(name, None)
    else:
        os.environ[name] = prior


def _validate_game_graph(game_graph: Mapping[str, Any]) -> None:
    body = dict(game_graph)
    claimed = body.pop("content_digest", None)
    failures: list[str] = []
    if (
        claimed
        != S1_GAME_GRAPH_DIGEST_PREFIX + digest_object(body)
    ):
        failures.append("S1_GAME_GRAPH_DIGEST_INVALID")
    if game_graph.get("strict_progress_policy") is not True:
        failures.append("S1_GAME_GRAPH_PROGRESS_POLICY_INVALID")
    raw_nodes = game_graph.get("nodes")
    if not isinstance(raw_nodes, list) or not raw_nodes:
        failures.append("S1_GAME_GRAPH_NODES_INVALID")
    if failures:
        raise ValueError(";".join(sorted(set(failures))))


def _node_index(
    game_graph: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    raw_nodes = _sequence(game_graph.get("nodes"), "nodes")
    output: dict[str, Mapping[str, Any]] = {}
    for raw_node in raw_nodes:
        node = _mapping(raw_node, "node")
        state_signature = str(node.get("state_signature", ""))
        if not state_signature or state_signature in output:
            raise ValueError("S1_GAME_GRAPH_NODE_ID_INVALID")
        output[state_signature] = node
    return output


def _selected_edge(
    node: Mapping[str, Any],
) -> Mapping[str, Any]:
    selected = node.get("selected_action_signature")
    if not isinstance(selected, str) or not selected:
        raise S1PolicyDivergence("S1_SELECTED_ACTION_MISSING")
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
        raise S1PolicyDivergence("S1_SELECTED_ACTION_NOT_UNIQUE")
    edge = matches[0]
    if edge.get("strict_distance_decrease") is not True:
        raise S1PolicyDivergence("S1_SELECTED_ACTION_NOT_PROGRESSIVE")
    return edge


def _emit_selected_action(
    *,
    environment: LocalEnvironmentWrapper,
    frame: FrameDataRaw,
    state_signature: str,
    policy_graph_digest: str,
    edge: Mapping[str, Any],
) -> FrameDataRaw:
    action = _mapping(edge.get("action"), "action")
    action_id = _integer(action.get("action_id"), "action_id")
    if not 0 <= action_id <= 7:
        raise S1PolicyDivergence("S1_SELECTED_ACTION_ID_INVALID")
    available = _available_action_ids(frame)
    if action_id != 0 and action_id not in available:
        raise S1PolicyDivergence(
            f"S1_SELECTED_ACTION_UNAVAILABLE:{action_id}"
        )
    raw_data = _mapping(action.get("action_data"), "action_data")
    action_data = {
        str(key): _integer(value, f"action_data.{key}")
        for key, value in raw_data.items()
    }
    reset_scope = str(action.get("reset_scope", ""))
    if reset_scope not in {"RECORDED_ACTION", "LEVEL_COMPATIBILITY"}:
        raise S1PolicyDivergence("S1_RESET_SCOPE_INVALID")
    prior_reset_scope = os.environ.get("ONLY_RESET_LEVELS")
    if reset_scope == "LEVEL_COMPATIBILITY":
        os.environ["ONLY_RESET_LEVELS"] = "true"
    try:
        result = environment.step(
            GameAction.from_id(action_id),
            data=action_data,
            reasoning={
                "authority": "S1_STATE_CONDITIONED_TEACHER",
                "runtime_use": "FORBIDDEN",
                "condition_signature": state_signature,
                "policy_graph_digest": policy_graph_digest,
                "selection_rule": "STRICT_DISTANCE_TO_WIN_DECREASE",
            },
        )
    finally:
        if reset_scope == "LEVEL_COMPATIBILITY":
            _restore_environment_variable(
                "ONLY_RESET_LEVELS",
                prior_reset_scope,
            )
    if not isinstance(result, FrameDataRaw):
        raise S1PolicyDivergence("S1_ENVIRONMENT_EMISSION_FAILED")
    return result


def execute_s1_game_graph(
    *,
    environment: LocalEnvironmentWrapper,
    game_graph: Mapping[str, Any],
    policy_graph_digest: str,
) -> dict[str, Any]:
    """Execute one graph solely by current-state lookup and strict progress."""

    if not isinstance(environment, LocalEnvironmentWrapper):
        raise AuthorityViolation("S1_LOCAL_WRAPPER_REQUIRED")
    _validate_game_graph(game_graph)
    game_id = str(game_graph.get("game_id", ""))
    target_levels = _integer(
        game_graph.get("target_levels"),
        "target_levels",
    )
    nodes = _node_index(game_graph)
    initial = environment.observation_space
    if not isinstance(initial, FrameDataRaw):
        raise S1PolicyDivergence(
            f"S1_INITIAL_FRAME_MISSING:{game_id}"
        )
    state_signature, _ = state_condition_signature(
        environment=environment,
        frame=initial,
        action_effect_history=(),
    )
    if state_signature != game_graph.get("initial_state_signature"):
        raise S1PolicyDivergence(
            f"S1_INITIAL_CONDITION_DIVERGED:{game_id}"
        )
    initial_node = nodes.get(state_signature)
    if initial_node is None:
        raise S1PolicyDivergence(
            f"S1_INITIAL_NODE_MISSING:{game_id}"
        )
    initial_distance = _integer(
        initial_node.get("distance_to_goal"),
        "distance_to_goal",
    )
    if initial_distance < 1:
        raise S1PolicyDivergence(
            f"S1_INITIAL_DISTANCE_INVALID:{game_id}"
        )

    frame = initial
    current_rendered_digest = str(
        _mapping(
            initial_node.get("condition"),
            "condition",
        ).get("rendered_frame_digest", "")
    )
    emission_count = 0
    actions_in_current_level = 0
    level_action_counts: list[int] = []
    prior_levels = _frame_levels(initial)
    trace: list[dict[str, object]] = []
    action_effect_history: list[dict[str, object]] = []
    while _frame_state(frame) != "WIN":
        if emission_count >= initial_distance:
            raise S1PolicyDivergence(
                f"S1_STRICT_PROGRESS_BUDGET_EXHAUSTED:{game_id}"
            )
        node = nodes.get(state_signature)
        if node is None:
            raise S1PolicyDivergence(
                f"S1_CURRENT_NODE_MISSING:{game_id}:{state_signature}"
            )
        before_distance = _integer(
            node.get("distance_to_goal"),
            "distance_to_goal",
        )
        edge = _selected_edge(node)
        action = _mapping(edge.get("action"), "action")
        result = _emit_selected_action(
            environment=environment,
            frame=frame,
            state_signature=state_signature,
            policy_graph_digest=policy_graph_digest,
            edge=edge,
        )
        next_rendered_digest = rendered_frame_digest(result)
        effect = transition_effect_record(
            before=frame,
            action=action,
            after=result,
            before_rendered_frame_digest=current_rendered_digest,
            after_rendered_frame_digest=next_rendered_digest,
        )
        next_history = [*action_effect_history, effect][
            -S1_ACTION_EFFECT_HISTORY_LIMIT:
        ]
        next_signature, _ = state_condition_signature(
            environment=environment,
            frame=result,
            action_effect_history=next_history,
            current_rendered_frame_digest=next_rendered_digest,
        )
        expected_targets = {
            str(item)
            for item in _sequence(
                edge.get("target_state_signatures"),
                "target_state_signatures",
            )
        }
        if next_signature not in expected_targets:
            raise S1PolicyDivergence(
                "S1_TRANSITION_TARGET_DIVERGED:"
                f"{game_id}:{state_signature}:{next_signature}"
            )
        next_node = nodes.get(next_signature)
        if next_node is None:
            raise S1PolicyDivergence(
                f"S1_TARGET_NODE_MISSING:{game_id}:{next_signature}"
            )
        after_distance = _integer(
            next_node.get("distance_to_goal"),
            "distance_to_goal",
        )
        if after_distance >= before_distance:
            raise S1PolicyDivergence(
                "S1_DISTANCE_DID_NOT_DECREASE:"
                f"{game_id}:{before_distance}:{after_distance}"
            )

        emission_count += 1
        actions_in_current_level += 1
        current_levels = _frame_levels(result)
        if current_levels < prior_levels or current_levels > prior_levels + 1:
            raise S1PolicyDivergence(
                "S1_LEVEL_PROGRESS_INVALID:"
                f"{game_id}:{prior_levels}:{current_levels}"
            )
        if current_levels == prior_levels + 1:
            level_action_counts.append(actions_in_current_level)
            actions_in_current_level = 0
        raw_action_data = _mapping(
            action.get("action_data"),
            "action_data",
        )
        trace.append(
            {
                "before_state_signature": state_signature,
                "before_distance_to_goal": before_distance,
                "action_id": _integer(
                    action.get("action_id"),
                    "action_id",
                ),
                "action_data": dict(raw_action_data),
                "after_state_signature": next_signature,
                "after_distance_to_goal": after_distance,
                "levels_completed": current_levels,
                "terminal_state": _frame_state(result),
            }
        )
        prior_levels = current_levels
        frame = result
        current_rendered_digest = next_rendered_digest
        state_signature = next_signature
        action_effect_history = next_history

    final_levels = _frame_levels(frame)
    if (
        final_levels != target_levels
        or len(level_action_counts) != target_levels
        or actions_in_current_level != 0
    ):
        raise S1PolicyDivergence(
            "S1_FINAL_CLOSURE_INVALID:"
            f"{game_id}:{final_levels}/{target_levels}:"
            f"boundaries={len(level_action_counts)}"
        )
    return {
        "game_id": game_id,
        "target_levels": target_levels,
        "completed_levels": final_levels,
        "complete": True,
        "final_state": _frame_state(frame),
        "actions_executed": emission_count,
        "level_action_counts": level_action_counts,
        "initial_distance_to_goal": initial_distance,
        "strict_distance_decrease_count": emission_count,
        "node_lookup_miss_count": 0,
        "unexpected_target_count": 0,
        "actual_trace_digest": digest_object(trace),
        "source_game_graph_digest": game_graph.get("content_digest"),
    }


def run_s1_policy_graph(
    *,
    environments_dir: Path,
    policy_graph_path: Path,
    requested_games: Sequence[str] = (),
    recordings_dir: Path | None = None,
) -> dict[str, Any]:
    """Run selected S1 state graphs without loading the S0 corpus."""

    if os.getenv("OPERATION_MODE", "").strip().casefold() == "competition":
        raise AuthorityViolation("COMPETITION_MODE_FORBIDDEN_DURING_S1")
    environments_dir = environments_dir.resolve()
    if not environments_dir.is_dir():
        raise FileNotFoundError(
            f"sample environment directory not found: {environments_dir}"
        )
    graph = load_s1_policy_graph(
        policy_graph_path,
        require_complete=not requested_games,
    )
    raw_games = _sequence(graph.get("games"), "games")
    requested = tuple(dict.fromkeys(str(item) for item in requested_games))
    known = {
        str(game.get("game_id"))
        for game in raw_games
        if isinstance(game, Mapping)
    }
    unknown = sorted(set(requested).difference(known))
    if unknown:
        raise ValueError(
            "S1_EXECUTOR_REQUESTED_GAME_UNKNOWN:" + ",".join(unknown)
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

    reports: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    policy_graph_digest = str(graph.get("content_digest", ""))
    for game_graph in selected:
        game_id = str(game_graph.get("game_id", ""))
        scorecard_id = arcade.open_scorecard(
            tags=["p10-r4", "s1-executor", "development-only"]
        )
        try:
            environment = arcade.make(
                game_id,
                scorecard_id=scorecard_id,
                save_recording=False,
                include_frame_data=True,
            )
            if not isinstance(environment, LocalEnvironmentWrapper):
                raise S1PolicyDivergence(
                    f"S1_ENVIRONMENT_LOAD_FAILED:{game_id}"
                )
            game_report = execute_s1_game_graph(
                environment=environment,
                game_graph=game_graph,
                policy_graph_digest=policy_graph_digest,
            )
            reports.append(game_report)
            print(
                json.dumps(
                    {
                        "event": "S1_GAME_GRAPH_EXECUTED",
                        "game_id": game_id,
                        "completed_levels": game_report[
                            "completed_levels"
                        ],
                        "actions_executed": game_report[
                            "actions_executed"
                        ],
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
        except Exception as error:
            errors.append(
                {
                    "game_id": game_id,
                    "error_type": type(error).__name__,
                    "message": str(error),
                }
            )
        finally:
            arcade.close_scorecard(scorecard_id)
            gc.collect()
    reports.sort(key=lambda item: str(item["game_id"]))
    errors.sort(key=lambda item: str(item["game_id"]))

    level_count = sum(
        _integer(game.get("target_levels"), "target_levels")
        for game in selected
    )
    completed_levels = sum(
        int(report["completed_levels"]) for report in reports
    )
    actions_executed = sum(
        int(report["actions_executed"]) for report in reports
    )
    all_complete = (
        not errors
        and len(reports) == len(selected)
        and completed_levels == level_count
    )
    body: dict[str, Any] = {
        "schema_version": S1_CLOSURE_REPORT_SCHEMA_VERSION,
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "phase": "P10-R4-STRUCTURAL-EXECUTOR",
        "privilege_stage": "S1",
        "operation_mode": "offline",
        "source_policy_graph_digest": graph.get("content_digest"),
        "complete_inventory": (
            graph.get("complete_inventory") is True and not requested
        ),
        "game_count": len(selected),
        "completed_game_count": len(reports),
        "level_count": level_count,
        "completed_levels": completed_levels,
        "actions_executed": actions_executed,
        "strict_distance_decrease_count": sum(
            int(report["strict_distance_decrease_count"])
            for report in reports
        ),
        "node_lookup_miss_count": sum(
            int(report["node_lookup_miss_count"])
            for report in reports
        ),
        "unexpected_target_count": sum(
            int(report["unexpected_target_count"])
            for report in reports
        ),
        "error_count": len(errors),
        "all_complete": all_complete,
        "hds_stage_decision": "PASS" if all_complete else "HOLD",
        "next_stage_authorized": all_complete,
        "fixed_action_sequence_used": False,
        "decision_uses_replay_position": False,
        "decision_uses_action_ordinal": False,
        "decision_uses_current_state_condition": True,
        "action_effect_history_limit": S1_ACTION_EFFECT_HISTORY_LIMIT,
        "remaining_privilege_dependencies": {
            "task_game_identity": True,
            "source_or_hidden_state": True,
            "answer_or_replay_graph": True,
            "literal_coordinate": True,
            "rendered_only": False,
        },
        "reports": reports,
        "errors": errors,
    }
    return {
        **body,
        "content_digest": (
            S1_CLOSURE_REPORT_DIGEST_PREFIX + digest_object(body)
        ),
    }


def load_s1_closure_report(path: Path) -> dict[str, Any]:
    """Load the exact all-game S1 closure gate."""

    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("S1_CLOSURE_REPORT_INVALID")
    body = dict(value)
    claimed = body.pop("content_digest", None)
    failures: list[str] = []
    if (
        claimed
        != S1_CLOSURE_REPORT_DIGEST_PREFIX + digest_object(body)
    ):
        failures.append("S1_CLOSURE_REPORT_DIGEST_INVALID")
    if value.get("schema_version") != S1_CLOSURE_REPORT_SCHEMA_VERSION:
        failures.append("S1_CLOSURE_REPORT_SCHEMA_INVALID")
    if value.get("development_only") is not True:
        failures.append("S1_CLOSURE_REPORT_BOUNDARY_INVALID")
    if value.get("runtime_use") != "FORBIDDEN":
        failures.append("S1_CLOSURE_REPORT_RUNTIME_USE_INVALID")
    if str(value.get("operation_mode", "")).casefold() != "offline":
        failures.append("S1_CLOSURE_REPORT_NON_OFFLINE")
    if (
        value.get("complete_inventory") is not True
        or value.get("game_count") != 25
        or value.get("completed_game_count") != 25
        or value.get("level_count") != 183
        or value.get("completed_levels") != 183
        or value.get("error_count") != 0
        or value.get("all_complete") is not True
        or value.get("hds_stage_decision") != "PASS"
        or value.get("next_stage_authorized") is not True
    ):
        failures.append("S1_CLOSURE_REPORT_NOT_183_COMPLETE")
    if (
        value.get("fixed_action_sequence_used") is not False
        or value.get("decision_uses_replay_position") is not False
        or value.get("decision_uses_action_ordinal") is not False
        or value.get("decision_uses_current_state_condition") is not True
    ):
        failures.append("S1_CLOSURE_REPORT_DECISION_BASIS_INVALID")
    if (
        value.get("node_lookup_miss_count") != 0
        or value.get("unexpected_target_count") != 0
        or value.get("strict_distance_decrease_count")
        != value.get("actions_executed")
    ):
        failures.append("S1_CLOSURE_REPORT_PROGRESS_AUDIT_INVALID")
    if failures:
        raise ValueError(";".join(sorted(set(failures))))
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Execute a state-conditioned S1 graph without an action corpus."
        )
    )
    parser.add_argument("--environments-dir", type=Path, required=True)
    parser.add_argument("--policy-graph", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--game", action="append", default=[])
    parser.add_argument("--recordings-dir", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    report = run_s1_policy_graph(
        environments_dir=args.environments_dir,
        policy_graph_path=args.policy_graph,
        requested_games=tuple(args.game),
        recordings_dir=args.recordings_dir,
    )
    _write_json(args.output, report)
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "game_count": report["game_count"],
                "completed_levels": report["completed_levels"],
                "level_count": report["level_count"],
                "actions_executed": report["actions_executed"],
                "error_count": report["error_count"],
                "all_complete": report["all_complete"],
                "content_digest": report["content_digest"],
            },
            sort_keys=True,
        )
    )
    return 0 if report["all_complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "S1PolicyDivergence",
    "S1_CLOSURE_REPORT_DIGEST_PREFIX",
    "S1_CLOSURE_REPORT_SCHEMA_VERSION",
    "execute_s1_game_graph",
    "load_s1_closure_report",
    "run_s1_policy_graph",
]
