"""Deterministic P10 reproducibility and P11 regression evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import platform
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

from ..schema import digest_object

P10_REPRODUCIBILITY_AUDIT_SCHEMA_VERSION = (
    "arc3-p10-reproducibility-audit-v1"
)
P10_REPRODUCIBILITY_AUDIT_DIGEST_PREFIX = (
    "arc3_p10_reproducibility_audit:"
)
P11_REGRESSION_REPORT_SCHEMA_VERSION = (
    "arc3-p11-regression-report-v1"
)
P11_REGRESSION_REPORT_DIGEST_PREFIX = (
    "arc3_p11_regression_report:"
)

_SECRET_PATTERNS = (
    re.compile(
        rb"(?<![A-Za-z0-9_-])sk-[A-Za-z0-9_-]{20,}"
    ),
    re.compile(rb"gh[pousr]_[A-Za-z0-9]{20,}"),
    re.compile(rb"AKIA[0-9A-Z]{16}"),
    re.compile(rb"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _json_object(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise TypeError(f"JSON_OBJECT_REQUIRED:{path.name}")
    return dict(value)


def _without_digest(value: Mapping[str, Any]) -> dict[str, Any]:
    body = dict(value)
    body.pop("content_digest", None)
    return body


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _load_digest_report(
    path: Path,
    *,
    schema_version: str,
    digest_prefix: str,
) -> dict[str, Any]:
    report = _json_object(path)
    if report.get("schema_version") != schema_version:
        raise ValueError(f"REPORT_SCHEMA_INVALID:{path.name}")
    if report.get("content_digest") != (
        digest_prefix + digest_object(_without_digest(report))
    ):
        raise ValueError(f"REPORT_CONTENT_DIGEST_INVALID:{path.name}")
    return report


def compile_p10_reproducibility_audit(
    *,
    s5_primary_path: Path,
    s5_reproduction_path: Path,
    s6_primary_path: Path,
    s6_reproduction_path: Path,
) -> dict[str, Any]:
    """Bind the two exact S5 and S6 reruns into one compact audit."""

    evidence: dict[str, dict[str, object]] = {}
    specifications = (
        (
            "S5_RENDERED_ONLY_CLOSURE",
            s5_primary_path,
            s5_reproduction_path,
            "arc3_s5_rendered_runtime_closure:",
            {
                "all_complete": True,
                "completed_levels": 183,
                "environment_count": 25,
                "error_count": 0,
                "deterministic_seed": 0,
            },
        ),
        (
            "S6_PERTURBATION_MEASUREMENT",
            s6_primary_path,
            s6_reproduction_path,
            "arc3_s6_perturbation_measurement:",
            {
                "status": "COMPLETE",
                "covered_level_count": 183,
                "covered_game_count": 25,
                "total_measurement_count": 14_336,
                "exception_count": 0,
                "generalization_claim": "MEASURED_NOT_PROVEN",
            },
        ),
    )
    for (
        evidence_id,
        primary_path,
        reproduction_path,
        digest_prefix,
        requirements,
    ) in specifications:
        primary_bytes = primary_path.read_bytes()
        reproduction_bytes = reproduction_path.read_bytes()
        primary = _json_object(primary_path)
        reproduction = _json_object(reproduction_path)
        failures: list[str] = []
        for key, expected in requirements.items():
            if primary.get(key) != expected:
                failures.append(f"{evidence_id}_PRIMARY_INVALID:{key}")
            if reproduction.get(key) != expected:
                failures.append(
                    f"{evidence_id}_REPRODUCTION_INVALID:{key}"
                )
        for label, report in (
            ("PRIMARY", primary),
            ("REPRODUCTION", reproduction),
        ):
            claimed = report.get("content_digest")
            actual = digest_prefix + digest_object(
                _without_digest(report)
            )
            if claimed != actual:
                failures.append(
                    f"{evidence_id}_{label}_CONTENT_DIGEST_INVALID"
                )
        if primary_bytes != reproduction_bytes:
            failures.append(f"{evidence_id}_BYTE_MISMATCH")
        if failures:
            raise ValueError(";".join(sorted(set(failures))))
        evidence[evidence_id] = {
            "byte_equal": True,
            "content_digest": primary.get("content_digest"),
            "file_sha256": hashlib.sha256(primary_bytes).hexdigest(),
            "primary_filename": primary_path.name,
            "reproduction_filename": reproduction_path.name,
        }
    body: dict[str, Any] = {
        "schema_version": P10_REPRODUCIBILITY_AUDIT_SCHEMA_VERSION,
        "phase": "P10-R6-REPRODUCIBILITY-AUDIT",
        "status": "PASS",
        "evidence": evidence,
        "s5_exact_rerun_count": 2,
        "s6_exact_rerun_count": 2,
        "s5_byte_equal": True,
        "s6_byte_equal": True,
        "generalization_claim": "MEASURED_NOT_PROVEN",
        "next_stage": "P11_RELEASE_STATE",
    }
    return {
        **body,
        "content_digest": (
            P10_REPRODUCIBILITY_AUDIT_DIGEST_PREFIX
            + digest_object(body)
        ),
    }


def load_p10_reproducibility_audit(path: Path) -> dict[str, Any]:
    report = _load_digest_report(
        path,
        schema_version=P10_REPRODUCIBILITY_AUDIT_SCHEMA_VERSION,
        digest_prefix=P10_REPRODUCIBILITY_AUDIT_DIGEST_PREFIX,
    )
    if (
        report.get("status") != "PASS"
        or report.get("s5_byte_equal") is not True
        or report.get("s6_byte_equal") is not True
        or report.get("generalization_claim")
        != "MEASURED_NOT_PROVEN"
    ):
        raise ValueError("P10_REPRODUCIBILITY_AUDIT_NOT_PASS")
    return report


def _git(
    repository_root: Path,
    *arguments: str,
) -> str:
    completed = subprocess.run(
        ("git", *arguments),
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if completed.returncode:
        raise RuntimeError(
            "GIT_COMMAND_FAILED:"
            + ":".join(arguments)
            + ":"
            + completed.stderr.strip()[-500:]
        )
    return completed.stdout.strip()


def _tracked_secret_scan(repository_root: Path) -> dict[str, object]:
    raw_paths = _git(repository_root, "ls-files", "-z")
    paths = tuple(path for path in raw_paths.split("\0") if path)
    scanned_file_count = 0
    binary_file_count = 0
    finding_count = 0
    for relative in paths:
        path = repository_root / relative
        if not path.is_file():
            continue
        data = path.read_bytes()
        if b"\0" in data:
            binary_file_count += 1
            continue
        scanned_file_count += 1
        finding_count += sum(
            len(pattern.findall(data)) for pattern in _SECRET_PATTERNS
        )
    return {
        "status": "PASS" if finding_count == 0 else "FAIL",
        "tracked_file_count": len(paths),
        "scanned_text_file_count": scanned_file_count,
        "skipped_binary_file_count": binary_file_count,
        "high_confidence_finding_count": finding_count,
        "pattern_set": (
            "OPENAI_STYLE_KEY",
            "GITHUB_TOKEN",
            "AWS_ACCESS_KEY",
            "PRIVATE_KEY_BLOCK",
        ),
    }


def _run_validation_command(
    *,
    command_id: str,
    command: Sequence[str],
    report_command: Sequence[str],
    workdir: Path,
    environment: Mapping[str, str],
) -> dict[str, object]:
    completed = subprocess.run(
        tuple(command),
        cwd=workdir,
        env=dict(environment),
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    result: dict[str, object] = {
        "command_id": command_id,
        "command": list(report_command),
        "return_code": completed.returncode,
        "status": "PASS" if completed.returncode == 0 else "FAIL",
    }
    if completed.returncode:
        result["stdout_tail"] = completed.stdout[-2000:]
        result["stderr_tail"] = completed.stderr[-2000:]
    print(
        json.dumps(
            {
                "command_id": command_id,
                "return_code": completed.returncode,
                "status": result["status"],
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return result


def run_p11_regression_suite(
    *,
    repository_root: Path,
) -> dict[str, Any]:
    """Execute the fixed local P11 regression suite."""

    repository_root = repository_root.resolve()
    package_root = repository_root / "ARC-AGI-3-Agents"
    python_executable = Path(sys.executable).resolve()
    if package_root not in python_executable.parents:
        raise ValueError("P11_REGRESSION_PYTHON_OUTSIDE_PACKAGE")
    code_commit = _git(repository_root, "rev-parse", "HEAD")
    code_tree = _git(repository_root, "rev-parse", "HEAD^{tree}")
    branch = _git(repository_root, "branch", "--show-current")
    if branch != "main":
        raise ValueError("P11_REGRESSION_MAIN_BRANCH_REQUIRED")

    temporary_root = (
        repository_root / "scratch" / "p11-regression-temporary"
    )
    temporary_root.mkdir(parents=True, exist_ok=True)
    environment = dict(os.environ)
    environment.update(
        {
            "OPERATION_MODE": "offline",
            "PYTHONHASHSEED": "0",
            "TEMP": str(temporary_root),
            "TMP": str(temporary_root),
        }
    )
    python = str(python_executable)
    commands = (
        (
            "COMPILEALL",
            (
                python,
                "-m",
                "compileall",
                "-q",
                "arc3_agi_agent",
                "agents",
                "tests/unit",
                "tests/integration",
            ),
            (
                "{PYTHON}",
                "-m",
                "compileall",
                "-q",
                "arc3_agi_agent",
                "agents",
                "tests/unit",
                "tests/integration",
            ),
            package_root,
        ),
        (
            "RUFF",
            (
                python,
                "-m",
                "ruff",
                "check",
                "arc3_agi_agent",
                "agents/__init__.py",
                "agents/recorder.py",
                "tests/conftest.py",
                "tests/unit",
                "tests/integration",
            ),
            (
                "{PYTHON}",
                "-m",
                "ruff",
                "check",
                "arc3_agi_agent",
                "agents/__init__.py",
                "agents/recorder.py",
                "tests/conftest.py",
                "tests/unit",
                "tests/integration",
            ),
            package_root,
        ),
        (
            "MYPY_STRICT",
            (
                python,
                "-m",
                "mypy",
                "arc3_agi_agent",
                "--strict",
            ),
            (
                "{PYTHON}",
                "-m",
                "mypy",
                "arc3_agi_agent",
                "--strict",
            ),
            package_root,
        ),
        (
            "PYTEST_UNIT",
            (
                python,
                "-m",
                "pytest",
                "-q",
                "tests/unit",
                "--basetemp=../scratch/p11-pytest-unit",
            ),
            (
                "{PYTHON}",
                "-m",
                "pytest",
                "-q",
                "tests/unit",
                "--basetemp={SCRATCH}/p11-pytest-unit",
            ),
            package_root,
        ),
        (
            "PYTEST_INTEGRATION",
            (
                python,
                "-m",
                "pytest",
                "-q",
                "tests/integration",
                "--basetemp=../scratch/p11-pytest-integration",
            ),
            (
                "{PYTHON}",
                "-m",
                "pytest",
                "-q",
                "tests/integration",
                "--basetemp={SCRATCH}/p11-pytest-integration",
            ),
            package_root,
        ),
        (
            "GIT_DIFF_CHECK",
            ("git", "diff", "--check", "HEAD"),
            ("git", "diff", "--check", "HEAD"),
            repository_root,
        ),
    )
    results = [
        _run_validation_command(
            command_id=command_id,
            command=command,
            report_command=report_command,
            workdir=workdir,
            environment=environment,
        )
        for command_id, command, report_command, workdir in commands
    ]
    secret_scan = _tracked_secret_scan(repository_root)
    print(
        json.dumps(
            {
                "command_id": "TRACKED_SECRET_SCAN",
                "status": secret_scan["status"],
            },
            sort_keys=True,
        ),
        flush=True,
    )
    failed = [
        str(result["command_id"])
        for result in results
        if result["status"] != "PASS"
    ]
    if secret_scan["status"] != "PASS":
        failed.append("TRACKED_SECRET_SCAN")
    body: dict[str, Any] = {
        "schema_version": P11_REGRESSION_REPORT_SCHEMA_VERSION,
        "phase": "P11-RELEASE-STATE-REGRESSION",
        "status": "PASS" if not failed else "FAIL",
        "code_commit": code_commit,
        "code_tree": code_tree,
        "branch": branch,
        "python_version": platform.python_version(),
        "operation_mode": "offline",
        "python_hash_seed": 0,
        "validation_count": len(results) + 1,
        "passed_validation_count": (
            len(results) + 1 - len(failed)
        ),
        "failed_validation_ids": failed,
        "commands": results,
        "tracked_secret_scan": secret_scan,
        "uv_lock_sha256": _file_sha256(package_root / "uv.lock"),
    }
    return {
        **body,
        "content_digest": (
            P11_REGRESSION_REPORT_DIGEST_PREFIX + digest_object(body)
        ),
    }


def load_p11_regression_report(path: Path) -> dict[str, Any]:
    report = _load_digest_report(
        path,
        schema_version=P11_REGRESSION_REPORT_SCHEMA_VERSION,
        digest_prefix=P11_REGRESSION_REPORT_DIGEST_PREFIX,
    )
    if (
        report.get("status") != "PASS"
        or report.get("failed_validation_ids") != []
        or report.get("passed_validation_count")
        != report.get("validation_count")
    ):
        raise ValueError("P11_REGRESSION_REPORT_NOT_PASS")
    return report


def reproducibility_main() -> int:
    parser = argparse.ArgumentParser(
        description="Bind exact S5 and S6 reruns."
    )
    parser.add_argument("--s5-primary", type=Path, required=True)
    parser.add_argument("--s5-reproduction", type=Path, required=True)
    parser.add_argument("--s6-primary", type=Path, required=True)
    parser.add_argument("--s6-reproduction", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = compile_p10_reproducibility_audit(
        s5_primary_path=args.s5_primary,
        s5_reproduction_path=args.s5_reproduction,
        s6_primary_path=args.s6_primary,
        s6_reproduction_path=args.s6_reproduction,
    )
    _write_json(args.output, report)
    load_p10_reproducibility_audit(args.output)
    print(
        json.dumps(
            {
                "content_digest": report["content_digest"],
                "output": str(args.output.resolve()),
                "status": report["status"],
            },
            sort_keys=True,
        )
    )
    return 0


def regression_main() -> int:
    parser = argparse.ArgumentParser(
        description="Run the fixed local P11 regression suite."
    )
    parser.add_argument("--repository-root", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report = run_p11_regression_suite(
        repository_root=args.repository_root,
    )
    _write_json(args.output, report)
    if report["status"] != "PASS":
        print(
            json.dumps(
                {
                    "failed_validation_ids": report[
                        "failed_validation_ids"
                    ],
                    "output": str(args.output.resolve()),
                    "status": report["status"],
                },
                sort_keys=True,
            )
        )
        return 1
    load_p11_regression_report(args.output)
    print(
        json.dumps(
            {
                "code_commit": report["code_commit"],
                "content_digest": report["content_digest"],
                "output": str(args.output.resolve()),
                "status": report["status"],
                "validation_count": report["validation_count"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(regression_main())


__all__ = [
    "P10_REPRODUCIBILITY_AUDIT_DIGEST_PREFIX",
    "P10_REPRODUCIBILITY_AUDIT_SCHEMA_VERSION",
    "P11_REGRESSION_REPORT_DIGEST_PREFIX",
    "P11_REGRESSION_REPORT_SCHEMA_VERSION",
    "compile_p10_reproducibility_audit",
    "load_p10_reproducibility_audit",
    "load_p11_regression_report",
    "run_p11_regression_suite",
]
