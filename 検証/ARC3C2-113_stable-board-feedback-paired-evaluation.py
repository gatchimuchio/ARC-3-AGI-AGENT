"""Evaluate whether masking repeatedly alternating screen cells improves ARC3 exploration."""

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
OUTPUT = ROOT / "出力/ARC3-RUN-003-local/C2-113/stable-board-feedback-paired.json"
FULL_OUTPUT = ROOT / "出力/ARC3-RUN-003-local/C2-113/stable-board-feedback-full-15-pairs.json"
MAX_ACTIONS = 80
MAX_REMEMBERED_BOARDS = 2 * MAX_ACTIONS + 2


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


def _stable_feedback_policy(base_policy: type) -> type:
    class StableBoardFeedbackPolicy(base_policy):
        """Reduce reward from cell animations that repeatedly reverse without level progress."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self._value_history: dict[tuple[int, int], list[int]] = {}
            self._alternating_cells: set[tuple[int, int]] = set()
            self._raw_boards: list[tuple[tuple[int, ...], ...]] = []
            self._masked_boards: set[tuple[tuple[int, ...], ...]] = set()
            self._masked_cell_changes = 0
            self._raw_cell_changes = 0

        @staticmethod
        def _snapshot(board: Any) -> tuple[tuple[int, ...], ...]:
            return tuple(tuple(int(cell) for cell in row) for row in board)

        def _mask(self, board: tuple[tuple[int, ...], ...]) -> tuple[tuple[int, ...], ...]:
            return tuple(
                tuple(-1 if (y, x) in self._alternating_cells else value for x, value in enumerate(row))
                for y, row in enumerate(board)
            )

        def _remember(self, board: tuple[tuple[int, ...], ...]) -> None:
            self._raw_boards.append(board)
            if len(self._raw_boards) > MAX_REMEMBERED_BOARDS:
                self._raw_boards.pop(0)
            self._masked_boards.add(self._mask(board))

        def 選ぶ(self, 現在: Any, **kwargs: Any) -> Any:
            if 現在.状態 == "NOT_FINISHED" and 現在.最新盤面:
                self._remember(self._snapshot(現在.最新盤面))
            return super().選ぶ(現在, **kwargs)

        def 応答を記録する(self, 作用前: Any, action: Any, 作用後: Any) -> dict[str, Any]:
            response = super().応答を記録する(作用前, action, 作用後)
            if (
                action.作用番号 == 0
                or 作用前.状態 != "NOT_FINISHED"
                or not 作用前.最新盤面
                or not 作用後.最新盤面
                or len(作用前.最新盤面) != len(作用後.最新盤面)
            ):
                return response

            before = self._snapshot(作用前.最新盤面)
            after = self._snapshot(作用後.最新盤面)
            if any(len(a) != len(b) for a, b in zip(before, after)):
                return response

            changed: list[tuple[int, int]] = []
            mask_changed = False
            for y, (before_row, after_row) in enumerate(zip(before, after)):
                for x, (before_value, after_value) in enumerate(zip(before_row, after_row)):
                    if before_value == after_value:
                        continue
                    changed.append((y, x))
                    history = self._value_history.setdefault((y, x), [before_value])
                    if history[-1] != before_value:
                        history.append(before_value)
                    if history[-1] != after_value:
                        history.append(after_value)
                    if len(history) > 6:
                        del history[:-6]
                    if (
                        len(history) >= 4
                        and history[-4] == history[-2]
                        and history[-3] == history[-1]
                        and history[-1] != history[-2]
                    ):
                        point = (y, x)
                        if point not in self._alternating_cells:
                            self._alternating_cells.add(point)
                            mask_changed = True

            previous_reward = float(response.get("公開応答報酬", 0.0))
            if mask_changed:
                self._masked_boards = {self._mask(item) for item in self._raw_boards}
            masked_after = self._mask(after)
            new_stable_board = masked_after not in self._masked_boards
            self._remember(after)

            level_delta = max(0, 作用後.完了レベル数 - 作用前.完了レベル数)
            meaningful_changes = sum(point not in self._alternating_cells for point in changed)
            area = max(1, sum(len(row) for row in before))
            raw_changes = len(changed)
            self._raw_cell_changes += raw_changes
            self._masked_cell_changes += raw_changes - meaningful_changes

            reward = float(self._レベル進行報酬) * level_delta
            if new_stable_board:
                reward += 0.5
            reward += float(self._可視変化係数) * min(1.0, meaningful_changes / area)
            if level_delta == 0 and meaningful_changes == 0:
                reward -= 1.0

            self._報酬合計[action.作用番号] += reward - previous_reward
            color = response.get("座標可視色")
            if color is not None and color in self._色報酬合計:
                self._色報酬合計[color] += reward - previous_reward
            response["公開応答報酬"] = reward
            response["安定盤面可視変化セル数"] = meaningful_changes
            response["反転マスク済セル数"] = len(self._alternating_cells)
            return response

        def 統計(self) -> dict[str, Any]:
            stats = super().統計()
            stats["stable_board_feedback"] = {
                "alternating_cells_masked": len(self._alternating_cells),
                "raw_changed_cells": self._raw_cell_changes,
                "masked_changed_cells": self._masked_cell_changes,
            }
            return stats

    return StableBoardFeedbackPolicy


def evaluate(*, full: bool = False) -> dict[str, Any]:
    started = time.perf_counter()
    experiment = runpy.run_path(str(BASELINE_RUNNER))
    control = json.loads(CONTROL_EVIDENCE.read_text(encoding="utf-8"))
    run_game = experiment["_run"].__globals__["_run_game"]
    score_game = experiment["_スコアを計算する"]
    policy_type = _stable_feedback_policy(experiment["_CurrentHDSRankingPolicy"])
    control_rows = control["results"]["pairs"]
    screening_seed = min(int(pair["seed"]) for pair in control_rows)
    if not full:
        control_rows = [pair for pair in control_rows if int(pair["seed"]) == screening_seed]
    control_pairs = {
        (pair["seed"], pair["game_id"]): pair
        for pair in control_rows
    }

    pairs: list[dict[str, Any]] = []
    for (seed, game_id), control_pair in control_pairs.items():
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
        "control_experiment": "C2-111 legal RESET with retained online exploration statistics",
        "control_evidence": CONTROL_EVIDENCE.relative_to(ROOT).as_posix(),
        "control_evidence_sha256": _sha256(CONTROL_EVIDENCE),
        "policy_seeds": sorted({pair["seed"] for pair in pairs}),
        "dev_games": list(dict.fromkeys(pair["game_id"] for pair in pairs)),
        "max_actions_per_game_including_resets": MAX_ACTIONS,
        "baseline": "C2-111 retained UCB with unmasked board-change and novelty feedback.",
        "candidate": "Keep legal RESET/UCB/HDS behavior; discount cells that repeatedly alternate between two visible values without level progress, then score masked-state novelty and meaningful changes.",
        "decision_gate": {
            "minimum_mean_rhae_delta": 0.01,
            "require_nonnegative_levels_and_wins": True,
            "screen_only_cannot_promote": not full,
            "full_15_pair_rerun_required_after_positive_screen": not full,
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
            "illegal_actions": sum(pair["candidate"]["illegal_action_attempts"] for pair in pairs),
            "alternating_cells_masked": sum(
                pair["candidate"]["policy_action_stats"].get("stable_board_feedback", {}).get("alternating_cells_masked", 0)
                for pair in pairs
            ),
            "wall_seconds": round(time.perf_counter() - started, 3),
        },
        "evaluation_scope": "full_15_matched_pairs" if full else "5_game_screen_at_one_seed",
        "screening_seed": None if full else screening_seed,
        "pairs": pairs,
        "runner_file": Path(__file__).relative_to(ROOT).as_posix(),
        "runner_sha256": _sha256(Path(__file__)),
        "baseline_runner_file": BASELINE_RUNNER.relative_to(ROOT).as_posix(),
        "baseline_runner_sha256": _sha256(BASELINE_RUNNER),
    }


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="run all 15 matched starts")
    args = parser.parse_args()
    output = FULL_OUTPUT if args.full else OUTPUT
    payload = json.dumps(evaluate(full=args.full), ensure_ascii=False, indent=2)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(payload + "\n", encoding="utf-8")
    print(json.dumps({"output": str(output), "sha256": _sha256(output)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
