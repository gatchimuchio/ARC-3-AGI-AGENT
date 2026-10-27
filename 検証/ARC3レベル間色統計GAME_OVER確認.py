"""C4-002で見えたGAME_OVER差を固定holdoutで確認する。"""

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

import ARC3レベル間色統計評価 as color_transfer  # noqa: E402
import ARC3探索Actionローカル評価 as runner  # noqa: E402

_SEEDS = (7, 31, 73)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _gate(result: dict[str, Any]) -> dict[str, Any]:
    checks_by_seed = {}
    for seed in _SEEDS:
        key = str(seed)
        previous = result["previous"][key]
        candidate = result["candidate"][key]
        checks_by_seed[key] = {
            "levels_not_lower": candidate["levels_completed"] >= previous["levels_completed"],
            "no_op_not_higher": candidate["no_op_actions"] <= previous["no_op_actions"],
            "game_over_not_higher": candidate["game_over_events"]
            <= previous["game_over_events"],
            "holds_zero": candidate["policy_holds"] == 0,
            "illegal_zero": candidate["illegal_action_attempts"] == 0,
            "duplicates_zero": candidate["duplicate_observation_steps"] == 0,
        }
    previous_game_over = sum(
        result["previous"][str(seed)]["game_over_events"] for seed in _SEEDS
    )
    candidate_game_over = sum(
        result["candidate"][str(seed)]["game_over_events"] for seed in _SEEDS
    )
    checks = {
        "all_previous_runs_match_C2-003": all(
            all(seed_checks.values())
            for seed_checks in result["previous_matches_C2-003"].values()
        ),
        "all_paired_public_starts_match": all(
            result["same_public_start_pairs"][str(seed)]
            == result["paired_environment_runs"][str(seed)]
            for seed in _SEEDS
        ),
        "levels_not_lower_each_seed": all(
            seed_checks["levels_not_lower"] for seed_checks in checks_by_seed.values()
        ),
        "no_op_not_higher_each_seed": all(
            seed_checks["no_op_not_higher"] for seed_checks in checks_by_seed.values()
        ),
        "game_over_not_higher_each_seed": all(
            seed_checks["game_over_not_higher"] for seed_checks in checks_by_seed.values()
        ),
        "holds_illegal_duplicates_zero": all(
            seed_checks["holds_zero"]
            and seed_checks["illegal_zero"]
            and seed_checks["duplicates_zero"]
            for seed_checks in checks_by_seed.values()
        ),
        "total_game_over_reduction_at_least_two": previous_game_over - candidate_game_over
        >= 2,
        "game_over_reduced_in_at_least_two_seeds": sum(
            result["candidate"][str(seed)]["game_over_events"]
            < result["previous"][str(seed)]["game_over_events"]
            for seed in _SEEDS
        )
        >= 2,
    }
    return {"checks": checks, "by_seed": checks_by_seed, "passed": all(checks.values())}


def run_experiment(output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite evaluation output: {output}")
    games = runner._load_games(ROOT / "入力/Kaggle/environment_files")
    if len(games) != 25:
        raise RuntimeError(f"Expected 25 public environments, found {len(games)}")
    split = list(games)
    random.Random(20261022).shuffle(split)
    stage = color_transfer._run_stage("holdout", split[5:], _SEEDS)
    gate = _gate(stage)
    result = {
        "evaluation": "ARC3-RUN-002-C4-003",
        "scope": "fixed public holdout 20 environments; action seeds 7/31/73; max 80 requests; SDK RESET after GAME_OVER",
        "split_seed": 20261022,
        "public_environment_count": len(games),
        "candidate_rule": "C4-002 unchanged: clear only color UCB counts/rewards after positive level progress",
        "development_evidence": {
            "source": "C4-002 fixed dev 5 environments, seeds 7/31/73",
            "levels_previous_candidate": [3, 3],
            "no_op_previous_candidate": [35, 35],
            "game_over_previous_candidate": [18, 16],
            "interpretation": "GAME_OVER was lower by one in seeds 31 and 73; no-op and completed levels were unchanged",
        },
        "holdout": stage,
        "holdout_gate": gate,
        "decision": "candidate_for_C6_review" if gate["passed"] else "reject_color_reset_transfer",
        "source_sha256": {
            "experiment_runner": _sha256(Path(__file__)),
            "color_transfer_runner": _sha256(ROOT / "検証/ARC3レベル間色統計評価.py"),
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
        default=ROOT / "出力/ARC3-RUN-002-local/C4-003-level-color-gameover-holdout.json",
    )
    args = parser.parse_args()
    result = run_experiment(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
