"""Pure public-pixel observer; no action selection, native judgment, or offline-loader import."""

from __future__ import annotations

from copy import deepcopy
import json

AREA = "作用点同色4連結成分面積"
TARGET = "公開作用点効果区分"
EFFECT_BY_FLAGS = {
    (False, False): "局所なし・局所以外なし",
    (False, True): "局所なし・局所以外あり",
    (True, False): "局所あり・局所以外なし",
    (True, True): "局所あり・局所以外あり",
}
EFFECT_VALUES = tuple(EFFECT_BY_FLAGS.values())
REVISION = "Action6-PRE4CC-area-and-7x7-actual-effect.v1"
PROVENANCE = {
    "area_source": "検証/ARC3作用点成分面積HDS比較.py",
    "area_source_sha256": "cf3f783c39501b2887eb41acba20dd865854c00fc23d21127952cda8490c91e1",
    "components_source": "検証/ARC3公開画素効果診断.py",
    "components_source_sha256": "003cbbae82e6da73919341496faaab47ad353fd6a2f9b1697375a4b5aea10d7c",
    "effect_source": "検証/ARC3作用点効果HDS学習診断.py",
    "effect_source_sha256": "331245be4dbffb17826fecc081c38ec68957e22992163e763cf97c6bfbb69dff",
    "positive_offline_proof_sha256": "8a24087d6a2e445a1e3991e155a3a63025d1b917c4f35f8bb20fdb542227ec24",
    "prior_positive_context": "REDUCED before-context without action availability; one reused game only",
    "runtime_context": "FULL original before-context plus exactly ONE PRE-area integer",
}


def component_area(before, action):
    """Area of the maximal PRE-target same-color4CC, without shape/identity matching."""
    if action.number != 6:
        return None
    board = before.board
    height, width = len(board), len(board[0])
    if not 0 <= action.x < width or not 0 <= action.y < height:
        raise ValueError("PRE target is outside the public board")
    color, seen, pending = board[action.y][action.x], {(action.x, action.y)}, [(action.x, action.y)]
    while pending:
        x, y = pending.pop()
        for nx, ny in ((x - 1, y), (x + 1, y), (x, y - 1), (x, y + 1)):
            if (
                0 <= nx < width
                and 0 <= ny < height
                and (nx, ny) not in seen
                and board[ny][nx] == color
            ):
                seen.add((nx, ny))
                pending.append((nx, ny))
    return len(seen)


def effect_class(before, action, after):
    """Actual changed pixels relative to the PRE-target fixed7x7 square.

    Unequal/empty visible shapes are UNKNOWN: no inferred missing/fatal pixels.
    Original public outcome remains available independently.
    """
    if action.number != 6:
        return None
    if (
        not before.board
        or not after.board
        or len(before.board) != len(after.board)
        or len(before.board[0]) != len(after.board[0])
    ):
        return None
    local = remote = False
    for y, row in enumerate(before.board):
        for x, cell in enumerate(row):
            if cell != after.board[y][x]:
                if abs(x - action.x) <= 3 and abs(y - action.y) <= 3:
                    local = True
                else:
                    remote = True
    return EFFECT_BY_FLAGS[(local, remote)]


def enrich(content, before, action, after=None):
    result = deepcopy(content)
    if action.number == 6:
        result["作用前公開状態"][AREA] = component_area(before, action)
        if after is not None:
            effect = effect_class(before, action, after)
            if effect is not None:
                result[TARGET] = effect
    return result


def query_content(api, before, action):
    return enrich(api._query_content(before, action), before, action)


class ObserverBridge:
    """Intercept the original bridge encoder only after its lifecycle guards pass."""

    def __init__(self, core):
        self.core = core

    def __getattr__(self, name):
        return getattr(self.core, name)

    def _invoke(self, operation, before, action, after=None):
        original = self.core._call

        def observed(kind, content):
            return original(kind, enrich(content, before, action, after))

        self.core._call = observed
        try:
            return operation()
        finally:
            self.core._call = original

    def query(self, current, candidate):
        return self._invoke(lambda: self.core.query(current, candidate), current, candidate)

    def update(self, before, action, after):
        return self._invoke(lambda: self.core.update(before, action, after), before, action, after)


def native_locality_evidence(native, clip):
    content = getattr(native, "内容", None)
    content = content if isinstance(content, dict) else {}
    records, counts, truncated = {}, {}, False
    for key in ("予測群", "有効原理群", "競合群", "追加観測要求群", "係争中原理群", "識別不能群"):
        rows = content.get(key)
        if not isinstance(rows, (list, tuple)):
            records[key], counts[key] = None, None
            continue
        selected = [
            r for r in rows if isinstance(r, dict) and tuple(r.get("結果経路", ())) == (TARGET,)
        ]
        records[key], cut = clip(selected)
        counts[key] = len(selected)
        truncated |= cut
    holds, cut = clip(content.get("断定保留理由群"))
    result = {
        "native_status": getattr(native, "状態", None),
        "native_judgment_scope": "whole_query_original_0.4.2",
        "native_hold_reasons": holds,
        "target_result_path": [TARGET],
        "target_records": records,
        "target_record_counts": counts,
        "summary_is_truncated": truncated or cut,
        "support_counts": "UNKNOWN_UNLESS_EXPLICITLY_RETURNED_IN_NATIVE_RECORD",
        "missing_fields_are_unknown": True,
        "projection_revision": REVISION,
        "geometry_is_not_mechanism_or_progress": True,
        "remote_only_is_not_noop_failure_or_HUD": True,
    }
    if len(json.dumps(result, ensure_ascii=False)) > 5000:
        result["target_records"] = {key: None if rows else rows for key, rows in records.items()}
        result["target_record_details"] = "OMITTED_RESPONSE_BUDGET"
        result["summary_is_truncated"] = True
    return result
