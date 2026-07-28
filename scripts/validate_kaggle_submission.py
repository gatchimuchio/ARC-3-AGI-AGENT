"""Validate the ARC-AGI-3 notebook without consuming a submission slot."""

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
from pathlib import Path
from typing import Sequence

from build_kaggle_submission import (
    ACTION_BUDGET,
    AGENT_SOURCE,
    COMPETITION_SLUG,
    DEFAULT_OUTPUT_DIR,
    RUNTIME_MODULES,
    build_metadata,
    build_notebook,
    build_runtime_archive,
)

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "analysis" / "official" / (
    "KAGGLE_NOTEBOOK_VALIDATION.json"
)
SECRET_PATTERNS = (
    (
        "KAGGLE_TOKEN",
        re.compile(rb"(?<![A-Za-z0-9_-])KGAT_[A-Za-z0-9_-]{20,}"),
    ),
    (
        "OPENAI_TOKEN",
        re.compile(rb"(?<![A-Za-z0-9_-])sk-[A-Za-z0-9_-]{20,}"),
    ),
    (
        "GITHUB_TOKEN",
        re.compile(rb"(?<![A-Za-z0-9_-])gh[pousr]_[A-Za-z0-9]{20,}"),
    ),
    (
        "PRIVATE_KEY",
        re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    ),
)


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _cell_source(cell: object) -> str:
    if not isinstance(cell, dict):
        raise TypeError("KAGGLE_NOTEBOOK_CELL_INVALID")
    source = cell.get("source", "")
    if isinstance(source, str):
        return source
    if isinstance(source, list) and all(
        isinstance(item, str) for item in source
    ):
        return "".join(source)
    raise TypeError("KAGGLE_NOTEBOOK_CELL_SOURCE_INVALID")


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
                    {
                        "path": relative,
                        "pattern": name,
                        "match_count": count,
                    }
                )
    return findings


def _runtime_import_smoke(runtime_archive: bytes) -> dict[str, object]:
    with tempfile.TemporaryDirectory(
        prefix="arc3-kaggle-runtime-validation-"
    ) as directory:
        root = Path(directory)
        archive_path = root / "runtime.zip"
        archive_path.write_bytes(runtime_archive)
        with zipfile.ZipFile(archive_path) as archive:
            archive.extractall(root)
        command = dedent_smoke_command()
        environment = os.environ.copy()
        environment["PYTHONPATH"] = str(root)
        result = subprocess.run(
            [sys.executable, "-c", command],
            cwd=root,
            env=environment,
            check=False,
            capture_output=True,
            text=True,
            timeout=120,
        )
        return {
            "returncode": result.returncode,
            "stdout": result.stdout.strip(),
            "stderr": result.stderr.strip(),
            "passed": result.returncode == 0
            and result.stdout.strip() == "WIN:2:True:False",
        }


def dedent_smoke_command() -> str:
    return (
        "from arc3_agi_agent.generic_compute import "
        "HybridRelationalInstructionBody\n"
        "from arc3_agi_agent.generic_env import MechanismWorld\n"
        "from arc3_agi_agent.generic_runtime import "
        "GenericAGIRuntime, GenericRuntimeConfiguration\n"
        "report = GenericAGIRuntime("
        "MechanismWorld((11, 29, 47), (1,), required_progress=2), "
        "HybridRelationalInstructionBody(), "
        "GenericRuntimeConfiguration(max_cycles=16)).run()\n"
        "print(f'{report.final_state}:{report.progress_count}:'"
        "f'{report.no_fallback_used}:{report.runtime_identity_received}')\n"
    )


def validate(
    *,
    notebook_dir: Path,
) -> dict[str, object]:
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
    expected_metadata = build_metadata(
        username=username,
        notebook_slug=notebook_slug,
    )
    cells = notebook.get("cells")
    if not isinstance(cells, list):
        raise TypeError("KAGGLE_NOTEBOOK_CELLS_INVALID")
    cell_ids = [
        cell.get("id")
        for cell in cells
        if isinstance(cell, dict)
    ]
    cell_types = [
        cell.get("cell_type")
        for cell in cells
        if isinstance(cell, dict)
    ]
    cell_sources_by_id = {
        str(cell.get("id")): _cell_source(cell)
        for cell in cells
        if isinstance(cell, dict) and isinstance(cell.get("id"), str)
    }
    install_source = cell_sources_by_id.get(
        "install-official-offline-wheels",
        "",
    )
    competition_source = cell_sources_by_id.get(
        "execute-generic-runtime",
        "",
    )
    placeholder_source = cell_sources_by_id.get(
        "write-official-placeholder",
        "",
    )
    sources = "\n".join(_cell_source(cell) for cell in cells)
    code_sources = [
        _cell_source(cell)
        for cell in cells
        if isinstance(cell, dict) and cell.get("cell_type") == "code"
    ]
    compile_failures: list[str] = []
    for index, source in enumerate(code_sources):
        try:
            compile(source, f"submission.ipynb:code-cell-{index}", "exec")
        except SyntaxError as error:
            compile_failures.append(f"{index}:{error}")

    runtime_archive, runtime_manifest = build_runtime_archive()
    import_smoke = _runtime_import_smoke(runtime_archive)
    archive_members: list[str]
    with tempfile.TemporaryDirectory(
        prefix="arc3-kaggle-members-"
    ) as directory:
        archive_path = Path(directory) / "runtime.zip"
        archive_path.write_bytes(runtime_archive)
        with zipfile.ZipFile(archive_path) as archive:
            archive_members = sorted(archive.namelist())
    required_members = sorted(
        [
            "ARC3_KAGGLE_RUNTIME_MANIFEST.json",
            "arc3_agi_agent/__init__.py",
            *(f"arc3_agi_agent/{name}" for name in RUNTIME_MODULES),
        ]
    )
    tracked_secret_findings = _tracked_secret_findings()
    notebook_secret_findings = [
        {
            "pattern": name,
            "match_count": len(pattern.findall(notebook_data)),
        }
        for name, pattern in SECRET_PATTERNS
        if pattern.search(notebook_data)
    ]
    kaggle_metadata = (
        notebook.get("metadata", {}).get("kaggle", {})
        if isinstance(notebook.get("metadata"), dict)
        else {}
    )
    checks = {
        "NB-001_SOURCE_REBUILD_EXACT": notebook == expected_notebook,
        "NB-002_METADATA_REBUILD_EXACT": metadata == expected_metadata,
        "NB-003_BUILD_DIGEST_BOUND": (
            build_report.get("notebook_sha256") == _sha256(notebook_data)
            and build_report.get("metadata_sha256") == _sha256(metadata_data)
            and build_report.get("runtime_archive", {}).get(
                "archive_sha256"
            )
            == _sha256(runtime_archive)
            and build_report.get("agent_sha256")
            == _sha256(AGENT_SOURCE.read_bytes())
            and expected_build_report.get("runtime_archive", {}).get(
                "archive_sha256"
            )
            == _sha256(runtime_archive)
        ),
        "NB-004_CODE_COMPILES": not compile_failures,
        "NB-005_RUNTIME_IMPORT_SMOKE": bool(import_smoke["passed"]),
        "NB-006_RUNTIME_ALLOWLIST_EXACT": archive_members
        == required_members,
        "NB-007_CPU_INTERNET_DISABLED": (
            isinstance(kaggle_metadata, dict)
            and kaggle_metadata.get("accelerator") == "none"
            and kaggle_metadata.get("isGpuEnabled") is False
            and kaggle_metadata.get("isInternetEnabled") is False
            and metadata.get("enable_gpu") is False
            and metadata.get("enable_internet") is False
        ),
        "NB-008_COMPETITION_SOURCE_EXACT": metadata.get(
            "competition_sources"
        )
        == [COMPETITION_SLUG],
        "NB-009_GATEWAY_RERUN_CONTRACT": all(
            marker in sources
            for marker in (
                "KAGGLE_IS_COMPETITION_RERUN",
                "http://gateway:8001/api/games",
                "OPERATION_MODE=online",
                "main.py",
                "--agent",
                "genericagi",
            )
        ),
        "NB-010_OFFICIAL_OFFLINE_WHEEL_CONTRACT": (
            all(
                marker in install_source
                for marker in (
                    "--no-index",
                    "arc_agi_3_wheels",
                    '"arc-agi"',
                    '"python-dotenv"',
                    "if wheel_dir.is_dir()",
                    'elif os.getenv("KAGGLE_IS_COMPETITION_RERUN")',
                    "raise FileNotFoundError",
                )
            )
            and "==" not in install_source
        ),
        "NB-011_GATEWAY_OWNS_RERUN_OUTPUT": (
            "/kaggle/working/submission.parquet"
            not in competition_source
            and "to_parquet" not in competition_source
            and "submission_visible_to_notebook" not in competition_source
        ),
        "NB-012_NO_SUBMISSION_SIDE_EFFECT": not any(
            marker in sources
            for marker in (
                "create_code_competition_submission",
                "kaggle competitions submit",
                "/api/v1/competitions/submissions",
            )
        ),
        "NB-013_NO_EXTERNAL_ARC_OR_LLM_ENDPOINT": not any(
            marker in sources.casefold()
            for marker in (
                "three.arcprize.org",
                "api.openai.com",
                "anthropic.com",
            )
        ),
        "NB-014_NO_SECRET": not notebook_secret_findings
        and not tracked_secret_findings,
        "NB-015_GENERIC_BOUNDARY": (
            build_report.get("runtime_archive", {}).get(
                "teacher_included"
            )
            is False
            and build_report.get("runtime_archive", {}).get(
                "known_sample_policy_included"
            )
            is False
            and build_report.get("runtime_archive", {}).get(
                "runtime_identity_routing_included"
            )
            is False
            and runtime_manifest.get("action_budget") == ACTION_BUDGET
        ),
        "NB-016_CELL_IDS_UNIQUE": (
            len(cell_ids) == len(cells)
            and all(
                isinstance(cell_id, str) and bool(cell_id)
                for cell_id in cell_ids
            )
            and len(set(cell_ids)) == len(cell_ids)
        ),
        "NB-017_OFFICIAL_PLACEHOLDER_EXACT": (
            all(
                marker in placeholder_source
                for marker in (
                    'data=[["1_0", "1", True, 1]]',
                    'columns=["row_id", "game_id", "end_of_game", "score"]',
                    'if not os.getenv("KAGGLE_IS_COMPETITION_RERUN")',
                    '"/kaggle/working/submission.parquet"',
                    "index=False",
                )
            )
            and "dry-run" not in placeholder_source
        ),
        "NB-018_OFFICIAL_FOUR_CODE_CELL_LAYOUT": (
            cell_ids
            == [
                "install-official-offline-wheels",
                "verify-runtime-payload",
                "execute-generic-runtime",
                "write-official-placeholder",
            ]
            and cell_types == ["code", "code", "code", "code"]
        ),
        "NB-019_RERUN_AND_PLACEHOLDER_SEPARATE": (
            "to_parquet" not in competition_source
            and "subprocess.run" not in placeholder_source
            and "KAGGLE_IS_COMPETITION_RERUN" in competition_source
            and "KAGGLE_IS_COMPETITION_RERUN" in placeholder_source
        ),
        "NB-020_NO_UNDOCUMENTED_RUNTIME_LIMIT": (
            "timeout=36_000" not in competition_source
            and "timeout=36000" not in competition_source
            and "MAX_WALL" not in sources
            and "WALL_TIME" not in sources
        ),
        "NB-021_NOTEBOOK_FORMAT_MATCHES_OFFICIAL": (
            notebook.get("nbformat") == 4
            and notebook.get("nbformat_minor") == 4
        ),
    }
    return {
        "schema_version": "arc3-kaggle-notebook-validation-v3",
        "status": "PASS" if all(checks.values()) else "FAIL",
        "checks": checks,
        "failed_check_ids": [
            name for name, passed in checks.items() if not passed
        ],
        "notebook": {
            "path": notebook_path.relative_to(ROOT).as_posix(),
            "id": notebook_id,
            "sha256": _sha256(notebook_data),
            "size_bytes": len(notebook_data),
            "cell_count": len(cells),
        },
        "metadata_sha256": _sha256(metadata_data),
        "build_report_sha256": _sha256(build_report_data),
        "runtime_archive": runtime_manifest,
        "agent_sha256": _sha256(AGENT_SOURCE.read_bytes()),
        "compile_failures": compile_failures,
        "runtime_import_smoke": import_smoke,
        "notebook_secret_findings": notebook_secret_findings,
        "tracked_secret_findings": tracked_secret_findings,
        "submission_api_call_count": 0,
    }


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--notebook-dir",
        type=Path,
        default=DEFAULT_OUTPUT_DIR,
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT,
    )
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
