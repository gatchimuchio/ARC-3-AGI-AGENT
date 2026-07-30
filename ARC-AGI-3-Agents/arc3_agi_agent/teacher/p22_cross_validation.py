"""Development-only five-fold P compilation for P22 procedure evidence."""

from __future__ import annotations

import hashlib
import json
import tempfile
from pathlib import Path
from typing import Final

from ..evaluation_registry import EvaluationRegistry
from ..generic_hds import HDSConfiguration
from ..p_compiler_v2 import PCompilerV2
from ..runtime_identity import build_runtime_identity
from ..schema import digest_object
from .generic_policy_migration import migrate_identity_free_policy
from .s5_policy_compiler import compile_s5_rendered_policy

P22_CV_COMPILER_VERSION: Final = "arc3-p22-cv-compiler-v1"
P22_CV_FOLD_COUNT: Final = 5
P22_CV_GAME_COUNT: Final = 25
P22_CV_ACTION_BUDGET: Final = 4096


def deterministic_cv_folds(
    *,
    game_count: int = P22_CV_GAME_COUNT,
    fold_count: int = P22_CV_FOLD_COUNT,
) -> tuple[tuple[int, ...], ...]:
    if game_count <= 0 or fold_count <= 1 or game_count % fold_count:
        raise ValueError("P22_CV_PARTITION_DIMENSIONS_INVALID")
    folds = tuple(
        tuple(
            ordinal
            for ordinal in range(game_count)
            if ordinal % fold_count == fold
        )
        for fold in range(fold_count)
    )
    flattened = tuple(item for fold in folds for item in fold)
    if (
        len(flattened) != game_count
        or set(flattened) != set(range(game_count))
        or any(len(fold) != game_count // fold_count for fold in folds)
    ):
        raise RuntimeError("P22_CV_PARTITION_INVALID")
    return folds


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_content_bound(
    path: Path,
    value: dict[str, object],
) -> dict[str, object]:
    body = dict(value)
    body["content_digest"] = "p22-cv-compile:" + digest_object(body)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            body,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return body


def compile_cv_fold_artifacts(
    *,
    corpus_path: Path,
    corpus_manifest_path: Path,
    output_dir: Path,
) -> dict[str, object]:
    """Compile five physically separate P artifacts with disjoint holdouts."""

    corpus_manifest = json.loads(
        corpus_manifest_path.read_text(encoding="utf-8")
    )
    if not isinstance(corpus_manifest, dict):
        raise TypeError("P22_CV_CORPUS_MANIFEST_INVALID")
    if (
        corpus_manifest.get("environment_count") != P22_CV_GAME_COUNT
        or corpus_manifest.get("development_only") is not True
        or corpus_manifest.get("runtime_use") != "FORBIDDEN"
    ):
        raise ValueError("P22_CV_CORPUS_BOUNDARY_INVALID")
    if corpus_manifest.get("corpus_sha256") != _sha256(corpus_path):
        raise ValueError("P22_CV_CORPUS_DIGEST_MISMATCH")
    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_dir = output_dir / "cv_artifacts"
    artifact_dir.mkdir(parents=True, exist_ok=True)
    folds = deterministic_cv_folds()
    all_ordinals = set(range(P22_CV_GAME_COUNT))
    registry = EvaluationRegistry()
    results: list[dict[str, object]] = []
    for fold_index, holdout in enumerate(folds):
        fold_id = f"fold-{fold_index:02d}"
        training = tuple(sorted(all_ordinals.difference(holdout)))
        if set(training).intersection(holdout):
            raise RuntimeError("P22_CV_TRAIN_HOLDOUT_OVERLAP")
        if set(training).union(holdout) != all_ordinals:
            raise RuntimeError("P22_CV_TRAIN_HOLDOUT_COVERAGE_INVALID")
        with tempfile.TemporaryDirectory(
            prefix=f"arc3-p22-{fold_id}-"
        ) as temporary:
            temporary_dir = Path(temporary)
            source_manifest = temporary_dir / "source.json"
            source_weights = temporary_dir / "source.npz"
            generic_manifest = temporary_dir / "generic.json"
            generic_weights = temporary_dir / "generic.npz"
            compile_report = compile_s5_rendered_policy(
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
            from ..compiled_policy import (
                load_compiled_autonomous_instruction_body,
            )

            body = load_compiled_autonomous_instruction_body(
                manifest_path=generic_manifest,
                weights_path=generic_weights,
            )
            bundle = PCompilerV2().bootstrap(
                body=body,
                version=f"p22-cv-{fold_id}-v1",
            )
            package_path = artifact_dir / f"{fold_id}.p.zip"
            package_payload = bundle.package_bytes()
            package_path.write_bytes(package_payload)
        hds = HDSConfiguration(
            resource_budget=P22_CV_ACTION_BUDGET,
            stop_after_no_progress=P22_CV_ACTION_BUDGET,
        )
        runtime_identity = build_runtime_identity(
            p_bundle=bundle.body,
            p_ir_program=bundle.program,
            hds_configuration=hds,
            initial_memory_records=(),
        )
        dataset_id = f"P22_CV_HOLDOUT_{fold_index:02d}"
        dataset_digest = "p22-cv-holdout:" + digest_object(
            {
                "source_corpus": corpus_manifest["corpus_sha256"],
                "holdout_ordinals": holdout,
            }
        )
        registry.register_dataset(
            dataset_id=dataset_id,
            dataset_digest=dataset_digest,
            owner="P22_CV_EVALUATOR",
            role="CV_HOLDOUT",
        )
        initial_state_digest = "p22-cv-initial-state:" + digest_object(
            {
                "p": bundle.logical_digest(),
                "j0": hds,
                "m0": (),
            }
        )
        registry_artifact = registry.register_cv_artifact(
            fold_id=fold_id,
            dataset_id=dataset_id,
            p_logical_digest=bundle.logical_digest(),
            initial_state_logical_digest=initial_state_digest,
            runtime_identity=runtime_identity,
        )
        results.append(
            {
                "fold_id": fold_id,
                "training_game_ordinals": training,
                "holdout_game_ordinals": holdout,
                "training_game_count": len(training),
                "holdout_game_count": len(holdout),
                "training_selection_digest": compile_report[
                    "training_selection_digest"
                ],
                "training_record_count": compile_report[
                    "training_record_count"
                ],
                "teacher_forced_error_count": compile_report[
                    "teacher_forced_error_count"
                ],
                "quantized_teacher_forced_error_count": compile_report[
                    "quantized_teacher_forced_error_count"
                ],
                "runtime_artifact_contains_examples": migration_report[
                    "runtime_artifact_contains_examples"
                ],
                "artifact_path": package_path.relative_to(
                    output_dir.parent.parent
                ).as_posix(),
                "artifact_size_bytes": len(package_payload),
                "artifact_sha256": hashlib.sha256(
                    package_payload
                ).hexdigest(),
                "p_logical_digest": bundle.logical_digest(),
                "p_package_digest": bundle.physical_digest(),
                "runtime_identity_digest": runtime_identity.digest(),
                "dataset_id": dataset_id,
                "dataset_digest": dataset_digest,
                "access_event_digest": (
                    registry_artifact.access_event_digest
                ),
                "allowed_claim": registry_artifact.allowed_claim,
            }
        )
    summary = registry.cv_procedure_summary()
    p_digests = {str(item["p_logical_digest"]) for item in results}
    runtime_digests = {
        str(item["runtime_identity_digest"]) for item in results
    }
    training_separated = all(
        not all_ordinals.difference(holdout).intersection(holdout)
        for holdout in folds
    )
    requirements = {
        "P22A-003": summary.fold_count == P22_CV_FOLD_COUNT,
        "P22A-004": (
            summary.distinct_runtime_identity_count == P22_CV_FOLD_COUNT
        ),
        "P22A-CV-P-DISTINCT": len(p_digests) == P22_CV_FOLD_COUNT,
        "P22A-CV-TRAINING-SEPARATION": training_separated,
        "P22A-CV-RUNTIME-EXAMPLES": all(
            item["runtime_artifact_contains_examples"] is False
            for item in results
        ),
    }
    failed = [key for key, passed in requirements.items() if not passed]
    report: dict[str, object] = {
        "schema_version": P22_CV_COMPILER_VERSION,
        "evaluation_role": "CV_HOLDOUT",
        "allowed_claim": "CV_PROCEDURE_EVIDENCE",
        "same_single_artifact_claim_allowed": False,
        "source_corpus_sha256": corpus_manifest["corpus_sha256"],
        "fold_count": len(results),
        "distinct_p_artifact_count": len(p_digests),
        "distinct_runtime_identity_count": len(runtime_digests),
        "training_data_completely_separated": training_separated,
        "holdout_execution_status": "PENDING",
        "folds": results,
        "registry_digest": registry.digest(),
        "status": "PASS" if not failed else "FAIL",
        "failed_requirement_ids": failed,
    }
    return _write_content_bound(
        output_dir / "cv_compile_manifest.json",
        report,
    )


__all__ = [
    "P22_CV_ACTION_BUDGET",
    "P22_CV_COMPILER_VERSION",
    "P22_CV_FOLD_COUNT",
    "P22_CV_GAME_COUNT",
    "compile_cv_fold_artifacts",
    "deterministic_cv_folds",
]
