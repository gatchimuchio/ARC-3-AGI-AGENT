"""Saved model-v5 and local-v4 public runs rescored with ARC's scorecard."""

from __future__ import annotations

import argparse
import hashlib
import inspect
import json
import math
from pathlib import Path
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "検証"))

from ARC3公開RHAE評価 import _スコアを計算する
from ARC3探索Actionローカル評価 import _load_games
from arc_agi.scorecard import EnvironmentScoreCalculator

_PREVIOUS = ROOT / "出力/ARC3-RUN-002-local/C2-025-v4-public-25-retry.json"
_CURRENT_DIR = ROOT / "出力/ARC3-RUN-002-local/C2-027-kaggle-output/v5"
_INPUT = ROOT / "入力/Kaggle/environment_files"
_PREVIOUS_C0 = ROOT / "出力/ARC3-RUN-003-local/C0-001-public25-rhae-baseline.json"
_DEFAULT_OUTPUT = ROOT / "出力/ARC3-RUN-003-local/C1-017-model-v5-public25-scorecard.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _public_input_hash(root: Path) -> tuple[int, str]:
    hashes = sorted(_sha256(path) for path in root.rglob("*") if path.is_file())
    return len(hashes), hashlib.sha256("\n".join(hashes).encode("ascii")).hexdigest()


def _load_json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"expected JSON object: {path.name}")
    return value


def _candidate_score(run: dict[str, Any]) -> float:
    actions = run.get("actions_per_level")
    baselines = run.get("base_actions_per_level")
    levels_completed = run.get("levels_completed")
    number_of_levels = run.get("number_of_levels")
    if not isinstance(actions, list) or not isinstance(baselines, list):
        raise ValueError("candidate per-level action arrays are missing")
    if len(actions) != len(baselines) or len(actions) != number_of_levels:
        raise ValueError("candidate action arrays do not match level count")
    if type(levels_completed) is not int or not 0 <= levels_completed <= len(actions):
        raise ValueError("candidate completed level count is invalid")
    if any(type(value) is not int or value < 0 for value in actions):
        raise ValueError("candidate action counts must be nonnegative integers")
    if any(type(value) is not int or value <= 0 for value in baselines):
        raise ValueError("public baseline actions must be positive integers")

    calculator = EnvironmentScoreCalculator()
    for level_index, (count, baseline) in enumerate(zip(actions, baselines), start=1):
        calculator.add_level(
            level_index=level_index,
            completed=level_index <= levels_completed,
            actions_taken=count,
            baseline_actions=baseline,
        )
    return float(calculator.to_score(include_levels=True).score)


def _paired_summary(previous: list[float], current: list[float]) -> dict[str, Any]:
    if not previous or len(previous) != len(current):
        raise ValueError("paired score vectors must be nonempty and equal length")
    deltas = [now - before for before, now in zip(previous, current)]
    return {
        "paired_environments": len(previous),
        "previous_mean_score": sum(previous) / len(previous),
        "current_mean_score": sum(current) / len(current),
        "mean_delta": sum(deltas) / len(deltas),
        "improved_environments": sum(delta > 1e-9 for delta in deltas),
        "unchanged_environments": sum(abs(delta) <= 1e-9 for delta in deltas),
        "regressed_environments": sum(delta < -1e-9 for delta in deltas),
    }


def _evaluate(
    previous_path: Path = _PREVIOUS,
    current_dir: Path = _CURRENT_DIR,
    environment_dir: Path = _INPUT,
) -> dict[str, Any]:
    previous_data = _load_json(previous_path)
    previous_c0 = _load_json(_PREVIOUS_C0)
    comparison = _load_json(current_dir / "C2-027-comparison.json")
    benchmark = _load_json(current_dir / "benchmark.json")

    if comparison.get("id_sets_exact") is not True:
        raise ValueError("saved comparison does not confirm exact run-key sets")
    run_count = len(benchmark.get("game_runs", []))
    if run_count != 25:
        raise ValueError("expected 25 saved candidate runs")
    for key in ("initial_board_matches", "initial_state_matches", "initial_level_matches"):
        if comparison.get(key) != 25:
            raise ValueError(f"saved initial-condition check failed: {key}")

    previous_runs = previous_data.get("games")
    current_runs = benchmark.get("game_runs")
    comparison_runs = comparison.get("games")
    if not all(
        isinstance(rows, list) and len(rows) == 25
        for rows in (previous_runs, current_runs, comparison_runs)
    ):
        raise ValueError("expected 25 rows in each saved comparison source")

    metadata_rows = _load_games(environment_dir)
    metadata_by_id = {str(metadata["game_id"]): metadata for metadata, _ in metadata_rows}
    previous_by_id = {
        str(row["game_id"]): row["exploration"]
        for row in previous_runs
        if isinstance(row, dict) and isinstance(row.get("exploration"), dict)
    }
    current_by_id = {str(row["game_id"]): row for row in current_runs if isinstance(row, dict)}
    comparison_by_id = {
        str(row["game_id"]): row for row in comparison_runs if isinstance(row, dict)
    }
    sets = (set(metadata_by_id), set(previous_by_id), set(current_by_id), set(comparison_by_id))
    if any(keys != sets[0] for keys in sets[1:]) or len(sets[0]) != 25:
        raise ValueError("public inputs and paired output keys do not match exactly")

    previous_scores: list[float] = []
    current_scores: list[float] = []
    previous_levels = current_levels = 0
    previous_actions = current_actions = 0
    previous_wins = current_wins = 0
    candidate_score_mismatches = 0
    candidate_run_states: dict[str, int] = {}
    for key in sorted(sets[0]):
        metadata = metadata_by_id[key]
        baseline_actions = metadata.get("baseline_actions")
        before = previous_by_id[key]
        after = current_by_id[key]
        comparison_row = comparison_by_id[key]
        if not isinstance(baseline_actions, list) or not all(
            type(value) is int and value > 0 for value in baseline_actions
        ):
            raise ValueError("public environment baseline metadata is invalid")
        if after.get("base_actions_per_level") != baseline_actions:
            raise ValueError("candidate human-baseline actions differ from public input")
        if len(before.get("action_responses", [])) != before.get("actions"):
            raise ValueError("previous saved action count is inconsistent")
        if sum(after["actions_per_level"]) != comparison_row.get("candidate_actions"):
            raise ValueError("candidate per-level action sum differs from comparison")
        if after.get("levels_completed") != comparison_row.get("candidate_levels_completed"):
            raise ValueError("candidate level count differs from comparison")

        previous_score, previous_run_levels, _ = _スコアを計算する(baseline_actions, before)
        current_score = _candidate_score(after)
        if not math.isclose(current_score, float(after["final_score"]), rel_tol=0, abs_tol=1e-9):
            candidate_score_mismatches += 1
        if previous_run_levels != int(comparison_row["baseline_levels_completed"]):
            raise ValueError("previous completed-level count differs from paired comparison")
        if int(before["actions"]) != int(comparison_row["baseline_actions"]):
            raise ValueError("previous action count differs from paired comparison")

        previous_scores.append(previous_score)
        current_scores.append(current_score)
        previous_levels += previous_run_levels
        current_levels += int(after["levels_completed"])
        previous_actions += int(before["actions"])
        current_actions += sum(after["actions_per_level"])
        previous_wins += int(before.get("final_state") == "WIN")
        current_wins += int(after.get("state") == "WIN")
        state = str(after.get("state", "UNKNOWN"))
        candidate_run_states[state] = candidate_run_states.get(state, 0) + 1

    if candidate_score_mismatches:
        raise ValueError("candidate scorecard does not match saved benchmark")
    if previous_levels != comparison.get("baseline_total_levels"):
        raise ValueError("previous completed-level aggregate mismatch")
    if current_levels != comparison.get("candidate_total_levels"):
        raise ValueError("candidate completed-level aggregate mismatch")
    if previous_actions != comparison.get("baseline_actions"):
        raise ValueError("previous action aggregate mismatch")
    if current_actions != comparison.get("candidate_actions"):
        raise ValueError("candidate action aggregate mismatch")
    c0_seed31 = next(
        (
            row
            for row in previous_c0.get("runs", [])
            if row.get("seed") == 31 and row.get("games") == 25
        ),
        None,
    )
    if c0_seed31 is None or not math.isclose(
        sum(previous_scores) / len(previous_scores),
        float(c0_seed31["RHAE_score"]),
        rel_tol=0,
        abs_tol=1e-6,
    ):
        raise ValueError("previous paired scorecard does not match C0 seed 31 aggregate")

    input_count, input_hash = _public_input_hash(environment_dir)
    scorecard_source = Path(inspect.getsourcefile(EnvironmentScoreCalculator) or "")
    scorecard_version_source_sha256 = _sha256(scorecard_source)
    return {
        "audit": "paired-public25-official-scorecard-rescore",
        "previous": "local-v4-seed31",
        "current": "model-guided-private-v5",
        "score_unit": "EnvironmentScoreCalculator points",
        "comparison": _paired_summary(previous_scores, current_scores),
        "totals": {
            "previous_completed_levels": previous_levels,
            "current_completed_levels": current_levels,
            "completed_level_delta": current_levels - previous_levels,
            "previous_actions": previous_actions,
            "current_actions": current_actions,
            "action_delta": current_actions - previous_actions,
            "previous_wins": previous_wins,
            "current_wins": current_wins,
            "candidate_run_states": candidate_run_states,
            "candidate_runtime_cap_games": len(comparison.get("candidate_runtime_cap_games", [])),
        },
        "checks": {
            "matched_public_environments": len(sets[0]),
            "initial_board_matches": comparison["initial_board_matches"],
            "initial_state_matches": comparison["initial_state_matches"],
            "initial_level_matches": comparison["initial_level_matches"],
            "previous_c0_seed31_score_matches": True,
            "candidate_benchmark_score_matches": True,
        },
        "public_input": {"file_count": input_count, "content_set_sha256": input_hash},
        "source_sha256": {
            "evaluator": _sha256(Path(__file__)),
            "previous_result": _sha256(previous_path),
            "previous_c0_result": _sha256(_PREVIOUS_C0),
            "candidate_benchmark": _sha256(current_dir / "benchmark.json"),
            "candidate_comparison": _sha256(current_dir / "C2-027-comparison.json"),
            "candidate_output_manifest": _sha256(current_dir / "C2-027-output.sha256"),
            "scorecard_source": scorecard_version_source_sha256,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--previous", type=Path, default=_PREVIOUS)
    parser.add_argument("--current-dir", type=Path, default=_CURRENT_DIR)
    parser.add_argument("--environment-dir", type=Path, default=_INPUT)
    parser.add_argument("--output", type=Path, default=_DEFAULT_OUTPUT)
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"refusing to overwrite existing result: {args.output}")
    result = _evaluate(args.previous, args.current_dir, args.environment_dir)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
