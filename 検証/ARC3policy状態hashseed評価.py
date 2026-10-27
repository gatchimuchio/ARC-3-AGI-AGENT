"""現在の公開観測と同一run内統計からtie-break seedを作る隔離評価。"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "検証"))

import ARC3探索Actionローカル評価 as 評価器  # noqa: E402
from 接続.観測駆動探索Action import 観測駆動探索方針  # noqa: E402

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
_OUTPUT = ROOT / "出力/ARC3-RUN-003-local/C2-037-policy-state-hashseed.json"


class _現在観測決定seed方針(観測駆動探索方針):
    """各選択時にID-freeな現在観測とrun統計だけからRNGを再初期化する。"""

    def 選ぶ(self, 現在):
        self._rng = random.Random(_decision_seed(現在, self))
        return super().選ぶ(現在)


def _seed_material(現在, 方針: 観測駆動探索方針) -> dict[str, Any]:
    """公開観測と一般化された同一run統計からseed材料を作る。"""
    盤面 = 現在.最新盤面
    return {
        "state": 現在.状態,
        "board": 盤面,
        "available_actions": sorted(現在.作用可能番号),
        "action_count": 方針._総作用数,
        "action_counts": sorted(方針._回数.items()),
        "action_rewards": sorted(方針._報酬合計.items()),
        "color_counts": sorted(方針._色回数.items()),
        "color_rewards": sorted(方針._色報酬合計.items()),
        "coordinate_attempt_count": len(方針._座標試行.get(盤面, set())),
    }


def _decision_seed(現在, 方針: 観測駆動探索方針) -> int:
    material = json.dumps(
        _seed_material(現在, 方針),
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    digest = hashlib.sha256(material).digest()
    return int.from_bytes(digest[:8], byteorder="big", signed=False)


def _empty_aggregate() -> dict[str, int]:
    return {key: 0 for key in _COUNTERS} | {"games": 0}


def _add_result(aggregate: dict[str, int], result: dict[str, Any]) -> None:
    aggregate["games"] += 1
    aggregate["actions"] += int(result["actions"])
    aggregate["levels_completed"] += int(result["levels_completed"])
    aggregate["wins"] += int(result["final_state"] == "WIN")
    aggregate["no_op_actions"] += int(result["no_op_actions"])
    aggregate["game_over_events"] += int(result["game_over_events"])
    aggregate["reset_actions"] += int(result["reset_actions"])
    aggregate["illegal_action_attempts"] += int(result["illegal_action_attempts"])
    aggregate["duplicate_observation_steps"] += int(result["duplicate_observation_steps"])
    aggregate["policy_holds"] += int(result["stop_reason"] == "exploration_hold")
    if result["actions"] != len(result["action_responses"]):
        raise RuntimeError("Action数と公開応答記録数が一致しない")


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _public_input_hash(root: Path) -> tuple[int, str]:
    hashes = sorted(_sha256(path) for path in root.rglob("*") if path.is_file())
    return len(hashes), hashlib.sha256("\n".join(hashes).encode("ascii")).hexdigest()


def _source_hashes() -> dict[str, str]:
    paths = {
        "evaluator": Path(__file__),
        "local_policy_evaluator": ROOT / "検証/ARC3探索Actionローカル評価.py",
        "policy": ROOT / "接続/観測駆動探索Action.py",
    }
    return {name: _sha256(path) for name, path in paths.items()}


def run(output: Path, environment_dir: Path) -> dict[str, Any]:
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite diagnostic output: {output}")

    games = 評価器._load_games(environment_dir)
    split = list(games)
    random.Random(20261022).shuffle(split)
    development = split[:5]
    if len(development) != 5:
        raise RuntimeError("fixed development split does not contain five environments")

    conditions = ("previous", "current")
    aggregates = {
        condition: {str(seed): _empty_aggregate() for seed in _SEEDS} for condition in conditions
    }
    same_start_pairs = {str(seed): 0 for seed in _SEEDS}
    paired_runs = {str(seed): 0 for seed in _SEEDS}
    previous_policy = 評価器.観測駆動探索方針
    started = time.perf_counter()
    評価器.観測駆動探索方針 = _現在観測決定seed方針
    try:
        for seed in _SEEDS:
            seed_key = str(seed)
            for metadata, metadata_path in development:
                pair: dict[str, dict[str, Any]] = {}
                for condition in conditions:
                    if condition == "previous":
                        評価器.観測駆動探索方針 = previous_policy
                    else:
                        評価器.観測駆動探索方針 = _現在観測決定seed方針
                    result = 評価器._run_game(
                        metadata,
                        metadata_path,
                        "exploration",
                        seed=seed,
                        policy_seed=seed,
                        max_actions=80,
                        retry_game_over=True,
                    )
                    pair[condition] = result
                    _add_result(aggregates[condition][seed_key], result)

                old, current = pair["previous"], pair["current"]
                same_start = (
                    old["initial_state"] == current["initial_state"]
                    and old["initial_levels_completed"] == current["initial_levels_completed"]
                    and old["initial_available_actions"] == current["initial_available_actions"]
                    and old["initial_board"] == current["initial_board"]
                )
                paired_runs[seed_key] += 1
                same_start_pairs[seed_key] += int(same_start)
    finally:
        評価器.観測駆動探索方針 = previous_policy

    deltas = {
        str(seed): {
            key: aggregates["current"][str(seed)][key] - aggregates["previous"][str(seed)][key]
            for key in _COUNTERS
        }
        for seed in _SEEDS
    }
    seed_checks = {
        str(seed): {
            "paired_starts_match": (
                same_start_pairs[str(seed)] == paired_runs[str(seed)] == len(development)
            ),
            "levels_not_lower": deltas[str(seed)]["levels_completed"] >= 0,
            "wins_not_lower": deltas[str(seed)]["wins"] >= 0,
            "game_over_not_higher": deltas[str(seed)]["game_over_events"] <= 0,
            "legal_lifecycle_no_hold_or_duplicate": all(
                aggregates["current"][str(seed)][key] == 0
                for key in (
                    "illegal_action_attempts",
                    "duplicate_observation_steps",
                    "policy_holds",
                )
            ),
        }
        for seed in _SEEDS
    }
    accepted = all(all(checks.values()) for checks in seed_checks.values())
    input_count, input_hash = _public_input_hash(environment_dir)
    report = {
        "指示ID": "ARC3-RUN-003-C2-037",
        "評価": "public_local_environment_paired_policy_rng_ablation",
        "split": "development",
        "split_seed": 20261022,
        "environments_per_seed": len(development),
        "environment_seeds": list(_SEEDS),
        "max_actions_per_run": 80,
        "retry_game_over": True,
        "conditions": {
            "previous": "existing policy RNG seeded from environment seed",
            "current": "per-selection SHA256 seed from current public observation and policy statistics",
        },
        "previous": aggregates["previous"],
        "current": aggregates["current"],
        "delta": deltas,
        "paired_start_match_counts": same_start_pairs,
        "paired_run_counts": paired_runs,
        "acceptance_checks": seed_checks,
        "decision": "accept_for_separate_C3_test" if accepted else "reject",
        "public_input": {"file_count": input_count, "content_set_sha256": input_hash},
        "source_sha256": _source_hashes(),
        "elapsed_seconds": round(time.perf_counter() - started, 3),
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    raw = json.dumps(report, ensure_ascii=False, indent=2).encode("utf-8")
    output.write_bytes(raw)
    return {
        "output": str(output),
        "output_sha256": hashlib.sha256(raw).hexdigest(),
        "summary": report,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--environment-dir", type=Path, default=ROOT / "入力/Kaggle/environment_files"
    )
    parser.add_argument("--output", type=Path, default=_OUTPUT)
    args = parser.parse_args()
    print(json.dumps(run(args.output, args.environment_dir), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
