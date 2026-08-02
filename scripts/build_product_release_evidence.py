#!/usr/bin/env python3
"""Build fail-closed local release evidence for ARC3CompletionAgent v1.0."""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Sequence

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_M4_EVIDENCE = Path("analysis/product/rev4/m4_full_sample_product.json")
DEFAULT_M5_EVIDENCE = Path("analysis/product/rev4/m5_clean_install_product.json")
DEFAULT_RELEASE_DIR = Path("release/ARC3CompletionAgent-v1.0")
DEFAULT_NOTEBOOK_VALIDATION = Path("analysis/official/KAGGLE_NOTEBOOK_VALIDATION.json")
DEFAULT_OUTPUT = Path("analysis/product/rev4/m5_product_release.json")
WHEEL_FILENAME = "arc3_completion_agent-1.0.0-py3-none-any.whl"


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _load_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"ARC3_RELEASE_EVIDENCE_OBJECT_REQUIRED:{path}")
    return value


def _verify_run_evidence(value: dict[str, object], expected_stage: str) -> None:
    body = dict(value)
    claimed = body.pop("content_digest", None)
    expected = "arc3-product-run-evidence:" + _sha256(
        _canonical_json(body).encode("utf-8")
    )
    if claimed != expected:
        raise RuntimeError("ARC3_RELEASE_RUN_EVIDENCE_DIGEST_MISMATCH")
    required: dict[str, object] = {
        "evidence_stage": expected_stage,
        "product_status": "COMPLETE",
        "product_completion_established": True,
        "product_endpoint_failure_count": 0,
        "product_game_win_count": 25,
        "product_level_completion_count": 183,
        "product_total_action_count": 10733,
        "product_plan_integrity_row_count": 25,
        "product_runtime_failure_signature_row_count": 0,
        "product_executed_plan_count": 10733,
        "product_hds_plan_commit_count": 10733,
        "product_initial_plan_count": 25,
        "product_max_plan_step_count": 4,
        "product_failure_attribution_count": 12,
        "product_rollback_plan_count": 42,
        "product_post_rollback_replan_count": 42,
        "per_game_reference_exact": True,
        "identity_boundary": "PASS",
        "runtime_policy_changed": False,
        "scorecard_closed": True,
        "shared_session_count": 1,
        "state_owner_violation_count": 0,
    }
    failures = [
        key
        for key, expected_value in required.items()
        if value.get(key) != expected_value
    ]
    if failures:
        raise RuntimeError(
            "ARC3_RELEASE_RUN_EVIDENCE_CONTRACT_MISMATCH:" + ",".join(failures)
        )


def _functional_rows(value: dict[str, object]) -> tuple[tuple[object, ...], ...]:
    raw_index = value.get("orchestration_game_index")
    raw_results = value.get("results")
    if not isinstance(raw_index, list) or not isinstance(raw_results, list):
        raise TypeError("ARC3_RELEASE_FUNCTIONAL_ROWS_INVALID")
    if len(raw_index) != 25 or len(raw_results) != 25:
        raise ValueError("ARC3_RELEASE_FUNCTIONAL_ROW_COUNT_INVALID")
    rows: list[tuple[object, ...]] = []
    for metadata, result in zip(raw_index, raw_results, strict=True):
        if not isinstance(metadata, dict) or not isinstance(result, dict):
            raise TypeError("ARC3_RELEASE_FUNCTIONAL_ROW_INVALID")
        rows.append(
            (
                metadata.get("game_index"),
                metadata.get("game_id"),
                result.get("actions_executed"),
                result.get("progress_count"),
                result.get("final_state"),
                result.get("stop_reason"),
            )
        )
    return tuple(rows)


def _installed_environment(python: Path) -> dict[str, object]:
    probe_source = (
        "import importlib.metadata as m,json,pathlib,sys;"
        "import arc3_agi_agent;"
        "print(json.dumps({"
        "'distribution':m.version('arc3-completion-agent'),"
        "'arc_agi':m.version('arc-agi'),"
        "'numpy':m.version('numpy'),"
        "'python':sys.version.split()[0],"
        "'module_path':pathlib.Path(arc3_agi_agent.__file__).resolve().as_posix()"
        "},sort_keys=True))"
    )
    probe = subprocess.run(
        [str(python), "-I", "-c", probe_source],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    value = json.loads(probe.stdout)
    if not isinstance(value, dict):
        raise TypeError("ARC3_RELEASE_INSTALL_PROBE_INVALID")
    module_path = str(value.pop("module_path", ""))
    if "site-packages/arc3_agi_agent/__init__.py" not in module_path.casefold():
        raise RuntimeError("ARC3_RELEASE_INSTALL_NOT_FROM_SITE_PACKAGES")
    expected = {
        "distribution": "1.0.0",
        "arc_agi": "0.9.8",
        "numpy": "2.3.2",
    }
    if any(
        value.get(key) != expected_value for key, expected_value in expected.items()
    ):
        raise RuntimeError("ARC3_RELEASE_INSTALL_VERSION_MISMATCH")

    pip_check = subprocess.run(
        [str(python), "-m", "pip", "check"],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    freeze = subprocess.run(
        [str(python), "-m", "pip", "freeze", "--all"],
        check=True,
        capture_output=True,
        text=True,
        timeout=120,
    )
    freeze_lines = tuple(
        sorted(line.strip() for line in freeze.stdout.splitlines() if line.strip())
    )
    return {
        **value,
        "module_origin": "FRESH_VENV_SITE_PACKAGES",
        "pip_check": pip_check.stdout.strip(),
        "dependency_freeze": freeze_lines,
        "dependency_freeze_sha256": _sha256(
            ("\n".join(freeze_lines) + "\n").encode("utf-8")
        ),
    }


def build_release_evidence(
    *,
    implementation_commit: str,
    m4_path: Path,
    m5_path: Path,
    release_dir: Path,
    notebook_validation_path: Path,
    installed_python: Path,
) -> dict[str, object]:
    if len(implementation_commit) != 40 or any(
        char not in "0123456789abcdef" for char in implementation_commit
    ):
        raise ValueError("ARC3_RELEASE_IMPLEMENTATION_COMMIT_INVALID")
    m4 = _load_object(m4_path)
    m5 = _load_object(m5_path)
    _verify_run_evidence(m4, "M4_CANONICAL_FULL_SAMPLE")
    _verify_run_evidence(m5, "M5_CLEAN_INSTALL_FULL_SAMPLE")
    if (
        m4.get("implementation_commit") != implementation_commit
        or m5.get("implementation_commit") != implementation_commit
    ):
        raise RuntimeError("ARC3_RELEASE_IMPLEMENTATION_BINDING_MISMATCH")
    if _functional_rows(m4) != _functional_rows(m5):
        raise RuntimeError("ARC3_RELEASE_CLEAN_INSTALL_FUNCTIONAL_MISMATCH")

    logical_fields = (
        "product_initial_state_logical_digest",
        "product_p_logical_digest",
        "product_p_program_id",
        "product_p_body_format",
        "product_p_body_version",
        "product_p_compiler_mode",
        "product_bundle_j0_digest",
        "product_j0_digest",
        "product_m0_digest",
        "product_m0_record_count",
    )
    if any(m4.get(field) != m5.get(field) for field in logical_fields):
        raise RuntimeError("ARC3_RELEASE_PRODUCT_LOGICAL_IDENTITY_MISMATCH")

    manifest_path = release_dir / "MANIFEST.json"
    wheel_path = release_dir / WHEEL_FILENAME
    sums_path = release_dir / "SHA256SUMS"
    dependency_lock_path = release_dir / "requirements-lock.txt"
    manifest = _load_object(manifest_path)
    wheel_bytes = wheel_path.read_bytes()
    if manifest.get("wheel_sha256") != _sha256(wheel_bytes):
        raise RuntimeError("ARC3_RELEASE_WHEEL_DIGEST_MISMATCH")
    required_manifest: dict[str, object] = {
        "product_id": "ARC3CompletionAgent",
        "product_version": "1.0.0",
        "byte_reproducible": True,
        "teacher_included": False,
        "fixed_action_trajectory_included": False,
        "runtime_identity_routing_included": False,
        "literal_coordinate_table_included": False,
        "compiled_identity_free_product_policy_included": True,
    }
    if any(
        manifest.get(key) != expected_value
        for key, expected_value in required_manifest.items()
    ):
        raise RuntimeError("ARC3_RELEASE_MANIFEST_CONTRACT_MISMATCH")

    notebook = _load_object(notebook_validation_path)
    if (
        notebook.get("status") != "PASS"
        or notebook.get("failed_check_ids") != []
        or notebook.get("tracked_secret_findings") != []
        or notebook.get("notebook_secret_findings") != []
        or notebook.get("submission_api_call_count") != 0
    ):
        raise RuntimeError("ARC3_RELEASE_NOTEBOOK_VALIDATION_FAILURE")
    runtime_archive = notebook.get("runtime_archive")
    if not isinstance(runtime_archive, dict) or runtime_archive.get(
        "archive_sha256"
    ) != manifest.get("runtime_archive_sha256"):
        raise RuntimeError("ARC3_RELEASE_NOTEBOOK_RUNTIME_DIGEST_MISMATCH")

    installed = _installed_environment(installed_python)
    raw_freeze = installed.get("dependency_freeze")
    if not isinstance(raw_freeze, tuple):
        raise TypeError("ARC3_RELEASE_DEPENDENCY_FREEZE_INVALID")
    resolved_dependencies = {
        str(line)
        for line in raw_freeze
        if not str(line).casefold().startswith("arc3-completion-agent @")
        and not str(line).casefold().startswith("pip==")
    }
    locked_dependencies = {
        line.strip()
        for line in dependency_lock_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    }
    if resolved_dependencies != locked_dependencies:
        raise RuntimeError("ARC3_RELEASE_DEPENDENCY_LOCK_MISMATCH")
    evidence: dict[str, object] = {
        "schema_version": "arc3-product-release-evidence-v1",
        "product_id": "ARC3CompletionAgent",
        "product_version": "1.0.0",
        "implementation_commit": implementation_commit,
        "local_release_status": "LOCAL_PRODUCT_CLOSURE_COMPLETE",
        "external_kaggle_normal_run_status": (
            "NOT_EXECUTED_REQUIRES_CURRENT_OWNER_AUTHORIZATION"
        ),
        "product_released": False,
        "m4_evidence_path": m4_path.relative_to(REPOSITORY_ROOT).as_posix(),
        "m4_evidence_sha256": _sha256(m4_path.read_bytes()),
        "m5_clean_evidence_path": m5_path.relative_to(REPOSITORY_ROOT).as_posix(),
        "m5_clean_evidence_sha256": _sha256(m5_path.read_bytes()),
        "clean_install_functional_result_exact": True,
        "product_logical_identity_preserved": True,
        "runtime_identity_scope_difference": (
            "DEVELOPMENT_CHECKOUT_VS_DISTRIBUTION_CLOSURE"
        ),
        "release_manifest_path": manifest_path.relative_to(REPOSITORY_ROOT).as_posix(),
        "release_manifest_sha256": _sha256(manifest_path.read_bytes()),
        "release_sums_path": sums_path.relative_to(REPOSITORY_ROOT).as_posix(),
        "release_sums_sha256": _sha256(sums_path.read_bytes()),
        "dependency_lock_path": dependency_lock_path.relative_to(
            REPOSITORY_ROOT
        ).as_posix(),
        "dependency_lock_sha256": _sha256(dependency_lock_path.read_bytes()),
        "dependency_lock_matches_fresh_install": True,
        "wheel_path": wheel_path.relative_to(REPOSITORY_ROOT).as_posix(),
        "wheel_sha256": manifest["wheel_sha256"],
        "wheel_size_bytes": len(wheel_bytes),
        "wheel_byte_reproducible": True,
        "fresh_install": installed,
        "notebook_validation_path": notebook_validation_path.relative_to(
            REPOSITORY_ROOT
        ).as_posix(),
        "notebook_validation_sha256": _sha256(notebook_validation_path.read_bytes()),
        "notebook_validation_status": "PASS",
        "notebook_submission_api_call_count": 0,
        "notebook_secret_finding_count": 0,
        "local_acceptance_failure_count": 0,
        "remaining_release_gate_count": 1,
        "remaining_release_gates": [
            "EXTERNAL_KAGGLE_NORMAL_RUN_REQUIRES_CURRENT_OWNER_AUTHORIZATION"
        ],
    }
    digest = _sha256(_canonical_json(evidence).encode("utf-8"))
    return {
        **evidence,
        "content_digest": "arc3-product-release-evidence:" + digest,
    }


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--implementation-commit", required=True)
    parser.add_argument("--m4-evidence", type=Path, default=DEFAULT_M4_EVIDENCE)
    parser.add_argument("--m5-evidence", type=Path, default=DEFAULT_M5_EVIDENCE)
    parser.add_argument("--release-dir", type=Path, default=DEFAULT_RELEASE_DIR)
    parser.add_argument(
        "--notebook-validation",
        type=Path,
        default=DEFAULT_NOTEBOOK_VALIDATION,
    )
    parser.add_argument("--installed-python", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    evidence = build_release_evidence(
        implementation_commit=arguments.implementation_commit,
        m4_path=(REPOSITORY_ROOT / arguments.m4_evidence).resolve(),
        m5_path=(REPOSITORY_ROOT / arguments.m5_evidence).resolve(),
        release_dir=(REPOSITORY_ROOT / arguments.release_dir).resolve(),
        notebook_validation_path=(
            REPOSITORY_ROOT / arguments.notebook_validation
        ).resolve(),
        installed_python=arguments.installed_python.resolve(),
    )
    output = (REPOSITORY_ROOT / arguments.output).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(
        json.dumps(
            {
                "content_digest": evidence["content_digest"],
                "local_release_status": evidence["local_release_status"],
                "output": output.as_posix(),
                "remaining_release_gate_count": evidence[
                    "remaining_release_gate_count"
                ],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
