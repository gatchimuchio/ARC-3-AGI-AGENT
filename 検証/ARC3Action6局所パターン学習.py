"""Learn ID-free public local patterns for ARC3 coordinate Action 6."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass
import hashlib
import json
import math
import os
from pathlib import Path
import random
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from ARC3公開RHAE評価 import _スコアを計算する
from ARC3探索Actionローカル評価 import _load_games, _run_game
from 接続.ARC3境界 import 観測
from 接続.観測駆動探索Action import 観測駆動探索方針

_PRIOR_STRENGTH = 3.0
_UCB_WEIGHT = 0.35


def _coordinate_feature(
    board: tuple[tuple[int, ...], ...],
    color: int,
    x: int,
    y: int,
    color_share: float | None = None,
) -> str:
    height = len(board)
    width = len(board[0]) if board else 0
    if not height or not width or any(len(row) != width for row in board):
        raise ValueError("coordinate feature requires a nonempty rectangular board")
    if not (0 <= x < width and 0 <= y < height):
        raise ValueError("coordinate is outside the public board")

    area = width * height
    if color_share is None:
        color_share = sum(cell == color for row in board for cell in row) / area
    frequency = "rare" if color_share < 0.05 else "mid" if color_share < 0.25 else "common"
    same_neighbors = sum(
        board[ny][nx] == color
        for ny in range(max(0, y - 1), min(height, y + 2))
        for nx in range(max(0, x - 1), min(width, x + 2))
        if (nx, ny) != (x, y)
    )
    neighbor_band = (
        "zero" if same_neighbors == 0 else "one_two" if same_neighbors <= 2 else "three_plus"
    )
    location = "edge" if x in (0, width - 1) or y in (0, height - 1) else "interior"
    return f"{frequency}|{neighbor_band}|{location}"


@dataclass
class _FeatureStats:
    count: int = 0
    reward_sum: float = 0.0


class _LocalPatternMemory:
    def __init__(self, ucb_weight: float = _UCB_WEIGHT) -> None:
        if not math.isfinite(ucb_weight) or ucb_weight < 0:
            raise ValueError("ucb_weight must be finite and nonnegative")
        self._ucb_weight = ucb_weight
        self._features: dict[str, _FeatureStats] = {}
        self._total = 0
        self._reward_sum = 0.0

    def observe(self, feature: str, reward: float) -> None:
        stats = self._features.setdefault(feature, _FeatureStats())
        stats.count += 1
        stats.reward_sum += reward
        self._total += 1
        self._reward_sum += reward

    def support(self, feature: str) -> int:
        return self._features.get(feature, _FeatureStats()).count

    def score(self, feature: str) -> float:
        global_mean = self._reward_sum / self._total if self._total else 0.0
        stats = self._features.get(feature, _FeatureStats())
        mean = (stats.reward_sum + _PRIOR_STRENGTH * global_mean) / (stats.count + _PRIOR_STRENGTH)
        bonus = self._ucb_weight * math.sqrt(math.log(max(2, self._total)) / (stats.count + 1))
        return mean + bonus

    def snapshot(self) -> dict[str, Any]:
        return {
            "version": 1,
            "prior_strength": _PRIOR_STRENGTH,
            "ucb_weight": self._ucb_weight,
            "total_action6_samples": self._total,
            "global_reward_sum": round(self._reward_sum, 9),
            "features": {
                key: {
                    "count": value.count,
                    "reward_sum": round(value.reward_sum, 9),
                }
                for key, value in sorted(self._features.items())
            },
        }

    def digest(self) -> str:
        encoded = json.dumps(
            self.snapshot(), ensure_ascii=True, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(encoded).hexdigest()

    @classmethod
    def from_snapshot(cls, snapshot: dict[str, Any]) -> _LocalPatternMemory:
        memory = cls(float(snapshot["ucb_weight"]))
        memory._total = int(snapshot["total_action6_samples"])
        memory._reward_sum = float(snapshot["global_reward_sum"])
        memory._features = {
            key: _FeatureStats(count=int(value["count"]), reward_sum=float(value["reward_sum"]))
            for key, value in snapshot["features"].items()
        }
        return memory


def _policy_type(memory: _LocalPatternMemory, *, use_memory: bool, metrics: dict[str, int]):
    class _Action6LearnedPolicy(観測駆動探索方針):
        def _未試行座標を選ぶ(self, 盤面, 色, 未試行座標):
            if not use_memory:
                return self._rng.choice(未試行座標)
            area = sum(len(row) for row in 盤面)
            color_share = sum(cell == 色 for row in 盤面 for cell in row) / max(1, area)
            scored = []
            for x, y in 未試行座標:
                feature = _coordinate_feature(盤面, 色, x, y, color_share)
                scored.append((memory.score(feature), feature, (x, y)))
            best_score = max(item[0] for item in scored)
            ties = [item for item in scored if item[0] == best_score]
            selected = self._rng.choice(ties)
            metrics["model_supported_coordinate_selections"] += int(memory.support(selected[1]) > 0)
            return selected[2]

        def 応答を記録する(self, 作用前: 観測, action, 作用後: 観測):
            response = super().応答を記録する(作用前, action, 作用後)
            if action.作用番号 == 6:
                x, y = action.引数["x"], action.引数["y"]
                color = int(作用前.最新盤面[y][x])
                memory.observe(
                    _coordinate_feature(作用前.最新盤面, color, x, y),
                    float(response["公開応答報酬"]),
                )
            return response

    return _Action6LearnedPolicy


def _input_manifest_hash() -> str:
    root = ROOT / "入力/Kaggle/environment_files"
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(hashlib.sha256(content).digest())
    return digest.hexdigest()


def _score(metadata: dict[str, Any], run: dict[str, Any]) -> tuple[float, int, int, int, int]:
    baseline = metadata.get("baseline_actions")
    if not isinstance(baseline, list) or not all(
        type(value) is int and value > 0 for value in baseline
    ):
        raise RuntimeError("public scorecard baseline metadata is invalid")
    score, scored_levels, _ = _スコアを計算する(baseline, run)
    if scored_levels != int(run["levels_completed"]) - int(run["initial_levels_completed"]):
        raise RuntimeError("scorecard levels disagree with SDK completion count")
    return (
        float(score),
        int(run["levels_completed"]),
        int(run["final_state"] == "WIN"),
        int(run["no_op_actions"]),
        int(run["actions"]),
    )


def _aggregate(rows: list[dict[str, int | float]]) -> dict[str, Any]:
    deltas = [float(row["candidate_score"]) - float(row["previous_score"]) for row in rows]
    return {
        "pairs": len(rows),
        "previous_score_mean": sum(float(row["previous_score"]) for row in rows) / len(rows),
        "candidate_score_mean": sum(float(row["candidate_score"]) for row in rows) / len(rows),
        "score_delta_mean": sum(deltas) / len(rows),
        "score_improvements": sum(value > 1e-9 for value in deltas),
        "score_regressions": sum(value < -1e-9 for value in deltas),
        "score_ties": sum(abs(value) <= 1e-9 for value in deltas),
        "levels_delta_total": sum(
            int(row["candidate_levels"]) - int(row["previous_levels"]) for row in rows
        ),
        "wins_delta_total": sum(
            int(row["candidate_wins"]) - int(row["previous_wins"]) for row in rows
        ),
        "noops_delta_total": sum(
            int(row["candidate_noops"]) - int(row["previous_noops"]) for row in rows
        ),
        "start_matches": sum(int(row["start_matches"]) for row in rows),
        "trace_changed_pairs": sum(int(row["trace_changed"]) for row in rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("dev", "holdout"), default="dev")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--split-seed", type=int, default=20261027)
    parser.add_argument("--train-games", type=int, default=5)
    parser.add_argument("--train-offsets", type=int, nargs="+")
    parser.add_argument("--train-actions", type=int, default=40)
    parser.add_argument("--dev-games", type=int, default=5)
    parser.add_argument("--dev-offset", type=int)
    parser.add_argument("--eval-actions", type=int, default=80)
    parser.add_argument("--seeds", type=int, nargs="+", default=[7, 31, 73])
    parser.add_argument("--ucb-weight", type=float, default=_UCB_WEIGHT)
    args = parser.parse_args()
    if not math.isfinite(args.ucb_weight) or args.ucb_weight < 0:
        raise ValueError("ucb-weight must be finite and nonnegative")
    if min(args.train_games, args.train_actions, args.dev_games, args.eval_actions) <= 0:
        raise ValueError("game and action limits must be positive")

    started = time.perf_counter()
    all_games = _load_games(ROOT / "入力/Kaggle/environment_files")
    if len(all_games) != 25 or args.train_games + args.dev_games >= len(all_games):
        raise RuntimeError("expected 25 games and nonempty train/dev/holdout splits")
    shuffled = list(all_games)
    random.Random(args.split_seed).shuffle(shuffled)
    dev_offset = args.train_games if args.dev_offset is None else args.dev_offset
    train_offsets = [0] if args.train_offsets is None else args.train_offsets
    if not train_offsets or args.train_games % len(train_offsets):
        raise ValueError("train-games must divide evenly among train-offsets")
    train_window_size = args.train_games // len(train_offsets)
    train_indices = [
        index for offset in train_offsets for index in range(offset, offset + train_window_size)
    ]
    dev_indices = list(range(dev_offset, dev_offset + args.dev_games))
    if (
        len(set(train_indices)) != len(train_indices)
        or min(train_indices + dev_indices) < 0
        or max(train_indices + dev_indices) >= len(shuffled)
        or set(train_indices) & set(dev_indices)
    ):
        raise ValueError("train and dev windows overlap or exceed the public dataset")
    train_games = [shuffled[index] for index in train_indices]
    dev_games = [shuffled[index] for index in dev_indices]
    memory = _LocalPatternMemory(args.ucb_weight)
    training_updates = 0
    for index, (metadata, metadata_path) in enumerate(train_games, start=1):
        metrics = Counter()
        policy = _policy_type(memory, use_memory=False, metrics=metrics)
        run = _run_game(
            metadata,
            metadata_path,
            "exploration",
            seed=args.split_seed + index,
            policy_seed=args.split_seed + index,
            max_actions=args.train_actions,
            visible_change_coefficient=0.0,
            policy_type_override=policy,
        )
        training_updates += sum(1 for row in run["action_responses"] if row["action_id"] == 6)
        print(f"PROGRESS train={index}/{len(train_games)}", flush=True)

    trained_snapshot = memory.snapshot()
    trained_hash = memory.digest()
    rows: list[dict[str, int | float]] = []
    supported_selections = 0
    online_updates = 0
    post_episode_hashes: list[str] = []
    illegal_actions = 0
    duplicate_observations = 0
    for seed in args.seeds:
        for index, (metadata, metadata_path) in enumerate(dev_games, start=1):
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
            candidate_policy = _policy_type(episode_memory, use_memory=True, metrics=metrics)
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
            prev = _score(metadata, baseline_run)
            cand = _score(metadata, candidate_run)
            prev_trace = [
                (item["action_id"], item["data"]) for item in baseline_run["action_responses"]
            ]
            cand_trace = [
                (item["action_id"], item["data"]) for item in candidate_run["action_responses"]
            ]
            rows.append(
                {
                    "seed": seed,
                    "previous_score": prev[0],
                    "candidate_score": cand[0],
                    "previous_levels": prev[1],
                    "candidate_levels": cand[1],
                    "previous_wins": prev[2],
                    "candidate_wins": cand[2],
                    "previous_noops": prev[3],
                    "candidate_noops": cand[3],
                    "start_matches": same_start,
                    "trace_changed": int(prev_trace != cand_trace),
                }
            )
            supported_selections += int(metrics["model_supported_coordinate_selections"])
            online_updates += (
                episode_memory.snapshot()["total_action6_samples"]
                - trained_snapshot["total_action6_samples"]
            )
            post_episode_hashes.append(episode_memory.digest())
            print(
                f"PROGRESS {args.stage} seed={seed} episodes={index}/{len(dev_games)}",
                flush=True,
            )

    serialized = json.dumps(trained_snapshot, ensure_ascii=True, sort_keys=True)
    if any(token in serialized for token in ("game_id", "level_id", '"x"', '"y"')):
        raise RuntimeError("identifier or raw coordinate found in learned memory")
    grouped = [
        {"seed": seed, **_aggregate([row for row in rows if row["seed"] == seed])}
        for seed in args.seeds
    ]
    output = {
        "schema": "arc3-action6-local-pattern-transfer.v1",
        "stage": args.stage,
        "python_hash_seed": os.environ.get("PYTHONHASHSEED", "randomized"),
        "split_seed": args.split_seed,
        "train_games": args.train_games,
        "train_windows": [
            {"offset": offset, "games": train_window_size} for offset in train_offsets
        ],
        "train_actions_per_game": args.train_actions,
        "dev_games": args.dev_games,
        "dev_offset": dev_offset,
        "evaluation_seeds": args.seeds,
        "evaluation_actions_per_game": args.eval_actions,
        "features": [
            "target_color_frequency_band",
            "same_color_8_neighbor_band",
            "edge_or_interior",
        ],
        "memory": {
            "ucb_weight": args.ucb_weight,
            "training_action6_updates": training_updates,
            "feature_categories": len(trained_snapshot["features"]),
            "trained_sha256": trained_hash,
            "holdout_online_action6_updates": online_updates,
            "model_supported_coordinate_selections": supported_selections,
            "holdout_episode_hashes_sha256": hashlib.sha256(
                "".join(sorted(post_episode_hashes)).encode("ascii")
            ).hexdigest(),
            "game_ids_level_ids_and_raw_coordinates_persisted": False,
        },
        "comparison": {**_aggregate(rows), "by_seed": grouped},
        "errors": 0,
        "illegal_actions": illegal_actions,
        "duplicate_observations": duplicate_observations,
        "official_submission_made": False,
        "notebook_or_kernel_changed": False,
        "environment_manifest_sha256": _input_manifest_hash(),
        "policy_source_sha256": hashlib.sha256(
            (ROOT / "接続/観測駆動探索Action.py").read_bytes()
        ).hexdigest(),
        "runner_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(output, ensure_ascii=False, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
