"""Audit a materially new C10 temporal-causal contrast from P10 traces.

The legacy C10 phase/timer surface is closed negative.  This development-only
audit therefore does not count timer changes.  It asks a narrower question:
does the same rendered source frame and same action have different visible
outcomes, and can the immediately preceding action/effect boundary separate
those outcomes without game identity or a replay suffix?

The audit only reads completed shadow telemetry.  It cannot choose or emit an
action, write memory, compile Runtime P, or promote a capability.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from arc3_agi_agent.cross_cutting_transition import C2_C3_PROBE_FORMAT
from arc3_agi_agent.schema import digest_object

C10_TEMPORAL_AUDIT_SCHEMA_VERSION = (
    "arc3-p10-c10-temporal-causal-contrast-audit-v1"
)
C10_CAPABILITY_ID = "C10_phase_timer_unlock_model"
C10_EXAMPLE_LIMIT = 128
C10_MIN_GAME_SUPPORT = 2
C10_MIN_SEPARABLE_GROUPS = 2


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


def _items(value: object, field_name: str) -> list[object]:
    if not isinstance(value, Sequence) or isinstance(
        value,
        (str, bytes, bytearray),
    ):
        raise TypeError(f"{field_name} must be an array")
    return list(value)


def _strings(value: object, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(
        value,
        (str, bytes, bytearray),
    ):
        raise TypeError(f"{field_name} must be an array")
    return tuple(str(item) for item in value)


def _emitted_step(
    value: object,
    *,
    game_id: str,
    ordinal: int,
) -> Mapping[str, Any]:
    steps = _rows(value, f"{game_id} emitted_steps[{ordinal}]")
    if not steps:
        raise ValueError(f"C10_EMITTED_STEP_MISSING:{game_id}:{ordinal}")
    step = steps[0]
    source = step.get("visual_source_signature")
    if not isinstance(source, str) or not source.startswith("visual-state:"):
        raise ValueError(
            f"C10_RENDERED_SOURCE_SIGNATURE_MISSING:{game_id}:{ordinal}"
        )
    return step


def _outcome(record: Mapping[str, Any]) -> tuple[object, ...]:
    return (
        _strings(record.get("effect_classes"), "effect_classes"),
        str(record.get("observed_boundary", "")),
    )


def _causal_token(record: Mapping[str, Any]) -> tuple[object, ...]:
    return (
        str(record.get("action_class", "")),
        _strings(record.get("effect_classes"), "effect_classes"),
        str(record.get("observed_boundary", "")),
    )


def _group_key(
    *,
    step: Mapping[str, Any],
    record: Mapping[str, Any],
) -> tuple[str, str, str]:
    return (
        str(step["visual_source_signature"]),
        str(record.get("action_prototype", "")),
        str(record.get("action_class", "")),
    )


def _group_digest(
    *,
    key: tuple[str, str, str],
    observations: Sequence[tuple[int, tuple[object, ...]]],
) -> str:
    return "temporal-contrast-group:" + digest_object(
        {
            "source_rendered_signature": key[0],
            "action_prototype": key[1],
            "action_class": key[2],
            "observations": [
                {
                    "ordinal": ordinal,
                    "outcome": outcome,
                }
                for ordinal, outcome in observations
            ],
        }
    )[:24]


def build_c10_temporal_contrast_audit(
    *,
    raw_report: Mapping[str, Any],
    raw_report_sha256: str,
) -> dict[str, object]:
    """Build a bounded C10 reopening audit from a complete shadow run."""

    reports = sorted(
        _rows(raw_report.get("reports"), "reports"),
        key=lambda report: str(report.get("game_id", "")),
    )
    errors = _rows(raw_report.get("errors"), "errors")
    contract_checks = {
        "operation_mode_offline": (
            str(raw_report.get("operation_mode", "")).casefold()
            == "offline"
        ),
        "instruction_lifecycle_active": (
            raw_report.get("instruction_lifecycle") == "active"
        ),
        "standard_budget_450": raw_report.get("max_actions") == 450,
        "all_25_reports_present": (
            raw_report.get("environment_count") == 25
            and len(reports) == 25
            and len(
                {
                    str(report.get("game_id", ""))
                    for report in reports
                }
            )
            == 25
        ),
        "runtime_errors_zero": (
            raw_report.get("error_count") == 0 and not errors
        ),
    }

    game_rows: list[dict[str, object]] = []
    example_rows: list[dict[str, object]] = []
    all_group_digests: list[str] = []
    ambiguous_game_count = 0
    separable_game_count = 0
    ambiguous_group_count = 0
    separable_group_count = 0
    nonseparable_group_count = 0
    total_transitions = 0

    for report in reports:
        game_id = str(report.get("game_id", ""))
        probe = report.get("development_transition_probe")
        if not isinstance(probe, Mapping):
            raise ValueError(f"C10_TRANSITION_PROBE_MISSING:{game_id}")
        probe_checks = {
            "format": probe.get("format") == C2_C3_PROBE_FORMAT,
            "local_probe": probe.get("candidate_tier") == "LOCAL_PROBE",
            "runtime_forbidden": (
                probe.get("runtime_decision_use") == "FORBIDDEN"
            ),
            "action_influence_absent": (
                probe.get("action_selection_influence") is False
            ),
            "memory_authority_absent": (
                probe.get("memory_write_authority") is False
            ),
            "emit_authority_absent": (
                probe.get("external_emit_authority") is False
            ),
            "promotion_authority_absent": (
                probe.get("runtime_p_promotion_authority") is False
            ),
            "faults_zero": probe.get("fault_count") == 0,
            "overflow_zero": all(
                probe.get(field) == 0
                for field in (
                    "model_overflow_count",
                    "context_overflow_count",
                    "contrast_overflow_count",
                )
            ),
        }
        failures = sorted(
            key for key, passed in probe_checks.items() if not passed
        )
        if failures:
            raise ValueError(
                f"C10_SHADOW_CONTRACT_INVALID:{game_id}:"
                + ",".join(failures)
            )

        records = _rows(
            probe.get("contrast_records"),
            f"{game_id} contrast_records",
        )
        emitted_steps = _items(
            report.get("emitted_steps"),
            f"{game_id} emitted_steps",
        )
        if (
            len(records) != len(emitted_steps)
            or probe.get("observation_count") != len(records)
        ):
            raise ValueError(
                f"C10_TRACE_CARDINALITY_MISMATCH:{game_id}"
            )
        total_transitions += len(records)
        groups: defaultdict[
            tuple[str, str, str],
            list[tuple[int, tuple[object, ...]]],
        ] = defaultdict(list)
        previous_tokens: dict[int, tuple[object, ...]] = {}
        for index, (record, raw_steps) in enumerate(
            zip(records, emitted_steps, strict=True),
        ):
            ordinal = index + 1
            if record.get("ordinal") != ordinal:
                raise ValueError(
                    f"C10_TRACE_ORDINAL_INVALID:{game_id}:{ordinal}"
                )
            step = _emitted_step(
                raw_steps,
                game_id=game_id,
                ordinal=ordinal,
            )
            groups[_group_key(step=step, record=record)].append(
                (ordinal, _outcome(record))
            )
            if index:
                previous_tokens[ordinal] = _causal_token(
                    records[index - 1]
                )

        game_ambiguous = 0
        game_separable = 0
        game_nonseparable = 0
        for key, observations in sorted(groups.items()):
            outcomes = {outcome for _ordinal, outcome in observations}
            if len(outcomes) < 2:
                continue
            game_ambiguous += 1
            ambiguous_group_count += 1
            by_token: defaultdict[
                tuple[object, ...],
                set[tuple[object, ...]],
            ] = defaultdict(set)
            missing_previous = False
            for ordinal, outcome in observations:
                token = previous_tokens.get(ordinal)
                if token is None:
                    missing_previous = True
                    continue
                by_token[token].add(outcome)
            separable = (
                not missing_previous
                and len(by_token) >= 2
                and all(len(values) == 1 for values in by_token.values())
            )
            if separable:
                game_separable += 1
                separable_group_count += 1
            else:
                game_nonseparable += 1
                nonseparable_group_count += 1
            group_digest = _group_digest(
                key=key,
                observations=observations,
            )
            all_group_digests.append(group_digest)
            if len(example_rows) < C10_EXAMPLE_LIMIT:
                example_rows.append(
                    {
                        "game_id": game_id,
                        "group_digest": group_digest,
                        "observation_count": len(observations),
                        "distinct_outcome_count": len(outcomes),
                        "distinct_previous_token_count": len(by_token),
                        "one_step_causal_context_separates": separable,
                        "minimum_token_support": (
                            0
                            if not by_token
                            else min(
                                sum(
                                    previous_tokens.get(ordinal) == token
                                    for ordinal, _outcome_value in observations
                                )
                                for token in by_token
                            )
                        ),
                    }
                )

        if game_ambiguous:
            ambiguous_game_count += 1
        if game_separable:
            separable_game_count += 1
        game_rows.append(
            {
                "game_id": game_id,
                "transition_count": len(records),
                "ambiguous_same_frame_action_group_count": game_ambiguous,
                "one_step_separable_group_count": game_separable,
                "nonseparable_group_count": game_nonseparable,
            }
        )

    contract_failures = sorted(
        key for key, passed in contract_checks.items() if not passed
    )
    if contract_failures:
        raise ValueError(
            "C10_INPUT_CONTRACT_INVALID:" + ",".join(contract_failures)
        )

    game_rows.sort(key=lambda row: str(row["game_id"]))
    example_rows.sort(
        key=lambda row: (
            str(row["game_id"]),
            str(row["group_digest"]),
        )
    )
    cross_game_reopening_evidence = (
        separable_game_count >= C10_MIN_GAME_SUPPORT
        and separable_group_count >= C10_MIN_SEPARABLE_GROUPS
    )
    evidence_checks = {
        "same_rendered_frame_and_action_ambiguity_observed": (
            ambiguous_group_count > 0
        ),
        "one_step_visible_effect_context_separates_outcomes": (
            separable_group_count > 0
        ),
        "separation_has_cross_game_support": cross_game_reopening_evidence,
        "audit_did_not_execute_actions": True,
        "audit_did_not_use_timer_counter_or_path_length_as_selector": True,
        "audit_did_not_change_runtime_p": True,
    }
    group_inventory_digest = digest_object(sorted(all_group_digests))
    body: dict[str, object] = {
        "schema_version": C10_TEMPORAL_AUDIT_SCHEMA_VERSION,
        "artifact_type": "arc3_c10_temporal_causal_contrast_audit",
        "phase": "P10_COMPLETE_ARC3_SAMPLE_SOLVING",
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "capability_id": C10_CAPABILITY_ID,
        "source_evidence": {
            "raw_report_sha256": raw_report_sha256,
            "transition_group_inventory_digest": group_inventory_digest,
        },
        "reopening_contract": {
            "legacy_phase_timer_surface_status": "CLOSED_NEGATIVE",
            "same_surface_retry": "REJECTED",
            "materially_new_observable_variable": (
                "previous visible action/effect/boundary causal context"
            ),
            "forbidden_shortcuts": [
                "task game or level identity",
                "fixed action suffix",
                "path-length parity as an emitter",
                "source or hidden state",
                "replay or answer map",
            ],
        },
        "thresholds": {
            "minimum_separable_game_support": C10_MIN_GAME_SUPPORT,
            "minimum_separable_group_count": C10_MIN_SEPARABLE_GROUPS,
            "example_retention_limit": C10_EXAMPLE_LIMIT,
        },
        "summary": {
            "game_count": len(game_rows),
            "transition_count": total_transitions,
            "ambiguous_game_count": ambiguous_game_count,
            "separable_game_count": separable_game_count,
            "ambiguous_same_frame_action_group_count": (
                ambiguous_group_count
            ),
            "one_step_separable_group_count": separable_group_count,
            "nonseparable_group_count": nonseparable_group_count,
            "retained_example_count": len(example_rows),
        },
        "contract_checks": contract_checks,
        "evidence_checks": evidence_checks,
        "rows": game_rows,
        "examples": example_rows,
        "hds_judgment": {
            "c10_reopen_probe_status": (
                "PASS" if cross_game_reopening_evidence else "HOLD"
            ),
            "local_probe_status": (
                "PASS" if cross_game_reopening_evidence else "HOLD"
            ),
            "cluster_stable_status": "HOLD",
            "composable_status": "HOLD",
            "progress_or_commit_separator_status": "HOLD",
            "hazard_separator_status": "HOLD",
            "runtime_p_compile_authorized": False,
            "runtime_p_promotion_authorized": False,
            "score_progress_claim_authorized": False,
            "next_bounded_experiment": (
                "compare a one-step visible-effect causal-context action "
                "binding against unchanged-policy and timer-only controls"
                if cross_game_reopening_evidence
                else "retain C10 closed negative until a new separator exists"
            ),
        },
    }
    return {
        **body,
        "content_digest": (
            "arc3_c10_temporal_causal_contrast_audit:"
            + digest_object(body)
        ),
    }


def write_c10_temporal_contrast_audit(
    *,
    raw_report_path: Path,
    output_path: Path,
) -> Path:
    value = build_c10_temporal_contrast_audit(
        raw_report=_json_object(raw_report_path),
        raw_report_sha256=_sha256(raw_report_path),
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
        description="Audit the new C10 temporal-causal contrast axis."
    )
    parser.add_argument("--raw-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    output = write_c10_temporal_contrast_audit(
        raw_report_path=args.raw_report,
        output_path=args.output,
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "C10_TEMPORAL_AUDIT_SCHEMA_VERSION",
    "build_c10_temporal_contrast_audit",
    "write_c10_temporal_contrast_audit",
]
