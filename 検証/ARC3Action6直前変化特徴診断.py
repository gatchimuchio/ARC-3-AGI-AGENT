"""Observe Action6 target relevance to the preceding public transition only."""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "検証")]

from ARC3公開Action特徴応答探索 import _manifest_sha256  # noqa: E402
from ARC3公開RHAE評価 import _スコアを計算する  # noqa: E402
from ARC3探索Actionローカル評価 import _load_games, _run_game  # noqa: E402
from 接続.ARC3境界 import 観測  # noqa: E402
from 接続.観測駆動探索Action import 観測駆動探索方針  # noqa: E402

_FEATURES = ("changed", "unchanged", "unknown")
_OUTCOMES = ("win", "game_over", "level_progress", "board_change", "no_op")
_SPLIT_SEED = 20261027


def _shape(board: tuple[tuple[int, ...], ...]) -> tuple[int, int] | None:
    if not board or not board[0] or any(len(row) != len(board[0]) for row in board):
        return None
    return len(board), len(board[0])


class _PreviousChangeContext:
    """Keep one preceding public change mask, never an accumulated history."""

    def __init__(self) -> None:
        self._mask: frozenset[tuple[int, int]] | None = None
        self._shape: tuple[int, int] | None = None

    def clear(self) -> None:
        self._mask = None
        self._shape = None

    def feature(self, board: tuple[tuple[int, ...], ...], x: int, y: int) -> str:
        shape = _shape(board)
        if shape is None or shape != self._shape:
            self.clear()
            return "unknown"
        if self._mask is None:
            return "unknown"
        return "changed" if (x, y) in self._mask else "unchanged"

    def observe(self, before: 観測, after: 観測) -> str:
        if after.状態 in ("GAME_OVER", "WIN"):
            self.clear()
            return "terminal_clear"
        if before.完了レベル数 != after.完了レベル数:
            self.clear()
            return "level_transition_clear"
        before_shape, after_shape = _shape(before.最新盤面), _shape(after.最新盤面)
        if before_shape is None or before_shape != after_shape:
            self.clear()
            return "shape_change_clear"
        self._shape = after_shape
        self._mask = frozenset(
            (x, y)
            for y, row in enumerate(after.最新盤面)
            for x, value in enumerate(row)
            if value != before.最新盤面[y][x]
        )
        return "comparable_response"


class _Audit:
    def __init__(self) -> None:
        self.counts: Counter[str] = Counter()
        self.by_feature: dict[str, Counter[str]] = defaultdict(Counter)
        self.outcome_games: dict[tuple[str, str], set[int]] = defaultdict(set)
        self._both_groups_games: set[int] = set()

    def record(
        self,
        feature: str,
        outcome: str,
        game_index: int,
        eligible_changed: int,
        eligible_unchanged: int,
        eligible_unknown: int,
    ) -> None:
        if feature not in _FEATURES or outcome not in _OUTCOMES:
            raise ValueError("unexpected aggregate feature or outcome")
        both = eligible_changed > 0 and eligible_unchanged > 0
        self.counts["action6_responses"] += 1
        self.counts["selected_color_both_groups_opportunities"] += int(both)
        if both:
            self._both_groups_games.add(game_index)
        self.counts["eligible_changed_coordinates"] += eligible_changed
        self.counts["eligible_unchanged_coordinates"] += eligible_unchanged
        self.counts["eligible_unknown_coordinates"] += eligible_unknown
        self.by_feature[feature]["selections"] += 1
        self.by_feature[feature]["both_groups_opportunities"] += int(both)
        self.by_feature[feature][outcome] += 1
        self.outcome_games[(feature, outcome)].add(game_index)

    def snapshot(self) -> dict[str, Any]:
        return {
            "counts": dict(sorted(self.counts.items())),
            "both_groups_distinct_public_games": len(self._both_groups_games),
            "selected_feature_outcomes": [
                {
                    "feature": feature,
                    "selections": self.by_feature[feature]["selections"],
                    "both_groups_opportunities": self.by_feature[feature][
                        "both_groups_opportunities"
                    ],
                    "outcomes": {
                        outcome: {
                            "responses": self.by_feature[feature][outcome],
                            "distinct_public_games": len(self.outcome_games[(feature, outcome)]),
                        }
                        for outcome in _OUTCOMES
                    },
                }
                for feature in _FEATURES
            ],
        }


def _outcome(after: 観測, receipt: dict[str, Any]) -> str:
    if after.状態 == "WIN":
        return "win"
    if after.状態 == "GAME_OVER":
        return "game_over"
    if receipt["完了レベル増分"] > 0:
        return "level_progress"
    return "board_change" if receipt["可視変化セル数"] > 0 else "no_op"


def _policy_type(audit: _Audit, game_index: int):
    class _ObservedPolicy(観測駆動探索方針):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, **kwargs)
            self._previous_change = _PreviousChangeContext()
            self._pending_target_feature: tuple[str, int, int, int] | None = None

        def 選ぶ(self, 現在: 観測, **kwargs):
            self._pending_target_feature = None
            if 現在.状態 in ("NOT_PLAYED", "GAME_OVER"):
                self._previous_change.clear()
                audit.counts["sdk_reset_observation_clear"] += 1
            return super().選ぶ(現在, **kwargs)

        def _未試行座標を選ぶ(self, 盤面, 色, 未試行座標):
            # Preserve candidate order and the baseline's exact RNG call.
            group_counts = Counter(self._previous_change.feature(盤面, x, y) for x, y in 未試行座標)
            point = super()._未試行座標を選ぶ(盤面, 色, 未試行座標)
            feature = self._previous_change.feature(盤面, *point)
            self._pending_target_feature = (
                feature,
                group_counts["changed"],
                group_counts["unchanged"],
                group_counts["unknown"],
            )
            return point

        def 応答を記録する(self, 作用前: 観測, action, 作用後: 観測):
            receipt = super().応答を記録する(作用前, action, 作用後)
            if action.作用番号 == 6:
                if self._pending_target_feature is None:
                    raise RuntimeError("Action6 response lacks its pre-action target feature")
                feature, changed, unchanged, unknown = self._pending_target_feature
                audit.record(
                    feature, _outcome(作用後, receipt), game_index, changed, unchanged, unknown
                )
            audit.counts[self._previous_change.observe(作用前, 作用後)] += 1
            self._pending_target_feature = None
            return receipt

    return _ObservedPolicy


def _source_hashes() -> dict[str, str]:
    paths = {
        "diagnostic": Path(__file__),
        "policy": ROOT / "接続/観測駆動探索Action.py",
        "local_evaluator": ROOT / "検証/ARC3探索Actionローカル評価.py",
        "scorer": ROOT / "検証/ARC3公開RHAE評価.py",
    }
    return {name: hashlib.sha256(path.read_bytes()).hexdigest() for name, path in paths.items()}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", choices=("dev", "remainder"), required=True)
    parser.add_argument("--seeds", type=int, nargs="+", required=True)
    parser.add_argument("--max-actions", type=int, default=80)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if len(set(args.seeds)) != len(args.seeds) or args.max_actions <= 0:
        parser.error("seeds must be unique and max-actions must be positive")
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if output.exists():
        parser.error(f"refusing to overwrite existing diagnostic: {output}")

    games = _load_games(ROOT / "入力/Kaggle/environment_files")
    if len(games) != 25:
        raise RuntimeError("expected 25 reused public environments")
    shuffled = list(games)
    random.Random(_SPLIT_SEED).shuffle(shuffled)
    indexed = list(enumerate(shuffled))
    selected = indexed[:5] if args.stage == "dev" else indexed[5:]
    audit = _Audit()
    totals: Counter[str] = Counter()
    stop_reasons: Counter[str] = Counter()
    by_seed = []
    for seed in args.seeds:
        seed_totals: Counter[str] = Counter()
        for index, (game_index, (metadata, metadata_path)) in enumerate(selected, 1):
            run = _run_game(
                metadata,
                metadata_path,
                "exploration",
                seed=seed,
                policy_seed=seed,
                max_actions=args.max_actions,
                retry_game_over=True,
                visible_change_coefficient=0.0,
                level_progress_reward=4.0,
                policy_type_override=_policy_type(audit, game_index),
            )
            score, levels, _ = _スコアを計算する(metadata["baseline_actions"], run)
            if levels != run["levels_completed"] - run["initial_levels_completed"]:
                raise RuntimeError("scorecard level boundary mismatch")
            values = {
                "episodes": 1,
                "rhae_sum": score,
                "levels_completed": levels,
                "wins": int(run["final_state"] == "WIN"),
                "actions": run["actions"],
                "noops": run["no_op_actions"],
                "action6_responses": sum(
                    response["action_id"] == 6 for response in run["action_responses"]
                ),
                "reset_actions": run["reset_actions"],
                "game_over_events": run["game_over_events"],
                "illegal_actions": run["illegal_action_attempts"],
                "duplicate_observations": run["duplicate_observation_steps"],
            }
            seed_totals.update(values)
            totals.update(values)
            stop_reasons[run["stop_reason"]] += 1
            print(f"PROGRESS {args.stage} seed={seed} episode={index}/{len(selected)}", flush=True)
        seed_summary = dict(seed_totals)
        seed_summary["rhae_mean"] = seed_summary.pop("rhae_sum") / seed_summary["episodes"]
        by_seed.append({"seed": seed, **seed_summary})

    summary = dict(totals)
    summary["rhae_mean"] = summary.pop("rhae_sum") / summary["episodes"]
    if summary["action6_responses"] != audit.counts["action6_responses"]:
        raise RuntimeError("observational Action6 count differs from SDK response count")
    result = {
        "schema": "arc3-action6-previous-public-change-observation.v1",
        "run_id": output.stem,
        "observed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "stage": args.stage,
        "split_seed": _SPLIT_SEED,
        "split_rule": "first five shuffled public games are dev; remaining twenty are remainder",
        "games_per_seed": len(selected),
        "seeds": args.seeds,
        "seed_interpretation": "trajectory/RNG confirmation; every public game has been reused",
        "all_public_games_previously_used": True,
        "max_actions_per_episode": args.max_actions,
        "retry_game_over": True,
        "visible_change_coefficient": 0.0,
        "level_progress_reward": 4.0,
        "python_hash_seed": os.environ.get("PYTHONHASHSEED", "randomized"),
        "summary": summary,
        "stop_reason_counts": dict(sorted(stop_reasons.items())),
        "per_seed_aggregate": by_seed,
        "feature_observation": audit.snapshot(),
        "score_interpretation": "descriptive baseline exploration only; no paired causal effect",
        "feature_definition": "selected target changed in the preceding comparable public response",
        "context_clear_rule": "RESET observation, terminal response, level transition, or shape change",
        "selection_intervention": False,
        "completed_without_exception": True,
        "exception_handling": "fail immediately; incomplete evaluation does not write a result",
        "raw_boards_masks_coordinates_game_ids_or_per_game_rows_persisted": False,
        "only_public_observations_used": True,
        "official_submission_made": False,
        "competition_api_called": False,
        "notebook_or_kernel_changed": False,
        "environment_manifest_sha256": _manifest_sha256(),
        "source_sha256": _source_hashes(),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result["summary"], ensure_ascii=False, separators=(",", ":")), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
