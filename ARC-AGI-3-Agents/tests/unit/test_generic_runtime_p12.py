from __future__ import annotations

import pytest

from arc3_agi_agent.generic_compute import (
    HybridRelationalInstructionBody,
    ParametricRelationalInstructionBody,
)
from arc3_agi_agent.generic_env import MechanismWorld
from arc3_agi_agent.generic_hds import ActionAuthorizationExecutor
from arc3_agi_agent.generic_runtime import GenericAGIRuntime
from arc3_agi_agent.generic_session import (
    ResourceContract,
    create_cognitive_session,
)


def _runtime(
    world: MechanismWorld,
    body: object,
    *,
    max_cycles: int,
) -> GenericAGIRuntime:
    if not isinstance(
        body,
        (HybridRelationalInstructionBody, ParametricRelationalInstructionBody),
    ):
        raise TypeError
    session = create_cognitive_session(
        p_bundle=body,
        resource_contract=ResourceContract(
            action_budget_per_episode=max_cycles
        ),
    )
    return GenericAGIRuntime(world, session, session.begin_episode())


def test_generic_runtime_has_full_serial_trace_and_semantic_candidates() -> None:
    runtime = _runtime(
        MechanismWorld((11, 29, 47), (1,), required_progress=2),
        HybridRelationalInstructionBody(),
        max_cycles=16,
    )

    report = runtime.run()
    first = report.cycles[0]

    assert report.final_state == "WIN"
    assert report.no_fallback_used is True
    assert report.runtime_identity_received is True
    assert report.identity_boundary_passed is True
    assert tuple(stage.stage for stage in first.compute_result.stages) == (
        "represent",
        "retrieve",
        "model",
        "predict",
        "candidate",
    )
    assert len(
        {
            candidate.semantic_identity()
            for candidate in first.compute_result.candidates
        }
    ) >= 2
    assert tuple(gate.gate_id for gate in first.decision.gate_results) == tuple(
        f"G{index:02d}" for index in range(16)
    )


def test_hds_capabilities_and_compute_commands_are_single_use() -> None:
    runtime = _runtime(
        MechanismWorld((11, 29), (0,), required_progress=1),
        ParametricRelationalInstructionBody(),
        max_cycles=4,
    )
    observation = runtime.environment.observe()
    memory = runtime.memory.view()
    frame = runtime.hds.frame(observation, memory, remaining_budget=4)
    command = runtime.hds.issue_compute(frame, observation, memory)
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
    candidate = next(
        item
        for item in result.candidates
        if item.candidate_id == decision.selected_candidate_id
    )
    authorization = runtime.hds.authorize_action(
        decision, candidate, observation
    )
    executor = ActionAuthorizationExecutor(runtime.session.authority)

    executor.consume(authorization, decision, candidate, observation)
    with pytest.raises(
        PermissionError, match="GENERIC_ACTION_AUTHORIZATION_REUSED"
    ):
        executor.consume(authorization, decision, candidate, observation)

    with pytest.raises(
        PermissionError, match="GENERIC_COMPUTE_COMMAND_REUSED"
    ):
        runtime.compute.compute(
            command=command,
            observation=observation,
            memory=runtime.memory,
            instruction_body=runtime.instruction_body,
        )
