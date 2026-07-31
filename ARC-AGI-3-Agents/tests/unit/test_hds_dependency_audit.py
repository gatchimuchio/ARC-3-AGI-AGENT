from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
AUDITOR_PATH = REPOSITORY_ROOT / "scripts" / "audit_hds_dependencies.py"
AUDITOR_SPEC = importlib.util.spec_from_file_location(
    "arc3_hds_dependency_auditor_test_target",
    AUDITOR_PATH,
)
assert AUDITOR_SPEC is not None and AUDITOR_SPEC.loader is not None
AUDITOR: ModuleType = importlib.util.module_from_spec(AUDITOR_SPEC)
sys.modules[AUDITOR_SPEC.name] = AUDITOR
AUDITOR_SPEC.loader.exec_module(AUDITOR)

MANIFEST_PATH = (
    REPOSITORY_ROOT
    / "artifacts"
    / "source_content_manifests"
    / "hds_dependencies.json"
)
REPORT_PATH = (
    REPOSITORY_ROOT
    / "artifacts"
    / "reports"
    / "dependency_audit.json"
)
OPEN_TERM_LEDGER_PATH = (
    REPOSITORY_ROOT
    / "artifacts"
    / "reports"
    / "open_term_ledger.json"
)


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _write_canonical(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        AUDITOR.canonical_json(payload) + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _rebind_digest(
    payload: dict[str, Any],
    namespace: str,
    excluded_fields: tuple[str, ...],
) -> None:
    payload["content_digest"] = AUDITOR.artifact_content_digest(
        payload,
        namespace=namespace,
        expected_excluded_fields=excluded_fields,
    )


def test_current_dependency_lock_passes_fail_closed_contract() -> None:
    selector = _json(
        REPOSITORY_ROOT
        / "control"
        / "rev3"
        / "REV3_CURRENT_SELECTOR.json"
    )
    assert selector["installation_status"] == "INSTALLED"
    assert selector["ph_r1_status"] == "OWNER_APPROVED_PASS"
    assert selector["active_phase"] == "PH-D02B"
    assert selector["current_work_class"] == (
        "PH-D02B_SCHEMA_SET_BUNDLE_CONTRACT_REBIND"
    )
    assert selector["ph_r00_owner_authorization"] == "ESTABLISHED"
    assert selector["ph_r00_status"] == "OWNER_APPROVED_PASS"
    assert selector["ph_d00a_status"] == "OWNER_APPROVED_PASS"
    assert selector["ph_d00b_status"] == "OWNER_APPROVED_PASS"
    assert selector["ph_d01a_status"] == "OWNER_APPROVED_PASS"
    assert selector["ph_d01b_status"] == "OWNER_APPROVED_PASS"
    assert selector["ph_d02a_status"] == "OWNER_APPROVED_PASS"
    assert selector["ph_d02b_status"] == "IN_PROGRESS"
    assert selector["runtime_activation_status"] == "SUSPEND"
    assert (
        selector["historical_evidence"]["classification"]
        == "HISTORICAL_PRE_AUDIT_NONAUTHORITATIVE"
    )

    report = AUDITOR.audit_repository(REPOSITORY_ROOT)
    assert report == _json(REPORT_PATH)
    assert report["hds_dependency_match"] is True
    assert report["authority_defined"] is True
    assert report["unresolved_dependency_count"] == 0


def test_cli_accepts_current_checked_report() -> None:
    process = subprocess.run(
        [
            sys.executable,
            str(AUDITOR_PATH),
            "--root",
            str(REPOSITORY_ROOT),
            "--verify-report",
            str(REPORT_PATH),
        ],
        check=False,
        capture_output=True,
        text=True,
    )

    assert process.returncode == 0
    assert process.stderr == ""
    assert process.stdout.startswith(
        "DEPENDENCY_LOCK_PASS:hds-dependency-audit-report:"
    )


@pytest.mark.parametrize(
    "path",
    [MANIFEST_PATH, REPORT_PATH, OPEN_TERM_LEDGER_PATH],
)
def test_phase_artifacts_are_physically_canonical(path: Path) -> None:
    payload = _json(path)

    assert path.read_text(encoding="utf-8") == (
        AUDITOR.canonical_json(payload) + "\n"
    )


def test_three_live_rebuild_attempts_are_byte_identical() -> None:
    reports: list[str] = []
    for _ in range(3):
        reports.append(
            AUDITOR.canonical_json(
                AUDITOR.audit_repository(REPOSITORY_ROOT)
            )
        )

    assert len(set(reports)) == 1
    assert reports[0] + "\n" == REPORT_PATH.read_text(encoding="utf-8")


def test_recomputed_manifest_drift_still_fails_closed(tmp_path: Path) -> None:
    manifest = _json(MANIFEST_PATH)
    manifest["local_dependencies"][0]["sha256"] = "0" * 64
    _rebind_digest(
        manifest,
        "hds-dependency-lock",
        ("content_digest", "manifest_id"),
    )
    mutated = tmp_path / "hds_dependencies.json"
    _write_canonical(mutated, manifest)

    with pytest.raises(
        AUDITOR.AuditFailure,
        match="DG00_LOCAL_DEPENDENCY_LOCK_MISMATCH",
    ):
        AUDITOR.audit_repository(REPOSITORY_ROOT, manifest_path=mutated)


def test_unknown_manifest_field_fails_closed(tmp_path: Path) -> None:
    manifest = _json(MANIFEST_PATH)
    manifest["undeclared"] = "forbidden"
    mutated = tmp_path / "hds_dependencies.json"
    _write_canonical(mutated, manifest)

    with pytest.raises(AUDITOR.AuditFailure, match="DG00_UNKNOWN_FIELD"):
        AUDITOR.audit_repository(REPOSITORY_ROOT, manifest_path=mutated)


def test_bool_cannot_impersonate_integer(tmp_path: Path) -> None:
    manifest = _json(MANIFEST_PATH)
    manifest["local_dependencies"][0]["size_bytes"] = True
    _rebind_digest(
        manifest,
        "hds-dependency-lock",
        ("content_digest", "manifest_id"),
    )
    mutated = tmp_path / "hds_dependencies.json"
    _write_canonical(mutated, manifest)

    with pytest.raises(AUDITOR.AuditFailure, match="DG00_INTEGER_REQUIRED"):
        AUDITOR.audit_repository(REPOSITORY_ROOT, manifest_path=mutated)


def test_repository_path_escape_fails_closed(tmp_path: Path) -> None:
    manifest = _json(MANIFEST_PATH)
    manifest["local_dependencies"][0]["path"] = "../outside.md"
    _rebind_digest(
        manifest,
        "hds-dependency-lock",
        ("content_digest", "manifest_id"),
    )
    mutated = tmp_path / "hds_dependencies.json"
    _write_canonical(mutated, manifest)

    with pytest.raises(
        AUDITOR.AuditFailure,
        match="DG00_REPOSITORY_PATH_INVALID",
    ):
        AUDITOR.audit_repository(REPOSITORY_ROOT, manifest_path=mutated)


def test_nonempty_dependency_open_term_fails_closed(tmp_path: Path) -> None:
    ledger = _json(OPEN_TERM_LEDGER_PATH)
    ledger["open_terms"] = [
        {
            "content_digest": "hds-open-term-record:" + "0" * 64,
            "digest_excluded_fields": ["content_digest", "open_term_id"],
            "open_term_id": "UNRESOLVED-DEPENDENCY",
            "phase_id": "PH-D00A",
            "question": "Which dependency is authoritative?",
            "schema_version": "hds-open-term-record-v1",
            "status": "OPEN",
        }
    ]
    ledger["open_term_count"] = 1
    ledger["unresolved_dependency_count"] = 1
    _rebind_digest(
        ledger,
        "hds-open-term-ledger",
        ("content_digest", "ledger_id"),
    )
    mutated = tmp_path / "open_term_ledger.json"
    _write_canonical(mutated, ledger)

    with pytest.raises(
        AUDITOR.AuditFailure,
        match="DG01_OPEN_TERM_LEDGER_NOT_EMPTY",
    ):
        AUDITOR._validate_open_term_ledger(REPOSITORY_ROOT, mutated)


def test_schemas_forbid_unknown_fields_and_require_digest() -> None:
    dependency_schema = _json(
        REPOSITORY_ROOT / "schemas" / "dependency_lock.schema.json"
    )
    open_term_schema = _json(
        REPOSITORY_ROOT / "schemas" / "open_term_record.schema.json"
    )

    for schema in (dependency_schema, open_term_schema):
        assert schema["$schema"] == (
            "https://json-schema.org/draft/2020-12/schema"
        )
        assert schema["additionalProperties"] is False
        assert "schema_version" in schema["required"]
        assert "content_digest" in schema["required"]


def test_auditor_has_no_arc_runtime_or_corpus_dependency() -> None:
    source = AUDITOR_PATH.read_text(encoding="utf-8")

    assert "arc3_agi_agent" not in source
    assert "datasets/" not in source
    assert "analysis/autonomous_completion" not in source
    assert "kaggle" not in source.casefold()
    assert "requests" not in source


def test_missing_translator_git_directory_is_visible_failure(
    tmp_path: Path,
) -> None:
    missing = tmp_path / "missing.git"

    with pytest.raises(
        AUDITOR.AuditFailure,
        match="DG00_TRANSLATOR_GIT_DIR_MISSING",
    ):
        AUDITOR.validate_translator_git_objects(missing)
