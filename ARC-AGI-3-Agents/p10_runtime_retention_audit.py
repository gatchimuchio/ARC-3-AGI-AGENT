"""Audit HDS-closed-cycle retention against a retained P10 worker."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from arc3_agi_agent.p10_evidence import stable_p10_run
from arc3_agi_agent.schema import digest_object

P10_RUNTIME_RETENTION_AUDIT_SCHEMA_VERSION = (
    "arc3-p10-runtime-retention-audit-v1"
)
_TIME_PATTERN = re.compile(
    r"elapsed=(?P<elapsed>[0-9.]+) "
    r"max_rss_kb=(?P<rss>[0-9]+)"
    r"(?: swaps=(?P<swaps>[0-9]+))?"
    r"(?: exit=(?P<exit>[0-9]+))?"
)


def _integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    return value


def _json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def _unwrap_report(value: Mapping[str, Any]) -> dict[str, Any]:
    nested = value.get("single_game_report")
    if isinstance(nested, Mapping):
        return dict(nested)
    return dict(value)


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _descriptor(path: Path, repository_root: Path) -> dict[str, object]:
    return {
        "path": path.resolve().relative_to(
            repository_root.resolve()
        ).as_posix(),
        "sha256": _sha256(path),
        "bytes": path.stat().st_size,
    }


def _timing(path: Path, repository_root: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    match = _TIME_PATTERN.search(text)
    if match is None:
        raise ValueError(f"P10_RUNTIME_TIMING_INVALID:{path}")
    swaps = match.group("swaps")
    exit_code = match.group("exit")
    return {
        **_descriptor(path, repository_root),
        "elapsed_wall_seconds": float(match.group("elapsed")),
        "maximum_rss_kb": int(match.group("rss")),
        "swaps": None if swaps is None else int(swaps),
        "exit_code": None if exit_code is None else int(exit_code),
    }


def _agent_behavior_projection(
    value: Mapping[str, Any],
) -> dict[str, object]:
    stable = stable_p10_run(value)
    raw_reports = stable.get("reports")
    if not isinstance(raw_reports, Sequence) or isinstance(
        raw_reports,
        (str, bytes, bytearray),
    ):
        raise TypeError("P10_RUNTIME_REPORTS_INVALID")
    reports: list[dict[str, object]] = []
    for raw in raw_reports:
        if not isinstance(raw, Mapping):
            raise TypeError("P10_RUNTIME_GAME_REPORT_INVALID")
        report = copy.deepcopy(dict(raw))
        report.pop("development_transition_probe", None)
        reports.append(report)
    stable["reports"] = reports
    return stable


def build_runtime_retention_audit(
    *,
    baseline_report: Mapping[str, Any],
    fresh_report: Mapping[str, Any],
    baseline_report_descriptor: Mapping[str, object],
    fresh_report_descriptor: Mapping[str, object],
    baseline_timing: Mapping[str, object],
    fresh_timing: Mapping[str, object],
    high_water_threshold_kb: int = 1_048_576,
) -> dict[str, object]:
    """Prove behavior equality and bounded fresh-worker retention."""

    if high_water_threshold_kb < 1:
        raise ValueError("P10_RUNTIME_HIGH_WATER_THRESHOLD_INVALID")
    baseline = _agent_behavior_projection(baseline_report)
    fresh = _agent_behavior_projection(fresh_report)
    baseline_reports = baseline["reports"]
    fresh_reports = fresh["reports"]
    if (
        not isinstance(baseline_reports, list)
        or not isinstance(fresh_reports, list)
        or len(baseline_reports) != 1
        or len(fresh_reports) != 1
    ):
        raise ValueError("P10_RUNTIME_SINGLE_GAME_REPORT_REQUIRED")
    baseline_game = baseline_reports[0]
    fresh_game = fresh_reports[0]
    fresh_rss = _integer(
        fresh_timing.get("maximum_rss_kb", -1),
        "maximum_rss_kb",
    )
    fresh_swaps = fresh_timing.get("swaps")
    checks = {
        "same_game": (
            baseline_game.get("game_id") == fresh_game.get("game_id")
        ),
        "operation_mode_offline": (
            str(fresh.get("operation_mode", "")).casefold() == "offline"
        ),
        "active_hybrid_standard_budget": (
            fresh.get("instruction_variant") == "hybrid"
            and _integer(fresh.get("max_actions", 0), "max_actions")
            == 450
        ),
        "fresh_error_count_zero": (
            _integer(fresh.get("error_count", -1), "error_count") == 0
        ),
        "fresh_action_count_450": (
            _integer(fresh_game.get("actions", 0), "actions") == 450
        ),
        "agent_behavior_projection_equal": baseline == fresh,
        "fresh_worker_below_high_water_threshold": (
            0 < fresh_rss < high_water_threshold_kb
        ),
        "fresh_worker_swap_zero": fresh_swaps == 0,
    }
    failures = sorted(key for key, passed in checks.items() if not passed)
    if failures:
        raise ValueError(
            "P10_RUNTIME_RETENTION_AUDIT_FAILED:" + ",".join(failures)
        )
    body: dict[str, object] = {
        "schema_version": P10_RUNTIME_RETENTION_AUDIT_SCHEMA_VERSION,
        "artifact_type": "p10_hds_closed_cycle_retention_audit",
        "phase": "P10_COMPLETE_ARC3_SAMPLE_SOLVING",
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "work_block": {
            "selected_hypothesis": (
                "H37-hds-closed-cycle-heavy-binding-release"
            ),
            "rejected_hypotheses": [
                "H35-increase-machine-or-parallelism",
                "H36-truncate-audit-trace-or-provenance",
            ],
            "failure_signature": (
                "high-water-runtime-allocation-on-standard-budget"
            ),
        },
        "comparison_contract": {
            "excluded_field": (
                "development_transition_probe shadow telemetry"
            ),
            "retained_fields": (
                "all agent actions, HDS decisions, verification, memory, "
                "trace, rollback, recovery, and level outcomes"
            ),
            "high_water_threshold_kb": high_water_threshold_kb,
        },
        "baseline": {
            "report": dict(baseline_report_descriptor),
            "timing": dict(baseline_timing),
            "behavior_projection_digest": digest_object(baseline),
        },
        "fresh": {
            "report": dict(fresh_report_descriptor),
            "timing": dict(fresh_timing),
            "behavior_projection_digest": digest_object(fresh),
        },
        "checks": checks,
        "hds_judgment": {
            "resource_headroom_status": "PASS",
            "failure_signature_status": "RESOLVED",
            "behavior_regression_status": "PASS",
            "capability_progress_status": "NOT_CLAIMED",
            "score_progress_status": "NOT_CLAIMED",
            "active_p_changed": False,
            "runtime_p_promotion_authorized": False,
            "p10_status": "HOLD",
            "p11_status": "GATED",
        },
    }
    return {
        **body,
        "content_digest": (
            "arc3_p10_runtime_retention_audit:" + digest_object(body)
        ),
    }


def write_runtime_retention_audit(
    *,
    baseline_report_path: Path,
    fresh_report_path: Path,
    baseline_timing_path: Path,
    fresh_timing_path: Path,
    repository_root: Path,
    output_path: Path,
    high_water_threshold_kb: int = 1_048_576,
) -> Path:
    value = build_runtime_retention_audit(
        baseline_report=_unwrap_report(
            _json_object(baseline_report_path)
        ),
        fresh_report=_unwrap_report(_json_object(fresh_report_path)),
        baseline_report_descriptor=_descriptor(
            baseline_report_path,
            repository_root,
        ),
        fresh_report_descriptor=_descriptor(
            fresh_report_path,
            repository_root,
        ),
        baseline_timing=_timing(
            baseline_timing_path,
            repository_root,
        ),
        fresh_timing=_timing(fresh_timing_path, repository_root),
        high_water_threshold_kb=high_water_threshold_kb,
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return output_path


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Audit P10 HDS-closed-cycle runtime retention."
    )
    parser.add_argument("--baseline-report", type=Path, required=True)
    parser.add_argument("--fresh-report", type=Path, required=True)
    parser.add_argument("--baseline-timing", type=Path, required=True)
    parser.add_argument("--fresh-timing", type=Path, required=True)
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--high-water-threshold-kb",
        type=int,
        default=1_048_576,
    )
    return parser


def main() -> int:
    args = _parser().parse_args()
    output = write_runtime_retention_audit(
        baseline_report_path=args.baseline_report,
        fresh_report_path=args.fresh_report,
        baseline_timing_path=args.baseline_timing,
        fresh_timing_path=args.fresh_timing,
        repository_root=args.repository_root,
        output_path=args.output,
        high_water_threshold_kb=args.high_water_threshold_kb,
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "P10_RUNTIME_RETENTION_AUDIT_SCHEMA_VERSION",
    "build_runtime_retention_audit",
    "write_runtime_retention_audit",
]
