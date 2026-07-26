"""Subtract source/hidden state from the global S3 policy graph."""

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
from .s2_role_selector import resolve_role_relative_selector
from .s3_graph_schema import load_s3_policy_graph
from .s3_state import (
    S3_ACTION_EFFECT_HISTORY_LIMIT,
)
from .s3_state import (
    state_condition_signature as s3_state_condition_signature,
)
from .s3_state import (
    transition_effect_record as s3_transition_effect_record,
)
from .s4_graph_schema import (
    S4_ACTION_SIGNATURE_PREFIX,
    S4_POLICY_GRAPH_DIGEST_PREFIX,
    S4_POLICY_GRAPH_SCHEMA_VERSION,
    identity_literal_values,
)
from .s4_state import (
    S4_ACTION_EFFECT_HISTORY_LIMIT,
    S4_STATE_SIGNATURE_PREFIX,
    descriptor_from_s3_condition,
    state_condition_signature,
    transition_effect_record,
)


class S4GraphCompilationError(RuntimeError):
    """Raised when S3 cannot be reduced to an S4 observation graph."""


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


def _action_signature(action: Mapping[str, Any]) -> str:
    return S4_ACTION_SIGNATURE_PREFIX + digest_object(dict(action))


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
    source: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    output: dict[str, Mapping[str, Any]] = {}
    for raw_node in _sequence(source.get("nodes"), "nodes"):
        node = _mapping(raw_node, "source_node")
        signature = str(node.get("state_signature", ""))
        if not signature or signature in output:
            raise S4GraphCompilationError(
                "S4_SOURCE_NODE_SIGNATURE_INVALID"
            )
        output[signature] = node
    return output


def _selected_source_edge(
    node: Mapping[str, Any],
) -> Mapping[str, Any]:
    selected = node.get("selected_action_signature")
    if not isinstance(selected, str) or not selected:
        raise S4GraphCompilationError(
            "S4_SOURCE_SELECTED_ACTION_MISSING"
        )
    matches = [
        edge
        for raw_edge in _sequence(
            node.get("outgoing_edges"),
            "outgoing_edges",
        )
        for edge in [_mapping(raw_edge, "source_edge")]
        if edge.get("action_signature") == selected
    ]
    if len(matches) != 1:
        raise S4GraphCompilationError(
            "S4_SOURCE_SELECTED_ACTION_NOT_UNIQUE"
        )
    if matches[0].get("strict_distance_decrease") is not True:
        raise S4GraphCompilationError(
            "S4_SOURCE_SELECTED_ACTION_NOT_PROGRESSIVE"
        )
    return matches[0]


def _execute_graph_action(
    *,
    environment: LocalEnvironmentWrapper,
    frame: FrameDataRaw,
    action: Mapping[str, Any],
    authority: str,
) -> tuple[FrameDataRaw, str | None]:
    action_id = _integer(action.get("action_id"), "action_id")
    if not 0 <= action_id <= 7:
        raise S4GraphCompilationError("S4_ACTION_ID_INVALID")
    available = _available_action_ids(frame)
    if action_id != 0 and action_id not in available:
        raise S4GraphCompilationError(
            f"S4_ACTION_UNAVAILABLE:{action_id}"
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
        raise S4GraphCompilationError(
            "S4_NON_POINTER_SELECTOR_PRESENT"
        )

    reset_scope = str(action.get("reset_scope", ""))
    if reset_scope not in {"RECORDED_ACTION", "LEVEL_COMPATIBILITY"}:
        raise S4GraphCompilationError("S4_RESET_SCOPE_INVALID")
    prior_reset_scope = os.environ.get("ONLY_RESET_LEVELS")
    if reset_scope == "LEVEL_COMPATIBILITY":
        os.environ["ONLY_RESET_LEVELS"] = "true"
    try:
        result = environment.step(
            GameAction.from_id(action_id),
            data=transient_payload,
            reasoning={
                "authority": authority,
                "runtime_use": "FORBIDDEN",
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
        raise S4GraphCompilationError("S4_COMPILER_STEP_FAILED")
    return result, selector_digest


def _collect_guidance_actions(
    *,
    environment: LocalEnvironmentWrapper,
    source_nodes: Mapping[str, Mapping[str, Any]],
) -> tuple[list[dict[str, Any]], int]:
    """Recover one answer trajectory on a disposable privileged mirror."""

    frame = environment.observation_space
    if not isinstance(frame, FrameDataRaw):
        raise S4GraphCompilationError(
            "S4_GUIDANCE_INITIAL_FRAME_MISSING"
        )
    state_signature, _ = s3_state_condition_signature(
        environment=environment,
        frame=frame,
        action_effect_history=(),
    )
    initial_node = source_nodes.get(state_signature)
    if initial_node is None:
        raise S4GraphCompilationError(
            "S4_GUIDANCE_INITIAL_STATE_DIVERGED"
        )
    budget = _integer(
        initial_node.get("distance_to_goal"),
        "distance_to_goal",
    )
    current_rendered_digest = rendered_frame_digest(frame)
    history: list[dict[str, object]] = []
    actions: list[dict[str, Any]] = []
    while _frame_state(frame) != "WIN":
        if len(actions) >= budget:
            raise S4GraphCompilationError(
                "S4_GUIDANCE_PROGRESS_BUDGET_EXHAUSTED"
            )
        node = source_nodes.get(state_signature)
        if node is None:
            raise S4GraphCompilationError(
                "S4_GUIDANCE_NODE_MISSING"
            )
        edge = _selected_source_edge(node)
        action = dict(_mapping(edge.get("action"), "action"))
        result, selector_digest = _execute_graph_action(
            environment=environment,
            frame=frame,
            action=action,
            authority="S4_DISPOSABLE_S3_GUIDANCE",
        )
        next_rendered_digest = rendered_frame_digest(result)
        effect = s3_transition_effect_record(
            before=frame,
            action_id=_integer(action.get("action_id"), "action_id"),
            reset_scope=str(action.get("reset_scope", "")),
            target_selector_digest=selector_digest,
            after=result,
            before_rendered_frame_digest=current_rendered_digest,
            after_rendered_frame_digest=next_rendered_digest,
        )
        next_history = [*history, effect][
            -S3_ACTION_EFFECT_HISTORY_LIMIT:
        ]
        next_signature, _ = s3_state_condition_signature(
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
            raise S4GraphCompilationError(
                "S4_GUIDANCE_TRANSITION_DIVERGED"
            )
        actions.append(action)
        frame = result
        current_rendered_digest = next_rendered_digest
        history = next_history
        state_signature = next_signature
    return actions, _frame_levels(frame)


def _discover_environment_ids(environments_dir: Path) -> list[str]:
    identifiers: list[str] = []
    for metadata_path in sorted(
        environments_dir.glob("*/*/metadata.json")
    ):
        value = json.loads(metadata_path.read_text(encoding="utf-8"))
        if not isinstance(value, Mapping):
            raise TypeError("S4_ENVIRONMENT_METADATA_INVALID")
        identifier = value.get("game_id")
        if not isinstance(identifier, str) or not identifier:
            raise ValueError("S4_ENVIRONMENT_METADATA_ID_INVALID")
        expected = (
            metadata_path.parent.parent.name
            + "-"
            + metadata_path.parent.name
        )
        if identifier != expected:
            raise ValueError("S4_ENVIRONMENT_METADATA_PATH_DIVERGED")
        identifiers.append(identifier)
    if not identifiers or len(identifiers) != len(set(identifiers)):
        raise ValueError("S4_ENVIRONMENT_INVENTORY_INVALID")
    return identifiers


def _register_node(
    *,
    nodes: dict[str, dict[str, Any]],
    state_signature: str,
    condition: Mapping[str, object],
    source_environment_ordinal: int,
) -> None:
    node = nodes.get(state_signature)
    if node is None:
        nodes[state_signature] = {
            "state_signature": state_signature,
            "condition": dict(condition),
            "observation_count": 1,
            "source_environment_ordinals": {
                source_environment_ordinal
            },
            "source_state_node_count": 1,
            "raw_edges": {},
        }
        return
    if node["condition"] != dict(condition):
        raise S4GraphCompilationError(
            "S4_STATE_SIGNATURE_COLLISION:" + state_signature
        )
    node["observation_count"] = int(node["observation_count"]) + 1
    raw_origins = node.get("source_environment_ordinals")
    if not isinstance(raw_origins, set):
        raise TypeError("S4_COMPILER_ORIGIN_SET_INVALID")
    raw_origins.add(source_environment_ordinal)
    node["source_state_node_count"] = (
        int(node["source_state_node_count"]) + 1
    )


def _add_edge(
    *,
    node: dict[str, Any],
    action: Mapping[str, Any],
    target_signature: str,
    transition_witness_count: int,
) -> None:
    action_signature = _action_signature(action)
    raw_edges = node.get("raw_edges")
    if not isinstance(raw_edges, dict):
        raise TypeError("S4_COMPILER_EDGE_INDEX_INVALID")
    edge = raw_edges.get(action_signature)
    if edge is None:
        edge = {
            "action_signature": action_signature,
            "action": dict(action),
            "targets": Counter(),
        }
        raw_edges[action_signature] = edge
    elif edge["action"] != dict(action):
        raise S4GraphCompilationError(
            "S4_ACTION_SIGNATURE_COLLISION:" + action_signature
        )
    targets = edge.get("targets")
    if not isinstance(targets, Counter):
        raise TypeError("S4_COMPILER_TARGET_COUNTER_INVALID")
    targets[target_signature] += transition_witness_count


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
                raise TypeError("S4_COMPILER_TARGETS_INVALID")
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


def _finalized_nodes(
    *,
    nodes: dict[str, dict[str, Any]],
    goal_signatures: set[str],
) -> tuple[list[dict[str, Any]], dict[str, int]]:
    distance = _distance_to_goal(
        nodes=nodes,
        goal_signatures=sorted(goal_signatures),
    )
    unreachable = sorted(set(nodes).difference(distance))
    if unreachable:
        raise S4GraphCompilationError(
            f"S4_GRAPH_UNREACHABLE_NODE:{len(unreachable)}"
        )
    output: list[dict[str, Any]] = []
    goal_set = set(goal_signatures)
    for state_signature in sorted(nodes):
        raw_node = nodes[state_signature]
        node_distance = distance[state_signature]
        raw_edges = _mapping(raw_node.get("raw_edges"), "raw_edges")
        outgoing: list[dict[str, Any]] = []
        selectable: list[tuple[int, int, str]] = []
        for action_signature in sorted(raw_edges):
            raw_edge = _mapping(
                raw_edges[action_signature],
                "raw_edge",
            )
            targets = raw_edge.get("targets")
            if not isinstance(targets, Counter):
                raise TypeError("S4_COMPILER_TARGETS_INVALID")
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
            outgoing.append(
                {
                    "action_signature": action_signature,
                    "action": dict(
                        _mapping(raw_edge.get("action"), "action")
                    ),
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
                raise S4GraphCompilationError(
                    "S4_GRAPH_GOAL_DISTANCE_INVALID"
                )
        else:
            if not selectable:
                raise S4GraphCompilationError(
                    "S4_GRAPH_NO_STRICT_PROGRESS_ACTION:"
                    + state_signature
                )
            selected_action_signature = min(selectable)[2]
        raw_origins = raw_node.get("source_environment_ordinals")
        if not isinstance(raw_origins, set):
            raise TypeError("S4_COMPILER_ORIGIN_SET_INVALID")
        output.append(
            {
                "state_signature": state_signature,
                "condition": dict(raw_node["condition"]),
                "observation_count": int(raw_node["observation_count"]),
                "source_environment_count": len(raw_origins),
                "source_state_node_count": int(
                    raw_node["source_state_node_count"]
                ),
                "distance_to_goal": node_distance,
                "goal_node": is_goal,
                "outgoing_edges": outgoing,
                "selected_action_signature": selected_action_signature,
            }
        )
    return output, distance


def compile_s4_policy_graph(
    *,
    environments_dir: Path,
    s3_policy_graph_path: Path,
    requested_games: Sequence[str] = (),
    recordings_dir: Path | None = None,
) -> dict[str, Any]:
    """Recollect S4 trajectories without inspecting target internals.

    A disposable S3 mirror recovers the already-proven answer trajectory.
    A fresh target environment then executes those actions without any source
    or hidden-state read.  Only target render/history conditions are compiled
    into the emitted graph.
    """

    if os.getenv("OPERATION_MODE", "").strip().casefold() == "competition":
        raise AuthorityViolation("COMPETITION_MODE_FORBIDDEN_DURING_S4")
    environments_dir = environments_dir.resolve()
    if not environments_dir.is_dir():
        raise FileNotFoundError(
            f"sample environment directory not found: {environments_dir}"
        )
    source = load_s3_policy_graph(
        s3_policy_graph_path,
        require_complete=not requested_games,
    )
    raw_nodes = _sequence(source.get("nodes"), "nodes")
    source_nodes = _source_node_index(source)

    # Prove that mechanically subtracting the source digest is collision-free,
    # but do not use these transformed conditions as runtime evidence.  Some
    # sample hidden-state getters have side effects, so S4 conditions must be
    # recollected on a fresh environment that never invokes them.
    transformed_signatures: set[str] = set()
    for raw_node in raw_nodes:
        source_node = _mapping(raw_node, "source_node")
        source_condition = _mapping(
            source_node.get("condition"),
            "source_condition",
        )
        transformed = descriptor_from_s3_condition(source_condition)
        transformed_signature = (
            S4_STATE_SIGNATURE_PREFIX + digest_object(transformed)
        )
        if transformed_signature in transformed_signatures:
            raise S4GraphCompilationError(
                "S4_PREFLIGHT_SOURCE_SUBTRACTION_MERGE"
            )
        transformed_signatures.add(transformed_signature)

    discovered = _discover_environment_ids(environments_dir)
    requested = tuple(dict.fromkeys(str(item) for item in requested_games))
    unknown = sorted(set(requested).difference(discovered))
    if unknown:
        raise ValueError(
            "S4_COMPILER_REQUESTED_ENVIRONMENT_UNKNOWN:"
            + ",".join(unknown)
        )
    selected = sorted(requested) if requested else sorted(discovered)
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
    for source_environment_ordinal, evaluation_identifier in enumerate(
        selected
    ):
        guidance_scorecard = arcade.open_scorecard(
            tags=["p10-r5", "s4-guidance", "development-only"]
        )
        try:
            guidance = arcade.make(
                evaluation_identifier,
                scorecard_id=guidance_scorecard,
                save_recording=False,
                include_frame_data=True,
            )
            if not isinstance(guidance, LocalEnvironmentWrapper):
                raise S4GraphCompilationError(
                    "S4_GUIDANCE_ENVIRONMENT_LOAD_FAILED"
                )
            actions, target_level_count = _collect_guidance_actions(
                environment=guidance,
                source_nodes=source_nodes,
            )
        finally:
            arcade.close_scorecard(guidance_scorecard)
            gc.collect()

        target_scorecard = arcade.open_scorecard(
            tags=["p10-r5", "s4-target", "development-only"]
        )
        try:
            target = arcade.make(
                evaluation_identifier,
                scorecard_id=target_scorecard,
                save_recording=False,
                include_frame_data=True,
            )
            if not isinstance(target, LocalEnvironmentWrapper):
                raise S4GraphCompilationError(
                    "S4_TARGET_ENVIRONMENT_LOAD_FAILED"
                )
            frame = target.observation_space
            if not isinstance(frame, FrameDataRaw):
                raise S4GraphCompilationError(
                    "S4_TARGET_INITIAL_FRAME_MISSING"
                )
            state_signature, condition = state_condition_signature(
                frame=frame,
                action_effect_history=(),
            )
            initial_signatures.add(state_signature)
            _register_node(
                nodes=nodes,
                state_signature=state_signature,
                condition=condition,
                source_environment_ordinal=(
                    source_environment_ordinal
                ),
            )
            current_rendered_digest = rendered_frame_digest(frame)
            history: list[dict[str, object]] = []
            local_transition_count = 0
            for action in actions:
                if _frame_state(frame) == "WIN":
                    raise S4GraphCompilationError(
                        "S4_TARGET_EARLY_WIN"
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
                result, selector_digest = _execute_graph_action(
                    environment=target,
                    frame=frame,
                    action=action,
                    authority="S4_SOURCE_HIDDEN_FREE_TARGET",
                )
                next_rendered_digest = rendered_frame_digest(result)
                effect = transition_effect_record(
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
                next_history = [*history, effect][
                    -S4_ACTION_EFFECT_HISTORY_LIMIT:
                ]
                (
                    next_signature,
                    next_condition,
                ) = state_condition_signature(
                    frame=result,
                    action_effect_history=next_history,
                    current_rendered_frame_digest=(
                        next_rendered_digest
                    ),
                )
                _register_node(
                    nodes=nodes,
                    state_signature=next_signature,
                    condition=next_condition,
                    source_environment_ordinal=(
                        source_environment_ordinal
                    ),
                )
                _add_edge(
                    node=nodes[state_signature],
                    action=action,
                    target_signature=next_signature,
                    transition_witness_count=1,
                )
                frame = result
                current_rendered_digest = next_rendered_digest
                history = next_history
                state_signature = next_signature
                local_transition_count += 1
                transition_witness_count += 1
            if (
                _frame_state(frame) != "WIN"
                or _frame_levels(frame) != target_level_count
            ):
                raise S4GraphCompilationError(
                    "S4_TARGET_ANSWER_TRAJECTORY_DIVERGED"
                )
            goal_signatures.add(state_signature)
            level_count += target_level_count
            print(
                json.dumps(
                    {
                        "event": "S4_SOURCE_HIDDEN_FREE_COMPILED",
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
            arcade.close_scorecard(target_scorecard)
            gc.collect()

    finalized_nodes, distance = _finalized_nodes(
        nodes=nodes,
        goal_signatures=goal_signatures,
    )
    if any(
        signature not in distance or distance[signature] < 1
        for signature in initial_signatures
    ):
        raise S4GraphCompilationError(
            "S4_GRAPH_INITIAL_DISTANCE_INVALID"
        )

    merged_state_node_count = sum(
        int(int(node["source_state_node_count"]) > 1)
        for node in finalized_nodes
    )
    branch_node_count = sum(
        int(len(node["outgoing_edges"]) > 1)
        for node in finalized_nodes
    )
    nondeterministic_action_count = sum(
        int(len(edge["target_state_signatures"]) > 1)
        for node in finalized_nodes
        for edge in node["outgoing_edges"]
    )
    role_selector_edge_count = sum(
        int(
            _mapping(edge.get("action"), "action").get(
                "target_selector"
            )
            is not None
        )
        for node in finalized_nodes
        for edge in node["outgoing_edges"]
    )
    body: dict[str, Any] = {
        "schema_version": S4_POLICY_GRAPH_SCHEMA_VERSION,
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "phase": "P10-R5-SOURCE-HIDDEN-STATE-SUBTRACTION",
        "privilege_stage": "S4",
        "operation_mode": "offline",
        "complete_inventory": (
            source.get("complete_inventory") is True
            and not requested
            and len(selected) == 25
        ),
        "source_s3_policy_graph_digest": source.get("content_digest"),
        "environment_count": len(selected),
        "level_count": level_count,
        "policy_partition_count": 1,
        "identity_routing_key_count": 0,
        "source_hidden_decision_key_count": 0,
        "source_state_digest_stored": False,
        "hidden_state_stored": False,
        "target_environment_source_or_hidden_read_count": 0,
        "compilation_guidance": (
            "DISPOSABLE_S3_ANSWER_TRAJECTORY_MIRROR"
        ),
        "compilation_guidance_uses_privileged_source": True,
        "initial_state_signatures": sorted(initial_signatures),
        "initial_state_signature_count": len(initial_signatures),
        "goal_state_signatures": sorted(goal_signatures),
        "goal_state_signature_count": len(goal_signatures),
        "source_transition_witness_count": transition_witness_count,
        "state_node_count": len(finalized_nodes),
        "selected_policy_action_count": sum(
            int(node["selected_action_signature"] is not None)
            for node in finalized_nodes
        ),
        "edge_count": sum(
            len(node["outgoing_edges"]) for node in finalized_nodes
        ),
        "branch_node_count": branch_node_count,
        "merged_state_node_count": merged_state_node_count,
        "source_state_nodes_merged_count": (
            len(raw_nodes) - len(finalized_nodes)
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
            "OBSERVATION_ONLY_BOUNDED_ACTION_EFFECT_HISTORY",
            "TARGET_CENTERED_RENDER_RELATIONS",
            "REVERSE_GRAPH_DISTANCE_TO_WIN",
        ],
        "forbidden_decision_basis": [
            "TASK_ID",
            "GAME_ID",
            "LEVEL_ID",
            "GAME_CLASS",
            "LEVEL_PROGRESS_COUNTER",
            "SOURCE_STATE",
            "HIDDEN_STATE",
            "PER_GAME_GRAPH_PARTITION",
            "REPLAY_POSITION",
            "ACTION_ORDINAL",
            "FIXED_ACTION_LIST",
            "ABSOLUTE_POINTER_PAYLOAD",
            "LITERAL_TARGET_TABLE",
        ],
        "selection_rule": (
            "Match one render/history state in the global index, select "
            "an edge whose targets strictly reduce reverse-BFS distance "
            "to WIN, and resolve pointer payloads from current render."
        ),
        "compilation_boundary": (
            "The disposable S3 mirror may inspect source/hidden state only "
            "to recover the retained answer trajectory. The separately "
            "instantiated S4 target is never inspected beyond FrameDataRaw, "
            "and no mirror condition is retained in this graph."
        ),
        "action_effect_history_limit": S4_ACTION_EFFECT_HISTORY_LIMIT,
        "remaining_privilege_dependencies": {
            "task_game_level_identity": False,
            "source_or_hidden_state": False,
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
            S4_POLICY_GRAPH_DIGEST_PREFIX + digest_object(body)
        ),
    }
    retained_identities = identity_literal_values(graph)
    if retained_identities:
        raise S4GraphCompilationError(
            "S4_GRAPH_IDENTITY_LITERAL_RETAINED:"
            + ",".join(sorted(retained_identities))
        )
    return graph


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Subtract source/hidden state from the S3 graph."
    )
    parser.add_argument("--environments-dir", type=Path, required=True)
    parser.add_argument("--s3-policy-graph", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--game", action="append", default=[])
    parser.add_argument("--recordings-dir", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    graph = compile_s4_policy_graph(
        environments_dir=args.environments_dir,
        s3_policy_graph_path=args.s3_policy_graph,
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
                "source_hidden_decision_key_count": graph[
                    "source_hidden_decision_key_count"
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
    "S4GraphCompilationError",
    "compile_s4_policy_graph",
]
