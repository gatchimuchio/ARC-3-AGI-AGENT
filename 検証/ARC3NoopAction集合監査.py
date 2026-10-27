"""公開Action集合の変化がno-op報酬に含まれるかを読み取り専用で監査する。"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import random
from typing import Any, Mapping

import ARC3探索Actionローカル評価 as evaluation
from 接続.観測駆動探索Action import 観測駆動探索方針


ROOT = Path(__file__).resolve().parents[1]
_捕捉応答: list[dict[str, Any]] = []


def 応答を分類する(応答: Mapping[str, Any]) -> dict[str, bool]:
    """評価runnerが捕捉した公開差分からno-op条件と状態変化を分類する。"""
    no_op = 応答.get("changed_cells") == 0 and 応答.get("level_delta") == 0
    action_set_changed = 応答.get("before_actions") != 応答.get("after_actions")
    state_changed = 応答.get("before_state") != 応答.get("after_state")
    return {
        "no_op": no_op,
        "action_set_changed": action_set_changed,
        "state_changed": state_changed,
        "same_state_action_set_change": no_op and action_set_changed and not state_changed,
        "full_reset_changed": 応答.get("before_full_reset") != 応答.get("after_full_reset"),
        "frame_count_changed": 応答.get("before_frame_count") != 応答.get("after_frame_count"),
    }


def 集計する(応答群: list[Mapping[str, Any]]) -> dict[str, int]:
    counts = {
        "responses": len(応答群),
        "no_op_actions": 0,
        "no_op_with_action_set_change": 0,
        "no_op_with_action_set_change_same_state": 0,
        "no_op_with_state_change": 0,
        "no_op_with_full_reset_change": 0,
        "no_op_with_frame_count_change": 0,
    }
    for response in 応答群:
        features = 応答を分類する(response)
        counts["no_op_actions"] += int(features["no_op"])
        counts["no_op_with_action_set_change"] += int(
            features["no_op"] and features["action_set_changed"]
        )
        counts["no_op_with_action_set_change_same_state"] += int(
            features["same_state_action_set_change"]
        )
        counts["no_op_with_state_change"] += int(features["no_op"] and features["state_changed"])
        counts["no_op_with_full_reset_change"] += int(
            features["no_op"] and features["full_reset_changed"]
        )
        counts["no_op_with_frame_count_change"] += int(
            features["no_op"] and features["frame_count_changed"]
        )
    return counts


class _応答監査方針(観測駆動探索方針):
    def 応答を記録する(self, 作用前, action, 作用後):
        _捕捉応答.append(
            {
                "before_state": 作用前.状態,
                "after_state": 作用後.状態,
                "before_actions": tuple(sorted(作用前.作用可能番号)),
                "after_actions": tuple(sorted(作用後.作用可能番号)),
                "before_full_reset": 作用前.全初期化,
                "after_full_reset": 作用後.全初期化,
                "before_frame_count": len(作用前.盤面列),
                "after_frame_count": len(作用後.盤面列),
                "changed_cells": evaluation._盤面差分(作用前, 作用後),
                "level_delta": max(0, 作用後.完了レベル数 - 作用前.完了レベル数),
            }
        )
        return super().応答を記録する(作用前, action, 作用後)


def _run(seed: int, split_seed: int, max_actions: int, environment_dir: Path) -> dict[str, Any]:
    games = evaluation._load_games(environment_dir)
    dev = list(games)
    random.Random(split_seed).shuffle(dev)
    dev = dev[:5]

    evaluation.観測駆動探索方針 = _応答監査方針
    per_run = []
    for metadata, metadata_path in dev:
        _捕捉応答.clear()
        result = evaluation._run_game(
            metadata,
            metadata_path,
            "exploration",
            seed=seed,
            max_actions=max_actions,
            retry_game_over=True,
        )
        random_start = evaluation._run_game(
            metadata,
            metadata_path,
            "random",
            seed=seed,
            max_actions=max_actions,
            retry_game_over=True,
        )
        per_run.append(
            {
                "same_public_start": (
                    result["initial_board"] == random_start["initial_board"]
                    and result["initial_available_actions"]
                    == random_start["initial_available_actions"]
                ),
                "actions": result["actions"],
                "levels_completed": result["levels_completed"],
                "no_op_actions": result["no_op_actions"],
                "game_over_events": result["game_over_events"],
                "reset_actions": result["reset_actions"],
                "illegal_action_attempts": result["illegal_action_attempts"],
                "duplicate_observation_steps": result["duplicate_observation_steps"],
                "stop_reason": result["stop_reason"],
                **集計する(_捕捉応答),
            }
        )
    aggregate = {
        key: sum(run[key] for run in per_run)
        for key in (
            "actions",
            "levels_completed",
            "no_op_actions",
            "game_over_events",
            "reset_actions",
            "illegal_action_attempts",
            "duplicate_observation_steps",
            "responses",
            "no_op_with_action_set_change",
            "no_op_with_action_set_change_same_state",
            "no_op_with_state_change",
            "no_op_with_full_reset_change",
            "no_op_with_frame_count_change",
        )
    }
    aggregate["same_public_starts"] = sum(int(run["same_public_start"]) for run in per_run)
    return {"seed": seed, "aggregate": aggregate, "runs": per_run}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--environment-dir",
        type=Path,
        default=ROOT / "入力/Kaggle/environment_files",
    )
    parser.add_argument("--split-seed", type=int, default=20261022)
    parser.add_argument("--seeds", type=int, nargs="+", default=[7, 31, 73])
    parser.add_argument("--max-actions", type=int, default=80)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "出力/ARC3-RUN-002-local/C2-018-noop-action-set-audit.json",
    )
    args = parser.parse_args()
    if args.max_actions < 1 or not args.seeds:
        parser.error("--max-actionsと--seedsは正の値が必要です")

    results = [
        _run(seed, args.split_seed, args.max_actions, args.environment_dir) for seed in args.seeds
    ]
    report = {
        "evaluation": "public_local_noop_action_set_audit",
        "stage": "dev",
        "split_seed": args.split_seed,
        "dev_games": 5,
        "max_actions_per_game": args.max_actions,
        "retry_game_over": True,
        "policy_changed": False,
        "results_by_seed": results,
        "aggregate": {
            key: sum(result["aggregate"][key] for result in results)
            for key in results[0]["aggregate"]
        },
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(
        json.dumps(
            {"output": str(args.output), "aggregate": report["aggregate"]},
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
