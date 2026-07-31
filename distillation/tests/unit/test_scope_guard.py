from __future__ import annotations

import hashlib
import json
import shutil
import subprocess
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import cast

import pytest

from hds_distill.scope_guard import (
    REPORT_DIGEST_EXCLUDED_FIELDS,
    REPORT_DIGEST_NAMESPACE,
    ScopeAuditError,
    audit_project,
    canonical_json,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PROJECT_ROOT = REPOSITORY_ROOT / "distillation"
SOURCE_ROOT = PROJECT_ROOT / "src" / "hds_distill"
GUARD_PATH = SOURCE_ROOT / "scope_guard.py"
REPORT_PATH = (
    PROJECT_ROOT
    / "artifacts"
    / "reports"
    / "distillation_scope_audit.json"
)


def _fixture_repository(tmp_path: Path) -> tuple[Path, Path]:
    repository = tmp_path / "repository"
    project = repository / "distillation"
    shutil.copytree(
        PROJECT_ROOT,
        project,
        ignore=shutil.ignore_patterns(
            "__pycache__",
            ".mypy_cache",
            ".pytest_cache",
            ".ruff_cache",
            "*.pyc",
        ),
    )
    shutil.copy2(REPOSITORY_ROOT / "SCOPE_LOCK.md", repository)
    (repository / "bridge").mkdir()
    (repository / "bridge" / ".gitkeep").write_text(
        "\n",
        encoding="utf-8",
        newline="\n",
    )
    (repository / "runtime").mkdir()
    shutil.copy2(
        REPOSITORY_ROOT / "runtime" / "REFERENCE_ONLY.md",
        repository / "runtime",
    )
    return repository, project


def _write_module(project: Path, name: str, source: str) -> Path:
    path = project / "src" / "hds_distill" / name
    path.write_text(source, encoding="utf-8", newline="\n")
    return path


def _finding_codes(report: Mapping[str, object]) -> set[str]:
    raw_findings = cast(list[object], report["findings"])
    codes: set[str] = set()
    for raw_finding in raw_findings:
        finding = cast(Mapping[str, object], raw_finding)
        codes.add(str(finding["code"]))
    return codes


def _audit_fixture(tmp_path: Path) -> tuple[Path, Path, dict[str, object]]:
    repository, project = _fixture_repository(tmp_path)
    report = cast(
        dict[str, object],
        audit_project(project, repository_root=repository),
    )
    return repository, project, report


def test_live_project_is_finding_free_and_matches_checked_report() -> None:
    report = audit_project(PROJECT_ROOT, repository_root=REPOSITORY_ROOT)
    checked = json.loads(REPORT_PATH.read_text(encoding="utf-8"))

    assert report["scope_guard_pass"] is True
    assert report["finding_count"] == 0
    assert report["audited_source_execution_count"] == 0
    assert report["gates"] == {
        "DG-02": "PASS",
        "DG-09": "PASS",
        "DG-14": "PASS",
    }
    assert report == checked
    assert REPORT_PATH.read_text(encoding="utf-8") == (
        canonical_json(report) + "\n"
    )


def test_report_digest_and_three_rebuilds_are_deterministic() -> None:
    reports = [
        audit_project(PROJECT_ROOT, repository_root=REPOSITORY_ROOT)
        for _ in range(3)
    ]
    encoded = [canonical_json(report) + "\n" for report in reports]
    assert encoded[0] == encoded[1] == encoded[2]

    body = dict(reports[0])
    digest = str(body["content_digest"])
    for field in REPORT_DIGEST_EXCLUDED_FIELDS:
        body.pop(field)
    expected = REPORT_DIGEST_NAMESPACE + ":" + hashlib.sha256(
        canonical_json(body).encode("utf-8")
    ).hexdigest()
    assert digest == expected


def test_report_digest_changes_on_import_neutral_source_change(
    tmp_path: Path,
) -> None:
    repository, project, baseline = _audit_fixture(tmp_path)
    guard_path = project / "src" / "hds_distill" / "scope_guard.py"
    guard_path.write_text(
        guard_path.read_text(encoding="utf-8") + "\n_AUDIT_PROBE = 1\n",
        encoding="utf-8",
        newline="\n",
    )

    changed = audit_project(project, repository_root=repository)
    assert changed["scope_guard_pass"] is True
    assert changed["content_digest"] != baseline["content_digest"]
    assert changed["import_graph"] == baseline["import_graph"]
    assert changed["source_manifest"] != baseline["source_manifest"]


def test_cli_verifies_checked_report_with_stable_pass(tmp_path: Path) -> None:
    process = subprocess.run(
        [
            sys.executable,
            str(GUARD_PATH),
            "--project-root",
            str(PROJECT_ROOT),
            "--repository-root",
            str(REPOSITORY_ROOT),
            "--verify-report",
            str(REPORT_PATH),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )

    assert process.returncode == 0, process.stderr
    assert process.stderr == ""
    assert process.stdout.startswith(
        "DISTILLATION_SCOPE_GUARD_PASS:"
        "hds-distillation-scope-audit:"
    )


def test_solver_filename_does_not_false_positive_valid_offline_work(
    tmp_path: Path,
) -> None:
    repository, project, _report = _audit_fixture(tmp_path)
    _write_module(
        project,
        "solver_named_offline.py",
        """\
from hds_distill.scope_contract import offline_interpreter, teacher_bound


@offline_interpreter
def interpret_program(program: tuple[str, ...], machine_state: int) -> int:
    return machine_state + len(program)


@teacher_bound
def replay_solver(task: object, expected_answer: object) -> object:
    del task
    return expected_answer
""",
    )

    report = audit_project(project, repository_root=repository)
    assert report["scope_guard_pass"] is True
    assert report["findings"] == []


def test_official_api_callable_fails_closed(tmp_path: Path) -> None:
    repository, project, _report = _audit_fixture(tmp_path)
    _write_module(
        project,
        "official_client.py",
        """\
from arc_agi import Arcade, OperationMode


def create_client(config: object) -> object:
    return Arcade(config, mode=OperationMode.COMPETITION)
""",
    )

    report = cast(
        dict[str, object],
        audit_project(project, repository_root=repository),
    )
    codes = _finding_codes(report)
    assert "D00B_OFFICIAL_API_IMPORT_FORBIDDEN" in codes
    assert "D00B_OFFICIAL_API_CALL_FORBIDDEN" in codes
    assert "D00B_COMPETITION_MODE_FORBIDDEN" in codes


def test_network_alias_and_dynamic_import_fail_closed(tmp_path: Path) -> None:
    repository, project, _report = _audit_fixture(tmp_path)
    _write_module(
        project,
        "transport.py",
        """\
import importlib
import requests as transport


def fetch() -> object:
    return transport.get("https://example.invalid")


def load(name: str) -> object:
    return importlib.import_module(name)
""",
    )

    report = cast(
        dict[str, object],
        audit_project(project, repository_root=repository),
    )
    codes = _finding_codes(report)
    assert "D00B_NETWORK_IMPORT_FORBIDDEN" in codes
    assert "D00B_NETWORK_CALL_FORBIDDEN" in codes
    assert "D00B_DYNAMIC_IMPORT_FORBIDDEN" in codes


def test_network_subprocess_command_fails_closed(tmp_path: Path) -> None:
    repository, project, _report = _audit_fixture(tmp_path)
    _write_module(
        project,
        "command.py",
        """\
import subprocess


def download() -> object:
    return subprocess.run(["curl", "https://example.invalid"], check=True)
""",
    )

    report = cast(
        dict[str, object],
        audit_project(project, repository_root=repository),
    )
    assert "D00B_NETWORK_COMMAND_FORBIDDEN" in _finding_codes(report)


def test_non_allowlisted_process_execution_fails_closed(
    tmp_path: Path,
) -> None:
    repository, project, _report = _audit_fixture(tmp_path)
    _write_module(
        project,
        "process.py",
        """\
import subprocess


def run_local_tool() -> object:
    return subprocess.run(["python", "tool.py"], check=True)
""",
    )

    report = cast(
        dict[str, object],
        audit_project(project, repository_root=repository),
    )
    assert "D00B_PROCESS_EXECUTION_FORBIDDEN" in _finding_codes(report)


def test_read_only_git_inventory_process_is_allowlisted(
    tmp_path: Path,
) -> None:
    repository, project, _report = _audit_fixture(tmp_path)
    _write_module(
        project,
        "git_inventory.py",
        """\
import subprocess


def list_repository_metadata(root: str) -> object:
    return subprocess.run(
        ["git", "ls-files", "--", root],
        check=False,
        capture_output=True,
        text=True,
    )
""",
    )

    report = audit_project(project, repository_root=repository)
    assert report["scope_guard_pass"] is True
    assert report["findings"] == []


def test_unlabeled_task_answer_callable_fails_closed(tmp_path: Path) -> None:
    repository, project, _report = _audit_fixture(tmp_path)
    _write_module(
        project,
        "answerer.py",
        """\
def solve_task(task: object) -> list[list[int]]:
    del task
    return [[1, 2], [3, 4]]
""",
    )

    report = cast(
        dict[str, object],
        audit_project(project, repository_root=repository),
    )
    assert (
        "D00B_UNLABELED_TASK_PUBLIC_CALLABLE" in _finding_codes(report)
    )


def test_locally_spoofed_teacher_marker_cannot_bypass_guard(
    tmp_path: Path,
) -> None:
    repository, project, _report = _audit_fixture(tmp_path)
    _write_module(
        project,
        "spoofed_marker.py",
        """\
def teacher_bound(function: object) -> object:
    return function


@teacher_bound
def solve_task(task: object) -> object:
    return task
""",
    )

    report = cast(
        dict[str, object],
        audit_project(project, repository_root=repository),
    )
    codes = _finding_codes(report)
    assert "D00B_UNTRUSTED_SCOPE_MARKER" in codes
    assert "D00B_UNLABELED_TASK_PUBLIC_CALLABLE" in codes


def test_rebound_trusted_teacher_marker_cannot_bypass_guard(
    tmp_path: Path,
) -> None:
    repository, project, _report = _audit_fixture(tmp_path)
    _write_module(
        project,
        "rebound_marker.py",
        """\
from hds_distill.scope_contract import teacher_bound


teacher_bound = lambda function: function


@teacher_bound
def solve_task(task: object, expected_answer: object) -> object:
    del task
    return expected_answer
""",
    )

    report = cast(
        dict[str, object],
        audit_project(project, repository_root=repository),
    )
    assert (
        "D00B_TRUSTED_SCOPE_MARKER_REBOUND" in _finding_codes(report)
    )


def test_submission_generator_fails_closed(tmp_path: Path) -> None:
    repository, project, _report = _audit_fixture(tmp_path)
    _write_module(
        project,
        "exporter.py",
        """\
def write_submission(frame: object) -> object:
    return frame.to_parquet("submission.parquet")
""",
    )

    report = cast(
        dict[str, object],
        audit_project(project, repository_root=repository),
    )
    assert "D00B_SUBMISSION_OUTPUT_FORBIDDEN" in _finding_codes(report)


def test_identity_routing_and_answer_map_fail_closed(tmp_path: Path) -> None:
    repository, project, _report = _audit_fixture(tmp_path)
    _write_module(
        project,
        "router.py",
        """\
ANSWER_MAP = {"game-a": ["UP", "RIGHT"]}


def select(task: object, game_id: str, table: dict[str, object]) -> object:
    del task
    return table[game_id]
""",
    )

    report = cast(
        dict[str, object],
        audit_project(project, repository_root=repository),
    )
    codes = _finding_codes(report)
    assert "D00B_IDENTITY_SELECTOR_FORBIDDEN" in codes
    assert "D00B_ANSWER_LITERAL_OR_FIXED_ACTION_FORBIDDEN" in codes


def test_runtime_dependency_fails_closed(tmp_path: Path) -> None:
    repository, project, _report = _audit_fixture(tmp_path)
    _write_module(
        project,
        "runtime_link.py",
        """\
from arc3_agi_agent import runtime


def reference() -> object:
    return runtime
""",
    )

    report = cast(
        dict[str, object],
        audit_project(project, repository_root=repository),
    )
    assert "D00B_RUNTIME_DEPENDENCY_FORBIDDEN" in _finding_codes(report)


def test_hidden_entrypoint_fails_closed(tmp_path: Path) -> None:
    repository, project, _report = _audit_fixture(tmp_path)
    _write_module(
        project,
        "hidden_entrypoint.py",
        """\
def main() -> int:
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
""",
    )

    report = cast(
        dict[str, object],
        audit_project(project, repository_root=repository),
    )
    codes = _finding_codes(report)
    assert "D00B_UNDECLARED_ENTRYPOINT" in codes
    assert "D00B_UNDECLARED_MAIN_CALLABLE" in codes


def test_unknown_pyproject_execution_surface_fails_closed(
    tmp_path: Path,
) -> None:
    repository, project, _report = _audit_fixture(tmp_path)
    pyproject = project / "pyproject.toml"
    pyproject.write_text(
        pyproject.read_text(encoding="utf-8")
        + "\n[build-system]\n"
        + 'requires = ["untrusted-build-backend"]\n',
        encoding="utf-8",
        newline="\n",
    )

    report = cast(
        dict[str, object],
        audit_project(project, repository_root=repository),
    )
    assert (
        "D00B_PYPROJECT_UNKNOWN_TOP_LEVEL_FIELD"
        in _finding_codes(report)
    )


def test_executable_artifact_fails_closed(tmp_path: Path) -> None:
    repository, project, _report = _audit_fixture(tmp_path)
    script = project / "run.sh"
    script.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")

    report = cast(
        dict[str, object],
        audit_project(project, repository_root=repository),
    )
    assert "D00B_EXECUTABLE_ARTIFACT_FORBIDDEN" in _finding_codes(report)


def test_audited_module_is_never_executed(tmp_path: Path) -> None:
    repository, project, _report = _audit_fixture(tmp_path)
    _write_module(
        project,
        "must_not_execute.py",
        """\
raise RuntimeError("audited source was executed")

SAFE_METADATA = "parse-only"
""",
    )

    report = audit_project(project, repository_root=repository)
    assert report["scope_guard_pass"] is True
    assert report["audited_source_execution_count"] == 0


def test_syntax_error_is_visible_failure(tmp_path: Path) -> None:
    repository, project, _report = _audit_fixture(tmp_path)
    _write_module(project, "broken.py", "def broken(:\n")

    report = cast(
        dict[str, object],
        audit_project(project, repository_root=repository),
    )
    assert "D00B_SOURCE_PARSE_FAILURE" in _finding_codes(report)


@pytest.mark.parametrize("boundary", ["bridge", "runtime"])
def test_bridge_and_runtime_code_fail_closed(
    tmp_path: Path,
    boundary: str,
) -> None:
    repository, project, _report = _audit_fixture(tmp_path)
    (repository / boundary / "implementation.py").write_text(
        "VALUE = 1\n",
        encoding="utf-8",
        newline="\n",
    )

    report = cast(
        dict[str, object],
        audit_project(project, repository_root=repository),
    )
    expected = (
        "D00B_BRIDGE_MUST_REMAIN_EMPTY"
        if boundary == "bridge"
        else "D00B_RUNTIME_IMPLEMENTATION_FORBIDDEN"
    )
    assert expected in _finding_codes(report)


def test_runtime_dependency_declared_in_pyproject_fails_closed(
    tmp_path: Path,
) -> None:
    repository, project, _report = _audit_fixture(tmp_path)
    pyproject = project / "pyproject.toml"
    value = pyproject.read_text(encoding="utf-8").replace(
        "dependencies = []",
        'dependencies = ["requests==2.32.4"]',
    )
    pyproject.write_text(value, encoding="utf-8", newline="\n")

    report = cast(
        dict[str, object],
        audit_project(project, repository_root=repository),
    )
    assert "D00B_RUNTIME_DEPENDENCY_FORBIDDEN" in _finding_codes(report)


def test_wrong_project_coordinate_is_configuration_error(
    tmp_path: Path,
) -> None:
    with pytest.raises(
        ScopeAuditError,
        match="D00B_PROJECT_ROOT_MUST_BE_REPOSITORY_DISTILLATION",
    ):
        audit_project(PROJECT_ROOT, repository_root=tmp_path)
