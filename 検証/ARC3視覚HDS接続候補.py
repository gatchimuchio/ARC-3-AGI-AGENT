"""視覚ソルバーの実行済み公開一手と既存HDSをつなぐ、検証専用の候補。

Actionは実行しない。HDSの判断・保存形式も変更しない。呼出側が一つの
実ゲームにつき一つのbridgeを作り、実際に実行した一手ごとにupdateする。
この小さなframe型だけでは、同一実行の前後であること自体は証明できない。
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
import json
from pathlib import Path
import sys
import time
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "HDS/学習系統/v0.4.2"))
from hds学習系統 import HDS学習系統  # noqa: E402
from hds学習系統.型 import 外部入力  # noqa: E402
from 接続.ARC3事前記憶 import (  # noqa: E402
    BOUNDARY as PRIOR_BOUNDARY,
    PRINCIPLES,
    VERSION as PRIOR_VERSION,
    事前記憶をHDSへ供給する,
)

_BOUNDARY = "ARC3視覚公開作用応答候補"
_OUTCOME_PATH = ("公開応答区分",)
_OUTCOMES = {"勝利", "GAME_OVER", "レベル進行", "盤面変化", "可視変化なし"}
_MAX_PREDICTIONS = 4
_MAX_RULES = 4
_MAX_CONFLICTS = 2
_MAX_REQUESTS = 2
_DIRECTIONS = (
    ("N", 0, -1),
    ("NE", 1, -1),
    ("E", 1, 0),
    ("SE", 1, 1),
    ("S", 0, 1),
    ("SW", -1, 1),
    ("W", -1, 0),
    ("NW", -1, -1),
)


class _PriorBudgetExhausted(RuntimeError):
    pass


def _target_topology(board: tuple[tuple[int, ...], ...], x: int, y: int) -> tuple[str, ...]:
    height, width = len(board), len(board[0])
    center = board[y][x]
    return tuple(
        "outside"
        if not (0 <= x + dx < width and 0 <= y + dy < height)
        else "same"
        if board[y + dy][x + dx] == center
        else "different"
        for _, dx, dy in _DIRECTIONS
    )


@dataclass(frozen=True)
class PublicFrame:
    board: tuple[tuple[int, ...], ...]
    state: str
    levels_completed: int
    available_actions: tuple[int, ...]

    def __post_init__(self) -> None:
        if self.state not in {"NOT_PLAYED", "NOT_FINISHED", "GAME_OVER", "WIN"}:
            raise ValueError("unknown public state")
        if type(self.levels_completed) is not int or self.levels_completed < 0:
            raise ValueError("public completed-level count must be a nonnegative integer")
        board = tuple(tuple(row) for row in self.board)
        width = len(board[0]) if board else 0
        if board and (
            not 1 <= len(board) <= 64
            or not 1 <= width <= 64
            or any(len(row) != width for row in board)
        ):
            raise ValueError("public board must be rectangular and within 64 by 64")
        if self.state == "NOT_FINISHED" and not board:
            raise ValueError("unfinished public frame needs a board")
        if any(type(cell) is not int or not 0 <= cell <= 15 for row in board for cell in row):
            raise ValueError("public board cells must be ARC3 color integers")
        actions = tuple(self.available_actions)
        if any(type(action) is not int or not 0 <= action <= 7 for action in actions):
            raise ValueError("public available action is outside the SDK range")
        if len(actions) != len(set(actions)):
            raise ValueError("public available actions contain duplicates")
        object.__setattr__(self, "board", board)
        object.__setattr__(self, "available_actions", actions)


@dataclass(frozen=True)
class PublicAction:
    number: int
    x: int | None = None
    y: int | None = None

    def __post_init__(self) -> None:
        if type(self.number) is not int or not 0 <= self.number <= 7:
            raise ValueError("public action is outside the SDK range")
        if self.number == 6:
            if any(type(value) is not int or not 0 <= value <= 63 for value in (self.x, self.y)):
                raise ValueError("Action6 needs public integer coordinates within 0..63")
        elif self.x is not None or self.y is not None:
            raise ValueError("only Action6 can have coordinates")


def _legal(frame: PublicFrame, action: PublicAction) -> bool:
    if action.number == 0:
        return frame.state in {"NOT_PLAYED", "GAME_OVER"}
    if frame.state != "NOT_FINISHED" or action.number not in frame.available_actions:
        return False
    if action.number == 6:
        return (
            bool(frame.board)
            and 0 <= action.y < len(frame.board)
            and 0 <= action.x < len(frame.board[0])
        )
    return True


def _public_context(frame: PublicFrame, action: PublicAction) -> dict[str, Any]:
    counts = Counter(cell for row in frame.board for cell in row)
    area = max(1, sum(len(row) for row in frame.board))
    share = max(counts.values(), default=0) / area
    context: dict[str, Any] = {
        "作用可能数": sum(1 <= number <= 7 for number in frame.available_actions),
        "色種類数": len(counts),
        "最多色占有帯": (
            "低" if share < 0.25 else "中低" if share < 0.5 else "中高" if share < 0.75 else "高"
        ),
    }
    if action.number == 6:
        topology = _target_topology(frame.board, action.x, action.y)
        context["対象局所配置"] = "|".join(
            f"{direction}={value}" for (direction, _, _), value in zip(_DIRECTIONS, topology)
        )
    return context


def _query_content(frame: PublicFrame, action: PublicAction) -> dict[str, Any]:
    return {
        "作用前公開状態": _public_context(frame, action),
        "作用": {"番号": action.number, "引数あり": action.number == 6},
    }


def _observed_outcome(before: PublicFrame, after: PublicFrame) -> str:
    if after.state == "WIN":
        return "勝利"
    if after.state == "GAME_OVER":
        return "GAME_OVER"
    if after.levels_completed > before.levels_completed:
        return "レベル進行"
    return "盤面変化" if after.board != before.board else "可視変化なし"


def _text(value: Any, limit: int = 160) -> str:
    return value[:limit] if isinstance(value, str) else ""


def _rows(value: Any) -> list[dict]:
    return (
        [item for item in value if isinstance(item, dict)]
        if isinstance(value, (list, tuple))
        else []
    )


def _path(value: Any) -> tuple[str, ...]:
    if not isinstance(value, (list, tuple)) or any(not isinstance(part, str) for part in value):
        return ()
    return tuple(part[:64] for part in value[:4])


def _native_summary(result: Any) -> dict[str, Any]:
    content = getattr(result, "内容", None)
    content = content if isinstance(content, dict) else {}
    predictions = [
        row
        for row in _rows(content.get("予測群"))
        if _path(row.get("結果経路")) == _OUTCOME_PATH
        and isinstance(row.get("予測値"), str)
        and row["予測値"] in _OUTCOMES
    ]
    rules = [
        row
        for row in _rows(content.get("有効原理群"))
        if _path(row.get("結果経路")) == _OUTCOME_PATH
    ]
    conflicts = [
        row for row in _rows(content.get("競合群")) if _path(row.get("結果経路")) == _OUTCOME_PATH
    ]
    requests = [
        row
        for row in _rows(content.get("追加観測要求群"))
        if _path(row.get("結果経路")) == _OUTCOME_PATH
    ]
    evidence = []
    for row in rules[:_MAX_RULES]:
        scope = row.get("適用範囲")
        scope = scope if isinstance(scope, dict) else {}
        bounded_scope = {
            key: value if type(value) in {int, bool} else _text(value)
            for key, value in scope.items()
            if key in {"確認範囲", "条件数", "条件種類数"}
        }
        conditions = row.get("条件経路群")
        conditions = conditions if isinstance(conditions, (list, tuple)) else ()
        evidence.append(
            {
                "principle_ref": _text(row.get("原理識別子"), 80),
                "version": row.get("版") if type(row.get("版")) is int else None,
                "native_state": _text(row.get("状態"), 64),
                "native_adoption_state": _text(row.get("採用状態"), 64),
                "relation": _text(row.get("関係型"), 64),
                "condition_paths": [list(_path(path)) for path in conditions[:4]],
                "native_scope": bounded_scope,
            }
        )
    holds = content.get("断定保留理由群")
    holds = holds if isinstance(holds, (list, tuple)) else ()
    return {
        "native_status": _text(getattr(result, "状態", None), 64),
        "native_learning_state": _text(content.get("学習成立状態"), 64),
        "relevant_prediction_count": len(predictions),
        "predictions": [
            {"value": row["予測値"], "principle_ref": _text(row.get("原理参照"), 80)}
            for row in predictions[:_MAX_PREDICTIONS]
        ],
        "relevant_active_rule_count": len(rules),
        "rule_evidence": evidence,
        "relevant_conflict_count": len(conflicts),
        "conflicts": [
            {
                "candidate_values": [
                    value
                    for value in row.get("候補値群", ())
                    if isinstance(value, str) and value in _OUTCOMES
                ][:_MAX_PREDICTIONS]
            }
            for row in conflicts[:_MAX_CONFLICTS]
        ],
        "relevant_observation_request_count": len(requests),
        "observation_requests": [
            {"reason": _text(row.get("理由"))} for row in requests[:_MAX_REQUESTS]
        ],
        "native_hold_reasons": [_text(reason) for reason in holds[:3]],
        "summary_is_truncated": (
            len(predictions) > _MAX_PREDICTIONS
            or len(rules) > _MAX_RULES
            or len(conflicts) > _MAX_CONFLICTS
            or len(requests) > _MAX_REQUESTS
            or len(holds) > 3
        ),
    }


def render_hint(result: dict[str, Any], *, max_chars: int = 1200) -> str:
    """既存HDSの有効な非競合予測がある時だけ、短い任意文脈を返す。"""
    if type(max_chars) is not int or max_chars < 0:
        raise ValueError("max_chars must be a finite nonnegative integer")
    if (
        result.get("bridge_status") != "queried"
        or result.get("native_status") != "出力"
        or result.get("authorization") is not False
        or result.get("relevant_conflict_count", 0)
        or result.get("relevant_observation_request_count", 0)
    ):
        return ""
    rules = [
        row
        for row in _rows(result.get("rule_evidence"))
        if row.get("native_state") == "適用範囲付き暫定原理"
        and row.get("native_adoption_state") == "有効"
    ]
    refs = {row.get("principle_ref") for row in rules}
    predictions = [
        row
        for row in _rows(result.get("predictions"))
        if row.get("principle_ref") in refs
        and isinstance(row.get("value"), str)
        and row["value"] in _OUTCOMES
    ]
    if not predictions:
        return ""
    payload = {
        "native_status": result["native_status"],
        "candidate_action_number": result.get("candidate_action_number"),
        "predictions": predictions[:2],
        "rule_scope": [
            {
                "principle_ref": row["principle_ref"],
                "condition_paths": row["condition_paths"],
                "native_scope": row["native_scope"],
            }
            for row in rules[:2]
        ],
    }
    hint = (
        "HDS native evidence; authorization=false; predictive utility unverified.\n"
        + json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
    )
    return hint if len(hint) <= max_chars else ""


class VisualHDSBridge:
    def __init__(self, *, update_budget: int, query_budget: int, hds_seconds_budget: float) -> None:
        for name, value in (("update_budget", update_budget), ("query_budget", query_budget)):
            if type(value) is not int or value < 0:
                raise ValueError(f"{name} must be an explicit finite nonnegative integer")
        if (
            type(hds_seconds_budget) not in {int, float}
            or not math.isfinite(hds_seconds_budget)
            or hds_seconds_budget < 0
        ):
            raise ValueError("hds_seconds_budget must be explicit, finite and nonnegative")
        self._hds = HDS学習系統()
        self._budgets = {"update": update_budget, "query": query_budget}
        self._seconds_budget = float(hds_seconds_budget)
        self._attempts: Counter[str] = Counter()
        self._successes: Counter[str] = Counter()
        self._errors: Counter[str] = Counter()
        self._seconds: Counter[str] = Counter()
        self._skipped_resets = 0
        self._rejected = 0
        self._budget_blocks = 0
        self._last_error_type: str | None = None
        self._prior_report: dict[str, Any] = {
            "version": PRIOR_VERSION,
            "boundary": PRIOR_BOUNDARY,
            "expected_count": len(PRINCIPLES),
            "loaded_count": 0,
            "action_authorization": False,
            "load_status": "not_started",
        }
        self._load_prior()

    def _load_prior(self) -> None:
        owner = self

        class _PriorSink:
            def 処理する(self, value):
                if (
                    owner._attempts["prior"] >= len(PRINCIPLES)
                    or sum(owner._seconds.values()) >= owner._seconds_budget
                ):
                    owner._budget_blocks += 1
                    raise _PriorBudgetExhausted("fixed prior load budget exhausted")
                owner._attempts["prior"] += 1
                started = time.perf_counter()
                try:
                    result = owner._hds.処理する(value)
                    owner._successes["prior"] += 1
                    return result
                except Exception as exc:
                    owner._errors["prior"] += 1
                    owner._last_error_type = type(exc).__name__
                    raise
                finally:
                    owner._seconds["prior"] += max(0.0, time.perf_counter() - started)

        try:
            report = 事前記憶をHDSへ供給する(_PriorSink())
            self._prior_report = {
                **report,
                "expected_count": len(PRINCIPLES),
                "action_authorization": False,
                "load_status": "loaded",
            }
        except Exception as exc:
            self._prior_report.update(
                {
                    "loaded_count": self._successes["prior"],
                    "load_status": (
                        "budget_exhausted"
                        if isinstance(exc, _PriorBudgetExhausted)
                        else "hds_error"
                    ),
                    "error_type": type(exc).__name__,
                }
            )

    @property
    def prior_report(self) -> dict[str, Any]:
        return dict(self._prior_report)

    @property
    def stats(self) -> dict[str, Any]:
        elapsed = sum(self._seconds.values())
        return {
            "updates_attempted": self._attempts["update"],
            "updates_succeeded": self._successes["update"],
            "queries_attempted": self._attempts["query"],
            "queries_succeeded": self._successes["query"],
            "update_errors": self._errors["update"],
            "query_errors": self._errors["query"],
            "summary_errors": self._errors["summary"],
            "prior_updates_attempted": self._attempts["prior"],
            "prior_updates_succeeded": self._successes["prior"],
            "prior_update_errors": self._errors["prior"],
            "skipped_resets": self._skipped_resets,
            "rejected_requests": self._rejected,
            "budget_exhaustion_requests": self._budget_blocks,
            "update_seconds": round(self._seconds["update"], 6),
            "query_seconds": round(self._seconds["query"], 6),
            "total_hds_seconds": round(elapsed, 6),
            "prior_load_seconds": round(self._seconds["prior"], 6),
            "update_budget": self._budgets["update"],
            "query_budget": self._budgets["query"],
            "hds_seconds_budget": self._seconds_budget,
            "update_budget_exhausted": self._attempts["update"] >= self._budgets["update"],
            "query_budget_exhausted": self._attempts["query"] >= self._budgets["query"],
            "time_budget_exhausted": elapsed >= self._seconds_budget,
            "time_budget_can_overrun_one_inflight_call": True,
            "last_error_type": self._last_error_type,
        }

    def _result(self, status: str, **fields: Any) -> dict[str, Any]:
        return {
            "bridge_status": status,
            "authorization": False,
            "continue_visual_solver": True,
            "prior_report": self.prior_report,
            **fields,
            "stats": self.stats,
        }

    def _reject(self, reason: str) -> dict[str, Any]:
        self._rejected += 1
        return self._result("rejected", reason=reason)

    def _call(self, kind: str, content: dict[str, Any]) -> dict[str, Any]:
        blocked_by = []
        if self._attempts[kind] >= self._budgets[kind]:
            blocked_by.append(f"{kind}_count")
        if sum(self._seconds.values()) >= self._seconds_budget:
            blocked_by.append("total_hds_seconds")
        if blocked_by:
            self._budget_blocks += 1
            return self._result("budget_exhausted", blocked_by=blocked_by)
        self._attempts[kind] += 1
        started = time.perf_counter()
        result = None
        error = None
        try:
            operation = self._hds.処理する if kind == "update" else self._hds.照会する
            result = operation(
                外部入力(
                    content,
                    _BOUNDARY,
                    目的="実行済み公開一手の観測学習または既存HDS判断の照会。Action認可には不使用",
                )
            )
            self._successes[kind] += 1
        except Exception as exc:
            self._errors[kind] += 1
            self._last_error_type = type(exc).__name__
            error = type(exc).__name__
        finally:
            self._seconds[kind] += max(0.0, time.perf_counter() - started)
        if error is not None:
            return self._result("hds_error", operation=kind, error_type=error)
        try:
            summary = _native_summary(result)
        except Exception as exc:
            self._errors["summary"] += 1
            self._last_error_type = type(exc).__name__
            return self._result("summary_error", operation=kind, error_type=type(exc).__name__)
        return self._result("updated" if kind == "update" else "queried", **summary)

    def update(
        self, before: PublicFrame, action: PublicAction, after: PublicFrame
    ) -> dict[str, Any]:
        if not _legal(before, action):
            return self._reject("action is not legal in the supplied pre-action public frame")
        if action.number == 0:
            self._skipped_resets += 1
            return self._result("skipped_reset")
        if after.state not in {"NOT_FINISHED", "GAME_OVER", "WIN"}:
            return self._reject("non-reset response has an invalid public lifecycle state")
        if after.levels_completed < before.levels_completed and after.state != "GAME_OVER":
            return self._reject("completed levels decreased across a non-reset transition")
        content = _query_content(before, action)
        content["公開応答区分"] = _observed_outcome(before, after)
        return self._call("update", content)

    def query(self, current: PublicFrame, candidate: PublicAction) -> dict[str, Any]:
        if candidate.number == 0 or not _legal(current, candidate):
            return self._reject("query candidate is not a legal non-reset public action")
        result = self._call("query", _query_content(current, candidate))
        result["candidate_action_number"] = candidate.number
        return result
