"""同一公開盤面での離散Action reward meanを使う隔離paired ablation。"""

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
    "illegal_action_attempts",
    "duplicate_observation_steps",
    "policy_holds",
)
_OUTPUT = ROOT / "出力/ARC3-RUN-003-local/C2-038-board-action-context.json"


class _同盤Action報酬文脈方針(観測駆動探索方針):
    """反復盤面だけ同盤面Actionの報酬平均をUCB exploitationへ使う。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._盤面Action報酬: dict[tuple[tuple[int, ...], ...], dict[int, tuple[int, float]]] = {}

    def 選ぶ(self, 現在):
        if 現在.状態 != "NOT_FINISHED":
            return super().選ぶ(現在)

        local = self._盤面Action報酬.get(現在.最新盤面)
        if not local:
            return super().選ぶ(現在)

        global_rewards = self._報酬合計
        contextual_rewards = global_rewards.copy()
        for action_id, (count, reward_sum) in local.items():
            global_count = self._回数.get(action_id, 0)
            if count < 1 or global_count < count:
                raise RuntimeError("盤面Action統計がglobal Action統計と矛盾する")
            contextual_rewards[action_id] = (reward_sum / count) * global_count

        self._報酬合計 = contextual_rewards
        try:
            return super().選ぶ(現在)
        finally:
            self._報酬合計 = global_rewards

    def 応答を記録する(self, 作用前, action, 作用後):
        receipt = super().応答を記録する(作用前, action, 作用後)
        if action.作用番号 == 6:
            return receipt

        state_actions = self._盤面Action報酬.setdefault(作用前.最新盤面, {})
        count, reward_sum = state_actions.get(action.作用番号, (0, 0.0))
        state_actions[action.作用番号] = (
            count + 1,
            reward_sum + float(receipt["公開応答報酬"]),
        )
        return receipt


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
        "targeted_test": ROOT / "検証/test_ARC3stateAction報酬contextablation.py",
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
                        previous_policy if condition == "previous" else _同盤Action報酬文脈方針
                    )
                    result = 評価器._run_game(
                        metadata,
                        metadata_path,
                        "exploration",
                        seed=seed,
                        policy_seed=seed,
                        max_actions=80,
                        retry_game_over=True,
                    )
                    pair[condition] = result
                    _add_result(aggregates[condition][seed_key], result)

                paired_run_counts[seed_key] += 1
                same_start_counts[seed_key] += int(_same_start(pair["previous"], pair["current"]))
    finally:
        評価器.観測駆動探索方針 = previous_policy

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
    no_op_reduced_multiple_seeds = (
        sum(deltas[str(seed)]["no_op_actions"] < 0 for seed in _SEEDS) >= 2
    )
    has_measured_improvement = (
        sum(deltas[str(seed)]["levels_completed"] for seed in _SEEDS) > 0
        or sum(deltas[str(seed)]["wins"] for seed in _SEEDS) > 0
        or (
            no_op_reduced_multiple_seeds
            and all(deltas[str(seed)]["no_op_actions"] <= 0 for seed in _SEEDS)
        )
    )
    accepted = all_checks and has_measured_improvement
    input_count, input_hash = _public_input_hash(environment_dir)
    report = {
        "指示ID": "ARC3-RUN-003-C2-038",
        "評価": "public_local_same_board_discrete_action_reward_context_ablation",
        "split": "development",
        "split_seed": 20261022,
        "environments_per_seed": len(development),
        "environment_seeds": list(_SEEDS),
        "max_actions_per_run": 80,
        "retry_game_over": True,
        "conditions": {
            "previous": "existing global action UCB reward mean",
            "current": "same-board prior reward mean for known discrete actions; global UCB bonus and unknown states unchanged",
        },
        "previous": aggregates["previous"],
        "current": aggregates["current"],
        "delta": deltas,
        "paired_start_match_counts": same_start_counts,
        "paired_run_counts": paired_run_counts,
        "acceptance_checks": seed_checks,
        "aggregate_acceptance": {
            "all_seed_safety_gates": all_checks,
            "no_op_reduced_at_least_two_seeds": no_op_reduced_multiple_seeds,
            "measured_improvement": has_measured_improvement,
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
