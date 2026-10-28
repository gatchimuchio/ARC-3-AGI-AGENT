"""Screen resetting public action-value counts at completed-level boundaries."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import runpy
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BASELINE_RUNNER = ROOT / "検証/ARC3C2-109_ACTION6-family-HDS-paired-evaluation.py"
CONTROL_EVIDENCE = ROOT / "運用/証拠/ARC26-UNIFIED/ARC3-C2-111-reset-after-game-over-20261027T215948Z.json"
OUTPUT = ROOT / "出力/ARC3-RUN-003-local/C2-124/level-boundary-bandit-reset-screen.json"
MAX_ACTIONS = 80


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _start_hash(run: dict[str, Any]) -> str:
    start = {
        key: run[key]
        for key in (
            "initial_state",
            "initial_levels_completed",
            "initial_available_actions",
            "initial_board",
        )
    }
    payload = json.dumps(start, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _level_boundary_reset_policy(base_policy: type) -> type:
    class LevelBoundaryResetPolicy(base_policy):
        """Start fresh action-value statistics after public level progress."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self._level_boundary_resets = 0
            self._action_observations_discarded = 0

        def 応答を記録する(self, 作用前: Any, action: Any, 作用後: Any) -> dict[str, Any]:
            response = super().応答を記録する(作用前, action, 作用後)
            if 作用後.完了レベル数 > 作用前.完了レベル数:
                self._level_boundary_resets += 1
                self._action_observations_discarded += sum(self._回数.values())
                self._回数.clear()
                self._報酬合計.clear()
                self._色回数.clear()
                self._色報酬合計.clear()
                self._総作用数 = 0
            return response

        def 統計(self) -> dict[str, Any]:
            stats = super().統計()
            stats["level_boundary_bandit_reset"] = {
                "level_boundary_resets": self._level_boundary_resets,
                "action_observations_discarded": self._action_observations_discarded,
                "reset_scope": ["action_visits", "action_rewards", "coordinate_color_visits", "coordinate_color_rewards", "total_action_count"],
                "board_novelty_and_tried_coordinate_memory_retained": True,
                "game_identifier_used_for_selection": False,
            }
            return stats

    return LevelBoundaryResetPolicy


def _trace_signature(record: dict[str, Any]) -> tuple[Any, ...]:
    return (
        record["action_id"],
        tuple(sorted(record["data"].items())),
        record["level_delta"],
        record["after_state"],
    )


def evaluate() -> dict[str, Any]:
    started = time.perf_counter()
    experiment = runpy.run_path(str(BASELINE_RUNNER))
    control = json.loads(CONTROL_EVIDENCE.read_text(encoding="utf-8"))
    run_game = experiment["_run"].__globals__["_run_game"]
    score_game = experiment["_スコアを計算する"]
    policy_type = _level_boundary_reset_policy(experiment["_CurrentHDSRankingPolicy"])
    control_rows = control["results"]["pairs"]
    screening_seed = min(int(pair["seed"]) for pair in control_rows)
    control_rows = [pair for pair in control_rows if int(pair["seed"]) == screening_seed]

    pairs: list[dict[str, Any]] = []
    for control_pair in control_rows:
        seed = int(control_pair["seed"])
        game_id = str(control_pair["game_id"])
        metadata_path = (
            ROOT
            / "入力/Kaggle/environment_files"
            / game_id.split("-")[0]
            / game_id.split("-")[1]
            / "metadata.json"
        )
        metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        run = run_game(
            metadata,
            metadata_path,
            "exploration",
            seed=seed,
            policy_seed=seed,
            max_actions=MAX_ACTIONS,
            retry_game_over=True,
            exploration_coefficient=0.8,
            coordinate_color_exploration_coefficient=None,
            visible_change_coefficient=0.25,
            level_progress_reward=4.0,
            policy_type_override=policy_type,
        )
        score, levels, level_details = score_game(metadata.get("baseline_actions", []), run)
        candidate_trace = run["action_responses"]
        previous_trace = control_pair["candidate"]["action_trace"]
        common_length = min(len(previous_trace), len(candidate_trace))
        divergence_positions = [
            index
            for index in range(common_length)
            if _trace_signature(previous_trace[index]) != _trace_signature(candidate_trace[index])
        ]
        if len(previous_trace) != len(candidate_trace) and not divergence_positions:
            divergence_positions.append(common_length)
        candidate = {
            "start_sha256": _start_hash(run),
            "score": score,
            "levels": levels,
            "actions": run["actions"],
            "gameplay_actions": run["gameplay_actions"],
            "reset_actions": run["reset_actions"],
            "attempts": run["attempts"],
            "game_over_events": run["game_over_events"],
            "no_op_actions": run["no_op_actions"],
            "illegal_action_attempts": run["illegal_action_attempts"],
            "final_state": run["final_state"],
            "stop_reason": run["stop_reason"],
            "level_details": level_details,
            "policy_action_stats": run.get("policy_action_stats", {}),
            "first_policy_divergence_action_index": divergence_positions[0] if divergence_positions else None,
        }
        previous = control_pair["candidate"]
        pairs.append(
            {
                "seed": seed,
                "game_id": game_id,
                "matched_start": candidate["start_sha256"] == previous["start_sha256"],
                "previous": {
                    key: previous[key]
                    for key in (
                        "start_sha256",
                        "score",
                        "levels",
                        "actions",
                        "gameplay_actions",
                        "reset_actions",
                        "attempts",
                        "game_over_events",
                        "no_op_actions",
                        "illegal_action_attempts",
                        "final_state",
                        "stop_reason",
                        "level_details",
                    )
                },
                "candidate": candidate,
                "score_delta": candidate["score"] - previous["score"],
                "levels_delta": candidate["levels"] - previous["levels"],
                "actions_delta": candidate["actions"] - previous["actions"],
            }
        )

    deltas = [pair["score_delta"] for pair in pairs]
    return {
        "control_experiment": "C2-111 legal RESET with retained online exploration statistics",
        "control_evidence": CONTROL_EVIDENCE.relative_to(ROOT).as_posix(),
        "control_evidence_sha256": _sha256(CONTROL_EVIDENCE),
        "policy_seeds": [screening_seed],
        "dev_games": [pair["game_id"] for pair in control_rows],
        "max_actions_per_game_including_resets": MAX_ACTIONS,
        "candidate": "When a public level-completion transition occurs, clear action and coordinate-color visit/reward statistics and restart the UCB count for the next level. Retain board novelty and tried-coordinate memory; no game ID or hidden state is used.",
        "decision_gate": {
            "minimum_mean_rhae_delta": 0.01,
            "require_nonnegative_levels_and_wins": True,
            "screen_only_cannot_promote": True,
            "full_15_pair_rerun_required_after_positive_screen": True,
        },
        "summary": {
            "pairs": len(pairs),
            "matched_start_pairs": sum(pair["matched_start"] for pair in pairs),
            "mean_previous": sum(pair["previous"]["score"] for pair in pairs) / len(pairs),
            "mean_candidate": sum(pair["candidate"]["score"] for pair in pairs) / len(pairs),
            "mean_delta": sum(deltas) / len(deltas),
            "positive_pairs": sum(delta > 0 for delta in deltas),
            "negative_pairs": sum(delta < 0 for delta in deltas),
            "tied_pairs": sum(delta == 0 for delta in deltas),
            "levels_delta": sum(pair["levels_delta"] for pair in pairs),
            "wins_delta": sum(
                int(pair["candidate"]["final_state"] == "WIN")
                - int(pair["previous"]["final_state"] == "WIN")
                for pair in pairs
            ),
            "actions_previous": sum(pair["previous"]["actions"] for pair in pairs),
            "actions_candidate": sum(pair["candidate"]["actions"] for pair in pairs),
            "noops_previous": sum(pair["previous"]["no_op_actions"] for pair in pairs),
            "noops_candidate": sum(pair["candidate"]["no_op_actions"] for pair in pairs),
            "game_over_events_previous": sum(pair["previous"]["game_over_events"] for pair in pairs),
            "game_over_events_candidate": sum(pair["candidate"]["game_over_events"] for pair in pairs),
            "illegal_actions": sum(pair["candidate"]["illegal_action_attempts"] for pair in pairs),
            "level_boundary_resets": sum(
                pair["candidate"]["policy_action_stats"]
                .get("level_boundary_bandit_reset", {})
                .get("level_boundary_resets", 0)
                for pair in pairs
            ),
            "action_observations_discarded": sum(
                pair["candidate"]["policy_action_stats"]
                .get("level_boundary_bandit_reset", {})
                .get("action_observations_discarded", 0)
                for pair in pairs
            ),
            "action_divergent_pairs": sum(
                pair["candidate"]["first_policy_divergence_action_index"] is not None
                for pair in pairs
            ),
            "wall_seconds": round(time.perf_counter() - started, 3),
        },
        "evaluation_scope": "5_game_screen_at_one_seed",
        "screening_seed": screening_seed,
        "pairs": pairs,
        "runner_file": Path(__file__).relative_to(ROOT).as_posix(),
        "runner_sha256": _sha256(Path(__file__)),
        "baseline_runner_file": BASELINE_RUNNER.relative_to(ROOT).as_posix(),
        "baseline_runner_sha256": _sha256(BASELINE_RUNNER),
    }


def main() -> None:
    if OUTPUT.exists():
        raise SystemExit(f"Refusing to overwrite existing output: {OUTPUT}")
    payload = json.dumps(evaluate(), ensure_ascii=False, indent=2)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(payload + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "sha256": _sha256(OUTPUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
