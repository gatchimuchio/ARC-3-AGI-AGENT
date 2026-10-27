from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
HDS_ROOT = ROOT / "HDS/学習系統/v0.4.2"
sys.path[:0] = [str(HDS_ROOT), str(ROOT / "接続"), str(ROOT / "検証")]

from ARC3視覚HDS接続候補 import (  # noqa: E402
    VisualHDSBridge,
    render_hint,
)


DEFAULT_ARTIFACTS = (
    ROOT
    / "出力/ARC3-RUN-003-local/C2-088/"
    / "B-v3-sequential-exact-output-version4-20261027T151952Z/artifacts"
)
DEFAULT_GAMES = (
    "m0r0-492f87ba",
    "sk48-d8078629",
    "tn36-ef4dde99",
)
POST_ACTION_FEATURE = "公開作用点効果区分"
TARGET = "公開応答区分"


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_rows(artifacts: Path, game: str) -> tuple[Path, dict[str, Any], list[dict[str, Any]]]:
    state_path = artifacts / f"{game}_p0_tool_runtime_state.visual-hds-query.json"
    state = json.loads(state_path.read_text(encoding="utf-8"))
    if state.get("authorization") is not False or state.get("native_judgment_modified") is not False:
        raise ValueError(f"Public trace lost its non-authorization boundary: {state_path}")
    rows = state.get("public_response_rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"No public response rows in {state_path}")
    ordered = sorted(rows, key=lambda row: row["public_step_before"])
    if any(row.get("update_bridge_status") != "updated" for row in ordered):
        raise ValueError(f"A public response update did not succeed for {game}")
    return state_path, state, ordered


def query_input(update_input: dict[str, Any]) -> dict[str, Any]:
    """Reconstruct the pre-action query map without observed outcome fields."""
    return {
        key: copy.deepcopy(value)
        for key, value in update_input.items()
        if key not in {TARGET, POST_ACTION_FEATURE}
    }


def forecast_value(result: dict[str, Any]) -> str | None:
    predictions = result.get("predictions")
    if not isinstance(predictions, list):
        return None
    values = {row.get("value") for row in predictions if isinstance(row, dict)}
    values.discard(None)
    return next(iter(values)) if len(values) == 1 else None


def metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    forecasted = [row for row in rows if row["raw_unique_prediction"] is not None]
    hinted = [row for row in rows if row["bounded_hint_prediction"] is not None]
    return {
        "transitions": len(rows),
        "raw_unique_forecasts": len(forecasted),
        "raw_unique_forecast_coverage": len(forecasted) / len(rows) if rows else 0.0,
        "raw_unique_forecasts_correct": sum(x["raw_correct"] is True for x in forecasted),
        "bounded_hints": len(hinted),
        "bounded_hint_coverage": len(hinted) / len(rows) if rows else 0.0,
        "bounded_hint_predictions_correct": sum(x["hint_correct"] is True for x in hinted),
        "legal_actions_recorded": sum(x["legal_action_count"] for x in rows),
        "states_with_alternative_legal_actions": sum(x["legal_action_count"] > 1 for x in rows),
        "actual_action_present_in_recorded_legal_set": sum(
            x["actual_action_recorded_legal"] for x in rows
        ),
    }


def run(artifacts: Path, games: tuple[str, ...]) -> dict[str, Any]:
    per_game: dict[str, Any] = {}
    all_rows: list[dict[str, Any]] = []
    for game in games:
        state_path, state, rows = load_rows(artifacts, game)
        bridge = VisualHDSBridge(
            update_budget=len(rows),
            query_budget=len(rows),
            hds_seconds_budget=120.0,
        )
        if bridge.prior_report.get("loaded_count") != 5:
            raise RuntimeError(f"Prior context did not load for {game}: {bridge.prior_report}")

        scored: list[dict[str, Any]] = []
        bridge_statuses: Counter[str] = Counter()
        native_statuses: Counter[str] = Counter()
        for row in rows:
            update = copy.deepcopy(row["projected_update_input"])
            pre_action = query_input(update)
            recorded_query = row.get("projected_query_input_at_matching_inspection")
            if recorded_query is not None and pre_action != recorded_query:
                raise ValueError(
                    f"Reconstructed pre-action query differs from recorded query in {game}"
                )

            query = bridge._call("query", pre_action)
            action = update.get("作用", {}).get("番号")
            if type(action) is not int:
                raise ValueError(f"Missing integer candidate action in {game}")
            query["candidate_action_number"] = action
            hint = render_hint(query)
            raw_prediction = forecast_value(query)
            hint_prediction = None
            if hint:
                try:
                    payload = json.loads(hint.split("\n", 1)[1])
                except (IndexError, json.JSONDecodeError) as exc:
                    raise ValueError("Bounded hint was not parseable JSON") from exc
                predictions = payload.get("predictions", [])
                values = {
                    item.get("value")
                    for item in predictions
                    if isinstance(item, dict) and isinstance(item.get("value"), str)
                }
                if len(values) == 1:
                    hint_prediction = next(iter(values))

            available = row.get("before_available_actions")
            if not isinstance(available, list) or any(type(a) is not int for a in available):
                raise ValueError(f"Missing public legal action list in {game}")
            legal_non_reset = sorted({a for a in available if 1 <= a <= 7})
            observed = update.get(TARGET)
            item = {
                "public_step_before": row["public_step_before"],
                "actual_action_number": action,
                "before_public_state": row.get("before_public_state"),
                "legal_action_count": len(legal_non_reset),
                "actual_action_recorded_legal": action in available,
                "observed_response": observed,
                "native_status": query.get("native_status"),
                "bridge_status": query.get("bridge_status"),
                "raw_unique_prediction": raw_prediction,
                "bounded_hint_prediction": hint_prediction,
                "raw_correct": raw_prediction == observed if raw_prediction is not None else None,
                "hint_correct": hint_prediction == observed if hint_prediction is not None else None,
                "hint_characters": len(hint),
                "hint_candidate_action_number": action if hint else None,
                "authorization": query.get("authorization"),
                "relevant_conflict_count": query.get("relevant_conflict_count", 0),
                "relevant_observation_request_count": query.get(
                    "relevant_observation_request_count", 0
                ),
            }
            if item["authorization"] is not False:
                raise RuntimeError(f"HDS bridge authorization changed for {game}")
            bridge_statuses[str(item["bridge_status"])] += 1
            native_statuses[str(item["native_status"])] += 1
            scored.append(item)

            update.pop(POST_ACTION_FEATURE, None)
            updated = bridge._call("update", update)
            if updated.get("bridge_status") != "updated":
                raise RuntimeError(
                    f"HDS update failed for {game} step {row['public_step_before']}: {updated}"
                )

        per_game[game] = {
            "input_state_sha256": sha256(state_path),
            "transitions": len(rows),
            "loaded_prior_principles": bridge.prior_report.get("loaded_count"),
            "post_action_effect_excluded_from_updates": True,
            "bridge_status_counts": dict(sorted(bridge_statuses.items())),
            "native_status_counts": dict(sorted(native_statuses.items())),
            "metrics": metrics(scored),
            "candidate_action_rows_have_compared_alternatives": 0,
            "bounded_hint_values_per_transition": [
                {
                    "step": x["public_step_before"],
                    "action": x["actual_action_number"],
                    "prediction": x["bounded_hint_prediction"],
                }
                for x in scored
                if x["bounded_hint_prediction"] is not None
            ],
        }
        all_rows.extend(scored)

    return {
        "schema": "arc3-hds-prequential-bounded-guidance-audit.v1",
        "source_run": "C2-088 B-v3 sequential exact output version 4",
        "initial_attempt_note": "The first C2-099 runner attempt exited with KeyError: 'raw_prediction' because the metrics reader used a mismatched row key. The field reference was corrected before the successful evaluation; the failed attempt produced no result artifact.",
        "games": list(games),
        "transitions": sum(row["transitions"] for row in per_game.values()),
        "comparison": "same archived public transitions; query before each update; fresh prior-loaded HDS per game; post-action effect excluded from updates",
        "aggregate": metrics(all_rows),
        "action6_aggregate": metrics(
            [row for row in all_rows if row["actual_action_number"] == 6]
        ),
        "action_ranking_effect_evaluable": False,
        "action_ranking_limitation": "Only the actually executed action has an outcome label in each recorded state; alternatives were not counterfactually executed or queried with state-complete inputs.",
        "native_hold_and_action_authorization_preserved": True,
        "official_score_effect": "NOT_MEASURED",
        "notebook_or_kernel_changed": False,
        "official_submission_or_kernel_run": False,
        "per_game": per_game,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Audit usable bounded HDS hints on exact public transitions without action authorization."
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
