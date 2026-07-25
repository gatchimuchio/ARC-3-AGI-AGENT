"""Build deterministic P10 evidence from OFFLINE runner reports."""

from __future__ import annotations

import argparse
import copy
import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from .schema import digest_object

P10_EVIDENCE_SCHEMA_VERSION = "arc3-p10-execution-evidence-v1"
P10_COMPACT_EVIDENCE_SCHEMA_VERSION = (
    "arc3-p10-compact-execution-evidence-v1"
)
P10_COMPACT_RUN_EVIDENCE_SCHEMA_VERSION = (
    "arc3-p10-compact-run-evidence-v1"
)
P10_VARIANTS = ("P-A", "P-B", "hybrid")
_TOP_LEVEL_FIELDS = (
    "phase",
    "operation_mode",
    "environment_count",
    "completed_count",
    "complete_game_count",
    "completed_levels",
    "total_levels",
    "all_complete",
    "error_count",
    "max_actions",
    "instruction_variant",
    "reports",
    "errors",
)


def _mapping(value: object, field_name: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be an object")
    return value


def _integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    return value


def _reports(value: object) -> tuple[Mapping[str, object], ...]:
    if not isinstance(value, Sequence) or isinstance(
        value,
        (str, bytes, bytearray),
    ):
        raise TypeError("P10 reports must be an array")
    return tuple(_mapping(report, "P10 game report") for report in value)


def stable_p10_run(value: Mapping[str, object]) -> dict[str, object]:
    """Remove local scorecard identity while retaining every agent trace."""

    missing = [field for field in _TOP_LEVEL_FIELDS if field not in value]
    if missing:
        raise ValueError("P10_REPORT_FIELDS_MISSING:" + ",".join(missing))
    if value["phase"] != "P10":
        raise ValueError("P10_REPORT_PHASE_INVALID")
    if str(value["operation_mode"]).casefold() != "offline":
        raise ValueError("P10_REPORT_NON_OFFLINE")
    reports = value["reports"]
    errors = value["errors"]
    if (
        not isinstance(reports, Sequence)
        or isinstance(reports, (str, bytes, bytearray))
        or not isinstance(errors, Sequence)
        or isinstance(errors, (str, bytes, bytearray))
    ):
        raise TypeError("P10_REPORT_COLLECTION_INVALID")
    stable = {
        field: copy.deepcopy(value[field])
        for field in _TOP_LEVEL_FIELDS
        if field not in {"reports", "errors"}
    }
    stable["reports"] = sorted(
        (
            dict(_mapping(report, "P10 game report"))
            for report in reports
        ),
        key=lambda report: str(report.get("game_id", "")),
    )
    stable["errors"] = sorted(
        (
            dict(_mapping(error, "P10 error"))
            for error in errors
        ),
        key=lambda error: (
            str(error.get("game_id", "")),
            str(error.get("error_type", "")),
            str(error.get("message", "")),
        ),
    )
    return stable


def build_p10_variant_evidence(
    runs: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    """Bind P-A/P-B/hybrid runs under identical observable conditions."""

    if tuple(sorted(runs)) != tuple(sorted(P10_VARIANTS)):
        raise ValueError("P10_EVIDENCE_REQUIRES_ALL_VARIANTS")
    stable_runs = {
        variant: stable_p10_run(runs[variant])
        for variant in P10_VARIANTS
    }
    conditions = {
        (
            _integer(run["max_actions"], "max_actions"),
            tuple(
                str(report.get("game_id", ""))
                for report in _reports(run["reports"])
            ),
            _integer(run["environment_count"], "environment_count"),
            _integer(run["total_levels"], "total_levels"),
        )
        for run in stable_runs.values()
    }
    if len(conditions) != 1:
        raise ValueError("P10_VARIANT_CONDITIONS_DIFFER")
    for variant, run in stable_runs.items():
        if run["instruction_variant"] != variant:
            raise ValueError("P10_VARIANT_LABEL_MISMATCH")

    condition = next(iter(conditions))
    summaries: dict[str, object] = {}
    encoded_runs: dict[str, object] = {}
    for variant in P10_VARIANTS:
        run = stable_runs[variant]
        summaries[variant] = {
            "all_complete": run["all_complete"],
            "complete_game_count": run["complete_game_count"],
            "completed_levels": run["completed_levels"],
            "error_count": run["error_count"],
            "max_action_exhausted_count": sum(
                int(bool(report.get("max_action_exhausted")))
                for report in _reports(run["reports"])
            ),
            "action_count": sum(
                _integer(report.get("actions", 0), "actions")
                for report in _reports(run["reports"])
            ),
            "stable_run_digest": digest_object(run),
        }
        encoded_runs[variant] = run
    core: dict[str, object] = {
        "schema_version": P10_EVIDENCE_SCHEMA_VERSION,
        "operation_mode": "offline",
        "conditions": {
            "max_actions": condition[0],
            "game_ids": list(condition[1]),
            "environment_count": condition[2],
            "total_levels": condition[3],
        },
        "variant_summaries": summaries,
        "stable_runs": encoded_runs,
    }
    return {
        **core,
        "content_digest": digest_object(core),
    }


def compact_p10_run(value: Mapping[str, object]) -> dict[str, object]:
    """Bind complete traces without duplicating every trace event.

    The compact projection retains the emitted action, provenance, level
    transition, and per-cycle trace digest.  It also binds the omitted trace
    event bodies under ``trace_events_digest`` so a retained raw report can be
    checked independently.
    """

    stable = stable_p10_run(value)
    compact_reports: list[dict[str, object]] = []
    for report in _reports(stable["reports"]):
        trace_events = report.get("trace_events", ())
        if not isinstance(trace_events, Sequence) or isinstance(
            trace_events,
            (str, bytes, bytearray),
        ):
            raise TypeError("P10_TRACE_EVENTS_INVALID")
        compact_report: dict[str, object] = {
                "game_id": str(report.get("game_id", "")),
                "actions": _integer(report.get("actions"), "actions"),
                "recoveries": _integer(
                    report.get("recoveries"),
                    "recoveries",
                ),
                "search_resets": _integer(
                    report.get("search_resets"),
                    "search_resets",
                ),
                "levels_completed": _integer(
                    report.get("levels_completed"),
                    "levels_completed",
                ),
                "win_levels": _integer(
                    report.get("win_levels"),
                    "win_levels",
                ),
                "terminal_state": str(report.get("terminal_state", "")),
                "final_status": str(report.get("final_status", "")),
                "complete": bool(report.get("complete")),
                "max_action_exhausted": bool(
                    report.get("max_action_exhausted")
                ),
                "memory_version": _integer(
                    report.get("memory_version"),
                    "memory_version",
                ),
                "memory_influenced_cycle_count": _integer(
                    report.get("memory_influenced_cycle_count"),
                    "memory_influenced_cycle_count",
                ),
                "visual_operator_version": str(
                    report.get("visual_operator_version", "")
                ),
                "instruction_body_formats": copy.deepcopy(
                    report.get("instruction_body_formats", ())
                ),
                "instruction_body_versions": copy.deepcopy(
                    report.get("instruction_body_versions", ())
                ),
                "instruction_body_digests": copy.deepcopy(
                    report.get("instruction_body_digests", ())
                ),
                "instruction_query_digests": copy.deepcopy(
                    report.get("instruction_query_digests", ())
                ),
                "decision_statuses": copy.deepcopy(
                    report.get("decision_statuses", ())
                ),
                "verification_statuses": copy.deepcopy(
                    report.get("verification_statuses", ())
                ),
                "emitted_steps": copy.deepcopy(
                    report.get("emitted_steps", ())
                ),
                "emitted_provenance": copy.deepcopy(
                    report.get("emitted_provenance", ())
                ),
                "emitted_level_counts": copy.deepcopy(
                    report.get("emitted_level_counts", ())
                ),
                "trace_digests": copy.deepcopy(
                    report.get("trace_digests", ())
                ),
                "trace_cycle_count": len(trace_events),
                "trace_events_digest": digest_object(trace_events),
                "rollback_decision_ids": copy.deepcopy(
                    report.get("rollback_decision_ids", ())
                ),
                "rollback_memory_versions": copy.deepcopy(
                    report.get("rollback_memory_versions", ())
                ),
                "failure_payload_digests": copy.deepcopy(
                    report.get("failure_payload_digests", ())
                ),
                "search_reset_decision_ids": copy.deepcopy(
                    report.get("search_reset_decision_ids", ())
                ),
                "search_reset_memory_versions": copy.deepcopy(
                    report.get("search_reset_memory_versions", ())
                ),
                "search_reset_payload_digests": copy.deepcopy(
                    report.get("search_reset_payload_digests", ())
                ),
                "search_reset_evidence_signatures": copy.deepcopy(
                    report.get("search_reset_evidence_signatures", ())
                ),
        }
        transition_probe = report.get("development_transition_probe")
        if transition_probe is not None:
            if not isinstance(transition_probe, Mapping):
                raise TypeError("P10_TRANSITION_PROBE_INVALID")
            compact_report["development_transition_probe"] = (
                copy.deepcopy(dict(transition_probe))
            )
        compact_reports.append(compact_report)
    return {
        field: copy.deepcopy(stable[field])
        for field in _TOP_LEVEL_FIELDS
        if field not in {"reports", "errors"}
    } | {
        "reports": compact_reports,
        "errors": copy.deepcopy(stable["errors"]),
    }


def build_p10_compact_variant_evidence(
    runs: Mapping[str, Mapping[str, object]],
) -> dict[str, object]:
    """Build a content-bound compact P-A/P-B/hybrid comparison."""

    if tuple(sorted(runs)) != tuple(sorted(P10_VARIANTS)):
        raise ValueError("P10_EVIDENCE_REQUIRES_ALL_VARIANTS")
    compact_runs = {
        variant: compact_p10_run(runs[variant])
        for variant in P10_VARIANTS
    }
    conditions = {
        (
            _integer(run["max_actions"], "max_actions"),
            tuple(
                str(report.get("game_id", ""))
                for report in _reports(run["reports"])
            ),
            _integer(run["environment_count"], "environment_count"),
            _integer(run["total_levels"], "total_levels"),
        )
        for run in compact_runs.values()
    }
    if len(conditions) != 1:
        raise ValueError("P10_VARIANT_CONDITIONS_DIFFER")
    for variant, run in compact_runs.items():
        if run["instruction_variant"] != variant:
            raise ValueError("P10_VARIANT_LABEL_MISMATCH")

    condition = next(iter(conditions))
    summaries: dict[str, object] = {}
    for variant in P10_VARIANTS:
        run = compact_runs[variant]
        summaries[variant] = {
            "all_complete": run["all_complete"],
            "complete_game_count": run["complete_game_count"],
            "completed_levels": run["completed_levels"],
            "error_count": run["error_count"],
            "max_action_exhausted_count": sum(
                int(bool(report.get("max_action_exhausted")))
                for report in _reports(run["reports"])
            ),
            "action_count": sum(
                _integer(report.get("actions", 0), "actions")
                for report in _reports(run["reports"])
            ),
            "compact_run_digest": digest_object(run),
        }
    core: dict[str, object] = {
        "schema_version": P10_COMPACT_EVIDENCE_SCHEMA_VERSION,
        "operation_mode": "offline",
        "conditions": {
            "max_actions": condition[0],
            "game_ids": list(condition[1]),
            "environment_count": condition[2],
            "total_levels": condition[3],
        },
        "variant_summaries": summaries,
        "compact_runs": compact_runs,
    }
    return {
        **core,
        "content_digest": digest_object(core),
    }


def build_p10_compact_run_evidence(
    value: Mapping[str, object],
) -> dict[str, object]:
    """Build a content-bound compact certificate for one runner invocation."""

    compact = compact_p10_run(value)
    reports = _reports(compact["reports"])
    core: dict[str, object] = {
        "schema_version": P10_COMPACT_RUN_EVIDENCE_SCHEMA_VERSION,
        "operation_mode": "offline",
        "conditions": {
            "max_actions": _integer(
                compact["max_actions"],
                "max_actions",
            ),
            "game_ids": [
                str(report.get("game_id", "")) for report in reports
            ],
            "environment_count": _integer(
                compact["environment_count"],
                "environment_count",
            ),
            "total_levels": _integer(
                compact["total_levels"],
                "total_levels",
            ),
            "instruction_variant": str(
                compact["instruction_variant"]
            ),
        },
        "summary": {
            "all_complete": compact["all_complete"],
            "complete_game_count": compact["complete_game_count"],
            "completed_levels": compact["completed_levels"],
            "error_count": compact["error_count"],
            "max_action_exhausted_count": sum(
                int(bool(report.get("max_action_exhausted")))
                for report in reports
            ),
            "action_count": sum(
                _integer(report.get("actions", 0), "actions")
                for report in reports
            ),
            "compact_run_digest": digest_object(compact),
        },
        "compact_run": compact,
    }
    return {
        **core,
        "content_digest": digest_object(core),
    }


def _load(path: Path) -> Mapping[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    return _mapping(value, str(path))


def write_p10_variant_evidence(
    *,
    p_a_report: Path,
    p_b_report: Path,
    hybrid_report: Path,
    output_path: Path,
) -> Path:
    evidence = build_p10_variant_evidence(
        {
            "P-A": _load(p_a_report),
            "P-B": _load(p_b_report),
            "hybrid": _load(hybrid_report),
        }
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            evidence,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return output_path


def write_p10_compact_variant_evidence(
    *,
    p_a_report: Path,
    p_b_report: Path,
    hybrid_report: Path,
    output_path: Path,
) -> Path:
    evidence = build_p10_compact_variant_evidence(
        {
            "P-A": _load(p_a_report),
            "P-B": _load(p_b_report),
            "hybrid": _load(hybrid_report),
        }
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            evidence,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return output_path


def write_p10_compact_run_evidence(
    *,
    report: Path,
    output_path: Path,
) -> Path:
    evidence = build_p10_compact_run_evidence(_load(report))
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(
            evidence,
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
        description="Build stable P10 P-A/P-B/hybrid execution evidence."
    )
    parser.add_argument("--single-report", type=Path)
    parser.add_argument("--p-a-report", type=Path)
    parser.add_argument("--p-b-report", type=Path)
    parser.add_argument("--hybrid-report", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--compact",
        action="store_true",
        help="retain trace roots and emissions without duplicating trace bodies",
    )
    return parser


def main() -> int:
    parser = _parser()
    args = parser.parse_args()
    variant_paths = (
        args.p_a_report,
        args.p_b_report,
        args.hybrid_report,
    )
    if args.single_report is not None:
        if any(path is not None for path in variant_paths):
            parser.error(
                "--single-report cannot be combined with variant reports"
            )
        path = write_p10_compact_run_evidence(
            report=args.single_report,
            output_path=args.output,
        )
        print(path)
        return 0
    if any(path is None for path in variant_paths):
        parser.error(
            "provide --single-report or all three variant reports"
        )
    if (
        args.p_a_report is None
        or args.p_b_report is None
        or args.hybrid_report is None
    ):
        raise AssertionError("argparse variant validation failed")
    writer = (
        write_p10_compact_variant_evidence
        if args.compact
        else write_p10_variant_evidence
    )
    path = writer(
        p_a_report=args.p_a_report,
        p_b_report=args.p_b_report,
        hybrid_report=args.hybrid_report,
        output_path=args.output,
    )
    print(path)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "P10_COMPACT_EVIDENCE_SCHEMA_VERSION",
    "P10_COMPACT_RUN_EVIDENCE_SCHEMA_VERSION",
    "P10_EVIDENCE_SCHEMA_VERSION",
    "P10_VARIANTS",
    "build_p10_compact_run_evidence",
    "build_p10_compact_variant_evidence",
    "build_p10_variant_evidence",
    "compact_p10_run",
    "main",
    "stable_p10_run",
    "write_p10_compact_run_evidence",
    "write_p10_compact_variant_evidence",
    "write_p10_variant_evidence",
]
