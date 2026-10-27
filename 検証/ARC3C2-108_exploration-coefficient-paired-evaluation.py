"""Paired public-dev sweep of the generic exploration UCB coefficient (C2-108)."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
from typing import Any

from ARC3探索Actionローカル評価 import ROOT, _load_games, _run_game
from ARC3公開RHAE評価 import _スコアを計算する

SPLIT_SEED = 20261022
POLICY_SEEDS = (7, 31, 73)
MAX_ACTIONS = 80
BASELINE_COEFFICIENT = 0.8
CANDIDATE_COEFFICIENTS = (0.4, 1.6)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _start_hash(run: dict[str, Any]) -> str:
    start = {
        key: run[key]
        for key in (
            "initial_state",
            "initial_levels_completed",
            "initial_available_actions",
            "initial_board",
        )
    }
    payload = json.dumps(start, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _run(metadata: dict[str, Any], path: Path, seed: int, coefficient: float) -> dict[str, Any]:
    return _run_game(
        metadata,
        path,
        "exploration",
        seed=seed,
        policy_seed=seed,
        max_actions=MAX_ACTIONS,
        retry_game_over=False,
        exploration_coefficient=coefficient,
        coordinate_color_exploration_coefficient=None,
        visible_change_coefficient=0.25,
        level_progress_reward=4.0,
    )


def evaluate() -> dict[str, Any]:
    games = _load_games(ROOT / "入力/Kaggle/environment_files")
    shuffled = list(games)
    random.Random(SPLIT_SEED).shuffle(shuffled)
    selected = shuffled[:5]
    rows: list[dict[str, Any]] = []

    for seed in POLICY_SEEDS:
        for metadata, path in selected:
            baseline = _run(metadata, path, seed, BASELINE_COEFFICIENT)
            score, levels, _ = _スコアを計算する(metadata.get("baseline_actions", []), baseline)
            rows.append({
                "coefficient": BASELINE_COEFFICIENT,
                "seed": seed,
                "game_id": metadata["game_id"],
                "score": score,
                "levels": levels,
                "actions": baseline["actions"],
                "noops": baseline["no_op_actions"],
                "wins": int(baseline["final_state"] == "WIN"),
                "illegal_actions": baseline["illegal_action_attempts"],
                "initial_public_state_sha256": _start_hash(baseline),
            })

    summaries = []
    for coefficient in CANDIDATE_COEFFICIENTS:
        for seed in POLICY_SEEDS:
            for metadata, path in selected:
                candidate = _run(metadata, path, seed, coefficient)
                score, levels, _ = _スコアを計算する(
                    metadata.get("baseline_actions", []), candidate
                )
                rows.append({
                    "coefficient": coefficient,
                    "seed": seed,
                    "game_id": metadata["game_id"],
                    "score": score,
                    "levels": levels,
                    "actions": candidate["actions"],
                    "noops": candidate["no_op_actions"],
                    "wins": int(candidate["final_state"] == "WIN"),
                    "illegal_actions": candidate["illegal_action_attempts"],
                    "initial_public_state_sha256": _start_hash(candidate),
                })

        baseline_by_pair = {
            (row["seed"], row["game_id"]): row
            for row in rows
            if row["coefficient"] == BASELINE_COEFFICIENT
        }
        candidate_rows = [row for row in rows if row["coefficient"] == coefficient]
        paired = [
            (
                baseline_by_pair[(row["seed"], row["game_id"])],
                row,
            )
            for row in candidate_rows
        ]
        delta = [current["score"] - previous["score"] for previous, current in paired]
        mean_previous = sum(previous["score"] for previous, _ in paired) / len(paired)
        mean_candidate = sum(current["score"] for _, current in paired) / len(paired)
        summaries.append({
            "coefficient": coefficient,
            "pairs": len(paired),
            "matched_start_pairs": sum(
                previous["initial_public_state_sha256"]
                == current["initial_public_state_sha256"]
                for previous, current in paired
            ),
            "mean_previous": mean_previous,
            "mean_candidate": mean_candidate,
            "mean_delta": sum(delta) / len(delta),
            "positive_pairs": sum(value > 0 for value in delta),
            "negative_pairs": sum(value < 0 for value in delta),
            "tied_pairs": sum(value == 0 for value in delta),
            "levels_delta": sum(current["levels"] - previous["levels"] for previous, current in paired),
            "wins_delta": sum(current["wins"] - previous["wins"] for previous, current in paired),
            "actions_previous": sum(previous["actions"] for previous, _ in paired),
            "actions_candidate": sum(current["actions"] for _, current in paired),
            "noops_previous": sum(previous["noops"] for previous, _ in paired),
            "noops_candidate": sum(current["noops"] for _, current in paired),
            "illegal_actions": sum(previous["illegal_actions"] + current["illegal_actions"] for previous, current in paired),
            "pair_deltas": [
                {
                    "seed": previous["seed"],
                    "game_id": previous["game_id"],
                    "delta": current["score"] - previous["score"],
                }
                for previous, current in paired
            ],
        })

    return {
        "split_seed": SPLIT_SEED,
        "policy_seeds": POLICY_SEEDS,
        "max_actions_per_game": MAX_ACTIONS,
        "dev_games": [metadata["game_id"] for metadata, _ in selected],
        "baseline_coefficient": BASELINE_COEFFICIENT,
        "candidate_coefficients": CANDIDATE_COEFFICIENTS,
        "score_summaries": summaries,
        "raw_rows": rows,
        "decision_gate": {
            "minimum_mean_rhae_delta": 0.01,
            "require_nonnegative_levels_and_wins": True,
            "holdout_or_promotion_if_gate_fails": False,
        },
        "input_manifest_sha256": {
            path.relative_to(ROOT).as_posix(): _sha256(path)
            for _, path in selected
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "出力/ARC3-RUN-003-local/C2-108/exploration-coefficient-sweep.json",
    )
    args = parser.parse_args()
    report = evaluate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["score_summaries"], ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()

