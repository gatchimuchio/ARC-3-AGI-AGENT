"""GAME_OVER応答への追加報酬罰を匿名aggregateでdev/holdout評価する。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "検証"))

import ARC3探索Actionローカル評価 as runner  # noqa: E402
import ARC3レベル間色統計評価 as baseline_helper  # noqa: E402
from 接続.観測駆動探索Action import 観測駆動探索方針  # noqa: E402

_SEEDS = (7, 31, 73)
_COUNTERS = (
    "actions",
    "levels_completed",
    "wins",
    "no_op_actions",
    "game_over_events",
    "reset_actions",
    "illegal_action_attempts",
    "duplicate_observation_steps",
    "policy_holds",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _empty_aggregate() -> dict[str, int]:
    return {key: 0 for key in _COUNTERS} | {"games": 0}


def _run_stage(stage: str, environments) -> dict[str, Any]:
    conditions = ("previous", "candidate")
    aggregates = {
        condition: {str(seed): _empty_aggregate() for seed in _SEEDS}
        for condition in conditions
    }
    game_over_by_action = {
        condition: {str(seed): {} for seed in _SEEDS} for condition in conditions
    }
    same_start_pairs = {str(seed): 0 for seed in _SEEDS}
    paired_runs = {str(seed): 0 for seed in _SEEDS}
    original_record = 観測駆動探索方針.応答を記録する
    current = ["", ""]

    def instrumented_record(self, before, action, after):
        response = original_record(self, before, action, after)
        if after.状態 == "GAME_OVER" and (
            after.完了レベル数 <= before.完了レベル数
        ):
            condition, seed = current
            counts = game_over_by_action[condition][seed]
            action_key = str(action.作用番号)
            counts[action_key] = counts.get(action_key, 0) + 1
        return response

    観測駆動探索方針.応答を記録する = instrumented_record
    try:
        for seed in _SEEDS:
            seed_key = str(seed)
            for metadata, metadata_path in environments:
                pair_results = {}
                for condition in conditions:
                    current[:] = [condition, seed_key]
                    game = runner._run_game(
                        metadata,
                        metadata_path,
                        "exploration",
                        seed=seed,
                        max_actions=80,
                        retry_game_over=True,
                        penalize_game_over_action=condition == "candidate",
                    )
                    pair_results[condition] = game
                    aggregate = aggregates[condition][seed_key]
                    aggregate["games"] += 1
                    aggregate["actions"] += int(game["actions"])
                    aggregate["levels_completed"] += int(game["levels_completed"])
                    aggregate["wins"] += int(game["final_state"] == "WIN")
                    aggregate["no_op_actions"] += int(game["no_op_actions"])
                    aggregate["game_over_events"] += int(game["game_over_events"])
                    aggregate["reset_actions"] += int(game["reset_actions"])
                    aggregate["illegal_action_attempts"] += int(
                        game["illegal_action_attempts"]
                    )
                    aggregate["duplicate_observation_steps"] += int(
                        game["duplicate_observation_steps"]
                    )
                    aggregate["policy_holds"] += int(game["stop_reason"] == "exploration_hold")
                    if game["actions"] != len(game["action_responses"]):
                        raise RuntimeError("action response count differs from evaluator actions")
                paired_runs[seed_key] += 1
                same_start = (
                    pair_results["previous"]["initial_state"]
                    == pair_results["candidate"]["initial_state"]
                    and pair_results["previous"]["initial_levels_completed"]
                    == pair_results["candidate"]["initial_levels_completed"]
                    and pair_results["previous"]["initial_available_actions"]
                    == pair_results["candidate"]["initial_available_actions"]
                    and pair_results["previous"]["initial_board"]
                    == pair_results["candidate"]["initial_board"]
                )
                same_start_pairs[seed_key] += int(same_start)
    finally:
        観測駆動探索方針.応答を記録する = original_record

    baseline_matches = {}
    for seed in _SEEDS:
        key = str(seed)
        expected = baseline_helper._baseline_expected(stage, seed)
        baseline_matches[key] = {
            metric: aggregates["previous"][key][metric] == value
            for metric, value in expected.items()
        }
    return {
        "stage": stage,
        "environments_per_seed": len(environments),
        "seeds": list(_SEEDS),
        "previous": aggregates["previous"],
        "candidate": aggregates["candidate"],
        "previous_matches_C2-003": baseline_matches,
        "same_public_start_pairs": same_start_pairs,
        "paired_environment_runs": paired_runs,
        "game_over_by_action": game_over_by_action,
    }


def _gate(result: dict[str, Any]) -> dict[str, Any]:
    checks_by_seed = {}
    for seed in _SEEDS:
        key = str(seed)
        old = result["previous"][key]
        new = result["candidate"][key]
        checks_by_seed[key] = {
            "levels_not_lower": new["levels_completed"] >= old["levels_completed"],
            "no_op_not_higher": new["no_op_actions"] <= old["no_op_actions"],
            "game_over_not_higher": new["game_over_events"] <= old["game_over_events"],
            "game_over_lower": new["game_over_events"] < old["game_over_events"],
            "holds_zero": new["policy_holds"] == 0,
            "illegal_zero": new["illegal_action_attempts"] == 0,
            "duplicates_zero": new["duplicate_observation_steps"] == 0,
        }
    previous = result["previous"]
    candidate = result["candidate"]
    checks = {
        "all_previous_runs_match_C2-003": all(
            all(seed_checks.values())
            for seed_checks in result["previous_matches_C2-003"].values()
        ),
        "all_paired_public_starts_match": all(
            result["same_public_start_pairs"][str(seed)]
            == result["paired_environment_runs"][str(seed)]
            for seed in _SEEDS
        ),
        "levels_not_lower_each_seed": all(
            check["levels_not_lower"] for check in checks_by_seed.values()
        ),
        "no_op_not_higher_each_seed": all(
            check["no_op_not_higher"] for check in checks_by_seed.values()
        ),
        "no_op_total_not_higher": sum(
            candidate[str(seed)]["no_op_actions"] for seed in _SEEDS
        )
        <= sum(previous[str(seed)]["no_op_actions"] for seed in _SEEDS),
        "game_over_not_higher_each_seed": all(
            check["game_over_not_higher"] for check in checks_by_seed.values()
        ),
        "game_over_total_lower": sum(
            candidate[str(seed)]["game_over_events"] for seed in _SEEDS
        )
        < sum(previous[str(seed)]["game_over_events"] for seed in _SEEDS),
        "game_over_lower_in_at_least_two_seeds": sum(
            check["game_over_lower"] for check in checks_by_seed.values()
        )
        >= 2,
        "holds_illegal_duplicates_zero": all(
            check["holds_zero"] and check["illegal_zero"] and check["duplicates_zero"]
            for check in checks_by_seed.values()
        ),
    }
    return {"checks": checks, "by_seed": checks_by_seed, "passed": all(checks.values())}


def run_experiment(output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite evaluation output: {output}")
    games = runner._load_games(ROOT / "入力/Kaggle/environment_files")
    if len(games) != 25:
        raise RuntimeError(f"Expected 25 public environments, found {len(games)}")
    split = list(games)
    random.Random(20261022).shuffle(split)
    development = _run_stage("dev", split[:5])
    development_gate = _gate(development)
    holdout = None
    holdout_gate = None
    if development_gate["passed"]:
        holdout = _run_stage("holdout", split[5:])
        holdout_gate = _gate(holdout)
    result = {
        "evaluation": "ARC3-RUN-002-C2-014",
        "scope": "public local environments; split seed 20261022; action seeds 7/31/73; 80 requests; SDK RESET after GAME_OVER",
        "public_environment_count": len(games),
        "candidate_rule": "subtract 1.0 from Action and selected color reward after GAME_OVER with no level progress",
        "development": development,
        "development_gate": development_gate,
        "holdout": holdout,
        "holdout_gate": holdout_gate,
        "decision": (
            "holdout_pass_candidate_only"
            if holdout_gate and holdout_gate["passed"]
            else "reject_no_holdout"
            if not development_gate["passed"]
            else "reject_holdout"
        ),
        "source_sha256": {
            "experiment_runner": _sha256(Path(__file__)),
            "evaluation_runner": _sha256(ROOT / "検証/ARC3探索Actionローカル評価.py"),
            "baseline_helper": _sha256(ROOT / "検証/ARC3レベル間色統計評価.py"),
            "policy": _sha256(ROOT / "接続/観測駆動探索Action.py"),
            "boundary": _sha256(ROOT / "接続/ARC3境界.py"),
            "starter_agent": _sha256(ROOT / "入力/Kaggle/ARC-AGI-3-Agents/agents/agent.py"),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result["output_sha256"] = _sha256(output)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "出力/ARC3-RUN-002-local/C2-014-game-over-reward.json",
    )
    args = parser.parse_args()
    result = run_experiment(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
