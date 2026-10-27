"""Paired RHAE tuning for the generic reward on a newly observed board."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import time

from ARC3公開RHAE評価 import _スコアを計算する
import ARC3探索Actionローカル評価 as evaluator

ROOT = Path(__file__).resolve().parents[1]
_BASE_POLICY = evaluator.観測駆動探索方針


class _NoveltyRewardPolicy(_BASE_POLICY):
    board_bonus = 0.5

    def 応答を記録する(self, before, action, after):
        result = super().応答を記録する(before, action, after)
        if result["盤面新規性"]:
            bonus_delta = self.board_bonus - 0.5
            if bonus_delta:
                self._報酬合計[action.作用番号] += bonus_delta
                if action.作用番号 == 6:
                    color = result["座標可視色"]
                    if color is None:
                        raise RuntimeError("ACTION6 new-board response lacks observed color")
                    self._色報酬合計[color] += bonus_delta
                result["公開応答報酬"] += bonus_delta
        return result


def _run(games, seeds, bonus):
    _NoveltyRewardPolicy.board_bonus = bonus
    rows = []
    for seed in seeds:
        for index, (metadata, path) in enumerate(games):
            run = evaluator._run_game(
                metadata,
                path,
                "exploration",
                seed=seed,
                policy_seed=seed,
                max_actions=80,
                retry_game_over=True,
                exploration_coefficient=0.8,
                visible_change_coefficient=0.25,
                level_progress_reward=4.0,
            )
            baseline = metadata.get("baseline_actions")
            if (
                not isinstance(baseline, list)
                or not baseline
                or not all(type(value) is int and value > 0 for value in baseline)
            ):
                raise RuntimeError("invalid public baseline_actions metadata")
            score, levels, _ = _スコアを計算する(baseline, run)
            if levels != run["levels_completed"]:
                raise RuntimeError("scorecard level boundaries disagree with environment result")
            rows.append(
                {
                    "seed": seed,
                    "game_index": index,
                    "score": round(score, 9),
                    "levels": levels,
                    "no_ops": run["no_op_actions"],
                    "game_over": run["game_over_events"],
                    "resets": run["reset_actions"],
                    "wins": int(run["final_state"] == "WIN"),
                }
            )
    return rows


def _summary(rows, seeds, games_per_seed):
    summaries = []
    for seed in seeds:
        selected = [row for row in rows if row["seed"] == seed]
        if len(selected) != games_per_seed:
            raise RuntimeError("run count mismatch")
        summaries.append(
            {
                "seed": seed,
                "games": len(selected),
                "rhae_score_mean": round(sum(row["score"] for row in selected) / len(selected), 9),
                "levels": sum(row["levels"] for row in selected),
                "no_ops": sum(row["no_ops"] for row in selected),
                "game_over": sum(row["game_over"] for row in selected),
                "resets": sum(row["resets"] for row in selected),
                "wins": sum(row["wins"] for row in selected),
            }
        )
    return summaries


def _paired(candidate, baseline):
    lookup = {(row["seed"], row["game_index"]): row for row in baseline}
    deltas = []
    for row in candidate:
        control = lookup[(row["seed"], row["game_index"])]
        deltas.append(
            {
                "score_delta": round(row["score"] - control["score"], 9),
                "levels_delta": row["levels"] - control["levels"],
                "no_ops_delta": row["no_ops"] - control["no_ops"],
                "game_over_delta": row["game_over"] - control["game_over"],
            }
        )
    return {
        "pairs": len(deltas),
        "score_improvements": sum(row["score_delta"] > 0 for row in deltas),
        "score_regressions": sum(row["score_delta"] < 0 for row in deltas),
        "score_ties": sum(row["score_delta"] == 0 for row in deltas),
        "score_delta_mean": round(sum(row["score_delta"] for row in deltas) / len(deltas), 9),
        "levels_delta_total": sum(row["levels_delta"] for row in deltas),
        "no_ops_delta_total": sum(row["no_ops_delta"] for row in deltas),
        "game_over_delta_total": sum(row["game_over_delta"] for row in deltas),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("dev", "holdout"), default="dev")
    parser.add_argument("--seeds", type=int, nargs="+", default=[7, 31, 73])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    games = evaluator._load_games(ROOT / "入力/Kaggle/environment_files")
    if len(games) != 25:
        parser.error("expected the 25 public ARC3 environments")
    split = list(games)
    random.Random(20261022).shuffle(split)
    selected = split[:5] if args.stage == "dev" else split[5:25]
    evaluator.観測駆動探索方針 = _NoveltyRewardPolicy

    started = time.perf_counter()
    parameters = {"baseline": 0.5, "novelty_0": 0.0, "novelty_1": 1.0}
    conditions = {}
    for name, bonus in parameters.items():
        rows = _run(selected, args.seeds, bonus)
        conditions[name] = {
            "new_board_bonus": bonus,
            "runs": _summary(rows, args.seeds, len(selected)),
            "per_game_aggregates": rows,
        }
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing evidence: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    result = {
        "schema": "arc3-new-board-bonus-paired-rhae.v1",
        "evaluation": "public offline paired; official ARC scorecard; identical environment/action seeds",
        "stage": args.stage,
        "split_seed": 20261022,
        "games": len(selected),
        "seeds": args.seeds,
        "max_actions_per_game": 80,
        "conditions": conditions,
        "paired_delta_vs_baseline": {
            name: _paired(
                value["per_game_aggregates"], conditions["baseline"]["per_game_aggregates"]
            )
            for name, value in conditions.items()
            if name != "baseline"
        },
        "elapsed_seconds": round(time.perf_counter() - started, 6),
    }
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
