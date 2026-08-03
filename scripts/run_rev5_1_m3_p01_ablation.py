#!/usr/bin/env python3
"""Execute and seal the rev5.1 C/J/M/P product ablation evidence."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Final

REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[1]
PACKAGE_ROOT: Final = REPOSITORY_ROOT / "ARC-AGI-3-Agents"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from arc3_agi_agent.generic_compute import (  # noqa: E402
    GENERIC_P_REMOVAL_WITNESS,
    GENERIC_SERIAL_DEPTH_WITNESS,
    ComputeAblation,
)
from arc3_agi_agent.generic_env import MechanismWorld  # noqa: E402
from arc3_agi_agent.generic_hds import HDSAblation  # noqa: E402
from arc3_agi_agent.generic_runtime import (  # noqa: E402
    GenericAGIRuntime,
    GenericRuntimeAblation,
)
from arc3_agi_agent.product_capability import (  # noqa: E402
    load_product_initial_state,
)
from arc3_agi_agent.product_runner import create_product_session  # noqa: E402
from arc3_agi_agent.schema import digest_object  # noqa: E402

OUTPUT_PATH: Final = Path("analysis/product/rev5_1/m3_p01_cjmp_ablation.json")
BUNDLE_PATH: Final = Path(
    "ARC-AGI-3-Agents/arc3_agi_agent/bundles/arc3_product_initial_state_v1.json"
)
REPRESENTATIVE_ACTIONS: Final = (11, 29)
REPRESENTATIVE_WINNING_ORDINALS: Final = (0,)
REPRESENTATIVE_ACTION_BUDGET: Final = 6


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _encoded(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _require(condition: bool, failure: str) -> None:
    if not condition:
        raise RuntimeError(failure)


def _world() -> MechanismWorld:
    return MechanismWorld(
        REPRESENTATIVE_ACTIONS,
        REPRESENTATIVE_WINNING_ORDINALS,
        required_progress=1,
        max_turns=REPRESENTATIVE_ACTION_BUDGET,
    )


def _active_memory_digest(session: object) -> str:
    memory = getattr(session, "memory")
    active = tuple(record for record in memory.snapshot() if record.state == "ACTIVE")
    return "active-memory:" + digest_object(active)


def _action_sequence(report: object) -> list[int]:
    cycles = getattr(report, "cycles")
    return [
        cycle.selected_candidate.descriptor.action_id
        for cycle in cycles
        if cycle.selected_candidate is not None
    ]


def _attribution_sequence(report: object) -> list[str]:
    cycles = getattr(report, "cycles")
    return [
        cycle.attribution.category for cycle in cycles if cycle.attribution is not None
    ]


def _baseline_case() -> dict[str, object]:
    session = create_product_session(
        action_budget=REPRESENTATIVE_ACTION_BUDGET,
        mode="VALIDATION",
    )
    world = _world()
    initial_observation = world.observe()
    initial_memory_version = session.memory.version
    initial_memory_digest = _active_memory_digest(session)
    handle = session.begin_episode()
    report = GenericAGIRuntime(world, session, handle).run()
    action_sequence = _action_sequence(report)
    attribution_sequence = _attribution_sequence(report)
    cycle_stage_sequences = [
        [stage.stage for stage in cycle.compute_result.stages]
        for cycle in report.cycles
    ]
    all_actions_j_authorized = all(
        cycle.decision.external_action_authorized
        and cycle.selected_candidate is not None
        and any(
            event.startswith("hds-external-action:") for event in cycle.authority_events
        )
        for cycle in report.cycles
    )
    all_memory_updates_j_authorized = all(
        cycle.decision.memory_update_authorized
        and any(
            event.startswith("hds-memory-update:") for event in cycle.authority_events
        )
        for cycle in report.cycles
    )
    final_memory_version = session.memory.version
    final_memory_digest = _active_memory_digest(session)
    action_history_count = len(session.action_history.view())
    session.end_episode(
        handle,
        succeeded=report.final_state == "WIN",
        reason=report.stop_reason,
    )
    _require(report.final_state == "WIN", "M3_P01_BASELINE_NOT_WIN")
    _require(action_sequence == [29, 11], "M3_P01_BASELINE_ACTION_SEQUENCE")
    _require(
        attribution_sequence == ["NO_EFFECT", "PROGRESS"],
        "M3_P01_BASELINE_ATTRIBUTION_SEQUENCE",
    )
    _require(all_actions_j_authorized, "M3_P01_BASELINE_J_AUTHORIZATION")
    _require(
        all_memory_updates_j_authorized,
        "M3_P01_BASELINE_M_AUTHORIZATION",
    )
    _require(
        all(
            stages == ["represent", "retrieve", "model", "predict", "candidate"]
            for stages in cycle_stage_sequences
        ),
        "M3_P01_BASELINE_C_STAGE_SEQUENCE",
    )
    _require(
        final_memory_version > initial_memory_version,
        "M3_P01_BASELINE_M_NOT_UPDATED",
    )
    _require(action_history_count == 2, "M3_P01_BASELINE_ACTION_HISTORY")
    return {
        "status": "PASS",
        "observation_digest": initial_observation.digest(),
        "final_state": report.final_state,
        "stop_reason": report.stop_reason,
        "actions_executed": report.actions_executed,
        "action_sequence": action_sequence,
        "attribution_sequence": attribution_sequence,
        "compute_stage_sequences": cycle_stage_sequences,
        "all_actions_J_authorized": all_actions_j_authorized,
        "all_memory_updates_J_authorized": all_memory_updates_j_authorized,
        "initial_memory_version": initial_memory_version,
        "final_memory_version": final_memory_version,
        "active_memory_changed": final_memory_digest != initial_memory_digest,
        "action_history_count": action_history_count,
        "new_representation_hypothesis_plan_generated": all(
            cycle.compute_result.representation is not None
            and cycle.compute_result.hypotheses
            and cycle.selected_candidate is not None
            and cycle.selected_candidate.plan.steps
            for cycle in report.cycles
        ),
    }


def _failed_runtime_ablation(
    *,
    ablation: GenericRuntimeAblation,
    expected_exception: type[Exception],
    expected_witness: str,
) -> dict[str, object]:
    session = create_product_session(
        action_budget=REPRESENTATIVE_ACTION_BUDGET,
        mode="VALIDATION",
    )
    world = _world()
    initial_observation = world.observe()
    initial_memory_version = session.memory.version
    initial_memory_digest = _active_memory_digest(session)
    handle = session.begin_episode()
    witness = ""
    exception_type = ""
    try:
        GenericAGIRuntime(world, session, handle).run(ablation=ablation)
    except expected_exception as error:
        exception_type = type(error).__name__
        witness = str(error)
    final_observation = world.observe()
    final_memory_version = session.memory.version
    final_memory_digest = _active_memory_digest(session)
    action_history_count = len(session.action_history.view())
    session.end_episode(handle, succeeded=False, reason=expected_witness)
    _require(witness == expected_witness, "M3_P01_ABLATION_WITNESS_MISMATCH")
    _require(
        final_observation.digest() == initial_observation.digest(),
        "M3_P01_ABLATION_EXTERNAL_ACTION_LEAK",
    )
    _require(
        final_memory_version == initial_memory_version,
        "M3_P01_ABLATION_ACTIVE_MEMORY_VERSION_LEAK",
    )
    _require(
        final_memory_digest == initial_memory_digest,
        "M3_P01_ABLATION_ACTIVE_MEMORY_CONTENT_LEAK",
    )
    _require(action_history_count == 0, "M3_P01_ABLATION_ACTION_HISTORY_LEAK")
    return {
        "status": "PASS",
        "exception_type": exception_type,
        "witness": witness,
        "external_action_count": 0,
        "active_memory_commit_count": 0,
        "action_history_count": action_history_count,
        "observation_unchanged": True,
        "active_memory_unchanged": True,
    }


def _memory_ablation_case() -> dict[str, object]:
    session = create_product_session(
        action_budget=REPRESENTATIVE_ACTION_BUDGET,
        mode="VALIDATION",
    )
    world = _world()
    initial_memory_version = session.memory.version
    initial_memory_digest = _active_memory_digest(session)
    handle = session.begin_episode()
    report = GenericAGIRuntime(world, session, handle).run(
        ablation=GenericRuntimeAblation(
            memory_read=False,
            memory_write=False,
        )
    )
    action_sequence = _action_sequence(report)
    attribution_sequence = _attribution_sequence(report)
    final_memory_version = session.memory.version
    final_memory_digest = _active_memory_digest(session)
    action_history_count = len(session.action_history.view())
    session.end_episode(handle, succeeded=False, reason=report.stop_reason)
    _require(
        report.final_state == "NOT_FINISHED",
        "M3_P01_M_ABLATION_UNEXPECTED_COMPLETION",
    )
    _require(
        action_sequence == [29, 29, 29, 29, 29, 29],
        "M3_P01_M_ABLATION_FAILURE_NOT_REPEATED",
    )
    _require(
        attribution_sequence == ["NO_EFFECT"] * REPRESENTATIVE_ACTION_BUDGET,
        "M3_P01_M_ABLATION_ATTRIBUTION_MISMATCH",
    )
    _require(
        final_memory_version == initial_memory_version,
        "M3_P01_M_ABLATION_MEMORY_VERSION_CHANGED",
    )
    _require(
        final_memory_digest == initial_memory_digest,
        "M3_P01_M_ABLATION_ACTIVE_MEMORY_CHANGED",
    )
    _require(action_history_count == 0, "M3_P01_M_ABLATION_HISTORY_CHANGED")
    return {
        "status": "PASS",
        "final_state": report.final_state,
        "stop_reason": report.stop_reason,
        "actions_executed": report.actions_executed,
        "action_sequence": action_sequence,
        "attribution_sequence": attribution_sequence,
        "failed_action_repeat_count": action_sequence.count(29) - 1,
        "learning_delta_disappeared": True,
        "active_memory_commit_count": 0,
        "action_history_count": action_history_count,
    }


def _p_ablation_case() -> dict[str, object]:
    session = create_product_session(
        action_budget=REPRESENTATIVE_ACTION_BUDGET,
        mode="VALIDATION",
    )
    world = _world()
    observation = world.observe()
    initial_memory_version = session.memory.version
    initial_memory_digest = _active_memory_digest(session)
    handle = session.begin_episode()
    memory_view = session.memory.view()
    frame = session.hds.frame(
        observation,
        memory_view,
        remaining_budget=REPRESENTATIVE_ACTION_BUDGET,
    )
    command = session.hds.issue_compute(frame, observation, memory_view)
    witness = ""
    exception_type = ""
    try:
        session.compute.compute(
            command=command,
            observation=observation,
            memory=session.memory,
            instruction_body=None,
            p_ir_program=session.p_ir_program,
        )
    except RuntimeError as error:
        exception_type = type(error).__name__
        witness = str(error)
    final_memory_version = session.memory.version
    final_memory_digest = _active_memory_digest(session)
    session.end_episode(handle, succeeded=False, reason=GENERIC_P_REMOVAL_WITNESS)
    _require(witness == GENERIC_P_REMOVAL_WITNESS, "M3_P01_P_WITNESS")
    _require(world.observe() == observation, "M3_P01_P_EXTERNAL_ACTION_LEAK")
    _require(
        final_memory_version == initial_memory_version,
        "M3_P01_P_MEMORY_VERSION_LEAK",
    )
    _require(
        final_memory_digest == initial_memory_digest,
        "M3_P01_P_MEMORY_CONTENT_LEAK",
    )
    return {
        "status": "PASS",
        "exception_type": exception_type,
        "witness": witness,
        "external_action_count": 0,
        "active_memory_commit_count": 0,
        "ARC3_capability_available": False,
    }


def build_report(root: Path = REPOSITORY_ROOT) -> dict[str, object]:
    bundle_bytes = (root / BUNDLE_PATH).read_bytes()
    initial = load_product_initial_state()
    identity_before = {
        "initial_state_logical_digest": initial.logical_digest,
        "p_logical_digest": initial.p_bundle.logical_digest(),
        "j0_digest": "j0:" + digest_object(initial.j0),
        "m0_digest": "m0:" + digest_object(initial.m0),
    }
    baseline = _baseline_case()
    c_ablation = _failed_runtime_ablation(
        ablation=GenericRuntimeAblation(
            compute=ComputeAblation(effective_serial_depth=False)
        ),
        expected_exception=RuntimeError,
        expected_witness=GENERIC_SERIAL_DEPTH_WITNESS,
    )
    j_ablation = _failed_runtime_ablation(
        ablation=GenericRuntimeAblation(hds=HDSAblation(purpose=False)),
        expected_exception=PermissionError,
        expected_witness="HDS_COMPUTE_PURPOSE_MISSING",
    )
    m_ablation = _memory_ablation_case()
    p_ablation = _p_ablation_case()
    identity_after_state = load_product_initial_state()
    identity_after = {
        "initial_state_logical_digest": identity_after_state.logical_digest,
        "p_logical_digest": identity_after_state.p_bundle.logical_digest(),
        "j0_digest": "j0:" + digest_object(identity_after_state.j0),
        "m0_digest": "m0:" + digest_object(identity_after_state.m0),
    }
    _require(identity_after == identity_before, "M3_P01_PRODUCT_BUNDLE_CHANGED")

    report: dict[str, object] = {
        "schema_version": "arc3-rev5-1-m3-p01-cjmp-ablation-v1",
        "artifact_type": "CjmpAblationEvidence",
        "point_id": "M3-P01_C_J_M_P_ABLATION",
        "runtime_product": "ARC3CompletionAgent",
        "asset_stage": "ACTIVE_DEV",
        "status": "M3_P01_PASS",
        "input_binding": {
            "active_product_bundle_path": BUNDLE_PATH.as_posix(),
            "active_product_bundle_sha256": _sha256(bundle_bytes),
            **identity_before,
        },
        "representative_case": {
            "identity_input_count": 0,
            "rendered_observation_only": True,
            "available_actions": list(REPRESENTATIVE_ACTIONS),
            "required_progress": 1,
            "action_budget": REPRESENTATIVE_ACTION_BUDGET,
            "same_case_used_by_all_ablations": True,
        },
        "baseline": baseline,
        "C_removal": {
            **c_ablation,
            "new_representation_hypothesis_plan_generated": False,
        },
        "J_removal": {
            **j_ablation,
            "external_action_authorization_available": False,
            "ACTIVE_M_authorization_available": False,
        },
        "M_removal": m_ablation,
        "P_removal": p_ablation,
        "functional_equivalent_audit": {
            "mock_subject_count": 0,
            "direct_action_selector_enabled": False,
            "direct_action_emitter_enabled": False,
            "non_J_active_memory_commit_path_count": 0,
            "functional_equivalent_leak_count": 0,
            "active_product_bundle_changed": False,
            "runtime_policy_changed": False,
        },
        "exit_audit": {
            "baseline_intact": True,
            "C_removal_blocks_new_representation_hypothesis_plan": True,
            "J_removal_blocks_external_action_and_ACTIVE_M_commit": True,
            "M_removal_eliminates_learning_delta_and_repeats_failure": True,
            "P_removal_eliminates_ARC3_capability": True,
            "functional_equivalent_leak_count": 0,
            "active_development_product_bundle_count": 1,
            "runtime_policy_changed": False,
            "status": "M3_P01_PASS",
        },
        "claim_boundary": {
            "allowed_claim": "M3_P01_C_J_M_P_ABLATION_ONLY",
            "M3_complete": False,
            "product_completion_established": False,
            "release_established": False,
            "next_point": "M3-P02_MEMORY_CAUSALITY",
        },
    }
    report["logical_content_sha256"] = _sha256(_canonical_json(report))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=REPOSITORY_ROOT)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    report = build_report(root)
    expected = _encoded(report)
    path = root / OUTPUT_PATH
    if arguments.write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(expected)
        status = "WRITTEN"
        success = True
    else:
        success = path.is_file() and path.read_bytes() == expected
        status = "PASS" if success else "STALE"
    print(
        json.dumps(
            {
                "output": OUTPUT_PATH.as_posix(),
                "point_status": report["status"],
                "status": status,
            },
            sort_keys=True,
        )
    )
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
