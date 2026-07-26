"""Compile and validate the frozen P11 local release state."""

from __future__ import annotations

import argparse
import dataclasses
import hashlib
import importlib.metadata
import json
import platform
import subprocess
import zipfile
from collections.abc import Mapping
from pathlib import Path
from typing import Any

from ..judgment import HDSFramePolicy
from ..kernel import HDSController
from ..memory import PassiveMemory
from ..s5_authority import (
    HDSOutcomeRetentionController,
    HDSPolicyResetController,
)
from ..s5_policy import load_s5_rendered_policy_body
from ..s5_runner import load_s5_execution_trace_manifest
from ..s5_runtime import S5_MEMORY_HISTORY_SNAPSHOT_LIMIT
from ..schema import digest_object
from .p11_regression import (
    load_p10_reproducibility_audit,
    load_p11_regression_report,
)
from .s6_generalization import load_s6_generalization_report

P11_RELEASE_STATE_SCHEMA_VERSION = "arc3-p11-release-state-v2"
P11_RELEASE_STATE_DIGEST_PREFIX = "arc3_p11_release_state:"
P11_ACTION_BUDGET = 4096
P11_RUNTIME_SEED = 0
P11_SOURCE_DATE_EPOCH = 946_684_800
P11_BUILD_BACKEND_VERSION = "83.0.0"
P11_UV_VERSION = "0.11.32"


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


def _json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise TypeError(f"JSON_OBJECT_REQUIRED:{path.name}")
    return dict(value)


def _without_digest(value: Mapping[str, Any]) -> dict[str, Any]:
    body = dict(value)
    body.pop("content_digest", None)
    return body


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_digest_report(
    path: Path,
    *,
    digest_prefix: str,
) -> dict[str, Any]:
    report = _json_object(path)
    if report.get("content_digest") != (
        digest_prefix + digest_object(_without_digest(report))
    ):
        raise ValueError(f"REPORT_CONTENT_DIGEST_INVALID:{path.name}")
    return report


def _git(repository_root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ("git", *arguments),
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode:
        raise RuntimeError(
            "GIT_COMMAND_FAILED:"
            + ":".join(arguments)
            + ":"
            + completed.stderr.strip()[-500:]
        )
    return completed.stdout.strip()


def _git_tree_inventory(
    repository_root: Path,
    code_commit: str,
    pathspec: str,
) -> dict[str, object]:
    output = _git(
        repository_root,
        "ls-tree",
        "-r",
        "--full-tree",
        code_commit,
        pathspec,
    )
    lines = tuple(line for line in output.splitlines() if line)
    if not lines:
        raise ValueError(f"P11_GIT_TREE_INVENTORY_EMPTY:{pathspec}")
    return {
        "pathspec": pathspec,
        "tracked_file_count": len(lines),
        "git_tree_inventory_sha256": hashlib.sha256(
            ("\n".join(lines) + "\n").encode("utf-8")
        ).hexdigest(),
    }


def p11_initial_state_descriptors() -> dict[str, Any]:
    """Materialize fresh P0/J0/M0 and return only immutable descriptors."""

    policy = load_s5_rendered_policy_body()
    frame_policy = HDSFramePolicy()
    hds = HDSController(frame_policy=frame_policy)
    retention = HDSOutcomeRetentionController()
    reset = HDSPolicyResetController()
    memory = PassiveMemory(
        max_entries=1,
        max_history_snapshots=S5_MEMORY_HISTORY_SNAPSHOT_LIMIT,
    )
    memory_snapshot = memory.view()
    j0_counts = {
        "issued_compute_command_count": len(hds._issued),
        "owned_compute_command_count": len(hds._commands),
        "retained_compute_binding_count": (
            hds.retained_compute_binding_count
        ),
        "decision_count": len(hds._decisions),
        "memory_directive_count": len(hds._memory_directives),
        "emission_directive_count": len(hds._emission_directives),
        "observed_emission_count": len(hds._observed_emissions),
        "outcome_retention_decision_count": len(
            retention._decisions
        ),
        "outcome_retention_directive_count": len(
            retention._directives
        ),
        "policy_reset_decision_count": len(reset._decisions),
        "policy_reset_directive_count": len(reset._directives),
        "counter": hds._counter,
    }
    if any(j0_counts.values()):
        raise RuntimeError("P11_J0_NOT_EMPTY")
    p0_body: dict[str, Any] = {
        "format_id": policy.format_id,
        "body_version": policy.body_version,
        "content_digest": policy.digest(),
        "provenance_digest": policy.provenance_digest,
        "parameter_count": policy.parameter_count,
        "parameter_dtype": policy._manifest.get("parameter_dtype"),
        "runtime_inputs": policy._manifest.get("runtime_inputs"),
        "runtime_identity_free": policy._manifest.get(
            "runtime_identity_free"
        ),
        "runtime_artifact_contains_training_examples": (
            policy._manifest.get(
                "runtime_artifact_contains_training_examples"
            )
        ),
        "weights_sha256": policy._weights_sha256,
    }
    j0_body: dict[str, Any] = {
        "frame_policy": dataclasses.asdict(frame_policy),
        "frame_policy_digest": frame_policy.digest,
        "controller_type": type(hds).__name__,
        "judgment_subject_type": type(hds.judgment_subject).__name__,
        "outcome_retention_controller_type": type(retention).__name__,
        "policy_reset_controller_type": type(reset).__name__,
        "initial_counts": j0_counts,
        "rollback_conditions": (
            "hazard-or-closure-rejection",
            "authorized-GAME_OVER-recovery",
            "rendered-policy-compatibility-reset",
        ),
        "authority": (
            "HDS alone commands, judges, stops, authorizes memory, "
            "authorizes reset, and authorizes external emission."
        ),
    }
    m0_body: dict[str, Any] = {
        "memory_type": type(memory).__name__,
        "version": memory_snapshot.version,
        "max_entries": memory.max_entries,
        "max_history_snapshots": memory.max_history_snapshots,
        "active_entry_count": len(memory_snapshot.entries),
        "archive_entry_count": len(memory_snapshot.archive_entries),
        "provenance_event_count": len(memory.provenance()),
        "retained_snapshot_versions": list(
            memory.retained_snapshot_versions
        ),
        "snapshot_digest": memory_snapshot.digest,
        "runtime_identity_free": True,
    }
    if (
        m0_body["version"] != 0
        or m0_body["active_entry_count"] != 0
        or m0_body["archive_entry_count"] != 0
        or m0_body["provenance_event_count"] != 0
    ):
        raise RuntimeError("P11_M0_NOT_EMPTY")
    return {
        "P0": {
            **p0_body,
            "initial_state_digest": digest_object(p0_body),
        },
        "J0": {
            **j0_body,
            "initial_state_digest": digest_object(j0_body),
        },
        "M0": {
            **m0_body,
            "initial_state_digest": digest_object(m0_body),
        },
    }


def inspect_reproducible_wheels(
    primary_path: Path,
    reproduction_path: Path,
) -> dict[str, Any]:
    primary_bytes = primary_path.read_bytes()
    reproduction_bytes = reproduction_path.read_bytes()
    if primary_bytes != reproduction_bytes:
        raise ValueError("P11_PACKAGE_BYTE_MISMATCH")
    with zipfile.ZipFile(primary_path) as archive:
        names = tuple(sorted(archive.namelist()))
        wheel_metadata_names = tuple(
            name
            for name in names
            if name.endswith(".dist-info/WHEEL")
        )
        if len(wheel_metadata_names) != 1:
            raise ValueError("P11_PACKAGE_WHEEL_METADATA_INVALID")
        wheel_metadata = archive.read(
            wheel_metadata_names[0]
        ).decode("utf-8")
    generator = next(
        (
            line.removeprefix("Generator: ").strip()
            for line in wheel_metadata.splitlines()
            if line.startswith("Generator: ")
        ),
        "",
    )
    expected_generator = (
        f"setuptools ({P11_BUILD_BACKEND_VERSION})"
    )
    if generator != expected_generator:
        raise ValueError("P11_PACKAGE_BUILD_BACKEND_VERSION_MISMATCH")
    required_suffixes = (
        "arc3_agi_agent/bundles/s5_rendered_policy_v1.json",
        "arc3_agi_agent/bundles/s5_rendered_policy_v1.npz",
    )
    missing = [
        suffix
        for suffix in required_suffixes
        if not any(name.endswith(suffix) for name in names)
    ]
    if missing:
        raise ValueError(
            "P11_PACKAGE_RUNTIME_BUNDLE_MISSING:" + ",".join(missing)
        )
    forbidden = [
        name
        for name in names
        if (
            name.startswith("analysis/")
            or name.startswith("environment_files/")
            or "S5_RENDERED_POLICY_TRAINING_CORPUS" in name
        )
    ]
    if forbidden:
        raise ValueError("P11_PACKAGE_DEVELOPMENT_CORPUS_LEAK")
    wheel_sha256 = hashlib.sha256(primary_bytes).hexdigest()
    return {
        "filename": primary_path.name,
        "sha256": wheel_sha256,
        "size_bytes": len(primary_bytes),
        "byte_reproducible": True,
        "reproduction_sha256": hashlib.sha256(
            reproduction_bytes
        ).hexdigest(),
        "archive_entry_count": len(names),
        "archive_entry_inventory_digest": digest_object(names),
        "contains_runtime_policy_manifest": True,
        "contains_runtime_policy_weights": True,
        "contains_training_corpus": False,
        "contains_analysis_artifacts": False,
        "contains_environment_sources": False,
        "development_compiler_modules_included": any(
            "/teacher/" in name for name in names
        ),
        "build_contract": {
            "backend": "setuptools.build_meta",
            "backend_generator": generator,
            "backend_version": P11_BUILD_BACKEND_VERSION,
            "command_wsl_windows_interop": (
                "SOURCE_DATE_EPOCH=946684800 "
                "WSLENV=SOURCE_DATE_EPOCH "
                "uv.exe build --wheel --out-dir <output>"
            ),
            "source_date_epoch": P11_SOURCE_DATE_EPOCH,
            "wsl_environment_bridge_required": True,
        },
    }


def _uv_descriptor(uv_executable_path: Path) -> dict[str, object]:
    resolved = uv_executable_path.resolve()
    if not resolved.is_file():
        raise ValueError("P11_UV_EXECUTABLE_MISSING")
    completed = subprocess.run(
        (str(resolved), "--version"),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    reported = completed.stdout.strip()
    parts = reported.split()
    if (
        completed.returncode != 0
        or len(parts) < 2
        or parts[0] != "uv"
        or parts[1] != P11_UV_VERSION
    ):
        raise ValueError("P11_UV_VERSION_MISMATCH")
    return {
        "filename": resolved.name,
        "reported_version": reported,
        "sha256": _file_sha256(resolved),
        "version": P11_UV_VERSION,
    }


def _artifact_descriptor(
    path: Path,
    report: Mapping[str, Any],
) -> dict[str, object]:
    return {
        "filename": path.name,
        "file_sha256": _file_sha256(path),
        "content_digest": report.get("content_digest"),
    }


def compile_p11_release_state(
    *,
    repository_root: Path,
    regression_report_path: Path,
    reproducibility_audit_path: Path,
    primary_wheel_path: Path,
    reproduction_wheel_path: Path,
    uv_executable_path: Path,
    sample_zip_path: Path,
) -> dict[str, Any]:
    """Compile a content-addressed release state from the frozen code tree."""

    repository_root = repository_root.resolve()
    package_root = repository_root / "ARC-AGI-3-Agents"
    analysis_root = repository_root / "analysis"
    teacher_root = analysis_root / "teacher"
    runtime_root = analysis_root / "runtime"
    regression = load_p11_regression_report(regression_report_path)
    reproducibility = load_p10_reproducibility_audit(
        reproducibility_audit_path
    )
    current_commit = _git(repository_root, "rev-parse", "HEAD")
    current_tree = _git(repository_root, "rev-parse", "HEAD^{tree}")
    if (
        regression.get("code_commit") != current_commit
        or regression.get("code_tree") != current_tree
    ):
        raise ValueError("P11_RELEASE_CODE_STATE_MISMATCH")
    if regression.get("branch") != "main":
        raise ValueError("P11_RELEASE_MAIN_BRANCH_REQUIRED")
    if platform.python_version() != "3.12.13":
        raise ValueError("P11_RELEASE_PYTHON_VERSION_MISMATCH")

    closure_path = runtime_root / "S5_RENDERED_ONLY_CLOSURE_REPORT.json"
    closure = _load_digest_report(
        closure_path,
        digest_prefix="arc3_s5_rendered_runtime_closure:",
    )
    full_trace_manifest_path = (
        runtime_root / "S5_FULL_EXECUTION_TRACE_MANIFEST.json"
    )
    full_trace = load_s5_execution_trace_manifest(
        full_trace_manifest_path,
        closure_path=closure_path,
    )
    full_trace_path = (
        full_trace_manifest_path.parent
        / str(full_trace["trace_filename"])
    )
    boundary_audit_path = (
        runtime_root / "S5_SHORTCUT_AND_AUTHORITY_AUDIT.json"
    )
    boundary_audit = _load_digest_report(
        boundary_audit_path,
        digest_prefix="arc3_s5_runtime_boundary_audit:",
    )
    s6_path = runtime_root / "S6_PERTURBATION_MEASUREMENT.json"
    s6 = load_s6_generalization_report(s6_path)
    matrix_path = teacher_root / "PRIVILEGE_SUBTRACTION_MATRIX.json"
    matrix = _load_digest_report(
        matrix_path,
        digest_prefix="arc3_privilege_subtraction_matrix:",
    )
    runtime_p_path = teacher_root / "RUNTIME_P_COMPILATION_REPORT.json"
    runtime_p = _load_digest_report(
        runtime_p_path,
        digest_prefix="arc3_runtime_p_compilation_report:",
    )
    compiler_report_path = (
        teacher_root / "S5_RUNTIME_P_COMPILATION_REPORT.json"
    )
    compiler_report = _load_digest_report(
        compiler_report_path,
        digest_prefix="arc3_s5_runtime_policy_compilation:",
    )
    corpus_manifest_path = (
        teacher_root / "S5_RENDERED_POLICY_TRAINING_CORPUS.json"
    )
    corpus_manifest = _load_digest_report(
        corpus_manifest_path,
        digest_prefix="arc3_s5_training_corpus:",
    )
    corpus_path = (
        teacher_root / "S5_RENDERED_POLICY_TRAINING_CORPUS.npz"
    )
    if corpus_manifest.get("corpus_sha256") != _file_sha256(corpus_path):
        raise ValueError("P11_RELEASE_CORPUS_DIGEST_MISMATCH")
    oracle_path = runtime_root / "S5_LOCAL_SCORE_ORACLE.json"
    oracle = _json_object(oracle_path)
    current_oracle = oracle.get("current_local_result")
    if not isinstance(current_oracle, Mapping):
        raise TypeError("P11_RELEASE_LOCAL_ORACLE_RESULT_INVALID")
    if (
        current_oracle.get("completed_levels") != 183
        or current_oracle.get("completion_rate_percent") != 100.0
        or current_oracle.get("error_count") != 0
    ):
        raise ValueError("P11_RELEASE_LOCAL_ORACLE_NOT_CLOSED")
    if (
        closure.get("all_complete") is not True
        or closure.get("completed_levels") != 183
        or closure.get("error_count") != 0
        or closure.get("deterministic_seed") != P11_RUNTIME_SEED
        or full_trace.get("record_count")
        != closure.get("actions_executed")
        or full_trace.get("complete_execution_trace_coverage")
        is not True
        or reproducibility.get("evidence", {})
        .get("S5_FULL_EXECUTION_TRACE", {})
        .get("content_digest")
        != full_trace.get("content_digest")
        or boundary_audit.get("status") != "PASS"
        or matrix.get("stage_summary", {}).get("S5", {}).get("status")
        != "PASS"
        or matrix.get("stage_summary", {}).get("S6", {}).get("status")
        != "MEASURED"
        or runtime_p.get("claims", {}).get("generalization")
        != "MEASURED_NOT_PROVEN"
    ):
        raise ValueError("P11_RELEASE_P10_EVIDENCE_NOT_CLOSED")

    p9_path = (
        repository_root
        / "certificates"
        / "p9"
        / "agi_minimum_three_certificate.json"
    )
    p9 = _json_object(p9_path)
    if (
        p9.get("full_set_pass") is not True
        or p9.get("proper_subset_fail_count") != 7
        or p9.get("functional_equivalent_leak_count") != 0
    ):
        raise ValueError("P11_RELEASE_P9_CERTIFICATE_INVALID")
    dataset_manifest_path = repository_root / "manifests" / "dataset_manifest.json"
    dataset_manifest = _json_object(dataset_manifest_path)
    identity_audit_path = (
        repository_root / "manifests" / "identity_free_audit.json"
    )
    identity_audit = _json_object(identity_audit_path)
    if (
        dataset_manifest.get("runtime_identity_free") is not True
        or identity_audit.get("runtime_identity_free") is not True
        or identity_audit.get("forbidden_path_count") != 0
    ):
        raise ValueError("P11_RELEASE_DATASET_IDENTITY_AUDIT_INVALID")

    initial_states = p11_initial_state_descriptors()
    wheels = inspect_reproducible_wheels(
        primary_wheel_path,
        reproduction_wheel_path,
    )
    uv_descriptor = _uv_descriptor(uv_executable_path)
    sample_zip_sha256 = _file_sha256(sample_zip_path)
    if not sample_zip_sha256:
        raise ValueError("P11_RELEASE_SAMPLE_ZIP_DIGEST_MISSING")
    pyproject_path = package_root / "pyproject.toml"
    uv_lock_path = package_root / "uv.lock"
    python_version_path = package_root / ".python-version"
    if python_version_path.read_text(encoding="utf-8").strip() != "3.12.13":
        raise ValueError("P11_RELEASE_PYTHON_PIN_INVALID")
    if regression.get("uv_lock_sha256") != _file_sha256(uv_lock_path):
        raise ValueError("P11_RELEASE_LOCK_CHANGED_AFTER_REGRESSION")
    compiler_paths = (
        package_root
        / "arc3_agi_agent"
        / "s5_runner.py",
        package_root
        / "arc3_agi_agent"
        / "teacher"
        / "s5_training_corpus.py",
        package_root
        / "arc3_agi_agent"
        / "teacher"
        / "s5_policy_compiler.py",
        package_root
        / "arc3_agi_agent"
        / "teacher"
        / "solution_graph_compiler.py",
        package_root
        / "arc3_agi_agent"
        / "teacher"
        / "s6_generalization.py",
        package_root
        / "arc3_agi_agent"
        / "teacher"
        / "p11_regression.py",
        package_root
        / "arc3_agi_agent"
        / "teacher"
        / "p11_release.py",
    )
    compiler_inventory = {
        str(path.relative_to(repository_root)).replace("\\", "/"): (
            _file_sha256(path)
        )
        for path in compiler_paths
    }
    body: dict[str, Any] = {
        "schema_version": P11_RELEASE_STATE_SCHEMA_VERSION,
        "phase": "P11-RELEASE-STATE-FREEZE",
        "status": "P11_RELEASE_STATE_FIXED",
        "operation_mode": "offline",
        "official_connection_executed": False,
        "competition_mode_executed": False,
        "kaggle_work_executed": False,
        "code": {
            "commit": current_commit,
            "tree": current_tree,
            "branch": "main",
        },
        "dependency": {
            "python_version": platform.python_version(),
            "python_version_file": "3.12.13",
            "pyproject_sha256": _file_sha256(pyproject_path),
            "uv_lock_sha256": _file_sha256(uv_lock_path),
            "arc_agi_version": importlib.metadata.version("arc-agi"),
            "numpy_version": importlib.metadata.version("numpy"),
            "scikit_learn_version": importlib.metadata.version(
                "scikit-learn"
            ),
            "pytest_version": importlib.metadata.version("pytest"),
            "mypy_version": importlib.metadata.version("mypy"),
            "ruff_version": importlib.metadata.version("ruff"),
            "uv": uv_descriptor,
        },
        "initial_state": initial_states,
        "dataset": {
            "p3_dataset_manifest_sha256": _file_sha256(
                dataset_manifest_path
            ),
            "p3_dataset_schema_version": dataset_manifest.get(
                "schema_version"
            ),
            "p3_runtime_record_count": dataset_manifest.get(
                "runtime_record_count"
            ),
            "p3_identity_free_audit_sha256": _file_sha256(
                identity_audit_path
            ),
            "s5_training_manifest_digest": corpus_manifest.get(
                "content_digest"
            ),
            "s5_training_manifest_sha256": _file_sha256(
                corpus_manifest_path
            ),
            "s5_training_corpus_sha256": _file_sha256(corpus_path),
            "s5_training_record_count": corpus_manifest.get(
                "record_count"
            ),
            "runtime_use_of_s5_training_corpus": "FORBIDDEN",
        },
        "compiler": {
            "source_sha256": compiler_inventory,
            "source_inventory_digest": digest_object(
                compiler_inventory
            ),
            "s5_compilation_report_digest": compiler_report.get(
                "content_digest"
            ),
            "s5_policy_parameter_count": compiler_report.get(
                "parameter_count"
            ),
            "s5_teacher_forced_error_count": compiler_report.get(
                "teacher_forced_error_count"
            ),
            "s5_quantized_teacher_forced_error_count": (
                compiler_report.get(
                    "quantized_teacher_forced_error_count"
                )
            ),
        },
        "determinism": {
            "runtime_seed": P11_RUNTIME_SEED,
            "python_hash_seed": 0,
            "s5_action_head_random_states": list(range(10)),
            "s5_pointer_head_random_states": {
                "horizontal": 41,
                "vertical": 43,
            },
            "s6_selection_algorithm": s6.get(
                "selection_algorithm"
            ),
            "s6_selection_digest": s6.get("selection_digest"),
            "source_date_epoch": P11_SOURCE_DATE_EPOCH,
            "action_budget": P11_ACTION_BUDGET,
        },
        "environment": {
            "sample_zip_filename": sample_zip_path.name,
            "sample_zip_sha256": sample_zip_sha256,
            "git_inventory": _git_tree_inventory(
                repository_root,
                current_commit,
                "environment_files",
            ),
            "expected_game_count": 25,
            "expected_level_count": 183,
            "toolkit_operation_mode": "OFFLINE",
        },
        "regression": {
            "report_digest": regression.get("content_digest"),
            "report_sha256": _file_sha256(regression_report_path),
            "validation_count": regression.get("validation_count"),
            "passed_validation_count": regression.get(
                "passed_validation_count"
            ),
            "tracked_secret_scan": regression.get(
                "tracked_secret_scan"
            ),
        },
        "package": wheels,
        "evidence": {
            "p9_minimum_three_certificate": {
                "file_sha256": _file_sha256(p9_path),
                "content_digest": p9.get("content_digest"),
            },
            "p10_reproducibility": _artifact_descriptor(
                reproducibility_audit_path,
                reproducibility,
            ),
            "s5_rendered_only_closure": _artifact_descriptor(
                closure_path,
                closure,
            ),
            "s5_full_execution_trace": {
                **_artifact_descriptor(
                    full_trace_manifest_path,
                    full_trace,
                ),
                "trace_filename": full_trace_path.name,
                "trace_file_sha256": _file_sha256(full_trace_path),
                "record_count": full_trace.get("record_count"),
                "complete_execution_trace_coverage": (
                    full_trace.get(
                        "complete_execution_trace_coverage"
                    )
                ),
            },
            "s5_boundary_audit": _artifact_descriptor(
                boundary_audit_path,
                boundary_audit,
            ),
            "s5_local_score_oracle": {
                "filename": oracle_path.name,
                "file_sha256": _file_sha256(oracle_path),
                "score_digest": oracle.get("score_digest"),
                "completed_levels": current_oracle.get(
                    "completed_levels"
                ),
                "completion_percentage": current_oracle.get(
                    "completion_rate_percent"
                ),
                "rhae_percentage": current_oracle.get(
                    "official_rhae_score_percent"
                ),
            },
            "s6_generalization_measurement": _artifact_descriptor(
                s6_path,
                s6,
            ),
            "privilege_subtraction_matrix": _artifact_descriptor(
                matrix_path,
                matrix,
            ),
            "runtime_p_compilation": _artifact_descriptor(
                runtime_p_path,
                runtime_p,
            ),
        },
        "claims": {
            "minimum_three_conformance": "SUPPORTED",
            "P0_fixed": "SUPPORTED",
            "J0_fixed": "SUPPORTED",
            "M0_fixed": "SUPPORTED",
            "sample_completion_183": "SUPPORTED",
            "all_execution_traces_persisted": "SUPPORTED",
            "same_condition_reproducibility": "SUPPORTED",
            "release_package_reproducibility": "SUPPORTED",
            "generalization": "MEASURED_NOT_PROVEN",
            "official_environment_readiness": "NOT_EVALUATED",
        },
        "next_phase": {
            "phase": "P12",
            "status": "NOT_STARTED_CURRENT_REQUEST_OUT_OF_SCOPE",
        },
    }
    return {
        **body,
        "content_digest": (
            P11_RELEASE_STATE_DIGEST_PREFIX + digest_object(body)
        ),
    }


def load_p11_release_state(path: Path) -> dict[str, Any]:
    report = _load_digest_report(
        path,
        digest_prefix=P11_RELEASE_STATE_DIGEST_PREFIX,
    )
    if (
        report.get("schema_version")
        != P11_RELEASE_STATE_SCHEMA_VERSION
        or report.get("status") != "P11_RELEASE_STATE_FIXED"
        or report.get("operation_mode") != "offline"
        or report.get("official_connection_executed") is not False
        or report.get("competition_mode_executed") is not False
        or report.get("kaggle_work_executed") is not False
        or report.get("claims", {}).get("sample_completion_183")
        != "SUPPORTED"
        or report.get("claims", {}).get(
            "all_execution_traces_persisted"
        )
        != "SUPPORTED"
        or report.get("claims", {}).get("generalization")
        != "MEASURED_NOT_PROVEN"
    ):
        raise ValueError("P11_RELEASE_STATE_INVALID")
    return report


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Freeze the local P11 release state."
    )
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument(
        "--regression-report",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--reproducibility-audit",
        type=Path,
        required=True,
    )
    parser.add_argument("--primary-wheel", type=Path, required=True)
    parser.add_argument(
        "--reproduction-wheel",
        type=Path,
        required=True,
    )
    parser.add_argument(
        "--uv-executable",
        type=Path,
        required=True,
    )
    parser.add_argument("--sample-zip", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = compile_p11_release_state(
        repository_root=args.repository_root,
        regression_report_path=args.regression_report,
        reproducibility_audit_path=args.reproducibility_audit,
        primary_wheel_path=args.primary_wheel,
        reproduction_wheel_path=args.reproduction_wheel,
        uv_executable_path=args.uv_executable,
        sample_zip_path=args.sample_zip,
    )
    _write_json(args.output, report)
    load_p11_release_state(args.output)
    print(
        json.dumps(
            {
                "code_commit": report["code"]["commit"],
                "content_digest": report["content_digest"],
                "package_sha256": report["package"]["sha256"],
                "status": report["status"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "P11_ACTION_BUDGET",
    "P11_BUILD_BACKEND_VERSION",
    "P11_RELEASE_STATE_DIGEST_PREFIX",
    "P11_RELEASE_STATE_SCHEMA_VERSION",
    "P11_RUNTIME_SEED",
    "P11_SOURCE_DATE_EPOCH",
    "P11_UV_VERSION",
    "compile_p11_release_state",
    "inspect_reproducible_wheels",
    "load_p11_release_state",
    "p11_initial_state_descriptors",
]
