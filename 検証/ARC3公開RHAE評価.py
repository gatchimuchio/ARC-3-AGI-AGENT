"""公開OFFLINE環境で公式ARC3 RHAEを匿名集計する。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
import sys
from typing import Any

from arc_agi.scorecard import EnvironmentScoreCalculator

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "検証"))
from ARC3探索Actionローカル評価 import _load_games, _run_game


def _スコアを計算する(
    基準行動数: list[int], 実行結果: dict[str, Any]
) -> tuple[float, int, list[dict[str, int | float | bool]]]:
    """公式ScorecardCalculatorと同じlevel境界・action countで1環境を採点する。"""
    行動応答 = 実行結果["action_responses"]
    総行動数 = len(行動応答)
    if 総行動数 != 実行結果["actions"]:
        raise ValueError("actions count does not match action_responses")

    完了境界: list[int] = []
    完了レベル数 = int(実行結果["initial_levels_completed"])
    for 行動位置, 応答 in enumerate(行動応答, start=1):
        次完了数 = 完了レベル数 + int(応答["level_delta"])
        if 次完了数 != 完了レベル数:
            完了境界.append(行動位置)
        完了レベル数 = 次完了数

    # ARC scorecard returns a zero score when public baselines are absent or
    # when more level transitions are reported than baseline entries.
    if not 基準行動数 or len(完了境界) > len(基準行動数):
        return 0.0, len(完了境界), []

    calculator = EnvironmentScoreCalculator()
    前完了境界 = 0
    for level_index, baseline in enumerate(基準行動数, start=1):
        boundary_index = level_index - 1
        if boundary_index < len(完了境界):
            完了境界行動数 = 完了境界[boundary_index]
            level_actions = 完了境界行動数 - 前完了境界
            completed = True
            前完了境界 = 完了境界行動数
        else:
            level_actions = 総行動数 - 前完了境界
            completed = False
            前完了境界 = 総行動数
        calculator.add_level(
            level_index=level_index,
            completed=completed,
            actions_taken=level_actions,
            baseline_actions=int(baseline),
        )

    scorecard = calculator.to_score(include_levels=True)
    level_details = [
        {
            "level_index": level_index,
            "completed": level_index <= len(完了境界),
            "actions": int(scorecard.level_actions[level_index - 1]),
            "baseline_actions": int(scorecard.level_baseline_actions[level_index - 1]),
            "level_score": float(scorecard.level_scores[level_index - 1]),
        }
        for level_index in range(1, len(基準行動数) + 1)
    ]
    return float(scorecard.score), len(完了境界), level_details


def _集計する(
    environment_dir: Path,
    *,
    stage: str,
    split_seed: int,
    seeds: list[int],
    max_actions: int,
) -> dict[str, Any]:
    games = _load_games(environment_dir)
    split = list(games)
    random.Random(split_seed).shuffle(split)
    selected = split[:5] if stage == "dev" else split[5:25] if stage == "holdout" else split

    seed_results = []
    all_seed_scores = []
    level_totals: dict[int, dict[str, int | float]] = {}
    for seed in seeds:
        game_scores = []
        metrics = {
            "completed_levels": 0,
            "wins": 0,
            "actions": 0,
            "no_ops": 0,
            "game_over": 0,
            "resets": 0,
            "level_event_count_mismatches": 0,
            "scorecard_contract_errors": 0,
        }
        for metadata, metadata_path in selected:
            run = _run_game(
                metadata,
                metadata_path,
                "exploration",
                seed=seed,
                policy_seed=seed,
                max_actions=max_actions,
                retry_game_over=True,
            )
            baselines = metadata.get("baseline_actions")
            if not isinstance(baselines, list) or not all(
                isinstance(value, int) and value > 0 for value in baselines
            ):
                metrics["scorecard_contract_errors"] += 1
                game_scores.append(0.0)
                continue

            score, level_events, level_details = _スコアを計算する(baselines, run)
            game_scores.append(score)
            metrics["level_event_count_mismatches"] += int(level_events != run["levels_completed"])
            metrics["scorecard_contract_errors"] += int(level_events > len(baselines))
            metrics["completed_levels"] += run["levels_completed"]
            metrics["wins"] += int(run["final_state"] == "WIN")
            metrics["actions"] += run["actions"]
            metrics["no_ops"] += run["no_op_actions"]
            metrics["game_over"] += run["game_over_events"]
            metrics["resets"] += run["reset_actions"]
            for detail in level_details:
                level_total = level_totals.setdefault(
                    int(detail["level_index"]),
                    {
                        "level_slots": 0,
                        "completed": 0,
                        "completed_actions_total": 0,
                        "completed_baseline_actions_total": 0,
                        "completed_level_score_total": 0.0,
                    },
                )
                level_total["level_slots"] += 1
                if detail["completed"]:
                    level_total["completed"] += 1
                    level_total["completed_actions_total"] += int(detail["actions"])
                    level_total["completed_baseline_actions_total"] += int(
                        detail["baseline_actions"]
                    )
                    level_total["completed_level_score_total"] += float(detail["level_score"])

        seed_score = sum(game_scores) / len(game_scores) if game_scores else 0.0
        all_seed_scores.append(seed_score)
        seed_results.append(
            {
                "seed": seed,
                "games": len(game_scores),
                "RHAE_score": round(seed_score, 6),
                **metrics,
            }
        )

    return {
        "evaluation": "public-offline-rhae",
        "stage": stage,
        "split_seed": split_seed,
        "environment_seeds": seeds,
        "policy_seed_rule": "policy seed equals environment seed",
        "max_actions_per_game": max_actions,
        "public_environments": len(selected),
        "public_baseline_metadata_count": sum(
            int(
                isinstance(metadata.get("baseline_actions"), list)
                and bool(metadata["baseline_actions"])
            )
            for metadata, _ in selected
        ),
        "runs": seed_results,
        "level_completion_by_index": [
            {
                "level_index": level_index,
                "level_slots": int(values["level_slots"]),
                "completed": int(values["completed"]),
                "mean_actions_when_completed": round(
                    int(values["completed_actions_total"]) / int(values["completed"]), 2
                )
                if values["completed"]
                else None,
                "mean_baseline_actions_when_completed": round(
                    int(values["completed_baseline_actions_total"]) / int(values["completed"]), 2
                )
                if values["completed"]
                else None,
                "mean_level_score_when_completed": round(
                    float(values["completed_level_score_total"]) / int(values["completed"]), 6
                )
                if values["completed"]
                else None,
            }
            for level_index, values in sorted(level_totals.items())
        ],
        "mean_RHAE_score_across_seeds": round(sum(all_seed_scores) / len(all_seed_scores), 6)
        if all_seed_scores
        else 0.0,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Score public OFFLINE runs with the pinned ARC scorecard calculator"
    )
    parser.add_argument(
        "--environment-dir",
        type=Path,
        default=ROOT / "入力/Kaggle/environment_files",
    )
    parser.add_argument("--stage", choices=("dev", "holdout", "all"), default="holdout")
    parser.add_argument("--split-seed", type=int, default=20261022)
    parser.add_argument("--seeds", type=int, nargs="+", default=[7, 31, 73])
    parser.add_argument("--max-actions", type=int, default=80)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "出力/ARC3-RUN-003-local/C0-001-public-rhae-baseline-v2.json",
    )
    args = parser.parse_args()
    if args.max_actions < 1:
        parser.error("--max-actions must be positive")
    result = _集計する(
        args.environment_dir,
        stage=args.stage,
        split_seed=args.split_seed,
        seeds=args.seeds,
        max_actions=args.max_actions,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.output.exists():
        parser.error(f"refusing to overwrite existing result: {args.output}")
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
