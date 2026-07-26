"""Static and execution-evidence audit for the rendered-only S5 Runtime P."""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
from collections import Counter, defaultdict
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import numpy as np

from ..s5_policy import (
    S5_FEATURE_COUNT,
    S5_POLICY_BODY_VERSION,
    load_s5_rendered_policy_body,
)
from ..s5_runner import load_s5_closure_report
from ..schema import digest_object, forbidden_runtime_paths

S5_RUNTIME_AUDIT_SCHEMA_VERSION = "arc3-s5-runtime-boundary-audit-v1"
S5_RUNTIME_AUDIT_DIGEST_PREFIX = "arc3_s5_runtime_boundary_audit:"
S5_POLICY_COMPILATION_REPORT_DIGEST_PREFIX = (
    "arc3_s5_runtime_policy_compilation:"
)

_DECISION_MODULES = (
    "s5_policy.py",
    "s5_compute.py",
    "s5_runtime.py",
    "s5_authority.py",
)
_FORBIDDEN_IMPORT_PREFIXES = (
    "arc3_agi_agent.teacher",
    "teacher",
)
_EXPECTED_CLOSURE_FALSE_CLAIMS = (
    "action_selection_receives_environment_identity",
    "action_selection_receives_environment_wrapper",
    "action_selection_receives_source_or_hidden_state",
    "runtime_imports_teacher_package",
    "runtime_reads_teacher_artifact",
    "decision_uses_task_game_level_identity",
    "decision_uses_level_progress_counter",
    "decision_uses_per_game_policy_partition",
    "decision_uses_source_or_hidden_state",
    "decision_uses_answer_or_replay_graph",
    "decision_uses_fixed_action_sequence",
    "decision_uses_literal_coordinate_table",
)


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


def _mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be an object")
    return value


def _load_digest_report(
    path: Path,
    *,
    digest_prefix: str,
) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    report = dict(_mapping(value, str(path)))
    content_digest = report.pop("content_digest", None)
    if content_digest != digest_prefix + digest_object(report):
        raise ValueError(f"S5_REPORT_DIGEST_MISMATCH:{path.name}")
    return dict(value)


def _imports(tree: ast.AST) -> tuple[str, ...]:
    values: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            values.update(item.name for item in node.names)
        elif isinstance(node, ast.ImportFrom):
            prefix = "." * node.level
            values.add(prefix + (node.module or ""))
    return tuple(sorted(values))


def _function(tree: ast.AST, name: str) -> ast.FunctionDef:
    matches = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.FunctionDef) and node.name == name
    ]
    if len(matches) != 1:
        raise ValueError(f"S5_AUDIT_FUNCTION_RESOLUTION_FAILED:{name}")
    return matches[0]


def _method(
    tree: ast.AST,
    class_name: str,
    method_name: str,
) -> ast.FunctionDef:
    classes = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.ClassDef) and node.name == class_name
    ]
    if len(classes) != 1:
        raise ValueError(
            f"S5_AUDIT_CLASS_RESOLUTION_FAILED:{class_name}"
        )
    matches = [
        node
        for node in classes[0].body
        if isinstance(node, ast.FunctionDef) and node.name == method_name
    ]
    if len(matches) != 1:
        raise ValueError(
            "S5_AUDIT_METHOD_RESOLUTION_FAILED:"
            f"{class_name}.{method_name}"
        )
    return matches[0]


def inspect_s5_runtime_boundary(
    package_dir: Path,
) -> dict[str, object]:
    """Inspect action-selection source without trusting report claims."""

    module_reports: list[dict[str, object]] = []
    failures: list[str] = []
    trees: dict[str, ast.Module] = {}
    for filename in _DECISION_MODULES:
        path = package_dir / filename
        source = path.read_text(encoding="utf-8")
        tree = ast.parse(source, filename=str(path))
        trees[filename] = tree
        imports = _imports(tree)
        forbidden = tuple(
            item
            for item in imports
            if any(
                item.lstrip(".").startswith(prefix)
                for prefix in _FORBIDDEN_IMPORT_PREFIXES
            )
        )
        if forbidden:
            failures.append(f"S5_RUNTIME_TEACHER_IMPORT:{filename}")
        module_reports.append(
            {
                "filename": filename,
                "imports": list(imports),
                "forbidden_teacher_imports": list(forbidden),
                "sha256": hashlib.sha256(
                    source.encode("utf-8")
                ).hexdigest(),
            }
        )

    policy_tree = trees["s5_policy.py"]
    predict = _method(
        policy_tree,
        "S5RenderedPolicyBody",
        "predict",
    )
    predict_parameters = tuple(
        item.arg
        for item in (
            *predict.args.posonlyargs,
            *predict.args.args,
            *predict.args.kwonlyargs,
        )
    )
    expected_parameters = ("self", "observation", "context", "memory")
    if predict_parameters != expected_parameters:
        failures.append("S5_POLICY_PREDICT_INPUT_BOUNDARY_INVALID")

    feature = _function(policy_tree, "s5_feature_vector_from_render")
    feature_parameters = tuple(
        item.arg
        for item in (
            *feature.args.posonlyargs,
            *feature.args.args,
            *feature.args.kwonlyargs,
        )
    )
    expected_feature_parameters = (
        "rendered",
        "available_actions",
        "history",
    )
    if feature_parameters != expected_feature_parameters:
        failures.append("S5_POLICY_FEATURE_INPUT_BOUNDARY_INVALID")
    history_fields = tuple(
        sorted(
            {
                node.attr
                for node in ast.walk(feature)
                if isinstance(node, ast.Attribute)
                and isinstance(node.value, ast.Name)
                and node.value.id == "record"
            }
        )
    )
    if "source_render_digest" in history_fields:
        failures.append("S5_RENDER_DIGEST_USED_AS_POLICY_FEATURE")

    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": sorted(set(failures)),
        "decision_modules": module_reports,
        "policy_predict_parameters": list(predict_parameters),
        "feature_parameters": list(feature_parameters),
        "history_feature_fields": list(history_fields),
        "source_render_digest_used_as_policy_feature": False
        if "source_render_digest" not in history_fields
        else True,
    }


def inspect_s5_policy_artifact(
    *,
    manifest_path: Path,
    weights_path: Path,
) -> dict[str, object]:
    """Validate that Runtime P contains parameters, not Teacher examples."""

    body = load_s5_rendered_policy_body(
        manifest_path=manifest_path,
        weights_path=weights_path,
    )
    manifest_value = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = _mapping(manifest_value, "policy manifest")
    failures: list[str] = []
    forbidden_paths = forbidden_runtime_paths(manifest)
    if forbidden_paths:
        failures.append("S5_POLICY_MANIFEST_FORBIDDEN_RUNTIME_PATH")
    if (
        manifest.get("runtime_artifact_contains_training_examples")
        is not False
    ):
        failures.append("S5_POLICY_TRAINING_EXAMPLE_FLAG_INVALID")
    if manifest.get("runtime_identity_free") is not True:
        failures.append("S5_POLICY_IDENTITY_FLAG_INVALID")
    if manifest.get("body_version") != S5_POLICY_BODY_VERSION:
        failures.append("S5_POLICY_BODY_VERSION_INVALID")

    expected_arrays: set[str] = set()
    for raw in _mapping_sequence(manifest.get("action_heads"), "action_heads"):
        head_id = str(raw.get("head_id", ""))
        expected_arrays.update(
            f"{head_id}_{suffix}" for suffix in ("w0", "b0", "w1", "b1")
        )
    pointer_heads = _mapping(manifest.get("pointer_heads"), "pointer_heads")
    for axis in ("horizontal", "vertical"):
        head = _mapping(pointer_heads.get(axis), f"pointer.{axis}")
        head_id = str(head.get("head_id", ""))
        expected_arrays.update(
            f"{head_id}_{suffix}" for suffix in ("w0", "b0", "w1", "b1")
        )

    array_reports: list[dict[str, object]] = []
    with np.load(weights_path, allow_pickle=False) as loaded:
        actual_arrays = set(loaded.files)
        if actual_arrays != expected_arrays:
            failures.append("S5_POLICY_PARAMETER_ARRAY_SCHEMA_INVALID")
        for name in sorted(loaded.files):
            value = np.asarray(loaded[name])
            if value.dtype != np.float16:
                failures.append(f"S5_POLICY_PARAMETER_DTYPE_INVALID:{name}")
            if value.ndim not in {1, 2}:
                failures.append(f"S5_POLICY_PARAMETER_RANK_INVALID:{name}")
            if not np.isfinite(value).all():
                failures.append(f"S5_POLICY_PARAMETER_NONFINITE:{name}")
            if S5_FEATURE_COUNT in value.shape and not name.endswith("_w0"):
                failures.append(
                    f"S5_POLICY_FEATURE_AXIS_OUTSIDE_INPUT_WEIGHT:{name}"
                )
            array_reports.append(
                {
                    "dtype": str(value.dtype),
                    "name": name,
                    "shape": list(value.shape),
                }
            )

    return {
        "status": "PASS" if not failures else "FAIL",
        "failures": sorted(set(failures)),
        "policy_digest": body.digest(),
        "parameter_count": body.parameter_count,
        "weights_sha256": hashlib.sha256(
            weights_path.read_bytes()
        ).hexdigest(),
        "forbidden_runtime_paths": list(forbidden_paths),
        "parameter_array_count": len(array_reports),
        "parameter_arrays": array_reports,
        "training_examples_present": False
        if manifest.get("runtime_artifact_contains_training_examples")
        is False
        else True,
    }


def _mapping_sequence(
    value: object,
    field_name: str,
) -> tuple[Mapping[str, Any], ...]:
    if (
        not isinstance(value, list)
        or not all(isinstance(item, Mapping) for item in value)
    ):
        raise TypeError(f"{field_name} must be an object array")
    return tuple(value)


def inspect_s5_development_corpus(
    corpus_path: Path,
) -> dict[str, object]:
    """Measure observable-surface proxy risk without exporting identities."""

    with np.load(corpus_path, allow_pickle=False) as loaded:
        available = np.asarray(loaded["available"])
        actions = np.asarray(loaded["actions"])
        frames = np.asarray(loaded["frames"])
        ordinals = np.asarray(loaded["game_ordinal"])
    surfaces: dict[tuple[int, ...], set[int]] = defaultdict(set)
    frame_surface_actions: dict[
        tuple[str, tuple[int, ...]],
        list[int],
    ] = defaultdict(list)
    for frame, available_row, action, ordinal in zip(
        frames,
        available,
        actions,
        ordinals,
        strict=True,
    ):
        surface = tuple(int(item) for item in np.flatnonzero(available_row))
        surfaces[surface].add(int(ordinal))
        frame_digest = hashlib.sha256(
            np.asarray(frame).tobytes(order="C")
        ).hexdigest()
        frame_surface_actions[(frame_digest, surface)].append(int(action))
    span_counts = Counter(len(values) for values in surfaces.values())
    conflicts = tuple(
        values
        for values in frame_surface_actions.values()
        if len(set(values)) > 1
    )
    return {
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "record_count": len(actions),
        "observable_action_surface_count": len(surfaces),
        "surface_game_span_histogram": {
            str(span): count for span, count in sorted(span_counts.items())
        },
        "single_game_surface_count": span_counts.get(1, 0),
        "multi_game_surface_count": sum(
            count for span, count in span_counts.items() if span > 1
        ),
        "exact_render_surface_action_conflict_group_count": len(conflicts),
        "exact_render_surface_action_conflict_record_count": sum(
            len(values) for values in conflicts
        ),
        "history_is_observably_necessary": bool(conflicts),
        "observable_surface_proxy_risk_present": span_counts.get(1, 0) > 0,
        "generalization_claim_authorized": False,
    }


def audit_s5_runtime(
    *,
    package_dir: Path,
    manifest_path: Path,
    weights_path: Path,
    policy_compilation_report_path: Path,
    closure_report_path: Path,
    training_corpus_path: Path,
) -> dict[str, Any]:
    """Combine independent static checks with closed execution evidence."""

    static_boundary = inspect_s5_runtime_boundary(package_dir)
    policy_artifact = inspect_s5_policy_artifact(
        manifest_path=manifest_path,
        weights_path=weights_path,
    )
    compilation = _load_digest_report(
        policy_compilation_report_path,
        digest_prefix=S5_POLICY_COMPILATION_REPORT_DIGEST_PREFIX,
    )
    closure = load_s5_closure_report(closure_report_path)
    corpus_measurement = inspect_s5_development_corpus(
        training_corpus_path
    )
    failures: list[str] = []
    if static_boundary["status"] != "PASS":
        failures.append("S5_STATIC_RUNTIME_BOUNDARY_FAILED")
    if policy_artifact["status"] != "PASS":
        failures.append("S5_POLICY_ARTIFACT_BOUNDARY_FAILED")
    expected_compilation: Mapping[str, object] = {
        "teacher_forced_error_count": 0,
        "quantized_teacher_forced_error_count": 0,
        "runtime_artifact_contains_training_examples": False,
        "runtime_artifact_contains_render_hash_lookup": False,
        "runtime_artifact_contains_action_sequence": False,
        "runtime_artifact_contains_literal_coordinate_table": False,
        "runtime_routes_by_task_game_level_identity": False,
        "runtime_routes_by_observable_action_surface": True,
    }
    for key, expected in expected_compilation.items():
        if compilation.get(key) != expected:
            failures.append(f"S5_COMPILATION_CLAIM_INVALID:{key}")
    if compilation.get("runtime_policy_digest") != policy_artifact.get(
        "policy_digest"
    ):
        failures.append("S5_COMPILATION_POLICY_DIGEST_MISMATCH")
    closure_expectations: Mapping[str, object] = {
        "all_complete": True,
        "complete_inventory": True,
        "environment_count": 25,
        "completed_environment_count": 25,
        "completed_levels": 183,
        "deterministic_seed": 0,
        "error_count": 0,
        "hds_stage_decision": "PASS",
        "next_stage_authorized": True,
        "runtime_student": True,
        "operation_mode": "offline",
    }
    for key, expected in closure_expectations.items():
        if closure.get(key) != expected:
            failures.append(f"S5_CLOSURE_INVALID:{key}")
    for key in _EXPECTED_CLOSURE_FALSE_CLAIMS:
        if closure.get(key) is not False:
            failures.append(f"S5_CLOSURE_BOUNDARY_CLAIM_INVALID:{key}")
    action_count = int(closure.get("actions_executed", -1))
    if closure.get("hds_compute_command_count") != action_count:
        failures.append("S5_HDS_COMMAND_ACCOUNTING_INVALID")
    if (
        int(closure.get("normal_external_emit_count", -1))
        + int(closure.get("policy_reset_count", -1))
        != action_count
    ):
        failures.append("S5_EXTERNAL_EFFECT_ACCOUNTING_INVALID")
    if closure.get("game_over_observation_count") != closure.get(
        "outcome_retention_count"
    ):
        failures.append("S5_GAME_OVER_RETENTION_ACCOUNTING_INVALID")
    if int(closure.get("memory_influenced_decision_count", 0)) <= 0:
        failures.append("S5_MEMORY_CAUSAL_USE_NOT_OBSERVED")
    if int(closure.get("pointer_payload_generated_count", 0)) <= 0:
        failures.append("S5_POINTER_GENERATION_NOT_OBSERVED")

    status = "PASS" if not failures else "FAIL"
    body: dict[str, Any] = {
        "schema_version": S5_RUNTIME_AUDIT_SCHEMA_VERSION,
        "phase": "P10-R5-S5-RENDERED-ONLY-RUNTIME-AUDIT",
        "status": status,
        "hds_decision": (
            "PASS_S5_SAME_SAMPLE_HOLD_S6_GENERALIZATION"
            if status == "PASS"
            else "HOLD_S5"
        ),
        "failures": sorted(set(failures)),
        "runtime_policy_digest": policy_artifact.get("policy_digest"),
        "policy_compilation_report_digest": compilation.get(
            "content_digest"
        ),
        "closure_report_digest": closure.get("content_digest"),
        "static_runtime_boundary": static_boundary,
        "runtime_policy_artifact": policy_artifact,
        "execution_accounting": {
            "environment_count": closure.get("environment_count"),
            "completed_levels": closure.get("completed_levels"),
            "actions_executed": closure.get("actions_executed"),
            "hds_compute_command_count": closure.get(
                "hds_compute_command_count"
            ),
            "normal_external_emit_count": closure.get(
                "normal_external_emit_count"
            ),
            "policy_reset_count": closure.get("policy_reset_count"),
            "game_over_observation_count": closure.get(
                "game_over_observation_count"
            ),
            "outcome_retention_count": closure.get(
                "outcome_retention_count"
            ),
            "memory_influenced_decision_count": closure.get(
                "memory_influenced_decision_count"
            ),
        },
        "development_corpus_measurement": corpus_measurement,
        "claim_boundary": {
            "same_sample_rendered_only_closure": (
                "PASS" if status == "PASS" else "NOT_PROVEN"
            ),
            "task_game_level_identity_free_by_runtime_interface": (
                "PASS" if status == "PASS" else "NOT_PROVEN"
            ),
            "generalization": "NOT_MEASURED",
            "s6_authorized": status == "PASS",
            "s6_complete": False,
        },
    }
    return {
        **body,
        "content_digest": (
            S5_RUNTIME_AUDIT_DIGEST_PREFIX + digest_object(body)
        ),
    }


def _parser() -> argparse.ArgumentParser:
    package_dir = Path(__file__).resolve().parents[1]
    parser = argparse.ArgumentParser(
        description="Audit S5 Runtime P and HDS execution evidence."
    )
    parser.add_argument("--package-dir", type=Path, default=package_dir)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--weights", type=Path, required=True)
    parser.add_argument(
        "--policy-compilation-report",
        type=Path,
        required=True,
    )
    parser.add_argument("--closure-report", type=Path, required=True)
    parser.add_argument("--training-corpus", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    return parser


def main() -> int:
    args = _parser().parse_args()
    report = audit_s5_runtime(
        package_dir=args.package_dir,
        manifest_path=args.manifest,
        weights_path=args.weights,
        policy_compilation_report_path=args.policy_compilation_report,
        closure_report_path=args.closure_report,
        training_corpus_path=args.training_corpus,
    )
    _write_json(args.output, report)
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "status": report["status"],
                "hds_decision": report["hds_decision"],
                "failure_count": len(report["failures"]),
                "content_digest": report["content_digest"],
            },
            sort_keys=True,
        )
    )
    return int(report["status"] != "PASS")


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "S5_RUNTIME_AUDIT_SCHEMA_VERSION",
    "audit_s5_runtime",
    "inspect_s5_development_corpus",
    "inspect_s5_policy_artifact",
    "inspect_s5_runtime_boundary",
]
