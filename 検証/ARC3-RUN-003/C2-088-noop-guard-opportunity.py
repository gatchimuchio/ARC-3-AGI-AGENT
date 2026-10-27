from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
OUTPUT_ROOT = ROOT / "出力/ARC3-RUN-003-local/C2-088"
TRACES = {
    "v4": OUTPUT_ROOT
    / "B-v3-sequential-exact-output-version4-20261027T151952Z/artifacts",
    "v5": OUTPUT_ROOT
    / "B-v3-sequential-exact-output-version5-20261027T161329Z/artifacts",
}
ACTION_COORDS = re.compile(
    r"^([A-Z0-9_]+)\(\s*(?:ROW\s*=\s*)?(-?\d+)\s*,\s*(?:COL\s*=\s*)?(-?\d+)\s*\)$"
)


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def action_signature(value: str) -> str:
    text = " ".join(value.upper().split())
    match = ACTION_COORDS.match(text)
    if match:
        return f"{match.group(1)}({match.group(2)},{match.group(3)})"
    return text


def state_hash(board: list[list[int]]) -> str:
    # C2-088 v5 does not set ARC3_STATE_IDENTITY_BORDER; the pinned runtime
    # therefore hashes the full public frame (default border width is zero).
    canonical = json.dumps(board, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def analyze_trace(path: Path) -> dict:
    rows = [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    actions = [
        row
        for row in rows
        if row.get("type") == "action" and row.get("action_display")
    ]
    assert rows and actions

    known_noops: set[tuple[str, str]] = set()
    previous = rows[0]
    level = previous.get("level")
    unchanged_count = 0
    first_interception = None

    for action in actions:
        if action.get("level") != level:
            known_noops.clear()
            level = action.get("level")

        display = str(action["action_display"])
        if display.strip().upper() == "RESET":
            previous = action
            continue

        before_hash = state_hash(previous["board"])
        signature = action_signature(display)
        key = (before_hash, signature)
        if key in known_noops:
            first_interception = {
                "action_num": action.get("action_num"),
                "analysis_step": action.get("analysis_step"),
                "level": action.get("level"),
                "action": display,
                "prior_noop_state_hash": before_hash,
                "counterfactual": "would refuse once and force a fresh model turn; subsequent model response is unknown",
            }
            break

        same_public_outcome = (
            previous.get("board") == action.get("board")
            and previous.get("score") == action.get("score")
            and previous.get("level") == action.get("level")
            and previous.get("state") == action.get("state")
        )
        if same_public_outcome:
            known_noops.add(key)
            unchanged_count += 1
        previous = action

    return {
        "trace_path": str(path.relative_to(ROOT)),
        "trace_sha256": sha256(path),
        "action_events": len(actions),
        "batch_size_counts": {
            str(size): count
            for size, count in sorted(Counter(row.get("batch_size") for row in actions).items())
        },
        "exact_same_public_outcome_actions": unchanged_count,
        "first_potential_guard_interception": first_interception,
    }


def main() -> None:
    candidate = ROOT / "出力/ARC3-RUN-003-local/C2-089/action-cap-v2/submission.ipynb"
    notebook = json.loads(candidate.read_text(encoding="utf-8"))
    setup = "".join(notebook["cells"][5]["source"])
    assert "'ARC3_GUARDS_FROM_LEVEL': 2" in setup
    assert "'ARC3_NOOP_REPEAT_GUARD'" not in setup
    assert "'ARC3_STATE_IDENTITY_BORDER'" not in setup

    results = {}
    for version, directory in TRACES.items():
        results[version] = {}
        for trace in sorted(directory.glob("*_p0_events.jsonl")):
            results[version][trace.name.removesuffix("_p0_events.jsonl")] = analyze_trace(trace)

    print(
        json.dumps(
            {
                "schema": "arc3-exact-noop-guard-opportunity.v1",
                "candidate_notebook_sha256": sha256(candidate),
                "candidate_guard_configuration": {
                    "ARC3_NOOP_REPEAT_GUARD": "unset; runtime default false",
                    "ARC3_GUARDS_FROM_LEVEL": 2,
                    "ARC3_STATE_IDENTITY_BORDER": "unset; runtime default 0/full frame",
                },
                "analysis": "Count only the first exact full-frame state/action repeat after a public board, score, level, and state no-change. Stop each trace at that first counterfactual divergence.",
                "traces": results,
                "limitations": [
                    "This is a retrospective public-trace analysis, not a rerun",
                    "A guard refusal changes the next model context; later actions and scores are unknown",
                    "No score improvement is inferred",
                ],
            },
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
