"""同一runで既観測盤面へ戻る可視遷移を匿名集計する。"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
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
_OUTPUT = ROOT / "出力/ARC3-RUN-003-local/C1-013-visible-board-cycle-audit.json"
_ACTIVE_AUDIT: "_AuditCounters | None" = None


@dataclass
class _AuditCounters:
    decisions: int = 0
    visible_nonterminal_transitions: int = 0
    transitions_to_previously_seen_board: int = 0


class _既観測盤面循環監査方針(観測駆動探索方針):
    """Action選択を変えず、既観測盤面へ戻る遷移を数える。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if _ACTIVE_AUDIT is None:
            raise RuntimeError("監査counterが開始されていない")
        self._audit = _ACTIVE_AUDIT

    def 選ぶ(self, 現在):
        if 現在.状態 == "NOT_FINISHED":
            self._audit.decisions += 1
        return super().選ぶ(現在)

    def 応答を記録する(self, 作用前, action, 作用後):
        receipt = super().応答を記録する(作用前, action, 作用後)
        if (
            作用後.状態 == "NOT_FINISHED"
            and receipt["完了レベル増分"] == 0
            and receipt["可視変化セル数"] > 0
        ):
            self._audit.visible_nonterminal_transitions += 1
            self._audit.transitions_to_previously_seen_board += int(not receipt["盤面新規性"])
        return receipt


def _sum_counts(target: _AuditCounters, source: _AuditCounters) -> None:
    for name, value in asdict(source).items():
        setattr(target, name, getattr(target, name) + value)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _public_input_hash(root: Path) -> tuple[int, str]:
    hashes = sorted(_sha256(path) for path in root.rglob("*") if path.is_file())
    return len(hashes), hashlib.sha256("\n".join(hashes).encode("ascii")).hexdigest()


def _source_hashes() -> dict[str, str]:
    paths = {
        "evaluator": Path(__file__),
        "targeted_test": ROOT / "検証/test_ARC3既観測盤面循環遷移監査.py",
        "local_policy_evaluator": ROOT / "検証/ARC3探索Actionローカル評価.py",
        "policy": ROOT / "接続/観測駆動探索Action.py",
    }
    return {name: _sha256(path) for name, path in paths.items()}


def run(output: Path, environment_dir: Path) -> dict[str, Any]:
    global _ACTIVE_AUDIT
    if output.exists():
        raise FileExistsError(f"Refusing to overwrite diagnostic output: {output}")

    games = 評価器._load_games(environment_dir)
    split = list(games)
    random.Random(20261022).shuffle(split)
    development = split[:5]
    if len(development) != 5:
        raise RuntimeError("fixed development split does not contain five environments")

    counts = {str(seed): _AuditCounters() for seed in _SEEDS}
    run_counts = {str(seed): 0 for seed in _SEEDS}
    actions_counts = {str(seed): 0 for seed in _SEEDS}
    levels_counts = {str(seed): 0 for seed in _SEEDS}
    no_op_counts = {str(seed): 0 for seed in _SEEDS}
    game_over_counts = {str(seed): 0 for seed in _SEEDS}
    reset_counts = {str(seed): 0 for seed in _SEEDS}
    illegal_counts = {str(seed): 0 for seed in _SEEDS}
    duplicate_counts = {str(seed): 0 for seed in _SEEDS}
    holds_counts = {str(seed): 0 for seed in _SEEDS}
    previous_policy = 評価器.観測駆動探索方針
    started = time.perf_counter()

    try:
        評価器.観測駆動探索方針 = _既観測盤面循環監査方針
        for seed in _SEEDS:
            seed_key = str(seed)
            for metadata, metadata_path in development:
                _ACTIVE_AUDIT = _AuditCounters()
                result = 評価器._run_game(
                    metadata,
                    metadata_path,
                    "exploration",
                    seed=seed,
                    policy_seed=seed,
                    max_actions=80,
                    retry_game_over=True,
                )
                _sum_counts(counts[seed_key], _ACTIVE_AUDIT)
                run_counts[seed_key] += 1
                actions_counts[seed_key] += int(result["actions"])
                levels_counts[seed_key] += int(result["levels_completed"])
                no_op_counts[seed_key] += int(result["no_op_actions"])
                game_over_counts[seed_key] += int(result["game_over_events"])
                reset_counts[seed_key] += int(result["reset_actions"])
                illegal_counts[seed_key] += int(result["illegal_action_attempts"])
                duplicate_counts[seed_key] += int(result["duplicate_observation_steps"])
                holds_counts[seed_key] += int(result["stop_reason"] == "exploration_hold")
    finally:
        評価器.観測駆動探索方針 = previous_policy
        _ACTIVE_AUDIT = None

    per_seed = {seed: asdict(counter) for seed, counter in counts.items()}
    revisit_counts = {
        seed: data["transitions_to_previously_seen_board"] for seed, data in per_seed.items()
    }
    rates = {
        seed: (
            round(
                per_seed[seed]["transitions_to_previously_seen_board"]
                / per_seed[seed]["visible_nonterminal_transitions"],
                6,
            )
            if per_seed[seed]["visible_nonterminal_transitions"]
            else 0.0
        )
        for seed in per_seed
    }
    supported = (
        sum(count >= 10 for count in revisit_counts.values()) >= 2
        and all(run_counts[str(seed)] == len(development) for seed in _SEEDS)
        and all(illegal_counts[str(seed)] == 0 for seed in _SEEDS)
        and all(duplicate_counts[str(seed)] == 0 for seed in _SEEDS)
        and all(holds_counts[str(seed)] == 0 for seed in _SEEDS)
    )
    input_count, input_hash = _public_input_hash(environment_dir)
    report = {
        "指示ID": "ARC3-RUN-003-C1-013",
        "評価": "public_local_visible_transition_to_seen_board_audit",
        "split": "development",
        "split_seed": 20261022,
        "environments_per_seed": len(development),
        "environment_seeds": list(_SEEDS),
        "max_actions_per_run": 80,
        "retry_game_over": True,
        "監査counter_各seed": per_seed,
        "runs_per_seed": run_counts,
        "actions_per_seed": actions_counts,
        "levels_per_seed": levels_counts,
        "no_op_per_seed": no_op_counts,
        "game_over_per_seed": game_over_counts,
        "reset_per_seed": reset_counts,
        "illegal_per_seed": illegal_counts,
        "duplicate_per_seed": duplicate_counts,
        "policy_holds_per_seed": holds_counts,
        "既観測盤面遷移率_per_seed": rates,
        "C2候補支持条件": {
            "threshold_per_seed": 10,
            "seeds_required": 2,
            "transitions_per_seed": revisit_counts,
            "supported": supported,
        },
        "decision": "open_separate_C2_instruction" if supported else "no_supported_C2_candidate",
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
