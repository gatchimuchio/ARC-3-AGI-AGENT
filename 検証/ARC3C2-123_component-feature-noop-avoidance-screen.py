"""Screen public component-feature no-op avoidance for ACTION6."""

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
OUTPUT = ROOT / "出力/ARC3-RUN-003-local/C2-123/component-feature-noop-avoidance-screen.json"
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


def _component_feature_noop_avoidance_policy(base_policy: type) -> type:
    class ComponentFeatureNoopAvoidancePolicy(base_policy):
        """Avoid ACTION6 component feature classes with observed public no-op feedback."""

        def __init__(self, *args: Any, **kwargs: Any) -> None:
            super().__init__(*args, **kwargs)
            self._no_op_component_contexts: set[tuple[str, str, int]] = set()
            self._filter_opportunities = 0
            self._suppressed_cells = 0
            self._no_op_feedback_events = 0

        @staticmethod
        def _component_rows(
            board: tuple[tuple[int, ...], ...],
            color: int,
            unseen: set[tuple[int, int]] | None = None,
        ) -> list[tuple[tuple[str, str, int], list[tuple[int, int]]]]:
            seen: set[tuple[int, int]] = set()
            components: list[list[tuple[int, int]]] = []
            total_color_cells = sum(value == color for row in board for value in row)
            for y, row in enumerate(board):
                for x, value in enumerate(row):
                    point = (x, y)
                    if value != color or point in seen:
                        continue
                    stack = [point]
                    seen.add(point)
                    cells: list[tuple[int, int]] = []
                    while stack:
                        cx, cy = stack.pop()
                        cells.append((cx, cy))
                        for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
                            if (
                                0 <= ny < len(board)
                                and 0 <= nx < len(board[ny])
                                and board[ny][nx] == color
                                and (nx, ny) not in seen
                            ):
                                seen.add((nx, ny))
                                stack.append((nx, ny))
                    components.append(cells)

            rows: list[tuple[tuple[str, str, int], list[tuple[int, int]]]] = []
            for cells in components:
                area = len(cells)
                area_band = "1" if area == 1 else "2-4" if area <= 4 else "5-16" if area <= 16 else "17+"
                share = area / max(1, total_color_cells)
                share_band = "small" if share <= 0.25 else "medium" if share <= 0.75 else "large"
                context = (area_band, share_band, min(3, len({c for row in board for c in row})))
                available = [point for point in cells if unseen is None or point in unseen]
                if available:
                    rows.append((context, available))
            return rows

        def _未試行座標を選ぶ(
            self,
            盤面: tuple[tuple[int, ...], ...],
            色: int,
            未試行座標: list[tuple[int, int]],
        ) -> tuple[int, int]:
            remaining = set(未試行座標)
            components = self._component_rows(盤面, 色, remaining)
            blocked = [
                point
                for context, points in components
                if context in self._no_op_component_contexts
                for point in points
            ]
            allowed = [
                point
                for context, points in components
                if context not in self._no_op_component_contexts
                for point in points
            ]
            if blocked and allowed:
                self._filter_opportunities += 1
                self._suppressed_cells += len(blocked)
                return self._rng.choice(allowed)
            return super()._未試行座標を選ぶ(盤面, 色, 未試行座標)

        def 応答を記録する(self, 作用前: Any, action: Any, 作用後: Any) -> dict[str, Any]:
            context = None
            if action.作用番号 == 6 and action.引数 and 作用前.最新盤面:
                x, y = action.引数["x"], action.引数["y"]
                color = 作用前.最新盤面[y][x]
                for candidate, points in self._component_rows(作用前.最新盤面, color):
                    if (x, y) in points:
                        context = candidate
                        break
            response = super().応答を記録する(作用前, action, 作用後)
            if (
                context is not None
                and response.get("可視変化セル数") == 0
                and response.get("完了レベル増分") == 0
            ):
                self._no_op_feedback_events += 1
                self._no_op_component_contexts.add(context)
            return response

        def 統計(self) -> dict[str, Any]:
            stats = super().統計()
            stats["component_feature_noop_avoidance"] = {
                "learned_no_op_contexts": len(self._no_op_component_contexts),
                "no_op_feedback_events": self._no_op_feedback_events,
                "filter_opportunities": self._filter_opportunities,
                "unseen_cells_suppressed": self._suppressed_cells,
                "context_features": ["component_area_band", "component_share_band", "board_color_count_band"],
                "game_identifier_used_for_selection": False,
            }
            return stats

    return ComponentFeatureNoopAvoidancePolicy


def evaluate() -> dict[str, Any]:
    started = time.perf_counter()
    experiment = runpy.run_path(str(BASELINE_RUNNER))
    control = json.loads(CONTROL_EVIDENCE.read_text(encoding="utf-8"))
    run_game = experiment["_run"].__globals__["_run_game"]
    score_game = experiment["_スコアを計算する"]
    policy_type = _component_feature_noop_avoidance_policy(experiment["_CurrentHDSRankingPolicy"])
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
        "control_experiment": "C2-111 legal RESET with retained online exploration statistics",
        "control_evidence": CONTROL_EVIDENCE.relative_to(ROOT).as_posix(),
        "control_evidence_sha256": _sha256(CONTROL_EVIDENCE),
        "policy_seeds": [screening_seed],
        "dev_games": [pair["game_id"] for pair in control_rows],
        "max_actions_per_game_including_resets": MAX_ACTIONS,
        "candidate": "For ACTION6, use public no-op feedback to suppress unseen cells in same-color component feature classes with component area, component share, and board color-count bands, only when another legal coordinate exists. The suppression memory is episode-local; no game ID, hidden state, or fixed action sequence is used.",
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
            "learned_no_op_contexts": sum(
                pair["candidate"]["policy_action_stats"]
                .get("component_feature_noop_avoidance", {})
                .get("learned_no_op_contexts", 0)
                for pair in pairs
            ),
            "no_op_feedback_events": sum(
                pair["candidate"]["policy_action_stats"]
                .get("component_feature_noop_avoidance", {})
                .get("no_op_feedback_events", 0)
                for pair in pairs
            ),
            "filter_opportunities": sum(
                pair["candidate"]["policy_action_stats"]
                .get("component_feature_noop_avoidance", {})
                .get("filter_opportunities", 0)
                for pair in pairs
            ),
            "unseen_cells_suppressed": sum(
                pair["candidate"]["policy_action_stats"]
                .get("component_feature_noop_avoidance", {})
                .get("unseen_cells_suppressed", 0)
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
