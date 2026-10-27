from __future__ import annotations

import argparse
import hashlib
import json
import re
from datetime import datetime
from pathlib import Path
from typing import Any

WALLCLOCK = re.compile(r"^total wallclock:\s*([0-9.]+)s\s*$", re.MULTILINE)
TOKENS = re.compile(r"^total tokens:\s*([0-9,]+)\s*$", re.MULTILINE)
SOLVER_TOKENS = re.compile(r"(?:^|\s)tokens=(\d+)(?:\s|$)")


def _summary_value(pattern: re.Pattern[str], text: str) -> float | int | None:
    match = pattern.search(text)
    if match is None:
        return None
    value = match.group(1).replace(",", "")
    return float(value) if pattern is WALLCLOCK else int(value)


def audit_benchmark(data: dict[str, Any], summary: str = "") -> dict[str, Any]:
    """Compare job duration with cumulative per-run clocks and token counters."""
    started = datetime.fromisoformat(data["start_time"])
    ended = datetime.fromisoformat(data["end_time"])
    job_seconds = (ended - started).total_seconds()
    if job_seconds < 0:
        raise ValueError("benchmark end_time precedes start_time")

    runs = []
    previous_clock = 0.0
    cumulative_clocks = []
    history_total = 0
    solver_total = 0
    solver_count = 0
    final_token_total = 0
    for run in data.get("game_runs", []):
        clock = run.get("final_wallclock_seconds")
        elapsed = None
        if clock is not None:
            clock = float(clock)
            if clock < previous_clock:
                raise ValueError("final_wallclock_seconds must be cumulative and nondecreasing")
            elapsed = clock - previous_clock
            previous_clock = clock
            cumulative_clocks.append(clock)

        history = run.get("history", [])
        history_tokens = sum(int(item.get("generated_tokens", 0) or 0) for item in history)
        history_total += history_tokens
        match = SOLVER_TOKENS.search(str(run.get("solver_note") or ""))
        solver_tokens = int(match.group(1)) if match else None
        if solver_tokens is not None:
            solver_total += solver_tokens
            solver_count += 1
        final_tokens = int(run.get("final_generated_tokens", 0) or 0)
        final_token_total += final_tokens
        runs.append(
            {
                "game_id": run.get("game_id"),
                "state": run.get("state"),
                "levels_completed": run.get("levels_completed"),
                "actions_in_history": len(history),
                "history_generated_tokens": history_tokens,
                "solver_note_tokens": solver_tokens,
                "solver_note_minus_history_tokens": (
                    solver_tokens - history_tokens if solver_tokens is not None else None
                ),
                "final_generated_tokens_field": final_tokens,
                "cumulative_wallclock_seconds": clock,
                "elapsed_since_previous_game_seconds": elapsed,
            }
        )

    reported_clock = _summary_value(WALLCLOCK, summary)
    reported_tokens = _summary_value(TOKENS, summary)
    cumulative_sum = sum(cumulative_clocks)
    return {
        "benchmark_label": data.get("label"),
        "start_time": data["start_time"],
        "end_time": data["end_time"],
        "job_elapsed_seconds": job_seconds,
        "run_count": len(runs),
        "game_runs": runs,
        "total_history_generated_tokens": history_total,
        "total_solver_note_tokens": solver_total if solver_count else None,
        "solver_note_count": solver_count,
        "total_final_generated_tokens_field": final_token_total,
        "sum_of_cumulative_wallclocks_seconds": cumulative_sum,
        "summary_reported_total_wallclock_seconds": reported_clock,
        "summary_reported_total_tokens": reported_tokens,
        "summary_wallclock_matches_job_elapsed_1s_tolerance": (
            abs(reported_clock - job_seconds) <= 1.0 if reported_clock is not None else None
        ),
        "summary_wallclock_matches_cumulative_sum_0_11s_tolerance": (
            abs(reported_clock - cumulative_sum) <= 0.11 if reported_clock is not None else None
        ),
        "summary_tokens_match_history_1_token_tolerance": (
            abs(reported_tokens - history_total) <= 1 if reported_tokens is not None else None
        ),
    }


def verify_manifest(root: Path, manifest: Path) -> dict[str, Any]:
    root = root.resolve()
    checked = 0
    failures = []
    for line_number, line in enumerate(manifest.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        parts = line.split(None, 1)
        if len(parts) != 2 or not re.fullmatch(r"[0-9a-fA-F]{64}", parts[0]):
            failures.append({"line": line_number, "reason": "invalid manifest row"})
            continue
        expected, relative_name = parts
        target = (root / relative_name.replace("/", "\\")).resolve()
        if target != root and root not in target.parents:
            failures.append({"file": relative_name, "reason": "path escapes output root"})
            continue
        if not target.is_file():
            failures.append({"file": relative_name, "reason": "file missing"})
            continue
        digest = hashlib.sha256()
        with target.open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        checked += 1
        if digest.hexdigest().lower() != expected.lower():
            failures.append({"file": relative_name, "reason": "sha256 mismatch"})
    return {"checked_files": checked, "failures": failures, "all_match": not failures}


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit ARC3 benchmark clocks and token telemetry")
    parser.add_argument("--benchmark", type=Path, required=True)
    parser.add_argument("--summary", type=Path)
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()

    data = json.loads(args.benchmark.read_text(encoding="utf-8"))
    summary = args.summary.read_text(encoding="utf-8") if args.summary else ""
    result = audit_benchmark(data, summary)
    if args.manifest:
        result["output_manifest"] = verify_manifest(args.benchmark.parent, args.manifest)
    rendered = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())