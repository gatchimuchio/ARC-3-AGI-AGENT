"""ACTION6選択色の同色4近傍がある座標を優先する匿名dev/holdout評価。"""

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
_OUTCOMES = ("no_op", "board_change", "level_progress", "level_decrease")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _empty_aggregate() -> dict[str, int]:
    return {key: 0 for key in _COUNTERS} | {"games": 0}


def _empty_bucket() -> dict[str, int]:
    return {"action6_responses": 0, **{key: 0 for key in _OUTCOMES}}


def _neighbor_bucket(board, x: int, y: int) -> str:
    if not board or any(len(row) != len(board[0]) for row in board):
        raise ValueError("ACTION6 pre-action board must be rectangular")
    height, width = len(board), len(board[0])
    if not (0 <= x < width and 0 <= y < height):
        raise ValueError("selected coordinate is outside the public board")
    color = board[y][x]
    count = sum(
        1
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))
        if 0 <= x + dx < width and 0 <= y + dy < height and board[y + dy][x + dx] == color
    )
    if count == 0:
        return "0"
    if count <= 2:
        return "1_2"
    return "3_4"


def _run_stage(stage: str, environments, seeds: tuple[int, ...]) -> dict[str, Any]:
    conditions = ("previous", "candidate")
    aggregates = {
        condition: {str(seed): _empty_aggregate() for seed in seeds}
        for condition in conditions
    }
    feature_counts = {
        condition: {str(seed): {} for seed in seeds} for condition in conditions
    }
    same_start_pairs = {str(seed): 0 for seed in seeds}
    paired_runs = {str(seed): 0 for seed in seeds}
    original_record = 観測駆動探索方針.応答を記録する
    current = ["", ""]

    def instrumented_record(self, before, action, after):
        response = original_record(self, before, action, after)
        if action.作用番号 != 6:
            return response
        bucket_name = _neighbor_bucket(
            before.最新盤面, action.引数["x"], action.引数["y"]
        )
        level_delta = after.完了レベル数 - before.完了レベル数
        if level_delta > 0:
            outcome = "level_progress"
        elif level_delta < 0:
            outcome = "level_decrease"
        elif response["可視変化セル数"] > 0:
            outcome = "board_change"
        else:
            outcome = "no_op"
        condition, seed_key = current
        bucket = feature_counts[condition][seed_key].setdefault(
            bucket_name, _empty_bucket()
        )
        bucket["action6_responses"] += 1
        bucket[outcome] += 1
        return response

    観測駆動探索方針.応答を記録する = instrumented_record
    try:
        for seed in seeds:
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
                        prefer_connected_action6=condition == "candidate",
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
    for seed in seeds:
        key = str(seed)
        expected = baseline_helper._baseline_expected(stage, seed)
        baseline_matches[key] = {
            metric: aggregates["previous"][key][metric] == value
            for metric, value in expected.items()
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
        "action6_neighbor_outcomes": feature_counts,
    }


def _gate(stage: str, result: dict[str, Any]) -> dict[str, Any]:
    checks_by_seed = {}
    for seed in result["seeds"]:
        key = str(seed)
        old = result["previous"][key]
        new = result["candidate"][key]
        checks_by_seed[key] = {
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
            all(seed_checks.values())
            for seed_checks in result["previous_matches_C2-003"].values()
        ),
        "all_paired_public_starts_match": all(
            result["same_public_start_pairs"][str(seed)]
            == result["paired_environment_runs"][str(seed)]
            for seed in result["seeds"]
        ),
        "levels_not_lower_each_seed": all(
            check["levels_not_lower"] for check in checks_by_seed.values()
        ),
        "game_over_not_higher_each_seed": all(
            check["game_over_not_higher"] for check in checks_by_seed.values()
        ),
        "holds_illegal_duplicates_zero": all(
            check["holds_zero"] and check["illegal_zero"] and check["duplicates_zero"]
            for check in checks_by_seed.values()
        ),
    }
    if stage == "dev":
        checks["total_no_op_lower"] = sum(
            result["candidate"][str(seed)]["no_op_actions"] for seed in result["seeds"]
        ) < sum(result["previous"][str(seed)]["no_op_actions"] for seed in result["seeds"])
        checks["no_op_lower_in_at_least_two_seeds"] = sum(
            check["no_op_lower"] for check in checks_by_seed.values()
        ) >= 2
    else:
        checks["no_op_not_higher_each_seed"] = all(
            check["no_op_not_higher"] for check in checks_by_seed.values()
        )
        checks["total_no_op_lower"] = sum(
            result["candidate"][str(seed)]["no_op_actions"] for seed in result["seeds"]
        ) < sum(result["previous"][str(seed)]["no_op_actions"] for seed in result["seeds"])
    return {"checks": checks, "by_seed": checks_by_seed, "passed": all(checks.values())}


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
        holdout = _run_stage("holdout", split[5:], _DEV_SEEDS)
        holdout_gate = _gate("holdout", holdout)
    result = {
        "evaluation": "ARC3-RUN-002-C2-013",
        "scope": "public local environments; split seed 20261022; dev/holdout action seeds 7/31/73; max 80 requests; SDK RESET after GAME_OVER",
        "public_environment_count": len(games),
        "candidate_rule": "after existing color UCB, prefer untried same-color cells with at least one orthogonal same-color neighbor; fallback to all remaining same-color cells",
        "one_factor_boundary": "only ACTION6 coordinate subset changes; Action/color UCB, reward, lifecycle, HDS, runtime, Notebook, and kernel source are unchanged",
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
        default=ROOT / "出力/ARC3-RUN-002-local/C2-013-action6-same-color-neighbors.json",
    )
    args = parser.parse_args()
    result = run_experiment(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
