"""C1-003のgrid監査値と現行no-op罰の重複を匿名集計する。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
import sys
from types import SimpleNamespace
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "検証"))

import ARC3探索Actionローカル評価 as runner  # noqa: E402
from ARC3複数Frame公開観測診断 import _empty_metrics, _grid_sequence, _transition_metrics  # noqa: E402

_EXTRA_KEYS = (
    "policy_noop_penalty",
    "evaluation_noop_actions",
    "policy_noop_multiframe",
    "policy_noop_intermediate_diff",
    "policy_noop_transient_cell_occurrences",
    "multiframe_level_progress_responses",
    "level_decrease_responses",
)
_SEEDS = (7, 31, 73)


def _empty() -> dict[str, int]:
    result = _empty_metrics()
    result.update({key: 0 for key in _EXTRA_KEYS})
    return result


def _merge(target: dict[str, int], source: dict[str, int]) -> None:
    for key, value in source.items():
        target[key] += value


def _snapshot(raw: Any) -> SimpleNamespace:
    """SDKが後続stepで更新し得るgrid列を、応答時点の値として複製する。"""
    grids = _grid_sequence(getattr(raw, "frame", None))
    return SimpleNamespace(
        frame=tuple(np.array(grid, dtype=int, copy=True) for grid in grids),
        levels_completed=int(getattr(raw, "levels_completed", 0)),
    )


def _classify(action_name: str, before: Any, after: Any) -> dict[str, int]:
    """現行探索no-op罰と評価器no-op計数を区別して分類する。"""
    old_layers = _grid_sequence(getattr(before, "frame", None))
    new_layers = _grid_sequence(getattr(after, "frame", None))
    before_levels = int(getattr(before, "levels_completed", 0))
    after_levels = int(getattr(after, "levels_completed", 0))
    delta = after_levels - before_levels
    unchanged = bool(old_layers and new_layers and old_layers[-1] == new_layers[-1])
    non_reset = action_name != "RESET"
    policy_noop = non_reset and unchanged and max(0, delta) == 0
    evaluation_noop = non_reset and unchanged and delta == 0
    response = _transition_metrics(before, after)
    return {
        "policy_noop_penalty": int(policy_noop),
        "evaluation_noop_actions": int(evaluation_noop),
        "policy_noop_multiframe": int(policy_noop and len(new_layers) > 1),
        "policy_noop_intermediate_diff": int(
            policy_noop and response["intermediate_grids_different_from_final"] > 0
        ),
        "policy_noop_transient_cell_occurrences": (
            response["transient_cells_returning_to_prior_value"] if policy_noop else 0
        ),
        "multiframe_level_progress_responses": int(len(new_layers) > 1 and delta > 0),
        "level_decrease_responses": int(delta < 0),
    }


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _existing_baseline(seed: int) -> dict[str, int]:
    expected = {
        key: 0
        for key in (
            "actions",
            "levels_completed",
            "wins",
            "no_op_actions",
            "game_over_events",
            "reset_actions",
        )
    }
    for stage in ("dev", "holdout"):
        path = ROOT / "出力/ARC3-RUN-002-local" / f"C2-003-after-{stage}-seed-{seed}.json"
        artifact = json.loads(path.read_text(encoding="utf-8"))
        aggregate = artifact["aggregate"]["exploration"]
        for key in expected:
            expected[key] += int(aggregate.get(key, 0))
    return expected


def run_audit(output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite diagnostic output: {output}")
    games = runner._load_games(ROOT / "入力/Kaggle/environment_files")
    split = list(games)
    random.Random(20261022).shuffle(split)

    from arc_agi import LocalEnvironmentWrapper

    original_step = LocalEnvironmentWrapper.step
    active: list[tuple[str, dict[str, int]]] | None = None
    previous_response_by_environment: dict[int, Any] = {}
    by_seed_action: dict[str, dict[str, dict[str, int]]] = {}
    by_seed: dict[str, dict[str, int]] = {}
    all_comparisons: dict[str, dict[str, int | bool]] = {}

    def instrumented_step(self, action, data=None, reasoning=None):
        nonlocal active
        # The evaluator advances from the previous step() return value. Keep that
        # exact observation as a value snapshot: SDK frame arrays can be mutated by
        # a later step even after the wrapper returned a new response object.
        before_raw = previous_response_by_environment.get(
            id(self), getattr(self, "observation_space", None)
        )
        before = _snapshot(before_raw) if before_raw is not None else None
        response = original_step(self, action, data=data, reasoning=reasoning)
        if active is None:
            raise RuntimeError("instrumentation received a step outside a game run")
        action_name = getattr(action, "name", str(action))
        metrics = _empty()
        if response is None:
            metrics["response_count"] = 1
            metrics["uncomparable_transitions"] = 1
            metrics["evaluation_noop_actions"] = 0
        else:
            after = _snapshot(response)
            _merge(metrics, _transition_metrics(before, after))
            _merge(metrics, _classify(action_name, before, after))
            previous_response_by_environment[id(self)] = after
        active.append((action_name, metrics))
        action_bucket = by_seed_action.setdefault(_ACTIVE_SEED[0], {}).setdefault(
            action_name, _empty()
        )
        _merge(action_bucket, metrics)
        return response

    _ACTIVE_SEED = [""]
    LocalEnvironmentWrapper.step = instrumented_step
    try:
        for seed in _SEEDS:
            seed_key = str(seed)
            _ACTIVE_SEED[0] = seed_key
            by_seed_action[seed_key] = {}
            seed_runs = {
                key: 0
                for key in (
                    "games",
                    "actions",
                    "levels_completed",
                    "wins",
                    "no_op_actions",
                    "game_over_events",
                    "reset_actions",
                    "policy_holds",
                    "illegal_action_attempts",
                    "duplicate_observation_steps",
                )
            }
            aggregate_events = _empty()
            for game_index, (metadata, metadata_path) in enumerate(split):
                active = []
                previous_response_by_environment.clear()
                game = runner._run_game(
                    metadata,
                    metadata_path,
                    "exploration",
                    seed=seed,
                    max_actions=80,
                    retry_game_over=True,
                )
                if len(active) != game["actions"]:
                    raise RuntimeError(
                        "captured response count differs from evaluator action count"
                    )
                captured_noop_by_action: dict[str, int] = {}
                for action_name, event in active:
                    captured_noop_by_action[action_name] = (
                        captured_noop_by_action.get(action_name, 0)
                        + event["evaluation_noop_actions"]
                    )
                evaluator_noop_by_action: dict[str, int] = {}
                for event in game["action_responses"]:
                    if (
                        not event["lifecycle_action"]
                        and event["changed_cells"] == 0
                        and event["level_delta"] == 0
                    ):
                        action_name = f"ACTION{event['action_id']}"
                        evaluator_noop_by_action[action_name] = (
                            evaluator_noop_by_action.get(action_name, 0) + 1
                        )
                if sum(captured_noop_by_action.values()) != game["no_op_actions"]:
                    raise RuntimeError(
                        f"captured no-op count differs from evaluator: seed={seed}, game_index={game_index}, "
                        f"captured={captured_noop_by_action}, evaluator={evaluator_noop_by_action}, "
                        f"expected_total={game['no_op_actions']}"
                    )
                seed_runs["games"] += 1
                for key in seed_runs:
                    if key == "games":
                        continue
                    seed_runs[key] += int(game.get(key, 0))
                for _, event in active:
                    _merge(aggregate_events, event)
            by_seed[seed_key] = {**seed_runs, **aggregate_events}
            expected = _existing_baseline(seed)
            compared = {key: int(seed_runs[key]) == value for key, value in expected.items()}
            if not all(compared.values()):
                raise RuntimeError(
                    f"policy execution differs from fixed C2-003 baseline for seed {seed}"
                )
            all_comparisons[seed_key] = {
                "expected": expected,
                "current": {key: int(seed_runs[key]) for key in expected},
                "matches": compared,
            }
        active = None
    finally:
        LocalEnvironmentWrapper.step = original_step

    result = {
        "evaluation": "ARC3-RUN-002-C1-004",
        "scope": "25 public environments, current exploration policy, seeds 7/31/73, max 80 requests, SDK RESET after GAME_OVER",
        "split_seed": 20261022,
        "public_environment_count": len(games),
        "baseline_matches": all(all(v["matches"].values()) for v in all_comparisons.values()),
        "baseline_comparisons": all_comparisons,
        "by_seed": by_seed,
        "by_seed_and_action_name": by_seed_action,
        "interpretation_boundary": "no-op overlap and frame differences are observational; no causal or semantic inference",
        "source_sha256": {
            "runner": _sha256(ROOT / "検証/ARC3探索Actionローカル評価.py"),
            "frame_audit": _sha256(ROOT / "検証/ARC3複数Frame公開観測診断.py"),
            "boundary": _sha256(ROOT / "接続/ARC3境界.py"),
            "policy": _sha256(ROOT / "接続/観測駆動探索Action.py"),
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
        default=ROOT / "出力/ARC3-RUN-002-local/C1-004-multiframe-noop-audit.json",
    )
    args = parser.parse_args()
    result = run_audit(args.output)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
