"""Deterministic PH-D01A source and contamination inventory.

This module reads profile and locator metadata only. It never imports,
executes, replays, or semantically parses an ARC source payload. Content,
acquisition, environment, and Merkle freezing belong to PH-D01B.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from collections import Counter
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Final, cast

type JsonScalar = None | bool | int | float | str
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]

PHASE_ID: Final = "PH-D01A"
PROFILE_SCHEMA_VERSION: Final = "hds-distillation-source-profile-v1"
PLAN_SCHEMA_VERSION: Final = "hds-distillation-source-inventory-plan-v1"
REPORT_SCHEMA_VERSION: Final = "hds-distillation-source-inventory-report-v1"
REPORT_ID: Final = "HDS-DISTILLATION-SOURCE-INVENTORY-PH-D01A-V1"
PROVENANCE_REPORT_SCHEMA_VERSION: Final = (
    "hds-distillation-primary-source-provenance-v1"
)
PROVENANCE_REPORT_ID: Final = (
    "HDS-DISTILLATION-PRIMARY-SOURCE-PROVENANCE-PH-D01A-V1"
)

PROFILE_DIGEST_NAMESPACE: Final = "hds-source-profile"
PLAN_DIGEST_NAMESPACE: Final = "hds-source-inventory-plan"
PREINVENTORY_DIGEST_NAMESPACE: Final = (
    "rev3-ph-d01a-source-preinventory"
)
REPORT_DIGEST_NAMESPACE: Final = "hds-source-inventory-report"
REPORT_DIGEST_EXCLUDED_FIELDS: Final = ("content_digest", "report_id")
PROVENANCE_REPORT_DIGEST_NAMESPACE: Final = (
    "hds-primary-source-provenance-report"
)
PROVENANCE_REPORT_DIGEST_EXCLUDED_FIELDS: Final = (
    "content_digest",
    "report_id",
)

PROFILE_TYPES: Final = frozenset(
    {
        "ARC2_KAGGLE_CHALLENGE_SOLUTION",
        "ARC2_OFFICIAL_TASK_JSON",
        "ARC2_INTERNAL_NORMALIZED_CORPUS",
        "ARC3_ENVIRONMENT_SOURCE_BUNDLE",
        "ARC3_RAW_TEACHER_RECORDING",
        "ARC3_CANONICAL_TEACHER_TRAJECTORY",
    }
)
SPLIT_ROLES: Final = frozenset(
    {
        "TRAIN_TEACHER",
        "PUBLIC_EVALUATION_TEACHER",
        "PUBLIC_EVALUATION_CONSUMED",
        "UNLABELED_TEST",
        "REPLAY_ONLY_SOURCE",
        "SEALED_AUDIT",
    }
)
ANSWER_VISIBILITIES: Final = frozenset(
    {
        "CHALLENGE_ONLY",
        "ANSWER_VISIBLE",
        "ANSWER_UNAVAILABLE",
        "SUCCESS_TRAJECTORY_VISIBLE",
        "ENVIRONMENT_SOURCE_AND_HIDDEN_STATE_VISIBLE",
    }
)
DEVELOPMENT_USAGES: Final = frozenset(
    {
        "DISTILLATION_SOURCE",
        "AVAILABLE_TEACHER_NOT_CONSUMED",
        "REPLAY_HARNESS_ONLY",
        "SEALED_AUDIT_ONLY",
    }
)
CONTAMINATION_CLASSES: Final = frozenset(
    {
        "NONE",
        "PUBLIC_EVALUATION_INPUT_VISIBLE",
        "PUBLIC_EVALUATION_ANSWER_VISIBLE_NOT_CONSUMED",
        "PUBLIC_EVALUATION_SUCCESS_TRAJECTORY_CONSUMED",
        "UNLABELED_TEST_NO_ANSWER",
        "PRIVILEGED_ENVIRONMENT_IMPLEMENTATION",
    }
)
MATERIALIZATION_STATES: Final = frozenset(
    {
        "REPOSITORY_TRACKED",
        "EXTERNAL_ARCHIVE_VERIFIED",
        "REFERENCED_NOT_LOCALLY_MATERIALIZED",
    }
)
SOURCE_CODE_ACCESS_STATES: Final = frozenset(
    {"NOT_SOURCE_CODE", "REPLAY_HARNESS_ONLY"}
)
SELECTOR_KINDS: Final = frozenset(
    {
        "REPOSITORY_TREE",
        "REPOSITORY_FILES",
        "ARCHIVE_MEMBERS",
        "EXTERNAL_DATASET_MANIFEST_ROWS",
    }
)

PROFILE_FIELDS: Final = frozenset(
    {
        "schema_version",
        "profile_id",
        "profile_type",
        "domain",
        "distribution_format",
        "split_role",
        "answer_visibility",
        "development_usage",
        "contamination_class",
        "materialization_state",
        "source_code_access",
        "policy_weight_source",
        "selectors",
        "digest_excluded_fields",
        "content_digest",
    }
)
PLAN_FIELDS: Final = frozenset(
    {
        "schema_version",
        "phase_id",
        "preinventory_path",
        "preinventory_digest",
        "profile_paths",
        "repository_candidate_roots",
        "repository_admitted_paths",
        "arc2_distribution",
        "arc3_distribution",
        "raw_recording_source",
        "non_source_policy",
        "expected_accounting",
        "source_payload_access",
        "digest_excluded_fields",
        "content_digest",
    }
)
ARC2_DISTRIBUTION_FIELDS: Final = frozenset(
    {
        "distribution_id",
        "expected_sha256",
        "expected_member_count",
        "expected_member_path_set_sha256",
        "admitted_members",
        "excluded_members",
    }
)
ARC3_DISTRIBUTION_FIELDS: Final = frozenset(
    {
        "distribution_id",
        "expected_sha256",
        "expected_member_count",
        "expected_member_path_set_sha256",
        "environment_alias_prefix",
        "environment_alias_count",
        "agent_scaffold_non_source_count",
        "runtime_wheel_non_source_count",
    }
)
RAW_RECORDING_SOURCE_FIELDS: Final = frozenset(
    {
        "source_manifest_path",
        "dataset_id",
        "dataset_repo_sha",
        "expected_selected_count",
        "expected_level_count",
        "expected_filename_set_sha256",
    }
)
NON_SOURCE_POLICY_FIELDS: Final = frozenset(
    {
        "historical_policy_bundle_root",
        "historical_policy_bundle_file_count",
        "teacher_policy_or_report_file_count",
        "policy_weight_admitted_source_count",
    }
)
RAW_RECORDING_MANIFEST_FIELDS: Final = frozenset(
    {
        "config",
        "dataset_id",
        "dataset_repo_sha",
        "dataset_row_count",
        "development_only",
        "pinned_trajectory_sha256_by_game",
        "rows",
        "runtime_use",
        "schema_version",
        "selected_expected_actions",
        "selected_game_count",
        "selected_level_count",
        "selection",
        "split",
    }
)
RAW_RECORDING_ROW_FIELDS: Final = frozenset(
    {
        "expected_actions",
        "game_id",
        "recording_file",
        "row_index",
        "target_levels",
    }
)
CANONICAL_CORPUS_PATHS: Final = (
    "analysis/teacher/FULL_SOLUTION_CORPUS.json",
    "analysis/teacher/S5_RENDERED_POLICY_TRAINING_CORPUS.json",
    "analysis/teacher/S5_RENDERED_POLICY_TRAINING_CORPUS.npz",
)
FORBIDDEN_PRIMARY_SOURCE_REPOSITORY_PREFIXES: Final = (
    "analysis/rev3/",
    "artifacts/reports/",
    "control/",
    "distillation/artifacts/",
    "distillation/profiles/",
)

_SHA256_RE: Final = re.compile(r"^[0-9a-f]{64}$")
_GIT_SHA_RE: Final = re.compile(r"^[0-9a-f]{40}$")
_PROFILE_ID_RE: Final = re.compile(r"^[a-z0-9][a-z0-9-]*$")
_GAME_ID_RE: Final = re.compile(r"^[a-z0-9]{4}-[0-9a-f]{8}$")
_RECORDING_FILE_RE: Final = re.compile(
    r"^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-"
    r"[0-9a-f]{4}-[0-9a-f]{12}\.recording$"
)


class SourceInventoryError(ValueError):
    """A stable fail-closed PH-D01A inventory error."""


def canonical_json(value: JsonValue) -> str:
    """Return deterministic UTF-8 JSON without a trailing newline."""

    return json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    )


def _digest(
    value: Mapping[str, JsonValue],
    namespace: str,
    *,
    excluded_fields: Sequence[str] = ("content_digest",),
) -> str:
    body = dict(value)
    for field in excluded_fields:
        body.pop(field, None)
    encoded = canonical_json(body).encode("utf-8")
    return namespace + ":" + hashlib.sha256(encoded).hexdigest()


def _path_set_digest(paths: Sequence[str]) -> str:
    encoded = canonical_json(cast(JsonValue, sorted(paths))).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _load_object(path: Path, code: str) -> JsonObject:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise SourceInventoryError(f"{code}_UNREADABLE:{path}") from exc
    if not isinstance(value, dict):
        raise SourceInventoryError(f"{code}_NOT_OBJECT:{path}")
    return cast(JsonObject, value)


def _object(value: JsonValue, code: str) -> JsonObject:
    if not isinstance(value, dict):
        raise SourceInventoryError(f"{code}_NOT_OBJECT")
    return value


def _list(value: JsonValue, code: str) -> list[JsonValue]:
    if not isinstance(value, list):
        raise SourceInventoryError(f"{code}_NOT_ARRAY")
    return value


def _string(value: JsonValue, code: str) -> str:
    if not isinstance(value, str) or not value:
        raise SourceInventoryError(f"{code}_NOT_NONEMPTY_STRING")
    return value


def _integer(value: JsonValue, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SourceInventoryError(f"{code}_NOT_INTEGER")
    return value


def _nonnegative_integer(value: JsonValue, code: str) -> int:
    item = _integer(value, code)
    if item < 0:
        raise SourceInventoryError(f"{code}_NEGATIVE")
    return item


def _positive_integer(value: JsonValue, code: str) -> int:
    item = _integer(value, code)
    if item <= 0:
        raise SourceInventoryError(f"{code}_NOT_POSITIVE")
    return item


def _string_list(value: JsonValue, code: str) -> list[str]:
    items = _list(value, code)
    result = [_string(item, code + "_ITEM") for item in items]
    if len(result) != len(set(result)):
        raise SourceInventoryError(f"{code}_DUPLICATE")
    return result


def _strict_fields(
    value: Mapping[str, JsonValue],
    expected: frozenset[str],
    code: str,
) -> None:
    actual = frozenset(value)
    missing = sorted(expected - actual)
    unknown = sorted(actual - expected)
    if missing:
        raise SourceInventoryError(
            f"{code}_MISSING_FIELDS:{','.join(missing)}"
        )
    if unknown:
        raise SourceInventoryError(
            f"{code}_UNKNOWN_FIELDS:{','.join(unknown)}"
        )


def _enum(
    value: JsonValue,
    allowed: frozenset[str],
    code: str,
) -> str:
    item = _string(value, code)
    if item not in allowed:
        raise SourceInventoryError(f"{code}_UNKNOWN:{item}")
    return item


def _sha256(value: JsonValue, code: str) -> str:
    item = _string(value, code)
    if _SHA256_RE.fullmatch(item) is None:
        raise SourceInventoryError(f"{code}_INVALID:{item}")
    return item


def _git_sha(value: JsonValue, code: str) -> str:
    item = _string(value, code)
    if _GIT_SHA_RE.fullmatch(item) is None:
        raise SourceInventoryError(f"{code}_INVALID:{item}")
    return item


def _repository_path(value: JsonValue, code: str) -> str:
    item = _string(value, code)
    if "\\" in item or item.startswith("/"):
        raise SourceInventoryError(f"{code}_NOT_RELATIVE_POSIX:{item}")
    canonical = PurePosixPath(item).as_posix()
    parts = PurePosixPath(item).parts
    if not parts or any(part in {"", ".", ".."} for part in parts):
        raise SourceInventoryError(f"{code}_ESCAPE:{item}")
    if canonical != item:
        raise SourceInventoryError(f"{code}_NOT_CANONICAL:{item}")
    return item


def _validate_bound_digest(
    value: Mapping[str, JsonValue],
    namespace: str,
    code: str,
) -> str:
    excluded = _string_list(
        value.get("digest_excluded_fields"),
        code + "_DIGEST_EXCLUDED_FIELDS",
    )
    if excluded != ["content_digest"]:
        raise SourceInventoryError(
            f"{code}_DIGEST_EXCLUSION_INVALID:{','.join(excluded)}"
        )
    claimed = _string(value.get("content_digest"), code + "_DIGEST")
    expected = _digest(value, namespace, excluded_fields=excluded)
    if claimed != expected:
        raise SourceInventoryError(
            f"{code}_DIGEST_MISMATCH:expected={expected}:actual={claimed}"
        )
    return claimed


def _git_paths(repository_root: Path, root: str) -> tuple[str, ...]:
    process = subprocess.run(
        ["git", "ls-files", "--", root],
        cwd=repository_root,
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    if process.returncode != 0:
        detail = process.stderr.strip().replace("\n", " ")
        raise SourceInventoryError(
            f"D01A_GIT_LS_FILES_FAILED:{root}:{detail}"
        )
    return tuple(sorted(line for line in process.stdout.splitlines() if line))


def _validate_plan(plan: JsonObject) -> str:
    _strict_fields(plan, PLAN_FIELDS, "D01A_PLAN")
    if plan["schema_version"] != PLAN_SCHEMA_VERSION:
        raise SourceInventoryError("D01A_PLAN_SCHEMA_VERSION_MISMATCH")
    if plan["phase_id"] != PHASE_ID:
        raise SourceInventoryError("D01A_PLAN_PHASE_MISMATCH")
    arc2 = _object(plan["arc2_distribution"], "D01A_PLAN_ARC2")
    _strict_fields(arc2, ARC2_DISTRIBUTION_FIELDS, "D01A_PLAN_ARC2")
    _string(arc2["distribution_id"], "D01A_PLAN_ARC2_DISTRIBUTION")
    _sha256(arc2["expected_sha256"], "D01A_PLAN_ARC2_SHA256")
    _positive_integer(
        arc2["expected_member_count"],
        "D01A_PLAN_ARC2_MEMBER_COUNT",
    )
    _sha256(
        arc2["expected_member_path_set_sha256"],
        "D01A_PLAN_ARC2_MEMBER_PATH_SET",
    )
    for path in _string_list(
        arc2["admitted_members"],
        "D01A_PLAN_ARC2_ADMITTED_MEMBERS",
    ):
        _repository_path(path, "D01A_PLAN_ARC2_ADMITTED_MEMBER")
    for raw_exclusion in _list(
        arc2["excluded_members"],
        "D01A_PLAN_ARC2_EXCLUDED_MEMBERS",
    ):
        exclusion = _object(
            raw_exclusion,
            "D01A_PLAN_ARC2_EXCLUDED_MEMBER",
        )
        _strict_fields(
            exclusion,
            frozenset({"path", "reason"}),
            "D01A_PLAN_ARC2_EXCLUDED_MEMBER",
        )
        _repository_path(
            exclusion["path"],
            "D01A_PLAN_ARC2_EXCLUDED_MEMBER_PATH",
        )
        _string(
            exclusion["reason"],
            "D01A_PLAN_ARC2_EXCLUDED_MEMBER_REASON",
        )

    arc3 = _object(plan["arc3_distribution"], "D01A_PLAN_ARC3")
    _strict_fields(arc3, ARC3_DISTRIBUTION_FIELDS, "D01A_PLAN_ARC3")
    _string(arc3["distribution_id"], "D01A_PLAN_ARC3_DISTRIBUTION")
    _sha256(arc3["expected_sha256"], "D01A_PLAN_ARC3_SHA256")
    _positive_integer(
        arc3["expected_member_count"],
        "D01A_PLAN_ARC3_MEMBER_COUNT",
    )
    _sha256(
        arc3["expected_member_path_set_sha256"],
        "D01A_PLAN_ARC3_MEMBER_PATH_SET",
    )
    alias_prefix = arc3["environment_alias_prefix"]
    if not isinstance(alias_prefix, str):
        raise SourceInventoryError(
            "D01A_PLAN_ARC3_ALIAS_PREFIX_NOT_STRING"
        )
    for field in (
        "environment_alias_count",
        "agent_scaffold_non_source_count",
        "runtime_wheel_non_source_count",
    ):
        _nonnegative_integer(arc3[field], "D01A_PLAN_ARC3_" + field.upper())

    raw_source = _object(
        plan["raw_recording_source"],
        "D01A_PLAN_RAW_SOURCE",
    )
    _strict_fields(
        raw_source,
        RAW_RECORDING_SOURCE_FIELDS,
        "D01A_PLAN_RAW_SOURCE",
    )
    _repository_path(
        raw_source["source_manifest_path"],
        "D01A_PLAN_RAW_SOURCE_MANIFEST_PATH",
    )
    _string(raw_source["dataset_id"], "D01A_PLAN_RAW_SOURCE_DATASET_ID")
    _git_sha(
        raw_source["dataset_repo_sha"],
        "D01A_PLAN_RAW_SOURCE_DATASET_REPO_SHA",
    )
    _positive_integer(
        raw_source["expected_selected_count"],
        "D01A_PLAN_RAW_SOURCE_SELECTED_COUNT",
    )
    _positive_integer(
        raw_source["expected_level_count"],
        "D01A_PLAN_RAW_SOURCE_LEVEL_COUNT",
    )
    _sha256(
        raw_source["expected_filename_set_sha256"],
        "D01A_PLAN_RAW_SOURCE_FILENAME_SET",
    )

    non_source = _object(
        plan["non_source_policy"],
        "D01A_PLAN_NON_SOURCE_POLICY",
    )
    _strict_fields(
        non_source,
        NON_SOURCE_POLICY_FIELDS,
        "D01A_PLAN_NON_SOURCE_POLICY",
    )
    _repository_path(
        non_source["historical_policy_bundle_root"],
        "D01A_PLAN_POLICY_BUNDLE_ROOT",
    )
    for field in (
        "historical_policy_bundle_file_count",
        "teacher_policy_or_report_file_count",
        "policy_weight_admitted_source_count",
    ):
        _nonnegative_integer(
            non_source[field],
            "D01A_PLAN_NON_SOURCE_" + field.upper(),
        )
    return _validate_bound_digest(
        plan,
        PLAN_DIGEST_NAMESPACE,
        "D01A_PLAN",
    )


def _validate_raw_recording_manifest(
    manifest: JsonObject,
    raw_source: JsonObject,
) -> list[JsonObject]:
    _strict_fields(
        manifest,
        RAW_RECORDING_MANIFEST_FIELDS,
        "D01A_RECORDING_MANIFEST",
    )
    if manifest["schema_version"] != (
        "arc3-teacher-human-replay-source-manifest-v1"
    ):
        raise SourceInventoryError(
            "D01A_RECORDING_MANIFEST_SCHEMA_VERSION_MISMATCH"
        )
    if manifest["dataset_id"] != raw_source["dataset_id"]:
        raise SourceInventoryError("D01A_DATASET_ID_MISMATCH")
    if manifest["dataset_repo_sha"] != raw_source["dataset_repo_sha"]:
        raise SourceInventoryError("D01A_DATASET_REPO_SHA_MISMATCH")
    if manifest["development_only"] is not True:
        raise SourceInventoryError(
            "D01A_RECORDING_MANIFEST_DEVELOPMENT_ONLY_REQUIRED"
        )
    if manifest["runtime_use"] != "FORBIDDEN":
        raise SourceInventoryError(
            "D01A_RECORDING_MANIFEST_RUNTIME_USE_NOT_FORBIDDEN"
        )
    if manifest["split"] != "train":
        raise SourceInventoryError("D01A_RECORDING_MANIFEST_SPLIT_INVALID")
    _string(manifest["config"], "D01A_RECORDING_MANIFEST_CONFIG")
    _string(manifest["selection"], "D01A_RECORDING_MANIFEST_SELECTION")

    dataset_row_count = _positive_integer(
        manifest["dataset_row_count"],
        "D01A_RECORDING_MANIFEST_DATASET_ROW_COUNT",
    )
    rows = [
        _object(row, "D01A_RECORDING_ROW")
        for row in _list(
            manifest["rows"],
            "D01A_RECORDING_MANIFEST_ROWS",
        )
    ]
    expected_selected_count = _positive_integer(
        raw_source["expected_selected_count"],
        "D01A_RAW_RECORDING_EXPECTED_COUNT",
    )
    if (
        len(rows) != expected_selected_count
        or _positive_integer(
            manifest["selected_game_count"],
            "D01A_RECORDING_MANIFEST_SELECTED_GAME_COUNT",
        )
        != expected_selected_count
    ):
        raise SourceInventoryError("D01A_RECORDING_COUNT_MISMATCH")

    game_references: list[str] = []
    recording_files: list[str] = []
    row_indices: list[int] = []
    selected_level_count = 0
    selected_expected_actions = 0
    for row in rows:
        _strict_fields(
            row,
            RAW_RECORDING_ROW_FIELDS,
            "D01A_RECORDING_ROW",
        )
        game_reference = _string(
            row["game_id"],
            "D01A_RECORDING_GAME_ID",
        )
        if _GAME_ID_RE.fullmatch(game_reference) is None:
            raise SourceInventoryError(
                f"D01A_RECORDING_GAME_ID_INVALID:{game_reference}"
            )
        recording_file = _repository_path(
            row["recording_file"],
            "D01A_RECORDING_FILENAME",
        )
        if _RECORDING_FILE_RE.fullmatch(recording_file) is None:
            raise SourceInventoryError(
                f"D01A_RECORDING_FILENAME_INVALID:{recording_file}"
            )
        row_index = _nonnegative_integer(
            row["row_index"],
            "D01A_RECORDING_ROW_INDEX",
        )
        if row_index >= dataset_row_count:
            raise SourceInventoryError(
                f"D01A_RECORDING_ROW_INDEX_OUT_OF_RANGE:{row_index}"
            )
        selected_level_count += _positive_integer(
            row["target_levels"],
            "D01A_RECORDING_TARGET_LEVELS",
        )
        selected_expected_actions += _positive_integer(
            row["expected_actions"],
            "D01A_RECORDING_EXPECTED_ACTIONS",
        )
        game_references.append(game_reference)
        recording_files.append(recording_file)
        row_indices.append(row_index)

    for values, code in (
        (game_references, "D01A_RECORDING_GAME_ID_DUPLICATE"),
        (recording_files, "D01A_RECORDING_FILENAME_DUPLICATE"),
        (row_indices, "D01A_RECORDING_ROW_INDEX_DUPLICATE"),
    ):
        if len(values) != len(set(values)):
            raise SourceInventoryError(code)

    if selected_level_count != _positive_integer(
        raw_source["expected_level_count"],
        "D01A_RAW_RECORDING_EXPECTED_LEVEL_COUNT",
    ):
        raise SourceInventoryError("D01A_RECORDING_LEVEL_COUNT_MISMATCH")
    if selected_level_count != _positive_integer(
        manifest["selected_level_count"],
        "D01A_RECORDING_MANIFEST_SELECTED_LEVEL_COUNT",
    ):
        raise SourceInventoryError(
            "D01A_RECORDING_MANIFEST_LEVEL_ACCOUNTING_MISMATCH"
        )
    if selected_expected_actions != _positive_integer(
        manifest["selected_expected_actions"],
        "D01A_RECORDING_MANIFEST_SELECTED_ACTION_COUNT",
    ):
        raise SourceInventoryError(
            "D01A_RECORDING_MANIFEST_ACTION_ACCOUNTING_MISMATCH"
        )
    if _path_set_digest(recording_files) != _sha256(
        raw_source["expected_filename_set_sha256"],
        "D01A_RAW_RECORDING_FILENAME_SET",
    ):
        raise SourceInventoryError("D01A_RECORDING_FILENAME_SET_DRIFT")

    pinned = _object(
        manifest["pinned_trajectory_sha256_by_game"],
        "D01A_RECORDING_PINNED_TRAJECTORIES",
    )
    if set(pinned) != set(game_references):
        raise SourceInventoryError(
            "D01A_RECORDING_PINNED_TRAJECTORY_GAME_SET_MISMATCH"
        )
    for game_reference in sorted(game_references):
        _sha256(
            pinned[game_reference],
            "D01A_RECORDING_PINNED_TRAJECTORY_SHA256",
        )
    return sorted(
        rows,
        key=lambda row: _string(
            row["game_id"],
            "D01A_RECORDING_GAME_ID",
        ),
    )


def _validate_profile(profile: JsonObject) -> str:
    _strict_fields(profile, PROFILE_FIELDS, "D01A_PROFILE")
    if profile["schema_version"] != PROFILE_SCHEMA_VERSION:
        raise SourceInventoryError("D01A_PROFILE_SCHEMA_VERSION_MISMATCH")
    profile_id = _string(profile["profile_id"], "D01A_PROFILE_ID")
    if _PROFILE_ID_RE.fullmatch(profile_id) is None:
        raise SourceInventoryError(
            f"D01A_PROFILE_ID_INVALID:{profile_id}"
        )
    profile_type = _enum(
        profile["profile_type"],
        PROFILE_TYPES,
        "D01A_PROFILE_TYPE",
    )
    domain = _enum(
        profile["domain"],
        frozenset({"ARC2", "ARC3"}),
        "D01A_PROFILE_DOMAIN",
    )
    if not profile_type.startswith(domain):
        raise SourceInventoryError(
            f"D01A_PROFILE_DOMAIN_TYPE_MISMATCH:{profile_id}"
        )
    _string(profile["distribution_format"], "D01A_DISTRIBUTION_FORMAT")
    split_role = _enum(
        profile["split_role"],
        SPLIT_ROLES,
        "D01A_SPLIT_ROLE",
    )
    answer_visibility = _enum(
        profile["answer_visibility"],
        ANSWER_VISIBILITIES,
        "D01A_ANSWER_VISIBILITY",
    )
    development_usage = _enum(
        profile["development_usage"],
        DEVELOPMENT_USAGES,
        "D01A_DEVELOPMENT_USAGE",
    )
    contamination_class = _enum(
        profile["contamination_class"],
        CONTAMINATION_CLASSES,
        "D01A_CONTAMINATION_CLASS",
    )
    _enum(
        profile["materialization_state"],
        MATERIALIZATION_STATES,
        "D01A_MATERIALIZATION_STATE",
    )
    source_code_access = _enum(
        profile["source_code_access"],
        SOURCE_CODE_ACCESS_STATES,
        "D01A_SOURCE_CODE_ACCESS",
    )
    if profile["policy_weight_source"] is not False:
        raise SourceInventoryError(
            f"D01A_POLICY_WEIGHT_SOURCE_FORBIDDEN:{profile_id}"
        )

    if split_role == "PUBLIC_EVALUATION_CONSUMED":
        if development_usage != "DISTILLATION_SOURCE":
            raise SourceInventoryError(
                f"D01A_CONSUMED_SOURCE_USAGE_INVALID:{profile_id}"
            )
        if contamination_class != (
            "PUBLIC_EVALUATION_SUCCESS_TRAJECTORY_CONSUMED"
        ):
            raise SourceInventoryError(
                f"D01A_CONSUMED_SOURCE_CONTAMINATION_MISSING:{profile_id}"
            )
    if (
        split_role == "PUBLIC_EVALUATION_TEACHER"
        and answer_visibility == "ANSWER_VISIBLE"
        and development_usage == "DISTILLATION_SOURCE"
    ):
        raise SourceInventoryError(
            f"D01A_EVALUATION_ANSWER_CONSUMPTION_UNDECLARED:{profile_id}"
        )
    if answer_visibility == "ANSWER_VISIBLE" and split_role.startswith(
        "PUBLIC_EVALUATION"
    ):
        if contamination_class == "NONE":
            raise SourceInventoryError(
                f"D01A_EVALUATION_ANSWER_CONTAMINATION_MISSING:{profile_id}"
            )
    if profile_type == "ARC3_ENVIRONMENT_SOURCE_BUNDLE":
        if (
            split_role != "REPLAY_ONLY_SOURCE"
            or development_usage != "REPLAY_HARNESS_ONLY"
            or source_code_access != "REPLAY_HARNESS_ONLY"
        ):
            raise SourceInventoryError(
                f"D01A_ENVIRONMENT_SOURCE_ACCESS_INVALID:{profile_id}"
            )
    elif source_code_access != "NOT_SOURCE_CODE":
        raise SourceInventoryError(
            f"D01A_NON_ENVIRONMENT_SOURCE_ACCESS_INVALID:{profile_id}"
        )

    selectors = _list(profile["selectors"], "D01A_PROFILE_SELECTORS")
    if not selectors:
        raise SourceInventoryError(
            f"D01A_PROFILE_SELECTORS_EMPTY:{profile_id}"
        )
    return _validate_bound_digest(
        profile,
        PROFILE_DIGEST_NAMESPACE,
        "D01A_PROFILE",
    )


def _load_profiles(
    plan: JsonObject,
    repository_root: Path,
    project_root: Path,
    profile_documents: Mapping[str, JsonObject] | None,
) -> list[tuple[str, JsonObject]]:
    expected_paths = _string_list(
        plan["profile_paths"],
        "D01A_PROFILE_PATHS",
    )
    actual_paths = sorted(
        path.relative_to(repository_root).as_posix()
        for path in (project_root / "profiles" / "source").glob("*.json")
    )
    if actual_paths != sorted(expected_paths):
        raise SourceInventoryError(
            "D01A_PROFILE_FILE_SET_MISMATCH:"
            f"expected={','.join(sorted(expected_paths))}:"
            f"actual={','.join(actual_paths)}"
        )
    documents: list[tuple[str, JsonObject]] = []
    for path in sorted(expected_paths):
        document = (
            profile_documents[path]
            if profile_documents is not None and path in profile_documents
            else _load_object(repository_root / path, "D01A_PROFILE")
        )
        _validate_profile(document)
        documents.append((path, document))
    if profile_documents is not None:
        unknown_overrides = sorted(set(profile_documents) - set(expected_paths))
        if unknown_overrides:
            raise SourceInventoryError(
                "D01A_PROFILE_OVERRIDE_UNKNOWN:"
                + ",".join(unknown_overrides)
            )
    profile_ids = [
        _string(item["profile_id"], "D01A_PROFILE_ID")
        for _path, item in documents
    ]
    if len(profile_ids) != len(set(profile_ids)):
        raise SourceInventoryError("D01A_PROFILE_ID_DUPLICATE")
    return documents


def _candidate_paths(
    plan: JsonObject,
    repository_root: Path,
    tracked_paths_by_root: Mapping[str, Sequence[str]] | None,
) -> tuple[dict[str, tuple[str, ...]], list[JsonValue]]:
    roots = _list(
        plan["repository_candidate_roots"],
        "D01A_CANDIDATE_ROOTS",
    )
    result: dict[str, tuple[str, ...]] = {}
    report_rows: list[JsonValue] = []
    seen_roots: set[str] = set()
    for raw_row in roots:
        row = _object(raw_row, "D01A_CANDIDATE_ROOT")
        expected_fields = frozenset(
            {
                "root",
                "expected_file_count",
                "expected_path_set_sha256",
                "admitted_source_count",
                "excluded_non_source_count",
            }
        )
        _strict_fields(row, expected_fields, "D01A_CANDIDATE_ROOT")
        root = _repository_path(row["root"], "D01A_CANDIDATE_ROOT_PATH")
        if root in seen_roots:
            raise SourceInventoryError(
                f"D01A_CANDIDATE_ROOT_DUPLICATE:{root}"
            )
        seen_roots.add(root)
        paths = tuple(
            sorted(
                tracked_paths_by_root[root]
                if tracked_paths_by_root is not None
                and root in tracked_paths_by_root
                else _git_paths(repository_root, root)
            )
        )
        expected_count = _integer(
            row["expected_file_count"],
            "D01A_CANDIDATE_ROOT_COUNT",
        )
        expected_digest = _sha256(
            row["expected_path_set_sha256"],
            "D01A_CANDIDATE_ROOT_PATH_SET",
        )
        actual_digest = _path_set_digest(paths)
        if len(paths) != expected_count or actual_digest != expected_digest:
            raise SourceInventoryError(
                f"D01A_CANDIDATE_PATH_SET_DRIFT:{root}"
            )
        admitted = _integer(
            row["admitted_source_count"],
            "D01A_CANDIDATE_ROOT_ADMITTED",
        )
        excluded = _integer(
            row["excluded_non_source_count"],
            "D01A_CANDIDATE_ROOT_EXCLUDED",
        )
        if admitted + excluded != expected_count:
            raise SourceInventoryError(
                f"D01A_CANDIDATE_ROOT_ACCOUNTING_INVALID:{root}"
            )
        result[root] = paths
        report_rows.append(
            {
                "admitted_source_count": admitted,
                "excluded_non_source_count": excluded,
                "path_set_sha256": actual_digest,
                "root": root,
                "tracked_file_count": len(paths),
            }
        )
    return result, report_rows


def _validate_plan_preinventory_alignment(
    plan: JsonObject,
    preinventory: JsonObject,
) -> None:
    plan_roots = {
        _string(
            _object(row, "D01A_PLAN_ROOT")["root"],
            "D01A_PLAN_ROOT_PATH",
        ): _object(row, "D01A_PLAN_ROOT")
        for row in _list(
            plan["repository_candidate_roots"],
            "D01A_PLAN_ROOTS",
        )
    }
    preinventory_roots = {
        _string(
            _object(row, "D01A_PREINVENTORY_ROOT")["root"],
            "D01A_PREINVENTORY_ROOT_PATH",
        ): _object(row, "D01A_PREINVENTORY_ROOT")
        for row in _list(
            preinventory.get("repository_candidate_roots"),
            "D01A_PREINVENTORY_ROOTS",
        )
    }
    if set(plan_roots) != set(preinventory_roots):
        raise SourceInventoryError(
            "D01A_PLAN_PREINVENTORY_ROOT_SET_MISMATCH"
        )
    field_pairs = (
        ("expected_file_count", "tracked_file_count"),
        ("expected_path_set_sha256", "path_set_sha256"),
        ("admitted_source_count", "admitted_source_count"),
        ("excluded_non_source_count", "excluded_non_source_count"),
    )
    for root in sorted(plan_roots):
        for plan_field, preinventory_field in field_pairs:
            if (
                plan_roots[root].get(plan_field)
                != preinventory_roots[root].get(preinventory_field)
            ):
                raise SourceInventoryError(
                    "D01A_PLAN_PREINVENTORY_ROOT_MISMATCH:"
                    f"{root}:{plan_field}"
                )

    distributions = {
        _string(
            _object(
                row,
                "D01A_PREINVENTORY_DISTRIBUTION",
            )["distribution_id"],
            "D01A_PREINVENTORY_DISTRIBUTION_ID",
        ): _object(row, "D01A_PREINVENTORY_DISTRIBUTION")
        for row in _list(
            preinventory.get("distribution_observations"),
            "D01A_PREINVENTORY_DISTRIBUTIONS",
        )
    }
    for domain_key in ("arc2_distribution", "arc3_distribution"):
        declared = _object(
            plan[domain_key],
            "D01A_PLAN_DISTRIBUTION",
        )
        distribution_id = _string(
            declared["distribution_id"],
            "D01A_PLAN_DISTRIBUTION_ID",
        )
        observed = distributions.get(distribution_id)
        if observed is None:
            raise SourceInventoryError(
                "D01A_PLAN_DISTRIBUTION_NOT_PREINVENTORIED:"
                + distribution_id
            )
        checks = (
            ("expected_sha256", "authority_sha256"),
            ("expected_member_count", "file_member_count"),
            (
                "expected_member_path_set_sha256",
                "member_path_set_sha256",
            ),
        )
        for plan_field, observed_field in checks:
            if declared.get(plan_field) != observed.get(observed_field):
                raise SourceInventoryError(
                    "D01A_PLAN_PREINVENTORY_DISTRIBUTION_MISMATCH:"
                    f"{distribution_id}:{plan_field}"
                )


def _validate_selector_contract(
    profile: JsonObject,
    selector_kind: str,
) -> None:
    profile_id = _string(profile["profile_id"], "D01A_PROFILE_ID")
    profile_type = _string(
        profile["profile_type"],
        "D01A_PROFILE_TYPE",
    )
    materialization = _string(
        profile["materialization_state"],
        "D01A_MATERIALIZATION_STATE",
    )
    expected_kinds = {
        "ARC2_KAGGLE_CHALLENGE_SOLUTION": {"ARCHIVE_MEMBERS"},
        "ARC2_OFFICIAL_TASK_JSON": {
            "ARCHIVE_MEMBERS",
            "REPOSITORY_FILES",
        },
        "ARC2_INTERNAL_NORMALIZED_CORPUS": {"REPOSITORY_FILES"},
        "ARC3_ENVIRONMENT_SOURCE_BUNDLE": {"REPOSITORY_TREE"},
        "ARC3_RAW_TEACHER_RECORDING": {
            "EXTERNAL_DATASET_MANIFEST_ROWS"
        },
        "ARC3_CANONICAL_TEACHER_TRAJECTORY": {"REPOSITORY_FILES"},
    }
    if selector_kind not in expected_kinds[profile_type]:
        raise SourceInventoryError(
            f"D01A_PROFILE_SELECTOR_KIND_INVALID:{profile_id}:"
            f"{selector_kind}"
        )
    expected_materialization = {
        "REPOSITORY_TREE": "REPOSITORY_TRACKED",
        "REPOSITORY_FILES": "REPOSITORY_TRACKED",
        "ARCHIVE_MEMBERS": "EXTERNAL_ARCHIVE_VERIFIED",
        "EXTERNAL_DATASET_MANIFEST_ROWS": (
            "REFERENCED_NOT_LOCALLY_MATERIALIZED"
        ),
    }
    if materialization != expected_materialization[selector_kind]:
        raise SourceInventoryError(
            f"D01A_PROFILE_MATERIALIZATION_INVALID:{profile_id}:"
            f"{selector_kind}"
        )


def _common_record(profile: Mapping[str, JsonValue]) -> JsonObject:
    return {
        "answer_visibility": profile["answer_visibility"],
        "contamination_class": profile["contamination_class"],
        "development_usage": profile["development_usage"],
        "distribution_format": profile["distribution_format"],
        "domain": profile["domain"],
        "materialization_state": profile["materialization_state"],
        "policy_weight_source": False,
        "profile_id": profile["profile_id"],
        "profile_type": profile["profile_type"],
        "source_code_access": profile["source_code_access"],
        "split_role": profile["split_role"],
    }


def _repository_tree_records(
    selector: JsonObject,
    profile: JsonObject,
    paths_by_root: Mapping[str, Sequence[str]],
) -> list[JsonObject]:
    fields = frozenset(
        {
            "selector_kind",
            "root",
            "expected_file_count",
            "expected_path_set_sha256",
            "archive_alias_distribution_id",
            "archive_alias_prefix",
        }
    )
    _strict_fields(selector, fields, "D01A_REPOSITORY_TREE_SELECTOR")
    root = _repository_path(selector["root"], "D01A_SELECTOR_ROOT")
    if root not in paths_by_root:
        raise SourceInventoryError(
            f"D01A_SELECTOR_ROOT_NOT_CANDIDATE:{root}"
        )
    paths = tuple(paths_by_root[root])
    if len(paths) != _integer(
        selector["expected_file_count"],
        "D01A_SELECTOR_FILE_COUNT",
    ):
        raise SourceInventoryError(
            f"D01A_SELECTOR_FILE_COUNT_MISMATCH:{root}"
        )
    if _path_set_digest(paths) != _sha256(
        selector["expected_path_set_sha256"],
        "D01A_SELECTOR_PATH_SET",
    ):
        raise SourceInventoryError(
            f"D01A_SELECTOR_PATH_SET_MISMATCH:{root}"
        )
    distribution = selector["archive_alias_distribution_id"]
    prefix = selector["archive_alias_prefix"]
    if (distribution is None) != (prefix is None):
        raise SourceInventoryError(
            f"D01A_SELECTOR_ALIAS_PARTIAL:{root}"
        )
    if distribution is not None and not isinstance(distribution, str):
        raise SourceInventoryError(
            f"D01A_SELECTOR_ALIAS_DISTRIBUTION_INVALID:{root}"
        )
    if prefix is not None and not isinstance(prefix, str):
        raise SourceInventoryError(
            f"D01A_SELECTOR_ALIAS_PREFIX_INVALID:{root}"
        )
    records: list[JsonObject] = []
    for path in paths:
        common = _common_record(profile)
        aliases: list[JsonValue] = []
        if distribution is not None and prefix is not None:
            aliases.append(
                f"archive:{distribution}!/{prefix}{path}"
            )
        common.update(
            {
                "aliases": aliases,
                "locator": path,
                "locator_kind": "REPOSITORY_FILE",
                "source_id": "repo:" + path,
            }
        )
        records.append(common)
    return records


def _repository_file_records(
    selector: JsonObject,
    profile: JsonObject,
    repository_root: Path,
) -> list[JsonObject]:
    fields = frozenset(
        {"selector_kind", "paths", "expected_file_count"}
    )
    _strict_fields(selector, fields, "D01A_REPOSITORY_FILES_SELECTOR")
    paths = _string_list(selector["paths"], "D01A_SELECTOR_PATHS")
    paths = [
        _repository_path(path, "D01A_SELECTOR_REPOSITORY_PATH")
        for path in paths
    ]
    if len(paths) != _integer(
        selector["expected_file_count"],
        "D01A_SELECTOR_FILE_COUNT",
    ):
        raise SourceInventoryError(
            "D01A_SELECTOR_FILE_COUNT_MISMATCH:REPOSITORY_FILES"
        )
    records: list[JsonObject] = []
    for path in sorted(paths):
        if not (repository_root / path).is_file():
            raise SourceInventoryError(
                f"D01A_REPOSITORY_SOURCE_MISSING:{path}"
            )
        common = _common_record(profile)
        common.update(
            {
                "aliases": [],
                "locator": path,
                "locator_kind": "REPOSITORY_FILE",
                "source_id": "repo:" + path,
            }
        )
        records.append(common)
    return records


def _archive_member_records(
    selector: JsonObject,
    profile: JsonObject,
) -> list[JsonObject]:
    fields = frozenset(
        {
            "selector_kind",
            "distribution_id",
            "expected_distribution_sha256",
            "members",
        }
    )
    _strict_fields(selector, fields, "D01A_ARCHIVE_SELECTOR")
    distribution = _string(
        selector["distribution_id"],
        "D01A_ARCHIVE_DISTRIBUTION",
    )
    distribution_sha256 = _sha256(
        selector["expected_distribution_sha256"],
        "D01A_ARCHIVE_SHA256",
    )
    members = [
        _repository_path(item, "D01A_ARCHIVE_MEMBER")
        for item in _string_list(
            selector["members"],
            "D01A_ARCHIVE_MEMBERS",
        )
    ]
    records: list[JsonObject] = []
    for member in sorted(members):
        locator = f"{distribution}!/{member}"
        common = _common_record(profile)
        common.update(
            {
                "aliases": [],
                "distribution_sha256": distribution_sha256,
                "locator": locator,
                "locator_kind": "ARCHIVE_MEMBER",
                "source_id": "archive:" + locator,
            }
        )
        records.append(common)
    return records


def _external_dataset_records(
    selector: JsonObject,
    profile: JsonObject,
    repository_root: Path,
    raw_source: JsonObject,
    source_manifest_document: JsonObject | None,
) -> list[JsonObject]:
    fields = frozenset(
        {
            "selector_kind",
            "source_manifest_path",
            "dataset_id",
            "dataset_repo_sha",
            "recording_field",
            "expected_selected_count",
            "expected_filename_set_sha256",
        }
    )
    _strict_fields(selector, fields, "D01A_DATASET_SELECTOR")
    manifest_path = _repository_path(
        selector["source_manifest_path"],
        "D01A_DATASET_MANIFEST_PATH",
    )
    expected_manifest_path = _repository_path(
        raw_source["source_manifest_path"],
        "D01A_RAW_SOURCE_MANIFEST_PATH",
    )
    if manifest_path != expected_manifest_path:
        raise SourceInventoryError(
            "D01A_DATASET_MANIFEST_PATH_MISMATCH"
        )
    manifest = (
        source_manifest_document
        if source_manifest_document is not None
        else _load_object(
            repository_root / manifest_path,
            "D01A_RECORDING_MANIFEST",
        )
    )
    dataset_id = _string(
        selector["dataset_id"],
        "D01A_DATASET_ID",
    )
    dataset_repo_sha = _git_sha(
        selector["dataset_repo_sha"],
        "D01A_DATASET_REPO_SHA",
    )
    if dataset_id != raw_source["dataset_id"]:
        raise SourceInventoryError("D01A_DATASET_ID_PLAN_MISMATCH")
    if dataset_repo_sha != raw_source["dataset_repo_sha"]:
        raise SourceInventoryError("D01A_DATASET_REPO_SHA_PLAN_MISMATCH")
    if manifest.get("dataset_id") != dataset_id:
        raise SourceInventoryError("D01A_DATASET_ID_MISMATCH")
    if manifest.get("dataset_repo_sha") != dataset_repo_sha:
        raise SourceInventoryError("D01A_DATASET_REPO_SHA_MISMATCH")
    field = _string(
        selector["recording_field"],
        "D01A_RECORDING_FIELD",
    )
    if field != "recording_file":
        raise SourceInventoryError("D01A_RECORDING_FIELD_INVALID")
    rows = _list(
        manifest.get("rows"),
        "D01A_RECORDING_MANIFEST_ROWS",
    )
    filenames: list[str] = []
    for raw_row in rows:
        row = _object(raw_row, "D01A_RECORDING_ROW")
        filenames.append(
            _repository_path(
                row.get(field),
                "D01A_RECORDING_FILENAME",
            )
        )
    if len(filenames) != len(set(filenames)):
        raise SourceInventoryError("D01A_RECORDING_FILENAME_DUPLICATE")
    if len(filenames) != _integer(
        selector["expected_selected_count"],
        "D01A_RECORDING_EXPECTED_COUNT",
    ):
        raise SourceInventoryError("D01A_RECORDING_COUNT_MISMATCH")
    if selector["expected_selected_count"] != (
        raw_source["expected_selected_count"]
    ):
        raise SourceInventoryError(
            "D01A_RECORDING_COUNT_PLAN_MISMATCH"
        )
    if _path_set_digest(filenames) != _sha256(
        selector["expected_filename_set_sha256"],
        "D01A_RECORDING_FILENAME_SET",
    ):
        raise SourceInventoryError("D01A_RECORDING_FILENAME_SET_DRIFT")
    if selector["expected_filename_set_sha256"] != (
        raw_source["expected_filename_set_sha256"]
    ):
        raise SourceInventoryError(
            "D01A_RECORDING_FILENAME_SET_PLAN_MISMATCH"
        )
    records: list[JsonObject] = []
    for filename in sorted(filenames):
        locator = f"{dataset_id}@{dataset_repo_sha}/{filename}"
        common = _common_record(profile)
        common.update(
            {
                "aliases": [],
                "locator": locator,
                "locator_kind": "EXTERNAL_DATASET_MEMBER",
                "source_id": "dataset:" + locator,
            }
        )
        records.append(common)
    return records


def _expand_profiles(
    profiles: Sequence[tuple[str, JsonObject]],
    repository_root: Path,
    paths_by_root: Mapping[str, Sequence[str]],
    raw_source: JsonObject,
    source_manifest_document: JsonObject | None,
) -> tuple[list[JsonObject], list[JsonValue]]:
    records: list[JsonObject] = []
    manifests: list[JsonValue] = []
    for path, profile in profiles:
        profile_records: list[JsonObject] = []
        for raw_selector in _list(
            profile["selectors"],
            "D01A_PROFILE_SELECTORS",
        ):
            selector = _object(raw_selector, "D01A_PROFILE_SELECTOR")
            kind = _enum(
                selector.get("selector_kind"),
                SELECTOR_KINDS,
                "D01A_SELECTOR_KIND",
            )
            _validate_selector_contract(profile, kind)
            if kind == "REPOSITORY_TREE":
                expanded = _repository_tree_records(
                    selector,
                    profile,
                    paths_by_root,
                )
            elif kind == "REPOSITORY_FILES":
                expanded = _repository_file_records(
                    selector,
                    profile,
                    repository_root,
                )
            elif kind == "ARCHIVE_MEMBERS":
                expanded = _archive_member_records(selector, profile)
            else:
                expanded = _external_dataset_records(
                    selector,
                    profile,
                    repository_root,
                    raw_source,
                    source_manifest_document,
                )
            profile_records.extend(expanded)
        records.extend(profile_records)
        manifests.append(
            {
                "content_digest": profile["content_digest"],
                "path": path,
                "profile_id": profile["profile_id"],
                "profile_type": profile["profile_type"],
                "source_count": len(profile_records),
            }
        )
    source_ids = [
        _string(record["source_id"], "D01A_SOURCE_ID")
        for record in records
    ]
    duplicates = sorted(
        source_id
        for source_id, count in Counter(source_ids).items()
        if count > 1
    )
    if duplicates:
        raise SourceInventoryError(
            "D01A_SOURCE_ASSIGNMENT_DUPLICATE:" + ",".join(duplicates)
        )
    aliases = [
        _string(alias, "D01A_SOURCE_ALIAS")
        for record in records
        for alias in _list(record["aliases"], "D01A_SOURCE_ALIASES")
    ]
    duplicate_aliases = sorted(
        alias
        for alias, count in Counter(aliases).items()
        if count > 1
    )
    if duplicate_aliases:
        raise SourceInventoryError(
            "D01A_SOURCE_ALIAS_DUPLICATE:" + ",".join(duplicate_aliases)
        )
    source_id_set = set(source_ids)
    alias_source_collisions = sorted(set(aliases) & source_id_set)
    if alias_source_collisions:
        raise SourceInventoryError(
            "D01A_SOURCE_ALIAS_ID_COLLISION:"
            + ",".join(alias_source_collisions)
        )
    return sorted(
        records,
        key=lambda item: _string(item["source_id"], "D01A_SOURCE_ID"),
    ), manifests


def _expected_repository_sources(
    plan: JsonObject,
    paths_by_root: Mapping[str, Sequence[str]],
) -> set[str]:
    admitted = _object(
        plan["repository_admitted_paths"],
        "D01A_REPOSITORY_ADMITTED_PATHS",
    )
    _strict_fields(
        admitted,
        frozenset({"tree_roots", "exact_paths"}),
        "D01A_REPOSITORY_ADMITTED_PATHS",
    )
    expected: set[str] = set()
    for root in _string_list(
        admitted["tree_roots"],
        "D01A_REPOSITORY_ADMITTED_ROOTS",
    ):
        if root not in paths_by_root:
            raise SourceInventoryError(
                f"D01A_ADMITTED_ROOT_NOT_CANDIDATE:{root}"
            )
        expected.update(paths_by_root[root])
    expected.update(
        _repository_path(path, "D01A_ADMITTED_EXACT_PATH")
        for path in _string_list(
            admitted["exact_paths"],
            "D01A_REPOSITORY_ADMITTED_EXACT_PATHS",
        )
    )
    return expected


def _validate_assignments(
    plan: JsonObject,
    records: Sequence[JsonObject],
    paths_by_root: Mapping[str, Sequence[str]],
) -> None:
    repository_actual = {
        _string(record["locator"], "D01A_REPOSITORY_LOCATOR")
        for record in records
        if record["locator_kind"] == "REPOSITORY_FILE"
    }
    repository_expected = _expected_repository_sources(plan, paths_by_root)
    if repository_actual != repository_expected:
        missing = sorted(repository_expected - repository_actual)
        extra = sorted(repository_actual - repository_expected)
        raise SourceInventoryError(
            "D01A_REPOSITORY_ASSIGNMENT_MISMATCH:"
            f"missing={','.join(missing)}:extra={','.join(extra)}"
        )

    arc2 = _object(
        plan["arc2_distribution"],
        "D01A_ARC2_DISTRIBUTION",
    )
    distribution = _string(
        arc2["distribution_id"],
        "D01A_ARC2_DISTRIBUTION_ID",
    )
    distribution_sha256 = _sha256(
        arc2["expected_sha256"],
        "D01A_ARC2_DISTRIBUTION_SHA256",
    )
    expected_members = set(
        _string_list(
            arc2["admitted_members"],
            "D01A_ARC2_ADMITTED_MEMBERS",
        )
    )
    actual_members = {
        _string(record["locator"], "D01A_ARCHIVE_LOCATOR").split(
            "!/", 1
        )[1]
        for record in records
        if record["locator_kind"] == "ARCHIVE_MEMBER"
        and _string(record["locator"], "D01A_ARCHIVE_LOCATOR").startswith(
            distribution + "!/"
        )
    }
    if actual_members != expected_members:
        raise SourceInventoryError("D01A_ARC2_ASSIGNMENT_MISMATCH")
    archive_records = [
        record
        for record in records
        if record["locator_kind"] == "ARCHIVE_MEMBER"
    ]
    if any(
        not _string(
            record["locator"],
            "D01A_ARCHIVE_LOCATOR",
        ).startswith(distribution + "!/")
        or record.get("distribution_sha256") != distribution_sha256
        for record in archive_records
    ):
        raise SourceInventoryError("D01A_ARC2_DISTRIBUTION_BINDING_MISMATCH")

    arc3 = _object(
        plan["arc3_distribution"],
        "D01A_ARC3_DISTRIBUTION",
    )
    arc3_distribution = _string(
        arc3["distribution_id"],
        "D01A_ARC3_DISTRIBUTION_ID",
    )
    alias_prefix_value = arc3["environment_alias_prefix"]
    if not isinstance(alias_prefix_value, str):
        raise SourceInventoryError(
            "D01A_ARC3_ENVIRONMENT_ALIAS_PREFIX_NOT_STRING"
        )
    alias_prefix = alias_prefix_value
    environment_records = [
        record
        for record in records
        if record["profile_type"] == "ARC3_ENVIRONMENT_SOURCE_BUNDLE"
    ]
    for record in environment_records:
        locator = _string(
            record["locator"],
            "D01A_ENVIRONMENT_LOCATOR",
        )
        expected_alias = (
            f"archive:{arc3_distribution}!/{alias_prefix}{locator}"
        )
        if record["aliases"] != [expected_alias]:
            raise SourceInventoryError(
                "D01A_ARC3_ENVIRONMENT_ALIAS_MISMATCH:" + locator
            )
    if len(environment_records) != _integer(
        arc3["environment_alias_count"],
        "D01A_ARC3_ENVIRONMENT_ALIAS_COUNT",
    ):
        raise SourceInventoryError(
            "D01A_ARC3_ENVIRONMENT_ALIAS_COUNT_MISMATCH"
        )

    raw_source = _object(
        plan["raw_recording_source"],
        "D01A_RAW_RECORDING_SOURCE",
    )
    dataset_id = _string(
        raw_source["dataset_id"],
        "D01A_RAW_DATASET_ID",
    )
    dataset_repo_sha = _git_sha(
        raw_source["dataset_repo_sha"],
        "D01A_RAW_DATASET_REPO_SHA",
    )
    raw_records = [
        record
        for record in records
        if record["profile_type"] == "ARC3_RAW_TEACHER_RECORDING"
    ]
    raw_prefix = f"{dataset_id}@{dataset_repo_sha}/"
    if any(
        not _string(
            record["locator"],
            "D01A_RAW_RECORDING_LOCATOR",
        ).startswith(raw_prefix)
        for record in raw_records
    ):
        raise SourceInventoryError("D01A_RAW_RECORDING_BINDING_MISMATCH")
    if len(raw_records) != _integer(
        raw_source["expected_selected_count"],
        "D01A_RAW_RECORDING_COUNT",
    ):
        raise SourceInventoryError("D01A_RAW_RECORDING_COUNT_MISMATCH")

    non_source_policy = _object(
        plan["non_source_policy"],
        "D01A_NON_SOURCE_POLICY",
    )
    if _integer(
        non_source_policy["policy_weight_admitted_source_count"],
        "D01A_POLICY_WEIGHT_EXPECTED_COUNT",
    ) != 0:
        raise SourceInventoryError(
            "D01A_POLICY_WEIGHT_EXPECTATION_NOT_ZERO"
        )
    if any(record["policy_weight_source"] is not False for record in records):
        raise SourceInventoryError("D01A_POLICY_WEIGHT_SOURCE_ADMITTED")


def _count_by(
    records: Sequence[JsonObject],
    field: str,
    complete_keys: Sequence[str],
) -> JsonObject:
    counts = Counter(_string(record[field], "D01A_COUNT_FIELD") for record in records)
    return {key: counts.get(key, 0) for key in sorted(complete_keys)}


def _validate_expected_accounting(
    plan: JsonObject,
    actual: Mapping[str, int],
) -> None:
    expected = _object(
        plan["expected_accounting"],
        "D01A_EXPECTED_ACCOUNTING",
    )
    if set(expected) != set(actual):
        raise SourceInventoryError("D01A_ACCOUNTING_FIELD_SET_MISMATCH")
    for field in sorted(actual):
        expected_value = _integer(
            expected[field],
            "D01A_EXPECTED_ACCOUNTING_VALUE",
        )
        if actual[field] != expected_value:
            raise SourceInventoryError(
                f"D01A_ACCOUNTING_MISMATCH:{field}:"
                f"expected={expected_value}:actual={actual[field]}"
            )


def build_source_inventory(
    project_root: Path,
    *,
    repository_root: Path | None = None,
    profile_documents: Mapping[str, JsonObject] | None = None,
    tracked_paths_by_root: Mapping[str, Sequence[str]] | None = None,
    source_manifest_document: JsonObject | None = None,
) -> JsonObject:
    """Build the PH-D01A inventory from metadata without source execution."""

    project_root = project_root.resolve()
    repository_root = (
        repository_root.resolve()
        if repository_root is not None
        else project_root.parent.resolve()
    )
    if project_root != repository_root / "distillation":
        raise SourceInventoryError(
            "D01A_PROJECT_ROOT_MUST_BE_REPOSITORY_DISTILLATION"
        )

    plan_path = project_root / "input" / "source_inventory_plan.json"
    plan = _load_object(plan_path, "D01A_PLAN")
    plan_digest = _validate_plan(plan)
    preinventory_path = repository_root / _repository_path(
        plan["preinventory_path"],
        "D01A_PREINVENTORY_PATH",
    )
    preinventory = _load_object(
        preinventory_path,
        "D01A_PREINVENTORY",
    )
    preinventory_digest = _digest(
        preinventory,
        PREINVENTORY_DIGEST_NAMESPACE,
    )
    if preinventory.get("content_digest") != preinventory_digest:
        raise SourceInventoryError("D01A_PREINVENTORY_DIGEST_MISMATCH")
    if plan["preinventory_digest"] != preinventory_digest:
        raise SourceInventoryError("D01A_PLAN_PREINVENTORY_BINDING_MISMATCH")
    _validate_plan_preinventory_alignment(plan, preinventory)
    raw_source = _object(
        plan["raw_recording_source"],
        "D01A_RAW_RECORDING_SOURCE",
    )
    raw_manifest_path = repository_root / _repository_path(
        raw_source["source_manifest_path"],
        "D01A_RAW_RECORDING_MANIFEST_PATH",
    )
    raw_manifest = (
        source_manifest_document
        if source_manifest_document is not None
        else _load_object(
            raw_manifest_path,
            "D01A_RECORDING_MANIFEST",
        )
    )
    _validate_raw_recording_manifest(raw_manifest, raw_source)

    paths_by_root, candidate_rows = _candidate_paths(
        plan,
        repository_root,
        tracked_paths_by_root,
    )
    profiles = _load_profiles(
        plan,
        repository_root,
        project_root,
        profile_documents,
    )
    records, profile_manifest = _expand_profiles(
        profiles,
        repository_root,
        paths_by_root,
        raw_source,
        raw_manifest,
    )
    _validate_assignments(plan, records, paths_by_root)

    repository_candidate_count = sum(
        _integer(
            row["tracked_file_count"],
            "D01A_REPORT_CANDIDATE_COUNT",
        )
        for row in cast(list[JsonObject], candidate_rows)
    )
    repository_admitted_count = sum(
        1 for record in records if record["locator_kind"] == "REPOSITORY_FILE"
    )
    archive_admitted_count = sum(
        1 for record in records if record["locator_kind"] == "ARCHIVE_MEMBER"
    )
    raw_recording_count = sum(
        1
        for record in records
        if record["locator_kind"] == "EXTERNAL_DATASET_MEMBER"
    )
    actual_accounting = {
        "duplicate_source_assignment_count": 0,
        "external_arc2_admitted_source_count": archive_admitted_count,
        "external_raw_recording_admitted_source_count": raw_recording_count,
        "policy_weight_admitted_source_count": 0,
        "profile_count": len(profiles),
        "repository_admitted_source_count": repository_admitted_count,
        "repository_candidate_file_count": repository_candidate_count,
        "repository_excluded_non_source_count": (
            repository_candidate_count - repository_admitted_count
        ),
        "unassigned_admitted_source_count": 0,
        "unique_admitted_source_count": len(records),
        "unknown_answer_visibility_count": 0,
        "unknown_split_role_count": 0,
    }
    _validate_expected_accounting(plan, actual_accounting)

    source_payload_access = _object(
        plan["source_payload_access"],
        "D01A_SOURCE_PAYLOAD_ACCESS",
    )
    _strict_fields(
        source_payload_access,
        frozenset(
            {
                "payload_parse_count",
                "source_execution_count",
                "replay_execution_count",
            }
        ),
        "D01A_SOURCE_PAYLOAD_ACCESS",
    )
    if any(
        _integer(value, "D01A_SOURCE_PAYLOAD_ACCESS_COUNT") != 0
        for value in source_payload_access.values()
    ):
        raise SourceInventoryError("D01A_SOURCE_PAYLOAD_ACCESS_NONZERO")

    report: JsonObject = {
        "schema_version": REPORT_SCHEMA_VERSION,
        "report_id": REPORT_ID,
        "phase_id": PHASE_ID,
        "inventory_semantics": (
            "SOURCE_PROFILE_AND_CONTAMINATION_METADATA_ONLY"
        ),
        "plan_digest": plan_digest,
        "preinventory_digest": preinventory_digest,
        "profile_manifest": profile_manifest,
        "profile_count": len(profiles),
        "source_count": len(records),
        "source_records": list(records),
        "counts_by_profile_type": _count_by(
            records,
            "profile_type",
            sorted(PROFILE_TYPES),
        ),
        "counts_by_split_role": _count_by(
            records,
            "split_role",
            sorted(SPLIT_ROLES),
        ),
        "counts_by_answer_visibility": _count_by(
            records,
            "answer_visibility",
            sorted(ANSWER_VISIBILITIES),
        ),
        "counts_by_development_usage": _count_by(
            records,
            "development_usage",
            sorted(DEVELOPMENT_USAGES),
        ),
        "counts_by_contamination_class": _count_by(
            records,
            "contamination_class",
            sorted(CONTAMINATION_CLASSES),
        ),
        "candidate_root_accounting": candidate_rows,
        "accounting": {
            key: actual_accounting[key] for key in sorted(actual_accounting)
        },
        "source_payload_access": source_payload_access,
        "arc3_distribution_alias_count": sum(
            len(_list(record["aliases"], "D01A_SOURCE_ALIASES"))
            for record in records
        ),
        "policy_weight_admitted_source_count": 0,
        "environment_source_non_replay_access_count": 0,
        "public_evaluation_consumed_source_count": sum(
            1
            for record in records
            if record["split_role"] == "PUBLIC_EVALUATION_CONSUMED"
        ),
        "unknown_answer_visibility_count": 0,
        "unknown_split_role_count": 0,
        "duplicate_source_assignment_count": 0,
        "unassigned_admitted_source_count": 0,
        "gates": {
            "DG-00": "PASS",
            "DG-06": "PASS",
            "DG-09": "PASS",
        },
        "phase_exit_claim": "PH_D01A_SOURCE_INVENTORY_PASS",
        "claim_boundary": (
            "Metadata classification only; not SourceContentManifest, "
            "AcquisitionRecord, EnvironmentManifest, Merkle, trajectory "
            "normalization, causal, Rule-promotion, Bridge, AGI, official, "
            "or submission evidence."
        ),
        "phase_boundaries": {
            "content_manifest_frozen": False,
            "acquisition_manifest_frozen": False,
            "environment_manifest_frozen": False,
            "trajectory_normalization_started": False,
            "causal_ir_started": False,
            "candidate_generation_started": False,
            "bridge_started": False,
            "runtime_started": False,
            "official_access_count": 0,
            "kaggle_mutation_count": 0,
        },
        "digest_excluded_fields": list(REPORT_DIGEST_EXCLUDED_FIELDS),
        "content_digest": "",
    }
    report["content_digest"] = _digest(
        report,
        REPORT_DIGEST_NAMESPACE,
        excluded_fields=REPORT_DIGEST_EXCLUDED_FIELDS,
    )
    return report


def build_primary_source_provenance_report(
    project_root: Path,
    *,
    repository_root: Path | None = None,
    source_manifest_document: JsonObject | None = None,
) -> JsonObject:
    """Build explicit raw-recording-to-corpus provenance from metadata only."""

    project_root = project_root.resolve()
    repository_root = (
        repository_root.resolve()
        if repository_root is not None
        else project_root.parent.resolve()
    )
    if project_root != repository_root / "distillation":
        raise SourceInventoryError(
            "D01A_PROJECT_ROOT_MUST_BE_REPOSITORY_DISTILLATION"
        )

    inventory = build_source_inventory(
        project_root,
        repository_root=repository_root,
        source_manifest_document=source_manifest_document,
    )
    plan = _load_object(
        project_root / "input" / "source_inventory_plan.json",
        "D01A_PLAN",
    )
    _validate_plan(plan)
    raw_source = _object(
        plan["raw_recording_source"],
        "D01A_RAW_RECORDING_SOURCE",
    )
    manifest_path = repository_root / _repository_path(
        raw_source["source_manifest_path"],
        "D01A_RAW_RECORDING_MANIFEST_PATH",
    )
    manifest = (
        source_manifest_document
        if source_manifest_document is not None
        else _load_object(
            manifest_path,
            "D01A_RECORDING_MANIFEST",
        )
    )
    rows = _validate_raw_recording_manifest(manifest, raw_source)
    pinned = _object(
        manifest["pinned_trajectory_sha256_by_game"],
        "D01A_RECORDING_PINNED_TRAJECTORIES",
    )

    source_records = cast(
        list[JsonObject],
        _list(inventory["source_records"], "D01A_SOURCE_RECORDS"),
    )
    source_ids = {
        _string(record["source_id"], "D01A_SOURCE_ID")
        for record in source_records
    }
    canonical_source_ids = tuple(
        "repo:" + path for path in CANONICAL_CORPUS_PATHS
    )
    missing_canonical_sources = sorted(set(canonical_source_ids) - source_ids)
    if missing_canonical_sources:
        raise SourceInventoryError(
            "D01A_CANONICAL_CORPUS_SOURCE_MISSING:"
            + ",".join(missing_canonical_sources)
        )

    raw_records_by_filename: dict[str, JsonObject] = {}
    for record in source_records:
        if record["profile_type"] != "ARC3_RAW_TEACHER_RECORDING":
            continue
        locator = _string(record["locator"], "D01A_RAW_RECORDING_LOCATOR")
        filename = PurePosixPath(locator).name
        if filename in raw_records_by_filename:
            raise SourceInventoryError(
                "D01A_RAW_RECORDING_FILENAME_DUPLICATE:" + filename
            )
        raw_records_by_filename[filename] = record

    provenance_records: list[JsonValue] = []
    for row in rows:
        game_reference = _string(
            row["game_id"],
            "D01A_RECORDING_GAME_ID",
        )
        filename = _string(
            row["recording_file"],
            "D01A_RECORDING_FILENAME",
        )
        raw_record = raw_records_by_filename.get(filename)
        if raw_record is None:
            raise SourceInventoryError(
                "D01A_RAW_RECORDING_SOURCE_NOT_IN_INVENTORY:" + filename
            )
        body: JsonObject = {
            "game_reference": game_reference,
            "identity_use_boundary": (
                "PROVENANCE_ONLY_NOT_SELECTOR_PARAMETER_OR_RUNTIME_ROUTING"
            ),
            "raw_recording_source_id": raw_record["source_id"],
            "raw_recording_locator": raw_record["locator"],
            "recording_file": filename,
            "pinned_trajectory_sha256": _sha256(
                pinned[game_reference],
                "D01A_RECORDING_PINNED_TRAJECTORY_SHA256",
            ),
            "target_level_count": _positive_integer(
                row["target_levels"],
                "D01A_RECORDING_TARGET_LEVELS",
            ),
            "expected_action_count": _positive_integer(
                row["expected_actions"],
                "D01A_RECORDING_EXPECTED_ACTIONS",
            ),
            "canonical_corpus_source_ids": list(canonical_source_ids),
            "relation_kind": (
                "D01A_METADATA_LEDGER_RAW_RECORDING_TO_CANONICAL_CORPUS"
            ),
            "evidence_basis": (
                "D01A_LEDGER_DECLARATION_PLUS_PINNED_SOURCE_MANIFEST_METADATA"
            ),
            "payload_cross_check_status": (
                "NOT_PERFORMED_PH_D01A_METADATA_ONLY"
            ),
        }
        body["provenance_record_id"] = (
            "hds-primary-source-provenance:"
            + hashlib.sha256(
                canonical_json(body).encode("utf-8")
            ).hexdigest()
        )
        provenance_records.append(body)

    if set(raw_records_by_filename) != {
        _string(row["recording_file"], "D01A_RECORDING_FILENAME")
        for row in rows
    }:
        raise SourceInventoryError(
            "D01A_RAW_RECORDING_PROVENANCE_COVERAGE_MISMATCH"
        )

    forbidden_repository_sources = sorted(
        _string(record["locator"], "D01A_REPOSITORY_LOCATOR")
        for record in source_records
        if record["locator_kind"] == "REPOSITORY_FILE"
        and _string(record["locator"], "D01A_REPOSITORY_LOCATOR").startswith(
            FORBIDDEN_PRIMARY_SOURCE_REPOSITORY_PREFIXES
        )
    )
    if forbidden_repository_sources:
        raise SourceInventoryError(
            "D01A_NON_PRIMARY_ARTIFACT_LAYER_ADMITTED:"
            + ",".join(forbidden_repository_sources)
        )
    if any(record["policy_weight_source"] is not False for record in source_records):
        raise SourceInventoryError("D01A_POLICY_WEIGHT_SOURCE_ADMITTED")

    metadata_binding: JsonObject = {
        "dataset_id": manifest["dataset_id"],
        "dataset_repo_sha": manifest["dataset_repo_sha"],
        "development_only": manifest["development_only"],
        "pinned_trajectory_sha256_by_game": pinned,
        "rows": cast(JsonValue, rows),
        "runtime_use": manifest["runtime_use"],
        "schema_version": manifest["schema_version"],
        "selected_expected_actions": manifest["selected_expected_actions"],
        "selected_game_count": manifest["selected_game_count"],
        "selected_level_count": manifest["selected_level_count"],
        "selection": manifest["selection"],
        "split": manifest["split"],
    }
    metadata_digest = (
        "hds-source-manifest-metadata:"
        + hashlib.sha256(
            canonical_json(metadata_binding).encode("utf-8")
        ).hexdigest()
    )

    report: JsonObject = {
        "schema_version": PROVENANCE_REPORT_SCHEMA_VERSION,
        "report_id": PROVENANCE_REPORT_ID,
        "phase_id": PHASE_ID,
        "inventory_semantics": (
            "PRIMARY_TEACHER_SOURCE_PROVENANCE_METADATA_ONLY"
        ),
        "source_inventory_digest": inventory["content_digest"],
        "source_manifest_path": raw_source["source_manifest_path"],
        "source_manifest_metadata_digest": metadata_digest,
        "artifact_layer_policy": {
            "admitted_artifact_layer": "PRIMARY_TEACHER_SOURCE",
            "primary_teacher_source_count": len(source_records),
            "derived_distillation_evidence_admitted_source_count": 0,
            "governance_artifact_admitted_source_count": 0,
            "forbidden_repository_prefixes": list(
                FORBIDDEN_PRIMARY_SOURCE_REPOSITORY_PREFIXES
            ),
            "forbidden_repository_source_count": 0,
            "policy_weight_admitted_source_count": 0,
        },
        "raw_recording_provenance_count": len(provenance_records),
        "canonical_corpus_source_ids": list(canonical_source_ids),
        "canonical_corpus_source_count": len(canonical_source_ids),
        "provenance_relation_count": (
            len(provenance_records) * len(canonical_source_ids)
        ),
        "covered_level_count": sum(
            _positive_integer(
                row["target_levels"],
                "D01A_RECORDING_TARGET_LEVELS",
            )
            for row in rows
        ),
        "covered_expected_action_count": sum(
            _positive_integer(
                row["expected_actions"],
                "D01A_RECORDING_EXPECTED_ACTIONS",
            )
            for row in rows
        ),
        "provenance_records": provenance_records,
        "raw_trajectory_to_s5_provenance_complete": True,
        "source_payload_access": {
            "payload_parse_count": 0,
            "replay_execution_count": 0,
            "source_execution_count": 0,
        },
        "gates": {
            "DG-00": "PASS",
            "DG-06": "PASS",
            "DG-09": "PASS",
        },
        "claim_boundary": (
            "Records ledger-declared metadata provenance and artifact-layer "
            "exclusion only; does not claim that the source manifest itself "
            "declares corpus targets, verify corpus payload derivation, freeze "
            "content or environment manifests, normalize trajectories, "
            "establish causal mechanisms, promote Rules, start Bridge or "
            "Runtime, or authorize official access or submission."
        ),
        "digest_excluded_fields": list(
            PROVENANCE_REPORT_DIGEST_EXCLUDED_FIELDS
        ),
        "content_digest": "",
    }
    report["content_digest"] = _digest(
        report,
        PROVENANCE_REPORT_DIGEST_NAMESPACE,
        excluded_fields=PROVENANCE_REPORT_DIGEST_EXCLUDED_FIELDS,
    )
    return report


def report_bytes(report: JsonObject) -> bytes:
    """Serialize a report deterministically with one final newline."""

    return (canonical_json(report) + "\n").encode("utf-8")


def write_source_inventory_report(
    report_path: Path,
    project_root: Path,
    *,
    repository_root: Path | None = None,
) -> JsonObject:
    """Write the canonical local PH-D01A inventory report."""

    report = build_source_inventory(
        project_root,
        repository_root=repository_root,
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_bytes(report_bytes(report))
    return report


def verify_source_inventory_report(
    report_path: Path,
    project_root: Path,
    *,
    repository_root: Path | None = None,
) -> JsonObject:
    """Fail closed unless the checked report is the exact current rebuild."""

    report = build_source_inventory(
        project_root,
        repository_root=repository_root,
    )
    try:
        expected = report_path.read_bytes()
    except OSError as exc:
        raise SourceInventoryError(
            f"D01A_REPORT_UNREADABLE:{report_path}"
        ) from exc
    if expected != report_bytes(report):
        raise SourceInventoryError(
            f"D01A_REPORT_MISMATCH:{report_path}"
        )
    return report


def write_primary_source_provenance_report(
    report_path: Path,
    project_root: Path,
    *,
    repository_root: Path | None = None,
) -> JsonObject:
    """Write the canonical PH-D01A primary-source provenance report."""

    report = build_primary_source_provenance_report(
        project_root,
        repository_root=repository_root,
    )
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_bytes(report_bytes(report))
    return report


def verify_primary_source_provenance_report(
    report_path: Path,
    project_root: Path,
    *,
    repository_root: Path | None = None,
) -> JsonObject:
    """Fail closed unless the checked provenance report is the exact rebuild."""

    report = build_primary_source_provenance_report(
        project_root,
        repository_root=repository_root,
    )
    try:
        expected = report_path.read_bytes()
    except OSError as exc:
        raise SourceInventoryError(
            f"D01A_PROVENANCE_REPORT_UNREADABLE:{report_path}"
        ) from exc
    if expected != report_bytes(report):
        raise SourceInventoryError(
            f"D01A_PROVENANCE_REPORT_MISMATCH:{report_path}"
        )
    return report


__all__ = [
    "ANSWER_VISIBILITIES",
    "CONTAMINATION_CLASSES",
    "DEVELOPMENT_USAGES",
    "MATERIALIZATION_STATES",
    "PROFILE_TYPES",
    "PROVENANCE_REPORT_DIGEST_EXCLUDED_FIELDS",
    "PROVENANCE_REPORT_DIGEST_NAMESPACE",
    "REPORT_DIGEST_EXCLUDED_FIELDS",
    "REPORT_DIGEST_NAMESPACE",
    "SOURCE_CODE_ACCESS_STATES",
    "SPLIT_ROLES",
    "SourceInventoryError",
    "build_primary_source_provenance_report",
    "build_source_inventory",
    "canonical_json",
    "report_bytes",
    "verify_primary_source_provenance_report",
    "verify_source_inventory_report",
    "write_primary_source_provenance_report",
    "write_source_inventory_report",
]
