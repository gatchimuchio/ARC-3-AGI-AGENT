"""Product-equivalent train/holdout evaluation for ARC3 Runtime P.

This module is development-only.  It recompiles the same dense Runtime P
family on twenty games, keeps five games physically excluded, and then runs
the candidate with the product P-IR/J0/M0 stack.  The resulting evidence may
measure cross-game transfer, but it is neither a locked evaluation nor a
same-single-artifact final claim.
"""

from __future__ import annotations

import hashlib
import json
import tempfile
import time
import zipfile
from collections.abc import Mapping
from dataclasses import replace
from pathlib import Path
from typing import Final

from arc_agi import Arcade, OperationMode  # type: ignore[import-untyped]

from .compiled_policy import (
    CompiledAutonomousInstructionBody,
    load_compiled_autonomous_instruction_body,
)
from .generic_env import OfflineGenericEnvironment
from .generic_runtime import GenericAGIRuntime
from .generic_session import (
    CognitiveSession,
    ResourceContract,
    create_cognitive_session,
)
from .p22_evaluator import ContentBoundTraceSink
from .p_bundle import PBundle, p_bundle_from_package
from .p_compiler_v2 import PCompilerV2
from .product_capability import load_product_initial_state
from .product_governance import (
    ARC3_DEVELOPMENT_ACTION_BUDGET,
    ARC3_PRODUCT_NO_PROGRESS_LIMIT,
)
from .runtime_identity import build_runtime_identity
from .schema import digest_object
from .teacher.generic_policy_migration import migrate_identity_free_policy
from .teacher.p22_cross_validation import deterministic_cv_folds
from .teacher.s5_policy_compiler import compile_s5_rendered_policy

PRODUCT_CV_SCHEMA_VERSION: Final = "arc3-product-cross-validation-v1"
PRODUCT_CV_COMPILE_DIGEST_PREFIX: Final = "arc3-product-cv-compile:"
PRODUCT_CV_FOLD_DIGEST_PREFIX: Final = "arc3-product-cv-fold:"
PRODUCT_CV_MANIFEST_DIGEST_PREFIX: Final = "arc3-product-cv-manifest:"
PRODUCT_CV_FOLD_COUNT: Final = 5
PRODUCT_CV_GAME_COUNT: Final = 25
PRODUCT_CV_ACTION_BUDGET: Final = ARC3_DEVELOPMENT_ACTION_BUDGET
PRODUCT_CV_NO_PROGRESS_LIMIT: Final = ARC3_PRODUCT_NO_PROGRESS_LIMIT


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_content_bound(
    path: Path,
    value: Mapping[str, object],
    *,
    prefix: str,
) -> dict[str, object]:
    body = dict(value)
    if "content_digest" in body:
        raise ValueError("PRODUCT_CV_CONTENT_DIGEST_PREEXISTS")
    report = {**body, "content_digest": prefix + digest_object(body)}
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return report


def _load_content_bound(path: Path, *, prefix: str) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("PRODUCT_CV_REPORT_INVALID")
    body = dict(value)
    expected = body.pop("content_digest", None)
    if expected != prefix + digest_object(body):
        raise ValueError("PRODUCT_CV_CONTENT_DIGEST_MISMATCH")
    body["content_digest"] = expected
    return body


def product_cv_partition(fold_index: int) -> tuple[tuple[int, ...], tuple[int, ...]]:
    """Return deterministic train/holdout ordinals for one five-fold split."""

    if isinstance(fold_index, bool) or not 0 <= fold_index < PRODUCT_CV_FOLD_COUNT:
        raise ValueError("PRODUCT_CV_FOLD_INDEX_INVALID")
    holdout = deterministic_cv_folds()[fold_index]
    training = tuple(sorted(set(range(PRODUCT_CV_GAME_COUNT)).difference(holdout)))
    if (
        len(training) != 20
        or len(holdout) != 5
        or set(training).intersection(holdout)
        or set(training).union(holdout) != set(range(PRODUCT_CV_GAME_COUNT))
    ):
        raise RuntimeError("PRODUCT_CV_PARTITION_INVALID")
    return training, holdout


def _candidate_product_bundle(
    body: CompiledAutonomousInstructionBody,
    *,
    fold_index: int,
) -> PBundle:
    initial = load_product_initial_state()
    return PCompilerV2().compile_product(
        body=body,
        program=initial.p_bundle.program,
        evidence_digest=initial.p_bundle.compiler_report.evidence_selection_digest,
        selected_evidence_count=(
            initial.p_bundle.compiler_report.selected_evidence_count
        ),
        target_version=f"arc3-product-cv-fold-{fold_index:02d}-v1",
    )


def create_product_cv_session(
    bundle: PBundle,
    *,
    action_budget: int = PRODUCT_CV_ACTION_BUDGET,
    no_progress_limit: int = PRODUCT_CV_NO_PROGRESS_LIMIT,
) -> CognitiveSession:
    """Bind candidate P to the unchanged product P-IR/J0/M0 subjects."""

    initial = load_product_initial_state()
    if bundle.program.program_id != initial.p_bundle.program.program_id:
        raise ValueError("PRODUCT_CV_P_IR_PROGRAM_MISMATCH")
    selected_j0 = replace(
        initial.j0,
        resource_budget=action_budget,
        stop_after_no_progress=min(action_budget, no_progress_limit),
    )
    return create_cognitive_session(
        p_bundle=bundle.body,
        p_ir_program=bundle.program,
        mode="VALIDATION",
        hds_configuration=selected_j0,
        initial_memory_records=initial.m0,
        resource_contract=ResourceContract(
            action_budget_per_episode=action_budget,
        ),
        enable_cross_game_promotion=True,
    )


def _cached_compile_report(
    *,
    report_path: Path,
    package_path: Path,
    corpus_sha256: str,
    fold_index: int,
) -> dict[str, object] | None:
    if not report_path.is_file() or not package_path.is_file():
        return None
    try:
        report = _load_content_bound(
            report_path,
            prefix=PRODUCT_CV_COMPILE_DIGEST_PREFIX,
        )
    except (OSError, TypeError, ValueError, json.JSONDecodeError):
        return None
    if (
        report.get("schema_version") != PRODUCT_CV_SCHEMA_VERSION
        or report.get("fold_index") != fold_index
        or report.get("source_corpus_sha256") != corpus_sha256
        or report.get("p_package_sha256") != _sha256(package_path)
    ):
        return None
    try:
        bundle = p_bundle_from_package(package_path.read_bytes())
    except (TypeError, ValueError, zipfile.BadZipFile):
        return None
    if bundle.logical_digest() != report.get("p_logical_digest"):
        return None
    return report


def compile_product_cv_fold(
    *,
    repository_root: Path,
    corpus_path: Path,
    corpus_manifest_path: Path,
    output_dir: Path,
    fold_index: int,
    use_cache: bool = True,
) -> dict[str, object]:
    """Compile one train-only dense P and freeze it as a product P package."""

    started = time.monotonic()
    training, holdout = product_cv_partition(fold_index)
    manifest_value = json.loads(corpus_manifest_path.read_text(encoding="utf-8"))
    if not isinstance(manifest_value, dict):
        raise TypeError("PRODUCT_CV_CORPUS_MANIFEST_INVALID")
    corpus_sha256 = _sha256(corpus_path)
    if (
        manifest_value.get("development_only") is not True
        or manifest_value.get("runtime_use") != "FORBIDDEN"
        or manifest_value.get("environment_count") != PRODUCT_CV_GAME_COUNT
        or manifest_value.get("corpus_sha256") != corpus_sha256
    ):
        raise ValueError("PRODUCT_CV_CORPUS_BOUNDARY_INVALID")
    fold_id = f"fold-{fold_index:02d}"
    artifact_dir = output_dir / "artifacts"
    package_path = artifact_dir / f"{fold_id}.product-p.zip"
    report_path = output_dir / "compile" / f"{fold_id}.json"
    if use_cache:
        cached = _cached_compile_report(
            report_path=report_path,
            package_path=package_path,
            corpus_sha256=corpus_sha256,
            fold_index=fold_index,
        )
        if cached is not None:
            return cached
    artifact_dir.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=f"arc3-product-cv-{fold_id}-") as raw:
        temporary = Path(raw)
        source_manifest = temporary / "source-s5.json"
        source_weights = temporary / "source-s5.npz"
        generic_manifest = temporary / "generic.json"
        generic_weights = temporary / "generic.npz"
        training_report = compile_s5_rendered_policy(
            corpus_path=corpus_path,
            corpus_manifest_path=corpus_manifest_path,
            output_manifest_path=source_manifest,
            output_weights_path=source_weights,
            training_game_ordinals=training,
        )
        migration_report = migrate_identity_free_policy(
            source_manifest_path=source_manifest,
            source_weights_path=source_weights,
            output_manifest_path=generic_manifest,
            output_weights_path=generic_weights,
        )
        body = load_compiled_autonomous_instruction_body(
            manifest_path=generic_manifest,
            weights_path=generic_weights,
        )
        bundle = _candidate_product_bundle(body, fold_index=fold_index)
        package_payload = bundle.package_bytes()
    package_path.write_bytes(package_payload)
    session = create_product_cv_session(bundle)
    initial = load_product_initial_state()
    expected_identity = build_runtime_identity(
        p_bundle=bundle.body,
        p_ir_program=bundle.program,
        hds_configuration=session.hds_config,
        initial_memory_records=initial.m0,
    )
    if session.runtime_identity != expected_identity:
        raise RuntimeError("PRODUCT_CV_RUNTIME_IDENTITY_MISMATCH")
    relative_package = package_path.resolve().relative_to(repository_root.resolve())
    report_body: dict[str, object] = {
        "schema_version": PRODUCT_CV_SCHEMA_VERSION,
        "evaluation_role": "DEVELOPMENT_CROSS_GAME_CV_COMPILE",
        "allowed_claim": "PRODUCT_EQUIVALENT_CV_PROCEDURE_EVIDENCE",
        "final_generic_claim": "NOT_AUTHORIZED",
        "same_single_artifact_claim_allowed": False,
        "fold_id": fold_id,
        "fold_index": fold_index,
        "training_game_ordinals": training,
        "holdout_game_ordinals": holdout,
        "training_data_completely_separated": True,
        "source_corpus_sha256": corpus_sha256,
        "source_corpus_content_digest": manifest_value.get("content_digest"),
        "compiler_family": "s5-feed-forward-relu-mlp",
        "training_record_count": training_report["training_record_count"],
        "training_game_count": training_report["training_game_count"],
        "teacher_forced_error_count": training_report["teacher_forced_error_count"],
        "quantized_teacher_forced_error_count": training_report[
            "quantized_teacher_forced_error_count"
        ],
        "parameter_count": training_report["parameter_count"],
        "runtime_artifact_contains_training_examples": False,
        "runtime_identity_free": migration_report["runtime_identity_free"],
        "candidate_p_body_digest": bundle.body.digest(),
        "active_product_p_body_digest": initial.p_bundle.body.digest(),
        "p_program_id": bundle.program.program_id,
        "p_program_logical_digest": bundle.manifest.program_logical_digest,
        "j0_digest": "j0:" + digest_object(session.hds_config),
        "m0_digest": "m0:" + digest_object(initial.m0),
        "m0_record_count": len(initial.m0),
        "action_budget_per_environment": PRODUCT_CV_ACTION_BUDGET,
        "no_progress_limit": PRODUCT_CV_NO_PROGRESS_LIMIT,
        "p_logical_digest": bundle.logical_digest(),
        "p_package_digest": bundle.physical_digest(),
        "p_package_path": relative_package.as_posix(),
        "p_package_sha256": hashlib.sha256(package_payload).hexdigest(),
        "p_package_size_bytes": len(package_payload),
        "runtime_identity_digest": session.runtime_identity.digest(),
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "status": "PASS",
        "failed_requirement_ids": [],
    }
    return _write_content_bound(
        report_path,
        report_body,
        prefix=PRODUCT_CV_COMPILE_DIGEST_PREFIX,
    )


def _integer(mapping: Mapping[str, object], key: str) -> int:
    value = mapping.get(key)
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("PRODUCT_CV_INTEGER_INVALID:" + key)
    return value


def _integer_sequence(mapping: Mapping[str, object], key: str) -> tuple[int, ...]:
    value = mapping.get(key)
    if not isinstance(value, (list, tuple)) or any(
        isinstance(item, bool) or not isinstance(item, int) for item in value
    ):
        raise TypeError("PRODUCT_CV_INTEGER_SEQUENCE_INVALID:" + key)
    return tuple(value)


def run_product_cv_fold(
    *,
    repository_root: Path,
    environments_dir: Path,
    output_dir: Path,
    fold_index: int,
) -> dict[str, object]:
    """Execute one candidate P on its five excluded ARC3 games."""

    started = time.monotonic()
    fold_id = f"fold-{fold_index:02d}"
    compile_report = _load_content_bound(
        output_dir / "compile" / f"{fold_id}.json",
        prefix=PRODUCT_CV_COMPILE_DIGEST_PREFIX,
    )
    package_relative = compile_report.get("p_package_path")
    if not isinstance(package_relative, str) or not package_relative:
        raise TypeError("PRODUCT_CV_PACKAGE_PATH_INVALID")
    package_path = (repository_root / package_relative).resolve()
    if repository_root.resolve() not in package_path.parents:
        raise PermissionError("PRODUCT_CV_PACKAGE_PATH_OUTSIDE_REPOSITORY")
    if _sha256(package_path) != compile_report.get("p_package_sha256"):
        raise ValueError("PRODUCT_CV_PACKAGE_DIGEST_MISMATCH")
    bundle = p_bundle_from_package(package_path.read_bytes())
    if bundle.logical_digest() != compile_report.get("p_logical_digest"):
        raise ValueError("PRODUCT_CV_P_LOGICAL_DIGEST_MISMATCH")
    action_budget = _integer(compile_report, "action_budget_per_environment")
    no_progress_limit = _integer(compile_report, "no_progress_limit")
    session = create_product_cv_session(
        bundle,
        action_budget=action_budget,
        no_progress_limit=no_progress_limit,
    )
    if session.runtime_identity.digest() != compile_report.get(
        "runtime_identity_digest"
    ):
        raise ValueError("PRODUCT_CV_RUNTIME_IDENTITY_DIGEST_MISMATCH")
    holdout_raw = compile_report.get("holdout_game_ordinals")
    if not isinstance(holdout_raw, list) or any(
        isinstance(item, bool) or not isinstance(item, int) for item in holdout_raw
    ):
        raise TypeError("PRODUCT_CV_HOLDOUT_ORDINALS_INVALID")
    holdout = tuple(holdout_raw)
    arcade = Arcade(
        operation_mode=OperationMode.OFFLINE,
        environments_dir=str(environments_dir.resolve()),
        recordings_dir=str((output_dir / "recordings" / fold_id).resolve()),
    )
    game_ids = tuple(sorted(str(item.game_id) for item in arcade.get_environments()))
    if len(game_ids) != PRODUCT_CV_GAME_COUNT:
        raise RuntimeError("PRODUCT_CV_ENVIRONMENT_COUNT_INVALID")
    selected_games = tuple(game_ids[index] for index in holdout)
    scorecard_id = arcade.open_scorecard(tags=["product-cv", fold_id])
    reports: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []
    try:
        for local_index, (game_ordinal, game_id) in enumerate(
            zip(holdout, selected_games)
        ):
            handle = session.begin_episode()
            try:
                environment = arcade.make(
                    game_id,
                    scorecard_id=scorecard_id,
                    save_recording=False,
                    include_frame_data=True,
                )
                if environment is None:
                    raise RuntimeError("PRODUCT_CV_ENVIRONMENT_LOAD_FAILED")
                trace_path = (
                    output_dir / "traces" / fold_id / f"game-{local_index:02d}.jsonl.gz"
                )
                with ContentBoundTraceSink(
                    trace_path,
                    relative_to=repository_root,
                ) as sink:
                    runtime_report = GenericAGIRuntime(
                        OfflineGenericEnvironment(environment),
                        session,
                        handle,
                        retain_cycle_objects=False,
                        trace_sink=sink,
                    ).run()
                    trace = sink.close()
                receipt = session.end_episode(
                    handle,
                    succeeded=runtime_report.final_state == "WIN",
                    reason=runtime_report.stop_reason,
                )
                reports.append(
                    {
                        "game_ordinal": game_ordinal,
                        "game_id": game_id,
                        "complete": runtime_report.final_state == "WIN",
                        "completed_levels": runtime_report.progress_count,
                        "actions_executed": runtime_report.actions_executed,
                        "final_state": runtime_report.final_state,
                        "stop_reason": runtime_report.stop_reason,
                        "failure_signatures": runtime_report.failure_signatures,
                        "identity_boundary_passed": (
                            runtime_report.identity_boundary_passed
                        ),
                        "no_fallback_used": runtime_report.no_fallback_used,
                        "run_report_digest": runtime_report.digest(),
                        "memory_promoted": receipt.promoted,
                        "trace": trace.as_dict(),
                    }
                )
            except Exception as error:
                errors.append(
                    {
                        "game_ordinal": game_ordinal,
                        "game_id": game_id,
                        "error_type": type(error).__name__,
                        "error_message": str(error)[:1000],
                    }
                )
                if session.active_episode is handle:
                    session.end_episode(
                        handle,
                        succeeded=False,
                        reason=type(error).__name__,
                    )
    finally:
        arcade.close_scorecard(scorecard_id)
    execution_complete = len(reports) == len(holdout) and not errors
    completed_games = sum(bool(item["complete"]) for item in reports)
    completed_levels = sum(_integer(item, "completed_levels") for item in reports)
    identity_boundary_passed = all(
        item["identity_boundary_passed"] is True for item in reports
    )
    body: dict[str, object] = {
        "schema_version": PRODUCT_CV_SCHEMA_VERSION,
        "evaluation_role": "DEVELOPMENT_CROSS_GAME_CV_HOLDOUT",
        "allowed_claim": "PRODUCT_EQUIVALENT_CV_MEASUREMENT",
        "final_generic_claim": "NOT_AUTHORIZED",
        "locked_evaluator": False,
        "same_single_artifact_claim_allowed": False,
        "fold_id": fold_id,
        "fold_index": fold_index,
        "training_game_ordinals": compile_report["training_game_ordinals"],
        "holdout_game_ordinals": holdout,
        "training_data_completely_separated": True,
        "p_logical_digest": bundle.logical_digest(),
        "runtime_identity_digest": session.runtime_identity.digest(),
        "product_p_ir_j0_m0_bound": True,
        "action_budget_per_environment": action_budget,
        "no_progress_limit": no_progress_limit,
        "execution_count": len(reports),
        "completed_environment_count": completed_games,
        "completed_level_count": completed_levels,
        "actions_executed": sum(_integer(item, "actions_executed") for item in reports),
        "identity_boundary_passed": identity_boundary_passed,
        "reports": reports,
        "errors": errors,
        "elapsed_seconds": round(time.monotonic() - started, 3),
        "execution_status": "PASS" if execution_complete else "FAIL",
        "capability_status": ("PASS" if completed_games == len(holdout) else "FAIL"),
        "status": "PASS" if execution_complete else "FAIL",
        "failed_requirement_ids": (
            [] if execution_complete else ["M3_PRODUCT_CV_FOLD_EXECUTION"]
        ),
        "product_completion_allowed": False,
    }
    return _write_content_bound(
        output_dir / "results" / f"{fold_id}.json",
        body,
        prefix=PRODUCT_CV_FOLD_DIGEST_PREFIX,
    )


def assemble_product_cv_manifest(*, output_dir: Path) -> dict[str, object]:
    """Assemble five fold reports without upgrading them to final evidence."""

    compile_reports = tuple(
        _load_content_bound(
            output_dir / "compile" / f"fold-{index:02d}.json",
            prefix=PRODUCT_CV_COMPILE_DIGEST_PREFIX,
        )
        for index in range(PRODUCT_CV_FOLD_COUNT)
    )
    fold_reports = tuple(
        _load_content_bound(
            output_dir / "results" / f"fold-{index:02d}.json",
            prefix=PRODUCT_CV_FOLD_DIGEST_PREFIX,
        )
        for index in range(PRODUCT_CV_FOLD_COUNT)
    )
    holdout_ordinals = tuple(
        item
        for report in fold_reports
        for item in _integer_sequence(report, "holdout_game_ordinals")
    )
    execution_count = sum(_integer(item, "execution_count") for item in fold_reports)
    completed_games = sum(
        _integer(item, "completed_environment_count") for item in fold_reports
    )
    completed_levels = sum(
        _integer(item, "completed_level_count") for item in fold_reports
    )
    procedure_passed = (
        sorted(holdout_ordinals) == list(range(PRODUCT_CV_GAME_COUNT))
        and execution_count == PRODUCT_CV_GAME_COUNT
        and all(item["status"] == "PASS" for item in compile_reports)
        and all(item["execution_status"] == "PASS" for item in fold_reports)
        and len({item["p_logical_digest"] for item in fold_reports})
        == PRODUCT_CV_FOLD_COUNT
        and len({item["runtime_identity_digest"] for item in fold_reports})
        == PRODUCT_CV_FOLD_COUNT
    )
    capability_passed = completed_games == PRODUCT_CV_GAME_COUNT
    body: dict[str, object] = {
        "schema_version": PRODUCT_CV_SCHEMA_VERSION,
        "evaluation_role": "DEVELOPMENT_CROSS_GAME_CV",
        "allowed_claim": "PRODUCT_EQUIVALENT_CV_MEASUREMENT",
        "final_generic_claim": "NOT_AUTHORIZED",
        "locked_evaluator": False,
        "same_single_artifact_claim_allowed": False,
        "fold_count": len(fold_reports),
        "holdout_execution_count": execution_count,
        "holdout_completed_environment_count": completed_games,
        "holdout_completed_level_count": completed_levels,
        "distinct_p_artifact_count": len(
            {item["p_logical_digest"] for item in fold_reports}
        ),
        "distinct_runtime_identity_count": len(
            {item["runtime_identity_digest"] for item in fold_reports}
        ),
        "training_data_completely_separated": all(
            item["training_data_completely_separated"] is True for item in fold_reports
        ),
        "procedure_status": "PASS" if procedure_passed else "FAIL",
        "capability_status": "PASS" if capability_passed else "FAIL",
        "status": "PASS" if procedure_passed else "FAIL",
        "failed_requirement_ids": (
            [] if procedure_passed else ["M3_PRODUCT_CV_PROCEDURE"]
        ),
        "genericity_completion_established": False,
        "product_completion_allowed": False,
        "compile_reports": compile_reports,
        "folds": fold_reports,
    }
    return _write_content_bound(
        output_dir / "manifest.json",
        body,
        prefix=PRODUCT_CV_MANIFEST_DIGEST_PREFIX,
    )


__all__ = [
    "PRODUCT_CV_ACTION_BUDGET",
    "PRODUCT_CV_COMPILE_DIGEST_PREFIX",
    "PRODUCT_CV_FOLD_COUNT",
    "PRODUCT_CV_FOLD_DIGEST_PREFIX",
    "PRODUCT_CV_GAME_COUNT",
    "PRODUCT_CV_MANIFEST_DIGEST_PREFIX",
    "PRODUCT_CV_NO_PROGRESS_LIMIT",
    "PRODUCT_CV_SCHEMA_VERSION",
    "assemble_product_cv_manifest",
    "compile_product_cv_fold",
    "create_product_cv_session",
    "product_cv_partition",
    "run_product_cv_fold",
]
