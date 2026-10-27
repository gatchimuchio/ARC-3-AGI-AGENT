"""C2-106: same-board legal action novelty as a paired public-game experiment."""

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


class _盤面条件付きActionUCB(観測駆動探索方針):
    """Repeat a previously seen public state with contextual UCB over legal actions."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._状態訪問数: dict[tuple[Any, ...], int] = {}
        self._状態作用訪問数: dict[tuple[tuple[Any, ...], int], int] = {}

    @staticmethod
    def _状態キー(現在: Any) -> tuple[Any, ...] | None:
        if not 現在.最新盤面:
            return None
        合法 = tuple(sorted(a for a in 現在.作用可能番号 if 1 <= a <= 7))
        return (現在.状態, 現在.完了レベル数, 合法, 現在.最新盤面)

    def _追加行動価値(self, 現在: Any, 作用番号: int) -> float:
        # ACTION6 already tracks untried coordinates per visible board.
        if 作用番号 == 6:
            return 0.0
        state = self._状態キー(現在)
        if state is None:
            return 0.0
        state_visits = self._状態訪問数.get(state, 0)
        if state_visits == 0:
            return 0.0
        action_visits = self._状態作用訪問数.get((state, 作用番号), 0)
        return self._探索係数 * math.sqrt(
            math.log(state_visits + 1) / (action_visits + 1)
        )

    def 応答を記録する(self, 作用前: Any, action: Any, 作用後: Any) -> dict[str, Any]:
        state = self._状態キー(作用前)
        response = super().応答を記録する(作用前, action, 作用後)
        if state is not None:
            self._状態訪問数[state] = self._状態訪問数.get(state, 0) + 1
            if action.作用番号 != 6:
                key = (state, action.作用番号)
                self._状態作用訪問数[key] = self._状態作用訪問数.get(key, 0) + 1
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
    start_matches = 0
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
                policy_type_override=_盤面条件付きActionUCB,
                **shared,
            )
            same_start = _same_start(previous, candidate)
            start_matches += int(same_start)

            previous_trace = previous["action_responses"]
            candidate_trace = candidate["action_responses"]
            common_length = min(len(previous_trace), len(candidate_trace))
            divergence_positions = [
                index
                for index in range(common_length)
                if _signature(previous_trace[index]) != _signature(candidate_trace[index])
            ]
            if len(previous_trace) != len(candidate_trace) and not divergence_positions:
                divergence_positions.append(common_length)

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
            illegal_attempts += previous["illegal_action_attempts"] + candidate[
                "illegal_action_attempts"
            ]
            duplicate_observations += previous["duplicate_observation_steps"] + candidate[
                "duplicate_observation_steps"
            ]

            pairs.append(
                {
                    "seed": seed,
                    "same_public_start": same_start,
                    "first_policy_divergence_action_index": (
                        divergence_positions[0] if divergence_positions else None
                    ),
                    "previous_score": previous_score,
                    "candidate_score": candidate_score,
                    "score_delta": candidate_score - previous_score,
                    "previous_levels": previous["levels_completed"],
                    "candidate_levels": candidate["levels_completed"],
                    "levels_delta": candidate["levels_completed"] - previous["levels_completed"],
                    "previous_win": previous["final_state"] == "WIN",
                    "candidate_win": candidate["final_state"] == "WIN",
                    "previous_actions": previous["actions"],
                    "candidate_actions": candidate["actions"],
                    "previous_noops": previous["no_op_actions"],
                    "candidate_noops": candidate["no_op_actions"],
                    "previous_game_over_events": previous["game_over_events"],
                    "candidate_game_over_events": candidate["game_over_events"],
                }
            )
            if len(pairs) % 15 == 0:
                print(f"PROGRESS stage={stage} pairs={len(pairs)}/{len(selected) * 3}", flush=True)

    deltas = [pair["score_delta"] for pair in pairs]
    level_deltas = [pair["levels_delta"] for pair in pairs]
    mean_delta = sum(deltas) / len(deltas)
    candidate_mean = sum(pair["candidate_score"] for pair in pairs) / len(pairs)
    previous_mean = sum(pair["previous_score"] for pair in pairs) / len(pairs)
    divergent_pairs = sum(
        pair["first_policy_divergence_action_index"] is not None for pair in pairs
    )
    dev_gate = (
        mean_delta >= 0.01
        and all(delta >= 0 for delta in level_deltas)
        and start_matches == len(pairs)
        and scorecard_errors == 0
        and illegal_attempts == 0
        and duplicate_observations == 0
        and divergent_pairs > 0
    )

    report = {
        "run_id": "C2-106",
        "stage": stage,
        "split_seed": SPLIT_SEED,
        "policy_seeds": list(POLICY_SEEDS),
        "episodes_per_condition": len(pairs),
        "max_actions_per_episode": MAX_ACTIONS,
        "candidate": {
            "policy": "state-action contextual UCB over repeated public observations",
            "state_key": ["state", "completed_levels", "legal_action_set", "visible_board"],
            "coordinate_action_bonus": "none; existing per-board coordinate exploration remains active",
            "contextual_coefficient": "same configured exploration_coefficient as baseline UCB",
            "game_identifier_used_for_selection": False,
            "fixed_action_sequences_used": False,
        },
        "aggregate": {
            "previous_score_mean": previous_mean,
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
            "action_divergent_pairs": divergent_pairs,
            "matched_starts": start_matches,
            "scorecard_contract_errors": scorecard_errors,
            "illegal_action_attempts": illegal_attempts,
            "duplicate_observation_steps": duplicate_observations,
        },
        "dev_gate": {
            "minimum_mean_score_delta": 0.01,
            "requires_no_level_regressions": True,
            "requires_all_paired_starts": True,
            "requires_zero_contract_errors_illegal_duplicates": True,
            "requires_action_divergence": True,
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
    output = args.output or ROOT / "出力/ARC3-RUN-003-local/C2-106" / (
        f"state-action-context-ucb-{args.stage}.json"
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
