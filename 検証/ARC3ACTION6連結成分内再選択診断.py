"""ACTION6の4近傍・同色成分内で座標が再選択される頻度を診断する。"""

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


def _component_cells(
    board: tuple[tuple[int, ...], ...], x: int, y: int
) -> frozenset[tuple[int, int]]:
    if not board or not 0 <= y < len(board) or not 0 <= x < len(board[y]):
        raise ValueError("component start is outside the board")
    color = board[y][x]
    pending = [(x, y)]
    cells: set[tuple[int, int]] = set()
    while pending:
        current_x, current_y = pending.pop()
        point = (current_x, current_y)
        if point in cells:
            continue
        if not (0 <= current_y < len(board)):
            continue
        if not (0 <= current_x < len(board[current_y])):
            continue
        if board[current_y][current_x] != color:
            continue
        cells.add(point)
        pending.extend(
            (
                (current_x - 1, current_y),
                (current_x + 1, current_y),
                (current_x, current_y - 1),
                (current_x, current_y + 1),
            )
        )
    return frozenset(cells)


def _size_bucket(size: int) -> str:
    if size == 1:
        return "1"
    if size == 2:
        return "2"
    if size <= 4:
        return "3_4"
    if size <= 8:
        return "5_8"
    return "9_plus"


def _outcome_summary(samples: list[dict[str, Any]]) -> dict[str, Any]:
    count = len(samples)
    no_ops = sum(int(sample["no_op"]) for sample in samples)
    game_over = sum(int(sample["game_over"]) for sample in samples)
    level_progress = sum(int(sample["level_progress"]) for sample in samples)
    return {
        "actions": count,
        "no_op": no_ops,
        "no_op_rate": round(no_ops / count, 6) if count else None,
        "game_over": game_over,
        "level_progress": level_progress,
    }


def _summarize(
    samples: list[dict[str, Any]],
    *,
    no_hold_illegal_duplicate_regression: bool = False,
) -> dict[str, Any]:
    overall = {
        repeated: _outcome_summary(
            [sample for sample in samples if sample["repeated_component"] is repeated]
        )
        for repeated in (False, True)
    }
    by_seed: dict[tuple[int, bool], list[dict[str, Any]]] = defaultdict(list)
    by_size: dict[tuple[str, bool], list[dict[str, Any]]] = defaultdict(list)
    for sample in samples:
        by_seed[(sample["seed"], sample["repeated_component"])].append(sample)
        by_size[(sample["size_bucket"], sample["repeated_component"])].append(sample)

    seed_rows = []
    per_seed_summary = []
    seed_deltas = []
    for seed in (7, 31, 73):
        first = by_seed[(seed, False)]
        repeated = by_seed[(seed, True)]
        first_summary = _outcome_summary(first)
        repeated_summary = _outcome_summary(repeated)
        per_seed_summary.append(
            {
                "seed": seed,
                "first_selection": first_summary,
                "component_reselection": (
                    repeated_summary
                    if len(repeated) >= 10
                    else {"actions": "suppressed (<10)", "outcomes_suppressed": True}
                ),
            }
        )
        if len(first) < 5 or len(repeated) < 5:
            continue
        delta = (repeated_summary["no_op_rate"] - first_summary["no_op_rate"]) * 100
        seed_deltas.append(delta)
        seed_rows.append(
            {
                "seed": seed,
                "first_selection": first_summary,
                "component_reselection": repeated_summary,
                "no_op_delta_percentage_points": round(delta, 2),
            }
        )

    compared = len(seed_deltas)
    positive = sum(delta > 0 for delta in seed_deltas)
    negative = sum(delta < 0 for delta in seed_deltas)
    direction_consistency = max(positive, negative) / compared if compared else 0.0
    repeat_seed_count = sum(bool(by_seed[(seed, True)]) for seed in (7, 31, 73))
    no_op_delta = None
    if overall[True]["actions"] and overall[False]["actions"]:
        no_op_delta = round(
            (overall[True]["no_op_rate"] - overall[False]["no_op_rate"]) * 100,
            2,
        )

    size_rows = []
    for (bucket, repeated), grouped in sorted(by_size.items()):
        represented_seeds = {sample["seed"] for sample in grouped}
        if len(grouped) < 10 or len(represented_seeds) < 2:
            continue
        size_rows.append(
            {
                "component_size": bucket,
                "selection": "reselection" if repeated else "first",
                **_outcome_summary(grouped),
                "seed_count": len(represented_seeds),
            }
        )

    first_progress_rate = (
        overall[False]["level_progress"] / overall[False]["actions"]
        if overall[False]["actions"]
        else 0.0
    )
    repeat_progress_rate = (
        overall[True]["level_progress"] / overall[True]["actions"]
        if overall[True]["actions"]
        else 0.0
    )
    preconditions = {
        "repeat_count_at_least_20_and_two_seeds": (
            overall[True]["actions"] >= 20 and repeat_seed_count >= 2
        ),
        "no_op_delta_at_least_10pp": no_op_delta is not None and no_op_delta >= 10,
        "no_op_direction_consistent_in_two_thirds": (
            compared >= 2 and direction_consistency >= (2 / 3)
        ),
        "reselection_level_progress_rate_not_above_first": (
            overall[True]["level_progress"] == 0 or repeat_progress_rate <= first_progress_rate
        ),
        "no_hold_illegal_duplicate": no_hold_illegal_duplicate_regression,
    }
    preconditions["eligible_for_dev_ablation"] = all(preconditions.values())
    return {
        "action6_count": len(samples),
        "first_selection": overall[False],
        "component_reselection": overall[True],
        "no_op_delta_percentage_points": no_op_delta,
        "comparable_seed_count": compared,
        "consistent_direction_fraction": round(direction_consistency, 6),
        "per_seed_suppression_threshold": "component reselection outcomes below 10 are suppressed",
        "per_seed_summary": per_seed_summary,
        "per_seed": seed_rows,
        "component_size_buckets_suppressed_below_10_across_two_seeds": size_rows,
        "preconditions": preconditions,
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
    seen_components_by_run: dict[str, set[tuple[Any, ...]]] = defaultdict(set)
    original_record = 観測駆動探索方針.応答を記録する

    def record_response(self, before, action, after):
        receipt = original_record(self, before, action, after)
        if action.作用番号 == 6:
            x, y = action.引数["x"], action.引数["y"]
            cells = _component_cells(before.最新盤面, x, y)
            component_key = (
                before.完了レベル数,
                before.最新盤面,
                cells,
            )
            seen = seen_components_by_run[active_run]
            repeated_component = component_key in seen
            seen.add(component_key)
            samples.append(
                {
                    "seed": active_seed,
                    "run": active_run,
                    "repeated_component": repeated_component,
                    "size_bucket": _size_bucket(len(cells)),
                    "no_op": receipt["可視変化セル数"] == 0 and receipt["完了レベル増分"] == 0,
                    "game_over": after.状態 == "GAME_OVER",
                    "level_progress": receipt["完了レベル増分"] > 0,
                }
            )
        return receipt

    try:
        観測駆動探索方針.応答を記録する = record_response
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
        観測駆動探索方針.応答を記録する = original_record

    return {
        "instruction_id": "ARC3-RUN-002-C2-021",
        "evaluation": "public development split only; no runtime changes",
        "split_seed": args.split_seed,
        "action_seeds": list(seeds),
        "max_actions_per_game": 80,
        "retry_game_over": True,
        "runs": 15,
        "initial_metadata_matches": initial_metadata_matches,
        "baseline_metric_deltas": metric_deltas,
        "component_summary": _summarize(
            samples,
            no_hold_illegal_duplicate_regression=all(
                metric_deltas[seed][key]["delta"] <= 0
                for seed in seeds
                for key in (
                    "policy_holds",
                    "illegal_action_attempts",
                    "duplicate_observation_steps",
                )
            ),
        ),
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
        default=ROOT / "出力/ARC3-RUN-002-local/C2-021-action6-component-repeat.json",
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
            {"output": str(args.output), "component_summary": result["component_summary"]},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
