"""25公開ARC3環境の応答frame列を匿名集計する読み取り専用診断。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
import sys
from typing import Any

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "検証"))

import ARC3探索Actionローカル評価 as runner  # noqa: E402


def _grid_sequence(raw_frames: Any) -> tuple[tuple[tuple[int, ...], ...], ...]:
    """SDKのgrid配列を不変の整数行列列へ変換する。"""
    if raw_frames is None:
        return ()
    if not isinstance(raw_frames, (list, tuple)):
        raise ValueError("frame sequence is not a list")
    grids = []
    for raw in raw_frames:
        array = np.asarray(raw)
        if array.ndim != 2 or not array.size:
            raise ValueError("frame grid is empty or not two-dimensional")
        if array.shape[0] > 64 or array.shape[1] > 64:
            raise ValueError("frame grid exceeds the official dimensions")
        grids.append(tuple(tuple(int(value) for value in row) for row in array.tolist()))
    return tuple(grids)


def _transition_metrics(before: Any, after: Any) -> dict[str, int]:
    """one SDK response内のgrid数・差分のみを計測する。"""
    old = _grid_sequence(getattr(before, "frame", None))
    new = _grid_sequence(getattr(after, "frame", None))
    result = {
        "response_count": 1,
        "response_frame_count": len(new),
        "multi_frame_responses": int(len(new) > 1),
        "distinct_response_grids": len(set(new)),
        "intermediate_grids_different_from_final": len(set(new[:-1]) - {new[-1]}) if new else 0,
        "transient_cells_returning_to_prior_value": 0,
        "uncomparable_transitions": 0,
    }
    if not old or not new:
        result["uncomparable_transitions"] = 1
        return result
    prior, final = old[-1], new[-1]
    shapes = {(len(grid), len(grid[0])) for grid in (prior, final, *new[:-1]) if grid and grid[0]}
    if len(shapes) != 1 or any(len(set(map(len, grid))) != 1 for grid in (prior, final, *new[:-1])):
        result["uncomparable_transitions"] = 1
        return result
    transient = 0
    for y, row in enumerate(prior):
        for x, value in enumerate(row):
            if final[y][x] == value and any(frame[y][x] != value for frame in new[:-1]):
                transient += 1
    result["transient_cells_returning_to_prior_value"] = transient
    return result


def _empty_metrics() -> dict[str, int]:
    return {
        "response_count": 0,
        "response_frame_count": 0,
        "multi_frame_responses": 0,
        "distinct_response_grids": 0,
        "intermediate_grids_different_from_final": 0,
        "transient_cells_returning_to_prior_value": 0,
        "uncomparable_transitions": 0,
    }


def _add(target: dict[str, int], source: dict[str, int]) -> None:
    for key in target:
        target[key] += source[key]


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run_audit(output: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite diagnostic output: {output}")
    games = runner._load_games(ROOT / "入力/Kaggle/environment_files")
    split = list(games)
    random.Random(20261022).shuffle(split)

    from arc_agi import LocalEnvironmentWrapper

    original_step = LocalEnvironmentWrapper.step
    action_totals: dict[str, dict[str, int]] = {}
    game_metrics: list[dict[str, int]] = []
    active: list[dict[str, int]] | None = None

    def instrumented_step(self, action, data=None, reasoning=None):
        nonlocal active
        before = getattr(self, "observation_space", None)
        response = original_step(self, action, data=data, reasoning=reasoning)
        if active is None:
            raise RuntimeError("instrumentation received a step outside a game run")
        if response is None:
            current = _empty_metrics()
            current["response_count"] = 1
            current["uncomparable_transitions"] = 1
        else:
            current = _transition_metrics(before, response)
        active.append(current)
        action_name = getattr(action, "name", str(action))
        bucket = action_totals.setdefault(action_name, _empty_metrics())
        _add(bucket, current)
        return response

    LocalEnvironmentWrapper.step = instrumented_step
    try:
        for metadata, metadata_path in split:
            active = []
            result = runner._run_game(
                metadata,
                metadata_path,
                "exploration",
                seed=31,
                max_actions=80,
                retry_game_over=True,
            )
            if len(active) != result["actions"]:
                raise RuntimeError("captured response count differs from evaluator action count")
            aggregate = _empty_metrics()
            for event in active:
                _add(aggregate, event)
            game_metrics.append(aggregate)
        active = None
    finally:
        LocalEnvironmentWrapper.step = original_step

    aggregate = _empty_metrics()
    for game in game_metrics:
        _add(aggregate, game)
    result = {
        "evaluation": "ARC3-RUN-002-C1-003",
        "scope": "25 public environments, current exploration policy, action seed 31, max 80 requests, SDK RESET after GAME_OVER",
        "split_seed": 20261022,
        "public_environment_count": len(games),
        "all_game_runs_same_public_policy": True,
        "game_count_with_multiframe_response": sum(
            g["multi_frame_responses"] > 0 for g in game_metrics
        ),
        "aggregate": aggregate,
        "by_action_name": action_totals,
        "per_game_anonymous_counts": game_metrics,
        "interpretation_boundary": "frame order and grid differences are measured; animation or gameplay meaning is not inferred",
        "source_sha256": {
            "runner": _sha256(ROOT / "検証/ARC3探索Actionローカル評価.py"),
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
        default=ROOT / "出力/ARC3-RUN-002-local/C1-003-multiframe-audit.json",
    )
    args = parser.parse_args()
    result = run_audit(args.output)
    print(
        json.dumps(
            {k: v for k, v in result.items() if k != "per_game_anonymous_counts"},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
