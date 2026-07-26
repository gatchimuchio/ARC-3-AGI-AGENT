"""Compile public winning human trajectories into the S0 Teacher corpus.

This module is intentionally development-only.  It retains game identity,
literal click coordinates, reset actions, and fixed replay order so that P10-R1
can establish a complete 183-level Teacher reference before privilege
subtraction begins.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterator, Mapping, Sequence
from pathlib import Path
from typing import Any

from ..schema import digest_object

SOURCE_MANIFEST_SCHEMA_VERSION = (
    "arc3-teacher-human-replay-source-manifest-v1"
)
FULL_SOLUTION_CORPUS_SCHEMA_VERSION = (
    "arc3-full-solution-corpus-v1"
)
SOURCE_MANIFEST_DIGEST_PREFIX = "arc3_teacher_replay_source_manifest:"
GAME_SOLUTION_DIGEST_PREFIX = "arc3_teacher_game_solution:"
FULL_SOLUTION_CORPUS_DIGEST_PREFIX = "arc3_full_solution_corpus:"
DATASET_ROWS_ENDPOINT = "https://datasets-server.huggingface.co/rows"
TEACHER_PRIVILEGES = (
    "TASK_GAME_LEVEL_ID",
    "FIXED_ACTION_SEQUENCE",
    "LITERAL_COORDINATE",
    "PUBLIC_WINNING_REPLAY",
)


def _json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


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


def _string(value: object, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise TypeError(f"{field_name} must be a non-empty string")
    return value


def _sequence(value: object, field_name: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(
        value,
        (str, bytes, bytearray),
    ):
        raise TypeError(f"{field_name} must be an array")
    return value


def _without_digest(
    value: Mapping[str, Any],
    field_name: str = "content_digest",
) -> dict[str, Any]:
    body = dict(value)
    body.pop(field_name, None)
    return body


def load_source_manifest(path: Path) -> dict[str, Any]:
    """Load and fully validate the pinned 25-game winning-row selection."""

    manifest = _json_object(path)
    failures: list[str] = []
    if manifest.get("schema_version") != SOURCE_MANIFEST_SCHEMA_VERSION:
        failures.append("TEACHER_SOURCE_MANIFEST_SCHEMA_INVALID")
    if manifest.get("development_only") is not True:
        failures.append("TEACHER_SOURCE_NOT_DEVELOPMENT_ONLY")
    if manifest.get("runtime_use") != "FORBIDDEN":
        failures.append("TEACHER_SOURCE_RUNTIME_BOUNDARY_INVALID")
    dataset_id = manifest.get("dataset_id")
    config = manifest.get("config")
    split = manifest.get("split")
    dataset_repo_sha = manifest.get("dataset_repo_sha")
    if not isinstance(dataset_id, str) or "/" not in dataset_id:
        failures.append("TEACHER_SOURCE_DATASET_ID_INVALID")
    if not isinstance(config, str) or not config:
        failures.append("TEACHER_SOURCE_CONFIG_INVALID")
    if not isinstance(split, str) or not split:
        failures.append("TEACHER_SOURCE_SPLIT_INVALID")
    if (
        not isinstance(dataset_repo_sha, str)
        or len(dataset_repo_sha) != 40
        or any(
            character not in "0123456789abcdef"
            for character in dataset_repo_sha
        )
    ):
        failures.append("TEACHER_SOURCE_REPO_SHA_INVALID")

    raw_rows = manifest.get("rows")
    if not isinstance(raw_rows, list):
        failures.append("TEACHER_SOURCE_ROWS_INVALID")
        raw_rows = []
    game_ids: list[str] = []
    row_indices: list[int] = []
    level_total = 0
    action_total = 0
    for index, raw_row in enumerate(raw_rows):
        if not isinstance(raw_row, dict):
            failures.append(f"TEACHER_SOURCE_ROW_INVALID:{index}")
            continue
        try:
            game_id = _string(
                raw_row.get("game_id"),
                f"rows[{index}].game_id",
            )
            row_index = _integer(
                raw_row.get("row_index"),
                f"rows[{index}].row_index",
            )
            target_levels = _integer(
                raw_row.get("target_levels"),
                f"rows[{index}].target_levels",
            )
            expected_actions = _integer(
                raw_row.get("expected_actions"),
                f"rows[{index}].expected_actions",
            )
            recording_file = _string(
                raw_row.get("recording_file"),
                f"rows[{index}].recording_file",
            )
        except (TypeError, ValueError) as error:
            failures.append(f"TEACHER_SOURCE_ROW_FIELD_INVALID:{index}:{error}")
            continue
        if (
            row_index < 0
            or target_levels < 1
            or expected_actions < 1
            or not recording_file.endswith(".recording")
        ):
            failures.append(f"TEACHER_SOURCE_ROW_RANGE_INVALID:{index}")
        game_ids.append(game_id)
        row_indices.append(row_index)
        level_total += target_levels
        action_total += expected_actions

    if len(raw_rows) != 25 or len(set(game_ids)) != 25:
        failures.append("TEACHER_SOURCE_GAME_COVERAGE_INVALID")
    if len(set(row_indices)) != len(row_indices):
        failures.append("TEACHER_SOURCE_ROW_INDEX_DUPLICATE")
    if level_total != 183:
        failures.append("TEACHER_SOURCE_LEVEL_TOTAL_INVALID")
    if action_total != 11648:
        failures.append("TEACHER_SOURCE_ACTION_TOTAL_INVALID")
    if manifest.get("selected_game_count") != len(raw_rows):
        failures.append("TEACHER_SOURCE_GAME_COUNT_MISMATCH")
    if manifest.get("selected_level_count") != level_total:
        failures.append("TEACHER_SOURCE_LEVEL_COUNT_MISMATCH")
    if manifest.get("selected_expected_actions") != action_total:
        failures.append("TEACHER_SOURCE_ACTION_COUNT_MISMATCH")
    raw_trajectory_digests = manifest.get(
        "pinned_trajectory_sha256_by_game"
    )
    if not isinstance(raw_trajectory_digests, dict):
        failures.append("TEACHER_SOURCE_TRAJECTORY_DIGESTS_INVALID")
        raw_trajectory_digests = {}
    if set(raw_trajectory_digests) != set(game_ids):
        failures.append("TEACHER_SOURCE_TRAJECTORY_DIGEST_COVERAGE_INVALID")
    for game_id, raw_digest in raw_trajectory_digests.items():
        if (
            not isinstance(game_id, str)
            or not isinstance(raw_digest, str)
            or len(raw_digest) != 64
            or any(
                character not in "0123456789abcdef"
                for character in raw_digest
            )
        ):
            failures.append(
                f"TEACHER_SOURCE_TRAJECTORY_DIGEST_INVALID:{game_id}"
            )
    if failures:
        raise ValueError(";".join(sorted(set(failures))))
    return manifest


def source_manifest_digest(manifest: Mapping[str, Any]) -> str:
    """Return a content digest for the validated source selection."""

    return SOURCE_MANIFEST_DIGEST_PREFIX + digest_object(dict(manifest))


def _fetch_dataset_row(
    *,
    dataset_id: str,
    config: str,
    split: str,
    row_index: int,
    timeout_seconds: float,
    retry_count: int,
) -> dict[str, Any]:
    query = urllib.parse.urlencode(
        {
            "dataset": dataset_id,
            "config": config,
            "split": split,
            "offset": row_index,
            "length": 1,
        }
    )
    request = urllib.request.Request(
        f"{DATASET_ROWS_ENDPOINT}?{query}",
        headers={"User-Agent": "ARC-3-AGI-AGENT-S0-Teacher/1"},
    )
    last_error: Exception | None = None
    for attempt in range(retry_count + 1):
        try:
            with urllib.request.urlopen(
                request,
                timeout=timeout_seconds,
            ) as response:
                payload = response.read()
            decoded = json.loads(payload)
            if not isinstance(decoded, dict):
                raise TypeError("dataset response must be an object")
            raw_rows = decoded.get("rows")
            if not isinstance(raw_rows, list) or len(raw_rows) != 1:
                raise ValueError("dataset response must contain exactly one row")
            wrapper = raw_rows[0]
            if not isinstance(wrapper, dict):
                raise TypeError("dataset row wrapper must be an object")
            if wrapper.get("row_idx") != row_index:
                raise ValueError("dataset row index mismatch")
            row = wrapper.get("row")
            if not isinstance(row, dict):
                raise TypeError("dataset row must be an object")
            return row
        except (
            OSError,
            TimeoutError,
            TypeError,
            ValueError,
            json.JSONDecodeError,
            urllib.error.URLError,
        ) as error:
            last_error = error
            if attempt >= retry_count:
                break
            time.sleep(min(2.0, 0.25 * (2**attempt)))
    raise RuntimeError(
        f"TEACHER_DATASET_ROW_FETCH_FAILED:{row_index}:{last_error}"
    ) from last_error


def _iter_json_array_items(value: str) -> Iterator[dict[str, Any]]:
    """Decode one large trajectory event at a time without materializing it."""

    decoder = json.JSONDecoder()
    index = 0
    length = len(value)
    while index < length and value[index].isspace():
        index += 1
    if index >= length or value[index] != "[":
        raise ValueError("trajectory must be a JSON array")
    index += 1
    while True:
        while index < length and value[index].isspace():
            index += 1
        if index < length and value[index] == "]":
            index += 1
            break
        item, index = decoder.raw_decode(value, index)
        if not isinstance(item, dict):
            raise TypeError("trajectory event must be an object")
        yield item
        while index < length and value[index].isspace():
            index += 1
        if index < length and value[index] == ",":
            index += 1
            continue
        if index < length and value[index] == "]":
            index += 1
            break
        raise ValueError("trajectory event separator invalid")
    if value[index:].strip():
        raise ValueError("trajectory contains trailing data")


def _normalized_action_data(value: object) -> dict[str, int]:
    if not isinstance(value, Mapping):
        return {}
    normalized: dict[str, int] = {}
    for key in ("x", "y"):
        raw = value.get(key)
        if raw is None:
            continue
        normalized[key] = _integer(raw, f"action_data.{key}")
    return normalized


def _normalized_available_actions(value: object) -> list[int]:
    actions = []
    for raw in _sequence(value, "available_actions"):
        action_id = _integer(raw, "available_actions[]")
        if not 0 <= action_id <= 7:
            raise ValueError("available action outside RESET-ACTION7")
        actions.append(action_id)
    return actions


def _normalized_action_id(value: object, field_name: str) -> int:
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be an action identifier")
    if isinstance(value, int):
        action_id = value
    elif isinstance(value, str):
        normalized = value.strip().upper()
        if normalized == "RESET":
            action_id = 0
        elif normalized.startswith("ACTION"):
            suffix = normalized.removeprefix("ACTION")
            if not suffix.isdecimal():
                raise ValueError(f"{field_name} has an invalid action name")
            action_id = int(suffix)
        elif normalized.isdecimal():
            action_id = int(normalized)
        else:
            raise ValueError(f"{field_name} has an invalid action identifier")
    else:
        raise TypeError(f"{field_name} must be an action identifier")
    if not 0 <= action_id <= 7:
        raise ValueError(f"{field_name} must be between RESET and ACTION7")
    return action_id


def _extract_game_solution(
    *,
    source_row: Mapping[str, Any],
    dataset_row: Mapping[str, Any],
    dataset_id: str,
    dataset_repo_sha: str,
    expected_trajectory_sha256: str,
) -> dict[str, Any]:
    game_id = _string(source_row.get("game_id"), "source_row.game_id")
    target_levels = _integer(
        source_row.get("target_levels"),
        "source_row.target_levels",
    )
    expected_actions = _integer(
        source_row.get("expected_actions"),
        "source_row.expected_actions",
    )
    row_index = _integer(
        source_row.get("row_index"),
        "source_row.row_index",
    )
    recording_file = _string(
        source_row.get("recording_file"),
        "source_row.recording_file",
    )
    if dataset_row.get("game_id") != game_id:
        raise ValueError(f"TEACHER_DATASET_GAME_MISMATCH:{game_id}")
    if dataset_row.get("guid") != recording_file:
        raise ValueError(f"TEACHER_DATASET_RECORDING_MISMATCH:{game_id}")
    if dataset_row.get("won") != 1:
        raise ValueError(f"TEACHER_DATASET_ROW_NOT_WIN:{game_id}")
    states = list(_sequence(dataset_row.get("states"), "states"))
    levels_completed = list(
        _sequence(dataset_row.get("levels_completed"), "levels_completed")
    )
    action_counts = list(
        _sequence(dataset_row.get("actions"), "actions")
    )
    if (
        states != ["WIN"]
        or levels_completed != [target_levels]
        or action_counts != [expected_actions]
    ):
        raise ValueError(f"TEACHER_DATASET_FULL_WIN_MISMATCH:{game_id}")
    trajectory = _string(
        dataset_row.get("trajectory"),
        "dataset_row.trajectory",
    )
    trajectory_sha256 = hashlib.sha256(
        trajectory.encode("utf-8")
    ).hexdigest()
    if trajectory_sha256 != expected_trajectory_sha256:
        raise ValueError(
            f"TEACHER_DATASET_TRAJECTORY_DIGEST_MISMATCH:{game_id}"
        )

    initial_observation: dict[str, Any] | None = None
    actions: list[dict[str, Any]] = []
    level_boundaries: list[dict[str, int]] = []
    prior_levels = 0
    recorded_action_count = 0
    solution_closed = False
    for event_index, event in enumerate(_iter_json_array_items(trajectory)):
        raw_data = event.get("data")
        if not isinstance(raw_data, Mapping):
            raise TypeError(f"trajectory data invalid: {game_id}:{event_index}")
        action_input = raw_data.get("action_input")
        if not isinstance(action_input, Mapping):
            raise TypeError(
                f"trajectory action input invalid: {game_id}:{event_index}"
            )
        action_id = _normalized_action_id(
            action_input.get("id"),
            f"action_id:{game_id}:{event_index}",
        )
        state = _string(
            raw_data.get("state"),
            f"state:{game_id}:{event_index}",
        ).upper()
        completed = _integer(
            raw_data.get("levels_completed"),
            f"levels_completed:{game_id}:{event_index}",
        )
        available_actions = _normalized_available_actions(
            raw_data.get("available_actions")
        )
        frame_digest = "sha256:" + digest_object(raw_data.get("frame"))
        if event_index == 0:
            if action_id == 0 and completed == 0:
                initial_observation = {
                    "source": "RECORDED_RESET_OBSERVATION",
                    "state": state,
                    "levels_completed": completed,
                    "available_actions": available_actions,
                    "frame_digest": frame_digest,
                }
                continue
            initial_observation = {
                "source": "INFERRED_PRE_ACTION",
                "state": "NOT_FINISHED",
                "levels_completed": 0,
                "available_actions": [],
                "frame_digest": None,
            }
        recorded_action_count += 1
        if solution_closed:
            continue
        step_index = len(actions) + 1
        action = {
            "step": step_index,
            "action_id": action_id,
            "action_data": _normalized_action_data(
                action_input.get("data")
            ),
            "expected_state": state,
            "expected_levels_completed": completed,
            "expected_available_actions": available_actions,
            "expected_frame_digest": frame_digest,
            "full_reset": bool(raw_data.get("full_reset", False)),
        }
        actions.append(action)
        if completed > prior_levels:
            for level in range(prior_levels + 1, completed + 1):
                level_boundaries.append(
                    {
                        "level": level,
                        "action_count": step_index,
                    }
                )
        prior_levels = completed
        solution_closed = (
            state == "WIN"
            and completed == target_levels
        )

    if initial_observation is None:
        raise ValueError(f"TEACHER_INITIAL_OBSERVATION_MISSING:{game_id}")
    if recorded_action_count != expected_actions:
        raise ValueError(
            "TEACHER_ACTION_COUNT_MISMATCH:"
            f"{game_id}:expected={expected_actions}:"
            f"actual={recorded_action_count}"
        )
    if prior_levels != target_levels:
        raise ValueError(
            "TEACHER_FINAL_LEVEL_MISMATCH:"
            f"{game_id}:expected={target_levels}:actual={prior_levels}"
        )
    if len(level_boundaries) != target_levels:
        raise ValueError(f"TEACHER_LEVEL_BOUNDARY_MISMATCH:{game_id}")
    if actions[-1]["expected_state"] != "WIN":
        raise ValueError(f"TEACHER_FINAL_STATE_NOT_WIN:{game_id}")

    body: dict[str, Any] = {
        "schema_version": "arc3-teacher-game-solution-v1",
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "privilege_stage": "S0",
        "privileges": list(TEACHER_PRIVILEGES),
        "game_id": game_id,
        "target_levels": target_levels,
        "source_recorded_action_count": recorded_action_count,
        "action_count": len(actions),
        "source": {
            "dataset_id": dataset_id,
            "dataset_repo_sha": dataset_repo_sha,
            "row_index": row_index,
            "recording_file": recording_file,
            "result_timestamp": dataset_row.get("result_timestamp"),
            "trajectory_sha256": trajectory_sha256,
        },
        "initial_observation": initial_observation,
        "level_boundaries": level_boundaries,
        "actions": actions,
        "final_state": "WIN",
    }
    return {
        **body,
        "content_digest": GAME_SOLUTION_DIGEST_PREFIX + digest_object(body),
    }


def build_full_solution_corpus(
    *,
    source_manifest_path: Path,
    requested_games: Sequence[str] = (),
    timeout_seconds: float = 120.0,
    retry_count: int = 2,
) -> dict[str, Any]:
    """Fetch and compile the selected winning rows into a replay corpus."""

    manifest = load_source_manifest(source_manifest_path)
    requested = tuple(dict.fromkeys(str(item) for item in requested_games))
    known = {
        str(row["game_id"])
        for row in manifest["rows"]
        if isinstance(row, dict)
    }
    unknown = sorted(set(requested).difference(known))
    if unknown:
        raise ValueError(
            "TEACHER_REQUESTED_GAME_UNKNOWN:" + ",".join(unknown)
        )
    selected_rows = [
        row
        for row in manifest["rows"]
        if isinstance(row, dict)
        and (
            not requested
            or str(row.get("game_id")) in set(requested)
        )
    ]
    games: list[dict[str, Any]] = []
    for source_row in selected_rows:
        dataset_row = _fetch_dataset_row(
            dataset_id=str(manifest["dataset_id"]),
            config=str(manifest["config"]),
            split=str(manifest["split"]),
            row_index=int(source_row["row_index"]),
            timeout_seconds=timeout_seconds,
            retry_count=retry_count,
        )
        games.append(
            _extract_game_solution(
                source_row=source_row,
                dataset_row=dataset_row,
                dataset_id=str(manifest["dataset_id"]),
                dataset_repo_sha=str(manifest["dataset_repo_sha"]),
                expected_trajectory_sha256=str(
                    manifest["pinned_trajectory_sha256_by_game"][
                        str(source_row["game_id"])
                    ]
                ),
            )
        )
    return _build_corpus_document(
        manifest=manifest,
        games=games,
        complete_inventory=not requested,
    )


def _build_corpus_document(
    *,
    manifest: Mapping[str, Any],
    games: Sequence[Mapping[str, Any]],
    complete_inventory: bool,
) -> dict[str, Any]:
    normalized_games = [dict(game) for game in games]
    normalized_games.sort(key=lambda item: str(item["game_id"]))
    body: dict[str, Any] = {
        "schema_version": FULL_SOLUTION_CORPUS_SCHEMA_VERSION,
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "privilege_stage": "S0",
        "privileges": list(TEACHER_PRIVILEGES),
        "source_manifest_digest": source_manifest_digest(manifest),
        "complete_inventory": complete_inventory,
        "game_count": len(normalized_games),
        "level_count": sum(
            int(item["target_levels"]) for item in normalized_games
        ),
        "source_recorded_action_count": sum(
            int(item["source_recorded_action_count"])
            for item in normalized_games
        ),
        "action_count": sum(
            int(item["action_count"]) for item in normalized_games
        ),
        "all_source_rows_are_full_game_wins": True,
        "games": normalized_games,
    }
    return {
        **body,
        "content_digest": (
            FULL_SOLUTION_CORPUS_DIGEST_PREFIX + digest_object(body)
        ),
    }


def merge_solution_corpora(
    *,
    source_manifest_path: Path,
    corpus_paths: Sequence[Path],
) -> dict[str, Any]:
    """Merge validated per-game checkpoints into one pinned corpus."""

    manifest = load_source_manifest(source_manifest_path)
    source_rows = {
        str(row["game_id"]): row
        for row in manifest["rows"]
        if isinstance(row, dict)
    }
    expected_game_ids = {
        str(row["game_id"])
        for row in manifest["rows"]
        if isinstance(row, dict)
    }
    by_game_id: dict[str, dict[str, Any]] = {}
    for path in corpus_paths:
        corpus = load_full_solution_corpus(path)
        raw_games = corpus.get("games")
        if not isinstance(raw_games, list):
            raise TypeError(f"TEACHER_CORPUS_GAMES_INVALID:{path}")
        for raw_game in raw_games:
            if not isinstance(raw_game, dict):
                raise TypeError(f"TEACHER_CORPUS_GAME_INVALID:{path}")
            game_id = _string(raw_game.get("game_id"), "game_id")
            source_row = source_rows.get(game_id)
            if source_row is None:
                raise ValueError(
                    f"TEACHER_CORPUS_GAME_UNKNOWN:{game_id}"
                )
            _validate_game_source_against_manifest(
                game=raw_game,
                source_row=source_row,
                manifest=manifest,
            )
            existing = by_game_id.get(game_id)
            if (
                existing is not None
                and existing.get("content_digest")
                != raw_game.get("content_digest")
            ):
                raise ValueError(
                    f"TEACHER_CORPUS_GAME_CONFLICT:{game_id}"
                )
            by_game_id[game_id] = raw_game
    unknown = sorted(set(by_game_id).difference(expected_game_ids))
    if unknown:
        raise ValueError(
            "TEACHER_CORPUS_GAME_UNKNOWN:" + ",".join(unknown)
        )
    complete_inventory = set(by_game_id) == expected_game_ids
    return _build_corpus_document(
        manifest=manifest,
        games=list(by_game_id.values()),
        complete_inventory=complete_inventory,
    )


def _validate_game_source_against_manifest(
    *,
    game: Mapping[str, Any],
    source_row: Mapping[str, Any],
    manifest: Mapping[str, Any],
) -> None:
    game_id = _string(game.get("game_id"), "game_id")
    raw_source = game.get("source")
    if not isinstance(raw_source, Mapping):
        raise TypeError(f"TEACHER_CORPUS_GAME_SOURCE_INVALID:{game_id}")
    nested_source = raw_source.get("public_human_trajectory")
    source = (
        nested_source
        if isinstance(nested_source, Mapping)
        else raw_source
    )
    trajectory_digests = manifest.get(
        "pinned_trajectory_sha256_by_game"
    )
    if not isinstance(trajectory_digests, Mapping):
        raise TypeError("TEACHER_SOURCE_TRAJECTORY_DIGESTS_INVALID")
    expected = {
        "dataset_id": manifest.get("dataset_id"),
        "dataset_repo_sha": manifest.get("dataset_repo_sha"),
        "row_index": source_row.get("row_index"),
        "recording_file": source_row.get("recording_file"),
        "trajectory_sha256": trajectory_digests.get(game_id),
    }
    mismatched = sorted(
        key for key, value in expected.items() if source.get(key) != value
    )
    if (
        mismatched
        or game.get("target_levels") != source_row.get("target_levels")
        or game.get("source_recorded_action_count")
        != source_row.get("expected_actions")
    ):
        raise ValueError(
            "TEACHER_CORPUS_SOURCE_ROW_MISMATCH:"
            f"{game_id}:{','.join(mismatched)}"
        )


def load_full_solution_corpus(path: Path) -> dict[str, Any]:
    """Load and validate a generated S0 corpus without network access."""

    corpus = _json_object(path)
    failures: list[str] = []
    if corpus.get("schema_version") != FULL_SOLUTION_CORPUS_SCHEMA_VERSION:
        failures.append("TEACHER_CORPUS_SCHEMA_INVALID")
    if corpus.get("development_only") is not True:
        failures.append("TEACHER_CORPUS_NOT_DEVELOPMENT_ONLY")
    if corpus.get("runtime_use") != "FORBIDDEN":
        failures.append("TEACHER_CORPUS_RUNTIME_BOUNDARY_INVALID")
    claimed = corpus.get("content_digest")
    actual = FULL_SOLUTION_CORPUS_DIGEST_PREFIX + digest_object(
        _without_digest(corpus)
    )
    if claimed != actual:
        failures.append("TEACHER_CORPUS_DIGEST_INVALID")
    raw_games = corpus.get("games")
    if not isinstance(raw_games, list):
        failures.append("TEACHER_CORPUS_GAMES_INVALID")
        raw_games = []
    game_ids: list[str] = []
    levels = 0
    actions = 0
    source_recorded_actions = 0
    for index, raw_game in enumerate(raw_games):
        if not isinstance(raw_game, dict):
            failures.append(f"TEACHER_CORPUS_GAME_INVALID:{index}")
            continue
        game_ids.append(str(raw_game.get("game_id", "")))
        levels += int(raw_game.get("target_levels", 0))
        actions += int(raw_game.get("action_count", 0))
        source_recorded_actions += int(
            raw_game.get("source_recorded_action_count", 0)
        )
        game_claimed = raw_game.get("content_digest")
        game_actual = GAME_SOLUTION_DIGEST_PREFIX + digest_object(
            _without_digest(raw_game)
        )
        if game_claimed != game_actual:
            failures.append(f"TEACHER_CORPUS_GAME_DIGEST_INVALID:{index}")
        raw_actions = raw_game.get("actions")
        if (
            not isinstance(raw_actions, list)
            or len(raw_actions) != raw_game.get("action_count")
        ):
            failures.append(f"TEACHER_CORPUS_ACTIONS_INVALID:{index}")
    if len(set(game_ids)) != len(game_ids):
        failures.append("TEACHER_CORPUS_GAME_DUPLICATE")
    if corpus.get("game_count") != len(raw_games):
        failures.append("TEACHER_CORPUS_GAME_COUNT_INVALID")
    if corpus.get("level_count") != levels:
        failures.append("TEACHER_CORPUS_LEVEL_COUNT_INVALID")
    if corpus.get("action_count") != actions:
        failures.append("TEACHER_CORPUS_ACTION_COUNT_INVALID")
    if (
        corpus.get("source_recorded_action_count")
        != source_recorded_actions
    ):
        failures.append(
            "TEACHER_CORPUS_SOURCE_RECORDED_ACTION_COUNT_INVALID"
        )
    if corpus.get("complete_inventory") is True:
        if (
            len(raw_games) != 25
            or levels != 183
            or source_recorded_actions != 11648
        ):
            failures.append("TEACHER_CORPUS_COMPLETE_INVENTORY_INVALID")
    if failures:
        raise ValueError(";".join(sorted(set(failures))))
    return corpus


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build or validate the development-only S0 Teacher corpus."
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    fetch = subparsers.add_parser("fetch")
    fetch.add_argument("--source-manifest", type=Path, required=True)
    fetch.add_argument("--output", type=Path, required=True)
    fetch.add_argument("--game", action="append", default=[])
    fetch.add_argument("--timeout-seconds", type=float, default=120.0)
    fetch.add_argument("--retry-count", type=int, default=2)
    merge = subparsers.add_parser("merge")
    merge.add_argument("--source-manifest", type=Path, required=True)
    merge.add_argument("--corpus", type=Path, action="append", required=True)
    merge.add_argument("--output", type=Path, required=True)
    validate = subparsers.add_parser("validate")
    validate.add_argument("--corpus", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    if args.command == "fetch":
        corpus = build_full_solution_corpus(
            source_manifest_path=args.source_manifest,
            requested_games=tuple(args.game),
            timeout_seconds=args.timeout_seconds,
            retry_count=args.retry_count,
        )
        _write_json(args.output, corpus)
        print(
            json.dumps(
                {
                    "output": str(args.output.resolve()),
                    "game_count": corpus["game_count"],
                    "level_count": corpus["level_count"],
                    "action_count": corpus["action_count"],
                    "content_digest": corpus["content_digest"],
                },
                sort_keys=True,
            )
        )
        return 0
    if args.command == "merge":
        corpus = merge_solution_corpora(
            source_manifest_path=args.source_manifest,
            corpus_paths=tuple(args.corpus),
        )
        _write_json(args.output, corpus)
        print(
            json.dumps(
                {
                    "output": str(args.output.resolve()),
                    "game_count": corpus["game_count"],
                    "level_count": corpus["level_count"],
                    "action_count": corpus["action_count"],
                    "complete_inventory": corpus["complete_inventory"],
                    "content_digest": corpus["content_digest"],
                },
                sort_keys=True,
            )
        )
        return 0
    corpus = load_full_solution_corpus(args.corpus)
    print(
        json.dumps(
            {
                "corpus": str(args.corpus.resolve()),
                "game_count": corpus["game_count"],
                "level_count": corpus["level_count"],
                "action_count": corpus["action_count"],
                "content_digest": corpus["content_digest"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "DATASET_ROWS_ENDPOINT",
    "FULL_SOLUTION_CORPUS_SCHEMA_VERSION",
    "SOURCE_MANIFEST_SCHEMA_VERSION",
    "TEACHER_PRIVILEGES",
    "build_full_solution_corpus",
    "load_full_solution_corpus",
    "load_source_manifest",
    "merge_solution_corpora",
    "source_manifest_digest",
]
