from __future__ import annotations

from dataclasses import dataclass

from arc3_agi_agent.generic_runtime import GenericAGIRuntime
from arc3_agi_agent.generic_types import GenericObservation
from arc3_agi_agent.local_capability import (
    ACTIVE_DEV_CAPABILITY_STAGE,
    LOCAL_CAPABILITY_STAGE,
    RELATION_CAPABILITY,
    RESOURCE_CAPABILITY,
    TEMPORAL_CAPABILITY,
    refresh_local_capability_memory,
)
from arc3_agi_agent.product_runner import create_product_session


def _matrix(marker_x: int) -> tuple[tuple[int, ...], ...]:
    return tuple(
        tuple(9 if (x, y) == (marker_x, 24) else 0 for x in range(64))
        for y in range(64)
    )


def _observation(
    *,
    signature: str,
    actions: tuple[int, ...],
    frames: tuple[tuple[tuple[int, ...], ...], ...],
    terminal: str = "NOT_FINISHED",
    progress: int = 0,
    action_complete: bool = True,
) -> GenericObservation:
    payload_schema = ((6, ("x", "y")),) if 6 in actions else ()
    return GenericObservation(
        signature=signature,
        available_actions=actions,
        rendered_layers=frames,
        terminal_state=terminal,
        progress_count=progress,
        visible_effects=(),
        action_payload_schema=payload_schema,
        win_level_count=1,
        observation_history=(),
        action_complete=action_complete,
    )


@dataclass
class _OneStepEnvironment:
    before: GenericObservation
    after: GenericObservation
    action_count: int = 0

    def observe(self) -> GenericObservation:
        return self.before

    def step(
        self,
        action_id: int,
        *,
        payload: dict[str, int],
        request_id: str,
    ) -> GenericObservation:
        assert action_id in self.before.available_actions
        assert request_id.startswith("generic-action-request:")
        if action_id == 6:
            assert set(payload) == {"x", "y"}
        self.action_count += 1
        return self.after

    def reset_level(self, *, request_id: str) -> GenericObservation:
        raise AssertionError(request_id)


def test_actual_product_runtime_loads_and_cites_probation_capability() -> None:
    before = _observation(
        signature="rendered-before",
        actions=(6,),
        frames=(_matrix(12), _matrix(13)),
    )
    after = _observation(
        signature="rendered-win",
        actions=(6,),
        frames=(_matrix(14),),
        terminal="WIN",
        progress=1,
    )
    environment = _OneStepEnvironment(before, after)
    session = create_product_session(action_budget=4, mode="VALIDATION")
    handle = session.begin_episode()

    report = GenericAGIRuntime(environment, session, handle).run()

    assert report.final_state == "WIN"
    assert report.actions_executed == 1
    assert environment.action_count == 1
    cycle = report.cycles[0]
    citation_ids = {
        citation.memory_id for citation in cycle.compute_result.memory_citations
    }
    assert "local-m:temporal-settle" in citation_ids
    assert "local-m:coordinate-binding" in citation_ids
    capability_refs = {
        ref
        for prediction in cycle.compute_result.predictions
        for ref in prediction.instruction_refs
        if ref.startswith(("active-capability:", "probation-capability:"))
    }
    assert capability_refs == {
        f"probation-capability:{TEMPORAL_CAPABILITY}",
        f"active-capability:{RELATION_CAPABILITY}",
        f"probation-capability:{RESOURCE_CAPABILITY}",
    }
    assert {
        hypothesis.model_type
        for hypothesis in cycle.compute_result.hypotheses
    } >= {"active_mechanism", "counter_hypothesis", "goal_model"}
    assert cycle.decision.operation_state == "PROBE"
    assert cycle.decision.external_action_authorized is True
    assert all(
        record.payload()["execute_eligibility"] is False
        for record in session.memory.view().working
    )
    assert all(
        (
            record.state == "PROBATION"
            and record.payload()["asset_stage"]
            == ACTIVE_DEV_CAPABILITY_STAGE
        )
        if record.payload()["capability_id"] == RELATION_CAPABILITY
        else (
            record.state == "PROBATION"
            and record.payload()["asset_stage"] == LOCAL_CAPABILITY_STAGE
        )
        for record in session.memory.view().working
    )
    assert "LOCAL_M_REFRESH" in {
        event.event_type for event in session.ledger.events()
    }


def test_local_m_refresh_revises_and_invalidates_surface_capability() -> None:
    session = create_product_session(action_budget=4, mode="VALIDATION")
    active_before = session.memory.snapshot()
    first = _observation(
        signature="coordinate-surface",
        actions=(6,),
        frames=(_matrix(10), _matrix(11)),
    )
    second = _observation(
        signature="coupled-surface",
        actions=(1, 2, 3, 4, 5),
        frames=(_matrix(20),),
    )

    first_receipt = refresh_local_capability_memory(session.memory, first)
    second_receipt = refresh_local_capability_memory(session.memory, second)

    assert "local-m:coordinate-binding" in first_receipt.added_ids
    assert "local-m:coordinate-binding" in second_receipt.invalidated_ids
    assert "local-m:coupling-binding" in second_receipt.added_ids
    assert "local-m:observation-state" in second_receipt.revised_ids
    assert "local-m:temporal-settle" in second_receipt.revised_ids
    assert {
        record.memory_id for record in session.memory.view().working
    } == set(second_receipt.working_record_ids)
    assert session.memory.snapshot() == active_before


def test_hds_rejects_action_while_temporal_effect_is_unsettled() -> None:
    unsettled = _observation(
        signature="unsettled-render-sequence",
        actions=(6,),
        frames=(_matrix(30), _matrix(31)),
        action_complete=False,
    )
    environment = _OneStepEnvironment(unsettled, unsettled)
    session = create_product_session(action_budget=2, mode="VALIDATION")
    handle = session.begin_episode()

    report = GenericAGIRuntime(environment, session, handle).run()

    assert report.actions_executed == 0
    assert report.stop_reason == "HDS_SUSPEND"
    assert environment.action_count == 0
    decision = report.cycles[0].decision
    temporal_gate = next(
        gate for gate in decision.gate_results if gate.gate_id == "G11"
    )
    assert temporal_gate.status == "SUSPEND"
    assert temporal_gate.reason_codes == ("TEMPORAL_EFFECT_UNSETTLED",)
    assert decision.external_action_authorized is False
