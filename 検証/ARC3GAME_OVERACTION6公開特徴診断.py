"""ACTION6後のGAME_OVER直前に見える公開特徴を匿名集計する。"""

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
import ARC3ACTION6座標特徴診断 as feature_helper  # noqa: E402
from 接続.観測駆動探索Action import 観測駆動探索方針  # noqa: E402

_SEEDS = (7, 31, 73)
_OUTCOMES = ("game_over", "level_progress", "level_decrease", "no_op", "board_change")
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


def _classify_outcome(after_state: str, level_delta: int, changed_cells: int) -> str:
    if after_state == "GAME_OVER":
        return "game_over"
    if level_delta > 0:
        return "level_progress"
    if level_delta < 0:
        return "level_decrease"
    if changed_cells == 0:
        return "no_op"
    return "board_change"


def _empty_bucket() -> dict[str, int]:
    return {"action6_responses": 0, **{outcome: 0 for outcome in _OUTCOMES}}


def _empty_aggregate() -> dict[str, int]:
    return {key: 0 for key in _COUNTERS} | {"games": 0}


def _baseline_expected(seed: int) -> dict[str, int]:
    path = ROOT / "出力/ARC3-RUN-002-local" / f"C2-003-after-dev-seed-{seed}.json"
    artifact = json.loads(path.read_text(encoding="utf-8"))
    aggregate = artifact["aggregate"]["exploration"]
    return {key: int(aggregate[key]) for key in _COUNTERS}


def run_diagnostic(output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite diagnostic output: {output}")

    games = runner._load_games(ROOT / "入力/Kaggle/environment_files")
    if len(games) != 25:
        raise RuntimeError(f"Expected 25 public environments, found {len(games)}")
    split = list(games)
    random.Random(20261022).shuffle(split)
    development = split[:5]

    original_record = 観測駆動探索方針.応答を記録する
    current_seed = [""]
    feature_counts: dict[str, dict[str, dict[str, dict[str, int]]]] = {}

    def instrumented_record(self, before, action, after):
        response = original_record(self, before, action, after)
        if action.作用番号 != 6:
            return response

        features = feature_helper._cell_features(
            before.最新盤面,
            action.引数["x"],
            action.引数["y"],
        )
        outcome = _classify_outcome(
            after.状態,
            after.完了レベル数 - before.完了レベル数,
            int(response["可視変化セル数"]),
        )
        seed_counts = feature_counts.setdefault(current_seed[0], {})
        for feature, bucket in features.items():
            counts = seed_counts.setdefault(feature, {}).setdefault(bucket, _empty_bucket())
            counts["action6_responses"] += 1
            counts[outcome] += 1
        return response

    観測駆動探索方針.応答を記録する = instrumented_record
    by_seed: dict[str, Any] = {}
    try:
        for seed in _SEEDS:
            seed_key = str(seed)
            current_seed[0] = seed_key
            aggregate = _empty_aggregate()
            for metadata, metadata_path in development:
                game = runner._run_game(
                    metadata,
                    metadata_path,
                    "exploration",
                    seed=seed,
                    max_actions=80,
                    retry_game_over=True,
                )
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
                if game["actions"] != len(game["action_responses"]):
                    raise RuntimeError("action response count differs from evaluator actions")

            expected = _baseline_expected(seed)
            baseline_matches = {key: aggregate[key] == value for key, value in expected.items()}
            by_seed[seed_key] = {
                "baseline_expected": expected,
                "current": aggregate,
                "baseline_matches": baseline_matches,
                "action6_feature_counts": feature_counts.get(seed_key, {}),
            }
    finally:
        観測駆動探索方針.応答を記録する = original_record

    result = {
        "evaluation": "ARC3-RUN-002-C2-015",
        "scope": "fixed development split: 5 public environments, seeds 7/31/73, current policy, max 80 requests, SDK RESET after GAME_OVER",
        "split_seed": 20261022,
        "public_environment_count": len(games),
        "development_environment_count": len(development),
        "condition": "previous: unmodified candidate-v4-equivalent local exploration policy",
        "outcome_priority": [
            "game_over",
            "level_progress",
            "level_decrease",
            "no_op",
            "board_change",
        ],
        "outcome_definition": "GAME_OVER state first; otherwise completed-level delta; otherwise visible latest-board changed-cell count",
        "feature_definitions": {
            "selected_color_frequency": "same public-board frequency buckets as C2-011",
            "same_color_neighbors_4": "same four-neighbor buckets as C2-011",
            "relative_center_distance": "same normalized center-distance buckets as C2-011",
        },
        "all_baselines_match_C2-003": all(
            all(seed_result["baseline_matches"].values()) for seed_result in by_seed.values()
        ),
        "by_seed": by_seed,
        "interpretation_boundary": "anonymous observational aggregates only; no action, reward, HDS, or runtime change; no causal, safety, or score claim",
        "source_sha256": {
            "diagnostic_runner": _sha256(Path(__file__)),
            "feature_helper": _sha256(Path(feature_helper.__file__)),
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
        default=ROOT / "出力/ARC3-RUN-002-local/C2-015-action6-game-over-features.json",
    )
    args = parser.parse_args()
    result = run_diagnostic(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
