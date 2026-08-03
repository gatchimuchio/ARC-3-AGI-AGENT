"""Validate the M4-P05 Kaggle package without creating a submission."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import zipfile
from email.parser import BytesParser
from pathlib import Path
from typing import Final, Sequence

from build_kaggle_submission import (
    ACTION_BUDGET,
    COMPETITION_SLUG,
    DEFAULT_OUTPUT_DIR,
    M4_P02_REPORT_PATH,
    M4_P04_REPORT_PATH,
    OFFICIAL_PINNED_NOTEBOOK,
    OFFICIAL_PINNED_NOTEBOOK_SOURCE_SHA256,
    OFFICIAL_PLACEHOLDER_PARQUET_SHA256,
    OFFICIAL_PLACEHOLDER_PARQUET_SIZE,
    RELEASE_BUNDLE_ID,
    RELEASE_BUNDLE_LOGICAL_DIGEST,
    RELEASE_DESCRIPTOR_SHA256,
    RELEASE_DISTRIBUTION,
    RELEASE_ENTRYPOINT,
    RELEASE_ENTRYPOINT_TARGET,
    RELEASE_INITIAL_STATE_DIGEST,
    RELEASE_J0_DIGEST,
    RELEASE_M0_DIGEST,
    RELEASE_P_DIGEST,
    RELEASE_PACKAGE_SHA256,
    RELEASE_RUNTIME_IDENTITY,
    RELEASE_VERSION,
    RELEASE_WHEEL_PATH,
    RELEASE_WHEEL_SHA256,
    ROOT,
    WHEELHOUSE_DATASET_ID,
    WHEELHOUSE_DATASET_SLUG,
    WHEELHOUSE_DATASET_SOURCE,
    WHEELHOUSE_INPUT_ROOT,
    WHEELHOUSE_MANIFEST_PATH,
    build_metadata,
    build_notebook,
)

DEFAULT_REPORT: Final = ROOT / "analysis/product/rev5_1/" / (
    "m4_p05_kaggle_package_validation.json"
)
SECRET_PATTERNS: Final = (
    ("KAGGLE_TOKEN", re.compile(rb"(?<![A-Za-z0-9_-])KGAT_[A-Za-z0-9_-]{20,}")),
    ("OPENAI_TOKEN", re.compile(rb"(?<![A-Za-z0-9_-])sk-[A-Za-z0-9_-]{20,}")),
    ("GITHUB_TOKEN", re.compile(rb"(?<![A-Za-z0-9_-])gh[pousr]_[A-Za-z0-9]{20,}")),
    ("PRIVATE_KEY", re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----")),
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _cell_source(cell: object) -> str:
    if not isinstance(cell, dict):
        raise TypeError("KAGGLE_NOTEBOOK_CELL_INVALID")
    source = cell.get("source", "")
    if isinstance(source, str):
        return source
    if isinstance(source, list) and all(isinstance(item, str) for item in source):
        return "".join(source)
    raise TypeError("KAGGLE_NOTEBOOK_CELL_SOURCE_INVALID")


def _load_object(path: Path) -> tuple[dict[str, object], bytes]:
    payload = path.read_bytes()
    value = json.loads(payload)
    if not isinstance(value, dict):
        raise TypeError("KAGGLE_VALIDATION_JSON_OBJECT_REQUIRED:" + path.as_posix())
    return {str(key): item for key, item in value.items()}, payload


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


def _require_object(value: object, error: str) -> dict[str, object]:
    if not isinstance(value, dict):
        raise TypeError(error)
    return {str(key): item for key, item in value.items()}


def _report_notebook_path(notebook_path: Path) -> str:
    try:
        return notebook_path.relative_to(ROOT).as_posix()
    except ValueError:
        return notebook_path.as_posix()


def _tracked_secret_findings() -> list[dict[str, object]]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=ROOT,
        check=True,
        capture_output=True,
    )
    findings: list[dict[str, object]] = []
    for raw_path in result.stdout.split(b"\0"):
        if not raw_path:
            continue
        relative = raw_path.decode("utf-8")
        path = ROOT / relative
        if not path.is_file() or path.stat().st_size > 10_000_000:
            continue
        data = path.read_bytes()
        if b"\0" in data:
            continue
        for name, pattern in SECRET_PATTERNS:
            count = len(pattern.findall(data))
            if count:
                findings.append(
                    {"path": relative, "pattern": name, "match_count": count}
                )
    return findings


def _preexecution_fallback_smoke(install_source: str) -> dict[str, object]:
    with tempfile.TemporaryDirectory(prefix="arc3-m4-p05-fallback-") as directory:
        root = Path(directory)
        fallback_path = root / "submission.parquet"
        status_path = root / "arc3_install_status.json"
        missing_wheelhouse = root / "missing-wheelhouse"
        transformed = (
            install_source.replace(
                'Path("/kaggle/working/submission.parquet")',
                f"Path({str(fallback_path)!r})",
            )
            .replace(
                'Path("/kaggle/working/arc3_install_status.json")',
                f"Path({str(status_path)!r})",
            )
            .replace(
                repr("/kaggle/input/" + WHEELHOUSE_DATASET_SLUG),
                repr(str(missing_wheelhouse)),
            )
            .replace(
                repr(WHEELHOUSE_INPUT_ROOT),
                repr(str(root / "isolated-kaggle-input")),
            )
        )
        script_path = root / "install_cell.py"
        script_path.write_text(transformed, encoding="utf-8", newline="\n")
        environment = os.environ.copy()
        environment["KAGGLE_IS_COMPETITION_RERUN"] = "1"
        result = subprocess.run(
            [sys.executable, str(script_path)],
            cwd=root,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        fallback: dict[str, object] = {}
        if fallback_path.is_file():
            payload = fallback_path.read_bytes()
            fallback = {
                "size_bytes": len(payload),
                "sha256": _sha256(payload),
                "parquet_magic_valid": payload[:4] == b"PAR1" and payload[-4:] == b"PAR1",
            }
        install_status: dict[str, object] = {}
        if status_path.is_file():
            install_status = json.loads(status_path.read_text(encoding="utf-8"))
            error_message = install_status.get("error_message")
            if isinstance(error_message, str):
                normalized_message = error_message
                root_variants = {
                    str(root),
                    root.as_posix(),
                    json.dumps(str(root))[1:-1],
                    json.dumps(root.as_posix())[1:-1],
                }
                for root_variant in root_variants:
                    normalized_message = normalized_message.replace(
                        root_variant,
                        "<TEMP_ROOT>",
                    )
                install_status["error_message"] = normalized_message
        visible = (
            "FileNotFoundError" in result.stderr
            and "frozen wheelhouse dataset is missing or unverified" in result.stderr
        )
        passed = (
            result.returncode == 0
            and fallback.get("size_bytes") == OFFICIAL_PLACEHOLDER_PARQUET_SIZE
            and fallback.get("sha256") == OFFICIAL_PLACEHOLDER_PARQUET_SHA256
            and fallback.get("parquet_magic_valid") is True
            and install_status.get("status") == "INSTALL_EXCEPTION"
            and install_status.get("error_type") == "FileNotFoundError"
            and visible
        )
        return {
            "passed": passed,
            "returncode": result.returncode,
            "fallback": fallback,
            "install_status": install_status,
            "expected_install_failure_visible": visible,
        }


def _release_wheel_inspection() -> dict[str, object]:
    payload = RELEASE_WHEEL_PATH.read_bytes()
    p02, _ = _load_object(M4_P02_REPORT_PATH)
    p02_wheel = _require_object(
        p02.get("wheel_artifact"),
        "KAGGLE_M4_P02_WHEEL_ARTIFACT_INVALID",
    )
    expected_names = p02_wheel.get("member_names")
    with zipfile.ZipFile(RELEASE_WHEEL_PATH) as archive:
        member_names = tuple(archive.namelist())
        metadata_names = tuple(
            name for name in member_names if name.endswith(".dist-info/METADATA")
        )
        entrypoint_names = tuple(
            name for name in member_names if name.endswith(".dist-info/entry_points.txt")
        )
        release_manifest_names = tuple(
            name
            for name in member_names
            if name.endswith(".dist-info/release_manifest.json")
        )
        if len(metadata_names) != 1 or len(entrypoint_names) != 1 or len(release_manifest_names) != 1:
            raise ValueError("KAGGLE_RELEASE_WHEEL_METADATA_CARDINALITY_INVALID")
        metadata = BytesParser().parsebytes(archive.read(metadata_names[0]))
        requirements = tuple(str(item) for item in metadata.get_all("Requires-Dist", ()))
        entrypoints = archive.read(entrypoint_names[0]).decode("utf-8")
        release_manifest = json.loads(archive.read(release_manifest_names[0]))
        descriptor = archive.read("arc3_agi_agent/bundles/arc3_product_release_v1.json")
        package = archive.read("arc3_agi_agent/bundles/arc3_product_release_v1.zip")
        runner_source = archive.read(
            "arc3_agi_agent/generic_competition_runner.py"
        ).decode("utf-8")
        product_runner_source = archive.read("arc3_agi_agent/product_runner.py").decode(
            "utf-8"
        )
    forbidden_members = tuple(
        name
        for name in member_names
        if name.startswith("arc3_agi_agent/teacher/")
        or name.startswith("analysis/")
        or name.startswith("scratch/")
    )
    return {
        "sha256": _sha256(payload),
        "size_bytes": len(payload),
        "member_count": len(member_names),
        "member_names_match_M4_P02": list(member_names) == expected_names,
        "distribution": str(metadata.get("Name", "")),
        "version": str(metadata.get("Version", "")),
        "requires_python": str(metadata.get("Requires-Python", "")),
        "requirements": requirements,
        "dependency_count": len(requirements),
        "entrypoints": entrypoints,
        "release_manifest": release_manifest,
        "release_descriptor_sha256": _sha256(descriptor),
        "release_package_sha256": _sha256(package),
        "forbidden_members": forbidden_members,
        "runner_source": runner_source,
        "product_runner_source": product_runner_source,
    }


def validate(*, notebook_dir: Path) -> dict[str, object]:
    notebook_path = notebook_dir / "submission.ipynb"
    metadata_path = notebook_dir / "kernel-metadata.json"
    build_report_path = notebook_dir / "build-report.json"
    notebook_data = notebook_path.read_bytes()
    metadata_data = metadata_path.read_bytes()
    build_report_data = build_report_path.read_bytes()
    notebook = json.loads(notebook_data)
    metadata = json.loads(metadata_data)
    build_report = json.loads(build_report_data)
    notebook_id = metadata.get("id")
    if not isinstance(notebook_id, str) or "/" not in notebook_id:
        raise ValueError("KAGGLE_NOTEBOOK_ID_INVALID")
    username, notebook_slug = notebook_id.split("/", 1)

    expected_notebook, expected_build_report = build_notebook()
    expected_metadata = build_metadata(username=username, notebook_slug=notebook_slug)
    expected_notebook_data = (
        json.dumps(expected_notebook, indent=1, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    expected_metadata_data = (
        json.dumps(expected_metadata, indent=2, ensure_ascii=False) + "\n"
    ).encode("utf-8")
    expected_build_report.update(
        {
            "notebook_sha256": _sha256(expected_notebook_data),
            "notebook_size_bytes": len(expected_notebook_data),
            "metadata_sha256": _sha256(expected_metadata_data),
            "metadata": expected_metadata,
        }
    )

    cells = notebook.get("cells")
    if not isinstance(cells, list):
        raise TypeError("KAGGLE_NOTEBOOK_CELLS_INVALID")
    cell_ids = [cell.get("id") for cell in cells if isinstance(cell, dict)]
    cell_types = [cell.get("cell_type") for cell in cells if isinstance(cell, dict)]
    sources_by_id = {
        str(cell.get("id")): _cell_source(cell)
        for cell in cells
        if isinstance(cell, dict) and isinstance(cell.get("id"), str)
    }
    install_source = sources_by_id.get("install-exact-frozen-wheelhouse", "")
    payload_source = sources_by_id.get("verify-exact-release-identity", "")
    runtime_source = sources_by_id.get("execute-frozen-product-runtime", "")
    placeholder_source = sources_by_id.get("write-official-placeholder", "")
    sources = "\n".join(_cell_source(cell) for cell in cells)
    compile_failures: list[str] = []
    for index, cell in enumerate(cells):
        if not isinstance(cell, dict) or cell.get("cell_type") != "code":
            continue
        try:
            compile(_cell_source(cell), f"submission.ipynb:code-cell-{index}", "exec")
        except SyntaxError as error:
            compile_failures.append(f"{index}:{error}")

    wheelhouse, wheelhouse_payload = _load_object(WHEELHOUSE_MANIFEST_PATH)
    p04, p04_payload = _load_object(M4_P04_REPORT_PATH)
    release = _release_wheel_inspection()
    runner_source = str(release.pop("runner_source"))
    product_runner_source = str(release.pop("product_runner_source"))
    release_manifest = _require_object(
        release.get("release_manifest"),
        "KAGGLE_RELEASE_MANIFEST_INVALID",
    )
    release_requirements = release.get("requirements")
    if not isinstance(release_requirements, tuple) or not all(
        isinstance(item, str) for item in release_requirements
    ):
        raise TypeError("KAGGLE_RELEASE_REQUIREMENTS_INVALID")
    wheelhouse_release = _require_object(
        wheelhouse.get("release_wheel"),
        "KAGGLE_WHEELHOUSE_RELEASE_INVALID",
    )
    wheelhouse_dependencies = wheelhouse.get("dependency_wheels")
    if not isinstance(wheelhouse_dependencies, list):
        raise TypeError("KAGGLE_WHEELHOUSE_DEPENDENCIES_INVALID")
    build_official_basis = _require_object(
        build_report.get("official_contract_basis"),
        "KAGGLE_BUILD_OFFICIAL_BASIS_INVALID",
    )
    build_sources = _require_object(
        build_report.get("source_bindings"),
        "KAGGLE_BUILD_SOURCE_BINDINGS_INVALID",
    )
    p04_exit = _require_object(
        p04.get("exit_audit"),
        "KAGGLE_M4_P04_EXIT_AUDIT_INVALID",
    )
    p04_sources = _require_object(
        p04.get("source_bindings"),
        "KAGGLE_M4_P04_SOURCE_BINDINGS_INVALID",
    )
    p04_release = _require_object(
        p04_sources.get("release_wheel"),
        "KAGGLE_M4_P04_RELEASE_BINDING_INVALID",
    )
    fallback_smoke = _preexecution_fallback_smoke(install_source)
    tracked_secret_findings = _tracked_secret_findings()
    notebook_secret_findings = [
        {"pattern": name, "match_count": len(pattern.findall(notebook_data))}
        for name, pattern in SECRET_PATTERNS
        if pattern.search(notebook_data)
    ]
    kaggle_metadata = (
        notebook.get("metadata", {}).get("kaggle", {})
        if isinstance(notebook.get("metadata"), dict)
        else {}
    )
    submission_markers = (
        "create_code_competition_submission",
        "kaggle competitions submit",
        "/api/v1/competitions/submissions",
    )
    checks = {
        "NB-001_SOURCE_REBUILD_EXACT": notebook == expected_notebook,
        "NB-002_METADATA_REBUILD_EXACT": metadata == expected_metadata,
        "NB-003_BUILD_REPORT_REBUILD_EXACT": build_report == expected_build_report,
        "NB-004_BUILD_DIGEST_BOUND": (
            build_report.get("notebook_sha256") == _sha256(notebook_data)
            and build_report.get("metadata_sha256") == _sha256(metadata_data)
        ),
        "NB-005_CODE_COMPILES": not compile_failures,
        "NB-006_RELEASE_WHEEL_EXACT": (
            release["sha256"] == RELEASE_WHEEL_SHA256
            and release["distribution"] == RELEASE_DISTRIBUTION
            and release["version"] == RELEASE_VERSION
            and release["requires_python"] == "==3.12.*"
            and release["member_names_match_M4_P02"] is True
            and release["forbidden_members"] == ()
        ),
        "NB-007_RELEASE_BUNDLE_EXACT": (
            release["release_descriptor_sha256"] == RELEASE_DESCRIPTOR_SHA256
            and release["release_package_sha256"] == RELEASE_PACKAGE_SHA256
            and release_manifest.get("asset_stage") == "RELEASE_FROZEN"
            and release_manifest.get("entrypoint") == RELEASE_ENTRYPOINT
            and release_manifest.get("entrypoint_target")
            == RELEASE_ENTRYPOINT_TARGET
        ),
        "NB-008_WHEELHOUSE_MANIFEST_EXACT": (
            wheelhouse.get("status") == "WHEELHOUSE_READY"
            and wheelhouse.get("logical_content_sha256") == _logical_seal(wheelhouse)
            and wheelhouse.get("dependency_count") == 32
            and wheelhouse.get("file_count") == 33
            and wheelhouse_release.get("sha256") == RELEASE_WHEEL_SHA256
            and release["dependency_count"] == 32
            and tuple(sorted(release_requirements))
            == tuple(
                sorted(
                    str(row["requirement"])
                    for row in wheelhouse_dependencies
                    if isinstance(row, dict)
                )
            )
        ),
        "NB-009_DATASET_SOURCE_EXACT": metadata.get("dataset_sources")
        == [WHEELHOUSE_DATASET_SOURCE],
        "NB-010_CPU_INTERNET_DISABLED": (
            isinstance(kaggle_metadata, dict)
            and kaggle_metadata.get("accelerator") == "none"
            and kaggle_metadata.get("isGpuEnabled") is False
            and kaggle_metadata.get("isInternetEnabled") is False
            and metadata.get("enable_gpu") is False
            and metadata.get("enable_internet") is False
        ),
        "NB-011_COMPETITION_SOURCE_EXACT": metadata.get("competition_sources")
        == [COMPETITION_SLUG],
        "NB-012_EXACT_OFFLINE_INSTALL": all(
            marker in install_source
            for marker in (
                WHEELHOUSE_DATASET_SLUG,
                WHEELHOUSE_DATASET_SOURCE,
                RELEASE_WHEEL_SHA256,
                "--no-index",
                "--no-cache-dir",
                "--no-compile",
                "--no-deps",
                "--target",
                "--force-reinstall",
                "observed_target_versions",
                "arc3_runtime_environment",
                '/tmp/arc3_runtime_env',
            )
        ),
        "NB-013_RELEASE_BOOT_IDENTITY_EXACT": all(
            marker in payload_source
            for marker in (
                RELEASE_RUNTIME_IDENTITY,
                RELEASE_BUNDLE_ID,
                RELEASE_BUNDLE_LOGICAL_DIGEST,
                RELEASE_INITIAL_STATE_DIGEST,
                RELEASE_P_DIGEST,
                RELEASE_J0_DIGEST,
                RELEASE_M0_DIGEST,
                RELEASE_ENTRYPOINT_TARGET,
                '"dependency_pin_mismatch_count": 0',
            )
        ),
        "NB-014_GATEWAY_RERUN_CONTRACT": all(
            marker in runtime_source
            for marker in (
                "KAGGLE_IS_COMPETITION_RERUN",
                "http://gateway:8001/api/games",
                '"OPERATION_MODE": "competition"',
                '"--mode"',
                '"competition"',
                '"--release-frozen"',
            )
        ),
        "NB-015_ONE_FROZEN_ENTRYPOINT": (
            RELEASE_ENTRYPOINT in runtime_source
            and "shutil.which" in runtime_source
            and '"main.py"' not in runtime_source
            and '"--agent"' not in runtime_source
            and "arc3_agi_agent.product_runner" not in runtime_source
        ),
        "NB-016_SEQUENTIAL_SCORECARD_LIFECYCLE": (
            "SEQUENTIAL_SINGLE_ACTIVE_GAME" in runner_source
            and "for game_index, game_id in enumerate(game_ids)" in runner_source
            and "active_agent_peak" in runner_source
            and "scorecard_open_count" in runner_source
            and "scorecard_close_count" in runner_source
            and "close_scorecard" in runner_source
            and "Thread(" not in runner_source
            and "SEQUENTIAL_SINGLE_ACTIVE_GAME" in runtime_source
            and '"scorecard_open_count": 1' in runtime_source
            and '"scorecard_close_count": 1' in runtime_source
            and '"scorecard_closed": True' in runtime_source
        ),
        "NB-017_GATEWAY_OWNS_SUCCESS_OUTPUT": (
            "/kaggle/working/submission.parquet" not in runtime_source
            and "to_parquet" not in runtime_source
        ),
        "NB-018_NO_SUBMISSION_SIDE_EFFECT": not any(
            marker in sources for marker in submission_markers
        ),
        "NB-019_NO_EXTERNAL_ARC_OR_LLM_ENDPOINT": not any(
            marker in sources.casefold()
            for marker in ("three.arcprize.org", "api.openai.com", "anthropic.com")
        ),
        "NB-020_NO_SECRET": not notebook_secret_findings
        and not tracked_secret_findings,
        "NB-021_CELL_IDS_UNIQUE_AND_OFFICIAL_LAYOUT": (
            cell_ids
            == [
                "install-exact-frozen-wheelhouse",
                "verify-exact-release-identity",
                "execute-frozen-product-runtime",
                "write-official-placeholder",
            ]
            and cell_types == ["code"] * 4
            and len(set(cell_ids)) == 4
        ),
        "NB-022_OFFICIAL_PLACEHOLDER_SCHEMA": all(
            marker in placeholder_source
            for marker in (
                'data=[["1_0", "1", True, 1]]',
                'columns=["row_id", "game_id", "end_of_game", "score"]',
                'if not os.getenv("KAGGLE_IS_COMPETITION_RERUN")',
                'Path("/kaggle/working/submission.parquet")',
                "index=False",
            )
        ),
        "NB-023_PREEXEC_COLLECTIBLE_FALLBACK": (
            fallback_smoke["passed"] is True
            and OFFICIAL_PLACEHOLDER_PARQUET_SHA256 in install_source
            and str(OFFICIAL_PLACEHOLDER_PARQUET_SIZE) in install_source
            and cell_ids.index("install-exact-frozen-wheelhouse")
            < cell_ids.index("execute-frozen-product-runtime")
        ),
        "NB-024_FAILURE_VISIBLE_AND_COLLECTIBLE": all(
            marker in sources
            for marker in (
                '"INSTALL_EXCEPTION"',
                '"BOOT_EXCEPTION"',
                '"RUNTIME_EXCEPTION"',
                "traceback.print_exc()",
                "/kaggle/working/arc3_install_status.json",
                "/kaggle/working/arc3_payload_status.json",
                "/kaggle/working/arc3_runtime_status.json",
            )
        ),
        "NB-025_NO_UNDOCUMENTED_RUNTIME_LIMIT": (
            "timeout=36_000" not in runtime_source
            and "timeout=36000" not in runtime_source
            and "MAX_WALL" not in sources
            and "WALL_TIME" not in sources
            and "subprocess.run(" in runtime_source
            and "check=False" in runtime_source
        ),
        "NB-026_NOTEBOOK_FORMAT_MATCHES_OFFICIAL": (
            notebook.get("nbformat") == 4
            and notebook.get("nbformat_minor") == 4
            and build_official_basis.get("pinned_notebook") == OFFICIAL_PINNED_NOTEBOOK
            and build_official_basis.get("pinned_notebook_source_sha256")
            == OFFICIAL_PINNED_NOTEBOOK_SOURCE_SHA256
        ),
        "NB-027_SAME_M4_P04_RELEASE": (
            p04.get("status") == "M4_P04_PASS"
            and p04_exit.get("same_release_artifact") is True
            and p04_release.get("sha256") == RELEASE_WHEEL_SHA256
            and build_sources.get("M4_P04_same_release_full_sample_sha256")
            == _sha256(p04_payload)
        ),
        "NB-028_NO_RUNTIME_REPACKAGING": (
            "copytree" not in sources
            and "agent_payload" not in sources
            and "runtime_archive" not in sources
            and "generic_agi_agent.py" not in sources
            and "arc3_completion_agent.py" not in sources
        ),
        "NB-029_NO_INPUT_MUTATION": (
            "wheelhouse_root.write" not in install_source
            and "(wheelhouse_root / filename).write" not in install_source
            and "manifest_path.write" not in install_source
            and "shutil.copy" not in sources
        ),
        "NB-030_PRODUCT_EXIT_BOUNDARY_PRESERVED": (
            'if mode == "competition"' in product_runner_source
            and "return 0" in product_runner_source
            and "official scorecard" in product_runner_source
        ),
        "NB-031_ACTION_BUDGET_FROZEN": (
            ACTION_BUDGET == 4096
            and '"--action-budget"' in runtime_source
            and "4096" in runtime_source
        ),
        "NB-032_RUNTIME_POLICY_UNCHANGED": (
            build_report.get("runtime_policy_changed") is False
            and wheelhouse.get("runtime_policy_changed") is False
            and "/kaggle/working/arc3_runtime_env" not in sources
        ),
    }
    return {
        "schema_version": "arc3-rev5-1-m4-p05-kaggle-package-validation-v1",
        "artifact_type": "M4KagglePackageValidationEvidence",
        "point_id": "M4-P05_KAGGLE_PACKAGE_NORMAL_RUN",
        "runtime_product": "ARC3CompletionAgent",
        "asset_stage": "RELEASE_FROZEN",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "passed_check_count": sum(checks.values()),
        "check_count": len(checks),
        "failed_check_ids": [name for name, passed in checks.items() if not passed],
        "notebook": {
            "path": _report_notebook_path(notebook_path),
            "id": notebook_id,
            "sha256": _sha256(notebook_data),
            "size_bytes": len(notebook_data),
            "cell_count": len(cells),
        },
        "metadata_sha256": _sha256(metadata_data),
        "build_report_sha256": _sha256(build_report_data),
        "wheelhouse_manifest": {
            "path": WHEELHOUSE_MANIFEST_PATH.relative_to(ROOT).as_posix(),
            "sha256": _sha256(wheelhouse_payload),
            "logical_content_sha256": wheelhouse.get("logical_content_sha256"),
            "dataset_id": WHEELHOUSE_DATASET_ID,
            "dataset_source": WHEELHOUSE_DATASET_SOURCE,
            "dependency_count": wheelhouse.get("dependency_count"),
            "file_count": wheelhouse.get("file_count"),
            "total_size_bytes": wheelhouse.get("total_size_bytes"),
        },
        "release_wheel": release,
        "M4_P04_same_release_full_sample": {
            "path": M4_P04_REPORT_PATH.relative_to(ROOT).as_posix(),
            "sha256": _sha256(p04_payload),
            "status": p04.get("status"),
        },
        "compile_failures": compile_failures,
        "preexecution_fallback_smoke": fallback_smoke,
        "notebook_secret_findings": notebook_secret_findings,
        "tracked_secret_findings": tracked_secret_findings,
        "secret_finding_count": len(notebook_secret_findings)
        + len(tracked_secret_findings),
        "submission_api_call_count": 0,
        "runtime_policy_changed": False,
    }


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--notebook-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    report = validate(notebook_dir=arguments.notebook_dir.resolve())
    report_path = arguments.report.resolve()
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(
        json.dumps(report, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    print(json.dumps(report, indent=2, sort_keys=True))
    return 0 if report["status"] == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
