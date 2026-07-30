from __future__ import annotations

import copy
import hashlib
import json
import subprocess
from pathlib import Path
from typing import Any, cast

import pytest

from hds_distill.source_inventory import (
    ANSWER_VISIBILITIES,
    CONTAMINATION_CLASSES,
    DEVELOPMENT_USAGES,
    MATERIALIZATION_STATES,
    PROFILE_TYPES,
    REPORT_DIGEST_EXCLUDED_FIELDS,
    REPORT_DIGEST_NAMESPACE,
    SOURCE_CODE_ACCESS_STATES,
    SPLIT_ROLES,
    SourceInventoryError,
    build_source_inventory,
    canonical_json,
    report_bytes,
    verify_source_inventory_report,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PROJECT_ROOT = REPOSITORY_ROOT / "distillation"
PROFILE_ROOT = PROJECT_ROOT / "profiles" / "source"
REPORT_PATH = PROJECT_ROOT / "artifacts" / "reports" / "source_inventory.json"
SCHEMA_PATH = PROJECT_ROOT / "schemas" / "source_profile.schema.json"


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected object: {path}")
    return value


def _profiles() -> dict[str, dict[str, Any]]:
    return {
        path.relative_to(REPOSITORY_ROOT).as_posix(): _json(path)
        for path in sorted(PROFILE_ROOT.glob("*.json"))
    }


def _profile_path(profile_id: str) -> str:
    for path, profile in _profiles().items():
        if profile["profile_id"] == profile_id:
            return path
    raise KeyError(profile_id)


def _rebind_profile(profile: dict[str, Any]) -> None:
    body = dict(profile)
    body.pop("content_digest")
    profile["content_digest"] = "hds-source-profile:" + hashlib.sha256(
        canonical_json(cast(Any, body)).encode("utf-8")
    ).hexdigest()


def _tracked_paths() -> dict[str, tuple[str, ...]]:
    plan = _json(PROJECT_ROOT / "input" / "source_inventory_plan.json")
    result: dict[str, tuple[str, ...]] = {}
    for raw_row in plan["repository_candidate_roots"]:
        root = str(raw_row["root"])
        process = subprocess.run(
            ["git", "ls-files", "--", root],
            cwd=REPOSITORY_ROOT,
            check=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        result[root] = tuple(sorted(process.stdout.splitlines()))
    return result


def test_live_inventory_matches_checked_report_and_all_gates_pass() -> None:
    report = build_source_inventory(
        PROJECT_ROOT,
        repository_root=REPOSITORY_ROOT,
    )
    checked = _json(REPORT_PATH)

    assert report == checked
    assert REPORT_PATH.read_bytes() == report_bytes(report)
    assert report["gates"] == {
        "DG-00": "PASS",
        "DG-06": "PASS",
        "DG-09": "PASS",
    }
    assert report["phase_exit_claim"] == "PH_D01A_SOURCE_INVENTORY_PASS"


def test_all_83_sources_have_one_profile_and_no_unknown_classification() -> None:
    report = build_source_inventory(
        PROJECT_ROOT,
        repository_root=REPOSITORY_ROOT,
    )
    records = cast(list[dict[str, Any]], report["source_records"])
    source_ids = [str(record["source_id"]) for record in records]

    assert len(records) == 83
    assert len(source_ids) == len(set(source_ids))
    assert report["unknown_answer_visibility_count"] == 0
    assert report["unknown_split_role_count"] == 0
    assert report["duplicate_source_assignment_count"] == 0
    assert report["unassigned_admitted_source_count"] == 0
    assert report["policy_weight_admitted_source_count"] == 0


def test_profile_type_and_split_accounting_is_complete() -> None:
    report = build_source_inventory(
        PROJECT_ROOT,
        repository_root=REPOSITORY_ROOT,
    )

    assert report["counts_by_profile_type"] == {
        "ARC2_INTERNAL_NORMALIZED_CORPUS": 0,
        "ARC2_KAGGLE_CHALLENGE_SOLUTION": 5,
        "ARC2_OFFICIAL_TASK_JSON": 0,
        "ARC3_CANONICAL_TEACHER_TRAJECTORY": 3,
        "ARC3_ENVIRONMENT_SOURCE_BUNDLE": 50,
        "ARC3_RAW_TEACHER_RECORDING": 25,
    }
    assert report["counts_by_split_role"] == {
        "PUBLIC_EVALUATION_CONSUMED": 28,
        "PUBLIC_EVALUATION_TEACHER": 2,
        "REPLAY_ONLY_SOURCE": 50,
        "SEALED_AUDIT": 0,
        "TRAIN_TEACHER": 2,
        "UNLABELED_TEST": 1,
    }


def test_environment_source_is_replay_only_and_archive_aliases_are_not_doubled(
) -> None:
    report = build_source_inventory(
        PROJECT_ROOT,
        repository_root=REPOSITORY_ROOT,
    )
    records = cast(list[dict[str, Any]], report["source_records"])
    environment_records = [
        record
        for record in records
        if record["profile_type"] == "ARC3_ENVIRONMENT_SOURCE_BUNDLE"
    ]

    assert len(environment_records) == 50
    assert report["arc3_distribution_alias_count"] == 50
    assert all(
        record["source_code_access"] == "REPLAY_HARNESS_ONLY"
        and record["development_usage"] == "REPLAY_HARNESS_ONLY"
        and record["split_role"] == "REPLAY_ONLY_SOURCE"
        and len(record["aliases"]) == 1
        for record in environment_records
    )


def test_public_25_and_canonical_corpus_are_explicitly_consumed() -> None:
    report = build_source_inventory(
        PROJECT_ROOT,
        repository_root=REPOSITORY_ROOT,
    )
    records = cast(list[dict[str, Any]], report["source_records"])
    consumed = [
        record
        for record in records
        if record["split_role"] == "PUBLIC_EVALUATION_CONSUMED"
    ]

    assert len(consumed) == 28
    assert {record["profile_type"] for record in consumed} == {
        "ARC3_RAW_TEACHER_RECORDING",
        "ARC3_CANONICAL_TEACHER_TRAJECTORY",
    }
    assert all(
        record["development_usage"] == "DISTILLATION_SOURCE"
        and record["contamination_class"]
        == "PUBLIC_EVALUATION_SUCCESS_TRAJECTORY_CONSUMED"
        for record in consumed
    )


def test_arc2_evaluation_answer_is_visible_but_not_claimed_consumed() -> None:
    report = build_source_inventory(
        PROJECT_ROOT,
        repository_root=REPOSITORY_ROOT,
    )
    records = cast(list[dict[str, Any]], report["source_records"])
    [evaluation_solution] = [
        record
        for record in records
        if str(record["locator"]).endswith(
            "arc-agi_evaluation_solutions.json"
        )
    ]

    assert evaluation_solution["split_role"] == (
        "PUBLIC_EVALUATION_TEACHER"
    )
    assert evaluation_solution["answer_visibility"] == "ANSWER_VISIBLE"
    assert evaluation_solution["development_usage"] == (
        "AVAILABLE_TEACHER_NOT_CONSUMED"
    )
    assert evaluation_solution["contamination_class"] == (
        "PUBLIC_EVALUATION_ANSWER_VISIBLE_NOT_CONSUMED"
    )


def test_schema_enums_match_the_runtime_contract() -> None:
    schema = _json(SCHEMA_PATH)
    properties = schema["properties"]

    assert set(properties["profile_type"]["enum"]) == PROFILE_TYPES
    assert set(properties["split_role"]["enum"]) == SPLIT_ROLES
    assert set(properties["answer_visibility"]["enum"]) == (
        ANSWER_VISIBILITIES
    )
    assert set(properties["development_usage"]["enum"]) == (
        DEVELOPMENT_USAGES
    )
    assert set(properties["contamination_class"]["enum"]) == (
        CONTAMINATION_CLASSES
    )
    assert set(properties["materialization_state"]["enum"]) == (
        MATERIALIZATION_STATES
    )
    assert set(properties["source_code_access"]["enum"]) == (
        SOURCE_CODE_ACCESS_STATES
    )
    assert schema["additionalProperties"] is False


def test_report_and_profile_digests_are_deterministic() -> None:
    reports = [
        build_source_inventory(
            PROJECT_ROOT,
            repository_root=REPOSITORY_ROOT,
        )
        for _ in range(3)
    ]
    encoded = [report_bytes(report) for report in reports]
    assert encoded[0] == encoded[1] == encoded[2]

    body = dict(reports[0])
    claimed = str(body["content_digest"])
    for field in REPORT_DIGEST_EXCLUDED_FIELDS:
        body.pop(field)
    expected = REPORT_DIGEST_NAMESPACE + ":" + hashlib.sha256(
        canonical_json(cast(Any, body)).encode("utf-8")
    ).hexdigest()
    assert claimed == expected


def test_unknown_profile_field_fails_closed() -> None:
    profiles = _profiles()
    path = _profile_path("arc2-training-challenges")
    profiles[path]["unexpected"] = True

    with pytest.raises(
        SourceInventoryError,
        match="D01A_PROFILE_UNKNOWN_FIELDS",
    ):
        build_source_inventory(
            PROJECT_ROOT,
            repository_root=REPOSITORY_ROOT,
            profile_documents=cast(Any, profiles),
        )


def test_unknown_split_and_answer_visibility_fail_closed() -> None:
    for field, value, error in (
        ("split_role", "UNKNOWN", "D01A_SPLIT_ROLE_UNKNOWN"),
        (
            "answer_visibility",
            "UNKNOWN",
            "D01A_ANSWER_VISIBILITY_UNKNOWN",
        ),
    ):
        profiles = _profiles()
        path = _profile_path("arc2-training-challenges")
        profiles[path][field] = value
        with pytest.raises(SourceInventoryError, match=error):
            build_source_inventory(
                PROJECT_ROOT,
                repository_root=REPOSITORY_ROOT,
                profile_documents=cast(Any, profiles),
            )


def test_policy_weight_admission_fails_closed() -> None:
    profiles = _profiles()
    path = _profile_path("arc3-canonical-teacher-trajectories")
    profiles[path]["policy_weight_source"] = True

    with pytest.raises(
        SourceInventoryError,
        match="D01A_POLICY_WEIGHT_SOURCE_FORBIDDEN",
    ):
        build_source_inventory(
            PROJECT_ROOT,
            repository_root=REPOSITORY_ROOT,
            profile_documents=cast(Any, profiles),
        )


def test_undeclared_evaluation_answer_consumption_fails_closed() -> None:
    profiles = _profiles()
    path = _profile_path("arc2-evaluation-solutions")
    profile = profiles[path]
    profile["development_usage"] = "DISTILLATION_SOURCE"
    _rebind_profile(profile)

    with pytest.raises(
        SourceInventoryError,
        match="D01A_EVALUATION_ANSWER_CONSUMPTION_UNDECLARED",
    ):
        build_source_inventory(
            PROJECT_ROOT,
            repository_root=REPOSITORY_ROOT,
            profile_documents=cast(Any, profiles),
        )


def test_environment_source_access_leak_fails_closed() -> None:
    profiles = _profiles()
    path = _profile_path("arc3-environment-source-bundle")
    profile = profiles[path]
    profile["source_code_access"] = "NOT_SOURCE_CODE"
    _rebind_profile(profile)

    with pytest.raises(
        SourceInventoryError,
        match="D01A_ENVIRONMENT_SOURCE_ACCESS_INVALID",
    ):
        build_source_inventory(
            PROJECT_ROOT,
            repository_root=REPOSITORY_ROOT,
            profile_documents=cast(Any, profiles),
        )


def test_profile_materialization_selector_mismatch_fails_closed() -> None:
    profiles = _profiles()
    path = _profile_path("arc3-environment-source-bundle")
    profile = profiles[path]
    profile["materialization_state"] = "EXTERNAL_ARCHIVE_VERIFIED"
    _rebind_profile(profile)

    with pytest.raises(
        SourceInventoryError,
        match="D01A_PROFILE_MATERIALIZATION_INVALID",
    ):
        build_source_inventory(
            PROJECT_ROOT,
            repository_root=REPOSITORY_ROOT,
            profile_documents=cast(Any, profiles),
        )


def test_archive_distribution_binding_drift_fails_closed() -> None:
    profiles = _profiles()
    path = _profile_path("arc2-training-challenges")
    profile = profiles[path]
    profile["selectors"][0]["expected_distribution_sha256"] = "0" * 64
    _rebind_profile(profile)

    with pytest.raises(
        SourceInventoryError,
        match="D01A_ARC2_DISTRIBUTION_BINDING_MISMATCH",
    ):
        build_source_inventory(
            PROJECT_ROOT,
            repository_root=REPOSITORY_ROOT,
            profile_documents=cast(Any, profiles),
        )


def test_duplicate_assignment_fails_closed() -> None:
    profiles = _profiles()
    source_path = _profile_path("arc2-training-solutions")
    profile = profiles[source_path]
    selector = profile["selectors"][0]
    selector["members"] = ["arc-agi_training_challenges.json"]
    _rebind_profile(profile)

    with pytest.raises(
        SourceInventoryError,
        match="D01A_SOURCE_ASSIGNMENT_DUPLICATE",
    ):
        build_source_inventory(
            PROJECT_ROOT,
            repository_root=REPOSITORY_ROOT,
            profile_documents=cast(Any, profiles),
        )


def test_candidate_path_set_drift_fails_closed() -> None:
    tracked = _tracked_paths()
    tracked["environment_files"] = tracked["environment_files"][:-1]

    with pytest.raises(
        SourceInventoryError,
        match="D01A_CANDIDATE_PATH_SET_DRIFT",
    ):
        build_source_inventory(
            PROJECT_ROOT,
            repository_root=REPOSITORY_ROOT,
            tracked_paths_by_root=tracked,
        )


def test_raw_recording_locator_drift_fails_closed() -> None:
    manifest = _json(
        REPOSITORY_ROOT
        / "analysis"
        / "teacher"
        / "HUMAN_WINNING_REPLAY_SOURCE_MANIFEST.json"
    )
    manifest = copy.deepcopy(manifest)
    manifest["rows"][0]["recording_file"] = "changed.recording"

    with pytest.raises(
        SourceInventoryError,
        match="D01A_RECORDING_FILENAME_SET_DRIFT",
    ):
        build_source_inventory(
            PROJECT_ROOT,
            repository_root=REPOSITORY_ROOT,
            source_manifest_document=cast(Any, manifest),
        )


def test_source_payload_files_are_not_read(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    original = Path.read_text
    forbidden = {
        "analysis/teacher/FULL_SOLUTION_CORPUS.json",
        "analysis/teacher/S5_RENDERED_POLICY_TRAINING_CORPUS.json",
    }

    def guarded_read_text(
        path: Path,
        encoding: str | None = None,
        errors: str | None = None,
    ) -> str:
        try:
            relative = path.resolve().relative_to(REPOSITORY_ROOT).as_posix()
        except ValueError:
            relative = ""
        if relative.startswith("environment_files/") or relative in forbidden:
            raise AssertionError(f"source payload read: {relative}")
        return original(path, encoding=encoding, errors=errors)

    monkeypatch.setattr(Path, "read_text", guarded_read_text)
    report = build_source_inventory(
        PROJECT_ROOT,
        repository_root=REPOSITORY_ROOT,
    )
    assert report["source_payload_access"] == {
        "payload_parse_count": 0,
        "replay_execution_count": 0,
        "source_execution_count": 0,
    }


def test_checked_report_verifier_rejects_drift(tmp_path: Path) -> None:
    checked = tmp_path / "source_inventory.json"
    checked.write_bytes(REPORT_PATH.read_bytes() + b"\n")

    with pytest.raises(
        SourceInventoryError,
        match="D01A_REPORT_MISMATCH",
    ):
        verify_source_inventory_report(
            checked,
            PROJECT_ROOT,
            repository_root=REPOSITORY_ROOT,
        )
