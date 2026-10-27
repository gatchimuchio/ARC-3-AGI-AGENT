"""Paired dev score test for exposing generic ACTION6-family HDS forecasts."""
from __future__ import annotations

import argparse
import hashlib
import json
import random
from pathlib import Path
from typing import Any

from ARC3探索Actionローカル評価 import ROOT, _load_games, _run_game
from ARC3公開RHAE評価 import _スコアを計算する
from 接続.ARC3事前記憶 import 事前記憶をHDSへ供給する
from 接続.観測駆動探索Action import 探索Action, 観測駆動探索方針
from hds学習系統 import HDS学習系統
from hds学習系統.型 import 外部入力

SPLIT_SEED = 20261022
POLICY_SEEDS = (7, 31, 73)
MAX_ACTIONS = 80


def _public_state(observed: Any) -> dict[str, Any]:
    board = observed.最新盤面
    color_counts: dict[int, int] = {}
    for row in board:
        for color in row:
            color_counts[color] = color_counts.get(color, 0) + 1
    area = max(1, sum(len(row) for row in board))
    majority_share = max(color_counts.values(), default=0) / area
    occupancy_band = (
        "低"
        if majority_share < 0.25
        else "中低"
        if majority_share < 0.5
        else "中高"
        if majority_share < 0.75
        else "高"
    )
    return {
        "作用可能数": len(observed.作用可能番号),
        "色種類数": len(color_counts),
        "最多色占有帯": occupancy_band,
    }


def _response_rank(result: Any) -> int | None:
    content = getattr(result, "内容", None)
    if (
        not isinstance(content, dict)
        or getattr(result, "状態", None) not in ("出力", "断定保留")
    ):
        return None
    path = ("公開応答区分",)
    if any(
        isinstance(item, dict) and tuple(item.get("結果経路", ())) == path
        for item in content.get("競合群", ())
    ):
        return None
    active = {
        item.get("原理識別子")
        for item in content.get("有効原理群", ())
        if isinstance(item, dict)
        and tuple(item.get("結果経路", ())) == path
        and item.get("状態") == "適用範囲付き暫定原理"
        and item.get("採用状態") == "有効"
        and any(
            tuple(condition)[:1] == ("作用前公開状態",)
            for condition in item.get("条件経路群", ())
        )
        and any(
            tuple(condition) == ("作用", "番号")
            for condition in item.get("条件経路群", ())
        )
    }
    values = {
        item.get("予測値")
        for item in content.get("予測群", ())
        if isinstance(item, dict)
        and tuple(item.get("結果経路", ())) == path
        and item.get("原理参照") in active
        and item.get("予測値")
        in ("可視変化なし", "盤面変化", "レベル進行", "勝利")
    }
    if len(values) != 1:
        return None
    return {
        "可視変化なし": 0,
        "盤面変化": 1,
        "レベル進行": 2,
        "勝利": 3,
    }[next(iter(values))]


class _HDSRankingPolicy(観測駆動探索方針):
    """Mirror current MyAgent HDS ranking; optionally query ACTION6 as a family."""

    INCLUDE_ACTION6 = False

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self._hds = HDS学習系統()
        self._prior_report = 事前記憶をHDSへ供給する(self._hds)
        self._queries = 0
        self._query_candidates = 0
        self._forecasts: dict[int, int] = {}
        self._action6_preferred_states = 0
        self._guided_selections = 0
        self._errors = 0

    def 選ぶ(self, 現在: Any) -> 探索Action | None:
        if 現在.状態 != "NOT_FINISHED":
            return super().選ぶ(現在)
        predicted: dict[int, int] = {}
        self._queries += 1
        for action_number in sorted(set(現在.作用可能番号)):
            if type(action_number) is not int or not 1 <= action_number <= 7:
                continue
            if action_number == 6 and not self.INCLUDE_ACTION6:
                continue
            self._query_candidates += 1
            try:
                result = self._hds.照会する(
                    外部入力(
                        {
                            "作用前公開状態": _public_state(現在),
                            "作用": {
                                "番号": action_number,
                                "引数あり": action_number == 6,
                            },
                        },
                        "ARC3公開作用応答",
                        目的="公開状態と合法作用に対する既学習公開応答区分の順位照会。Action認可には不使用",
                    )
                )
                rank = _response_rank(result)
                if rank is not None:
                    predicted[action_number] = rank
                    self._forecasts[action_number] = (
                        self._forecasts.get(action_number, 0) + 1
                    )
            except Exception:
                self._errors += 1
        preferred: tuple[int, ...] = ()
        if predicted:
            best = max(predicted.values())
            preferred = tuple(
                number for number, rank in sorted(predicted.items()) if rank == best
            )
        if 6 in preferred:
            self._action6_preferred_states += 1
        action = super().選ぶ(現在, HDS優先作用番号群=preferred)
        if action is not None and action.作用番号 in preferred:
            self._guided_selections += 1
        return action

    def 応答を記録する(
        self, 作用前: Any, action: 探索Action, 作用後: Any
    ) -> dict[str, Any]:
        response = super().応答を記録する(作用前, action, 作用後)
        if (
            作用前.状態 != "NOT_FINISHED"
            or 作用後.状態 not in ("NOT_FINISHED", "WIN", "GAME_OVER")
            or 作用前.ゲーム識別子 != 作用後.ゲーム識別子
        ):
            return response
        if 作用後.状態 == "WIN":
            outcome = "勝利"
        elif 作用後.完了レベル数 > 作用前.完了レベル数:
            outcome = "レベル進行"
        elif 作用後.最新盤面 != 作用前.最新盤面:
            outcome = "盤面変化"
        else:
            outcome = "可視変化なし"
        self._hds.処理する(
            外部入力(
                {
                    "作用前公開状態": _public_state(作用前),
                    "作用": {
                        "番号": action.作用番号,
                        "引数あり": bool(action.引数),
                    },
                    "公開応答区分": outcome,
                },
                "ARC3公開作用応答",
                目的="公開観測された遷移と方針報酬の記録。因果や成功規則を仮定しない",
            )
        )
        return response

    def 統計(self) -> dict[str, Any]:
        stats = super().統計()
        stats["hds"] = {
            "queries": self._queries,
            "candidate_action_queries": self._query_candidates,
            "forecasts_by_action": self._forecasts,
            "action6_preferred_states": self._action6_preferred_states,
            "guided_selections": self._guided_selections,
            "query_errors": self._errors,
        }
        return stats


class _CurrentHDSRankingPolicy(_HDSRankingPolicy):
    INCLUDE_ACTION6 = False


class _Action6FamilyHDSRankingPolicy(_HDSRankingPolicy):
    INCLUDE_ACTION6 = True


def _start_hash(run: dict[str, Any]) -> str:
    start = {
        key: run[key]
        for key in (
            "initial_state",
            "initial_levels_completed",
            "initial_available_actions",
            "initial_board",
        )
    }
    payload = json.dumps(start, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _run(
    metadata: dict[str, Any],
    path: Path,
    seed: int,
    policy_type: type[_HDSRankingPolicy],
) -> dict[str, Any]:
    return _run_game(
        metadata,
        path,
        "exploration",
        seed=seed,
        policy_seed=seed,
        max_actions=MAX_ACTIONS,
        retry_game_over=False,
        exploration_coefficient=0.8,
        coordinate_color_exploration_coefficient=None,
        visible_change_coefficient=0.25,
        level_progress_reward=4.0,
        policy_type_override=policy_type,
    )


def evaluate() -> dict[str, Any]:
    games = _load_games(ROOT / "入力/Kaggle/environment_files")
    shuffled = list(games)
    random.Random(SPLIT_SEED).shuffle(shuffled)
    selected = shuffled[:5]
    rows: list[dict[str, Any]] = []
    for seed in POLICY_SEEDS:
        for metadata, path in selected:
            run = _run(metadata, path, seed, _CurrentHDSRankingPolicy)
            score, levels, _ = _スコアを計算する(
                metadata.get("baseline_actions", []), run
            )
            rows.append({
                "arm": "current_hds_excludes_action6",
                "seed": seed,
                "game_id": metadata["game_id"],
                "score": score,
                "levels": levels,
                "actions": run["actions"],
                "noops": run["no_op_actions"],
                "wins": int(run["final_state"] == "WIN"),
                "illegal_actions": run["illegal_action_attempts"],
                "start_sha256": _start_hash(run),
                "hds": run["policy_action_stats"].get("hds", {}),
            })
    for seed in POLICY_SEEDS:
        for metadata, path in selected:
            run = _run(metadata, path, seed, _Action6FamilyHDSRankingPolicy)
            score, levels, _ = _スコアを計算する(
                metadata.get("baseline_actions", []), run
            )
            rows.append({
                "arm": "candidate_hds_includes_action6_family",
                "seed": seed,
                "game_id": metadata["game_id"],
                "score": score,
                "levels": levels,
                "actions": run["actions"],
                "noops": run["no_op_actions"],
                "wins": int(run["final_state"] == "WIN"),
                "illegal_actions": run["illegal_action_attempts"],
                "start_sha256": _start_hash(run),
                "hds": run["policy_action_stats"].get("hds", {}),
            })
    baseline = {
        (row["seed"], row["game_id"]): row
        for row in rows
        if row["arm"] == "current_hds_excludes_action6"
    }
    candidate = [
        row for row in rows if row["arm"] == "candidate_hds_includes_action6_family"
    ]
    pairs = [
        (baseline[(row["seed"], row["game_id"])], row) for row in candidate
    ]
    deltas = [current["score"] - previous["score"] for previous, current in pairs]
    same_starts = sum(
        previous["start_sha256"] == current["start_sha256"]
        for previous, current in pairs
    )
    summary = {
        "pairs": len(pairs),
        "matched_start_pairs": same_starts,
        "mean_previous": sum(previous["score"] for previous, _ in pairs) / len(pairs),
        "mean_candidate": sum(current["score"] for _, current in pairs) / len(pairs),
        "mean_delta": sum(deltas) / len(deltas),
        "positive_pairs": sum(value > 0 for value in deltas),
        "negative_pairs": sum(value < 0 for value in deltas),
        "tied_pairs": sum(value == 0 for value in deltas),
        "levels_delta": sum(current["levels"] - previous["levels"] for previous, current in pairs),
        "wins_delta": sum(current["wins"] - previous["wins"] for previous, current in pairs),
        "actions_previous": sum(previous["actions"] for previous, _ in pairs),
        "actions_candidate": sum(current["actions"] for _, current in pairs),
        "noops_previous": sum(previous["noops"] for previous, _ in pairs),
        "noops_candidate": sum(current["noops"] for _, current in pairs),
        "illegal_actions": sum(
            previous["illegal_actions"] + current["illegal_actions"]
            for previous, current in pairs
        ),
        "candidate_action6_forecasts": sum(
            current["hds"].get("forecasts_by_action", {}).get("6", 0)
            + current["hds"].get("forecasts_by_action", {}).get(6, 0)
            for _, current in pairs
        ),
        "candidate_action6_preferred_states": sum(
            current["hds"].get("action6_preferred_states", 0)
            for _, current in pairs
        ),
    }
    return {
        "split_seed": SPLIT_SEED,
        "policy_seeds": POLICY_SEEDS,
        "max_actions_per_game": MAX_ACTIONS,
        "dev_games": [metadata["game_id"] for metadata, _ in selected],
        "baseline": "current MyAgent HDS action ranking; ACTION6 query excluded",
        "candidate": "same HDS prior/update/rank; query ACTION6 family with has_args=true; raw coordinates not stored",
        "decision_gate": {
            "minimum_mean_rhae_delta": 0.01,
            "require_nonnegative_levels_and_wins": True,
            "holdout_or_promotion_if_gate_fails": False,
        },
        "summary": summary,
        "pairs": [
            {
                "seed": previous["seed"],
                "game_id": previous["game_id"],
                "previous_score": previous["score"],
                "candidate_score": current["score"],
                "score_delta": current["score"] - previous["score"],
                "previous_levels": previous["levels"],
                "candidate_levels": current["levels"],
                "previous_actions": previous["actions"],
                "candidate_actions": current["actions"],
                "previous_hds": previous["hds"],
                "candidate_hds": current["hds"],
            }
            for previous, current in pairs
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "出力/ARC3-RUN-003-local/C2-109/action6-family-hds.json",
    )
    args = parser.parse_args()
    report = evaluate()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(report, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(json.dumps(report["summary"], ensure_ascii=False, separators=(",", ":")))


if __name__ == "__main__":
    main()

