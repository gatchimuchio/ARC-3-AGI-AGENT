from __future__ import annotations

import ast
from collections import defaultdict
from copy import deepcopy
import importlib.util
import json
from pathlib import Path
import random
import sys
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


builder = load(ROOT / "検証/ARC3局所応答observer候補構築.py", "observer_builder")
observer = builder.observer_module()
helpers = load(ROOT / "検証/test_ARC3視覚HDS照会候補.py", "frozen_query_test_helpers")


def pure_source_function(path, name, namespace):
    tree = ast.parse(path.read_text(encoding="utf-8"))
    node = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == name)
    exec(compile(ast.Module(body=[node], type_ignores=[]), str(path), "exec"), namespace)
    return namespace[name]


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def test_area_and_effect_equal_reviewed_pure_oracles_without_loader_imports():
    components = pure_source_function(
        ROOT / observer.PROVENANCE["components_source"], "_components", {"defaultdict": defaultdict}
    )
    namespace = {
        "geometry": SimpleNamespace(_components=components),
        "replay": SimpleNamespace(
            base=SimpleNamespace(_require=require, ContractError=AssertionError)
        ),
    }
    area = pure_source_function(ROOT / observer.PROVENANCE["area_source"], "_area", namespace)
    effect = pure_source_function(
        ROOT / observer.PROVENANCE["effect_source"],
        "_effect",
        {"replay": namespace["replay"], "EFFECT_BY_FLAGS": observer.EFFECT_BY_FLAGS},
    )
    rng = random.Random(20261027)
    for height, width in ((2, 2), (7, 9), (9, 7), (9, 9)):
        for _ in range(8):
            board = tuple(tuple(rng.randrange(3) for _ in range(width)) for _ in range(height))
            other = tuple(tuple(rng.randrange(3) for _ in range(width)) for _ in range(height))
            before, after = SimpleNamespace(board=board), SimpleNamespace(board=other)
            action = SimpleNamespace(number=6, x=rng.randrange(width), y=rng.randrange(height))
            assert observer.component_area(before, action) == area(before, action)
            assert observer.effect_class(before, action, after) == effect(before, action, after)
    diagonal = SimpleNamespace(board=((1, 0), (0, 1)))
    assert observer.component_area(diagonal, SimpleNamespace(number=6, x=0, y=0)) == 1


@pytest.mark.parametrize(
    "local,remote", [(False, False), (False, True), (True, False), (True, True)]
)
def test_fixed7x7_flags_and_remote_only_are_geometric_not_noop(local, remote):
    board = tuple(tuple(0 for _ in range(9)) for _ in range(9))
    changed = [list(row) for row in board]
    if local:
        changed[3][3] = 1
    if remote:
        changed[4][4] = 1
    before, after = SimpleNamespace(board=board), SimpleNamespace(board=tuple(map(tuple, changed)))
    action = SimpleNamespace(number=6, x=0, y=0)
    assert observer.effect_class(before, action, after) == observer.EFFECT_BY_FLAGS[(local, remote)]


@pytest.fixture
def runtime(monkeypatch):
    previous, _ = builder.load_builder()
    r3 = previous.base_builder()
    modules = (
        ("arc3_visual_hds_base", r3.RUNTIME_SOURCE),
        ("arc3_python_hds_query_base", builder.FROZEN_RUNTIME.read_text(encoding="utf-8")),
        ("arc3_action6_locality_observer", builder.OBSERVER.read_text(encoding="utf-8")),
    )
    for name, source in modules:
        module = ModuleType(name)
        monkeypatch.setitem(sys.modules, name, module)
        exec(compile(source, name, "exec"), module.__dict__)
    result = ModuleType("observer_runtime")
    exec(compile(builder.RUNTIME.read_bytes(), "observer-runtime", "exec"), result.__dict__)
    for key, value in {
        "ARC3_VISUAL_HDS_MODE": "shadow",
        "ARC3_HDS_EVIDENCE_VISIBILITY": "shown",
        "ARC3_VISUAL_HDS_UPDATE_BUDGET": "80",
        "ARC3_VISUAL_HDS_QUERY_BUDGET": "80",
        "ARC3_VISUAL_HDS_SECONDS_BUDGET": "120",
    }.items():
        monkeypatch.setenv(key, value)
    return result


def state(board, status="NOT_FINISHED", completed=0):
    return helpers.public_state(board=board, state=status, completed=completed)


def click_runtime(runtime, session, after, *, x=0, y=0):
    action = SimpleNamespace(id=SimpleNamespace(name="ACTION6"), data={"x": x, "y": y})
    runtime.record_action_call(session, {"tool_call_id": "action-2", "model_turn_id": "model-2"})
    captured = runtime.before_action(
        session, action, public_grid=session.game.current_state.frame.data
    )
    session.action_count += 1
    session.game.current_state = after
    runtime.after_action(session, action, captured, after, public_grid=after.frame.data)
    return runtime._base._state(session)


def test_actual_query_teacher_pre_area_equal_no_future_leak_original_native_hold(runtime, tmp_path):
    session = helpers.Session(tmp_path / "state.json")
    before = ((1, 0), (0, 0))
    session.game.current_state = state(before)
    bridge = runtime._bridge(runtime._base._state(session))
    query_inputs, teachers = [], []
    original_query, original_update = bridge._hds.照会する, bridge._hds.処理する

    def capture_query(value):
        query_inputs.append(deepcopy(value.内容))
        return original_query(value)

    def capture_teacher(value):
        teachers.append(deepcopy(value.内容))
        return original_update(value)

    bridge._hds.照会する, bridge._hds.処理する = capture_query, capture_teacher
    result = runtime.query_candidate(
        session,
        {
            "candidate": {"action": "MOUSE", "row": 0, "col": 0},
            "expected_step": 0,
            "tool_call_id": "query-1",
            "model_turn_id": "model-1",
        },
    )
    assert result["evidence"]["native_status"] == "断定保留"
    assert result["evidence"]["Action6_locality_evidence"]["native_status"] == "断定保留"
    assert result["authorization"] is result["endorsement"] is False
    assert len(query_inputs) == 1 and not teachers
    assert query_inputs[0]["作用前公開状態"][observer.AREA] == 1
    assert query_inputs[0]["作用前公開状態"]["作用可能数"] == 3  # FULL, not reduced offline schema.
    assert observer.TARGET not in query_inputs[0] and "公開応答区分" not in query_inputs[0]
    result = click_runtime(runtime, session, state(((0, 0), (0, 0))))
    assert len(teachers) == 1 and teachers[0]["作用前公開状態"][observer.AREA] == 1
    assert teachers[0][observer.TARGET] == observer.EFFECT_BY_FLAGS[(True, False)]
    assert teachers[0]["公開応答区分"] == "盤面変化"
    assert (
        observer.component_area(
            SimpleNamespace(board=((0, 0), (0, 0))), SimpleNamespace(number=6, x=0, y=0)
        )
        == 4
    )
    assert (
        result["bridge"].stats["queries_attempted"]
        == result["bridge"].stats["updates_attempted"]
        == 1
    )
    row = result["public_response_rows"][-1]
    assert row["projected_update_input"] == teachers[0]
    assert row["projected_query_input_at_matching_inspection"] == query_inputs[0]


def test_nonAction6_omits_new_fields_and_keeps_original_public_encoder(runtime, tmp_path):
    session = helpers.Session(tmp_path / "other.json")
    api = runtime._original_api()
    before = api.PublicFrame(((0, 1), (1, 0)), "NOT_FINISHED", 0, (1, 2, 6))
    action = api.PublicAction(1)
    assert observer.query_content(api, before, action) == api._query_content(before, action)
    query = runtime.query_candidate(
        session, {"candidate": "UP", "expected_step": 0, "tool_call_id": "q"}
    )
    assert "Action6_locality_evidence" not in query["evidence"]
    outcome = helpers.act(runtime._base, session)
    row = outcome["public_response_rows"][-1]
    assert observer.AREA not in row["projected_update_input"]["作用前公開状態"]
    assert observer.TARGET not in row["projected_update_input"]


@pytest.mark.parametrize(
    "status,completed,outcome",
    [("NOT_FINISHED", 1, "レベル進行"), ("WIN", 1, "勝利"), ("GAME_OVER", 0, "GAME_OVER")],
)
def test_original_public_outcome_precedence_preserved(
    runtime, tmp_path, status, completed, outcome
):
    session = helpers.Session(tmp_path / "lifecycle.json")
    result = click_runtime(runtime, session, state(((0, 1), (1, 1)), status, completed))
    content = result["bridge"]._hds.エンジン.台帳.取得("観測台帳")[-1].原入力
    assert content["公開応答区分"] == outcome
    assert content[observer.TARGET] == observer.EFFECT_BY_FLAGS[(True, False)]


def test_shape_mismatch_and_reset_do_not_invent_effect_or_drop_fatal_teacher(runtime, tmp_path):
    session = helpers.Session(tmp_path / "fatal.json")
    result = click_runtime(runtime, session, state((), "GAME_OVER"))
    content = result["bridge"]._hds.エンジン.台帳.取得("観測台帳")[-1].原入力
    assert content["公開応答区分"] == "GAME_OVER" and observer.TARGET not in content
    assert result["public_response_rows"][-1]["observed_Action6_effect_class"] is None
    api = runtime._original_api()
    bridge = result["bridge"]
    before = api.PublicFrame(((0,),), "GAME_OVER", 0, (0,))
    reset = bridge.update(
        before, api.PublicAction(0), api.PublicFrame(((0,),), "NOT_FINISHED", 0, (6,))
    )
    assert reset["bridge_status"] == "skipped_reset" and bridge.stats["updates_attempted"] == 1


def test_budget_failure_keeps_actual_after_update_and_native_count_limits(
    runtime, tmp_path, monkeypatch
):
    monkeypatch.setenv("ARC3_VISUAL_HDS_QUERY_BUDGET", "0")
    session = helpers.Session(tmp_path / "budget.json")
    result = runtime.query_candidate(
        session, {"candidate": {"action": "MOUSE", "row": 0, "col": 0}, "expected_step": 0}
    )
    assert result["status"] == "budget_exhausted" and session.action_count == 0
    result = click_runtime(runtime, session, state(((1, 1), (1, 0))))
    assert result["bridge"].stats["queries_attempted"] == 0
    assert result["bridge"].stats["updates_succeeded"] == 1


def test_dual_target_native_formatter_preserves_hold_unknown_isolation(runtime):
    local = observer.TARGET
    native = SimpleNamespace(
        状態="断定保留",
        内容={
            "断定保留理由群": ["native unresolved"],
            "予測群": [
                {"結果経路": ["公開応答区分"], "予測値": "盤面変化", "原理参照": "original"},
                {"結果経路": [local], "予測値": observer.EFFECT_VALUES[1], "原理参照": "local"},
            ],
            "係争中原理群": [{"結果経路": [local], "採用状態": "隔離"}],
            "識別不能群": [{"結果経路": [local], "理由": "actual ambiguity"}],
        },
    )
    result = runtime._native_evidence(
        native, {"bridge_status": "queried", "candidate_action_number": 6}
    )
    assert (
        result["native_status"]
        == result["Action6_locality_evidence"]["native_status"]
        == "断定保留"
    )
    detail = result["Action6_locality_evidence"]
    assert detail["target_record_counts"]["有効原理群"] is None
    assert detail["target_records"]["係争中原理群"][0]["採用状態"] == "隔離"
    assert detail["target_records"]["識別不能群"][0]["理由"] == "actual ambiguity"
    assert detail["target_records"]["予測群"][0]["予測値"] == observer.EFFECT_VALUES[1]


def test_generated_cell_bundle_import_keeps_native_canonical_and_observer_cpu_only():
    previous, _ = builder.load_builder()
    base = previous.base_builder()
    previous.configure(base, "masked")
    records = json.loads(base.SOURCE_MANIFEST.read_text(encoding="utf-8"))[
        "patched_source_manifest"
    ]
    sources = {r["path"]: base._guarded(base.SOURCE_ROOT / r["path"], r["sha256"]) for r in records}
    payload, _ = base._bundle()
    assert base._cpu_bundle_import(payload)["bundle_import"] is True
    solver = base._patch_solver(sources[base.SOLVER_REL])
    cell = base._patch_cell(
        payload,
        records,
        "shadow",
        {"update_budget": 80, "query_budget": 80, "hds_seconds_budget": 120.0},
    )
    result = base._cpu_patch_cell(cell, sources, solver)
    assert result["generated_cell_executed"] and result["native_HDS_patched"] is False
