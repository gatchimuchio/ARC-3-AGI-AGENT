#!/usr/bin/env python3
"""Validate and normalize one completed ARC3CompletionAgent product run."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Sequence

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
AGENTS_ROOT = REPOSITORY_ROOT / "ARC-AGI-3-Agents"
REFERENCE_PATH = Path("analysis/runtime/S5_RENDERED_ONLY_CLOSURE_REPORT.json")

sys.path.insert(0, str(AGENTS_ROOT))
try:
    from arc3_agi_agent.product_governance import ARC3_PRODUCT_ENDPOINT
finally:
    sys.path.remove(str(AGENTS_ROOT))


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _canonical_json(value: object) -> str:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _load_object(path: Path) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"ARC3_PRODUCT_EVIDENCE_OBJECT_REQUIRED:{path}")
    return value


def _game_key(value: object) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError("ARC3_PRODUCT_EVIDENCE_GAME_ID_INVALID")
    return value.split("-", 1)[0].upper()


def _reference_results(reference: dict[str, object]) -> dict[str, tuple[int, int, str]]:
    raw_reports = reference.get("reports")
    if not isinstance(raw_reports, list):
        raise TypeError("ARC3_PRODUCT_REFERENCE_REPORTS_INVALID")
    expected: dict[str, tuple[int, int, str]] = {}
    for row in raw_reports:
        if not isinstance(row, dict):
            raise TypeError("ARC3_PRODUCT_REFERENCE_ROW_INVALID")
        expected[_game_key(row.get("game_id"))] = (
            int(row["completed_levels"]),
            int(row["actions_executed"]),
            str(row["final_state"]),
        )
    return expected


def _actual_results(report: dict[str, object]) -> dict[str, tuple[int, int, str]]:
    raw_index = report.get("orchestration_game_index")
    raw_results = report.get("results")
    if not isinstance(raw_index, list) or not isinstance(raw_results, list):
        raise TypeError("ARC3_PRODUCT_RUN_RESULTS_INVALID")
    if len(raw_index) != len(raw_results):
        raise ValueError("ARC3_PRODUCT_RUN_RESULT_INDEX_MISMATCH")
    actual: dict[str, tuple[int, int, str]] = {}
    for metadata, row in zip(raw_index, raw_results, strict=True):
        if not isinstance(metadata, dict) or not isinstance(row, dict):
            raise TypeError("ARC3_PRODUCT_RUN_RESULT_ROW_INVALID")
        actual[_game_key(metadata.get("game_id"))] = (
            int(row["progress_count"]),
            int(row["actions_executed"]),
            str(row["final_state"]),
        )
    return actual


def build_evidence(
    *,
    source_report: Path,
    stage: str,
    implementation_commit: str,
) -> dict[str, object]:
    """Return fail-closed evidence bound to raw bytes and the reference matrix."""

    if stage not in {"M4_CANONICAL_FULL_SAMPLE", "M5_CLEAN_INSTALL_FULL_SAMPLE"}:
        raise ValueError("ARC3_PRODUCT_EVIDENCE_STAGE_INVALID")
    if len(implementation_commit) != 40 or any(
        char not in "0123456789abcdef" for char in implementation_commit
    ):
        raise ValueError("ARC3_PRODUCT_EVIDENCE_COMMIT_INVALID")
    source_bytes = source_report.read_bytes()
    report = _load_object(source_report)
    report.update(ARC3_PRODUCT_ENDPOINT.metrics(report))
    if report.get("product_completion_established") is not True:
        raise RuntimeError("ARC3_PRODUCT_EVIDENCE_ENDPOINT_INCOMPLETE")
    if report.get("product_endpoint_failures") not in ([], ()):
        raise RuntimeError("ARC3_PRODUCT_EVIDENCE_ENDPOINT_FAILURE_PRESENT")

    reference_path = REPOSITORY_ROOT / REFERENCE_PATH
    reference_bytes = reference_path.read_bytes()
    reference = _load_object(reference_path)
    expected = _reference_results(reference)
    actual = _actual_results(report)
    if actual != expected:
        raise RuntimeError("ARC3_PRODUCT_EVIDENCE_REFERENCE_RESULT_MISMATCH")

    evidence: dict[str, object] = {
        **report,
        "evidence_schema_version": "arc3-product-run-evidence-v1",
        "evidence_stage": stage,
        "implementation_commit": implementation_commit,
        "source_report_sha256": _sha256(source_bytes),
        "source_report_size_bytes": len(source_bytes),
        "reference_report_path": REFERENCE_PATH.as_posix(),
        "reference_report_sha256": _sha256(reference_bytes),
        "per_game_reference_exact": True,
    }
    digest = _sha256(_canonical_json(evidence).encode("utf-8"))
    return {
        **evidence,
        "content_digest": "arc3-product-run-evidence:" + digest,
    }


def write_evidence(
    *,
    source_report: Path,
    output: Path,
    stage: str,
    implementation_commit: str,
) -> dict[str, object]:
    evidence = build_evidence(
        source_report=source_report,
        stage=stage,
        implementation_commit=implementation_commit,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(evidence, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return evidence


def parse_arguments(argv: Sequence[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--stage",
        choices=("M4_CANONICAL_FULL_SAMPLE", "M5_CLEAN_INSTALL_FULL_SAMPLE"),
        required=True,
    )
    parser.add_argument("--implementation-commit", required=True)
    return parser.parse_args(argv)


def main(argv: Sequence[str] | None = None) -> int:
    arguments = parse_arguments(argv)
    evidence = write_evidence(
        source_report=arguments.source_report.resolve(),
        output=arguments.output.resolve(),
        stage=arguments.stage,
        implementation_commit=arguments.implementation_commit,
    )
    print(
        json.dumps(
            {
                "content_digest": evidence["content_digest"],
                "output": arguments.output.resolve().as_posix(),
                "product_status": evidence["product_status"],
                "stage": evidence["evidence_stage"],
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
