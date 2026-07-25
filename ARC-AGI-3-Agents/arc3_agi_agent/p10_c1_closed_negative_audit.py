"""Admit the frozen C1 objectizer as negative-only development evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from .schema import digest_object

P10_C1_CLOSED_NEGATIVE_AUDIT_SCHEMA_VERSION = (
    "arc3-p10-c1-closed-negative-admission-v1"
)
_CONTENT_DIGEST_PREFIX = "arc3_p10_c1_closed_negative_admission:"
_LEGACY_SOURCE_PATH = (
    "analysis/c1_rendered_affordance_objectizer_capability_latest.json"
)
_CAPABILITY_ID = "C1_rendered_affordance_objectizer"
_BP35_GAME_ID = "bp35-0a0ad940"
_LF52_GAME_ID = "lf52-271a04aa"


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
            "P10_C1_FROZEN_SOURCE_DESCRIPTOR_CARDINALITY_INVALID"
        )
    return matches[0]


def _game_by_id(
    artifact: Mapping[str, Any],
) -> dict[str, Mapping[str, Any]]:
    games = _sequence(artifact.get("games"), "C1 games")
    by_id: dict[str, Mapping[str, Any]] = {}
    for raw_game in games:
        game = _mapping(raw_game, "C1 game")
        game_id = game.get("game_id")
        if not isinstance(game_id, str) or game_id in by_id:
            raise ValueError("P10_C1_GAME_ID_INVALID")
        by_id[game_id] = game
    return by_id


def _support_rows_are_negative(rows: object, field_name: str) -> bool:
    support_rows = _sequence(rows, field_name)
    return all(
        isinstance(raw, Mapping)
        and isinstance(raw.get("variable"), str)
        and raw.get("level_progress_separator") is False
        and raw.get("hazard_separator") is False
        and raw.get("reusable_hazard_separator") is False
        and raw.get("promotion_eligible") is False
        for raw in support_rows
    )


def build_p10_c1_closed_negative_audit(
    *,
    provenance_manifest: Mapping[str, Any],
    legacy_artifact: Mapping[str, Any],
    legacy_artifact_path: Path,
) -> dict[str, object]:
    """Bind the exact frozen C1 source to a conservative negative judgment."""

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
            "P10_C1_FROZEN_SOURCE_INVALID:" + ",".join(failures)
        )

    summary = _mapping(legacy_artifact.get("summary"), "C1 summary")
    decision = _mapping(legacy_artifact.get("decision"), "C1 decision")
    scope = _mapping(legacy_artifact.get("scope"), "C1 scope")
    forbidden_inputs = _mapping(
        legacy_artifact.get("forbidden_inputs"),
        "C1 forbidden inputs",
    )
    games = _game_by_id(legacy_artifact)
    bp35 = games.get(_BP35_GAME_ID)
    lf52 = games.get(_LF52_GAME_ID)
    if bp35 is None or lf52 is None or len(games) != 2:
        raise ValueError("P10_C1_TARGET_GAME_SET_INVALID")
    bp35_summary = _mapping(bp35.get("summary"), "BP35 C1 summary")
    lf52_summary = _mapping(lf52.get("summary"), "LF52 C1 summary")
    support_variables = _sequence(
        legacy_artifact.get("support_variables"),
        "C1 support variables",
    )

    negative_checks = {
        "capability_id_matches": (
            legacy_artifact.get("capability_id") == _CAPABILITY_ID
            and summary.get("capability_id") == _CAPABILITY_ID
        ),
        "analysis_only_public_scope": (
            scope.get("analysis_only") is True
            and scope.get("public_only_artifact") is True
            and scope.get("agent_core_changed") is False
            and scope.get("evaluator_path_changed") is False
            and scope.get("external_api_used") is False
            and scope.get("hidden_generalization_claim") is False
            and scope.get("exact_public_replay_added") is False
        ),
        "forbidden_inputs_all_absent": all(
            value is False for value in forbidden_inputs.values()
        ),
        "two_target_contracts_complete": (
            summary.get("target_count") == 2
            and summary.get("target_contract_count") == 2
            and summary.get("target_contract_complete_count") == 2
            and set(summary.get("target_game_ids", ()))
            == {_BP35_GAME_ID, _LF52_GAME_ID}
        ),
        "all_1768_probes_accounted": (
            summary.get("total_probe_count") == 1768
            and bp35.get("probe_count") == 140
            and lf52.get("probe_count") == 1628
            and bp35.get("mechanism_probe_count") == 140
            and lf52.get("mechanism_probe_count") == 1628
        ),
        "visible_change_counts_retained": (
            summary.get("changed_probe_count") == 1720
            and bp35.get("changed_probe_count") == 100
            and lf52.get("changed_probe_count") == 1620
        ),
        "prefix_only_progress_is_explicit": (
            summary.get("total_progress_count") == 2
            and bp35.get("progress_count") == 1
            and lf52.get("progress_count") == 1
            and bp35_summary.get("replay_action_count") == 40
            and bp35_summary.get("replay_progress_action_count") == 1
            and bp35_summary.get("replay_progress_steps") == [40]
            and lf52_summary.get("policy_action_count") == 8
            and lf52_summary.get("policy_progress_action_count") == 1
            and lf52_summary.get("policy_progress_steps") == [8]
        ),
        "non_prefix_candidates_have_zero_progress": (
            bp35_summary.get("post_level1_candidate_count") == 100
            and bp35_summary.get("post_level1_progress_count") == 0
            and lf52_summary.get("post_level1_offset_candidate_count")
            == 1620
            and lf52_summary.get("post_level1_progress_count") == 0
            and lf52_summary.get("post_level1_game_over_count") == 0
        ),
        "no_game_over_or_hazard_signature": (
            summary.get("total_game_over_count") == 0
            and bp35.get("game_over_count") == 0
            and lf52.get("game_over_count") == 0
            and bp35.get("hazard_signatures") == []
            and lf52.get("hazard_signatures") == []
        ),
        "global_support_variables_all_negative": (
            len(support_variables) == 27
            and _support_rows_are_negative(
                support_variables,
                "C1 support variables",
            )
        ),
        "per_game_support_variables_all_negative": (
            len(
                _sequence(
                    bp35.get("support_variable_rows"),
                    "BP35 support variables",
                )
            )
            == 14
            and len(
                _sequence(
                    lf52.get("support_variable_rows"),
                    "LF52 support variables",
                )
            )
            == 13
            and _support_rows_are_negative(
                bp35.get("support_variable_rows"),
                "BP35 support variables",
            )
            and _support_rows_are_negative(
                lf52.get("support_variable_rows"),
                "LF52 support variables",
            )
        ),
        "no_promotion_variable_observed": (
            summary.get("promotion_eligible_variable_count") == 0
            and bp35.get("promotion_eligible_variable_count") == 0
            and lf52.get("promotion_eligible_variable_count") == 0
            and bp35_summary.get("promotion_eligible_separator_count") == 0
            and lf52_summary.get("promotion_eligible_separator_count") == 0
        ),
        "stale_public_score_fields_explicit": (
            summary.get("public_total_levels") == 76
            and summary.get("public_total_win_levels") == 183
        ),
        "error_free_harness": (
            summary.get("errors") == 0
            and summary.get("maxed_out_count") == 0
        ),
        "legacy_decision_closed_negative": (
            decision.get(
                "c1_rendered_affordance_objectizer_harness_closed_negative"
            )
            is True
            and decision.get(
                "c1_rendered_affordance_objectizer_harness_ready"
            )
            is True
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
            "P10_C1_NEGATIVE_EVIDENCE_INVALID:" + ",".join(failures)
        )

    body: dict[str, object] = {
        "schema_version": P10_C1_CLOSED_NEGATIVE_AUDIT_SCHEMA_VERSION,
        "artifact_type": "arc3_p10_c1_closed_negative_admission",
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
                    "C1 descriptor record ids",
                )
            ),
            "sensitive_path_count": descriptor.get(
                "sensitive_path_count"
            ),
        },
        "source_checks": source_checks,
        "negative_checks": negative_checks,
        "retained_measurements": {
            "target_count": 2,
            "total_probe_count": 1768,
            "changed_probe_count": 1720,
            "prefix_probe_count": 48,
            "prefix_progress_count": 2,
            "non_prefix_candidate_count": 1720,
            "non_prefix_changed_count": 1720,
            "non_prefix_progress_count": 0,
            "total_game_over_count": 0,
            "support_variable_count": 27,
            "progress_separator_variable_count": 0,
            "hazard_separator_variable_count": 0,
            "reusable_hazard_separator_variable_count": 0,
            "promotion_eligible_variable_count": 0,
            "error_count": 0,
            "quarantined_stale_score_fields": {
                "public_total_levels": summary.get(
                    "public_total_levels"
                ),
                "public_total_win_levels": summary.get(
                    "public_total_win_levels"
                ),
            },
        },
        "admission_scope": {
            "admitted_for_negative_surface_closure": True,
            "admitted_for_runtime_compile": False,
            "admitted_for_runtime_promotion": False,
            "admitted_for_positive_generalization_claim": False,
            "task_aware_prefix_progress_quarantined": True,
            "task_game_level_identity_quarantined": True,
            "literal_coordinates_quarantined": True,
            "stale_public_score_fields_quarantined": True,
            "same_rendered_affordance_surface_retry_has_new_information": (
                False
            ),
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
                "WB-C14_symbolic_relation_commit_model"
            ),
            "reason_codes": [
                "frozen-source-sha-and-bytes-match",
                "two-task-aware-prefix-progress-records-quarantined",
                "1720-non-prefix-candidates-zero-progress",
                "zero-hazard-separators",
                "zero-promotion-eligible-variables",
                "stale-score-fields-quarantined",
                "select-next-unembedded-high-support-capability",
            ],
        },
    }
    return {
        **body,
        "content_digest": _CONTENT_DIGEST_PREFIX + digest_object(body),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Admit the exact frozen C1 rendered-affordance harness for "
            "negative-only P10 development accounting."
        )
    )
    parser.add_argument("--provenance-manifest", type=Path, required=True)
    parser.add_argument("--legacy-artifact", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    audit = build_p10_c1_closed_negative_audit(
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
    "P10_C1_CLOSED_NEGATIVE_AUDIT_SCHEMA_VERSION",
    "build_p10_c1_closed_negative_audit",
    "main",
]
