from __future__ import annotations

from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = load(ROOT / "検証/ARC3native学習差分候補構築.py", "learning_ablation_builder")
oldtests = load(ROOT / "検証/test_ARC3局所応答observer候補.py", "frozen_observer_test_helpers")


def runtime(monkeypatch, mode):
    observer_builder = builder.load_builder(mode)
    previous, _ = observer_builder.load_builder()
    r3 = previous.base_builder()
    modules = (
        ("arc3_visual_hds_base", r3.RUNTIME_SOURCE),
        ("arc3_python_hds_query_base", oldtests.builder.FROZEN_RUNTIME.read_text(encoding="utf-8")),
        ("arc3_action6_locality_observer", oldtests.builder.OBSERVER.read_text(encoding="utf-8")),
    )
    for name, source in modules:
        module = ModuleType(name)
        monkeypatch.setitem(sys.modules, name, module)
        exec(compile(source, name, "exec"), module.__dict__)
    result = ModuleType("learning_ablation_runtime")
    exec(
        compile(builder.RUNTIME.read_bytes(), "learning-ablation-runtime", "exec"), result.__dict__
    )
    for key, value in {
        "ARC3_VISUAL_HDS_MODE": "shadow",
        "ARC3_HDS_EVIDENCE_VISIBILITY": "shown",
        "ARC3_VISUAL_HDS_UPDATE_BUDGET": "80",
        "ARC3_VISUAL_HDS_QUERY_BUDGET": "80",
        "ARC3_VISUAL_HDS_SECONDS_BUDGET": "120",
        builder.FLAG: mode,
    }.items():
        monkeypatch.setenv(key, value)
    return result


def knowledge(bridge):
    engine = bridge._hds.エンジン
    return deepcopy((engine.台帳.全取得(), engine.状態.履歴(), engine._原理履歴))


@pytest.mark.parametrize("mode", ["disabled", "enabled"])
def test_prior5_separate_four_teachers_computed_only_enabled_native_ingestion(
    monkeypatch, tmp_path, mode
):
    rt = runtime(monkeypatch, mode)
    session = oldtests.helpers.Session(tmp_path / (mode + ".json"))
    session.game.current_state = oldtests.state(((1, 0), (0, 0)))
    state = rt._base._state(session)
    bridge = rt._bridge(state)
    frozen = knowledge(bridge)
    native_teachers = []
    native_queries = []
    original_update, original_query = bridge._hds.処理する, bridge._hds.照会する

    def update(value):
        native_teachers.append(deepcopy(value.内容))
        return original_update(value)

    def query(value):
        native_queries.append(deepcopy(value.内容))
        return original_query(value)

    bridge._hds.処理する, bridge._hds.照会する = update, query
    for step in range(4):
        q = rt.query_candidate(
            session,
            {
                "candidate": {"action": "MOUSE", "row": 0, "col": 0},
                "expected_step": session.action_count,
                "tool_call_id": f"query-{step}",
                "model_turn_id": f"model-{2 * step}",
            },
        )
        assert q["visibility"] == "shown" and q["authorization"] is q["endorsement"] is False
        after = oldtests.state(((step % 2, 0), (0, 0)))
        oldtests.click_runtime(rt, session, after)
        if mode == "disabled":
            assert knowledge(bridge) == frozen
            assert not q["evidence"]["target_records"]["予測群"]
            assert not q["evidence"]["Action6_locality_evidence"]["target_records"]["予測群"]
    expected = 4 if mode == "enabled" else 0
    assert len(native_teachers) == bridge.stats["updates_succeeded"] == expected
    assert bridge.stats["prior_updates_succeeded"] == bridge.prior_report["loaded_count"] == 5
    assert bridge.stats["queries_attempted"] == len(native_queries) == 4
    assert bridge._hds.エンジン.台帳.件数("観測台帳") == 5 + expected
    assert state["counts"]["game_response_teacher_inputs_computed"] == 4
    assert len(state["public_response_rows"]) == 4
    for row in state["public_response_rows"]:
        assert oldtests.observer.TARGET in row["projected_update_input"]
        assert row["projected_update_input"]["公開応答区分"] == "盤面変化"
        assert row["update_bridge_status"] == (
            "updated" if mode == "enabled" else "game_response_update_disabled"
        )
    assert all(
        "公開応答区分" not in row and oldtests.observer.TARGET not in row for row in native_queries
    )
    if mode == "disabled":
        assert state["counts"]["game_response_update_expected_disabled"] == 4
        assert bridge.stats["update_budget_exhausted"] is False
        assert not bridge.stats["update_errors"]
    payload = json.loads(
        session.state_path.with_suffix(".visual-hds-query.json").read_text(encoding="utf-8")
    )
    config = payload["learning_ablation"]
    assert config["frozen_mode"] == mode and config["configuration_unchanged"] is True
    assert config["prior_native_updates_succeeded"] == 5
    assert config["game_response_native_updates_enabled"] is (mode == "enabled")
    assert all(
        r["native_game_update_skip_is_expected"] is (mode == "disabled")
        for r in payload["public_response_rows"]
    )


@pytest.mark.parametrize("mode", ["disabled", "enabled"])
def test_query_budget_failure_does_not_stop_actual_legal_action_or_fake_update_status(
    monkeypatch, tmp_path, mode
):
    rt = runtime(monkeypatch, mode)
    monkeypatch.setenv("ARC3_VISUAL_HDS_QUERY_BUDGET", "0")
    session = oldtests.helpers.Session(tmp_path / "budget.json")
    result = rt.query_candidate(
        session, {"candidate": {"action": "MOUSE", "row": 0, "col": 0}, "expected_step": 0}
    )
    assert result["status"] == "budget_exhausted"
    state = oldtests.click_runtime(rt, session, oldtests.state(((1, 1), (1, 0))))
    assert session.action_count == 1
    assert state["bridge"].stats["updates_attempted"] == (mode == "enabled")
    assert state["public_response_rows"][-1]["update_bridge_status"] == (
        "updated" if mode == "enabled" else "game_response_update_disabled"
    )
    assert state["bridge"].stats["update_budget_exhausted"] is False


def test_configuration_drift_does_not_silently_enable_frozen_native_learning(monkeypatch, tmp_path):
    rt = runtime(monkeypatch, "disabled")
    session = oldtests.helpers.Session(tmp_path / "drift.json")
    first = rt.query_candidate(session, {"candidate": "UP", "expected_step": 0})
    assert first["status"] == "queried"
    bridge = rt._base._state(session)["bridge"]
    before = knowledge(bridge)
    monkeypatch.setenv(builder.FLAG, "enabled")
    result = rt.query_candidate(session, {"candidate": "DOWN", "expected_step": 0})
    assert result["status"] == "query_unavailable"
    assert knowledge(bridge) == before and bridge.stats["updates_attempted"] == 0
    payload = json.loads(
        session.state_path.with_suffix(".visual-hds-query.json").read_text(encoding="utf-8")
    )
    assert payload["learning_ablation"]["configuration_unchanged"] is False
    assert payload["learning_ablation"]["frozen_mode"] == "disabled"


@pytest.mark.parametrize("mode", ["disabled", "enabled"])
def test_generated_shown_arm_cell_preserves_prefix_and_explicit_learning_mode(mode):
    observer_builder = builder.load_builder(mode)
    previous, _ = observer_builder.load_builder()
    base = previous.base_builder()
    previous.configure(base, "shown")
    records = json.loads(base.SOURCE_MANIFEST.read_text(encoding="utf-8"))[
        "patched_source_manifest"
    ]
    sources = {r["path"]: base._guarded(base.SOURCE_ROOT / r["path"], r["sha256"]) for r in records}
    payload, _ = base._bundle()
    assert base._cpu_bundle_import(payload)["bundle_import"] is True
    cell = base._patch_cell(
        payload,
        records,
        "shadow",
        {"update_budget": 80, "query_budget": 80, "hds_seconds_budget": 120.0},
    )
    assert f"os.environ[{builder.FLAG!r}] = {mode!r}" in cell
    result = base._cpu_patch_cell(cell, sources, base._patch_solver(sources[base.SOLVER_REL]))
    assert result["game_response_learning_mode"] == mode
    assert result["evidence_visibility"] == "shown"
    assert result["native_HDS_patched"] is False
