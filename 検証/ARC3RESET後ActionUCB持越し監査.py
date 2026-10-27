"""RESET後のAction/color UCB統計の持越しと選択影響を匿名監査する。"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
import copy
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
_OUTPUT = ROOT / "出力/ARC3-RUN-003-local/C1-014-reset-action-ucb-audit.json"
_ACTIVE_AUDIT: "_AuditCounters | None" = None


@dataclass
class _AuditCounters:
    post_reset_decisions: int = 0
    same_as_initial_public_condition: int = 0
    post_reset_board_previously_seen: int = 0
    legal_actions_total: int = 0
    legal_actions_with_prior_statistics: int = 0
    decisions_all_legal_actions_previously_sampled: int = 0
    shadow_comparisons: int = 0
    shadow_choice_differences: int = 0


class _RESET後Action統計監査方針(観測駆動探索方針):
    """Action選択を変えず、RESET後に持ち越されたUCBの影響をshadow比較する。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if _ACTIVE_AUDIT is None:
            raise RuntimeError("監査counterが開始されていない")
        self._audit = _ACTIVE_AUDIT
        self._awaiting_post_reset_decision = False
        self._initial_public_condition: tuple[Any, ...] | None = None

    @staticmethod
    def _public_condition(現在) -> tuple[Any, ...]:
        return (
            現在.状態,
            現在.完了レベル数,
            tuple(sorted(a for a in 現在.作用可能番号 if 1 <= a <= 7)),
            現在.最新盤面,
        )

    @staticmethod
    def _clear_ucb_statistics(policy: 観測駆動探索方針) -> None:
        policy._回数.clear()
        policy._報酬合計.clear()
        policy._総作用数 = 0
        policy._色回数.clear()
        policy._色報酬合計.clear()

    def 選ぶ(self, 現在):
        if 現在.状態 == "GAME_OVER":
            action = super().選ぶ(現在)
            self._awaiting_post_reset_decision = action is not None and action.作用番号 == 0
            return action

        if 現在.状態 != "NOT_FINISHED":
            return super().選ぶ(現在)

        condition = self._public_condition(現在)
        if self._initial_public_condition is None:
            self._initial_public_condition = condition

        if not self._awaiting_post_reset_decision:
            return super().選ぶ(現在)

        legal = tuple(sorted(a for a in 現在.作用可能番号 if 1 <= a <= 7))
        if not legal:
            self._awaiting_post_reset_decision = False
            return super().選ぶ(現在)

        was_seen = bool(現在.最新盤面) and 現在.最新盤面 in self._既観測盤面
        sampled = sum(self._回数.get(action, 0) > 0 for action in legal)
        rng_state = self._rng.getstate()
        shadow = copy.deepcopy(self)
        self._clear_ucb_statistics(shadow)
        shadow_choice = 観測駆動探索方針.選ぶ(shadow, 現在)
        self._rng.setstate(rng_state)
        live_choice = super().選ぶ(現在)

        self._audit.post_reset_decisions += 1
        self._audit.same_as_initial_public_condition += int(
            condition == self._initial_public_condition
        )
        self._audit.post_reset_board_previously_seen += int(was_seen)
        self._audit.legal_actions_total += len(legal)
        self._audit.legal_actions_with_prior_statistics += sampled
        self._audit.decisions_all_legal_actions_previously_sampled += int(sampled == len(legal))
        self._audit.shadow_comparisons += 1
        self._audit.shadow_choice_differences += int(shadow_choice != live_choice)
        self._awaiting_post_reset_decision = False
        return live_choice


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
        "targeted_test": ROOT / "検証/test_ARC3RESET後ActionUCB持越し監査.py",
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

    counters = {str(seed): _AuditCounters() for seed in _SEEDS}
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
        評価器.観測駆動探索方針 = _RESET後Action統計監査方針
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
                _sum_counts(counters[seed_key], _ACTIVE_AUDIT)
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

    per_seed = {seed: asdict(counter) for seed, counter in counters.items()}
    supported_seeds = {
        seed: (
            per_seed[seed]["same_as_initial_public_condition"] >= 3
            and per_seed[seed]["decisions_all_legal_actions_previously_sampled"] >= 3
            and per_seed[seed]["shadow_choice_differences"] >= 3
        )
        for seed in per_seed
    }
    supported = (
        sum(supported_seeds.values()) >= 2
        and all(run_counts[str(seed)] == len(development) for seed in _SEEDS)
        and all(illegal_counts[str(seed)] == 0 for seed in _SEEDS)
        and all(duplicate_counts[str(seed)] == 0 for seed in _SEEDS)
        and all(holds_counts[str(seed)] == 0 for seed in _SEEDS)
    )
    input_count, input_hash = _public_input_hash(environment_dir)
    report = {
        "指示ID": "ARC3-RUN-003-C1-014",
        "評価": "public_local_post_reset_action_ucb_carryover_audit",
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
        "C2候補支持": {
            "same_initial_condition_per_seed_min": 3,
            "all_legal_previously_sampled_per_seed_min": 3,
            "shadow_choice_difference_per_seed_min": 3,
            "seeds_required": 2,
            "supported_seeds": supported_seeds,
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
