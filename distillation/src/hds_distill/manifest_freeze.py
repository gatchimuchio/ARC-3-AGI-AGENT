"""Deterministic PH-D01B source and environment manifest freeze.

This module hashes source bytes and frozen acquisition metadata only.  It
never imports or executes ARC environment source, parses ARC task semantics,
replays a trajectory, accesses a network, or selects a policy.
"""

from __future__ import annotations

import hashlib
import importlib.metadata
import json
import platform
import re
import struct
import sys
import sysconfig
import zipfile
from collections import defaultdict
from collections.abc import Mapping, Sequence
from datetime import datetime
from pathlib import Path, PurePosixPath
from typing import Final, cast

from hds_distill.source_inventory import (
    ANSWER_VISIBILITIES,
    CONTAMINATION_CLASSES,
    DEVELOPMENT_USAGES,
    SPLIT_ROLES,
    JsonObject,
    JsonValue,
    canonical_json,
    verify_source_inventory_report,
)

PHASE_ID: Final = "PH-D01B"
PLAN_SCHEMA_VERSION: Final = "hds-manifest-freeze-plan-v1"
CAPTURE_SCHEMA_VERSION: Final = "hds-raw-recording-content-capture-v1"
SOURCE_MANIFEST_SCHEMA_VERSION: Final = "hds-source-content-manifest-v1"
ACQUISITION_SCHEMA_VERSION: Final = "hds-acquisition-record-v1"
ENVIRONMENT_SCHEMA_VERSION: Final = "hds-environment-manifest-v1"
RUN_SCHEMA_VERSION: Final = "hds-run-manifest-v1"

PLAN_DIGEST_NAMESPACE: Final = "hds-manifest-freeze-plan"
CAPTURE_DIGEST_NAMESPACE: Final = "hds-raw-recording-content-capture"
SOURCE_MANIFEST_DIGEST_NAMESPACE: Final = "hds-source-content-manifest"
ACQUISITION_DIGEST_NAMESPACE: Final = "hds-acquisition-record"
ENVIRONMENT_DIGEST_NAMESPACE: Final = "hds-environment-manifest"
RUN_DIGEST_NAMESPACE: Final = "hds-run-manifest"
RAW_RECORDING_ROW_DIGEST_NAMESPACE: Final = "hds-raw-recording-row"
DEPENDENCY_LOCK_DIGEST_NAMESPACE: Final = (
    "hds-environment-dependency-lock"
)
DIRECTORY_MERKLE_NAMESPACE: Final = "hds-directory-merkle-v1"
INPUT_SNAPSHOT_NAMESPACE: Final = "hds-source-input-snapshot"
ISOLATION_REPORT_DIGEST_NAMESPACE: Final = (
    "hds-environment-isolation-report"
)
FREEZE_REPORT_DIGEST_NAMESPACE: Final = "hds-source-manifest-freeze-report"

SHA256_PATTERN: Final = re.compile(r"^[0-9a-f]{64}$")

PLAN_FIELDS: Final = frozenset(
    {
        "schema_version",
        "phase_id",
        "frame_digest",
        "preinventory_digest",
        "source_inventory",
        "raw_recording_capture",
        "distributions",
        "profile_bindings",
        "acquisition_records",
        "environment",
        "run_manifest",
        "resource_budget",
        "expected_accounting",
        "phase_boundaries",
        "digest_excluded_fields",
        "content_digest",
    }
)
SOURCE_MANIFEST_FIELDS: Final = frozenset(
    {
        "schema_version",
        "manifest_id",
        "manifest_version",
        "source_profile",
        "domain",
        "repository_relative_posix_paths",
        "files",
        "directory_merkle_root",
        "upstream_repository",
        "upstream_commit_or_release",
        "split_role",
        "answer_visibility",
        "development_usage",
        "contamination_class",
        "license",
        "source_count",
        "digest_excluded_fields",
        "content_digest",
    }
)
FILE_RECORD_FIELDS: Final = frozenset(
    {
        "source_id",
        "repository_relative_posix_path",
        "source_locator",
        "aliases",
        "sha256",
        "size_bytes",
        "verification_method",
    }
)
ACQUISITION_RECORD_FIELDS: Final = frozenset(
    {
        "schema_version",
        "acquisition_id",
        "source_content_manifest_id",
        "source_content_digest",
        "acquired_at",
        "local_path",
        "mtime",
        "acquisition_actor",
        "transport",
        "notes",
        "digest_excluded_fields",
        "acquisition_digest",
    }
)
ENVIRONMENT_MANIFEST_FIELDS: Final = frozenset(
    {
        "schema_version",
        "manifest_id",
        "manifest_version",
        "environment_source",
        "runtime_wheels",
        "python",
        "os",
        "dependencies",
        "dependency_lock_digest",
        "seed",
        "reset_mode",
        "source_access_contract",
        "isolation_report_digest",
        "digest_excluded_fields",
        "content_digest",
    }
)
RUN_MANIFEST_FIELDS: Final = frozenset(
    {
        "schema_version",
        "run_id",
        "purpose",
        "input_profile_ids",
        "input_content_digests",
        "environment_manifest_digest",
        "working_directory",
        "command",
        "capture_tool_sha256",
        "started_at",
        "ended_at",
        "exit_code",
        "stdout_sha256",
        "stderr_sha256",
        "network_scope",
        "digest_excluded_fields",
        "run_digest",
    }
)


class ManifestFreezeError(ValueError):
    """Fail-closed PH-D01B manifest error."""


def _object(value: object, code: str) -> JsonObject:
    if not isinstance(value, dict):
        raise ManifestFreezeError(code + "_NOT_OBJECT")
    return cast(JsonObject, value)


def _list(value: object, code: str) -> list[JsonValue]:
    if not isinstance(value, list):
        raise ManifestFreezeError(code + "_NOT_ARRAY")
    return cast(list[JsonValue], value)


def _string(value: object, code: str) -> str:
    if not isinstance(value, str) or not value:
        raise ManifestFreezeError(code + "_NOT_STRING")
    return value


def _integer(value: object, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ManifestFreezeError(code + "_NOT_INTEGER")
    return value


def _boolean(value: object, code: str) -> bool:
    if not isinstance(value, bool):
        raise ManifestFreezeError(code + "_NOT_BOOLEAN")
    return value


def _string_list(value: object, code: str) -> list[str]:
    return [
        _string(item, code + "_ITEM")
        for item in _list(value, code)
    ]


def _timestamp(value: object, code: str) -> str:
    text = _string(value, code)
    if not text.endswith("Z"):
        raise ManifestFreezeError(code + "_NOT_UTC_Z")
    try:
        parsed = datetime.fromisoformat(text.removesuffix("Z") + "+00:00")
    except ValueError as exc:
        raise ManifestFreezeError(code + "_INVALID") from exc
    utc_offset = parsed.utcoffset()
    if utc_offset is None or utc_offset.total_seconds() != 0:
        raise ManifestFreezeError(code + "_NOT_UTC")
    return text


def _require_digest_excluded_fields(
    value: object,
    expected: Sequence[str],
    code: str,
) -> list[str]:
    actual = _string_list(value, code)
    if actual != list(expected):
        raise ManifestFreezeError(code + "_INVALID")
    return actual


def _strict_fields(
    value: Mapping[str, JsonValue],
    expected: frozenset[str],
    code: str,
) -> None:
    actual = frozenset(value)
    if actual != expected:
        missing = ",".join(sorted(expected - actual))
        extra = ",".join(sorted(actual - expected))
        raise ManifestFreezeError(
            f"{code}_FIELDS:missing={missing}:extra={extra}"
        )


def _sha256(value: object, code: str) -> str:
    text = _string(value, code)
    if SHA256_PATTERN.fullmatch(text) is None:
        raise ManifestFreezeError(code + "_INVALID")
    return text


def _bound_digest(
    value: object,
    namespace: str,
    code: str,
) -> str:
    text = _string(value, code)
    if not text.startswith(namespace + ":"):
        raise ManifestFreezeError(code + "_NAMESPACE")
    _sha256(text.removeprefix(namespace + ":"), code)
    return text


def _digest(
    value: Mapping[str, JsonValue],
    namespace: str,
    *,
    excluded_fields: Sequence[str],
) -> str:
    body = {
        key: item
        for key, item in value.items()
        if key not in set(excluded_fields)
    }
    encoded = canonical_json(body).encode("utf-8")
    return namespace + ":" + hashlib.sha256(encoded).hexdigest()


def _read_json(path: Path, code: str) -> JsonObject:
    try:
        decoded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ManifestFreezeError(f"{code}_UNREADABLE:{path}") from exc
    return _object(decoded, code)


def _normalized_relative_posix_path(value: object, code: str) -> str:
    text = _string(value, code)
    if "\\" in text or text.startswith("/") or "\x00" in text:
        raise ManifestFreezeError(code + "_NOT_RELATIVE_POSIX")
    path = PurePosixPath(text)
    if (
        path.is_absolute()
        or text != path.as_posix()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise ManifestFreezeError(code + "_NOT_NORMALIZED")
    return text


def _file_sha256(path: Path) -> tuple[str, int]:
    try:
        payload = path.read_bytes()
    except OSError as exc:
        raise ManifestFreezeError(f"D01B_SOURCE_UNREADABLE:{path}") from exc
    return hashlib.sha256(payload).hexdigest(), len(payload)


def _zip_member_bytes(
    archive: zipfile.ZipFile,
    member: str,
) -> bytes:
    try:
        info = archive.getinfo(member)
        if info.is_dir():
            raise ManifestFreezeError(
                "D01B_ARCHIVE_MEMBER_IS_DIRECTORY:" + member
            )
        return archive.read(info)
    except KeyError as exc:
        raise ManifestFreezeError(
            "D01B_ARCHIVE_MEMBER_MISSING:" + member
        ) from exc


def _file_record_key(value: Mapping[str, JsonValue]) -> str:
    return _string(
        value["repository_relative_posix_path"],
        "D01B_FILE_PATH",
    )


def directory_merkle_root(
    files: Sequence[Mapping[str, JsonValue]],
) -> str:
    """Return a path-, size-, and content-bound deterministic Merkle root."""

    if not files:
        raise ManifestFreezeError("D01B_MERKLE_EMPTY")
    ordered = sorted(files, key=_file_record_key)
    paths = [_file_record_key(item) for item in ordered]
    if len(paths) != len(set(paths)):
        raise ManifestFreezeError("D01B_MERKLE_DUPLICATE_PATH")
    leaf_digests: list[bytes] = []
    for item in ordered:
        _strict_fields(item, FILE_RECORD_FIELDS, "D01B_FILE_RECORD")
        leaf: JsonObject = {
            "path": _normalized_relative_posix_path(
                item["repository_relative_posix_path"],
                "D01B_FILE_PATH",
            ),
            "sha256": _sha256(item["sha256"], "D01B_FILE_SHA256"),
            "size_bytes": _integer(
                item["size_bytes"],
                "D01B_FILE_SIZE",
            ),
        }
        if cast(int, leaf["size_bytes"]) < 0:
            raise ManifestFreezeError("D01B_FILE_SIZE_NEGATIVE")
        encoded = (
            b"hds-directory-leaf-v1\x00"
            + canonical_json(leaf).encode("utf-8")
        )
        leaf_digests.append(hashlib.sha256(encoded).digest())
    root = hashlib.sha256(
        b"hds-directory-root-v1\x00" + b"".join(leaf_digests)
    ).hexdigest()
    return DIRECTORY_MERKLE_NAMESPACE + ":" + root


def build_source_content_manifest(
    *,
    manifest_id: str,
    profile_id: str,
    profile_digest: str,
    domain: str,
    files: Sequence[Mapping[str, JsonValue]],
    upstream_repository: str,
    upstream_commit_or_release: str,
    split_role: str,
    answer_visibility: str,
    development_usage: str,
    contamination_class: str,
    license_value: str,
) -> JsonObject:
    """Build one strict, local-path- and acquisition-time-free manifest."""

    if not manifest_id or not profile_id:
        raise ManifestFreezeError("D01B_MANIFEST_ID_MISSING")
    _bound_digest(
        profile_digest,
        "hds-source-profile",
        "D01B_PROFILE_DIGEST",
    )
    ordered = [
        dict(item) for item in sorted(files, key=_file_record_key)
    ]
    paths = [_file_record_key(item) for item in ordered]
    if len(paths) != len(set(paths)):
        raise ManifestFreezeError("D01B_SOURCE_PATH_DUPLICATE")
    source_ids = [
        _string(item["source_id"], "D01B_SOURCE_ID") for item in ordered
    ]
    if len(source_ids) != len(set(source_ids)):
        raise ManifestFreezeError("D01B_SOURCE_ID_DUPLICATE")
    for item in ordered:
        _strict_fields(item, FILE_RECORD_FIELDS, "D01B_FILE_RECORD")
        _normalized_relative_posix_path(
            item["repository_relative_posix_path"],
            "D01B_FILE_PATH",
        )
        _sha256(item["sha256"], "D01B_FILE_SHA256")
        if _integer(item["size_bytes"], "D01B_FILE_SIZE") < 0:
            raise ManifestFreezeError("D01B_FILE_SIZE_NEGATIVE")
    manifest: JsonObject = {
        "schema_version": SOURCE_MANIFEST_SCHEMA_VERSION,
        "manifest_id": manifest_id,
        "manifest_version": 1,
        "source_profile": {
            "profile_id": profile_id,
            "profile_digest": profile_digest,
        },
        "domain": domain,
        "repository_relative_posix_paths": cast(JsonValue, paths),
        "files": cast(JsonValue, ordered),
        "directory_merkle_root": directory_merkle_root(ordered),
        "upstream_repository": upstream_repository,
        "upstream_commit_or_release": upstream_commit_or_release,
        "split_role": split_role,
        "answer_visibility": answer_visibility,
        "development_usage": development_usage,
        "contamination_class": contamination_class,
        "license": license_value,
        "source_count": len(ordered),
        "digest_excluded_fields": ["content_digest"],
        "content_digest": "",
    }
    _strict_fields(
        manifest,
        SOURCE_MANIFEST_FIELDS,
        "D01B_SOURCE_MANIFEST",
    )
    manifest["content_digest"] = _digest(
        manifest,
        SOURCE_MANIFEST_DIGEST_NAMESPACE,
        excluded_fields=("content_digest",),
    )
    return manifest


def validate_source_content_manifest(
    manifest: Mapping[str, JsonValue],
) -> None:
    """Fail unless a source manifest is internally complete and bound."""

    _strict_fields(
        manifest,
        SOURCE_MANIFEST_FIELDS,
        "D01B_SOURCE_MANIFEST",
    )
    if manifest["schema_version"] != SOURCE_MANIFEST_SCHEMA_VERSION:
        raise ManifestFreezeError("D01B_SOURCE_MANIFEST_SCHEMA")
    _string(manifest["manifest_id"], "D01B_SOURCE_MANIFEST_ID")
    if _integer(manifest["manifest_version"], "D01B_SOURCE_VERSION") != 1:
        raise ManifestFreezeError("D01B_SOURCE_VERSION_INVALID")
    profile = _object(
        manifest["source_profile"],
        "D01B_SOURCE_PROFILE_BINDING",
    )
    _strict_fields(
        profile,
        frozenset({"profile_id", "profile_digest"}),
        "D01B_SOURCE_PROFILE_BINDING",
    )
    _string(profile["profile_id"], "D01B_SOURCE_PROFILE_ID")
    _bound_digest(
        profile["profile_digest"],
        "hds-source-profile",
        "D01B_SOURCE_PROFILE_DIGEST",
    )
    if manifest["domain"] not in {"ARC2", "ARC3"}:
        raise ManifestFreezeError("D01B_SOURCE_DOMAIN")
    _string(
        manifest["upstream_repository"],
        "D01B_UPSTREAM_REPOSITORY",
    )
    _string(
        manifest["upstream_commit_or_release"],
        "D01B_UPSTREAM_RELEASE",
    )
    if manifest["split_role"] not in SPLIT_ROLES:
        raise ManifestFreezeError("D01B_SOURCE_SPLIT_ROLE")
    if manifest["answer_visibility"] not in ANSWER_VISIBILITIES:
        raise ManifestFreezeError("D01B_SOURCE_ANSWER_VISIBILITY")
    if manifest["development_usage"] not in DEVELOPMENT_USAGES:
        raise ManifestFreezeError("D01B_SOURCE_DEVELOPMENT_USAGE")
    if manifest["contamination_class"] not in CONTAMINATION_CLASSES:
        raise ManifestFreezeError("D01B_SOURCE_CONTAMINATION")
    _string(manifest["license"], "D01B_SOURCE_LICENSE")
    files = [
        _object(item, "D01B_FILE_RECORD")
        for item in _list(manifest["files"], "D01B_FILES")
    ]
    paths = [
        _normalized_relative_posix_path(
            item,
            "D01B_MANIFEST_PATH",
        )
        for item in _list(
            manifest["repository_relative_posix_paths"],
            "D01B_MANIFEST_PATHS",
        )
    ]
    file_paths = [_file_record_key(item) for item in files]
    source_ids: list[str] = []
    for item in files:
        source_ids.append(_string(item["source_id"], "D01B_SOURCE_ID"))
        _string(item["source_locator"], "D01B_SOURCE_LOCATOR")
        aliases = _string_list(item["aliases"], "D01B_SOURCE_ALIASES")
        if len(aliases) != len(set(aliases)):
            raise ManifestFreezeError("D01B_SOURCE_ALIAS_DUPLICATE")
        _sha256(item["sha256"], "D01B_FILE_SHA256")
        if _integer(item["size_bytes"], "D01B_FILE_SIZE") < 0:
            raise ManifestFreezeError("D01B_FILE_SIZE_NEGATIVE")
        if item["verification_method"] not in {
            "REPOSITORY_FILE_SHA256",
            "ARCHIVE_MEMBER_SHA256",
            "REPOSITORY_ARCHIVE_ALIAS_BYTE_IDENTITY",
            "PINNED_DATASET_TRAJECTORY_SHA256",
        }:
            raise ManifestFreezeError("D01B_VERIFICATION_METHOD")
    if len(source_ids) != len(set(source_ids)):
        raise ManifestFreezeError("D01B_SOURCE_ID_DUPLICATE")
    if paths != sorted(paths) or paths != file_paths:
        raise ManifestFreezeError("D01B_MANIFEST_PATH_SET_MISMATCH")
    if _integer(manifest["source_count"], "D01B_SOURCE_COUNT") != len(
        files
    ):
        raise ManifestFreezeError("D01B_SOURCE_COUNT_MISMATCH")
    if manifest["directory_merkle_root"] != directory_merkle_root(files):
        raise ManifestFreezeError("D01B_DIRECTORY_MERKLE_MISMATCH")
    _require_digest_excluded_fields(
        manifest["digest_excluded_fields"],
        ("content_digest",),
        "D01B_SOURCE_EXCLUDED_FIELDS",
    )
    claimed = _bound_digest(
        manifest["content_digest"],
        SOURCE_MANIFEST_DIGEST_NAMESPACE,
        "D01B_SOURCE_CONTENT_DIGEST",
    )
    actual = _digest(
        manifest,
        SOURCE_MANIFEST_DIGEST_NAMESPACE,
        excluded_fields=("content_digest",),
    )
    if claimed != actual:
        raise ManifestFreezeError("D01B_SOURCE_CONTENT_DIGEST_MISMATCH")


def validate_acquisition_record(
    record: Mapping[str, JsonValue],
) -> None:
    """Fail unless acquisition metadata is separate and self-consistent."""

    _strict_fields(
        record,
        ACQUISITION_RECORD_FIELDS,
        "D01B_ACQUISITION_RECORD",
    )
    if record["schema_version"] != ACQUISITION_SCHEMA_VERSION:
        raise ManifestFreezeError("D01B_ACQUISITION_SCHEMA")
    _string(record["acquisition_id"], "D01B_ACQUISITION_ID")
    _string(
        record["source_content_manifest_id"],
        "D01B_ACQUISITION_SOURCE_MANIFEST_ID",
    )
    _bound_digest(
        record["source_content_digest"],
        SOURCE_MANIFEST_DIGEST_NAMESPACE,
        "D01B_ACQUISITION_SOURCE_DIGEST",
    )
    _timestamp(record["acquired_at"], "D01B_ACQUIRED_AT")
    _string(record["local_path"], "D01B_ACQUISITION_LOCAL_PATH")
    _string(record["mtime"], "D01B_ACQUISITION_MTIME")
    _string(record["acquisition_actor"], "D01B_ACQUISITION_ACTOR")
    transport = _string(record["transport"], "D01B_ACQUISITION_TRANSPORT")
    if transport not in {
        "LOCAL_GIT_WORKTREE_READ",
        "LOCAL_ARCHIVE_MEMBER_READ",
        "HUGGINGFACE_DATASET_VIEWER_ROWS_HTTPS_GET",
    }:
        raise ManifestFreezeError("D01B_ACQUISITION_TRANSPORT_INVALID")
    _string_list(record["notes"], "D01B_ACQUISITION_NOTES")
    excluded = _require_digest_excluded_fields(
        record["digest_excluded_fields"],
        ("acquisition_digest",),
        "D01B_ACQUISITION_EXCLUDED_FIELDS",
    )
    claimed = _bound_digest(
        record["acquisition_digest"],
        ACQUISITION_DIGEST_NAMESPACE,
        "D01B_ACQUISITION_DIGEST",
    )
    if claimed != _digest(
        record,
        ACQUISITION_DIGEST_NAMESPACE,
        excluded_fields=excluded,
    ):
        raise ManifestFreezeError("D01B_ACQUISITION_DIGEST_MISMATCH")


def validate_environment_manifest(
    manifest: Mapping[str, JsonValue],
) -> None:
    """Fail unless the ARC3 replay environment identity is complete."""

    _strict_fields(
        manifest,
        ENVIRONMENT_MANIFEST_FIELDS,
        "D01B_ENVIRONMENT_MANIFEST",
    )
    if manifest["schema_version"] != ENVIRONMENT_SCHEMA_VERSION:
        raise ManifestFreezeError("D01B_ENVIRONMENT_SCHEMA")
    _string(manifest["manifest_id"], "D01B_ENVIRONMENT_MANIFEST_ID")
    if _integer(manifest["manifest_version"], "D01B_ENVIRONMENT_VERSION") != 1:
        raise ManifestFreezeError("D01B_ENVIRONMENT_VERSION_INVALID")

    source = _object(
        manifest["environment_source"],
        "D01B_ENVIRONMENT_SOURCE",
    )
    _strict_fields(
        source,
        frozenset(
            {
                "source_content_manifest_id",
                "source_content_digest",
                "source_count",
                "directory_merkle_root",
            }
        ),
        "D01B_ENVIRONMENT_SOURCE",
    )
    _string(
        source["source_content_manifest_id"],
        "D01B_ENVIRONMENT_SOURCE_ID",
    )
    _bound_digest(
        source["source_content_digest"],
        SOURCE_MANIFEST_DIGEST_NAMESPACE,
        "D01B_ENVIRONMENT_SOURCE_DIGEST",
    )
    if _integer(source["source_count"], "D01B_ENVIRONMENT_SOURCE_COUNT") != 50:
        raise ManifestFreezeError("D01B_ENVIRONMENT_SOURCE_COUNT_INVALID")
    _bound_digest(
        source["directory_merkle_root"],
        DIRECTORY_MERKLE_NAMESPACE,
        "D01B_ENVIRONMENT_SOURCE_MERKLE",
    )

    wheel_fields = frozenset(
        {
            "distribution",
            "version",
            "filename",
            "archive_member",
            "sha256",
            "size_bytes",
        }
    )
    wheels = [
        _object(item, "D01B_ENVIRONMENT_WHEEL")
        for item in _list(manifest["runtime_wheels"], "D01B_RUNTIME_WHEELS")
    ]
    if len(wheels) != 2:
        raise ManifestFreezeError("D01B_RUNTIME_WHEEL_COUNT")
    wheel_names: list[str] = []
    wheel_versions: dict[str, str] = {}
    for wheel in wheels:
        _strict_fields(wheel, wheel_fields, "D01B_ENVIRONMENT_WHEEL")
        distribution = _string(
            wheel["distribution"],
            "D01B_WHEEL_DISTRIBUTION",
        )
        version = _string(wheel["version"], "D01B_WHEEL_VERSION")
        filename = _string(wheel["filename"], "D01B_WHEEL_FILENAME")
        member = _normalized_relative_posix_path(
            wheel["archive_member"],
            "D01B_WHEEL_ARCHIVE_MEMBER",
        )
        if filename != PurePosixPath(member).name:
            raise ManifestFreezeError("D01B_WHEEL_FILENAME_MISMATCH")
        wheel_names.append(distribution)
        wheel_versions[distribution] = version
        _sha256(wheel["sha256"], "D01B_WHEEL_SHA256")
        if _integer(wheel["size_bytes"], "D01B_WHEEL_SIZE") <= 0:
            raise ManifestFreezeError("D01B_WHEEL_SIZE_INVALID")
    if wheel_names != sorted(wheel_names) or set(wheel_names) != {
        "arc-agi",
        "arcengine",
    }:
        raise ManifestFreezeError("D01B_RUNTIME_WHEEL_SET")
    if wheel_versions != {"arc-agi": "0.9.8", "arcengine": "0.9.3"}:
        raise ManifestFreezeError("D01B_RUNTIME_WHEEL_VERSION_SET")

    python_record = _object(manifest["python"], "D01B_ENVIRONMENT_PYTHON")
    _strict_fields(
        python_record,
        frozenset(
            {
                "implementation",
                "version",
                "architecture",
                "abi_flags",
                "soabi",
            }
        ),
        "D01B_ENVIRONMENT_PYTHON",
    )
    if (
        python_record["implementation"] != "CPython"
        or python_record["version"] != "3.12.13"
    ):
        raise ManifestFreezeError("D01B_ENVIRONMENT_PYTHON_INVALID")
    _string(python_record["architecture"], "D01B_PYTHON_ARCHITECTURE")
    if not isinstance(python_record["abi_flags"], str):
        raise ManifestFreezeError("D01B_PYTHON_ABI_FLAGS")
    if python_record["soabi"] is not None and not isinstance(
        python_record["soabi"],
        str,
    ):
        raise ManifestFreezeError("D01B_PYTHON_SOABI")

    os_record = _object(manifest["os"], "D01B_ENVIRONMENT_OS")
    _strict_fields(
        os_record,
        frozenset({"system", "release", "version", "machine"}),
        "D01B_ENVIRONMENT_OS",
    )
    for field in sorted(os_record):
        _string(os_record[field], "D01B_ENVIRONMENT_OS_" + field.upper())

    dependencies = [
        _object(item, "D01B_DEPENDENCY")
        for item in _list(manifest["dependencies"], "D01B_DEPENDENCIES")
    ]
    if not dependencies:
        raise ManifestFreezeError("D01B_DEPENDENCY_LOCK_EMPTY")
    dependency_pairs: list[tuple[str, str]] = []
    for dependency in dependencies:
        _strict_fields(
            dependency,
            frozenset({"name", "version"}),
            "D01B_DEPENDENCY",
        )
        dependency_pairs.append(
            (
                _string(dependency["name"], "D01B_DEPENDENCY_NAME"),
                _string(dependency["version"], "D01B_DEPENDENCY_VERSION"),
            )
        )
    if (
        dependency_pairs != sorted(dependency_pairs)
        or len(dependency_pairs) != len(set(dependency_pairs))
    ):
        raise ManifestFreezeError("D01B_DEPENDENCY_LOCK_ORDER_OR_DUPLICATE")
    if not set(wheel_versions.items()).issubset(set(dependency_pairs)):
        raise ManifestFreezeError("D01B_RUNTIME_WHEEL_NOT_INSTALLED")
    dependency_digest = _bound_digest(
        manifest["dependency_lock_digest"],
        DEPENDENCY_LOCK_DIGEST_NAMESPACE,
        "D01B_DEPENDENCY_LOCK_DIGEST",
    )
    if dependency_digest != _digest(
        {"dependencies": cast(JsonValue, dependencies)},
        DEPENDENCY_LOCK_DIGEST_NAMESPACE,
        excluded_fields=(),
    ):
        raise ManifestFreezeError("D01B_DEPENDENCY_LOCK_DIGEST_MISMATCH")

    if _integer(manifest["seed"], "D01B_ENVIRONMENT_SEED") < 0:
        raise ManifestFreezeError("D01B_ENVIRONMENT_SEED_INVALID")
    if manifest["reset_mode"] != "OFFLINE_FULL_RESET_PER_REPLAY":
        raise ManifestFreezeError("D01B_ENVIRONMENT_RESET_MODE")
    access = _object(
        manifest["source_access_contract"],
        "D01B_SOURCE_ACCESS_CONTRACT",
    )
    _strict_fields(
        access,
        frozenset(
            {
                "mode",
                "source_write_count",
                "source_mutation_count",
                "environment_source_consumer",
            }
        ),
        "D01B_SOURCE_ACCESS_CONTRACT",
    )
    expected_access: JsonObject = {
        "mode": "READ_ONLY_HASH_AND_REPLAY_INTERFACE",
        "source_write_count": 0,
        "source_mutation_count": 0,
        "environment_source_consumer": "REPLAY_HARNESS_ONLY",
    }
    if access != expected_access:
        raise ManifestFreezeError("D01B_SOURCE_ACCESS_CONTRACT_MISMATCH")
    _bound_digest(
        manifest["isolation_report_digest"],
        ISOLATION_REPORT_DIGEST_NAMESPACE,
        "D01B_ISOLATION_REPORT_DIGEST",
    )
    excluded = _require_digest_excluded_fields(
        manifest["digest_excluded_fields"],
        ("content_digest",),
        "D01B_ENVIRONMENT_EXCLUDED_FIELDS",
    )
    claimed = _bound_digest(
        manifest["content_digest"],
        ENVIRONMENT_DIGEST_NAMESPACE,
        "D01B_ENVIRONMENT_DIGEST",
    )
    if claimed != _digest(
        manifest,
        ENVIRONMENT_DIGEST_NAMESPACE,
        excluded_fields=excluded,
    ):
        raise ManifestFreezeError("D01B_ENVIRONMENT_DIGEST_MISMATCH")


def validate_run_manifest(
    manifest: Mapping[str, JsonValue],
) -> None:
    """Fail unless one run record is complete, ordered, and self-bound."""

    _strict_fields(manifest, RUN_MANIFEST_FIELDS, "D01B_RUN_MANIFEST")
    if manifest["schema_version"] != RUN_SCHEMA_VERSION:
        raise ManifestFreezeError("D01B_RUN_SCHEMA")
    _string(manifest["run_id"], "D01B_RUN_ID")
    _string(manifest["purpose"], "D01B_RUN_PURPOSE")
    profile_ids = _string_list(
        manifest["input_profile_ids"],
        "D01B_RUN_PROFILE_IDS",
    )
    if (
        not profile_ids
        or profile_ids != sorted(profile_ids)
        or len(profile_ids) != len(set(profile_ids))
    ):
        raise ManifestFreezeError("D01B_RUN_PROFILE_IDS_INVALID")
    input_digests = _string_list(
        manifest["input_content_digests"],
        "D01B_RUN_INPUT_DIGESTS",
    )
    if (
        len(input_digests) != len(profile_ids)
        or input_digests != sorted(input_digests)
        or len(input_digests) != len(set(input_digests))
    ):
        raise ManifestFreezeError("D01B_RUN_INPUT_DIGESTS_INVALID")
    for digest in input_digests:
        _bound_digest(
            digest,
            SOURCE_MANIFEST_DIGEST_NAMESPACE,
            "D01B_RUN_INPUT_DIGEST",
        )
    _bound_digest(
        manifest["environment_manifest_digest"],
        ENVIRONMENT_DIGEST_NAMESPACE,
        "D01B_RUN_ENVIRONMENT_DIGEST",
    )
    _string(manifest["working_directory"], "D01B_RUN_WORKING_DIRECTORY")
    command = _string_list(manifest["command"], "D01B_RUN_COMMAND")
    if not command:
        raise ManifestFreezeError("D01B_RUN_COMMAND_EMPTY")
    _sha256(manifest["capture_tool_sha256"], "D01B_CAPTURE_TOOL_SHA256")
    started_at = _timestamp(manifest["started_at"], "D01B_RUN_STARTED_AT")
    ended_at = _timestamp(manifest["ended_at"], "D01B_RUN_ENDED_AT")
    if datetime.fromisoformat(
        ended_at.removesuffix("Z") + "+00:00"
    ) < datetime.fromisoformat(started_at.removesuffix("Z") + "+00:00"):
        raise ManifestFreezeError("D01B_RUN_TIME_ORDER")
    if _integer(manifest["exit_code"], "D01B_RUN_EXIT_CODE") != 0:
        raise ManifestFreezeError("D01B_RUN_EXIT_NONZERO")
    _sha256(manifest["stdout_sha256"], "D01B_RUN_STDOUT_SHA256")
    _sha256(manifest["stderr_sha256"], "D01B_RUN_STDERR_SHA256")
    if manifest["network_scope"] not in {
        "NONE",
        "PINNED_HUGGINGFACE_DATASET_READ_ONLY",
    }:
        raise ManifestFreezeError("D01B_RUN_NETWORK_SCOPE")
    excluded = _require_digest_excluded_fields(
        manifest["digest_excluded_fields"],
        ("run_digest",),
        "D01B_RUN_EXCLUDED_FIELDS",
    )
    claimed = _bound_digest(
        manifest["run_digest"],
        RUN_DIGEST_NAMESPACE,
        "D01B_RUN_DIGEST",
    )
    if claimed != _digest(
        manifest,
        RUN_DIGEST_NAMESPACE,
        excluded_fields=excluded,
    ):
        raise ManifestFreezeError("D01B_RUN_DIGEST_MISMATCH")


def _load_plan(project_root: Path) -> JsonObject:
    plan = _read_json(
        project_root / "input" / "manifest_freeze_plan.json",
        "D01B_PLAN",
    )
    _strict_fields(plan, PLAN_FIELDS, "D01B_PLAN")
    if (
        plan["schema_version"] != PLAN_SCHEMA_VERSION
        or plan["phase_id"] != PHASE_ID
    ):
        raise ManifestFreezeError("D01B_PLAN_SCHEMA_OR_PHASE")
    excluded = [
        _string(item, "D01B_PLAN_EXCLUDED_FIELD")
        for item in _list(
            plan["digest_excluded_fields"],
            "D01B_PLAN_EXCLUDED_FIELDS",
        )
    ]
    if excluded != ["content_digest"]:
        raise ManifestFreezeError("D01B_PLAN_EXCLUDED_FIELDS_INVALID")
    claimed = _bound_digest(
        plan["content_digest"],
        PLAN_DIGEST_NAMESPACE,
        "D01B_PLAN_DIGEST",
    )
    if claimed != _digest(
        plan,
        PLAN_DIGEST_NAMESPACE,
        excluded_fields=excluded,
    ):
        raise ManifestFreezeError("D01B_PLAN_DIGEST_MISMATCH")
    return plan


def _load_capture(
    project_root: Path,
    plan: Mapping[str, JsonValue],
) -> JsonObject:
    binding = _object(
        plan["raw_recording_capture"],
        "D01B_CAPTURE_BINDING",
    )
    _strict_fields(
        binding,
        frozenset(
            {
                "path",
                "content_digest",
                "dataset_id",
                "dataset_repo_sha",
                "config",
                "split",
                "selected_row_count",
                "selected_level_count",
                "recording_filename_set_sha256",
            }
        ),
        "D01B_CAPTURE_BINDING",
    )
    path = project_root.parent / _normalized_relative_posix_path(
        binding["path"],
        "D01B_CAPTURE_PATH",
    )
    capture = _read_json(path, "D01B_CAPTURE")
    expected_capture_fields = frozenset(
        {
            "schema_version",
            "capture_id",
            "dataset_id",
            "dataset_repo_sha",
            "config",
            "split",
            "selected_row_count",
            "selected_level_count",
            "recording_filename_set_sha256",
            "rows",
            "acquisition",
            "digest_excluded_fields",
            "content_digest",
        }
    )
    _strict_fields(capture, expected_capture_fields, "D01B_CAPTURE")
    if capture["schema_version"] != CAPTURE_SCHEMA_VERSION:
        raise ManifestFreezeError("D01B_CAPTURE_SCHEMA")
    for field in ("dataset_id", "dataset_repo_sha", "config", "split"):
        if capture[field] != binding[field]:
            raise ManifestFreezeError(
                "D01B_CAPTURE_BINDING_MISMATCH:" + field
            )
    if (
        capture["selected_row_count"] != binding["selected_row_count"]
        or capture["selected_level_count"] != binding["selected_level_count"]
        or capture["recording_filename_set_sha256"]
        != binding["recording_filename_set_sha256"]
    ):
        raise ManifestFreezeError("D01B_CAPTURE_SELECTION_BINDING_MISMATCH")
    excluded = [
        _string(item, "D01B_CAPTURE_EXCLUDED_FIELD")
        for item in _list(
            capture["digest_excluded_fields"],
            "D01B_CAPTURE_EXCLUDED_FIELDS",
        )
    ]
    if excluded != ["acquisition", "content_digest"]:
        raise ManifestFreezeError("D01B_CAPTURE_EXCLUDED_FIELDS_INVALID")
    claimed = _bound_digest(
        capture["content_digest"],
        CAPTURE_DIGEST_NAMESPACE,
        "D01B_CAPTURE_DIGEST",
    )
    if claimed != binding["content_digest"]:
        raise ManifestFreezeError("D01B_CAPTURE_PLAN_DIGEST_MISMATCH")
    if claimed != _digest(
        capture,
        CAPTURE_DIGEST_NAMESPACE,
        excluded_fields=excluded,
    ):
        raise ManifestFreezeError("D01B_CAPTURE_DIGEST_MISMATCH")
    rows = [
        _object(item, "D01B_CAPTURE_ROW")
        for item in _list(capture["rows"], "D01B_CAPTURE_ROWS")
    ]
    if (
        _integer(
            capture["selected_row_count"],
            "D01B_CAPTURE_ROW_COUNT",
        )
        != 25
        or len(rows) != 25
    ):
        raise ManifestFreezeError("D01B_CAPTURE_ROW_COUNT_MISMATCH")
    filenames = [
        _string(item.get("recording_file"), "D01B_RECORDING_FILE")
        for item in rows
    ]
    if filenames != sorted(filenames) or len(filenames) != len(set(filenames)):
        raise ManifestFreezeError("D01B_CAPTURE_ROW_ORDER_OR_DUPLICATE")
    filename_set_sha256 = hashlib.sha256(
        canonical_json(cast(JsonValue, sorted(filenames))).encode("utf-8")
    ).hexdigest()
    if filename_set_sha256 != _sha256(
        capture["recording_filename_set_sha256"],
        "D01B_CAPTURE_FILENAME_SET_SHA256",
    ):
        raise ManifestFreezeError("D01B_CAPTURE_FILENAME_SET_MISMATCH")
    row_fields = frozenset(
        {
            "game_id",
            "row_index",
            "recording_file",
            "target_levels",
            "expected_actions",
            "trajectory_sha256",
            "trajectory_size_bytes",
            "row_binding_digest",
        }
    )
    game_ids: list[str] = []
    row_indexes: list[int] = []
    selected_level_count = 0
    for row in rows:
        _strict_fields(row, row_fields, "D01B_CAPTURE_ROW")
        game_ids.append(_string(row["game_id"], "D01B_CAPTURE_GAME_ID"))
        row_indexes.append(
            _integer(row["row_index"], "D01B_CAPTURE_ROW_INDEX")
        )
        selected_level_count += _integer(
            row["target_levels"],
            "D01B_CAPTURE_TARGET_LEVELS",
        )
        if _integer(
            row["expected_actions"],
            "D01B_CAPTURE_EXPECTED_ACTIONS",
        ) <= 0:
            raise ManifestFreezeError("D01B_CAPTURE_EXPECTED_ACTIONS_INVALID")
        _sha256(
            row.get("trajectory_sha256"),
            "D01B_TRAJECTORY_SHA256",
        )
        if (
            _integer(
                row.get("trajectory_size_bytes"),
                "D01B_TRAJECTORY_SIZE",
            )
            <= 0
        ):
            raise ManifestFreezeError("D01B_TRAJECTORY_SIZE_INVALID")
        claimed_row_digest = _bound_digest(
            row["row_binding_digest"],
            RAW_RECORDING_ROW_DIGEST_NAMESPACE,
            "D01B_CAPTURE_ROW_BINDING_DIGEST",
        )
        if claimed_row_digest != _digest(
            row,
            RAW_RECORDING_ROW_DIGEST_NAMESPACE,
            excluded_fields=("row_binding_digest",),
        ):
            raise ManifestFreezeError("D01B_CAPTURE_ROW_BINDING_MISMATCH")
    if (
        len(game_ids) != len(set(game_ids))
        or len(row_indexes) != len(set(row_indexes))
    ):
        raise ManifestFreezeError("D01B_CAPTURE_ID_OR_INDEX_DUPLICATE")
    if selected_level_count != _integer(
        capture["selected_level_count"],
        "D01B_CAPTURE_LEVEL_COUNT",
    ):
        raise ManifestFreezeError("D01B_CAPTURE_LEVEL_COUNT_MISMATCH")

    acquisition = _object(
        capture["acquisition"],
        "D01B_CAPTURE_ACQUISITION",
    )
    _strict_fields(
        acquisition,
        frozenset(
            {
                "api_call_count",
                "captured_at",
                "dataset_sha_before_capture",
                "dataset_sha_after_capture",
                "dataset_last_modified_at_capture",
                "trajectory_payload_retained",
                "trajectory_semantic_parse_count",
                "transient_retry_count",
                "transport",
                "user_agent",
            }
        ),
        "D01B_CAPTURE_ACQUISITION",
    )
    if (
        acquisition["dataset_sha_before_capture"]
        != capture["dataset_repo_sha"]
        or acquisition["dataset_sha_after_capture"]
        != capture["dataset_repo_sha"]
    ):
        raise ManifestFreezeError("D01B_CAPTURE_REVISION_CHANGED_DURING_READ")
    _timestamp(acquisition["captured_at"], "D01B_CAPTURED_AT")
    _timestamp(
        acquisition["dataset_last_modified_at_capture"],
        "D01B_DATASET_LAST_MODIFIED",
    )
    if _boolean(
        acquisition["trajectory_payload_retained"],
        "D01B_TRAJECTORY_PAYLOAD_RETAINED",
    ):
        raise ManifestFreezeError("D01B_TRAJECTORY_PAYLOAD_WAS_RETAINED")
    if _integer(
        acquisition["trajectory_semantic_parse_count"],
        "D01B_TRAJECTORY_SEMANTIC_PARSE_COUNT",
    ) != 0:
        raise ManifestFreezeError("D01B_TRAJECTORY_SEMANTIC_PARSE_OCCURRED")
    if (
        acquisition["transport"]
        != "HUGGINGFACE_DATASET_VIEWER_ROWS_HTTPS_GET"
    ):
        raise ManifestFreezeError("D01B_CAPTURE_TRANSPORT")
    _string(acquisition["user_agent"], "D01B_CAPTURE_USER_AGENT")

    budget = _object(plan["resource_budget"], "D01B_RESOURCE_BUDGET")
    required_budget_fields = frozenset(
        {
            "distribution_archive_sha256_read_count",
            "archive_member_content_hash_max_count",
            "repository_source_content_hash_count",
            "remote_recording_content_hash_count",
            "huggingface_dataset_viewer_read_call_max_count",
            "huggingface_dataset_viewer_transient_retry_max_count",
            "source_payload_semantic_parse_count",
            "arc_environment_source_execution_count",
            "teacher_replay_execution_count",
            "llm_call_count",
            "locked_final_access_count",
            "official_access_count",
            "network_submission_count",
            "kaggle_mutation_count",
            "external_network_use",
        }
    )
    _strict_fields(budget, required_budget_fields, "D01B_RESOURCE_BUDGET")
    api_call_count = _integer(
        acquisition["api_call_count"],
        "D01B_CAPTURE_API_CALL_COUNT",
    )
    retry_count = _integer(
        acquisition["transient_retry_count"],
        "D01B_CAPTURE_RETRY_COUNT",
    )
    if (
        api_call_count <= 0
        or api_call_count
        > _integer(
            budget["huggingface_dataset_viewer_read_call_max_count"],
            "D01B_CAPTURE_CALL_MAX",
        )
        or retry_count < 0
        or retry_count
        > _integer(
            budget["huggingface_dataset_viewer_transient_retry_max_count"],
            "D01B_CAPTURE_RETRY_MAX",
        )
    ):
        raise ManifestFreezeError("D01B_CAPTURE_RESOURCE_BUDGET_EXCEEDED")
    for zero_field in (
        "source_payload_semantic_parse_count",
        "arc_environment_source_execution_count",
        "teacher_replay_execution_count",
        "llm_call_count",
        "locked_final_access_count",
        "official_access_count",
        "network_submission_count",
        "kaggle_mutation_count",
    ):
        if _integer(budget[zero_field], "D01B_RESOURCE_" + zero_field) != 0:
            raise ManifestFreezeError(
                "D01B_RESOURCE_ZERO_BOUNDARY:" + zero_field
            )
    return capture


def _distribution_index(
    plan: Mapping[str, JsonValue],
    distribution_paths: Mapping[str, Path],
) -> tuple[dict[str, JsonObject], dict[str, Path]]:
    definitions: dict[str, JsonObject] = {}
    resolved: dict[str, Path] = {}
    rows = _list(plan["distributions"], "D01B_DISTRIBUTIONS")
    for item in rows:
        row = _object(item, "D01B_DISTRIBUTION")
        _strict_fields(
            row,
            frozenset({"distribution_id", "expected_sha256"}),
            "D01B_DISTRIBUTION",
        )
        distribution_id = _string(
            row["distribution_id"],
            "D01B_DISTRIBUTION_ID",
        )
        if distribution_id in definitions:
            raise ManifestFreezeError("D01B_DISTRIBUTION_DUPLICATE")
        expected = _sha256(
            row["expected_sha256"],
            "D01B_DISTRIBUTION_SHA256",
        )
        path = distribution_paths.get(distribution_id)
        if path is None:
            raise ManifestFreezeError(
                "D01B_DISTRIBUTION_PATH_MISSING:" + distribution_id
            )
        actual, _size = _file_sha256(path)
        if actual != expected:
            raise ManifestFreezeError(
                "D01B_DISTRIBUTION_SHA256_MISMATCH:" + distribution_id
            )
        definitions[distribution_id] = row
        resolved[distribution_id] = path
    if set(distribution_paths) != set(definitions):
        raise ManifestFreezeError("D01B_DISTRIBUTION_PATH_SET_MISMATCH")
    return definitions, resolved


def _profile_binding_index(
    plan: Mapping[str, JsonValue],
) -> dict[str, JsonObject]:
    index: dict[str, JsonObject] = {}
    expected = frozenset(
        {
            "profile_id",
            "path_mode",
            "logical_path_prefix",
            "upstream_repository",
            "upstream_commit_or_release",
            "license",
        }
    )
    for item in _list(plan["profile_bindings"], "D01B_PROFILE_BINDINGS"):
        row = _object(item, "D01B_PROFILE_BINDING")
        _strict_fields(row, expected, "D01B_PROFILE_BINDING")
        profile_id = _string(row["profile_id"], "D01B_PROFILE_ID")
        if profile_id in index:
            raise ManifestFreezeError("D01B_PROFILE_BINDING_DUPLICATE")
        if row["path_mode"] not in {
            "REPOSITORY_PATH",
            "ARC2_ARCHIVE_MEMBER",
            "RAW_RECORDING_LOGICAL_PATH",
        }:
            raise ManifestFreezeError("D01B_PROFILE_PATH_MODE")
        prefix = _string(
            row["logical_path_prefix"],
            "D01B_LOGICAL_PATH_PREFIX",
        )
        _normalized_relative_posix_path(
            prefix,
            "D01B_LOGICAL_PATH_PREFIX",
        )
        index[profile_id] = row
    return index


def _profile_digest_index(
    inventory: Mapping[str, JsonValue],
) -> dict[str, str]:
    index: dict[str, str] = {}
    for item in _list(
        inventory["profile_manifest"],
        "D01B_PROFILE_MANIFEST",
    ):
        row = _object(item, "D01B_PROFILE_MANIFEST_ROW")
        profile_id = _string(row.get("profile_id"), "D01B_PROFILE_ID")
        digest = _bound_digest(
            row.get("content_digest"),
            "hds-source-profile",
            "D01B_PROFILE_DIGEST",
        )
        index[profile_id] = digest
    return index


def _archive_locator(locator: str) -> tuple[str, str]:
    distribution_id, separator, member = locator.partition("!/")
    if separator != "!/" or not distribution_id or not member:
        raise ManifestFreezeError("D01B_ARCHIVE_LOCATOR_INVALID")
    return distribution_id, _normalized_relative_posix_path(
        member,
        "D01B_ARCHIVE_MEMBER",
    )


def _logical_path(
    record: Mapping[str, JsonValue],
    binding: Mapping[str, JsonValue],
) -> str:
    locator = _string(record["locator"], "D01B_SOURCE_LOCATOR")
    prefix = _string(
        binding["logical_path_prefix"],
        "D01B_LOGICAL_PATH_PREFIX",
    )
    if binding["path_mode"] == "REPOSITORY_PATH":
        return _normalized_relative_posix_path(
            locator,
            "D01B_REPOSITORY_SOURCE_PATH",
        )
    if binding["path_mode"] == "ARC2_ARCHIVE_MEMBER":
        _distribution, member = _archive_locator(locator)
        return _normalized_relative_posix_path(
            prefix + "/" + member,
            "D01B_ARC2_LOGICAL_PATH",
        )
    filename = locator.rsplit("/", 1)[-1]
    return _normalized_relative_posix_path(
        prefix + "/" + filename,
        "D01B_RECORDING_LOGICAL_PATH",
    )


def _repository_file_record(
    record: Mapping[str, JsonValue],
    binding: Mapping[str, JsonValue],
    repository_root: Path,
    archives: Mapping[str, zipfile.ZipFile],
) -> JsonObject:
    locator = _normalized_relative_posix_path(
        record["locator"],
        "D01B_REPOSITORY_SOURCE_PATH",
    )
    path = repository_root / locator
    digest, size = _file_sha256(path)
    aliases = [
        _string(item, "D01B_SOURCE_ALIAS")
        for item in _list(record["aliases"], "D01B_SOURCE_ALIASES")
    ]
    method = "REPOSITORY_FILE_SHA256"
    if aliases:
        for alias in aliases:
            normalized_alias = alias.removeprefix("archive:")
            distribution_id, member = _archive_locator(normalized_alias)
            archive = archives.get(distribution_id)
            if archive is None:
                raise ManifestFreezeError(
                    "D01B_ALIAS_DISTRIBUTION_MISSING:"
                    + distribution_id
                )
            archive_payload = _zip_member_bytes(archive, member)
            if (
                len(archive_payload) != size
                or hashlib.sha256(archive_payload).hexdigest() != digest
            ):
                raise ManifestFreezeError(
                    "D01B_ARCHIVE_ALIAS_CONTENT_MISMATCH:" + locator
                )
        method = "REPOSITORY_ARCHIVE_ALIAS_BYTE_IDENTITY"
    return {
        "source_id": record["source_id"],
        "repository_relative_posix_path": _logical_path(record, binding),
        "source_locator": locator,
        "aliases": cast(JsonValue, aliases),
        "sha256": digest,
        "size_bytes": size,
        "verification_method": method,
    }


def _archive_file_record(
    record: Mapping[str, JsonValue],
    binding: Mapping[str, JsonValue],
    archives: Mapping[str, zipfile.ZipFile],
) -> JsonObject:
    locator = _string(record["locator"], "D01B_ARCHIVE_LOCATOR")
    distribution_id, member = _archive_locator(locator)
    archive = archives.get(distribution_id)
    if archive is None:
        raise ManifestFreezeError(
            "D01B_ARCHIVE_DISTRIBUTION_MISSING:" + distribution_id
        )
    payload = _zip_member_bytes(archive, member)
    return {
        "source_id": record["source_id"],
        "repository_relative_posix_path": _logical_path(record, binding),
        "source_locator": locator,
        "aliases": [],
        "sha256": hashlib.sha256(payload).hexdigest(),
        "size_bytes": len(payload),
        "verification_method": "ARCHIVE_MEMBER_SHA256",
    }


def _capture_file_record(
    record: Mapping[str, JsonValue],
    binding: Mapping[str, JsonValue],
    capture_rows: Mapping[str, Mapping[str, JsonValue]],
) -> JsonObject:
    locator = _string(record["locator"], "D01B_RECORDING_LOCATOR")
    filename = locator.rsplit("/", 1)[-1]
    captured = capture_rows.get(filename)
    if captured is None:
        raise ManifestFreezeError(
            "D01B_CAPTURE_ROW_MISSING:" + filename
        )
    return {
        "source_id": record["source_id"],
        "repository_relative_posix_path": _logical_path(record, binding),
        "source_locator": locator,
        "aliases": [],
        "sha256": _sha256(
            captured["trajectory_sha256"],
            "D01B_TRAJECTORY_SHA256",
        ),
        "size_bytes": _integer(
            captured["trajectory_size_bytes"],
            "D01B_TRAJECTORY_SIZE",
        ),
        "verification_method": "PINNED_DATASET_TRAJECTORY_SHA256",
    }


def _source_input_snapshot(
    *,
    repository_root: Path,
    inventory: Mapping[str, JsonValue],
    distribution_paths: Mapping[str, Path],
    capture_path: Path,
) -> str:
    records: list[JsonObject] = []
    for item in _list(
        inventory["source_records"],
        "D01B_SOURCE_RECORDS",
    ):
        record = _object(item, "D01B_SOURCE_RECORD")
        if record["locator_kind"] != "REPOSITORY_FILE":
            continue
        locator = _normalized_relative_posix_path(
            record["locator"],
            "D01B_REPOSITORY_SOURCE_PATH",
        )
        digest, size = _file_sha256(repository_root / locator)
        records.append(
            {
                "kind": "REPOSITORY_SOURCE",
                "identity": locator,
                "sha256": digest,
                "size_bytes": size,
            }
        )
    for distribution_id, path in sorted(distribution_paths.items()):
        digest, size = _file_sha256(path)
        records.append(
            {
                "kind": "EXTERNAL_DISTRIBUTION",
                "identity": distribution_id,
                "sha256": digest,
                "size_bytes": size,
            }
        )
    digest, size = _file_sha256(capture_path)
    records.append(
        {
            "kind": "FROZEN_REMOTE_CAPTURE",
            "identity": capture_path.name,
            "sha256": digest,
            "size_bytes": size,
        }
    )
    records.sort(
        key=lambda item: (
            _string(item["kind"], "D01B_SNAPSHOT_KIND"),
            _string(item["identity"], "D01B_SNAPSHOT_IDENTITY"),
        )
    )
    return INPUT_SNAPSHOT_NAMESPACE + ":" + hashlib.sha256(
        canonical_json(cast(JsonValue, records)).encode("utf-8")
    ).hexdigest()


def _runtime_dependencies() -> list[JsonObject]:
    records = {
        (
            str(distribution.metadata.get("Name", "")).strip()
            .casefold()
            .replace("_", "-"),
            str(distribution.version),
        )
        for distribution in importlib.metadata.distributions()
        if str(distribution.metadata.get("Name", "")).strip()
    }
    return [
        {"name": name, "version": version}
        for name, version in sorted(records)
    ]


def _runtime_python() -> JsonObject:
    return {
        "implementation": platform.python_implementation(),
        "version": platform.python_version(),
        "architecture": f"{struct.calcsize('P') * 8}bit",
        "abi_flags": getattr(sys, "abiflags", ""),
        "soabi": sysconfig.get_config_var("SOABI"),
    }


def _runtime_os() -> JsonObject:
    return {
        "system": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "machine": platform.machine(),
    }


def _build_isolation_report(
    *,
    pre_snapshot: str,
    post_snapshot: str,
    capture: Mapping[str, JsonValue],
    plan: Mapping[str, JsonValue],
) -> JsonObject:
    if pre_snapshot != post_snapshot:
        raise ManifestFreezeError("D01B_SOURCE_INPUT_MUTATION")
    acquisition = _object(
        capture["acquisition"],
        "D01B_CAPTURE_ACQUISITION",
    )
    report: JsonObject = {
        "schema_version": "hds-environment-isolation-report-v1",
        "report_id": "PH-D01B-MANIFEST-COMPILER-ISOLATION",
        "phase_id": PHASE_ID,
        "source_access_mode": "READ_ONLY_HASH_AND_REPLAY_INTERFACE",
        "source_snapshot_before": pre_snapshot,
        "source_snapshot_after": post_snapshot,
        "source_write_count": 0,
        "source_mutation_count": 0,
        "source_payload_semantic_parse_count": 0,
        "source_execution_count": 0,
        "teacher_replay_execution_count": 0,
        "compiler_network_call_count": 0,
        "external_capture_network_scope": (
            "PINNED_HUGGINGFACE_DATASET_READ_ONLY"
        ),
        "external_capture_revision_before": acquisition[
            "dataset_sha_before_capture"
        ],
        "external_capture_revision_after": acquisition[
            "dataset_sha_after_capture"
        ],
        "external_capture_api_call_count": _integer(
            acquisition["api_call_count"],
            "D01B_CAPTURE_API_CALL_COUNT",
        ),
        "external_capture_transient_retry_count": _integer(
            acquisition["transient_retry_count"],
            "D01B_CAPTURE_RETRY_COUNT",
        ),
        "secret_value_access_count": 0,
        "subprocess_execution_count": 0,
        "filesystem_write_allowlist": [
            "distillation/manifests/**",
            "distillation/artifacts/reports/**",
        ],
        "os_source_mount_read_only_enforced": False,
        "source_read_only_contract_pass": True,
        "scope_limit": (
            "Manifest compilation non-mutation and read-only API evidence "
            "only; later replay-sandbox mount enforcement is not claimed."
        ),
        "gates": {
            "DG-00": "PASS",
            "DG-06": "PASS",
            "DG-12": "PASS",
        },
        "finding_count": 0,
        "resource_budget": plan["resource_budget"],
        "digest_excluded_fields": [
            "content_digest",
            "report_id",
        ],
        "content_digest": "",
    }
    report["content_digest"] = _digest(
        report,
        ISOLATION_REPORT_DIGEST_NAMESPACE,
        excluded_fields=("content_digest", "report_id"),
    )
    return report


def _build_acquisition_records(
    plan: Mapping[str, JsonValue],
    manifests: Mapping[str, Mapping[str, JsonValue]],
) -> dict[str, JsonObject]:
    records: dict[str, JsonObject] = {}
    expected_fields = frozenset(
        {
            "profile_id",
            "acquisition_id",
            "acquired_at",
            "local_path",
            "mtime",
            "acquisition_actor",
            "transport",
            "notes",
        }
    )
    for item in _list(
        plan["acquisition_records"],
        "D01B_ACQUISITION_RECORDS",
    ):
        template = _object(item, "D01B_ACQUISITION_TEMPLATE")
        _strict_fields(
            template,
            expected_fields,
            "D01B_ACQUISITION_TEMPLATE",
        )
        profile_id = _string(
            template["profile_id"],
            "D01B_ACQUISITION_PROFILE_ID",
        )
        manifest = manifests.get(profile_id)
        if manifest is None:
            raise ManifestFreezeError(
                "D01B_ACQUISITION_PROFILE_UNKNOWN:" + profile_id
            )
        record: JsonObject = {
            "schema_version": ACQUISITION_SCHEMA_VERSION,
            "acquisition_id": template["acquisition_id"],
            "source_content_manifest_id": manifest["manifest_id"],
            "source_content_digest": manifest["content_digest"],
            "acquired_at": template["acquired_at"],
            "local_path": template["local_path"],
            "mtime": template["mtime"],
            "acquisition_actor": template["acquisition_actor"],
            "transport": template["transport"],
            "notes": template["notes"],
            "digest_excluded_fields": ["acquisition_digest"],
            "acquisition_digest": "",
        }
        record["acquisition_digest"] = _digest(
            record,
            ACQUISITION_DIGEST_NAMESPACE,
            excluded_fields=("acquisition_digest",),
        )
        validate_acquisition_record(record)
        if profile_id in records:
            raise ManifestFreezeError(
                "D01B_ACQUISITION_PROFILE_DUPLICATE:" + profile_id
            )
        records[profile_id] = record
    if set(records) != set(manifests):
        raise ManifestFreezeError("D01B_ACQUISITION_COVERAGE_MISMATCH")
    return records


def _build_environment_manifest(
    *,
    plan: Mapping[str, JsonValue],
    environment_source: Mapping[str, JsonValue],
    arc3_archive: zipfile.ZipFile,
    isolation_report: Mapping[str, JsonValue],
) -> JsonObject:
    environment = _object(plan["environment"], "D01B_ENVIRONMENT_PLAN")
    expected_fields = frozenset(
        {
            "manifest_id",
            "expected_python",
            "runtime_wheels",
            "seed",
            "reset_mode",
            "source_access_contract",
        }
    )
    _strict_fields(environment, expected_fields, "D01B_ENVIRONMENT_PLAN")
    python_record = _runtime_python()
    expected_python = _object(
        environment["expected_python"],
        "D01B_EXPECTED_PYTHON",
    )
    if python_record != expected_python:
        raise ManifestFreezeError("D01B_PYTHON_ENVIRONMENT_DRIFT")
    wheels: list[JsonObject] = []
    wheel_fields = frozenset(
        {
            "distribution",
            "version",
            "filename",
            "archive_member",
            "expected_sha256",
        }
    )
    for item in _list(
        environment["runtime_wheels"],
        "D01B_RUNTIME_WHEELS",
    ):
        wheel = _object(item, "D01B_RUNTIME_WHEEL")
        _strict_fields(wheel, wheel_fields, "D01B_RUNTIME_WHEEL")
        member = _normalized_relative_posix_path(
            wheel["archive_member"],
            "D01B_WHEEL_ARCHIVE_MEMBER",
        )
        payload = _zip_member_bytes(arc3_archive, member)
        digest = hashlib.sha256(payload).hexdigest()
        expected_digest = _sha256(
            wheel["expected_sha256"],
            "D01B_WHEEL_SHA256",
        )
        if digest != expected_digest:
            raise ManifestFreezeError(
                "D01B_WHEEL_SHA256_MISMATCH:" + member
            )
        wheels.append(
            {
                "distribution": wheel["distribution"],
                "version": wheel["version"],
                "filename": wheel["filename"],
                "archive_member": member,
                "sha256": digest,
                "size_bytes": len(payload),
            }
        )
    wheels.sort(key=lambda item: _string(item["distribution"], "D01B_WHEEL"))
    dependencies = _runtime_dependencies()
    dependency_lock_digest = _digest(
        {"dependencies": cast(JsonValue, dependencies)},
        DEPENDENCY_LOCK_DIGEST_NAMESPACE,
        excluded_fields=(),
    )
    manifest: JsonObject = {
        "schema_version": ENVIRONMENT_SCHEMA_VERSION,
        "manifest_id": environment["manifest_id"],
        "manifest_version": 1,
        "environment_source": {
            "source_content_manifest_id": environment_source["manifest_id"],
            "source_content_digest": environment_source["content_digest"],
            "source_count": environment_source["source_count"],
            "directory_merkle_root": environment_source[
                "directory_merkle_root"
            ],
        },
        "runtime_wheels": cast(JsonValue, wheels),
        "python": python_record,
        "os": _runtime_os(),
        "dependencies": cast(JsonValue, dependencies),
        "dependency_lock_digest": dependency_lock_digest,
        "seed": environment["seed"],
        "reset_mode": environment["reset_mode"],
        "source_access_contract": environment["source_access_contract"],
        "isolation_report_digest": isolation_report["content_digest"],
        "digest_excluded_fields": ["content_digest"],
        "content_digest": "",
    }
    manifest["content_digest"] = _digest(
        manifest,
        ENVIRONMENT_DIGEST_NAMESPACE,
        excluded_fields=("content_digest",),
    )
    validate_environment_manifest(manifest)
    return manifest


def _build_run_manifest(
    *,
    plan: Mapping[str, JsonValue],
    source_manifests: Mapping[str, Mapping[str, JsonValue]],
    environment_manifest: Mapping[str, JsonValue],
) -> JsonObject:
    template = _object(plan["run_manifest"], "D01B_RUN_TEMPLATE")
    expected_fields = frozenset(
        {
            "run_id",
            "purpose",
            "input_profile_ids",
            "working_directory",
            "command",
            "capture_tool_sha256",
            "started_at",
            "ended_at",
            "exit_code",
            "stdout_sha256",
            "stderr_sha256",
            "network_scope",
        }
    )
    _strict_fields(template, expected_fields, "D01B_RUN_TEMPLATE")
    input_profile_ids = sorted(
        _string_list(
            template["input_profile_ids"],
            "D01B_RUN_INPUT_PROFILE_IDS",
        )
    )
    if (
        not input_profile_ids
        or len(input_profile_ids) != len(set(input_profile_ids))
        or any(
            profile_id not in source_manifests
            for profile_id in input_profile_ids
        )
    ):
        raise ManifestFreezeError("D01B_RUN_INPUT_PROFILE_SET")
    input_digests = sorted(
        _bound_digest(
            source_manifests[profile_id]["content_digest"],
            SOURCE_MANIFEST_DIGEST_NAMESPACE,
            "D01B_RUN_INPUT_DIGEST",
        )
        for profile_id in input_profile_ids
    )
    manifest: JsonObject = {
        "schema_version": RUN_SCHEMA_VERSION,
        "run_id": template["run_id"],
        "purpose": template["purpose"],
        "input_profile_ids": cast(JsonValue, input_profile_ids),
        "input_content_digests": cast(JsonValue, input_digests),
        "environment_manifest_digest": environment_manifest[
            "content_digest"
        ],
        "working_directory": template["working_directory"],
        "command": template["command"],
        "capture_tool_sha256": template["capture_tool_sha256"],
        "started_at": template["started_at"],
        "ended_at": template["ended_at"],
        "exit_code": template["exit_code"],
        "stdout_sha256": template["stdout_sha256"],
        "stderr_sha256": template["stderr_sha256"],
        "network_scope": template["network_scope"],
        "digest_excluded_fields": ["run_digest"],
        "run_digest": "",
    }
    manifest["run_digest"] = _digest(
        manifest,
        RUN_DIGEST_NAMESPACE,
        excluded_fields=("run_digest",),
    )
    validate_run_manifest(manifest)
    return manifest


def _expected_accounting(
    plan: Mapping[str, JsonValue],
) -> JsonObject:
    expected = _object(
        plan["expected_accounting"],
        "D01B_EXPECTED_ACCOUNTING",
    )
    required = frozenset(
        {
            "source_content_manifest_count",
            "source_entry_count",
            "acquisition_record_count",
            "environment_manifest_count",
            "run_manifest_count",
            "raw_recording_verified_count",
            "environment_archive_alias_verified_count",
            "runtime_wheel_verified_count",
        }
    )
    _strict_fields(expected, required, "D01B_EXPECTED_ACCOUNTING")
    return expected


def build_manifest_freeze(
    project_root: Path,
    *,
    repository_root: Path,
    distribution_paths: Mapping[str, Path],
) -> dict[str, JsonValue]:
    """Build all checked PH-D01B artifacts without network or source execution."""

    project_root = project_root.resolve()
    repository_root = repository_root.resolve()
    plan = _load_plan(project_root)
    capture = _load_capture(project_root, plan)
    source_inventory_binding = _object(
        plan["source_inventory"],
        "D01B_SOURCE_INVENTORY_BINDING",
    )
    _strict_fields(
        source_inventory_binding,
        frozenset({"path", "content_digest"}),
        "D01B_SOURCE_INVENTORY_BINDING",
    )
    inventory_path = repository_root / _normalized_relative_posix_path(
        source_inventory_binding["path"],
        "D01B_SOURCE_INVENTORY_PATH",
    )
    inventory = verify_source_inventory_report(
        inventory_path,
        project_root,
        repository_root=repository_root,
    )
    if (
        inventory["content_digest"]
        != source_inventory_binding["content_digest"]
    ):
        raise ManifestFreezeError("D01B_SOURCE_INVENTORY_DIGEST_MISMATCH")
    _definitions, resolved_distributions = _distribution_index(
        plan,
        distribution_paths,
    )
    capture_binding = _object(
        plan["raw_recording_capture"],
        "D01B_CAPTURE_BINDING",
    )
    capture_path = repository_root / _normalized_relative_posix_path(
        capture_binding["path"],
        "D01B_CAPTURE_PATH",
    )
    pre_snapshot = _source_input_snapshot(
        repository_root=repository_root,
        inventory=inventory,
        distribution_paths=resolved_distributions,
        capture_path=capture_path,
    )
    profile_bindings = _profile_binding_index(plan)
    profile_digests = _profile_digest_index(inventory)
    records_by_profile: dict[str, list[JsonObject]] = defaultdict(list)
    for item in _list(
        inventory["source_records"],
        "D01B_SOURCE_RECORDS",
    ):
        record = _object(item, "D01B_SOURCE_RECORD")
        records_by_profile[
            _string(record["profile_id"], "D01B_PROFILE_ID")
        ].append(record)
    if set(records_by_profile) != set(profile_bindings):
        raise ManifestFreezeError("D01B_PROFILE_COVERAGE_MISMATCH")

    raw_profile_records = records_by_profile.get(
        "arc3-raw-teacher-recordings",
        [],
    )
    raw_locator_prefix = (
        _string(capture["dataset_id"], "D01B_CAPTURE_DATASET_ID")
        + "@"
        + _string(capture["dataset_repo_sha"], "D01B_CAPTURE_DATASET_SHA")
        + "/"
    )
    raw_locator_filenames: list[str] = []
    for raw_record in raw_profile_records:
        locator = _string(raw_record["locator"], "D01B_RECORDING_LOCATOR")
        if not locator.startswith(raw_locator_prefix):
            raise ManifestFreezeError("D01B_CAPTURE_INVENTORY_REVISION_MISMATCH")
        raw_locator_filenames.append(locator.removeprefix(raw_locator_prefix))
    capture_filenames = [
        _string(row["recording_file"], "D01B_RECORDING_FILE")
        for row in (
            _object(item, "D01B_CAPTURE_ROW")
            for item in _list(capture["rows"], "D01B_CAPTURE_ROWS")
        )
    ]
    if sorted(raw_locator_filenames) != sorted(capture_filenames):
        raise ManifestFreezeError("D01B_CAPTURE_INVENTORY_SELECTION_MISMATCH")

    capture_rows = {
        _string(row["recording_file"], "D01B_RECORDING_FILE"): row
        for row in (
            _object(item, "D01B_CAPTURE_ROW")
            for item in _list(capture["rows"], "D01B_CAPTURE_ROWS")
        )
    }
    archive_handles: dict[str, zipfile.ZipFile] = {}
    try:
        for distribution_id, path in resolved_distributions.items():
            archive_handles[distribution_id] = zipfile.ZipFile(path, "r")
        source_manifests: dict[str, JsonObject] = {}
        raw_verified_count = 0
        alias_verified_count = 0
        for profile_id in sorted(records_by_profile):
            source_records = sorted(
                records_by_profile[profile_id],
                key=lambda item: _string(
                    item["source_id"],
                    "D01B_SOURCE_ID",
                ),
            )
            binding = profile_bindings[profile_id]
            file_records: list[JsonObject] = []
            for source_record in source_records:
                locator_kind = source_record["locator_kind"]
                if locator_kind == "REPOSITORY_FILE":
                    file_record = _repository_file_record(
                        source_record,
                        binding,
                        repository_root,
                        archive_handles,
                    )
                    if file_record["verification_method"] == (
                        "REPOSITORY_ARCHIVE_ALIAS_BYTE_IDENTITY"
                    ):
                        alias_verified_count += 1
                elif locator_kind == "ARCHIVE_MEMBER":
                    file_record = _archive_file_record(
                        source_record,
                        binding,
                        archive_handles,
                    )
                elif locator_kind == "EXTERNAL_DATASET_MEMBER":
                    file_record = _capture_file_record(
                        source_record,
                        binding,
                        capture_rows,
                    )
                    raw_verified_count += 1
                else:
                    raise ManifestFreezeError(
                        "D01B_LOCATOR_KIND_FORBIDDEN:"
                        + str(locator_kind)
                    )
                file_records.append(file_record)
            first = source_records[0]
            manifest = build_source_content_manifest(
                manifest_id="source-content-" + profile_id,
                profile_id=profile_id,
                profile_digest=profile_digests[profile_id],
                domain=_string(first["domain"], "D01B_DOMAIN"),
                files=file_records,
                upstream_repository=_string(
                    binding["upstream_repository"],
                    "D01B_UPSTREAM_REPOSITORY",
                ),
                upstream_commit_or_release=_string(
                    binding["upstream_commit_or_release"],
                    "D01B_UPSTREAM_RELEASE",
                ),
                split_role=_string(
                    first["split_role"],
                    "D01B_SPLIT_ROLE",
                ),
                answer_visibility=_string(
                    first["answer_visibility"],
                    "D01B_ANSWER_VISIBILITY",
                ),
                development_usage=_string(
                    first["development_usage"],
                    "D01B_DEVELOPMENT_USAGE",
                ),
                contamination_class=_string(
                    first["contamination_class"],
                    "D01B_CONTAMINATION",
                ),
                license_value=_string(
                    binding["license"],
                    "D01B_LICENSE",
                ),
            )
            validate_source_content_manifest(manifest)
            source_manifests[profile_id] = manifest

        post_snapshot = _source_input_snapshot(
            repository_root=repository_root,
            inventory=inventory,
            distribution_paths=resolved_distributions,
            capture_path=capture_path,
        )
        isolation_report = _build_isolation_report(
            pre_snapshot=pre_snapshot,
            post_snapshot=post_snapshot,
            capture=capture,
            plan=plan,
        )
        acquisitions = _build_acquisition_records(
            plan,
            source_manifests,
        )
        arc3_archive = archive_handles.get(
            "arc-prize-2026-arc-agi-3.zip"
        )
        if arc3_archive is None:
            raise ManifestFreezeError("D01B_ARC3_ARCHIVE_MISSING")
        environment_source = source_manifests.get(
            "arc3-environment-source-bundle"
        )
        if environment_source is None:
            raise ManifestFreezeError(
                "D01B_ENVIRONMENT_SOURCE_MANIFEST_MISSING"
            )
        environment_manifest = _build_environment_manifest(
            plan=plan,
            environment_source=environment_source,
            arc3_archive=arc3_archive,
            isolation_report=isolation_report,
        )
        run_manifest = _build_run_manifest(
            plan=plan,
            source_manifests=source_manifests,
            environment_manifest=environment_manifest,
        )
    finally:
        for archive in archive_handles.values():
            archive.close()

    expected = _expected_accounting(plan)
    actual_accounting: JsonObject = {
        "source_content_manifest_count": len(source_manifests),
        "source_entry_count": sum(
            _integer(
                manifest["source_count"],
                "D01B_SOURCE_COUNT",
            )
            for manifest in source_manifests.values()
        ),
        "acquisition_record_count": len(acquisitions),
        "environment_manifest_count": 1,
        "run_manifest_count": 1,
        "raw_recording_verified_count": raw_verified_count,
        "environment_archive_alias_verified_count": alias_verified_count,
        "runtime_wheel_verified_count": len(
            _list(
                environment_manifest["runtime_wheels"],
                "D01B_RUNTIME_WHEELS",
            )
        ),
    }
    if actual_accounting != expected:
        raise ManifestFreezeError(
            "D01B_ACCOUNTING_MISMATCH:"
            f"expected={canonical_json(expected)}:"
            f"actual={canonical_json(actual_accounting)}"
        )
    phase_boundaries = _object(
        plan["phase_boundaries"],
        "D01B_PHASE_BOUNDARIES",
    )
    required_true = {
        "content_manifest_frozen",
        "acquisition_manifest_frozen",
        "environment_manifest_frozen",
    }
    if any(phase_boundaries.get(key) is not True for key in required_true):
        raise ManifestFreezeError("D01B_PHASE_FREEZE_BOUNDARY_FALSE")
    required_false_or_zero = {
        "trajectory_normalization_started": False,
        "causal_ir_started": False,
        "candidate_generation_started": False,
        "bridge_started": False,
        "runtime_started": False,
        "official_access_count": 0,
        "kaggle_mutation_count": 0,
    }
    if any(
        phase_boundaries.get(key) != value
        for key, value in required_false_or_zero.items()
    ):
        raise ManifestFreezeError("D01B_DOWNSTREAM_PHASE_BOUNDARY")

    freeze_report: JsonObject = {
        "schema_version": "hds-source-manifest-freeze-report-v1",
        "report_id": "HDS-SOURCE-MANIFEST-FREEZE-PH-D01B-V1",
        "phase_id": PHASE_ID,
        "plan_digest": plan["content_digest"],
        "source_inventory_digest": inventory["content_digest"],
        "raw_recording_capture_digest": capture["content_digest"],
        "source_content_manifests": [
            {
                "profile_id": profile_id,
                "manifest_id": manifest["manifest_id"],
                "content_digest": manifest["content_digest"],
                "directory_merkle_root": manifest[
                    "directory_merkle_root"
                ],
                "source_count": manifest["source_count"],
            }
            for profile_id, manifest in sorted(source_manifests.items())
        ],
        "acquisition_records": [
            {
                "profile_id": profile_id,
                "acquisition_id": record["acquisition_id"],
                "acquisition_digest": record["acquisition_digest"],
            }
            for profile_id, record in sorted(acquisitions.items())
        ],
        "environment_manifest": {
            "manifest_id": environment_manifest["manifest_id"],
            "content_digest": environment_manifest["content_digest"],
            "dependency_lock_digest": environment_manifest[
                "dependency_lock_digest"
            ],
        },
        "run_manifest": {
            "run_id": run_manifest["run_id"],
            "run_digest": run_manifest["run_digest"],
        },
        "isolation_report_digest": isolation_report["content_digest"],
        "accounting": actual_accounting,
        "input_snapshot_before": pre_snapshot,
        "input_snapshot_after": post_snapshot,
        "content_path_and_time_independent": True,
        "source_mutation_invalidates_downstream": True,
        "environment_binding_complete": True,
        "source_read_only_contract_pass": True,
        "gates": {
            "DG-00": "PASS",
            "DG-06": "PASS",
            "DG-12": "PASS",
        },
        "phase_boundaries": phase_boundaries,
        "phase_exit_claim": "ARC3_TEACHER_SOURCE_FROZEN",
        "claim_boundary": (
            "Source and environment identity only; not trajectory "
            "normalization, causal evidence, Rule promotion, Bridge, AGI, "
            "locked-final, official, or submission evidence."
        ),
        "digest_excluded_fields": [
            "content_digest",
            "report_id",
        ],
        "content_digest": "",
    }
    freeze_report["content_digest"] = _digest(
        freeze_report,
        FREEZE_REPORT_DIGEST_NAMESPACE,
        excluded_fields=("content_digest", "report_id"),
    )
    return {
        "source_manifests": cast(JsonValue, source_manifests),
        "acquisition_records": cast(JsonValue, acquisitions),
        "environment_manifest": environment_manifest,
        "run_manifest": run_manifest,
        "isolation_report": isolation_report,
        "freeze_report": freeze_report,
    }


def artifact_bytes(value: Mapping[str, JsonValue]) -> bytes:
    """Serialize one deterministic checked artifact."""

    return (canonical_json(dict(value)) + "\n").encode("utf-8")


def _artifact_map(
    bundle: Mapping[str, JsonValue],
) -> dict[str, Mapping[str, JsonValue]]:
    source_manifests = cast(
        Mapping[str, Mapping[str, JsonValue]],
        bundle["source_manifests"],
    )
    acquisitions = cast(
        Mapping[str, Mapping[str, JsonValue]],
        bundle["acquisition_records"],
    )
    artifacts: dict[str, Mapping[str, JsonValue]] = {}
    for profile_id, manifest in source_manifests.items():
        artifacts[
            "manifests/source_content/" + profile_id + ".json"
        ] = manifest
    for profile_id, record in acquisitions.items():
        artifacts["manifests/acquisition/" + profile_id + ".json"] = record
    artifacts["manifests/environment/arc3-replay.json"] = cast(
        Mapping[str, JsonValue],
        bundle["environment_manifest"],
    )
    artifacts["manifests/run/ph-d01b-freeze.json"] = cast(
        Mapping[str, JsonValue],
        bundle["run_manifest"],
    )
    artifacts["artifacts/reports/environment_isolation.json"] = cast(
        Mapping[str, JsonValue],
        bundle["isolation_report"],
    )
    artifacts["artifacts/reports/source_manifest_freeze.json"] = cast(
        Mapping[str, JsonValue],
        bundle["freeze_report"],
    )
    return artifacts


def write_manifest_freeze_artifacts(
    project_root: Path,
    *,
    repository_root: Path,
    distribution_paths: Mapping[str, Path],
) -> dict[str, JsonValue]:
    """Write only PH-D01B-owned deterministic manifest artifacts."""

    bundle = build_manifest_freeze(
        project_root,
        repository_root=repository_root,
        distribution_paths=distribution_paths,
    )
    for relative_path, value in sorted(_artifact_map(bundle).items()):
        output_path = project_root / relative_path
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_bytes(artifact_bytes(value))
    return bundle


def verify_manifest_freeze_artifacts(
    project_root: Path,
    *,
    repository_root: Path,
    distribution_paths: Mapping[str, Path],
) -> dict[str, JsonValue]:
    """Fail unless every checked PH-D01B artifact matches a live rebuild."""

    bundle = build_manifest_freeze(
        project_root,
        repository_root=repository_root,
        distribution_paths=distribution_paths,
    )
    for relative_path, value in sorted(_artifact_map(bundle).items()):
        checked_path = project_root / relative_path
        try:
            checked = checked_path.read_bytes()
        except OSError as exc:
            raise ManifestFreezeError(
                f"D01B_CHECKED_ARTIFACT_UNREADABLE:{relative_path}"
            ) from exc
        if checked != artifact_bytes(value):
            raise ManifestFreezeError(
                f"D01B_CHECKED_ARTIFACT_MISMATCH:{relative_path}"
            )
    return bundle


__all__ = [
    "ManifestFreezeError",
    "artifact_bytes",
    "build_manifest_freeze",
    "build_source_content_manifest",
    "directory_merkle_root",
    "validate_acquisition_record",
    "validate_environment_manifest",
    "validate_run_manifest",
    "validate_source_content_manifest",
    "verify_manifest_freeze_artifacts",
    "write_manifest_freeze_artifacts",
]
