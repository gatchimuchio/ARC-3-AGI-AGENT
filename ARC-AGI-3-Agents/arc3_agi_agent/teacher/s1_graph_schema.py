"""Content-bound schema for the development-only S1 policy graph."""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..schema import digest_object

S1_POLICY_GRAPH_SCHEMA_VERSION = (
    "arc3-teacher-s1-state-conditioned-policy-graph-v2"
)
S1_POLICY_GRAPH_DIGEST_PREFIX = (
    "arc3_teacher_s1_state_conditioned_policy_graph:"
)
S1_GAME_GRAPH_DIGEST_PREFIX = "arc3_teacher_s1_game_policy_graph:"
S1_ACTION_SIGNATURE_PREFIX = "arc3_teacher_s1_action:"
_FORBIDDEN_POSITION_KEYS = frozenset(
    {
        "action_ordinal",
        "cursor",
        "replay_index",
        "source_order",
        "source_step",
        "step",
    }
)


def _all_keys(value: object) -> set[str]:
    if isinstance(value, Mapping):
        mapping_output = {str(key) for key in value}
        for item in value.values():
            mapping_output.update(_all_keys(item))
        return mapping_output
    if isinstance(value, list):
        list_output: set[str] = set()
        for item in value:
            list_output.update(_all_keys(item))
        return list_output
    return set()


def load_s1_policy_graph(
    path: Path,
    *,
    require_complete: bool = True,
) -> dict[str, Any]:
    """Load and fail closed on a malformed S1 policy graph."""

    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("S1_POLICY_GRAPH_INVALID")
    body = dict(value)
    claimed = body.pop("content_digest", None)
    failures: list[str] = []
    if (
        claimed
        != S1_POLICY_GRAPH_DIGEST_PREFIX + digest_object(body)
    ):
        failures.append("S1_POLICY_GRAPH_DIGEST_INVALID")
    if value.get("schema_version") != S1_POLICY_GRAPH_SCHEMA_VERSION:
        failures.append("S1_POLICY_GRAPH_SCHEMA_INVALID")
    if value.get("development_only") is not True:
        failures.append("S1_POLICY_GRAPH_BOUNDARY_INVALID")
    if value.get("runtime_use") != "FORBIDDEN":
        failures.append("S1_POLICY_GRAPH_RUNTIME_USE_INVALID")
    if value.get("privilege_stage") != "S1":
        failures.append("S1_POLICY_GRAPH_STAGE_INVALID")
    dependencies = value.get("remaining_privilege_dependencies")
    if not isinstance(dependencies, Mapping):
        failures.append("S1_POLICY_GRAPH_DEPENDENCIES_INVALID")
    elif dependencies.get("fixed_action_sequence") is not False:
        failures.append("S1_POLICY_GRAPH_FIXED_ACTION_DEPENDENCY")
    if require_complete and (
        value.get("complete_inventory") is not True
        or value.get("game_count") != 25
        or value.get("level_count") != 183
        or value.get("source_transition_witness_count") != 11574
        or value.get("strict_progress_game_count") != 25
    ):
        failures.append("S1_POLICY_GRAPH_NOT_COMPLETE")
    if _all_keys(value).intersection(_FORBIDDEN_POSITION_KEYS):
        failures.append("S1_POLICY_GRAPH_POSITION_KEY_PRESENT")
    raw_games = value.get("games")
    if not isinstance(raw_games, list) or not raw_games:
        failures.append("S1_POLICY_GRAPH_GAMES_INVALID")
        raw_games = []
    for raw_game in raw_games:
        if not isinstance(raw_game, Mapping):
            failures.append("S1_GAME_GRAPH_INVALID")
            continue
        game_body = dict(raw_game)
        game_claimed = game_body.pop("content_digest", None)
        if (
            game_claimed
            != S1_GAME_GRAPH_DIGEST_PREFIX + digest_object(game_body)
        ):
            failures.append("S1_GAME_GRAPH_DIGEST_INVALID")
        if raw_game.get("strict_progress_policy") is not True:
            failures.append("S1_GAME_GRAPH_PROGRESS_POLICY_INVALID")
    if failures:
        raise ValueError(";".join(sorted(set(failures))))
    return value


__all__ = [
    "S1_ACTION_SIGNATURE_PREFIX",
    "S1_GAME_GRAPH_DIGEST_PREFIX",
    "S1_POLICY_GRAPH_DIGEST_PREFIX",
    "S1_POLICY_GRAPH_SCHEMA_VERSION",
    "load_s1_policy_graph",
]
