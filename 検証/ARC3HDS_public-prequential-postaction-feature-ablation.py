from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
HDS_ROOT = ROOT / "HDS/学習系統/v0.4.2"
sys.path[:0] = [str(HDS_ROOT), str(ROOT / "接続"), str(ROOT / "検証")]

from ARC3視覚HDS接続候補 import VisualHDSBridge  # noqa: E402


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
BOUNDARY = "ARC3視覚公開作用応答候補"
PURPOSE = "公開遷移からのAction応答を事前予測する隔離診断"
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
    rows = state.get("public_response_rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"No public response rows in {state_path}")
    ordered = sorted(rows, key=lambda row: row["public_step_before"])
    if any(row.get("update_bridge_status") != "updated" for row in ordered):
        raise ValueError(f"A public response update did not succeed for {game}")
    return state_path, state, ordered


def query_input(update_input: dict[str, Any]) -> dict[str, Any]:
    """Reconstruct the pre-action query map by removing observed outcome fields."""
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


def run_arm(
    artifacts: Path,
    games: tuple[str, ...],
    *,
    exclude_post_action_feature: bool,
) -> dict[str, Any]:
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
        step39: dict[str, Any] | None = None
        for row in rows:
            update = copy.deepcopy(row["projected_update_input"])
            pre_action = query_input(update)
            recorded_query = row.get("projected_query_input_at_matching_inspection")
            if recorded_query is not None and pre_action != recorded_query:
                raise ValueError(
                    f"Reconstructed pre-action query differs from the recorded query in {game}"
                )

            query = bridge._call("query", pre_action)
            predicted = forecast_value(query)
            observed = update.get(TARGET)
            item = {
                "public_step_before": row["public_step_before"],
                "action_number": row["actual_action_number"],
                "observed_response": observed,
                "predicted_response": predicted,
                "prediction_count": query.get("relevant_prediction_count", 0),
                "active_rule_count": query.get("relevant_active_rule_count", 0),
                "observation_request_count": query.get(
                    "relevant_observation_request_count", 0
                ),
                "native_status": query.get("native_status"),
                "post_action_effect_condition_rules": sum(
                    POST_ACTION_FEATURE in path
                    for rule in query.get("rule_evidence", [])
                    for path in rule.get("condition_paths", [])
                ),
            }
            item["correct"] = predicted == observed if predicted is not None else None
            scored.append(item)
            if row["public_step_before"] == 39:
                step39 = copy.deepcopy(item)

            if exclude_post_action_feature:
                update.pop(POST_ACTION_FEATURE, None)
            updated = bridge._call("update", update)
            if updated.get("bridge_status") != "updated":
                raise RuntimeError(
                    f"HDS update failed for {game} step {row['public_step_before']}: {updated}"
                )

        per_game[game] = {
            "input_state_sha256": sha256(state_path),
            "updates": len(rows),
            "queries": len(rows),
            "query_update_state_had_prior_context": state.get("prior", {}).get("loaded_count"),
            "step39": step39,
            "metrics": metrics(scored),
            "action6_metrics": metrics([x for x in scored if x["action_number"] == 6]),
            "post_action_effect_condition_rules_seen": sum(
                x["post_action_effect_condition_rules"] for x in scored
            ),
        }
        all_rows.extend(scored)

    return {
        "exclude_post_action_feature_from_updates": exclude_post_action_feature,
        "per_game": per_game,
        "aggregate": metrics(all_rows),
        "action6_aggregate": metrics([x for x in all_rows if x["action_number"] == 6]),
        "post_action_effect_condition_rules_seen": sum(
            x["post_action_effect_condition_rules"] for x in all_rows
        ),
    }


def metrics(rows: list[dict[str, Any]]) -> dict[str, Any]:
    forecasted = [row for row in rows if row["predicted_response"] is not None]
    correct = sum(row["correct"] is True for row in forecasted)
    return {
        "transitions": len(rows),
        "forecasted": len(forecasted),
        "coverage": len(forecasted) / len(rows) if rows else 0.0,
        "correct": correct,
        "precision": correct / len(forecasted) if forecasted else None,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Read-only prequential HDS comparison on exact public transitions. "
            "Candidate excludes the post-action effect feature from the response learner."
        )
    )
    parser.add_argument("--artifacts", type=Path, default=DEFAULT_ARTIFACTS)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    artifacts = args.artifacts.resolve()
    games = DEFAULT_GAMES

    baseline = run_arm(artifacts, games, exclude_post_action_feature=False)
    candidate = run_arm(artifacts, games, exclude_post_action_feature=True)
    result = {
        "schema": "arc3-hds-public-prequential-postaction-feature-ablation.v1",
        "source_run": "C2-088 B-v3 sequential version 4",
        "games": list(games),
        "boundary": BOUNDARY,
        "target": TARGET,
        "removed_candidate_feature": POST_ACTION_FEATURE,
        "comparison": "same ordered public transitions; query before each update; fresh prior-loaded HDS per game",
        "baseline": baseline,
        "candidate": candidate,
        "score_effect": "NOT_MEASURED",
        "action_or_score_improvement_proven": False,
        "official_submission_or_kernel_run": False,
    }
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
