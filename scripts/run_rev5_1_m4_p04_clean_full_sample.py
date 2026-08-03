#!/usr/bin/env python3
"""Run and audit M4-P04 from the exact M4-P03 clean installation."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from pathlib import Path
from typing import Final, cast

REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[1]
LOCAL_RECEIPT_PATH: Final = Path(".codex-m4-clean-install-state.json")
M4_P02_REPORT_PATH: Final = Path(
    "analysis/product/rev5_1/m4_p02_freeze_manifest.json"
)
M4_P03_REPORT_PATH: Final = Path(
    "analysis/product/rev5_1/m4_p03_clean_install.json"
)
M3_P06_REPORT_PATH: Final = Path(
    "analysis/product/rev5_1/m3_p06_clean_full_regression_run.json"
)
M2_RUN_PATHS: Final = (
    Path("analysis/product/rev5_1/m2_p01_clean_run_a.json"),
    Path("analysis/product/rev5_1/m2_p04_shuffled_run_b.json"),
    Path("analysis/product/rev5_1/m2_p04_shuffled_run_c.json"),
)
WHEEL_PATH: Final = Path(
    "release/rev5_1/arc3_completion_agent_release-0.1.0-py3-none-any.whl"
)
RESOURCE_ARCHIVE_PATH: Final = Path(
    "release/rev5_1/arc3_official_sample_resources_v1.zip"
)
RELEASE_DESCRIPTOR_PATH: Final = Path(
    "ARC-AGI-3-Agents/arc3_agi_agent/bundles/arc3_product_release_v1.json"
)
RELEASE_PACKAGE_PATH: Final = Path(
    "ARC-AGI-3-Agents/arc3_agi_agent/bundles/arc3_product_release_v1.zip"
)
RUN_REPORT_PATH: Final = Path(
    "analysis/product/rev5_1/m4_p04_clean_full_sample_run.json"
)
CLOSURE_PATH: Final = Path(
    "analysis/product/rev5_1/m4_p04_clean_full_sample_closure.json"
)
SCRIPT_PATH: Final = Path("scripts/run_rev5_1_m4_p04_clean_full_sample.py")
EXPECTED_WHEEL_SHA256: Final = (
    "b930ea1b339d4cb153f6ae153b3cec1e57ea1661dc40c7616a3ad6c6bc5790e4"
)
EXPECTED_RESOURCE_SHA256: Final = (
    "af87352f7533f1459564fa3cbc2f9eb4c6e29cc104872432ec99d9a3bc3db590"
)
EXPECTED_RELEASE_PACKAGE_SHA256: Final = (
    "99dd28966a0c20eaf2d93c3c47746d81d0ff2de666290f33b13526e8e878c923"
)
EXPECTED_P03_SHA256: Final = (
    "1bc133a3163c9b0636619f876731ff57241158ff92206596c7587476d3811fbc"
)
EXPECTED_RUNTIME_IDENTITY: Final = (
    "runtime-identity:47094e2ddb524bb1dba76078d51e10a20b090148bcd5b9a7c9cc4a20a416faff"
)
FUNCTIONAL_FIELDS: Final = (
    "action_id_counts",
    "actions_executed",
    "failed_hypothesis_invalidation_count",
    "failure_attribution_count",
    "failure_signatures",
    "final_state",
    "memory_causal_behavior_change_count",
    "post_rollback_replan_count",
    "progress_count",
    "rollback_plan_count",
    "stop_reason",
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _encoded(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _require(condition: bool, failure: str) -> None:
    if not condition:
        raise RuntimeError(failure)


def _load_object(path: Path, error: str) -> tuple[dict[str, object], bytes]:
    payload = path.read_bytes()
    value = json.loads(payload.decode("utf-8"))
    if not isinstance(value, dict):
        raise TypeError(error)
    return {str(key): item for key, item in value.items()}, payload


def _load_embedded_stdout_object(
    path: Path,
) -> tuple[dict[str, object], bytes, bytes]:
    payload = path.read_bytes()
    text = payload.decode("utf-8")
    markers = (
        '{\n  "active_agent_peak"',
        '{\r\n  "active_agent_peak"',
    )
    starts = tuple(index for marker in markers if (index := text.find(marker)) >= 0)
    _require(bool(starts), "M4_P04_PRODUCT_STDOUT_FINAL_JSON_MISSING")
    start = min(starts)
    value, end = json.JSONDecoder().raw_decode(text[start:])
    _require(
        not text[start + end :].strip(),
        "M4_P04_PRODUCT_STDOUT_TRAILING_CONTENT",
    )
    if not isinstance(value, dict):
        raise TypeError("M4_P04_PRODUCT_STDOUT_OBJECT_REQUIRED")
    prefix = text[:start].encode("utf-8")
    return {str(key): item for key, item in value.items()}, payload, prefix


def _verify_logical_seal(value: dict[str, object], error: str) -> str:
    body = dict(value)
    claimed = body.pop("logical_content_sha256", None)
    actual = _sha256(_canonical_json(body))
    _require(claimed == actual, error)
    return actual


def _binding(path: Path, payload: bytes) -> dict[str, object]:
    return {"path": path.as_posix(), "sha256": _sha256(payload)}


def _is_within(path: Path, root: Path) -> bool:
    resolved = path.resolve()
    resolved_root = root.resolve()
    return resolved == resolved_root or resolved_root in resolved.parents


def _clean_subprocess_environment(root: Path) -> dict[str, str]:
    allowed = (
        "APPDATA",
        "COMSPEC",
        "LOCALAPPDATA",
        "PATH",
        "PATHEXT",
        "SystemDrive",
        "SystemRoot",
        "TEMP",
        "TMP",
        "USERPROFILE",
        "WINDIR",
    )
    output = {name: os.environ[name] for name in allowed if name in os.environ}
    clean_path: list[str] = []
    for value in output.get("PATH", "").split(os.pathsep):
        if not value:
            continue
        try:
            if _is_within(Path(value), root):
                continue
        except OSError:
            pass
        clean_path.append(value)
    output["PATH"] = os.pathsep.join(clean_path)
    output.update(
        {
            "PIP_CONFIG_FILE": os.devnull,
            "PIP_DISABLE_PIP_VERSION_CHECK": "1",
            "PIP_NO_CACHE_DIR": "1",
            "PIP_NO_INPUT": "1",
            "PYTHONNOUSERSITE": "1",
            "PYTHONUTF8": "1",
        }
    )
    return output


def _verify_context(root: Path) -> dict[str, object]:
    receipt, receipt_payload = _load_object(
        root / LOCAL_RECEIPT_PATH,
        "M4_P04_LOCAL_RECEIPT_OBJECT_REQUIRED",
    )
    _require(
        receipt.get("schema_version") == "arc3-rev5-1-m4-p03-local-receipt-v1",
        "M4_P04_LOCAL_RECEIPT_SCHEMA_INVALID",
    )
    for key in ("install_root", "fresh_python", "resource_dir", "boot_script"):
        if not isinstance(receipt.get(key), str):
            raise TypeError("M4_P04_LOCAL_RECEIPT_FIELD_INVALID:" + key)

    install_root = Path(str(receipt["install_root"])).resolve()
    fresh_python = Path(str(receipt["fresh_python"])).resolve()
    resource_dir = Path(str(receipt["resource_dir"])).resolve()
    entrypoint = install_root / "venv" / "Scripts" / "arc3-completion-product.exe"
    installed_wheel = install_root / WHEEL_PATH.name
    installed_resource_archive = install_root / "official_sample_resources.zip"
    _require(
        install_root.is_dir()
        and fresh_python.is_file()
        and entrypoint.is_file()
        and resource_dir.is_dir()
        and installed_wheel.is_file()
        and installed_resource_archive.is_file(),
        "M4_P04_CLEAN_INSTALL_STATE_MISSING",
    )
    _require(
        not _is_within(install_root, root),
        "M4_P04_INSTALL_INSIDE_DEVELOPMENT_TREE",
    )

    p02, p02_payload = _load_object(
        root / M4_P02_REPORT_PATH,
        "M4_P04_P02_REPORT_OBJECT_REQUIRED",
    )
    p02_logical = _verify_logical_seal(
        p02,
        "M4_P04_P02_LOGICAL_SEAL_INVALID",
    )
    p03, p03_payload = _load_object(
        root / M4_P03_REPORT_PATH,
        "M4_P04_P03_REPORT_OBJECT_REQUIRED",
    )
    p03_logical = _verify_logical_seal(
        p03,
        "M4_P04_P03_LOGICAL_SEAL_INVALID",
    )
    wheel_payload = (root / WHEEL_PATH).read_bytes()
    resource_payload = (root / RESOURCE_ARCHIVE_PATH).read_bytes()
    release_descriptor_payload = (root / RELEASE_DESCRIPTOR_PATH).read_bytes()
    release_package_payload = (root / RELEASE_PACKAGE_PATH).read_bytes()
    p03_boot = p03.get("boot_audit")
    p03_clean = p03.get("clean_environment")
    if not isinstance(p03_boot, dict) or not isinstance(p03_clean, dict):
        raise TypeError("M4_P04_P03_AUDIT_SECTIONS_REQUIRED")
    _require(
        _sha256(p03_payload) == EXPECTED_P03_SHA256
        and p03.get("status") == "M4_P03_PASS"
        and p02.get("status") == "M4_P02_PASS"
        and _sha256(wheel_payload) == EXPECTED_WHEEL_SHA256
        and _sha256(resource_payload) == EXPECTED_RESOURCE_SHA256
        and _sha256(release_package_payload) == EXPECTED_RELEASE_PACKAGE_SHA256
        and receipt.get("wheel_sha256") == EXPECTED_WHEEL_SHA256
        and receipt.get("resource_archive_sha256") == EXPECTED_RESOURCE_SHA256
        and receipt.get("M4_P02_report_sha256") == _sha256(p02_payload)
        and _sha256(installed_wheel.read_bytes()) == EXPECTED_WHEEL_SHA256
        and _sha256(installed_resource_archive.read_bytes())
        == EXPECTED_RESOURCE_SHA256
        and p03_boot.get("release_bundle_sha256")
        == EXPECTED_RELEASE_PACKAGE_SHA256
        and p03_boot.get("runtime_identity_digest") == EXPECTED_RUNTIME_IDENTITY
        and p03_clean.get("development_tree_import_count") == 0
        and p03_clean.get("development_tree_sys_path_count") == 0
        and p03_clean.get("credential_binding_count") == 0,
        "M4_P04_CLEAN_INSTALL_BINDING_FAILED",
    )
    return {
        "receipt": receipt,
        "receipt_payload": receipt_payload,
        "install_root": install_root,
        "fresh_python": fresh_python,
        "resource_dir": resource_dir,
        "entrypoint": entrypoint,
        "p02": p02,
        "p02_payload": p02_payload,
        "p02_logical": p02_logical,
        "p03": p03,
        "p03_payload": p03_payload,
        "p03_logical": p03_logical,
        "wheel_payload": wheel_payload,
        "resource_payload": resource_payload,
        "release_descriptor_payload": release_descriptor_payload,
        "release_package_payload": release_package_payload,
    }


def _temp_paths(context: dict[str, object]) -> dict[str, Path]:
    install_root = context["install_root"]
    if not isinstance(install_root, Path):
        raise TypeError("M4_P04_INSTALL_ROOT_INVALID")
    return {
        "report": install_root / "m4-p04-clean-full-run.json",
        "stdout": install_root / "m4-p04-product-stdout.json",
        "log": install_root / "m4-p04-product-console.log",
        "recordings": install_root / "m4-p04-recordings",
    }


def _run_installed_product(root: Path, context: dict[str, object]) -> None:
    paths = _temp_paths(context)
    _require(
        not any(paths[key].exists() for key in ("report", "stdout", "log")),
        "M4_P04_PRIOR_EXECUTION_OUTPUT_PRESENT",
    )
    paths["recordings"].mkdir(parents=True, exist_ok=False)
    entrypoint = context["entrypoint"]
    install_root = context["install_root"]
    resource_dir = context["resource_dir"]
    if not all(isinstance(value, Path) for value in (entrypoint, install_root, resource_dir)):
        raise TypeError("M4_P04_EXECUTION_PATH_INVALID")
    entrypoint = cast(Path, entrypoint)
    install_root = cast(Path, install_root)
    resource_dir = cast(Path, resource_dir)
    command = [
        str(entrypoint),
        "--mode",
        "offline",
        "--release-frozen",
        "--environments-dir",
        str(resource_dir),
        "--recordings-dir",
        str(paths["recordings"]),
        "--action-budget",
        "4096",
        "--report",
        str(paths["report"]),
    ]
    environment = _clean_subprocess_environment(root)
    credential_names = (
        "AGENTOPS_API_KEY",
        "KAGGLE_API_TOKEN",
        "OPENAI_API_KEY",
    )
    _require(
        not any(name in environment for name in credential_names)
        and "PYTHONPATH" not in environment
        and "OPERATION_MODE" not in environment,
        "M4_P04_EXECUTION_ENVIRONMENT_NOT_CLEAN",
    )
    with paths["stdout"].open("wb") as stdout_stream, paths["log"].open(
        "w", encoding="utf-8", newline="\n"
    ) as log_stream:
        process = subprocess.Popen(
            command,
            cwd=install_root,
            env=environment,
            stdout=stdout_stream,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
            bufsize=1,
        )
        if process.stderr is None:
            raise RuntimeError("M4_P04_STDERR_PIPE_MISSING")
        for line in process.stderr:
            log_stream.write(line)
            log_stream.flush()
            if any(
                marker in line
                for marker in (
                    "Sequential game complete:",
                    "Sequential game failed:",
                    "Sequential competition summary:",
                )
            ):
                print(line.rstrip(), flush=True)
        return_code = process.wait()
    if return_code != 0:
        tail = paths["log"].read_text(encoding="utf-8", errors="replace")[-4000:]
        raise RuntimeError(f"M4_P04_PRODUCT_PROCESS_FAILED:{return_code}:{tail}")
    _require(paths["report"].is_file(), "M4_P04_PRODUCT_REPORT_MISSING")
    run, run_payload = _load_object(
        paths["report"],
        "M4_P04_PRODUCT_REPORT_OBJECT_REQUIRED",
    )
    stdout, _, _ = _load_embedded_stdout_object(paths["stdout"])
    _require(run == stdout, "M4_P04_PRODUCT_STDOUT_REPORT_MISMATCH")
    output_path = root / RUN_REPORT_PATH
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(run_payload)


def _recover_completed_product(root: Path, context: dict[str, object]) -> None:
    paths = _temp_paths(context)
    run, run_payload = _load_object(
        paths["report"],
        "M4_P04_RECOVERY_REPORT_OBJECT_REQUIRED",
    )
    stdout, _, _ = _load_embedded_stdout_object(paths["stdout"])
    log_text = paths["log"].read_text(encoding="utf-8", errors="replace")
    _require(
        run == stdout
        and run.get("known_sample_regression_established") is True
        and run.get("product_game_win_count") == 25
        and run.get("product_level_completion_count") == 183
        and run.get("product_total_action_count") == 10733
        and run.get("failed_game_count") == 0
        and run.get("lifecycle_failure_count") == 0
        and log_text.count("Sequential game complete:") == 25
        and log_text.count("Sequential competition summary:") == 1
        and "Sequential game failed:" not in log_text,
        "M4_P04_COMPLETED_RUN_NOT_RECOVERABLE",
    )
    output_path = root / RUN_REPORT_PATH
    _require(not output_path.exists(), "M4_P04_REPOSITORY_RUN_ALREADY_PRESENT")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_bytes(run_payload)


def _inspect_execution(
    root: Path,
    context: dict[str, object],
) -> tuple[dict[str, object], bytes, dict[str, object]]:
    paths = _temp_paths(context)
    clean_run, clean_run_payload = _load_object(
        paths["report"],
        "M4_P04_CLEAN_RUN_OBJECT_REQUIRED",
    )
    stdout, stdout_payload, stdout_prefix = _load_embedded_stdout_object(
        paths["stdout"]
    )
    repository_run, repository_run_payload = _load_object(
        root / RUN_REPORT_PATH,
        "M4_P04_REPOSITORY_RUN_OBJECT_REQUIRED",
    )
    log_payload = paths["log"].read_bytes()
    log_text = log_payload.decode("utf-8", errors="replace")
    entrypoint = context["entrypoint"]
    if not isinstance(entrypoint, Path):
        raise TypeError("M4_P04_ENTRYPOINT_INVALID")
    environment = _clean_subprocess_environment(root)
    _require(
        clean_run == stdout == repository_run
        and clean_run_payload == repository_run_payload
        and log_text.count("Sequential game complete:") == 25
        and log_text.count("Sequential competition summary:") == 1
        and "Sequential game failed:" not in log_text,
        "M4_P04_EXECUTION_EVIDENCE_INVALID",
    )
    path_exposure_count = sum(
        1
        for value in environment.get("PATH", "").split(os.pathsep)
        if value and _is_within(Path(value), root)
    )
    credential_names = (
        "AGENTOPS_API_KEY",
        "KAGGLE_API_TOKEN",
        "OPENAI_API_KEY",
    )
    execution = {
        "product_process_exit_code": 0,
        "product_process_exit_code_basis": (
            "PARENT_REACHED_POST_ZERO_EXIT_EVIDENCE_VALIDATION"
        ),
        "console_entrypoint_count": 1,
        "console_entrypoint_sha256": _sha256(entrypoint.read_bytes()),
        "stdout_json_equal_to_report": True,
        "stdout_contract": "LOG_PREAMBLE_PLUS_FINAL_JSON",
        "stdout_log_preamble_present": bool(stdout_prefix),
        "stdout_log_preamble_sha256": _sha256(stdout_prefix),
        "stdout_sha256": _sha256(stdout_payload),
        "console_log_sha256": _sha256(log_payload),
        "completed_game_log_count": 25,
        "summary_log_count": 1,
        "development_tree_path_exposure_count": path_exposure_count,
        "credential_environment_count": sum(
            name in environment for name in credential_names
        ),
    }
    return repository_run, repository_run_payload, execution


def _rows(
    report: dict[str, object],
    *,
    label: str,
) -> tuple[list[str], dict[str, dict[str, object]]]:
    index = report.get("orchestration_game_index")
    results = report.get("results")
    if not isinstance(index, list) or not isinstance(results, list):
        raise TypeError(f"M4_P04_RUN_ROWS_INVALID:{label}")
    _require(len(index) == len(results) == 25, f"M4_P04_RUN_COUNT:{label}")
    order: list[str] = []
    rows: dict[str, dict[str, object]] = {}
    for ordinal, (metadata, result) in enumerate(zip(index, results, strict=True)):
        if not isinstance(metadata, dict) or not isinstance(result, dict):
            raise TypeError(f"M4_P04_RUN_ROW_INVALID:{label}:{ordinal}")
        game_id = metadata.get("game_id")
        if not isinstance(game_id, str) or not game_id:
            raise TypeError(f"M4_P04_GAME_ID_INVALID:{label}:{ordinal}")
        _require(
            metadata.get("game_index") == ordinal
            and result.get("game_index") == ordinal
            and game_id not in rows,
            f"M4_P04_GAME_INDEX_INVALID:{label}:{game_id}",
        )
        order.append(game_id)
        rows[game_id] = {str(key): value for key, value in result.items()}
    return order, rows


def _build_closure(
    root: Path,
    context: dict[str, object],
    run: dict[str, object],
    run_payload: bytes,
    execution: dict[str, object],
) -> dict[str, object]:
    baseline, baseline_payload = _load_object(
        root / M3_P06_REPORT_PATH,
        "M4_P04_M3_BASELINE_OBJECT_REQUIRED",
    )
    m2_runs = [
        _load_object(root / path, "M4_P04_M2_RUN_OBJECT_REQUIRED")
        for path in M2_RUN_PATHS
    ]
    p03 = context["p03"]
    p03_payload = context["p03_payload"]
    if not isinstance(p03, dict) or not isinstance(p03_payload, bytes):
        raise TypeError("M4_P04_P03_CONTEXT_INVALID")
    p03_boot = p03.get("boot_audit")
    p03_clean = p03.get("clean_environment")
    if not isinstance(p03_boot, dict) or not isinstance(p03_clean, dict):
        raise TypeError("M4_P04_P03_SECTIONS_INVALID")
    p02_payload = cast(bytes, context["p02_payload"])
    p02_logical = cast(str, context["p02_logical"])
    p03_logical = cast(str, context["p03_logical"])
    wheel_payload = cast(bytes, context["wheel_payload"])
    resource_payload = cast(bytes, context["resource_payload"])
    release_descriptor_payload = cast(
        bytes,
        context["release_descriptor_payload"],
    )
    release_package_payload = cast(bytes, context["release_package_payload"])

    expected: dict[str, object] = {
        "active_agent_peak": 1,
        "active_product_path_count": 1,
        "adapter_crash_count": 0,
        "advertised_game_count": 25,
        "completed_game_count": 25,
        "failed_game_count": 0,
        "identity_boundary": "PASS",
        "known_sample_regression_established": True,
        "known_sample_regression_status": "KNOWN_SAMPLE_REGRESSION_COMPLETE",
        "lifecycle_failure_count": 0,
        "offline_environment_available_count": 25,
        "offline_environment_selected_count": 25,
        "operation_mode": "offline",
        "p_j0_m0_runtime_identity_bound": True,
        "per_game_new_memory_count": 0,
        "per_game_new_p_count": 0,
        "product_active_dev_mechanism_family_count": 0,
        "product_bundle_stage": "RELEASE_FROZEN",
        "product_endpoint_failure_count": 0,
        "product_executed_plan_count": 10733,
        "product_game_started_count": 25,
        "product_game_win_count": 25,
        "product_hds_plan_commit_count": 10733,
        "product_level_completion_count": 183,
        "product_release_bundle_id": "ARC3ProductBundle-release-v1",
        "product_release_bundle_loaded": True,
        "product_release_bundle_sha256": EXPECTED_RELEASE_PACKAGE_SHA256,
        "product_release_frozen_mechanism_family_count": 1,
        "product_result_count": 25,
        "product_runtime_failure_signature_row_count": 0,
        "product_runtime_identity_digest": EXPECTED_RUNTIME_IDENTITY,
        "product_total_action_count": 10733,
        "resource_action_budget_per_episode": 4096,
        "runtime_identity_digest": EXPECTED_RUNTIME_IDENTITY,
        "runtime_policy_changed": False,
        "scorecard_close_count": 1,
        "scorecard_closed": True,
        "scorecard_lifecycle_leak_count": 0,
        "scorecard_open_count": 1,
        "shared_session_count": 1,
        "started_game_count": 25,
        "state_owner_violation_count": 0,
    }
    mismatches = tuple(key for key, value in expected.items() if run.get(key) != value)
    _require(
        not mismatches,
        "M4_P04_FULL_RUN_CONTRACT:" + ",".join(mismatches),
    )
    _require(
        run.get("failures") == []
        and run.get("lifecycle_failures") == []
        and run.get("product_endpoint_failures") == [],
        "M4_P04_FAILURE_ROWS_PRESENT",
    )
    _require(
        run.get("product_initial_state_logical_digest")
        == p03_boot.get("initial_state_logical_digest")
        and run.get("product_p_logical_digest") == p03_boot.get("p_logical_digest")
        and run.get("product_j0_digest") == p03_boot.get("j0_digest")
        and run.get("product_m0_digest") == p03_boot.get("m0_digest")
        and run.get("product_release_bundle_logical_digest")
        == p03_boot.get("release_bundle_logical_digest")
        and execution.get("development_tree_path_exposure_count") == 0
        and execution.get("credential_environment_count") == 0,
        "M4_P04_RELEASE_OR_ENVIRONMENT_BINDING_FAILED",
    )

    order, rows = _rows(run, label="M4-P04")
    baseline_order, baseline_rows = _rows(baseline, label="M3-P06")
    _require(order == baseline_order, "M4_P04_OFFICIAL_ORDER_DRIFT")
    functional_mismatches: list[str] = []
    for game_id in order:
        row = rows[game_id]
        baseline_row = baseline_rows[game_id]
        _require(
            row.get("final_state") == "WIN"
            and row.get("stop_reason") == "GOAL_REACHED"
            and row.get("failure_signatures") == []
            and row.get("hds_plan_commit_count") == row.get("actions_executed")
            and row.get("executed_plan_count") == row.get("actions_executed"),
            f"M4_P04_GAME_NOT_AUTHORIZED_COMPLETE:{game_id}",
        )
        for field in FUNCTIONAL_FIELDS:
            if row.get(field) != baseline_row.get(field):
                functional_mismatches.append(f"{game_id}:{field}")
    _require(
        not functional_mismatches,
        "M4_P04_FUNCTIONAL_REGRESSION:" + ",".join(functional_mismatches),
    )

    lineage = run.get("session_lineage_digest")
    prior_lineages = {
        baseline.get("session_lineage_digest"),
        *(value.get("session_lineage_digest") for value, _ in m2_runs),
    }
    _require(
        isinstance(lineage, str)
        and lineage.startswith("cognitive-lineage:")
        and lineage not in prior_lineages,
        "M4_P04_SESSION_LINEAGE_NOT_INDEPENDENT",
    )

    source_bindings = {
        "M4_P02_freeze": {
            **_binding(M4_P02_REPORT_PATH, p02_payload),
            "logical_content_sha256": p02_logical,
        },
        "M4_P03_clean_install": {
            **_binding(M4_P03_REPORT_PATH, p03_payload),
            "logical_content_sha256": p03_logical,
        },
        "M3_P06_functional_baseline": _binding(
            M3_P06_REPORT_PATH,
            baseline_payload,
        ),
        "release_wheel": _binding(WHEEL_PATH, wheel_payload),
        "official_sample_resources": _binding(
            RESOURCE_ARCHIVE_PATH,
            resource_payload,
        ),
        "release_descriptor": _binding(
            RELEASE_DESCRIPTOR_PATH,
            release_descriptor_payload,
        ),
        "release_package": _binding(
            RELEASE_PACKAGE_PATH,
            release_package_payload,
        ),
        "clean_installed_run": _binding(RUN_REPORT_PATH, run_payload),
        "M4_P04_runner": _binding(SCRIPT_PATH, (root / SCRIPT_PATH).read_bytes()),
    }
    closure: dict[str, object] = {
        "schema_version": "arc3-rev5-1-m4-p04-clean-full-sample-v1",
        "artifact_type": "M4CleanInstalledFullSampleEvidence",
        "point_id": "M4-P04_CLEAN_FULL_SAMPLE_RERUN",
        "runtime_product": "ARC3CompletionAgent",
        "asset_stage": "RELEASE_FROZEN",
        "status": "M4_P04_PASS",
        "source_bindings": source_bindings,
        "clean_execution": {
            **execution,
            "environment_identity_digest": p03_clean[
                "environment_identity_digest"
            ],
            "same_clean_install_as_M4_P03": True,
            "same_release_artifact_as_M4_P02": True,
            "source_tree_module_invocation_count": 0,
            "manual_step_intervention_count": 0,
            "network_service_count": 0,
        },
        "release_identity": {
            "release_bundle_id": run["product_release_bundle_id"],
            "release_bundle_logical_digest": run[
                "product_release_bundle_logical_digest"
            ],
            "release_bundle_sha256": run["product_release_bundle_sha256"],
            "initial_state_logical_digest": run[
                "product_initial_state_logical_digest"
            ],
            "p_logical_digest": run["product_p_logical_digest"],
            "j0_digest": run["product_j0_digest"],
            "m0_digest": run["product_m0_digest"],
            "runtime_identity_digest": run["product_runtime_identity_digest"],
            "release_bundle_count": 1,
            "active_dev_bundle_count": 0,
            "runtime_policy_changed": False,
        },
        "full_sample_audit": {
            "official_sample_game_count": 25,
            "game_WIN_count": 25,
            "level_completion_count": 183,
            "total_action_count": 10733,
            "game_failure_count": 0,
            "lifecycle_failure_count": 0,
            "adapter_crash_count": 0,
            "runtime_failure_signature_count": 0,
            "J_plan_commit_count": 10733,
            "executed_plan_count": 10733,
            "unauthorized_action_count": 0,
            "memory_causal_behavior_change_count": run[
                "product_memory_causal_behavior_change_count"
            ],
            "failed_hypothesis_invalidation_count": run[
                "product_failed_hypothesis_invalidation_count"
            ],
            "failure_attribution_count": run[
                "product_failure_attribution_count"
            ],
            "rollback_plan_count": run["product_rollback_plan_count"],
            "post_rollback_replan_count": run[
                "product_post_rollback_replan_count"
            ],
        },
        "equivalence_audit": {
            "baseline": M3_P06_REPORT_PATH.as_posix(),
            "official_game_order_equal": True,
            "functional_field_count_per_game": len(FUNCTIONAL_FIELDS),
            "functional_mismatch_count": 0,
            "functional_equivalence": True,
            "current_session_lineage_digest": lineage,
            "prior_session_lineage_count": len(prior_lineages),
            "independent_session_lineage": True,
        },
        "exit_audit": {
            "M4_P03_clean_install": "PASS",
            "same_release_artifact": True,
            "official_sample_game_wins": "25/25",
            "official_sample_level_completions": "183/183",
            "total_actions": 10733,
            "failure_count": 0,
            "unauthorized_action_count": 0,
            "functional_equivalence_to_M3_P06": True,
            "independent_session_lineage": True,
            "status": "M4_P04_PASS",
        },
        "claim_boundary": {
            "allowed_claim": "M4_P04_SAME_RELEASE_FULL_SAMPLE_PASS",
            "clean_full_sample_repeat_complete": True,
            "Kaggle_normal_run_complete": False,
            "ARC3_PRODUCT_RELEASED": False,
            "next_point": "M4-P05_KAGGLE_PACKAGE_NORMAL_RUN",
        },
    }
    closure["logical_content_sha256"] = _sha256(_canonical_json(closure))
    return closure


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run", action="store_true")
    mode.add_argument("--recover-completed-run", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=REPOSITORY_ROOT)
    arguments = parser.parse_args()
    root = arguments.repo_root.resolve()
    context = _verify_context(root)
    if arguments.run:
        _run_installed_product(root, context)
    elif arguments.recover_completed_run:
        _recover_completed_product(root, context)
    run, run_payload, execution = _inspect_execution(root, context)
    closure = _build_closure(root, context, run, run_payload, execution)
    closure_payload = _encoded(closure)
    closure_path = root / CLOSURE_PATH
    if arguments.run or arguments.recover_completed_run:
        closure_path.parent.mkdir(parents=True, exist_ok=True)
        closure_path.write_bytes(closure_payload)
        write_status = (
            "RECOVERED_WRITTEN" if arguments.recover_completed_run else "WRITTEN"
        )
    else:
        _require(
            closure_path.read_bytes() == closure_payload,
            "M4_P04_CLOSURE_REPORT_STALE",
        )
        write_status = "PASS"
    print(
        json.dumps(
            {
                "closure": CLOSURE_PATH.as_posix(),
                "clean_run": RUN_REPORT_PATH.as_posix(),
                "game_wins": 25,
                "level_completions": 183,
                "point_status": "M4_P04_PASS",
                "status": write_status,
                "total_actions": 10733,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
