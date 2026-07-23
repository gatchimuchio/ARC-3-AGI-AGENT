"""Build deterministic P10 evidence from OFFLINE runner reports."""

from __future__ import annotations

import argparse
import copy
import json
from collections.abc import Mapping, Sequence
from pathlib import Path

from .schema import digest_object

P10_EVIDENCE_SCHEMA_VERSION = "arc3-p10-execution-evidence-v1"
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


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build stable P10 P-A/P-B/hybrid execution evidence."
    )
    parser.add_argument("--p-a-report", type=Path, required=True)
    parser.add_argument("--p-b-report", type=Path, required=True)
    parser.add_argument("--hybrid-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    path = write_p10_variant_evidence(
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
    "P10_EVIDENCE_SCHEMA_VERSION",
    "P10_VARIANTS",
    "build_p10_variant_evidence",
    "main",
    "stable_p10_run",
    "write_p10_variant_evidence",
]
