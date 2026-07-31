from __future__ import annotations

import copy
import hashlib
import json
from pathlib import Path, PurePosixPath
from typing import Any, cast

import pytest

import hds_distill.manifest_freeze as manifest_freeze
from hds_distill.manifest_freeze import (
    ACQUISITION_DIGEST_NAMESPACE,
    CAPTURE_DIGEST_NAMESPACE,
    ENVIRONMENT_DIGEST_NAMESPACE,
    ManifestFreezeError,
    artifact_bytes,
    build_manifest_freeze,
    build_source_content_manifest,
    directory_merkle_root,
    validate_acquisition_record,
    validate_environment_manifest,
    validate_run_manifest,
    validate_source_content_manifest,
    verify_manifest_freeze_artifacts,
)
from hds_distill.source_inventory import canonical_json

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PROJECT_ROOT = REPOSITORY_ROOT / "distillation"
PLAN_PATH = PROJECT_ROOT / "input" / "manifest_freeze_plan.json"
CAPTURE_PATH = (
    PROJECT_ROOT / "input" / "raw_recording_content_capture.json"
)
SOURCE_INVENTORY_PATH = (
    PROJECT_ROOT / "artifacts" / "reports" / "source_inventory.json"
)
FREEZE_REPORT_PATH = (
    PROJECT_ROOT / "artifacts" / "reports" / "source_manifest_freeze.json"
)
ISOLATION_REPORT_PATH = (
    PROJECT_ROOT / "artifacts" / "reports" / "environment_isolation.json"
)
ENVIRONMENT_MANIFEST_PATH = (
    PROJECT_ROOT / "manifests" / "environment" / "arc3-replay.json"
)
RUN_MANIFEST_PATH = (
    PROJECT_ROOT / "manifests" / "run" / "ph-d01b-freeze.json"
)
DISTRIBUTION_PATHS = {
    "arc-prize-2026-arc-agi-2.zip": (
        REPOSITORY_ROOT.parent
        / "Downloads"
        / "arc-prize-2026-arc-agi-2.zip"
    ),
    "arc-prize-2026-arc-agi-3.zip": (
        REPOSITORY_ROOT.parent
        / "Downloads"
        / "arc-prize-2026-arc-agi-3.zip"
    ),
}


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected object: {path}")
    return value


def _digest(
    value: dict[str, Any],
    namespace: str,
    excluded_fields: tuple[str, ...],
) -> str:
    body = {
        key: item
        for key, item in value.items()
        if key not in excluded_fields
    }
    return namespace + ":" + hashlib.sha256(
        canonical_json(cast(Any, body)).encode("utf-8")
    ).hexdigest()


def _live_bundle() -> dict[str, Any]:
    for distribution_id, path in DISTRIBUTION_PATHS.items():
        if not path.is_file():
            pytest.fail(
                f"required PH-D01B distribution missing: "
                f"{distribution_id}: {path}"
            )
    return cast(
        dict[str, Any],
        build_manifest_freeze(
            PROJECT_ROOT,
            repository_root=REPOSITORY_ROOT,
            distribution_paths=DISTRIBUTION_PATHS,
        ),
    )


@pytest.fixture(scope="module")
def live_bundle() -> dict[str, Any]:
    return _live_bundle()


def _source_manifest(
    bundle: dict[str, Any],
    profile_id: str,
) -> dict[str, Any]:
    manifests = cast(
        dict[str, dict[str, Any]],
        bundle["source_manifests"],
    )
    return manifests[profile_id]


def _rebuild_source_manifest(
    source_manifest: dict[str, Any],
    files: list[dict[str, Any]],
) -> dict[str, Any]:
    profile = cast(dict[str, Any], source_manifest["source_profile"])
    return cast(
        dict[str, Any],
        build_source_content_manifest(
            manifest_id=str(source_manifest["manifest_id"]),
            profile_id=str(profile["profile_id"]),
            profile_digest=str(profile["profile_digest"]),
            domain=str(source_manifest["domain"]),
            files=files,
            upstream_repository=str(
                source_manifest["upstream_repository"]
            ),
            upstream_commit_or_release=str(
                source_manifest["upstream_commit_or_release"]
            ),
            split_role=str(source_manifest["split_role"]),
            answer_visibility=str(
                source_manifest["answer_visibility"]
            ),
            development_usage=str(
                source_manifest["development_usage"]
            ),
            contamination_class=str(
                source_manifest["contamination_class"]
            ),
            license_value=str(source_manifest["license"]),
        ),
    )


def test_live_bundle_matches_every_checked_artifact(
    live_bundle: dict[str, Any],
) -> None:
    checked = verify_manifest_freeze_artifacts(
        PROJECT_ROOT,
        repository_root=REPOSITORY_ROOT,
        distribution_paths=DISTRIBUTION_PATHS,
    )

    assert checked == live_bundle
    assert artifact_bytes(
        cast(dict[str, Any], live_bundle["freeze_report"])
    ) == FREEZE_REPORT_PATH.read_bytes()
    assert artifact_bytes(
        cast(dict[str, Any], live_bundle["isolation_report"])
    ) == ISOLATION_REPORT_PATH.read_bytes()


def test_eight_manifests_cover_all_83_sources_exactly_once(
    live_bundle: dict[str, Any],
) -> None:
    inventory = _json(SOURCE_INVENTORY_PATH)
    expected_ids = {
        str(record["source_id"])
        for record in cast(
            list[dict[str, Any]],
            inventory["source_records"],
        )
    }
    manifests = cast(
        dict[str, dict[str, Any]],
        live_bundle["source_manifests"],
    )
    actual_ids: list[str] = []
    for manifest in manifests.values():
        validate_source_content_manifest(manifest)
        actual_ids.extend(
            str(record["source_id"])
            for record in cast(
                list[dict[str, Any]],
                manifest["files"],
            )
        )

    assert len(manifests) == 8
    assert len(actual_ids) == 83
    assert len(actual_ids) == len(set(actual_ids))
    assert set(actual_ids) == expected_ids


def test_arc2_authority_member_hashes_are_exact(
    live_bundle: dict[str, Any],
) -> None:
    expected = {
        "arc2-evaluation-challenges": (
            "e7c62a4bd211867c6b538f66b8013b81"
            "f299663c82ca062f49a52bf439d6e4e8"
        ),
        "arc2-evaluation-solutions": (
            "84be4f4f39b79e82c36d565fc8788309"
            "88b094917f052ee7069aef30b33ca8f1"
        ),
        "arc2-test-challenges": (
            "232264c58f825ee77327dcfc9f4e5cb2"
            "f83b8d997eb69032be1bf2205bbe1a83"
        ),
        "arc2-training-challenges": (
            "779eaba89790ebad9af02514a7efc0aef"
            "af2cf8236f046a31bbf8b9ec48f20f5"
        ),
        "arc2-training-solutions": (
            "9f07a38bd25af5e83aa5bf85c5cb1a1f"
            "efdb30f6a755256fa65429e697ca97f9"
        ),
    }

    for profile_id, expected_sha256 in expected.items():
        manifest = _source_manifest(live_bundle, profile_id)
        [record] = cast(list[dict[str, Any]], manifest["files"])
        assert record["sha256"] == expected_sha256
        assert record["verification_method"] == "ARCHIVE_MEMBER_SHA256"


def test_raw_capture_is_revision_bound_and_payload_free() -> None:
    capture = _json(CAPTURE_PATH)
    acquisition = cast(dict[str, Any], capture["acquisition"])
    rows = cast(list[dict[str, Any]], capture["rows"])
    immutable_digest = _digest(
        capture,
        CAPTURE_DIGEST_NAMESPACE,
        ("acquisition", "content_digest"),
    )

    assert capture["content_digest"] == immutable_digest
    assert capture["selected_row_count"] == len(rows) == 25
    assert capture["selected_level_count"] == 183
    assert sum(int(row["target_levels"]) for row in rows) == 183
    assert sum(int(row["trajectory_size_bytes"]) for row in rows) == (
        495_947_429
    )
    assert acquisition["dataset_sha_before_capture"] == (
        capture["dataset_repo_sha"]
    )
    assert acquisition["dataset_sha_after_capture"] == (
        capture["dataset_repo_sha"]
    )
    assert acquisition["api_call_count"] == 27
    assert acquisition["transient_retry_count"] == 0
    assert acquisition["trajectory_payload_retained"] is False
    assert acquisition["trajectory_semantic_parse_count"] == 0


def test_environment_binds_sources_wheels_interpreter_and_dependencies(
    live_bundle: dict[str, Any],
) -> None:
    manifest = cast(
        dict[str, Any],
        live_bundle["environment_manifest"],
    )
    source = cast(dict[str, Any], manifest["environment_source"])
    wheels = cast(list[dict[str, Any]], manifest["runtime_wheels"])
    dependencies = {
        (str(row["name"]), str(row["version"]))
        for row in cast(
            list[dict[str, Any]],
            manifest["dependencies"],
        )
    }

    validate_environment_manifest(manifest)
    assert manifest == _json(ENVIRONMENT_MANIFEST_PATH)
    assert source["source_count"] == 50
    assert {
        (
            str(wheel["distribution"]),
            str(wheel["version"]),
            str(wheel["sha256"]),
            int(wheel["size_bytes"]),
        )
        for wheel in wheels
    } == {
        (
            "arc-agi",
            "0.9.8",
            "aeca1663db342e91cb8fc96cf0c83e2f"
            "a39db1640bc1298e80a8d522e3af70f3",
            40_151,
        ),
        (
            "arcengine",
            "0.9.3",
            "5f9739d6d0055780a4581fd6fe09066b"
            "b08775c4c8212c9adcca2eb008aef59c",
            38_374,
        ),
    }
    assert {("arc-agi", "0.9.8"), ("arcengine", "0.9.3")} <= (
        dependencies
    )
    assert manifest["python"] == {
        "implementation": "CPython",
        "version": "3.12.13",
        "architecture": "64bit",
        "abi_flags": "",
        "soabi": None,
    }
    assert manifest["os"] == {
        "system": "Windows",
        "release": "11",
        "version": "10.0.26200",
        "machine": "AMD64",
    }


def test_environment_source_has_50_exact_archive_aliases(
    live_bundle: dict[str, Any],
) -> None:
    manifest = _source_manifest(
        live_bundle,
        "arc3-environment-source-bundle",
    )
    files = cast(list[dict[str, Any]], manifest["files"])

    assert len(files) == 50
    assert all(
        record["verification_method"]
        == "REPOSITORY_ARCHIVE_ALIAS_BYTE_IDENTITY"
        and len(cast(list[Any], record["aliases"])) == 1
        for record in files
    )


def test_run_manifest_binds_clean_capture_evidence(
    live_bundle: dict[str, Any],
) -> None:
    manifest = cast(dict[str, Any], live_bundle["run_manifest"])

    validate_run_manifest(manifest)
    assert manifest == _json(RUN_MANIFEST_PATH)
    assert manifest["input_profile_ids"] == [
        "arc3-raw-teacher-recordings"
    ]
    assert manifest["exit_code"] == 0
    assert manifest["stdout_sha256"] == (
        "09d7d78f1b1b4b16ade74d54308b9948"
        "2b01a43ff30547f50baf1f1d7ab6c56d"
    )
    assert manifest["stderr_sha256"] == hashlib.sha256(b"").hexdigest()
    assert manifest["network_scope"] == (
        "PINNED_HUGGINGFACE_DATASET_READ_ONLY"
    )


def test_acquisition_path_and_time_do_not_enter_content_digest(
    live_bundle: dict[str, Any],
) -> None:
    source_manifest = _source_manifest(
        live_bundle,
        "arc3-raw-teacher-recordings",
    )
    acquisitions = cast(
        dict[str, dict[str, Any]],
        live_bundle["acquisition_records"],
    )
    baseline = acquisitions["arc3-raw-teacher-recordings"]
    changed = copy.deepcopy(baseline)
    changed["local_path"] = "/another/local/acquisition/path"
    changed["acquired_at"] = "2030-01-02T03:04:05Z"
    changed["mtime"] = "2030-01-02T03:04:06Z"
    changed["acquisition_digest"] = _digest(
        changed,
        ACQUISITION_DIGEST_NAMESPACE,
        ("acquisition_digest",),
    )

    validate_acquisition_record(baseline)
    validate_acquisition_record(changed)
    assert changed["acquisition_digest"] != baseline["acquisition_digest"]
    assert source_manifest["content_digest"] == (
        _source_manifest(
            live_bundle,
            "arc3-raw-teacher-recordings",
        )["content_digest"]
    )
    assert not {
        "local_path",
        "acquired_at",
        "mtime",
        "acquisition_actor",
        "transport",
    } & set(source_manifest)


def test_capture_content_digest_ignores_acquisition_timestamp_and_mtime(
) -> None:
    capture = _json(CAPTURE_PATH)
    changed = copy.deepcopy(capture)
    acquisition = cast(dict[str, Any], changed["acquisition"])
    acquisition["captured_at"] = "2030-01-02T03:04:05Z"
    acquisition["dataset_last_modified_at_capture"] = (
        "2030-01-02T03:04:06Z"
    )

    assert _digest(
        capture,
        CAPTURE_DIGEST_NAMESPACE,
        ("acquisition", "content_digest"),
    ) == _digest(
        changed,
        CAPTURE_DIGEST_NAMESPACE,
        ("acquisition", "content_digest"),
    )


def test_directory_merkle_is_order_independent_and_mutation_sensitive(
) -> None:
    records = [
        {
            "source_id": "source-a",
            "repository_relative_posix_path": "source/a.bin",
            "source_locator": "source/a.bin",
            "aliases": [],
            "sha256": hashlib.sha256(b"a").hexdigest(),
            "size_bytes": 1,
            "verification_method": "REPOSITORY_FILE_SHA256",
        },
        {
            "source_id": "source-b",
            "repository_relative_posix_path": "source/b.bin",
            "source_locator": "source/b.bin",
            "aliases": [],
            "sha256": hashlib.sha256(b"b").hexdigest(),
            "size_bytes": 1,
            "verification_method": "REPOSITORY_FILE_SHA256",
        },
    ]
    baseline = directory_merkle_root(cast(Any, records))
    reversed_root = directory_merkle_root(
        cast(Any, list(reversed(records)))
    )
    changed_path = copy.deepcopy(records)
    changed_path[0]["repository_relative_posix_path"] = "source/c.bin"
    changed_size = copy.deepcopy(records)
    changed_size[0]["size_bytes"] = 2
    changed_content = copy.deepcopy(records)
    changed_content[0]["sha256"] = hashlib.sha256(b"changed").hexdigest()

    assert baseline == reversed_root
    assert directory_merkle_root(cast(Any, changed_path)) != baseline
    assert directory_merkle_root(cast(Any, changed_size)) != baseline
    assert directory_merkle_root(cast(Any, changed_content)) != baseline
    with pytest.raises(
        ManifestFreezeError,
        match="D01B_MERKLE_DUPLICATE_PATH",
    ):
        directory_merkle_root(cast(Any, [records[0], records[0]]))


@pytest.mark.parametrize(
    "path",
    [
        "/absolute/file.json",
        "../escape.json",
        "nested/../escape.json",
        r"windows\path.json",
    ],
)
def test_non_normalized_posix_paths_fail_closed(path: str) -> None:
    record = {
        "source_id": "source-a",
        "repository_relative_posix_path": path,
        "source_locator": "source-a",
        "aliases": [],
        "sha256": hashlib.sha256(b"a").hexdigest(),
        "size_bytes": 1,
        "verification_method": "REPOSITORY_FILE_SHA256",
    }

    with pytest.raises(ManifestFreezeError, match="D01B_FILE_PATH"):
        directory_merkle_root(cast(Any, [record]))


def test_source_mutation_changes_merkle_content_and_environment_binding(
    live_bundle: dict[str, Any],
) -> None:
    source = _source_manifest(
        live_bundle,
        "arc3-environment-source-bundle",
    )
    files = copy.deepcopy(cast(list[dict[str, Any]], source["files"]))
    files[0]["sha256"] = hashlib.sha256(b"mutated-source").hexdigest()
    mutated_source = _rebuild_source_manifest(source, files)

    assert mutated_source["directory_merkle_root"] != (
        source["directory_merkle_root"]
    )
    assert mutated_source["content_digest"] != source["content_digest"]

    environment = copy.deepcopy(
        cast(dict[str, Any], live_bundle["environment_manifest"])
    )
    environment_source = cast(
        dict[str, Any],
        environment["environment_source"],
    )
    environment_source["source_content_digest"] = (
        mutated_source["content_digest"]
    )
    environment_source["directory_merkle_root"] = (
        mutated_source["directory_merkle_root"]
    )
    with pytest.raises(
        ManifestFreezeError,
        match="D01B_ENVIRONMENT_DIGEST_MISMATCH",
    ):
        validate_environment_manifest(environment)

    old_environment_digest = environment["content_digest"]
    environment["content_digest"] = _digest(
        environment,
        ENVIRONMENT_DIGEST_NAMESPACE,
        ("content_digest",),
    )
    validate_environment_manifest(environment)
    assert environment["content_digest"] != old_environment_digest


def test_manifest_validators_reject_unknown_fields_and_tampering(
    live_bundle: dict[str, Any],
) -> None:
    source = copy.deepcopy(
        _source_manifest(
            live_bundle,
            "arc3-canonical-teacher-trajectories",
        )
    )
    source["unknown"] = True
    with pytest.raises(ManifestFreezeError, match="D01B_SOURCE_MANIFEST_FIELDS"):
        validate_source_content_manifest(source)

    acquisition = copy.deepcopy(
        cast(
            dict[str, dict[str, Any]],
            live_bundle["acquisition_records"],
        )["arc3-canonical-teacher-trajectories"]
    )
    acquisition["local_path"] = "/tampered"
    with pytest.raises(
        ManifestFreezeError,
        match="D01B_ACQUISITION_DIGEST_MISMATCH",
    ):
        validate_acquisition_record(acquisition)

    run = copy.deepcopy(cast(dict[str, Any], live_bundle["run_manifest"]))
    run["exit_code"] = 1
    with pytest.raises(
        ManifestFreezeError,
        match="D01B_RUN_EXIT_NONZERO",
    ):
        validate_run_manifest(run)


def _capture_fixture(
    tmp_path: Path,
    capture: dict[str, Any],
) -> tuple[Path, dict[str, Any]]:
    repository = tmp_path / "repository"
    project = repository / "distillation"
    input_root = project / "input"
    input_root.mkdir(parents=True)
    (input_root / "raw_recording_content_capture.json").write_text(
        json.dumps(capture, ensure_ascii=False, indent=2, sort_keys=True)
        + "\n",
        encoding="utf-8",
        newline="\n",
    )
    return project, copy.deepcopy(_json(PLAN_PATH))


def test_capture_row_tampering_fails_closed(tmp_path: Path) -> None:
    capture = _json(CAPTURE_PATH)
    rows = cast(list[dict[str, Any]], capture["rows"])
    rows[0]["trajectory_size_bytes"] = (
        int(rows[0]["trajectory_size_bytes"]) + 1
    )
    capture["content_digest"] = _digest(
        capture,
        CAPTURE_DIGEST_NAMESPACE,
        ("acquisition", "content_digest"),
    )
    project, plan = _capture_fixture(tmp_path, capture)
    binding = cast(dict[str, Any], plan["raw_recording_capture"])
    binding["content_digest"] = capture["content_digest"]

    with pytest.raises(
        ManifestFreezeError,
        match="D01B_CAPTURE_ROW_BINDING_MISMATCH",
    ):
        manifest_freeze._load_capture(project, cast(Any, plan))


def test_capture_revision_change_during_read_fails_closed(
    tmp_path: Path,
) -> None:
    capture = _json(CAPTURE_PATH)
    acquisition = cast(dict[str, Any], capture["acquisition"])
    acquisition["dataset_sha_after_capture"] = "0" * 40
    project, plan = _capture_fixture(tmp_path, capture)

    with pytest.raises(
        ManifestFreezeError,
        match="D01B_CAPTURE_REVISION_CHANGED_DURING_READ",
    ):
        manifest_freeze._load_capture(project, cast(Any, plan))


def test_plan_metadata_tampering_fails_closed(tmp_path: Path) -> None:
    project = tmp_path / "distillation"
    input_root = project / "input"
    input_root.mkdir(parents=True)
    plan = _json(PLAN_PATH)
    plan["phase_id"] = "PH-D99"
    (input_root / "manifest_freeze_plan.json").write_text(
        json.dumps(plan, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
        newline="\n",
    )

    with pytest.raises(
        ManifestFreezeError,
        match="D01B_PLAN_SCHEMA_OR_PHASE",
    ):
        manifest_freeze._load_plan(project)


def test_four_contract_schemas_are_strict_and_match_artifacts() -> None:
    pairs = [
        (
            PROJECT_ROOT / "schemas" / "source_content_manifest.schema.json",
            _json(
                PROJECT_ROOT
                / "manifests"
                / "source_content"
                / "arc3-raw-teacher-recordings.json"
            ),
        ),
        (
            PROJECT_ROOT / "schemas" / "acquisition_record.schema.json",
            _json(
                PROJECT_ROOT
                / "manifests"
                / "acquisition"
                / "arc3-raw-teacher-recordings.json"
            ),
        ),
        (
            PROJECT_ROOT / "schemas" / "environment_manifest.schema.json",
            _json(ENVIRONMENT_MANIFEST_PATH),
        ),
        (
            PROJECT_ROOT / "schemas" / "run_manifest.schema.json",
            _json(RUN_MANIFEST_PATH),
        ),
    ]

    for path, artifact in pairs:
        schema = _json(path)
        assert schema["additionalProperties"] is False
        assert set(cast(list[str], schema["required"])) == set(artifact)
        assert set(cast(dict[str, Any], schema["properties"])) == set(
            artifact
        )


def test_three_live_rebuilds_are_byte_identical() -> None:
    bundles = [_live_bundle() for _ in range(3)]
    report_bytes = [
        artifact_bytes(cast(dict[str, Any], bundle["freeze_report"]))
        for bundle in bundles
    ]
    environment_bytes = [
        artifact_bytes(
            cast(dict[str, Any], bundle["environment_manifest"])
        )
        for bundle in bundles
    ]

    assert report_bytes[0] == report_bytes[1] == report_bytes[2]
    assert environment_bytes[0] == (
        environment_bytes[1]
    ) == environment_bytes[2]


def test_isolation_and_phase_boundaries_remain_zero(
    live_bundle: dict[str, Any],
) -> None:
    isolation = cast(dict[str, Any], live_bundle["isolation_report"])
    report = cast(dict[str, Any], live_bundle["freeze_report"])
    phase_boundaries = cast(dict[str, Any], report["phase_boundaries"])

    assert isolation["compiler_network_call_count"] == 0
    assert isolation["source_write_count"] == 0
    assert isolation["source_mutation_count"] == 0
    assert isolation["source_payload_semantic_parse_count"] == 0
    assert isolation["source_execution_count"] == 0
    assert isolation["teacher_replay_execution_count"] == 0
    assert isolation["os_source_mount_read_only_enforced"] is True
    assert isolation["os_source_mount_enforcement_scope"] == (
        "ROLE_PROJECTION_PROBE"
    )
    assert isolation["source_blind_probe_process_count"] == 3
    assert isolation["source_blind_role_count"] == 3
    assert (
        isolation["source_blind_execution_contract_established"] is True
    )
    assert (
        isolation[
            "same_process_source_access_then_candidate_generation_count"
        ]
        == 0
    )
    assert report["source_blind_execution_contract_established"] is True
    assert report["accounting"]["source_blind_execution_record_count"] == 1
    assert isolation["source_snapshot_before"] == (
        isolation["source_snapshot_after"]
    )
    assert phase_boundaries == {
        "content_manifest_frozen": True,
        "acquisition_manifest_frozen": True,
        "environment_manifest_frozen": True,
        "trajectory_normalization_started": False,
        "causal_ir_started": False,
        "candidate_generation_started": False,
        "bridge_started": False,
        "runtime_started": False,
        "official_access_count": 0,
        "kaggle_mutation_count": 0,
    }
    assert report["claim_boundary"].startswith(
        "Source and environment identity only"
    )


def test_all_manifest_paths_are_normalized_relative_posix(
    live_bundle: dict[str, Any],
) -> None:
    manifests = cast(
        dict[str, dict[str, Any]],
        live_bundle["source_manifests"],
    )
    for manifest in manifests.values():
        paths = cast(
            list[str],
            manifest["repository_relative_posix_paths"],
        )
        assert paths == sorted(paths)
        assert len(paths) == len(set(paths))
        assert all(
            PurePosixPath(path).as_posix() == path
            and not PurePosixPath(path).is_absolute()
            and ".." not in PurePosixPath(path).parts
            for path in paths
        )
