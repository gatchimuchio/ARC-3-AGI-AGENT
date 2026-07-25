"""Build a content-bound audit for the shadow-only C2/C3 LOCAL_PROBE."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .cross_cutting_transition import (
    C2_C3_CAPABILITY_IDS,
    C2_C3_LEGACY_PROBE_FORMATS,
    C2_C3_PROBE_FORMAT,
)
from .p10_evidence import build_p10_compact_run_evidence
from .schema import digest_object

C2_C3_PROBE_AUDIT_SCHEMA_VERSION = "arc3-c2-c3-local-probe-audit-v1"


def _json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def _file_digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _mapping_rows(value: object, field_name: str) -> list[Mapping[str, Any]]:
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


def build_c2_c3_probe_audit(
    *,
    raw_report: Mapping[str, Any],
    raw_report_sha256: str,
    compact_evidence: Mapping[str, Any],
    compact_evidence_sha256: str,
) -> dict[str, Any]:
    """Validate and summarize one all-sample shadow-probe run."""

    reports = _mapping_rows(raw_report.get("reports"), "reports")
    errors = _mapping_rows(raw_report.get("errors"), "errors")
    if str(raw_report.get("operation_mode", "")).casefold() != "offline":
        raise ValueError("C2_C3_PROBE_REPORT_NOT_OFFLINE")
    if raw_report.get("instruction_lifecycle") != "active":
        raise ValueError("C2_C3_PROBE_REPORT_NOT_ACTIVE")
    compact_body = dict(compact_evidence)
    compact_digest = str(compact_body.pop("content_digest", ""))
    if compact_digest != digest_object(compact_body):
        raise ValueError("C2_C3_COMPACT_EVIDENCE_DIGEST_INVALID")
    compact_matches_raw = (
        dict(compact_evidence)
        == build_p10_compact_run_evidence(raw_report)
    )

    effect_counts: Counter[str] = Counter()
    boundary_counts: Counter[str] = Counter()
    probe_rows: list[dict[str, Any]] = []
    action_selection_influence = False
    unauthorized_authority = False
    probe_contract_valid = True
    fault_count = 0
    for report in reports:
        probe = report.get("development_transition_probe")
        if not isinstance(probe, Mapping):
            raise ValueError("C2_C3_PROBE_PAYLOAD_MISSING")
        if probe.get("format") not in (
            C2_C3_PROBE_FORMAT,
            *C2_C3_LEGACY_PROBE_FORMATS,
        ):
            raise ValueError("C2_C3_PROBE_FORMAT_INVALID")
        raw_capabilities = probe.get("capability_ids")
        probe_contract_valid = probe_contract_valid and (
            isinstance(raw_capabilities, Sequence)
            and not isinstance(
                raw_capabilities,
                (str, bytes, bytearray),
            )
            and list(raw_capabilities) == list(C2_C3_CAPABILITY_IDS)
            and probe.get("candidate_tier") == "LOCAL_PROBE"
            and probe.get("runtime_decision_use") == "FORBIDDEN"
        )
        raw_effects = probe.get("effect_counts")
        raw_boundaries = probe.get("boundary_counts")
        if not isinstance(raw_effects, Mapping) or not isinstance(
            raw_boundaries,
            Mapping,
        ):
            raise TypeError("C2_C3_PROBE_COUNTS_INVALID")
        effect_counts.update(
            {
                str(key): int(value)
                for key, value in raw_effects.items()
            }
        )
        boundary_counts.update(
            {
                str(key): int(value)
                for key, value in raw_boundaries.items()
            }
        )
        action_selection_influence = (
            action_selection_influence
            or bool(probe.get("action_selection_influence"))
        )
        unauthorized_authority = unauthorized_authority or any(
            bool(probe.get(field))
            for field in (
                "memory_write_authority",
                "external_emit_authority",
                "runtime_p_promotion_authority",
            )
        )
        row_fault_count = int(probe.get("fault_count", 0))
        fault_count += row_fault_count
        probe_rows.append(
            {
                "game_id": str(report.get("game_id", "")),
                "actions": int(report.get("actions", 0)),
                "observation_count": int(
                    probe.get("observation_count", 0)
                ),
                "fault_count": row_fault_count,
                "effect_counts": dict(sorted(raw_effects.items())),
                "boundary_counts": dict(sorted(raw_boundaries.items())),
                "transition_digest_chain": str(
                    probe.get("transition_digest_chain", "")
                ),
                "action_selection_influence": bool(
                    probe.get("action_selection_influence")
                ),
            }
        )
    probe_rows.sort(key=lambda row: row["game_id"])
    game_ids = [str(row["game_id"]) for row in probe_rows]
    checkpointing = raw_report.get("checkpointing")
    conditions: Mapping[str, Any] | None = None
    conditions_digest_valid = False
    condition_game_ids: list[str] = []
    checkpoint_game_ids: list[str] = []
    if isinstance(checkpointing, Mapping):
        raw_conditions = checkpointing.get("conditions")
        if isinstance(raw_conditions, Mapping):
            conditions = raw_conditions
            conditions_body = dict(raw_conditions)
            claimed_conditions_digest = str(
                conditions_body.pop("conditions_digest", "")
            )
            conditions_digest_valid = (
                claimed_conditions_digest == digest_object(conditions_body)
            )
            raw_condition_game_ids = raw_conditions.get("game_ids")
            if isinstance(raw_condition_game_ids, Sequence) and not isinstance(
                raw_condition_game_ids,
                (str, bytes, bytearray),
            ):
                condition_game_ids = sorted(
                    str(game_id) for game_id in raw_condition_game_ids
                )
        raw_game_checkpoints = checkpointing.get("game_checkpoints")
        if isinstance(raw_game_checkpoints, Sequence) and not isinstance(
            raw_game_checkpoints,
            (str, bytes, bytearray),
        ):
            checkpoint_game_ids = sorted(
                str(row.get("game_id", ""))
                for row in raw_game_checkpoints
                if isinstance(row, Mapping)
            )
    checks = {
        "operation_mode_offline": (
            str(raw_report.get("operation_mode", "")).casefold()
            == "offline"
        ),
        "instruction_lifecycle_active": (
            raw_report.get("instruction_lifecycle") == "active"
        ),
        "all_25_environments_reported": (
            int(raw_report.get("environment_count", 0)) == 25
            and len(reports) == 25
            and len(set(game_ids)) == 25
        ),
        "error_count_zero": (
            int(raw_report.get("error_count", -1)) == 0 and not errors
        ),
        "max_actions_one": int(raw_report.get("max_actions", 0)) == 1,
        "one_action_and_probe_per_game": all(
            int(row["actions"]) == 1
            and int(row["observation_count"]) == 1
            for row in probe_rows
        ),
        "all_probe_rows_nonempty": all(
            int(row["observation_count"]) > 0 for row in probe_rows
        ),
        "action_selection_influence_absent": (
            not action_selection_influence
        ),
        "memory_emit_promotion_authority_absent": (
            not unauthorized_authority
        ),
        "probe_contract_valid": probe_contract_valid,
        "probe_fault_count_zero": fault_count == 0,
        "compact_matches_raw_report": compact_matches_raw,
        "checkpointed_execution_present": (
            isinstance(checkpointing, Mapping)
            and conditions is not None
            and int(checkpointing.get("executed_game_count", -1)) == 25
            and int(checkpointing.get("reused_game_count", -1)) == 0
        ),
        "checkpoint_conditions_digest_valid": conditions_digest_valid,
        "reported_games_match_checkpoint_conditions": (
            game_ids == condition_game_ids
        ),
        "checkpoint_rows_match_reported_games": (
            game_ids == checkpoint_game_ids
        ),
    }
    if not all(checks.values()):
        failures = sorted(key for key, passed in checks.items() if not passed)
        raise ValueError("C2_C3_PROBE_AUDIT_FAILED:" + ",".join(failures))
    if conditions is None:
        raise TypeError("C2_C3_PROBE_CHECKPOINT_CONDITIONS_MISSING")
    body: dict[str, Any] = {
        "schema_version": C2_C3_PROBE_AUDIT_SCHEMA_VERSION,
        "artifact_type": "arc3_c2_c3_local_probe_audit",
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "capability_ids": list(C2_C3_CAPABILITY_IDS),
        "candidate_tier": "LOCAL_PROBE",
        "source_evidence": {
            "raw_report_sha256": raw_report_sha256,
            "compact_evidence_sha256": compact_evidence_sha256,
            "compact_content_digest": compact_digest,
            "conditions": dict(conditions),
        },
        "summary": {
            "game_count": len(probe_rows),
            "action_count": sum(
                int(row["actions"]) for row in probe_rows
            ),
            "observation_count": sum(
                int(row["observation_count"]) for row in probe_rows
            ),
            "fault_count": fault_count,
            "effect_counts": dict(sorted(effect_counts.items())),
            "boundary_counts": dict(sorted(boundary_counts.items())),
            "completed_levels": int(
                raw_report.get("completed_levels", 0)
            ),
            "total_levels": int(raw_report.get("total_levels", 0)),
            "error_count": int(raw_report.get("error_count", -1)),
        },
        "checks": checks,
        "rows": probe_rows,
        "hds_judgment": {
            "local_probe_status": "PASS",
            "cluster_stable_status": "HOLD",
            "composable_status": "HOLD",
            "runtime_p_promotion_authorized": False,
            "score_claim_authorized": False,
            "reason": (
                "All 25 first transitions were observed without policy "
                "influence, but one transition per game is not sufficient "
                "for positive/negative cluster closure."
            ),
        },
    }
    return {
        **body,
        "content_digest": (
            "arc3_c2_c3_local_probe_audit:" + digest_object(body)
        ),
    }


def write_c2_c3_probe_audit(
    *,
    raw_report_path: Path,
    compact_evidence_path: Path,
    output_path: Path,
) -> Path:
    value = build_c2_c3_probe_audit(
        raw_report=_json_object(raw_report_path),
        raw_report_sha256=_file_digest(raw_report_path),
        compact_evidence=_json_object(compact_evidence_path),
        compact_evidence_sha256=_file_digest(compact_evidence_path),
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
        description="Build a shadow-only C2/C3 LOCAL_PROBE audit."
    )
    parser.add_argument("--raw-report", type=Path, required=True)
    parser.add_argument("--compact-evidence", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    output = write_c2_c3_probe_audit(
        raw_report_path=args.raw_report,
        compact_evidence_path=args.compact_evidence,
        output_path=args.output,
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
