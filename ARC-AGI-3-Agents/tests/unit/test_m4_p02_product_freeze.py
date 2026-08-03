from __future__ import annotations

import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from arc3_agi_agent.product_freeze import (
    RELEASE_ENTRYPOINT,
    RELEASE_ENTRYPOINT_TARGET,
    RELEASE_WHEEL_FILENAME,
    ReleaseResourceBuild,
    ReleaseWheelBuild,
    build_official_sample_resource_archive,
    build_release_wheel,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_ROOT = REPOSITORY_ROOT / "ARC-AGI-3-Agents"
BUNDLE_DIRECTORY = PACKAGE_ROOT / "arc3_agi_agent" / "bundles"
RELEASE_DESCRIPTOR = BUNDLE_DIRECTORY / "arc3_product_release_v1.json"
RELEASE_PACKAGE = BUNDLE_DIRECTORY / "arc3_product_release_v1.zip"


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


@pytest.fixture(scope="module")
def frozen_artifacts() -> tuple[ReleaseWheelBuild, ReleaseResourceBuild]:
    return (
        build_release_wheel(
            package_root=PACKAGE_ROOT,
            release_descriptor_payload=RELEASE_DESCRIPTOR.read_bytes(),
            release_package_payload=RELEASE_PACKAGE.read_bytes(),
        ),
        build_official_sample_resource_archive(
            REPOSITORY_ROOT / "environment_files"
        ),
    )


def test_runtime_source_closure_excludes_development_paths(
    frozen_artifacts: tuple[ReleaseWheelBuild, ReleaseResourceBuild],
) -> None:
    wheel, _ = frozen_artifacts
    closure = wheel.source_closure

    assert closure.dynamic_import_count == 0
    assert "arc3_agi_agent.product_runner" in closure.module_names
    assert "agents.templates.arc3_completion_agent" in closure.module_names
    assert not any(".teacher" in module for module in closure.module_names)
    assert not any(".p10_" in module for module in closure.module_names)
    assert len(closure.module_names) == 55
    assert len(wheel.dependencies) == 32
    assert any(pin.requirement == "arc-agi==0.9.8" for pin in wheel.dependencies)


def test_release_wheel_is_installable_shape_and_content_bound(
    frozen_artifacts: tuple[ReleaseWheelBuild, ReleaseResourceBuild],
) -> None:
    wheel, _ = frozen_artifacts
    assert RELEASE_WHEEL_FILENAME.endswith("-py3-none-any.whl")
    wheel_again = build_release_wheel(
        package_root=PACKAGE_ROOT,
        release_descriptor_payload=RELEASE_DESCRIPTOR.read_bytes(),
        release_package_payload=RELEASE_PACKAGE.read_bytes(),
    )
    assert wheel.payload == wheel_again.payload
    assert wheel.logical_digest == wheel_again.logical_digest

    wheel_path = REPOSITORY_ROOT / "release" / "rev5_1" / RELEASE_WHEEL_FILENAME
    assert _sha256(wheel.payload) == _sha256(wheel_path.read_bytes())
    with zipfile.ZipFile(wheel_path) as archive:
        names = set(archive.namelist())
        assert "arc3_agi_agent/product_runner.py" in names
        assert "agents/templates/arc3_completion_agent.py" in names
        assert "arc3_agi_agent/bundles/arc3_product_release_v1.zip" in names
        assert not any("teacher/" in name for name in names)
        entry_points = archive.read(
            "arc3_completion_agent_release-0.1.0.dist-info/entry_points.txt"
        ).decode("utf-8")
        assert entry_points.count("=") == 1
        assert f"{RELEASE_ENTRYPOINT} = {RELEASE_ENTRYPOINT_TARGET}" in entry_points


def test_official_sample_resource_archive_is_exact_and_deterministic(
    frozen_artifacts: tuple[ReleaseWheelBuild, ReleaseResourceBuild],
) -> None:
    _, resources = frozen_artifacts
    resource_again = build_official_sample_resource_archive(
        REPOSITORY_ROOT / "environment_files"
    )
    assert resources.payload == resource_again.payload
    assert resources.logical_digest == resource_again.logical_digest
    assert len({name.split("/", 2)[1] for name in resources.member_names}) == 25

    report = json.loads(
        (
            REPOSITORY_ROOT
            / "analysis"
            / "product"
            / "rev5_1"
            / "m4_p02_freeze_manifest.json"
        ).read_text(encoding="utf-8")
    )
    assert report["status"] == "M4_P02_PASS"
    assert report["exit_audit"]["runtime_source_closure"] == "FROZEN"
    assert report["exit_audit"]["dependency_lock"] == "FROZEN"
    assert report["exit_audit"]["resource_and_adapter_config"] == "FROZEN"
    assert report["security_audit"]["credential_binding_count"] == 0
