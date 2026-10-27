"""Screen a generic online terminal-loss penalty against the C2-111 control."""

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
OUTPUT = ROOT / "出力/ARC3-RUN-003-local/C2-115/terminal-loss-penalty-screen.json"
MAX_ACTIONS = 80
TERMINAL_LOSS_REWARD = -4.0


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


def _terminal_loss_policy(base_policy: type) -> type:
    class TerminalLossPolicy(base_policy):
        """Assign a bounded negative learning reward when an action ends a run."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self._terminal_loss_events = 0

        def 応答を記録する(self, 作用前: Any, action: Any, 作用後: Any) -> dict[str, Any]:
            response = super().応答を記録する(作用前, action, 作用後)
            if 作用前.状態 != "NOT_FINISHED" or 作用後.状態 != "GAME_OVER":
                return response

            previous_reward = float(response.get("公開応答報酬", 0.0))
            reward_delta = TERMINAL_LOSS_REWARD - previous_reward
            self._報酬合計[action.作用番号] += reward_delta
            color = response.get("座標可視色")
            if color is not None and color in self._色報酬合計:
                self._色報酬合計[color] += reward_delta
            response["公開応答報酬"] = TERMINAL_LOSS_REWARD
            self._terminal_loss_events += 1
            return response

        def 統計(self) -> dict[str, Any]:
            stats = super().統計()
            stats["terminal_loss_penalty"] = {
                "reward": TERMINAL_LOSS_REWARD,
                "events": self._terminal_loss_events,
            }
            return stats

    return TerminalLossPolicy


def evaluate() -> dict[str, Any]:
    started = time.perf_counter()
    experiment = runpy.run_path(str(BASELINE_RUNNER))
    control = json.loads(CONTROL_EVIDENCE.read_text(encoding="utf-8"))
    run_game = experiment["_run"].__globals__["_run_game"]
    score_game = experiment["_スコアを計算する"]
    policy_type = _terminal_loss_policy(experiment["_CurrentHDSRankingPolicy"])
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
    mean_delta = sum(deltas) / len(deltas)
    levels_delta = sum(pair["levels_delta"] for pair in pairs)
    wins_delta = sum(
        int(pair["candidate"]["final_state"] == "WIN")
        - int(pair["previous"]["final_state"] == "WIN")
        for pair in pairs
    )
    return {
        "control_experiment": "C2-111 legal RESET with retained online exploration statistics",
        "control_evidence": CONTROL_EVIDENCE.relative_to(ROOT).as_posix(),
        "control_evidence_sha256": _sha256(CONTROL_EVIDENCE),
        "policy_seeds": [screening_seed],
        "dev_games": [pair["game_id"] for pair in control_rows],
        "max_actions_per_game_including_resets": MAX_ACTIONS,
        "candidate": (
            "Keep the existing legal RESET/UCB/HDS and visible-change behavior; replace an action's "
            "ordinary learning reward with -4.0 if that action produces public GAME_OVER."
        ),
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
            "mean_delta": mean_delta,
            "positive_pairs": sum(delta > 0 for delta in deltas),
            "negative_pairs": sum(delta < 0 for delta in deltas),
            "tied_pairs": sum(delta == 0 for delta in deltas),
            "levels_delta": levels_delta,
            "wins_delta": wins_delta,
            "actions_previous": sum(pair["previous"]["actions"] for pair in pairs),
            "actions_candidate": sum(pair["candidate"]["actions"] for pair in pairs),
            "noops_previous": sum(pair["previous"]["no_op_actions"] for pair in pairs),
            "noops_candidate": sum(pair["candidate"]["no_op_actions"] for pair in pairs),
            "game_over_events_previous": sum(pair["previous"]["game_over_events"] for pair in pairs),
            "game_over_events_candidate": sum(pair["candidate"]["game_over_events"] for pair in pairs),
            "terminal_loss_penalty_events": sum(
                pair["candidate"]["policy_action_stats"].get("terminal_loss_penalty", {}).get("events", 0)
                for pair in pairs
            ),
            "illegal_actions": sum(pair["candidate"]["illegal_action_attempts"] for pair in pairs),
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
