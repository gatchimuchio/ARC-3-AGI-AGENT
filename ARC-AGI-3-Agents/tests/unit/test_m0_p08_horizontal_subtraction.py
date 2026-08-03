from __future__ import annotations

from arc3_agi_agent.generic_types import GenericObservation
from arc3_agi_agent.local_capability import (
    ACTIVE_DEV_CAPABILITY_STAGE,
    RELATION_CAPABILITY,
    active_dev_mechanism_families,
    development_hypotheses,
    local_capability_records,
    relation_bound_action_applicable,
)


def _matrix(marker: int) -> tuple[tuple[int, ...], ...]:
    return tuple(
        tuple(marker if (x, y) == (12, 12) else 0 for x in range(64))
        for y in range(64)
    )


def _observation(
    actions: tuple[int, ...],
    *,
    signature: str,
    terminal_state: str = "NOT_FINISHED",
    action_complete: bool = True,
) -> GenericObservation:
    return GenericObservation(
        signature=signature,
        available_actions=actions,
        rendered_layers=(_matrix(9),),
        terminal_state=terminal_state,
        progress_count=1 if terminal_state == "WIN" else 0,
        action_payload_schema=((6, ("x", "y")),) if 6 in actions else (),
        win_level_count=1,
        action_complete=action_complete,
    )


def test_active_family_is_parameterized_and_identity_free() -> None:
    families = active_dev_mechanism_families()

    assert len(families) == 1
    family = families[0]
    assert family.family_id == RELATION_CAPABILITY
    assert family.asset_state == ACTIVE_DEV_CAPABILITY_STAGE
    assert family.independent_support_count == 3
    assert family.negative_case_count == 3
    assert family.boundary_case_count == 3
    assert family.execute_eligibility is False
    assert family.validate() == ()
    assert family.logical_digest().startswith("generic-mechanism-family:")
    assert set(family.parameter_schema) == {
        "ACTION_KIND_PARAMETER",
        "EFFECT_CLASS_PARAMETER",
        "PAYLOAD_SCHEMA_PARAMETER",
        "RELATION_PARAMETER",
        "ROLE_PARAMETER",
    }
    serialized = repr(family).casefold()
    assert all(
        token not in serialized
        for token in (
            "game_id",
            "level_id",
            "recording_id",
            "trajectory_id",
            "full-frame exact hash",
            "successful action index",
        )
    )


def test_applicability_covers_three_surfaces_and_rejects_boundaries() -> None:
    positive = (
        _observation((6,), signature="coordinate-only"),
        _observation((1, 2, 3, 4, 6, 7), signature="mixed-surface"),
        _observation((1, 2, 3, 4, 5), signature="keyboard-coupling"),
    )
    negative = _observation((0,), signature="reset-only")
    terminal = _observation((1, 2), signature="terminal", terminal_state="WIN")
    unsettled = _observation(
        (1, 2),
        signature="unsettled",
        action_complete=False,
    )

    assert all(relation_bound_action_applicable(item) for item in positive)
    assert relation_bound_action_applicable(negative) is False
    assert relation_bound_action_applicable(terminal) is False
    assert relation_bound_action_applicable(unsettled) is False


def test_active_projection_is_loaded_only_when_applicable() -> None:
    applicable = _observation((1, 2, 3, 4, 5), signature="applicable")
    boundary = _observation(
        (1, 2, 3, 4, 5),
        signature="boundary",
        action_complete=False,
    )

    applicable_records = local_capability_records(applicable)
    active_records = tuple(
        record
        for record in applicable_records
        if record.payload()["capability_id"] == RELATION_CAPABILITY
    )
    assert active_records
    assert all(
        record.state == "PROBATION"
        and record.payload()["asset_stage"] == ACTIVE_DEV_CAPABILITY_STAGE
        and record.payload()["applicability_match"] is True
        and record.payload()["execute_eligibility"] is False
        for record in active_records
    )
    assert "active_mechanism" in {
        item.model_type
        for item in development_hypotheses(applicable_records, applicable)
    }

    boundary_records = local_capability_records(boundary)
    assert all(
        record.payload()["applicability_match"] is False
        for record in boundary_records
        if record.payload()["capability_id"] == RELATION_CAPABILITY
    )
    assert "active_mechanism" not in {
        item.model_type
        for item in development_hypotheses(boundary_records, boundary)
    }
