"""Build the development-only C2/C3 CLUSTER_STABLE audit.

The audit consumes shadow telemetry after execution.  It has no import path
into candidate selection, memory mutation, HDS judgment, emission, or Runtime
P promotion.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .cross_cutting_transition import (
    C2_C3_CAPABILITY_IDS,
    C2_C3_PROBE_FORMAT,
    BoundaryLabel,
)
from .p10_evidence import build_p10_compact_run_evidence
from .schema import digest_object, forbidden_runtime_paths

C2_C3_CLUSTER_AUDIT_SCHEMA_VERSION = (
    "arc3-c2-c3-cluster-stable-audit-v1"
)
_BOUNDARY_LABELS: tuple[BoundaryLabel, ...] = (
    "COMMIT",
    "HAZARD",
    "TRANSITION_NO_COMMIT",
    "NO_VISIBLE_COMMIT",
)
_MIN_GAME_SUPPORT = {
    "COMMIT": 3,
    "HAZARD": 3,
    "TRANSITION_NO_COMMIT": 3,
    "NO_VISIBLE_COMMIT": 3,
}
_MIN_STRUCTURE_SUPPORT = {
    "COMMIT": 3,
    "HAZARD": 3,
    "TRANSITION_NO_COMMIT": 3,
    "NO_VISIBLE_COMMIT": 3,
}
_REQUIRED_EFFECT_GAME_SUPPORT = {
    "VISIBLE_STATE_CHANGE": 3,
    "NO_VISIBLE_CHANGE": 3,
    "COMPONENT_MOTION": 3,
    "LOCAL_PIXEL_DELTA": 3,
    "REGIONAL_REDRAW": 2,
    "GLOBAL_REDRAW": 2,
}
_ROLE_BY_BOUNDARY = {
    "COMMIT": "POSITIVE",
    "HAZARD": "HAZARD",
    "TRANSITION_NO_COMMIT": "NEGATIVE",
    "NO_VISIBLE_COMMIT": "NEGATIVE",
}
_OBLIGATION_BY_BOUNDARY = {
    "COMMIT": "REOBSERVE_COMMIT_STATE",
    "HAZARD": "SUSPEND_AND_REQUEST_ROLLBACK",
    "TRANSITION_NO_COMMIT": "REOBSERVE_BEFORE_CONTINUATION",
    "NO_VISIBLE_COMMIT": "WAIT_REOBSERVE_OR_REPLAN",
}


def _json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _rows(value: object, field_name: str) -> list[Mapping[str, Any]]:
    if not isinstance(value, Sequence) or isinstance(
        value,
        (str, bytes, bytearray),
    ):
        raise TypeError(f"{field_name} must be an array")
    rows: list[Mapping[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise TypeError(f"{field_name} rows must be objects")
        rows.append(item)
    return rows


def _strings(value: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(
        value,
        (str, bytes, bytearray),
    ):
        raise TypeError(f"{field_name} must be an array")
    return tuple(str(item) for item in value)


def _expected_boundary(record: Mapping[str, Any]) -> BoundaryLabel:
    terminal_state = str(record.get("terminal_state", ""))
    progress = record.get("progress_observed")
    if not isinstance(progress, bool):
        raise TypeError("progress_observed must be boolean")
    effects = set(_strings(record.get("effect_classes"), "effect_classes"))
    if terminal_state == "GAME_OVER":
        return "HAZARD"
    if progress or terminal_state == "WIN":
        return "COMMIT"
    if "VISIBLE_STATE_CHANGE" in effects:
        return "TRANSITION_NO_COMMIT"
    if "NO_VISIBLE_CHANGE" in effects:
        return "NO_VISIBLE_COMMIT"
    raise ValueError("C2_C3_CLUSTER_VISIBLE_EFFECT_SEPARATOR_MISSING")


def _record_semantics_valid(record: Mapping[str, Any]) -> bool:
    expected = _expected_boundary(record)
    observed = str(record.get("observed_boundary", ""))
    predicted = str(record.get("predicted_boundary", ""))
    effects = set(_strings(record.get("effect_classes"), "effect_classes"))
    visible_separator = (
        ("VISIBLE_STATE_CHANGE" in effects)
        != ("NO_VISIBLE_CHANGE" in effects)
    )
    hazard_separator = (
        expected != "HAZARD"
        or "IRREVERSIBLE_HAZARD" in effects
    )
    commit_separator = (
        expected != "COMMIT"
        or (
            bool(record.get("progress_observed"))
            and "PROGRESS_BOUNDARY" in effects
        )
        or str(record.get("terminal_state", "")) == "WIN"
    )
    return all(
        (
            observed == expected,
            predicted == expected,
            str(record.get("contrast_role", ""))
            == _ROLE_BY_BOUNDARY[expected],
            str(record.get("reobserve_obligation", ""))
            == _OBLIGATION_BY_BOUNDARY[expected],
            visible_separator,
            hazard_separator,
            commit_separator,
            not forbidden_runtime_paths(record),
        )
    )


def build_c2_c3_cluster_audit(
    *,
    raw_report: Mapping[str, Any],
    raw_report_sha256: str,
    compact_evidence: Mapping[str, Any],
    compact_evidence_sha256: str,
) -> dict[str, Any]:
    """Validate all standard-budget C2/C3 contrast records."""

    reports = _rows(raw_report.get("reports"), "reports")
    errors = _rows(raw_report.get("errors"), "errors")
    compact_body = dict(compact_evidence)
    compact_digest = str(compact_body.pop("content_digest", ""))
    compact_digest_valid = compact_digest == digest_object(compact_body)
    compact_matches_raw = (
        dict(compact_evidence)
        == build_p10_compact_run_evidence(raw_report)
    )

    boundary_counts: Counter[str] = Counter()
    role_counts: Counter[str] = Counter()
    effect_counts: Counter[str] = Counter()
    boundary_games: defaultdict[str, set[str]] = defaultdict(set)
    boundary_structures: defaultdict[str, set[str]] = defaultdict(set)
    effect_games: defaultdict[str, set[str]] = defaultdict(set)
    action_boundaries: defaultdict[str, set[str]] = defaultdict(set)
    game_rows: list[dict[str, object]] = []
    all_records_retained = True
    all_semantics_valid = True
    identity_free = True
    action_selection_influence = False
    unauthorized_authority = False
    total_faults = 0
    total_overflow = 0
    total_observations = 0
    total_records = 0
    total_actions = 0
    game_ids: list[str] = []

    for report in reports:
        game_id = str(report.get("game_id", ""))
        game_ids.append(game_id)
        probe = report.get("development_transition_probe")
        if not isinstance(probe, Mapping):
            raise ValueError("C2_C3_CLUSTER_PROBE_MISSING")
        if probe.get("format") != C2_C3_PROBE_FORMAT:
            raise ValueError("C2_C3_CLUSTER_REQUIRES_V2_PROBE")
        records = _rows(
            probe.get("contrast_records"),
            "contrast_records",
        )
        observation_count = int(probe.get("observation_count", -1))
        fault_count = int(probe.get("fault_count", -1))
        overflow_count = sum(
            int(probe.get(field, -1))
            for field in (
                "model_overflow_count",
                "context_overflow_count",
                "contrast_overflow_count",
            )
        )
        total_observations += observation_count
        total_records += len(records)
        total_actions += int(report.get("actions", 0))
        total_faults += fault_count
        total_overflow += overflow_count
        all_records_retained = all_records_retained and (
            len(records) == observation_count
            and [
                int(record.get("ordinal", -1)) for record in records
            ]
            == list(range(1, observation_count + 1))
        )
        game_boundaries: Counter[str] = Counter()
        game_effects: Counter[str] = Counter()
        for record in records:
            semantic_valid = _record_semantics_valid(record)
            all_semantics_valid = all_semantics_valid and semantic_valid
            identity_free = identity_free and (
                not forbidden_runtime_paths(record)
            )
            boundary = str(record.get("observed_boundary", ""))
            structure = str(record.get("source_structure_class", ""))
            action_class = str(record.get("action_class", ""))
            role = str(record.get("contrast_role", ""))
            effects = _strings(
                record.get("effect_classes"),
                "effect_classes",
            )
            boundary_counts[boundary] += 1
            role_counts[role] += 1
            game_boundaries[boundary] += 1
            boundary_games[boundary].add(game_id)
            boundary_structures[boundary].add(structure)
            action_boundaries[action_class].add(boundary)
            for effect in effects:
                effect_counts[effect] += 1
                game_effects[effect] += 1
                effect_games[effect].add(game_id)
        action_selection_influence = action_selection_influence or bool(
            probe.get("action_selection_influence")
        )
        unauthorized_authority = unauthorized_authority or any(
            bool(probe.get(field))
            for field in (
                "memory_write_authority",
                "external_emit_authority",
                "runtime_p_promotion_authority",
            )
        )
        game_rows.append(
            {
                "game_id": game_id,
                "actions": int(report.get("actions", 0)),
                "observations": observation_count,
                "contrast_records": len(records),
                "faults": fault_count,
                "overflow": overflow_count,
                "boundary_counts": dict(sorted(game_boundaries.items())),
                "effect_counts": dict(sorted(game_effects.items())),
            }
        )

    game_rows.sort(key=lambda row: str(row["game_id"]))
    game_ids.sort()
    checkpointing = raw_report.get("checkpointing")
    conditions: Mapping[str, Any] | None = None
    conditions_digest_valid = False
    condition_game_ids: list[str] = []
    if isinstance(checkpointing, Mapping):
        raw_conditions = checkpointing.get("conditions")
        if isinstance(raw_conditions, Mapping):
            conditions = raw_conditions
            conditions_body = dict(raw_conditions)
            claimed = str(
                conditions_body.pop("conditions_digest", "")
            )
            conditions_digest_valid = claimed == digest_object(
                conditions_body
            )
            raw_ids = raw_conditions.get("game_ids")
            if isinstance(raw_ids, Sequence) and not isinstance(
                raw_ids,
                (str, bytes, bytearray),
            ):
                condition_game_ids = sorted(str(item) for item in raw_ids)

    boundary_support = {
        label: {
            "observations": boundary_counts[label],
            "game_count": len(boundary_games[label]),
            "structure_count": len(boundary_structures[label]),
        }
        for label in _BOUNDARY_LABELS
    }
    effect_support = {
        effect: {
            "observations": effect_counts[effect],
            "game_count": len(effect_games[effect]),
        }
        for effect in sorted(effect_counts)
    }
    contrasted_action_classes = {
        action: sorted(labels)
        for action, labels in sorted(action_boundaries.items())
        if len(labels) >= 2
    }
    hazard_separating_action_classes = {
        action: sorted(labels)
        for action, labels in sorted(action_boundaries.items())
        if "HAZARD" in labels and len(labels) >= 2
    }
    checks = {
        "operation_mode_offline": (
            str(raw_report.get("operation_mode", "")).casefold()
            == "offline"
        ),
        "instruction_lifecycle_active": (
            raw_report.get("instruction_lifecycle") == "active"
        ),
        "standard_budget_450": int(raw_report.get("max_actions", 0)) == 450,
        "all_25_environments_reported": (
            int(raw_report.get("environment_count", 0)) == 25
            and len(reports) == 25
            and len(set(game_ids)) == 25
        ),
        "error_count_zero": (
            int(raw_report.get("error_count", -1)) == 0 and not errors
        ),
        "probe_fault_count_zero": total_faults == 0,
        "bounded_retention_overflow_zero": total_overflow == 0,
        "all_observations_have_contrast_records": (
            total_observations > 0
            and total_observations == total_records
            and all_records_retained
        ),
        "all_record_semantics_recomputed": all_semantics_valid,
        "runtime_identity_absent": identity_free,
        "action_selection_influence_absent": (
            not action_selection_influence
        ),
        "memory_emit_promotion_authority_absent": (
            not unauthorized_authority
        ),
        "positive_negative_hazard_contrast_present": (
            role_counts["POSITIVE"] > 0
            and role_counts["NEGATIVE"] > 0
            and role_counts["HAZARD"] > 0
        ),
        "all_boundary_labels_cross_game_stable": all(
            len(boundary_games[label]) >= _MIN_GAME_SUPPORT[label]
            for label in _BOUNDARY_LABELS
        ),
        "all_boundary_labels_cross_structure_stable": all(
            len(boundary_structures[label])
            >= _MIN_STRUCTURE_SUPPORT[label]
            for label in _BOUNDARY_LABELS
        ),
        "required_effect_classes_cross_game_stable": all(
            len(effect_games[effect]) >= minimum
            for effect, minimum in _REQUIRED_EFFECT_GAME_SUPPORT.items()
        ),
        "multiple_action_classes_have_boundary_contrast": (
            len(contrasted_action_classes) >= 3
        ),
        "multiple_action_classes_separate_hazard": (
            len(hazard_separating_action_classes) >= 3
        ),
        "compact_content_digest_valid": compact_digest_valid,
        "compact_matches_raw_report": compact_matches_raw,
        "checkpoint_conditions_digest_valid": conditions_digest_valid,
        "reported_games_match_checkpoint_conditions": (
            game_ids == condition_game_ids
        ),
    }
    failures = sorted(key for key, passed in checks.items() if not passed)
    if failures:
        raise ValueError(
            "C2_C3_CLUSTER_STABLE_AUDIT_FAILED:" + ",".join(failures)
        )
    if conditions is None:
        raise TypeError("C2_C3_CLUSTER_CHECKPOINT_CONDITIONS_MISSING")

    body: dict[str, Any] = {
        "schema_version": C2_C3_CLUSTER_AUDIT_SCHEMA_VERSION,
        "artifact_type": "arc3_c2_c3_cluster_stable_audit",
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "capability_ids": list(C2_C3_CAPABILITY_IDS),
        "candidate_tier": "CLUSTER_STABLE",
        "source_evidence": {
            "raw_report_sha256": raw_report_sha256,
            "compact_evidence_sha256": compact_evidence_sha256,
            "compact_content_digest": compact_digest,
            "conditions": dict(conditions),
        },
        "thresholds": {
            "minimum_game_support_by_boundary": _MIN_GAME_SUPPORT,
            "minimum_structure_support_by_boundary": (
                _MIN_STRUCTURE_SUPPORT
            ),
            "required_effect_game_support": (
                _REQUIRED_EFFECT_GAME_SUPPORT
            ),
            "minimum_contrasted_action_classes": 3,
            "minimum_hazard_separating_action_classes": 3,
        },
        "summary": {
            "game_count": len(game_rows),
            "completed_levels": int(
                raw_report.get("completed_levels", 0)
            ),
            "total_levels": int(raw_report.get("total_levels", 0)),
            "action_count": total_actions,
            "observation_count": total_observations,
            "contrast_record_count": total_records,
            "fault_count": total_faults,
            "overflow_count": total_overflow,
            "boundary_counts": dict(sorted(boundary_counts.items())),
            "contrast_role_counts": dict(sorted(role_counts.items())),
            "effect_counts": dict(sorted(effect_counts.items())),
            "error_count": int(raw_report.get("error_count", -1)),
        },
        "cross_context_support": {
            "boundaries": boundary_support,
            "effects": effect_support,
            "contrasted_action_classes": contrasted_action_classes,
            "hazard_separating_action_classes": (
                hazard_separating_action_classes
            ),
        },
        "checks": checks,
        "rows": game_rows,
        "hds_judgment": {
            "local_probe_status": "PASS",
            "cluster_stable_status": "PASS",
            "composable_status": "HOLD",
            "runtime_p_compile_authorized": False,
            "runtime_p_promotion_authorized": False,
            "score_progress_claim_authorized": False,
            "reason": (
                "C2/C3 positive, negative, and hazard separators are "
                "recomputed across independent games and structures with "
                "zero policy influence. Composition and removal evidence "
                "are still required before Runtime P compilation."
            ),
        },
    }
    return {
        **body,
        "content_digest": (
            "arc3_c2_c3_cluster_stable_audit:" + digest_object(body)
        ),
    }


def write_c2_c3_cluster_audit(
    *,
    raw_report_path: Path,
    compact_evidence_path: Path,
    output_path: Path,
) -> Path:
    value = build_c2_c3_cluster_audit(
        raw_report=_json_object(raw_report_path),
        raw_report_sha256=_sha256(raw_report_path),
        compact_evidence=_json_object(compact_evidence_path),
        compact_evidence_sha256=_sha256(compact_evidence_path),
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
        description="Build the C2/C3 CLUSTER_STABLE audit."
    )
    parser.add_argument("--raw-report", type=Path, required=True)
    parser.add_argument("--compact-evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    output = write_c2_c3_cluster_audit(
        raw_report_path=args.raw_report,
        compact_evidence_path=args.compact_evidence,
        output_path=args.output,
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "C2_C3_CLUSTER_AUDIT_SCHEMA_VERSION",
    "build_c2_c3_cluster_audit",
    "write_c2_c3_cluster_audit",
]
