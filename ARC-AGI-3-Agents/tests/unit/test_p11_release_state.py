from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from arc3_agi_agent.s5_runner import (
    write_s5_execution_trace_artifact,
)
from arc3_agi_agent.schema import digest_object
from arc3_agi_agent.teacher.p11_regression import (
    _SECRET_PATTERNS,
    P10_REPRODUCIBILITY_AUDIT_DIGEST_PREFIX,
    compile_p10_reproducibility_audit,
    load_p10_reproducibility_audit,
)
from arc3_agi_agent.teacher.p11_release import (
    P11_RELEASE_STATE_DIGEST_PREFIX,
    P11_RELEASE_STATE_SCHEMA_VERSION,
    inspect_reproducible_wheels,
    load_p11_release_state,
    p11_initial_state_descriptors,
)


def _digest_report(
    body: dict[str, object],
    prefix: str,
) -> dict[str, object]:
    return {
        **body,
        "content_digest": prefix + digest_object(body),
    }


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, sort_keys=True),
        encoding="utf-8",
    )


def _s5_trace_event(
    *,
    completed_levels: int,
) -> dict[str, object]:
    kernel_trace = [
        {
            "actor": "HDS",
            "details": [["status", "PASS"]],
            "index": 0,
            "operation": "CYCLE_BOUNDARY",
            "stage": "REFRAME",
        }
    ]
    return {
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
        "levels_completed": completed_levels,
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


def _runtime_summary(
    event: dict[str, object],
) -> dict[str, object]:
    return {
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


def test_secret_scan_does_not_treat_embedded_task_suffix_as_key() -> None:
    openai_style_pattern = _SECRET_PATTERNS[0]
    task_identifier = b"H47-promote-ta" + b"sk-" + (b"x" * 24)
    key_assignment = b"OPENAI_API_KEY=" + b"sk-" + (b"x" * 24)

    assert openai_style_pattern.search(task_identifier) is None
    assert openai_style_pattern.search(key_assignment) is not None


def test_p10_reproducibility_audit_requires_exact_s5_and_s6_bytes(
    tmp_path: Path,
) -> None:
    s5_body: dict[str, object] = {
        "actions_executed": 25,
        "all_complete": True,
        "complete_inventory": True,
        "completed_levels": 183,
        "environment_count": 25,
        "error_count": 0,
        "deterministic_seed": 0,
        "instruction_body_digest": "policy:test",
        "instruction_body_version": "policy-v1",
    }
    traced_games: list[
        tuple[str, tuple[dict[str, object], ...]]
    ] = []
    reports: list[dict[str, object]] = []
    for ordinal in range(25):
        completed_levels = 8 if ordinal < 8 else 7
        event = _s5_trace_event(
            completed_levels=completed_levels
        )
        environment = f"environment-{ordinal:02d}"
        traced_games.append((environment, (event,)))
        reports.append(
            {
                "actions_executed": 1,
                "complete": True,
                "completed_levels": completed_levels,
                "game_id": environment,
                "runtime_trace_digest": digest_object(
                    [_runtime_summary(event)]
                ),
            }
        )
    s5_body["reports"] = reports
    s6_body: dict[str, object] = {
        "status": "COMPLETE",
        "covered_level_count": 183,
        "covered_game_count": 25,
        "total_measurement_count": 14_336,
        "exception_count": 0,
        "generalization_claim": "MEASURED_NOT_PROVEN",
    }
    s5 = _digest_report(
        s5_body,
        "arc3_s5_rendered_runtime_closure:",
    )
    s6 = _digest_report(
        s6_body,
        "arc3_s6_perturbation_measurement:",
    )
    paths = {
        name: tmp_path / f"{name}.json"
        for name in ("s5_primary", "s5_reproduction", "s6_primary", "s6_reproduction")
    }
    for name in ("s5_primary", "s5_reproduction"):
        _write_json(paths[name], s5)
    for name in ("s6_primary", "s6_reproduction"):
        _write_json(paths[name], s6)
    trace_manifest_paths: dict[str, Path] = {}
    for label in ("primary", "reproduction"):
        directory = tmp_path / f"trace-{label}"
        trace_path = (
            directory / "S5_FULL_EXECUTION_TRACE.jsonl.gz"
        )
        manifest_path = (
            directory
            / "S5_FULL_EXECUTION_TRACE_MANIFEST.json"
        )
        write_s5_execution_trace_artifact(
            closure_report=s5,
            traced_games=traced_games,
            trace_jsonl_path=trace_path,
            trace_manifest_path=manifest_path,
            max_actions=4096,
        )
        trace_manifest_paths[label] = manifest_path

    report = compile_p10_reproducibility_audit(
        s5_primary_path=paths["s5_primary"],
        s5_reproduction_path=paths["s5_reproduction"],
        s5_trace_primary_manifest_path=(
            trace_manifest_paths["primary"]
        ),
        s5_trace_reproduction_manifest_path=(
            trace_manifest_paths["reproduction"]
        ),
        s6_primary_path=paths["s6_primary"],
        s6_reproduction_path=paths["s6_reproduction"],
    )

    assert report["status"] == "PASS"
    assert report["s5_byte_equal"] is True
    assert report["s6_byte_equal"] is True
    output = tmp_path / "audit.json"
    _write_json(output, report)
    loaded = load_p10_reproducibility_audit(output)
    assert loaded["content_digest"].startswith(
        P10_REPRODUCIBILITY_AUDIT_DIGEST_PREFIX
    )

    paths["s6_reproduction"].write_text(
        paths["s6_reproduction"].read_text(encoding="utf-8") + "\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="S6_PERTURBATION_MEASUREMENT_BYTE_MISMATCH"):
        compile_p10_reproducibility_audit(
            s5_primary_path=paths["s5_primary"],
            s5_reproduction_path=paths["s5_reproduction"],
            s5_trace_primary_manifest_path=(
                trace_manifest_paths["primary"]
            ),
            s5_trace_reproduction_manifest_path=(
                trace_manifest_paths["reproduction"]
            ),
            s6_primary_path=paths["s6_primary"],
            s6_reproduction_path=paths["s6_reproduction"],
        )


def test_p11_initial_state_is_empty_versioned_and_identity_free() -> None:
    states = p11_initial_state_descriptors()

    assert states["P0"]["body_version"] == "s5-rendered-history-mlp-v1"
    assert states["P0"]["parameter_count"] == 4_269_485
    assert states["P0"]["runtime_identity_free"] is True
    assert (
        states["P0"]["runtime_artifact_contains_training_examples"]
        is False
    )
    assert not any(states["J0"]["initial_counts"].values())
    assert states["M0"]["version"] == 0
    assert states["M0"]["active_entry_count"] == 0
    assert states["M0"]["archive_entry_count"] == 0
    assert states["M0"]["retained_snapshot_versions"] == [0]


def test_release_state_requires_full_execution_trace_claim(
    tmp_path: Path,
) -> None:
    body: dict[str, object] = {
        "schema_version": P11_RELEASE_STATE_SCHEMA_VERSION,
        "status": "P11_RELEASE_STATE_FIXED",
        "operation_mode": "offline",
        "official_connection_executed": False,
        "competition_mode_executed": False,
        "kaggle_work_executed": False,
        "claims": {
            "sample_completion_183": "SUPPORTED",
            "all_execution_traces_persisted": "SUPPORTED",
            "generalization": "MEASURED_NOT_PROVEN",
        },
    }
    path = tmp_path / "release.json"
    _write_json(
        path,
        {
            **body,
            "content_digest": (
                P11_RELEASE_STATE_DIGEST_PREFIX
                + digest_object(body)
            ),
        },
    )
    assert load_p11_release_state(path)["status"] == (
        "P11_RELEASE_STATE_FIXED"
    )

    claims_value = body["claims"]
    assert isinstance(claims_value, dict)
    claims = dict(claims_value)
    claims.pop("all_execution_traces_persisted")
    tampered_body = {**body, "claims": claims}
    _write_json(
        path,
        {
            **tampered_body,
            "content_digest": (
                P11_RELEASE_STATE_DIGEST_PREFIX
                + digest_object(tampered_body)
            ),
        },
    )
    with pytest.raises(ValueError, match="P11_RELEASE_STATE_INVALID"):
        load_p11_release_state(path)


def _write_test_wheel(path: Path) -> None:
    with zipfile.ZipFile(path, "w") as archive:
        archive.writestr(
            "arc3_agi_agent/bundles/s5_rendered_policy_v1.json",
            "{}",
        )
        archive.writestr(
            "arc3_agi_agent/bundles/s5_rendered_policy_v1.npz",
            b"weights",
        )
        archive.writestr(
            "arc3_agi_agent/teacher/compiler.py",
            "# development compiler\n",
        )
        archive.writestr(
            "arc_agi_3_agents-0.1.0.dist-info/WHEEL",
            "Wheel-Version: 1.0\n"
            "Generator: setuptools (83.0.0)\n"
            "Root-Is-Purelib: true\n"
            "Tag: py3-none-any\n",
        )


def test_wheel_audit_requires_reproducible_runtime_bundle(
    tmp_path: Path,
) -> None:
    primary = tmp_path / "package.whl"
    reproduction = tmp_path / "package-reproduction.whl"
    _write_test_wheel(primary)
    _write_test_wheel(reproduction)

    report = inspect_reproducible_wheels(primary, reproduction)

    assert report["byte_reproducible"] is True
    assert report["contains_runtime_policy_manifest"] is True
    assert report["contains_runtime_policy_weights"] is True
    assert report["contains_training_corpus"] is False
    assert report["development_compiler_modules_included"] is True
    assert (
        report["build_contract"]["backend_generator"]
        == "setuptools (83.0.0)"
    )

    reproduction.write_bytes(reproduction.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="P11_PACKAGE_BYTE_MISMATCH"):
        inspect_reproducible_wheels(primary, reproduction)
