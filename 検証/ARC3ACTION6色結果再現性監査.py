"""同一公開盤面・ACTION6色の応答カテゴリ再現性を匿名監査する。"""

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
_OUTPUT = ROOT / "出力/ARC3-RUN-003-local/C1-015-action6-color-outcome-audit.json"
_ACTIVE_AUDIT: "_AuditCounters | None" = None


@dataclass
class _AuditCounters:
    decisions: int = 0
    action6_selections: int = 0
    repeated_board_color_selections: int = 0
    repeated_board_color_with_alternative_color: int = 0
    repeated_outcome_category_match: int = 0
    repeated_outcome_category_mismatch: int = 0
    eligible_color_opportunities: int = 0


class _ACTION6色結果監査方針(観測駆動探索方針):
    """選択を変えず、同盤面・色の公開結果カテゴリだけを照合する。"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if _ACTIVE_AUDIT is None:
            raise RuntimeError("監査counterが開始されていない")
        self._audit = _ACTIVE_AUDIT
        self._結果_by_state_color: dict[tuple[tuple[int, ...], ...], dict[int, str]] = defaultdict(
            dict
        )
        self._pending_repeat: tuple[tuple[tuple[int, ...], ...], int, str] | None = None

    def _未試行色候補(self, board) -> tuple[int, ...]:
        if (
            not board
            or len(board) > 64
            or not board[0]
            or len(board[0]) > 64
            or any(len(row) != len(board[0]) for row in board)
        ):
            return ()
        tried = self._座標試行.get(board, set())
        eligible = set()
        for y, row in enumerate(board):
            for x, color in enumerate(row):
                if (x, y) not in tried:
                    eligible.add(color)
        return tuple(sorted(eligible))

    def 選ぶ(self, 現在):
        if 現在.状態 != "NOT_FINISHED":
            return super().選ぶ(現在)

        self._audit.decisions += 1
        colors_before = self._未試行色候補(現在.最新盤面)
        known = self._結果_by_state_color.get(現在.最新盤面, {})
        choice = super().選ぶ(現在)
        self._pending_repeat = None
        if choice is None or choice.作用番号 != 6:
            return choice

        color = self._選択座標色
        if color is None:
            raise RuntimeError("ACTION6の選択色を取得できない")
        self._audit.action6_selections += 1
        previous_outcome = known.get(color)
        if previous_outcome is not None:
            self._audit.repeated_board_color_selections += 1
            if len(colors_before) > 1:
                self._audit.repeated_board_color_with_alternative_color += 1
                self._pending_repeat = (現在.最新盤面, color, previous_outcome)
        self._audit.eligible_color_opportunities += int(len(colors_before) > 1)
        return choice

    @staticmethod
    def _result_category(receipt: dict[str, Any]) -> str:
        if receipt["作用後状態"] in ("WIN", "GAME_OVER"):
            return "terminal"
        if receipt["完了レベル増分"] > 0:
            return "level_progress"
        if receipt["可視変化セル数"] > 0:
            return "board_change"
        return "no_op"

    def 応答を記録する(self, 作用前, action, 作用後):
        receipt = super().応答を記録する(作用前, action, 作用後)
        if action.作用番号 != 6:
            self._pending_repeat = None
            return receipt

        color = receipt["座標可視色"]
        if color is None:
            raise RuntimeError("ACTION6の応答色を取得できない")
        outcome = self._result_category(receipt)
        pending = self._pending_repeat
        if pending is not None and pending[:2] == (作用前.最新盤面, color):
            if pending[2] == outcome:
                self._audit.repeated_outcome_category_match += 1
            else:
                self._audit.repeated_outcome_category_mismatch += 1
        self._結果_by_state_color[作用前.最新盤面][color] = outcome
        self._pending_repeat = None
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
        "targeted_test": ROOT / "検証/test_ARC3ACTION6色結果再現性監査.py",
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
        評価器.観測駆動探索方針 = _ACTION6色結果監査方針
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
    repeats = {
        seed: data["repeated_board_color_with_alternative_color"] for seed, data in per_seed.items()
    }
    matches = sum(data["repeated_outcome_category_match"] for data in per_seed.values())
    mismatches = sum(data["repeated_outcome_category_mismatch"] for data in per_seed.values())
    compared = matches + mismatches
    match_rate = matches / compared if compared else 0.0
    supported = (
        sum(repeats.values()) >= 10
        and sum(value > 0 for value in repeats.values()) >= 2
        and match_rate >= 0.8
        and all(run_counts[str(seed)] == len(development) for seed in _SEEDS)
        and all(illegal_counts[str(seed)] == 0 for seed in _SEEDS)
        and all(duplicate_counts[str(seed)] == 0 for seed in _SEEDS)
        and all(holds_counts[str(seed)] == 0 for seed in _SEEDS)
    )
    input_count, input_hash = _public_input_hash(environment_dir)
    report = {
        "指示ID": "ARC3-RUN-003-C1-015",
        "評価": "public_local_state_action6_color_outcome_repeatability_audit",
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
        "C2候補支持条件": {
            "threshold_reselected_board_color_with_alternative": 10,
            "seeds_required": 2,
            "outcome_category_match_rate_minimum": 0.8,
            "reselected_pairs_by_seed": repeats,
            "outcome_category_match_rate": round(match_rate, 6),
            "compared_repeat_outcomes": compared,
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
