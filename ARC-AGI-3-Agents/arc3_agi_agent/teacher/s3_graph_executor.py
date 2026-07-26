"""Execute one global S3 graph without environment-identity routing.

Environment identifiers are used only by the OFFLINE evaluation harness to
instantiate retained samples and attribute results.  The action-selection
function receives only the environment state and one global policy graph.
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
from .render_state import rendered_frame_digest
from .s2_role_selector import resolve_role_relative_selector
from .s3_graph_schema import load_s3_policy_graph
from .s3_state import (
    S3_ACTION_EFFECT_HISTORY_LIMIT,
    state_condition_signature,
    transition_effect_record,
)

S3_CLOSURE_REPORT_SCHEMA_VERSION = (
    "arc3-teacher-s3-global-identity-free-closure-report-v1"
)
S3_CLOSURE_REPORT_DIGEST_PREFIX = (
    "arc3_teacher_s3_global_identity_free_closure:"
)


class S3PolicyDivergence(RuntimeError):
    """Raised when current state cannot follow the global S3 policy."""


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
    graph: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    output: dict[str, Mapping[str, Any]] = {}
    for raw_node in _sequence(graph.get("nodes"), "nodes"):
        node = _mapping(raw_node, "node")
        signature = str(node.get("state_signature", ""))
        if not signature or signature in output:
            raise ValueError("S3_POLICY_NODE_ID_INVALID")
        output[signature] = node
    return output


def _selected_edge(
    node: Mapping[str, Any],
) -> Mapping[str, Any]:
    selected = node.get("selected_action_signature")
    if not isinstance(selected, str) or not selected:
        raise S3PolicyDivergence("S3_SELECTED_ACTION_MISSING")
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
        raise S3PolicyDivergence("S3_SELECTED_ACTION_NOT_UNIQUE")
    edge = matches[0]
    if edge.get("strict_distance_decrease") is not True:
        raise S3PolicyDivergence("S3_SELECTED_ACTION_NOT_PROGRESSIVE")
    return edge


def _emit_selected_action(
    *,
    environment: LocalEnvironmentWrapper,
    frame: FrameDataRaw,
    state_signature: str,
    policy_graph_digest: str,
    edge: Mapping[str, Any],
) -> tuple[FrameDataRaw, bool, str | None]:
    """Emit without receiving task/game/level identity."""

    action = _mapping(edge.get("action"), "action")
    action_id = _integer(action.get("action_id"), "action_id")
    if not 0 <= action_id <= 7:
        raise S3PolicyDivergence("S3_SELECTED_ACTION_ID_INVALID")
    available = _available_action_ids(frame)
    if action_id != 0 and action_id not in available:
        raise S3PolicyDivergence(
            f"S3_SELECTED_ACTION_UNAVAILABLE:{action_id}"
        )

    raw_selector = action.get("target_selector")
    transient_payload: dict[str, int] = {}
    selector_digest: str | None = None
    selector_resolved = False
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
        selector_resolved = True
    elif raw_selector is not None:
        raise S3PolicyDivergence(
            "S3_NON_POINTER_SELECTOR_PRESENT"
        )

    reset_scope = str(action.get("reset_scope", ""))
    if reset_scope not in {"RECORDED_ACTION", "LEVEL_COMPATIBILITY"}:
        raise S3PolicyDivergence("S3_RESET_SCOPE_INVALID")
    prior_reset_scope = os.environ.get("ONLY_RESET_LEVELS")
    if reset_scope == "LEVEL_COMPATIBILITY":
        os.environ["ONLY_RESET_LEVELS"] = "true"
    try:
        result = environment.step(
            GameAction.from_id(action_id),
            data=transient_payload,
            reasoning={
                "authority": "S3_GLOBAL_IDENTITY_FREE_TEACHER",
                "runtime_use": "FORBIDDEN",
                "condition_signature": state_signature,
                "policy_graph_digest": policy_graph_digest,
                "target_selector_digest": selector_digest,
                "identity_routing_used": False,
                "policy_partition": "GLOBAL",
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
        raise S3PolicyDivergence("S3_ENVIRONMENT_EMISSION_FAILED")
    return result, selector_resolved, selector_digest


def execute_s3_global_policy(
    *,
    environment: LocalEnvironmentWrapper,
    policy_graph: Mapping[str, Any],
) -> dict[str, Any]:
    """Execute the global graph with no environment identity input."""

    if not isinstance(environment, LocalEnvironmentWrapper):
        raise AuthorityViolation("S3_LOCAL_WRAPPER_REQUIRED")
    nodes = _node_index(policy_graph)
    initial = environment.observation_space
    if not isinstance(initial, FrameDataRaw):
        raise S3PolicyDivergence("S3_INITIAL_FRAME_MISSING")
    state_signature, _ = state_condition_signature(
        environment=environment,
        frame=initial,
        action_effect_history=(),
    )
    initial_signatures = {
        str(item)
        for item in _sequence(
            policy_graph.get("initial_state_signatures"),
            "initial_state_signatures",
        )
    }
    if state_signature not in initial_signatures:
        raise S3PolicyDivergence("S3_INITIAL_CONDITION_DIVERGED")
    initial_node = nodes.get(state_signature)
    if initial_node is None:
        raise S3PolicyDivergence("S3_INITIAL_NODE_MISSING")
    initial_distance = _integer(
        initial_node.get("distance_to_goal"),
        "distance_to_goal",
    )
    if initial_distance < 1:
        raise S3PolicyDivergence("S3_INITIAL_DISTANCE_INVALID")

    frame = initial
    current_rendered_digest = str(
        _mapping(
            initial_node.get("condition"),
            "condition",
        ).get("rendered_frame_digest", "")
    )
    emission_count = 0
    role_selector_resolution_count = 0
    actions_in_current_level = 0
    level_action_counts: list[int] = []
    prior_levels = _frame_levels(initial)
    trace: list[dict[str, object]] = []
    action_effect_history: list[dict[str, object]] = []
    policy_graph_digest = str(policy_graph.get("content_digest", ""))
    while _frame_state(frame) != "WIN":
        if emission_count >= initial_distance:
            raise S3PolicyDivergence(
                "S3_STRICT_PROGRESS_BUDGET_EXHAUSTED"
            )
        node = nodes.get(state_signature)
        if node is None:
            raise S3PolicyDivergence("S3_CURRENT_NODE_MISSING")
        before_distance = _integer(
            node.get("distance_to_goal"),
            "distance_to_goal",
        )
        edge = _selected_edge(node)
        action = _mapping(edge.get("action"), "action")
        (
            result,
            selector_resolved,
            selector_digest,
        ) = _emit_selected_action(
            environment=environment,
            frame=frame,
            state_signature=state_signature,
            policy_graph_digest=policy_graph_digest,
            edge=edge,
        )
        next_rendered_digest = rendered_frame_digest(result)
        action_id = _integer(action.get("action_id"), "action_id")
        effect = transition_effect_record(
            before=frame,
            action_id=action_id,
            reset_scope=str(action.get("reset_scope", "")),
            target_selector_digest=selector_digest,
            after=result,
            before_rendered_frame_digest=current_rendered_digest,
            after_rendered_frame_digest=next_rendered_digest,
        )
        next_history = [*action_effect_history, effect][
            -S3_ACTION_EFFECT_HISTORY_LIMIT:
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
            raise S3PolicyDivergence(
                "S3_TRANSITION_TARGET_DIVERGED"
            )
        next_node = nodes.get(next_signature)
        if next_node is None:
            raise S3PolicyDivergence("S3_TARGET_NODE_MISSING")
        after_distance = _integer(
            next_node.get("distance_to_goal"),
            "distance_to_goal",
        )
        if after_distance >= before_distance:
            raise S3PolicyDivergence(
                "S3_DISTANCE_DID_NOT_DECREASE:"
                f"{before_distance}:{after_distance}"
            )

        emission_count += 1
        role_selector_resolution_count += int(selector_resolved)
        actions_in_current_level += 1
        current_levels = _frame_levels(result)
        if current_levels < prior_levels or current_levels > prior_levels + 1:
            raise S3PolicyDivergence(
                "S3_EVALUATION_LEVEL_PROGRESS_INVALID:"
                f"{prior_levels}:{current_levels}"
            )
        if current_levels == prior_levels + 1:
            level_action_counts.append(actions_in_current_level)
            actions_in_current_level = 0
        trace.append(
            {
                "before_state_signature": state_signature,
                "before_distance_to_goal": before_distance,
                "action_id": action_id,
                "target_selector_digest": selector_digest,
                "after_state_signature": next_signature,
                "after_distance_to_goal": after_distance,
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
        final_levels <= 0
        or len(level_action_counts) != final_levels
        or actions_in_current_level != 0
    ):
        raise S3PolicyDivergence(
            "S3_FINAL_CLOSURE_INVALID:"
            f"{final_levels}:boundaries={len(level_action_counts)}"
        )
    return {
        "completed_levels": final_levels,
        "complete": True,
        "final_state": _frame_state(frame),
        "actions_executed": emission_count,
        "level_action_counts": level_action_counts,
        "initial_distance_to_goal": initial_distance,
        "strict_distance_decrease_count": emission_count,
        "role_selector_resolution_count": (
            role_selector_resolution_count
        ),
        "selector_resolution_failure_count": 0,
        "node_lookup_miss_count": 0,
        "unexpected_target_count": 0,
        "identity_routing_decision_count": 0,
        "policy_partition_count": 1,
        "actual_trace_digest": digest_object(trace),
    }


def _discover_environment_ids(environments_dir: Path) -> list[str]:
    """Discover retained samples for evaluation orchestration only."""

    identifiers: list[str] = []
    for metadata_path in sorted(
        environments_dir.glob("*/*/metadata.json")
    ):
        value = json.loads(metadata_path.read_text(encoding="utf-8"))
        if not isinstance(value, Mapping):
            raise TypeError("S3_ENVIRONMENT_METADATA_INVALID")
        identifier = value.get("game_id")
        if not isinstance(identifier, str) or not identifier:
            raise ValueError("S3_ENVIRONMENT_METADATA_ID_INVALID")
        expected = (
            metadata_path.parent.parent.name
            + "-"
            + metadata_path.parent.name
        )
        if identifier != expected:
            raise ValueError("S3_ENVIRONMENT_METADATA_PATH_DIVERGED")
        identifiers.append(identifier)
    if not identifiers or len(identifiers) != len(set(identifiers)):
        raise ValueError("S3_ENVIRONMENT_INVENTORY_INVALID")
    return identifiers


def run_s3_policy_graph(
    *,
    environments_dir: Path,
    policy_graph_path: Path,
    requested_games: Sequence[str] = (),
    recordings_dir: Path | None = None,
) -> dict[str, Any]:
    """Run a global S3 graph; IDs remain outside action selection."""

    if os.getenv("OPERATION_MODE", "").strip().casefold() == "competition":
        raise AuthorityViolation("COMPETITION_MODE_FORBIDDEN_DURING_S3")
    environments_dir = environments_dir.resolve()
    if not environments_dir.is_dir():
        raise FileNotFoundError(
            f"sample environment directory not found: {environments_dir}"
        )
    graph = load_s3_policy_graph(
        policy_graph_path,
        require_complete=not requested_games,
    )
    discovered = _discover_environment_ids(environments_dir)
    requested = tuple(dict.fromkeys(str(item) for item in requested_games))
    unknown = sorted(set(requested).difference(discovered))
    if unknown:
        raise ValueError(
            "S3_EXECUTOR_REQUESTED_ENVIRONMENT_UNKNOWN:"
            + ",".join(unknown)
        )
    selected = (
        sorted(requested) if requested else sorted(discovered)
    )
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
    for evaluation_identifier in selected:
        scorecard_id = arcade.open_scorecard(
            tags=["p10-r5", "s3-executor", "development-only"]
        )
        try:
            environment = arcade.make(
                evaluation_identifier,
                scorecard_id=scorecard_id,
                save_recording=False,
                include_frame_data=True,
            )
            if not isinstance(environment, LocalEnvironmentWrapper):
                raise S3PolicyDivergence(
                    "S3_ENVIRONMENT_LOAD_FAILED"
                )
            action_report = execute_s3_global_policy(
                environment=environment,
                policy_graph=graph,
            )
            report = {
                "game_id": evaluation_identifier,
                **action_report,
            }
            reports.append(report)
            print(
                json.dumps(
                    {
                        "event": "S3_GLOBAL_POLICY_EXECUTED",
                        "evaluation_environment": (
                            evaluation_identifier
                        ),
                        "completed_levels": report[
                            "completed_levels"
                        ],
                        "actions_executed": report[
                            "actions_executed"
                        ],
                        "identity_routing_decision_count": 0,
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
        except Exception as error:
            errors.append(
                {
                    "game_id": evaluation_identifier,
                    "error_type": type(error).__name__,
                    "message": str(error),
                }
            )
        finally:
            arcade.close_scorecard(scorecard_id)
            gc.collect()
    reports.sort(key=lambda item: str(item["game_id"]))
    errors.sort(key=lambda item: str(item["game_id"]))

    completed_levels = sum(
        int(report["completed_levels"]) for report in reports
    )
    actions_executed = sum(
        int(report["actions_executed"]) for report in reports
    )
    role_selector_resolution_count = sum(
        int(report["role_selector_resolution_count"])
        for report in reports
    )
    complete_inventory = (
        graph.get("complete_inventory") is True
        and not requested
        and len(selected) == graph.get("environment_count")
    )
    expected_levels = (
        _integer(graph.get("level_count"), "level_count")
        if complete_inventory
        else completed_levels
    )
    all_complete = (
        not errors
        and len(reports) == len(selected)
        and completed_levels == expected_levels
        and all(report.get("complete") is True for report in reports)
    )
    body: dict[str, Any] = {
        "schema_version": S3_CLOSURE_REPORT_SCHEMA_VERSION,
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "phase": "P10-R5-IDENTITY-ROUTING-SUBTRACTION",
        "privilege_stage": "S3",
        "operation_mode": "offline",
        "source_policy_graph_digest": graph.get("content_digest"),
        "complete_inventory": complete_inventory,
        "environment_count": len(selected),
        "completed_environment_count": len(reports),
        "level_count": expected_levels,
        "completed_levels": completed_levels,
        "actions_executed": actions_executed,
        "strict_distance_decrease_count": sum(
            int(report["strict_distance_decrease_count"])
            for report in reports
        ),
        "role_selector_resolution_count": (
            role_selector_resolution_count
        ),
        "environment_api_pointer_payload_generated_count": (
            role_selector_resolution_count
        ),
        "selector_resolution_failure_count": sum(
            int(report["selector_resolution_failure_count"])
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
        "identity_routing_decision_count": sum(
            int(report["identity_routing_decision_count"])
            for report in reports
        ),
        "policy_partition_count": 1,
        "error_count": len(errors),
        "all_complete": all_complete,
        "hds_stage_decision": "PASS" if all_complete else "HOLD",
        "next_stage_authorized": all_complete,
        "evaluation_identity_use": "ORCHESTRATION_AND_ATTRIBUTION_ONLY",
        "action_selection_receives_environment_identity": False,
        "decision_uses_task_game_level_identity": False,
        "decision_uses_level_progress_counter": False,
        "decision_uses_per_game_graph_partition": False,
        "fixed_action_sequence_used": False,
        "literal_coordinate_stored": False,
        "literal_coordinate_decision_used": False,
        "pointer_payload_generated_from_current_render": True,
        "decision_uses_replay_position": False,
        "decision_uses_action_ordinal": False,
        "decision_uses_current_state_condition": True,
        "action_effect_history_limit": S3_ACTION_EFFECT_HISTORY_LIMIT,
        "remaining_privilege_dependencies": {
            "task_game_level_identity": False,
            "source_or_hidden_state": True,
            "answer_or_replay_graph": True,
            "literal_coordinate": False,
            "rendered_only": False,
        },
        "reports": reports,
        "errors": errors,
    }
    return {
        **body,
        "content_digest": (
            S3_CLOSURE_REPORT_DIGEST_PREFIX + digest_object(body)
        ),
    }


def load_s3_closure_report(path: Path) -> dict[str, Any]:
    """Load the exact all-environment S3 closure gate."""

    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("S3_CLOSURE_REPORT_INVALID")
    body = dict(value)
    claimed = body.pop("content_digest", None)
    failures: list[str] = []
    if claimed != S3_CLOSURE_REPORT_DIGEST_PREFIX + digest_object(body):
        failures.append("S3_CLOSURE_REPORT_DIGEST_INVALID")
    if value.get("schema_version") != S3_CLOSURE_REPORT_SCHEMA_VERSION:
        failures.append("S3_CLOSURE_REPORT_SCHEMA_INVALID")
    if value.get("development_only") is not True:
        failures.append("S3_CLOSURE_REPORT_BOUNDARY_INVALID")
    if value.get("runtime_use") != "FORBIDDEN":
        failures.append("S3_CLOSURE_REPORT_RUNTIME_USE_INVALID")
    if str(value.get("operation_mode", "")).casefold() != "offline":
        failures.append("S3_CLOSURE_REPORT_NON_OFFLINE")
    if (
        value.get("complete_inventory") is not True
        or value.get("environment_count") != 25
        or value.get("completed_environment_count") != 25
        or value.get("level_count") != 183
        or value.get("completed_levels") != 183
        or value.get("actions_executed") != 10733
        or value.get("role_selector_resolution_count") != 3112
        or value.get("error_count") != 0
        or value.get("all_complete") is not True
        or value.get("hds_stage_decision") != "PASS"
        or value.get("next_stage_authorized") is not True
    ):
        failures.append("S3_CLOSURE_REPORT_NOT_183_COMPLETE")
    if (
        value.get("identity_routing_decision_count") != 0
        or value.get("policy_partition_count") != 1
        or value.get(
            "action_selection_receives_environment_identity"
        )
        is not False
        or value.get("decision_uses_task_game_level_identity")
        is not False
        or value.get("decision_uses_level_progress_counter") is not False
        or value.get("decision_uses_per_game_graph_partition") is not False
    ):
        failures.append("S3_CLOSURE_REPORT_IDENTITY_ROUTING_PRESENT")
    if (
        value.get("fixed_action_sequence_used") is not False
        or value.get("literal_coordinate_stored") is not False
        or value.get("literal_coordinate_decision_used") is not False
        or value.get(
            "pointer_payload_generated_from_current_render"
        )
        is not True
        or value.get("decision_uses_replay_position") is not False
        or value.get("decision_uses_action_ordinal") is not False
        or value.get("decision_uses_current_state_condition") is not True
    ):
        failures.append("S3_CLOSURE_REPORT_DECISION_BASIS_INVALID")
    if (
        value.get("selector_resolution_failure_count") != 0
        or value.get("node_lookup_miss_count") != 0
        or value.get("unexpected_target_count") != 0
        or value.get("strict_distance_decrease_count")
        != value.get("actions_executed")
        or value.get("role_selector_resolution_count")
        != value.get(
            "environment_api_pointer_payload_generated_count"
        )
    ):
        failures.append("S3_CLOSURE_REPORT_PROGRESS_AUDIT_INVALID")
    if failures:
        raise ValueError(";".join(sorted(set(failures))))
    return value


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Execute one global S3 graph without identity routing."
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
    report = run_s3_policy_graph(
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
                "environment_count": report["environment_count"],
                "completed_levels": report["completed_levels"],
                "level_count": report["level_count"],
                "actions_executed": report["actions_executed"],
                "identity_routing_decision_count": report[
                    "identity_routing_decision_count"
                ],
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
    "S3PolicyDivergence",
    "S3_CLOSURE_REPORT_DIGEST_PREFIX",
    "S3_CLOSURE_REPORT_SCHEMA_VERSION",
    "execute_s3_global_policy",
    "load_s3_closure_report",
    "run_s3_policy_graph",
]
