from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
NOTEBOOK = ROOT / "出力/ARC3-RUN-003-local/C2-089/action-cap-v2/submission.ipynb"
SOURCE_ARCHIVE = (
    ROOT
    / "入力/モデル実行基底/v5/taaf-source-v1/taaf-kaggle-source-bundle-copy.zip"
)
EXPECTED_NOTEBOOK_SHA256 = "88b619063c485f5c46163d64df86d83c542ebe1559d05c53ef669a625099586e"
EXPECTED_SOURCE_ARCHIVE_SHA256 = "cd687f4bc10b2128ea9895024cd2e990b24a1070607a071901cccd1638606187"
CAP_ENV = "ARC3_MAX_ACTIONS_PER_PYTHON_CALL"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_patched_agent():
    notebook_bytes = NOTEBOOK.read_bytes()
    source_archive_bytes = SOURCE_ARCHIVE.read_bytes()
    notebook_hash = hashlib.sha256(notebook_bytes).hexdigest()
    source_archive_hash = hashlib.sha256(source_archive_bytes).hexdigest()
    assert notebook_hash == EXPECTED_NOTEBOOK_SHA256, notebook_hash
    assert source_archive_hash == EXPECTED_SOURCE_ARCHIVE_SHA256, source_archive_hash

    notebook = json.loads(notebook_bytes)
    manifest = json.loads(
        (NOTEBOOK.parent / "candidate-manifest.json").read_text(encoding="utf-8")
    )
    assert manifest["treatment"]["max_executed_actions_per_python_call"] == 12
    cell3 = "".join(notebook["cells"][3]["source"])
    assert "%%writefile /kaggle/harness-changes.patch\n" in cell3
    patch = cell3.split("\n", 1)[1]
    assert patch.startswith("diff --git a/ARC3-Inference/")
    patch_hash = hashlib.sha256(patch.encode("utf-8")).hexdigest()
    cell5 = "".join(notebook["cells"][5]["source"])
    assert f"'{CAP_ENV}': '12'" in cell5

    temp = tempfile.TemporaryDirectory(prefix="arc3-c2-089-cap12-")
    source_root = Path(temp.name) / "src"
    with zipfile.ZipFile(SOURCE_ARCHIVE) as archive:
        for member in archive.namelist():
            prefix = "src/ARC3-Inference/"
            if not member.startswith(prefix) or member.endswith("/"):
                continue
            relative = Path(member.removeprefix("src/"))
            destination = (source_root / relative).resolve()
            destination.relative_to(source_root.resolve())
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(archive.read(member))

    applied = subprocess.run(
        ["git", "apply", "--whitespace=nowarn", "-"],
        input=patch.encode("utf-8"),
        cwd=source_root,
        capture_output=True,
        check=False,
    )
    assert applied.returncode == 0, applied.stderr.decode("utf-8", errors="replace")
    sys.path.insert(0, str(source_root / "ARC3-Inference"))
    os.environ["EXPOSE_RESET"] = "off"
    import inference.agent.tool_agent as tool_agent

    return temp, tool_agent, {
        "notebook_sha256": notebook_hash,
        "source_archive_sha256": source_archive_hash,
        "notebook_cell3_patch_sha256": patch_hash,
        "manifest_sha256": sha256(NOTEBOOK.parent / "candidate-manifest.json"),
    }


def exercise_case(tool_agent, name, requests, replies, cap):
    if cap is None:
        os.environ.pop(CAP_ENV, None)
    else:
        os.environ[CAP_ENV] = str(cap)

    engine_action_counts: list[int] = []
    action_results: list[dict] = []

    def step_callback(arguments):
        actions = arguments["actions"]
        engine_action_counts.append(len(actions))
        reply = replies[len(engine_action_counts) - 1]
        if reply == "refused":
            executed_count = 0
            executed = False
        else:
            executed_count = len(actions) if reply == "full" else int(reply)
            executed = executed_count > 0
        return {
            "executed": executed,
            "executed_count": executed_count,
            "requested_count": len(actions),
            "action_num": sum(engine_action_counts),
            "level": 1,
            "score": 0,
            "state": "NOT_FINISHED",
            "valid_actions": ["UP", "DOWN"],
            "board_changed": bool(executed_count),
            "gameplay_changed": bool(executed_count),
            "done": False,
            "level_completed": False,
            "game_over": False,
            "run_complete": False,
        }

    agent = tool_agent.ToolAgent.__new__(tool_agent.ToolAgent)
    agent._ensure_session = lambda _path: None
    agent._current_valid_actions = ["UP", "DOWN"]
    agent._step_env_callback = step_callback
    agent._python_timeout = 30
    agent._noop_repeat_guard = None
    agent._guard_hook_trace = []
    agent._guard_death_override_batch = False
    agent._repeat_state_seen = set()
    agent._last_action_call_result = None
    agent._last_step_summary = None
    agent._game_elapsed_seconds = None
    agent._record_retained_functions = lambda _result, _payload: None
    agent._retained_sources = lambda: {}
    agent._summarize_step_sequence = lambda _results: {"synthetic": True}
    agent._update_summarized_knowledge_from_step_summary = lambda: None
    agent._render_tool_payload = lambda payload, truncate_fields=(): json.dumps(
        payload, default=str
    )

    def fake_sandbox(**arguments):
        for count in requests:
            wrapped = arguments["action_handler"](["UP"] * count)
            action_results.append(wrapped["action_result"])
        return {"action_results": action_results, "stdout": "", "error": "", "result": None}

    previous_sandbox = tool_agent.run_sandboxed_python
    tool_agent.run_sandboxed_python = fake_sandbox
    try:
        dispatch = agent._run_python_tool(Path("synthetic-state"), {"code": "pass"})
    finally:
        tool_agent.run_sandboxed_python = previous_sandbox

    return {
        "name": name,
        "configured_cap": cap,
        "engine_action_counts": engine_action_counts,
        "results": [
            {
                "executed": result.get("executed"),
                "requested_count": result.get("requested_count"),
                "executed_count": result.get("executed_count"),
                "stop_reason": result.get("stop_reason"),
            }
            for result in action_results
        ],
        "dispatch_step_executed": dispatch.step_executed,
    }


def main() -> None:
    temp, tool_agent, input_hashes = load_patched_agent()
    try:
        tool_agent.load_runtime_state = lambda _path: (None, [])
        tool_agent._ascii_frame_view_payload = lambda _frame: {}
        tool_agent._ascii_history_view_payload = lambda _history: []
        tool_agent._animation_enabled = lambda: False

        partial = exercise_case(
            tool_agent,
            "partial_execution_accumulates",
            [8, 10, 1],
            [5, 7],
            12,
        )
        assert partial["engine_action_counts"] == [8, 7], partial
        assert partial["results"][1]["requested_count"] == 10, partial
        assert partial["results"][1]["executed_count"] == 7, partial
        assert partial["results"][1]["stop_reason"] == "python_tool_action_limit", partial
        assert partial["results"][2]["executed"] is False, partial
        assert partial["results"][2]["stop_reason"] == "python_tool_action_limit", partial

        refused = exercise_case(
            tool_agent,
            "refused_action_does_not_consume",
            [1, 15, 1],
            ["refused", 12],
            12,
        )
        assert refused["engine_action_counts"] == [1, 12], refused
        assert refused["results"][1]["requested_count"] == 15, refused
        assert refused["results"][1]["executed_count"] == 12, refused
        assert refused["results"][2]["stop_reason"] == "python_tool_action_limit", refused

        uncapped = exercise_case(
            tool_agent,
            "unset_cap_preserves_uncapped_behavior",
            [15, 1],
            ["full", "full"],
            None,
        )
        assert uncapped["engine_action_counts"] == [15, 1], uncapped
        assert all(result["stop_reason"] is None for result in uncapped["results"]), uncapped

        print(
            json.dumps(
                {
                    "status": "PASS",
                    "candidate": "C2-089 action-cap-v2 cap12",
                    "method": "Exact candidate Notebook cell 3 patch applied to pinned source archive; synthetic sandbox callback",
                    "input_hashes": input_hashes,
                    "scenarios": [partial, refused, uncapped],
                    "limitations": [
                        "No real game engine or public game was run",
                        "No private Kaggle kernel was pushed or run",
                        "No score effect was measured",
                    ],
                },
                ensure_ascii=False,
                indent=2,
            )
        )
    finally:
        temp.cleanup()


if __name__ == "__main__":
    main()
