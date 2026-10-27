"""Evaluate an ID-free Action 6 prior learned from public human demonstrations."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path, PurePosixPath
import random
import sys
import time
from typing import Any
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "検証"))

from ARC3探索Actionローカル評価 import _load_games, _run_game
from ARC3Action6局所パターン学習 import (
    _LocalPatternMemory,
    _aggregate,
    _coordinate_feature,
    _input_manifest_hash,
    _policy_type,
    _score,
)

EXPECTED_DATASET_SHA256 = "347a4fdba7075babc84b263273122d623fadbe5183b76daa6850534d72039a7c"


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(8 * 1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _action_number(value: Any) -> int | None:
    if type(value) is int and 0 <= value <= 7:
        return value
    if value == "RESET":
        return 0
    if isinstance(value, str) and value.startswith("ACTION"):
        suffix = value[6:]
        if suffix in {str(number) for number in range(1, 8)}:
            return int(suffix)
    return None


def _event_game_id(event: dict[str, Any]) -> str | None:
    action_input = event.get("action_input")
    payload = action_input.get("data") if isinstance(action_input, dict) else None
    game_id = payload.get("game_id") if isinstance(payload, dict) else None
    return game_id if isinstance(game_id, str) and game_id else None


def _first_game_id(archive: zipfile.ZipFile, info: zipfile.ZipInfo) -> str | None:
    with archive.open(info) as stream:
        for line in stream:
            wrapper = json.loads(line)
            event = wrapper.get("data") if isinstance(wrapper, dict) else None
            if isinstance(event, dict):
                game_id = _event_game_id(event)
                if game_id is not None:
                    return game_id
    return None


def _latest_board(event: dict[str, Any]) -> tuple[tuple[int, ...], ...] | None:
    frames = event.get("frame")
    if not isinstance(frames, list) or not frames or not isinstance(frames[-1], list):
        return None
    rows = frames[-1]
    if not 1 <= len(rows) <= 64:
        return None
    board: list[tuple[int, ...]] = []
    for row in rows:
        if not isinstance(row, list) or not 1 <= len(row) <= 64:
            return None
        if any(type(cell) is not int or not 0 <= cell <= 15 for cell in row):
            return None
        board.append(tuple(row))
    if len({len(row) for row in board}) != 1:
        return None
    return tuple(board)


def _board_digest(board: tuple[tuple[int, ...], ...]) -> bytes:
    encoded = len(board).to_bytes(2, "big") + len(board[0]).to_bytes(2, "big")
    encoded += b"".join(bytes(row) for row in board)
    return hashlib.sha256(encoded).digest()


def _available_actions(event: dict[str, Any]) -> set[int]:
    raw = event.get("available_actions")
    if not isinstance(raw, list):
        return set()
    return {number for item in raw if (number := _action_number(item)) is not None}


def _integer_field(event: dict[str, Any], key: str) -> int:
    value = event.get(key, 0)
    return value if type(value) is int and value >= 0 else 0


def _changed_cells(
    before: tuple[tuple[int, ...], ...], after: tuple[tuple[int, ...], ...]
) -> int:
    if len(before) != len(after) or any(len(a) != len(b) for a, b in zip(before, after)):
        return max(1, len(before) + len(after))
    return sum(
        old != new
        for old_row, new_row in zip(before, after)
        for old, new in zip(old_row, new_row)
    )


def _recording_features(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    expected_game_id: str,
) -> tuple[list[tuple[str, float]], Counter[str], bool]:
    """Return only compact feature/reward pairs; discard raw observations and IDs."""
    features: list[tuple[str, float]] = []
    counts: Counter[str] = Counter()
    seen_game_ids: set[str] = set()
    seen_boards: set[bytes] = set()
    previous: dict[str, Any] | None = None
    version_matches = True

    with archive.open(info) as stream:
        for line in stream:
            wrapper = json.loads(line)
            event = wrapper.get("data") if isinstance(wrapper, dict) else None
            if not isinstance(event, dict):
                counts["invalid_events"] += 1
                previous = None
                seen_boards.clear()
                continue

            observed_game_id = _event_game_id(event)
            if observed_game_id is not None:
                seen_game_ids.add(observed_game_id)
                if observed_game_id != expected_game_id:
                    version_matches = False

            board_after = _latest_board(event)
            action_input = event.get("action_input")
            action_number = (
                _action_number(action_input.get("id"))
                if isinstance(action_input, dict)
                else None
            )

            if action_number == 0:
                previous = event
                seen_boards = {_board_digest(board_after)} if board_after else set()
                continue

            if previous is not None and action_number == 6:
                counts["action6_records"] += 1
                before = _latest_board(previous)
                payload = action_input.get("data") if isinstance(action_input, dict) else None
                x = payload.get("x") if isinstance(payload, dict) else None
                y = payload.get("y") if isinstance(payload, dict) else None
                if (
                    before is None
                    or board_after is None
                    or not isinstance(payload, dict)
                    or type(x) is not int
                    or type(y) is not int
                    or not (0 <= x < len(before[0]) and 0 <= y < len(before))
                    or 6 not in _available_actions(previous)
                    or previous.get("state") != "NOT_FINISHED"
                ):
                    counts["invalid_action6_transitions"] += 1
                else:
                    color = before[y][x]
                    try:
                        feature = _coordinate_feature(before, color, x, y)
                    except ValueError:
                        counts["invalid_action6_transitions"] += 1
                    else:
                        changed = _changed_cells(before, board_after)
                        area = max(1, sum(len(row) for row in before))
                        progress = max(
                            0,
                            _integer_field(event, "levels_completed")
                            - _integer_field(previous, "levels_completed"),
                        )
                        new_board = _board_digest(board_after) not in seen_boards
                        reward = 4.0 * progress
                        reward += 0.5 if new_board else 0.0
                        reward += 0.25 * min(1.0, changed / area)
                        if changed == 0 and progress == 0:
                            reward -= 1.0
                        features.append((feature, reward))
                        counts["usable_action6_transitions"] += 1

            if board_after is not None:
                seen_boards.add(_board_digest(board_after))
            previous = event

    if len(seen_game_ids) != 1 or next(iter(seen_game_ids), None) != expected_game_id:
        version_matches = False
    return features, counts, version_matches


def _recording_manifest(
    archive: zipfile.ZipFile,
    current_game_ids: dict[str, str],
) -> tuple[dict[str, list[zipfile.ZipInfo]], Counter[str]]:
    exact_by_group: dict[str, list[zipfile.ZipInfo]] = defaultdict(list)
    counts: Counter[str] = Counter()
    for info in archive.infolist():
        if not info.filename.endswith(".recording.jsonl"):
            continue
        counts["recording_files"] += 1
        path = PurePosixPath(info.filename)
        if len(path.parts) != 3 or path.parts[0] != "public_games-dataset":
            counts["invalid_recording_paths"] += 1
            continue
        group = path.parts[1]
        if group not in current_game_ids:
            counts["unmatched_environment_groups"] += 1
            continue
        game_id = _first_game_id(archive, info)
        if game_id is None:
            counts["missing_version_ids"] += 1
            continue
        counts["recordings_with_version_id"] += 1
        if game_id == current_game_ids[group]:
            exact_by_group[group].append(info)
            counts["current_version_recordings"] += 1
        else:
            counts["stale_version_recordings"] += 1
    counts["current_version_groups"] = len(exact_by_group)
    counts["stale_version_groups"] = len(
        {
            PurePosixPath(info.filename).parts[1]
            for info in archive.infolist()
            if info.filename.endswith(".recording.jsonl")
            and len(PurePosixPath(info.filename).parts) == 3
            and PurePosixPath(info.filename).parts[1] in current_game_ids
        }
        - set(exact_by_group)
    )
    return exact_by_group, counts


def _sha256_group_set(groups: list[str]) -> str:
    # IDs are used only to define nonoverlapping evaluation groups, never as features.
    encoded = "\n".join(sorted(groups)).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _trace_digest(run: dict[str, Any]) -> str:
    public_trace = [
        (int(row["action_id"]), row.get("data", {})) for row in run["action_responses"]
    ]
    encoded = json.dumps(public_trace, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--human-archive", type=Path, required=True)
    parser.add_argument("--expected-archive-sha256", required=True)
    parser.add_argument(
        "--environment-dir", type=Path, default=ROOT / "入力/Kaggle/environment_files"
    )
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split-seed", type=int, default=20261027)
    parser.add_argument("--train-groups", type=int, default=7)
    parser.add_argument("--dev-groups", type=int, default=3)
    parser.add_argument("--max-samples-per-train-group", type=int, default=1000)
    parser.add_argument("--eval-actions", type=int, default=80)
    parser.add_argument("--seeds", type=int, nargs="+", default=[7, 31, 73])
    parser.add_argument("--ucb-weight", type=float, default=0.35)
    args = parser.parse_args()

    if args.expected_archive_sha256 != EXPECTED_DATASET_SHA256:
        raise ValueError("the requested archive hash is not the reviewed dataset snapshot")
    if min(args.train_groups, args.dev_groups, args.max_samples_per_train_group) <= 0:
        raise ValueError("group and sample limits must be positive")
    if args.train_groups + args.dev_groups != 10:
        raise ValueError("the reviewed current-version human subset has 10 environments")
    started = time.perf_counter()
    archive_sha = _sha256_file(args.human_archive)
    if archive_sha != args.expected_archive_sha256:
        raise ValueError("human dataset archive SHA-256 mismatch")

    all_games = _load_games(args.environment_dir)
    current_game_ids: dict[str, str] = {}
    games_by_group: dict[str, tuple[dict[str, Any], Path]] = {}
    for metadata, metadata_path in all_games:
        group = metadata_path.parent.parent.name
        if group in current_game_ids:
            raise RuntimeError("more than one current environment metadata file per group")
        current_game_ids[group] = str(metadata["game_id"])
        games_by_group[group] = (metadata, metadata_path)
    if len(current_game_ids) != 25:
        raise RuntimeError("expected the current 25 public ARC3 environments")

    with zipfile.ZipFile(args.human_archive) as archive:
        exact_by_group, source_counts = _recording_manifest(archive, current_game_ids)
        groups = sorted(exact_by_group)
        if len(groups) != 10:
            raise RuntimeError("current-version recordings do not cover the reviewed 10 groups")
        random.Random(args.split_seed).shuffle(groups)
        train_groups = groups[: args.train_groups]
        dev_groups = groups[args.train_groups : args.train_groups + args.dev_groups]

        per_group_features: dict[str, list[tuple[str, float]]] = {}
        per_group_counts: dict[str, Counter[str]] = {}
        groups_without_action6: list[str] = []
        sample_rng = random.Random(args.split_seed ^ 0xA6C3)
        for group_index, group in enumerate(sorted(train_groups), start=1):
            features: list[tuple[str, float]] = []
            group_counts: Counter[str] = Counter()
            for info in sorted(exact_by_group[group], key=lambda item: item.filename):
                recording_features, counts, version_matches = _recording_features(
                    archive, info, current_game_ids[group]
                )
                group_counts.update(counts)
                if not version_matches:
                    group_counts["recordings_rejected_for_version_conflict"] += 1
                    continue
                features.extend(recording_features)
            per_group_counts[group] = group_counts
            if features:
                per_group_features[group] = features
            else:
                groups_without_action6.append(group)
            print(f"PROGRESS train_group={group_index}/{len(train_groups)}", flush=True)

        if len(per_group_features) < 4:
            raise RuntimeError("fewer than four training environments contain valid Action 6 samples")
        sample_target = min(
            args.max_samples_per_train_group,
            min(len(features) for features in per_group_features.values()),
        )
        if sample_target < 1:
            raise RuntimeError("no balanced human Action 6 samples remain")
        memory = _LocalPatternMemory(args.ucb_weight)
        training_counts: Counter[str] = Counter()
        for group in sorted(per_group_features):
            features = per_group_features[group]
            selected = (
                features
                if len(features) <= sample_target
                else sample_rng.sample(features, sample_target)
            )
            training_counts["usable_action6_transitions"] += len(features)
            training_counts["balanced_training_samples"] += len(selected)
            for feature, reward in selected:
                memory.observe(feature, reward)
        trained_snapshot = memory.snapshot()
        trained_hash = memory.digest()

        rows: list[dict[str, int | float]] = []
        supported_selections = 0
        online_updates = 0
        post_episode_hashes: list[str] = []
        illegal_actions = 0
        duplicate_observations = 0
        deterministic_repeat_match: bool | None = None
        repeat_reference: tuple[float, int, int, int, int, str] | None = None

        for seed in args.seeds:
            for index, group in enumerate(dev_groups, start=1):
                metadata, metadata_path = games_by_group[group]
                baseline_run = _run_game(
                    metadata,
                    metadata_path,
                    "exploration",
                    seed=seed,
                    policy_seed=seed,
                    max_actions=args.eval_actions,
                    visible_change_coefficient=0.0,
                )
                episode_memory = _LocalPatternMemory.from_snapshot(trained_snapshot)
                metrics = Counter()
                candidate_policy = _policy_type(
                    episode_memory, use_memory=True, metrics=metrics
                )
                candidate_run = _run_game(
                    metadata,
                    metadata_path,
                    "exploration",
                    seed=seed,
                    policy_seed=seed,
                    max_actions=args.eval_actions,
                    visible_change_coefficient=0.0,
                    policy_type_override=candidate_policy,
                )
                same_start = int(
                    all(
                        baseline_run[key] == candidate_run[key]
                        for key in (
                            "initial_state",
                            "initial_levels_completed",
                            "initial_available_actions",
                            "initial_board",
                        )
                    )
                )
                if not same_start:
                    raise RuntimeError("paired initial observation mismatch")
                illegal_actions += int(baseline_run["illegal_action_attempts"])
                illegal_actions += int(candidate_run["illegal_action_attempts"])
                duplicate_observations += int(baseline_run["duplicate_observation_steps"])
                duplicate_observations += int(candidate_run["duplicate_observation_steps"])
                baseline_score = _score(metadata, baseline_run)
                candidate_score = _score(metadata, candidate_run)
                candidate_trace_hash = _trace_digest(candidate_run)

                if seed == args.seeds[0] and index == 1:
                    repeat_reference = (*candidate_score, candidate_trace_hash)
                    repeated_memory = _LocalPatternMemory.from_snapshot(trained_snapshot)
                    repeated_metrics = Counter()
                    repeated_policy = _policy_type(
                        repeated_memory, use_memory=True, metrics=repeated_metrics
                    )
                    repeated_run = _run_game(
                        metadata,
                        metadata_path,
                        "exploration",
                        seed=seed,
                        policy_seed=seed,
                        max_actions=args.eval_actions,
                        visible_change_coefficient=0.0,
                        policy_type_override=repeated_policy,
                    )
                    repeated_score = _score(metadata, repeated_run)
                    deterministic_repeat_match = (
                        (*repeated_score, _trace_digest(repeated_run)) == repeat_reference
                    )

                row = {
                    "seed": seed,
                    "previous_score": baseline_score[0],
                    "candidate_score": candidate_score[0],
                    "previous_levels": baseline_score[1],
                    "candidate_levels": candidate_score[1],
                    "previous_wins": baseline_score[2],
                    "candidate_wins": candidate_score[2],
                    "previous_noops": baseline_score[3],
                    "candidate_noops": candidate_score[3],
                    "start_matches": same_start,
                    "trace_changed": int(
                        _trace_digest(baseline_run) != candidate_trace_hash
                    ),
                }
                rows.append(row)
                supported_selections += int(
                    metrics["model_supported_coordinate_selections"]
                )
                online_updates += (
                    episode_memory.snapshot()["total_action6_samples"]
                    - trained_snapshot["total_action6_samples"]
                )
                post_episode_hashes.append(episode_memory.digest())
                print(
                    f"PROGRESS dev seed={seed} episode={index}/{len(dev_groups)}",
                    flush=True,
                )

    serialized = json.dumps(trained_snapshot, ensure_ascii=True, sort_keys=True)
    if any(token in serialized for token in ("game_id", "level_id", '"x"', '"y"')):
        raise RuntimeError("identifier or raw coordinate found in learned memory")
    overall = _aggregate(rows)
    grouped = [
        {"seed": seed, **_aggregate([row for row in rows if row["seed"] == seed])}
        for seed in args.seeds
    ]
    gates = {
        "dev_mean_delta_at_least_0_01": overall["score_delta_mean"] >= 0.01,
        "improvements_at_least_regressions": overall["score_improvements"]
        >= overall["score_regressions"],
        "levels_not_regressed": overall["levels_delta_total"] >= 0,
        "wins_not_regressed": overall["wins_delta_total"] >= 0,
        "illegal_actions_zero": illegal_actions == 0,
        "duplicate_observations_zero": duplicate_observations == 0,
        "same_run_reproduced": deterministic_repeat_match is True,
    }
    result = {
        "schema": "arc3-human-action6-prior-dev.v1",
        "run_id": "C2-093_human-public-demo-action6-prior-dev",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": {
            "official_release": "https://arcprize.org/blog/arc-agi-3-human-dataset",
            "kaggle_dataset": "magicsword001/arc-agi-3-public-demo-human-testing",
            "dataset_archive_sha256": archive_sha,
            "dataset_archive_bytes": args.human_archive.stat().st_size,
            "official_article_replays": 342,
            "mirror_recording_files": source_counts["recording_files"],
            "current_version_recordings": source_counts["current_version_recordings"],
            "stale_version_recordings": source_counts["stale_version_recordings"],
            "current_version_environment_groups": source_counts[
                "current_version_groups"
            ],
            "stale_environment_groups": source_counts["stale_version_groups"],
            "human_reasoning_text_used": False,
            "game_and_session_identifiers_used_as_features": False,
            "kaggle_license_label": "other",
        },
        "split": {
            "seed": args.split_seed,
            "current_version_groups_total": len(exact_by_group),
            "train_groups": len(train_groups),
            "dev_groups": len(dev_groups),
            "train_groups_with_valid_action6_data": len(per_group_features),
            "train_groups_without_valid_action6_data": len(groups_without_action6),
            "train_group_digest": _sha256_group_set(train_groups),
            "dev_group_digest": _sha256_group_set(dev_groups),
            "group_identifiers_persisted": False,
        },
        "training": {
            "features": [
                "target_color_frequency_band",
                "same_color_8_neighbor_band",
                "edge_or_interior",
            ],
            "max_samples_per_group": args.max_samples_per_train_group,
            "balanced_samples_per_group": sample_target,
            "valid_action6_transitions_before_balancing": training_counts[
                "usable_action6_transitions"
            ],
            "samples_used": training_counts["balanced_training_samples"],
            "feature_categories": len(trained_snapshot["features"]),
            "learned_memory_sha256": trained_hash,
            "game_ids_level_ids_and_raw_coordinates_persisted": False,
        },
        "comparison": {**overall, "by_seed": grouped},
        "candidate_online_learning": {
            "model_supported_coordinate_selections": supported_selections,
            "online_action6_updates_after_human_prior": online_updates,
            "episode_memory_hashes_sha256": hashlib.sha256(
                "".join(sorted(post_episode_hashes)).encode("ascii")
            ).hexdigest(),
        },
        "reproducibility": {
            "same_candidate_run_repeated": deterministic_repeat_match,
            "same_candidate_run_reference_trace_sha256": (
                repeat_reference[-1] if repeat_reference else None
            ),
        },
        "gates": gates,
        "decision": "PROMOTE_TO_INDEPENDENT_HOLDOUT"
        if all(gates.values())
        else "REJECT_CANDIDATE",
        "errors": 0,
        "illegal_actions": illegal_actions,
        "duplicate_observations": duplicate_observations,
        "official_submission_made": False,
        "notebook_or_kernel_changed": False,
        "environment_manifest_sha256": _input_manifest_hash(),
        "runtime_version": {
            "python": sys.version.split()[0],
            "arc_agi": "see locked project environment",
            "arcengine": "see locked project environment",
        },
        "runner_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "limitations": [
            "Only recordings whose game version exactly matches the current public environment metadata were used.",
            "The mirror has 340 recordings while the official article reports 342; the two-record gap is unresolved.",
            "Kaggle marks the mirror license as other; the official source describes the release as open source but no explicit license was recovered.",
            "This is a three-environment development holdout and is not an official competition score.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
