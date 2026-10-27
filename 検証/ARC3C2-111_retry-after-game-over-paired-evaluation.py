"""Paired local evaluation of preserving online learning across GAME_OVER resets."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import random
import runpy
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SPLIT_SEED = 20261022
POLICY_SEEDS = (7, 31, 73)
MAX_ACTIONS = 80
BASELINE_RUNNER = ROOT / "検証/ARC3C2-109_ACTION6-family-HDS-paired-evaluation.py"
OUTPUT = ROOT / "出力/ARC3-RUN-003-local/C2-111/retry-after-game-over-paired.json"


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


def _run_pair(
    run_game: Any,
    score_game: Any,
    metadata: dict[str, Any],
    metadata_path: Path,
    seed: int,
    policy_type: type,
) -> dict[str, Any]:
    arms: dict[str, dict[str, Any]] = {}
    for name, retry in (("previous", False), ("candidate", True)):
        run = run_game(
            metadata,
            metadata_path,
            "exploration",
            seed=seed,
            policy_seed=seed,
            max_actions=MAX_ACTIONS,
            retry_game_over=retry,
            exploration_coefficient=0.8,
            coordinate_color_exploration_coefficient=None,
            visible_change_coefficient=0.25,
            level_progress_reward=4.0,
            policy_type_override=policy_type,
        )
        score, levels, level_details = score_game(
            metadata.get("baseline_actions", []), run
        )
        arms[name] = {
            "start_sha256": _start_hash(run),
            "score": score,
            "levels": levels,
            "actions": run["actions"],
            "gameplay_actions": run["gameplay_actions"],
            "reset_actions": run["reset_actions"],
            "attempts": run["attempts"],
            "game_over_events": run["game_over_events"],
            "no_op_actions": run["no_op_actions"],
            "illegal_action_attempts": run["illegal_action_attempts"],
            "final_state": run["final_state"],
            "stop_reason": run["stop_reason"],
            "level_details": level_details,
            "action_trace": [
                {
                    "action_id": item["action_id"],
                    "data": item["data"],
                    "before_state": item["before_state"],
                    "after_state": item["after_state"],
                    "level_delta": item["level_delta"],
                    "changed_cells": item["changed_cells"],
                    "lifecycle_action": item["lifecycle_action"],
                }
                for item in run["action_responses"]
            ],
        }

    previous = arms["previous"]
    candidate = arms["candidate"]
    return {
        "seed": seed,
        "game_id": metadata["game_id"],
        "matched_start": previous["start_sha256"] == candidate["start_sha256"],
        "previous": previous,
        "candidate": candidate,
        "score_delta": candidate["score"] - previous["score"],
        "levels_delta": candidate["levels"] - previous["levels"],
        "actions_delta": candidate["actions"] - previous["actions"],
        "reset_actions_delta": candidate["reset_actions"] - previous["reset_actions"],
    }


def evaluate() -> dict[str, Any]:
    experiment = runpy.run_path(str(BASELINE_RUNNER))
    run_game = experiment["_run"].__globals__["_run_game"]
    score_game = experiment["_スコアを計算する"]
    policy_type = experiment["_CurrentHDSRankingPolicy"]
    games = experiment["_load_games"](ROOT / "入力/Kaggle/environment_files")
    random.Random(SPLIT_SEED).shuffle(games)
    selected = games[:5]

    pairs = [
        _run_pair(run_game, score_game, metadata, path, seed, policy_type)
        for seed in POLICY_SEEDS
        for metadata, path in selected
    ]
    previous_scores = [pair["previous"]["score"] for pair in pairs]
    candidate_scores = [pair["candidate"]["score"] for pair in pairs]
    deltas = [pair["score_delta"] for pair in pairs]
    summary = {
        "pairs": len(pairs),
        "matched_start_pairs": sum(pair["matched_start"] for pair in pairs),
        "mean_previous": sum(previous_scores) / len(pairs),
        "mean_candidate": sum(candidate_scores) / len(pairs),
        "mean_delta": sum(deltas) / len(deltas),
        "positive_pairs": sum(delta > 0 for delta in deltas),
        "negative_pairs": sum(delta < 0 for delta in deltas),
        "tied_pairs": sum(delta == 0 for delta in deltas),
        "levels_delta": sum(pair["levels_delta"] for pair in pairs),
        "wins_delta": sum(
            int(pair["candidate"]["final_state"] == "WIN")
            - int(pair["previous"]["final_state"] == "WIN")
            for pair in pairs
        ),
        "actions_previous": sum(pair["previous"]["actions"] for pair in pairs),
        "actions_candidate": sum(pair["candidate"]["actions"] for pair in pairs),
        "resets_previous": sum(pair["previous"]["reset_actions"] for pair in pairs),
        "resets_candidate": sum(pair["candidate"]["reset_actions"] for pair in pairs),
        "noops_previous": sum(pair["previous"]["no_op_actions"] for pair in pairs),
        "noops_candidate": sum(pair["candidate"]["no_op_actions"] for pair in pairs),
        "illegal_actions": sum(
            pair["previous"]["illegal_action_attempts"]
            + pair["candidate"]["illegal_action_attempts"]
            for pair in pairs
        ),
    }
    return {
        "split_seed": SPLIT_SEED,
        "policy_seeds": POLICY_SEEDS,
        "max_actions_per_game_including_resets": MAX_ACTIONS,
        "dev_games": [metadata["game_id"] for metadata, _ in selected],
        "baseline": "Current HDS ranking policy; stop at first GAME_OVER.",
        "candidate": "Same policy, RNG, and learned statistics; issue legal SDK RESET at GAME_OVER and preserve policy state until the shared action cap.",
        "decision_gate": {
            "minimum_mean_rhae_delta": 0.01,
            "require_nonnegative_levels_and_wins": True,
            "holdout_or_promotion_if_gate_fails": False,
        },
        "summary": summary,
        "pairs": pairs,
        "runner_file": Path(__file__).relative_to(ROOT).as_posix(),
        "runner_sha256": _sha256(Path(__file__)),
        "baseline_runner_file": BASELINE_RUNNER.relative_to(ROOT).as_posix(),
        "baseline_runner_sha256": _sha256(BASELINE_RUNNER),
    }


def main() -> None:
    payload = json.dumps(evaluate(), ensure_ascii=False, indent=2)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(payload + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "sha256": _sha256(OUTPUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
