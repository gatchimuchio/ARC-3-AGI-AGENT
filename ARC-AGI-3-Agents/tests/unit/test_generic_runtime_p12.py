from __future__ import annotations

import pytest

from arc3_agi_agent.generic_compute import (
    HybridRelationalInstructionBody,
    ParametricRelationalInstructionBody,
)
from arc3_agi_agent.generic_env import MechanismWorld
from arc3_agi_agent.generic_hds import ActionAuthorizationExecutor
from arc3_agi_agent.generic_runtime import (
    GenericAGIRuntime,
    GenericRuntimeConfiguration,
)


def test_generic_runtime_has_full_serial_trace_and_semantic_candidates() -> None:
    runtime = GenericAGIRuntime(
        MechanismWorld((11, 29, 47), (1,), required_progress=2),
        HybridRelationalInstructionBody(),
        GenericRuntimeConfiguration(max_cycles=16),
    )

    report = runtime.run()
    first = report.cycles[0]

    assert report.final_state == "WIN"
    assert report.no_fallback_used is True
    assert report.runtime_identity_received is False
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
    runtime = GenericAGIRuntime(
        MechanismWorld((11, 29), (0,), required_progress=1),
        ParametricRelationalInstructionBody(),
        GenericRuntimeConfiguration(max_cycles=4),
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
    executor = ActionAuthorizationExecutor(runtime.authority_token)

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
