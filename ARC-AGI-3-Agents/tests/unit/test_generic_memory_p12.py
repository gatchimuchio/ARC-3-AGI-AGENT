from __future__ import annotations

import pytest

from arc3_agi_agent.generic_compute import ParametricRelationalInstructionBody
from arc3_agi_agent.generic_env import MechanismWorld
from arc3_agi_agent.generic_memory import (
    MemoryMutationProposal,
    semantic_record,
)
from arc3_agi_agent.generic_runtime import GenericAGIRuntime
from arc3_agi_agent.generic_session import (
    ResourceContract,
    create_cognitive_session,
)


def _proposal(identifier: str) -> MemoryMutationProposal:
    record = semantic_record(
        memory_id=identifier,
        kind="HYPOTHESIS",
        statement=f"bounded hypothesis {identifier}",
        semantic_tokens=("goal:progress", f"test:{identifier}"),
        evidence=("environment-observation",),
        counter_evidence=("no-counter-evidence-in-bounded-scope",),
        falsification_condition="future observation contradicts hypothesis",
    )
    return MemoryMutationProposal(
        operation="ADD",
        target_id=identifier,
        record=record,
        evidence=("environment-observation",),
        counter_evidence=("no-counter-evidence-in-bounded-scope",),
        scope=("p12-test",),
        falsification_condition=record.falsification_condition,
        reason="exercise version and authorization binding",
    )


def _runtime(*, max_cycles: int) -> GenericAGIRuntime:
    session = create_cognitive_session(
        p_bundle=ParametricRelationalInstructionBody(),
        resource_contract=ResourceContract(
            action_budget_per_episode=max_cycles
        ),
    )
    return GenericAGIRuntime(
        MechanismWorld((11, 29, 47), (1,), required_progress=2),
        session,
        session.begin_episode(),
    )


def test_semantic_memory_rejects_reuse_and_stale_version() -> None:
    runtime = _runtime(max_cycles=4)
    observation = runtime.environment.observe()
    view = runtime.memory.view()
    frame = runtime.hds.frame(observation, view, remaining_budget=4)
    command = runtime.hds.issue_compute(frame, observation, view)
    result = runtime.compute.compute(
        command=command,
        observation=observation,
        memory=runtime.memory,
        instruction_body=runtime.instruction_body,
    )
    decision = runtime.hds.judge(
        frame=frame,
        observation=observation,
        result=result,
    )
    first = _proposal("test-alpha")
    second = _proposal("test-beta")
    first_authorization = runtime.hds.authorize_memory(
        decision, first, memory_version=runtime.memory.version
    )
    stale_authorization = runtime.hds.authorize_memory(
        decision, second, memory_version=runtime.memory.version
    )

    first_receipt = runtime.memory.apply_authorized(
        first, first_authorization
    )

    assert first_receipt.old_version == 0
    assert first_receipt.new_version == 1
    with pytest.raises(
        PermissionError, match="SEMANTIC_MEMORY_AUTHORIZATION_REUSED"
    ):
        runtime.memory.apply_authorized(first, first_authorization)
    with pytest.raises(
        RuntimeError, match="SEMANTIC_MEMORY_VERSION_CONFLICT"
    ):
        runtime.memory.apply_authorized(second, stale_authorization)


def test_memory_provenance_records_complete_causal_boundary() -> None:
    runtime = _runtime(max_cycles=8)

    report = runtime.run()

    assert report.final_state == "WIN"
    assert runtime.memory.provenance()
    assert all(
        event.old_version < event.new_version
        and event.evidence
        and event.counter_evidence
        and event.scope
        and event.falsification_condition
        and event.authority == "HDS"
        and event.rollback_pointer >= 0
        for event in runtime.memory.provenance()
    )
