"""Close the remaining provenance-frozen negative capability surfaces."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .schema import digest_object

P10_FROZEN_NEGATIVE_ADMISSION_SCHEMA_VERSION = (
    "arc3-p10-frozen-negative-admission-v1"
)
P10_REMAINING_NEGATIVE_CATALOG_SCHEMA_VERSION = (
    "arc3-p10-remaining-frozen-negative-catalog-v1"
)
_ADMISSION_DIGEST_PREFIX = "arc3_p10_frozen_negative_admission:"
_CATALOG_DIGEST_PREFIX = (
    "arc3_p10_remaining_frozen_negative_catalog:"
)
_NEXT_GENERATIVE_WORK_BLOCK = (
    "WB-PROSPECTIVE-OBLIGATION-RELATION-COMPILER"
)


@dataclass(frozen=True)
class FrozenNegativeSpec:
    """Exact immutable contract for one frozen capability harness."""

    rank: int
    capability_id: str
    source_path: str
    retained_filename: str
    audit_filename: str
    source_artifact_type: str
    decision_closed_key: str
    decision_ready_key: str
    target_count: int
    probe_count: int
    changed_probe_count: int
    progress_count: int
    game_over_count: int
    summary_support_count: int | None
    support_row_count: int | None
    reusable_hazard_separator_count: int | None
    error_count: int | None
    stale_score_fields: bool
    semantic_summary_fields: tuple[tuple[str, object], ...]
    next_work_block_id: str


FROZEN_NEGATIVE_SPECS: tuple[FrozenNegativeSpec, ...] = (
    FrozenNegativeSpec(
        rank=6,
        capability_id="C14_symbolic_relation_commit_model",
        source_path=(
            "analysis/"
            "c14_symbolic_relation_commit_model_capability_latest.json"
        ),
        retained_filename=(
            "LEGACY_C14_SYMBOLIC_RELATION_COMMIT_MODEL_CAPABILITY.json"
        ),
        audit_filename=(
            "C14_SYMBOLIC_RELATION_CLOSED_NEGATIVE_AUDIT.json"
        ),
        source_artifact_type=(
            "arc3_c14_symbolic_relation_commit_model_capability_harness"
        ),
        decision_closed_key=(
            "c14_symbolic_relation_commit_harness_closed_negative"
        ),
        decision_ready_key=(
            "c14_symbolic_relation_commit_harness_ready"
        ),
        target_count=3,
        probe_count=252,
        changed_probe_count=180,
        progress_count=0,
        game_over_count=0,
        summary_support_count=9,
        support_row_count=9,
        reusable_hazard_separator_count=0,
        error_count=0,
        stale_score_fields=True,
        semantic_summary_fields=(
            ("symbolic_relation_commit_effect_probe_count", 252),
            ("relation_vector_changed_probe_count", 54),
            ("relation_state_changed_probe_count", 0),
            ("closed_surface_collapse_probe_count", 216),
        ),
        next_work_block_id="WB-C8_helper_handoff_state_model",
    ),
    FrozenNegativeSpec(
        rank=7,
        capability_id="C8_helper_handoff_state_model",
        source_path=(
            "analysis/c8_helper_handoff_state_model_capability_latest.json"
        ),
        retained_filename=(
            "LEGACY_C8_HELPER_HANDOFF_STATE_MODEL_CAPABILITY.json"
        ),
        audit_filename="C8_HELPER_HANDOFF_CLOSED_NEGATIVE_AUDIT.json",
        source_artifact_type=(
            "arc3_c8_helper_handoff_state_model_capability_harness"
        ),
        decision_closed_key="c8_helper_handoff_harness_closed_negative",
        decision_ready_key="c8_helper_handoff_harness_ready",
        target_count=3,
        probe_count=203,
        changed_probe_count=131,
        progress_count=0,
        game_over_count=0,
        summary_support_count=None,
        support_row_count=9,
        reusable_hazard_separator_count=0,
        error_count=None,
        stale_score_fields=False,
        semantic_summary_fields=(
            ("helper_handoff_effect_probe_count", 203),
            ("binding_signature_changed_probe_count", 131),
            ("helper_state_changed_probe_count", 0),
            ("closed_surface_collapse_probe_count", 203),
        ),
        next_work_block_id="WB-C4_hazard_rollback_verifier",
    ),
    FrozenNegativeSpec(
        rank=8,
        capability_id="C4_hazard_rollback_verifier",
        source_path=(
            "analysis/c4_hazard_rollback_verifier_capability_latest.json"
        ),
        retained_filename=(
            "LEGACY_C4_HAZARD_ROLLBACK_VERIFIER_CAPABILITY.json"
        ),
        audit_filename="C4_HAZARD_ROLLBACK_CLOSED_NEGATIVE_AUDIT.json",
        source_artifact_type=(
            "arc3_c4_hazard_rollback_verifier_capability_harness"
        ),
        decision_closed_key=(
            "c4_hazard_rollback_verifier_harness_closed_negative"
        ),
        decision_ready_key=(
            "c4_hazard_rollback_verifier_harness_ready"
        ),
        target_count=8,
        probe_count=77,
        changed_probe_count=77,
        progress_count=0,
        game_over_count=0,
        summary_support_count=9,
        support_row_count=9,
        reusable_hazard_separator_count=0,
        error_count=0,
        stale_score_fields=True,
        semantic_summary_fields=(
            ("rollback_cycle_effect_probe_count", 1),
            ("safe_cycle_exit_probe_count", 1),
            ("unsafe_hazard_probe_count", 0),
            ("closed_surface_collapse_probe_count", 76),
        ),
        next_work_block_id="WB-C6_action_channel_emitter_model",
    ),
    FrozenNegativeSpec(
        rank=9,
        capability_id="C6_action_channel_emitter_model",
        source_path=(
            "analysis/"
            "c6_action_channel_emitter_model_capability_latest.json"
        ),
        retained_filename=(
            "LEGACY_C6_ACTION_CHANNEL_EMITTER_MODEL_CAPABILITY.json"
        ),
        audit_filename="C6_ACTION_CHANNEL_CLOSED_NEGATIVE_AUDIT.json",
        source_artifact_type=(
            "arc3_c6_action_channel_emitter_model_capability_harness"
        ),
        decision_closed_key=(
            "c6_action_channel_emitter_model_harness_closed_negative"
        ),
        decision_ready_key=(
            "c6_action_channel_emitter_model_harness_ready"
        ),
        target_count=2,
        probe_count=20,
        changed_probe_count=20,
        progress_count=0,
        game_over_count=0,
        summary_support_count=9,
        support_row_count=9,
        reusable_hazard_separator_count=None,
        error_count=0,
        stale_score_fields=True,
        semantic_summary_fields=(
            ("channel_effect_probe_count", 5),
            ("channel_readiness_key_delta_probe_count", 5),
            ("emitter_gap_reduction_probe_count", 0),
            ("closed_surface_collapse_probe_count", 15),
        ),
        next_work_block_id="WB-C9_token_slot_submission_verifier",
    ),
    FrozenNegativeSpec(
        rank=11,
        capability_id="C9_token_slot_submission_verifier",
        source_path=(
            "analysis/"
            "c9_token_slot_submission_verifier_capability_latest.json"
        ),
        retained_filename=(
            "LEGACY_C9_TOKEN_SLOT_SUBMISSION_VERIFIER_CAPABILITY.json"
        ),
        audit_filename=(
            "C9_TOKEN_SLOT_SUBMISSION_CLOSED_NEGATIVE_AUDIT.json"
        ),
        source_artifact_type=(
            "arc3_c9_token_slot_submission_verifier_capability_harness"
        ),
        decision_closed_key=(
            "c9_token_slot_submission_harness_closed_negative"
        ),
        decision_ready_key="c9_token_slot_submission_harness_ready",
        target_count=2,
        probe_count=154,
        changed_probe_count=61,
        progress_count=0,
        game_over_count=0,
        summary_support_count=None,
        support_row_count=9,
        reusable_hazard_separator_count=0,
        error_count=None,
        stale_score_fields=False,
        semantic_summary_fields=(
            ("token_slot_submission_effect_probe_count", 154),
            ("assignment_changed_probe_count", 25),
            ("submission_state_changed_probe_count", 0),
            ("closed_surface_collapse_probe_count", 154),
        ),
        next_work_block_id=(
            "WB-C11_route_terminal_reachability_verifier"
        ),
    ),
    FrozenNegativeSpec(
        rank=12,
        capability_id="C11_route_terminal_reachability_verifier",
        source_path=(
            "analysis/"
            "c11_route_terminal_reachability_verifier_"
            "capability_latest.json"
        ),
        retained_filename=(
            "LEGACY_C11_ROUTE_TERMINAL_REACHABILITY_"
            "VERIFIER_CAPABILITY.json"
        ),
        audit_filename=(
            "C11_ROUTE_TERMINAL_CLOSED_NEGATIVE_AUDIT.json"
        ),
        source_artifact_type=(
            "arc3_c11_route_terminal_reachability_"
            "verifier_capability_harness"
        ),
        decision_closed_key=(
            "c11_route_terminal_reachability_"
            "verifier_harness_closed_negative"
        ),
        decision_ready_key=(
            "c11_route_terminal_reachability_verifier_harness_ready"
        ),
        target_count=2,
        probe_count=96,
        changed_probe_count=0,
        progress_count=0,
        game_over_count=5,
        summary_support_count=71,
        support_row_count=71,
        reusable_hazard_separator_count=0,
        error_count=0,
        stale_score_fields=True,
        semantic_summary_fields=(
            ("depth1_probe_count", 8),
            ("depth2_probe_count", 16),
            ("depth3_probe_count", 28),
        ),
        next_work_block_id="WB-C13_support_bridge_slider_model",
    ),
    FrozenNegativeSpec(
        rank=13,
        capability_id="C13_support_bridge_slider_model",
        source_path=(
            "analysis/"
            "c13_support_bridge_slider_model_capability_latest.json"
        ),
        retained_filename=(
            "LEGACY_C13_SUPPORT_BRIDGE_SLIDER_MODEL_CAPABILITY.json"
        ),
        audit_filename=(
            "C13_SUPPORT_BRIDGE_SLIDER_CLOSED_NEGATIVE_AUDIT.json"
        ),
        source_artifact_type=(
            "arc3_c13_support_bridge_slider_model_capability_harness"
        ),
        decision_closed_key=(
            "c13_support_bridge_slider_model_harness_closed_negative"
        ),
        decision_ready_key=(
            "c13_support_bridge_slider_model_harness_ready"
        ),
        target_count=1,
        probe_count=1397,
        changed_probe_count=96,
        progress_count=0,
        game_over_count=0,
        summary_support_count=60,
        support_row_count=60,
        reusable_hazard_separator_count=0,
        error_count=0,
        stale_score_fields=True,
        semantic_summary_fields=(
            ("support_bridge_progress_probe_count", 0),
            ("axis14_plateau_transition_count", 1086),
            ("physical_transition_count", 1666),
            ("status_change_transition_count", 2536),
        ),
        next_work_block_id=_NEXT_GENERATIVE_WORK_BLOCK,
    ),
)

_EXPECTED_TRUE_CHECKS = {
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
            "P10_FROZEN_NEGATIVE_SOURCE_DESCRIPTOR_"
            f"CARDINALITY_INVALID:{source_path}"
        )
    return matches[0]


def _support_rows_are_negative(
    rows: object,
    *,
    reusable_field_required: bool,
) -> bool:
    support_rows = _sequence(rows, "support variables")
    return all(
        isinstance(raw, Mapping)
        and isinstance(raw.get("variable"), str)
        and raw.get("level_progress_separator") is False
        and raw.get("hazard_separator") is False
        and (
            not reusable_field_required
            or raw.get("reusable_hazard_separator") is False
        )
        and raw.get("promotion_eligible") is False
        for raw in support_rows
    )


def _forbidden_inputs_are_absent(
    artifact: Mapping[str, Any],
) -> bool:
    encoded = artifact.get("forbidden_inputs")
    if isinstance(encoded, Mapping):
        return bool(encoded) and all(
            value is False for value in encoded.values()
        )

    audit_rules = artifact.get("audit_rules")
    scope = artifact.get("scope")
    return (
        isinstance(audit_rules, Mapping)
        and isinstance(scope, Mapping)
        and artifact.get("source_sprite_or_tag_state_used") is False
        and artifact.get("source_transition_table_used") is False
        and artifact.get("source_valid_actions_used") is False
        and artifact.get("agent_core_adopted") is False
        and artifact.get("hidden_generalization_evidence") is False
        and scope.get("external_api_used") is False
        and scope.get("exact_public_replay_added") is False
        and scope.get("hidden_generalization_claim") is False
        and audit_rules.get(
            "exact_public_replay_addition_disallowed"
        )
        is True
        and audit_rules.get("hidden_generalization_claim_disallowed")
        is True
        and audit_rules.get(
            "runtime_promotion_requires_progress_or_reusable_hazard_separator"
        )
        is True
    )


def _support_rows(artifact: Mapping[str, Any]) -> object:
    if "support_variables" in artifact:
        return artifact["support_variables"]
    return artifact.get("support_variable_rows", ())


def _scope_is_development_only(artifact: Mapping[str, Any]) -> bool:
    scope = _mapping(artifact.get("scope"), "frozen source scope")
    return (
        scope.get("analysis_only") is True
        and scope.get("public_only_artifact") is True
        and scope.get("agent_core_changed") is False
        and scope.get("evaluator_path_changed") is False
        and scope.get("external_api_used") is False
        and scope.get("hidden_generalization_claim") is False
        and scope.get("exact_public_replay_added") is False
    )


def build_frozen_negative_admission(
    *,
    spec: FrozenNegativeSpec,
    provenance_manifest: Mapping[str, Any],
    legacy_artifact: Mapping[str, Any],
    legacy_artifact_path: Path,
) -> dict[str, object]:
    """Bind one exact frozen harness to a negative-only HDS judgment."""

    descriptor = _source_descriptor(
        provenance_manifest,
        spec.source_path,
    )
    actual_sha256 = _file_digest(legacy_artifact_path)
    actual_bytes = legacy_artifact_path.stat().st_size
    source_checks = {
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
            legacy_artifact == _json_object(legacy_artifact_path)
        ),
    }
    if not all(source_checks.values()):
        failures = sorted(
            key for key, passed in source_checks.items() if not passed
        )
        raise ValueError(
            "P10_FROZEN_NEGATIVE_SOURCE_INVALID:"
            + spec.capability_id
            + ":"
            + ",".join(failures)
        )

    summary = _mapping(
        legacy_artifact.get("summary"),
        f"{spec.capability_id} summary",
    )
    decision = _mapping(
        legacy_artifact.get("decision"),
        f"{spec.capability_id} decision",
    )
    checks_value = legacy_artifact.get("checks")
    checks = checks_value if isinstance(checks_value, Mapping) else {}
    support_rows = _support_rows(legacy_artifact)
    support_row_count = len(
        _sequence(support_rows, "support variables")
    )
    expected_semantic = dict(spec.semantic_summary_fields)

    negative_checks = {
        "capability_and_artifact_type_match": (
            legacy_artifact.get("capability_id") == spec.capability_id
            and summary.get("capability_id") == spec.capability_id
            and legacy_artifact.get("artifact_type")
            == spec.source_artifact_type
        ),
        "analysis_only_public_scope": (
            _scope_is_development_only(legacy_artifact)
        ),
        "forbidden_inputs_all_absent": (
            _forbidden_inputs_are_absent(legacy_artifact)
        ),
        "optional_legacy_checks_consistent": (
            not checks
            or (
                all(
                    checks.get(key) is True
                    for key in _EXPECTED_TRUE_CHECKS
                )
                and checks.get("probe_artifact_matches_contract_spec")
                is False
            )
        ),
        "target_contracts_complete": (
            summary.get("target_count") == spec.target_count
            and summary.get("target_contract_count")
            == spec.target_count
            and summary.get("target_contract_complete_count")
            == spec.target_count
        ),
        "probe_and_change_counts_match": (
            summary.get("total_probe_count") == spec.probe_count
            and summary.get("changed_probe_count")
            == spec.changed_probe_count
        ),
        "no_progress_observed": (
            summary.get("total_progress_count") == spec.progress_count
            and spec.progress_count == 0
            and summary.get("progress_separator_variable_count") == 0
        ),
        "no_reusable_hazard_separator_observed": (
            summary.get("total_game_over_count")
            == spec.game_over_count
            and summary.get("hazard_separator_variable_count") == 0
            and (
                spec.reusable_hazard_separator_count is None
                or summary.get(
                    "reusable_hazard_separator_variable_count"
                )
                == spec.reusable_hazard_separator_count
            )
        ),
        "no_promotion_variable_observed": (
            summary.get("promotion_eligible_variable_count") == 0
        ),
        "support_summary_count_matches": (
            spec.summary_support_count is None
            or summary.get("support_variable_count")
            == spec.summary_support_count
        ),
        "support_rows_are_negative": (
            spec.support_row_count is None
            or (
                support_row_count == spec.support_row_count
                and _support_rows_are_negative(
                    support_rows,
                    reusable_field_required=(
                        spec.reusable_hazard_separator_count is not None
                    ),
                )
            )
        ),
        "separator_rows_are_empty": all(
            legacy_artifact.get(field_name, []) == []
            for field_name in (
                "progress_separator_rows",
                "hazard_separator_rows",
                "promotion_eligible_rows",
            )
        ),
        "semantic_counts_match": all(
            summary.get(field_name) == expected
            for field_name, expected in expected_semantic.items()
        ),
        "error_count_matches": (
            spec.error_count is None
            or (
                summary.get("errors") == spec.error_count
                and summary.get("maxed_out_count") == 0
            )
        ),
        "stale_score_fields_explicit_when_expected": (
            not spec.stale_score_fields
            or (
                summary.get("public_total_levels") == 76
                and summary.get("public_total_win_levels") == 183
            )
        ),
        "legacy_decision_closed_negative": (
            decision.get(spec.decision_closed_key) is True
            and decision.get(spec.decision_ready_key) is True
            and decision.get("promotion_decision")
            == "REJECTED_NO_PROMOTION"
            and decision.get("promotion_candidate") is False
            and decision.get("promote_to_agent") is False
            and decision.get("agent_edit_required") is False
            and decision.get(
                "progress_or_reusable_hazard_separator_found"
            )
            is False
            and decision.get(
                "exact_or_single_surface_hazard_separator_found"
            )
            is False
        ),
    }
    if not all(negative_checks.values()):
        failures = sorted(
            key for key, passed in negative_checks.items() if not passed
        )
        raise ValueError(
            "P10_FROZEN_NEGATIVE_EVIDENCE_INVALID:"
            + spec.capability_id
            + ":"
            + ",".join(failures)
        )

    body: dict[str, object] = {
        "schema_version": P10_FROZEN_NEGATIVE_ADMISSION_SCHEMA_VERSION,
        "artifact_type": "arc3_p10_frozen_negative_admission",
        "phase": "P10_COMPLETE_ARC3_SAMPLE_SOLVING",
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "queue_rank": spec.rank,
        "capability_id": spec.capability_id,
        "source_evidence": {
            "frozen_source_path": spec.source_path,
            "retained_copy_filename": legacy_artifact_path.name,
            "sha256": actual_sha256,
            "bytes": actual_bytes,
            "record_id_count": len(
                _sequence(
                    descriptor.get("record_ids"),
                    "frozen descriptor record ids",
                )
            ),
            "sensitive_path_count": descriptor.get(
                "sensitive_path_count"
            ),
        },
        "source_checks": source_checks,
        "negative_checks": negative_checks,
        "retained_measurements": {
            "target_count": spec.target_count,
            "total_probe_count": spec.probe_count,
            "changed_probe_count": spec.changed_probe_count,
            "total_progress_count": spec.progress_count,
            "total_game_over_count": spec.game_over_count,
            "progress_separator_variable_count": 0,
            "hazard_separator_variable_count": 0,
            "reusable_hazard_separator_variable_count": (
                spec.reusable_hazard_separator_count
            ),
            "promotion_eligible_variable_count": 0,
            "summary_support_variable_count": (
                spec.summary_support_count
            ),
            "retained_support_row_count": support_row_count,
            "error_count": spec.error_count,
            "semantic_measurements": expected_semantic,
            "quarantined_stale_score_fields": (
                {
                    "public_total_levels": summary.get(
                        "public_total_levels"
                    ),
                    "public_total_win_levels": summary.get(
                        "public_total_win_levels"
                    ),
                }
                if spec.stale_score_fields
                else {}
            ),
        },
        "admission_scope": {
            "admitted_for_negative_surface_closure": True,
            "admitted_for_runtime_compile": False,
            "admitted_for_runtime_promotion": False,
            "admitted_for_positive_generalization_claim": False,
            "identity_and_literal_coordinates_quarantined": True,
            "stale_public_score_fields_quarantined": (
                spec.stale_score_fields
            ),
            "observed_game_over_without_reusable_separator": (
                spec.game_over_count > 0
            ),
            "same_surface_retry_has_new_information": False,
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
            "next_work_block_id": spec.next_work_block_id,
            "reason_codes": [
                "frozen-source-sha-and-bytes-match",
                "zero-level-progress",
                "zero-progress-separators",
                "zero-reusable-hazard-separators",
                "zero-promotion-eligible-variables",
                "same-surface-retry-has-no-new-information",
            ],
        },
    }
    return {
        **body,
        "content_digest": _ADMISSION_DIGEST_PREFIX
        + digest_object(body),
    }


def build_remaining_frozen_negative_catalog(
    admissions: Sequence[Mapping[str, Any]],
) -> dict[str, object]:
    """Bind strict queue order and the next materially new work block."""

    by_capability = {
        str(admission.get("capability_id")): admission
        for admission in admissions
    }
    expected_ids = tuple(
        spec.capability_id for spec in FROZEN_NEGATIVE_SPECS
    )
    if (
        len(by_capability) != len(FROZEN_NEGATIVE_SPECS)
        or tuple(by_capability) != expected_ids
    ):
        raise ValueError(
            "P10_REMAINING_NEGATIVE_CATALOG_ORDER_INVALID"
    )
    for admission in admissions:
        admission_body = dict(admission)
        claimed = admission_body.pop("content_digest", None)
        if claimed != (
            _ADMISSION_DIGEST_PREFIX + digest_object(admission_body)
        ):
            raise ValueError(
                "P10_REMAINING_NEGATIVE_ADMISSION_DIGEST_INVALID"
            )
        judgment = _mapping(
            admission.get("hds_judgment"),
            "frozen admission judgment",
        )
        if (
            judgment.get("causal_result") != "CLOSED_NEGATIVE"
            or judgment.get("runtime_p_compile_authorized") is not False
        ):
            raise ValueError(
                "P10_REMAINING_NEGATIVE_ADMISSION_NOT_CLOSED"
            )

    ordered_steps: list[dict[str, object]] = []
    for spec in FROZEN_NEGATIVE_SPECS:
        if spec.rank == 11:
            ordered_steps.append(
                {
                    "rank": 10,
                    "work_block_id": (
                        "WB-C5_stale_settle_frame_controller"
                    ),
                    "resolution": "PREVIOUSLY_CLOSED_NEGATIVE_AXIS",
                    "evidence_ref": (
                        "evidence/p10/development/"
                        "directional_settle_composition_v1/"
                        "DIRECTIONAL_SETTLE_FAILURE_AUDIT.json"
                    ),
                    "same_axis_retry_authorized": False,
                    "required_new_information": (
                        "visible successor obligation state"
                    ),
                }
            )
        admission = by_capability[spec.capability_id]
        ordered_steps.append(
            {
                "rank": spec.rank,
                "work_block_id": f"WB-{spec.capability_id}",
                "resolution": "CLOSED_NEGATIVE",
                "admission_audit": spec.audit_filename,
                "content_digest": admission["content_digest"],
                "same_surface_retry_authorized": False,
            }
        )
    retained = [
        _mapping(
            admission.get("retained_measurements"),
            "retained measurements",
        )
        for admission in admissions
    ]
    source_evidence = [
        _mapping(admission.get("source_evidence"), "source evidence")
        for admission in admissions
    ]
    body: dict[str, object] = {
        "schema_version": (
            P10_REMAINING_NEGATIVE_CATALOG_SCHEMA_VERSION
        ),
        "artifact_type": (
            "arc3_p10_remaining_frozen_negative_catalog"
        ),
        "phase": "P10_COMPLETE_ARC3_SAMPLE_SOLVING",
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "strict_queue_resolution": ordered_steps,
        "summary": {
            "newly_closed_capability_count": len(admissions),
            "previously_closed_axis_count": 1,
            "frozen_source_count": len(source_evidence),
            "frozen_source_bytes": sum(
                int(source["bytes"]) for source in source_evidence
            ),
            "target_count": sum(
                int(item["target_count"]) for item in retained
            ),
            "probe_count": sum(
                int(item["total_probe_count"]) for item in retained
            ),
            "changed_probe_count": sum(
                int(item["changed_probe_count"]) for item in retained
            ),
            "progress_count": sum(
                int(item["total_progress_count"]) for item in retained
            ),
            "game_over_count": sum(
                int(item["total_game_over_count"]) for item in retained
            ),
            "runtime_p_compile_count": 0,
            "runtime_p_promotion_count": 0,
            "score_progress_claim_count": 0,
        },
        "hds_judgment": {
            "authority": "development-hds-only",
            "status": "PASS_NEGATIVE_ACCOUNTING_HOLD_RUNTIME",
            "all_frozen_surfaces_closed": True,
            "same_surface_retry_authorized": False,
            "runtime_p_compile_authorized": False,
            "runtime_p_promotion_authorized": False,
            "score_progress_claim_authorized": False,
            "active_p_changed": False,
            "next_work_block_id": _NEXT_GENERATIVE_WORK_BLOCK,
            "required_new_information": (
                "prospective identity-free rendered relation and "
                "successor-obligation state"
            ),
        },
    }
    return {
        **body,
        "content_digest": _CATALOG_DIGEST_PREFIX
        + digest_object(body),
    }


def build_all_remaining_frozen_negative_audits(
    *,
    provenance_manifest: Mapping[str, Any],
    retained_dir: Path,
) -> dict[str, dict[str, object]]:
    """Build every admission and the strict-order catalog."""

    outputs: dict[str, dict[str, object]] = {}
    admissions: list[dict[str, object]] = []
    for spec in FROZEN_NEGATIVE_SPECS:
        source_path = retained_dir / spec.retained_filename
        admission = build_frozen_negative_admission(
            spec=spec,
            provenance_manifest=provenance_manifest,
            legacy_artifact=_json_object(source_path),
            legacy_artifact_path=source_path,
        )
        outputs[spec.audit_filename] = admission
        admissions.append(admission)
    outputs["REMAINING_FROZEN_NEGATIVE_CATALOG.json"] = (
        build_remaining_frozen_negative_catalog(admissions)
    )
    return outputs


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Admit the remaining provenance-frozen P10 capability "
            "harnesses for negative-only accounting."
        )
    )
    parser.add_argument("--provenance-manifest", type=Path, required=True)
    parser.add_argument("--retained-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    outputs = build_all_remaining_frozen_negative_audits(
        provenance_manifest=_json_object(args.provenance_manifest),
        retained_dir=args.retained_dir,
    )
    for filename, value in outputs.items():
        _write_json(args.output_dir / filename, value)
    catalog = outputs["REMAINING_FROZEN_NEGATIVE_CATALOG.json"]
    print(catalog["content_digest"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "FROZEN_NEGATIVE_SPECS",
    "P10_FROZEN_NEGATIVE_ADMISSION_SCHEMA_VERSION",
    "P10_REMAINING_NEGATIVE_CATALOG_SCHEMA_VERSION",
    "FrozenNegativeSpec",
    "build_all_remaining_frozen_negative_audits",
    "build_frozen_negative_admission",
    "build_remaining_frozen_negative_catalog",
    "main",
]
