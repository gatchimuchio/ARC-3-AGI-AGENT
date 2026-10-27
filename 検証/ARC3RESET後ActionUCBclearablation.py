"""GAME_OVER後RESET時にAction/color UCB統計だけをclearする隔離paired ablation。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "検証"))

import ARC3探索Actionローカル評価 as 評価器  # noqa: E402
from 接続.観測駆動探索Action import 観測駆動探索方針  # noqa: E402

_SEEDS = (7, 31, 73)
_CONDITIONS = ("previous", "current")
_COUNTERS = (
    "actions",
    "levels_completed",
    "wins",
    "no_op_actions",
    "game_over_events",
    "reset_actions",
    "reset_stat_clears",
    "illegal_action_attempts",
    "duplicate_observation_steps",
    "policy_holds",
)
_OUTPUT = ROOT / "出力/ARC3-RUN-003-local/C2-040-reset-action-ucb-clear-verified.json"
_ACTIVE_CLEAR_COUNTER: list[int] | None = None


class _RESET後Action統計clear方針(観測駆動探索方針):
    """GAME_OVER後RESETの次のゲームAction前にUCB統計だけを初期化する。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._awaiting_post_reset_decision = False

    def 選ぶ(self, 現在):
        if 現在.状態 == "GAME_OVER":
            action = super().選ぶ(現在)
            self._awaiting_post_reset_decision = action is not None and action.作用番号 == 0
            return action

        if self._awaiting_post_reset_decision and 現在.状態 == "NOT_FINISHED":
            self._回数.clear()
            self._報酬合計.clear()
            self._総作用数 = 0
            self._色回数.clear()
            self._色報酬合計.clear()
            if _ACTIVE_CLEAR_COUNTER is not None:
                _ACTIVE_CLEAR_COUNTER[0] += 1
            self._awaiting_post_reset_decision = False
        return super().選ぶ(現在)


def _empty_aggregate() -> dict[str, int]:
    return {key: 0 for key in _COUNTERS} | {"games": 0}


def _add_result(aggregate: dict[str, int], result: dict[str, Any]) -> None:
    aggregate["games"] += 1
    aggregate["actions"] += int(result["actions"])
    aggregate["levels_completed"] += int(result["levels_completed"])
    aggregate["wins"] += int(result["final_state"] == "WIN")
    aggregate["no_op_actions"] += int(result["no_op_actions"])
    aggregate["game_over_events"] += int(result["game_over_events"])
    aggregate["reset_actions"] += int(result["reset_actions"])
    aggregate["reset_stat_clears"] += int(result.get("reset_stat_clears", 0))
    aggregate["illegal_action_attempts"] += int(result["illegal_action_attempts"])
    aggregate["duplicate_observation_steps"] += int(result["duplicate_observation_steps"])
    aggregate["policy_holds"] += int(result["stop_reason"] == "exploration_hold")
    if result["actions"] != len(result["action_responses"]):
        raise RuntimeError("Action数と公開応答記録数が一致しない")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _public_input_hash(root: Path) -> tuple[int, str]:
    hashes = sorted(_sha256(path) for path in root.rglob("*") if path.is_file())
    return len(hashes), hashlib.sha256("\n".join(hashes).encode("ascii")).hexdigest()


def _source_hashes() -> dict[str, str]:
    paths = {
        "evaluator": Path(__file__),
        "targeted_test": ROOT / "検証/test_ARC3RESET後ActionUCBclearablation.py",
        "local_policy_evaluator": ROOT / "検証/ARC3探索Actionローカル評価.py",
        "policy": ROOT / "接続/観測駆動探索Action.py",
    }
    return {name: _sha256(path) for name, path in paths.items()}


def _same_start(previous: dict[str, Any], current: dict[str, Any]) -> bool:
    return all(
        previous[key] == current[key]
        for key in (
            "initial_state",
            "initial_levels_completed",
            "initial_available_actions",
            "initial_board",
        )
    )


def run(output: Path, environment_dir: Path) -> dict[str, Any]:
    global _ACTIVE_CLEAR_COUNTER
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite diagnostic output: {output}")

    games = 評価器._load_games(environment_dir)
    split = list(games)
    random.Random(20261022).shuffle(split)
    development = split[:5]
    if len(development) != 5:
        raise RuntimeError("fixed development split does not contain five environments")

    aggregates = {
        condition: {str(seed): _empty_aggregate() for seed in _SEEDS} for condition in _CONDITIONS
    }
    same_start_counts = {str(seed): 0 for seed in _SEEDS}
    paired_run_counts = {str(seed): 0 for seed in _SEEDS}
    previous_policy = 評価器.観測駆動探索方針
    started = time.perf_counter()

    try:
        for seed in _SEEDS:
            seed_key = str(seed)
            for metadata, metadata_path in development:
                pair: dict[str, dict[str, Any]] = {}
                for condition in _CONDITIONS:
                    評価器.観測駆動探索方針 = (
                        previous_policy if condition == "previous" else _RESET後Action統計clear方針
                    )
                    _ACTIVE_CLEAR_COUNTER = [0]
                    result = 評価器._run_game(
                        metadata,
                        metadata_path,
                        "exploration",
                        seed=seed,
                        policy_seed=seed,
                        max_actions=80,
                        retry_game_over=True,
                    )
                    result["reset_stat_clears"] = _ACTIVE_CLEAR_COUNTER[0]
                    pair[condition] = result
                    _add_result(aggregates[condition][seed_key], result)

                paired_run_counts[seed_key] += 1
                same_start_counts[seed_key] += int(_same_start(pair["previous"], pair["current"]))
    finally:
        評価器.観測駆動探索方針 = previous_policy
        _ACTIVE_CLEAR_COUNTER = None

    deltas = {
        str(seed): {
            key: aggregates["current"][str(seed)][key] - aggregates["previous"][str(seed)][key]
            for key in _COUNTERS
        }
        for seed in _SEEDS
    }
    seed_checks = {
        str(seed): {
            "paired_starts_match": (
                same_start_counts[str(seed)] == paired_run_counts[str(seed)] == len(development)
            ),
            "levels_not_lower": deltas[str(seed)]["levels_completed"] >= 0,
            "wins_not_lower": deltas[str(seed)]["wins"] >= 0,
            "game_over_not_higher": deltas[str(seed)]["game_over_events"] <= 0,
            "no_op_not_higher": deltas[str(seed)]["no_op_actions"] <= 0,
            "reset_clear_count_valid": (
                aggregates["current"][str(seed)]["reset_stat_clears"]
                == aggregates["current"][str(seed)]["reset_actions"]
            ),
            "legal_lifecycle_no_hold_or_duplicate": all(
                aggregates["current"][str(seed)][key] == 0
                for key in (
                    "illegal_action_attempts",
                    "duplicate_observation_steps",
                    "policy_holds",
                )
            ),
        }
        for seed in _SEEDS
    }
    all_checks = all(all(checks.values()) for checks in seed_checks.values())
    no_op_reduced_multiple_seeds = sum(
        deltas[str(seed)]["no_op_actions"] < 0 for seed in _SEEDS
    ) >= 2 and all(deltas[str(seed)]["no_op_actions"] <= 0 for seed in _SEEDS)
    measured_improvement = (
        sum(deltas[str(seed)]["levels_completed"] for seed in _SEEDS) > 0
        or sum(deltas[str(seed)]["wins"] for seed in _SEEDS) > 0
        or no_op_reduced_multiple_seeds
    )
    accepted = all_checks and measured_improvement
    input_count, input_hash = _public_input_hash(environment_dir)
    report = {
        "指示ID": "ARC3-RUN-003-C2-040",
        "評価": "public_local_post_reset_action_color_ucb_clear_ablation",
        "split": "development",
        "split_seed": 20261022,
        "environments_per_seed": len(development),
        "environment_seeds": list(_SEEDS),
        "max_actions_per_run": 80,
        "retry_game_over": True,
        "conditions": {
            "previous": "existing action and Action 6 color UCB statistics retained after RESET",
            "current": "clear action/color UCB counts and reward sums before first post-RESET game action",
        },
        "previous": aggregates["previous"],
        "current": aggregates["current"],
        "delta": deltas,
        "paired_start_match_counts": same_start_counts,
        "paired_run_counts": paired_run_counts,
        "acceptance_checks": seed_checks,
        "aggregate_acceptance": {
            "all_seed_safety_gates": all_checks,
            "no_op_reduced_at_least_two_seeds_without_regression": no_op_reduced_multiple_seeds,
            "measured_improvement": measured_improvement,
        },
        "decision": "accept_for_separate_C3_test" if accepted else "reject",
        "public_input": {"file_count": input_count, "content_set_sha256": input_hash},
        "source_sha256": _source_hashes(),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8")
    output.write_bytes(raw)
    return {
        "output": str(output),
        "output_sha256": hashlib.sha256(raw).hexdigest(),
        "summary": report,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--environment-dir", type=Path, default=ROOT / "入力/Kaggle/environment_files"
    )
    parser.add_argument("--output", type=Path, default=_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.environment_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
