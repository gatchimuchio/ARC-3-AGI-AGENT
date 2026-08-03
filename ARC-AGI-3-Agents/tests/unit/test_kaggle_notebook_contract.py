from __future__ import annotations

import ast
import importlib.util
import json
import sys
from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SCRIPTS_ROOT = REPOSITORY_ROOT / "scripts"


def _load_script(name: str, filename: str) -> object:
    path = SCRIPTS_ROOT / filename
    spec = importlib.util.spec_from_file_location(name, path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.path.insert(0, str(SCRIPTS_ROOT))
    try:
        spec.loader.exec_module(module)
    finally:
        sys.path.remove(str(SCRIPTS_ROOT))
    return module


BUILDER = _load_script("arc3_m4_p05_kaggle_builder", "build_kaggle_submission.py")
VALIDATOR = _load_script(
    "arc3_m4_p05_kaggle_validator",
    "validate_kaggle_submission.py",
)
WHEELHOUSE = _load_script(
    "arc3_m4_p05_wheelhouse_builder",
    "build_rev5_1_m4_p05_wheelhouse.py",
)


def _sources_by_id(notebook: dict[str, object]) -> dict[str, str]:
    cells = notebook["cells"]
    assert isinstance(cells, list)
    return {
        str(cell["id"]): str(cell["source"])
        for cell in cells
        if isinstance(cell, dict)
    }


def test_m4_p05_notebook_uses_exact_frozen_wheelhouse() -> None:
    notebook, report = BUILDER.build_notebook()
    cells = notebook["cells"]
    assert isinstance(cells, list)
    assert notebook["nbformat"] == 4
    assert notebook["nbformat_minor"] == 4
    assert [cell["cell_type"] for cell in cells] == ["code"] * 4
    assert [cell["id"] for cell in cells] == [
        "install-exact-frozen-wheelhouse",
        "verify-exact-release-identity",
        "execute-frozen-product-runtime",
        "write-official-placeholder",
    ]

    sources = _sources_by_id(notebook)
    install = sources["install-exact-frozen-wheelhouse"]
    assert BUILDER.WHEELHOUSE_DATASET_SLUG in install
    assert BUILDER.WHEELHOUSE_DATASET_SOURCE in install
    assert "visible_input_entries" in install
    assert "MANIFEST" in install
    assert BUILDER.RELEASE_WHEEL_SHA256 in install
    assert '"--no-index"' in install
    assert '"--no-cache-dir"' in install
    assert '"--no-compile"' in install
    assert '"--no-deps"' in install
    assert '"--target"' in install
    assert '"--force-reinstall"' in install
    assert "observed_target_versions" in install
    assert "arc3_runtime_environment" in install
    assert '/tmp/arc3_runtime_env' in install
    assert '/kaggle/working/arc3_runtime_env' not in install
    assert "base64.b64decode" in install
    assert BUILDER.OFFICIAL_PLACEHOLDER_PARQUET_SHA256 in install
    assert str(BUILDER.OFFICIAL_PLACEHOLDER_PARQUET_SIZE) in install
    assert '"INSTALL_EXCEPTION"' in install

    payload = sources["verify-exact-release-identity"]
    assert BUILDER.RELEASE_RUNTIME_IDENTITY in payload
    assert BUILDER.RELEASE_PACKAGE_SHA256 in payload
    assert BUILDER.RELEASE_BUNDLE_ID in payload
    assert BUILDER.RELEASE_ENTRYPOINT_TARGET in payload
    assert '"dependency_pin_mismatch_count": 0' in payload
    assert '"BOOT_EXCEPTION"' in payload

    runtime = sources["execute-frozen-product-runtime"]
    assert "http://gateway:8001/api/games" in runtime
    assert '"OPERATION_MODE": "competition"' in runtime
    assert '"--release-frozen"' in runtime
    assert '"--action-budget"' in runtime
    assert "shutil.which" in runtime
    assert '"main.py"' not in runtime
    assert '"--agent"' not in runtime
    assert "to_parquet" not in runtime
    subprocess_calls = [
        node
        for node in ast.walk(ast.parse(runtime))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "subprocess"
        and node.func.attr == "run"
    ]
    assert len(subprocess_calls) == 1
    assert all(keyword.arg != "timeout" for keyword in subprocess_calls[0].keywords)
    assert any(
        keyword.arg == "check"
        and isinstance(keyword.value, ast.Constant)
        and keyword.value.value is False
        for keyword in subprocess_calls[0].keywords
    )

    placeholder = sources["write-official-placeholder"]
    assert 'data=[["1_0", "1", True, 1]]' in placeholder
    assert 'columns=["row_id", "game_id", "end_of_game", "score"]' in placeholder
    assert 'Path("/kaggle/working/submission.parquet")' in placeholder
    assert "index=False" in placeholder
    assert report["release_artifact"]["wheel_sha256"] == BUILDER.RELEASE_WHEEL_SHA256
    assert report["dependency_transport"]["dependency_count"] == 32
    assert report["submission_api_call_count"] == 0
    assert report["runtime_policy_changed"] is False


def test_m4_p05_metadata_binds_only_required_inputs() -> None:
    metadata = BUILDER.build_metadata(
        username="owner",
        notebook_slug="candidate",
    )
    assert metadata["id"] == "owner/candidate"
    assert metadata["dataset_sources"] == [BUILDER.WHEELHOUSE_DATASET_SOURCE]
    assert metadata["competition_sources"] == [BUILDER.COMPETITION_SLUG]
    assert metadata["kernel_sources"] == []
    assert metadata["model_sources"] == []
    assert metadata["enable_gpu"] is False
    assert metadata["enable_tpu"] is False
    assert metadata["enable_internet"] is False


def test_m4_p05_release_wheel_matches_freeze_and_runtime_contract() -> None:
    inspection = VALIDATOR._release_wheel_inspection()
    assert inspection["sha256"] == BUILDER.RELEASE_WHEEL_SHA256
    assert inspection["distribution"] == BUILDER.RELEASE_DISTRIBUTION
    assert inspection["version"] == BUILDER.RELEASE_VERSION
    assert inspection["requires_python"] == "==3.12.*"
    assert inspection["dependency_count"] == 32
    assert inspection["member_count"] == 64
    assert inspection["member_names_match_M4_P02"] is True
    assert inspection["forbidden_members"] == ()
    assert inspection["release_descriptor_sha256"] == BUILDER.RELEASE_DESCRIPTOR_SHA256
    assert inspection["release_package_sha256"] == BUILDER.RELEASE_PACKAGE_SHA256
    assert BUILDER.RELEASE_ENTRYPOINT in inspection["entrypoints"]
    assert BUILDER.RELEASE_ENTRYPOINT_TARGET in inspection["entrypoints"]


def test_m4_p05_wheelhouse_manifest_is_logically_sealed() -> None:
    manifest = json.loads(BUILDER.WHEELHOUSE_MANIFEST_PATH.read_text(encoding="utf-8"))
    assert manifest["status"] == "WHEELHOUSE_READY"
    assert manifest["dataset"]["id"] == BUILDER.WHEELHOUSE_DATASET_ID
    assert manifest["dependency_count"] == 32
    assert manifest["file_count"] == 33
    assert len(manifest["all_file_sha256"]) == 33
    assert manifest["release_wheel"]["sha256"] == BUILDER.RELEASE_WHEEL_SHA256
    assert manifest["logical_content_sha256"] == VALIDATOR._logical_seal(manifest)
    assert WHEELHOUSE._logical_seal(manifest) == manifest["logical_content_sha256"]


def test_m4_p05_preexecution_failure_remains_collectible() -> None:
    notebook, _ = BUILDER.build_notebook()
    install = _sources_by_id(notebook)["install-exact-frozen-wheelhouse"]
    result = VALIDATOR._preexecution_fallback_smoke(install)
    assert result["passed"] is True
    assert result["returncode"] == 0
    assert result["fallback"] == {
        "size_bytes": BUILDER.OFFICIAL_PLACEHOLDER_PARQUET_SIZE,
        "sha256": BUILDER.OFFICIAL_PLACEHOLDER_PARQUET_SHA256,
        "parquet_magic_valid": True,
    }
    assert result["install_status"]["status"] == "INSTALL_EXCEPTION"
    assert result["install_status"]["error_type"] == "FileNotFoundError"
    assert "<TEMP_ROOT>" in result["install_status"]["error_message"]
    assert "arc3-m4-p05-fallback-" not in result["install_status"]["error_message"]


def test_m4_p05_validator_accepts_generated_package(tmp_path: Path) -> None:
    assert BUILDER.main(["--output-dir", str(tmp_path)]) == 0
    report = VALIDATOR.validate(notebook_dir=tmp_path)
    assert report["status"] == "PASS"
    assert report["passed_check_count"] == 32
    assert report["check_count"] == 32
    assert report["failed_check_ids"] == []
    assert report["secret_finding_count"] == 0
    assert report["submission_api_call_count"] == 0


def test_kaggle_validator_accepts_external_notebook_report_path() -> None:
    external_path = (
        Path(REPOSITORY_ROOT.anchor)
        / "arc3-external-validation"
        / "submission.ipynb"
    )
    assert VALIDATOR._report_notebook_path(external_path) == external_path.as_posix()
