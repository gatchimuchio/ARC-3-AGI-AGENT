"""Paired public scorecard for one level-progress reward coefficient."""

from __future__ import annotations

import argparse
import hashlib
import json
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
        raise RuntimeError("scorecard level count disagrees with the local environment")
    return score, levels, int(run["final_state"] == "WIN")


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
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
        "actions_delta_total": sum(
            int(row["candidate_actions"]) - int(row["baseline_actions"]) for row in rows
        ),
        "action6_delta_total": sum(
            int(row["candidate_action6"]) - int(row["baseline_action6"]) for row in rows
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
    parser.add_argument("--seeds", type=int, nargs="+")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--candidate-reward", type=float, default=16.0)
    args = parser.parse_args()
    if args.candidate_reward <= 4.0:
        parser.error("candidate reward must exceed the fixed baseline 4.0")

    all_games = _load_games(ROOT / "入力/Kaggle/environment_files")
    if len(all_games) != 25:
        raise RuntimeError("expected the 25 public ARC3 environments")
    shuffled = list(all_games)
    random.Random(20261027).shuffle(shuffled)
    selected_games = shuffled[5:10] if args.stage == "dev" else shuffled
    seeds = (
        args.seeds
        if args.seeds is not None
        else ([7, 31, 73] if args.stage == "dev" else [101, 211, 307])
    )
    started = time.perf_counter()
    rows: list[dict[str, Any]] = []

    for seed in seeds:
        for game_index, (metadata, metadata_path) in enumerate(selected_games):
            runs = {}
            scores = {}
            levels = {}
            wins = {}
            for label, reward in (("baseline", 4.0), ("candidate", args.candidate_reward)):
                run = _run_game(
                    metadata,
                    metadata_path,
                    "exploration",
                    seed=seed,
                    policy_seed=seed,
                    max_actions=80,
                    visible_change_coefficient=0.0,
                    level_progress_reward=reward,
                )
                runs[label] = run
                scores[label], levels[label], wins[label] = _score(metadata, run)

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
                raise RuntimeError("paired runs did not start from the same public observation")
            baseline_trace = [
                (item["action_id"], item["data"]) for item in baseline["action_responses"]
            ]
            candidate_trace = [
                (item["action_id"], item["data"]) for item in candidate["action_responses"]
            ]
            rows.append(
                {
                    "seed": seed,
                    "game_index": game_index,
                    "baseline_score": scores["baseline"],
                    "candidate_score": scores["candidate"],
                    "baseline_levels": levels["baseline"],
                    "candidate_levels": levels["candidate"],
                    "baseline_wins": wins["baseline"],
                    "candidate_wins": wins["candidate"],
                    "baseline_noops": int(baseline["no_op_actions"]),
                    "candidate_noops": int(candidate["no_op_actions"]),
                    "baseline_actions": int(baseline["actions"]),
                    "candidate_actions": int(candidate["actions"]),
                    "baseline_action6": sum(
                        item["action_id"] == 6 for item in baseline["action_responses"]
                    ),
                    "candidate_action6": sum(
                        item["action_id"] == 6 for item in candidate["action_responses"]
                    ),
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
                f"PROGRESS {args.stage} seed={seed} episode={game_index + 1}/{len(selected_games)}",
                flush=True,
            )

    grouped = [
        {"seed": seed, **_summary([row for row in rows if row["seed"] == seed])} for seed in seeds
    ]
    comparison = _summary(rows)
    if args.stage == "dev":
        candidate_passes_gate = bool(
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
            "minimum_score_improvement_minus_regression": 0,
            "minimum_levels_delta": 0,
        }
    else:
        candidate_passes_gate = bool(
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
            "score_improvements_must_exceed_regressions": True,
            "minimum_levels_delta": 0,
        }
    result = {
        "schema": "arc3-level-progress-reward-paired.v1",
        "stage": args.stage,
        "python_hash_seed": os.environ.get("PYTHONHASHSEED", "randomized"),
        "split_seed": 20261027,
        "games": len(selected_games),
        "seeds": list(seeds),
        "max_actions": 80,
        "retry_game_over": False,
        "visible_change_coefficient": 0.0,
        "baseline_level_progress_reward": 4.0,
        "candidate_level_progress_reward": args.candidate_reward,
        "public_rhae_comparison": {**comparison, "by_seed": grouped},
        "validation_gate": gate,
        "candidate_passes_gate": candidate_passes_gate,
        "errors": 0,
        "illegal_actions": sum(int(row["illegal_actions"]) for row in rows),
        "duplicate_observations": sum(int(row["duplicate_observations"]) for row in rows),
        "per_game_rows_persisted": False,
        "game_ids_persisted": False,
        "hidden_or_answer_data_read": False,
        "official_submission_made": False,
        "notebook_or_kernel_changed": False,
        "environment_manifest_sha256": _manifest_sha256(),
        "policy_source_sha256": _sha(ROOT / "接続/観測駆動探索Action.py"),
        "local_evaluator_sha256": _sha(ROOT / "検証/ARC3探索Actionローカル評価.py"),
        "scorer_sha256": _sha(ROOT / "検証/ARC3公開RHAE評価.py"),
        "runner_source_sha256": _sha(Path(__file__)),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if output.exists():
        raise FileExistsError(f"refusing to overwrite existing result: {output}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
