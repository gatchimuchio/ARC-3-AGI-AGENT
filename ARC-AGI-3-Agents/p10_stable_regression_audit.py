"""Build a content-bound P10 visual-operator stable-regression audit.

This development-only tool compares a retained HDS-admitted report with a
fresh report.  It excludes only source-state signatures and digests that are
expected to change when the visual-state identity format changes; emitted
actions, HDS statuses, level transitions, memory influence, rollback, and
recovery behavior remain in the compared projection.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from arc3_agi_agent.p10_evidence import build_p10_compact_run_evidence
from arc3_agi_agent.schema import digest_object

_TIME_PATTERN = re.compile(
    r"elapsed=(?P<elapsed>[0-9.]+) "
    r"max_rss_kb=(?P<rss>[0-9]+) "
    r"exit=(?P<exit>[0-9]+)"
)
_VISUAL_OPERATOR_PREFIX = "arc3-p10-visual-operator-v"


def _integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    return value


def _boolean(value: object, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise TypeError(f"{field_name} must be boolean")
    return value


def _load_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"JSON_OBJECT_REQUIRED:{path}")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _relative(path: Path, repository_root: Path) -> str:
    return path.resolve().relative_to(repository_root.resolve()).as_posix()


def _descriptor(path: Path, repository_root: Path) -> dict[str, object]:
    return {
        "path": _relative(path, repository_root),
        "sha256": _sha256(path),
        "bytes": path.stat().st_size,
    }


def _compact_evidence(value: Mapping[str, Any]) -> dict[str, Any]:
    compact = value.get("compact_run")
    if isinstance(compact, Mapping):
        return dict(value)
    return build_p10_compact_run_evidence(value)


def _single_report(value: Mapping[str, Any]) -> dict[str, Any]:
    compact = value.get("compact_run")
    if not isinstance(compact, Mapping):
        raise TypeError("COMPACT_RUN_REQUIRED")
    reports = compact.get("reports")
    if (
        not isinstance(reports, Sequence)
        or isinstance(reports, (str, bytes, bytearray))
        or len(reports) != 1
        or not isinstance(reports[0], Mapping)
    ):
        raise ValueError("SINGLE_COMPACT_REPORT_REQUIRED")
    return dict(reports[0])


def _normalize_step(value: object) -> object:
    if isinstance(value, Mapping):
        return {
            str(key): _normalize_step(item)
            for key, item in value.items()
            if str(key) != "visual_source_signature"
        }
    if isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        return [_normalize_step(item) for item in value]
    return value


def _normalize_provenance(value: object) -> object:
    if isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        return [
            _normalize_provenance(item)
            for item in value
            if not (
                isinstance(item, str)
                and (
                    item.startswith(_VISUAL_OPERATOR_PREFIX)
                    or item.startswith("query:")
                )
            )
        ]
    return value


def _behavior_projection(report: Mapping[str, Any]) -> dict[str, object]:
    scalar_fields = (
        "game_id",
        "actions",
        "recoveries",
        "search_resets",
        "levels_completed",
        "win_levels",
        "terminal_state",
        "final_status",
        "complete",
        "max_action_exhausted",
        "memory_version",
        "memory_influenced_cycle_count",
    )
    sequence_fields = (
        "instruction_body_formats",
        "decision_statuses",
        "verification_statuses",
        "emitted_level_counts",
        "rollback_decision_ids",
        "rollback_memory_versions",
        "failure_payload_digests",
        "search_reset_decision_ids",
        "search_reset_memory_versions",
        "search_reset_payload_digests",
        "search_reset_evidence_signatures",
    )
    projection: dict[str, object] = {
        field: report.get(field) for field in scalar_fields
    }
    projection.update(
        {field: report.get(field, []) for field in sequence_fields}
    )
    projection["emitted_steps"] = _normalize_step(
        report.get("emitted_steps", [])
    )
    projection["emitted_provenance"] = _normalize_provenance(
        report.get("emitted_provenance", [])
    )
    return projection


def _timing(path: Path, repository_root: Path) -> dict[str, object]:
    text = path.read_text(encoding="utf-8")
    match = _TIME_PATTERN.search(text)
    if match is None:
        raise ValueError(f"TIMING_RECORD_INVALID:{path}")
    return {
        **_descriptor(path, repository_root),
        "elapsed_wall_seconds": float(match.group("elapsed")),
        "maximum_rss_kb": int(match.group("rss")),
        "exit_code": int(match.group("exit")),
    }


def _parse_comparison(
    value: str,
) -> tuple[str, Path, Path, Path]:
    parts = value.split(":", 3)
    if len(parts) != 4 or not parts[0]:
        raise ValueError(
            "COMPARISON_REQUIRES_LABEL:BASELINE:FRESH:TIMING"
        )
    return parts[0], Path(parts[1]), Path(parts[2]), Path(parts[3])


def build_audit(
    *,
    comparisons: Sequence[tuple[str, Path, Path, Path]],
    repository_root: Path,
    runtime_source_inventory_digest: str,
    active_manifest_digest: str,
) -> dict[str, object]:
    rows: list[dict[str, object]] = []
    checks: dict[str, bool] = {}
    for label, baseline_path, fresh_path, timing_path in comparisons:
        baseline_value = _load_object(baseline_path)
        fresh_value = _load_object(fresh_path)
        baseline = _compact_evidence(baseline_value)
        fresh = _compact_evidence(fresh_value)
        baseline_report = _single_report(baseline)
        fresh_report = _single_report(fresh)
        baseline_projection = _behavior_projection(baseline_report)
        fresh_projection = _behavior_projection(fresh_report)
        projection_equal = baseline_projection == fresh_projection
        fresh_run = fresh.get("compact_run")
        if not isinstance(fresh_run, Mapping):
            raise TypeError("FRESH_COMPACT_RUN_REQUIRED")
        error_count = int(fresh_run.get("error_count", -1))
        complete = bool(fresh_report.get("complete"))
        timing = _timing(timing_path, repository_root)
        exit_matches = timing["exit_code"] == (0 if complete else 1)
        checks[f"{label}_behavior_projection_equal"] = projection_equal
        checks[f"{label}_fresh_error_count_zero"] = error_count == 0
        checks[f"{label}_exit_matches_completion"] = exit_matches
        rows.append(
            {
                "label": label,
                "game_id": str(fresh_report.get("game_id", "")),
                "baseline_evidence": _descriptor(
                    baseline_path,
                    repository_root,
                ),
                "fresh_report": _descriptor(
                    fresh_path,
                    repository_root,
                ),
                "timing": timing,
                "baseline_visual_operator_version": str(
                    baseline_report.get("visual_operator_version", "")
                ),
                "fresh_visual_operator_version": str(
                    fresh_report.get("visual_operator_version", "")
                ),
                "behavior_projection_equal": projection_equal,
                "behavior_projection_digest": digest_object(
                    fresh_projection
                ),
                "actions": int(fresh_report.get("actions", 0)),
                "completed_levels": int(
                    fresh_report.get("levels_completed", 0)
                ),
                "total_levels": int(
                    fresh_report.get("win_levels", 0)
                ),
                "complete": complete,
                "terminal_state": str(
                    fresh_report.get("terminal_state", "")
                ),
                "error_count": error_count,
                "memory_influenced_cycle_count": int(
                    fresh_report.get(
                        "memory_influenced_cycle_count",
                        0,
                    )
                ),
            }
        )
    body: dict[str, object] = {
        "schema_version": "arc3-p10-stable-regression-audit-v1",
        "artifact_type": "p10_visual_operator_stable_regression_audit",
        "phase": "P10_COMPLETE_ARC3_SAMPLE_SOLVING",
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "fixed_conditions": {
            "operation_mode": "offline",
            "instruction_variant": "hybrid",
            "instruction_lifecycle": "active",
            "runtime_source_inventory_digest": (
                runtime_source_inventory_digest
            ),
            "active_manifest_digest": active_manifest_digest,
        },
        "comparison_contract": {
            "included": [
                "emitted action ids and coordinates",
                "visual action keys",
                "HDS decision and verification statuses",
                "level transitions and terminal state",
                "memory influence counts",
                "rollback recovery and search-reset behavior",
                "non-version and non-query visual provenance",
            ],
            "excluded": [
                "visual_source_signature because v14 extends state identity with the available-action surface",
                "visual operator version token",
                "instruction query tokens body digests and trace digests derived from the changed source signature",
            ],
            "exclusion_may_not_hide_action_or_hds_status_change": True,
        },
        "comparisons": rows,
        "checks": checks,
        "summary": {
            "comparison_count": len(rows),
            "behavior_projection_match_count": sum(
                int(
                    _boolean(
                        row["behavior_projection_equal"],
                        "behavior projection equality",
                    )
                )
                for row in rows
            ),
            "error_count": sum(
                _integer(row["error_count"], "comparison error count")
                for row in rows
            ),
            "completed_levels": sum(
                _integer(
                    row["completed_levels"],
                    "comparison completed levels",
                )
                for row in rows
            ),
            "action_count": sum(
                _integer(row["actions"], "comparison actions")
                for row in rows
            ),
        },
        "hds_judgment": {
            "stable_regression_status": (
                "PASS" if checks and all(checks.values()) else "FAIL"
            ),
            "visual_operator_v14_behavioral_equivalence": (
                "PASS" if checks and all(checks.values()) else "FAIL"
            ),
            "capability_progress_status": "NOT_CLAIMED",
            "score_progress_status": "NOT_CLAIMED",
            "runtime_p_compile_authorized": False,
            "runtime_p_promotion_authorized": False,
            "p11_status": "GATED",
        },
    }
    return {
        **body,
        "content_digest": (
            "arc3_p10_stable_regression_audit:" + digest_object(body)
        ),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--comparison",
        action="append",
        required=True,
        help="LABEL:BASELINE:FRESH:TIMING",
    )
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument(
        "--runtime-source-inventory-digest",
        required=True,
    )
    parser.add_argument("--active-manifest-digest", required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    comparisons = [
        _parse_comparison(value) for value in args.comparison
    ]
    audit = build_audit(
        comparisons=comparisons,
        repository_root=args.repository_root,
        runtime_source_inventory_digest=(
            args.runtime_source_inventory_digest
        ),
        active_manifest_digest=args.active_manifest_digest,
    )
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        json.dumps(
            audit,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )
    hds_judgment = audit.get("hds_judgment")
    if not isinstance(hds_judgment, Mapping):
        raise TypeError("HDS_JUDGMENT_REQUIRED")
    return int(hds_judgment.get("stable_regression_status") != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())
