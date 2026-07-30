#!/usr/bin/env python3
"""Fail-closed PH-D00A HDS dependency and authority audit.

The audit is deliberately independent of the ARC runtime and corpus. It reads
only locked authority files, schemas, manifests, and optional read-only Git
objects for the frozen HDS-BlackBox-Translator reference.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import subprocess
import sys
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Final, NoReturn

type JsonValue = (
    None
    | bool
    | int
    | float
    | str
    | list[JsonValue]
    | dict[str, JsonValue]
)

PHASE_ID: Final = "PH-D00A"
MANIFEST_SCHEMA_VERSION: Final = "hds-dependency-lock-v1"
OPEN_TERM_LEDGER_SCHEMA_VERSION: Final = "hds-open-term-ledger-v1"
REPORT_SCHEMA_VERSION: Final = "hds-dependency-audit-report-v1"
MANIFEST_RELATIVE_PATH: Final = (
    "artifacts/source_content_manifests/hds_dependencies.json"
)
AUTHORITY_ORDER_RELATIVE_PATH: Final = "AUTHORITY_ORDER.md"
OPEN_TERM_LEDGER_RELATIVE_PATH: Final = (
    "artifacts/reports/open_term_ledger.json"
)
DEPENDENCY_SCHEMA_RELATIVE_PATH: Final = (
    "schemas/dependency_lock.schema.json"
)
OPEN_TERM_SCHEMA_RELATIVE_PATH: Final = (
    "schemas/open_term_record.schema.json"
)
OWNER_APPROVAL_RELATIVE_PATH: Final = (
    "control/rev3/OWNER_APPROVAL_RECORDS/PH-R00.json"
)

EXPECTED_AUTHORITY_ORDER_SHA256: Final = (
    "dfe6fb43564c2aa1ee1cb83cb00861397a466f57a853cbc20a90981719d9e03c"
)
EXPECTED_OWNER_APPROVAL_SHA256: Final = (
    "e34e21bfb72172dda3c43b922119bee962a9aca899c9d4850402f90c5c7f04f7"
)
EXPECTED_OWNER_APPROVAL_DIGEST: Final = (
    "owner-approval-record:"
    "a7df8aa233f07c3bb3831f24eb462db0be5dc0fe6885a6da42bb5dce7c5693c0"
)

EXPECTED_LOCAL_DEPENDENCIES: Final[
    tuple[dict[str, JsonValue], ...]
] = (
    {
        "dependency_id": "HDS_DISTILLATION_ROADMAP_REV2",
        "path": (
            "docs/roadmap/HDS蒸留開発ロードマップ_ARC2_ARC3_rev2.md"
        ),
        "required": True,
        "role": "HDS_DISTILLATION_ROADMAP",
        "sha256": (
            "64640eff883f417baeb2d70716e1904c1fd765a3d1a5a5eacb8bba82e3500518"
        ),
        "size_bytes": 20818,
    },
    {
        "dependency_id": "HDS_DISTILLATION_SPEC_REV2",
        "path": "docs/strategy/HDS蒸留仕様書_ARC2_ARC3_rev2.md",
        "required": True,
        "role": "HDS_DISTILLATION_SPECIFICATION",
        "sha256": (
            "79bc7169550c94ea8d86d5004989f9d7c1d93fa173e5fad2d4df02d88fb6fc93"
        ),
        "size_bytes": 38926,
    },
    {
        "dependency_id": "HDS_FRAMEWORK_EXTERNAL_REV3_1",
        "path": "docs/references/HDSフレーム_rev3_1_外向け仕様.md",
        "required": True,
        "role": "HDS_EXTERNAL_SPECIFICATION",
        "sha256": (
            "d7cbbf4c981621509e124077ae66cc49bd29b2271fbf94194c6786d2a5a8724a"
        ),
        "size_bytes": 31229,
    },
    {
        "dependency_id": "HDS_FRAMEWORK_INTERNAL_REV3_1A",
        "path": "docs/references/HDS_FRAMEWORK_rev3_1a_INTERNAL.md",
        "required": True,
        "role": "HDS_INTERNAL_CANONICAL_SPECIFICATION",
        "sha256": (
            "6f55471c0bb3b2b54d434ac05ac09ee24ef69fda3f2f024e5f762696e822216c"
        ),
        "size_bytes": 32565,
    },
    {
        "dependency_id": "HDS_SELF_CONTAINED_PROMPT_V1_2",
        "path": "docs/references/HDS_SelfContained_Prompt_v1_2_utf8bom.txt",
        "required": True,
        "role": "HDS_SELF_CONTAINED_PROMPT",
        "sha256": (
            "33b8a35176a0cc2f18502befb4a53cfbbf378b35e36b911888fa534a8b377b50"
        ),
        "size_bytes": 9876,
    },
    {
        "dependency_id": "REV3_ARC3_ROADMAP",
        "path": "docs/roadmap/ARC3_HDS蒸留先行_開発ロードマップ_rev3.md",
        "required": True,
        "role": "ARC3_REV3_ROADMAP",
        "sha256": (
            "b210be684fd43c9f7a1f431e01c3cd5145e7c36301f2c55b9b2fcffc548652b2"
        ),
        "size_bytes": 17209,
    },
    {
        "dependency_id": "REV3_ARC3_SPEC",
        "path": (
            "docs/strategy/"
            "ARC3_HDS蒸留先行_汎用自律完遂主体_実装仕様書_rev3.md"
        ),
        "required": True,
        "role": "ARC3_REV3_SPECIFICATION",
        "sha256": (
            "feea0ac2319e0776b8c34101379608a69ac6e59aefbf4f8943ee453a660ff29f"
        ),
        "size_bytes": 23083,
    },
)

EXPECTED_TRANSLATOR: Final[dict[str, JsonValue]] = {
    "capability_boundary": "DETERMINISTIC_HDS_TRANSLATION_REFERENCE_ONLY",
    "commit": "b501cc77c94048421af8efdb2e866c22b06f7208",
    "dependency_id": "HDS_BLACK_BOX_TRANSLATOR",
    "readme_git_blob": "7f6f9f4b1e2a25a07e25688b5cde24a96bfd2335",
    "readme_path": "README.md",
    "readme_sha256": (
        "a49d75aadce49fcd95576abf06106c03286b8ce38e010e4205cc5e0fc0708e99"
    ),
    "repository": "gatchimuchio/HDS-BlackBox-Translator",
    "required": True,
    "tree": "de5e9e5907efd2d32d22c41d1ef9215867ce9ce5",
}

MANIFEST_KEYS: Final = frozenset(
    {
        "authority",
        "authority_defined",
        "content_digest",
        "digest_excluded_fields",
        "domain",
        "gates",
        "hash_algorithm",
        "hds_dependency_match",
        "local_dependencies",
        "manifest_id",
        "manifest_version",
        "phase_id",
        "repository_relative_posix_paths",
        "schema_version",
        "source_profile",
        "unresolved_dependency_count",
        "upstream_dependencies",
    }
)
LOCAL_DEPENDENCY_KEYS: Final = frozenset(
    {"dependency_id", "path", "required", "role", "sha256", "size_bytes"}
)
UPSTREAM_DEPENDENCY_KEYS: Final = frozenset(EXPECTED_TRANSLATOR)
AUTHORITY_KEYS: Final = frozenset(
    {
        "authority_order_path",
        "authority_order_sha256",
        "final_selector",
        "owner_approval_artifact_digest",
        "owner_approval_path",
        "owner_approval_sha256",
        "promotion_authority",
    }
)
OPEN_TERM_LEDGER_KEYS: Final = frozenset(
    {
        "content_digest",
        "digest_excluded_fields",
        "ledger_id",
        "open_term_count",
        "open_terms",
        "phase_id",
        "record_schema_path",
        "schema_version",
        "unresolved_dependency_count",
    }
)


@dataclass(frozen=True, slots=True)
class AuditFailure(Exception):
    """A stable fail-closed finding."""

    code: str
    detail: str

    def __str__(self) -> str:
        return f"{self.code}:{self.detail}"


def _fail(code: str, detail: str) -> NoReturn:
    raise AuditFailure(code=code, detail=detail)


def _reject_constant(value: str) -> NoReturn:
    _fail("DG00_NONFINITE_JSON", value)


def _object_pairs(pairs: list[tuple[str, JsonValue]]) -> dict[str, JsonValue]:
    result: dict[str, JsonValue] = {}
    for key, value in pairs:
        if key in result:
            _fail("DG00_DUPLICATE_JSON_KEY", key)
        result[key] = value
    return result


def load_json_object(path: Path) -> dict[str, JsonValue]:
    """Load a JSON object while rejecting duplicates and non-finite values."""

    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            parse_constant=_reject_constant,
            object_pairs_hook=_object_pairs,
        )
    except UnicodeDecodeError as exc:
        _fail("DG00_JSON_NOT_UTF8", f"{path}:{exc}")
    except json.JSONDecodeError as exc:
        _fail("DG00_JSON_INVALID", f"{path}:{exc}")
    if not isinstance(value, dict):
        _fail("DG00_JSON_OBJECT_REQUIRED", str(path))
    return value


def _normalize(value: JsonValue, context: str = "$") -> JsonValue:
    if value is None or isinstance(value, bool):
        return value
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        _fail("DG00_FLOAT_FORBIDDEN", context)
    if isinstance(value, str):
        return unicodedata.normalize("NFC", value)
    if isinstance(value, list):
        return [
            _normalize(item, f"{context}[{index}]")
            for index, item in enumerate(value)
        ]
    if isinstance(value, dict):
        normalized: dict[str, JsonValue] = {}
        for raw_key, item in value.items():
            key = unicodedata.normalize("NFC", raw_key)
            if key in normalized:
                _fail("DG00_NFC_KEY_COLLISION", f"{context}.{key}")
            normalized[key] = _normalize(item, f"{context}.{key}")
        return {key: normalized[key] for key in sorted(normalized)}
    _fail("DG00_UNSUPPORTED_JSON_TYPE", f"{context}:{type(value).__name__}")


def canonical_json(value: JsonValue) -> str:
    normalized = _normalize(value)
    return json.dumps(
        normalized,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_file(path: Path) -> str:
    try:
        return sha256_bytes(path.read_bytes())
    except OSError as exc:
        _fail("DG00_REQUIRED_FILE_UNREADABLE", f"{path}:{exc}")


def artifact_content_digest(
    payload: Mapping[str, JsonValue],
    *,
    namespace: str,
    expected_excluded_fields: tuple[str, ...],
) -> str:
    excluded = payload.get("digest_excluded_fields")
    if excluded != list(expected_excluded_fields):
        _fail(
            "DG00_DIGEST_EXCLUSION_MISMATCH",
            f"expected={expected_excluded_fields!r}:actual={excluded!r}",
        )
    body = dict(payload)
    for field in expected_excluded_fields:
        body.pop(field, None)
    return f"{namespace}:{sha256_bytes(canonical_json(body).encode('utf-8'))}"


def _require_exact_keys(
    value: Mapping[str, JsonValue],
    expected: frozenset[str],
    context: str,
) -> None:
    actual = frozenset(value)
    unknown = sorted(actual - expected)
    missing = sorted(expected - actual)
    if unknown:
        _fail("DG00_UNKNOWN_FIELD", f"{context}:{','.join(unknown)}")
    if missing:
        _fail("DG00_MISSING_FIELD", f"{context}:{','.join(missing)}")


def _require_object(value: JsonValue, context: str) -> dict[str, JsonValue]:
    if not isinstance(value, dict):
        _fail("DG00_OBJECT_REQUIRED", context)
    return value


def _require_list(value: JsonValue, context: str) -> list[JsonValue]:
    if not isinstance(value, list):
        _fail("DG00_ARRAY_REQUIRED", context)
    return value


def _require_string(value: JsonValue, context: str) -> str:
    if not isinstance(value, str):
        _fail("DG00_STRING_REQUIRED", context)
    if value != unicodedata.normalize("NFC", value):
        _fail("DG00_STRING_NOT_NFC", context)
    return value


def _require_int(value: JsonValue, context: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail("DG00_INTEGER_REQUIRED", context)
    return value


def _require_bool(value: JsonValue, context: str) -> bool:
    if not isinstance(value, bool):
        _fail("DG00_BOOLEAN_REQUIRED", context)
    return value


def _require_hex(value: JsonValue, length: int, context: str) -> str:
    text = _require_string(value, context)
    if len(text) != length:
        _fail("DG00_HEX_LENGTH", context)
    try:
        int(text, 16)
    except ValueError:
        _fail("DG00_HEX_INVALID", context)
    if text != text.lower():
        _fail("DG00_HEX_NOT_LOWERCASE", context)
    return text


def _require_repo_path(value: JsonValue, context: str) -> str:
    text = _require_string(value, context)
    path = PurePosixPath(text)
    if (
        not text
        or text.startswith("/")
        or "\\" in text
        or path.is_absolute()
        or ".." in path.parts
        or "." in path.parts
    ):
        _fail("DG00_REPOSITORY_PATH_INVALID", f"{context}:{text}")
    return text


def _require_canonical_file(path: Path, payload: JsonValue) -> None:
    expected = canonical_json(payload) + "\n"
    try:
        actual = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        _fail("DG00_CANONICAL_FILE_UNREADABLE", f"{path}:{exc}")
    if actual != expected:
        _fail("DG00_PHYSICAL_CANONICAL_JSON_MISMATCH", str(path))


def _validate_schema_file(
    root: Path,
    relative_path: str,
    required_instance_fields: frozenset[str],
) -> None:
    path = root / relative_path
    schema = load_json_object(path)
    if schema.get("$schema") != "https://json-schema.org/draft/2020-12/schema":
        _fail("DG00_SCHEMA_DRAFT_MISMATCH", relative_path)
    if schema.get("additionalProperties") is not False:
        _fail("DG00_SCHEMA_UNKNOWN_FIELDS_NOT_FORBIDDEN", relative_path)
    required = schema.get("required")
    if not isinstance(required, list):
        _fail("DG00_SCHEMA_REQUIRED_ARRAY_MISSING", relative_path)
    if not required_instance_fields.issubset(
        {item for item in required if isinstance(item, str)}
    ):
        _fail("DG00_SCHEMA_REQUIRED_FIELDS_MISSING", relative_path)


def _validate_owner_approval(root: Path, authority: Mapping[str, JsonValue]) -> None:
    approval_path = _require_repo_path(
        authority["owner_approval_path"], "authority.owner_approval_path"
    )
    if approval_path != OWNER_APPROVAL_RELATIVE_PATH:
        _fail("DG14_OWNER_APPROVAL_PATH_MISMATCH", approval_path)
    expected_sha = _require_hex(
        authority["owner_approval_sha256"],
        64,
        "authority.owner_approval_sha256",
    )
    if expected_sha != EXPECTED_OWNER_APPROVAL_SHA256:
        _fail("DG14_OWNER_APPROVAL_LOCK_MISMATCH", expected_sha)
    actual_sha = sha256_file(root / approval_path)
    if actual_sha != expected_sha:
        _fail("DG14_OWNER_APPROVAL_FILE_MISMATCH", actual_sha)

    approval = load_json_object(root / approval_path)
    excluded = approval.get("digest_excluded_fields")
    if excluded != ["approval_artifact_digest", "approved_at"]:
        _fail("DG14_OWNER_APPROVAL_DIGEST_POLICY_MISMATCH", repr(excluded))
    approval_body = dict(approval)
    approval_body.pop("approval_artifact_digest", None)
    approval_body.pop("approved_at", None)
    computed = (
        "owner-approval-record:"
        + sha256_bytes(canonical_json(approval_body).encode("utf-8"))
    )
    claimed = authority["owner_approval_artifact_digest"]
    if claimed != EXPECTED_OWNER_APPROVAL_DIGEST or claimed != computed:
        _fail("DG14_OWNER_APPROVAL_DIGEST_MISMATCH", str(claimed))
    if approval.get("authority") != "大平鉄兵":
        _fail("DG14_OWNER_IDENTITY_MISMATCH", repr(approval.get("authority")))
    if approval.get("next_state") != "OWNER_APPROVED_PASS":
        _fail("DG14_OWNER_DECISION_NOT_APPROVED", repr(approval.get("next_state")))


def _validate_authority(
    root: Path, manifest: Mapping[str, JsonValue]
) -> None:
    authority = _require_object(manifest["authority"], "authority")
    _require_exact_keys(authority, AUTHORITY_KEYS, "authority")
    if _require_bool(manifest["authority_defined"], "authority_defined") is not True:
        _fail("DG14_AUTHORITY_NOT_DEFINED", "authority_defined")
    if authority["final_selector"] != "大平鉄兵":
        _fail("DG14_FINAL_SELECTOR_MISMATCH", repr(authority["final_selector"]))
    if authority["promotion_authority"] != "OWNER_ONLY":
        _fail(
            "DG14_PROMOTION_AUTHORITY_MISMATCH",
            repr(authority["promotion_authority"]),
        )

    authority_path = _require_repo_path(
        authority["authority_order_path"],
        "authority.authority_order_path",
    )
    if authority_path != AUTHORITY_ORDER_RELATIVE_PATH:
        _fail("DG14_AUTHORITY_ORDER_PATH_MISMATCH", authority_path)
    expected_sha = _require_hex(
        authority["authority_order_sha256"],
        64,
        "authority.authority_order_sha256",
    )
    if expected_sha != EXPECTED_AUTHORITY_ORDER_SHA256:
        _fail("DG14_AUTHORITY_ORDER_LOCK_MISMATCH", expected_sha)
    actual_sha = sha256_file(root / authority_path)
    if actual_sha != expected_sha:
        _fail("DG14_AUTHORITY_ORDER_FILE_MISMATCH", actual_sha)
    _validate_owner_approval(root, authority)


def _validate_local_dependencies(
    root: Path, manifest: Mapping[str, JsonValue]
) -> None:
    dependencies = _require_list(
        manifest["local_dependencies"], "local_dependencies"
    )
    if len(dependencies) != len(EXPECTED_LOCAL_DEPENDENCIES):
        _fail(
            "DG00_LOCAL_DEPENDENCY_COUNT_MISMATCH",
            f"{len(dependencies)}",
        )
    expected_paths: list[str] = []
    actual_ids: list[str] = []
    for index, (raw, expected) in enumerate(
        zip(dependencies, EXPECTED_LOCAL_DEPENDENCIES, strict=True)
    ):
        item = _require_object(raw, f"local_dependencies[{index}]")
        _require_exact_keys(
            item, LOCAL_DEPENDENCY_KEYS, f"local_dependencies[{index}]"
        )
        dependency_id = _require_string(
            item["dependency_id"], f"local_dependencies[{index}].dependency_id"
        )
        actual_ids.append(dependency_id)
        path_text = _require_repo_path(
            item["path"], f"local_dependencies[{index}].path"
        )
        expected_paths.append(path_text)
        _require_bool(
            item["required"], f"local_dependencies[{index}].required"
        )
        _require_string(item["role"], f"local_dependencies[{index}].role")
        locked_sha = _require_hex(
            item["sha256"], 64, f"local_dependencies[{index}].sha256"
        )
        locked_size = _require_int(
            item["size_bytes"], f"local_dependencies[{index}].size_bytes"
        )
        if item != expected:
            _fail(
                "DG00_LOCAL_DEPENDENCY_LOCK_MISMATCH",
                dependency_id,
            )
        path = root / path_text
        actual_sha = sha256_file(path)
        if actual_sha != locked_sha:
            _fail("DG00_LOCAL_DEPENDENCY_SHA256_MISMATCH", dependency_id)
        try:
            actual_size = path.stat().st_size
        except OSError as exc:
            _fail("DG00_REQUIRED_FILE_UNREADABLE", f"{path}:{exc}")
        if actual_size != locked_size:
            _fail("DG00_LOCAL_DEPENDENCY_SIZE_MISMATCH", dependency_id)

    if actual_ids != sorted(actual_ids):
        _fail("DG00_LOCAL_DEPENDENCIES_NOT_SORTED", repr(actual_ids))
    manifest_paths = _require_list(
        manifest["repository_relative_posix_paths"],
        "repository_relative_posix_paths",
    )
    normalized_manifest_paths = [
        _require_repo_path(
            value, f"repository_relative_posix_paths[{index}]"
        )
        for index, value in enumerate(manifest_paths)
    ]
    if normalized_manifest_paths != sorted(expected_paths):
        _fail(
            "DG00_REPOSITORY_PATH_INDEX_MISMATCH",
            repr(normalized_manifest_paths),
        )


def _validate_upstream_dependencies(
    manifest: Mapping[str, JsonValue],
) -> None:
    dependencies = _require_list(
        manifest["upstream_dependencies"], "upstream_dependencies"
    )
    if len(dependencies) != 1:
        _fail("DG00_UPSTREAM_DEPENDENCY_COUNT_MISMATCH", f"{len(dependencies)}")
    item = _require_object(dependencies[0], "upstream_dependencies[0]")
    _require_exact_keys(item, UPSTREAM_DEPENDENCY_KEYS, "upstream_dependencies[0]")
    _require_hex(item["commit"], 40, "upstream_dependencies[0].commit")
    _require_hex(item["tree"], 40, "upstream_dependencies[0].tree")
    _require_hex(
        item["readme_git_blob"],
        40,
        "upstream_dependencies[0].readme_git_blob",
    )
    _require_hex(
        item["readme_sha256"],
        64,
        "upstream_dependencies[0].readme_sha256",
    )
    _require_repo_path(
        item["readme_path"], "upstream_dependencies[0].readme_path"
    )
    _require_bool(item["required"], "upstream_dependencies[0].required")
    if item != EXPECTED_TRANSLATOR:
        _fail("DG00_TRANSLATOR_LOCK_MISMATCH", repr(item))


def _validate_manifest(root: Path, path: Path) -> dict[str, JsonValue]:
    manifest = load_json_object(path)
    _require_exact_keys(manifest, MANIFEST_KEYS, "manifest")
    _require_canonical_file(path, manifest)
    if manifest["schema_version"] != MANIFEST_SCHEMA_VERSION:
        _fail("DG00_MANIFEST_SCHEMA_VERSION_MISMATCH", repr(manifest["schema_version"]))
    if manifest["phase_id"] != PHASE_ID:
        _fail("DG00_PHASE_ID_MISMATCH", repr(manifest["phase_id"]))
    expected_constants: tuple[tuple[str, JsonValue], ...] = (
        ("manifest_id", "HDS-DEPENDENCIES-PH-D00A-V1"),
        ("manifest_version", "1.0.0"),
        ("source_profile", "HDS_CANONICAL_AUTHORITY_LOCK"),
        ("domain", "HDS_AUTHORITY_DEPENDENCIES"),
        ("hash_algorithm", "sha256"),
        ("gates", ["DG-00", "DG-14"]),
        ("hds_dependency_match", True),
        ("authority_defined", True),
        ("unresolved_dependency_count", 0),
    )
    for key, expected in expected_constants:
        if manifest[key] != expected:
            _fail("DG00_MANIFEST_CONSTANT_MISMATCH", f"{key}:{manifest[key]!r}")
    _require_bool(manifest["hds_dependency_match"], "hds_dependency_match")
    _require_bool(manifest["authority_defined"], "authority_defined")
    _require_int(
        manifest["unresolved_dependency_count"],
        "unresolved_dependency_count",
    )
    computed = artifact_content_digest(
        manifest,
        namespace="hds-dependency-lock",
        expected_excluded_fields=("content_digest", "manifest_id"),
    )
    if manifest["content_digest"] != computed:
        _fail(
            "DG00_MANIFEST_CONTENT_DIGEST_MISMATCH",
            f"claimed={manifest['content_digest']}:computed={computed}",
        )
    _validate_local_dependencies(root, manifest)
    _validate_upstream_dependencies(manifest)
    _validate_authority(root, manifest)
    return manifest


def _validate_open_term_ledger(root: Path, path: Path) -> dict[str, JsonValue]:
    ledger = load_json_object(path)
    _require_exact_keys(ledger, OPEN_TERM_LEDGER_KEYS, "open_term_ledger")
    _require_canonical_file(path, ledger)
    if ledger["schema_version"] != OPEN_TERM_LEDGER_SCHEMA_VERSION:
        _fail(
            "DG00_OPEN_TERM_LEDGER_SCHEMA_MISMATCH",
            repr(ledger["schema_version"]),
        )
    expected_constants: tuple[tuple[str, JsonValue], ...] = (
        ("ledger_id", "OPEN-TERM-LEDGER-PH-D00A-V1"),
        ("phase_id", PHASE_ID),
        ("record_schema_path", OPEN_TERM_SCHEMA_RELATIVE_PATH),
        ("open_terms", []),
        ("open_term_count", 0),
        ("unresolved_dependency_count", 0),
    )
    for key, expected in expected_constants:
        if ledger[key] != expected:
            _fail("DG01_OPEN_TERM_LEDGER_NOT_EMPTY", f"{key}:{ledger[key]!r}")
    _require_int(ledger["open_term_count"], "open_term_count")
    _require_int(
        ledger["unresolved_dependency_count"],
        "open_term_ledger.unresolved_dependency_count",
    )
    computed = artifact_content_digest(
        ledger,
        namespace="hds-open-term-ledger",
        expected_excluded_fields=("content_digest", "ledger_id"),
    )
    if ledger["content_digest"] != computed:
        _fail("DG00_OPEN_TERM_LEDGER_DIGEST_MISMATCH", str(ledger["content_digest"]))
    return ledger


def _git_output(git_dir: Path, arguments: Sequence[str]) -> bytes:
    try:
        return subprocess.run(
            ["git", f"--git-dir={git_dir}", *arguments],
            check=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        ).stdout
    except (OSError, subprocess.CalledProcessError) as exc:
        _fail("DG00_TRANSLATOR_GIT_OBJECT_UNAVAILABLE", str(exc))


def validate_translator_git_objects(git_dir: Path) -> None:
    """Optionally prove the frozen Translator metadata against Git objects."""

    if not git_dir.is_dir():
        _fail("DG00_TRANSLATOR_GIT_DIR_MISSING", str(git_dir))
    commit = str(EXPECTED_TRANSLATOR["commit"])
    tree = _git_output(git_dir, ["rev-parse", f"{commit}^{{tree}}"])
    if tree.decode("ascii").strip() != EXPECTED_TRANSLATOR["tree"]:
        _fail("DG00_TRANSLATOR_TREE_MISMATCH", tree.decode("ascii").strip())
    listing = _git_output(
        git_dir,
        ["ls-tree", commit, str(EXPECTED_TRANSLATOR["readme_path"])],
    ).decode("utf-8")
    fields = listing.strip().split()
    if len(fields) < 3 or fields[2] != EXPECTED_TRANSLATOR["readme_git_blob"]:
        _fail("DG00_TRANSLATOR_README_BLOB_MISMATCH", listing.strip())
    readme = _git_output(
        git_dir,
        ["show", f"{commit}:{EXPECTED_TRANSLATOR['readme_path']}"],
    )
    if sha256_bytes(readme) != EXPECTED_TRANSLATOR["readme_sha256"]:
        _fail("DG00_TRANSLATOR_README_SHA256_MISMATCH", sha256_bytes(readme))


def _build_report(
    *,
    manifest_path: Path,
    manifest: Mapping[str, JsonValue],
    ledger: Mapping[str, JsonValue],
) -> dict[str, JsonValue]:
    checks: list[JsonValue] = [
        {
            "check_id": "D00A-AUTHORITY-ORDER",
            "gate_id": "DG-14",
            "status": "PASS",
        },
        {
            "check_id": "D00A-CANONICAL-SERIALIZATION",
            "gate_id": "DG-00",
            "status": "PASS",
        },
        {
            "check_id": "D00A-LOCAL-HDS-CONTENT",
            "gate_id": "DG-00",
            "status": "PASS",
        },
        {
            "check_id": "D00A-OPEN-TERM-LEDGER",
            "gate_id": "DG-00",
            "status": "PASS",
        },
        {
            "check_id": "D00A-SCHEMA-STRICTNESS",
            "gate_id": "DG-00",
            "status": "PASS",
        },
        {
            "check_id": "D00A-TRANSLATOR-LOCK",
            "gate_id": "DG-00",
            "status": "PASS",
        },
    ]
    report: dict[str, JsonValue] = {
        "authority_defined": True,
        "checks": checks,
        "dependency_manifest_content_digest": manifest["content_digest"],
        "dependency_manifest_path": MANIFEST_RELATIVE_PATH,
        "dependency_manifest_sha256": sha256_file(manifest_path),
        "digest_excluded_fields": ["content_digest", "report_id"],
        "gates": ["DG-00", "DG-14"],
        "hds_dependency_match": True,
        "mismatch_count": 0,
        "open_term_count": ledger["open_term_count"],
        "phase_id": PHASE_ID,
        "report_id": "DEPENDENCY-AUDIT-PH-D00A-V1",
        "schema_version": REPORT_SCHEMA_VERSION,
        "translator_commit": EXPECTED_TRANSLATOR["commit"],
        "translator_tree": EXPECTED_TRANSLATOR["tree"],
        "unresolved_dependency_count": ledger["unresolved_dependency_count"],
    }
    report["content_digest"] = artifact_content_digest(
        report,
        namespace="hds-dependency-audit-report",
        expected_excluded_fields=("content_digest", "report_id"),
    )
    return report


def audit_repository(
    root: Path,
    *,
    manifest_path: Path | None = None,
    authority_order_path: Path | None = None,
    open_term_ledger_path: Path | None = None,
    translator_git_dir: Path | None = None,
) -> dict[str, JsonValue]:
    """Run the complete offline PH-D00A audit and return its canonical report."""

    resolved_root = root.resolve()
    resolved_manifest = (
        manifest_path
        if manifest_path is not None
        else resolved_root / MANIFEST_RELATIVE_PATH
    )
    resolved_authority = (
        authority_order_path
        if authority_order_path is not None
        else resolved_root / AUTHORITY_ORDER_RELATIVE_PATH
    )
    resolved_ledger = (
        open_term_ledger_path
        if open_term_ledger_path is not None
        else resolved_root / OPEN_TERM_LEDGER_RELATIVE_PATH
    )
    if resolved_authority.resolve() != (
        resolved_root / AUTHORITY_ORDER_RELATIVE_PATH
    ).resolve():
        _fail("DG14_AUTHORITY_ORDER_OVERRIDE_FORBIDDEN", str(resolved_authority))

    _validate_schema_file(
        resolved_root,
        DEPENDENCY_SCHEMA_RELATIVE_PATH,
        frozenset({"schema_version", "content_digest"}),
    )
    _validate_schema_file(
        resolved_root,
        OPEN_TERM_SCHEMA_RELATIVE_PATH,
        frozenset({"schema_version", "content_digest"}),
    )
    manifest = _validate_manifest(resolved_root, resolved_manifest)
    ledger = _validate_open_term_ledger(resolved_root, resolved_ledger)
    if translator_git_dir is not None:
        validate_translator_git_objects(translator_git_dir.resolve())
    return _build_report(
        manifest_path=resolved_manifest,
        manifest=manifest,
        ledger=ledger,
    )


def _verify_report(path: Path, expected: Mapping[str, JsonValue]) -> None:
    actual = load_json_object(path)
    _require_canonical_file(path, actual)
    computed = artifact_content_digest(
        actual,
        namespace="hds-dependency-audit-report",
        expected_excluded_fields=("content_digest", "report_id"),
    )
    if actual.get("content_digest") != computed:
        _fail("DG00_AUDIT_REPORT_DIGEST_MISMATCH", str(actual.get("content_digest")))
    if actual != expected:
        _fail("DG00_AUDIT_REPORT_CONTENT_MISMATCH", str(path))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--root",
        type=Path,
        default=Path(__file__).resolve().parents[1],
        help="repository root (default: script parent)",
    )
    parser.add_argument("--manifest", type=Path)
    parser.add_argument("--open-term-ledger", type=Path)
    parser.add_argument("--translator-git-dir", type=Path)
    parser.add_argument("--verify-report", type=Path)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.verify_report is not None and args.output is not None:
        print(
            "DEPENDENCY_LOCK_FAIL:DG00_CONFLICTING_OUTPUT_OPTIONS",
            file=sys.stderr,
        )
        return 2
    try:
        report = audit_repository(
            args.root,
            manifest_path=args.manifest,
            open_term_ledger_path=args.open_term_ledger,
            translator_git_dir=args.translator_git_dir,
        )
        if args.verify_report is not None:
            _verify_report(args.verify_report, report)
            print(f"DEPENDENCY_LOCK_PASS:{report['content_digest']}")
        elif args.output is not None:
            args.output.write_text(
                canonical_json(report) + "\n",
                encoding="utf-8",
                newline="\n",
            )
            print(f"DEPENDENCY_LOCK_PASS:{report['content_digest']}")
        else:
            print(canonical_json(report))
    except AuditFailure as exc:
        print(f"DEPENDENCY_LOCK_FAIL:{exc}", file=sys.stderr)
        return 2
    except OSError as exc:
        print(
            f"DEPENDENCY_LOCK_FAIL:DG00_IO_FAILURE:{exc}",
            file=sys.stderr,
        )
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
