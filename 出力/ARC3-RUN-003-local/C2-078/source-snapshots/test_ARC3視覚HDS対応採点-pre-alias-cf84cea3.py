from __future__ import annotations

from datetime import datetime, timedelta, timezone
import json
from pathlib import Path
from statistics import mean
import subprocess
import sys

import pytest

from 検証 import ARC3視覚HDS対応採点 as scorecard


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False) + "\n", encoding="utf-8")


def refresh(arm: dict) -> None:
    doc = scorecard.load(arm["retrieval"])
    files = [
        {"path": p.relative_to(arm["root"]).as_posix(), "bytes": p.stat().st_size,
         "sha256": scorecard.sha256(p)}
        for p in sorted(arm["root"].rglob("*")) if p.is_file()
    ]
    doc.update(output_files=files, output_manifest_sha256=scorecard.output_manifest_digest(files))
    write_json(arm["retrieval"], doc)


def make_arm(tmp_path: Path, mode: str, *, completed: int = 0) -> dict:
    folder = tmp_path / mode
    output = folder / "exact-output-v1"
    output.mkdir(parents=True)
    common = {key: "a" * 64 for key in scorecard.COMMON_BUILD}
    common.update(shared_model_seed=0, pilot=scorecard.EXPECTED_PILOT.copy(),
                  budgets_per_game={"update_budget": 80, "query_budget": 80,
                                    "hds_seconds_budget": 120.0})
    write_json(folder / "submission.ipynb", {"test_fixture": True, "mode": mode})
    write_json(folder / "kernel-metadata.json", {
        "id": f"fixture/visual-{mode}", "title": mode, "is_private": True,
        "enable_internet": False, "enable_gpu": True,
    })
    (folder / "visual-hds-source.zip").write_bytes(b"synthetic source fixture")
    build = dict(common, schema="arc3-visual-hds-pilot-build.v1", mode=mode,
                 output_notebook_sha256=scorecard.sha256(folder / "submission.ipynb"),
                 kernel_metadata_sha256=scorecard.sha256(folder / "kernel-metadata.json"),
                 bundle_sha256=scorecard.sha256(folder / "visual-hds-source.zip"))
    write_json(folder / "build-manifest.json", build)
    runs = []
    for index, gid in enumerate(("public_a", "public_b", "public_c")):
        history = [{"action": {"id": 0 if i == 0 else 1}, "generated_tokens": 5,
                    "uncached_input_tokens": 8} for i in range(4)]
        run = {"game_id": gid, "number_of_levels": 2, "base_actions_per_level": [10, 10],
               "levels_completed": completed, "actions_per_level": [4, 0],
               "state": "gave_up", "history": history,
               "final_wallclock_seconds": (index + 1) * 20, "final_generated_tokens": 20}
        run["final_score"] = scorecard.helper().score_run(run)
        runs.append(run)
        first = {"board": [[0, 1]], "board_ascii": "01", "level": 1, "title": "public",
                 "run_status": "PLAYING", "score": 0, "state": "NOT_FINISHED",
                 "type": "initial", "reward": 0}
        write_json(output / f"artifacts/{gid}_p0_events.jsonl", first)
        counts = {"actual_action_calls_seen": 4}
        hds = prior = None
        if mode == "shadow":
            counts.update({"skipped_RESET_actions": 1, "public_responses_observed": 3,
                           "query_status:completed": 3, "query_native:断定保留": 3,
                           "update_status:completed": 3,
                           "supported_unique_predictions_observed": 3,
                           "supported_unique_prediction_matches": 2})
            hds = {key: 0 for key in scorecard.HDS_COUNTS}
            hds.update(updates_attempted=3, updates_succeeded=3, queries_attempted=3,
                       queries_succeeded=3, prior_updates_attempted=5, prior_updates_succeeded=5,
                       update_seconds=.02, query_seconds=.03, prior_load_seconds=.01,
                       total_hds_seconds=.06, update_budget=80, query_budget=80,
                       hds_seconds_budget=120, update_budget_exhausted=False,
                       query_budget_exhausted=False, time_budget_exhausted=False,
                       time_budget_can_overrun_one_inflight_call=True, last_error_type=None)
            prior = {"load_status": "loaded", "loaded_count": 5, "expected_count": 5,
                     "action_authorization": False}
        telemetry = {"schema": "arc3-visual-hds-shadow-telemetry.v1", "mode": mode,
                     "authorization": False, "continue_visual_solver": True,
                     "model_context_modified": False, "counts": counts,
                     "last_adapter_error": None, "hds": hds, "prior": prior}
        write_json(output / f"artifacts/{gid}_p0_tool_runtime_state.visual-hds.json", telemetry)
    write_json(output / "benchmark.json", {
        "n_passes": 1, "start_time": "2026-10-26T22:00:00+00:00",
        "end_time": "2026-10-26T22:01:00+00:00", "game_runs": runs,
    })
    retrieval = {"schema": "arc26-arc3-private-kernel-terminal-output.v1",
                 "kernel": f"fixture/visual-{mode}", "version": 1,
                 "status": "KernelWorkerStatus.COMPLETE", "terminal": True,
                 "output_exit_code": 0, "output_directory": str(output),
                 "candidate_notebook_sha256": build["output_notebook_sha256"],
                 "candidate_metadata_sha256": build["kernel_metadata_sha256"],
                 "retrieval_scope": "selected score/events/HDS files only"}
    arm = {"root": output, "build": folder / "build-manifest.json",
           "retrieval": folder / "terminal-retrieval.json"}
    write_json(arm["retrieval"], retrieval)
    refresh(arm)
    return arm


def evaluate(off: dict, shadow: dict | None = None) -> dict:
    kwargs = {} if shadow is None else {
        "shadow_retrieval": shadow["retrieval"], "shadow_build": shadow["build"],
        "shadow_output_root": shadow["root"], "shadow_version": 1,
    }
    return scorecard.evaluate(off["retrieval"], off["build"], off["root"], 1, **kwargs)


def change_json(path: Path, change) -> None:
    doc = scorecard.load(path)
    change(doc)
    write_json(path, doc)


def test_control_only_and_paired_scores_remain_descriptive(tmp_path):
    off = make_arm(tmp_path, "off")
    one = evaluate(off)
    assert one["inspection"] == "control_only" and one["control_valid_for_shadow"]
    assert one["off"]["HDS"]["off_zero_HDS_confirmed"]
    assert one["off"]["max_game_elapsed_seconds"] == 20  # cumulative clocks are not summed
    shadow = make_arm(tmp_path, "shadow", completed=1)
    result = evaluate(off, shadow)
    assert result["integration_valid"]
    assert result["paired"]["descriptive_mean_RHAE_delta_shadow_minus_off"] > 0
    assert result["shadow"]["HDS"]["operations"]["updates_succeeded"] == 9
    assert result["shadow"]["HDS"]["counters"]["supported_unique_prediction_matches"] == 6
    assert not result["causal_learning_or_score_improvement_proven"]
    exported = json.dumps(result)
    assert not any(gid in exported for gid in ("public_a", "public_b", "public_c"))
    assert "ACCEPT_LEARNING" not in exported and "19.309" not in exported


def test_standalone_shadow_allows_new_measurement_source_but_pair_does_not(tmp_path):
    off, shadow = make_arm(tmp_path, "off"), make_arm(tmp_path, "shadow")
    change_json(shadow["build"], lambda d: d.update(runtime_adapter_sha256="b" * 64))
    result = scorecard.evaluate_single(shadow["retrieval"], shadow["build"], shadow["root"], 1)
    assert result["inspection"] == "single_shadow" and result["integration_valid"]
    assert not result["paired_comparison_performed"] and "paired" not in result
    with pytest.raises(ValueError, match="source/configuration/budgets differ"):
        evaluate(off, shadow)


def test_standalone_CLI_runs_without_a_control_or_Kaggle(tmp_path):
    shadow = make_arm(tmp_path, "shadow")
    output = tmp_path / "aggregate.json"
    command = [sys.executable, str(Path(scorecard.__file__)),
               "--single-retrieval", str(shadow["retrieval"]),
               "--single-build", str(shadow["build"]),
               "--single-output-root", str(shadow["root"]),
               "--single-version", "1", "--output", str(output)]
    result = subprocess.run(command, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    report = scorecard.load(output)
    assert report["inspection"] == "single_shadow" and report["integration_valid"]


def test_GPU_metadata_is_required_even_with_matching_source_hashes(tmp_path):
    off = make_arm(tmp_path, "off")
    path = off["build"].parent / "kernel-metadata.json"
    change_json(path, lambda d: d.update(enable_gpu=False))
    digest = scorecard.sha256(path)
    change_json(off["build"], lambda d: d.update(kernel_metadata_sha256=digest))
    change_json(off["retrieval"], lambda d: d.update(candidate_metadata_sha256=digest))
    with pytest.raises(ValueError, match="private offline GPU"):
        evaluate(off)


@pytest.mark.parametrize("field,value,message", [
    ("version", 2, "wrong exact kernel version"),
    ("status", "KernelWorkerStatus.RUNNING", "not terminal COMPLETE"),
    ("terminal", False, "not terminal COMPLETE"),
    ("candidate_notebook_sha256", "0" * 64, "source hash differs"),
])
def test_rejects_wrong_version_nonterminal_and_source(tmp_path, field, value, message):
    off = make_arm(tmp_path, "off")
    change_json(off["retrieval"], lambda d: d.update({field: value}))
    with pytest.raises(ValueError, match=message):
        evaluate(off)


def test_rejects_unlisted_missing_and_changed_required_artifacts(tmp_path):
    off = make_arm(tmp_path, "off")
    sidecar = next(off["root"].glob("artifacts/*.visual-hds.json"))
    sidecar.unlink()
    refresh(off)
    with pytest.raises(ValueError, match="missing initial event/HDS sidecar"):
        evaluate(off)
    off = make_arm(tmp_path / "another", "off")
    (off["root"] / "benchmark.json").write_text("{}", encoding="utf-8")
    with pytest.raises(ValueError, match="hash/size mismatch"):
        evaluate(off)


def test_saved_score_and_actual_action_budget_are_checked(tmp_path):
    off = make_arm(tmp_path, "off")
    benchmark = off["root"] / "benchmark.json"
    change_json(benchmark, lambda d: d["game_runs"][0].update(final_score=99))
    refresh(off)
    with pytest.raises(ValueError, match="saved final_score mismatch"):
        evaluate(off)
    off = make_arm(tmp_path / "budget", "off")
    change_json(off["build"], lambda d: d["pilot"].update(actions_max=160))
    with pytest.raises(ValueError, match="pilot budget/model seed"):
        evaluate(off)
    off = make_arm(tmp_path / "actual_budget", "off")
    benchmark = scorecard.load(off["root"] / "benchmark.json")
    run = benchmark["game_runs"][0]
    run["history"] = [run["history"][0]] * 81
    run["actions_per_level"] = [81, 0]
    write_json(off["root"] / "benchmark.json", benchmark)
    refresh(off)
    with pytest.raises(ValueError, match="actual action budget/history mismatch"):
        evaluate(off)


def test_off_rejects_any_actual_HDS_work(tmp_path):
    off = make_arm(tmp_path, "off")
    path = next(off["root"].glob("artifacts/*.visual-hds.json"))
    change_json(path, lambda d: d["counts"].update({"query_status:completed": 1}))
    refresh(off)
    with pytest.raises(ValueError, match="off arm performed HDS work"):
        evaluate(off)


@pytest.mark.parametrize("kind", ["initial", "source", "HDS_budget"])
def test_paired_contract_mismatches_are_rejected(tmp_path, kind):
    off, shadow = make_arm(tmp_path, "off"), make_arm(tmp_path, "shadow")
    if kind == "initial":
        change_json(next(shadow["root"].glob("artifacts/*_events.jsonl")),
                    lambda d: d.update(board=[[9, 9]]))
    elif kind == "source":
        change_json(shadow["build"], lambda d: d.update(patched_solver_sha256="b" * 64))
    else:
        change_json(next(shadow["root"].glob("artifacts/*.visual-hds.json")),
                    lambda d: d["hds"].update(query_budget=79))
    refresh(shadow)
    with pytest.raises(ValueError, match="differ|mismatch"):
        evaluate(off, shadow)


def test_HDS_failure_is_reported_without_hiding_visual_score(tmp_path):
    off, shadow = make_arm(tmp_path, "off"), make_arm(tmp_path, "shadow", completed=1)
    change_json(next(shadow["root"].glob("artifacts/*.visual-hds.json")),
                lambda d: d["hds"].update(query_errors=1, queries_succeeded=2,
                                          last_error_type="RuntimeError"))
    refresh(shadow)
    result = evaluate(off, shadow)
    assert not result["integration_valid"]
    assert result["shadow"]["public_offline_RHAE_mean"] > 0
    assert result["shadow"]["HDS"]["HDS_error_count"] == 1
    assert result["shadow"]["HDS"]["error_type_counts"] == {"RuntimeError": 1}


def test_shadow_requires_actual_learning_updates(tmp_path):
    off, shadow = make_arm(tmp_path, "off"), make_arm(tmp_path, "shadow")
    for path in shadow["root"].glob("artifacts/*.visual-hds.json"):
        change_json(path, lambda d: d["hds"].update(updates_attempted=0, updates_succeeded=0))
    refresh(shadow)
    result = evaluate(off, shadow)
    assert not result["integration_valid"]
    assert result["shadow"]["HDS"]["games_with_prior_and_actual_query_update"] == 0


def test_native_HOLD_with_relevant_predictions_does_not_become_zero_accuracy(tmp_path):
    off, shadow = make_arm(tmp_path, "off"), make_arm(tmp_path, "shadow")
    for path in shadow["root"].glob("artifacts/*.visual-hds.json"):
        def hold_without_rendered_context(doc):
            counts = doc["counts"]
            counts.pop("supported_unique_predictions_observed")
            counts.pop("supported_unique_prediction_matches")
            counts["queries_with_relevant_predictions"] = 3
        change_json(path, hold_without_rendered_context)
    refresh(shadow)
    hds = evaluate(off, shadow)["shadow"]["HDS"]
    assert hds["integration_valid"] and hds["operations"]["updates_succeeded"] == 9
    assert hds["counters"]["queries_with_relevant_predictions"] == 9
    assert hds["counters"]["query_native:断定保留"] == 9
    assert hds["prediction_match_measurement"]["status"].startswith("UNMEASURED")
    assert hds["prediction_match_measurement"]["conditional_match_fraction"] is None


def test_R3_target_forecasts_are_separate_from_render_hint_and_global_HOLD(tmp_path):
    shadow = make_arm(tmp_path, "shadow")
    for path in shadow["root"].glob("artifacts/*.visual-hds.json"):
        def target_measurement(doc):
            doc["prediction_measurement_revision"] = "native-target-outcome-prequential.v1"
            counts = doc["counts"]
            counts.update(target_qualified_forecast_queries=2,
                          target_qualified_unique_predictions_observed=2,
                          target_qualified_unique_prediction_matches=1,
                          target_qualified_multiple_prediction_values=0)
            counts["target_qualified_unique_native_status:断定保留"] = 2
            counts["target_forecast_blocked:summary_truncated"] = 1
        change_json(path, target_measurement)
    refresh(shadow)
    result = scorecard.evaluate_single(shadow["retrieval"], shadow["build"], shadow["root"], 1)
    hds = result["arm"]["HDS"]
    target = hds["target_qualified_prediction_measurement"]
    assert target["unique_predictions_observed"] == 6 and target["matches"] == 3
    assert target["conditional_match_fraction"] == .5
    assert target["native_status_counts"] == {"断定保留": 6}
    assert target["blocked_reason_counts"] == {"summary_truncated": 3}
    assert hds["prediction_match_measurement"]["matches"] == 6
    assert not target["causal_learning_or_score_improvement_proven"]
    first_path = next(shadow["root"].glob("artifacts/*.visual-hds.json"))
    change_json(first_path, lambda d: d["counts"].update(target_qualified_unique_prediction_matches=3))
    refresh(shadow)
    with pytest.raises(ValueError, match="invalid target forecast count"):
        scorecard.evaluate_single(shadow["retrieval"], shadow["build"], shadow["root"], 1)


def test_runtime_overrun_and_missing_model_generation_invalidate_control(tmp_path):
    off = make_arm(tmp_path, "off")
    benchmark = scorecard.load(off["root"] / "benchmark.json")
    for index, run in enumerate(benchmark["game_runs"]):
        run["final_wallclock_seconds"] = 1206 + index * 20
        for row in run["history"]:
            row["generated_tokens"] = 0
    benchmark["end_time"] = (datetime(2026, 10, 26, 22, tzinfo=timezone.utc)
                             + timedelta(seconds=1246)).isoformat()
    write_json(off["root"] / "benchmark.json", benchmark)
    refresh(off)
    result = evaluate(off)
    assert not result["control_valid_for_shadow"]
    assert not result["off"]["visual_model_generation_observed"]
    assert not result["off"]["runtime_budget_compliant_with_5s_grace"]


def test_total_positive_tokens_do_not_hide_two_games_without_visual_generation(tmp_path):
    off = make_arm(tmp_path, "off")
    benchmark = scorecard.load(off["root"] / "benchmark.json")
    for run in benchmark["game_runs"][1:]:
        run["final_generated_tokens"] = 0
        for row in run["history"]:
            row["generated_tokens"] = 0
    write_json(off["root"] / "benchmark.json", benchmark)
    refresh(off)
    result = evaluate(off)
    arm = result["off"]
    assert arm["history_generated_tokens"] == 20 and arm["visual_model_generation_observed"]
    assert arm["games_with_visual_model_generation"] == 1
    assert arm["visual_generation_flags_in_benchmark_order_when_invalid"] == [True, False, False]
    assert not arm["all_games_visual_model_generation_observed"]
    assert not result["control_valid_for_shadow"]
    assert arm["public_offline_RHAE_mean"] == 0 and arm["saved_scores_match_recomputed"]


def test_reused_official_score_calculation_on_real_v28_fixture():
    path = scorecard.ROOT / "運用/証拠/ARC26-UNIFIED/ARC3-C2-059-v28-outputcheck/benchmark.json"
    runs = scorecard.load(path)["game_runs"]
    scores = [scorecard.helper().score_run(run) for run in runs]
    assert mean(scores) == pytest.approx(5.35178882805071)
    assert all(score == pytest.approx(run["final_score"], abs=1e-9)
               for score, run in zip(scores, runs))
