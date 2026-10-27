from __future__ import annotations

from copy import deepcopy
from pathlib import Path
import shutil
import subprocess
import sys

import pytest

from 検証 import ARC3視覚HDS学習比較採点 as scorer
from 検証.test_ARC3視覚HDS照会対応採点 import fixture as query_fixture
from 検証.test_ARC3視覚HDS対応採点 import change_json, refresh, write_json


def fixture(tmp: Path, mode: str, *, queries=True, same_response=False, completed=0, revision="r2") -> dict:
    arm = query_fixture(tmp / mode, "shown", queries=queries, same_response=same_response, completed=completed)
    source = scorer.ROOT / ("出力/ARC3-RUN-003-local/C2-087/" +
                            ("prior-only" if mode == "disabled" else "online-learning") +
                            ("-r2" if revision == "r2" else ""))
    for filename in ("submission.ipynb", "kernel-metadata.json", "visual-hds-source.zip", "build-manifest.json"):
        shutil.copyfile(source / filename, arm["build"].parent / filename)
    for path in arm["sidecars"]:
        def modify(d):
            status = "updated" if mode == "enabled" else scorer.DISABLED
            d["schema"] = "arc3-python-hds-learning-ablation-telemetry.v1"
            d["counts"].pop("update_status:updated")
            d["counts"].update({"update_status:" + status: 3, "game_response_teacher_inputs_computed": 3})
            d["counts"]["game_response_update_enabled_requests" if mode == "enabled"
                        else "game_response_update_expected_disabled"] = 3
            d["hds"].update(updates_attempted=3 if mode == "enabled" else 0,
                            updates_succeeded=3 if mode == "enabled" else 0)
            for row in d["public_response_rows"]:
                row.update(update_bridge_status=status, native_game_response_learning_enabled=mode == "enabled",
                           native_game_update_skip_is_expected=mode == "disabled")
            d["learning_ablation"] = {
                "revision": "native-game-response-learning-only.v1", "configuration_flag": scorer.FLAG,
                "frozen_mode": mode, "configuration_unchanged": True,
                "game_response_native_updates_enabled": mode == "enabled",
                "disabled_skips_are_expected_not_errors": mode == "disabled",
                "expected_disabled_skip_status": scorer.DISABLED, "prior_records_expected": 5,
                "prior_native_updates_attempted": 5, "prior_native_updates_succeeded": 5,
            }
        change_json(path, modify)
    b = scorer.load(arm["build"])
    m = scorer.load(arm["build"].parent / "kernel-metadata.json")
    change_json(arm["retrieval"], lambda d: d.update(kernel=m["id"], candidate_notebook_sha256=b["output_notebook_sha256"],
                                                   candidate_metadata_sha256=b["kernel_metadata_sha256"]))
    refresh(arm)
    return arm


def evaluate(arm, other=None):
    kw = {} if other is None else dict(other_retrieval=other["retrieval"], other_build=other["build"],
                                      other_output_root=other["root"], other_version=1)
    return scorer.evaluate(arm["retrieval"], arm["build"], arm["root"], 1, **kw)


@pytest.mark.parametrize("revision", ["r1", "r2"])
def test_prior_only_zero_native_updates_valid_and_separate_from_prior5(tmp_path, revision):
    result = evaluate(fixture(tmp_path, "disabled", queries=False, revision=revision))
    arm, hds = result["arm"], result["arm"]["HDS"]
    assert arm["gameplay_valid"] and arm["integration_valid"] and arm["public_offline_RHAE_mean"] == 0
    assert hds["operations"]["updates_attempted"] == hds["operations"]["updates_succeeded"] == 0
    assert hds["operations"]["prior_updates_succeeded"] == 15
    assert hds["game_response_update_evidence"] == {
        "nonRESET_callbacks": 9, "computed_game_teachers": 9, "expected_disabled_skips": 9, "native_budget_skips": 0}
    assert hds["exposure_classification"] == "NO_QUERY"
    assert arm["runtime_software_and_seed"]["actual_versions"] is None
    assert result["learning_benefit"] == "UNPROVEN" and not result["learning_effect_proven"]


def test_pair_only_update_flag_descriptive_positive_score_not_learning_proof(tmp_path):
    prior = fixture(tmp_path, "disabled", same_response=True)
    online = fixture(tmp_path, "enabled", same_response=True, completed=1)
    d = evaluate(online, prior)
    assert d["paired"]["both_gameplay_valid"] and d["paired"]["both_integration_valid"]
    assert d["paired"]["descriptive_mean_RHAE_delta_online_minus_prior"] > 0
    assert d["paired"]["runtime_software_seed_match"] is None
    assert d["online_learning"]["HDS"]["operations"]["updates_succeeded"] == 9
    assert d["prior_only"]["HDS"]["operations"]["updates_succeeded"] == 0
    for arm in (d["online_learning"], d["prior_only"]):
        assert arm["HDS"]["matched_candidate_ordering"]["SAME_RESPONSE_UNREVIEWED"] == 3
        assert arm["HDS"]["rendered_model_evidence_exposure"] == "UNKNOWN"
        assert not arm["HDS"]["comprehension_or_adoption_proven"]
    assert not d["learning_effect_proven"]


@pytest.mark.parametrize("mode", ["disabled", "enabled"])
def test_unexpected_native_ingestion_or_missing_online_ingestion_preserves_scores(tmp_path, mode):
    arm = fixture(tmp_path, mode, completed=1)
    change_json(arm["sidecars"][0], lambda d: d["hds"].update(
        updates_attempted=1 if mode == "disabled" else 0, updates_succeeded=1 if mode == "disabled" else 0))
    refresh(arm)
    d = evaluate(arm)["arm"]
    assert d["gameplay_valid"] and d["public_offline_RHAE_mean"] > 0 and not d["integration_valid"]
    assert d["HDS"]["integration_failures"]


def test_expected_disabled_skip_does_not_hide_real_query_failure(tmp_path):
    arm = fixture(tmp_path, "disabled", queries=False)
    def fail_query(d):
        d["counts"].update(query_helper_calls=1)
        d["hds"].update(queries_attempted=1, query_errors=1, last_error_type="RuntimeError")
    change_json(arm["sidecars"][0], fail_query)
    refresh(arm)
    d = evaluate(arm)["arm"]
    assert d["gameplay_valid"] and not d["integration_valid"]
    assert d["HDS"]["operations"]["updates_succeeded"] == 0
    assert d["HDS"]["game_response_update_evidence"]["expected_disabled_skips"] == 9
    assert d["HDS"]["errors"]["query_errors"] == 1
    assert d["HDS"]["exposure_classification"] == "UNKNOWN_INTEGRATION_FAILURE"


@pytest.mark.parametrize("honest", [True, False])
def test_online_partial_budget_is_distinct_from_disabled_and_real_failure(tmp_path, honest):
    arm = fixture(tmp_path, "enabled")
    def partial(d):
        d["public_response_rows"][-1]["update_bridge_status"] = "budget_exhausted"
        d["counts"].update({"update_status:updated": 2, "update_status:budget_exhausted": 1})
        d["hds"].update(updates_attempted=2, updates_succeeded=2, budget_exhaustion_requests=1,
                        time_budget_exhausted=honest, total_hds_seconds=120.01 if honest else .06,
                        update_seconds=119.97 if honest else .02)
    for path in arm["sidecars"]:
        change_json(path, partial)
    refresh(arm)
    d = evaluate(arm)["arm"]
    assert d["gameplay_valid"] and d["integration_valid"] is honest
    assert d["HDS"]["operations"]["updates_succeeded"] == 6
    if honest:
        assert d["HDS"]["game_response_update_evidence"]["native_budget_skips"] == 3
        assert d["HDS"]["game_response_update_evidence"]["expected_disabled_skips"] == 0


@pytest.mark.parametrize("kind", ["metadata", "notebook", "observer_claim"])
def test_pair_rejects_unrelated_configuration_source_or_observer_drift(tmp_path, kind):
    prior, online = fixture(tmp_path, "disabled"), fixture(tmp_path, "enabled")
    if kind == "metadata":
        path = online["build"].parent / "kernel-metadata.json"
        change_json(path, lambda d: d.update(accelerator="unrelated-config"))
        change_json(online["build"], lambda d: d.update(kernel_metadata_sha256=scorer.sha256(path)))
        change_json(online["retrieval"], lambda d: d.update(candidate_metadata_sha256=scorer.sha256(path)))
    elif kind == "notebook":
        path = online["build"].parent / "submission.ipynb"
        change_json(path, lambda d: d["cells"][11].update(source=["# unrelated changed source\n"]))
        change_json(online["build"], lambda d: d.update(output_notebook_sha256=scorer.sha256(path)))
        change_json(online["retrieval"], lambda d: d.update(candidate_notebook_sha256=scorer.sha256(path)))
    else:
        change_json(online["build"], lambda d: d.update(observer_projection_revision="wrong-observer"))
    with pytest.raises(ValueError, match="paired source"):
        evaluate(prior, online)


@pytest.mark.parametrize("kind", ["version", "nonterminal", "source_hash"])
def test_exact_output_and_source_contracts_are_not_relaxed(tmp_path, kind):
    arm = fixture(tmp_path, "disabled")
    if kind == "version":
        change_json(arm["retrieval"], lambda d: d.update(version=2))
    elif kind == "nonterminal":
        change_json(arm["retrieval"], lambda d: d.update(terminal=False))
    else:
        with (arm["build"].parent / "submission.ipynb").open("a", encoding="utf8") as f:
            f.write("\n")
    with pytest.raises(ValueError):
        evaluate(arm)


def stamp(arm, version="9.99-fixture", partial=False):
    write_json(arm["root"] / "arc3-runtime-software.json", {
        "schema": "arc3-runtime-software.v1", "python": {"version": "3.fixture", "implementation": "CPython"},
        "packages": {"arc-agi": None if partial else version, "arcengine": "8.88-fixture"},
        "public_Arcade_make_signature": "(game_id, *, seed=0)",
        "environment_seed": {"declared_offline_seed": 0, "explicit_keyword_scope": "OFFLINE private pilot only",
                             "competition_rerun_allowed": False},
        "observation_errors": {"arc-agi": "FixtureMissing"} if partial else {},
    })
    refresh(arm)


def test_actual_runtime_versions_are_observed_not_guessed_or_fixed_value_gate(tmp_path):
    prior, online = fixture(tmp_path, "disabled"), fixture(tmp_path, "enabled")
    stamp(prior)
    stamp(online)
    result = evaluate(prior, online)
    assert result["paired"]["runtime_software_seed_match"] is True
    assert result["prior_only"]["runtime_software_and_seed"]["actual_versions"]["arc-agi"] == "9.99-fixture"
    stamp(online, version="different-fixture")
    with pytest.raises(ValueError, match="runtime software/seed differs"):
        evaluate(prior, online)


def test_partial_runtime_stamp_stays_unknown_not_assumed_equal_actual_versions(tmp_path):
    prior, online = fixture(tmp_path, "disabled"), fixture(tmp_path, "enabled")
    stamp(prior, partial=True)
    stamp(online, partial=True)
    d = evaluate(prior, online)
    assert d["paired"]["runtime_software_seed_match"] is None
    assert d["prior_only"]["runtime_software_and_seed"]["status"] == "OBSERVED_PARTIAL"


@pytest.mark.parametrize("case", ["past", "first", "clipped"])
def test_Action6_after_only_target_join_and_strict_past_majority_reuse(tmp_path, case):
    arm = fixture(tmp_path, "enabled")
    benchmark = scorer.load(arm["root"] / "benchmark.json")
    for run in benchmark["game_runs"]:
        run["history"][2]["action"]["id"] = "ACTION6"
        if case != "first":
            run["history"][1]["action"]["id"] = "ACTION6"
    write_json(arm["root"] / "benchmark.json", benchmark)
    def add_locality(d):
        for index, outcome in ((0, "局所あり・局所以外なし"), (1, "局所なし・局所以外なし")):
            if index == 0 and case == "first":
                continue
            row = d["public_response_rows"][index]
            row.update(actual_action_number=6, observed_Action6_effect_class=outcome,
                       PRE_target_samecolor4CC_pixel_area=2)
            row["projected_update_input"][scorer.TARGET] = outcome
            row["projected_update_input"]["作用前公開状態"][scorer.AREA] = 2
            row["projected_update_input"]["作用"]["番号"] = 6
            if index == 1:
                row["projected_query_input_at_matching_inspection"] = {
                    k: deepcopy(v) for k, v in row["projected_update_input"].items() if k not in {scorer.TARGET, "公開応答区分"}}
                row.update(native_linked_Action6_effect_forecast_values_at_query=[outcome],
                           native_Action6_summary_truncated_at_query=case == "clipped")
    for path in arm["sidecars"]:
        change_json(path, add_locality)
    refresh(arm)
    d = evaluate(arm)["arm"]
    assert d["integration_valid"]
    m = d["HDS"]["Action6_effect_prediction_measurement"]
    if case == "past":
        assert m["same_covered_steps"] == 3 and m["same_covered_native_precision"] == 1
        assert m["same_covered_past_majority_precision"] == 0
    else:
        assert m["same_covered_steps"] == 0 and m["same_covered_past_majority_precision"] is None
        assert m["forecast_precision"] == (None if case == "clipped" else 1)
    assert m["native_guard_qualification"] == "UNKNOWN_NOT_INFERRED_FROM_ACTIVE_REF_LINKS"


def test_cli_single_prior_only_writes_new_aggregate_and_refuses_overwrite(tmp_path):
    arm = fixture(tmp_path, "disabled", queries=False)
    output = tmp_path / "new-scorecard.json"
    command = [sys.executable, str(Path(scorer.__file__)), "--retrieval", str(arm["retrieval"]),
               "--build", str(arm["build"]), "--output-root", str(arm["root"]), "--version", "1", "--output", str(output)]
    done = subprocess.run(command, capture_output=True, text=True, check=False)
    assert done.returncode == 0, done.stderr
    assert scorer.load(output)["arm"]["integration_valid"]
    again = subprocess.run(command, capture_output=True, text=True, check=False)
    assert again.returncode != 0
