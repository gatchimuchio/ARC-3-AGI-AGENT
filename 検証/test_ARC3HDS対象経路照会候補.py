"""原本ではなく凍結ZIPのTEMPコピーに対するnative照会契約。"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

PATH = Path(__file__).resolve().parent / "候補/ARC3HDS対象経路照会候補.py"
SPEC = importlib.util.spec_from_file_location("native_scope_candidate", PATH)
candidate = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(candidate)


@pytest.fixture(scope="module")
def evidence():
    return candidate.preflight()


def test_explicit_none_and_omitted_scope_preserve_whole_native_output(evidence):
    assert evidence["whole_query_full_structure_matches_frozen_original"] is True
    old = evidence["original_whole_query_contract"]["cases"]
    new = evidence["candidate_contract"]["cases"]
    assert len(old) == len(new) == 11
    assert [r["whole"] for r in old] == [r["whole"] for r in new]
    assert evidence["candidate_contract"]["learned_memory_state_and_input_unchanged_by_queries"]
    assert evidence["candidate_contract"]["legacy_query_identifier_allocation_preserved"]
    assert evidence["candidate_contract"]["malformed_scopes_rejected"] == 7


def test_scoped_synthetic_forecast_retains_full_original_hold(evidence):
    rows = evidence["candidate_contract"]["cases"][:2]
    assert [r["whole"]["状態"] for r in rows] == ["断定保留", "断定保留"]
    assert [r["scoped"]["状態"] for r in rows] == ["出力", "出力"]
    predictions = [r["scoped"]["内容"]["予測群"] for r in rows]
    assert [[p["予測値"] for p in group] for group in predictions] == [
        ["盤面変化"],
        ["可視変化なし"],
    ]
    for row in rows:
        assert row["whole"]["内容"]["係争中原理群"]
        assert row["whole"]["内容"]["識別不能群"]
        assert row["scoped"]["追跡情報"]["照会結果経路群"] == [["公開応答区分"]]


def test_missing_or_contested_target_evidence_remains_native_hold(evidence):
    rows = evidence["candidate_contract"]["cases"][2:]
    assert all(r["scoped"]["状態"] == "断定保留" for r in rows)
    keyed = {r["name"]: r["scoped"]["内容"] for r in rows}
    assert keyed["relevant_target_isolation"]["係争中原理群"]
    assert keyed["relevant_target_conflict"]["競合群"]
    assert keyed["relevant_target_identifiability"]["識別不能群"]
    for name in (
        "no_observations",
        "unlearned_boundary",
        "one_requested_target_has_no_rule",
        "already_observed_label_is_not_a_forecast",
        "missing_condition",
        "unseen_condition_values",
    ):
        assert keyed[name]["追加観測要求群"]


def test_only_pinned_native_temp_preimages_are_modified(evidence):
    assert evidence["canonical_native_sources_unchanged"] is True
    assert evidence["patch_applied_only_to_temporary_copy"] is True
    assert evidence["bridge_builder_R3_artifacts_modified"] is False
    assert evidence["game_model_GPU_Kaggle_called"] is False
    hashes = evidence["native_source_pre_post"]
    assert {Path(r["path"]).name for r in hashes} == {"系統.py", "実行系.py"}
    assert all(row["pre_sha256"] != row["post_sha256"] for row in hashes)


def test_refuses_bundle_drift_before_candidate_execution(tmp_path, monkeypatch):
    bundle = tmp_path / "drifted.zip"
    bundle.write_bytes(b"drifted")
    monkeypatch.setattr(candidate, "BUNDLE", bundle)
    with pytest.raises(ValueError, match="drifted"):
        candidate.preflight()
