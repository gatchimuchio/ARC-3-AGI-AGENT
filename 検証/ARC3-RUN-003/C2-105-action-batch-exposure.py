from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]
TRACE_DIR = ROOT / "出力/ARC3-RUN-003-local/C2-060-outputcap-20480-context139264/remote-v29/output/artifacts"
EXPECTED_TRACE_SHA256 = {
    "m0r0-492f87ba_p0_events.jsonl": "d532b2749e95347cbdc61b8ad8b38ec14383388078c3810c0f8feeeb0d06a3c5",
    "sk48-d8078629_p0_events.jsonl": "e67a94ba0aba46855d61ff147a9e4fcf3e8101b68c626bb9b6240d3a6b71c239",
    "tn36-ef4dde99_p0_events.jsonl": "50c6b69bbdf0403f9db17104b7021f9ce36af33436ec8a298e3ff0a70be70490",
}
CAP = 8


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_batches(path: Path) -> tuple[list[dict[str, Any]], int]:
    actions: list[dict[str, Any]] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if not line.strip():
            continue
        row = json.loads(line)
        if row.get("type") == "action":
            actions.append(row)

    batches: list[dict[str, Any]] = []
    current: list[dict[str, Any]] = []
    current_size: int | None = None

    def flush() -> None:
        nonlocal current, current_size
        if current:
            batches.append({"planned_size": current_size, "actions": current})
        current = []
        current_size = None

    for row in actions:
        index = int(row["batch_index"])
        size = int(row["batch_size"])
        if index == 1:
            flush()
            current_size = size
        if current_size is None or size != current_size or index != len(current) + 1:
            raise ValueError(f"Invalid action batch sequence in {path.name}: index={index}, size={size}")
        current.append(row)
        if index == size:
            flush()
    flush()
    return batches, len(actions)


def summarize_trace(path: Path) -> dict[str, Any]:
    digest = sha256(path)
    expected = EXPECTED_TRACE_SHA256.get(path.name)
    if digest != expected:
        raise ValueError(f"Trace hash mismatch for {path.name}: {digest}")
    batches, action_count = load_batches(path)
    sizes = Counter(int(batch["planned_size"]) for batch in batches)
    over_cap = [batch for batch in batches if int(batch["planned_size"]) > CAP]
    tails = [
        action
        for batch in over_cap
        for action in batch["actions"][CAP:]
    ]
    return {
        "source_file": str(path.relative_to(ROOT)),
        "source_sha256": digest,
        "action_events": action_count,
        "action_batches": len(batches),
        "batch_size_distribution": {str(k): sizes[k] for k in sorted(sizes)},
        "batches_over_cap": len(over_cap),
        "planned_actions_after_cap": sum(max(0, int(batch["planned_size"]) - CAP) for batch in over_cap),
        "executed_actions_after_cap": len(tails),
        "tail_outcomes": {
            "board_changed": sum(action.get("board_changed") is True for action in tails),
            "nonzero_reward": sum(float(action.get("reward", 0) or 0) != 0 for action in tails),
            "level_completed": sum(action.get("level_completed") is True for action in tails),
            "game_over": sum(action.get("game_over") is True for action in tails),
        },
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(f"Refusing to overwrite evidence: {args.output}")
    traces = [summarize_trace(TRACE_DIR / name) for name in EXPECTED_TRACE_SHA256]
    totals = {
        "action_events": sum(row["action_events"] for row in traces),
        "action_batches": sum(row["action_batches"] for row in traces),
        "batches_over_cap": sum(row["batches_over_cap"] for row in traces),
        "planned_actions_after_cap": sum(row["planned_actions_after_cap"] for row in traces),
        "executed_actions_after_cap": sum(row["executed_actions_after_cap"] for row in traces),
        "tail_outcomes": {
            key: sum(row["tail_outcomes"][key] for row in traces)
            for key in ("board_changed", "nonzero_reward", "level_completed", "game_over")
        },
    }
    result = {
        "schema": "arc3-c2-105-action-batch-exposure.v1",
        "observed_at_utc": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        "track": "ARC3",
        "candidate": "C2-105 action-plan cap 8",
        "base_kernel": "tecchannn/arc3-model-guided-c2-025 version 29",
        "cap": CAP,
        "batch_boundary": "Harness action batch_index/batch_size fields; analysis_step is not used as an action-batch boundary.",
        "traces": traces,
        "totals": totals,
        "interpretation": "Five logged action batches exceeded eight actions; their eleven executed tail actions all changed the board, while none completed a level, ended a game, or returned nonzero reward. A capped rerun could reobserve earlier, but its subsequent model actions and score cannot be inferred from static traces.",
        "limitations": [
            "Retrospective public trace analysis only; no game was rerun.",
            "Logged action batch boundaries are not asserted to equal every Python snippet boundary.",
            "No private kernel run, official Competition Rerun, or score measurement occurred.",
        ],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

