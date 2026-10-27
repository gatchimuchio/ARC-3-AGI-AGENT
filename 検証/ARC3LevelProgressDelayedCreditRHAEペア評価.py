"""Paired public RHAE test of a small, level-local delayed-credit update."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
import time
from typing import Any

from ARC3公開RHAE評価 import _スコアを計算する
import ARC3探索Actionローカル評価 as local_eval

ROOT = Path(__file__).resolve().parents[1]
SPLIT_SEED = 20261022


class _遅延信用方針(local_eval.観測駆動探索方針):
    """Credit half of a level-progress reward to the four preceding choices."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._直前作用: list[tuple[int, int | None]] = []

    def 応答を記録する(self, before, action, after):
        color = self._選択座標色
        result = super().応答を記録する(before, action, after)
        if result["完了レベル増分"] > 0:
            recent = self._直前作用[-4:]
            weights = [0.5**index for index in range(len(recent))]
            weight_sum = sum(weights)
            for (action_number, prior_color), weight in zip(reversed(recent), weights):
                credit = 2.0 * weight / weight_sum
                self._報酬合計[action_number] = self._報酬合計.get(action_number, 0.0) + credit
                if action_number == 6 and prior_color is not None:
                    self._色報酬合計[prior_color] = self._色報酬合計.get(prior_color, 0.0) + credit
            self._直前作用.clear()
        elif after.状態 in ("GAME_OVER", "WIN"):
            self._直前作用.clear()
        else:
            self._直前作用.append((action.作用番号, color))
            self._直前作用 = self._直前作用[-4:]
        return result


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


def _signature(record: dict[str, Any]) -> tuple[Any, ...]:
    return (
        record["action_id"],
        tuple(sorted(record["data"].items())),
        record["level_delta"],
        record["after_state"],
    )


def _prefix_matches_until_progress(
    previous: list[dict[str, Any]], candidate: list[dict[str, Any]]
) -> bool:
    limit = min(len(previous), len(candidate))
    for index in range(limit):
        old = previous[index]
        new = candidate[index]
        if _signature(old) != _signature(new):
            return False
        if old["level_delta"] > 0 or new["level_delta"] > 0:
            return True
    return len(previous) == len(candidate)


def _run_pair(games, seeds: list[int]) -> dict[str, Any]:
    previous_rows: list[tuple[int, float, dict[str, Any]]] = []
    candidate_rows: list[tuple[int, float, dict[str, Any]]] = []
    start_matches = pre_intervention_prefix_matches = 0
    contract_errors = illegal_actions = duplicate_observations = 0

    original_policy = local_eval.観測駆動探索方針
    try:
        for condition in ("previous", "candidate"):
            local_eval.観測駆動探索方針 = (
                original_policy if condition == "previous" else _遅延信用方針
            )
            rows = previous_rows if condition == "previous" else candidate_rows
            for seed in seeds:
                for index, (metadata, metadata_path) in enumerate(games, start=1):
                    run = local_eval._run_game(
                        metadata,
                        metadata_path,
                        "exploration",
                        seed=seed,
                        policy_seed=seed,
                        max_actions=80,
                        retry_game_over=True,
                        exploration_coefficient=0.8,
                        coordinate_color_exploration_coefficient=None,
                        visible_change_coefficient=0.25,
                        level_progress_reward=4.0,
                    )
                    baseline = metadata.get("baseline_actions")
                    if (
                        not isinstance(baseline, list)
                        or not baseline
                        or not all(type(value) is int and value > 0 for value in baseline)
                    ):
                        raise RuntimeError("invalid public baseline_actions metadata")
                    score, scored_levels, _ = _スコアを計算する(baseline, run)
                    contract_errors += int(scored_levels != run["levels_completed"])
                    illegal_actions += int(run["illegal_action_attempts"])
                    duplicate_observations += int(run["duplicate_observation_steps"])
                    rows.append((seed, score, run))
                    if index % 5 == 0:
                        print(f"PROGRESS {condition} seed={seed} episodes={index}/5", flush=True)
    finally:
        local_eval.観測駆動探索方針 = original_policy

    # The episode order is fixed by the split and retained only for pairing in memory.
    summary_by_seed = []
    all_score_deltas: list[float] = []
    all_level_deltas: list[int] = []
    all_noop_deltas: list[int] = []
    all_game_over_deltas: list[int] = []
    for seed in seeds:
        previous_seed = [row for row in previous_rows if row[0] == seed]
        candidate_seed = [row for row in candidate_rows if row[0] == seed]
        if len(previous_seed) != len(games) or len(candidate_seed) != len(games):
            raise RuntimeError("paired evaluation did not finish all episodes")
        seed_deltas = []
        for index, (previous_item, candidate_item) in enumerate(
            zip(previous_seed, candidate_seed), start=1
        ):
            _, previous_score, previous = previous_item
            _, candidate_score, candidate = candidate_item
            start_matches += int(_same_start(previous, candidate))
            previous_trace = previous["action_responses"]
            candidate_trace = candidate["action_responses"]
            pre_intervention_prefix_matches += int(
                _prefix_matches_until_progress(previous_trace, candidate_trace)
            )
            score_delta = candidate_score - previous_score
            level_delta = candidate["levels_completed"] - previous["levels_completed"]
            noop_delta = candidate["no_op_actions"] - previous["no_op_actions"]
            game_over_delta = candidate["game_over_events"] - previous["game_over_events"]
            seed_deltas.append(score_delta)
            all_score_deltas.append(score_delta)
            all_level_deltas.append(level_delta)
            all_noop_deltas.append(noop_delta)
            all_game_over_deltas.append(game_over_delta)
        summary_by_seed.append(
            {
                "seed": seed,
                "episodes": len(games),
                "score_delta_mean": round(sum(seed_deltas) / len(seed_deltas), 9),
                "previous_levels": sum(row[2]["levels_completed"] for row in previous_seed),
                "candidate_levels": sum(row[2]["levels_completed"] for row in candidate_seed),
                "levels_delta": sum(row[2]["levels_completed"] for row in candidate_seed)
                - sum(row[2]["levels_completed"] for row in previous_seed),
                "previous_noops": sum(row[2]["no_op_actions"] for row in previous_seed),
                "candidate_noops": sum(row[2]["no_op_actions"] for row in candidate_seed),
                "previous_game_over": sum(row[2]["game_over_events"] for row in previous_seed),
                "candidate_game_over": sum(row[2]["game_over_events"] for row in candidate_seed),
            }
        )

    improvements = sum(value > 1e-9 for value in all_score_deltas)
    regressions = sum(value < -1e-9 for value in all_score_deltas)
    ties = sum(abs(value) <= 1e-9 for value in all_score_deltas)
    return {
        "episodes_per_condition": len(previous_rows),
        "previous_score_mean": round(sum(row[1] for row in previous_rows) / len(previous_rows), 9),
        "candidate_score_mean": round(
            sum(row[1] for row in candidate_rows) / len(candidate_rows), 9
        ),
        "score_delta_mean": round(sum(all_score_deltas) / len(all_score_deltas), 9),
        "score_improvements": improvements,
        "score_regressions": regressions,
        "score_ties": ties,
        "levels_delta_total": sum(all_level_deltas),
        "noops_delta_total": sum(all_noop_deltas),
        "game_over_delta_total": sum(all_game_over_deltas),
        "start_matches": start_matches,
        "pre_intervention_prefix_matches": pre_intervention_prefix_matches,
        "contract_errors": contract_errors,
        "illegal_actions": illegal_actions,
        "duplicate_observations": duplicate_observations,
        "by_seed": summary_by_seed,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("dev", "holdout"), default="dev")
    parser.add_argument("--seeds", type=int, nargs="+", default=[7, 31, 73])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    all_games = local_eval._load_games(ROOT / "入力/Kaggle/environment_files")
    if len(all_games) != 25:
        parser.error("expected the 25 public ARC3 environments")
    split = list(all_games)
    random.Random(SPLIT_SEED).shuffle(split)
    selected = split[:5] if args.stage == "dev" else split[5:25]
    started = time.perf_counter()
    summary = _run_pair(selected, args.seeds)
    payload = {
        "schema": "arc3-delayed-level-credit-paired-rhae.v1",
        "stage": args.stage,
        "split_seed": SPLIT_SEED,
        "environment_seed_and_policy_seed": args.seeds,
        "evaluation": "public offline paired local policy scorecard; no HDS query or update",
        "previous": {"max_actions": 80, "delayed_credit": False},
        "candidate": {
            "max_actions": 80,
            "credit_budget": 2.0,
            "prior_action_window": 4,
            "geometric_decay": 0.5,
            "delayed_credit": True,
        },
        "comparison": summary,
        "agent_source_sha256": hashlib.sha256(
            (ROOT / "接続/観測駆動探索Action.py").read_bytes()
        ).hexdigest(),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
        "official_submission_made": False,
        "notebook_or_kernel_changed": False,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
