"""同一公開盤面で既知no-op Actionを再選択する機会を匿名集計する。"""

from __future__ import annotations

import argparse
from collections import defaultdict
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
_OUTPUT = ROOT / "出力/ARC3-RUN-003-local/C1-011-state-action-revisit-audit.json"
_ACTIVE_AUDIT: "_AuditCounters | None" = None


@dataclass
class _AuditCounters:
    decisions: int = 0
    board_revisits: int = 0
    known_noop_legal_opportunities: int = 0
    known_noop_with_legal_alternative: int = 0
    selected_known_noop: int = 0
    selected_known_noop_with_legal_alternative: int = 0
    post_reset_decisions: int = 0
    post_reset_same_initial_board: int = 0
    post_reset_known_noop_with_legal_alternative: int = 0
    post_reset_selected_known_noop_with_legal_alternative: int = 0
    discrete_noop_observations: int = 0


class _状態再訪監査方針(観測駆動探索方針):
    """方針は変えず、選択前の公開状態と既知no-opだけを計数する。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if _ACTIVE_AUDIT is None:
            raise RuntimeError("監査counterが開始されていない")
        self._audit = _ACTIVE_AUDIT
        self._既知no_op: dict[tuple[tuple[int, ...], ...], set[int]] = defaultdict(set)
        self._選択済み盤面: set[tuple[tuple[int, ...], ...]] = set()
        self._初期盤面: tuple[tuple[int, ...], ...] | None = None
        self._RESET後観測待ち = False

    def 選ぶ(self, 現在):
        if 現在.状態 == "GAME_OVER":
            self._RESET後観測待ち = True
            return super().選ぶ(現在)
        if 現在.状態 != "NOT_FINISHED":
            return super().選ぶ(現在)

        盤面 = 現在.最新盤面
        if self._初期盤面 is None:
            self._初期盤面 = 盤面
        RESET後 = self._RESET後観測待ち
        合法離散Action = {a for a in 現在.作用可能番号 if 1 <= a <= 7 and a != 6}
        既知no_op合法 = self._既知no_op.get(盤面, set()) & 合法離散Action
        別の合法離散Action = 合法離散Action - 既知no_op合法

        self._audit.decisions += 1
        self._audit.board_revisits += int(盤面 in self._選択済み盤面)
        self._audit.known_noop_legal_opportunities += int(bool(既知no_op合法))
        self._audit.known_noop_with_legal_alternative += int(
            bool(既知no_op合法 and 別の合法離散Action)
        )
        if RESET後:
            self._audit.post_reset_decisions += 1
            self._audit.post_reset_same_initial_board += int(盤面 == self._初期盤面)
            self._audit.post_reset_known_noop_with_legal_alternative += int(
                bool(既知no_op合法 and 別の合法離散Action)
            )

        choice = super().選ぶ(現在)
        if choice is not None and choice.作用番号 in 既知no_op合法:
            self._audit.selected_known_noop += 1
            if 別の合法離散Action:
                self._audit.selected_known_noop_with_legal_alternative += 1
                if RESET後:
                    self._audit.post_reset_selected_known_noop_with_legal_alternative += 1
        self._選択済み盤面.add(盤面)
        self._RESET後観測待ち = False
        return choice

    def 応答を記録する(self, 作用前, action, 作用後):
        result = super().応答を記録する(作用前, action, 作用後)
        if action.作用番号 != 6 and result["可視変化セル数"] == 0 and result["完了レベル増分"] == 0:
            self._既知no_op[作用前.最新盤面].add(action.作用番号)
            self._audit.discrete_noop_observations += 1
        return result


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
    illegal_counts = {str(seed): 0 for seed in _SEEDS}
    duplicate_counts = {str(seed): 0 for seed in _SEEDS}
    holds_counts = {str(seed): 0 for seed in _SEEDS}
    actions_counts = {str(seed): 0 for seed in _SEEDS}
    policy_before = 評価器.観測駆動探索方針
    started = time.perf_counter()

    try:
        評価器.観測駆動探索方針 = _状態再訪監査方針
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
                illegal_counts[seed_key] += int(result["illegal_action_attempts"])
                duplicate_counts[seed_key] += int(result["duplicate_observation_steps"])
                holds_counts[seed_key] += int(result["stop_reason"] == "exploration_hold")
                actions_counts[seed_key] += int(result["actions"])
    finally:
        評価器.観測駆動探索方針 = policy_before
        _ACTIVE_AUDIT = None

    per_seed = {seed: asdict(counter) for seed, counter in counts.items()}
    selected_opportunities = {
        seed: data["selected_known_noop_with_legal_alternative"] for seed, data in per_seed.items()
    }
    supported = (
        sum(selected_opportunities.values()) >= 10
        and sum(value > 0 for value in selected_opportunities.values()) >= 2
    )
    input_count, input_hash = _public_input_hash(environment_dir)
    report = {
        "指示ID": "ARC3-RUN-003-C1-011",
        "評価": "public_local_same_board_known_noop_reselection_audit",
        "split": "development",
        "split_seed": 20261022,
        "environments_per_seed": len(development),
        "environment_seeds": list(_SEEDS),
        "max_actions_per_run": 80,
        "retry_game_over": True,
        "監査counter_各seed": per_seed,
        "runs_per_seed": run_counts,
        "actions_per_seed": actions_counts,
        "illegal_actions_per_seed": illegal_counts,
        "duplicate_steps_per_seed": duplicate_counts,
        "policy_holds_per_seed": holds_counts,
        "C2候補支持条件": {
            "threshold": 10,
            "seeds_required": 2,
            "selected_known_noop_with_legal_alternative": selected_opportunities,
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
