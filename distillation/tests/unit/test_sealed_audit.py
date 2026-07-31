"""PH-D03B commitment-only sealed-audit tests."""

from __future__ import annotations

import ast
import copy
import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections.abc import Mapping
from functools import lru_cache
from pathlib import Path
from typing import cast

import pytest

from hds_distill.canonical import (
    JsonValue,
    canonical_json_document_bytes,
    verify_canonical_json_document_bytes,
)
from hds_distill.ir_types import JsonObject
from hds_distill.sealed_audit import (
    COMMITMENTS_PATH,
    CONTRACT_PATH,
    CORPUS_VERSION,
    EXACT_INPUTS,
    EXPECTED_COMMITMENT_COUNT,
    FREEZE_REPORT_PATH,
    MANIFEST_PATH,
    RUNNER_CONTRACT_PATH,
    SEALED_ARTIFACT_COUNT,
    SEALED_SUBMISSION_VERSION,
    audit_sealed_submission,
    build_phase_d03b_artifacts,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DISTILLATION_SOURCE = REPOSITORY_ROOT / "distillation" / "src"
SEALED_MODULE_PATH = (
    DISTILLATION_SOURCE / "hds_distill" / "sealed_audit.py"
)
BUILD_SCRIPT = REPOSITORY_ROOT / "scripts" / "build_ph_d03b_sealed_audit.py"
RUN_SCRIPT = REPOSITORY_ROOT / "scripts" / "run_ph_d03b_sealed_audit.py"
CANDIDATE_SET_PATH = (
    REPOSITORY_ROOT
    / "distillation"
    / "artifacts"
    / "golden"
    / "candidate_cases.json"
)


@lru_cache(maxsize=1)
def _encoded_artifacts() -> dict[str, bytes]:
    return build_phase_d03b_artifacts(REPOSITORY_ROOT)


def _artifact(relative_path: Path) -> JsonObject:
    payload = _encoded_artifacts()[relative_path.as_posix()]
    return cast(JsonObject, verify_canonical_json_document_bytes(payload))


@lru_cache(maxsize=1)
def _approved_expected_artifacts() -> tuple[JsonObject, ...]:
    candidate = cast(
        JsonObject,
        verify_canonical_json_document_bytes(CANDIDATE_SET_PATH.read_bytes()),
    )
    cases = cast(list[JsonObject], candidate["cases"])
    return tuple(
        copy.deepcopy(
            cast(JsonObject, case["provisional_expected_artifact"])
        )
        for case in cases
    )


def _submission_payload(
    artifacts: tuple[JsonObject, ...] | None = None,
) -> bytes:
    selected = artifacts or _approved_expected_artifacts()
    submission: JsonObject = {
        "schema_version": SEALED_SUBMISSION_VERSION,
        "corpus_version": CORPUS_VERSION,
        "artifact_count": len(selected),
        "artifacts": [copy.deepcopy(item) for item in selected],
    }
    return canonical_json_document_bytes(submission)


def _materialize_runtime_root(tmp_path: Path) -> Path:
    runtime_root = tmp_path / "runtime-root"
    for artifact_path, payload in _encoded_artifacts().items():
        destination = runtime_root / artifact_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
    for source_path in EXACT_INPUTS:
        source = REPOSITORY_ROOT / source_path
        destination = runtime_root / source_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    return runtime_root


def _write_submission(tmp_path: Path, payload: bytes | None = None) -> Path:
    path = tmp_path / "submission.json"
    path.write_bytes(payload or _submission_payload())
    return path


def _walk_keys(value: object) -> set[str]:
    result: set[str] = set()
    if isinstance(value, Mapping):
        for key, child in value.items():
            result.add(str(key))
            result.update(_walk_keys(child))
    elif isinstance(value, list):
        for child in value:
            result.update(_walk_keys(child))
    return result


def test_build_is_exact_canonical_and_does_not_consume_corpus() -> None:
    artifacts = _encoded_artifacts()

    assert len(artifacts) == SEALED_ARTIFACT_COUNT == 5
    assert set(artifacts) == {
        CONTRACT_PATH.as_posix(),
        COMMITMENTS_PATH.as_posix(),
        MANIFEST_PATH.as_posix(),
        RUNNER_CONTRACT_PATH.as_posix(),
        FREEZE_REPORT_PATH.as_posix(),
    }
    for payload in artifacts.values():
        assert canonical_json_document_bytes(
            verify_canonical_json_document_bytes(payload)
        ) == payload
    report = _artifact(FREEZE_REPORT_PATH)
    manifest = _artifact(MANIFEST_PATH)
    assert report["actual_sealed_corpus_execution_count"] == 0
    assert manifest["actual_audit_consumption_count"] == 0


def test_commitments_match_all_approved_targets_without_labels() -> None:
    commitments = _artifact(COMMITMENTS_PATH)
    target_bundle = cast(
        JsonObject,
        json.loads(
            (
                REPOSITORY_ROOT
                / "control"
                / "rev3"
                / "PH-D03A_OWNER_REVIEW_PACKAGE"
                / "exact_target_bundle.json"
            ).read_bytes()
        ),
    )
    targets = cast(list[JsonObject], target_bundle["targets"])
    expected = sorted(
        cast(str, target["provisional_expected_artifact_digest"])
        for target in targets
    )

    assert commitments["commitments"] == expected
    assert commitments["commitment_count"] == EXPECTED_COMMITMENT_COUNT
    assert commitments["fixture_identifier_count"] == 0
    assert commitments["expected_plaintext_stored_count"] == 0
    assert commitments["label_disclosure"] == "NONE"


def test_sealed_artifacts_contain_no_expected_plaintext_or_fixture_ids() -> None:
    forbidden_keys = {
        "expected_artifact",
        "expected_payload",
        "fixture_id",
        "provisional_expected_artifact",
    }
    fixture_ids = {
        cast(str, artifact["fixture_id"])
        for artifact in _approved_expected_artifacts()
    }
    combined = b"".join(_encoded_artifacts().values())

    for payload in _encoded_artifacts().values():
        parsed = verify_canonical_json_document_bytes(payload)
        assert not (_walk_keys(parsed) & forbidden_keys)
    for fixture_id in fixture_ids:
        assert fixture_id.encode("utf-8") not in combined


def test_manifest_freezes_exact_authority_and_source_hashes() -> None:
    manifest = _artifact(MANIFEST_PATH)
    records = cast(list[JsonObject], manifest["source_artifacts"])

    assert manifest["freeze_status"] == (
        "DISTILLATION_CONFORMANCE_CORPUS_FROZEN"
    )
    assert manifest["version_state"] == "FROZEN_UNCONSUMED"
    assert manifest["source_artifact_count"] == len(EXACT_INPUTS) == 7
    assert {record["path"] for record in records} == {
        path.as_posix() for path in EXACT_INPUTS
    }
    for record in records:
        relative_path = Path(cast(str, record["path"]))
        expected_sha256, expected_bound_digest = EXACT_INPUTS[relative_path]
        assert record["sha256"] == expected_sha256
        assert record["bound_digest"] == expected_bound_digest
        assert (
            hashlib.sha256(
                (REPOSITORY_ROOT / relative_path).read_bytes()
            ).hexdigest()
            == expected_sha256
        )


def test_required_gates_and_claim_boundary_are_exact() -> None:
    contract = _artifact(CONTRACT_PATH)
    report = _artifact(FREEZE_REPORT_PATH)
    manifest = _artifact(MANIFEST_PATH)
    entries = cast(list[JsonObject], report["gate_entries"])

    assert cast(JsonObject, contract["gate_contract"])[
        "required_gate_ids"
    ] == ["DG-06", "DG-14"]
    assert [entry["gate_id"] for entry in entries] == ["DG-06", "DG-14"]
    assert all(entry["result"] == "PASS" for entry in entries)
    assert report["failed_requirement_count"] == 0
    assert manifest["claim_boundary"] == (
        "FROZEN_IMPLEMENTATION_CONFORMANCE_INPUT_NOT_GENERALITY_PROOF"
    )
    prohibited = cast(JsonObject, contract["claim_boundary"])["prohibited"]
    assert "GENERALITY_PROVEN" in cast(list[JsonValue], prohibited)
    assert "RUNTIME_READY" in cast(list[JsonValue], prohibited)


def test_first_matching_attempt_passes_and_same_ledger_reuse_fails(
    tmp_path: Path,
) -> None:
    runtime_root = _materialize_runtime_root(tmp_path)
    submission = _write_submission(tmp_path)
    ledger = tmp_path / "external-ledger.json"

    assert audit_sealed_submission(runtime_root, submission, ledger) == "PASS"
    assert audit_sealed_submission(runtime_root, submission, ledger) == "FAIL"
    consumed = cast(
        JsonObject,
        verify_canonical_json_document_bytes(ledger.read_bytes()),
    )
    assert consumed["state"] == "CONSUMED"
    assert consumed["result"] == "PASS"


def test_failed_submission_consumes_version_and_blocks_later_match(
    tmp_path: Path,
) -> None:
    runtime_root = _materialize_runtime_root(tmp_path)
    invalid = _write_submission(tmp_path, b"{}\n")
    matching = tmp_path / "matching.json"
    matching.write_bytes(_submission_payload())
    ledger = tmp_path / "external-ledger.json"

    assert audit_sealed_submission(runtime_root, invalid, ledger) == "FAIL"
    assert audit_sealed_submission(runtime_root, matching, ledger) == "FAIL"
    consumed = cast(
        JsonObject,
        verify_canonical_json_document_bytes(ledger.read_bytes()),
    )
    assert consumed["state"] == "CONSUMED"
    assert consumed["result"] == "FAIL"


def test_copied_declared_digest_does_not_mask_changed_artifact(
    tmp_path: Path,
) -> None:
    runtime_root = _materialize_runtime_root(tmp_path)
    artifacts = list(copy.deepcopy(_approved_expected_artifacts()))
    artifacts[0]["unexpected_probe"] = "changed"
    submission = _write_submission(tmp_path, _submission_payload(tuple(artifacts)))
    ledger = tmp_path / "external-ledger.json"

    assert audit_sealed_submission(runtime_root, submission, ledger) == "FAIL"


def test_ledger_inside_repository_fails_without_creating_state(
    tmp_path: Path,
) -> None:
    runtime_root = _materialize_runtime_root(tmp_path)
    submission = _write_submission(tmp_path)
    ledger = runtime_root / "mutable-ledger.json"

    assert audit_sealed_submission(runtime_root, submission, ledger) == "FAIL"
    assert not ledger.exists()


def test_corrupt_static_bundle_fails_before_consumption(tmp_path: Path) -> None:
    runtime_root = _materialize_runtime_root(tmp_path)
    contract_path = runtime_root / CONTRACT_PATH
    contract = cast(
        JsonObject,
        verify_canonical_json_document_bytes(contract_path.read_bytes()),
    )
    contract["phase_id"] = "PH-D05"
    contract_path.write_bytes(canonical_json_document_bytes(contract))
    submission = _write_submission(tmp_path)
    ledger = tmp_path / "external-ledger.json"

    assert audit_sealed_submission(runtime_root, submission, ledger) == "FAIL"
    assert not ledger.exists()


@pytest.mark.parametrize(
    "relative_path",
    (
        Path(
            "control/rev3/OWNER_APPROVAL_RECORDS/"
            "PH-D03A_TO_PH-D03B_20260731.json"
        ),
        Path("distillation/artifacts/golden/candidate_cases.json"),
    ),
)
def test_bound_source_or_approval_drift_fails_before_consumption(
    tmp_path: Path,
    relative_path: Path,
) -> None:
    runtime_root = _materialize_runtime_root(tmp_path)
    target = runtime_root / relative_path
    target.write_bytes(target.read_bytes() + b" ")
    submission = _write_submission(tmp_path)
    ledger = tmp_path / "external-ledger.json"

    assert audit_sealed_submission(runtime_root, submission, ledger) == "FAIL"
    assert not ledger.exists()


def test_status_cli_emits_only_pass_or_fail(tmp_path: Path) -> None:
    runtime_root = _materialize_runtime_root(tmp_path)
    submission = _write_submission(tmp_path)
    ledger = tmp_path / "external-ledger.json"
    command = [
        sys.executable,
        str(RUN_SCRIPT),
        "--root",
        str(runtime_root),
        "--submission",
        str(submission),
        "--ledger",
        str(ledger),
    ]

    first = subprocess.run(
        command,
        check=False,
        capture_output=True,
        cwd=tmp_path,
    )
    second = subprocess.run(
        command,
        check=False,
        capture_output=True,
        cwd=tmp_path,
    )
    assert first.returncode == 0
    assert first.stdout == b"PASS\n"
    assert first.stderr == b""
    assert second.returncode == 1
    assert second.stdout == b"FAIL\n"
    assert second.stderr == b""


def test_builder_cli_writes_only_five_artifacts_and_no_ledger(
    tmp_path: Path,
) -> None:
    runtime_root = tmp_path / "build-root"
    for relative_path in EXACT_INPUTS:
        destination = runtime_root / relative_path
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(REPOSITORY_ROOT / relative_path, destination)
    process = subprocess.run(
        [
            sys.executable,
            str(BUILD_SCRIPT),
            "--root",
            str(runtime_root),
        ],
        check=False,
        capture_output=True,
        text=True,
        cwd=tmp_path,
    )

    assert process.returncode == 0, process.stderr
    assert process.stderr == ""
    result = cast(JsonObject, json.loads(process.stdout))
    assert result["status"] == "PASS"
    assert result["artifact_count"] == SEALED_ARTIFACT_COUNT
    assert result["actual_audit_consumption_count"] == 0
    assert {
        path.relative_to(runtime_root).as_posix()
        for path in runtime_root.rglob("*.json")
        if path.relative_to(runtime_root) not in EXACT_INPUTS
    } == set(_encoded_artifacts())
    assert not list(runtime_root.rglob("*ledger*"))


def test_three_independent_process_rebuilds_are_byte_identical(
    tmp_path: Path,
) -> None:
    source = """\
import hashlib
from pathlib import Path
from hds_distill.sealed_audit import build_phase_d03b_artifacts

root = Path.cwd()
artifacts = build_phase_d03b_artifacts(root)
aggregate = hashlib.sha256()
for path, payload in sorted(artifacts.items()):
    aggregate.update(path.encode("utf-8"))
    aggregate.update(b"\\0")
    aggregate.update(payload)
print(aggregate.hexdigest())
"""
    environment = dict(os.environ)
    environment["PYTHONPATH"] = str(DISTILLATION_SOURCE)
    outputs = [
        subprocess.run(
            [sys.executable, "-c", source],
            check=True,
            capture_output=True,
            text=True,
            cwd=REPOSITORY_ROOT,
            env=environment,
        ).stdout
        for _ in range(3)
    ]

    assert outputs[0] == outputs[1] == outputs[2]
    assert len(outputs[0].strip()) == 64
    assert not list(tmp_path.rglob("*"))


def test_runtime_loader_never_parses_golden_expected_plaintext() -> None:
    source = SEALED_MODULE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(source)
    loader = next(
        node
        for node in tree.body
        if isinstance(node, ast.FunctionDef)
        and node.name == "_load_runtime_bundle"
    )
    called_names = {
        node.func.id
        for node in ast.walk(loader)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
    }
    loader_source = ast.get_source_segment(source, loader)

    assert "_exact_sources" not in called_names
    assert "_expected_digests" not in called_names
    assert loader_source is not None
    assert "provisional_expected_artifact" not in loader_source
    assert "json.loads" not in loader_source
