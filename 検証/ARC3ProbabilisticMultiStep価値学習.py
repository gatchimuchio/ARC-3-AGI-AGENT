"""Evaluate ID-free probabilistic multi-step value transfer on public ARC3 games."""

from __future__ import annotations

import argparse
from collections import Counter
from dataclasses import dataclass, field
import hashlib
import json
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

_TERMINAL = "TERMINAL"
_GAMMA = 0.65
_DIRICHLET_BACKOFF = 2.0
_VALUE_ITERATIONS = 8
_VALUE_WEIGHT = 0.5


def _context_key(observation: 観測) -> str:
    """Encode coarse public affordances only; never encode game/level identity."""
    legal_actions = sorted(
        action for action in observation.作用可能番号 if type(action) is int and 1 <= action <= 7
    )
    color_counts: Counter[int] = Counter(color for row in observation.最新盤面 for color in row)
    area = max(1, sum(len(row) for row in observation.最新盤面))
    majority_share = max(color_counts.values(), default=0) / area
    majority_band = (
        "low"
        if majority_share < 0.25
        else "mid_low"
        if majority_share < 0.5
        else "mid_high"
        if majority_share < 0.75
        else "high"
    )
    colors_band = (
        "1"
        if len(color_counts) <= 1
        else "2"
        if len(color_counts) == 2
        else "3"
        if len(color_counts) == 3
        else "4plus"
    )
    return json.dumps(
        [legal_actions, colors_band, majority_band],
        ensure_ascii=True,
        separators=(",", ":"),
    )


@dataclass
class _TransitionStats:
    samples: int = 0
    reward_sum: float = 0.0
    next_counts: Counter[str] = field(default_factory=Counter)


class _ProbabilisticValueMemory:
    """Dirichlet-smoothed transition counts with short Bellman value iteration."""

    def __init__(self) -> None:
        self._transitions: dict[tuple[str, int], _TransitionStats] = {}
        self._global_reward_sum: Counter[int] = Counter()
        self._global_action_counts: Counter[int] = Counter()
        self._global_next_counts: dict[int, Counter[str]] = {}
        self._updates = 0
        self._cache: dict[tuple[str, int], float] | None = None

    def observe(
        self,
        before_key: str,
        action_number: int,
        reward: float,
        after_key: str | None,
    ) -> None:
        key = (before_key, action_number)
        stats = self._transitions.setdefault(key, _TransitionStats())
        stats.samples += 1
        stats.reward_sum += reward
        next_key = _TERMINAL if after_key is None else after_key
        stats.next_counts[next_key] += 1
        self._global_reward_sum[action_number] += reward
        self._global_action_counts[action_number] += 1
        self._global_next_counts.setdefault(action_number, Counter())[next_key] += 1
        self._updates += 1
        self._cache = None

    def value(self, state_key: str, action_number: int) -> float:
        if self._cache is None:
            self._cache = self._solve()
        return self._cache.get((state_key, action_number), self._global_mean(action_number))

    def _global_mean(self, action_number: int) -> float:
        count = self._global_action_counts[action_number]
        return self._global_reward_sum[action_number] / count if count else 0.0

    def _solve(self) -> dict[tuple[str, int], float]:
        q = {
            key: stats.reward_sum / stats.samples
            for key, stats in self._transitions.items()
            if stats.samples
        }
        for _ in range(_VALUE_ITERATIONS):
            updated: dict[tuple[str, int], float] = {}
            for (state_key, action_number), stats in self._transitions.items():
                global_mean = self._global_mean(action_number)
                reward_mean = (stats.reward_sum + _DIRICHLET_BACKOFF * global_mean) / (
                    stats.samples + _DIRICHLET_BACKOFF
                )
                global_next = self._global_next_counts[action_number]
                global_total = sum(global_next.values())
                pseudo_total = _DIRICHLET_BACKOFF
                categories = set(stats.next_counts) | set(global_next)
                continuation = 0.0
                for next_key in categories:
                    local_count = stats.next_counts[next_key]
                    global_probability = (
                        global_next[next_key] / global_total if global_total else 0.0
                    )
                    probability = (local_count + pseudo_total * global_probability) / (
                        stats.samples + pseudo_total
                    )
                    if next_key == _TERMINAL:
                        continue
                    legal_actions = json.loads(next_key)[0]
                    next_value = max(
                        (
                            q.get((next_key, next_action), self._global_mean(next_action))
                            for next_action in legal_actions
                        ),
                        default=0.0,
                    )
                    continuation += probability * next_value
                updated[(state_key, action_number)] = max(
                    -8.0, min(12.0, reward_mean + _GAMMA * continuation)
                )
            q = updated
        return q

    def snapshot(self) -> dict[str, Any]:
        rows = [
            {
                "state": state,
                "action": action,
                "samples": stats.samples,
                "reward_sum": round(stats.reward_sum, 9),
                "next_state_counts": dict(sorted(stats.next_counts.items())),
            }
            for (state, action), stats in sorted(self._transitions.items())
        ]
        return {
            "version": 1,
            "gamma": _GAMMA,
            "dirichlet_backoff": _DIRICHLET_BACKOFF,
            "value_iterations": _VALUE_ITERATIONS,
            "value_weight": _VALUE_WEIGHT,
            "updates": self._updates,
            "state_action_pairs": len(rows),
            "transitions": rows,
        }

    def digest(self) -> str:
        payload = json.dumps(
            self.snapshot(), ensure_ascii=True, sort_keys=True, separators=(",", ":")
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    @classmethod
    def from_snapshot(cls, snapshot: dict[str, Any]) -> _ProbabilisticValueMemory:
        model = cls()
        for row in snapshot["transitions"]:
            state_key = row["state"]
            action = row["action"]
            stats = _TransitionStats(
                samples=row["samples"],
                reward_sum=row["reward_sum"],
                next_counts=Counter(row["next_state_counts"]),
            )
            model._transitions[(state_key, action)] = stats
            model._global_reward_sum[action] += stats.reward_sum
            model._global_action_counts[action] += stats.samples
            model._global_next_counts.setdefault(action, Counter()).update(stats.next_counts)
            model._updates += stats.samples
        return model


def _policy_type(model: _ProbabilisticValueMemory, *, use_prior: bool):
    class _PolicyWithProbabilisticValue(観測駆動探索方針):
        def _追加行動価値(self, 現在: 観測, 作用番号: int) -> float:
            if not use_prior:
                return 0.0
            return _VALUE_WEIGHT * model.value(_context_key(現在), 作用番号)

        def 応答を記録する(self, 作用前: 観測, action, 作用後: 観測):
            response = super().応答を記録する(作用前, action, 作用後)
            next_key = None if 作用後.状態 in ("WIN", "GAME_OVER") else _context_key(作用後)
            model.observe(
                _context_key(作用前),
                action.作用番号,
                float(response["公開応答報酬"]),
                next_key,
            )
            return response

    return _PolicyWithProbabilisticValue


def _input_manifest_hash() -> str:
    digest = hashlib.sha256()
    environment_root = ROOT / "入力/Kaggle/environment_files"
    for path in sorted(item for item in environment_root.rglob("*") if item.is_file()):
        relative = path.relative_to(environment_root).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(hashlib.sha256(content).digest())
    return digest.hexdigest()


def _score(metadata: dict[str, Any], run: dict[str, Any]) -> tuple[float, int, int, int, int]:
    baseline_actions = metadata.get("baseline_actions")
    if not isinstance(baseline_actions, list) or not all(
        type(value) is int and value > 0 for value in baseline_actions
    ):
        raise RuntimeError("public scorecard baseline metadata is invalid")
    rhae, level_events, _ = _スコアを計算する(baseline_actions, run)
    if level_events != int(run["levels_completed"]) - int(run["initial_levels_completed"]):
        raise RuntimeError("scorecard level boundaries disagree with SDK completion count")
    return (
        float(rhae),
        int(run["levels_completed"]),
        int(run["final_state"] == "WIN"),
        int(run["no_op_actions"]),
        int(run["actions"]),
    )


def _aggregate(rows: list[dict[str, float | int]]) -> dict[str, Any]:
    pairs = len(rows)
    previous = [float(row["previous_score"]) for row in rows]
    candidate = [float(row["candidate_score"]) for row in rows]
    deltas = [b - a for a, b in zip(previous, candidate, strict=True)]
    return {
        "pairs": pairs,
        "previous_score_mean": sum(previous) / pairs,
        "candidate_score_mean": sum(candidate) / pairs,
        "score_delta_mean": sum(deltas) / pairs,
        "score_improvements": sum(delta > 1e-9 for delta in deltas),
        "score_regressions": sum(delta < -1e-9 for delta in deltas),
        "score_ties": sum(abs(delta) <= 1e-9 for delta in deltas),
        "levels_delta_total": sum(
            int(row["candidate_levels"]) - int(row["previous_levels"]) for row in rows
        ),
        "wins_delta_total": sum(
            int(row["candidate_wins"]) - int(row["previous_wins"]) for row in rows
        ),
        "noops_delta_total": sum(
            int(row["candidate_noops"]) - int(row["previous_noops"]) for row in rows
        ),
        "previous_actions_total": sum(int(row["previous_actions"]) for row in rows),
        "candidate_actions_total": sum(int(row["candidate_actions"]) for row in rows),
        "start_matches": sum(int(row["start_matches"]) for row in rows),
        "action_trace_changed_pairs": sum(int(row["action_trace_changed"]) for row in rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--train-games", type=int, default=5)
    parser.add_argument("--train-actions", type=int, default=40)
    parser.add_argument("--dev-games", type=int, default=5)
    parser.add_argument("--eval-actions", type=int, default=80)
    parser.add_argument("--split-seed", type=int, default=20261027)
    parser.add_argument("--seeds", type=int, nargs="+", default=[7, 31, 73])
    parser.add_argument(
        "--online-only",
        action="store_true",
        help="skip the train split and learn a fresh value model inside each dev episode",
    )
    args = parser.parse_args()
    if min(args.train_games, args.train_actions, args.dev_games, args.eval_actions) <= 0:
        raise ValueError("game and action limits must be positive")

    started = time.perf_counter()
    all_games = _load_games(ROOT / "入力/Kaggle/environment_files")
    if len(all_games) != 25 or args.train_games + args.dev_games >= len(all_games):
        raise RuntimeError("expected 25 games and nonempty train/dev/holdout splits")
    shuffled = list(all_games)
    random.Random(args.split_seed).shuffle(shuffled)
    train_games = shuffled[: args.train_games]
    dev_games = shuffled[args.train_games : args.train_games + args.dev_games]
    model = _ProbabilisticValueMemory()
    training_level_events = 0
    training_noops = 0
    active_train_games = [] if args.online_only else train_games
    for index, (metadata, metadata_path) in enumerate(active_train_games, start=1):
        training_policy = _policy_type(model, use_prior=False)
        run = _run_game(
            metadata,
            metadata_path,
            "exploration",
            seed=args.split_seed + index,
            policy_seed=args.split_seed + index,
            max_actions=args.train_actions,
            visible_change_coefficient=0.0,
            policy_type_override=training_policy,
        )
        training_level_events += int(run["levels_completed"])
        training_noops += int(run["no_op_actions"])
        print(f"PROGRESS train={index}/{len(active_train_games)}", flush=True)
    trained_digest = model.digest()
    trained_snapshot = model.snapshot()

    pair_rows: list[dict[str, float | int]] = []
    online_update_total = 0
    post_episode_digests: list[str] = []
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
            episode_model = _ProbabilisticValueMemory.from_snapshot(trained_snapshot)
            candidate_policy = _policy_type(episode_model, use_prior=True)
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
            start_matches = int(
                baseline_run["initial_state"] == candidate_run["initial_state"]
                and baseline_run["initial_levels_completed"]
                == candidate_run["initial_levels_completed"]
                and baseline_run["initial_available_actions"]
                == candidate_run["initial_available_actions"]
                and baseline_run["initial_board"] == candidate_run["initial_board"]
            )
            if not start_matches:
                raise RuntimeError("paired baseline and candidate initial conditions differ")
            illegal_actions += int(baseline_run["illegal_action_attempts"])
            illegal_actions += int(candidate_run["illegal_action_attempts"])
            duplicate_observations += int(baseline_run["duplicate_observation_steps"])
            duplicate_observations += int(candidate_run["duplicate_observation_steps"])
            previous_score, previous_levels, previous_wins, previous_noops, previous_actions = (
                _score(metadata, baseline_run)
            )
            (
                candidate_score,
                candidate_levels,
                candidate_wins,
                candidate_noops,
                candidate_actions,
            ) = _score(metadata, candidate_run)
            previous_trace = [
                [row["action_id"], row["data"]] for row in baseline_run["action_responses"]
            ]
            candidate_trace = [
                [row["action_id"], row["data"]] for row in candidate_run["action_responses"]
            ]
            pair_rows.append(
                {
                    "seed": seed,
                    "previous_score": previous_score,
                    "candidate_score": candidate_score,
                    "previous_levels": previous_levels,
                    "candidate_levels": candidate_levels,
                    "previous_wins": previous_wins,
                    "candidate_wins": candidate_wins,
                    "previous_noops": previous_noops,
                    "candidate_noops": candidate_noops,
                    "previous_actions": previous_actions,
                    "candidate_actions": candidate_actions,
                    "start_matches": start_matches,
                    "action_trace_changed": int(previous_trace != candidate_trace),
                }
            )
            online_update_total += episode_model.snapshot()["updates"] - trained_snapshot["updates"]
            post_episode_digests.append(episode_model.digest())
            print(f"PROGRESS dev seed={seed} episodes={index}/{len(dev_games)}", flush=True)

    aggregate = _aggregate(pair_rows)
    aggregate["by_seed"] = [
        {"seed": seed, **_aggregate([row for row in pair_rows if row["seed"] == seed])}
        for seed in args.seeds
    ]
    memory_serialized = json.dumps(
        trained_snapshot, ensure_ascii=True, sort_keys=True, separators=(",", ":")
    )
    if "game_id" in memory_serialized or "level_id" in memory_serialized:
        raise RuntimeError("identifier found in learned value memory")
    runner_sha = hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    output = {
        "schema": "arc3-probabilistic-multistep-value-transfer.v1",
        "stage": "dev",
        "learning_mode": "online_only" if args.online_only else "pretrained_plus_online",
        "split_seed": args.split_seed,
        "train_games": len(active_train_games),
        "train_actions_per_game": args.train_actions,
        "dev_games": args.dev_games,
        "evaluation_seeds": args.seeds,
        "evaluation_actions_per_game": args.eval_actions,
        "features": ["legal_action_set", "color_count_band", "majority_occupancy_band"],
        "value_model": {
            "kind": "empirical categorical transitions with Dirichlet backoff and finite Bellman iteration",
            "gamma": _GAMMA,
            "iterations": _VALUE_ITERATIONS,
            "prior_weight": _VALUE_WEIGHT,
            "trained_updates": trained_snapshot["updates"],
            "trained_state_action_pairs": trained_snapshot["state_action_pairs"],
            "training_level_events": training_level_events,
            "training_noops": training_noops,
            "trained_memory_sha256": trained_digest,
            "memory_contains_game_or_level_ids": False,
            "holdout_online_updates": online_update_total,
            "holdout_episode_memory_hashes_sha256": hashlib.sha256(
                "".join(sorted(post_episode_digests)).encode("ascii")
            ).hexdigest(),
        },
        "comparison": aggregate,
        "errors": 0,
        "illegal_actions": illegal_actions,
        "duplicate_observations": duplicate_observations,
        "training_and_dev_game_ids_persisted": False,
        "official_submission_made": False,
        "notebook_or_kernel_changed": False,
        "environment_manifest_sha256": _input_manifest_hash(),
        "policy_source_sha256": hashlib.sha256(
            (ROOT / "接続/観測駆動探索Action.py").read_bytes()
        ).hexdigest(),
        "runner_source_sha256": runner_sha,
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
