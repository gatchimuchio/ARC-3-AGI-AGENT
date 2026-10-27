"""C2-081: inspect exact-version masked/shown outputs without promoting the experiment."""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import inspect
import json
from pathlib import Path
from statistics import mean
import sys
import zipfile

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
from 検証 import ARC3視覚HDS対応採点 as common
from 検証.ARC3視覚HDS公開逐次予測診断 import _majority, _record_response

COMMON_SHA = "6ca19fcb4860b257e71c292ca77e7d775660f0c8f2f759bc4a0c984d6544db6a"
R3_ZIP = ROOT / "出力/ARC3-RUN-003-local/C2-078/shadow-r3/visual-hds-source.zip"
R3_SHA = "ed0c13e329c948e774424ebc738eaf2a8c3bb83c0bcdbcf71945a0ac3c5f3766"
OUTCOMES = {"勝利", "GAME_OVER", "レベル進行", "盤面変化", "可視変化なし"}
PAIR_FIELDS = (
    "builder_source_sha256", "frozen_R3_builder_sha256", "candidate_runtime_source_sha256",
    "runtime_adapter_sha256", "base_notebook_sha256", "source_preparation_manifest_sha256",
    "bridge_sha256", "bundle_sha256", "patched_solver_sha256", "patched_additional_source_sha256",
    "shared_prompt_note", "native_HDS_version", "query_scope", "shared_model_seed",
    "pilot", "budgets_per_game", "environment_seed",
)
require, load, sha256 = common.require, common.load, common.sha256


def action_number(row: dict) -> int:
    raw = row.get("action", {}).get("id")
    if raw == "RESET":
        return 0
    require(isinstance(raw, str) and raw in {f"ACTION{i}" for i in range(1, 8)},
            "invalid saved action identity")
    return int(raw[-1])


def build_contract(path: Path, visibility: str) -> tuple[dict, dict, dict]:
    b = load(path)
    require(b.get("schema") == "arc3-python-hds-query-pilot-build.v1"
            and b.get("mode") == "shadow" and b.get("evidence_visibility") == visibility,
            "wrong Python-HDS build/visibility")
    require(b.get("pilot") == common.EXPECTED_PILOT and b.get("shared_model_seed") == 0
            and b.get("budgets_per_game") == {
                "update_budget": 80, "query_budget": 80, "hds_seconds_budget": 120},
            "pilot/model/HDS budgets differ")
    require(all(k in b for k in PAIR_FIELDS), "missing matched build source fields")
    require(b.get("native_judgment_modified") is False and b.get("endorsement") is False
            and b.get("query_scope") == "whole_query_original_0.4.2",
            "native query/authorization boundary changed")
    for filename, key in (("submission.ipynb", "output_notebook_sha256"),
                           ("kernel-metadata.json", "kernel_metadata_sha256"),
                           ("visual-hds-source.zip", "bundle_sha256")):
        require(sha256(path.parent / filename) == b.get(key), "build source hash mismatch")
    metadata = load(path.parent / "kernel-metadata.json")
    require(metadata.get("is_private") is True and metadata.get("enable_gpu") is True
            and metadata.get("enable_internet") is False, "expected private offline GPU pilot")
    require(sha256(R3_ZIP) == R3_SHA, "frozen original-native reference drift")
    with zipfile.ZipFile(R3_ZIP) as old, zipfile.ZipFile(path.parent / "visual-hds-source.zip") as z:
        for row in b["bundle_manifest"]["files"]:
            require(hashlib.sha256(z.read(row["path"])).hexdigest() == row["sha256"],
                    "source bundle member hash mismatch")
        native = [n for n in old.namelist() if n.startswith("HDS/") and n.endswith(".py")]
        unchanged = native + [n for n in old.namelist() if n.startswith(("接続/", "検証/"))]
        require(len(native) == 12 and all(z.read(n) == old.read(n) for n in unchanged),
                "native/prior/bridge differs from canonical frozen R3")
    return b, metadata, load(path.parent / "submission.ipynb")


def response_metrics(rows: list, history: list, trace: list, trace_truncated: bool) -> dict:
    """Re-use the audited strictly-past comparator; every preceding response participates."""
    expected = [(i, action_number(r)) for i, r in enumerate(history) if action_number(r)]
    require(isinstance(rows, list) and len(rows) == len(expected), "incomplete nonRESET response stream")
    previous, counts, statuses, opportunities = Counter(), Counter(), {}, Counter()
    target_counts, unknown_counts = Counter(), Counter()
    require(isinstance(trace, list) and all(isinstance(r, dict) for r in trace), "invalid ordering trace")
    inspections = {r.get("inspection_id"): r for r in trace if r.get("event") == "query_returned"}
    for row, (step, number) in zip(rows, expected):
        require(isinstance(row, dict) and row.get("public_step_before") == step
                and row.get("public_step_after") == step + 1
                and row.get("actual_action_number") == number, "response/history step join mismatch")
        outcome = row.get("observed_public_outcome")
        require(outcome in OUTCOMES and row.get("authorization") is False
                and row.get("endorsement") is False, "invalid public response/boundary")
        update_input = row.get("projected_update_input")
        require(isinstance(update_input, dict) and update_input.get("公開応答区分") == outcome,
                "response update projection mismatch")
        matched = row.get("matching_candidate_was_queried_before_action") is True
        query_input = row.get("projected_query_input_at_matching_inspection")
        if matched:
            require(type(row.get("matching_inspection_id")) is int and row["matching_inspection_id"] > 0
                    and isinstance(query_input, dict) and "公開応答区分" not in query_input
                    and query_input == {k: v for k, v in update_input.items() if k != "公開応答区分"},
                    "matched candidate receipt/query projection mismatch")
            opportunities["matched_candidate_receipts"] += 1
            inspection = inspections.get(row["matching_inspection_id"])
            if inspection is None:
                require(trace_truncated, "candidate receipt not found in complete ordering trace")
                opportunities["inspection_trace_join_UNKNOWN_truncated"] += 1
            else:
                require(inspection.get("step") == step
                        and inspection.get("tool_call_id") == row.get("query_tool_call_id")
                        and inspection.get("model_turn_id") == row.get("query_model_turn_id"),
                        "candidate receipt/ordering trace mismatch")
                opportunities["matched_candidate_trace_joins"] += 1
            native_counts = row.get("native_target_counts_at_query")
            for field in ("予測群", "有効原理群", "競合群", "追加観測要求群", "係争中原理群", "識別不能群"):
                value = native_counts.get(field) if isinstance(native_counts, dict) else None
                if value is None:
                    unknown_counts[field] += 1
                else:
                    target_counts[field] += common.nonnegative(value, "native target count", integer=True)
            query_turn, action_turn = row.get("query_model_turn_id"), row.get("action_model_turn_id")
            if query_turn and action_turn:
                label = ("SAME_RESPONSE_UNREVIEWED" if query_turn == action_turn
                         else "distinct_model_response_observation_opportunity")
                opportunities[label] += 1
            else:
                opportunities["model_response_relation_UNKNOWN"] += 1
            if row.get("query_tool_call_id") == row.get("action_tool_call_id"):
                opportunities["SAME_PYTHON_CALL_UNREVIEWED"] += 1
        else:
            require(query_input is None and row.get("matching_inspection_id") is None,
                    "unmatched candidate has query receipt")
        values = row.get("native_active_ref_forecast_values_at_query")
        status = row.get("native_status_at_query")
        measurable = (matched and row.get("native_summary_truncated_at_query") is False
                      and isinstance(values, list) and len(values) == 1
                      and values[0] in OUTCOMES and status in {"出力", "断定保留"})
        majority, _ = _majority(previous)
        if measurable:
            bucket = statuses.setdefault(status, Counter())
            bucket["forecasts"] += 1
            bucket["matches"] += int(values[0] == outcome)
            if majority is not None:
                bucket["same_covered_steps_with_past_majority"] += 1
                bucket["past_majority_matches"] += int(majority == outcome)
        _record_response(previous, set(values) if measurable else set(),
                         None if measurable else "UNMEASURED_UNQUERIED_UNKNOWN_CLIPPED_OR_NONUNIQUE",
                         outcome, counts)
    covered, compared = counts["target_qualified_unique_forecasts"], counts["same_covered_steps_with_majority"]
    return {"counts": dict(counts), "ordering": dict(opportunities),
            "native_target_count_sums": dict(target_counts), "native_target_UNKNOWN_query_counts": dict(unknown_counts),
            "native_status_forecast_counts": {k: dict(v) for k, v in statuses.items()},
            "forecast_precision": counts["target_unique_matches"] / covered if covered else None,
            "same_covered_past_majority_precision": counts["majority_matches_on_same_covered_steps"] / compared if compared else None,
            "same_covered_native_precision": counts["target_matches_on_majority_comparable_steps"] / compared if compared else None}


def telemetry(paths: set[str], root: Path, runs: dict, visibility: str, budgets: dict) -> dict:
    counters, operations, seconds, prior, errors, native_status = (Counter() for _ in range(6))
    metrics = []
    failures, budget_flags, error_types = [], Counter(), Counter()
    max_overrun = 0.0
    active_games = 0
    for gid, run in runs.items():
        name = f"artifacts/{gid}_p0_tool_runtime_state.visual-hds-query.json"
        try:
            require(name in paths, "missing Python-HDS sidecar")
            d = load(root / name)
            require(d.get("schema") == "arc3-python-hds-query-telemetry.v1"
                    and d.get("visibility") == visibility and d.get("authorization") is False
                    and d.get("endorsement") is False and d.get("native_judgment_modified") is False
                    and d.get("native_scope") == "whole_query_original_0.4.2", "wrong Python-HDS telemetry boundary")
            c, h, p = d.get("counts"), d.get("hds"), d.get("prior")
            require(isinstance(c, dict), "missing runtime counters")
            for k, v in c.items():
                counters[k] += common.nonnegative(v, "runtime counter", integer=True)
            require(c.get("actual_action_calls_seen") == len(run["history"]), "runtime/history action count differs")
            require(isinstance(h, dict) and isinstance(p, dict), "learner/prior unavailable")
            for key in common.HDS_COUNTS:
                operations[key] += common.nonnegative(h.get(key), key, integer=True)
            for key in common.HDS_SECONDS:
                seconds[key] += common.nonnegative(h.get(key), key)
            require(all(h.get(k) == v for k, v in budgets.items()), "runtime/build HDS budgets differ")
            for kind, plural in (("update", "updates"), ("query", "queries")):
                require(h[f"{plural}_succeeded"] <= h[f"{plural}_attempted"] <= budgets[f"{kind}_budget"],
                        "HDS native operation count exceeds budget")
            require(p.get("loaded_count") == 5 and p.get("load_status") == "loaded"
                    and p.get("action_authorization") is False, "fixed prior incomplete")
            active_games += int(h["updates_succeeded"] > 0)
            prior[p["load_status"]] += 1
            for key in ("update_budget_exhausted", "query_budget_exhausted", "time_budget_exhausted"):
                require(type(h.get(key)) is bool, "missing HDS budget flag")
                budget_flags[key] += int(h[key])
            max_overrun = max(max_overrun, h["total_hds_seconds"] - budgets["hds_seconds_budget"])
            if d.get("last_error_type") or h.get("last_error_type"):
                error_types[str(d.get("last_error_type") or h.get("last_error_type"))] += 1
            m = response_metrics(d.get("public_response_rows"), run["history"],
                                 d.get("ordering_trace"), bool(c.get("ordering_trace_truncated")))
            require(h["updates_succeeded"] + c.get("update_status:budget_exhausted", 0)
                    == len(d["public_response_rows"]), "response update coverage mismatch")
            require(sum(r.get("update_bridge_status") == "updated" for r in d["public_response_rows"])
                    == h["updates_succeeded"], "per-response update receipts differ from native stats")
            metrics.append(m)
        except (ValueError, KeyError, TypeError, OSError) as exc:
            failures.append(str(exc) if isinstance(exc, ValueError) else f"telemetry data error: {type(exc).__name__}")
    for k, v in counters.items():
        if k.startswith("query_native:"):
            native_status[k.split(":", 1)[1]] += v
        if k.endswith("_errors"):
            errors[k] += v
    for key in ("update_errors", "query_errors", "summary_errors", "prior_update_errors", "rejected_requests"):
        errors[key] += operations[key]
    combined, order, strata, targets, unknown_targets = Counter(), Counter(), {}, Counter(), Counter()
    for m in metrics:
        combined.update(m["counts"])
        order.update(m["ordering"])
        targets.update(m["native_target_count_sums"])
        unknown_targets.update(m["native_target_UNKNOWN_query_counts"])
        for status, values in m["native_status_forecast_counts"].items():
            strata.setdefault(status, Counter()).update(values)
    covered, compared = combined["target_qualified_unique_forecasts"], combined["same_covered_steps_with_majority"]
    queries = counters["query_helper_calls"]
    integration_valid = not failures and not sum(errors.values()) and not error_types
    exposure = ("UNKNOWN_INTEGRATION_FAILURE" if not integration_valid else
                "NO_QUERY" if not queries else "MASKED" if visibility == "masked" else
                "SHOWN_RPC_NATIVE_AVAILABLE_MODEL_RENDERING_UNKNOWN" if operations["queries_succeeded"] else
                "QUERY_UNAVAILABLE")
    response_count = sum(sum(bool(action_number(h)) for h in r["history"]) for r in runs.values())
    return {"integration_valid": bool(integration_valid),
            "integration_failures": failures, "counters": dict(counters), "operations": dict(operations),
            "seconds": dict(seconds), "prior_status_counts": dict(prior), "errors": dict(errors),
            "error_type_counts": dict(error_types), "native_query_status_counts": dict(native_status),
            "budgets_per_game": budgets, "budget_exhausted_game_counts": dict(budget_flags),
            "games_with_game_response_updates": active_games,
            "game_response_updates_success_coverage": operations["updates_succeeded"] / response_count if response_count else None,
            "max_soft_HDS_time_overrun_seconds": max_overrun,
            "strict_past_prediction_measurement": {
                "complete_game_streams": len(metrics), "counts": dict(combined),
                "native_status_forecast_counts": {k: dict(v) for k, v in strata.items()},
                "forecast_precision": combined["target_unique_matches"] / covered if covered else None,
                "same_covered_steps": compared,
                "same_covered_native_precision": combined["target_matches_on_majority_comparable_steps"] / compared if compared else None,
                "same_covered_past_majority_precision": combined["majority_matches_on_same_covered_steps"] / compared if compared else None,
                "scope": "Partial native active/adopted-ref forecasts; HOLD and target uncertainty remain separate. Unknown/clipped/nonunique forecasts unmeasured."},
            "matched_candidate_ordering": dict(order), "exposure_classification": exposure,
            "native_target_count_sums_on_matched_responses": dict(targets),
            "native_target_UNKNOWN_query_counts": dict(unknown_targets),
            "rendered_model_evidence_exposure": "UNKNOWN", "comprehension_or_adoption_proven": False,
            "same_response_unreviewed_is_gameplay_failure": False}


def inspect_arm(retrieval_path: Path, build_path: Path, output_root: Path, version: int) -> tuple[dict, dict]:
    b = load(build_path)
    visibility = b.get("evidence_visibility")
    require(visibility in {"masked", "shown"}, "unknown evidence visibility")
    b, metadata, notebook = build_contract(build_path, visibility)
    doc = load(retrieval_path)
    paths, identity = common.verify_retrieval(doc, output_root, b, metadata, version)
    require("benchmark.json" in paths, "missing benchmark")
    benchmark = load(output_root / "benchmark.json")
    runs = benchmark.get("game_runs")
    require(isinstance(runs, list) and len(runs) == 3 and benchmark.get("n_passes") == 1, "expected three games/one pass")
    keyed = {r.get("game_id"): r for r in runs}
    require(len(keyed) == 3 and all(isinstance(k, str) and k for k in keyed), "invalid game identities")
    scorer, scores, starts = common.helper(), {}, {}
    for gid, run in keyed.items():
        require(f"artifacts/{gid}_p0_events.jsonl" in paths, "missing initial event")
        starts[gid] = scorer.first_event(output_root, gid)
        require(all(k in starts[gid] for k in scorer.START_FIELDS), "missing public initial fields")
        scores[gid] = scorer.score_run(run)
        require(type(run.get("final_score")) in {int, float}
                and abs(scores[gid] - run["final_score"]) <= 1e-9, "saved RHAE differs from official recomputation")
        require(isinstance(run.get("history"), list)
                and len(run["history"]) == sum(run["actions_per_level"]) <= 80, "actual action budget/history mismatch")
        for h in run["history"]:
            action_number(h)
    clocks = common.audit_benchmark(benchmark)
    elapsed = [common.nonnegative(r["elapsed_since_previous_game_seconds"], "game clock") for r in clocks["game_runs"]]
    generated = [r["history_generated_tokens"] > 0 for r in clocks["game_runs"]]
    gameplay = all(generated) and max(elapsed) <= 1205 and all(r.get("state") in {"won", "gave_up"} for r in runs)
    hds = telemetry(paths, output_root, keyed, visibility, b["budgets_per_game"])
    result = {**identity, "kernel": doc["kernel"], "version": version, "status": doc["status"],
              "mode": "shadow", "evidence_visibility": visibility,
              "build_manifest_sha256": sha256(build_path), "retrieval_manifest_sha256": sha256(retrieval_path),
              "selected_output_manifest_sha256": doc["output_manifest_sha256"],
              "benchmark_sha256": sha256(output_root / "benchmark.json"), "games": 3,
              "public_offline_RHAE_mean": mean(scores.values()), "saved_scores_match_recomputed": True,
              "levels_completed": sum(r["levels_completed"] for r in runs),
              "levels_total": sum(r["number_of_levels"] for r in runs),
              "actual_actions": sum(len(r["history"]) for r in runs),
              "run_state_counts": dict(Counter(r["state"] for r in runs)),
              "history_generated_tokens": clocks["total_history_generated_tokens"],
              "games_with_visual_model_generation": sum(generated),
              "generation_flags_in_benchmark_order_when_invalid": generated if not all(generated) else None,
              "job_elapsed_seconds": clocks["job_elapsed_seconds"], "max_game_elapsed_seconds": max(elapsed),
              "gameplay_valid": gameplay, "integration_valid": hds["integration_valid"], "HDS": hds}
    result["environment_seed_evidence"] = b["environment_seed"]
    return result, {"build": b, "metadata": metadata, "notebook": notebook,
                    "runs": keyed, "starts": starts, "scores": scores}


def compare(masked: dict, shown: dict) -> dict:
    require(masked["build"]["evidence_visibility"] == "masked" and shown["build"]["evidence_visibility"] == "shown",
            "pair requires masked then shown")
    require(all(masked["build"][k] == shown["build"][k] for k in PAIR_FIELDS), "paired source/prompt/native/budget mismatch")
    require({k: v for k, v in masked["metadata"].items() if k not in {"id", "title"}}
            == {k: v for k, v in shown["metadata"].items() if k not in {"id", "title"}}, "paired model configuration mismatch")
    cells = []
    for arm, visibility in ((masked, "masked"), (shown, "shown")):
        rows = common.canonical_cells(arm["notebook"])
        marker = f'os.environ["ARC3_HDS_EVIDENCE_VISIBILITY"] = {visibility!r}'
        require(sum(r["source"].count(marker) for r in rows) == 1, "missing unique visibility selector")
        cells.append([{**r, "source": r["source"].replace(marker, "VISIBILITY_SELECTOR")} for r in rows])
    require(cells[0] == cells[1] and masked["notebook"].get("metadata") == shown["notebook"].get("metadata"),
            "paired notebook source differs beyond evidence visibility")
    require(set(masked["runs"]) == set(shown["runs"]), "paired game sets differ")
    scorer = common.helper()
    for gid in masked["runs"]:
        require(all(masked["starts"][gid][k] == shown["starts"][gid][k] for k in scorer.START_FIELDS), "paired public initial fields differ")
        require(all(masked["runs"][gid][k] == shown["runs"][gid][k]
                    for k in ("number_of_levels", "base_actions_per_level")), "paired public baselines differ")
    delta = [shown["scores"][gid] - masked["scores"][gid] for gid in masked["runs"]]
    return {"games": 3, "source_prompt_native_bundle_model_pilot_initial_fields_matched": True,
            "descriptive_mean_RHAE_delta_shown_minus_masked": mean(delta),
            "descriptive_game_direction_counts": {"higher": sum(x > 1e-9 for x in delta),
                                                   "equal": sum(abs(x) <= 1e-9 for x in delta),
                                                   "lower": sum(x < -1e-9 for x in delta)}}


def evaluate(retrieval: Path, build: Path, output_root: Path, version: int,
             *, other_retrieval: Path | None = None, other_build: Path | None = None,
             other_output_root: Path | None = None, other_version: int | None = None) -> dict:
    require(sha256(Path(common.__file__)) == COMMON_SHA, "shared score/retrieval helper drift")
    result, internal = inspect_arm(retrieval, build, output_root, version)
    scorer = common.helper()
    report = {"schema": "arc3-python-hds-query-scorecard.v1", "observed_at_utc": datetime.now(timezone.utc).isoformat(),
              "inspection": "single", "arm": result, "common_scorecard_sha256": COMMON_SHA,
              "official_RHAE_helper_sha256": common.HELPER_SHA,
              "strict_past_baseline_source_sha256": sha256(Path(inspect.getsourcefile(_record_response))),
              "score_source_file_sha256": sha256(Path(inspect.getsourcefile(scorer.EnvironmentScoreCalculator))),
              "scorecard_source_sha256": sha256(Path(__file__)),
              "official_score_observed": False, "official_submission_or_quota_use": False,
              "visibility_effect_proven": False, "learning_effect_proven": False,
              "limitation": "Shown may alter model-visible context. RPC return is programmatic availability; rendered model exposure, comprehension and adoption remain unverified. Visibility alone does not isolate learning; comparisons are descriptive and require repeats."}
    optional = (other_retrieval, other_build, other_output_root, other_version)
    require(all(x is None for x in optional) or all(x is not None for x in optional), "paired arm requires all four exact inputs")
    if other_retrieval is not None:
        other, other_internal = inspect_arm(other_retrieval, other_build, other_output_root, other_version)
        by_visibility = {result["evidence_visibility"]: (result, internal), other["evidence_visibility"]: (other, other_internal)}
        require(set(by_visibility) == {"masked", "shown"}, "pair needs both visibility modes")
        report.update(inspection="paired", masked=by_visibility["masked"][0], shown=by_visibility["shown"][0],
                      paired=compare(by_visibility["masked"][1], by_visibility["shown"][1]))
        report["paired"]["both_gameplay_valid"] = all(v[0]["gameplay_valid"] for v in by_visibility.values())
        report["paired"]["both_integration_valid"] = all(v[0]["integration_valid"] for v in by_visibility.values())
        report.pop("arm")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for prefix in ("", "other-"):
        for field in ("retrieval", "build", "output-root", "version"):
            parser.add_argument(f"--{prefix}{field}", type=int if field == "version" else Path, required=not prefix)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    if args.output.exists():
        parser.error("refusing to overwrite existing scorecard")
    try:
        result = evaluate(args.retrieval, args.build, args.output_root, args.version,
                          other_retrieval=args.other_retrieval, other_build=args.other_build,
                          other_output_root=args.other_output_root, other_version=args.other_version)
    except (ValueError, KeyError, TypeError, OSError, StopIteration) as exc:
        parser.error(str(exc))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    print(json.dumps(result, ensure_ascii=True))


if __name__ == "__main__":
    main()
