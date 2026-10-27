from __future__ import annotations

import hashlib
import importlib.util
import json
import os
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
CANDIDATE = (
    ROOT
    / "出力/ARC3-RUN-003-local/C2-089/action-cap-v3-level1-noop/submission.ipynb"
)
PARENT = (
    ROOT / "出力/ARC3-RUN-003-local/C2-089/action-cap-v2/submission.ipynb"
)
EXPECTED_CANDIDATE_SHA256 = "15cd94b3a2702f6154a8c8dfe9771288b4800628a9f8f6222eb030249eeb17e6"
BOUNDARY_RUNNER = ROOT / "検証/ARC3-RUN-003/C2-089-cap12-synthetic-boundary.py"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_boundary_runner():
    spec = importlib.util.spec_from_file_location("arc3_cap12_boundary", BOUNDARY_RUNNER)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    module.NOTEBOOK = CANDIDATE
    module.EXPECTED_NOTEBOOK_SHA256 = EXPECTED_CANDIDATE_SHA256
    return module


def main() -> None:
    assert sha256(CANDIDATE) == EXPECTED_CANDIDATE_SHA256
    parent_nb = json.loads(PARENT.read_text(encoding="utf-8"))
    candidate_nb = json.loads(CANDIDATE.read_text(encoding="utf-8"))
    assert len(parent_nb["cells"]) == len(candidate_nb["cells"])
    changed = [
        index
        for index, (before, after) in enumerate(zip(parent_nb["cells"], candidate_nb["cells"]))
        if before.get("source") != after.get("source")
    ]
    assert changed == [5], changed
    setup = "".join(candidate_nb["cells"][5]["source"])
    assert "'ARC3_GUARDS_FROM_LEVEL': 1" in setup
    assert "'ARC3_NOOP_REPEAT_GUARD': '1'" in setup
    assert "'ARC3_MAX_ACTIONS_PER_PYTHON_CALL': '12'" in setup

    os.environ["ARC3_GUARDS_FROM_LEVEL"] = "1"
    os.environ["ARC3_NOOP_REPEAT_GUARD"] = "1"
    os.environ["ARC3_DEATH_REPEAT_GUARD"] = "0"
    boundary = load_boundary_runner()
    temp, tool_agent, source_hashes = boundary.load_patched_agent()
    try:
        assert tool_agent._guards_active(1)
        guard = tool_agent.NoopRepeatGuard()
        agent = tool_agent.ToolAgent.__new__(tool_agent.ToolAgent)
        agent._noop_repeat_guard = guard
        agent._noop_guard_deaths_enabled = False
        agent._noop_guard_noops_enabled = True
        agent._guard_death_override_batch = False
        agent._guard_hook_trace = []
        agent._repeat_state_seen = set()
        grid = [[0, 1, 2], [3, 4, 5], [6, 7, 8]]
        state_hash = tool_agent._interior_state_hash(grid)
        guard.note_level(1)
        guard.observe(state_hash, "UP", gameplay_changed=False)

        first = agent._action_guard_hook(grid, "UP", {}, level=1)
        second = agent._action_guard_hook(grid, "UP", {}, level=1)
        guard.observe(state_hash, "UP", gameplay_changed=True)
        after_contradiction = agent._action_guard_hook(grid, "UP", {}, level=1)
        assert first and first[0] == "known_noop", first
        assert second is None, second
        assert after_contradiction is None, after_contradiction

        partial = boundary.exercise_case(
            tool_agent, "partial_execution_accumulates", [8, 10, 1], [5, 7], 12
        )
        assert partial["engine_action_counts"] == [8, 7], partial
        assert partial["results"][1]["stop_reason"] == "python_tool_action_limit", partial

        refused = boundary.exercise_case(
            tool_agent, "refused_action_does_not_consume", [1, 15, 1], ["refused", 12], 12
        )
        assert refused["engine_action_counts"] == [1, 12], refused
        assert refused["results"][2]["stop_reason"] == "python_tool_action_limit", refused

        uncapped = boundary.exercise_case(
            tool_agent, "unset_cap_preserves_uncapped_behavior", [15, 1], ["full", "full"], None
        )
        assert uncapped["engine_action_counts"] == [15, 1], uncapped

        print(
            json.dumps(
                {
                    "status": "PASS",
                    "candidate_notebook_sha256": sha256(CANDIDATE),
                    "parent_notebook_sha256": sha256(PARENT),
                    "changed_cells_vs_cap12_v2": changed,
                    "candidate_guard_settings": {
                        "ARC3_GUARDS_FROM_LEVEL": 1,
                        "ARC3_NOOP_REPEAT_GUARD": "1",
                        "ARC3_MAX_ACTIONS_PER_PYTHON_CALL": "12",
                    },
                    "source_hashes": source_hashes,
                    "guard_behavior": {
                        "level1_active": True,
                        "known_noop_first_attempt": first[0],
                        "immediate_insist_override": second is None,
                        "contradictory_change_clears_known_noop": after_contradiction is None,
                    },
                    "cap12_scenarios": [partial, refused, uncapped],
                    "limitations": [
                        "Only synthetic runtime callbacks were used",
                        "No public game, private Kaggle kernel, or official score was produced",
                        "The proposed guard changes model turns; gameplay effect is unknown",
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
