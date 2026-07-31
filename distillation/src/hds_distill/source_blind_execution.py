"""Strict PH-D01B source-blind role and process evidence.

The record built here is operational evidence, not a member of the later
38-schema HDS data inventory.  It binds role identity, checkout projection,
mount allowlists, access counts, and an external OS-namespace probe without
reading ARC payload semantics or generating a hypothesis.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Mapping, Sequence
from pathlib import Path, PurePosixPath
from typing import Final, cast

from hds_distill.source_inventory import (
    JsonObject,
    JsonValue,
    canonical_json,
)

PHASE_ID: Final = "PH-D01B"
PLAN_SCHEMA_VERSION: Final = "hds-source-blind-execution-plan-v1"
RECORD_SCHEMA_VERSION: Final = "hds-source-blind-execution-record-v1"
PLAN_DIGEST_NAMESPACE: Final = "hds-source-blind-execution-plan"
RECORD_DIGEST_NAMESPACE: Final = "hds-source-blind-execution-record"
PROCESS_IDENTITY_NAMESPACE: Final = "hds-source-blind-process-identity"
CHECKOUT_PROJECTION_NAMESPACE: Final = (
    "hds-source-blind-checkout-projection"
)
FRAME_DIGEST_NAMESPACE: Final = "rev3-work-block-frame"

ROLE_ORDER: Final = (
    "DISTILLATION_AUDITOR",
    "DISTILLATION_EXECUTOR",
    "REPLAY_HARNESS_MAINTAINER",
)
ENFORCEMENT_BACKEND: Final = "BUBBLEWRAP_USER_MOUNT_NETWORK_NAMESPACE"
PROBE_STATUS: Final = "PASS"
SHA256_PATTERN: Final = re.compile(r"^[0-9a-f]{64}$")

PLAN_FIELDS: Final = frozenset(
    {
        "schema_version",
        "phase_id",
        "frame_digest",
        "enforcement_backend",
        "bubblewrap",
        "probe_tool",
        "roles",
        "access_ledger",
        "phase_boundaries",
        "digest_excluded_fields",
        "content_digest",
    }
)
ROLE_FIELDS: Final = frozenset(
    {
        "role_id",
        "process_identity",
        "checkout_projection_digest",
        "mount_allowlist",
        "allowed_input_roles",
        "environment_source_access",
        "environment_source_mount",
        "hypothesis_generation",
        "source_access_count",
        "candidate_generation_count",
    }
)
MOUNT_FIELDS: Final = frozenset(
    {
        "target",
        "source_path",
        "source_digest",
        "access",
    }
)
ACCESS_FIELDS: Final = frozenset(
    {
        "event_id",
        "role_id",
        "operation",
        "source_kind",
        "access_count",
        "outcome",
    }
)
PROBE_RESULT_FIELDS: Final = frozenset(
    {
        "role_id",
        "process_instance_count",
        "mount_namespace_enforced",
        "network_namespace_enforced",
        "repository_root_visible",
        "environment_source_mount_observed",
        "mounted_targets",
        "read_only_targets",
        "mounted_file_read_count",
        "write_probe_denied_count",
        "probe_status",
    }
)
ROLE_RECORD_FIELDS: Final = PROBE_RESULT_FIELDS | frozenset(
    {
        "process_identity",
        "checkout_projection_digest",
        "allowed_input_roles",
        "source_access_count",
        "candidate_generation_count",
        "hypothesis_generation",
    }
)
RECORD_FIELDS: Final = frozenset(
    {
        "schema_version",
        "record_id",
        "phase_id",
        "plan_digest",
        "enforcement_backend",
        "bubblewrap_binary_sha256",
        "probe_tool_sha256",
        "role_records",
        "access_ledger",
        "separation_assertions",
        "phase_boundaries",
        "gates",
        "claim_boundary",
        "digest_excluded_fields",
        "content_digest",
    }
)


class SourceBlindExecutionError(ValueError):
    """Fail-closed source-blind contract or evidence error."""


def _object(value: object, code: str) -> JsonObject:
    if not isinstance(value, dict):
        raise SourceBlindExecutionError(code + "_NOT_OBJECT")
    return cast(JsonObject, value)


def _list(value: object, code: str) -> list[JsonValue]:
    if not isinstance(value, list):
        raise SourceBlindExecutionError(code + "_NOT_ARRAY")
    return cast(list[JsonValue], value)


def _string(value: object, code: str) -> str:
    if not isinstance(value, str) or not value:
        raise SourceBlindExecutionError(code + "_NOT_STRING")
    return value


def _integer(value: object, code: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise SourceBlindExecutionError(code + "_NOT_INTEGER")
    return value


def _boolean(value: object, code: str) -> bool:
    if not isinstance(value, bool):
        raise SourceBlindExecutionError(code + "_NOT_BOOLEAN")
    return value


def _strict_fields(
    value: Mapping[str, JsonValue],
    expected: frozenset[str],
    code: str,
) -> None:
    actual = frozenset(value)
    if actual != expected:
        missing = ",".join(sorted(expected - actual))
        extra = ",".join(sorted(actual - expected))
        raise SourceBlindExecutionError(
            f"{code}_FIELDS:missing={missing}:extra={extra}"
        )


def _sha256(value: object, code: str) -> str:
    text = _string(value, code)
    if SHA256_PATTERN.fullmatch(text) is None:
        raise SourceBlindExecutionError(code + "_INVALID")
    return text


def _bound_digest(value: object, namespace: str, code: str) -> str:
    text = _string(value, code)
    prefix = namespace + ":"
    if not text.startswith(prefix):
        raise SourceBlindExecutionError(code + "_NAMESPACE")
    _sha256(text.removeprefix(prefix), code)
    return text


def _any_bound_digest(value: object, code: str) -> str:
    text = _string(value, code)
    namespace, separator, digest = text.partition(":")
    if not separator or not namespace:
        raise SourceBlindExecutionError(code + "_NAMESPACE")
    _sha256(digest, code)
    return text


def _digest(
    value: Mapping[str, JsonValue],
    namespace: str,
    *,
    excluded_fields: Sequence[str],
) -> str:
    excluded = set(excluded_fields)
    body = {key: item for key, item in value.items() if key not in excluded}
    return (
        namespace
        + ":"
        + hashlib.sha256(canonical_json(body).encode("utf-8")).hexdigest()
    )


def _relative_posix_path(value: object, code: str) -> str:
    text = _string(value, code)
    path = PurePosixPath(text)
    if (
        "\\" in text
        or "\x00" in text
        or path.is_absolute()
        or text != path.as_posix()
        or any(part in {"", ".", ".."} for part in path.parts)
    ):
        raise SourceBlindExecutionError(code + "_NOT_RELATIVE_POSIX")
    return text


def _absolute_posix_path(value: object, code: str) -> str:
    text = _string(value, code)
    path = PurePosixPath(text)
    if (
        "\\" in text
        or "\x00" in text
        or not path.is_absolute()
        or text != path.as_posix()
        or any(part in {"", ".", ".."} for part in path.parts[1:])
    ):
        raise SourceBlindExecutionError(code + "_NOT_ABSOLUTE_POSIX")
    return text


def _string_list(value: object, code: str) -> list[str]:
    return [_string(item, code + "_ITEM") for item in _list(value, code)]


def _role_without_bound_ids(role: Mapping[str, JsonValue]) -> JsonObject:
    return {
        key: item
        for key, item in role.items()
        if key not in {"process_identity", "checkout_projection_digest"}
    }


def _expected_process_identity(role: Mapping[str, JsonValue]) -> str:
    body = {
        "role_id": role["role_id"],
        "checkout_projection_digest": role["checkout_projection_digest"],
        "mount_allowlist": role["mount_allowlist"],
        "allowed_input_roles": role["allowed_input_roles"],
        "environment_source_access": role["environment_source_access"],
        "environment_source_mount": role["environment_source_mount"],
        "hypothesis_generation": role["hypothesis_generation"],
    }
    return _digest(
        body,
        PROCESS_IDENTITY_NAMESPACE,
        excluded_fields=(),
    )


def _expected_checkout_projection(role: Mapping[str, JsonValue]) -> str:
    body = _role_without_bound_ids(role)
    return _digest(
        body,
        CHECKOUT_PROJECTION_NAMESPACE,
        excluded_fields=(),
    )


def _validate_role(role: Mapping[str, JsonValue]) -> None:
    _strict_fields(role, ROLE_FIELDS, "D01B_SOURCE_BLIND_ROLE")
    role_id = _string(role["role_id"], "D01B_SOURCE_BLIND_ROLE_ID")
    mounts = [
        _object(item, "D01B_SOURCE_BLIND_MOUNT")
        for item in _list(
            role["mount_allowlist"],
            "D01B_SOURCE_BLIND_MOUNTS",
        )
    ]
    targets: list[str] = []
    for mount in mounts:
        _strict_fields(mount, MOUNT_FIELDS, "D01B_SOURCE_BLIND_MOUNT")
        targets.append(
            _absolute_posix_path(
                mount["target"],
                "D01B_SOURCE_BLIND_MOUNT_TARGET",
            )
        )
        _relative_posix_path(
            mount["source_path"],
            "D01B_SOURCE_BLIND_MOUNT_SOURCE",
        )
        _any_bound_digest(
            mount["source_digest"],
            "D01B_SOURCE_BLIND_MOUNT_DIGEST",
        )
        if mount["access"] != "READ_ONLY":
            raise SourceBlindExecutionError(
                "D01B_SOURCE_BLIND_MOUNT_NOT_READ_ONLY"
            )
    if targets != sorted(targets) or len(targets) != len(set(targets)):
        raise SourceBlindExecutionError(
            "D01B_SOURCE_BLIND_MOUNT_ORDER_OR_DUPLICATE"
        )
    inputs = _string_list(
        role["allowed_input_roles"],
        "D01B_SOURCE_BLIND_ALLOWED_INPUT_ROLES",
    )
    if inputs != sorted(inputs) or len(inputs) != len(set(inputs)):
        raise SourceBlindExecutionError(
            "D01B_SOURCE_BLIND_INPUT_ROLE_ORDER_OR_DUPLICATE"
        )
    environment_source_access = _boolean(
        role["environment_source_access"],
        "D01B_SOURCE_BLIND_ENVIRONMENT_ACCESS",
    )
    environment_source_mount = _boolean(
        role["environment_source_mount"],
        "D01B_SOURCE_BLIND_ENVIRONMENT_MOUNT",
    )
    hypothesis_generation = _boolean(
        role["hypothesis_generation"],
        "D01B_SOURCE_BLIND_HYPOTHESIS_GENERATION",
    )
    source_access_count = _integer(
        role["source_access_count"],
        "D01B_SOURCE_BLIND_SOURCE_ACCESS_COUNT",
    )
    candidate_generation_count = _integer(
        role["candidate_generation_count"],
        "D01B_SOURCE_BLIND_CANDIDATE_GENERATION_COUNT",
    )
    if source_access_count < 0 or candidate_generation_count != 0:
        raise SourceBlindExecutionError(
            "D01B_SOURCE_BLIND_ACCESS_OR_CANDIDATE_COUNT"
        )
    expected = {
        "DISTILLATION_AUDITOR": (False, False, False, 0),
        "DISTILLATION_EXECUTOR": (False, False, True, 0),
        "REPLAY_HARNESS_MAINTAINER": (True, True, False, 50),
    }
    if role_id not in expected or (
        environment_source_access,
        environment_source_mount,
        hypothesis_generation,
        source_access_count,
    ) != expected[role_id]:
        raise SourceBlindExecutionError(
            "D01B_SOURCE_BLIND_ROLE_AUTHORITY_MISMATCH:" + role_id
        )
    if role["checkout_projection_digest"] != _expected_checkout_projection(
        role
    ):
        raise SourceBlindExecutionError(
            "D01B_SOURCE_BLIND_CHECKOUT_DIGEST_MISMATCH"
        )
    if role["process_identity"] != _expected_process_identity(role):
        raise SourceBlindExecutionError(
            "D01B_SOURCE_BLIND_PROCESS_IDENTITY_MISMATCH"
        )
    if role_id != "REPLAY_HARNESS_MAINTAINER" and any(
        str(mount["source_path"]).startswith("environment_files")
        for mount in mounts
    ):
        raise SourceBlindExecutionError(
            "D01B_SOURCE_BLIND_ENVIRONMENT_SOURCE_LEAK"
        )


def validate_source_blind_execution_plan(
    plan: Mapping[str, JsonValue],
) -> None:
    """Validate one closed source-blind role and projection contract."""

    _strict_fields(plan, PLAN_FIELDS, "D01B_SOURCE_BLIND_PLAN")
    if (
        plan["schema_version"] != PLAN_SCHEMA_VERSION
        or plan["phase_id"] != PHASE_ID
        or plan["enforcement_backend"] != ENFORCEMENT_BACKEND
    ):
        raise SourceBlindExecutionError(
            "D01B_SOURCE_BLIND_PLAN_SCHEMA_PHASE_OR_BACKEND"
        )
    _bound_digest(
        plan["frame_digest"],
        FRAME_DIGEST_NAMESPACE,
        "D01B_SOURCE_BLIND_FRAME_DIGEST",
    )
    bubblewrap = _object(
        plan["bubblewrap"],
        "D01B_SOURCE_BLIND_BUBBLEWRAP",
    )
    _strict_fields(
        bubblewrap,
        frozenset({"path", "sha256"}),
        "D01B_SOURCE_BLIND_BUBBLEWRAP",
    )
    if bubblewrap["path"] != "/usr/bin/bwrap":
        raise SourceBlindExecutionError(
            "D01B_SOURCE_BLIND_BUBBLEWRAP_PATH"
        )
    _sha256(
        bubblewrap["sha256"],
        "D01B_SOURCE_BLIND_BUBBLEWRAP_SHA256",
    )
    probe_tool = _object(
        plan["probe_tool"],
        "D01B_SOURCE_BLIND_PROBE_TOOL",
    )
    _strict_fields(
        probe_tool,
        frozenset({"path", "sha256"}),
        "D01B_SOURCE_BLIND_PROBE_TOOL",
    )
    _relative_posix_path(
        probe_tool["path"],
        "D01B_SOURCE_BLIND_PROBE_TOOL_PATH",
    )
    _sha256(
        probe_tool["sha256"],
        "D01B_SOURCE_BLIND_PROBE_TOOL_SHA256",
    )
    roles = [
        _object(item, "D01B_SOURCE_BLIND_ROLE")
        for item in _list(plan["roles"], "D01B_SOURCE_BLIND_ROLES")
    ]
    role_ids = [
        _string(role["role_id"], "D01B_SOURCE_BLIND_ROLE_ID")
        for role in roles
    ]
    if tuple(role_ids) != ROLE_ORDER:
        raise SourceBlindExecutionError("D01B_SOURCE_BLIND_ROLE_ORDER")
    for role in roles:
        _validate_role(role)
    ledger = [
        _object(item, "D01B_SOURCE_BLIND_ACCESS")
        for item in _list(
            plan["access_ledger"],
            "D01B_SOURCE_BLIND_ACCESS_LEDGER",
        )
    ]
    event_ids: list[str] = []
    for entry in ledger:
        _strict_fields(entry, ACCESS_FIELDS, "D01B_SOURCE_BLIND_ACCESS")
        event_ids.append(
            _string(
                entry["event_id"],
                "D01B_SOURCE_BLIND_ACCESS_EVENT_ID",
            )
        )
        if entry["role_id"] not in ROLE_ORDER:
            raise SourceBlindExecutionError(
                "D01B_SOURCE_BLIND_ACCESS_ROLE"
            )
        _string(entry["operation"], "D01B_SOURCE_BLIND_ACCESS_OPERATION")
        _string(entry["source_kind"], "D01B_SOURCE_BLIND_ACCESS_KIND")
        if (
            _integer(
                entry["access_count"],
                "D01B_SOURCE_BLIND_ACCESS_COUNT",
            )
            < 0
            or entry["outcome"] != "ALLOWED_BY_ROLE_CONTRACT"
        ):
            raise SourceBlindExecutionError(
                "D01B_SOURCE_BLIND_ACCESS_INVALID"
            )
    if event_ids != sorted(event_ids) or len(event_ids) != len(set(event_ids)):
        raise SourceBlindExecutionError(
            "D01B_SOURCE_BLIND_ACCESS_ORDER_OR_DUPLICATE"
        )
    boundaries = _object(
        plan["phase_boundaries"],
        "D01B_SOURCE_BLIND_PHASE_BOUNDARIES",
    )
    expected_boundaries: JsonObject = {
        "candidate_generation_started": False,
        "hds_hypothesis_generation_started": False,
        "trajectory_normalization_started": False,
        "bridge_started": False,
        "runtime_started": False,
        "official_access_count": 0,
        "kaggle_mutation_count": 0,
    }
    if boundaries != expected_boundaries:
        raise SourceBlindExecutionError(
            "D01B_SOURCE_BLIND_PHASE_BOUNDARY"
        )
    excluded = _string_list(
        plan["digest_excluded_fields"],
        "D01B_SOURCE_BLIND_PLAN_EXCLUDED_FIELDS",
    )
    if excluded != ["content_digest"]:
        raise SourceBlindExecutionError(
            "D01B_SOURCE_BLIND_PLAN_EXCLUDED_FIELDS_INVALID"
        )
    claimed = _bound_digest(
        plan["content_digest"],
        PLAN_DIGEST_NAMESPACE,
        "D01B_SOURCE_BLIND_PLAN_DIGEST",
    )
    if claimed != _digest(
        plan,
        PLAN_DIGEST_NAMESPACE,
        excluded_fields=excluded,
    ):
        raise SourceBlindExecutionError(
            "D01B_SOURCE_BLIND_PLAN_DIGEST_MISMATCH"
        )


def load_source_blind_execution_plan(path: Path) -> JsonObject:
    """Read and validate a source-blind execution plan."""

    try:
        decoded = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceBlindExecutionError(
            f"D01B_SOURCE_BLIND_PLAN_UNREADABLE:{path}"
        ) from exc
    plan = _object(decoded, "D01B_SOURCE_BLIND_PLAN")
    validate_source_blind_execution_plan(plan)
    return plan


def build_source_blind_execution_record(
    plan: Mapping[str, JsonValue],
    *,
    probe_results: Sequence[Mapping[str, JsonValue]],
    probe_tool_sha256: str,
) -> JsonObject:
    """Build deterministic evidence from three successful OS probes."""

    validate_source_blind_execution_plan(plan)
    expected_tool = _object(
        plan["probe_tool"],
        "D01B_SOURCE_BLIND_PROBE_TOOL",
    )["sha256"]
    if _sha256(
        probe_tool_sha256,
        "D01B_SOURCE_BLIND_PROBE_TOOL_SHA256",
    ) != expected_tool:
        raise SourceBlindExecutionError(
            "D01B_SOURCE_BLIND_PROBE_TOOL_DRIFT"
        )
    role_plan = {
        _string(role["role_id"], "D01B_SOURCE_BLIND_ROLE_ID"): role
        for role in (
            _object(item, "D01B_SOURCE_BLIND_ROLE")
            for item in _list(plan["roles"], "D01B_SOURCE_BLIND_ROLES")
        )
    }
    role_records: list[JsonObject] = []
    for result_value in probe_results:
        result = dict(result_value)
        _strict_fields(result, PROBE_RESULT_FIELDS, "D01B_SOURCE_BLIND_PROBE")
        role_id = _string(
            result["role_id"],
            "D01B_SOURCE_BLIND_PROBE_ROLE",
        )
        role = role_plan.get(role_id)
        if role is None:
            raise SourceBlindExecutionError(
                "D01B_SOURCE_BLIND_PROBE_UNKNOWN_ROLE"
            )
        expected_targets = [
            _string(mount["target"], "D01B_SOURCE_BLIND_MOUNT_TARGET")
            for mount in (
                _object(item, "D01B_SOURCE_BLIND_MOUNT")
                for item in _list(
                    role["mount_allowlist"],
                    "D01B_SOURCE_BLIND_MOUNTS",
                )
            )
        ]
        mounted_targets = _string_list(
            result["mounted_targets"],
            "D01B_SOURCE_BLIND_PROBE_TARGETS",
        )
        read_only_targets = _string_list(
            result["read_only_targets"],
            "D01B_SOURCE_BLIND_PROBE_READ_ONLY_TARGETS",
        )
        if (
            mounted_targets != expected_targets
            or read_only_targets != expected_targets
            or result["probe_status"] != PROBE_STATUS
            or _integer(
                result["process_instance_count"],
                "D01B_SOURCE_BLIND_PROCESS_COUNT",
            )
            != 1
            or not _boolean(
                result["mount_namespace_enforced"],
                "D01B_SOURCE_BLIND_MOUNT_NAMESPACE",
            )
            or not _boolean(
                result["network_namespace_enforced"],
                "D01B_SOURCE_BLIND_NETWORK_NAMESPACE",
            )
            or _boolean(
                result["repository_root_visible"],
                "D01B_SOURCE_BLIND_REPOSITORY_VISIBLE",
            )
            or _boolean(
                result["environment_source_mount_observed"],
                "D01B_SOURCE_BLIND_ENVIRONMENT_MOUNT_OBSERVED",
            )
            is not role["environment_source_mount"]
            or _integer(
                result["write_probe_denied_count"],
                "D01B_SOURCE_BLIND_WRITE_DENIED_COUNT",
            )
            != len(expected_targets)
        ):
            raise SourceBlindExecutionError(
                "D01B_SOURCE_BLIND_PROBE_ASSERTION_FAILED:" + role_id
            )
        mounted_file_read_count = _integer(
            result["mounted_file_read_count"],
            "D01B_SOURCE_BLIND_MOUNTED_FILE_READ_COUNT",
        )
        if mounted_file_read_count <= 0:
            raise SourceBlindExecutionError(
                "D01B_SOURCE_BLIND_PROBE_NO_READ:" + role_id
            )
        role_records.append(
            {
                **result,
                "process_identity": role["process_identity"],
                "checkout_projection_digest": role[
                    "checkout_projection_digest"
                ],
                "allowed_input_roles": role["allowed_input_roles"],
                "source_access_count": role["source_access_count"],
                "candidate_generation_count": role[
                    "candidate_generation_count"
                ],
                "hypothesis_generation": role[
                    "hypothesis_generation"
                ],
            }
        )
    if tuple(record["role_id"] for record in role_records) != ROLE_ORDER:
        raise SourceBlindExecutionError(
            "D01B_SOURCE_BLIND_PROBE_ROLE_ORDER"
        )
    record: JsonObject = {
        "schema_version": RECORD_SCHEMA_VERSION,
        "record_id": "PH-D01B-SOURCE-BLIND-EXECUTION-20260731",
        "phase_id": PHASE_ID,
        "plan_digest": plan["content_digest"],
        "enforcement_backend": plan["enforcement_backend"],
        "bubblewrap_binary_sha256": _object(
            plan["bubblewrap"],
            "D01B_SOURCE_BLIND_BUBBLEWRAP",
        )["sha256"],
        "probe_tool_sha256": probe_tool_sha256,
        "role_records": cast(JsonValue, role_records),
        "access_ledger": plan["access_ledger"],
        "separation_assertions": {
            "role_count": 3,
            "distinct_process_identity_count": 3,
            "distinct_checkout_projection_count": 3,
            "distillation_executor_environment_source_mount_count": 0,
            "distillation_auditor_environment_source_mount_count": 0,
            "same_process_source_access_then_candidate_generation_count": 0,
            "source_blind_execution_contract_established": True,
            "candidate_execution_status": "NOT_STARTED_PHASE_D01B",
        },
        "phase_boundaries": plan["phase_boundaries"],
        "gates": {
            "DG-00": "PASS",
            "DG-06": "PASS",
            "DG-12": "PASS",
        },
        "claim_boundary": (
            "Establishes the three role projections and OS mount/network "
            "namespace probe only. No candidate, hypothesis, trajectory "
            "normalization, Rule, Bridge, Runtime, official, or submission "
            "claim is established."
        ),
        "digest_excluded_fields": [
            "content_digest",
            "record_id",
        ],
        "content_digest": "",
    }
    record["content_digest"] = _digest(
        record,
        RECORD_DIGEST_NAMESPACE,
        excluded_fields=("content_digest", "record_id"),
    )
    validate_source_blind_execution_record(record, plan)
    return record


def validate_source_blind_execution_record(
    record: Mapping[str, JsonValue],
    plan: Mapping[str, JsonValue],
) -> None:
    """Validate a checked source-blind record and its plan binding."""

    validate_source_blind_execution_plan(plan)
    _strict_fields(record, RECORD_FIELDS, "D01B_SOURCE_BLIND_RECORD")
    if (
        record["schema_version"] != RECORD_SCHEMA_VERSION
        or record["phase_id"] != PHASE_ID
        or record["plan_digest"] != plan["content_digest"]
        or record["enforcement_backend"] != ENFORCEMENT_BACKEND
    ):
        raise SourceBlindExecutionError(
            "D01B_SOURCE_BLIND_RECORD_SCHEMA_PHASE_OR_PLAN"
        )
    _string(record["record_id"], "D01B_SOURCE_BLIND_RECORD_ID")
    if record["bubblewrap_binary_sha256"] != _object(
        plan["bubblewrap"],
        "D01B_SOURCE_BLIND_BUBBLEWRAP",
    )["sha256"]:
        raise SourceBlindExecutionError(
            "D01B_SOURCE_BLIND_BUBBLEWRAP_DRIFT"
        )
    if record["probe_tool_sha256"] != _object(
        plan["probe_tool"],
        "D01B_SOURCE_BLIND_PROBE_TOOL",
    )["sha256"]:
        raise SourceBlindExecutionError(
            "D01B_SOURCE_BLIND_PROBE_TOOL_DRIFT"
        )
    role_records = [
        _object(item, "D01B_SOURCE_BLIND_ROLE_RECORD")
        for item in _list(
            record["role_records"],
            "D01B_SOURCE_BLIND_ROLE_RECORDS",
        )
    ]
    record_roles = [
        _string(item["role_id"], "D01B_SOURCE_BLIND_ROLE_ID")
        for item in role_records
    ]
    if tuple(record_roles) != ROLE_ORDER:
        raise SourceBlindExecutionError(
            "D01B_SOURCE_BLIND_RECORD_ROLE_ORDER"
        )
    planned_roles = {
        _string(role["role_id"], "D01B_SOURCE_BLIND_ROLE_ID"): role
        for role in (
            _object(item, "D01B_SOURCE_BLIND_ROLE")
            for item in _list(plan["roles"], "D01B_SOURCE_BLIND_ROLES")
        )
    }
    identities = {
        _bound_digest(
            item["process_identity"],
            PROCESS_IDENTITY_NAMESPACE,
            "D01B_SOURCE_BLIND_PROCESS_IDENTITY",
        )
        for item in role_records
    }
    projections = {
        _bound_digest(
            item["checkout_projection_digest"],
            CHECKOUT_PROJECTION_NAMESPACE,
            "D01B_SOURCE_BLIND_CHECKOUT_PROJECTION",
        )
        for item in role_records
    }
    for item in role_records:
        _strict_fields(
            item,
            ROLE_RECORD_FIELDS,
            "D01B_SOURCE_BLIND_ROLE_RECORD",
        )
        role_id = _string(
            item["role_id"],
            "D01B_SOURCE_BLIND_ROLE_ID",
        )
        planned = planned_roles[role_id]
        planned_mounts = [
            _object(value, "D01B_SOURCE_BLIND_MOUNT")
            for value in _list(
                planned["mount_allowlist"],
                "D01B_SOURCE_BLIND_MOUNTS",
            )
        ]
        planned_targets = [
            _string(
                mount["target"],
                "D01B_SOURCE_BLIND_MOUNT_TARGET",
            )
            for mount in planned_mounts
        ]
        expected_read_count = (
            _integer(
                planned["source_access_count"],
                "D01B_SOURCE_BLIND_SOURCE_ACCESS_COUNT",
            )
            if role_id == "REPLAY_HARNESS_MAINTAINER"
            else len(planned_targets)
        )
        if (
            item.get("probe_status") != PROBE_STATUS
            or item.get("repository_root_visible") is not False
            or item.get("mount_namespace_enforced") is not True
            or item.get("network_namespace_enforced") is not True
            or item.get("environment_source_mount_observed")
            is not planned["environment_source_mount"]
            or item.get("mounted_targets") != planned_targets
            or item.get("read_only_targets") != planned_targets
            or item.get("mounted_file_read_count") != expected_read_count
            or item.get("write_probe_denied_count")
            != len(planned_targets)
            or item.get("process_instance_count") != 1
            or item.get("process_identity")
            != planned["process_identity"]
            or item.get("checkout_projection_digest")
            != planned["checkout_projection_digest"]
            or item.get("allowed_input_roles")
            != planned["allowed_input_roles"]
            or item.get("source_access_count")
            != planned["source_access_count"]
            or item.get("candidate_generation_count") != 0
            or item.get("candidate_generation_count")
            != planned["candidate_generation_count"]
            or item.get("hypothesis_generation")
            != planned["hypothesis_generation"]
        ):
            raise SourceBlindExecutionError(
                "D01B_SOURCE_BLIND_RECORD_PROBE_FAILURE"
            )
    assertions = _object(
        record["separation_assertions"],
        "D01B_SOURCE_BLIND_ASSERTIONS",
    )
    expected_assertions: JsonObject = {
        "role_count": 3,
        "distinct_process_identity_count": 3,
        "distinct_checkout_projection_count": 3,
        "distillation_executor_environment_source_mount_count": 0,
        "distillation_auditor_environment_source_mount_count": 0,
        "same_process_source_access_then_candidate_generation_count": 0,
        "source_blind_execution_contract_established": True,
        "candidate_execution_status": "NOT_STARTED_PHASE_D01B",
    }
    if (
        assertions != expected_assertions
        or len(identities) != 3
        or len(projections) != 3
        or record["access_ledger"] != plan["access_ledger"]
        or record["phase_boundaries"] != plan["phase_boundaries"]
        or record["gates"]
        != {"DG-00": "PASS", "DG-06": "PASS", "DG-12": "PASS"}
    ):
        raise SourceBlindExecutionError(
            "D01B_SOURCE_BLIND_SEPARATION_ASSERTION"
        )
    _string(
        record["claim_boundary"],
        "D01B_SOURCE_BLIND_CLAIM_BOUNDARY",
    )
    excluded = _string_list(
        record["digest_excluded_fields"],
        "D01B_SOURCE_BLIND_RECORD_EXCLUDED_FIELDS",
    )
    if excluded != ["content_digest", "record_id"]:
        raise SourceBlindExecutionError(
            "D01B_SOURCE_BLIND_RECORD_EXCLUDED_FIELDS_INVALID"
        )
    claimed = _bound_digest(
        record["content_digest"],
        RECORD_DIGEST_NAMESPACE,
        "D01B_SOURCE_BLIND_RECORD_DIGEST",
    )
    if claimed != _digest(
        record,
        RECORD_DIGEST_NAMESPACE,
        excluded_fields=excluded,
    ):
        raise SourceBlindExecutionError(
            "D01B_SOURCE_BLIND_RECORD_DIGEST_MISMATCH"
        )


def artifact_bytes(value: Mapping[str, JsonValue]) -> bytes:
    """Return canonical checked-artifact bytes."""

    return (canonical_json(dict(value)) + "\n").encode("utf-8")


def verify_source_blind_execution_record(
    plan_path: Path,
    record_path: Path,
    *,
    probe_tool_path: Path,
    bubblewrap_path: Path,
) -> JsonObject:
    """Verify checked bytes and both executable hashes without probing."""

    plan = load_source_blind_execution_plan(plan_path)
    probe_tool_sha256 = hashlib.sha256(probe_tool_path.read_bytes()).hexdigest()
    bubblewrap_sha256 = hashlib.sha256(bubblewrap_path.read_bytes()).hexdigest()
    if probe_tool_sha256 != _object(
        plan["probe_tool"],
        "D01B_SOURCE_BLIND_PROBE_TOOL",
    )["sha256"]:
        raise SourceBlindExecutionError(
            "D01B_SOURCE_BLIND_PROBE_TOOL_DRIFT"
        )
    if bubblewrap_sha256 != _object(
        plan["bubblewrap"],
        "D01B_SOURCE_BLIND_BUBBLEWRAP",
    )["sha256"]:
        raise SourceBlindExecutionError(
            "D01B_SOURCE_BLIND_BUBBLEWRAP_DRIFT"
        )
    try:
        checked_bytes = record_path.read_bytes()
        decoded = json.loads(checked_bytes.decode("utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise SourceBlindExecutionError(
            f"D01B_SOURCE_BLIND_RECORD_UNREADABLE:{record_path}"
        ) from exc
    record = _object(decoded, "D01B_SOURCE_BLIND_RECORD")
    validate_source_blind_execution_record(record, plan)
    if checked_bytes != artifact_bytes(record):
        raise SourceBlindExecutionError(
            "D01B_SOURCE_BLIND_RECORD_NONCANONICAL"
        )
    return record


__all__ = [
    "CHECKOUT_PROJECTION_NAMESPACE",
    "ENFORCEMENT_BACKEND",
    "PLAN_DIGEST_NAMESPACE",
    "PHASE_ID",
    "PROCESS_IDENTITY_NAMESPACE",
    "RECORD_DIGEST_NAMESPACE",
    "ROLE_ORDER",
    "SourceBlindExecutionError",
    "artifact_bytes",
    "build_source_blind_execution_record",
    "load_source_blind_execution_plan",
    "validate_source_blind_execution_plan",
    "validate_source_blind_execution_record",
    "verify_source_blind_execution_record",
]
