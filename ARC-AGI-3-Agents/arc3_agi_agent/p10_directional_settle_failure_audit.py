"""Close the rejected directional-settle intervention with a failure signature."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .directional_force_route import DIRECTIONAL_FORCE_ROUTE_OPERATOR
from .p10_directional_settle_candidate_workflow import (
    P10_DIRECTIONAL_SETTLE_CANDIDATE_WORKFLOW_SCHEMA_VERSION,
)
from .p10_instruction_compiler import (
    P10_DIRECTIONAL_SETTLE_HYBRID_VERSION,
)
from .schema import digest_object

P10_DIRECTIONAL_SETTLE_FAILURE_AUDIT_SCHEMA_VERSION = (
    "arc3-p10-directional-settle-failure-audit-v1"
)
_INTERVENTION_DIGEST_PREFIX = (
    "arc3_p10_directional_settle_candidate_intervention:"
)
_CONTENT_DIGEST_PREFIX = (
    "arc3_p10_directional_settle_failure_audit:"
)
_REOBSERVE_MARKER = (
    f"{DIRECTIONAL_FORCE_ROUTE_OPERATOR}:"
    "post-progress-transition-reobserve"
)


def _json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
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


def _content_digest_valid(
    value: Mapping[str, Any],
    prefix: str,
) -> bool:
    body = dict(value)
    claimed = str(body.pop("content_digest", ""))
    return claimed == prefix + digest_object(body)


def _sequence(value: object, field_name: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(
        value,
        (str, bytes, bytearray),
    ):
        raise TypeError(f"{field_name} must be a sequence")
    return value


def _integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    return value


def _intervention_target_run(
    intervention: Mapping[str, Any],
) -> Mapping[str, Any]:
    if (
        intervention.get("schema_version")
        != P10_DIRECTIONAL_SETTLE_CANDIDATE_WORKFLOW_SCHEMA_VERSION
        or not _content_digest_valid(
            intervention,
            _INTERVENTION_DIGEST_PREFIX,
        )
    ):
        raise ValueError(
            "P10_DIRECTIONAL_SETTLE_INTERVENTION_INVALID"
        )
    evaluation = intervention.get("evaluation")
    judgment = intervention.get("hds_judgment")
    runs = intervention.get("runs")
    if (
        not isinstance(evaluation, Mapping)
        or not isinstance(judgment, Mapping)
        or not isinstance(runs, Mapping)
    ):
        raise TypeError(
            "P10 directional-settle intervention shape invalid"
        )
    candidate_first = _sequence(
        runs.get("candidate_first"),
        "candidate first runs",
    )
    targets = tuple(
        item
        for item in candidate_first
        if isinstance(item, Mapping)
        and item.get("cohort") == "target"
    )
    if len(targets) != 1:
        raise ValueError(
            "P10_DIRECTIONAL_SETTLE_TARGET_RUN_CARDINALITY_INVALID"
        )
    if (
        judgment.get("status") != "REJECT"
        or judgment.get("candidate_slot_retained") is not False
        or judgment.get("runtime_p_promotion_authorized") is not False
        or judgment.get("score_progress_claim_authorized") is not False
        or evaluation.get("target_completion_delta") != 0
        or evaluation.get("target_improved") is not False
        or evaluation.get("candidate_reproducible") is not True
        or evaluation.get("candidate_errors_zero") is not True
    ):
        raise ValueError(
            "P10_DIRECTIONAL_SETTLE_REJECTION_CONTRACT_INVALID"
        )
    return targets[0]


def _compact_report(
    compact: Mapping[str, Any],
) -> Mapping[str, Any]:
    body = dict(compact)
    claimed = body.pop("content_digest", None)
    if claimed != digest_object(body):
        raise ValueError(
            "P10_DIRECTIONAL_SETTLE_DIAGNOSTIC_DIGEST_INVALID"
        )
    if (
        compact.get("schema_version")
        != "arc3-p10-compact-run-evidence-v1"
        or compact.get("operation_mode") != "offline"
    ):
        raise ValueError(
            "P10_DIRECTIONAL_SETTLE_DIAGNOSTIC_CONDITION_INVALID"
        )
    summary = compact.get("summary")
    compact_run = compact.get("compact_run")
    if not isinstance(summary, Mapping) or not isinstance(
        compact_run,
        Mapping,
    ):
        raise TypeError(
            "P10 directional-settle compact diagnostic invalid"
        )
    reports = _sequence(compact_run.get("reports"), "compact reports")
    if (
        len(reports) != 1
        or not isinstance(reports[0], Mapping)
        or summary.get("error_count") != 0
    ):
        raise ValueError(
            "P10_DIRECTIONAL_SETTLE_DIAGNOSTIC_REPORT_INVALID"
        )
    return reports[0]


def _provenance_items(
    row: object,
    field_name: str,
) -> tuple[str, ...]:
    return tuple(
        str(item) for item in _sequence(row, field_name)
    )


def _emitted_action(step: object) -> Mapping[str, object]:
    emitted = _sequence(step, "emitted step")
    if (
        len(emitted) != 1
        or not isinstance(emitted[0], Mapping)
    ):
        raise TypeError("P10 directional-settle emitted step invalid")
    return emitted[0]


def _action_id(step: object) -> int:
    return _integer(
        _emitted_action(step).get("action_id"),
        "action id",
    )


def _visual_action_key(step: object) -> str:
    value = _emitted_action(step).get("visual_action_key")
    if not isinstance(value, str) or not value:
        raise TypeError(
            "P10 directional-settle visual action key invalid"
        )
    return value


def build_p10_directional_settle_failure_audit(
    intervention: Mapping[str, Any],
    candidate_compact: Mapping[str, Any],
) -> dict[str, object]:
    """Prove that bounded replay activated but produced no progress."""

    target_run = _intervention_target_run(intervention)
    report = _compact_report(candidate_compact)
    steps = _sequence(report.get("emitted_steps"), "emitted steps")
    provenance_rows = _sequence(
        report.get("emitted_provenance"),
        "emitted provenance",
    )
    level_counts = _sequence(
        report.get("emitted_level_counts"),
        "emitted level counts",
    )
    body_versions = _sequence(
        report.get("instruction_body_versions"),
        "instruction body versions",
    )
    if not (
        len(steps)
        == len(provenance_rows)
        == len(level_counts)
        == len(body_versions)
        == _integer(report.get("actions"), "report actions")
    ):
        raise ValueError(
            "P10_DIRECTIONAL_SETTLE_DIAGNOSTIC_TRACE_MISALIGNED"
        )
    if {
        str(version) for version in body_versions
    } != {P10_DIRECTIONAL_SETTLE_HYBRID_VERSION}:
        raise ValueError(
            "P10_DIRECTIONAL_SETTLE_DIAGNOSTIC_NOT_CANDIDATE"
        )

    boundary_indices: list[int] = []
    for index in range(1, len(level_counts)):
        prior = _integer(
            level_counts[index - 1],
            "prior level count",
        )
        current = _integer(level_counts[index], "level count")
        provenance = _provenance_items(
            provenance_rows[index],
            "boundary provenance",
        )
        if (
            current > prior
            and DIRECTIONAL_FORCE_ROUTE_OPERATOR in provenance
        ):
            boundary_indices.append(index)
    if not boundary_indices:
        raise ValueError(
            "P10_DIRECTIONAL_SETTLE_DIAGNOSTIC_BOUNDARY_MISSING"
        )
    boundary_index = boundary_indices[-1]
    replay_indices: list[int] = []
    cursor = boundary_index + 1
    while cursor < len(provenance_rows):
        provenance = _provenance_items(
            provenance_rows[cursor],
            "post-progress provenance",
        )
        if _REOBSERVE_MARKER not in provenance:
            break
        replay_indices.append(cursor)
        cursor += 1
    removal = intervention.get("removal_control")
    if not isinstance(removal, Mapping):
        raise TypeError(
            "P10 directional-settle removal control invalid"
        )
    observation_limit = _integer(
        removal.get("candidate_transition_observation_limit"),
        "candidate transition observation limit",
    )
    if cursor >= len(steps):
        raise ValueError(
            "P10_DIRECTIONAL_SETTLE_DIAGNOSTIC_FALLBACK_MISSING"
        )
    fallback_provenance = _provenance_items(
        provenance_rows[cursor],
        "fallback provenance",
    )
    boundary_action_id = _action_id(steps[boundary_index])
    boundary_action_key = _visual_action_key(steps[boundary_index])
    replay_action_ids = tuple(
        _action_id(steps[index]) for index in replay_indices
    )
    replay_action_keys = tuple(
        _visual_action_key(steps[index]) for index in replay_indices
    )
    final_level_count = _integer(
        level_counts[-1],
        "final level count",
    )
    boundary_level_count = _integer(
        level_counts[boundary_index],
        "boundary level count",
    )

    trace_checks = {
        "candidate_trace_matches_intervention_actions": (
            report.get("actions") == target_run.get("actions")
        ),
        "candidate_trace_matches_intervention_completion": (
            report.get("levels_completed")
            == target_run.get("completed_levels")
        ),
        "candidate_steps_match_intervention_digest": (
            digest_object(steps)
            == target_run.get("emitted_steps_digest")
        ),
        "candidate_provenance_matches_intervention_digest": (
            digest_object(provenance_rows)
            == target_run.get("emitted_provenance_digest")
        ),
        "candidate_operator_version_bound": True,
        "progress_boundary_directional": True,
        "bounded_replay_activated": bool(replay_indices),
        "bounded_replay_count_matches_parameter": (
            len(replay_indices) == observation_limit
        ),
        "bounded_replay_repeats_boundary_action": (
            replay_action_ids
            == (boundary_action_id,) * observation_limit
        ),
        "bounded_replay_reuses_boundary_visual_action": (
            replay_action_keys
            == (boundary_action_key,) * observation_limit
        ),
        "fallback_occurs_immediately_after_bound": (
            cursor == boundary_index + observation_limit + 1
        ),
        "fallback_is_generic_untested_candidate": (
            "VISUAL_UNTESTED_CANDIDATE" in fallback_provenance
        ),
        "no_progress_after_bounded_replay": (
            final_level_count == boundary_level_count
        ),
        "candidate_run_max_action_exhausted": (
            report.get("max_action_exhausted") is True
        ),
    }
    if not all(trace_checks.values()):
        failures = sorted(
            key for key, passed in trace_checks.items() if not passed
        )
        raise ValueError(
            "P10_DIRECTIONAL_SETTLE_FAILURE_SIGNATURE_INVALID:"
            + ",".join(failures)
        )

    failure_window = [
        {
            "action_ordinal": index + 1,
            "role": (
                "progress-boundary"
                if index == boundary_index
                else (
                    "bounded-old-action-replay"
                    if index in replay_indices
                    else "generic-fallback"
                )
            ),
            "level_count": _integer(
                level_counts[index],
                "failure-window level count",
            ),
            "action_id": _action_id(steps[index]),
            "step_digest": digest_object(steps[index]),
            "provenance_digest": digest_object(
                _provenance_items(
                    provenance_rows[index],
                    "failure-window provenance",
                )
            ),
        }
        for index in (
            boundary_index,
            *replay_indices,
            cursor,
        )
    ]
    body: dict[str, object] = {
        "schema_version": (
            P10_DIRECTIONAL_SETTLE_FAILURE_AUDIT_SCHEMA_VERSION
        ),
        "artifact_type": (
            "arc3_p10_directional_settle_closed_negative"
        ),
        "phase": "P10_COMPLETE_ARC3_SAMPLE_SOLVING",
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "candidate_tier": "LOCAL_PROBE_REJECTED",
        "capability_cluster": (
            "multi-actor-directional-force-obligation-composition"
        ),
        "source_evidence": {
            "intervention_content_digest": intervention[
                "content_digest"
            ],
            "candidate_compact_content_digest": candidate_compact[
                "content_digest"
            ],
            "candidate_trace_digest": digest_object(
                {
                    "steps": steps,
                    "provenance": provenance_rows,
                    "level_counts": level_counts,
                    "body_versions": body_versions,
                }
            ),
        },
        "failure_signature": {
            "id": (
                "bounded-old-direction-replay-exhausted-then-"
                "generic-fallback"
            ),
            "progress_boundary_action_ordinal": boundary_index + 1,
            "bounded_replay_first_action_ordinal": (
                replay_indices[0] + 1
            ),
            "bounded_replay_last_action_ordinal": (
                replay_indices[-1] + 1
            ),
            "bounded_replay_count": len(replay_indices),
            "generic_fallback_action_ordinal": cursor + 1,
            "completion_before": boundary_level_count,
            "completion_after": final_level_count,
            "target_completion_delta": 0,
            "failure_window": failure_window,
        },
        "trace_checks": trace_checks,
        "causal_interpretation": {
            "candidate_activation_confirmed": True,
            "candidate_parameter_exhausted": True,
            "old_action_replay_is_not_missing_capability": True,
            "remaining_gap": (
                "parse and compose the new visible obligation state; "
                "do not replay the predecessor action"
            ),
            "same_candidate_retry_has_new_information": False,
        },
        "hds_judgment": {
            "authority": "development-hds-only",
            "status": "REJECT",
            "causal_result": "CLOSED_NEGATIVE",
            "same_candidate_retry_authorized": False,
            "all_sample_regression_authorized": False,
            "runtime_p_promotion_authorized": False,
            "score_progress_claim_authorized": False,
            "active_p_mutation_authorized": False,
            "next_cluster_analysis_authorized": True,
            "reason_codes": [
                "candidate-activation-observed",
                "bounded-old-action-replay-exhausted",
                "target-completion-delta-zero",
                "stable-non-regression-does-not-offset-no-gain",
                "candidate-slot-restored",
            ],
        },
    }
    return {
        **body,
        "content_digest": _CONTENT_DIGEST_PREFIX
        + digest_object(body),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Close a rejected directional-settle candidate with a "
            "deterministic failure signature."
        )
    )
    parser.add_argument("--intervention", type=Path, required=True)
    parser.add_argument("--candidate-compact", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    audit = build_p10_directional_settle_failure_audit(
        _json_object(args.intervention),
        _json_object(args.candidate_compact),
    )
    _write_json(args.output, audit)
    print(audit["content_digest"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "P10_DIRECTIONAL_SETTLE_FAILURE_AUDIT_SCHEMA_VERSION",
    "build_p10_directional_settle_failure_audit",
    "main",
]
