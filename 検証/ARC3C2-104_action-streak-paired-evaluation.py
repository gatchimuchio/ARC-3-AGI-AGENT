"""C2-104 paired local scorecard for an eight-action no-progress streak cap."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
from typing import Any

from ARC3公開RHAE評価 import _スコアを計算する
from ARC3探索Actionローカル評価 import (
    ROOT,
    _load_games,
    _run_game,
    _同一Action停滞上限ablation,
)

SPLIT_SEED = 20261022
POLICY_SEEDS = (7, 31, 73)
MAX_ACTIONS = 80


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _manifest_hash(games: list[tuple[dict[str, Any], Path]]) -> str:
    digest = hashlib.sha256()
    for _, metadata_path in games:
        relative = metadata_path.relative_to(ROOT).as_posix().encode("utf-8")
        content_hash = hashlib.sha256(metadata_path.read_bytes()).digest()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(content_hash)
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


def _signature(record: dict[str, Any]) -> tuple[Any, ...]:
    return (
        record["action_id"],
        tuple(sorted(record["data"].items())),
        record["level_delta"],
        record["after_state"],
    )


def _evaluate(stage: str, output_path: Path) -> dict[str, Any]:
    all_games = _load_games(ROOT / "入力/Kaggle/environment_files")
    shuffled = list(all_games)
    random.Random(SPLIT_SEED).shuffle(shuffled)
    selected = shuffled[:5] if stage == "dev" else shuffled[5:25]

    pairs: list[dict[str, Any]] = []
    cap_positions: list[int] = []
    start_matches = prefix_matches = 0
    scorecard_errors = illegal_attempts = duplicate_observations = 0

    for seed in POLICY_SEEDS:
        for metadata, metadata_path in selected:
            shared = {
                "seed": seed,
                "policy_seed": seed,
                "max_actions": MAX_ACTIONS,
                "retry_game_over": False,
                "exploration_coefficient": 0.8,
                "coordinate_color_exploration_coefficient": None,
                "visible_change_coefficient": 0.25,
                "level_progress_reward": 4.0,
            }
            previous = _run_game(metadata, metadata_path, "exploration", **shared)
            candidate = _run_game(
                metadata,
                metadata_path,
                "exploration",
                policy_type_override=_同一Action停滞上限ablation,
                **shared,
            )
            same_start = _same_start(previous, candidate)
            start_matches += int(same_start)
            intervention_positions = candidate["policy_diagnostics"][
                "same_action_streak_cap_intervention_positions"
            ]
            cap_positions.extend(intervention_positions)
            prefix_length = (
                min(intervention_positions)
                if intervention_positions
                else min(previous["actions"], candidate["actions"])
            )
            prefix_match = (
                [_signature(item) for item in previous["action_responses"][:prefix_length]]
                == [
                    _signature(item)
                    for item in candidate["action_responses"][:prefix_length]
                ]
            )
            prefix_matches += int(prefix_match)

            previous_score, previous_levels, _ = _スコアを計算する(
                metadata.get("baseline_actions", []), previous
            )
            candidate_score, candidate_levels, _ = _スコアを計算する(
                metadata.get("baseline_actions", []), candidate
            )
            if (
                previous_levels != previous["levels_completed"]
                or candidate_levels != candidate["levels_completed"]
            ):
                scorecard_errors += 1
            illegal_attempts += (
                previous["illegal_action_attempts"] + candidate["illegal_action_attempts"]
            )
            duplicate_observations += (
                previous["duplicate_observation_steps"]
                + candidate["duplicate_observation_steps"]
            )

            pairs.append(
                {
                    "seed": seed,
                    "same_public_start": same_start,
                    "pre_intervention_action_prefix_match": prefix_match,
                    "previous_score": previous_score,
                    "candidate_score": candidate_score,
                    "score_delta": candidate_score - previous_score,
                    "previous_levels": previous["levels_completed"],
                    "candidate_levels": candidate["levels_completed"],
                    "levels_delta": candidate["levels_completed"]
                    - previous["levels_completed"],
                    "previous_win": previous["final_state"] == "WIN",
                    "candidate_win": candidate["final_state"] == "WIN",
                    "previous_actions": previous["actions"],
                    "candidate_actions": candidate["actions"],
                    "previous_noops": previous["no_op_actions"],
                    "candidate_noops": candidate["no_op_actions"],
                    "previous_game_over_events": previous["game_over_events"],
                    "candidate_game_over_events": candidate["game_over_events"],
                    "cap_interventions": len(intervention_positions),
                }
            )
            if len(pairs) % 15 == 0:
                print(f"PROGRESS stage={stage} pairs={len(pairs)}/{len(selected) * 3}", flush=True)

    deltas = [pair["score_delta"] for pair in pairs]
    level_deltas = [pair["levels_delta"] for pair in pairs]
    mean_delta = sum(deltas) / len(deltas)
    candidate_score_mean = sum(pair["candidate_score"] for pair in pairs) / len(pairs)
    previous_score_mean = sum(pair["previous_score"] for pair in pairs) / len(pairs)
    interventions = len(cap_positions)
    dev_gate = (
        mean_delta >= 0.01
        and all(delta >= 0 for delta in level_deltas)
        and all(pair["same_public_start"] for pair in pairs)
        and prefix_matches == len(pairs)
        and scorecard_errors == 0
        and illegal_attempts == 0
        and duplicate_observations == 0
        and interventions > 0
    )
    report = {
        "run_id": "C2-104",
        "stage": stage,
        "split_seed": SPLIT_SEED,
        "policy_seeds": list(POLICY_SEEDS),
        "episodes_per_condition": len(pairs),
        "max_actions_per_episode": MAX_ACTIONS,
        "candidate": {
            "policy": "same legal action streak cap after 8 no-level-progress choices",
            "only_activates_after_alternative_actions_were_tried": True,
            "cap": _同一Action停滞上限ablation._連続上限,
        },
        "aggregate": {
            "previous_score_mean": previous_score_mean,
            "candidate_score_mean": candidate_score_mean,
            "score_delta_mean": mean_delta,
            "improved_pairs": sum(delta > 1e-12 for delta in deltas),
            "regressed_pairs": sum(delta < -1e-12 for delta in deltas),
            "tied_pairs": sum(abs(delta) <= 1e-12 for delta in deltas),
            "previous_levels": sum(pair["previous_levels"] for pair in pairs),
            "candidate_levels": sum(pair["candidate_levels"] for pair in pairs),
            "levels_delta": sum(level_deltas),
            "previous_wins": sum(pair["previous_win"] for pair in pairs),
            "candidate_wins": sum(pair["candidate_win"] for pair in pairs),
            "previous_actions": sum(pair["previous_actions"] for pair in pairs),
            "candidate_actions": sum(pair["candidate_actions"] for pair in pairs),
            "previous_noops": sum(pair["previous_noops"] for pair in pairs),
            "candidate_noops": sum(pair["candidate_noops"] for pair in pairs),
            "previous_game_over_events": sum(
                pair["previous_game_over_events"] for pair in pairs
            ),
            "candidate_game_over_events": sum(
                pair["candidate_game_over_events"] for pair in pairs
            ),
            "cap_interventions": interventions,
            "start_matches": start_matches,
            "pre_intervention_prefix_matches": prefix_matches,
            "scorecard_contract_errors": scorecard_errors,
            "illegal_action_attempts": illegal_attempts,
            "duplicate_observation_steps": duplicate_observations,
        },
        "dev_gate": {
            "minimum_mean_score_delta": 0.01,
            "requires_no_level_regressions": True,
            "requires_all_paired_starts_and_prefixes": True,
            "requires_zero_contract_errors_illegal_duplicates": True,
            "requires_at_least_one_actual_intervention": True,
            "passed": dev_gate if stage == "dev" else None,
        },
        "source_sha256": {
            "pair_evaluation": _sha256(Path(__file__)),
            "local_runner": _sha256(ROOT / "検証/ARC3探索Actionローカル評価.py"),
            "agent_policy": _sha256(ROOT / "接続/観測駆動探索Action.py"),
            "rhae_evaluator": _sha256(ROOT / "検証/ARC3公開RHAE評価.py"),
            "environment_manifest": _manifest_hash(selected),
        },
        "pairs": pairs,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("dev", "holdout"), default="dev")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    output = args.output or ROOT / "運用/証拠/ARC26-UNIFIED" / (
        f"C2-104_action-streak-cap-{args.stage}.json"
    )
    report = _evaluate(args.stage, output)
    summary = {
        "stage": report["stage"],
        "episodes_per_condition": report["episodes_per_condition"],
        "aggregate": report["aggregate"],
        "gate_passed": report["dev_gate"]["passed"],
        "output": str(output),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
