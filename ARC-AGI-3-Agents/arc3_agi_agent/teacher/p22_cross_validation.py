"""Development-only five-fold P compilation for P22 procedure evidence."""

from __future__ import annotations

import hashlib
import json
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any, Final, TypedDict

import numpy as np

from ..compiled_policy import (
    COMPILED_POLICY_BODY_VERSION,
    COMPILED_POLICY_FEATURE_COUNT,
    COMPILED_POLICY_FORMAT_ID,
    COMPILED_POLICY_SCHEMA_VERSION,
    compiled_policy_manifest_digest,
    load_compiled_autonomous_instruction_body,
)
from ..evaluation_registry import EvaluationRegistry
from ..generic_compute import HybridRelationalInstructionBody
from ..generic_hds import HDSConfiguration
from ..p_compiler_v2 import PCompilerV2
from ..runtime_identity import build_runtime_identity
from ..schema import digest_object
from .s5_policy_compiler import _feature_matrix, _load_corpus
from .s5_training_corpus import write_deterministic_npz

P22_CV_COMPILER_VERSION: Final = "arc3-p22-cv-compiler-v1"
P22_CV_FOLD_COUNT: Final = 5
P22_CV_GAME_COUNT: Final = 25
# CV is procedure evidence, not the 183-level public completion gate.  Keep
# every holdout execution finite even when a train-only policy makes no
# progress; the measured completion count remains visible in the result.
P22_CV_ACTION_BUDGET: Final = 64
P22_CV_HIDDEN_FEATURES: Final = 64


class _HeadReport(TypedDict):
    head_id: str
    classes: tuple[int, ...]
    hidden_feature_count: int
    selected_feature_digest: str
    training_record_count: int
    training_error_count: int


class _CVPolicyCompileReport(TypedDict):
    training_selection_digest: str
    training_record_count: int
    training_game_count: int
    training_error_count: int
    runtime_artifact_contains_examples: bool
    runtime_policy_digest: str
    parameter_count: int
    head_reports: list[_HeadReport]


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


def _centroid_head(
    *,
    features: np.ndarray,
    labels: np.ndarray,
    head_id: str,
) -> tuple[dict[str, np.ndarray], _HeadReport]:
    classes = np.unique(labels)
    if len(classes) < 2:
        raise ValueError("P22_CV_HEAD_CLASS_COUNT_INVALID:" + head_id)
    variances = np.var(features, axis=0)
    candidate_indices = np.flatnonzero(variances > 0)
    if not len(candidate_indices):
        candidate_indices = np.arange(features.shape[1])
    ranked = candidate_indices[
        np.argsort(
            variances[candidate_indices],
            kind="stable",
        )
    ]
    selected = np.sort(ranked[-P22_CV_HIDDEN_FEATURES:])
    hidden_count = len(selected)
    weight0 = np.zeros(
        (COMPILED_POLICY_FEATURE_COUNT, hidden_count),
        dtype=np.float32,
    )
    weight0[selected, np.arange(hidden_count)] = 1.0
    bias0 = np.zeros(hidden_count, dtype=np.float32)
    projected = features[:, selected]
    centroids = np.stack(
        [
            np.mean(projected[labels == class_value], axis=0)
            for class_value in classes
        ]
    )
    if len(classes) == 2:
        weight1 = (
            2.0 * (centroids[1] - centroids[0])
        ).reshape(hidden_count, 1)
        bias1 = np.asarray(
            [
                np.dot(centroids[0], centroids[0])
                - np.dot(centroids[1], centroids[1])
            ],
            dtype=np.float32,
        )
    else:
        weight1 = (2.0 * centroids.T).astype(np.float32)
        bias1 = -np.sum(centroids * centroids, axis=1)
    arrays = {
        f"{head_id}_w0": np.asarray(weight0, dtype=np.float16),
        f"{head_id}_b0": np.asarray(bias0, dtype=np.float16),
        f"{head_id}_w1": np.asarray(weight1, dtype=np.float16),
        f"{head_id}_b1": np.asarray(bias1, dtype=np.float16),
    }
    quantized_hidden = np.maximum(
        features @ arrays[f"{head_id}_w0"].astype(np.float32)
        + arrays[f"{head_id}_b0"].astype(np.float32),
        0.0,
    )
    logits = (
        quantized_hidden @ arrays[f"{head_id}_w1"].astype(np.float32)
        + arrays[f"{head_id}_b1"].astype(np.float32)
    )
    if logits.shape[1] == 1:
        predicted = classes[(logits[:, 0] > 0).astype(np.int64)]
    else:
        predicted = classes[np.argmax(logits, axis=1)]
    return arrays, {
        "head_id": head_id,
        "classes": tuple(int(item) for item in classes),
        "hidden_feature_count": hidden_count,
        "selected_feature_digest": "p22-cv-features:"
        + digest_object(tuple(int(item) for item in selected)),
        "training_record_count": len(labels),
        "training_error_count": int(np.sum(predicted != labels)),
    }


def _compile_cv_policy(
    *,
    corpus_path: Path,
    corpus_manifest_path: Path,
    output_manifest_path: Path,
    output_weights_path: Path,
    training_game_ordinals: tuple[int, ...],
) -> _CVPolicyCompileReport:
    arrays, corpus_manifest = _load_corpus(
        corpus_path,
        corpus_manifest_path,
    )
    selection = np.isin(
        arrays["game_ordinal"],
        np.asarray(training_game_ordinals, dtype=np.uint8),
    )
    selected_arrays = {
        name: np.asarray(value[selection])
        for name, value in arrays.items()
    }
    features = _feature_matrix(selected_arrays)
    actions = selected_arrays["actions"]
    available = selected_arrays["available"]
    targets = selected_arrays["targets"]
    groups: dict[tuple[int, ...], list[int]] = defaultdict(list)
    for index, row in enumerate(available):
        groups[
            tuple(int(item) for item in np.flatnonzero(row))
        ].append(index)
    exported: dict[str, np.ndarray] = {}
    action_heads: list[dict[str, object]] = []
    head_reports: list[_HeadReport] = []
    for ordinal, (surface, raw_indices) in enumerate(
        sorted(groups.items())
    ):
        indices = np.asarray(raw_indices, dtype=np.int64)
        head_id = f"action_{ordinal:02d}"
        head_arrays, report = _centroid_head(
            features=features[indices],
            labels=actions[indices],
            head_id=head_id,
        )
        exported.update(head_arrays)
        action_heads.append(
            {
                "classes": list(report["classes"]),
                "head_id": head_id,
                "hidden_units": report["hidden_feature_count"],
                "record_count": len(indices),
                "surface": list(surface),
            }
        )
        head_reports.append(report)
    pointer_indices = np.flatnonzero(targets[:, 0] >= 0)
    pointer_heads: dict[str, object] = {}
    for axis, coordinate in ((0, "horizontal"), (1, "vertical")):
        head_id = f"pointer_{coordinate}"
        head_arrays, report = _centroid_head(
            features=features[pointer_indices],
            labels=targets[pointer_indices, axis],
            head_id=head_id,
        )
        exported.update(head_arrays)
        pointer_heads[coordinate] = {
            "classes": list(report["classes"]),
            "head_id": head_id,
            "hidden_units": report["hidden_feature_count"],
            "record_count": len(pointer_indices),
        }
        head_reports.append(report)
    write_deterministic_npz(output_weights_path, exported)
    weights_sha256 = _sha256(output_weights_path)
    parameter_count = sum(int(value.size) for value in exported.values())
    selection_digest = "p22-cv-training-selection:" + digest_object(
        {
            "corpus_sha256": corpus_manifest["corpus_sha256"],
            "training_game_ordinals": training_game_ordinals,
        }
    )
    structural = HybridRelationalInstructionBody()
    provenance_digest = "generic-policy-provenance:" + digest_object(
        {
            "compiler": P22_CV_COMPILER_VERSION,
            "selection_digest": selection_digest,
            "structural_body_digest": structural.digest(),
        }
    )
    manifest: dict[str, Any] = {
        "action_heads": action_heads,
        "body_version": COMPILED_POLICY_BODY_VERSION,
        "content_digest": "",
        "feature_count": COMPILED_POLICY_FEATURE_COUNT,
        "feature_schema": {
            "available_action_mask": 8,
            "bounded_history": 256,
            "coarse_palette_blocks": 1024,
            "downsampled_render": 1024,
            "history_limit": 16,
            "palette_statistics": 48,
        },
        "format_id": COMPILED_POLICY_FORMAT_ID,
        "frame_dimensions": [64, 64],
        "migration_version": P22_CV_COMPILER_VERSION,
        "model_family": "variance-projection-nearest-centroid",
        "parameter_count": parameter_count,
        "parameter_dtype": "float16",
        "pointer_heads": pointer_heads,
        "provenance_digest": provenance_digest,
        "runtime_artifact_contains_examples": False,
        "runtime_identity_free": True,
        "runtime_inputs": (
            "rendered observation",
            "available actions",
            "bounded HDS-authorized action-effect memory",
            "passive semantic memory",
        ),
        "schema_version": COMPILED_POLICY_SCHEMA_VERSION,
        "source_parameter_digest": selection_digest,
        "structural_body_digest": structural.digest(),
        "weights_sha256": weights_sha256,
    }
    manifest["content_digest"] = compiled_policy_manifest_digest(manifest)
    output_manifest_path.write_text(
        json.dumps(
            manifest,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    body = load_compiled_autonomous_instruction_body(
        manifest_path=output_manifest_path,
        weights_path=output_weights_path,
    )
    return {
        "training_selection_digest": selection_digest,
        "training_record_count": len(actions),
        "training_game_count": len(training_game_ordinals),
        "training_error_count": sum(
            report["training_error_count"] for report in head_reports
        ),
        "runtime_artifact_contains_examples": False,
        "runtime_policy_digest": body.digest(),
        "parameter_count": parameter_count,
        "head_reports": head_reports,
    }


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
            compile_report = _compile_cv_policy(
                corpus_path=corpus_path,
                corpus_manifest_path=corpus_manifest_path,
                output_manifest_path=source_manifest,
                output_weights_path=source_weights,
                training_game_ordinals=training,
            )
            body = load_compiled_autonomous_instruction_body(
                manifest_path=source_manifest,
                weights_path=source_weights,
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
                "action_budget_per_environment": P22_CV_ACTION_BUDGET,
                "training_selection_digest": compile_report[
                    "training_selection_digest"
                ],
                "training_record_count": compile_report[
                    "training_record_count"
                ],
                "training_error_count": compile_report[
                    "training_error_count"
                ],
                "runtime_artifact_contains_examples": compile_report[
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
        "action_budget_per_environment": P22_CV_ACTION_BUDGET,
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
