from __future__ import annotations

import argparse
import copy
import hashlib
import importlib.util
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
HDS_ROOT = ROOT / "HDS/学習系統/v0.4.2"
sys.path[:0] = [str(HDS_ROOT), str(ROOT / "接続"), str(ROOT / "検証")]

_ABLATOM = ROOT / "検証/ARC3HDS_prequential-bounded-guidance-audit.py"
_SPEC = importlib.util.spec_from_file_location("c2_099_bounded_guidance", _ABLATOM)
if _SPEC is None or _SPEC.loader is None:
    raise RuntimeError(f"Could not load shared public-trace helpers from {_ABLATOM}")
_ABLA = importlib.util.module_from_spec(_SPEC)
_SPEC.loader.exec_module(_ABLA)

import ARC3視覚HDS接続候補 as hds_bridge_module  # noqa: E402
from ARC3視覚HDS接続候補 import VisualHDSBridge  # noqa: E402


DEFAULT_ARTIFACTS = _ABLA.DEFAULT_ARTIFACTS
DEFAULT_GAMES = _ABLA.DEFAULT_GAMES
TARGET = _ABLA.TARGET
POST_ACTION_FEATURE = _ABLA.POST_ACTION_FEATURE


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def step_band(step: int) -> str:
    if step < 5:
        return "early_0_4"
    if step < 20:
        return "developing_5_19"
    return "mature_20_plus"


def run(artifacts: Path, games: tuple[str, ...]) -> dict[str, Any]:
    original_display_vocabulary = set(hds_bridge_module._OUTCOMES)
    observed_label_counts: Counter[str] = Counter()
    for game in games:
        _, _, source_rows = _ABLA.load_rows(artifacts, game)
        for source_row in source_rows:
            value = source_row["projected_update_input"].get(TARGET)
            if isinstance(value, str):
                observed_label_counts[value] += 1
    # This only widens the diagnostic serializer's display whitelist. It does
    # not alter HDS input, updates, native status, or action authorization.
    hds_bridge_module._OUTCOMES.update(observed_label_counts)

    per_game: dict[str, Any] = {}
    all_rows: list[dict[str, Any]] = []
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
                raise ValueError(
                    f"Reconstructed pre-action query differs from recorded query in {game}"
                )

            query = bridge._call("query", pre_action)
            if query.get("bridge_status") != "queried":
                raise RuntimeError(
                    f"HDS query failed for {game} step {row['public_step_before']}: {query}"
                )
            action_number = update.get("作用", {}).get("番号")
            observed = update.get(TARGET)
            predictions = query.get("predictions", [])
            predicted_values = sorted(
                {
                    item["value"]
                    for item in predictions
                    if isinstance(item, dict) and isinstance(item.get("value"), str)
                }
            )
            item = {
                "step": row["public_step_before"],
                "step_band": step_band(row["public_step_before"]),
                "action_number": action_number,
                "observed_response": observed,
                "native_status": query.get("native_status"),
                "native_learning_state": query.get("native_learning_state"),
                "native_hold_reasons": query.get("native_hold_reasons", []),
                "target_prediction_count": query.get("relevant_prediction_count", 0),
                "target_predictions": predictions,
                "unique_target_prediction_values": predicted_values,
                "unique_prediction_correct": (
                    predicted_values[0] == observed if len(predicted_values) == 1 else None
                ),
                "target_active_rule_count": query.get("relevant_active_rule_count", 0),
                "target_rule_evidence": query.get("rule_evidence", []),
                "target_conflict_count": query.get("relevant_conflict_count", 0),
                "target_conflicts": query.get("conflicts", []),
                "target_observation_request_count": query.get(
                    "relevant_observation_request_count", 0
                ),
                "target_observation_requests": query.get("observation_requests", []),
                "summary_is_truncated": query.get("summary_is_truncated", False),
                "authorization": query.get("authorization"),
            }
            if item["authorization"] is not False:
                raise RuntimeError(f"HDS authorization changed for {game} step {item['step']}")
            trace_rows.append(item)

            update.pop(POST_ACTION_FEATURE, None)
            updated = bridge._call("update", update)
            if updated.get("bridge_status") != "updated":
                raise RuntimeError(
                    f"HDS update failed for {game} step {row['public_step_before']}: {updated}"
                )

        per_game[game] = {
            "input_state_sha256": sha256(state_path),
            "transitions": len(rows),
            "prior_count": bridge.prior_report.get("loaded_count"),
            "queries_before_updates": True,
            "post_action_effect_excluded_from_updates": True,
            "band_summary": summarize(trace_rows),
            "reasoning_trace": trace_rows,
        }
        all_rows.extend(trace_rows)

    return {
        "schema": "arc3-hds-mature-query-hold-reason-audit.v1",
        "source_run": "C2-088 B-v3 sequential exact output version 4",
        "prior_attempt_notes": [
            "The first C2-100 replay used the unchanged five-class display whitelist; inspection then found the archived public target also contains 境界領域変化のみ. Its output remains local and is superseded for prediction counts.",
            "The first schema-corrected replay completed all transitions but failed while serializing the vocabulary delta with AttributeError: module 'c2_099_bounded_guidance' has no attribute '_OUTCOMES'. No corrected result artifact was emitted; the delta now uses the original bridge-module vocabulary captured before replay.",
        ],
        "games": list(games),
        "transitions": len(all_rows),
        "target": TARGET,
        "public_observed_target_label_counts": dict(sorted(observed_label_counts.items())),
        "diagnostic_display_vocabulary": sorted(hds_bridge_module._OUTCOMES),
        "diagnostic_display_only_widened_from_observed_labels": sorted(
            set(observed_label_counts) - original_display_vocabulary
        ),
        "comparison": "same ordered public transitions; pre-action query before each update; fresh prior-loaded HDS per game; post-action effect excluded from updates",
        "aggregate": summarize(all_rows),
        "native_hold_preserved": True,
        "action_authorization_false": True,
        "score_effect": "NOT_MEASURED",
        "official_submission_or_kernel_run": False,
        "per_game": per_game,
    }


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    hold_reasons: Counter[str] = Counter()
    request_reasons: Counter[str] = Counter()
    statuses: Counter[str] = Counter()
    path_counts: Counter[str] = Counter()
    band_rows: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for row in rows:
        statuses[str(row["native_status"])] += 1
        hold_reasons.update(str(reason) for reason in row["native_hold_reasons"])
        request_reasons.update(
            str(item.get("reason", ""))
            for item in row["target_observation_requests"]
            if isinstance(item, dict)
        )
        for rule in row["target_rule_evidence"]:
            for path in rule.get("condition_paths", []):
                path_counts["/".join(path)] += 1
        band_rows[row["step_band"]].append(row)

    def counts(items: list[dict[str, Any]]) -> dict[str, int]:
        return {
            "transitions": len(items),
            "native_HOLD": sum(row["native_status"] == "断定保留" for row in items),
            "target_prediction_present": sum(row["target_prediction_count"] > 0 for row in items),
            "target_active_rule_present": sum(row["target_active_rule_count"] > 0 for row in items),
            "target_conflict_present": sum(row["target_conflict_count"] > 0 for row in items),
            "target_observation_request_present": sum(
                row["target_observation_request_count"] > 0 for row in items
            ),
            "unique_prediction_correct_on_executed_action": sum(
                row["unique_prediction_correct"] is True for row in items
            ),
            "unique_prediction_wrong_on_executed_action": sum(
                row["unique_prediction_correct"] is False for row in items
            ),
        }

    return {
        **counts(rows),
        "native_status_counts": dict(sorted(statuses.items())),
        "native_hold_reason_counts": dict(sorted(hold_reasons.items())),
        "target_observation_request_reason_counts": dict(sorted(request_reasons.items())),
        "target_rule_condition_path_counts": dict(sorted(path_counts.items())),
        "by_step_band": {
            band: counts(items) for band, items in sorted(band_rows.items())
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Trace native HOLD reasons and target-scoped HDS evidence on exact public transitions."
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
