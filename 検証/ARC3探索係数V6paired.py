"""Paired public scorecard for the current ARC3 exploration UCB coefficient."""

from __future__ import annotations

import argparse
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

_SPLIT_SEED = 20261027
_BASELINE_UCB = 0.8
_VISIBLE_CHANGE_COEFFICIENT = 0.0
_LEVEL_PROGRESS_REWARD = 4.0
_MAX_ACTIONS = 80


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest_sha256() -> str:
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


def _score(metadata: dict[str, Any], run: dict[str, Any]) -> tuple[float, int, int]:
    score, levels, _ = _スコアを計算する(metadata["baseline_actions"], run)
    if levels != int(run["levels_completed"]) - int(run["initial_levels_completed"]):
        raise RuntimeError("scorecard levels disagree with local environment")
    return score, levels, int(run["final_state"] == "WIN")


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    deltas = [float(row["candidate_score"]) - float(row["baseline_score"]) for row in rows]
    return {
        "pairs": len(rows),
        "baseline_rhae_mean": sum(float(row["baseline_score"]) for row in rows) / len(rows),
        "candidate_rhae_mean": sum(float(row["candidate_score"]) for row in rows) / len(rows),
        "score_delta_mean": sum(deltas) / len(deltas),
        "score_improvements": sum(delta > 1e-9 for delta in deltas),
        "score_regressions": sum(delta < -1e-9 for delta in deltas),
        "score_ties": sum(abs(delta) <= 1e-9 for delta in deltas),
        "levels_delta_total": sum(
            int(row["candidate_levels"]) - int(row["baseline_levels"]) for row in rows
        ),
        "wins_delta_total": sum(
            int(row["candidate_wins"]) - int(row["baseline_wins"]) for row in rows
        ),
        "noops_delta_total": sum(
            int(row["candidate_noops"]) - int(row["baseline_noops"]) for row in rows
        ),
        "reset_delta_total": sum(
            int(row["candidate_resets"]) - int(row["baseline_resets"]) for row in rows
        ),
        "game_over_delta_total": sum(
            int(row["candidate_game_over"]) - int(row["baseline_game_over"]) for row in rows
        ),
        "same_starts": sum(int(row["same_start"]) for row in rows),
        "trace_changed_pairs": sum(int(row["trace_changed"]) for row in rows),
        "errors": sum(int(row["errors"]) for row in rows),
        "illegal_actions": sum(int(row["illegal_actions"]) for row in rows),
        "duplicate_observations": sum(int(row["duplicate_observations"]) for row in rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("dev", "seed_holdout"), default="dev")
    parser.add_argument("--seeds", type=int, nargs="+", required=True)
    parser.add_argument("--candidate-ucb", type=float)
    parser.add_argument("--candidate-action-ucb", type=float)
    parser.add_argument("--candidate-color-ucb", type=float)
    parser.add_argument("--candidate-visible-change", type=float)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    has_visible_change_candidate = args.candidate_visible_change is not None
    has_ucb_candidate = any(
        value is not None
        for value in (args.candidate_ucb, args.candidate_action_ucb, args.candidate_color_ucb)
    )
    if has_visible_change_candidate == has_ucb_candidate:
        parser.error("provide either a candidate-visible-change or UCB candidate")
    if has_visible_change_candidate:
        candidate_action_ucb = candidate_color_ucb = _BASELINE_UCB
        candidate_visible_change = args.candidate_visible_change
    else:
        if args.candidate_ucb is not None:
            if args.candidate_action_ucb is not None or args.candidate_color_ucb is not None:
                parser.error("candidate-ucb cannot be combined with separate coefficient options")
            candidate_action_ucb = candidate_color_ucb = args.candidate_ucb
        elif args.candidate_action_ucb is not None and args.candidate_color_ucb is not None:
            candidate_action_ucb = args.candidate_action_ucb
            candidate_color_ucb = args.candidate_color_ucb
        else:
            parser.error("provide candidate-ucb or both separate candidate coefficients")
        candidate_visible_change = _VISIBLE_CHANGE_COEFFICIENT
    if any(
        not math.isfinite(coefficient) or coefficient < 0
        for coefficient in (candidate_action_ucb, candidate_color_ucb)
    ):
        parser.error("candidate UCB coefficients must be finite and nonnegative")
    if not math.isfinite(candidate_visible_change) or candidate_visible_change < 0:
        parser.error("candidate visible-change coefficient must be finite and nonnegative")
    if not args.seeds or len(set(args.seeds)) != len(args.seeds):
        parser.error("seeds must be nonempty and unique")
    if args.output.exists():
        parser.error(f"refusing to overwrite existing result: {args.output}")

    all_games = _load_games(ROOT / "入力/Kaggle/environment_files")
    if len(all_games) != 25:
        raise RuntimeError("expected the 25 public ARC3 environments")
    shuffled = list(all_games)
    random.Random(_SPLIT_SEED).shuffle(shuffled)
    selected_games = shuffled[:5] if args.stage == "dev" else shuffled[5:]
    started = time.perf_counter()
    rows: list[dict[str, Any]] = []

    for seed in args.seeds:
        for game_index, (metadata, metadata_path) in enumerate(selected_games, start=1):
            runs: dict[str, dict[str, Any]] = {}
            scores: dict[str, tuple[float, int, int]] = {}
            for label, action_coefficient, color_coefficient, visible_coefficient in (
                (
                    "baseline",
                    _BASELINE_UCB,
                    _BASELINE_UCB,
                    _VISIBLE_CHANGE_COEFFICIENT,
                ),
                (
                    "candidate",
                    candidate_action_ucb,
                    candidate_color_ucb,
                    candidate_visible_change,
                ),
            ):
                run = _run_game(
                    metadata,
                    metadata_path,
                    "exploration",
                    seed=seed,
                    policy_seed=seed,
                    max_actions=_MAX_ACTIONS,
                    retry_game_over=True,
                    exploration_coefficient=action_coefficient,
                    coordinate_color_exploration_coefficient=color_coefficient,
                    visible_change_coefficient=visible_coefficient,
                    level_progress_reward=_LEVEL_PROGRESS_REWARD,
                )
                runs[label] = run
                scores[label] = _score(metadata, run)

            baseline = runs["baseline"]
            candidate = runs["candidate"]
            same_start = int(
                all(
                    baseline[key] == candidate[key]
                    for key in (
                        "initial_state",
                        "initial_levels_completed",
                        "initial_available_actions",
                        "initial_board",
                    )
                )
            )
            if not same_start:
                raise RuntimeError("paired runs did not share the initial public observation")
            baseline_trace = [
                (row["action_id"], row["data"]) for row in baseline["action_responses"]
            ]
            candidate_trace = [
                (row["action_id"], row["data"]) for row in candidate["action_responses"]
            ]
            rows.append(
                {
                    "seed": seed,
                    "game_index": game_index,
                    "baseline_score": scores["baseline"][0],
                    "candidate_score": scores["candidate"][0],
                    "baseline_levels": scores["baseline"][1],
                    "candidate_levels": scores["candidate"][1],
                    "baseline_wins": scores["baseline"][2],
                    "candidate_wins": scores["candidate"][2],
                    "baseline_noops": int(baseline["no_op_actions"]),
                    "candidate_noops": int(candidate["no_op_actions"]),
                    "baseline_resets": int(baseline["reset_actions"]),
                    "candidate_resets": int(candidate["reset_actions"]),
                    "baseline_game_over": int(baseline["game_over_events"]),
                    "candidate_game_over": int(candidate["game_over_events"]),
                    "same_start": same_start,
                    "trace_changed": int(baseline_trace != candidate_trace),
                    "errors": 0,
                    "illegal_actions": int(baseline["illegal_action_attempts"])
                    + int(candidate["illegal_action_attempts"]),
                    "duplicate_observations": int(baseline["duplicate_observation_steps"])
                    + int(candidate["duplicate_observation_steps"]),
                }
            )
            print(
                f"PROGRESS {args.stage} seed={seed} episode={game_index}/{len(selected_games)}",
                flush=True,
            )

    comparison = _summarize(rows)
    grouped = [
        {"seed": seed, **_summarize([row for row in rows if row["seed"] == seed])}
        for seed in args.seeds
    ]
    if args.stage == "dev":
        passes_gate = bool(
            comparison["score_delta_mean"] >= 0.01
            and comparison["score_improvements"] >= comparison["score_regressions"]
            and comparison["levels_delta_total"] >= 0
            and comparison["same_starts"] == len(rows)
            and comparison["errors"] == 0
            and comparison["illegal_actions"] == 0
            and comparison["duplicate_observations"] == 0
        )
        gate = {
            "minimum_mean_rhae_delta": 0.01,
            "minimum_improvements_at_least_regressions": True,
            "minimum_levels_delta": 0,
        }
    else:
        passes_gate = bool(
            comparison["score_delta_mean"] > 0
            and comparison["score_improvements"] > comparison["score_regressions"]
            and comparison["levels_delta_total"] >= 0
            and comparison["same_starts"] == len(rows)
            and comparison["errors"] == 0
            and comparison["illegal_actions"] == 0
            and comparison["duplicate_observations"] == 0
        )
        gate = {
            "minimum_mean_rhae_delta_exclusive": 0.0,
            "improvements_must_exceed_regressions": True,
            "minimum_levels_delta": 0,
        }

    result = {
        "schema": "arc3-exploration-ucb-coefficient-paired.v1",
        "stage": args.stage,
        "python_hash_seed": os.environ.get("PYTHONHASHSEED", "randomized"),
        "split_seed": _SPLIT_SEED,
        "games": len(selected_games),
        "seeds": args.seeds,
        "max_actions": _MAX_ACTIONS,
        "retry_game_over": True,
        "visible_change_coefficient": _VISIBLE_CHANGE_COEFFICIENT,
        "level_progress_reward": _LEVEL_PROGRESS_REWARD,
        "baseline_visible_change_coefficient": _VISIBLE_CHANGE_COEFFICIENT,
        "candidate_visible_change_coefficient": candidate_visible_change,
        "baseline_action_ucb": _BASELINE_UCB,
        "baseline_color_ucb": _BASELINE_UCB,
        "candidate_action_ucb": candidate_action_ucb,
        "candidate_color_ucb": candidate_color_ucb,
        "public_rhae_comparison": {**comparison, "by_seed": grouped},
        "validation_gate": gate,
        "candidate_passes_gate": passes_gate,
        "game_ids_persisted": False,
        "per_game_rows_persisted": False,
        "only_public_observations_used": True,
        "official_submission_made": False,
        "competition_api_called": False,
        "notebook_or_kernel_changed": False,
        "environment_manifest_sha256": _manifest_sha256(),
        "policy_source_sha256": _sha(ROOT / "接続/観測駆動探索Action.py"),
        "local_evaluator_sha256": _sha(ROOT / "検証/ARC3探索Actionローカル評価.py"),
        "scorer_sha256": _sha(ROOT / "検証/ARC3公開RHAE評価.py"),
        "runner_source_sha256": _sha(Path(__file__)),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
