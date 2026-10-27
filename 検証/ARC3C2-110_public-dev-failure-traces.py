"""Capture reproducible public-state traces for the fixed ARC3 dev split."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import random
import runpy
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

SPLIT_SEED = 20261022
POLICY_SEED = 7
MAX_ACTIONS = 80
BASELINE_RUNNER = ROOT / "検証/ARC3C2-109_ACTION6-family-HDS-paired-evaluation.py"
OUTPUT = ROOT / "出力/ARC3-RUN-003-local/C2-110/dev-failure-traces-seed-7.json"


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _observation_snapshot(observed: Any) -> dict[str, Any]:
    return {
        "observation_number": observed.観測通番,
        "state": observed.状態,
        "completed_levels": observed.完了レベル数,
        "available_actions": list(observed.作用可能番号),
        "board": [list(row) for row in observed.最新盤面],
    }


def collect() -> dict[str, Any]:
    experiment = runpy.run_path(str(BASELINE_RUNNER))
    load_games = experiment["_load_games"]
    run_game = experiment["_run"]
    policy_type = experiment["_CurrentHDSRankingPolicy"]
    score_game = experiment["_スコアを計算する"]
    games = load_games(ROOT / "入力/Kaggle/environment_files")
    random.Random(SPLIT_SEED).shuffle(games)
    selected = games[:5]

    evaluator_globals = run_game.__globals__["_run_game"].__globals__
    observe = evaluator_globals["観測する"]
    traces: list[dict[str, Any]] = []

    for metadata, metadata_path in selected:
        snapshots: list[dict[str, Any]] = []

        def capture(response: Any, **kwargs: Any) -> Any:
            observed = observe(response, **kwargs)
            snapshots.append(_observation_snapshot(observed))
            return observed

        evaluator_globals["観測する"] = capture
        try:
            run = run_game(metadata, metadata_path, POLICY_SEED, policy_type)
        finally:
            evaluator_globals["観測する"] = observe

        score, levels, _ = score_game(metadata.get("baseline_actions", []), run)
        traces.append(
            {
                "game_id": metadata["game_id"],
                "metadata_path": metadata_path.relative_to(ROOT).as_posix(),
                "metadata_sha256": _sha256(metadata_path),
                "score": score,
                "levels": levels,
                "actions": run["actions"],
                "no_op_actions": run["no_op_actions"],
                "illegal_action_attempts": run["illegal_action_attempts"],
                "stop_reason": run["stop_reason"],
                "policy_action_stats": run["policy_action_stats"],
                "observations": snapshots,
                "action_responses": run["action_responses"],
            }
        )

    return {
        "work_item": "C2-110",
        "method": "Current production-like HDS ranking policy, unchanged; one matched diagnostic seed per game.",
        "split_seed": SPLIT_SEED,
        "policy_seed": POLICY_SEED,
        "max_actions_per_game": MAX_ACTIONS,
        "game_ids": [metadata["game_id"] for metadata, _ in selected],
        "runner": BASELINE_RUNNER.relative_to(ROOT).as_posix(),
        "runner_sha256": _sha256(BASELINE_RUNNER),
        "traces": traces,
    }


def main() -> None:
    payload = json.dumps(collect(), ensure_ascii=False, indent=2)
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(payload + "\n", encoding="utf-8")
    print(json.dumps({"output": str(OUTPUT), "sha256": _sha256(OUTPUT)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
