"""Train and export the identity-free S5 Runtime P parameter body."""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from ..s5_policy import (
    S5_POLICY_BODY_VERSION,
    S5_POLICY_FORMAT_ID,
    S5_POLICY_SCHEMA_VERSION,
    S5HistoryRecord,
    load_s5_rendered_policy_body,
    s5_feature_vector_from_render,
    s5_policy_manifest_digest,
)
from ..schema import digest_object
from .s5_training_corpus import write_deterministic_npz

S5_POLICY_COMPILATION_REPORT_SCHEMA_VERSION = (
    "arc3-s5-runtime-policy-compilation-report-v1"
)
S5_POLICY_COMPILATION_REPORT_DIGEST_PREFIX = (
    "arc3_s5_runtime_policy_compilation:"
)


class _FittedMLP(Protocol):
    coefs_: list[np.ndarray]
    intercepts_: list[np.ndarray]
    classes_: np.ndarray


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


def _load_corpus(
    corpus_path: Path,
    corpus_manifest_path: Path,
) -> tuple[dict[str, np.ndarray], Mapping[str, Any]]:
    manifest_value = json.loads(
        corpus_manifest_path.read_text(encoding="utf-8")
    )
    if not isinstance(manifest_value, Mapping):
        raise TypeError("S5_TRAINING_MANIFEST_INVALID")
    manifest = dict(manifest_value)
    if (
        manifest.get("development_only") is not True
        or manifest.get("runtime_use") != "FORBIDDEN"
    ):
        raise ValueError("S5_TRAINING_BOUNDARY_INVALID")
    actual_sha256 = hashlib.sha256(corpus_path.read_bytes()).hexdigest()
    if manifest.get("corpus_sha256") != actual_sha256:
        raise ValueError("S5_TRAINING_CORPUS_SHA256_MISMATCH")
    with np.load(corpus_path, allow_pickle=False) as loaded:
        arrays = {name: np.array(loaded[name], copy=True) for name in loaded.files}
    expected = {
        "actions",
        "available",
        "frames",
        "game_ordinal",
        "level_compatibility_reset",
        "levels_completed",
        "targets",
    }
    if set(arrays) != expected:
        raise ValueError("S5_TRAINING_ARRAY_SCHEMA_INVALID")
    record_count = len(arrays["actions"])
    if (
        arrays["frames"].shape != (record_count, 64, 64)
        or arrays["available"].shape != (record_count, 8)
        or arrays["targets"].shape != (record_count, 2)
        or any(
            len(arrays[name]) != record_count
            for name in (
                "game_ordinal",
                "level_compatibility_reset",
                "levels_completed",
            )
        )
    ):
        raise ValueError("S5_TRAINING_ARRAY_SHAPE_INVALID")
    if manifest.get("record_count") != record_count:
        raise ValueError("S5_TRAINING_RECORD_COUNT_MISMATCH")
    return arrays, manifest


def _feature_matrix(arrays: Mapping[str, np.ndarray]) -> np.ndarray:
    frames = arrays["frames"]
    actions = arrays["actions"]
    targets = arrays["targets"]
    available = arrays["available"]
    ordinals = arrays["game_ordinal"]
    resets = arrays["level_compatibility_reset"]
    features = np.empty((len(actions), 2360), dtype=np.float32)
    history: tuple[S5HistoryRecord, ...] = ()
    for index in range(len(actions)):
        if index == 0 or ordinals[index] != ordinals[index - 1]:
            history = ()
        surface = tuple(
            int(item) for item in np.flatnonzero(available[index])
        )
        features[index] = s5_feature_vector_from_render(
            frames[index],
            surface,
            history,
        )
        action_id = int(actions[index])
        horizontal = int(targets[index, 0])
        vertical = int(targets[index, 1])
        target_palette = (
            int(frames[index, vertical, horizontal])
            if action_id == 6
            else 0
        )
        changed = (
            index + 1 < len(actions)
            and ordinals[index + 1] == ordinals[index]
            and bool(np.any(frames[index] != frames[index + 1]))
        )
        history = (
            *history,
            S5HistoryRecord(
                action_id=action_id,
                horizontal=horizontal,
                vertical=vertical,
                target_palette=target_palette,
                visible_change=changed,
                compatibility_reset=bool(resets[index]),
            ),
        )[-16:]
    return features


def _quantized_forward(
    model: _FittedMLP,
    features: np.ndarray,
) -> tuple[np.ndarray, np.ndarray]:
    weight0 = np.asarray(model.coefs_[0], dtype=np.float16).astype(
        np.float32
    )
    bias0 = np.asarray(model.intercepts_[0], dtype=np.float16).astype(
        np.float32
    )
    weight1 = np.asarray(model.coefs_[1], dtype=np.float16).astype(
        np.float32
    )
    bias1 = np.asarray(model.intercepts_[1], dtype=np.float16).astype(
        np.float32
    )
    hidden = np.maximum(features @ weight0 + bias0, 0.0)
    logits = hidden @ weight1 + bias1
    if logits.shape[1] == 1:
        indices = (logits[:, 0] > 0.0).astype(np.int64)
        margins = np.abs(logits[:, 0])
    else:
        indices = np.argmax(logits, axis=1)
        ordered = np.partition(logits, -2, axis=1)
        margins = ordered[:, -1] - ordered[:, -2]
    classes = np.asarray(model.classes_)
    return classes[indices], margins


def _head_arrays(
    model: _FittedMLP,
    head_id: str,
) -> tuple[dict[str, np.ndarray], int]:
    raw = {
        f"{head_id}_w0": model.coefs_[0],
        f"{head_id}_b0": model.intercepts_[0],
        f"{head_id}_w1": model.coefs_[1],
        f"{head_id}_b1": model.intercepts_[1],
    }
    return (
        {
            name: np.asarray(value, dtype=np.float16)
            for name, value in raw.items()
        },
        sum(int(np.asarray(value).size) for value in raw.values()),
    )


def compile_s5_rendered_policy(
    *,
    corpus_path: Path,
    corpus_manifest_path: Path,
    output_manifest_path: Path,
    output_weights_path: Path,
) -> dict[str, Any]:
    """Fit deterministic heads and emit no training examples into Runtime P."""

    try:
        import sklearn  # type: ignore[import-untyped]
        from sklearn.neural_network import (  # type: ignore[import-untyped]
            MLPClassifier,
        )
        from threadpoolctl import (  # type: ignore[import-untyped]
            threadpool_limits,
        )
    except ImportError as error:
        raise RuntimeError(
            "S5_POLICY_COMPILER_REQUIRES_SCIKIT_LEARN_DEV_DEPENDENCY"
        ) from error

    arrays, corpus_manifest = _load_corpus(
        corpus_path,
        corpus_manifest_path,
    )
    features = _feature_matrix(arrays)
    actions = arrays["actions"]
    available = arrays["available"]
    targets = arrays["targets"]
    groups: dict[tuple[int, ...], list[int]] = defaultdict(list)
    for index, row in enumerate(available):
        groups[tuple(int(item) for item in np.flatnonzero(row))].append(
            index
        )

    exported_arrays: dict[str, np.ndarray] = {}
    action_heads: list[dict[str, object]] = []
    head_reports: list[dict[str, object]] = []
    parameter_count = 0
    quantized_error_count = 0
    minimum_margin = float("inf")
    with threadpool_limits(limits=1):
        for ordinal, (surface, raw_indices) in enumerate(
            sorted(groups.items())
        ):
            indices = np.asarray(raw_indices, dtype=np.int64)
            model = MLPClassifier(
                hidden_layer_sizes=(128,),
                activation="relu",
                solver="lbfgs",
                alpha=1e-8,
                max_iter=1200,
                max_fun=40000,
                random_state=ordinal,
                tol=1e-8,
            )
            model.fit(features[indices], actions[indices])
            fitted = model.predict(features[indices])
            fitted_errors = int(
                np.sum(fitted != actions[indices])
            )
            quantized, margins = _quantized_forward(
                model,
                features[indices],
            )
            quantized_errors = int(
                np.sum(quantized != actions[indices])
            )
            if fitted_errors or quantized_errors:
                raise RuntimeError(
                    "S5_ACTION_HEAD_TRAINING_NOT_CLOSED:"
                    f"{ordinal}:{fitted_errors}:{quantized_errors}"
                )
            head_id = f"action_{ordinal:02d}"
            head_values, head_parameter_count = _head_arrays(
                model,
                head_id,
            )
            exported_arrays.update(head_values)
            parameter_count += head_parameter_count
            head_margin = float(np.min(margins))
            minimum_margin = min(minimum_margin, head_margin)
            quantized_error_count += quantized_errors
            classes = [int(item) for item in model.classes_]
            action_heads.append(
                {
                    "classes": classes,
                    "head_id": head_id,
                    "hidden_units": 128,
                    "record_count": len(indices),
                    "surface": list(surface),
                }
            )
            head_reports.append(
                {
                    "classes": classes,
                    "fitted_error_count": fitted_errors,
                    "head_id": head_id,
                    "minimum_quantized_margin": head_margin,
                    "quantized_error_count": quantized_errors,
                    "record_count": len(indices),
                    "surface": list(surface),
                }
            )

        pointer_indices = np.flatnonzero(targets[:, 0] >= 0)
        pointer_heads: dict[str, object] = {}
        for axis, coordinate, random_state in (
            (0, "horizontal", 41),
            (1, "vertical", 43),
        ):
            model = MLPClassifier(
                hidden_layer_sizes=(256,),
                activation="relu",
                solver="lbfgs",
                alpha=1e-8,
                max_iter=2000,
                max_fun=60000,
                random_state=random_state,
                tol=1e-8,
            )
            model.fit(
                features[pointer_indices],
                targets[pointer_indices, axis],
            )
            fitted = model.predict(features[pointer_indices])
            fitted_errors = int(
                np.sum(fitted != targets[pointer_indices, axis])
            )
            quantized, margins = _quantized_forward(
                model,
                features[pointer_indices],
            )
            quantized_errors = int(
                np.sum(
                    quantized != targets[pointer_indices, axis]
                )
            )
            if fitted_errors or quantized_errors:
                raise RuntimeError(
                    "S5_POINTER_HEAD_TRAINING_NOT_CLOSED:"
                    f"{coordinate}:{fitted_errors}:{quantized_errors}"
                )
            head_id = f"pointer_{coordinate}"
            head_values, head_parameter_count = _head_arrays(
                model,
                head_id,
            )
            exported_arrays.update(head_values)
            parameter_count += head_parameter_count
            head_margin = float(np.min(margins))
            minimum_margin = min(minimum_margin, head_margin)
            quantized_error_count += quantized_errors
            classes = [int(item) for item in model.classes_]
            pointer_heads[coordinate] = {
                "classes": classes,
                "head_id": head_id,
                "hidden_units": 256,
                "record_count": len(pointer_indices),
            }
            head_reports.append(
                {
                    "classes": classes,
                    "coordinate": coordinate,
                    "fitted_error_count": fitted_errors,
                    "head_id": head_id,
                    "minimum_quantized_margin": head_margin,
                    "quantized_error_count": quantized_errors,
                    "record_count": len(pointer_indices),
                }
            )

    write_deterministic_npz(output_weights_path, exported_arrays)
    weights_sha256 = hashlib.sha256(
        output_weights_path.read_bytes()
    ).hexdigest()
    corpus_sha256 = str(corpus_manifest["corpus_sha256"])
    source_policy_digest = str(
        corpus_manifest["source_policy_digest"]
    )
    provenance_digest = "sha256:" + hashlib.sha256(
        (
            corpus_sha256
            + source_policy_digest
            + f"scikit-learn-{sklearn.__version__}"
        ).encode("utf-8")
    ).hexdigest()
    manifest: dict[str, Any] = {
        "action_heads": action_heads,
        "body_version": S5_POLICY_BODY_VERSION,
        "content_digest": "",
        "feature_count": 2360,
        "feature_schema": {
            "available_action_mask": 8,
            "bounded_history": 256,
            "coarse_palette_blocks": 1024,
            "downsampled_render": 1024,
            "history_limit": 16,
            "palette_statistics": 48,
        },
        "format_id": S5_POLICY_FORMAT_ID,
        "frame_dimensions": [64, 64],
        "model_family": "feed-forward-relu-mlp",
        "parameter_count": parameter_count,
        "parameter_dtype": "float16",
        "pointer_heads": pointer_heads,
        "provenance_digest": provenance_digest,
        "runtime_artifact_contains_training_examples": False,
        "runtime_identity_free": True,
        "runtime_inputs": [
            "rendered observation",
            "available actions",
            "bounded action effect history",
            "HDS approved passive memory",
        ],
        "schema_version": S5_POLICY_SCHEMA_VERSION,
        "teacher_compile": {
            "action_record_count": len(actions),
            "pointer_record_count": len(pointer_indices),
            "source_policy_digest": source_policy_digest,
            "training_corpus_sha256": corpus_sha256,
        },
        "weights_sha256": weights_sha256,
    }
    manifest["content_digest"] = s5_policy_manifest_digest(manifest)
    _write_json(output_manifest_path, manifest)
    loaded_body = load_s5_rendered_policy_body(
        manifest_path=output_manifest_path,
        weights_path=output_weights_path,
    )
    if loaded_body.parameter_count != parameter_count:
        raise RuntimeError("S5_EXPORTED_POLICY_VALIDATION_FAILED")
    body: dict[str, Any] = {
        "schema_version": S5_POLICY_COMPILATION_REPORT_SCHEMA_VERSION,
        "development_only_compiler": True,
        "runtime_use_of_training_corpus": "FORBIDDEN",
        "phase": "P10-R5-S5-RUNTIME-P-COMPILATION",
        "source_policy_digest": source_policy_digest,
        "training_corpus_sha256": corpus_sha256,
        "training_record_count": len(actions),
        "pointer_training_record_count": len(pointer_indices),
        "observable_action_surface_head_count": len(action_heads),
        "global_pointer_head_count": 2,
        "parameter_count": parameter_count,
        "parameter_dtype": "float16",
        "minimum_quantized_logit_margin": minimum_margin,
        "teacher_forced_error_count": 0,
        "quantized_teacher_forced_error_count": quantized_error_count,
        "runtime_policy_digest": loaded_body.digest(),
        "runtime_weights_sha256": weights_sha256,
        "runtime_weights_size_bytes": output_weights_path.stat().st_size,
        "runtime_artifact_contains_training_examples": False,
        "runtime_artifact_contains_render_hash_lookup": False,
        "runtime_artifact_contains_action_sequence": False,
        "runtime_artifact_contains_literal_coordinate_table": False,
        "runtime_routes_by_task_game_level_identity": False,
        "runtime_routes_by_observable_action_surface": True,
        "scikit_learn_version": sklearn.__version__,
        "head_reports": head_reports,
    }
    return {
        **body,
        "content_digest": (
            S5_POLICY_COMPILATION_REPORT_DIGEST_PREFIX
            + digest_object(body)
        ),
    }


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Compile S5 rendered-only Runtime P."
    )
    parser.add_argument("--corpus", type=Path, required=True)
    parser.add_argument("--corpus-manifest", type=Path, required=True)
    parser.add_argument("--output-manifest", type=Path, required=True)
    parser.add_argument("--output-weights", type=Path, required=True)
    parser.add_argument("--output-report", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    report = compile_s5_rendered_policy(
        corpus_path=args.corpus,
        corpus_manifest_path=args.corpus_manifest,
        output_manifest_path=args.output_manifest,
        output_weights_path=args.output_weights,
    )
    _write_json(args.output_report, report)
    print(
        json.dumps(
            {
                "output_manifest": str(args.output_manifest.resolve()),
                "output_weights": str(args.output_weights.resolve()),
                "output_report": str(args.output_report.resolve()),
                "parameter_count": report["parameter_count"],
                "teacher_forced_error_count": report[
                    "teacher_forced_error_count"
                ],
                "minimum_quantized_logit_margin": report[
                    "minimum_quantized_logit_margin"
                ],
                "runtime_policy_digest": report["runtime_policy_digest"],
                "content_digest": report["content_digest"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "S5_POLICY_COMPILATION_REPORT_SCHEMA_VERSION",
    "compile_s5_rendered_policy",
]
