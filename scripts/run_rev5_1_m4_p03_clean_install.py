#!/usr/bin/env python3
"""Install and boot the M4-P02 wheel in a fresh, isolated environment."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
import sys
import tempfile
import textwrap
import zipfile
from pathlib import Path
from typing import Final

REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[1]
M4_P02_REPORT_PATH: Final = Path(
    "analysis/product/rev5_1/m4_p02_freeze_manifest.json"
)
WHEEL_PATH: Final = Path(
    "release/rev5_1/arc3_completion_agent_release-0.1.0-py3-none-any.whl"
)
RESOURCE_ARCHIVE_PATH: Final = Path(
    "release/rev5_1/arc3_official_sample_resources_v1.zip"
)
REPORT_PATH: Final = Path("analysis/product/rev5_1/m4_p03_clean_install.json")
LOCAL_RECEIPT_PATH: Final = Path(".codex-m4-clean-install-state.json")
SCRIPT_PATH: Final = Path("scripts/run_rev5_1_m4_p03_clean_install.py")
BOOT_SCRIPT_NAME: Final = "arc3_release_boot_check.py"
BOOT_SCRIPT: Final = textwrap.dedent(
    r'''
    from __future__ import annotations

    import importlib.metadata as metadata
    import json
    import os
    import sys
    from pathlib import Path

    import agents
    import arc3_agi_agent
    import arc_agi
    import arcengine
    from packaging.requirements import Requirement

    from agents.templates.arc3_completion_agent import ARC3CompletionAgent
    from arc3_agi_agent.p_ir_validator import require_valid_p_ir_program
    from arc3_agi_agent.product_release import (
        PRODUCT_RELEASE_BUNDLE_ID,
        PRODUCT_RELEASE_STAGE,
        load_default_product_release_bundle,
    )
    from arc3_agi_agent.product_runner import create_product_session

    release = load_default_product_release_bundle()
    session = create_product_session(
        action_budget=4096,
        mode="VALIDATION",
        initial_state=release.initial_state,
    )
    require_valid_p_ir_program(session.p_ir_program)
    release_distribution = metadata.distribution(
        "arc3-completion-agent-release"
    )
    requirements = tuple(release_distribution.requires or ())
    dependency_mismatches = []
    for raw in requirements:
        requirement = Requirement(raw)
        if requirement.marker is not None and not requirement.marker.evaluate():
            continue
        installed = metadata.version(requirement.name)
        if installed not in requirement.specifier:
            dependency_mismatches.append(
                f"{requirement.name}:{installed}:{requirement.specifier}"
            )
    prefix = Path(sys.prefix).resolve()
    forbidden_root = Path(os.environ["ARC3_FORBIDDEN_DEV_ROOT"]).resolve()
    local_module_paths = []
    for name, module in tuple(sys.modules.items()):
        if not (name == "agents" or name.startswith("agents.") or name == "arc3_agi_agent" or name.startswith("arc3_agi_agent.")):
            continue
        raw_path = getattr(module, "__file__", None)
        if raw_path:
            local_module_paths.append(Path(raw_path).resolve())
    development_imports = tuple(
        str(path)
        for path in local_module_paths
        if path == forbidden_root or forbidden_root in path.parents
    )
    outside_prefix = tuple(
        str(path)
        for path in local_module_paths
        if path != prefix and prefix not in path.parents
    )
    development_sys_path = tuple(
        value
        for value in sys.path
        if value
        and (
            Path(value).resolve() == forbidden_root
            or forbidden_root in Path(value).resolve().parents
        )
    )
    resources = Path(os.environ["ARC3_CLEAN_RESOURCE_DIR"]).resolve()
    game_directories = tuple(
        sorted(path.name for path in resources.iterdir() if path.is_dir())
    )
    entrypoints = tuple(
        entry
        for entry in metadata.entry_points(group="console_scripts")
        if entry.name == "arc3-completion-product"
    )
    result = {
        "python_version": ".".join(map(str, sys.version_info[:3])),
        "release_distribution_version": metadata.version(
            "arc3-completion-agent-release"
        ),
        "release_bundle_id": release.descriptor["product_bundle_id"],
        "release_bundle_stage": release.descriptor["asset_stage"],
        "release_bundle_logical_digest": release.logical_digest,
        "release_bundle_sha256": release.package_sha256,
        "initial_state_logical_digest": release.initial_state.logical_digest,
        "p_logical_digest": release.initial_state.p_bundle.logical_digest(),
        "j0_digest": release.descriptor["j0_digest"],
        "m0_digest": release.descriptor["m0_digest"],
        "m0_record_count": len(release.initial_state.m0),
        "runtime_identity_digest": session.runtime_identity.digest(),
        "compute_subject_type": type(session.compute).__name__,
        "judgement_subject_type": type(session.hds).__name__,
        "memory_subject_type": type(session.memory).__name__,
        "instruction_body_type": type(session.instruction_body).__name__,
        "p_ir_program_id": session.p_ir_program.program_id,
        "state_owner_violation_count": len(session.state_owner_violations()),
        "runtime_identity_failure_count": len(session.runtime_identity.validate()),
        "identity_boundary_finding_count": len(
            session.identity_boundary.inspect_decision_context(
                session.p_ir_program,
                session.hds_config,
                release.initial_state.m0,
            )
        ),
        "resource_action_budget": session.resource_contract.action_budget_per_episode,
        "hds_resource_budget": session.hds_config.resource_budget,
        "hds_no_progress_limit": session.hds_config.stop_after_no_progress,
        "official_adapter_import": bool(arc_agi and arcengine),
        "agent_class": ARC3CompletionAgent.__name__,
        "entrypoint_count": len(entrypoints),
        "entrypoint_target": entrypoints[0].value if entrypoints else None,
        "dependency_pin_count": len(requirements),
        "dependency_pin_mismatch_count": len(dependency_mismatches),
        "dependency_pin_mismatches": dependency_mismatches,
        "loaded_local_module_count": len(local_module_paths),
        "development_tree_import_count": len(development_imports),
        "outside_fresh_prefix_import_count": len(outside_prefix),
        "development_tree_sys_path_count": len(development_sys_path),
        "official_sample_game_directory_count": len(game_directories),
        "operation_mode_env_present": "OPERATION_MODE" in os.environ,
        "credential_env_present_count": sum(
            name in os.environ
            for name in (
                "AGENTOPS_API_KEY",
                "KAGGLE_API_TOKEN",
                "OPENAI_API_KEY",
            )
        ),
        "expected_release_bundle_id": PRODUCT_RELEASE_BUNDLE_ID,
        "expected_release_stage": PRODUCT_RELEASE_STAGE,
    }
    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    '''
).strip() + "\n"


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
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise TypeError(error)
    return {str(key): item for key, item in value.items()}, payload


def _verify_logical_seal(value: dict[str, object], error: str) -> str:
    body = dict(value)
    claimed = body.pop("logical_content_sha256", None)
    actual = _sha256(_canonical_json(body))
    _require(claimed == actual, error)
    return actual


def _clean_subprocess_environment(
    *,
    forbidden_root: Path | None = None,
    resource_dir: Path | None = None,
) -> dict[str, str]:
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
    if forbidden_root is not None:
        output["ARC3_FORBIDDEN_DEV_ROOT"] = str(forbidden_root)
    if resource_dir is not None:
        output["ARC3_CLEAN_RESOURCE_DIR"] = str(resource_dir)
    return output


def _run(
    command: list[str],
    *,
    cwd: Path,
    environment: dict[str, str],
    failure: str,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=environment,
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        raise RuntimeError(
            failure
            + f":exit={result.returncode}:"
            + (result.stderr or result.stdout)[-4000:]
        )
    return result


def _safe_extract_resource_archive(
    *,
    payload: bytes,
    install_root: Path,
) -> Path:
    archive_path = install_root / "official_sample_resources.zip"
    archive_path.write_bytes(payload)
    resource_root = install_root / "resources"
    with zipfile.ZipFile(archive_path) as archive:
        names = archive.namelist()
        _require(
            names
            and all(
                name.startswith("environment_files/")
                and "\\" not in name
                and ".." not in name.split("/")
                for name in names
            ),
            "M4_P03_RESOURCE_ARCHIVE_MEMBER_INVALID",
        )
        archive.extractall(resource_root)
    environments = resource_root / "environment_files"
    _require(environments.is_dir(), "M4_P03_RESOURCE_EXTRACTION_FAILED")
    return environments


def _fresh_python(install_root: Path) -> Path:
    return install_root / "venv" / "Scripts" / "python.exe"


def _create_install(root: Path) -> dict[str, object]:
    p02, p02_payload = _load_object(
        root / M4_P02_REPORT_PATH,
        "M4_P03_P02_REPORT_OBJECT_REQUIRED",
    )
    p02_logical_sha = _verify_logical_seal(
        p02,
        "M4_P03_P02_REPORT_LOGICAL_SEAL_INVALID",
    )
    p02_exit = p02.get("exit_audit")
    if not isinstance(p02_exit, dict):
        raise TypeError("M4_P03_P02_EXIT_AUDIT_REQUIRED")
    wheel_payload = (root / WHEEL_PATH).read_bytes()
    resource_payload = (root / RESOURCE_ARCHIVE_PATH).read_bytes()
    wheel_artifact = p02.get("wheel_artifact")
    resource_freeze = p02.get("resource_freeze")
    if not isinstance(wheel_artifact, dict) or not isinstance(resource_freeze, dict):
        raise TypeError("M4_P03_P02_ARTIFACT_SECTIONS_REQUIRED")
    _require(
        p02.get("status") == "M4_P02_PASS"
        and p02_exit.get("runtime_source_closure") == "FROZEN"
        and p02_exit.get("dependency_lock") == "FROZEN"
        and p02_exit.get("resource_and_adapter_config") == "FROZEN"
        and p02_exit.get("credential_binding_count") == 0
        and wheel_artifact.get("sha256") == _sha256(wheel_payload)
        and resource_freeze.get("sha256") == _sha256(resource_payload),
        "M4_P03_P02_GATE_FAILED",
    )
    install_root = Path(tempfile.mkdtemp(prefix="arc3-m4-p03-"))
    clean_env = _clean_subprocess_environment()
    _run(
        [sys.executable, "-m", "venv", str(install_root / "venv")],
        cwd=install_root,
        environment=clean_env,
        failure="M4_P03_VENV_CREATION_FAILED",
    )
    fresh_python = _fresh_python(install_root)
    _require(fresh_python.is_file(), "M4_P03_FRESH_PYTHON_MISSING")
    pyvenv_config = (install_root / "venv" / "pyvenv.cfg").read_text(
        encoding="utf-8"
    )
    _require(
        "include-system-site-packages = false" in pyvenv_config.casefold(),
        "M4_P03_SYSTEM_SITE_PACKAGES_INHERITED",
    )
    wheel_copy = install_root / WHEEL_PATH.name
    wheel_copy.write_bytes(wheel_payload)
    install_result = _run(
        [
            str(fresh_python),
            "-m",
            "pip",
            "install",
            "--no-cache-dir",
            "--disable-pip-version-check",
            str(wheel_copy),
        ],
        cwd=install_root,
        environment=clean_env,
        failure="M4_P03_WHEEL_INSTALL_FAILED",
    )
    (install_root / "pip-install.log").write_text(
        install_result.stdout + install_result.stderr,
        encoding="utf-8",
        newline="\n",
    )
    environments = _safe_extract_resource_archive(
        payload=resource_payload,
        install_root=install_root,
    )
    boot_script = install_root / BOOT_SCRIPT_NAME
    boot_script.write_text(BOOT_SCRIPT, encoding="utf-8", newline="\n")
    receipt: dict[str, object] = {
        "schema_version": "arc3-rev5-1-m4-p03-local-receipt-v1",
        "install_root": str(install_root),
        "fresh_python": str(fresh_python),
        "resource_dir": str(environments),
        "boot_script": str(boot_script),
        "wheel_sha256": _sha256(wheel_payload),
        "resource_archive_sha256": _sha256(resource_payload),
        "M4_P02_report_sha256": _sha256(p02_payload),
        "M4_P02_logical_sha256": p02_logical_sha,
    }
    (root / LOCAL_RECEIPT_PATH).write_bytes(_encoded(receipt))
    return receipt


def _load_receipt(root: Path) -> dict[str, object]:
    receipt, _ = _load_object(
        root / LOCAL_RECEIPT_PATH,
        "M4_P03_LOCAL_RECEIPT_OBJECT_REQUIRED",
    )
    for key in ("install_root", "fresh_python", "resource_dir", "boot_script"):
        if not isinstance(receipt.get(key), str):
            raise TypeError("M4_P03_LOCAL_RECEIPT_FIELD_INVALID:" + key)
    return receipt


def _boot(root: Path, receipt: dict[str, object]) -> dict[str, object]:
    install_root = Path(str(receipt["install_root"]))
    fresh_python = Path(str(receipt["fresh_python"]))
    resource_dir = Path(str(receipt["resource_dir"]))
    boot_script = Path(str(receipt["boot_script"]))
    _require(
        fresh_python.is_file()
        and resource_dir.is_dir()
        and boot_script.read_text(encoding="utf-8") == BOOT_SCRIPT,
        "M4_P03_LOCAL_INSTALL_STATE_INVALID",
    )
    clean_env = _clean_subprocess_environment(
        forbidden_root=root,
        resource_dir=resource_dir,
    )
    result = _run(
        [str(fresh_python), str(boot_script)],
        cwd=install_root,
        environment=clean_env,
        failure="M4_P03_BOOT_CHECK_FAILED",
    )
    value = json.loads(result.stdout)
    if not isinstance(value, dict):
        raise TypeError("M4_P03_BOOT_RESULT_OBJECT_REQUIRED")
    return {str(key): item for key, item in value.items()}


def _build_report(
    root: Path,
    receipt: dict[str, object],
    boot: dict[str, object],
) -> dict[str, object]:
    p02, p02_payload = _load_object(
        root / M4_P02_REPORT_PATH,
        "M4_P03_P02_REPORT_OBJECT_REQUIRED",
    )
    p02_logical_sha = _verify_logical_seal(
        p02,
        "M4_P03_P02_REPORT_LOGICAL_SEAL_INVALID",
    )
    wheel_payload = (root / WHEEL_PATH).read_bytes()
    resource_payload = (root / RESOURCE_ARCHIVE_PATH).read_bytes()
    _require(
        receipt.get("wheel_sha256") == _sha256(wheel_payload)
        and receipt.get("resource_archive_sha256") == _sha256(resource_payload)
        and receipt.get("M4_P02_report_sha256") == _sha256(p02_payload)
        and boot.get("python_version") == "3.12.13"
        and boot.get("release_distribution_version") == "0.1.0"
        and boot.get("release_bundle_id") == "ARC3ProductBundle-release-v1"
        and boot.get("release_bundle_stage") == "RELEASE_FROZEN"
        and boot.get("state_owner_violation_count") == 0
        and boot.get("runtime_identity_failure_count") == 0
        and boot.get("identity_boundary_finding_count") == 0
        and boot.get("resource_action_budget") == 4096
        and boot.get("hds_resource_budget") == 4096
        and boot.get("hds_no_progress_limit") == 650
        and boot.get("official_adapter_import") is True
        and boot.get("agent_class") == "ARC3CompletionAgent"
        and boot.get("entrypoint_count") == 1
        and boot.get("entrypoint_target")
        == "arc3_agi_agent.product_runner:main"
        and boot.get("dependency_pin_mismatch_count") == 0
        and boot.get("development_tree_import_count") == 0
        and boot.get("outside_fresh_prefix_import_count") == 0
        and boot.get("development_tree_sys_path_count") == 0
        and boot.get("official_sample_game_directory_count") == 25
        and boot.get("operation_mode_env_present") is False
        and boot.get("credential_env_present_count") == 0,
        "M4_P03_BOOT_ACCEPTANCE_FAILED",
    )
    environment_identity_material = {
        "wheel_sha256": _sha256(wheel_payload),
        "resource_archive_sha256": _sha256(resource_payload),
        "python_version": boot["python_version"],
        "release_bundle_logical_digest": boot["release_bundle_logical_digest"],
        "runtime_identity_digest": boot["runtime_identity_digest"],
        "dependency_pin_count": boot["dependency_pin_count"],
    }
    report: dict[str, object] = {
        "schema_version": "arc3-rev5-1-m4-p03-clean-install-v1",
        "artifact_type": "M4CleanInstallBootEvidence",
        "point_id": "M4-P03_CLEAN_INSTALL",
        "runtime_product": "ARC3CompletionAgent",
        "asset_stage": "RELEASE_FROZEN",
        "status": "M4_P03_PASS",
        "source_bindings": {
            "M4_P02_freeze": {
                "path": M4_P02_REPORT_PATH.as_posix(),
                "sha256": _sha256(p02_payload),
                "logical_content_sha256": p02_logical_sha,
            },
            "release_wheel": {
                "path": WHEEL_PATH.as_posix(),
                "sha256": _sha256(wheel_payload),
            },
            "official_sample_resources": {
                "path": RESOURCE_ARCHIVE_PATH.as_posix(),
                "sha256": _sha256(resource_payload),
            },
            "clean_install_runner": {
                "path": SCRIPT_PATH.as_posix(),
                "sha256": _sha256((root / SCRIPT_PATH).read_bytes()),
                "boot_script_sha256": _sha256(BOOT_SCRIPT.encode("utf-8")),
            },
        },
        "clean_environment": {
            "fresh_environment": True,
            "outside_development_tree": True,
            "system_site_packages_inherited": False,
            "pip_cache_disabled": True,
            "editable_install": False,
            "development_tree_import_count": boot[
                "development_tree_import_count"
            ],
            "outside_fresh_prefix_import_count": boot[
                "outside_fresh_prefix_import_count"
            ],
            "development_tree_sys_path_count": boot[
                "development_tree_sys_path_count"
            ],
            "credential_binding_count": boot["credential_env_present_count"],
            "environment_identity_digest": "clean-release-environment:"
            + _sha256(_canonical_json(environment_identity_material)),
        },
        "install_audit": {
            "wheel_install": "PASS",
            "python_version": boot["python_version"],
            "release_distribution_version": boot[
                "release_distribution_version"
            ],
            "dependency_pin_count": boot["dependency_pin_count"],
            "dependency_pin_mismatch_count": boot[
                "dependency_pin_mismatch_count"
            ],
            "resource_archive_extract": "PASS",
            "official_sample_game_directory_count": boot[
                "official_sample_game_directory_count"
            ],
        },
        "boot_audit": {
            "release_bundle_load": "PASS",
            "release_bundle_id": boot["release_bundle_id"],
            "release_bundle_stage": boot["release_bundle_stage"],
            "release_bundle_logical_digest": boot[
                "release_bundle_logical_digest"
            ],
            "release_bundle_sha256": boot["release_bundle_sha256"],
            "initial_state_logical_digest": boot[
                "initial_state_logical_digest"
            ],
            "p_logical_digest": boot["p_logical_digest"],
            "j0_digest": boot["j0_digest"],
            "m0_digest": boot["m0_digest"],
            "m0_record_count": boot["m0_record_count"],
            "runtime_identity_digest": boot["runtime_identity_digest"],
            "compute_subject_type": boot["compute_subject_type"],
            "judgement_subject_type": boot["judgement_subject_type"],
            "memory_subject_type": boot["memory_subject_type"],
            "instruction_body_type": boot["instruction_body_type"],
            "p_ir_program_id": boot["p_ir_program_id"],
            "state_owner_violation_count": boot[
                "state_owner_violation_count"
            ],
            "runtime_identity_failure_count": boot[
                "runtime_identity_failure_count"
            ],
            "identity_boundary_finding_count": boot[
                "identity_boundary_finding_count"
            ],
            "official_adapter_import": "PASS",
            "agent_class": boot["agent_class"],
            "entrypoint_count": boot["entrypoint_count"],
            "entrypoint_target": boot["entrypoint_target"],
            "C_J_M_P_self_check": "PASS",
        },
        "exit_audit": {
            "M4_P02_freeze": "PASS",
            "fresh_environment": True,
            "wheel_install": "PASS",
            "dependency_pin_mismatch_count": 0,
            "release_bundle_load": "PASS",
            "official_adapter_import": "PASS",
            "C_J_M_P_self_check": "PASS",
            "development_tree_import_count": 0,
            "credential_binding_count": 0,
            "status": "M4_P03_PASS",
        },
        "claim_boundary": {
            "allowed_claim": "M4_P03_CLEAN_INSTALL_BOOT_COMPLETE",
            "clean_full_sample_repeat_complete": False,
            "ARC3_PRODUCT_COMPLETE": False,
            "next_point": "M4-P04_CLEAN_FULL_SAMPLE_RERUN",
        },
    }
    report["logical_content_sha256"] = _sha256(_canonical_json(report))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--create", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=REPOSITORY_ROOT)
    arguments = parser.parse_args()
    root = arguments.repo_root.resolve()
    receipt = _create_install(root) if arguments.create else _load_receipt(root)
    boot = _boot(root, receipt)
    report = _build_report(root, receipt, boot)
    payload = _encoded(report)
    report_path = root / REPORT_PATH
    if arguments.create:
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_bytes(payload)
        status = "WRITTEN"
    else:
        _require(
            report_path.read_bytes() == payload,
            "M4_P03_CLEAN_INSTALL_REPORT_STALE",
        )
        status = "PASS"
    print(
        json.dumps(
            {
                "report": REPORT_PATH.as_posix(),
                "point_status": "M4_P03_PASS",
                "status": status,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
