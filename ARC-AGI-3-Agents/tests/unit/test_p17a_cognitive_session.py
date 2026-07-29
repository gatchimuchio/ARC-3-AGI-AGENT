from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from arc3_agi_agent.generic_compute import (
    HybridRelationalInstructionBody,
    ParametricRelationalInstructionBody,
)
from arc3_agi_agent.generic_env import MechanismWorld
from arc3_agi_agent.generic_hds import ActionAuthorizationExecutor
from arc3_agi_agent.generic_runtime import GenericAGIRuntime
from arc3_agi_agent.generic_session import (
    CognitiveSession,
    ResourceContract,
    create_cognitive_session,
)
from arc3_agi_agent.identity_boundary import (
    OrchestrationMetadata,
    Tainted,
)
from arc3_agi_agent.schema import (
    canonical_json,
    forbidden_runtime_paths,
)


def _session(
    *,
    max_cycles: int = 8,
    mode: str = "VALIDATION",
) -> CognitiveSession:
    return create_cognitive_session(
        p_bundle=HybridRelationalInstructionBody(),
        mode=mode,
        enable_cross_game_promotion=False,
        resource_contract=ResourceContract(
            action_budget_per_episode=max_cycles
        ),
    )


def _runtime(session: CognitiveSession) -> GenericAGIRuntime:
    return GenericAGIRuntime(
        environment=MechanismWorld(
            (11, 29, 47),
            (1,),
            required_progress=1,
        ),
        session=session,
        episode_handle=session.begin_episode(),
    )


def test_one_session_per_scorecard() -> None:
    session = _session(mode="COMPETITION")
    memory_id = id(session.memory)
    p_id = id(session.p_bundle.body)
    first = session.begin_episode()
    first_runtime = GenericAGIRuntime(
        MechanismWorld((11, 29), (0,), required_progress=1),
        session,
        first,
    )
    first_runtime.run()
    session.end_episode(first, succeeded=True, reason="GOAL_REACHED")

    second = session.begin_episode()
    second_runtime = GenericAGIRuntime(
        MechanismWorld((101, 205), (0,), required_progress=1),
        session,
        second,
    )

    assert first_runtime.session is second_runtime.session is session
    assert id(second_runtime.memory) == memory_id
    assert id(second_runtime.instruction_body) == p_id
    assert first.session_lineage_digest == second.session_lineage_digest


def test_runtime_does_not_create_memory() -> None:
    session = _session()
    memory = session.memory

    runtime = _runtime(session)

    assert runtime.memory is memory
    assert runtime.memory.authority_state is session.authority


def test_runtime_does_not_create_p() -> None:
    session = _session()
    p_bundle = session.p_bundle.body

    runtime = _runtime(session)

    assert runtime.instruction_body is p_bundle
    assert runtime.instruction_body.digest() == session.p_bundle.logical_digest


def test_authority_control_semantic_separation() -> None:
    session = _session()

    assert session.authority is not session.control
    assert session.memory is not session.control
    assert session.memory is not session.authority
    assert session.hds.authority_state is session.authority
    assert session.hds.control_state is session.control
    assert session.memory.authority_state is session.authority
    assert session.state_owner_violations() == ()
    memory_json = canonical_json(session.memory.view())
    assert "cycle_index" not in memory_json
    assert "no_progress_count" not in memory_json
    assert "live_token" not in memory_json


def test_new_scorecard_new_authority() -> None:
    first = _session(mode="COMPETITION")
    second = _session(mode="COMPETITION")

    assert first is not second
    assert first.authority is not second.authority
    assert first.authority.live_token is not second.authority.live_token
    assert first.lineage_digest != second.lineage_digest


def test_old_authorization_rejected() -> None:
    first = create_cognitive_session(
        p_bundle=ParametricRelationalInstructionBody(),
        resource_contract=ResourceContract(action_budget_per_episode=4),
    )
    first_runtime = GenericAGIRuntime(
        MechanismWorld((11, 29), (0,), required_progress=1),
        first,
        first.begin_episode(),
    )
    observation = first_runtime.environment.observe()
    memory_view = first_runtime.memory.view()
    frame = first_runtime.hds.frame(
        observation,
        memory_view,
        remaining_budget=4,
    )
    command = first_runtime.hds.issue_compute(
        frame,
        observation,
        memory_view,
    )
    result = first_runtime.compute.compute(
        command=command,
        observation=observation,
        memory=first_runtime.memory,
        instruction_body=first_runtime.instruction_body,
    )
    decision = first_runtime.hds.judge(
        frame=frame,
        observation=observation,
        result=result,
    )
    candidate = next(
        item
        for item in result.candidates
        if item.candidate_id == decision.selected_candidate_id
    )
    authorization = first_runtime.hds.authorize_action(
        decision,
        candidate,
        observation,
    )
    second = _session()

    with pytest.raises(
        PermissionError,
        match="GENERIC_ACTION_AUTHORITY_INVALID",
    ):
        ActionAuthorizationExecutor(second.authority).consume(
            authorization,
            decision,
            candidate,
            observation,
        )


def test_episode_overlay_discard_on_exception() -> None:
    session = _session(max_cycles=1)
    runtime = _runtime(session)
    handle = runtime.episode_handle
    base_active = session.memory.view().active

    report = runtime.run()
    assert report.memory_final_version > report.memory_initial_version
    assert session.memory.view().active != base_active

    receipt = session.end_episode(
        handle,
        succeeded=False,
        reason="RuntimeError",
    )

    assert receipt.promoted is False
    assert receipt.discarded is True
    assert session.memory.view().active == base_active
    assert session.cross_game_semantic_promotion_enabled is False


def test_prior_episode_memory_cannot_change_candidate_ranking() -> None:
    session = _session(max_cycles=1, mode="COMPETITION")
    first_runtime = _runtime(session)
    first_report = first_runtime.run()
    first_cycle = first_report.cycles[0]
    first_ranking = tuple(
        (
            item.descriptor.semantic_key,
            item.expected_progress,
            item.expected_information_gain,
            item.expected_risk,
        )
        for item in first_cycle.compute_result.candidates
    )
    first_selected = (
        first_cycle.selected_candidate.descriptor.semantic_key
        if first_cycle.selected_candidate is not None
        else None
    )
    session.end_episode(
        first_runtime.episode_handle,
        succeeded=False,
        reason="bounded-test-end",
    )

    second_runtime = _runtime(session)
    second_cycle = second_runtime.run().cycles[0]
    second_ranking = tuple(
        (
            item.descriptor.semantic_key,
            item.expected_progress,
            item.expected_information_gain,
            item.expected_risk,
        )
        for item in second_cycle.compute_result.candidates
    )
    second_selected = (
        second_cycle.selected_candidate.descriptor.semantic_key
        if second_cycle.selected_candidate is not None
        else None
    )

    assert second_ranking == first_ranking
    assert second_selected == first_selected


def test_game_metadata_not_in_decision_context() -> None:
    session = _session()
    metadata = OrchestrationMetadata(
        scorecard_id=Tainted("secret-scorecard"),
        game_id=Tainted("secret-game"),
        game_index=Tainted(7),
        environment_handle=Tainted(object()),
    )
    with pytest.raises(PermissionError, match="IDENTITY_BOUNDARY_VIOLATION"):
        session.identity_boundary.require_decision_context(metadata)

    report = _runtime(session).run()
    decision_payload = json.loads(canonical_json(report.cycles))

    assert forbidden_runtime_paths(decision_payload) == ()
    assert "secret-scorecard" not in canonical_json(decision_payload)
    assert "secret-game" not in canonical_json(decision_payload)
    assert report.identity_boundary_passed is True


def test_p17a_phase_state_is_content_bound() -> None:
    root = Path(__file__).resolve().parents[3]
    path = root / "control" / "p17a" / "P17A_PHASE_STATE.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    expected_digest = data.pop("content_digest")
    actual_digest = hashlib.sha256(
        json.dumps(
            data,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    assert expected_digest == actual_digest
    assert data["status"] == "PASS"
    assert data["failed_requirement_ids"] == []
    assert set(data["gates"].values()) == {"PASS"}
    assert data["cross_game_semantic_promotion"] == "DISABLED"
