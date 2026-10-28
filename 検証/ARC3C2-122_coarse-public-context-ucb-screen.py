"""Screen contextual UCB pooled across coarse, generic public-state features."""

from __future__ import annotations

import hashlib
import json
import math
from pathlib import Path
import runpy
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

BASELINE_RUNNER = ROOT / "検証/ARC3C2-109_ACTION6-family-HDS-paired-evaluation.py"
CONTROL_EVIDENCE = ROOT / "運用/証拠/ARC26-UNIFIED/ARC3-C2-111-reset-after-game-over-20261027T215948Z.json"
OUTPUT = ROOT / "出力/ARC3-RUN-003-local/C2-122/coarse-public-context-ucb-screen.json"
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


def _coarse_contextual_ucb_policy(base_policy: type) -> type:
    class CoarsePublicContextUCBPolicy(base_policy):
        """Pool exploration counts by public, non-identity board descriptors."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self._context_visits: dict[tuple[Any, ...], int] = {}
            self._context_action_visits: dict[tuple[tuple[Any, ...], int], int] = {}
            self._contextual_bonus_applications = 0
            self._recorded_context_steps = 0

        @staticmethod
        def _public_context(current: Any) -> tuple[Any, ...] | None:
            board = current.最新盤面
            if not board or current.状態 != "NOT_FINISHED":
                return None

            legal = tuple(sorted(action for action in current.作用可能番号 if 1 <= action <= 7))
            cells = [color for row in board for color in row]
            if not cells:
                return None
            color_counts: dict[int, int] = {}
            for color in cells:
                color_counts[color] = color_counts.get(color, 0) + 1
            color_count = len(color_counts)
            majority_share = max(color_counts.values()) / len(cells)
            majority_band = (
                "diffuse" if majority_share <= 1 / 3 else
                "mixed" if majority_share <= 2 / 3 else
                "dominant"
            )
            area = len(cells)
            area_band = "small" if area <= 64 else "medium" if area <= 256 else "large"
            row_count = len(board)
            column_count = max((len(row) for row in board), default=0)
            aspect = max(row_count, column_count) / max(1, min(row_count, column_count))
            aspect_band = "square" if aspect <= 1.25 else "compact" if aspect <= 2 else "elongated"
            color_count_band = 1 if color_count == 1 else 2 if color_count == 2 else 3
            return (
                current.完了レベル数,
                legal,
                color_count_band,
                majority_band,
                area_band,
                aspect_band,
            )

        def _追加行動価値(self, 現在: Any, 作用番号: int) -> float:
            # Coordinate selection already has its own board/color exploration path.
            if 作用番号 == 6:
                return 0.0
            context = self._public_context(現在)
            if context is None:
                return 0.0
            context_visits = self._context_visits.get(context, 0)
            if context_visits == 0:
                return 0.0
            action_visits = self._context_action_visits.get((context, 作用番号), 0)
            self._contextual_bonus_applications += 1
            return self._探索係数 * math.sqrt(
                math.log(context_visits + 1) / (action_visits + 1)
            )

        def 応答を記録する(self, 作用前: Any, action: Any, 作用後: Any) -> dict[str, Any]:
            context = self._public_context(作用前)
            response = super().応答を記録する(作用前, action, 作用後)
            if context is not None:
                self._recorded_context_steps += 1
                self._context_visits[context] = self._context_visits.get(context, 0) + 1
                if action.作用番号 != 6:
                    key = (context, action.作用番号)
                    self._context_action_visits[key] = self._context_action_visits.get(key, 0) + 1
            return response

        def 統計(self) -> dict[str, Any]:
            stats = super().統計()
            stats["coarse_public_context_ucb"] = {
                "context_features": [
                    "completed_levels",
                    "legal_action_set",
                    "color_count_band_1_2_3plus",
                    "majority_occupancy_band",
                    "board_area_band",
                    "board_aspect_band",
                ],
                "contexts_seen": len(self._context_visits),
                "recorded_context_steps": self._recorded_context_steps,
                "context_action_counts": sum(self._context_action_visits.values()),
                "contextual_bonus_applications": self._contextual_bonus_applications,
                "action6_context_bonus": False,
                "game_identifier_used_for_selection": False,
            }
            return stats

    return CoarsePublicContextUCBPolicy


def evaluate() -> dict[str, Any]:
    started = time.perf_counter()
    experiment = runpy.run_path(str(BASELINE_RUNNER))
    control = json.loads(CONTROL_EVIDENCE.read_text(encoding="utf-8"))
    run_game = experiment["_run"].__globals__["_run_game"]
    score_game = experiment["_スコアを計算する"]
    policy_type = _coarse_contextual_ucb_policy(experiment["_CurrentHDSRankingPolicy"])
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
    return {
        "run_id": "C2-122",
        "control_experiment": "C2-111 legal RESET with retained online exploration statistics",
        "control_evidence": CONTROL_EVIDENCE.relative_to(ROOT).as_posix(),
        "control_evidence_sha256": _sha256(CONTROL_EVIDENCE),
        "policy_seeds": [screening_seed],
        "dev_games": [pair["game_id"] for pair in control_rows],
        "max_actions_per_game_including_resets": MAX_ACTIONS,
        "candidate": "Add contextual UCB from completed levels, legal action set, color-count band, majority-occupancy band, board-area band, and board-aspect band. Contexts pool across different public boards; ACTION6 stays on its existing coordinate exploration path. No game ID or hidden state is used.",
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
            "contextual_bonus_applications": sum(
                pair["candidate"]["policy_action_stats"]
                .get("coarse_public_context_ucb", {})
                .get("contextual_bonus_applications", 0)
                for pair in pairs
            ),
            "contexts_seen_total": sum(
                pair["candidate"]["policy_action_stats"]
                .get("coarse_public_context_ucb", {})
                .get("contexts_seen", 0)
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
