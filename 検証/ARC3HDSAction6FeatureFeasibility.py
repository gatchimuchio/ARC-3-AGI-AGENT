"""Measure public feature coverage for HDS rules on coordinate Action 6."""

from __future__ import annotations

from collections import Counter, defaultdict
from datetime import datetime, timezone
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

from ARC3HDS公開転移shadow評価 import _実行する  # noqa: E402
from ARC3MyAgent_local_smoke import load_games  # noqa: E402
from test_ARC3提出agent import _load_agent_module  # noqa: E402
from hds学習系統.型 import 外部入力  # noqa: E402


SPLIT_SEED = 20261022
GAME_SEED = 7
MAX_ACTIONS = 80
OUTPUT = ROOT / "運用/証拠/ARC26-UNIFIED/ARC3-C2-091-HDS-Action6-feature-feasibility-20261027.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _component_size(board: tuple[tuple[int, ...], ...], x: int, y: int) -> int:
    if not (0 <= y < len(board) and 0 <= x < len(board[y])):
        return 0
    color = board[y][x]
    pending = [(x, y)]
    visited = {(x, y)}
    while pending:
        cx, cy = pending.pop()
        for nx, ny in ((cx - 1, cy), (cx + 1, cy), (cx, cy - 1), (cx, cy + 1)):
            if (
                0 <= ny < len(board)
                and 0 <= nx < len(board[ny])
                and (nx, ny) not in visited
                and board[ny][nx] == color
            ):
                visited.add((nx, ny))
                pending.append((nx, ny))
    return len(visited)


def _target_features(before: Any, action: Any) -> dict[str, Any]:
    board = before.最新盤面
    x, y = action.引数.get("x"), action.引数.get("y")
    if type(x) is not int or type(y) is not int or not (0 <= y < len(board)):
        return {"座標特徴状態": "未算出"}
    if not board[y] or not (0 <= x < len(board[y])):
        return {"座標特徴状態": "未算出"}
    width = max((len(row) for row in board), default=0)
    height = len(board)
    area = _component_size(board, x, y)
    if area <= 1:
        area_band = "1"
    elif area <= 3:
        area_band = "2-3"
    elif area <= 7:
        area_band = "4-7"
    else:
        area_band = "8+"
    color = board[y][x]
    same_color_neighbors = sum(
        1
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1))
        if 0 <= ny < height and 0 <= nx < len(board[ny]) and board[ny][nx] == color
    )
    return {
        "対象色": color,
        "対象同色成分帯": area_band,
        "同色4近傍数": same_color_neighbors,
        "盤面外周": x == 0 or y == 0 or x == width - 1 or y == height - 1,
        "横位置帯": min(2, (3 * x) // max(1, width)),
        "縦位置帯": min(2, (3 * y) // max(1, height)),
    }


def _outcome(before: Any, after: Any) -> str:
    if after.状態 == "WIN":
        return "勝利"
    if after.完了レベル数 > before.完了レベル数:
        return "レベル進行"
    if after.最新盤面 != before.最新盤面:
        return "盤面変化"
    return "可視変化なし"


def _feature_feasibility(rows: list[dict[str, Any]]) -> dict[str, Any]:
    features = sorted({key for row in rows for key in row["features"]})
    summary: dict[str, Any] = {}
    for feature in features:
        groups: dict[str, Counter[str]] = defaultdict(Counter)
        for row in rows:
            if feature in row["features"]:
                groups[json.dumps(row["features"][feature], ensure_ascii=False)][row["outcome"]] += 1
        conflicts = sum(len(outcomes) > 1 for outcomes in groups.values())
        stable_groups = {
            key: outcomes
            for key, outcomes in groups.items()
            if len(outcomes) == 1
        }
        stable_support = sum(sum(outcomes.values()) for outcomes in stable_groups.values())
        summary[feature] = {
            "observations": sum(sum(outcomes.values()) for outcomes in groups.values()),
            "categories": len(groups),
            "conflicting_categories": conflicts,
            "stable_categories": len(stable_groups),
            "stable_support": stable_support,
            "outcomes_by_category": {
                key: dict(sorted(outcomes.items())) for key, outcomes in sorted(groups.items())
            },
            "single_feature_rule_feasible_under_min_support_3": (
                conflicts == 0 and len(stable_groups) >= 2 and stable_support >= 3
            ),
        }
    return summary


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite evidence: {OUTPUT}")
    base = _load_agent_module().MyAgent

    class _Action6FeatureDiagnosticAgent(base):
        selected_action_counts: Counter[int] = Counter()
        action6_rows: list[dict[str, Any]] = []
        query_status_counts: Counter[str] = Counter()
        query_attempts = 0

        def choose_action(self, frames, latest_frame):
            action = super().choose_action(frames, latest_frame)
            type(self).selected_action_counts[action.作用番号] += 1
            return action

        def _HDS作用応答を学ぶ(self, before, action, after):
            if action.作用番号 == 6:
                type(self).action6_rows.append(
                    {
                        "features": {
                            **self._HDS作用前状態(before),
                            **_target_features(before, action),
                        },
                        "outcome": _outcome(before, after),
                    }
                )
            return super()._HDS作用応答を学ぶ(before, action, after)

        def _HDS状態を照会する(self, observed):
            preferred = super()._HDS状態を照会する(observed)
            if preferred or 6 not in observed.作用可能番号:
                return preferred
            self._HDS適用範囲を保つ(observed)
            try:
                result = self._hds.照会する(
                    外部入力(
                        {
                            "作用前公開状態": self._HDS作用前状態(observed),
                            "作用": {"番号": 6, "引数あり": True},
                        },
                        "ARC3公開作用応答",
                        目的="Action6一般規則の有無を読み取る診断のみ",
                    )
                )
                type(self).query_attempts += 1
                type(self).query_status_counts[str(result.状態)] += 1
            except Exception as exc:
                type(self).query_attempts += 1
                type(self).query_status_counts[f"ERROR:{type(exc).__name__}"] += 1
            return preferred

    games, manifest = load_games()
    if len(games) != 25:
        raise RuntimeError(f"expected 25 public environments, found {len(games)}")
    split = list(games)
    random.Random(SPLIT_SEED).shuffle(split)
    metadata, path = split[0]
    started = time.perf_counter()
    episode, hds = _実行する(
        _Action6FeatureDiagnosticAgent,
        metadata,
        path,
        seed=GAME_SEED,
        max_actions=MAX_ACTIONS,
    )

    current_rules = hds.エンジン._現行原理群()
    action6_rules = [
        rule
        for rule in current_rules
        if rule.結果経路 == ("公開応答区分",)
        and ("作用", "番号") in rule.条件経路群
        and any(feature[:1] == ("作用前公開状態",) for feature in rule.条件経路群)
    ]
    result = {
        "schema": "arc3-hds-action6-feature-feasibility.v1",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "evaluation": "single public dev episode; aggregate public feature-outcome coverage; policy unchanged",
        "split_seed": SPLIT_SEED,
        "selected_public_start_index": 1,
        "game_seed": GAME_SEED,
        "max_actions": MAX_ACTIONS,
        "environment_count": len(games),
        "environment_metadata_manifest_sha256": manifest,
        "agent_source_sha256": _sha(ROOT / "接続/ARC3提出agent.py"),
        "hds_source_sha256": _sha(ROOT / "HDS/学習系統/v0.4.2/hds学習系統/__init__.py"),
        "episode": episode,
        "selected_action_counts": {
            str(action): count
            for action, count in sorted(_Action6FeatureDiagnosticAgent.selected_action_counts.items())
        },
        "action6_observed_outcome_counts": dict(
            sorted(Counter(row["outcome"] for row in _Action6FeatureDiagnosticAgent.action6_rows).items())
        ),
        "action6_feature_feasibility": _feature_feasibility(
            _Action6FeatureDiagnosticAgent.action6_rows
        ),
        "generic_query": {
            "attempts": _Action6FeatureDiagnosticAgent.query_attempts,
            "status_counts": dict(sorted(_Action6FeatureDiagnosticAgent.query_status_counts.items())),
            "eligible_action6_rules_after_episode": sum(
                rule.採用状態.value == "有効"
                and rule.状態.value == "適用範囲付き暫定原理"
                for rule in action6_rules
            ),
            "matching_current_rule_states": dict(
                sorted(Counter(f"{rule.状態.value}|{rule.採用状態.value}" for rule in action6_rules).items())
            ),
        },
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "official_submission_or_quota_used": False,
        "runtime_modified": False,
        "interpretation": "feature feasibility is a one-episode diagnostic, not a score or transfer claim",
    }
    if len(_Action6FeatureDiagnosticAgent.action6_rows) != _Action6FeatureDiagnosticAgent.selected_action_counts.get(6, 0):
        raise RuntimeError("Action 6 transition telemetry does not match selected Action 6 count")
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({
        "observed_at_utc": result["observed_at_utc"],
        "episode": episode,
        "selected_action_counts": result["selected_action_counts"],
        "action6_observed_outcome_counts": result["action6_observed_outcome_counts"],
        "action6_feature_feasibility": result["action6_feature_feasibility"],
        "generic_query": result["generic_query"],
        "elapsed_seconds": result["elapsed_seconds"],
    }, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
