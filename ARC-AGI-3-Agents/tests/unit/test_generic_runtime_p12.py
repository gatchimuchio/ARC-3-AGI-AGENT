from __future__ import annotations

from typing import Mapping

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
from arc3_agi_agent.generic_types import GenericEnvironment, GenericObservation
from arc3_agi_agent.product_trace import ProductTraceSummarySink


def _runtime(
    world: GenericEnvironment,
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
    assert first.selected_candidate is not None
    assert first.decision.selected_plan_id == first.selected_candidate.plan.plan_id
    assert tuple(
        step.operation for step in first.selected_candidate.plan.steps
    ) in {
        ("ACTION", "REOBSERVE", "VERIFY", "REPLAN"),
        ("BOUNDED_PROBE", "REOBSERVE", "VERIFY", "REPLAN"),
    }
    assert len(first.selected_candidate.plan.representation_refs) >= 2
    assert len(report.cycles) >= 2
    second = report.cycles[1]
    assert second.selected_candidate is not None
    assert (
        second.selected_candidate.plan.predecessor_plan_id
        == first.selected_candidate.plan.plan_id
    )
    assert second.selected_candidate.plan.revision_reason != (
        "INITIAL_ONLINE_PLAN"
    )
    assert all(record.plan_id for record in runtime.session.action_history.view())


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


class _NoEffectThenWinWorld:
    def __init__(self) -> None:
        self.action_count = 0
        self.request_ids: set[str] = set()

    @staticmethod
    def _observation(*, won: bool = False) -> GenericObservation:
        return GenericObservation(
            signature=("no-effect-world:win" if won else "no-effect-world:same"),
            available_actions=(1, 2),
            rendered_layers=(((0, 1), (1, 0)),),
            terminal_state="WIN" if won else "NOT_FINISHED",
            progress_count=1 if won else 0,
            visible_effects=("LEVEL_PROGRESS",) if won else (),
        )

    def observe(self) -> GenericObservation:
        return self._observation()

    def step(
        self,
        action_id: int,
        *,
        payload: Mapping[str, int],
        request_id: str,
    ) -> GenericObservation:
        assert action_id in {1, 2}
        assert not payload
        assert request_id not in self.request_ids
        self.request_ids.add(request_id)
        self.action_count += 1
        return self._observation(won=self.action_count >= 2)

    def reset_level(self, *, request_id: str) -> GenericObservation:
        del request_id
        raise RuntimeError("NO_EFFECT_WORLD_RESET_UNAVAILABLE")


def test_no_effect_invalidates_failed_hypothesis_before_replan() -> None:
    world = _NoEffectThenWinWorld()
    runtime = _runtime(
        world,
        HybridRelationalInstructionBody(),
        max_cycles=3,
    )

    report = runtime.run()

    assert report.final_state == "WIN"
    assert len(report.cycles) == 2
    first, second = report.cycles
    assert first.attribution is not None
    assert first.attribution.category == "NO_EFFECT"
    assert first.selected_candidate is not None
    assert second.selected_candidate is not None
    first_plan = first.selected_candidate.plan
    revised = second.selected_candidate.plan
    assert revised.revision_reason == "NO_EFFECT_PLAN_REVISED"
    assert revised.predecessor_plan_id == first_plan.plan_id
    assert revised.invalidated_hypothesis_refs == first_plan.hypothesis_refs
    assert set(revised.hypothesis_refs).isdisjoint(
        revised.invalidated_hypothesis_refs
    )


def test_recovered_game_over_is_attribution_not_final_failure() -> None:
    runtime = _runtime(
        MechanismWorld(
            (11, 29),
            (0,),
            required_progress=1,
            failure_ordinals=(1,),
        ),
        HybridRelationalInstructionBody(),
        max_cycles=6,
    )

    report = runtime.run()

    assert report.final_state == "WIN"
    assert report.actions_executed == 2
    assert report.failure_signatures == ()
    assert report.cycles[0].attribution is not None
    assert report.cycles[0].attribution.category == "FAILURE"
    assert "GENERIC_GAME_OVER_OBSERVED" in (
        report.cycles[0].failure_signatures
    )
    summary = ProductTraceSummarySink()
    for cycle in report.cycles:
        summary.append(cycle)
    assert summary.executed_plan_count == report.actions_executed
    assert summary.hds_plan_commit_count == report.actions_executed
    assert summary.failure_attribution_count == 1
    assert sum(summary.action_id_counts.values()) == report.actions_executed
    assert summary.competing_hypothesis_plan_count == report.actions_executed
    assert summary.multi_representation_plan_count == report.actions_executed
    assert summary.subgoal_plan_count == report.actions_executed
    assert summary.max_plan_step_count == 4
