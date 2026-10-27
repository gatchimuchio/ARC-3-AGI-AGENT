"""Paired local RHAE scorecard for 80-vs-160 request exploration horizons."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
import time
from typing import Any

from ARC3公開RHAE評価 import _スコアを計算する
from ARC3探索Actionローカル評価 import _load_games, _run_game

ROOT = Path(__file__).resolve().parents[1]
SPLIT_SEED = 20261022
BASELINE_ACTIONS = 80
CANDIDATE_ACTIONS = 160


def _入力manifest_hash(games: list[tuple[dict[str, Any], Path]]) -> str:
    digest = hashlib.sha256()
    for _, metadata_path in games:
        relative = metadata_path.relative_to(ROOT).as_posix().encode("utf-8")
        content = metadata_path.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(hashlib.sha256(content).digest())
    return digest.hexdigest()


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


def _action_signature(record: dict[str, Any]) -> tuple[Any, ...]:
    return (
        record["action_id"],
        tuple(sorted(record["data"].items())),
        record["level_delta"],
        record["after_state"],
    )


def _summarize(games: list[tuple[dict[str, Any], Path]], seeds: list[int]) -> dict[str, Any]:
    rows: list[dict[str, int | float]] = []
    seed_summary: list[dict[str, int | float]] = []
    prefix_matches = 0
    start_matches = 0
    contract_errors = illegal = duplicate = 0

    for seed in seeds:
        previous_scores: list[float] = []
        current_scores: list[float] = []
        previous_levels = current_levels = 0
        previous_wins = current_wins = 0
        previous_actions = current_actions = 0
        previous_noops = current_noops = 0
        previous_game_over = current_game_over = 0
        previous_resets = current_resets = 0

        for game_number, (metadata, metadata_path) in enumerate(games, start=1):
            shared = {
                "seed": seed,
                "policy_seed": seed,
                "retry_game_over": True,
                "exploration_coefficient": 0.8,
                "coordinate_color_exploration_coefficient": None,
                "visible_change_coefficient": 0.25,
                "level_progress_reward": 4.0,
            }
            previous = _run_game(
                metadata,
                metadata_path,
                "exploration",
                max_actions=BASELINE_ACTIONS,
                **shared,
            )
            current = _run_game(
                metadata,
                metadata_path,
                "exploration",
                max_actions=CANDIDATE_ACTIONS,
                **shared,
            )
            start_matches += int(_same_start(previous, current))
            previous_trace = previous["action_responses"]
            current_trace = current["action_responses"]
            prefix_matches += int(
                len(current_trace) >= len(previous_trace)
                and [_action_signature(x) for x in previous_trace]
                == [_action_signature(x) for x in current_trace[: len(previous_trace)]]
            )
            metadata_baseline = metadata.get("baseline_actions")
            if (
                not isinstance(metadata_baseline, list)
                or not metadata_baseline
                or not all(type(value) is int and value > 0 for value in metadata_baseline)
            ):
                raise RuntimeError("invalid public baseline_actions metadata")
            previous_score, previous_scored_levels, _ = _スコアを計算する(
                metadata_baseline, previous
            )
            current_score, current_scored_levels, _ = _スコアを計算する(metadata_baseline, current)
            if (
                previous_scored_levels != previous["levels_completed"]
                or current_scored_levels != current["levels_completed"]
            ):
                contract_errors += 1
            illegal += int(previous["illegal_action_attempts"] + current["illegal_action_attempts"])
            duplicate += int(
                previous["duplicate_observation_steps"] + current["duplicate_observation_steps"]
            )

            previous_scores.append(previous_score)
            current_scores.append(current_score)
            previous_levels += previous["levels_completed"]
            current_levels += current["levels_completed"]
            previous_wins += int(previous["final_state"] == "WIN")
            current_wins += int(current["final_state"] == "WIN")
            previous_actions += previous["actions"]
            current_actions += current["actions"]
            previous_noops += previous["no_op_actions"]
            current_noops += current["no_op_actions"]
            previous_game_over += previous["game_over_events"]
            current_game_over += current["game_over_events"]
            previous_resets += previous["reset_actions"]
            current_resets += current["reset_actions"]

            rows.append(
                {
                    "seed": seed,
                    "score_delta": round(current_score - previous_score, 9),
                    "levels_delta": current["levels_completed"] - previous["levels_completed"],
                }
            )
            if game_number % 5 == 0:
                print(
                    f"PROGRESS seed={seed} episodes={game_number}/{len(games)}",
                    flush=True,
                )

        seed_summary.append(
            {
                "seed": seed,
                "episodes": len(games),
                "previous_score_mean": round(sum(previous_scores) / len(previous_scores), 9),
                "current_score_mean": round(sum(current_scores) / len(current_scores), 9),
                "score_delta_mean": round(
                    (sum(current_scores) - sum(previous_scores)) / len(previous_scores), 9
                ),
                "previous_levels": previous_levels,
                "current_levels": current_levels,
                "levels_delta": current_levels - previous_levels,
                "previous_wins": previous_wins,
                "current_wins": current_wins,
                "previous_actions": previous_actions,
                "current_actions": current_actions,
                "previous_noops": previous_noops,
                "current_noops": current_noops,
                "previous_game_over": previous_game_over,
                "current_game_over": current_game_over,
                "previous_resets": previous_resets,
                "current_resets": current_resets,
            }
        )

    deltas = [float(row["score_delta"]) for row in rows]
    return {
        "episodes_per_condition": len(rows),
        "previous_max_actions": BASELINE_ACTIONS,
        "candidate_max_actions": CANDIDATE_ACTIONS,
        "previous_score_mean": round(
            sum(item["previous_score_mean"] * len(games) for item in seed_summary) / len(rows),
            9,
        ),
        "candidate_score_mean": round(
            sum(item["current_score_mean"] * len(games) for item in seed_summary) / len(rows),
            9,
        ),
        "score_delta_mean": round(sum(deltas) / len(deltas), 9),
        "score_improvements": sum(delta > 1e-9 for delta in deltas),
        "score_regressions": sum(delta < -1e-9 for delta in deltas),
        "score_ties": sum(abs(delta) <= 1e-9 for delta in deltas),
        "prefix_matches": prefix_matches,
        "start_matches": start_matches,
        "contract_errors": contract_errors,
        "illegal_actions": illegal,
        "duplicate_observations": duplicate,
        "by_seed": seed_summary,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("dev", "holdout"), default="dev")
    parser.add_argument("--seeds", type=int, nargs="+", default=[7, 31, 73])
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    all_games = _load_games(ROOT / "入力/Kaggle/environment_files")
    if len(all_games) != 25:
        parser.error("expected the 25 public ARC3 environments")
    split = list(all_games)
    random.Random(SPLIT_SEED).shuffle(split)
    selected = split[:5] if args.stage == "dev" else split[5:25]
    started = time.perf_counter()
    summary = _summarize(selected, args.seeds)
    payload = {
        "schema": "arc3-action-horizon-paired-rhae.v1",
        "stage": args.stage,
        "split_seed": SPLIT_SEED,
        "environment_seed_and_policy_seed": args.seeds,
        "environment_manifest_sha256": _入力manifest_hash(all_games),
        "agent_source_sha256": hashlib.sha256(
            (ROOT / "接続/観測駆動探索Action.py").read_bytes()
        ).hexdigest(),
        "evaluation": "public offline paired local policy scorecard; no HDS query or update",
        "comparison": summary,
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
