"""level 1完了に関係する公開action結果を匿名集計する。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
import sys
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "検証"))
from ARC3探索Actionローカル評価 import _load_games, _run_game


def _action_kind_and_outcome(record: dict[str, Any]) -> tuple[str, str] | None:
    if record.get("lifecycle_action"):
        return None
    kind = "coordinate" if record.get("action_id") == 6 else "discrete"
    if int(record.get("level_delta", 0)) > 0:
        outcome = "level_progress"
    elif record.get("after_state") == "GAME_OVER":
        outcome = "game_over"
    elif int(record.get("changed_cells", 0)) == 0:
        outcome = "no_op"
    else:
        outcome = "board_change_without_progress"
    return kind, outcome


def _new_counts() -> dict[str, Any]:
    return {
        kind: {
            "selected": 0,
            "no_op": 0,
            "board_change_without_progress": 0,
            "level_progress": 0,
            "game_over": 0,
        }
        for kind in ("discrete", "coordinate")
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _public_input_hash(root: Path) -> tuple[int, str]:
    hashes = sorted(_sha256(path) for path in root.rglob("*") if path.is_file())
    return len(hashes), hashlib.sha256("\n".join(hashes).encode("ascii")).hexdigest()


def _source_hashes() -> dict[str, str]:
    paths = {
        "evaluator": Path(__file__),
        "targeted_test": ROOT / "検証/test_ARC3level1完了原因監査.py",
        "local_policy_evaluator": ROOT / "検証/ARC3探索Actionローカル評価.py",
        "policy": ROOT / "接続/観測駆動探索Action.py",
    }
    return {name: _sha256(path) for name, path in paths.items()}


def _audit(environment_dir: Path, seeds: list[int], split_seed: int) -> dict[str, Any]:
    games = _load_games(environment_dir)
    if len(games) != 25:
        raise ValueError(f"expected 25 public environments, got {len(games)}")
    input_count, input_hash = _public_input_hash(environment_dir)
    global_counts = _new_counts()
    seed_results = []

    for seed in seeds:
        counts = _new_counts()
        completed_level1_runs = 0
        reached_level2_runs = 0
        wins = game_over = resets = illegal = duplicate = 0
        selected_game_count = 0
        for metadata, path in games:
            run = _run_game(
                metadata,
                path,
                "exploration",
                seed=seed,
                policy_seed=seed,
                max_actions=80,
                retry_game_over=True,
            )
            selected_game_count += 1
            completed_level1_runs += int(run["levels_completed"] >= 1)
            reached_level2_runs += int(run["levels_completed"] >= 2)
            wins += int(run["final_state"] == "WIN")
            game_over += int(run["game_over_events"])
            resets += int(run["reset_actions"])
            illegal += int(run["illegal_action_attempts"])
            duplicate += int(run["duplicate_observation_steps"])

            gameplay_actions = 0
            for record in run["action_responses"]:
                categorized = _action_kind_and_outcome(record)
                if categorized is None:
                    continue
                kind, outcome = categorized
                counts[kind]["selected"] += 1
                counts[kind][outcome] += 1
                global_counts[kind]["selected"] += 1
                global_counts[kind][outcome] += 1
                gameplay_actions += 1
            if gameplay_actions != run["gameplay_actions"]:
                raise ValueError("categorized action count does not match gameplay actions")

        seed_results.append(
            {
                "seed": seed,
                "games": selected_game_count,
                "level1_completed_runs": completed_level1_runs,
                "level2_reached_runs": reached_level2_runs,
                "wins": wins,
                "action_outcomes": counts,
                "game_over": game_over,
                "resets": resets,
                "illegal": illegal,
                "duplicate": duplicate,
            }
        )

    return {
        "audit": "public-level1-completion-action-outcomes",
        "split_seed": split_seed,
        "environment_seeds": seeds,
        "policy_seed_rule": "policy seed equals environment seed",
        "max_actions_per_game": 80,
        "public_environments": len(games),
        "public_input": {
            "file_count": input_count,
            "content_set_sha256": input_hash,
        },
        "source_sha256": _source_hashes(),
        "runs_by_seed": seed_results,
        "all_seed_action_outcomes": global_counts,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Anonymously audit public action outcomes related to level progress"
    )
    parser.add_argument(
        "--environment-dir",
        type=Path,
        default=ROOT / "入力/Kaggle/environment_files",
    )
    parser.add_argument("--split-seed", type=int, default=20261022)
    parser.add_argument("--seeds", type=int, nargs="+", default=[7, 31, 73])
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "出力/ARC3-RUN-003-local/C1-016-level1-action-outcomes.json",
    )
    args = parser.parse_args()
    if args.output.exists():
        parser.error(f"refusing to overwrite existing result: {args.output}")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    result = _audit(args.environment_dir, args.seeds, args.split_seed)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
