"""Paired public-dev ablation for HDS guidance using Action 6 target color."""

from __future__ import annotations

from collections import Counter
from datetime import datetime, timezone
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import random
import sys
import time
from importlib.metadata import version
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "検証"))

import ARC3HDS公開転移shadow評価 as transfer_eval
from ARC3公開RHAE評価 import _スコアを計算する
from ARC3MyAgent_local_smoke import load_games
from 接続.観測駆動探索Action import 観測駆動探索方針
from test_ARC3提出agent import _load_agent_module
from hds学習系統.型 import 外部入力


SPLIT_SEED = 20261022
SEEDS = (7, 31, 73)
MAX_ACTIONS = 80
DEFAULT_OUTPUT = ROOT / "運用/証拠/ARC26-UNIFIED/ARC3-C2-092-target-color-guidance-dev-20261027.json"
DEFAULT_CHECKPOINT = ROOT / "運用/証拠/ARC26-UNIFIED/ARC3-C2-092-target-color-guidance-dev-20261027.jsonl"
_RANK_TO_POLICY_REWARD = {0: -1.0, 1: 0.25, 2: 4.0, 3: 4.0}
_RANK_TO_OUTCOME = {0: "可視変化なし", 1: "盤面変化", 2: "レベル進行", 3: "勝利"}


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class _TargetColorGuidedPolicy(観測駆動探索方針):
    """Keep the exploration UCB and add one bounded HDS pseudo-observation."""

    guided_color_choices = 0
    guided_outcome_counts: Counter[str] = Counter()

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._hds_target_color_ranks: dict[int, int] = {}

    def _set_hds_target_color_ranks(self, ranks: dict[int, int]) -> None:
        self._hds_target_color_ranks = dict(ranks)

    def _座標を選ぶ(self, 盤面: tuple[tuple[int, ...], ...]) -> tuple[int, int, int] | None:
        if not 盤面 or len(盤面) > 64 or any(not row or len(row) > 64 for row in 盤面):
            return None
        color_points: dict[int, list[tuple[int, int]]] = {}
        for y, row in enumerate(盤面):
            for x, color in enumerate(row):
                color_points.setdefault(color, []).append((x, y))
        tried = self._座標試行.setdefault(盤面, set())
        remaining = {
            color: [point for point in points if point not in tried]
            for color, points in color_points.items()
        }
        eligible = [color for color in sorted(color_points) if remaining[color]]
        if not eligible:
            return None

        untried = [color for color in eligible if self._色回数.get(color, 0) == 0]
        if untried:
            # Preserve the base policy's first-visit coverage before adding a prior.
            color = self._rng.choice(untried)
        else:
            prior_colors = [color for color in eligible if color in self._hds_target_color_ranks]
            total = max(2, sum(self._色回数.values()) + len(prior_colors))
            values: dict[int, float] = {}
            for candidate in eligible:
                count = self._色回数[candidate]
                reward = self._色報酬合計[candidate]
                rank = self._hds_target_color_ranks.get(candidate)
                if rank is not None:
                    # One virtual observation only; UCB still controls exploration.
                    count += 1
                    reward += _RANK_TO_POLICY_REWARD[rank]
                values[candidate] = reward / count + self._色探索係数 * math.sqrt(
                    math.log(total) / count
                )
            best = max(values.values())
            color = self._rng.choice([candidate for candidate in eligible if values[candidate] == best])

        point = self._未試行座標を選ぶ(盤面, color, remaining[color])
        tried.add(point)
        rank = self._hds_target_color_ranks.get(color)
        if rank is not None:
            type(self).guided_color_choices += 1
            type(self).guided_outcome_counts[_RANK_TO_OUTCOME[rank]] += 1
        return point[0], point[1], color


class _TargetColorHDSAgent(_load_agent_module().MyAgent):
    query_attempts = 0
    query_cache_hits = 0
    query_status_counts: Counter[str] = Counter()
    target_rule_prediction_counts: Counter[str] = Counter()
    target_prediction_uses = 0
    missing_target_colors = 0

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._target_color_for_update: int | None = None
        self._target_color_query_cache: dict[tuple[Any, ...], int | None] = {}

    def _HDS作用前状態(self, observed) -> dict[str, Any]:
        state = _load_agent_module().MyAgent._HDS作用前状態(observed)
        if self._target_color_for_update is not None:
            state["対象色"] = self._target_color_for_update
        return state

    def _HDS作用応答を学ぶ(self, before, action, after) -> None:
        self._target_color_for_update = None
        if action.作用番号 == 6:
            x, y = action.引数.get("x"), action.引数.get("y")
            board = before.最新盤面
            if type(x) is int and type(y) is int and 0 <= y < len(board) and 0 <= x < len(board[y]):
                self._target_color_for_update = board[y][x]
            else:
                type(self).missing_target_colors += 1
        try:
            super()._HDS作用応答を学ぶ(before, action, after)
        finally:
            self._target_color_for_update = None

    @staticmethod
    def _target_color_rank(result: Any) -> int | None:
        content = getattr(result, "内容", None)
        if (
            not isinstance(content, dict)
            or getattr(result, "状態", None) not in ("出力", "断定保留")
        ):
            return None
        result_path = ("公開応答区分",)
        if any(
            isinstance(item, dict) and tuple(item.get("結果経路", ())) == result_path
            for item in content.get("競合群", ())
        ):
            return None
        target_rule_ids = {
            item.get("原理識別子")
            for item in content.get("有効原理群", ())
            if isinstance(item, dict)
            and tuple(item.get("結果経路", ())) == result_path
            and item.get("状態") == "適用範囲付き暫定原理"
            and item.get("採用状態") == "有効"
            and ("作用前公開状態", "対象色") in item.get("条件経路群", ())
        }
        predicted = {
            item.get("予測値")
            for item in content.get("予測群", ())
            if isinstance(item, dict)
            and tuple(item.get("結果経路", ())) == result_path
            and item.get("原理参照") in target_rule_ids
            and item.get("予測値") in _RANK_TO_OUTCOME.values()
        }
        if len(predicted) != 1:
            return None
        return {outcome: rank for rank, outcome in _RANK_TO_OUTCOME.items()}[
            next(iter(predicted))
        ]

    def _HDS状態を照会する(self, observed) -> tuple[int, ...]:
        preferred = super()._HDS状態を照会する(observed)
        ranks: dict[int, int] = {}
        policy = getattr(self, "_policy", None)
        if hasattr(policy, "_set_hds_target_color_ranks"):
            policy._set_hds_target_color_ranks({})
        if 6 not in observed.作用可能番号 or not observed.最新盤面:
            return preferred

        self._HDS適用範囲を保つ(observed)
        target_path = ("作用前公開状態", "対象色")
        current_rules = self._hds.エンジン._現行原理群()
        target_rules = [
            rule
            for rule in self._hds.エンジン._有効原理群()
            if rule.結果経路 == ("公開応答区分",) and target_path in rule.条件経路群
        ]
        if not target_rules:
            return preferred
        cacheable = all(rule.条件経路群 == (target_path,) for rule in target_rules)
        rule_signature = tuple(
            sorted(
                repr(
                    (
                        rule.条件経路群,
                        rule.結果経路,
                        rule.状態.value,
                        rule.採用状態.value,
                        rule.対応表,
                        rule.対応値表,
                        rule.反証参照群,
                        rule.除外反証参照群,
                    )
                )
                for rule in current_rules
                if rule.結果経路 == ("公開応答区分",)
            )
        )
        coarse_state = tuple(
            sorted(_load_agent_module().MyAgent._HDS作用前状態(observed).items())
        )
        colors = sorted({color for row in observed.最新盤面 for color in row})
        for color in colors:
            cache_key = (rule_signature, coarse_state, color)
            if cacheable and cache_key in self._target_color_query_cache:
                type(self).query_cache_hits += 1
                rank = self._target_color_query_cache[cache_key]
                if rank is not None:
                    ranks[color] = rank
                continue
            started = time.perf_counter()
            self._hds_queries += 1
            self._hds_candidate_action_queries += 1
            try:
                state = _load_agent_module().MyAgent._HDS作用前状態(observed)
                state["対象色"] = color
                result = self._hds.照会する(
                    外部入力(
                        {
                            "作用前公開状態": state,
                            "作用": {"番号": 6, "引数あり": True},
                        },
                        "ARC3公開作用応答",
                        目的="公開盤面の対象セル色を含むAction 6応答をHDSで照会。合法座標は探索方針が選ぶ",
                    )
                )
                type(self).query_attempts += 1
                type(self).query_status_counts[str(result.状態)] += 1
                rank = self._target_color_rank(result)
                if cacheable:
                    self._target_color_query_cache[cache_key] = rank
                if rank is not None:
                    ranks[color] = rank
                    type(self).target_rule_prediction_counts[_RANK_TO_OUTCOME[rank]] += 1
            except Exception as exc:
                type(self).query_attempts += 1
                type(self).query_status_counts[f"ERROR:{type(exc).__name__}"] += 1
                if cacheable:
                    self._target_color_query_cache[cache_key] = None
            finally:
                self._hds_query_seconds += time.perf_counter() - started

        if hasattr(policy, "_set_hds_target_color_ranks"):
            policy._set_hds_target_color_ranks(ranks)
        type(self).target_prediction_uses += len(ranks)
        return preferred


def _summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    deltas = [float(row["candidate"]["score"]) - float(row["baseline"]["score"]) for row in rows]
    return {
        "pairs": len(rows),
        "baseline_rhae_mean": round(sum(float(row["baseline"]["score"]) for row in rows) / len(rows), 9),
        "candidate_rhae_mean": round(sum(float(row["candidate"]["score"]) for row in rows) / len(rows), 9),
        "score_delta_mean": round(sum(deltas) / len(deltas), 9),
        "score_improvements": sum(delta > 1e-9 for delta in deltas),
        "score_regressions": sum(delta < -1e-9 for delta in deltas),
        "score_ties": sum(abs(delta) <= 1e-9 for delta in deltas),
        "levels_delta_total": sum(int(row["candidate"]["levels"]) - int(row["baseline"]["levels"]) for row in rows),
        "wins_delta_total": sum(int(row["candidate"]["wins"]) - int(row["baseline"]["wins"]) for row in rows),
        "no_ops_delta_total": sum(int(row["candidate"]["no_ops"]) - int(row["baseline"]["no_ops"]) for row in rows),
        "target_color_query_attempts": sum(int(row["target_color_query_attempts"]) for row in rows),
        "target_color_query_cache_hits": sum(int(row["target_color_query_cache_hits"]) for row in rows),
        "target_color_rule_predictions": sum(
            sum(int(count) for count in row["target_color_rule_prediction_counts"].values())
            for row in rows
        ),
        "target_color_prediction_uses": sum(int(row["target_color_prediction_uses"]) for row in rows),
        "target_color_guided_choices": sum(int(row["target_color_guided_choices"]) for row in rows),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--checkpoint", type=Path, default=DEFAULT_CHECKPOINT)
    parser.add_argument("--pair-limit", type=int, default=15)
    args = parser.parse_args()
    if not 1 <= args.pair_limit <= len(SEEDS) * 5:
        parser.error("--pair-limit must be between 1 and 15")
    output = args.output if args.output.is_absolute() else ROOT / args.output
    checkpoint = args.checkpoint if args.checkpoint.is_absolute() else ROOT / args.checkpoint
    for path in (output, checkpoint):
        if path.exists():
            raise FileExistsError(f"refusing to overwrite evidence: {path}")

    games, manifest = load_games()
    if len(games) != 25:
        raise RuntimeError(f"expected 25 public environments, found {len(games)}")
    split = list(games)
    random.Random(SPLIT_SEED).shuffle(split)
    selected = split[:5]
    base = _load_agent_module().MyAgent
    original_policy = transfer_eval.観測駆動探索方針
    rows: list[dict[str, Any]] = []
    started = time.perf_counter()

    try:
        pair_index = 0
        for seed in SEEDS:
            for start_index, (metadata, path) in enumerate(selected, start=1):
                if pair_index >= args.pair_limit:
                    break
                baseline, _ = transfer_eval._実行する(
                    base, metadata, path, seed=seed, max_actions=MAX_ACTIONS
                )

                _TargetColorHDSAgent.query_attempts = 0
                _TargetColorHDSAgent.query_cache_hits = 0
                _TargetColorHDSAgent.query_status_counts = Counter()
                _TargetColorHDSAgent.target_rule_prediction_counts = Counter()
                _TargetColorHDSAgent.target_prediction_uses = 0
                _TargetColorHDSAgent.missing_target_colors = 0
                _TargetColorGuidedPolicy.guided_color_choices = 0
                _TargetColorGuidedPolicy.guided_outcome_counts = Counter()
                transfer_eval.観測駆動探索方針 = _TargetColorGuidedPolicy
                try:
                    candidate, hds = transfer_eval._実行する(
                        _TargetColorHDSAgent,
                        metadata,
                        path,
                        seed=seed,
                        max_actions=MAX_ACTIONS,
                    )
                finally:
                    transfer_eval.観測駆動探索方針 = original_policy

                target_rules = [
                    rule
                    for rule in hds.エンジン._有効原理群()
                    if rule.結果経路 == ("公開応答区分",)
                    and ("作用前公開状態", "対象色") in rule.条件経路群
                ]
                row = {
                    "seed": seed,
                    "public_start_index": start_index,
                    "baseline": baseline,
                    "candidate": candidate,
                    "target_color_query_attempts": _TargetColorHDSAgent.query_attempts,
                    "target_color_query_cache_hits": _TargetColorHDSAgent.query_cache_hits,
                    "target_color_query_status_counts": dict(
                        sorted(_TargetColorHDSAgent.query_status_counts.items())
                    ),
                    "target_color_rule_prediction_counts": dict(
                        sorted(_TargetColorHDSAgent.target_rule_prediction_counts.items())
                    ),
                    "target_color_prediction_uses": _TargetColorHDSAgent.target_prediction_uses,
                    "active_target_color_rules_after_episode": len(target_rules),
                    "target_color_guided_choices": _TargetColorGuidedPolicy.guided_color_choices,
                    "target_color_guided_outcome_counts": dict(
                        sorted(_TargetColorGuidedPolicy.guided_outcome_counts.items())
                    ),
                    "missing_target_colors": _TargetColorHDSAgent.missing_target_colors,
                }
                rows.append(row)
                with checkpoint.open("a", encoding="utf-8", newline="\n") as stream:
                    stream.write(json.dumps(row, ensure_ascii=False, separators=(",", ":")) + "\n")
                    stream.flush()
                    os.fsync(stream.fileno())
                print(json.dumps({"pair": pair_index + 1, **row}, ensure_ascii=False), flush=True)
                pair_index += 1
            if pair_index >= args.pair_limit:
                break
    finally:
        transfer_eval.観測駆動探索方針 = original_policy

    overall = _summary(rows)
    by_seed = [
        {"seed": seed, **_summary([row for row in rows if row["seed"] == seed])}
        for seed in sorted({row["seed"] for row in rows})
    ]
    gates = {
        "dev_mean_delta_at_least_0_01": overall["score_delta_mean"] >= 0.01,
        "improvements_at_least_regressions": overall["score_improvements"] >= overall["score_regressions"],
        "levels_not_regressed": overall["levels_delta_total"] >= 0,
        "wins_not_regressed": overall["wins_delta_total"] >= 0,
    }
    result = {
        "schema": "arc3-hds-action6-target-color-guidance-dev.v1",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "evaluation": "paired public dev; current exploration policy versus one HDS target-color pseudo-observation in color-level UCB",
        "split_seed": SPLIT_SEED,
        "public_environments": len(games),
        "selected_public_starts": len(selected),
        "seed_groups": list(SEEDS),
        "max_actions_per_episode": MAX_ACTIONS,
        "pair_limit": args.pair_limit,
        "environment_metadata_manifest_sha256": manifest,
        "python_version": sys.version.split()[0],
        "arc_agi_version": version("arc-agi"),
        "arcengine_version": version("arcengine"),
        "base_agent_source_sha256": _sha(ROOT / "接続/ARC3提出agent.py"),
        "policy_source_sha256": _sha(ROOT / "接続/観測駆動探索Action.py"),
        "hds_source_sha256": _sha(ROOT / "HDS/学習系統/v0.4.2/hds学習系統/__init__.py"),
        "hds_prior_memory_manifest_sha256": _sha(ROOT / "記憶/事前記憶/v0.4/マニフェスト.json"),
        "target_color_prior": {
            "evidence": "one virtual observation per target color with a fresh active HDS rule conditioned on target color and Action 6",
            "response_to_policy_reward": {
                "可視変化なし": -1.0,
                "盤面変化": 0.25,
                "レベル進行": 4.0,
                "勝利": 4.0,
            },
            "exploration": "base UCB exploration term is retained; unseen colors continue first-visit coverage",
        },
        "rows": rows,
        "overall": overall,
        "by_seed": by_seed,
        "gates": gates,
        "passes_dev_gate": all(gates.values()),
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "official_submission_made": False,
        "runtime_modified": False,
        "interpretation": "local public-dev evidence only; passing requires fresh-seed holdout and full public evaluation before any runtime promotion",
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(
        json.dumps(
            {
                "overall": overall,
                "by_seed": by_seed,
                "gates": gates,
                "passes_dev_gate": result["passes_dev_gate"],
                "elapsed_seconds": result["elapsed_seconds"],
                "output": str(output),
                "checkpoint": str(checkpoint),
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
