"""公開合法Action集合が汎用の方針文脈として反復するかを診断する。"""

from __future__ import annotations

import argparse
from collections import defaultdict
import hashlib
import importlib.util
import json
import logging
from pathlib import Path
import random
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from 接続.観測駆動探索Action import 観測駆動探索方針

_RUNNER_PATH = ROOT / "検証/ARC3探索Actionローカル評価.py"
_BASELINE_DIR = ROOT / "出力/ARC3-RUN-002-local"
_METRIC_FIELDS = (
    "actions",
    "gameplay_actions",
    "reset_actions",
    "game_over_events",
    "levels_completed",
    "no_op_actions",
    "duplicate_observation_steps",
    "illegal_action_attempts",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_runner():
    spec = importlib.util.spec_from_file_location("arc3_context_evaluation_runner", _RUNNER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("共通評価runnerを読み込めません")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_baseline(seed: int) -> dict[str, Any]:
    path = _BASELINE_DIR / f"C2-003-after-dev-seed-{seed}.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("stage") != "dev" or data.get("action_seed") != seed:
        raise RuntimeError("C2-003 dev基準artifactの条件が一致しません")
    return data


def _empty_bucket() -> dict[str, int]:
    return {"actions": 0, "no_op": 0, "game_over": 0, "level_progress": 0}


def _summarize(samples: list[dict[str, Any]]) -> dict[str, Any]:
    by_signature_seed: dict[tuple[tuple[int, ...], int], dict[str, int]] = defaultdict(
        _empty_bucket
    )
    by_context_action_seed: dict[tuple[tuple[int, ...], int, int], dict[str, int]] = defaultdict(
        _empty_bucket
    )
    run_signatures: dict[str, set[tuple[int, ...]]] = defaultdict(set)
    last_signature_by_run: dict[str, tuple[int, ...]] = {}
    transitions_by_run: dict[str, int] = defaultdict(int)

    for sample in samples:
        signature = tuple(sample["available_actions"])
        seed = sample["seed"]
        action = sample["action_id"]
        run = sample["run"]
        run_signatures[run].add(signature)
        if run in last_signature_by_run and last_signature_by_run[run] != signature:
            transitions_by_run[run] += 1
        last_signature_by_run[run] = signature
        for bucket in (
            by_signature_seed[(signature, seed)],
            by_context_action_seed[(signature, action, seed)],
        ):
            bucket["actions"] += 1
            bucket["no_op"] += int(sample["no_op"])
            bucket["game_over"] += int(sample["game_over"])
            bucket["level_progress"] += int(sample["level_progress"])

    signatures = sorted({key[0] for key in by_signature_seed})
    eligible_signatures = []
    for signature in signatures:
        per_seed = {
            seed: bucket
            for (candidate, seed), bucket in by_signature_seed.items()
            if candidate == signature
        }
        total = sum(bucket["actions"] for bucket in per_seed.values())
        represented_seeds = [seed for seed, bucket in per_seed.items() if bucket["actions"] >= 5]
        if total >= 20 and len(represented_seeds) >= 2:
            eligible_signatures.append(
                {
                    "available_actions": list(signature),
                    "actions": total,
                    "seed_count": len(represented_seeds),
                }
            )

    context_action_rows = []
    eligible_context_actions: dict[tuple[tuple[int, ...], int], dict[int, dict[str, int]]] = {}
    for signature in signatures:
        for action in range(1, 8):
            per_seed = {
                seed: by_context_action_seed[(signature, action, seed)]
                for seed in (7, 31, 73)
                if by_context_action_seed[(signature, action, seed)]["actions"] >= 5
            }
            total = sum(bucket["actions"] for bucket in per_seed.values())
            if total < 20 or len(per_seed) < 2:
                continue
            eligible_context_actions[(signature, action)] = per_seed
            row = {
                "available_actions": list(signature),
                "action_id": action,
                "actions": total,
                "seed_count": len(per_seed),
            }
            for outcome in ("no_op", "game_over", "level_progress"):
                row[f"{outcome}_rate"] = round(
                    sum(bucket[outcome] for bucket in per_seed.values()) / total, 6
                )
            context_action_rows.append(row)

    repeated_action_pairs = []
    eligible_keys = sorted(
        eligible_context_actions,
        key=lambda key: (key[1], key[0]),
    )
    for index, (left_signature, action) in enumerate(eligible_keys):
        for right_signature, other_action in eligible_keys[index + 1 :]:
            if action != other_action or left_signature == right_signature:
                continue
            left_by_seed = eligible_context_actions[(left_signature, action)]
            right_by_seed = eligible_context_actions[(right_signature, action)]
            compared_seeds = sorted(set(left_by_seed) & set(right_by_seed))
            if len(compared_seeds) < 2:
                continue
            deltas: dict[str, list[float]] = {"no_op": [], "game_over": []}
            for seed in compared_seeds:
                for outcome in deltas:
                    left = left_by_seed[seed]
                    right = right_by_seed[seed]
                    deltas[outcome].append(
                        right[outcome] / right["actions"] - left[outcome] / left["actions"]
                    )
            directional = {
                outcome: sum(delta > 0 for delta in values)
                if sum(delta > 0 for delta in values) >= sum(delta < 0 for delta in values)
                else -sum(delta < 0 for delta in values)
                for outcome, values in deltas.items()
            }
            repeated_action_pairs.append(
                {
                    "action_id": action,
                    "left_available_actions": list(left_signature),
                    "right_available_actions": list(right_signature),
                    "compared_seed_count": len(compared_seeds),
                    "consistent_no_op_direction_seeds": directional["no_op"],
                    "consistent_game_over_direction_seeds": directional["game_over"],
                }
            )

    return {
        "total_actions": len(samples),
        "distinct_available_action_sets": len(signatures),
        "within_run": {
            "runs": len(run_signatures),
            "runs_with_multiple_sets": sum(len(sets) > 1 for sets in run_signatures.values()),
            "total_signature_transitions": sum(transitions_by_run.values()),
            "max_distinct_sets_per_run": max(
                (len(sets) for sets in run_signatures.values()), default=0
            ),
        },
        "eligible_available_action_sets": eligible_signatures,
        "eligible_context_action_count": len(context_action_rows),
        "eligible_context_actions": context_action_rows,
        "repeated_action_context_pairs": repeated_action_pairs,
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
    metric_deltas: dict[int, dict[str, dict[str, int]]] = {}
    initial_metadata_matches: dict[int, int] = {}
    samples: list[dict[str, Any]] = []
    active_seed = 0
    active_run = ""
    original_record = 観測駆動探索方針.応答を記録する

    def record_response(self, before, action, after):
        receipt = original_record(self, before, action, after)
        samples.append(
            {
                "seed": active_seed,
                "run": active_run,
                "available_actions": sorted(before.作用可能番号),
                "action_id": action.作用番号,
                "no_op": receipt["可視変化セル数"] == 0 and receipt["完了レベル増分"] == 0,
                "game_over": after.状態 == "GAME_OVER",
                "level_progress": receipt["完了レベル増分"] > 0,
            }
        )
        return receipt

    try:
        観測駆動探索方針.応答を記録する = record_response
        for seed in seeds:
            current_totals = {key: 0 for key in (*_METRIC_FIELDS, "wins", "policy_holds")}
            same_start = 0
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
                    same_start += 1
                for key in _METRIC_FIELDS:
                    current_totals[key] += int(result[key])
                current_totals["wins"] += int(result["final_state"] == "WIN")
                current_totals["policy_holds"] += int(result["stop_reason"] == "exploration_hold")

            previous = baselines[seed]["aggregate"]["exploration"]
            deltas = {
                key: {
                    "previous": int(previous[key]),
                    "current": value,
                    "delta": value - int(previous[key]),
                }
                for key, value in current_totals.items()
            }
            if any(row["delta"] != 0 for row in deltas.values()):
                raise RuntimeError(f"seed {seed}のprevious/current基準集計が不一致です")
            if same_start != 5:
                raise RuntimeError(f"seed {seed}の公開開始状態照合が不足しています")
            metric_deltas[seed] = deltas
            initial_metadata_matches[seed] = same_start
    finally:
        観測駆動探索方針.応答を記録する = original_record

    summary = _summarize(samples)
    return {
        "instruction_id": "ARC3-RUN-002-C2-020",
        "evaluation": "public development split only; no runtime changes",
        "split_seed": args.split_seed,
        "action_seeds": list(seeds),
        "max_actions_per_game": 80,
        "retry_game_over": True,
        "runs": 15,
        "initial_metadata_matches": initial_metadata_matches,
        "baseline_metric_deltas": metric_deltas,
        "context_summary": summary,
        "source_sha256": {
            "diagnostic_runner": _sha256(Path(__file__)),
            "evaluation_runner": _sha256(_RUNNER_PATH),
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
        default=ROOT / "出力/ARC3-RUN-002-local/C2-020-available-actions-context.json",
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
            {"output": str(args.output), "context_summary": result["context_summary"]},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
