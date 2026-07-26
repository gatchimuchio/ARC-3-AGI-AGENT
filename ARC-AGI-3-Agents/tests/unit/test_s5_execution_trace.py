from __future__ import annotations

import json
from pathlib import Path

import pytest

from arc3_agi_agent.s5_runner import (
    load_s5_execution_trace_manifest,
    write_s5_execution_trace_artifact,
)
from arc3_agi_agent.schema import digest_object


def _fixture() -> tuple[dict[str, object], dict[str, object]]:
    kernel_trace = [
        {
            "actor": "HDS",
            "details": [["status", "PASS"]],
            "index": 0,
            "operation": "CYCLE_BOUNDARY",
            "stage": "REFRAME",
        }
    ]
    event: dict[str, object] = {
        "action_id": 1,
        "action_index": 0,
        "after_observation_signature": "frame:after",
        "after_state": "WIN",
        "authority_decision_id": "decision:test",
        "before_state": "NOT_FINISHED",
        "candidates": [{}],
        "closures": [{}],
        "compute_memory_digest": "memory:test",
        "compute_memory_version": 0,
        "decision": {},
        "emission_result": {},
        "follow_up_authority_decision": None,
        "hds_status": "PASS",
        "hypotheses": [{}],
        "instruction_body_digest": "policy:test",
        "instruction_body_format": "fixture",
        "instruction_body_version": "policy-v1",
        "instruction_query_digest": "query:test",
        "kernel_trace": kernel_trace,
        "levels_completed": 1,
        "memory_influenced_decision": False,
        "memory_result": {},
        "memory_version": 1,
        "observation": {},
        "outcome_retained": False,
        "outcome_retention_result": None,
        "policy_reset": False,
        "policy_reset_execution": None,
        "trace_digest": digest_object(kernel_trace),
    }
    summary = {
        key: event[key]
        for key in (
            "action_id",
            "after_state",
            "authority_decision_id",
            "before_state",
            "hds_status",
            "instruction_query_digest",
            "levels_completed",
            "memory_version",
            "outcome_retained",
            "policy_reset",
            "trace_digest",
        )
    }
    report = {
        "actions_executed": 1,
        "complete": True,
        "completed_levels": 1,
        "game_id": "fixture-environment",
        "runtime_trace_digest": digest_object([summary]),
    }
    body: dict[str, object] = {
        "actions_executed": 1,
        "all_complete": True,
        "complete_inventory": True,
        "completed_levels": 1,
        "deterministic_seed": 0,
        "environment_count": 1,
        "instruction_body_digest": "policy:test",
        "instruction_body_version": "policy-v1",
        "reports": [report],
    }
    closure = {
        **body,
        "content_digest": (
            "arc3_s5_rendered_runtime_closure:"
            + digest_object(body)
        ),
    }
    return closure, event


def test_compressed_full_trace_is_bound_to_closure(
    tmp_path: Path,
) -> None:
    closure, event = _fixture()
    closure_path = tmp_path / "closure.json"
    closure_path.write_text(
        json.dumps(closure, sort_keys=True),
        encoding="utf-8",
    )
    trace_path = tmp_path / "S5_FULL_EXECUTION_TRACE.jsonl.gz"
    manifest_path = (
        tmp_path / "S5_FULL_EXECUTION_TRACE_MANIFEST.json"
    )

    manifest = write_s5_execution_trace_artifact(
        closure_report=closure,
        traced_games=(("fixture-environment", (event,)),),
        trace_jsonl_path=trace_path,
        trace_manifest_path=manifest_path,
        max_actions=4096,
    )
    loaded = load_s5_execution_trace_manifest(
        manifest_path,
        closure_path=closure_path,
    )

    assert loaded == manifest
    assert loaded["record_count"] == 1
    assert loaded["complete_execution_trace_coverage"] is True
    assert loaded["trace_format"] == "canonical-json-lines+gzip"

    trace_path.write_bytes(trace_path.read_bytes() + b"tamper")
    with pytest.raises(
        ValueError,
        match="S5_TRACE_FILE_DIGEST_INVALID",
    ):
        load_s5_execution_trace_manifest(
            manifest_path,
            closure_path=closure_path,
        )


def test_full_trace_rejects_missing_runtime_detail(
    tmp_path: Path,
) -> None:
    closure, event = _fixture()
    event.pop("observation")
    with pytest.raises(
        ValueError,
        match="S5_TRACE_FULL_FIELD_MISSING:observation",
    ):
        write_s5_execution_trace_artifact(
            closure_report=closure,
            traced_games=(("fixture-environment", (event,)),),
            trace_jsonl_path=tmp_path / "trace.jsonl.gz",
            trace_manifest_path=tmp_path / "manifest.json",
            max_actions=4096,
        )
