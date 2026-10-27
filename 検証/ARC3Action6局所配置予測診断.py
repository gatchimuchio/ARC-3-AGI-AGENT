"""公開Action6の向き付き局所配置から、一手先応答の予測可能性だけを測る。

行動選択は現行方針を継承し、応答記録だけを観測する。全25公開ゲームを
5分割して再利用する探索的診断であり、closed-loop score改善を測らない。
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import random
import sys
import time
from typing import Iterable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "検証"))

from ARC3探索Actionローカル評価 import _load_games, _run_game  # noqa: E402
from 接続.ARC3境界 import 観測  # noqa: E402
from 接続.観測駆動探索Action import 探索Action, 観測駆動探索方針  # noqa: E402

_OUTCOMES = ("win", "game_over", "level_progress", "board_change", "no_op")
_DIRECTIONS = (
    ("N", 0, -1),
    ("NE", 1, -1),
    ("E", 1, 0),
    ("SE", 1, 1),
    ("S", 0, 1),
    ("SW", -1, 1),
    ("W", -1, 0),
    ("NW", -1, -1),
)
_SPLIT_SEED = 20261027
_FOLDS = 5
_PRIOR_STRENGTH = 3.0
_MIN_SUPPORT = 3
_MIN_TRAINING_GAMES = 2
Topology = tuple[str, ...]


@dataclass(frozen=True)
class _Sample:
    # 実行中のgroup連番のみ。ゲームID・座標・盤面を保持せず、保存もしない。
    game_group: int
    topology: Topology
    outcome: str


def _target_topology(board: tuple[tuple[int, ...], ...], x: int, y: int) -> Topology:
    height = len(board)
    width = len(board[0]) if height else 0
    if not width or any(len(row) != width for row in board):
        raise ValueError("target topology requires a nonempty rectangular public board")
    if type(x) is not int or type(y) is not int or not (0 <= x < width and 0 <= y < height):
        raise ValueError("target is outside the public board")
    center = board[y][x]
    return tuple(
        "outside"
        if not (0 <= x + dx < width and 0 <= y + dy < height)
        else "same"
        if board[y + dy][x + dx] == center
        else "different"
        for _, dx, dy in _DIRECTIONS
    )


def _outcome(before: 観測, after: 観測) -> str:
    if after.状態 == "WIN":
        return "win"
    if after.状態 == "GAME_OVER":
        return "game_over"
    if after.完了レベル数 > before.完了レベル数:
        return "level_progress"
    if after.最新盤面 != before.最新盤面:
        return "board_change"
    return "no_op"


def _sample_transition(game_group: int, before: 観測, action: 探索Action, after: 観測) -> _Sample:
    if action.作用番号 != 6 or set(action.引数) != {"x", "y"}:
        raise ValueError("only public Action6 transitions have target topology")
    return _Sample(
        game_group,
        _target_topology(before.最新盤面, action.引数["x"], action.引数["y"]),
        _outcome(before, after),
    )


def _policy_type(samples: list[_Sample], game_group: int):
    class _ResponseObserver(観測駆動探索方針):
        def 応答を記録する(self, 作用前, action, 作用後):
            response = super().応答を記録する(作用前, action, 作用後)
            if action.作用番号 == 6:
                samples.append(_sample_transition(game_group, 作用前, action, 作用後))
            return response

    return _ResponseObserver


def _fold_assignment(game_count: int, fold_count: int = _FOLDS) -> tuple[int, ...]:
    if game_count <= 0 or fold_count <= 1 or game_count % fold_count:
        raise ValueError("equal game-group folds require a positive divisible game count")
    shuffled = list(range(game_count))
    random.Random(_SPLIT_SEED).shuffle(shuffled)
    assignments = [-1] * game_count
    size = game_count // fold_count
    for position, game_group in enumerate(shuffled):
        assignments[game_group] = position // size
    return tuple(assignments)


class _EmpiricalForecast:
    def __init__(self, training: Iterable[_Sample]):
        self.outcomes: Counter[str] = Counter()
        self.by_topology: dict[Topology, Counter[str]] = defaultdict(Counter)
        self.games_by_topology: dict[Topology, set[int]] = defaultdict(set)
        for sample in training:
            if sample.outcome not in _OUTCOMES:
                raise ValueError("unknown public response category")
            self.outcomes[sample.outcome] += 1
            self.by_topology[sample.topology][sample.outcome] += 1
            self.games_by_topology[sample.topology].add(sample.game_group)
        total = self.outcomes.total()
        self.marginal = tuple(
            self.outcomes[outcome] / total if total else 1.0 / len(_OUTCOMES)
            for outcome in _OUTCOMES
        )

    def predict(self, topology: Topology) -> tuple[tuple[float, ...], bool, int, int]:
        counts = self.by_topology.get(topology, Counter())
        support = counts.total()
        games = len(self.games_by_topology.get(topology, set()))
        eligible = support >= _MIN_SUPPORT and games >= _MIN_TRAINING_GAMES
        if not eligible:
            return self.marginal, False, support, games
        probabilities = tuple(
            (counts[outcome] + _PRIOR_STRENGTH * prior) / (support + _PRIOR_STRENGTH)
            for outcome, prior in zip(_OUTCOMES, self.marginal)
        )
        return probabilities, True, support, games


def _brier(probabilities: tuple[float, ...], outcome: str) -> float:
    if outcome not in _OUTCOMES or len(probabilities) != len(_OUTCOMES):
        raise ValueError("invalid categorical Brier input")
    return sum(
        (probability - int(category == outcome)) ** 2
        for category, probability in zip(_OUTCOMES, probabilities)
    )


def _outcome_aggregate(samples: list[_Sample]) -> dict[str, dict[str, int]]:
    return {
        outcome: {
            "samples": sum(sample.outcome == outcome for sample in samples),
            "distinct_game_groups": len(
                {sample.game_group for sample in samples if sample.outcome == outcome}
            ),
        }
        for outcome in _OUTCOMES
    }


def _evaluate_folds(samples: list[_Sample], assignments: tuple[int, ...]) -> dict:
    if (
        not assignments
        or min(assignments) != 0
        or set(assignments) != set(range(max(assignments) + 1))
    ):
        raise ValueError("fold assignments must be contiguous nonnegative fold numbers")
    if any(not 0 <= sample.game_group < len(assignments) for sample in samples):
        raise ValueError("sample game group is outside fold assignment")
    rows = []
    for fold in range(max(assignments) + 1):
        training = [sample for sample in samples if assignments[sample.game_group] != fold]
        testing = [sample for sample in samples if assignments[sample.game_group] == fold]
        model = _EmpiricalForecast(training)
        candidate_sum = 0.0
        marginal_sum = 0.0
        covered = 0
        covered_games: set[int] = set()
        support_bins: Counter[str] = Counter()
        for sample in testing:
            prediction, eligible, support, games = model.predict(sample.topology)
            candidate_sum += _brier(prediction, sample.outcome)
            marginal_sum += _brier(model.marginal, sample.outcome)
            covered += int(eligible)
            if eligible:
                covered_games.add(sample.game_group)
            support_bins[
                "zero"
                if support == 0
                else "one_or_two"
                if support < _MIN_SUPPORT
                else "three_plus_one_game"
                if games < _MIN_TRAINING_GAMES
                else "three_plus_multiple_games"
            ] += 1
        count = len(testing)
        candidate = candidate_sum / count if count else None
        marginal = marginal_sum / count if count else None
        rows.append(
            {
                "fold": fold,
                "training_game_groups": sum(value != fold for value in assignments),
                "test_game_groups": sum(value == fold for value in assignments),
                "training_samples": len(training),
                "test_samples": count,
                "training_topology_categories": len(model.by_topology),
                "test_topology_categories": len({sample.topology for sample in testing}),
                "training_outcomes": _outcome_aggregate(training),
                "test_outcomes": _outcome_aggregate(testing),
                "forecast_eligible_test_samples": covered,
                "forecast_eligible_test_game_groups": len(covered_games),
                "forecast_coverage": covered / count if count else 0.0,
                "test_sample_training_support_bins": dict(sorted(support_bins.items())),
                "forecast_brier": candidate,
                "marginal_brier": marginal,
                "brier_delta_forecast_minus_marginal": (candidate - marginal if count else None),
            }
        )
    nonempty = [row for row in rows if row["test_samples"]]
    total = sum(row["test_samples"] for row in rows)
    macro_candidate = (
        sum(row["forecast_brier"] for row in nonempty) / len(nonempty) if nonempty else None
    )
    macro_marginal = (
        sum(row["marginal_brier"] for row in nonempty) / len(nonempty) if nonempty else None
    )
    return {
        "folds": rows,
        "aggregate": {
            "samples": total,
            "nonempty_folds": len(nonempty),
            "forecast_eligible_samples": sum(row["forecast_eligible_test_samples"] for row in rows),
            "forecast_coverage": (
                sum(row["forecast_eligible_test_samples"] for row in rows) / total if total else 0.0
            ),
            "macro_forecast_brier": macro_candidate,
            "macro_marginal_brier": macro_marginal,
            "macro_brier_delta_forecast_minus_marginal": (
                macro_candidate - macro_marginal if nonempty else None
            ),
            "sample_weighted_forecast_brier": (
                sum(row["forecast_brier"] * row["test_samples"] for row in nonempty) / total
                if total
                else None
            ),
            "sample_weighted_marginal_brier": (
                sum(row["marginal_brier"] * row["test_samples"] for row in nonempty) / total
                if total
                else None
            ),
            "outcomes": _outcome_aggregate(samples),
            "distinct_topology_categories": len({sample.topology for sample in samples}),
        },
    }


def _prerequisite_gate(evaluation: dict) -> dict:
    aggregate = evaluation["aggregate"]
    candidate = aggregate["macro_forecast_brier"]
    marginal = aggregate["macro_marginal_brier"]
    nonempty = [row for row in evaluation["folds"] if row["test_samples"]]
    non_worse = sum(row["brier_delta_forecast_minus_marginal"] <= 1e-12 for row in nonempty)
    relative_reduction = (
        (marginal - candidate) / marginal
        if marginal is not None and marginal > 0 and candidate is not None
        else None
    )
    checks = {
        "all_five_folds_nonempty": len(nonempty) == _FOLDS,
        "macro_brier_relative_reduction_at_least_five_percent": (
            relative_reduction is not None and relative_reduction >= 0.05 - 1e-12
        ),
        "at_least_four_folds_non_worse": non_worse >= 4,
        "forecast_coverage_at_least_quarter": aggregate["forecast_coverage"] >= 0.25,
    }
    return {
        "frozen_before_data_run": True,
        "thresholds": {
            "minimum_relative_macro_brier_reduction": 0.05,
            "minimum_non_worse_folds": 4,
            "required_nonempty_folds": _FOLDS,
            "minimum_forecast_coverage": 0.25,
            "numeric_tolerance": 1e-12,
        },
        "observed_relative_macro_brier_reduction": relative_reduction,
        "observed_non_worse_folds": non_worse,
        "checks": checks,
        "passed": all(checks.values()),
        "permits": "closed_loop_candidate_work_only",
        "runtime_adoption_justified": False,
        "score_gain_claim_justified": False,
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _input_manifest_hash(root: Path) -> str:
    digest = hashlib.sha256()
    for path in sorted(item for item in root.rglob("*") if item.is_file()):
        relative = path.relative_to(root).as_posix().encode("utf-8")
        content = path.read_bytes()
        digest.update(len(relative).to_bytes(4, "big"))
        digest.update(relative)
        digest.update(len(content).to_bytes(8, "big"))
        digest.update(hashlib.sha256(content).digest())
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seeds", type=int, nargs="+", required=True)
    parser.add_argument("--max-actions", type=int, default=80)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if len(set(args.seeds)) != len(args.seeds):
        parser.error("seeds must be unique")
    if args.max_actions <= 0:
        parser.error("max-actions must be positive")
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if output.exists():
        parser.error(f"refusing to overwrite existing result: {output}")

    started = time.perf_counter()
    environment_root = ROOT / "入力/Kaggle/environment_files"
    games = _load_games(environment_root)
    if len(games) != 25:
        raise RuntimeError("expected 25 public environments")
    assignments = _fold_assignment(len(games))
    samples: list[_Sample] = []
    totals: Counter[str] = Counter()
    for seed in args.seeds:
        for game_group, (metadata, metadata_path) in enumerate(games):
            run = _run_game(
                metadata,
                metadata_path,
                "exploration",
                seed=seed,
                policy_seed=seed,
                max_actions=args.max_actions,
                visible_change_coefficient=0.0,
                retry_game_over=True,
                policy_type_override=_policy_type(samples, game_group),
            )
            totals.update(
                {
                    "episodes": 1,
                    "actions": int(run["actions"]),
                    "noops": int(run["no_op_actions"]),
                    "game_over_events": int(run["game_over_events"]),
                    "reset_actions": int(run["reset_actions"]),
                    "illegal_actions": int(run["illegal_action_attempts"]),
                    "duplicate_observations": int(run["duplicate_observation_steps"]),
                }
            )
            print(f"PROGRESS episodes_completed={totals['episodes']}", flush=True)
    evaluation = _evaluate_folds(samples, assignments)
    result = {
        "schema": "arc3-action6-oriented-topology-outcome-diagnostic.v1",
        "run_id": output.stem,
        "observed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "seeds": args.seeds,
        "python_hash_seed": os.environ.get("PYTHONHASHSEED", "randomized"),
        "public_games": len(games),
        "max_actions_per_episode": args.max_actions,
        "visible_change_coefficient": 0.0,
        "retry_game_over": True,
        "observer_overrides_response_only": True,
        "feature": {
            "source": "pre_action_target_public_board",
            "directions": [name for name, _, _ in _DIRECTIONS],
            "values": ["same", "different", "outside"],
            "orientation_preserved": True,
            "color_ids_raw_coordinates_and_board_hashes_used_as_keys": False,
        },
        "method": {
            "split_seed": _SPLIT_SEED,
            "game_group_folds": _FOLDS,
            "training_games_per_fold": 20,
            "test_games_per_fold": 5,
            "all_public_games_reused_across_folds": True,
            "outcome_precedence": list(_OUTCOMES),
            "prior_strength_times_training_marginal": _PRIOR_STRENGTH,
            "minimum_training_support": _MIN_SUPPORT,
            "minimum_distinct_training_games": _MIN_TRAINING_GAMES,
            "insufficient_support_fallback": "training_marginal",
            "brier_definition": "sum_over_five_outcomes_squared_probability_error",
            "lower_brier_is_better": True,
        },
        "baseline_policy_observation_totals": dict(sorted(totals.items())),
        **evaluation,
        "exploratory_prerequisite_gate": _prerequisite_gate(evaluation),
        "interpretation": "exploratory public-game cross-validation; not unseen holdout evidence",
        "closed_loop_score_gain_measured": False,
        "samples_per_game_rows_and_feature_tables_persisted": False,
        "only_public_observations_used": True,
        "competition_api_called": False,
        "official_submission_made": False,
        "source_sha256": {
            "diagnostic": _sha256(Path(__file__)),
            "test": _sha256(ROOT / "検証/test_ARC3Action6局所配置予測診断.py"),
            "local_evaluator": _sha256(ROOT / "検証/ARC3探索Actionローカル評価.py"),
            "policy": _sha256(ROOT / "接続/観測駆動探索Action.py"),
        },
        "environment_manifest_sha256": _input_manifest_hash(environment_root),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(json.dumps(result["aggregate"], ensure_ascii=False, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
