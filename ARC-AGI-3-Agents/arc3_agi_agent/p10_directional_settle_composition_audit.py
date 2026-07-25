"""Development-only audit for bounded directional-force settle composition."""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .directional_force_route import (
    DIRECTIONAL_FORCE_ROUTE_OPERATOR,
    _DirectionalForceParameters,
)
from .instruction_body import SemanticOperatorInstruction
from .p10_instruction_compiler import (
    directional_force_route_instruction_mapping,
)
from .schema import digest_object, forbidden_runtime_paths

P10_DIRECTIONAL_SETTLE_COMPOSITION_AUDIT_SCHEMA_VERSION = (
    "arc3-p10-directional-settle-composition-audit-v1"
)
_CONTENT_DIGEST_PREFIX = (
    "arc3_p10_directional_settle_composition_audit:"
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


def _instruction(
    mapping: Mapping[str, object],
) -> SemanticOperatorInstruction:
    action_id = mapping.get("action_id")
    parameters = mapping.get("parameters")
    preconditions = mapping.get("preconditions")
    falsification_conditions = mapping.get("falsification_conditions")
    provenance = mapping.get("provenance")
    if (
        isinstance(action_id, bool)
        or not isinstance(action_id, int)
        or not isinstance(parameters, Mapping)
        or not isinstance(preconditions, Sequence)
        or isinstance(preconditions, (str, bytes, bytearray))
        or not isinstance(falsification_conditions, Sequence)
        or isinstance(
            falsification_conditions,
            (str, bytes, bytearray),
        )
        or not isinstance(provenance, Sequence)
        or isinstance(provenance, (str, bytes, bytearray))
    ):
        raise TypeError("directional-force instruction mapping invalid")
    return SemanticOperatorInstruction(
        operator_id=str(mapping.get("operator_id", "")),
        action_id=action_id,
        detector=str(mapping.get("detector", "")),
        transform=str(mapping.get("transform", "")),
        parameter_items=tuple(sorted(parameters.items())),
        preconditions=tuple(str(item) for item in preconditions),
        falsification_conditions=tuple(
            str(item) for item in falsification_conditions
        ),
        provenance=tuple(str(item) for item in provenance),
    )


def _compact_run(value: Mapping[str, Any]) -> Mapping[str, Any]:
    body = dict(value)
    claimed = body.pop("content_digest", None)
    if claimed != digest_object(body):
        raise ValueError(
            "P10_DIRECTIONAL_SETTLE_SOURCE_CONTENT_DIGEST_INVALID"
        )
    if value.get("schema_version") != "arc3-p10-compact-run-evidence-v1":
        raise ValueError(
            "P10_DIRECTIONAL_SETTLE_SOURCE_SCHEMA_INVALID"
        )
    if value.get("operation_mode") != "offline":
        raise ValueError(
            "P10_DIRECTIONAL_SETTLE_SOURCE_NOT_OFFLINE"
        )
    compact = value.get("compact_run")
    if not isinstance(compact, Mapping):
        raise TypeError("P10 directional-settle compact run invalid")
    reports = compact.get("reports")
    if (
        not isinstance(reports, Sequence)
        or isinstance(reports, (str, bytes, bytearray))
        or len(reports) != 1
        or not isinstance(reports[0], Mapping)
    ):
        raise TypeError("P10 directional-settle report invalid")
    return reports[0]


def build_p10_directional_settle_composition_audit(
    active_compact_evidence: Mapping[str, Any],
    *,
    maximum_transition_observations: int = 8,
) -> dict[str, object]:
    """Bind the observed progress-to-stale-frame gap to one dormant control."""

    report = _compact_run(active_compact_evidence)
    steps = report.get("emitted_steps")
    provenance_rows = report.get("emitted_provenance")
    level_counts = report.get("emitted_level_counts")
    if (
        not isinstance(steps, Sequence)
        or isinstance(steps, (str, bytes, bytearray))
        or not isinstance(provenance_rows, Sequence)
        or isinstance(provenance_rows, (str, bytes, bytearray))
        or not isinstance(level_counts, Sequence)
        or isinstance(level_counts, (str, bytes, bytearray))
        or not len(steps) == len(provenance_rows) == len(level_counts)
    ):
        raise TypeError("P10 directional-settle trace rows invalid")

    boundary_indices: list[int] = []
    for index in range(1, len(level_counts)):
        prior_count = level_counts[index - 1]
        current_count = level_counts[index]
        provenance = provenance_rows[index]
        if (
            isinstance(prior_count, int)
            and not isinstance(prior_count, bool)
            and isinstance(current_count, int)
            and not isinstance(current_count, bool)
            and current_count > prior_count
            and isinstance(provenance, Sequence)
            and not isinstance(provenance, (str, bytes, bytearray))
            and DIRECTIONAL_FORCE_ROUTE_OPERATOR
            in {str(item) for item in provenance}
        ):
            boundary_indices.append(index)
    if not boundary_indices:
        raise ValueError(
            "P10_DIRECTIONAL_SETTLE_PROGRESS_BOUNDARY_NOT_FOUND"
        )
    boundary_index = boundary_indices[-1]
    if boundary_index + 1 >= len(steps):
        raise ValueError(
            "P10_DIRECTIONAL_SETTLE_POST_BOUNDARY_ROW_MISSING"
        )
    post_provenance_raw = provenance_rows[boundary_index + 1]
    if not isinstance(post_provenance_raw, Sequence) or isinstance(
        post_provenance_raw,
        (str, bytes, bytearray),
    ):
        raise TypeError(
            "P10 directional-settle post-boundary provenance invalid"
        )
    post_provenance = tuple(str(item) for item in post_provenance_raw)

    active_mapping = directional_force_route_instruction_mapping()
    candidate_mapping = directional_force_route_instruction_mapping(
        maximum_transition_observations=(
            maximum_transition_observations
        )
    )
    active_parameters = _DirectionalForceParameters.from_instruction(
        _instruction(active_mapping)
    )
    candidate_parameters = _DirectionalForceParameters.from_instruction(
        _instruction(candidate_mapping)
    )
    if active_parameters is None or candidate_parameters is None:
        raise ValueError(
            "P10_DIRECTIONAL_SETTLE_INSTRUCTION_PARSE_FAILED"
        )
    identity_paths = forbidden_runtime_paths(candidate_mapping)
    candidate_falsification_conditions = candidate_mapping.get(
        "falsification_conditions"
    )
    if not isinstance(
        candidate_falsification_conditions,
        Sequence,
    ) or isinstance(
        candidate_falsification_conditions,
        (str, bytes, bytearray),
    ):
        raise TypeError(
            "P10 directional-settle falsification conditions invalid"
        )
    checks = {
        "active_source_content_digest_valid": True,
        "active_source_offline_only": True,
        "single_report_trace_aligned": True,
        "directional_force_progress_boundary_observed": True,
        "post_progress_generic_fallback_observed": (
            "VISUAL_UNTESTED_CANDIDATE" in post_provenance
        ),
        "active_run_error_free": (
            int(active_compact_evidence["summary"]["error_count"]) == 0
        ),
        "active_default_transition_limit_zero": (
            active_parameters.maximum_transition_observations == 0
        ),
        "candidate_transition_limit_bounded": (
            candidate_parameters.maximum_transition_observations
            == maximum_transition_observations
        ),
        "candidate_mapping_identity_free": not identity_paths,
        "candidate_operator_count_unchanged": (
            active_mapping["operator_id"]
            == candidate_mapping["operator_id"]
        ),
        "candidate_requires_confirmed_progress": (
            "confirmed progress boundary"
            in str(candidate_mapping["transform"])
        ),
        "candidate_releases_parseable_successor": any(
            "parseable stable successor" in str(item)
            for item in candidate_falsification_conditions
        ),
        "candidate_does_not_authorize_active_mutation": True,
    }
    compile_authorized = all(checks.values())
    body: dict[str, object] = {
        "schema_version": (
            P10_DIRECTIONAL_SETTLE_COMPOSITION_AUDIT_SCHEMA_VERSION
        ),
        "artifact_type": (
            "arc3_p10_directional_settle_composition_audit"
        ),
        "phase": "P10_COMPLETE_ARC3_SAMPLE_SOLVING",
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "candidate_tier": "LOCAL_PROBE",
        "capability_ids": [
            "C2_visible_effect_transition_model",
            "C5_stale_settle_frame_controller",
            "directional_force_multi_obligation_route",
        ],
        "source_evidence": {
            "active_compact_content_digest": (
                active_compact_evidence["content_digest"]
            ),
            "active_compact_run_digest": (
                active_compact_evidence["summary"][
                    "compact_run_digest"
                ]
            ),
        },
        "observed_gap": {
            "completed_levels": int(report.get("levels_completed", 0)),
            "total_levels": int(report.get("win_levels", 0)),
            "progress_boundary_action_ordinal": boundary_index + 1,
            "post_progress_action_ordinal": boundary_index + 2,
            "boundary_step_digest": digest_object(steps[boundary_index]),
            "post_progress_step_digest": digest_object(
                steps[boundary_index + 1]
            ),
            "post_progress_fallback_provenance_digest": digest_object(
                post_provenance
            ),
        },
        "candidate_contract": {
            "maximum_transition_observations": (
                maximum_transition_observations
            ),
            "activation_scope": "isolated-candidate-hybrid-only",
            "trigger": (
                "confirmed progress after a rendered directional-force action"
            ),
            "continue_while": (
                "predicted successor or rendered operator model is unavailable"
            ),
            "release_on": (
                "parseable stable successor mismatch or observation bound"
            ),
            "identity_routing": False,
            "fixed_action_sequence": False,
            "literal_coordinate_table": False,
            "active_default_limit": 0,
        },
        "removal_control": {
            "without_settle_limit": 0,
            "observed_post_progress_fallback": True,
            "candidate_compile_is_intervention_only": True,
        },
        "contract_checks": checks,
        "hds_judgment": {
            "authority": "development-hds-only",
            "local_probe_status": (
                "PASS" if compile_authorized else "HOLD"
            ),
            "candidate_hybrid_compile_authorized": compile_authorized,
            "active_p_compile_authorized": False,
            "runtime_p_promotion_authorized": False,
            "all_sample_regression_authorized": False,
            "score_progress_claim_authorized": False,
            "reason_codes": (
                [
                    "directional-progress-followed-by-generic-fallback",
                    "active-removal-control-limit-zero",
                    "candidate-control-progress-gated-and-bounded",
                    "runtime-identity-free-contract",
                ]
                if compile_authorized
                else [
                    key
                    for key, passed in checks.items()
                    if not passed
                ]
            ),
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
            "Build the development-only directional-settle composition "
            "audit without changing active P."
        )
    )
    parser.add_argument("--active-compact", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--maximum-transition-observations",
        type=int,
        default=8,
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    audit = build_p10_directional_settle_composition_audit(
        _json_object(args.active_compact),
        maximum_transition_observations=(
            args.maximum_transition_observations
        ),
    )
    _write_json(args.output, audit)
    print(audit["content_digest"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "P10_DIRECTIONAL_SETTLE_COMPOSITION_AUDIT_SCHEMA_VERSION",
    "build_p10_directional_settle_composition_audit",
    "main",
]
