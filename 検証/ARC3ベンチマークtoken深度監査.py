from __future__ import annotations

import argparse
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any


TOKEN_TOTAL = re.compile(r"^total tokens:\s*([0-9,]+)\s*$", re.MULTILINE)
SOLVER_TOKENS = re.compile(r"(?:^|\s)tokens=(\d+)(?:\s|$)")


def _nonnegative_int(value: Any, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field} must be a nonnegative integer")
    return value


def _public_action_depths(path: Path) -> list[int]:
    previous_level: int | None = None
    depths: list[int] = []
    with path.open(encoding="utf-8") as stream:
        for line in stream:
            if not line.strip():
                continue
            row = json.loads(line)
            row_type = row.get("type")
            if row_type == "initial":
                if previous_level is not None:
                    raise ValueError("event stream has more than one initial observation")
                level = row.get("level")
                if type(level) is not int or level < 1:
                    raise ValueError("initial public level is missing or invalid")
                previous_level = level
            elif row_type == "action":
                if previous_level is None:
                    raise ValueError("action appears before initial observation")
                level = row.get("level")
                if type(level) is not int or level < 1:
                    raise ValueError("post-action public level is missing or invalid")
                if level > previous_level + 1:
                    raise ValueError("public level jumped by more than one")
                depths.append(previous_level)
                previous_level = level
    if previous_level is None:
        raise ValueError("event stream has no initial observation")
    return depths


def _group_summary(group: dict[str, int]) -> dict[str, int | float]:
    actions = group["action_count"]
    return {
        "run_count": group["run_count"],
        "action_count": actions,
        "generated_tokens_total": group["generated_tokens_total"],
        "actions_with_generated_tokens": group["actions_with_generated_tokens"],
        "mean_generated_tokens_per_action": round(group["generated_tokens_total"] / actions, 2)
        if actions
        else 0.0,
    }


def audit_token_depth(
    benchmark: dict[str, Any], event_root: Path, summary_text: str, max_actions: int = 80
) -> dict[str, Any]:
    """Return anonymous depth aggregates; run identifiers are used only for joining."""
    if max_actions < 1:
        raise ValueError("max_actions must be positive")
    runs = benchmark.get("game_runs")
    if not isinstance(runs, list):
        raise ValueError("benchmark game_runs must be a list")

    event_files = list(event_root.glob("*_p0_events.jsonl"))
    if len(event_files) != len(runs):
        raise ValueError("event stream count does not match benchmark run count")
    event_by_run = {path.name.split("_p0_", 1)[0]: path for path in event_files}
    if len(event_by_run) != len(event_files):
        raise ValueError("event stream names are not unique")

    depth_stats: dict[int, dict[str, int]] = {}
    groups = {
        "action_limit_reached": {
            "run_count": 0,
            "action_count": 0,
            "generated_tokens_total": 0,
            "actions_with_generated_tokens": 0,
        },
        "below_action_limit": {
            "run_count": 0,
            "action_count": 0,
            "generated_tokens_total": 0,
            "actions_with_generated_tokens": 0,
        },
    }
    all_generated_tokens = 0
    all_input_tokens = 0
    nonzero_input_actions = 0
    history_count = 0
    max_wallclock = 0.0
    matched_runs = 0
    solver_note_tokens = 0
    solver_note_count = 0

    for run in runs:
        # This value is deliberately never copied into the aggregate result.
        run_key = Path(str(run.get("game_id", ""))).name
        event_path = event_by_run.get(run_key)
        if event_path is None:
            raise ValueError("benchmark run has no matching public event stream")
        depths = _public_action_depths(event_path)
        history = run.get("history", [])
        if not isinstance(history, list) or len(history) != len(depths):
            raise ValueError("action history does not align with public event stream")
        action_count = len(history)
        if action_count > max_actions:
            raise ValueError("run exceeds the configured action limit")
        group_name = "action_limit_reached" if action_count == max_actions else "below_action_limit"
        group = groups[group_name]
        group["run_count"] += 1
        group["action_count"] += action_count
        matched_runs += 1

        for depth, item in zip(depths, history, strict=True):
            generated = _nonnegative_int(item.get("generated_tokens"), "generated_tokens")
            uncached = _nonnegative_int(item.get("uncached_input_tokens"), "uncached_input_tokens")
            wallclock = item.get("wallclock_seconds")
            if isinstance(wallclock, bool) or not isinstance(wallclock, (int, float)):
                raise ValueError("wallclock_seconds must be numeric")
            all_generated_tokens += generated
            all_input_tokens += uncached
            nonzero_input_actions += uncached > 0
            max_wallclock = max(max_wallclock, float(wallclock))
            history_count += 1

            group["generated_tokens_total"] += generated
            group["actions_with_generated_tokens"] += generated > 0
            stat = depth_stats.setdefault(
                depth,
                {
                    "action_count": 0,
                    "generated_tokens_total": 0,
                    "actions_with_generated_tokens": 0,
                },
            )
            stat["action_count"] += 1
            stat["generated_tokens_total"] += generated
            stat["actions_with_generated_tokens"] += generated > 0

        note = SOLVER_TOKENS.search(str(run.get("solver_note") or ""))
        if note:
            solver_note_tokens += int(note.group(1))
            solver_note_count += 1

    summary_match = TOKEN_TOTAL.search(summary_text)
    summary_tokens = int(summary_match.group(1).replace(",", "")) if summary_match else None
    started = datetime.fromisoformat(benchmark["start_time"])
    ended = datetime.fromisoformat(benchmark["end_time"])
    job_seconds = (ended - started).total_seconds()
    if job_seconds < 0:
        raise ValueError("benchmark end_time precedes start_time")

    return {
        "run_count": len(runs),
        "event_history_aligned_runs": matched_runs,
        "action_count": history_count,
        "action_limit": max_actions,
        "termination_groups": {name: _group_summary(group) for name, group in groups.items()},
        "public_level_depth": [
            {
                "depth": depth,
                **{
                    **stats,
                    "mean_generated_tokens_per_action": round(
                        stats["generated_tokens_total"] / stats["action_count"], 2
                    ),
                },
            }
            for depth, stats in sorted(depth_stats.items())
        ],
        "telemetry": {
            "generated_tokens_total": all_generated_tokens,
            "summary_reported_tokens": summary_tokens,
            "generated_tokens_match_summary": (
                all_generated_tokens == summary_tokens if summary_tokens is not None else None
            ),
            "solver_note_tokens_total": solver_note_tokens if solver_note_count else None,
            "solver_note_count": solver_note_count,
            "solver_note_minus_history_tokens": (
                solver_note_tokens - all_generated_tokens if solver_note_count else None
            ),
            "uncached_input_tokens_total": all_input_tokens,
            "uncached_input_tokens_nonzero_actions": nonzero_input_actions,
            "wallclock_observation_count": history_count,
            "wallclock_field_max_seconds": round(max_wallclock, 3),
            "benchmark_elapsed_seconds": round(job_seconds, 3),
            "wallclock_max_minus_benchmark_elapsed_seconds": round(max_wallclock - job_seconds, 3),
            "wallclock_used_as_per_action_latency": False,
        },
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Create anonymous ARC3 public benchmark token-by-depth aggregates"
    )
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--events", type=Path, required=True)
    parser.add_argument("--summary", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--max-actions", type=int, default=80)
    parser.add_argument("--expected-runs", type=int, default=25)
    args = parser.parse_args()

    benchmark = json.loads(args.benchmark.read_text(encoding="utf-8"))
    result = audit_token_depth(
        benchmark,
        args.events,
        args.summary.read_text(encoding="utf-8"),
        max_actions=args.max_actions,
    )
    if result["run_count"] != args.expected_runs:
        raise ValueError(f"expected {args.expected_runs} runs")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
