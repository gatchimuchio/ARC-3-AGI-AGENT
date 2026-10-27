"""既存VisualHDSBridgeの理想化した合成経験からの実学習を小さく観測する。"""

from __future__ import annotations

import argparse
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "検証"))

from ARC3視覚HDS接続候補 import (  # noqa: E402
    PublicAction,
    PublicFrame,
    VisualHDSBridge,
    _query_content,
    render_hint,
)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _hds_manifest() -> str:
    base = ROOT / "HDS/学習系統/v0.4.2"
    rows = [
        f"{path.relative_to(base).as_posix()}:{_sha256(path)}"
        for path in sorted(base.rglob("*.py"))
    ]
    return hashlib.sha256("\n".join(rows).encode("utf-8")).hexdigest()


def _native_outcome_rules(bridge: VisualHDSBridge) -> list[dict]:
    return [
        {
            "principle_ref": rule.原理識別子,
            "version": rule.版,
            "relation": rule.関係型,
            "condition_paths": rule.条件経路群,
            "result_path": rule.結果経路,
            "support_count": len(rule.根拠参照群),
            "counterevidence_count": len(rule.反証参照群),
            "native_scope": dict(rule.適用範囲),
            "native_state": rule.状態.value,
            "native_adoption_state": rule.採用状態.value,
        }
        for rule in bridge._hds.エンジン._有効原理群()
        if rule.結果経路 == ("公開応答区分",)
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    output = args.output if args.output.is_absolute() else ROOT / args.output
    if output.exists():
        parser.error(f"refusing to overwrite evidence: {output}")
    started = time.perf_counter()
    boards = (
        ((0, 1, 0, 1), (1, 0, 1, 0), (0, 1, 0, 1), (1, 0, 1, 0)),
        ((0, 0, 0, 0), (0, 0, 0, 0), (1, 1, 1, 1), (2, 2, 2, 2)),
        ((0, 1, 2, 3), (1, 2, 3, 0), (2, 3, 0, 1), (3, 0, 1, 2)),
    )
    heldout = ((1, 0, 1, 0), (0, 1, 0, 1), (1, 0, 1, 0), (0, 1, 0, 1))
    bridge = VisualHDSBridge(update_budget=12, query_budget=2, hds_seconds_budget=25.0)
    training = []
    for repeat in range(2):
        for board_index, board in enumerate(boards):
            before = PublicFrame(board, "NOT_FINISHED", 0, (1, 2))
            for action_number in (1, 2):
                action = PublicAction(action_number)
                after_board = board
                if action_number == 1:
                    mutable = [list(row) for row in board]
                    mutable[0][0] = (mutable[0][0] + 1) % 16
                    after_board = tuple(tuple(row) for row in mutable)
                after = PublicFrame(after_board, "NOT_FINISHED", 0, (1, 2))
                result = bridge.update(before, action, after)
                training.append(
                    {
                        "repeat": repeat,
                        "synthetic_board_index": board_index,
                        "before_board": board,
                        "after_board": after_board,
                        "input_features": _query_content(before, action),
                        "expected_outcome": "盤面変化" if action_number == 1 else "可視変化なし",
                        "bridge_status": result["bridge_status"],
                        "native_status": result.get("native_status"),
                        "native_learning_state": result.get("native_learning_state"),
                        "native_active_outcome_rule_count": len(_native_outcome_rules(bridge)),
                    }
                )
    observation_count_before_queries = len(bridge._hds.エンジン.台帳.取得("観測台帳"))
    captured = []
    original_query = bridge._hds.照会する

    def capture_native_query(value):
        result = original_query(value)
        captured.append(result)
        return result

    # 検証用の同一呼出し観測。実HDSは一照会につき一回だけ実行する。
    bridge._hds.照会する = capture_native_query
    queries = []
    try:
        current = PublicFrame(heldout, "NOT_FINISHED", 0, (1, 2))
        for action_number in (1, 2):
            action = PublicAction(action_number)
            result = bridge.query(current, action)
            native = captured[-1] if len(captured) > len(queries) else None
            queries.append(
                {
                    "action_number": action_number,
                    "input_features": _query_content(current, action),
                    "bridge_result": result,
                    "rendered_hint": render_hint(result),
                    "native_output": asdict(native) if native is not None else None,
                }
            )
    finally:
        bridge._hds.照会する = original_query
    elapsed = time.perf_counter() - started
    result = {
        "schema": "arc3-visual-hds-synthetic-learning-probe.v1",
        "run_id": output.stem,
        "observed_at_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "purpose": "idealized one-step learning and adapter exposure check only",
        "actual_game_or_model_called": False,
        "game_ability_or_score_improvement_proven": False,
        "runtime_hds_notebook_or_bridge_source_changed": False,
        "training": training,
        "heldout_board": heldout,
        "heldout_board_was_training_before_board": heldout in boards,
        "heldout_public_features_match_one_training_context": (
            _query_content(PublicFrame(heldout, "NOT_FINISHED", 0, (1, 2)), PublicAction(1))
            in [row["input_features"] for row in training]
        ),
        "queries": queries,
        "native_active_outcome_rules": _native_outcome_rules(bridge),
        "native_observations_before_queries": observation_count_before_queries,
        "native_observations_after_queries": len(bridge._hds.エンジン.台帳.取得("観測台帳")),
        "stats": bridge.stats,
        "prior_report": bridge.prior_report,
        "total_actual_hds_updates_including_prior": (
            bridge.stats["updates_attempted"] + bridge.stats["prior_updates_attempted"]
        ),
        "under_forty_actual_hds_updates": (
            bridge.stats["updates_attempted"] + bridge.stats["prior_updates_attempted"] < 40
        ),
        "under_thirty_seconds": elapsed < 30.0,
        "elapsed_seconds": elapsed,
        "any_extracted_native_outcome_prediction": any(
            query["bridge_result"].get("relevant_prediction_count", 0) for query in queries
        ),
        "any_rendered_hint": any(query["rendered_hint"] for query in queries),
        "source_sha256": {
            "probe": _sha256(Path(__file__)),
            "bridge": _sha256(ROOT / "検証/ARC3視覚HDS接続候補.py"),
            "prior_loader": _sha256(ROOT / "接続/ARC3事前記憶.py"),
            "hds_python_source_manifest": _hds_manifest(),
        },
    }
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, sort_keys=True, indent=2) + "\n")
    print(
        json.dumps(
            {
                "updates_including_prior": result["total_actual_hds_updates_including_prior"],
                "elapsed_seconds": elapsed,
                "native_outcome_rules": len(result["native_active_outcome_rules"]),
                "native_statuses": [row["bridge_result"].get("native_status") for row in queries],
                "outcome_predictions": [row["bridge_result"].get("predictions") for row in queries],
                "rendered_hint_lengths": [len(row["rendered_hint"]) for row in queries],
            },
            ensure_ascii=False,
            separators=(",", ":"),
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
