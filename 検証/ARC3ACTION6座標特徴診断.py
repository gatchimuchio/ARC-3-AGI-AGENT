"""固定dev環境でACTION6選択座標の公開特徴だけを匿名集計する。"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "検証"))

import ARC3探索Actionローカル評価 as runner  # noqa: E402
from 接続.観測駆動探索Action import 観測駆動探索方針  # noqa: E402

_SEEDS = (7, 31, 73)
_OUTCOMES = ("no_op", "board_change", "level_progress", "level_decrease")


def _cell_features(board: tuple[tuple[int, ...], ...], x: int, y: int) -> dict[str, str]:
    height = len(board)
    width = len(board[0]) if height else 0
    if (
        not width
        or any(len(row) != width for row in board)
        or not (0 <= x < width and 0 <= y < height)
    ):
        raise ValueError("selected coordinate is outside a rectangular public board")

    color = board[y][x]
    counts: dict[int, int] = {}
    for row in board:
        for value in row:
            counts[value] = counts.get(value, 0) + 1
    frequency = counts[color] / (height * width)
    if counts[color] == max(counts.values()):
        color_bucket = "dominant"
    elif frequency < 0.10:
        color_bucket = "rare_lt_10pct"
    else:
        color_bucket = "middle_10_to_50pct"

    same_neighbors = sum(
        1
        for dx, dy in ((-1, 0), (1, 0), (0, -1), (0, 1))
        if 0 <= x + dx < width and 0 <= y + dy < height and board[y + dy][x + dx] == color
    )
    neighbor_bucket = "0"
    if same_neighbors in (1, 2):
        neighbor_bucket = "1_2"
    elif same_neighbors in (3, 4):
        neighbor_bucket = "3_4"

    center_x = (width - 1) / 2
    center_y = (height - 1) / 2
    max_distance = math.hypot(center_x, center_y)
    distance = math.hypot(x - center_x, y - center_y)
    relative_distance = 0.0 if max_distance == 0 else distance / max_distance
    if relative_distance <= 1 / 3:
        center_bucket = "central"
    elif relative_distance <= 2 / 3:
        center_bucket = "middle"
    else:
        center_bucket = "outer"

    return {
        "selected_color_frequency": color_bucket,
        "same_color_neighbors_4": neighbor_bucket,
        "relative_center_distance": center_bucket,
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _new_cell() -> dict[str, int]:
    return {"action6_responses": 0, **{outcome: 0 for outcome in _OUTCOMES}}


def _baseline_expected(seed: int) -> dict[str, int]:
    path = ROOT / "出力/ARC3-RUN-002-local" / f"C2-003-after-dev-seed-{seed}.json"
    artifact = json.loads(path.read_text(encoding="utf-8"))
    aggregate = artifact["aggregate"]["exploration"]
    keys = (
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
    return {key: int(aggregate[key]) for key in keys}


def run_audit(output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite diagnostic output: {output}")
    games = runner._load_games(ROOT / "入力/Kaggle/environment_files")
    split = list(games)
    random.Random(20261022).shuffle(split)
    development = split[:5]

    original_record = 観測駆動探索方針.応答を記録する
    current_seed = [""]
    per_seed_counts: dict[str, dict[str, dict[str, int]]] = {}

    def instrumented_record(self, before, action, after):
        response = original_record(self, before, action, after)
        if action.作用番号 != 6:
            return response

        features = _cell_features(
            before.最新盤面,
            action.引数["x"],
            action.引数["y"],
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

        seed_counts = per_seed_counts.setdefault(current_seed[0], {})
        for feature, bucket in features.items():
            feature_bucket = seed_counts.setdefault(feature, {}).setdefault(bucket, _new_cell())
            feature_bucket["action6_responses"] += 1
            feature_bucket[outcome] += 1
        return response

    観測駆動探索方針.応答を記録する = instrumented_record
    by_seed: dict[str, Any] = {}
    try:
        for seed in _SEEDS:
            seed_key = str(seed)
            current_seed[0] = seed_key
            runs = []
            aggregate = {
                "games": 0,
                "actions": 0,
                "levels_completed": 0,
                "wins": 0,
                "no_op_actions": 0,
                "game_over_events": 0,
                "reset_actions": 0,
                "illegal_action_attempts": 0,
                "duplicate_observation_steps": 0,
                "policy_holds": 0,
            }
            for metadata, metadata_path in development:
                game = runner._run_game(
                    metadata,
                    metadata_path,
                    "exploration",
                    seed=seed,
                    max_actions=80,
                    retry_game_over=True,
                )
                runs.append(game)
                aggregate["games"] += 1
                aggregate["actions"] += int(game["actions"])
                aggregate["levels_completed"] += int(game["levels_completed"])
                aggregate["wins"] += int(game["final_state"] == "WIN")
                aggregate["no_op_actions"] += int(game["no_op_actions"])
                aggregate["game_over_events"] += int(game["game_over_events"])
                aggregate["reset_actions"] += int(game["reset_actions"])
                aggregate["illegal_action_attempts"] += int(game["illegal_action_attempts"])
                aggregate["duplicate_observation_steps"] += int(game["duplicate_observation_steps"])
                aggregate["policy_holds"] += int(game["stop_reason"] == "exploration_hold")

            expected = _baseline_expected(seed)
            matches = {key: aggregate[key] == value for key, value in expected.items()}
            by_seed[seed_key] = {
                "baseline_expected": expected,
                "current": aggregate,
                "baseline_matches": matches,
                "action6_feature_counts": per_seed_counts.get(seed_key, {}),
            }
            for game in runs:
                if game["actions"] != len(game["action_responses"]):
                    raise RuntimeError("action response count differs from evaluator actions")
    finally:
        観測駆動探索方針.応答を記録する = original_record

    result = {
        "evaluation": "ARC3-RUN-002-C2-011",
        "scope": "fixed development split: 5 public environments, seeds 7/31/73, current policy, max 80 requests, SDK RESET after GAME_OVER",
        "split_seed": 20261022,
        "public_environment_count": len(games),
        "development_environment_count": len(development),
        "outcome_definition": "level_progress if completed level delta > 0; level_decrease if below 0; else board_change if latest-board changed-cell count > 0; else no_op",
        "feature_definitions": {
            "selected_color_frequency": "dominant if selected visible color has maximal board frequency; rare_lt_10pct if its board fraction is below 10%; otherwise middle_10_to_50pct",
            "same_color_neighbors_4": "count of matching up/down/left/right neighbors bucketed as 0, 1_2, or 3_4",
            "relative_center_distance": "selected cell distance from board center divided by the farthest corner distance, bucketed central <= 1/3, middle <= 2/3, outer > 2/3",
        },
        "all_baselines_match_C2-003": all(
            all(seed_result["baseline_matches"].values()) for seed_result in by_seed.values()
        ),
        "by_seed": by_seed,
        "interpretation_boundary": "pre-action public features are observational; no feature is used to select actions and no causal or score claim is made",
        "source_sha256": {
            "audit_runner": _sha256(Path(__file__)),
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
        default=ROOT / "出力/ARC3-RUN-002-local/C2-011-action6-coordinate-features.json",
    )
    args = parser.parse_args()
    result = run_audit(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
