#!/usr/bin/env python3
"""Freeze code, dependencies, resources, adapter, and entrypoint for M4-P02."""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
import sys
import zipfile
from pathlib import Path
from typing import Final

REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[1]
PACKAGE_ROOT: Final = REPOSITORY_ROOT / "ARC-AGI-3-Agents"
sys.path.insert(0, str(PACKAGE_ROOT))

from arc3_agi_agent.product_freeze import (  # noqa: E402
    PRODUCT_FREEZE_SCHEMA_VERSION,
    RELEASE_ENTRYPOINT,
    RELEASE_ENTRYPOINT_TARGET,
    RELEASE_RESOURCE_FILENAME,
    RELEASE_WHEEL_FILENAME,
    build_official_sample_resource_archive,
    build_release_wheel,
)
from arc3_agi_agent.product_release import (  # noqa: E402
    PRODUCT_RELEASE_BUNDLE_ID,
    PRODUCT_RELEASE_STAGE,
    load_product_release_bundle_payloads,
)

M4_P01_REPORT_PATH: Final = Path(
    "analysis/product/rev5_1/m4_p01_release_bundle_compilation.json"
)
RELEASE_DESCRIPTOR_PATH: Final = Path(
    "ARC-AGI-3-Agents/arc3_agi_agent/bundles/arc3_product_release_v1.json"
)
RELEASE_PACKAGE_PATH: Final = Path(
    "ARC-AGI-3-Agents/arc3_agi_agent/bundles/arc3_product_release_v1.zip"
)
PYPROJECT_PATH: Final = Path("ARC-AGI-3-Agents/pyproject.toml")
UV_LOCK_PATH: Final = Path("ARC-AGI-3-Agents/uv.lock")
ENVIRONMENTS_PATH: Final = Path("environment_files")
RELEASE_DIRECTORY: Final = Path("release/rev5_1")
WHEEL_PATH: Final = RELEASE_DIRECTORY / RELEASE_WHEEL_FILENAME
RESOURCE_ARCHIVE_PATH: Final = RELEASE_DIRECTORY / RELEASE_RESOURCE_FILENAME
REPORT_PATH: Final = Path("analysis/product/rev5_1/m4_p02_freeze_manifest.json")
IMPLEMENTATION_PATHS: Final = (
    Path("ARC-AGI-3-Agents/arc3_agi_agent/product_freeze.py"),
    Path("ARC-AGI-3-Agents/arc3_agi_agent/product_release.py"),
    Path("ARC-AGI-3-Agents/arc3_agi_agent/product_runner.py"),
    Path("scripts/build_rev5_1_m4_p02_freeze.py"),
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


def _source_bindings(root: Path) -> list[dict[str, object]]:
    return [
        {
            "path": path.as_posix(),
            "sha256": _sha256((root / path).read_bytes()),
        }
        for path in IMPLEMENTATION_PATHS
    ]


def build_artifacts(
    root: Path = REPOSITORY_ROOT,
) -> tuple[bytes, bytes, bytes]:
    p01, p01_payload = _load_object(
        root / M4_P01_REPORT_PATH,
        "M4_P02_P01_REPORT_OBJECT_REQUIRED",
    )
    p01_logical_sha = _verify_logical_seal(
        p01,
        "M4_P02_P01_REPORT_LOGICAL_SEAL_INVALID",
    )
    p01_exit = p01.get("exit_audit")
    if not isinstance(p01_exit, dict):
        raise TypeError("M4_P02_P01_EXIT_AUDIT_REQUIRED")
    _require(
        p01.get("status") == "M4_P01_PASS"
        and p01.get("asset_stage") == PRODUCT_RELEASE_STAGE
        and p01_exit.get("release_product_bundle_count") == 1
        and p01_exit.get("release_bundle_load") == "PASS"
        and p01_exit.get("deterministic_archive_rebuild") == "BYTE_IDENTICAL"
        and p01_exit.get("included_non_release_asset_count") == 0
        and p01_exit.get("identity_replay_finding_count") == 0,
        "M4_P02_P01_GATE_FAILED",
    )
    release_descriptor_payload = (root / RELEASE_DESCRIPTOR_PATH).read_bytes()
    release_package_payload = (root / RELEASE_PACKAGE_PATH).read_bytes()
    loaded_release = load_product_release_bundle_payloads(
        descriptor_payload=release_descriptor_payload,
        package_payload=release_package_payload,
    )
    _require(
        loaded_release.descriptor.get("product_bundle_id")
        == PRODUCT_RELEASE_BUNDLE_ID
        and loaded_release.descriptor.get("asset_stage")
        == PRODUCT_RELEASE_STAGE,
        "M4_P02_RELEASE_ARTIFACT_INVALID",
    )
    wheel_a = build_release_wheel(
        package_root=root / "ARC-AGI-3-Agents",
        release_descriptor_payload=release_descriptor_payload,
        release_package_payload=release_package_payload,
    )
    wheel_b = build_release_wheel(
        package_root=root / "ARC-AGI-3-Agents",
        release_descriptor_payload=release_descriptor_payload,
        release_package_payload=release_package_payload,
    )
    _require(
        wheel_a.payload == wheel_b.payload
        and wheel_a.logical_digest == wheel_b.logical_digest,
        "M4_P02_WHEEL_REBUILD_NOT_BYTE_IDENTICAL",
    )
    resource_a = build_official_sample_resource_archive(
        root / ENVIRONMENTS_PATH
    )
    resource_b = build_official_sample_resource_archive(
        root / ENVIRONMENTS_PATH
    )
    _require(
        resource_a.payload == resource_b.payload
        and resource_a.logical_digest == resource_b.logical_digest,
        "M4_P02_RESOURCE_REBUILD_NOT_BYTE_IDENTICAL",
    )
    with zipfile.ZipFile(root / RELEASE_PACKAGE_PATH) as release_archive:
        resource_contract = json.loads(
            release_archive.read("config/resource_contract.json")
        )
        adapter_config = json.loads(
            release_archive.read("config/official_adapter.json")
        )
        planner_config = json.loads(release_archive.read("config/planner.json"))
    if not all(
        isinstance(value, dict)
        for value in (resource_contract, adapter_config, planner_config)
    ):
        raise TypeError("M4_P02_RELEASE_CONFIG_OBJECT_REQUIRED")
    game_directories = tuple(
        sorted(
            path.name
            for path in (root / ENVIRONMENTS_PATH).iterdir()
            if path.is_dir()
        )
    )
    _require(
        len(game_directories) == 25
        and len(resource_a.member_names) > 25
        and wheel_a.source_closure.dynamic_import_count == 0
        and len(wheel_a.source_closure.module_names) > 0
        and len(wheel_a.dependencies) > 0
        and resource_contract.get("action_budget_per_episode") == 4096
        and resource_contract.get("no_progress_limit") == 650
        and adapter_config.get("orchestration_identity_to_decision_context")
        is False
        and planner_config.get("hds_authorization_required") is True
        and planner_config.get("fixed_trajectory_playback") is False
        and planner_config.get("identity_selected_plan") is False,
        "M4_P02_FREEZE_CONTRACT_INVALID",
    )
    pyproject_payload = (root / PYPROJECT_PATH).read_bytes()
    uv_lock_payload = (root / UV_LOCK_PATH).read_bytes()
    report: dict[str, object] = {
        "schema_version": PRODUCT_FREEZE_SCHEMA_VERSION,
        "artifact_type": "M4CodeDependencyResourceFreezeEvidence",
        "point_id": "M4-P02_CODE_DEPENDENCY_RESOURCE_FREEZE",
        "runtime_product": "ARC3CompletionAgent",
        "asset_stage": PRODUCT_RELEASE_STAGE,
        "status": "M4_P02_PASS",
        "source_bindings": {
            "M4_P01_release_compilation": {
                "path": M4_P01_REPORT_PATH.as_posix(),
                "sha256": _sha256(p01_payload),
                "logical_content_sha256": p01_logical_sha,
            },
            "release_descriptor": {
                "path": RELEASE_DESCRIPTOR_PATH.as_posix(),
                "sha256": _sha256(release_descriptor_payload),
            },
            "release_package": {
                "path": RELEASE_PACKAGE_PATH.as_posix(),
                "sha256": _sha256(release_package_payload),
            },
            "freeze_implementation": _source_bindings(root),
        },
        "runtime_source_freeze": {
            "status": "FROZEN",
            "source_tree_digest": wheel_a.source_closure.source_tree_digest,
            "root_modules": (
                "agents.templates.arc3_completion_agent",
                "arc3_agi_agent.product_runner",
            ),
            "runtime_module_count": len(wheel_a.source_closure.module_names),
            "runtime_modules": wheel_a.source_closure.module_names,
            "source_member_count": len(wheel_a.source_closure.source_members),
            "source_members": tuple(
                {
                    "path": name,
                    "sha256": _sha256(payload),
                    "size_bytes": len(payload),
                }
                for name, payload in wheel_a.source_closure.source_members
            ),
            "external_import_roots": (
                wheel_a.source_closure.external_import_roots
            ),
            "dynamic_import_count": wheel_a.source_closure.dynamic_import_count,
            "development_tree_included": False,
            "teacher_package_included": False,
        },
        "dependency_freeze": {
            "status": "FROZEN",
            "python_implementation": sys.implementation.name,
            "python_version": platform.python_version(),
            "python_cache_tag": sys.implementation.cache_tag,
            "platform_system": platform.system(),
            "platform_machine": platform.machine(),
            "requires_python": "==3.12.*",
            "pyproject_path": PYPROJECT_PATH.as_posix(),
            "pyproject_sha256": _sha256(pyproject_payload),
            "uv_lock_path": UV_LOCK_PATH.as_posix(),
            "uv_lock_sha256": _sha256(uv_lock_payload),
            "runtime_dependency_count": len(wheel_a.dependencies),
            "runtime_dependency_pins": tuple(
                dependency.requirement for dependency in wheel_a.dependencies
            ),
            "new_dependency_count": 0,
        },
        "wheel_artifact": {
            "path": WHEEL_PATH.as_posix(),
            "sha256": _sha256(wheel_a.payload),
            "size_bytes": len(wheel_a.payload),
            "logical_digest": wheel_a.logical_digest,
            "member_count": len(wheel_a.member_names),
            "member_names": wheel_a.member_names,
            "deterministic_rebuild": "BYTE_IDENTICAL",
            "embedded_release_descriptor_sha256": _sha256(
                release_descriptor_payload
            ),
            "embedded_release_package_sha256": _sha256(release_package_payload),
        },
        "resource_freeze": {
            "status": "FROZEN",
            "path": RESOURCE_ARCHIVE_PATH.as_posix(),
            "sha256": _sha256(resource_a.payload),
            "size_bytes": len(resource_a.payload),
            "logical_digest": resource_a.logical_digest,
            "member_count": len(resource_a.member_names),
            "official_sample_game_directory_count": len(game_directories),
            "official_sample_game_directories": game_directories,
            "deterministic_rebuild": "BYTE_IDENTICAL",
            "action_budget_per_episode": resource_contract[
                "action_budget_per_episode"
            ],
            "no_progress_limit": resource_contract["no_progress_limit"],
        },
        "adapter_planner_freeze": {
            "status": "FROZEN",
            "adapter_config": adapter_config,
            "planner_config": planner_config,
            "release_manifest_logical_digest": loaded_release.logical_digest,
        },
        "entrypoint_freeze": {
            "entrypoint_count": 1,
            "entrypoint": RELEASE_ENTRYPOINT,
            "entrypoint_target": RELEASE_ENTRYPOINT_TARGET,
            "module_target": "arc3_agi_agent.product_runner:main",
            "release_selector": "--release-frozen",
            "reconstruction_path_count": 1,
            "execution_template": (
                "arc3-completion-product --mode offline --release-frozen "
                "--environments-dir <environment_files> "
                "--recordings-dir <recordings> --action-budget 4096 "
                "--report <report.json>"
            ),
        },
        "security_audit": {
            "credential_binding_count": 0,
            "secret_member_count": 0,
            "external_cache_binding_count": 0,
            "recording_member_count": 0,
            "P05_candidate_included": False,
            "identity_router_included": False,
            "fixed_trajectory_included": False,
        },
        "exit_audit": {
            "M4_P01_release_bundle": "PASS",
            "runtime_source_closure": "FROZEN",
            "dependency_lock": "FROZEN",
            "resource_and_adapter_config": "FROZEN",
            "entrypoint_count": 1,
            "reconstruction_path_count": 1,
            "credential_binding_count": 0,
            "status": "M4_P02_PASS",
        },
        "claim_boundary": {
            "allowed_claim": "M4_P02_CODE_DEPENDENCY_RESOURCE_FREEZE_COMPLETE",
            "clean_install_complete": False,
            "clean_full_sample_repeat_complete": False,
            "ARC3_PRODUCT_COMPLETE": False,
            "next_point": "M4-P03_CLEAN_INSTALL",
        },
    }
    report["logical_content_sha256"] = _sha256(_canonical_json(report))
    return wheel_a.payload, resource_a.payload, _encoded(report)


def _write(root: Path, payloads: tuple[bytes, bytes, bytes]) -> None:
    for relative, payload in zip(
        (WHEEL_PATH, RESOURCE_ARCHIVE_PATH, REPORT_PATH),
        payloads,
        strict=True,
    ):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(payload)


def _check(root: Path, payloads: tuple[bytes, bytes, bytes]) -> None:
    for relative, expected in zip(
        (WHEEL_PATH, RESOURCE_ARCHIVE_PATH, REPORT_PATH),
        payloads,
        strict=True,
    ):
        _require(
            (root / relative).read_bytes() == expected,
            "M4_P02_FREEZE_ARTIFACT_STALE:" + relative.as_posix(),
        )


def main() -> int:
    parser = argparse.ArgumentParser()
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    parser.add_argument("--repo-root", type=Path, default=REPOSITORY_ROOT)
    arguments = parser.parse_args()
    root = arguments.repo_root.resolve()
    payloads = build_artifacts(root)
    if arguments.write:
        _write(root, payloads)
        status = "WRITTEN"
    else:
        _check(root, payloads)
        status = "PASS"
    print(
        json.dumps(
            {
                "wheel": WHEEL_PATH.as_posix(),
                "resources": RESOURCE_ARCHIVE_PATH.as_posix(),
                "report": REPORT_PATH.as_posix(),
                "point_status": "M4_P02_PASS",
                "status": status,
            },
            ensure_ascii=False,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
