"""中間Frame差分no-op罰のdev-only一要因ablation。"""

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

_SEEDS = (7, 31, 73)
_CONDITIONS = ("previous", "candidate")
_AGG_KEYS = (
    "games",
    "actions",
    "gameplay_actions",
    "reset_actions",
    "game_over_events",
    "levels_completed",
    "wins",
    "game_over",
    "no_op_actions",
    "policy_holds",
    "illegal_action_attempts",
    "duplicate_observation_steps",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _empty_totals() -> dict[str, int]:
    return {key: 0 for key in _AGG_KEYS}


def _summarize_game(
    target: dict[str, int], action_buckets: dict[str, dict[str, int]], game: dict[str, Any]
) -> None:
    target["games"] += 1
    target["actions"] += int(game["actions"])
    target["gameplay_actions"] += int(game["gameplay_actions"])
    target["reset_actions"] += int(game["reset_actions"])
    target["game_over_events"] += int(game["game_over_events"])
    target["levels_completed"] += int(game["levels_completed"])
    target["wins"] += int(game["final_state"] == "WIN")
    target["game_over"] += int(game["final_state"] == "GAME_OVER")
    target["policy_holds"] += int(game["stop_reason"] == "exploration_hold")
    target["illegal_action_attempts"] += int(game["illegal_action_attempts"])
    target["duplicate_observation_steps"] += int(game["duplicate_observation_steps"])

    for event in game["action_responses"]:
        name = "RESET" if event["lifecycle_action"] else f"ACTION{event['action_id']}"
        bucket = action_buckets.setdefault(
            name,
            {
                "actions": 0,
                "no_op_actions": 0,
                "level_progress_responses": 0,
                "levels_completed": 0,
            },
        )
        bucket["actions"] += 1
        is_noop = (
            not event["lifecycle_action"]
            and event["changed_cells"] == 0
            and event["level_delta"] == 0
        )
        bucket["no_op_actions"] += int(is_noop)
        bucket["level_progress_responses"] += int(event["level_delta"] > 0)
        bucket["levels_completed"] += max(0, int(event["level_delta"]))
        target["no_op_actions"] += int(is_noop)


def _baseline_expected(seed: int) -> dict[str, int]:
    path = ROOT / "出力/ARC3-RUN-002-local" / f"C2-003-after-dev-seed-{seed}.json"
    artifact = json.loads(path.read_text(encoding="utf-8"))
    result = artifact["aggregate"]["exploration"]
    return {key: int(result[key]) for key in _AGG_KEYS if key in result}


def run_ablation(output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite experiment output: {output}")
    games = runner._load_games(ROOT / "入力/Kaggle/environment_files")
    split = list(games)
    random.Random(20261022).shuffle(split)
    development = split[:5]
    by_seed: dict[str, Any] = {}
    by_seed_condition_and_action: dict[str, dict[str, dict[str, dict[str, int]]]] = {}

    for seed in _SEEDS:
        seed_key = str(seed)
        totals = {condition: _empty_totals() for condition in _CONDITIONS}
        action_counts = {condition: {} for condition in _CONDITIONS}
        same_public_starts = 0
        for metadata, metadata_path in development:
            previous = runner._run_game(
                metadata,
                metadata_path,
                "exploration",
                seed=seed,
                max_actions=80,
                retry_game_over=True,
            )
            candidate = runner._run_game(
                metadata,
                metadata_path,
                "exploration",
                seed=seed,
                max_actions=80,
                retry_game_over=True,
                exempt_intermediate_frame_noop_penalty=True,
            )
            same_start = (
                previous["initial_board"] == candidate["initial_board"]
                and previous["initial_available_actions"] == candidate["initial_available_actions"]
                and previous["initial_state"] == candidate["initial_state"]
                and previous["initial_levels_completed"] == candidate["initial_levels_completed"]
            )
            same_public_starts += int(same_start)
            _summarize_game(totals["previous"], action_counts["previous"], previous)
            _summarize_game(totals["candidate"], action_counts["candidate"], candidate)

        expected = _baseline_expected(seed)
        baseline_matches = {key: totals["previous"][key] == expected[key] for key in expected}
        delta = {
            key: totals["candidate"][key] - totals["previous"][key]
            for key in _AGG_KEYS
            if key != "games"
        }
        by_seed[seed_key] = {
            "public_start_matches": same_public_starts,
            "baseline_artifact_expected": expected,
            "previous": totals["previous"],
            "candidate": totals["candidate"],
            "delta": delta,
            "previous_matches_C2-003": baseline_matches,
        }
        by_seed_condition_and_action[seed_key] = action_counts

    result = {
        "evaluation": "ARC3-RUN-002-C1-005",
        "scope": "fixed development split: 5 public environments, seeds 7/31/73, max 80 requests, SDK RESET after GAME_OVER",
        "split_seed": 20261022,
        "public_environment_count": len(games),
        "development_environment_count": len(development),
        "conditions": {
            "previous": "candidate v4 reward; no-op penalty -1.0",
            "candidate": "cancel only the -1.0 no-op penalty when an intermediate grid differs from the unchanged final grid and clamped level delta is zero",
        },
        "all_public_starts_match": all(
            entry["public_start_matches"] == len(development) for entry in by_seed.values()
        ),
        "all_previous_baselines_match_C2-003": all(
            all(entry["previous_matches_C2-003"].values()) for entry in by_seed.values()
        ),
        "by_seed": by_seed,
        "by_seed_condition_and_action": by_seed_condition_and_action,
        "interpretation_boundary": "development-only local ablation; no causal claim outside this controlled comparison and no official score inference",
        "source_sha256": {
            "ablation_runner": _sha256(Path(__file__)),
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
        default=ROOT / "出力/ARC3-RUN-002-local/C1-005-intermediate-noop-ablation.json",
    )
    args = parser.parse_args()
    result = run_ablation(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
