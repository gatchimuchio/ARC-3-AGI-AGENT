"""Paired scorecard comparison of generic online exploration coefficients."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import time

from ARC3公開RHAE評価 import _スコアを計算する
from ARC3探索Actionローカル評価 import _load_games, _run_game

ROOT = Path(__file__).resolve().parents[1]


def _run_condition(games, seeds: list[int], *, action_ucb: float, color_ucb: float | None):
    summaries = []
    rows = []
    for seed in seeds:
        scores = []
        completed_levels = no_ops = wins = game_over = resets = 0
        for game_index, (metadata, path) in enumerate(games):
            run = _run_game(
                metadata,
                path,
                "exploration",
                seed=seed,
                policy_seed=seed,
                max_actions=80,
                retry_game_over=True,
                exploration_coefficient=action_ucb,
                coordinate_color_exploration_coefficient=color_ucb,
                visible_change_coefficient=0.25,
                level_progress_reward=4.0,
            )
            baseline = metadata.get("baseline_actions")
            if not isinstance(baseline, list) or not baseline or not all(
                type(value) is int and value > 0 for value in baseline
            ):
                raise RuntimeError("invalid public baseline_actions metadata")
            score, scored_levels, _ = _スコアを計算する(baseline, run)
            if scored_levels != run["levels_completed"]:
                raise RuntimeError("scorecard level boundaries disagree with environment result")
            scores.append(score)
            completed_levels += run["levels_completed"]
            no_ops += run["no_op_actions"]
            wins += int(run["final_state"] == "WIN")
            game_over += run["game_over_events"]
            resets += run["reset_actions"]
            rows.append(
                {
                    "seed": seed,
                    "game_index": game_index,
                    "score": round(score, 9),
                    "levels": run["levels_completed"],
                    "no_ops": run["no_op_actions"],
                    "game_over": run["game_over_events"],
                    "resets": run["reset_actions"],
                }
            )
        summaries.append({
            "seed": seed,
            "games": len(games),
            "rhae_score_mean": round(sum(scores) / len(scores), 9) if scores else 0.0,
            "completed_levels": completed_levels,
            "no_ops": no_ops,
            "game_over": game_over,
            "resets": resets,
            "wins": wins,
        })
    return summaries, rows


def _run_all(games, seeds, *, action_ucb, color_ucb):
    return _run_condition(
        games, seeds, action_ucb=action_ucb, color_ucb=color_ucb
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("dev", "holdout"), default="dev")
    parser.add_argument("--seeds", type=int, nargs="+", default=[7, 31, 73])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    all_games = _load_games(ROOT / "入力/Kaggle/environment_files")
    if len(all_games) != 25:
        parser.error("expected the 25 public ARC3 environments")
    split = list(all_games)
    random.Random(20261022).shuffle(split)
    selected = split[:5] if args.stage == "dev" else split[5:25]
    started = time.perf_counter()
    conditions = {
        "baseline": {"action_ucb": 0.8, "color_ucb": None},
        "action_ucb_1.2": {"action_ucb": 1.2, "color_ucb": None},
        "coordinate_color_ucb_1.2": {"action_ucb": 0.8, "color_ucb": 1.2},
    }
    condition_results = {}
    for name, parameters in conditions.items():
        summaries, rows = _run_all(selected, args.seeds, **parameters)
        condition_results[name] = {"parameters": parameters, "runs": summaries, "rows": rows}
    pair_results = {}
    baseline_rows = {
        (row["seed"], row["game_index"]): row
        for row in condition_results["baseline"]["rows"]
    }
    for name in conditions:
        if name == "baseline":
            continue
        deltas = []
        for row in condition_results[name]["rows"]:
            baseline = baseline_rows[(row["seed"], row["game_index"])]
            deltas.append(
                {
                    "score_delta": round(row["score"] - baseline["score"], 9),
                    "levels_delta": row["levels"] - baseline["levels"],
                    "no_ops_delta": row["no_ops"] - baseline["no_ops"],
                    "game_over_delta": row["game_over"] - baseline["game_over"],
                }
            )
        pair_results[name] = {
            "pairs": len(deltas),
            "score_improvements": sum(x["score_delta"] > 0 for x in deltas),
            "score_regressions": sum(x["score_delta"] < 0 for x in deltas),
            "score_ties": sum(x["score_delta"] == 0 for x in deltas),
            "score_delta_mean": round(sum(x["score_delta"] for x in deltas) / len(deltas), 9),
            "levels_delta_total": sum(x["levels_delta"] for x in deltas),
            "no_ops_delta_total": sum(x["no_ops_delta"] for x in deltas),
            "game_over_delta_total": sum(x["game_over_delta"] for x in deltas),
        }

    output = args.output if args.output.is_absolute() else ROOT / args.output
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing result: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "schema": "arc3-exploration-coefficient-paired-rhae.v1",
        "evaluation": "public offline paired; ARC scorecard; identical environment/action seeds",
        "stage": args.stage,
        "split_seed": 20261022,
        "games": len(selected),
        "seeds": args.seeds,
        "max_actions_per_game": 80,
        "conditions": condition_results,
        "paired_deltas_vs_baseline": pair_results,
        "elapsed_seconds": round(time.perf_counter() - started, 6),
    }
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
