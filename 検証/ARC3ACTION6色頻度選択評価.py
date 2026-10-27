"""ACTION6の色頻度bucketを使う遅延選択ruleをdev/holdout評価する。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "検証"))

import ARC3探索Actionローカル評価 as runner  # noqa: E402
import ARC3レベル間色統計評価 as baseline_helper  # noqa: E402

_SEEDS = (7, 31, 73)
_COUNTERS = (
    "actions",
    "levels_completed",
    "wins",
    "no_op_actions",
    "game_over_events",
    "reset_actions",
    "illegal_action_attempts",
    "duplicate_observation_steps",
    "policy_holds",
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _empty_aggregate() -> dict[str, int]:
    return {key: 0 for key in _COUNTERS} | {
        "games": 0,
        "middle_frequency_color_deferrals": 0,
    }


def _run_stage(stage: str, environments: list[tuple[dict[str, Any], Path]]) -> dict[str, Any]:
    aggregates = {
        condition: {str(seed): _empty_aggregate() for seed in _SEEDS}
        for condition in ("previous", "candidate")
    }
    paired_runs = {str(seed): 0 for seed in _SEEDS}
    same_public_starts = {str(seed): 0 for seed in _SEEDS}

    for seed in _SEEDS:
        key = str(seed)
        for metadata, metadata_path in environments:
            pair: dict[str, dict[str, Any]] = {}
            for condition in ("previous", "candidate"):
                game = runner._run_game(
                    metadata,
                    metadata_path,
                    "exploration",
                    seed=seed,
                    max_actions=80,
                    retry_game_over=True,
                    defer_middle_frequency_action6_color=condition == "candidate",
                )
                pair[condition] = game
                aggregate = aggregates[condition][key]
                aggregate["games"] += 1
                aggregate["actions"] += int(game["actions"])
                aggregate["levels_completed"] += int(game["levels_completed"])
                aggregate["wins"] += int(game["final_state"] == "WIN")
                aggregate["no_op_actions"] += int(game["no_op_actions"])
                aggregate["game_over_events"] += int(game["game_over_events"])
                aggregate["reset_actions"] += int(game["reset_actions"])
                aggregate["illegal_action_attempts"] += int(game["illegal_action_attempts"])
                aggregate["duplicate_observation_steps"] += int(game["duplicate_observation_steps"])
                aggregate["policy_holds"] += int(game["stop_reason"] == "exploration_hold")
                aggregate["middle_frequency_color_deferrals"] += int(
                    game["middle_frequency_color_deferrals"]
                )
                if game["actions"] != len(game["action_responses"]):
                    raise RuntimeError("action response count differs from evaluator actions")

            paired_runs[key] += 1
            same_public_starts[key] += int(
                pair["previous"]["initial_state"] == pair["candidate"]["initial_state"]
                and pair["previous"]["initial_levels_completed"]
                == pair["candidate"]["initial_levels_completed"]
                and pair["previous"]["initial_available_actions"]
                == pair["candidate"]["initial_available_actions"]
                and pair["previous"]["initial_board"] == pair["candidate"]["initial_board"]
            )

    baseline_matches = {}
    for seed in _SEEDS:
        key = str(seed)
        expected = baseline_helper._baseline_expected(stage, seed)
        baseline_matches[key] = {
            metric: aggregates["previous"][key][metric] == value
            for metric, value in expected.items()
        }

    return {
        "stage": stage,
        "environments_per_seed": len(environments),
        "seeds": list(_SEEDS),
        "previous": aggregates["previous"],
        "candidate": aggregates["candidate"],
        "previous_matches_C2-003": baseline_matches,
        "paired_runs": paired_runs,
        "same_public_start_pairs": same_public_starts,
    }


def _gate(stage: str, result: dict[str, Any]) -> dict[str, Any]:
    by_seed = {}
    for seed in _SEEDS:
        key = str(seed)
        old = result["previous"][key]
        new = result["candidate"][key]
        by_seed[key] = {
            "levels_not_lower": new["levels_completed"] >= old["levels_completed"],
            "no_op_not_higher": new["no_op_actions"] <= old["no_op_actions"],
            "no_op_lower": new["no_op_actions"] < old["no_op_actions"],
            "game_over_not_higher": new["game_over_events"] <= old["game_over_events"],
            "game_over_lower": new["game_over_events"] < old["game_over_events"],
            "holds_illegal_duplicates_zero": (
                new["policy_holds"] == 0
                and new["illegal_action_attempts"] == 0
                and new["duplicate_observation_steps"] == 0
            ),
        }

    checks = {
        "all_previous_runs_match_C2-003": all(
            all(seed_checks.values()) for seed_checks in result["previous_matches_C2-003"].values()
        ),
        "all_paired_public_starts_match": all(
            result["same_public_start_pairs"][str(seed)] == result["paired_runs"][str(seed)]
            for seed in _SEEDS
        ),
        "levels_not_lower_each_seed": all(
            seed_checks["levels_not_lower"] for seed_checks in by_seed.values()
        ),
        "no_op_not_higher_each_seed": all(
            seed_checks["no_op_not_higher"] for seed_checks in by_seed.values()
        ),
        "game_over_not_higher_each_seed": all(
            seed_checks["game_over_not_higher"] for seed_checks in by_seed.values()
        ),
        "holds_illegal_duplicates_zero": all(
            seed_checks["holds_illegal_duplicates_zero"] for seed_checks in by_seed.values()
        ),
    }
    if stage == "dev":
        checks["no_op_total_lower"] = sum(
            result["candidate"][str(seed)]["no_op_actions"] for seed in _SEEDS
        ) < sum(result["previous"][str(seed)]["no_op_actions"] for seed in _SEEDS)
        checks["no_op_lower_in_at_least_two_seeds"] = (
            sum(seed_checks["no_op_lower"] for seed_checks in by_seed.values()) >= 2
        )
        checks["game_over_total_lower"] = sum(
            result["candidate"][str(seed)]["game_over_events"] for seed in _SEEDS
        ) < sum(result["previous"][str(seed)]["game_over_events"] for seed in _SEEDS)
    else:
        checks["game_over_total_lower"] = sum(
            result["candidate"][str(seed)]["game_over_events"] for seed in _SEEDS
        ) < sum(result["previous"][str(seed)]["game_over_events"] for seed in _SEEDS)

    return {"checks": checks, "by_seed": by_seed, "passed": all(checks.values())}


def run_experiment(output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite evaluation output: {output}")
    games = runner._load_games(ROOT / "入力/Kaggle/environment_files")
    if len(games) != 25:
        raise RuntimeError(f"Expected 25 public environments, found {len(games)}")
    split = list(games)
    random.Random(20261022).shuffle(split)
    development = _run_stage("dev", split[:5])
    development_gate = _gate("dev", development)
    holdout = _run_stage("holdout", split[5:]) if development_gate["passed"] else None
    holdout_gate = _gate("holdout", holdout) if holdout is not None else None

    result = {
        "evaluation": "ARC3-RUN-002-C2-017",
        "scope": "public local environments; fixed split seed 20261022; dev/holdout seeds 7/31/73; 80 requests; SDK RESET after GAME_OVER",
        "public_environment_count": len(games),
        "development_candidate_rule": "when an untried dominant or rare color is available on the current public board, defer eligible 10-50% non-dominant colors; fallback to existing eligible colors if no alternative remains",
        "development": development,
        "development_gate": development_gate,
        "holdout": holdout,
        "holdout_gate": holdout_gate,
        "decision": (
            "candidate_only"
            if holdout_gate and holdout_gate["passed"]
            else "reject_no_holdout"
            if not development_gate["passed"]
            else "reject_holdout"
        ),
        "interpretation_boundary": "public observational feature ablation only; no official score or hidden-environment claim",
        "source_sha256": {
            "experiment_runner": _sha256(Path(__file__)),
            "evaluation_runner": _sha256(ROOT / "検証/ARC3探索Actionローカル評価.py"),
            "policy": _sha256(ROOT / "接続/観測駆動探索Action.py"),
            "boundary": _sha256(ROOT / "接続/ARC3境界.py"),
            "starter_agent": _sha256(ROOT / "入力/Kaggle/ARC-AGI-3-Agents/agents/agent.py"),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    result["output_sha256"] = _sha256(output)
    return result


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "出力/ARC3-RUN-002-local/C2-017-action6-color-frequency.json",
    )
    args = parser.parse_args()
    result = run_experiment(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
