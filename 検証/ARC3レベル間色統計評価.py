"""同一ゲーム内レベル進行時に色UCB統計だけをリセットする単独評価。"""

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

_DEV_SEEDS = (7, 31, 73)
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


def _baseline_expected(stage: str, seed: int) -> dict[str, int]:
    path = ROOT / "出力/ARC3-RUN-002-local" / f"C2-003-after-{stage}-seed-{seed}.json"
    artifact = json.loads(path.read_text(encoding="utf-8"))
    aggregate = artifact["aggregate"]["exploration"]
    return {key: int(aggregate[key]) for key in _COUNTERS}


def _run_stage(
    stage: str, environments: list[tuple[dict[str, Any], Path]], seeds: tuple[int, ...]
) -> dict[str, Any]:
    conditions = ("previous", "candidate")
    aggregates = {
        condition: {str(seed): _empty_aggregate() for seed in seeds}
        for condition in conditions
    }
    same_start_pairs = {str(seed): 0 for seed in seeds}
    paired_runs = {str(seed): 0 for seed in seeds}

    for seed in seeds:
        seed_key = str(seed)
        for metadata, metadata_path in environments:
            pair_results = {}
            for condition in conditions:
                game = runner._run_game(
                    metadata,
                    metadata_path,
                    "exploration",
                    seed=seed,
                    max_actions=80,
                    retry_game_over=True,
                    reset_coordinate_color_stats_each_level=condition == "candidate",
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
                aggregate["illegal_action_attempts"] += int(game["illegal_action_attempts"])
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

    baseline_matches = {}
    for seed in seeds:
        seed_key = str(seed)
        expected = _baseline_expected(stage, seed)
        baseline_matches[seed_key] = {
            key: aggregates["previous"][seed_key][key] == value
            for key, value in expected.items()
        }
    return {
        "stage": stage,
        "environments_per_seed": len(environments),
        "seeds": list(seeds),
        "previous": aggregates["previous"],
        "candidate": aggregates["candidate"],
        "previous_matches_C2-003": baseline_matches,
        "same_public_start_pairs": same_start_pairs,
        "paired_environment_runs": paired_runs,
    }


def _gate(stage: str, result: dict[str, Any]) -> dict[str, Any]:
    previous = result["previous"]
    candidate = result["candidate"]
    seed_checks = {}
    for seed in result["seeds"]:
        old = previous[str(seed)]
        new = candidate[str(seed)]
        seed_checks[str(seed)] = {
            "levels_not_lower": new["levels_completed"] >= old["levels_completed"],
            "no_op_not_higher": new["no_op_actions"] <= old["no_op_actions"],
            "no_op_lower": new["no_op_actions"] < old["no_op_actions"],
            "game_over_not_higher": new["game_over_events"] <= old["game_over_events"],
            "holds_zero": new["policy_holds"] == 0,
            "illegal_zero": new["illegal_action_attempts"] == 0,
            "duplicates_zero": new["duplicate_observation_steps"] == 0,
        }
    checks = {
        "all_previous_runs_match_C2-003": all(
            all(checks.values()) for checks in result["previous_matches_C2-003"].values()
        ),
        "all_paired_public_starts_match": all(
            result["same_public_start_pairs"][str(seed)]
            == result["paired_environment_runs"][str(seed)]
            for seed in result["seeds"]
        ),
        "levels_not_lower_each_seed": all(
            check["levels_not_lower"] for check in seed_checks.values()
        ),
        "game_over_not_higher_each_seed": all(
            check["game_over_not_higher"] for check in seed_checks.values()
        ),
        "holds_illegal_duplicates_zero": all(
            check["holds_zero"] and check["illegal_zero"] and check["duplicates_zero"]
            for check in seed_checks.values()
        ),
    }
    if stage == "dev":
        checks["total_no_op_lower"] = sum(
            candidate[str(seed)]["no_op_actions"] for seed in result["seeds"]
        ) < sum(previous[str(seed)]["no_op_actions"] for seed in result["seeds"])
        checks["no_op_lower_in_at_least_two_seeds"] = sum(
            check["no_op_lower"] for check in seed_checks.values()
        ) >= 2
    else:
        checks["no_op_not_higher_each_seed"] = all(
            check["no_op_not_higher"] for check in seed_checks.values()
        )
        checks["total_no_op_lower"] = sum(
            candidate[str(seed)]["no_op_actions"] for seed in result["seeds"]
        ) < sum(previous[str(seed)]["no_op_actions"] for seed in result["seeds"])
    return {"checks": checks, "by_seed": seed_checks, "passed": all(checks.values())}


def run_experiment(output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite evaluation output: {output}")
    games = runner._load_games(ROOT / "入力/Kaggle/environment_files")
    if len(games) != 25:
        raise RuntimeError(f"Expected 25 public environments, found {len(games)}")
    split = list(games)
    random.Random(20261022).shuffle(split)
    development = _run_stage("dev", split[:5], _DEV_SEEDS)
    development_gate = _gate("dev", development)
    holdout = None
    holdout_gate = None
    if development_gate["passed"]:
        holdout = _run_stage("holdout", split[5:], (31,))
        holdout_gate = _gate("holdout", holdout)

    result = {
        "evaluation": "ARC3-RUN-002-C4-002",
        "scope": "public local environments; fixed split seed 20261022; dev action seeds 7/31/73; holdout seed 31; 80 requests; SDK RESET after GAME_OVER",
        "split_seed": 20261022,
        "public_environment_count": len(games),
        "candidate_rule": "clear only color UCB count/reward maps after positive level progress; preserve Action statistics, RNG, and all other policy state",
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
        default=ROOT / "出力/ARC3-RUN-002-local/C4-002-level-color-transfer.json",
    )
    args = parser.parse_args()
    result = run_experiment(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
