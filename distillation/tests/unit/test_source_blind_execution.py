from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, cast

import pytest

from hds_distill.source_blind_execution import (
    ROLE_ORDER,
    SourceBlindExecutionError,
    artifact_bytes,
    load_source_blind_execution_plan,
    validate_source_blind_execution_plan,
    validate_source_blind_execution_record,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PLAN_PATH = (
    REPOSITORY_ROOT
    / "distillation"
    / "input"
    / "source_blind_execution_plan.json"
)
RECORD_PATH = (
    REPOSITORY_ROOT
    / "distillation"
    / "artifacts"
    / "reports"
    / "source_blind_execution.json"
)


def _record() -> dict[str, Any]:
    value = json.loads(RECORD_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("source-blind record must be an object")
    return cast(dict[str, Any], value)


def test_checked_source_blind_evidence_is_canonical_and_plan_bound() -> None:
    plan = load_source_blind_execution_plan(PLAN_PATH)
    record = _record()

    validate_source_blind_execution_record(record, plan)

    assert RECORD_PATH.read_bytes() == artifact_bytes(record)
    assert record["plan_digest"] == plan["content_digest"]
    assert tuple(
        role["role_id"]
        for role in cast(list[dict[str, Any]], record["role_records"])
    ) == ROLE_ORDER


def test_role_projections_enforce_source_blind_asymmetry() -> None:
    plan = load_source_blind_execution_plan(PLAN_PATH)
    roles = {
        role["role_id"]: role
        for role in cast(list[dict[str, Any]], plan["roles"])
    }

    assert roles["REPLAY_HARNESS_MAINTAINER"][
        "environment_source_mount"
    ] is True
    assert roles["REPLAY_HARNESS_MAINTAINER"][
        "hypothesis_generation"
    ] is False
    assert roles["DISTILLATION_EXECUTOR"][
        "environment_source_mount"
    ] is False
    assert roles["DISTILLATION_EXECUTOR"][
        "hypothesis_generation"
    ] is True
    assert roles["DISTILLATION_AUDITOR"][
        "environment_source_mount"
    ] is False
    assert len(
        {
            role["process_identity"]
            for role in roles.values()
        }
    ) == 3
    assert len(
        {
            role["checkout_projection_digest"]
            for role in roles.values()
        }
    ) == 3


def test_plan_rejects_executor_environment_source_authority() -> None:
    plan = copy.deepcopy(load_source_blind_execution_plan(PLAN_PATH))
    roles = cast(list[dict[str, Any]], plan["roles"])
    executor = next(
        role
        for role in roles
        if role["role_id"] == "DISTILLATION_EXECUTOR"
    )
    executor["environment_source_access"] = True

    with pytest.raises(
        SourceBlindExecutionError,
        match="D01B_SOURCE_BLIND_ROLE_AUTHORITY_MISMATCH",
    ):
        validate_source_blind_execution_plan(plan)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("repository_root_visible", True),
        ("candidate_generation_count", 1),
        ("network_namespace_enforced", False),
    ],
)
def test_record_rejects_separation_evidence_tampering(
    field: str,
    value: object,
) -> None:
    plan = load_source_blind_execution_plan(PLAN_PATH)
    record = copy.deepcopy(_record())
    roles = cast(list[dict[str, Any]], record["role_records"])
    roles[1][field] = value

    with pytest.raises(
        SourceBlindExecutionError,
        match="D01B_SOURCE_BLIND_RECORD_PROBE_FAILURE",
    ):
        validate_source_blind_execution_record(record, plan)


def test_record_rejects_unknown_role_evidence_fields() -> None:
    plan = load_source_blind_execution_plan(PLAN_PATH)
    record = copy.deepcopy(_record())
    roles = cast(list[dict[str, Any]], record["role_records"])
    roles[0]["unreviewed"] = True

    with pytest.raises(
        SourceBlindExecutionError,
        match="D01B_SOURCE_BLIND_ROLE_RECORD_FIELDS",
    ):
        validate_source_blind_execution_record(record, plan)
