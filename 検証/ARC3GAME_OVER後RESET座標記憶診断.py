"""SDK RESET後にACTION6の既試行座標cacheが再利用される頻度を診断する。"""

from __future__ import annotations

import argparse
from collections import defaultdict
import json
import logging
from pathlib import Path
import random
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from 接続.観測駆動探索Action import 観測駆動探索方針
from 検証.ARC3availableActions文脈診断 import (
    _BASELINE_DIR,
    _METRIC_FIELDS,
    _load_baseline,
    _load_runner,
    _sha256,
)


def _summarize(samples: list[dict[str, Any]]) -> dict[str, Any]:
    by_seed: dict[int, list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        by_seed[sample["seed"]].append(sample)

    cache_hits = [sample for sample in samples if sample["cache_hit"]]
    fractions = sorted(sample["cached_fraction"] for sample in cache_hits)
    median = None
    if fractions:
        middle = len(fractions) // 2
        median = (
            fractions[middle]
            if len(fractions) % 2
            else (fractions[middle - 1] + fractions[middle]) / 2
        )

    per_seed = []
    for seed in (7, 31, 73):
        seed_samples = by_seed[seed]
        seed_hits = [sample for sample in seed_samples if sample["cache_hit"]]
        row: dict[str, Any] = {
            "seed": seed,
            "reset_revisits": len(seed_samples),
            "cache_hit_events": (len(seed_hits) if len(seed_hits) >= 10 else "suppressed (<10)"),
        }
        if len(seed_hits) >= 10:
            seed_fractions = sorted(sample["cached_fraction"] for sample in seed_hits)
            middle = len(seed_fractions) // 2
            row["median_cached_coordinate_fraction"] = (
                seed_fractions[middle]
                if len(seed_fractions) % 2
                else (seed_fractions[middle - 1] + seed_fractions[middle]) / 2
            )
        else:
            row["cache_fraction_summary_suppressed"] = True
        per_seed.append(row)

    represented_seeds = sum(
        bool([s for s in by_seed[seed] if s["cache_hit"]]) for seed in (7, 31, 73)
    )
    return {
        "reset_revisits": len(samples),
        "same_board_with_prior_coordinate_cache": len(cache_hits),
        "cache_hit_seed_count": represented_seeds,
        "median_cached_coordinate_fraction_on_hits": (
            round(median, 6) if median is not None else None
        ),
        "per_seed_suppression_threshold": "cache hit summaries below 10 events are suppressed",
        "per_seed_summary": per_seed,
        "ablation_preconditions": {
            "at_least_10_cache_hits_across_two_seeds": (
                len(cache_hits) >= 10 and represented_seeds >= 2
            ),
            "median_cached_fraction_at_least_20_percent": (median is not None and median >= 0.2),
        },
    }


def _run(args: argparse.Namespace) -> dict[str, Any]:
    runner = _load_runner()
    games = runner._load_games(args.environment_dir)
    split = list(games)
    random.Random(args.split_seed).shuffle(split)
    selected = split[:5]
    seeds = (7, 31, 73)

    baselines = {seed: _load_baseline(seed) for seed in seeds}
    baseline_games = {
        seed: {game["game_id"]: game for game in baseline["games"]}
        for seed, baseline in baselines.items()
    }
    samples: list[dict[str, Any]] = []
    metric_deltas: dict[int, dict[str, dict[str, int]]] = {}
    initial_metadata_matches: dict[int, int] = {}
    active_seed = 0
    active_run = ""
    reset_pending: dict[str, bool] = defaultdict(bool)
    original_choose = 観測駆動探索方針.選ぶ

    def choose(self, current):
        nonlocal active_run
        if current.状態 == "GAME_OVER":
            action = original_choose(self, current)
            if action is not None and action.作用番号 == 0:
                reset_pending[active_run] = True
            return action

        if current.状態 == "NOT_FINISHED" and reset_pending[active_run]:
            board = current.最新盤面
            tried = self._座標試行.get(board, set())
            cells = sum(len(row) for row in board)
            cached_fraction = len(tried) / cells if cells else 0.0
            samples.append(
                {
                    "seed": active_seed,
                    "cache_hit": bool(tried),
                    "cached_fraction": cached_fraction,
                }
            )
            reset_pending[active_run] = False
        return original_choose(self, current)

    try:
        観測駆動探索方針.選ぶ = choose
        for seed in seeds:
            totals = {key: 0 for key in (*_METRIC_FIELDS, "wins", "policy_holds")}
            metadata_matches = 0
            for run_index, (metadata, metadata_path) in enumerate(selected):
                active_seed = seed
                active_run = f"{seed}:{run_index}"
                result = runner._run_game(
                    metadata,
                    metadata_path,
                    "exploration",
                    seed=seed,
                    max_actions=80,
                    retry_game_over=True,
                )
                baseline_record = baseline_games[seed].get(metadata["game_id"])
                if baseline_record is None:
                    raise RuntimeError("C2-003 dev基準とsplitの対象が一致しません")
                baseline_game = baseline_record["exploration"]
                if (
                    result["initial_state"] == baseline_game["initial_state"]
                    and result["initial_available_actions"]
                    == baseline_game["initial_available_actions"]
                    and result["initial_levels_completed"]
                    == baseline_game["initial_levels_completed"]
                ):
                    metadata_matches += 1
                for key in _METRIC_FIELDS:
                    totals[key] += int(result[key])
                totals["wins"] += int(result["final_state"] == "WIN")
                totals["policy_holds"] += int(result["stop_reason"] == "exploration_hold")

            previous = baselines[seed]["aggregate"]["exploration"]
            deltas = {
                key: {
                    "previous": int(previous[key]),
                    "current": value,
                    "delta": value - int(previous[key]),
                }
                for key, value in totals.items()
            }
            if any(row["delta"] != 0 for row in deltas.values()):
                raise RuntimeError(f"seed {seed}のprevious/current基準集計が不一致です")
            if metadata_matches != 5:
                raise RuntimeError(f"seed {seed}の初期metadata照合が不足しています")
            metric_deltas[seed] = deltas
            initial_metadata_matches[seed] = metadata_matches
    finally:
        観測駆動探索方針.選ぶ = original_choose

    reset_cache_summary = _summarize(samples)
    reset_cache_summary["ablation_preconditions"]["previous_metrics_and_initial_metadata_match"] = (
        all(initial_metadata_matches[seed] == 5 for seed in seeds)
        and all(row["delta"] == 0 for seed in seeds for row in metric_deltas[seed].values())
    )
    reset_cache_summary["ablation_preconditions"]["eligible_for_dev_ablation"] = all(
        reset_cache_summary["ablation_preconditions"].values()
    )

    return {
        "instruction_id": "ARC3-RUN-002-C3-003",
        "evaluation": "public development split only; no runtime changes",
        "split_seed": args.split_seed,
        "action_seeds": list(seeds),
        "max_actions_per_game": 80,
        "retry_game_over": True,
        "runs": 15,
        "reset_cache_summary": reset_cache_summary,
        "initial_metadata_matches": initial_metadata_matches,
        "baseline_metric_deltas": metric_deltas,
        "source_sha256": {
            "diagnostic_runner": _sha256(Path(__file__)),
            "evaluation_runner": _sha256(Path(runner.__file__)),
            "policy": _sha256(ROOT / "接続/観測駆動探索Action.py"),
            "baseline_seed_7": _sha256(_BASELINE_DIR / "C2-003-after-dev-seed-7.json"),
            "baseline_seed_31": _sha256(_BASELINE_DIR / "C2-003-after-dev-seed-31.json"),
            "baseline_seed_73": _sha256(_BASELINE_DIR / "C2-003-after-dev-seed-73.json"),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--environment-dir",
        type=Path,
        default=ROOT / "入力/Kaggle/environment_files",
    )
    parser.add_argument("--split-seed", type=int, default=20261022)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "出力/ARC3-RUN-002-local/C3-003-reset-coordinate-cache.json",
    )
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"出力先が既に存在します。別の--outputを指定してください: {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(level=logging.WARNING)
    result = _run(args)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(
        json.dumps(
            {"output": str(args.output), "reset_cache_summary": result["reset_cache_summary"]},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
