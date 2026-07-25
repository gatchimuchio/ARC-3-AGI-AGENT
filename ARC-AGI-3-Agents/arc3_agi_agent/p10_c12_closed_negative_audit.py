"""Admit frozen C12 layout-mode harnesses as negative-only evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .schema import digest_object

P10_C12_CLOSED_NEGATIVE_AUDIT_SCHEMA_VERSION = (
    "arc3-p10-c12-closed-negative-admission-v1"
)
_CONTENT_DIGEST_PREFIX = (
    "arc3_p10_c12_closed_negative_admission:"
)
_PRIMARY_SOURCE_PATH = (
    "analysis/c12_layout_mode_commit_discriminator_capability_latest.json"
)
_AUXILIARY_SOURCE_PATH = (
    "analysis/layout_mode_discriminator_harness_analysis.json"
)
_CAPABILITY_ID = "C12_layout_mode_commit_discriminator"


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


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def _mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be an object")
    return value


def _sequence(value: object, field_name: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(
        value,
        (str, bytes, bytearray),
    ):
        raise TypeError(f"{field_name} must be an array")
    return value


def _source_descriptor(
    provenance: Mapping[str, Any],
    source_path: str,
) -> Mapping[str, Any]:
    sources = _sequence(provenance.get("sources"), "provenance sources")
    matches = tuple(
        item
        for item in sources
        if isinstance(item, Mapping)
        and item.get("path") == source_path
    )
    if len(matches) != 1:
        raise ValueError(
            "P10_C12_FROZEN_SOURCE_DESCRIPTOR_CARDINALITY_INVALID:"
            + source_path
        )
    return matches[0]


def _source_evidence(
    *,
    provenance_manifest: Mapping[str, Any],
    source_path: str,
    artifact: Mapping[str, Any],
    artifact_path: Path,
) -> tuple[dict[str, object], dict[str, bool]]:
    descriptor = _source_descriptor(provenance_manifest, source_path)
    actual_sha256 = _file_digest(artifact_path)
    actual_bytes = artifact_path.stat().st_size
    checks = {
        "descriptor_kind_analysis": descriptor.get("kind") == "analysis",
        "descriptor_materialized": (
            descriptor.get("parse_status") == "PARSED"
            and descriptor.get("extraction_status") == "MATERIALIZED"
        ),
        "source_sha256_matches_frozen_manifest": (
            descriptor.get("sha256") == actual_sha256
        ),
        "source_bytes_match_frozen_manifest": (
            descriptor.get("bytes") == actual_bytes
        ),
        "source_json_matches_loaded_mapping": (
            artifact == _json_object(artifact_path)
        ),
    }
    if not all(checks.values()):
        failures = sorted(
            key for key, passed in checks.items() if not passed
        )
        raise ValueError(
            "P10_C12_FROZEN_SOURCE_INVALID:"
            + source_path
            + ":"
            + ",".join(failures)
        )
    evidence: dict[str, object] = {
        "frozen_source_path": source_path,
        "retained_copy_filename": artifact_path.name,
        "sha256": actual_sha256,
        "bytes": actual_bytes,
        "record_id_count": len(
            _sequence(
                descriptor.get("record_ids"),
                f"{source_path} descriptor record ids",
            )
        ),
        "sensitive_path_count": descriptor.get(
            "sensitive_path_count"
        ),
    }
    return evidence, checks


def _scope_is_development_only(
    artifact: Mapping[str, Any],
) -> bool:
    scope = _mapping(artifact.get("scope"), "C12 source scope")
    return (
        scope.get("analysis_only") is True
        and scope.get("public_only_artifact") is True
        and scope.get("agent_core_changed") is False
        and scope.get("evaluator_path_changed") is False
        and scope.get("external_api_used") is False
        and scope.get("hidden_generalization_claim") is False
    )


def _primary_negative_checks(
    artifact: Mapping[str, Any],
) -> tuple[dict[str, bool], Mapping[str, Any]]:
    summary = _mapping(artifact.get("summary"), "C12 primary summary")
    checks = _mapping(artifact.get("checks"), "C12 primary checks")
    decision = _mapping(
        artifact.get("decision"),
        "C12 primary decision",
    )
    forbidden_inputs = _mapping(
        artifact.get("forbidden_inputs"),
        "C12 primary forbidden inputs",
    )
    expected_true_checks = {
        "agent_core_not_adopted",
        "all_contracts_defined_before_probe",
        "all_contracts_reject_closed_surfaces",
        "all_probes_bind_state_variables",
        "all_target_contracts_complete",
        "exact_public_replay_not_added",
        "hidden_generalization_not_claimed",
        "no_source_sprite_or_tag_state_used",
        "no_source_transition_table_used",
        "no_source_valid_actions_used",
        "runtime_stops_match_public_eval",
        "selected_capability_matches_input",
    }
    negative_checks = {
        "capability_id_matches": (
            artifact.get("capability_id") == _CAPABILITY_ID
            and summary.get("capability_id") == _CAPABILITY_ID
        ),
        "analysis_only_public_scope": (
            _scope_is_development_only(artifact)
        ),
        "forbidden_inputs_all_absent": all(
            value is False for value in forbidden_inputs.values()
        ),
        "required_legacy_checks_true": all(
            checks.get(key) is True for key in expected_true_checks
        ),
        "legacy_contract_spec_mismatch_explicit": (
            checks.get("probe_artifact_matches_contract_spec") is False
        ),
        "five_target_contracts_complete": (
            summary.get("target_count") == 5
            and summary.get("target_contract_count") == 5
            and summary.get("target_contract_complete_count") == 5
        ),
        "all_212_probes_layout_effect_only": (
            summary.get("total_probe_count") == 212
            and summary.get("layout_mode_commit_effect_probe_count")
            == 212
            and summary.get("actual_outcome_counts")
            == {"layout_commit_effect_only": 212}
        ),
        "visible_layout_counts_retained": (
            summary.get("changed_probe_count") == 140
            and summary.get("layout_mode_changed_probe_count") == 104
            and summary.get("layout_vector_changed_probe_count") == 212
            and summary.get("large_redraw_probe_count") == 197
        ),
        "stale_public_score_fields_explicit": (
            summary.get("public_total_levels") == 76
            and summary.get("public_total_win_levels") == 183
            and summary.get(
                "layout_commit_score_advance_probe_count"
            )
            == 36
            and summary.get(
                "layout_commit_score_regression_probe_count"
            )
            == 164
        ),
        "no_progress_observed": (
            summary.get("total_progress_count") == 0
            and summary.get("progress_separator_variable_count") == 0
        ),
        "no_hazard_separator_observed": (
            summary.get("total_game_over_count") == 0
            and summary.get("hazard_separator_variable_count") == 0
            and summary.get(
                "reusable_hazard_separator_variable_count"
            )
            == 0
        ),
        "no_promotion_variable_observed": (
            summary.get("promotion_eligible_variable_count") == 0
        ),
        "error_free_harness": summary.get("errors") == 0,
        "legacy_decision_closed_negative": (
            decision.get(
                "c12_layout_mode_commit_harness_closed_negative"
            )
            is True
            and decision.get("promotion_decision")
            == "REJECTED_NO_PROMOTION"
            and decision.get("promote_to_agent") is False
            and decision.get("agent_edit_required") is False
            and decision.get(
                "progress_or_reusable_hazard_separator_found"
            )
            is False
        ),
    }
    return negative_checks, summary


def _auxiliary_negative_checks(
    artifact: Mapping[str, Any],
) -> tuple[dict[str, bool], Mapping[str, Any]]:
    summary = _mapping(
        artifact.get("summary"),
        "C12 auxiliary summary",
    )
    decision = _mapping(
        artifact.get("decision"),
        "C12 auxiliary decision",
    )
    classifications = _mapping(
        summary.get("classification_counts"),
        "C12 auxiliary classifications",
    )
    negative_checks = {
        "analysis_only_public_scope": (
            _scope_is_development_only(artifact)
        ),
        "public_interaction_derived": (
            artifact.get("public_interaction_derived") is True
            and artifact.get("frame_derived_observation_parser") is True
        ),
        "source_and_hidden_inputs_absent": (
            artifact.get("source_sprite_or_tag_state_used") is False
            and artifact.get("source_transition_table_used") is False
            and artifact.get("source_valid_actions_used") is False
            and artifact.get("hidden_generalization_evidence") is False
        ),
        "public_replay_bootstrap_explicit": (
            artifact.get("public_replay_bootstrap_used") is True
        ),
        "five_targets_and_176_probes": (
            summary.get("target_count") == 5
            and summary.get("total_probe_count") == 176
            and sum(
                value
                for value in classifications.values()
                if isinstance(value, int)
            )
            == 176
        ),
        "visible_classification_counts_retained": (
            summary.get("total_changed_probe_count") == 86
            and classifications.get("large_redraw_same_mode") == 90
            and classifications.get(
                "layout_mode_transition_no_progress"
            )
            == 65
            and classifications.get("local_delta_same_mode") == 21
        ),
        "no_progress_or_positive_variable_observed": (
            summary.get("total_progress_count") == 0
            and summary.get("progress_game_count") == 0
            and summary.get("progress_games") == []
            and summary.get("positive_pre_action_variable_count") == 0
            and summary.get("positive_pre_action_variables") == []
        ),
        "no_game_over_observed": (
            summary.get("total_game_over_probe_count") == 0
        ),
        "legacy_decision_closed_negative": (
            decision.get("layout_mode_gate_passed") is False
            and decision.get("promotion_decision") == "AUDIT_ONLY"
            and decision.get("promote_to_agent") is False
            and decision.get("promote_hidden_general_claim") is False
        ),
        "agent_core_not_adopted": (
            artifact.get("agent_core_adopted") is False
        ),
    }
    return negative_checks, summary


def build_p10_c12_closed_negative_audit(
    *,
    provenance_manifest: Mapping[str, Any],
    primary_artifact: Mapping[str, Any],
    primary_artifact_path: Path,
    auxiliary_artifact: Mapping[str, Any],
    auxiliary_artifact_path: Path,
) -> dict[str, object]:
    """Bind two exact frozen layout-mode sources to a negative judgment."""

    primary_evidence, primary_source_checks = _source_evidence(
        provenance_manifest=provenance_manifest,
        source_path=_PRIMARY_SOURCE_PATH,
        artifact=primary_artifact,
        artifact_path=primary_artifact_path,
    )
    auxiliary_evidence, auxiliary_source_checks = _source_evidence(
        provenance_manifest=provenance_manifest,
        source_path=_AUXILIARY_SOURCE_PATH,
        artifact=auxiliary_artifact,
        artifact_path=auxiliary_artifact_path,
    )
    primary_checks, primary_summary = _primary_negative_checks(
        primary_artifact
    )
    auxiliary_checks, auxiliary_summary = (
        _auxiliary_negative_checks(auxiliary_artifact)
    )
    negative_checks = {
        "primary": primary_checks,
        "auxiliary": auxiliary_checks,
    }
    failed_checks = sorted(
        f"{group}.{key}"
        for group, checks in negative_checks.items()
        for key, passed in checks.items()
        if not passed
    )
    if failed_checks:
        raise ValueError(
            "P10_C12_NEGATIVE_EVIDENCE_INVALID:"
            + ",".join(failed_checks)
        )

    body: dict[str, object] = {
        "schema_version": (
            P10_C12_CLOSED_NEGATIVE_AUDIT_SCHEMA_VERSION
        ),
        "artifact_type": (
            "arc3_p10_c12_closed_negative_admission"
        ),
        "phase": "P10_COMPLETE_ARC3_SAMPLE_SOLVING",
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "capability_id": _CAPABILITY_ID,
        "source_evidence": {
            "primary": primary_evidence,
            "auxiliary": auxiliary_evidence,
        },
        "source_checks": {
            "primary": primary_source_checks,
            "auxiliary": auxiliary_source_checks,
        },
        "negative_checks": negative_checks,
        "retained_measurements": {
            "primary_target_count": primary_summary.get("target_count"),
            "primary_total_probe_count": primary_summary.get(
                "total_probe_count"
            ),
            "primary_changed_probe_count": primary_summary.get(
                "changed_probe_count"
            ),
            "primary_layout_mode_changed_probe_count": (
                primary_summary.get("layout_mode_changed_probe_count")
            ),
            "auxiliary_target_count": auxiliary_summary.get(
                "target_count"
            ),
            "auxiliary_total_probe_count": auxiliary_summary.get(
                "total_probe_count"
            ),
            "auxiliary_changed_probe_count": auxiliary_summary.get(
                "total_changed_probe_count"
            ),
            "combined_probe_count": 388,
            "combined_changed_probe_count": 226,
            "combined_progress_count": 0,
            "combined_game_over_count": 0,
            "progress_separator_variable_count": 0,
            "hazard_separator_variable_count": 0,
            "reusable_hazard_separator_variable_count": 0,
            "promotion_eligible_variable_count": 0,
            "primary_error_count": 0,
            "quarantined_stale_primary_score_fields": {
                "public_total_levels": primary_summary.get(
                    "public_total_levels"
                ),
                "public_total_win_levels": primary_summary.get(
                    "public_total_win_levels"
                ),
                "layout_commit_score_advance_probe_count": (
                    primary_summary.get(
                        "layout_commit_score_advance_probe_count"
                    )
                ),
                "layout_commit_score_regression_probe_count": (
                    primary_summary.get(
                        "layout_commit_score_regression_probe_count"
                    )
                ),
            },
        },
        "admission_scope": {
            "admitted_for_negative_surface_closure": True,
            "admitted_for_runtime_compile": False,
            "admitted_for_runtime_promotion": False,
            "admitted_for_positive_generalization_claim": False,
            "legacy_contract_spec_mismatch_quarantined": True,
            "auxiliary_public_replay_bootstrap_quarantined": True,
            "stale_public_score_fields_quarantined": True,
            "same_layout_mode_surface_retry_has_new_information": False,
        },
        "hds_judgment": {
            "authority": "development-hds-only",
            "status": "REJECT",
            "causal_result": "CLOSED_NEGATIVE",
            "current_tier": "LOCAL_PROBE",
            "work_block_status": "CLOSED_NEGATIVE",
            "same_surface_retry_authorized": False,
            "runtime_p_compile_authorized": False,
            "runtime_p_promotion_authorized": False,
            "score_progress_claim_authorized": False,
            "next_work_block_id": (
                "WB-C1_rendered_affordance_objectizer"
            ),
            "reason_codes": [
                "two-frozen-sources-match-p3-provenance",
                "legacy-contract-spec-mismatch-negative-only",
                "auxiliary-public-replay-bootstrap-quarantined",
                "388-layout-mode-probes-zero-progress",
                "zero-hazard-separators",
                "zero-promotion-eligible-variables",
                "select-next-unembedded-high-support-capability",
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
            "Admit exact frozen C12 layout-mode harnesses for "
            "negative-only P10 development accounting."
        )
    )
    parser.add_argument("--provenance-manifest", type=Path, required=True)
    parser.add_argument("--primary-artifact", type=Path, required=True)
    parser.add_argument("--auxiliary-artifact", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    audit = build_p10_c12_closed_negative_audit(
        provenance_manifest=_json_object(args.provenance_manifest),
        primary_artifact=_json_object(args.primary_artifact),
        primary_artifact_path=args.primary_artifact,
        auxiliary_artifact=_json_object(args.auxiliary_artifact),
        auxiliary_artifact_path=args.auxiliary_artifact,
    )
    _write_json(args.output, audit)
    print(audit["content_digest"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "P10_C12_CLOSED_NEGATIVE_AUDIT_SCHEMA_VERSION",
    "build_p10_c12_closed_negative_audit",
    "main",
]
