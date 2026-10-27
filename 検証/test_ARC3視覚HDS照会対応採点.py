from __future__ import annotations

import json
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from 検証 import ARC3視覚HDS照会対応採点 as scorer
from 検証.test_ARC3視覚HDS対応採点 import change_json, make_arm, refresh, write_json


def fixture(tmp_path: Path, visibility: str, *, queries=True, same_response=False, completed=0) -> dict:
    arm = make_arm(tmp_path / visibility, "shadow", completed=completed)
    source = scorer.ROOT / f"出力/ARC3-RUN-003-local/C2-081/{visibility}-r2"
    for name in ("submission.ipynb", "kernel-metadata.json", "visual-hds-source.zip", "build-manifest.json"):
        shutil.copyfile(source / name, arm["build"].parent / name)
    build = scorer.load(arm["build"])
    metadata = scorer.load(arm["build"].parent / "kernel-metadata.json")
    benchmark = scorer.load(arm["root"] / "benchmark.json")
    sidecars = []
    for run in benchmark["game_runs"]:
        gid = run["game_id"]
        for i, h in enumerate(run["history"]):
            h["action"]["id"] = "RESET" if i == 0 else "ACTION1"
        old_path = arm["root"] / f"artifacts/{gid}_p0_tool_runtime_state.visual-hds.json"
        old = scorer.load(old_path)
        old_path.unlink()
        hds = old["hds"]
        hds.update(queries_attempted=int(queries), queries_succeeded=int(queries))
        counts = {"actual_action_calls_seen": 4, "update_status:updated": 3,
                  "query_helper_calls": int(queries), "query_status:queried": int(queries),
                  "query_native:断定保留": int(queries)}
        trace = ([{"event": "query_returned", "step": 2, "inspection_id": 1,
                   "tool_call_id": "python-1:call", "model_turn_id": "model-1", "native_status": "断定保留"}]
                 if queries else [])
        rows = []
        for step, outcome in ((1, "盤面変化"), (2, "可視変化なし"), (3, "盤面変化")):
            matched = queries and step == 2
            projection = {"作用": {"番号": 1, "引数あり": False}, "作用前公開状態": {"色種類数": 2}}
            rows.append({
                "public_step_before": step, "public_step_after": step + 1, "actual_action_number": 1,
                "observed_public_outcome": outcome, "authorization": False, "endorsement": False,
                "projected_update_input": {**projection, "公開応答区分": outcome},
                "projected_query_input_at_matching_inspection": projection if matched else None,
                "matching_candidate_was_queried_before_action": bool(matched),
                "matching_inspection_id": 1 if matched else None,
                "query_tool_call_id": "python-1:call" if matched else None,
                "query_model_turn_id": "model-1" if matched else None,
                "action_tool_call_id": "python-2:call",
                "action_model_turn_id": "model-1" if same_response else "model-2",
                "native_status_at_query": "断定保留" if matched else None,
                "native_active_ref_forecast_values_at_query": ["可視変化なし"] if matched else None,
                "native_summary_truncated_at_query": False if matched else None,
                "update_bridge_status": "updated",
                "native_target_counts_at_query": {
                    "予測群": 1, "有効原理群": 1, "競合群": 0, "追加観測要求群": 0,
                    "係争中原理群": 1, "識別不能群": 1} if matched else None,
            })
        path = arm["root"] / f"artifacts/{gid}_p0_tool_runtime_state.visual-hds-query.json"
        write_json(path, {
            "schema": "arc3-python-hds-query-telemetry.v1", "visibility": visibility,
            "authorization": False, "endorsement": False, "native_judgment_modified": False,
            "native_scope": "whole_query_original_0.4.2", "counts": counts,
            "hds": hds, "prior": old["prior"], "last_error_type": None,
            "ordering_trace": trace, "public_response_rows": rows,
        })
        sidecars.append(path)
    write_json(arm["root"] / "benchmark.json", benchmark)
    change_json(arm["retrieval"], lambda d: d.update(
        kernel=metadata["id"], candidate_notebook_sha256=build["output_notebook_sha256"],
        candidate_metadata_sha256=build["kernel_metadata_sha256"]))
    refresh(arm)
    arm["sidecars"] = sidecars
    return arm


def evaluate(arm: dict, other: dict | None = None) -> dict:
    kwargs = {} if other is None else {
        "other_retrieval": other["retrieval"], "other_build": other["build"],
        "other_output_root": other["root"], "other_version": 1,
    }
    return scorer.evaluate(arm["retrieval"], arm["build"], arm["root"], 1, **kwargs)


def test_zero_query_is_valid_learning_connection_without_exposure(tmp_path):
    arm = fixture(tmp_path, "shown", queries=False)
    result = evaluate(arm)
    assert result["arm"]["gameplay_valid"] and result["arm"]["integration_valid"]
    assert result["arm"]["public_offline_RHAE_mean"] == 0
    hds = result["arm"]["HDS"]
    assert hds["operations"]["updates_succeeded"] == 9 and hds["operations"]["queries_succeeded"] == 0
    assert hds["exposure_classification"] == "NO_QUERY"
    assert hds["strict_past_prediction_measurement"]["forecast_precision"] is None
    assert not result["visibility_effect_proven"] and not result["learning_effect_proven"]


def test_single_shown_CLI_writes_only_new_aggregate_output(tmp_path):
    arm = fixture(tmp_path, "shown", queries=False)
    output = tmp_path / "new-scorecard.json"
    command = [sys.executable, str(Path(scorer.__file__)), "--retrieval", str(arm["retrieval"]),
               "--build", str(arm["build"]), "--output-root", str(arm["root"]),
               "--version", "1", "--output", str(output)]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    assert scorer.load(output)["arm"]["HDS"]["exposure_classification"] == "NO_QUERY"


def test_pair_preserves_native_HOLD_and_uses_identical_strict_past_covered_steps(tmp_path):
    masked = fixture(tmp_path, "masked")
    shown = fixture(tmp_path, "shown", completed=1)
    result = evaluate(shown, masked)  # launch order may be shown first
    assert result["paired"]["descriptive_mean_RHAE_delta_shown_minus_masked"] > 0
    hds = result["shown"]["HDS"]
    measurement = hds["strict_past_prediction_measurement"]
    assert measurement["same_covered_steps"] == 3
    assert measurement["same_covered_native_precision"] == 1
    assert measurement["same_covered_past_majority_precision"] == 0
    assert measurement["counts"]["nonreset_public_responses"] == 9
    assert hds["matched_candidate_ordering"]["matched_candidate_trace_joins"] == 3
    assert hds["native_target_count_sums_on_matched_responses"]["係争中原理群"] == 3
    assert hds["native_query_status_counts"] == {"断定保留": 3}
    assert hds["rendered_model_evidence_exposure"] == "UNKNOWN"
    assert not result["visibility_effect_proven"]
    assert "shadow does not alter" not in json.dumps(result).lower()
    assert not any(gid in json.dumps(result) for gid in ("public_a", "public_b", "public_c"))


def test_same_response_is_unreviewed_but_gameplay_remains_valid(tmp_path):
    result = evaluate(fixture(tmp_path, "shown", same_response=True))["arm"]
    assert result["gameplay_valid"] and result["integration_valid"]
    assert result["HDS"]["matched_candidate_ordering"]["SAME_RESPONSE_UNREVIEWED"] == 3
    assert not result["HDS"]["same_response_unreviewed_is_gameplay_failure"]


def test_unknown_or_clipped_forecasts_are_unmeasured_not_zero_accuracy(tmp_path):
    arm = fixture(tmp_path, "shown")
    change_json(arm["sidecars"][0], lambda d: d["public_response_rows"][1].update(native_summary_truncated_at_query=True))
    change_json(arm["sidecars"][1], lambda d: d["public_response_rows"][1].update(native_active_ref_forecast_values_at_query=None))
    refresh(arm)
    result = evaluate(arm)["arm"]
    assert result["gameplay_valid"] and result["integration_valid"]
    measurement = result["HDS"]["strict_past_prediction_measurement"]
    assert measurement["same_covered_steps"] == 1 and measurement["forecast_precision"] == 1


@pytest.mark.parametrize("failure", ["missing", "partial", "future_label", "wrong_receipt", "native_error"])
def test_integration_failure_keeps_gameplay_scores_and_is_not_no_exposure(tmp_path, failure):
    arm = fixture(tmp_path, "shown", completed=1)
    path = arm["sidecars"][0]
    if failure == "missing":
        path.unlink()
    elif failure == "partial":
        change_json(path, lambda d: d["public_response_rows"].pop(0))
    elif failure == "future_label":
        change_json(path, lambda d: d["public_response_rows"][1]["projected_query_input_at_matching_inspection"].update(公開応答区分="可視変化なし"))
    elif failure == "wrong_receipt":
        change_json(path, lambda d: d["ordering_trace"][0].update(inspection_id=99))
    else:
        change_json(path, lambda d: d["hds"].update(query_errors=1, last_error_type="RuntimeError"))
    refresh(arm)
    result = evaluate(arm)["arm"]
    assert result["gameplay_valid"] and result["public_offline_RHAE_mean"] > 0
    assert not result["integration_valid"]
    assert result["HDS"]["exposure_classification"] != "NO_QUERY"


@pytest.mark.parametrize("failure,match", [
    ("version", "wrong exact kernel version"),
    ("prompt", "source/prompt/native/budget mismatch"),
    ("initial", "initial fields differ"),
    ("model", "model configuration mismatch"),
])
def test_pair_and_exact_retrieval_contracts_reject_mismatches(tmp_path, failure, match):
    masked, shown = fixture(tmp_path, "masked"), fixture(tmp_path, "shown")
    if failure == "version":
        change_json(shown["retrieval"], lambda d: d.update(version=2))
    elif failure == "prompt":
        change_json(shown["build"], lambda d: d.update(shared_prompt_note="different instructions"))
    elif failure == "initial":
        change_json(next(shown["root"].glob("artifacts/*_events.jsonl")), lambda d: d.update(board=[[9, 9]]))
        refresh(shown)
    else:
        meta = shown["build"].parent / "kernel-metadata.json"
        change_json(meta, lambda d: d.update(docker_image="different/image"))
        digest = scorer.sha256(meta)
        change_json(shown["build"], lambda d: d.update(kernel_metadata_sha256=digest))
        change_json(shown["retrieval"], lambda d: d.update(candidate_metadata_sha256=digest))
    with pytest.raises(ValueError, match=match):
        evaluate(masked, shown)
