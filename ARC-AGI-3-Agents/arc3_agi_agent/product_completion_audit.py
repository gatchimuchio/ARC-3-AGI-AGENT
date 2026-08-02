"""Fail-closed completion audit for the ARC3CompletionAgent product."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Final

from .schema import digest_object

PRODUCT_COMPLETION_AUDIT_SCHEMA_VERSION: Final = (
    "arc3-product-completion-audit-v1"
)
PRODUCT_COMPLETION_AUDIT_DIGEST_PREFIX: Final = (
    "arc3-product-completion-audit:"
)


def _integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return value


def _folds(value: Mapping[str, object]) -> tuple[Mapping[str, object], ...]:
    raw = value.get("folds")
    if not isinstance(raw, list):
        return ()
    return tuple(item for item in raw if isinstance(item, Mapping))


def evaluate_product_completion_evidence(
    *,
    known_sample_report: Mapping[str, object],
    clean_install_report: Mapping[str, object],
    release_report: Mapping[str, object],
    product_descriptor: Mapping[str, object],
    active_policy_manifest: Mapping[str, object],
    teacher_policy_manifest: Mapping[str, object],
    cv_manifest: Mapping[str, object],
    perturbation_report: Mapping[str, object],
    active_transformation_report: Mapping[str, object],
    sealed_report: Mapping[str, object],
    evidence_bindings: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Classify evidence without promoting known-sample success to AGI completion."""

    known_sample_complete = (
        _integer(known_sample_report.get("product_game_win_count")) == 25
        and _integer(
            known_sample_report.get("product_level_completion_count")
        )
        == 183
        and _integer(
            known_sample_report.get(
                "product_runtime_failure_signature_row_count"
            )
        )
        == 0
        and known_sample_report.get("product_endpoint_failures") == []
    )
    clean_install_complete = (
        _integer(clean_install_report.get("product_game_win_count")) == 25
        and _integer(
            clean_install_report.get("product_level_completion_count")
        )
        == 183
        and clean_install_report.get("product_endpoint_failures") == []
    )

    folds = _folds(cv_manifest)
    cv_execution_count = sum(
        _integer(item.get("execution_count")) for item in folds
    )
    cv_completed_environment_count = sum(
        _integer(item.get("completed_environment_count")) for item in folds
    )
    cv_completed_level_count = sum(
        _integer(item.get("completed_level_count")) for item in folds
    )
    cv_completion_established = (
        len(folds) == 5
        and cv_execution_count == 25
        and cv_completed_environment_count == 25
        and cv_completed_level_count > 0
    )

    active_p_body_digest = str(product_descriptor.get("p_body_digest", ""))
    active_weights_sha256 = str(
        active_policy_manifest.get("weights_sha256", "")
    )
    teacher_weights_sha256 = str(
        teacher_policy_manifest.get("weights_sha256", "")
    )
    active_policy_is_full_teacher_parameter_copy = (
        bool(active_weights_sha256)
        and active_weights_sha256 == teacher_weights_sha256
    )

    raw_transformation_completion = active_transformation_report.get(
        "transformation_completion"
    )
    transformation_completion = (
        raw_transformation_completion
        if isinstance(raw_transformation_completion, Mapping)
        else {}
    )
    perturbation_environment_complete = (
        active_transformation_report.get("status") == "PASS"
        and active_transformation_report.get(
            "semantic_environment_completion_executed"
        )
        is True
        and active_transformation_report.get("active_p_body_digest")
        == active_p_body_digest
        and active_transformation_report.get("product_p_j0_m0_identity_bound")
        is True
        and active_transformation_report.get(
            "same_runtime_identity_for_all_environments"
        )
        is True
        and _integer(transformation_completion.get("completed")) == 7
        and _integer(transformation_completion.get("required")) == 7
    )
    sealed_p_digest = str(sealed_report.get("frozen_p_digest", ""))
    sealed_same_active_artifact = (
        bool(active_p_body_digest)
        and sealed_p_digest == active_p_body_digest
    )
    sealed_active_artifact_complete = (
        sealed_same_active_artifact
        and sealed_report.get("status") == "PASS"
        and _integer(sealed_report.get("game_count")) > 0
        and _integer(sealed_report.get("win_count"))
        == _integer(sealed_report.get("game_count"))
        and sealed_report.get("code_frozen_before_generation") is True
        and sealed_report.get("p_frozen_before_generation") is True
    )

    external_status = str(
        release_report.get("external_kaggle_normal_run_status", "")
    )
    output_bytes = _integer(release_report.get("official_output_bytes"))
    official_score = release_report.get("official_score")
    official_output_present = output_bytes > 0
    official_score_returned = isinstance(official_score, (int, float)) and not isinstance(
        official_score, bool
    )
    official_same_runtime_identity = (
        release_report.get("official_same_runtime_identity") is True
    )
    official_full_complete = (
        release_report.get("official_full_complete") is True
        and official_output_present
        and official_score_returned
        and official_same_runtime_identity
    )

    gates = {
        "KNOWN_SAMPLE_REGRESSION": known_sample_complete,
        "LOCAL_PACKAGE_REGRESSION": clean_install_complete,
        "GEN_CV_HOLDOUT_COMPLETION": cv_completion_established,
        "GEN_SEMANTIC_TRANSFORMATION_COMPLETION": (
            perturbation_environment_complete
        ),
        "AUT_006_ACTIVE_ARTIFACT_LOCKED_EVALUATOR": (
            sealed_active_artifact_complete
        ),
        "OFF_004_OUTPUT_BYTES": official_output_present,
        "OFF_005_SCORE_RETURNED": official_score_returned,
        "OFF_007_SAME_RUNTIME_IDENTITY": official_same_runtime_identity,
        "OFFICIAL_FULL_COMPLETE": official_full_complete,
    }
    blocking_requirement_ids = tuple(
        key for key, passed in gates.items() if not passed
    )
    product_completion_allowed = not blocking_requirement_ids

    body: dict[str, object] = {
        "schema_version": PRODUCT_COMPLETION_AUDIT_SCHEMA_VERSION,
        "evaluation_role": "PRODUCT_COMPLETION_AUTHORITY_GATE",
        "claim_hierarchy": {
            "known_sample_regression_is_agi_completion": False,
            "cv_is_single_artifact_completion": False,
            "cross_artifact_evidence_aggregation_allowed": False,
        },
        "known_sample": {
            "game_win_count": _integer(
                known_sample_report.get("product_game_win_count")
            ),
            "level_completion_count": _integer(
                known_sample_report.get("product_level_completion_count")
            ),
            "action_count": _integer(
                known_sample_report.get("product_total_action_count")
            ),
            "regression_complete": known_sample_complete,
            "clean_install_regression_complete": clean_install_complete,
        },
        "active_policy": {
            "p_body_digest": active_p_body_digest,
            "manifest_content_digest": active_policy_manifest.get(
                "content_digest"
            ),
            "weights_sha256": active_weights_sha256,
            "teacher_weights_sha256": teacher_weights_sha256,
            "full_teacher_parameter_copy": (
                active_policy_is_full_teacher_parameter_copy
            ),
            "teacher_action_record_count": _integer(
                (
                    teacher_policy_manifest.get("teacher_compile", {})
                    if isinstance(
                        teacher_policy_manifest.get("teacher_compile"),
                        Mapping,
                    )
                    else {}
                ).get("action_record_count")
            ),
        },
        "cv": {
            "fold_count": len(folds),
            "execution_count": cv_execution_count,
            "completed_environment_count": cv_completed_environment_count,
            "completed_level_count": cv_completed_level_count,
            "same_single_artifact_claim_allowed": cv_manifest.get(
                "same_single_artifact_claim_allowed"
            ),
            "final_generic_claim": cv_manifest.get("final_generic_claim"),
            "completion_established": cv_completion_established,
        },
        "perturbation": {
            "active_product_report_status": active_transformation_report.get(
                "status"
            ),
            "active_product_p_digest": active_transformation_report.get(
                "active_p_body_digest"
            ),
            "active_product_completion": dict(transformation_completion),
            "active_product_same_runtime_identity": (
                active_transformation_report.get(
                    "same_runtime_identity_for_all_environments"
                )
            ),
            "measured_family_count": _integer(
                perturbation_report.get("measured_family_count")
            ),
            "full_environment_completion_executed": perturbation_report.get(
                "full_environment_completion_executed"
            ),
            "generalization_claim": perturbation_report.get(
                "generalization_claim"
            ),
            "semantic_completion_established": (
                perturbation_environment_complete
            ),
        },
        "sealed": {
            "evaluated_p_digest": sealed_p_digest,
            "active_p_digest": active_p_body_digest,
            "same_active_artifact": sealed_same_active_artifact,
            "active_artifact_completion_established": (
                sealed_active_artifact_complete
            ),
        },
        "official": {
            "external_run_status": external_status,
            "output_bytes": output_bytes,
            "score": official_score,
            "same_runtime_identity": official_same_runtime_identity,
            "official_full_complete": official_full_complete,
        },
        "gates": gates,
        "blocking_requirement_ids": blocking_requirement_ids,
        "product_completion_allowed": product_completion_allowed,
        "status": (
            "ARC3_AGI_PRODUCT_COMPLETE"
            if product_completion_allowed
            else "M3_GENERICITY_REOPENED"
        ),
        "evidence_bindings": dict(evidence_bindings or {}),
    }
    return {
        **body,
        "content_digest": (
            PRODUCT_COMPLETION_AUDIT_DIGEST_PREFIX + digest_object(body)
        ),
    }


__all__ = [
    "PRODUCT_COMPLETION_AUDIT_DIGEST_PREFIX",
    "PRODUCT_COMPLETION_AUDIT_SCHEMA_VERSION",
    "evaluate_product_completion_evidence",
]
