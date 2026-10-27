from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
HDS_ROOT = ROOT / "HDS/学習系統/v0.4.2"
sys.path[:0] = [str(HDS_ROOT), str(ROOT / "接続"), str(ROOT / "検証")]

_ABLA_PATH = ROOT / "検証/ARC3HDS_prequential-bounded-guidance-audit.py"
_SPEC = importlib.util.spec_from_file_location("c2_099_public_trace", _ABLA_PATH)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"Could not load shared public-trace helpers from {_ABLA_PATH}")
_ABLA = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_ABLA)

import ARC3視覚HDS接続候補 as bridge_module  # noqa: E402
from ARC3視覚HDS接続候補 import VisualHDSBridge  # noqa: E402


DEFAULT_ARTIFACTS = _ABLA.DEFAULT_ARTIFACTS
DEFAULT_GAMES = _ABLA.DEFAULT_GAMES
TARGET = _ABLA.TARGET
POST_ACTION_FEATURE = _ABLA.POST_ACTION_FEATURE
BOUNDARY_ONLY = "境界領域変化のみ"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _bounded_unidentifiable_records(result: Any) -> list[dict[str, Any]]:
    content = getattr(result, "内容", None)
    content = content if isinstance(content, dict) else {}
    rows = content.get("識別不能群")
    rows = rows if isinstance(rows, (list, tuple)) else ()
    selected = [
        row
        for row in rows
        if isinstance(row, dict)
        and bridge_module._path(row.get("結果経路")) == (TARGET,)
    ]
    bounded: list[dict[str, Any]] = []
    for row in selected[:4]:
        conditions = row.get("条件経路群")
        conditions = conditions if isinstance(conditions, (list, tuple)) else ()
        bounded.append(
            {
                "result_path": [TARGET],
                "principle_refs": [x[:80] for x in row.get("原理参照群", ()) if isinstance(x, str)][:4],
                "condition_paths": [
                    [part[:64] for part in path[:4] if isinstance(part, str)]
                    for path in conditions[:4]
                    if isinstance(path, (list, tuple))
                ],
                "support_refs_count": len(row.get("支持参照群", ())),
                "counterevidence_refs_count": len(row.get("反証参照群", ())),
                "reason": row.get("理由", "")[:160] if isinstance(row.get("理由"), str) else "",
            }
        )
    return bounded


_ORIGINAL_NATIVE_SUMMARY = bridge_module._native_summary


def _instrumented_native_summary(result: Any) -> dict[str, Any]:
    summary = _ORIGINAL_NATIVE_SUMMARY(result)
    content = getattr(result, "内容", None)
    content = content if isinstance(content, dict) else {}
    rows = content.get("識別不能群")
    rows = rows if isinstance(rows, (list, tuple)) else ()
    target_rows = [
        row
        for row in rows
        if isinstance(row, dict)
        and bridge_module._path(row.get("結果経路")) == (TARGET,)
    ]
    summary["target_unidentifiable_count"] = len(target_rows)
    summary["target_unidentifiable_evidence"] = _bounded_unidentifiable_records(result)
    summary["target_unidentifiable_summary_truncated"] = len(target_rows) > 4
    return summary


def _install_diagnostic_projection() -> None:
    bridge_module._OUTCOMES.add(BOUNDARY_ONLY)
    bridge_module._native_summary = _instrumented_native_summary


def run(artifacts: Path, games: tuple[str, ...]) -> dict[str, Any]:
    _install_diagnostic_projection()
    per_game: dict[str, Any] = {}
    all_rows: list[dict[str, Any]] = []
    public_labels: Counter[str] = Counter()

    for game in games:
        state_path, state, rows = _ABLA.load_rows(artifacts, game)
        bridge = VisualHDSBridge(
            update_budget=len(rows),
            query_budget=len(rows),
            hds_seconds_budget=120.0,
        )
        if bridge.prior_report.get("loaded_count") != 5:
            raise RuntimeError(f"Prior context did not load for {game}: {bridge.prior_report}")

        trace_rows: list[dict[str, Any]] = []
        for row in rows:
            update = copy.deepcopy(row["projected_update_input"])
            pre_action = _ABLA.query_input(update)
            recorded_query = row.get("projected_query_input_at_matching_inspection")
            if recorded_query is not None and pre_action != recorded_query:
                raise ValueError(f"Reconstructed query differs from recorded query in {game}")

            query = bridge._call("query", pre_action)
            if query.get("bridge_status") != "queried":
                raise RuntimeError(f"HDS query failed for {game} step {row['public_step_before']}: {query}")
            action_number = update.get("作用", {}).get("番号")
            observed = update.get(TARGET)
            if isinstance(observed, str):
                public_labels[observed] += 1
            predictions = query.get("predictions", [])
            unique_values = sorted(
                {
                    item["value"]
                    for item in predictions
                    if isinstance(item, dict) and isinstance(item.get("value"), str)
                }
            )
            item = {
                "game": game,
                "step": row["public_step_before"],
                "action_number": action_number,
                "observed_response": observed,
                "native_status": query.get("native_status"),
                "native_hold_reasons_global": query.get("native_hold_reasons", []),
                "target_prediction_count": query.get("relevant_prediction_count", 0),
                "target_prediction_values": unique_values,
                "unique_prediction_correct_on_executed_action": (
                    unique_values[0] == observed if len(unique_values) == 1 else None
                ),
                "target_active_rule_count": query.get("relevant_active_rule_count", 0),
                "target_rule_evidence": query.get("rule_evidence", []),
                "target_conflict_count": query.get("relevant_conflict_count", 0),
                "target_observation_requests": query.get("observation_requests", []),
                "target_unidentifiable_count": query.get("target_unidentifiable_count", 0),
                "target_unidentifiable_evidence": query.get(
                    "target_unidentifiable_evidence", []
                ),
                "target_unidentifiable_summary_truncated": query.get(
                    "target_unidentifiable_summary_truncated", False
                ),
                "authorization": query.get("authorization"),
            }
            if item["authorization"] is not False:
                raise RuntimeError(f"HDS authorization changed for {game} step {item['step']}")
            trace_rows.append(item)

            update.pop(POST_ACTION_FEATURE, None)
            updated = bridge._call("update", update)
            if updated.get("bridge_status") != "updated":
                raise RuntimeError(f"HDS update failed for {game} step {row['public_step_before']}")

        per_game[game] = {
            "input_state_sha256": sha256(state_path),
            "transitions": len(rows),
            "prior_count": bridge.prior_report.get("loaded_count"),
            "queries_before_updates": True,
            "post_action_effect_excluded_from_updates": True,
            "summary": summarize(trace_rows),
            "trace": trace_rows,
        }
        all_rows.extend(trace_rows)

    return {
        "schema": "arc3-hds-target-unidentifiability-audit.v1",
        "source_run": "C2-088 B-v3 sequential exact output version 4",
        "games": list(games),
        "transitions": len(all_rows),
        "target": TARGET,
        "public_observed_target_label_counts": dict(sorted(public_labels.items())),
        "display_only_vocabulary_extension": BOUNDARY_ONLY,
        "comparison": "same ordered public transitions; pre-action query before every update; fresh prior-loaded HDS per game; post-action effect excluded from updates",
        "aggregate": summarize(all_rows),
        "native_hold_preserved": True,
        "action_authorization_false": True,
        "score_effect": "NOT_MEASURED",
        "official_submission_or_kernel_run": False,
        "per_game": per_game,
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    hold_reasons: Counter[str] = Counter()
    unidentifiable_reasons: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    for row in rows:
        statuses[str(row["native_status"])] += 1
        hold_reasons.update(str(reason) for reason in row["native_hold_reasons_global"])
        for item in row["target_unidentifiable_evidence"]:
            unidentifiable_reasons[str(item.get("reason", ""))] += 1
    return {
        "transitions": len(rows),
        "native_HOLD": sum(row["native_status"] == "断定保留" for row in rows),
        "target_unidentifiable_present": sum(row["target_unidentifiable_count"] > 0 for row in rows),
        "target_unidentifiable_records": sum(row["target_unidentifiable_count"] for row in rows),
        "target_prediction_present": sum(row["target_prediction_count"] > 0 for row in rows),
        "unique_prediction_correct_on_executed_action": sum(
            row["unique_prediction_correct_on_executed_action"] is True for row in rows
        ),
        "unique_prediction_wrong_on_executed_action": sum(
            row["unique_prediction_correct_on_executed_action"] is False for row in rows
        ),
        "target_active_rule_present": sum(row["target_active_rule_count"] > 0 for row in rows),
        "target_conflict_present": sum(row["target_conflict_count"] > 0 for row in rows),
        "target_observation_request_present": sum(
            bool(row["target_observation_requests"]) for row in rows
        ),
        "native_status_counts": dict(sorted(statuses.items())),
        "target_unidentifiable_reason_counts_from_bounded_evidence": dict(
            sorted(unidentifiable_reasons.items())
        ),
        "global_native_hold_reason_counts": dict(sorted(hold_reasons.items())),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Expose only target-scoped unidentifiable records in a read-only HDS diagnostic projection."
    )
    parser.add_argument("--artifacts", type=Path, default=DEFAULT_ARTIFACTS)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = run(args.artifacts.resolve(), DEFAULT_GAMES)
    encoded = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        output = args.output.resolve()
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(encoded, encoding="utf-8", newline="\n")
        result["output_path"] = str(output)
        result["output_sha256"] = sha256(output)
    print(json.dumps(result, ensure_ascii=True, separators=(",", ":")))


if __name__ == "__main__":
    main()
