#!/usr/bin/env python3
"""Run and seal the focused rev5.1 M3 conformance test suite."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Final

REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[1]
PACKAGE_ROOT: Final = REPOSITORY_ROOT / "ARC-AGI-3-Agents"
OUTPUT_PATH: Final = Path("analysis/product/rev5_1/m3_p06_conformance_test_run.json")
TEST_PATHS: Final = (
    Path("tests/unit/test_m0_p08_horizontal_subtraction.py"),
    Path("tests/unit/test_m3_p01_cjmp_ablation.py"),
    Path("tests/unit/test_m3_p02_memory_causality.py"),
    Path("tests/unit/test_m3_p03_identity_replay_audit.py"),
    Path("tests/unit/test_m3_p04_applicability_counterfactual.py"),
    Path("tests/unit/test_m3_p05_runtime_version_learning.py"),
    Path("tests/unit/test_p20b_compiler_registry.py"),
    Path("tests/unit/test_generic_runtime_p12.py"),
    Path("tests/unit/test_product_runner.py"),
)
IMPLEMENTATION_PATHS: Final = (
    Path("arc3_agi_agent/compiled_policy.py"),
    Path("arc3_agi_agent/generic_compute.py"),
    Path("arc3_agi_agent/generic_hds.py"),
    Path("arc3_agi_agent/generic_memory.py"),
    Path("arc3_agi_agent/generic_runtime.py"),
    Path("arc3_agi_agent/identity_boundary.py"),
    Path("arc3_agi_agent/initial_state_compiler.py"),
    Path("arc3_agi_agent/local_capability.py"),
    Path("arc3_agi_agent/product_runner.py"),
    Path("arc3_agi_agent/product_version_learning.py"),
)
CONFORMANCE_ARTIFACTS: Final = (
    Path("analysis/product/rev5_1/m3_p01_cjmp_ablation.json"),
    Path("analysis/product/rev5_1/m3_p02_memory_causality.json"),
    Path("analysis/product/rev5_1/m3_p03_identity_replay_audit.json"),
    Path("analysis/product/rev5_1/m3_p04_applicability_counterfactual.json"),
    Path("analysis/product/rev5_1/m3_p05_runtime_version_learning.json"),
)
ANSI_ESCAPE: Final = re.compile(r"\x1b\[[0-9;]*m")


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


def _bindings(root: Path, paths: tuple[Path, ...]) -> list[dict[str, str]]:
    return [
        {
            "path": path.as_posix(),
            "sha256": _sha256((root / path).read_bytes()),
        }
        for path in paths
    ]


def run_tests(root: Path = REPOSITORY_ROOT) -> dict[str, object]:
    package_root = root / "ARC-AGI-3-Agents"
    command = [
        sys.executable,
        "-m",
        "pytest",
        "-q",
        *(path.as_posix() for path in TEST_PATHS),
    ]
    environment = dict(os.environ)
    environment.update({"NO_COLOR": "1", "PY_COLORS": "0"})
    completed = subprocess.run(
        command,
        cwd=package_root,
        env=environment,
        capture_output=True,
        check=False,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    output = completed.stdout + "\n" + completed.stderr
    plain_output = ANSI_ESCAPE.sub("", output)
    matches = re.findall(r"(?:^|\s)(\d+) passed(?:,|\s)", plain_output)
    passed_count = int(matches[-1]) if matches else 0
    if completed.returncode != 0 or passed_count <= 0:
        tail = "\n".join(plain_output.splitlines()[-40:])
        raise RuntimeError(
            f"M3_P06_CONFORMANCE_TEST_FAILURE:exit={completed.returncode}:tail={tail}"
        )
    report: dict[str, object] = {
        "schema_version": "arc3-rev5-1-m3-conformance-test-run-v1",
        "artifact_type": "M3ConformanceTestEvidence",
        "point_id": "M3-P06_CONFORMANCE_FULL_REGRESSION",
        "status": "PASS",
        "command": [
            "python",
            "-m",
            "pytest",
            "-q",
            *(path.as_posix() for path in TEST_PATHS),
        ],
        "process_exit_code": completed.returncode,
        "passed_test_count": passed_count,
        "failed_test_count": 0,
        "error_test_count": 0,
        "target_file_count": len(TEST_PATHS),
        "test_file_bindings": _bindings(package_root, TEST_PATHS),
        "implementation_file_bindings": _bindings(
            package_root,
            IMPLEMENTATION_PATHS,
        ),
        "conformance_artifact_bindings": _bindings(
            root,
            CONFORMANCE_ARTIFACTS,
        ),
        "claim_boundary": {
            "full_sample_regression_included": False,
            "M3_complete": False,
            "next_required_evidence": ("M3_P06_FRESH_OFFICIAL_SAMPLE_FULL_REGRESSION"),
        },
    }
    report["logical_content_sha256"] = _sha256(_canonical_json(report))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=REPOSITORY_ROOT)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    report = run_tests(root)
    expected = _encoded(report)
    path = root / OUTPUT_PATH
    if arguments.write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(expected)
        status = "WRITTEN"
        success = True
    else:
        success = path.is_file() and path.read_bytes() == expected
        status = "PASS" if success else "STALE"
    print(
        json.dumps(
            {
                "output": OUTPUT_PATH.as_posix(),
                "passed_test_count": report["passed_test_count"],
                "status": status,
            },
            sort_keys=True,
        )
    )
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
