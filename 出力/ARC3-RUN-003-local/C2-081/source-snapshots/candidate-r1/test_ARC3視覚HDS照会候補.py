from __future__ import annotations

import importlib.util
import json
from pathlib import Path
import sys
from types import ModuleType, SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "query_builder", ROOT / "検証/ARC3視覚HDS照会候補構築.py"
)
builder = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(builder)


def public_state(board=((0, 1), (1, 0)), state="NOT_FINISHED", completed=0):
    return SimpleNamespace(
        frame=SimpleNamespace(data=board),
        raw=SimpleNamespace(state=SimpleNamespace(name=state)),
        levels_completed=completed,
        available_actions=(1, 2, 6),
    )


class Session:
    def __init__(self, path):
        self.state_path = path
        self.action_count = 0
        self.game = SimpleNamespace(current_state=public_state())
        self.normalize_calls = 0

    def _normalize_actions(self, arguments):
        self.normalize_calls += 1
        result = []
        for raw in arguments["actions"]:
            name = {"UP": "ACTION1", "DOWN": "ACTION2", "MOUSE": "ACTION6", "RESET": "RESET"}.get(
                raw["action"].upper(), raw["action"].upper()
            )
            if name not in {"ACTION1", "ACTION2", "ACTION6", "RESET"}:
                return None, "unknown action"
            data = (
                {"x": min(63, max(0, int(raw["col"]))), "y": min(63, max(0, int(raw["row"])))}
                if name == "ACTION6"
                else {}
            )
            result.append(SimpleNamespace(id=SimpleNamespace(name=name), data=data))
        return result, None


@pytest.fixture
def runtime(monkeypatch):
    base = builder.base_builder()
    module = ModuleType("arc3_visual_hds_base")
    exec(compile(base.RUNTIME_SOURCE, "frozen-r3-base", "exec"), module.__dict__)
    monkeypatch.setitem(sys.modules, "arc3_visual_hds_base", module)
    result = ModuleType("query_runtime")
    exec(compile(builder.RUNTIME_SOURCE.read_bytes(), "query-runtime", "exec"), result.__dict__)
    for key, value in {
        "ARC3_VISUAL_HDS_MODE": "shadow",
        "ARC3_HDS_EVIDENCE_VISIBILITY": "shown",
        "ARC3_VISUAL_HDS_UPDATE_BUDGET": "80",
        "ARC3_VISUAL_HDS_QUERY_BUDGET": "80",
        "ARC3_VISUAL_HDS_SECONDS_BUDGET": "120",
    }.items():
        monkeypatch.setenv(key, value)
    return result


def query(runtime, session, candidate="UP", call_id="query-1", expected=None, model_turn="model-1"):
    return runtime.query_candidate(
        session,
        {
            "candidate": candidate,
            "expected_step": session.action_count if expected is None else expected,
            "tool_call_id": call_id,
            "model_turn_id": model_turn,
        },
    )


def windows_bootstrap_file_adapter(rpc, tmp_path, monkeypatch):
    """Windows cannot launch the existing 65KB v5 `-c` argument (WinError206).

    Test the identical bootstrap bytes/RPC using a file; Linux draft launcher is unchanged.
    """
    if sys.platform != "win32":
        return
    original = rpc.subprocess.Popen
    path = tmp_path / "identical_sandbox_bootstrap.py"
    path.write_bytes(rpc._SANDBOX_BOOTSTRAP.encode("utf-8"))

    def launch(arguments, **kwargs):
        assert arguments == [sys.executable, "-I", "-S", "-c", rpc._SANDBOX_BOOTSTRAP]
        return original([sys.executable, "-I", "-S", str(path)], **kwargs)

    monkeypatch.setattr(rpc.subprocess, "Popen", launch)


def act(runtime, session, call_id="action-1", candidate="UP", *, after=None, model_turn="model-2"):
    runtime.record_action_call(session, {"tool_call_id": call_id, "model_turn_id": model_turn})
    normalized, error = session._normalize_actions({"actions": [{"action": candidate}]})
    assert error is None
    action = normalized[0]
    current = session.game.current_state
    captured = runtime.before_action(session, action, public_grid=current.frame.data)
    session.action_count += 1
    response = after or public_state(((0, 1), (1, 1)))
    session.game.current_state = response
    runtime.after_action(session, action, captured, response, public_grid=response.frame.data)
    return runtime._state(session)


def test_query_is_native_hold_without_action_or_learning_update(runtime, tmp_path):
    session = Session(tmp_path / "state.json")
    before = session.game.current_state
    result = query(runtime, session)
    learner = runtime._state(session)["bridge"]
    assert result["executed"] is result["authorization"] is result["endorsement"] is False
    assert result["recommendation"] is None
    assert result["evidence_status"] == "UNCERTAIN"
    assert result["evidence"]["native_status"] == "断定保留"
    assert result["evidence"]["native_hold_reasons"]
    assert result["evidence"]["target_records"]["係争中原理群"] == []
    assert result["evidence"]["support_counts"].startswith("UNKNOWN")
    assert learner.stats["updates_attempted"] == 0
    assert learner.stats["queries_attempted"] == 1
    assert learner._hds.エンジン.台帳.件数("観測台帳") == 5
    assert session.action_count == 0 and session.game.current_state is before


@pytest.mark.parametrize(
    "candidate",
    [
        [],
        ["UP"],
        {"action": "RESET"},
        {"action": "MOUSE", "row": True, "col": 0},
        {"action": "MOUSE", "row": 0.0, "col": 0},
        {"action": "MOUSE", "row": -1, "col": 0},
        {"action": "MOUSE", "row": 2, "col": 0},
        {"action": "MOUSE", "x": 0, "y": 0},
        {"action": "UP", "row": 0},
        {"action": "ACTION7"},
    ],
)
def test_strict_single_legal_candidate_rejects_without_query(runtime, tmp_path, candidate):
    session = Session(tmp_path / "state.json")
    response = query(runtime, session, candidate)
    assert response["status"] == "query_unavailable"
    assert response["authorization"] is False
    assert runtime._state(session)["bridge"] is None
    assert session.action_count == 0


def test_exact_coords_cache_candidate_cap_public_state_and_session_lifetime(runtime, tmp_path):
    one = Session(tmp_path / "one.json")
    mouse = {"action": "MOUSE", "row": 0, "col": 1}
    query(runtime, one, mouse)
    learner = runtime._state(one)["bridge"]
    cached = query(runtime, one, mouse, "query-2")
    assert cached["cache_hit"] is True
    assert learner.stats["queries_attempted"] == 1
    assert next(iter(runtime._state(one)["cache"])) == runtime._api().PublicAction(6, 1, 0)
    query(runtime, one, "UP")
    assert query(runtime, one, "DOWN")["status"] == "distinct_candidate_limit"
    assert learner.stats["queries_attempted"] == 2
    assert query(runtime, one, expected=1)["status"] == "stale_public_step"
    one.game.current_state = public_state(((1, 1), (1, 0)))
    query(runtime, one, "UP")
    assert learner.stats["queries_attempted"] == 3
    two = Session(tmp_path / "two.json")
    query(runtime, two)
    assert runtime._state(two)["bridge"] is not learner
    assert runtime._state(two)["bridge"].stats["queries_attempted"] == 1


def test_actual_action_has_no_automatic_query_and_one_after_update(runtime, tmp_path):
    session = Session(tmp_path / "state.json")
    state = act(runtime, session)
    assert state["bridge"].stats["queries_attempted"] == 0
    assert state["bridge"].stats["updates_succeeded"] == 1
    assert state["counts"]["public_outcome:盤面変化"] == 1
    assert state["last_query"] is None


def test_actual_native_hold_partial_forecast_is_not_suppressed_or_endorsed(runtime, tmp_path):
    from hds学習系統.型 import 外部入力

    session = Session(tmp_path / "partial.json")
    learner = runtime._bridge(runtime._state(session))
    probe = json.loads(
        (ROOT / "運用/証拠/ARC26-UNIFIED/C2-078_synthetic-learning-probe.json").read_text(
            encoding="utf-8"
        )
    )
    for row in probe["training"]:
        learner._hds.処理する(
            外部入力(
                {**row["input_features"], "公開応答区分": row["expected_outcome"]},
                "ARC3視覚公開作用応答候補",
            )
        )
    result = query(runtime, session)
    native = result["evidence"]
    assert native["native_status"] == "断定保留"
    assert {r["予測値"] for r in native["target_records"]["予測群"]} == {"盤面変化"}
    assert native["target_records"]["有効原理群"]
    assert native["native_hold_reasons"]
    assert result["evidence_status"] == "UNCERTAIN"
    assert result["recommendation"] is None and result["endorsement"] is False
    assert learner.stats["queries_attempted"] == 1


def test_fatal_response_is_updated_before_reset_and_reset_is_not_taught(runtime, tmp_path):
    session = Session(tmp_path / "fatal.json")
    query(runtime, session)
    action = SimpleNamespace(id=SimpleNamespace(name="ACTION1"), data={})
    captured = runtime.before_action(
        session, action, public_grid=session.game.current_state.frame.data
    )
    session.action_count = 1
    fatal = public_state(((0, 0), (0, 0)), state="GAME_OVER")
    session.game.current_state = public_state()  # Model view may already be reset.
    runtime.after_action(session, action, captured, fatal, public_grid=fatal.frame.data)
    state = runtime._state(session)
    observations = state["bridge"]._hds.エンジン.台帳.取得("観測台帳")
    assert observations[-1].原入力["公開応答区分"] == "GAME_OVER"
    assert state["cache"] == {} and state["last_query"] is None
    reset = SimpleNamespace(id=SimpleNamespace(name="RESET"), data={})
    assert runtime.before_action(session, reset, public_grid=(), automatic=True) is None
    assert state["bridge"].stats["updates_attempted"] == 1


def test_same_call_is_unreviewed_separate_call_order_is_distinguished(runtime, tmp_path):
    same = Session(tmp_path / "same.json")
    query(runtime, same, call_id="tool-1")
    state = act(runtime, same, "tool-1", model_turn="model-1")
    assert state["counts"]["same_tool_call_query_then_action_unreviewed"] == 1
    assert state["counts"]["action_after_distinct_tool_call_query"] == 0
    assert state["counts"]["same_model_response_query_action_unreviewed"] == 1
    assert [r["event"] for r in state["trace"]] == [
        "query_returned",
        "action_call_requested",
        "action_after_query",
    ]
    separate = Session(tmp_path / "separate.json")
    query(runtime, separate, call_id="tool-1")
    state = act(runtime, separate, "tool-2")
    assert state["counts"]["action_after_distinct_tool_call_query"] == 1
    assert state["counts"]["distinct_model_response_after_query"] == 1
    assert (
        state["bridge"].stats["queries_attempted"]
        == state["bridge"].stats["updates_succeeded"]
        == 1
    )
    same_turn = Session(tmp_path / "same-turn.json")
    query(runtime, same_turn, call_id="python-1:markup-call-1", model_turn="model-9")
    state = act(runtime, same_turn, "python-2:markup-call-2", model_turn="model-9")
    assert state["counts"]["same_model_response_query_action_unreviewed"] == 1
    assert state["trace"][-1]["model_observation_opportunity"] is False


def test_query_budget_or_hds_error_never_prevents_separate_legal_play(
    runtime, tmp_path, monkeypatch
):
    monkeypatch.setenv("ARC3_VISUAL_HDS_QUERY_BUDGET", "0")
    session = Session(tmp_path / "budget.json")
    assert query(runtime, session)["status"] == "budget_exhausted"
    state = act(runtime, session)
    assert session.action_count == 1 and state["bridge"].stats["updates_succeeded"] == 1
    monkeypatch.setenv("ARC3_VISUAL_HDS_QUERY_BUDGET", "80")
    broken = Session(tmp_path / "error.json")
    bridge = runtime._bridge(runtime._state(broken))
    monkeypatch.setattr(
        bridge._hds, "照会する", lambda value: (_ for _ in ()).throw(RuntimeError("synthetic"))
    )
    assert query(runtime, broken)["status"] == "hds_error"
    assert act(runtime, broken)["bridge"].stats["updates_succeeded"] == 1


def test_masked_and_shown_compute_identical_native_operations(runtime, tmp_path, monkeypatch):
    shown, masked = Session(tmp_path / "shown.json"), Session(tmp_path / "masked.json")
    visible = query(runtime, shown)
    monkeypatch.setenv("ARC3_HDS_EVIDENCE_VISIBILITY", "masked")
    hidden = query(runtime, masked)
    assert hidden["evidence"] == {"masked": True}
    assert visible["evidence"]["native_status"] == "断定保留"
    for s in (shown, masked):
        learner = runtime._state(s)["bridge"]
        assert learner.stats["queries_succeeded"] == 1 and learner.stats["updates_attempted"] == 0


def test_missing_native_fields_remain_unknown_and_returned_target_hold_details_preserved(runtime):
    native = SimpleNamespace(
        状態="断定保留",
        内容={
            "断定保留理由群": ["native reason"],
            "係争中原理群": [
                {"結果経路": ["公開応答区分"], "採用状態": "隔離", "支持参照群": ["observed-ref"]}
            ],
            "識別不能群": [{"結果経路": ["公開応答区分"], "理由": "ambiguous"}],
        },
    )
    result = runtime._native_evidence(native, {"bridge_status": "queried"})
    assert result["native_status"] == "断定保留"
    assert result["target_record_counts"]["予測群"] is None
    assert result["target_records"]["係争中原理群"][0]["支持参照群"] == ["observed-ref"]
    assert result["target_records"]["識別不能群"][0]["理由"] == "ambiguous"


def test_actual_patched_sandbox_rpc_returns_query_before_any_action(runtime, tmp_path, monkeypatch):
    base = builder.base_builder()
    extras = builder.patched_extra_sources(base)
    path = tmp_path / "python_tool_sandbox.py"
    path.write_bytes(extras[builder.SANDBOX_REL])
    monkeypatch.syspath_prepend(str(base.SOURCE_ROOT / "src/ARC3-Inference"))
    spec = importlib.util.spec_from_file_location("candidate_rpc", path)
    rpc = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(rpc)
    windows_bootstrap_file_adapter(rpc, tmp_path, monkeypatch)
    session = Session(tmp_path / "state.json")
    actions, order = [], []

    def handler(request):
        order.append("query")
        return runtime.query_candidate(session, {**request, "tool_call_id": "model-query"})

    initial = {
        "current_frame": {
            "ascii": "AB\nBA",
            "step": 0,
            "level": 1,
            "shape": [2, 2],
            "grid": [[0, 1], [1, 0]],
        },
        "history": [],
        "valid_actions": ["UP", "MOUSE"],
    }
    result = rpc.run_sandboxed_python(
        code='q=hds_query("UP"); print(q["evidence"]["native_status"], q["authorization"])',
        timeout_seconds=10,
        initial_state=initial,
        action_handler=lambda *args, **kwargs: actions.append(args),
        hds_query_handler=handler,
    )
    assert not result["error"]
    assert "断定保留 False" in result["stdout"]
    assert actions == [] and order == ["query"]
    assert result["action_results"] == []
    assert session.action_count == 0


def test_actual_toolagent_python_rpc_routes_candidate_and_model_call_identity(
    runtime, tmp_path, monkeypatch
):
    base = builder.base_builder()
    extras = builder.patched_extra_sources(base)
    monkeypatch.syspath_prepend(str(base.SOURCE_ROOT / "src/ARC3-Inference"))
    rpc_path = tmp_path / "rpc.py"
    rpc_path.write_bytes(extras[builder.SANDBOX_REL])
    spec = importlib.util.spec_from_file_location("inference.agent.python_tool_sandbox", rpc_path)
    rpc = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "inference.agent.python_tool_sandbox", rpc)
    spec.loader.exec_module(rpc)
    windows_bootstrap_file_adapter(rpc, tmp_path, monkeypatch)
    tool_path = tmp_path / "tool_agent.py"
    tool_path.write_bytes(extras[base.TOOL_AGENT_REL])
    spec = importlib.util.spec_from_file_location("actual_candidate_toolagent", tool_path)
    tool = importlib.util.module_from_spec(spec)
    monkeypatch.setitem(sys.modules, "actual_candidate_toolagent", tool)
    spec.loader.exec_module(tool)
    session = Session(tmp_path / "state.json")
    frame = tool.Frame(grid=[[0, 1], [1, 0]], step=0, level=1)
    monkeypatch.setattr(tool, "load_runtime_state", lambda path: (frame, []))
    monkeypatch.setenv("ARC3_DEATH_LEDGER", "0")
    agent = tool.ToolAgent.__new__(tool.ToolAgent)
    agent._ensure_session = lambda path: None
    agent._current_valid_actions = ["ACTION1", "ACTION2", "ACTION6"]
    agent._last_action_call_result = None
    agent._last_step_summary = None
    agent._python_timeout = 10
    agent._repeat_state_seen = set()
    agent._retained_sources = lambda: None
    agent._record_retained_functions = lambda result, payload: None
    agent._tool_output_tokens = 2000
    agent._tool_output_chars = 8000
    agent._arc3_active_tool_call_id = "actual-model-query-call"
    agent._arc3_hds_active_model_turn = "model-11"
    requests = []

    def callback(request):
        requests.append(request)
        assert request["query"] == "hds"  # This inspection performs no action/order call.
        return runtime.query_candidate(session, request)

    agent._step_env_callback = callback
    response = agent._run_python_tool(
        session.state_path,
        {
            "code": 'q=hds_query({"action":"MOUSE","row":0,"col":1}); print(q["evidence"]["native_status"])'
        },
    )
    assert "断定保留" in json.loads(response.content)["stdout"] and not response.step_executed
    assert len(requests) == 1
    assert requests[0]["tool_call_id"] == "python-1:actual-model-query-call"
    assert requests[0]["model_turn_id"] == "model-11"
    assert requests[0]["candidate"] == {"action": "MOUSE", "row": 0, "col": 1}
    assert session.action_count == 0


def test_generated_cell_applies_all_shared_rpc_hashguards(tmp_path):
    base = builder.base_builder()
    builder.configure(base, "masked")
    records = json.loads(base.SOURCE_MANIFEST.read_text(encoding="utf-8"))[
        "patched_source_manifest"
    ]
    source_files = {
        r["path"]: base._guarded(base.SOURCE_ROOT / r["path"], r["sha256"]) for r in records
    }
    solver = base._patch_solver(source_files[base.SOLVER_REL])
    payload, _ = base._bundle()
    cell = base._patch_cell(
        payload,
        records,
        "shadow",
        {"update_budget": 80, "query_budget": 80, "hds_seconds_budget": 120.0},
    )
    result = base._cpu_patch_cell(cell, source_files, solver)
    assert result["generated_cell_executed"] and result["RPC_postimage_hashes_verified"]
    assert result["model_seed_before_import"] == 0
    assert result["native_HDS_patched"] is False
