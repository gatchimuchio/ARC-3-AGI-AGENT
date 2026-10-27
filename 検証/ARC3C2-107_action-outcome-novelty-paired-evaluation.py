"""C2-107: reward new public response categories per legal action."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
from typing import Any

from ARC3公開RHAE評価 import _スコアを計算する
from ARC3探索Actionローカル評価 import ROOT, _load_games, _run_game
from 接続.観測駆動探索Action import 観測駆動探索方針


SPLIT_SEED = 20261022
POLICY_SEEDS = (7, 31, 73)
MAX_ACTIONS = 80
NOVEL_OUTCOME_BONUS = 0.5


class _Action結果新規性UCB(観測駆動探索方針):
    """Add one bounded reward when a discrete action yields a new public result type."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._既知結果種: dict[int, set[tuple[str, bool, int]]] = {}

    @staticmethod
    def _変化量bucket(セル数: int) -> int:
        if セル数 == 0:
            return 0
        if セル数 <= 4:
            return 1
        if セル数 <= 16:
            return 2
        return 3

    def 応答を記録する(self, 作用前: Any, action: Any, 作用後: Any) -> dict[str, Any]:
        response = super().応答を記録する(作用前, action, 作用後)
        bonus = 0.0
        if action.作用番号 != 6:
            signature = (
                作用後.状態,
                作用後.完了レベル数 > 作用前.完了レベル数,
                self._変化量bucket(response["可視変化セル数"]),
            )
            known = self._既知結果種.setdefault(action.作用番号, set())
            if signature not in known:
                known.add(signature)
                bonus = NOVEL_OUTCOME_BONUS
                self._報酬合計[action.作用番号] += bonus
        response["Action結果新規性bonus"] = bonus
        return response


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
    keys = ("initial_state", "initial_levels_completed", "initial_available_actions", "initial_board")
    return all(previous[key] == current[key] for key in keys)


def _signature(record: dict[str, Any]) -> tuple[Any, ...]:
    return (
        record["action_id"],
        tuple(sorted(record["data"].items())),
        record["level_delta"],
        record["after_state"],
    )


def _evaluate(stage: str, output_path: Path) -> dict[str, Any]:
    games = _load_games(ROOT / "入力/Kaggle/environment_files")
    shuffled = list(games)
    random.Random(SPLIT_SEED).shuffle(shuffled)
    selected = shuffled[:5] if stage == "dev" else shuffled[5:25]

    pairs: list[dict[str, Any]] = []
    matched_starts = contract_errors = illegal_actions = duplicate_observations = 0
    bonus_applications = 0

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
                policy_type_override=_Action結果新規性UCB,
                **shared,
            )
            same_start = _same_start(previous, candidate)
            matched_starts += int(same_start)
            bonus_applications += sum(
                record.get("policy_response", {}).get("Action結果新規性bonus", 0.0) > 0
                for record in candidate["action_responses"]
            )

            prior_trace = previous["action_responses"]
            candidate_trace = candidate["action_responses"]
            first_difference = next(
                (
                    index
                    for index, (prior, current) in enumerate(zip(prior_trace, candidate_trace))
                    if _signature(prior) != _signature(current)
                ),
                None,
            )
            if first_difference is None and len(prior_trace) != len(candidate_trace):
                first_difference = min(len(prior_trace), len(candidate_trace))

            prior_score, prior_levels, _ = _スコアを計算する(
                metadata.get("baseline_actions", []), previous
            )
            candidate_score, candidate_levels, _ = _スコアを計算する(
                metadata.get("baseline_actions", []), candidate
            )
            if (
                prior_levels != previous["levels_completed"]
                or candidate_levels != candidate["levels_completed"]
            ):
                contract_errors += 1
            illegal_actions += previous["illegal_action_attempts"] + candidate[
                "illegal_action_attempts"
            ]
            duplicate_observations += previous["duplicate_observation_steps"] + candidate[
                "duplicate_observation_steps"
            ]
            pairs.append(
                {
                    "seed": seed,
                    "same_public_start": same_start,
                    "first_policy_divergence_action_index": first_difference,
                    "previous_score": prior_score,
                    "candidate_score": candidate_score,
                    "score_delta": candidate_score - prior_score,
                    "previous_levels": previous["levels_completed"],
                    "candidate_levels": candidate["levels_completed"],
                    "levels_delta": candidate["levels_completed"] - previous["levels_completed"],
                    "previous_win": previous["final_state"] == "WIN",
                    "candidate_win": candidate["final_state"] == "WIN",
                    "previous_actions": previous["actions"],
                    "candidate_actions": candidate["actions"],
                    "previous_noops": previous["no_op_actions"],
                    "candidate_noops": candidate["no_op_actions"],
                }
            )
            if len(pairs) % 15 == 0:
                print(f"PROGRESS stage={stage} pairs={len(pairs)}/{len(selected) * 3}", flush=True)

    deltas = [pair["score_delta"] for pair in pairs]
    level_deltas = [pair["levels_delta"] for pair in pairs]
    mean_delta = sum(deltas) / len(deltas)
    prior_mean = sum(pair["previous_score"] for pair in pairs) / len(pairs)
    candidate_mean = sum(pair["candidate_score"] for pair in pairs) / len(pairs)
    diverged_pairs = sum(pair["first_policy_divergence_action_index"] is not None for pair in pairs)
    dev_gate = (
        mean_delta >= 0.01
        and all(delta >= 0 for delta in level_deltas)
        and matched_starts == len(pairs)
        and contract_errors == 0
        and illegal_actions == 0
        and duplicate_observations == 0
        and bonus_applications > 0
        and diverged_pairs > 0
    )

    report = {
        "run_id": "C2-107",
        "stage": stage,
        "split_seed": SPLIT_SEED,
        "policy_seeds": list(POLICY_SEEDS),
        "episodes_per_condition": len(pairs),
        "max_actions_per_episode": MAX_ACTIONS,
        "candidate": {
            "policy": "per-action novelty bonus for public outcome categories",
            "novel_outcome_bonus": NOVEL_OUTCOME_BONUS,
            "outcome_features": ["after_state", "level_progress", "visible_cell_change_bucket"],
            "coordinate_action_bonus": "none; existing per-board coordinate exploration remains active",
            "game_identifier_used_for_selection": False,
            "fixed_action_sequences_used": False,
        },
        "aggregate": {
            "previous_score_mean": prior_mean,
            "candidate_score_mean": candidate_mean,
            "score_delta_mean": mean_delta,
            "improved_pairs": sum(delta > 1e-12 for delta in deltas),
            "regressed_pairs": sum(delta < -1e-12 for delta in deltas),
            "tied_pairs": sum(abs(delta) <= 1e-12 for delta in deltas),
            "previous_levels_total": sum(pair["previous_levels"] for pair in pairs),
            "candidate_levels_total": sum(pair["candidate_levels"] for pair in pairs),
            "previous_wins": sum(pair["previous_win"] for pair in pairs),
            "candidate_wins": sum(pair["candidate_win"] for pair in pairs),
            "previous_actions_total": sum(pair["previous_actions"] for pair in pairs),
            "candidate_actions_total": sum(pair["candidate_actions"] for pair in pairs),
            "previous_noops_total": sum(pair["previous_noops"] for pair in pairs),
            "candidate_noops_total": sum(pair["candidate_noops"] for pair in pairs),
            "action_divergent_pairs": diverged_pairs,
            "novel_outcome_bonus_applications": bonus_applications,
            "matched_starts": matched_starts,
            "scorecard_contract_errors": contract_errors,
            "illegal_action_attempts": illegal_actions,
            "duplicate_observation_steps": duplicate_observations,
        },
        "dev_gate": {
            "minimum_mean_score_delta": 0.01,
            "requires_no_level_regressions": True,
            "requires_all_paired_starts": True,
            "requires_zero_contract_errors_illegal_duplicates": True,
            "requires_bonus_application_and_policy_divergence": True,
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
    output = args.output or ROOT / "出力/ARC3-RUN-003-local/C2-107" / (
        f"action-outcome-novelty-{args.stage}.json"
    )
    report = _evaluate(args.stage, output)
    print(
        json.dumps(
            {
                "stage": report["stage"],
                "episodes_per_condition": report["episodes_per_condition"],
                "aggregate": report["aggregate"],
                "gate_passed": report["dev_gate"]["passed"],
                "output": str(output),
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
