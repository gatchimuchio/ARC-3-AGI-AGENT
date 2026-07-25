"""Bind C2 observation and C10 causal context with removal controls.

This development-only audit is the COMPOSABLE gate between cluster evidence
and a candidate Runtime P compile.  It does not execute actions or mutate P.
It accepts C2 only as a post-action visible-effect observer and C10 only as a
within-session prequential learner.  Fixed cross-game outcome labels and the
still-weak C3 commit predictor are explicitly excluded from the candidate.
"""

from __future__ import annotations

import argparse
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .schema import digest_object, forbidden_runtime_paths

C2_C10_COMPOSITION_AUDIT_SCHEMA_VERSION = (
    "arc3-p10-c2-c10-composition-removal-audit-v1"
)
_CONTENT_DIGEST_PREFIX = "arc3_p10_c2_c10_composition_audit:"
_C2_CAPABILITY_ID = "C2_visible_effect_transition_model"
_C3_CAPABILITY_ID = "C3_commit_boundary_predictor"
_C10_CAPABILITY_ID = "C10_phase_timer_unlock_model"
_C2_C3_DIGEST_PREFIX = "arc3_c2_c3_predictive_cluster_audit:"
_C10_DIGEST_PREFIX = "arc3_c10_temporal_causal_contrast_audit:"


def _object(
    value: object,
    field_name: str,
) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be an object")
    return value


def _integer(
    value: object,
    field_name: str,
) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    return value


def _content_digest_valid(
    value: Mapping[str, Any],
    prefix: str,
) -> bool:
    body = dict(value)
    claimed = str(body.pop("content_digest", ""))
    return claimed == prefix + digest_object(body)


def build_c2_c10_composition_audit(
    *,
    c2_c3_audit: Mapping[str, Any],
    c10_audit: Mapping[str, Any],
) -> dict[str, Any]:
    """Return an HDS candidate-compile decision with removal evidence."""

    c2_c3_tiers = _object(
        c2_c3_audit.get("capability_tiers"),
        "c2_c3 capability_tiers",
    )
    c2_c3_judgment = _object(
        c2_c3_audit.get("hds_judgment"),
        "c2_c3 hds_judgment",
    )
    c10_judgment = _object(
        c10_audit.get("hds_judgment"),
        "c10 hds_judgment",
    )
    c10_checks = _object(
        c10_audit.get("predictive_checks"),
        "c10 predictive_checks",
    )
    c10_summary = _object(
        c10_audit.get("summary"),
        "c10 summary",
    )
    c10_evaluation = _object(
        c10_audit.get("predictive_evaluation"),
        "c10 predictive_evaluation",
    )
    prequential = _object(
        c10_evaluation.get("within_game_prequential"),
        "within_game_prequential",
    )
    baseline = _object(
        prequential.get("ambiguous_baseline"),
        "ambiguous_baseline",
    )
    full_context = _object(
        prequential.get("ambiguous_context"),
        "ambiguous_context",
    )
    action_only = _object(
        prequential.get("ambiguous_action_only"),
        "ambiguous_action_only",
    )

    candidate_contract: dict[str, object] = {
        "capability_ids": [
            _C2_CAPABILITY_ID,
            _C10_CAPABILITY_ID,
        ],
        "input": {
            "current rendered state signature": "visible only",
            "current action prototype": "visible affordance only",
            "previous action prototype": "passive session memory",
            "previous coarse visible outcome": [
                "TRANSITION",
                "NO_CHANGE",
                "HAZARD",
            ],
        },
        "state_update_order": [
            "predict before current action",
            "observe current visible effect through C2",
            "HDS accepts or rejects the observation",
            "retain only accepted bounded context",
            "use retained context on the next prediction",
        ],
        "bounds": {
            "history_depth": 1,
            "current_or_future_outcome_as_prediction_input": False,
            "task_or_level_identity": False,
            "fixed_result_label_transfer": False,
            "timer_or_path_length_selector": False,
        },
        "excluded_capability": {
            "capability_id": _C3_CAPABILITY_ID,
            "reason": "non-circular commit prediction remains HOLD",
        },
    }
    contract_identity_free = not forbidden_runtime_paths(
        candidate_contract
    )

    integrity_checks = {
        "c2_c3_schema_v2": (
            c2_c3_audit.get("schema_version")
            == "arc3-c2-c3-predictive-cluster-audit-v2"
        ),
        "c10_schema_v2": (
            c10_audit.get("schema_version")
            == "arc3-p10-c10-temporal-causal-contrast-audit-v2"
        ),
        "c2_c3_content_digest_valid": _content_digest_valid(
            c2_c3_audit,
            _C2_C3_DIGEST_PREFIX,
        ),
        "c10_content_digest_valid": _content_digest_valid(
            c10_audit,
            _C10_DIGEST_PREFIX,
        ),
        "both_inputs_development_only": (
            c2_c3_audit.get("development_only") is True
            and c10_audit.get("development_only") is True
        ),
        "both_inputs_forbid_runtime_use": (
            c2_c3_audit.get("runtime_use") == "FORBIDDEN"
            and c10_audit.get("runtime_use") == "FORBIDDEN"
        ),
        "candidate_contract_identity_free": contract_identity_free,
        "audit_did_not_execute_actions": True,
        "audit_did_not_mutate_runtime_p": True,
    }
    integrity_failures = sorted(
        key for key, passed in integrity_checks.items() if not passed
    )
    if integrity_failures:
        raise ValueError(
            "C2_C10_COMPOSITION_INPUT_INTEGRITY_FAILED:"
            + ",".join(integrity_failures)
        )

    baseline_accuracy = _integer(
        baseline.get("accuracy_milli"),
        "baseline accuracy",
    )
    full_accuracy = _integer(
        full_context.get("accuracy_milli"),
        "full context accuracy",
    )
    action_only_accuracy = _integer(
        action_only.get("accuracy_milli"),
        "action only accuracy",
    )
    remove_c10_delta = full_accuracy - baseline_accuracy
    remove_c2_delta = full_accuracy - action_only_accuracy
    all_transition_delta = _integer(
        c10_summary.get("prequential_all_accuracy_delta_milli"),
        "all transition accuracy delta",
    )
    held_out_positive_count = _integer(
        c10_summary.get("held_out_positive_game_count"),
        "held out positive game count",
    )
    composable_checks = {
        "c2_observer_cluster_stable": (
            c2_c3_tiers.get(_C2_CAPABILITY_ID)
            == "CLUSTER_STABLE"
            and c2_c3_judgment.get(
                "c2_cluster_stable_observer_status"
            )
            == "PASS"
        ),
        "c3_predictor_excluded_while_hold": (
            c2_c3_tiers.get(_C3_CAPABILITY_ID) == "LOCAL_PROBE"
            and c2_c3_judgment.get(
                "c3_cluster_stable_predictor_status"
            )
            == "HOLD"
        ),
        "c10_context_cluster_stable": (
            c10_audit.get("candidate_tier") == "CLUSTER_STABLE"
            and c10_judgment.get("cluster_stable_status") == "PASS"
        ),
        "all_c10_predictive_checks_pass": all(
            value is True for value in c10_checks.values()
        ),
        "remove_c10_has_positive_delta": remove_c10_delta > 0,
        "remove_c2_observed_outcome_has_positive_delta": (
            remove_c2_delta > 0
        ),
        "all_transition_accuracy_nonregression": (
            all_transition_delta >= 0
        ),
        "held_out_mechanism_support_at_least_two": (
            held_out_positive_count >= 2
        ),
        "candidate_contract_history_depth_one": True,
        "fixed_cross_game_outcome_mapping_excluded": (
            c10_judgment.get("cross_game_outcome_mapping_status")
            == "HOLD"
        ),
    }
    composable = all(composable_checks.values())
    body: dict[str, Any] = {
        "schema_version": C2_C10_COMPOSITION_AUDIT_SCHEMA_VERSION,
        "artifact_type": "arc3_p10_c2_c10_composition_removal_audit",
        "phase": "P10_COMPLETE_ARC3_SAMPLE_SOLVING",
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "capability_ids": [
            _C2_CAPABILITY_ID,
            _C10_CAPABILITY_ID,
        ],
        "candidate_tier": (
            "COMPOSABLE" if composable else "CLUSTER_STABLE"
        ),
        "source_evidence": {
            "c2_c3_content_digest": c2_c3_audit.get(
                "content_digest"
            ),
            "c10_content_digest": c10_audit.get("content_digest"),
        },
        "candidate_contract": candidate_contract,
        "removal_evaluation": {
            "full_c2_c10_accuracy_milli": full_accuracy,
            "remove_c10_accuracy_milli": baseline_accuracy,
            "remove_c10_delta_milli": remove_c10_delta,
            "remove_c2_outcome_accuracy_milli": (
                action_only_accuracy
            ),
            "remove_c2_outcome_delta_milli": remove_c2_delta,
            "all_transition_accuracy_delta_milli": (
                all_transition_delta
            ),
            "held_out_positive_game_count": (
                held_out_positive_count
            ),
        },
        "integrity_checks": integrity_checks,
        "composable_checks": composable_checks,
        "hds_judgment": {
            "composable_status": "PASS" if composable else "HOLD",
            "runtime_p_candidate_compile_authorized": composable,
            "runtime_p_active_compile_authorized": False,
            "runtime_p_promotion_authorized": False,
            "score_progress_claim_authorized": False,
            "reason_codes": [
                (
                    "C2_C10_REMOVAL_AND_HELD_OUT_CONTROLS_PASS"
                    if composable
                    else "C2_C10_COMPOSITION_EVIDENCE_INSUFFICIENT"
                ),
                "C3_COMMIT_PREDICTOR_EXCLUDED",
                "ACTIVE_P_REMAINS_UNCHANGED",
            ],
            "next_bounded_experiment": (
                "compile only the bounded C2 plus C10 contract into a "
                "candidate P under HDS PROBE, then compare candidate, "
                "unchanged active, and removal controls"
                if composable
                else "retain the cluster candidate outside Runtime P"
            ),
        },
    }
    return {
        **body,
        "content_digest": _CONTENT_DIGEST_PREFIX + digest_object(body),
    }


def _json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def write_c2_c10_composition_audit(
    *,
    c2_c3_audit_path: Path,
    c10_audit_path: Path,
    output_path: Path,
) -> Path:
    value = build_c2_c10_composition_audit(
        c2_c3_audit=_json_object(c2_c3_audit_path),
        c10_audit=_json_object(c10_audit_path),
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
        description="Audit C2 plus C10 composition and removals."
    )
    parser.add_argument("--c2-c3-audit", type=Path, required=True)
    parser.add_argument("--c10-audit", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    output = write_c2_c10_composition_audit(
        c2_c3_audit_path=args.c2_c3_audit,
        c10_audit_path=args.c10_audit,
        output_path=args.output,
    )
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "C2_C10_COMPOSITION_AUDIT_SCHEMA_VERSION",
    "build_c2_c10_composition_audit",
    "write_c2_c10_composition_audit",
]
