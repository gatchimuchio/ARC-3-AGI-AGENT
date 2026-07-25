"""Admit the frozen C7 harness as negative-only development evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .schema import digest_object

P10_C7_CLOSED_NEGATIVE_AUDIT_SCHEMA_VERSION = (
    "arc3-p10-c7-closed-negative-admission-v1"
)
_CONTENT_DIGEST_PREFIX = (
    "arc3_p10_c7_closed_negative_admission:"
)
_LEGACY_SOURCE_PATH = (
    "analysis/c7_target_contact_boundary_capability_latest.json"
)
_CAPABILITY_ID = "C7_target_contact_boundary_verifier"


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
) -> Mapping[str, Any]:
    sources = _sequence(provenance.get("sources"), "provenance sources")
    matches = tuple(
        item
        for item in sources
        if isinstance(item, Mapping)
        and item.get("path") == _LEGACY_SOURCE_PATH
    )
    if len(matches) != 1:
        raise ValueError(
            "P10_C7_FROZEN_SOURCE_DESCRIPTOR_CARDINALITY_INVALID"
        )
    return matches[0]


def build_p10_c7_closed_negative_audit(
    *,
    provenance_manifest: Mapping[str, Any],
    legacy_artifact: Mapping[str, Any],
    legacy_artifact_path: Path,
) -> dict[str, object]:
    """Bind one exact frozen source to a conservative negative judgment."""

    descriptor = _source_descriptor(provenance_manifest)
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
            "P10_C7_FROZEN_SOURCE_INVALID:" + ",".join(failures)
        )

    summary = _mapping(legacy_artifact.get("summary"), "C7 summary")
    checks = _mapping(legacy_artifact.get("checks"), "C7 checks")
    decision = _mapping(legacy_artifact.get("decision"), "C7 decision")
    forbidden_inputs = _mapping(
        legacy_artifact.get("forbidden_inputs"),
        "C7 forbidden inputs",
    )
    scope = _mapping(legacy_artifact.get("scope"), "C7 scope")
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
            legacy_artifact.get("capability_id") == _CAPABILITY_ID
            and summary.get("capability_id") == _CAPABILITY_ID
        ),
        "analysis_only_public_scope": (
            scope.get("analysis_only") is True
            and scope.get("public_only_artifact") is True
            and scope.get("agent_core_changed") is False
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
        "seven_target_contracts_complete": (
            summary.get("target_count") == 7
            and summary.get("target_contract_count") == 7
            and summary.get("target_contract_complete_count") == 7
        ),
        "all_288_probes_target_contact_only": (
            summary.get("total_probe_count") == 288
            and summary.get("target_contact_boundary_effect_probe_count")
            == 288
            and summary.get("actual_outcome_counts")
            == {"target_contact_effect_only": 288}
        ),
        "changed_and_contact_gain_counts_retained": (
            summary.get("changed_probe_count") == 228
            and summary.get("contact_gain_probe_count") == 63
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
                "c7_target_contact_boundary_harness_closed_negative"
            )
            is True
            and decision.get("promotion_decision")
            == "REJECTED_NO_PROMOTION"
            and decision.get("promote_to_agent") is False
            and decision.get("agent_edit_required") is False
        ),
    }
    if not all(negative_checks.values()):
        failures = sorted(
            key for key, passed in negative_checks.items() if not passed
        )
        raise ValueError(
            "P10_C7_NEGATIVE_EVIDENCE_INVALID:" + ",".join(failures)
        )

    body: dict[str, object] = {
        "schema_version": (
            P10_C7_CLOSED_NEGATIVE_AUDIT_SCHEMA_VERSION
        ),
        "artifact_type": (
            "arc3_p10_c7_closed_negative_admission"
        ),
        "phase": "P10_COMPLETE_ARC3_SAMPLE_SOLVING",
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "capability_id": _CAPABILITY_ID,
        "source_evidence": {
            "frozen_source_path": _LEGACY_SOURCE_PATH,
            "retained_copy_filename": legacy_artifact_path.name,
            "sha256": actual_sha256,
            "bytes": actual_bytes,
            "record_id_count": len(
                _sequence(
                    descriptor.get("record_ids"),
                    "C7 descriptor record ids",
                )
            ),
            "sensitive_path_count": descriptor.get(
                "sensitive_path_count"
            ),
        },
        "source_checks": source_checks,
        "negative_checks": negative_checks,
        "retained_measurements": {
            "target_count": 7,
            "total_probe_count": 288,
            "changed_probe_count": 228,
            "contact_gain_probe_count": 63,
            "total_progress_count": 0,
            "total_game_over_count": 0,
            "progress_separator_variable_count": 0,
            "hazard_separator_variable_count": 0,
            "reusable_hazard_separator_variable_count": 0,
            "promotion_eligible_variable_count": 0,
            "error_count": 0,
        },
        "admission_scope": {
            "admitted_for_negative_surface_closure": True,
            "admitted_for_runtime_compile": False,
            "admitted_for_runtime_promotion": False,
            "admitted_for_positive_generalization_claim": False,
            "legacy_contract_spec_mismatch_quarantined": True,
            "same_target_contact_surface_retry_has_new_information": False,
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
                "WB-C12_layout_mode_commit_discriminator"
            ),
            "reason_codes": [
                "frozen-source-sha-and-bytes-match",
                "legacy-contract-spec-mismatch-negative-only",
                "288-target-contact-probes-zero-progress",
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
            "Admit the exact frozen C7 harness for negative-only P10 "
            "development accounting."
        )
    )
    parser.add_argument("--provenance-manifest", type=Path, required=True)
    parser.add_argument("--legacy-artifact", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    audit = build_p10_c7_closed_negative_audit(
        provenance_manifest=_json_object(args.provenance_manifest),
        legacy_artifact=_json_object(args.legacy_artifact),
        legacy_artifact_path=args.legacy_artifact,
    )
    _write_json(args.output, audit)
    print(audit["content_digest"])
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "P10_C7_CLOSED_NEGATIVE_AUDIT_SCHEMA_VERSION",
    "build_p10_c7_closed_negative_audit",
    "main",
]
