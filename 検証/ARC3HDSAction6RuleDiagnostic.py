"""Inspect public HDS Action 6 rule coverage without changing the action policy."""

from __future__ import annotations

from collections import Counter
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
OUTPUT = ROOT / "運用/証拠/ARC26-UNIFIED/ARC3-C2-090-HDS-Action6-query-diagnostic-with-action-counts-20261027.json"


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _eligible(rule: Any) -> bool:
    return (
        rule.結果経路 == ("公開応答区分",)
        and ("作用", "番号") in rule.条件経路群
        and any(path[:1] == ("作用前公開状態",) for path in rule.条件経路群)
    )


def _summary(events: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "action6_query_attempts": len(events),
        "eligible_action6_rule_count_at_query_min": min(
            (row["eligible_action6_rules"] for row in events), default=0
        ),
        "eligible_action6_rule_count_at_query_max": max(
            (row["eligible_action6_rules"] for row in events), default=0
        ),
        "query_status_counts": dict(sorted(Counter(row["status"] for row in events).items())),
        "query_prediction_count": sum(row["public_response_predictions"] for row in events),
        "query_conflict_count": sum(row["public_response_conflicts"] for row in events),
        "query_additional_observation_count": sum(
            row["public_response_additional_observation_requests"] for row in events
        ),
        "accepted_rank_count": sum(row["accepted_rank"] is not None for row in events),
        "predicted_outcome_counts": dict(
            sorted(
                Counter(
                    outcome
                    for row in events
                    for outcome in row["predicted_outcomes"]
                ).items()
            )
        ),
    }


def main() -> int:
    if OUTPUT.exists():
        raise FileExistsError(f"refusing to overwrite evidence: {OUTPUT}")

    base = _load_agent_module().MyAgent

    class _Action6DiagnosticAgent(base):
        events: list[dict[str, Any]] = []
        selected_action_counts: Counter[int] = Counter()

        def choose_action(self, frames, latest_frame):
            action = super().choose_action(frames, latest_frame)
            type(self).selected_action_counts[action.作用番号] += 1
            return action

        def _HDS状態を照会する(self, observed):
            preferred = super()._HDS状態を照会する(observed)
            if preferred or 6 not in observed.作用可能番号:
                return preferred

            self._HDS適用範囲を保つ(observed)
            started = time.perf_counter()
            try:
                result = self._hds.照会する(
                    外部入力(
                        {
                            "作用前公開状態": self._HDS作用前状態(observed),
                            "作用": {"番号": 6, "引数あり": True},
                        },
                        "ARC3公開作用応答",
                        目的="公開観測から学んだAction 6応答規則の診断。順位付けと作用選択には不使用",
                    )
                )
                content = result.内容 if isinstance(result.内容, dict) else {}
                active = content.get("有効原理群", ())
                eligible_ids = {
                    item.get("原理識別子")
                    for item in active
                    if isinstance(item, dict)
                    and item.get("原理識別子")
                    and tuple(item.get("結果経路", ())) == ("公開応答区分",)
                    and item.get("状態") == "適用範囲付き暫定原理"
                    and item.get("採用状態") == "有効"
                    and ("作用", "番号") in tuple(
                        tuple(path) for path in item.get("条件経路群", ())
                    )
                    and any(
                        tuple(path)[:1] == ("作用前公開状態",)
                        for path in item.get("条件経路群", ())
                    )
                }
                predictions = [
                    item
                    for item in content.get("予測群", ())
                    if isinstance(item, dict)
                    and tuple(item.get("結果経路", ())) == ("公開応答区分",)
                    and item.get("原理参照") in eligible_ids
                ]
                conflicts = [
                    item
                    for item in content.get("競合群", ())
                    if isinstance(item, dict)
                    and tuple(item.get("結果経路", ())) == ("公開応答区分",)
                ]
                requests = [
                    item
                    for item in content.get("追加観測要求群", ())
                    if isinstance(item, dict)
                    and tuple(item.get("結果経路", ())) == ("公開応答区分",)
                ]
                accepted_rank = self._HDS公開応答順位予測(result)
                self.events.append(
                    {
                        "status": str(result.状態),
                        "eligible_action6_rules": len(eligible_ids),
                        "public_response_predictions": len(predictions),
                        "public_response_conflicts": len(conflicts),
                        "public_response_additional_observation_requests": len(requests),
                        "predicted_outcomes": sorted(
                            {
                                str(item.get("予測値"))
                                for item in predictions
                            }
                        ),
                        "accepted_rank": accepted_rank,
                    }
                )
                self._hds_last_query_state = result.状態
                return preferred
            except Exception as exc:
                self.events.append(
                    {
                        "status": f"ERROR:{type(exc).__name__}",
                        "eligible_action6_rules": sum(
                            1 for rule in self._hds.エンジン._有効原理群() if _eligible(rule)
                        ),
                        "public_response_predictions": 0,
                        "public_response_conflicts": 0,
                        "public_response_additional_observation_requests": 0,
                        "predicted_outcomes": [],
                        "accepted_rank": None,
                    }
                )
                return preferred
            finally:
                self._hds_query_seconds += time.perf_counter() - started

    games, manifest = load_games()
    if len(games) != 25:
        raise RuntimeError(f"expected 25 public environments, found {len(games)}")
    split = list(games)
    random.Random(SPLIT_SEED).shuffle(split)
    metadata, path = split[0]
    started = time.perf_counter()
    episode, hds = _実行する(
        _Action6DiagnosticAgent,
        metadata,
        path,
        seed=GAME_SEED,
        max_actions=MAX_ACTIONS,
    )
    events = _Action6DiagnosticAgent.events
    active_rule_count = sum(1 for rule in hds.エンジン._有効原理群() if _eligible(rule))
    result = {
        "schema": "arc3-hds-action6-query-diagnostic.v1",
        "observed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "evaluation": "single public dev episode; query telemetry only; independent legal exploration policy unchanged",
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
            for action, count in sorted(_Action6DiagnosticAgent.selected_action_counts.items())
        },
        "eligible_action6_rules_after_episode": active_rule_count,
        "query_summary": _summary(events),
        "query_events": events,
        "elapsed_seconds": round(time.perf_counter() - started, 6),
        "official_submission_or_quota_used": False,
        "runtime_modified": False,
        "interpretation": "diagnostic only; one public episode does not establish a score improvement or generalization",
    }
    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    OUTPUT.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps({key: result[key] for key in (
        "observed_at_utc", "episode", "eligible_action6_rules_after_episode",
        "selected_action_counts", "query_summary", "elapsed_seconds",
    )}, ensure_ascii=True, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
