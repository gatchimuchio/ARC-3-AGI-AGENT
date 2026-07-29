from __future__ import annotations

import hashlib
import inspect
import json
from dataclasses import fields, replace
from pathlib import Path

import pytest

from arc3_agi_agent.decision_context import DecisionContext, DecisionObservation
from arc3_agi_agent.evidence_binding import (
    EvidenceBindingKey,
    bind_candidate_records,
    candidate_reproduced,
)
from arc3_agi_agent.generic_compute import (
    GenericComputeSubject,
    ParametricRelationalInstructionBody,
    action_descriptors,
    represent_observation,
)
from arc3_agi_agent.generic_env import MechanismWorld
from arc3_agi_agent.generic_hds import (
    GenericHDSJudgementSubject,
    HDSConfiguration,
)
from arc3_agi_agent.generic_memory import SemanticMemory, semantic_record
from arc3_agi_agent.generic_runtime import GenericAGIRuntime
from arc3_agi_agent.generic_session import (
    CognitiveSession,
    ResourceContract,
    create_cognitive_session,
)
from arc3_agi_agent.generic_types import (
    GenericCandidate,
    GenericComputeResult,
    GenericObservation,
)
from arc3_agi_agent.identity_boundary import OrchestrationMetadata, Tainted
from arc3_agi_agent.schema import canonical_json
from arc3_agi_agent.taint import (
    COORDINATE_PROVENANCE_CURRENT_RENDER,
    COORDINATE_PROVENANCE_PRECOMPUTED,
)


def _case(
    *,
    evidence_mode: str = "PROBE_WHEN_UNREPRODUCED",
) -> tuple[
    CognitiveSession,
    GenericObservation,
    object,
    GenericComputeResult,
]:
    session = create_cognitive_session(
        p_bundle=ParametricRelationalInstructionBody(),
        hds_configuration=HDSConfiguration(
            evidence_mode=evidence_mode,
            resource_budget=8,
            stop_after_no_progress=8,
        ),
        resource_contract=ResourceContract(action_budget_per_episode=8),
    )
    session.begin_episode()
    observation = MechanismWorld(
        (11,),
        (0,),
        required_progress=1,
    ).observe()
    memory_view = session.memory.view()
    frame = session.hds.frame(
        observation,
        memory_view,
        remaining_budget=8,
    )
    command = session.hds.issue_compute(frame, observation, memory_view)
    result = session.compute.compute(
        command=command,
        observation=observation,
        memory=session.memory,
        instruction_body=session.instruction_body,
    )
    assert result.validate(observation) == ()
    return session, observation, frame, result


def _record_for(
    candidate: GenericCandidate,
    *,
    key: EvidenceBindingKey | None = None,
    state: str = "ACTIVE",
    support_count: int = 2,
    contradiction_count: int = 0,
    hazard_count: int = 0,
    confidence_ppm: int = 800_000,
    execute_eligibility: bool = True,
):
    selected_key = key or candidate.evidence_binding_key
    return semantic_record(
        memory_id="evidence:" + selected_key.digest()[-24:],
        kind=(
            "FAILURE_SIGNATURE"
            if hazard_count > 0
            else "PROCEDURE_CAPABILITY"
        ),
        statement="Candidate-bound identity-free action/effect evidence.",
        semantic_tokens=(
            "goal:progress",
            candidate.descriptor.semantic_key,
        ),
        evidence=("independent-rendered-transition",),
        counter_evidence=(
            ("independent-rendered-hazard",)
            if hazard_count > 0
            else ()
        ),
        scope=("episode-overlay",),
        falsification_condition=(
            "a matching rendered precondition produces an incompatible effect"
        ),
        state=state,
        payload={
            **selected_key.payload(),
            "support_count": support_count,
            "contradiction_count": contradiction_count,
            "hazard_count": hazard_count,
            "confidence_ppm": confidence_ppm,
            "execute_eligibility": execute_eligibility,
            "probe_eligibility": True,
        },
    )


def _attach_record(
    result: GenericComputeResult,
    observation: GenericObservation,
    record: object,
) -> tuple[GenericComputeResult, GenericCandidate]:
    candidate = result.candidates[0]
    bindings = bind_candidate_records(
        key=candidate.evidence_binding_key,
        records=(record,),  # type: ignore[arg-type]
    )
    memory_refs = tuple(
        sorted(binding.record_digest for binding in bindings)
    )
    counter_refs = tuple(
        sorted(
            binding.record_digest
            for binding in bindings
            if (
                binding.hazard_count > 0
                or binding.contradiction_count > 0
                or not binding.precondition_match
                or not binding.effect_compatible
                or not binding.scope_applicable
            )
        )
    )
    candidate = replace(
        candidate,
        evidence_bindings=bindings,
        typed_provenance=replace(
            candidate.typed_provenance,
            memory_binding_refs=memory_refs,
            counter_evidence_refs=counter_refs,
        ),
    )
    bound_result = replace(
        result,
        candidates=(candidate,),
        memory_citations=(record.citation(),),  # type: ignore[attr-defined]
    )
    assert bound_result.validate(observation) == ()
    return bound_result, candidate


def test_unrelated_memory_never_marks_reproduced() -> None:
    session, observation, frame, result = _case(
        evidence_mode="REPRODUCED_ONLY"
    )
    candidate = result.candidates[0]
    unrelated_key = replace(
        candidate.evidence_binding_key,
        action_relation_digest="action-relation:unrelated",
    )
    record = _record_for(candidate, key=unrelated_key)
    result, candidate = _attach_record(result, observation, record)

    assert candidate.evidence_bindings == ()
    assert not candidate_reproduced(
        candidate.evidence_bindings,
        retrieved_citation_digests=(
            result.memory_citations[0].content_digest,
        ),
    )
    decision = session.hds.judge(
        frame=frame,
        observation=observation,
        result=result,
    )
    assert decision.operation_state == "SUSPEND"
    assert decision.external_action_authorized is False


def test_matching_record_can_mark_reproduced() -> None:
    session, observation, frame, result = _case(
        evidence_mode="REPRODUCED_ONLY"
    )
    record = _record_for(result.candidates[0])
    result, candidate = _attach_record(result, observation, record)

    assert candidate_reproduced(
        candidate.evidence_bindings,
        retrieved_citation_digests=(
            result.memory_citations[0].content_digest,
        ),
    )
    decision = session.hds.judge(
        frame=frame,
        observation=observation,
        result=result,
    )
    assert decision.operation_state == "EXECUTE"
    assert decision.selected_candidate_id == candidate.candidate_id
    assert decision.external_action_authorized is True


def test_precondition_mismatch_forces_probe() -> None:
    session, observation, frame, result = _case()
    candidate = result.candidates[0]
    record = _record_for(
        candidate,
        key=replace(
            candidate.evidence_binding_key,
            precondition_digest="precondition:mismatch",
        ),
    )
    result, candidate = _attach_record(result, observation, record)

    assert candidate.evidence_bindings
    assert not candidate.evidence_bindings[0].precondition_match
    decision = session.hds.judge(
        frame=frame,
        observation=observation,
        result=result,
    )
    assert decision.operation_state == "PROBE"
    assert decision.operation_state != "EXECUTE"


def test_effect_mismatch_forces_probe() -> None:
    session, observation, frame, result = _case()
    candidate = result.candidates[0]
    record = _record_for(
        candidate,
        key=replace(
            candidate.evidence_binding_key,
            predicted_effect_digest="predicted-effect:mismatch",
        ),
    )
    result, candidate = _attach_record(result, observation, record)

    assert candidate.evidence_bindings
    assert not candidate.evidence_bindings[0].effect_compatible
    decision = session.hds.judge(
        frame=frame,
        observation=observation,
        result=result,
    )
    assert decision.operation_state == "PROBE"
    assert decision.operation_state != "EXECUTE"


def test_hazard_exact_match_veto() -> None:
    session, observation, frame, result = _case()
    record = _record_for(
        result.candidates[0],
        support_count=0,
        hazard_count=1,
        confidence_ppm=0,
        execute_eligibility=False,
    )
    result, candidate = _attach_record(result, observation, record)

    assert candidate.evidence_bindings[0].hazard_count == 1
    decision = session.hds.judge(
        frame=frame,
        observation=observation,
        result=result,
    )
    gate = next(
        item for item in decision.gate_results if item.gate_id == "G10"
    )
    assert decision.operation_state == "SUSPEND"
    assert "EVIDENCE_HAZARD_VETO" in gate.reason_codes


def test_probation_never_authorizes_execute() -> None:
    session, observation, frame, result = _case()
    record = _record_for(
        result.candidates[0],
        state="PROBATION",
    )
    result, candidate = _attach_record(result, observation, record)

    assert candidate.evidence_bindings
    assert candidate.evidence_bindings[0].execute_eligible is False
    assert "RECORD_NOT_ACTIVE" in (
        candidate.evidence_bindings[0].rejection_reasons
    )
    decision = session.hds.judge(
        frame=frame,
        observation=observation,
        result=result,
    )
    assert decision.operation_state == "PROBE"
    assert decision.operation_state != "EXECUTE"


def test_failure_rolls_back_episode_overlay() -> None:
    session = create_cognitive_session(
        p_bundle=ParametricRelationalInstructionBody(),
        resource_contract=ResourceContract(action_budget_per_episode=1),
    )
    base_active = session.memory.view().active
    handle = session.begin_episode()
    transaction = session._active_transaction
    assert transaction is not None
    runtime = GenericAGIRuntime(
        MechanismWorld((11,), (0,), required_progress=2),
        session,
        handle,
    )

    report = runtime.run()
    assert report.memory_final_version > report.memory_initial_version
    assert session.memory.view().active != base_active
    receipt = session.end_episode(
        handle,
        succeeded=False,
        reason="simulated-episode-failure",
    )

    assert transaction.state == "ROLLED_BACK"
    assert receipt.promoted is False
    assert receipt.discarded is True
    assert receipt.final_active_digest == receipt.base_active_digest
    assert session.memory.view().active == base_active


def _ranking_with_tainted_metadata(
    metadata: OrchestrationMetadata,
) -> tuple[object, ...]:
    session = create_cognitive_session(
        p_bundle=ParametricRelationalInstructionBody(),
        resource_contract=ResourceContract(action_budget_per_episode=1),
    )
    with pytest.raises(PermissionError, match="IDENTITY_BOUNDARY_VIOLATION"):
        session.identity_boundary.require_decision_context(metadata)
    handle = session.begin_episode()
    report = GenericAGIRuntime(
        MechanismWorld((11, 29, 47), (1,), required_progress=2),
        session,
        handle,
    ).run()
    cycle = report.cycles[0]
    return (
        tuple(
            (
                item.descriptor.semantic_key,
                item.expected_progress,
                item.expected_information_gain,
                item.expected_risk,
            )
            for item in cycle.compute_result.candidates
        ),
        (
            cycle.selected_candidate.descriptor.semantic_key
            if cycle.selected_candidate is not None
            else None
        ),
    )


def test_game_order_not_visible() -> None:
    forbidden_api_names = {
        "scorecard_id",
        "game_id",
        "game_index",
        "environment_handle",
        "episode_handle",
    }
    for subject in (
        GenericComputeSubject.compute,
        GenericHDSJudgementSubject.judge,
        SemanticMemory.query,
    ):
        assert forbidden_api_names.isdisjoint(
            inspect.signature(subject).parameters
        )
    context_fields = {
        item.name
        for subject in (DecisionObservation, DecisionContext)
        for item in fields(subject)
    }
    assert forbidden_api_names.isdisjoint(context_fields)

    first = OrchestrationMetadata(
        scorecard_id=Tainted("scorecard-a"),
        game_id=Tainted("game-a"),
        game_index=Tainted(0),
        environment_handle=Tainted(object()),
    )
    second = OrchestrationMetadata(
        scorecard_id=Tainted("scorecard-z"),
        game_id=Tainted("game-z"),
        game_index=Tainted(999),
        environment_handle=Tainted(object()),
    )
    assert _ranking_with_tainted_metadata(first) == (
        _ranking_with_tainted_metadata(second)
    )


def test_opaque_handle_not_serializable() -> None:
    session = create_cognitive_session(
        p_bundle=ParametricRelationalInstructionBody(),
        resource_contract=ResourceContract(action_budget_per_episode=1),
    )
    handle = session.begin_episode()

    assert canonical_json(handle) == "{}"
    assert handle.handle_digest not in canonical_json(handle)
    control_handle_field = next(
        item
        for item in fields(type(session.control))
        if item.name == "current_episode_handle_digest"
    )
    assert control_handle_field.metadata["serialize"] is False


def _pointer_descriptors():
    observation = GenericObservation(
        signature="pointer-observation",
        available_actions=(6,),
        rendered_layers=(
            (
                (0, 0, 0, 0, 0),
                (0, 2, 2, 0, 0),
                (0, 2, 2, 0, 0),
                (0, 0, 0, 0, 0),
                (0, 0, 0, 0, 0),
            ),
        ),
        terminal_state="NOT_FINISHED",
        progress_count=0,
        visible_effects=(),
        action_payload_schema=((6, ("x", "y")),),
    )
    representation = represent_observation(
        observation,
        goal_tokens=("goal:progress",),
    )
    return observation, action_descriptors(observation, representation)


def test_dynamic_xy_from_render_allowed() -> None:
    observation, descriptors = _pointer_descriptors()

    assert descriptors
    assert all(
        item.coordinate_provenance
        == COORDINATE_PROVENANCE_CURRENT_RENDER
        and item.coordinate_observation_digest == observation.digest()
        and item.validate(observation) == ()
        for item in descriptors
    )


def test_precomputed_xy_rejected() -> None:
    observation, descriptors = _pointer_descriptors()
    precomputed = replace(
        descriptors[0],
        coordinate_provenance=COORDINATE_PROVENANCE_PRECOMPUTED,
    )

    assert "PRECOMPUTED_COORDINATE_REJECTED" in (
        precomputed.validate(observation)
    )


def test_candidate_binding_coverage_is_complete() -> None:
    _, observation, _, result = _case()

    assert result.candidates
    assert all(
        candidate.evidence_binding_key.validate() == ()
        and candidate.typed_provenance.validate() == ()
        and candidate.typed_provenance.prediction_refs
        == candidate.prediction_refs
        for candidate in result.candidates
    )


def test_p17b_phase_state_is_content_bound() -> None:
    root = Path(__file__).resolve().parents[3]
    path = root / "control" / "p17b" / "P17B_PHASE_STATE.json"
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
    assert data["metrics"]["cross_game_semantic_promotion"] == "DISABLED"
