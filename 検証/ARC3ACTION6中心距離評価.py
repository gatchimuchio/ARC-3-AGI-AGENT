"""ACTION6中心距離順の単独dev/holdout評価を匿名集計する。"""

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
from ARC3ACTION6座標特徴診断 import _cell_features  # noqa: E402
from 接続.観測駆動探索Action import 観測駆動探索方針  # noqa: E402

_SEEDS = (7, 31, 73)
_CONDITIONS = ("previous", "candidate")
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
_OUTCOMES = ("no_op", "board_change", "level_progress", "level_decrease")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _empty_aggregate() -> dict[str, int]:
    return {key: 0 for key in _COUNTERS} | {"games": 0}


def _baseline_expected(stage: str, seed: int) -> dict[str, int]:
    path = ROOT / "出力/ARC3-RUN-002-local" / f"C2-003-after-{stage}-seed-{seed}.json"
    artifact = json.loads(path.read_text(encoding="utf-8"))
    aggregate = artifact["aggregate"]["exploration"]
    return {key: int(aggregate[key]) for key in _COUNTERS}


def _empty_feature_bucket() -> dict[str, int]:
    return {"action6_responses": 0, **{key: 0 for key in _OUTCOMES}}


def _run_stage(stage: str, environments: list[tuple[dict[str, Any], Path]]) -> dict[str, Any]:
    aggregates = {
        condition: {str(seed): _empty_aggregate() for seed in _SEEDS}
        for condition in _CONDITIONS
    }
    feature_counts: dict[str, dict[str, dict[str, dict[str, int]]]] = {
        condition: {str(seed): {} for seed in _SEEDS} for condition in _CONDITIONS
    }
    same_start_pairs = {str(seed): 0 for seed in _SEEDS}
    total_pairs = {str(seed): 0 for seed in _SEEDS}
    original_record = 観測駆動探索方針.応答を記録する
    current = ["", ""]

    def instrumented_record(self, before, action, after):
        response = original_record(self, before, action, after)
        if action.作用番号 != 6:
            return response
        features = _cell_features(before.最新盤面, action.引数["x"], action.引数["y"])
        level_delta = after.完了レベル数 - before.完了レベル数
        if level_delta > 0:
            outcome = "level_progress"
        elif level_delta < 0:
            outcome = "level_decrease"
        elif response["可視変化セル数"] > 0:
            outcome = "board_change"
        else:
            outcome = "no_op"
        condition, seed = current
        counts = feature_counts[condition][seed]
        center_bucket = features["relative_center_distance"]
        bucket = counts.setdefault(center_bucket, _empty_feature_bucket())
        bucket["action6_responses"] += 1
        bucket[outcome] += 1
        return response

    観測駆動探索方針.応答を記録する = instrumented_record
    try:
        for seed in _SEEDS:
            seed_key = str(seed)
            for metadata, metadata_path in environments:
                pair_results = {}
                for condition in _CONDITIONS:
                    current[:] = [condition, seed_key]
                    game = runner._run_game(
                        metadata,
                        metadata_path,
                        "exploration",
                        seed=seed,
                        max_actions=80,
                        retry_game_over=True,
                        prioritize_center_distance_action6=condition == "candidate",
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
                total_pairs[seed_key] += 1
                same_public_start = (
                    pair_results["previous"]["initial_state"]
                    == pair_results["candidate"]["initial_state"]
                    and pair_results["previous"]["initial_levels_completed"]
                    == pair_results["candidate"]["initial_levels_completed"]
                    and pair_results["previous"]["initial_available_actions"]
                    == pair_results["candidate"]["initial_available_actions"]
                    and pair_results["previous"]["initial_board"]
                    == pair_results["candidate"]["initial_board"]
                )
                same_start_pairs[seed_key] += int(same_public_start)
    finally:
        観測駆動探索方針.応答を記録する = original_record

    baseline_matches = {}
    for seed in _SEEDS:
        seed_key = str(seed)
        expected = _baseline_expected(stage, seed)
        baseline_matches[seed_key] = {
            key: aggregates["previous"][seed_key][key] == value
            for key, value in expected.items()
        }
    return {
        "stage": stage,
        "environments_per_seed": len(environments),
        "previous": aggregates["previous"],
        "candidate": aggregates["candidate"],
        "previous_matches_C2-003": baseline_matches,
        "same_public_start_pairs": same_start_pairs,
        "paired_environment_runs": total_pairs,
        "action6_center_distance_outcomes": feature_counts,
    }


def _gate(stage: str, result: dict[str, Any]) -> dict[str, Any]:
    previous = result["previous"]
    candidate = result["candidate"]
    seed_checks: dict[str, dict[str, bool]] = {}
    for seed in map(str, _SEEDS):
        old = previous[seed]
        new = candidate[seed]
        seed_checks[seed] = {
            "levels_not_lower": new["levels_completed"] >= old["levels_completed"],
            "game_over_not_higher": new["game_over_events"] <= old["game_over_events"],
            "no_op_not_higher": new["no_op_actions"] <= old["no_op_actions"],
            "no_op_lower": new["no_op_actions"] < old["no_op_actions"],
            "holds_zero": new["policy_holds"] == 0,
            "illegal_zero": new["illegal_action_attempts"] == 0,
            "duplicates_zero": new["duplicate_observation_steps"] == 0,
        }
        if stage == "holdout":
            seed_checks[seed]["game_over_not_higher"] = (
                new["game_over_events"] <= old["game_over_events"]
            )
            for metric in (
                "game_over_events",
                "policy_holds",
                "illegal_action_attempts",
                "duplicate_observation_steps",
            ):
                seed_checks[seed][f"{metric}_not_higher"] = new[metric] <= old[metric]

    checks = {
        "all_previous_runs_match_C2-003": all(
            all(checks.values()) for checks in result["previous_matches_C2-003"].values()
        ),
        "all_paired_public_starts_match": all(
            result["same_public_start_pairs"][str(seed)]
            == result["paired_environment_runs"][str(seed)]
            for seed in _SEEDS
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
            candidate[seed]["no_op_actions"] for seed in candidate
        ) < sum(previous[seed]["no_op_actions"] for seed in previous)
        checks["no_op_lower_in_at_least_two_seeds"] = sum(
            seed_checks[seed]["no_op_lower"] for seed in seed_checks
        ) >= 2
    else:
        checks["no_op_not_higher_each_seed"] = all(
            check["no_op_not_higher"] for check in seed_checks.values()
        )
        checks["total_no_op_lower"] = sum(
            candidate[seed]["no_op_actions"] for seed in candidate
        ) < sum(previous[seed]["no_op_actions"] for seed in previous)
    return {"checks": checks, "by_seed": seed_checks, "passed": all(checks.values())}


def run_experiment(output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite evaluation output: {output}")
    games = runner._load_games(ROOT / "入力/Kaggle/environment_files")
    if len(games) != 25:
        raise RuntimeError(f"Expected 25 public environments, found {len(games)}")
    split = list(games)
    random.Random(20261022).shuffle(split)
    dev = split[:5]
    holdout = split[5:]
    development = _run_stage("dev", dev)
    development_gate = _gate("dev", development)
    holdout_result = None
    holdout_gate = None
    if development_gate["passed"]:
        holdout_result = _run_stage("holdout", holdout)
        holdout_gate = _gate("holdout", holdout_result)

    result = {
        "evaluation": "ARC3-RUN-002-C2-012",
        "scope": "public local environments; fixed split seed 20261022; action seeds 7/31/73; 80 requests per run; SDK RESET after GAME_OVER",
        "split_seed": 20261022,
        "public_environment_count": len(games),
        "dev_rule": "retain UCB color selection and uniformly choose among nearest-center untried same-color coordinates",
        "one_factor_boundary": "only ACTION6 untried coordinate selection differs; policy, HDS, runtime, notebook, and kernel source are unchanged",
        "development": development,
        "development_gate": development_gate,
        "holdout": holdout_result,
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
            "diagnostic_runner": _sha256(ROOT / "検証/ARC3ACTION6座標特徴診断.py"),
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
        default=ROOT / "出力/ARC3-RUN-002-local/C2-012-action6-center-distance.json",
    )
    args = parser.parse_args()
    result = run_experiment(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
