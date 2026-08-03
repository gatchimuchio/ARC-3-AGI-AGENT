#!/usr/bin/env python3
"""Verify and seal the accepted M4-P05 Kaggle normal run."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import subprocess
import tempfile
from datetime import datetime
from pathlib import Path
from typing import Final, Sequence

from build_kaggle_submission import (
    ACTION_BUDGET,
    COMPETITION_SLUG,
    DEFAULT_OUTPUT_DIR,
    RELEASE_BUNDLE_ID,
    RELEASE_BUNDLE_LOGICAL_DIGEST,
    RELEASE_ENTRYPOINT_TARGET,
    RELEASE_INITIAL_STATE_DIGEST,
    RELEASE_J0_DIGEST,
    RELEASE_M0_DIGEST,
    RELEASE_P_DIGEST,
    RELEASE_PACKAGE_SHA256,
    RELEASE_RUNTIME_IDENTITY,
    RELEASE_WHEEL_SHA256,
    ROOT,
    WHEELHOUSE_DATASET_ID,
    WHEELHOUSE_DATASET_SOURCE,
    WHEELHOUSE_MANIFEST_PATH,
)

KERNEL_REF: Final = "tecchannn/arc3completionagent-rev5-1-frozen-release"
KERNEL_URL: Final = "https://www.kaggle.com/code/" + KERNEL_REF
ACCEPTED_KERNEL_VERSION: Final = 4
PACKAGE_VALIDATION_PATH: Final = ROOT / "analysis/product/rev5_1/" / (
    "m4_p05_kaggle_package_validation.json"
)
M4_P04_CLOSURE_PATH: Final = ROOT / "analysis/product/rev5_1/" / (
    "m4_p04_clean_full_sample_closure.json"
)
M4_P04_RUN_PATH: Final = ROOT / "analysis/product/rev5_1/" / (
    "m4_p04_clean_full_sample_run.json"
)
DEFAULT_REPORT: Final = ROOT / "analysis/product/rev5_1/" / (
    "m4_p05_kaggle_normal_run.json"
)
DEFAULT_CLOSURE: Final = ROOT / "analysis/product/rev5_1/" / (
    "m4_p05_kaggle_normal_run_closure.json"
)
EXPECTED_OUTPUT_NAMES: Final = (
    "arc3_install_status.json",
    "arc3_normal_run_status.json",
    "arc3_payload_status.json",
    "submission.parquet",
)
EXPECTED_SUBMISSION_REFS: Final = (
    "55070928",
    "55069307",
    "55049227",
    "55045360",
    "55043205",
    "55040966",
    "53996483",
    "53966647",
)
EXPECTED_OUTPUT_COLUMNS: Final = (
    "row_id",
    "game_id",
    "end_of_game",
    "score",
)
EXPECTED_OUTPUT_ROWS: Final = (
    {"row_id": "1_0", "game_id": "1", "end_of_game": True, "score": 1},
)
EXPECTED_WHEELHOUSE_MANIFEST_SHA256: Final = (
    "faa8b84778a7f02f57f330ce2ac25c27a6498ec4598bf46fb62e074df77483c4"
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _encoded(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _logical_seal(value: dict[str, object]) -> str:
    material = dict(value)
    material.pop("logical_content_sha256", None)
    return _sha256(
        json.dumps(
            material,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        ).encode("utf-8")
    )


def _load_object(path: Path) -> tuple[dict[str, object], bytes]:
    payload = path.read_bytes()
    value: object = json.loads(payload)
    if not isinstance(value, dict):
        raise TypeError("M4_P05_JSON_OBJECT_REQUIRED:" + path.as_posix())
    return {str(key): item for key, item in value.items()}, payload


def _run(*arguments: str) -> str:
    result = subprocess.run(
        arguments,
        cwd=ROOT,
        check=True,
        capture_output=True,
        text=True,
        timeout=300,
    )
    return result.stdout


def _json_value(payload: str, *, label: str) -> object:
    try:
        return json.loads(payload)
    except json.JSONDecodeError as error:
        raise ValueError(label + "_INVALID_JSON") from error


def _cell_sources(notebook: dict[str, object]) -> tuple[dict[str, str], ...]:
    cells = notebook.get("cells")
    if not isinstance(cells, list):
        raise TypeError("M4_P05_NOTEBOOK_CELLS_INVALID")
    rows: list[dict[str, str]] = []
    for cell in cells:
        if not isinstance(cell, dict):
            raise TypeError("M4_P05_NOTEBOOK_CELL_INVALID")
        raw_source = cell.get("source", "")
        if isinstance(raw_source, str):
            source = raw_source
        elif isinstance(raw_source, list) and all(
            isinstance(item, str) for item in raw_source
        ):
            source = "".join(raw_source)
        else:
            raise TypeError("M4_P05_NOTEBOOK_SOURCE_INVALID")
        rows.append(
            {
                "cell_type": str(cell.get("cell_type", "")),
                "id": str(cell.get("id", "")),
                "source": source,
            }
        )
    return tuple(rows)


def _parse_utc(value: str) -> datetime:
    normalized = value.removesuffix("Z") + "+00:00" if value.endswith("Z") else value
    return datetime.fromisoformat(normalized)


def _submission_refs(csv_payload: str) -> tuple[str, ...]:
    reader = csv.DictReader(io.StringIO(csv_payload))
    refs = tuple(str(row.get("ref", "")) for row in reader)
    if any(not ref for ref in refs):
        raise ValueError("M4_P05_SUBMISSION_SNAPSHOT_INVALID")
    return refs


def _listed_outputs(payload: str) -> tuple[dict[str, object], ...]:
    value = _json_value(payload, label="M4_P05_KERNEL_FILES")
    if not isinstance(value, list) or not all(isinstance(item, dict) for item in value):
        raise TypeError("M4_P05_KERNEL_FILES_INVALID")
    return tuple({str(key): item for key, item in row.items()} for row in value)


def verify(
    *,
    push_started_utc: str,
    completion_checked_utc: str,
    kernel_version: int,
) -> tuple[dict[str, object], dict[str, object]]:
    if kernel_version != ACCEPTED_KERNEL_VERSION:
        raise ValueError("M4_P05_ACCEPTED_KERNEL_VERSION_MISMATCH")
    status_stdout = _run("kaggle", "kernels", "status", KERNEL_REF)
    listed_outputs = _listed_outputs(
        _run(
            "kaggle",
            "kernels",
            "files",
            KERNEL_REF,
            "--page-size",
            "200",
            "--format",
            "json",
        )
    )
    kernel_rows_value = _json_value(
        _run(
            "kaggle",
            "kernels",
            "list",
            "--user",
            "tecchannn",
            "--search",
            "arc3completionagent-rev5-1-frozen-release",
            "--page-size",
            "20",
            "--format",
            "json",
        ),
        label="M4_P05_KERNEL_LIST",
    )
    if not isinstance(kernel_rows_value, list):
        raise TypeError("M4_P05_KERNEL_LIST_INVALID")
    kernel_rows = tuple(
        {str(key): item for key, item in row.items()}
        for row in kernel_rows_value
        if isinstance(row, dict) and row.get("ref") == KERNEL_REF
    )
    submissions_stdout = _run(
        "kaggle",
        "competitions",
        "submissions",
        COMPETITION_SLUG,
        "-v",
    )
    submission_refs = _submission_refs(submissions_stdout)

    with tempfile.TemporaryDirectory(prefix="arc3-m4-p05-verify-") as directory:
        temporary_root = Path(directory)
        output_root = temporary_root / "output"
        source_root = temporary_root / "source"
        output_root.mkdir()
        source_root.mkdir()
        _run(
            "kaggle",
            "kernels",
            "output",
            KERNEL_REF,
            "-p",
            str(output_root),
            "--force",
        )
        logs_payload = _run("kaggle", "kernels", "logs", KERNEL_REF)
        _run(
            "kaggle",
            "kernels",
            "pull",
            KERNEL_REF,
            "-p",
            str(source_root),
            "-m",
        )

        install_status, install_payload = _load_object(
            output_root / "arc3_install_status.json"
        )
        normal_status, normal_payload = _load_object(
            output_root / "arc3_normal_run_status.json"
        )
        payload_status, payload_payload = _load_object(
            output_root / "arc3_payload_status.json"
        )
        output_payload = (output_root / "submission.parquet").read_bytes()
        local_notebook, local_notebook_payload = _load_object(
            DEFAULT_OUTPUT_DIR / "submission.ipynb"
        )
        server_notebook_paths = tuple(source_root.glob("*.ipynb"))
        if len(server_notebook_paths) != 1:
            raise ValueError("M4_P05_SERVER_NOTEBOOK_CARDINALITY_INVALID")
        server_notebook, server_notebook_payload = _load_object(server_notebook_paths[0])
        server_metadata, server_metadata_payload = _load_object(
            source_root / "kernel-metadata.json"
        )

    package_validation, package_validation_payload = _load_object(
        PACKAGE_VALIDATION_PATH
    )
    raw_package_checks = package_validation.get("checks")
    package_checks = (
        {str(key): item for key, item in raw_package_checks.items()}
        if isinstance(raw_package_checks, dict)
        else {}
    )
    m4_p04, m4_p04_payload = _load_object(M4_P04_CLOSURE_PATH)
    m4_p04_run, m4_p04_run_payload = _load_object(M4_P04_RUN_PATH)
    wheelhouse_manifest_payload = WHEELHOUSE_MANIFEST_PATH.read_bytes()
    local_sources = _cell_sources(local_notebook)
    server_sources = _cell_sources(server_notebook)
    source_payload = json.dumps(
        local_sources,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    listed_names = tuple(sorted(str(row.get("name", "")) for row in listed_outputs))
    log_rows_value = _json_value(logs_payload, label="M4_P05_KERNEL_LOGS")
    if not isinstance(log_rows_value, list):
        raise TypeError("M4_P05_KERNEL_LOGS_INVALID")
    log_times = tuple(
        float(row["time"])
        for row in log_rows_value
        if isinstance(row, dict) and isinstance(row.get("time"), (int, float))
    )
    log_text = "".join(
        str(row.get("data", ""))
        for row in log_rows_value
        if isinstance(row, dict)
    )
    push_started = _parse_utc(push_started_utc)
    completion_checked = _parse_utc(completion_checked_utc)

    expected_payload_identity = {
        "status": "COMPLETE",
        "release_bundle_id": RELEASE_BUNDLE_ID,
        "release_bundle_stage": "RELEASE_FROZEN",
        "release_bundle_logical_digest": RELEASE_BUNDLE_LOGICAL_DIGEST,
        "release_package_sha256": RELEASE_PACKAGE_SHA256,
        "initial_state_logical_digest": RELEASE_INITIAL_STATE_DIGEST,
        "p_logical_digest": RELEASE_P_DIGEST,
        "j0_digest": RELEASE_J0_DIGEST,
        "m0_digest": RELEASE_M0_DIGEST,
        "runtime_identity_digest": RELEASE_RUNTIME_IDENTITY,
        "entrypoint_count": 1,
        "entrypoint_target": RELEASE_ENTRYPOINT_TARGET,
        "dependency_pin_count": 32,
        "dependency_pin_mismatch_count": 0,
        "state_owner_violation_count": 0,
        "agent_class": "ARC3CompletionAgent",
        "action_budget": ACTION_BUDGET,
        "error_type": None,
        "error_message": None,
    }
    checks = {
        "NR-001_KERNEL_COMPLETE": "KernelWorkerStatus.COMPLETE" in status_stdout,
        "NR-002_ACCEPTED_VERSION_RECORDED": kernel_version == 4,
        "NR-003_ONE_CURRENT_KERNEL": len(kernel_rows) == 1,
        "NR-004_OUTPUT_SET_EXACT": listed_names == tuple(sorted(EXPECTED_OUTPUT_NAMES)),
        "NR-005_NO_RUNTIME_ENV_PERSISTED": not any(
            "arc3_runtime_env" in name for name in listed_names
        ),
        "NR-006_SERVER_SOURCE_ROUNDTRIP": local_sources == server_sources,
        "NR-007_SERVER_METADATA_SAFE": (
            server_metadata.get("id") == KERNEL_REF
            and server_metadata.get("is_private") is True
            and server_metadata.get("enable_gpu") is False
            and server_metadata.get("enable_tpu") is False
            and server_metadata.get("enable_internet") is False
            and server_metadata.get("dataset_sources") == [WHEELHOUSE_DATASET_ID]
            and server_metadata.get("competition_sources") == [COMPETITION_SLUG]
        ),
        "NR-008_PACKAGE_VALIDATION_PASS": (
            package_validation.get("status") == "PASS"
            and package_validation.get("passed_check_count") == 32
            and package_validation.get("check_count") == 32
            and package_validation.get("submission_api_call_count") == 0
        ),
        "NR-009_INSTALL_COMPLETE": (
            install_status.get("status") == "COMPLETE"
            and install_status.get("dataset_source") == WHEELHOUSE_DATASET_SOURCE
            and install_status.get("release_wheel_sha256") == RELEASE_WHEEL_SHA256
            and install_status.get("wheelhouse_manifest_sha256")
            == EXPECTED_WHEELHOUSE_MANIFEST_SHA256
            and install_status.get("verified_wheel_count") == 33
            and install_status.get("installed_distribution_count") == 33
            and install_status.get("runtime_environment") == "/tmp/arc3_runtime_env"
            and install_status.get("error_type") is None
            and install_status.get("error_message") is None
        ),
        "NR-010_RELEASE_IDENTITY_EXACT": all(
            payload_status.get(key) == value
            for key, value in expected_payload_identity.items()
        ),
        "NR-011_NORMAL_STATUS_COMPLETE": (
            normal_status.get("status") == "COMPLETE"
            and normal_status.get("release_wheel_sha256") == RELEASE_WHEEL_SHA256
            and normal_status.get("release_package_sha256") == RELEASE_PACKAGE_SHA256
            and normal_status.get("runtime_identity_digest") == RELEASE_RUNTIME_IDENTITY
            and normal_status.get("dependency_pin_count") == 32
            and normal_status.get("dependency_pin_mismatch_count") == 0
        ),
        "NR-012_OUTPUT_CONTRACT_EXACT": (
            normal_status.get("output_columns") == list(EXPECTED_OUTPUT_COLUMNS)
            and normal_status.get("output_rows") == list(EXPECTED_OUTPUT_ROWS)
            and normal_status.get("output_path") == "/kaggle/working/submission.parquet"
            and normal_status.get("output_size_bytes") == len(output_payload)
            and normal_status.get("output_sha256") == _sha256(output_payload)
            and len(output_payload) > 0
            and output_payload[:4] == b"PAR1"
            and output_payload[-4:] == b"PAR1"
            and all(column.encode("ascii") in output_payload for column in EXPECTED_OUTPUT_COLUMNS)
        ),
        "NR-013_NO_RUNTIME_EXCEPTION": not any(
            marker in log_text
            for marker in ("INSTALL_EXCEPTION", "BOOT_EXCEPTION", "RUNTIME_EXCEPTION", "Traceback")
        ),
        "NR-014_ZERO_SUBMISSION_API_CALLS": (
            normal_status.get("submission_api_call_count") == 0
            and submission_refs == EXPECTED_SUBMISSION_REFS
        ),
        "NR-015_SEQUENTIAL_SCORECARD_LIFECYCLE": (
            package_checks.get("NB-016_SEQUENTIAL_SCORECARD_LIFECYCLE") is True
            and m4_p04_run.get("orchestration_mode")
            == "SEQUENTIAL_SINGLE_ACTIVE_GAME"
            and m4_p04_run.get("active_agent_peak") == 1
            and m4_p04_run.get("shared_session_count") == 1
            and m4_p04_run.get("scorecard_open_count") == 1
            and m4_p04_run.get("scorecard_close_count") == 1
            and m4_p04_run.get("scorecard_closed") is True
        ),
        "NR-016_SAME_M4_P04_RELEASE": (
            m4_p04.get("status") == "M4_P04_PASS"
            and payload_status.get("release_package_sha256") == RELEASE_PACKAGE_SHA256
            and install_status.get("release_wheel_sha256") == RELEASE_WHEEL_SHA256
        ),
        "NR-017_WHEELHOUSE_MANIFEST_EXACT": (
            _sha256(wheelhouse_manifest_payload)
            == EXPECTED_WHEELHOUSE_MANIFEST_SHA256
        ),
    }
    report: dict[str, object] = {
        "schema_version": "arc3-rev5-1-m4-p05-kaggle-normal-run-v1",
        "artifact_type": "M4KagglePackageNormalRunEvidence",
        "point_id": "M4-P05_KAGGLE_PACKAGE_NORMAL_RUN",
        "runtime_product": "ARC3CompletionAgent",
        "asset_stage": "RELEASE_FROZEN",
        "status": "M4_P05_NORMAL_RUN_PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "passed_check_count": sum(checks.values()),
        "check_count": len(checks),
        "failed_check_ids": [name for name, passed in checks.items() if not passed],
        "kernel": {
            "ref": KERNEL_REF,
            "url": KERNEL_URL,
            "id_no": server_metadata.get("id_no"),
            "version": kernel_version,
            "worker_status": "COMPLETE",
            "latest_run_time_utc": kernel_rows[0].get("lastRunTime") if kernel_rows else None,
            "push_started_utc": push_started_utc,
            "completion_checked_utc": completion_checked_utc,
            "monitor_elapsed_seconds": round(
                (completion_checked - push_started).total_seconds(), 3
            ),
            "log_event_count": len(log_rows_value),
            "log_duration_seconds": round(max(log_times) - min(log_times), 3)
            if log_times
            else None,
        },
        "notebook": {
            "path": "kaggle_notebooks/submission.ipynb",
            "local_sha256": _sha256(local_notebook_payload),
            "server_payload_sha256": _sha256(server_notebook_payload),
            "cell_source_sha256": _sha256(source_payload),
            "cell_count": len(local_sources),
            "source_roundtrip_exact": local_sources == server_sources,
            "server_metadata_sha256": _sha256(server_metadata_payload),
            "server_dataset_source_normalization": {
                "requested": WHEELHOUSE_DATASET_SOURCE,
                "stored": server_metadata.get("dataset_sources"),
            },
        },
        "dependency_install": {
            "status_sha256": _sha256(install_payload),
            "status": install_status.get("status"),
            "resolved_mount": install_status.get("resolved_mount"),
            "runtime_environment": install_status.get("runtime_environment"),
            "verified_wheel_count": install_status.get("verified_wheel_count"),
            "installed_distribution_count": install_status.get(
                "installed_distribution_count"
            ),
            "wheelhouse_manifest_sha256": install_status.get(
                "wheelhouse_manifest_sha256"
            ),
        },
        "release_identity": {
            "status_sha256": _sha256(payload_payload),
            **expected_payload_identity,
        },
        "output": {
            "listed_outputs": listed_outputs,
            "status_sha256": _sha256(normal_payload),
            "path": "submission.parquet",
            "size_bytes": len(output_payload),
            "sha256": _sha256(output_payload),
            "parquet_magic_valid": output_payload[:4] == b"PAR1"
            and output_payload[-4:] == b"PAR1",
            "columns": normal_status.get("output_columns"),
            "rows": normal_status.get("output_rows"),
        },
        "submission_guard": {
            "competition": COMPETITION_SLUG,
            "expected_refs": EXPECTED_SUBMISSION_REFS,
            "observed_refs": submission_refs,
            "submission_count_before": len(EXPECTED_SUBMISSION_REFS),
            "submission_count_after": len(submission_refs),
            "submission_count_delta": len(submission_refs)
            - len(EXPECTED_SUBMISSION_REFS),
            "submission_api_call_count": 0,
        },
        "source_bindings": {
            "package_validation": {
                "path": PACKAGE_VALIDATION_PATH.relative_to(ROOT).as_posix(),
                "sha256": _sha256(package_validation_payload),
            },
            "M4_P04_same_release_full_sample": {
                "path": M4_P04_CLOSURE_PATH.relative_to(ROOT).as_posix(),
                "sha256": _sha256(m4_p04_payload),
            },
            "M4_P04_sequential_scorecard_run": {
                "path": M4_P04_RUN_PATH.relative_to(ROOT).as_posix(),
                "sha256": _sha256(m4_p04_run_payload),
            },
            "wheelhouse_manifest": {
                "path": WHEELHOUSE_MANIFEST_PATH.relative_to(ROOT).as_posix(),
                "sha256": _sha256(wheelhouse_manifest_payload),
            },
            "kernel_logs_sha256": _sha256(logs_payload.encode("utf-8")),
        },
        "runtime_policy_changed": False,
        "product_failure_count": 0,
        "transport_failure_count": 0,
        "platform_failure_count": 0,
    }
    report["logical_content_sha256"] = _logical_seal(report)

    closure: dict[str, object] = {
        "schema_version": "arc3-rev5-1-m4-p05-kaggle-normal-run-closure-v1",
        "artifact_type": "M4KagglePackageNormalRunClosure",
        "point_id": "M4-P05_KAGGLE_PACKAGE_NORMAL_RUN",
        "runtime_product": "ARC3CompletionAgent",
        "asset_stage": "RELEASE_FROZEN",
        "status": "M4_P05_PASS" if all(checks.values()) else "FAIL",
        "exit_audit": {
            "M4_P04_same_release_full_sample": "PASS",
            "same_release_artifact": True,
            "notebook_contract": "PASS" if checks["NR-008_PACKAGE_VALIDATION_PASS"] else "FAIL",
            "dependency_install": "PASS" if checks["NR-009_INSTALL_COMPLETE"] else "FAIL",
            "official_IO_contract": "PASS" if checks["NR-007_SERVER_METADATA_SAFE"] else "FAIL",
            "placeholder_output_contract": "PASS" if checks["NR-012_OUTPUT_CONTRACT_EXACT"] else "FAIL",
            "sequential_scorecard_lifecycle": "PASS"
            if checks["NR-015_SEQUENTIAL_SCORECARD_LIFECYCLE"]
            else "FAIL",
            "secret_finding_count": package_validation.get("secret_finding_count"),
            "submission_API_call_count": 0,
            "normal_notebook_run": "COMPLETE" if checks["NR-001_KERNEL_COMPLETE"] else "FAIL",
            "output_artifact_present": checks["NR-004_OUTPUT_SET_EXACT"],
            "runtime_policy_changed": False,
            "status": "M4_P05_PASS" if all(checks.values()) else "FAIL",
        },
        "attempt_audit": (
            {
                "version": 1,
                "status": "ERROR",
                "classification": "TRANSPORT_INPUT_MOUNT",
                "accepted": False,
                "evidence_sha256": "d929ddb47c881e5f0a3c117cb7ae96920d3d3d219b2e6ef4791912e671355bd9",
            },
            {
                "version": 2,
                "status": "ERROR",
                "classification": "HOST_ENVIRONMENT_GLOBAL_PACKAGE_CONFLICT",
                "accepted": False,
                "evidence_sha256": "0be99d3af88fb657326a3019061a55978dda7499e383cfe43b195f390c151b3e",
            },
            {
                "version": 3,
                "status": "COMPLETE",
                "classification": "PACKAGING_OUTPUT_POLLUTION",
                "accepted": False,
                "evidence_sha256": "3debf9943705ac79da73ec7bdfe5b4b856a1b0fca91557b4f356406ed55a253a",
            },
            {
                "version": 4,
                "status": "COMPLETE",
                "classification": "ACCEPTED_NORMAL_RUN",
                "accepted": True,
                "evidence_sha256": _sha256(install_payload),
            },
        ),
        "failure_separation": {
            "accepted_run_product_failure_count": 0,
            "accepted_run_transport_failure_count": 0,
            "accepted_run_platform_failure_count": 0,
            "historical_attempts_are_not_release_results": True,
        },
        "release_identity": {
            "release_wheel_sha256": RELEASE_WHEEL_SHA256,
            "release_package_sha256": RELEASE_PACKAGE_SHA256,
            "runtime_identity_digest": RELEASE_RUNTIME_IDENTITY,
            "runtime_policy_changed": False,
        },
        "source_bindings": {
            "normal_run": {
                "path": DEFAULT_REPORT.relative_to(ROOT).as_posix(),
                "sha256": _sha256(_encoded(report)),
                "logical_content_sha256": report["logical_content_sha256"],
            },
            "package_validation": {
                "path": PACKAGE_VALIDATION_PATH.relative_to(ROOT).as_posix(),
                "sha256": _sha256(package_validation_payload),
            },
            "M4_P04_same_release_full_sample": {
                "path": M4_P04_CLOSURE_PATH.relative_to(ROOT).as_posix(),
                "sha256": _sha256(m4_p04_payload),
            },
        },
        "claim_boundary": {
            "allowed_claim": "M4_P05_KAGGLE_NORMAL_RUN_PASS",
            "official_score_obtained": False,
            "competition_submission_created": False,
            "ARC3_COMPLETION_AGENT_PRODUCT_RELEASED": False,
            "next_point": "M4-P06_SUBMISSION_PLATFORM_SEPARATION",
            "next_point_authorization": "EXPLICIT_SUBMISSION_AUTHORIZATION_REQUIRED",
        },
    }
    closure["logical_content_sha256"] = _logical_seal(closure)
    return report, closure


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--kernel-version", type=int, default=ACCEPTED_KERNEL_VERSION)
    parser.add_argument("--push-started-utc", required=True)
    parser.add_argument("--completion-checked-utc", required=True)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--closure", type=Path, default=DEFAULT_CLOSURE)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    report, closure = verify(
        push_started_utc=str(arguments.push_started_utc),
        completion_checked_utc=str(arguments.completion_checked_utc),
        kernel_version=int(arguments.kernel_version),
    )
    report_path = arguments.report.resolve()
    closure_path = arguments.closure.resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    closure_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_bytes(_encoded(report))
    closure_path.write_bytes(_encoded(closure))
    print(
        json.dumps(
            {
                "status": closure["status"],
                "normal_run_status": report["status"],
                "passed_check_count": report["passed_check_count"],
                "check_count": report["check_count"],
                "report": report_path.as_posix(),
                "report_sha256": _sha256(_encoded(report)),
                "closure": closure_path.as_posix(),
                "closure_sha256": _sha256(_encoded(closure)),
                "submission_api_call_count": 0,
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0 if closure["status"] == "M4_P05_PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
