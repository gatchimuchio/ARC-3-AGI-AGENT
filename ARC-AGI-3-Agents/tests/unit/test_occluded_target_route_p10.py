from __future__ import annotations

import unittest

from arc3_agi_agent.instruction_body import SemanticOperatorInstruction
from arc3_agi_agent.occluded_target_route import (
    OCCLUDED_TARGET_ROUTE_OPERATOR,
    _model,
    _Parameters,
    _transition,
    occluded_target_route_observation_status,
    occluded_target_route_plan,
)
from arc3_agi_agent.p10_instruction_compiler import (
    occluded_target_route_instruction_mapping,
)
from arc3_agi_agent.schema import digest_object, forbidden_runtime_paths
from arc3_agi_agent.semantic_operators import SemanticPlannerState


def _instruction(
    *,
    maximum_search_states: int = 200000,
    maximum_transition_observations: int = 12,
) -> SemanticOperatorInstruction:
    parameters = {
        "click_action": 6,
        "up_action": 1,
        "down_action": 2,
        "left_action": 3,
        "right_action": 4,
        "selected_marker_color": 0,
        "unselected_marker_color": 5,
        "released_marker_color": 4,
        "marker_divisor": 3,
        "target_inset": 1,
        "minimum_object_side": 3,
        "maximum_object_side": 12,
        "maximum_missing_border_cells": 12,
        "maximum_search_states": maximum_search_states,
        "maximum_plan_actions": 128,
        "maximum_transition_observations": (
            maximum_transition_observations
        ),
    }
    return SemanticOperatorInstruction(
        operator_id=OCCLUDED_TARGET_ROUTE_OPERATOR,
        action_id=6,
        detector="rendered three-side target and selected object",
        transform="bounded rendered-state route search",
        parameter_items=tuple(sorted(parameters.items())),
        preconditions=("unique rendered roles close",),
        falsification_conditions=("reobserved transition differs",),
        provenance=("identity-free-synthetic-fixture",),
    )


def _object(
    grid: list[list[int]],
    *,
    x: int,
    y: int,
) -> None:
    for cell_y in range(y, y + 3):
        for cell_x in range(x, x + 3):
            grid[cell_y][cell_x] = 14
    grid[y + 1][x + 1] = 0


def _target(
    grid: list[list[int]],
    *,
    x: int,
    y: int,
    missing_side: str,
    occluded: bool = True,
) -> None:
    for cell_x in range(x, x + 5):
        grid[y][cell_x] = 4
        grid[y + 4][cell_x] = 4
    for cell_y in range(y, y + 5):
        grid[cell_y][x] = 4
        grid[cell_y][x + 4] = 4
    missing = {
        "left": tuple((x, cell_y) for cell_y in range(y + 1, y + 4)),
        "right": tuple(
            (x + 4, cell_y) for cell_y in range(y + 1, y + 4)
        ),
        "top": tuple((cell_x, y) for cell_x in range(x + 1, x + 4)),
        "bottom": tuple(
            (cell_x, y + 4) for cell_x in range(x + 1, x + 4)
        ),
    }[missing_side]
    delta = {
        "left": (-1, 0),
        "right": (1, 0),
        "top": (0, -1),
        "bottom": (0, 1),
    }[missing_side]
    for cell_x, cell_y in missing:
        grid[cell_y][cell_x] = 12 if occluded else 1
        grid[cell_y + delta[1]][cell_x + delta[0]] = (
            13 if occluded else 1
        )


def _grid(
    *,
    object_x: int = 3,
    object_y: int = 2,
    shift_x: int = 0,
    missing_side: str = "right",
    occluded: bool = True,
    second_target: bool = False,
    blocked: bool = False,
) -> tuple[tuple[int, ...], ...]:
    grid = [[1 for _x in range(36)] for _y in range(30)]
    grid[-1] = [2 for _x in range(36)]
    _object(
        grid,
        x=object_x + shift_x,
        y=object_y,
    )
    _target(
        grid,
        x=17 + shift_x,
        y=10,
        missing_side=missing_side,
        occluded=occluded,
    )
    if second_target:
        _target(
            grid,
            x=26,
            y=16,
            missing_side="bottom",
            occluded=True,
        )
    if blocked:
        grid[object_y][object_x + shift_x - 1] = 9
        grid[object_y][object_x + shift_x + 3] = 9
        grid[object_y + 3][object_x + shift_x] = 9
    return tuple(tuple(row) for row in grid)


class OccludedTargetRouteTests(unittest.TestCase):
    def test_unique_occluded_target_route_reaches_goal(self) -> None:
        instruction = _instruction()
        grid = _grid()
        parameters = _Parameters.from_instruction(instruction)
        self.assertIsNotNone(parameters)
        assert parameters is not None
        model = _model(grid, parameters)
        self.assertIsNotNone(model)
        assert model is not None

        plan = occluded_target_route_plan(
            grid,
            (1, 2, 3, 4, 6),
            instruction,
        )

        self.assertTrue(plan)
        position = model.initial_position
        for action in plan:
            position = _transition(model, position, action.action_id)
        self.assertEqual(position, model.goal)

    def test_translation_preserves_derived_action_sequence(self) -> None:
        instruction = _instruction()

        first = occluded_target_route_plan(
            _grid(),
            (1, 2, 3, 4, 6),
            instruction,
        )
        shifted = occluded_target_route_plan(
            _grid(shift_x=3),
            (1, 2, 3, 4, 6),
            instruction,
        )

        self.assertTrue(first)
        self.assertEqual(
            [action.action_id for action in first],
            [action.action_id for action in shifted],
        )

    def test_rotated_missing_side_is_completed(self) -> None:
        plan = occluded_target_route_plan(
            _grid(missing_side="bottom"),
            (1, 2, 3, 4, 6),
            _instruction(),
        )

        self.assertTrue(plan)
        self.assertIn(plan[-1].action_id, {3, 4})

    def test_open_or_ambiguous_target_is_rejected(self) -> None:
        instruction = _instruction()

        self.assertEqual(
            occluded_target_route_plan(
                _grid(occluded=False),
                (1, 2, 3, 4, 6),
                instruction,
            ),
            (),
        )
        self.assertEqual(
            occluded_target_route_plan(
                _grid(second_target=True),
                (1, 2, 3, 4, 6),
                instruction,
            ),
            (),
        )

    def test_blocked_initial_state_and_search_bound_are_rejected(self) -> None:
        self.assertEqual(
            occluded_target_route_plan(
                _grid(blocked=True),
                (1, 2, 3, 4, 6),
                _instruction(),
            ),
            (),
        )
        self.assertEqual(
            occluded_target_route_plan(
                _grid(),
                (1, 2, 3, 4, 6),
                _instruction(maximum_search_states=1),
            ),
            (),
        )

    def test_queued_action_requires_matching_rendered_state(self) -> None:
        instruction = _instruction()
        initial = _grid()
        plan = occluded_target_route_plan(
            initial,
            (1, 2, 3, 4, 6),
            instruction,
        )
        self.assertGreaterEqual(len(plan), 2)
        parameters = _Parameters.from_instruction(instruction)
        self.assertIsNotNone(parameters)
        assert parameters is not None
        model = _model(initial, parameters)
        self.assertIsNotNone(model)
        assert model is not None
        next_position = _transition(
            model,
            model.initial_position,
            plan[0].action_id,
        )
        next_grid = _grid(
            object_x=next_position[0],
            object_y=next_position[1],
        )

        self.assertEqual(
            occluded_target_route_observation_status(
                initial,
                instruction,
                plan[0],
            ),
            "MATCH",
        )
        self.assertEqual(
            occluded_target_route_observation_status(
                initial,
                instruction,
                plan[1],
            ),
            "MISMATCH",
        )
        self.assertEqual(
            occluded_target_route_observation_status(
                next_grid,
                instruction,
                plan[1],
            ),
            "MATCH",
        )

    def test_transient_reobservation_is_bounded_and_serialized(self) -> None:
        instruction = _instruction(maximum_transition_observations=3)
        plan = occluded_target_route_plan(
            _grid(),
            (1, 2, 3, 4, 6),
            instruction,
        )
        self.assertGreaterEqual(len(plan), 2)
        transient = [list(row) for row in _grid()]
        transient[10][18] = 1
        transient_grid = tuple(tuple(row) for row in transient)
        planner = SemanticPlannerState(
            queue=list(plan[1:]),
            active_operator=instruction.operator_id,
            active_instruction_digest=digest_object(instruction),
            active_plan_signature="semantic-plan:occluded-transient",
            source_signature="visual-state:fixture",
        )

        for expected_count in range(1, 4):
            expected_action = plan[expected_count]
            decision = planner.decide(
                transient_grid,
                (1, 2, 3, 4, 6),
                (instruction,),
                source_signature="visual-state:transient",
            )
            self.assertEqual(decision.action, expected_action)
            self.assertEqual(
                planner.occluded_route_wait_count,
                expected_count,
            )

        restored = SemanticPlannerState.from_payload(
            planner.to_payload()
        )
        self.assertEqual(restored.occluded_route_wait_count, 3)
        exhausted = restored.decide(
            transient_grid,
            (1, 2, 3, 4, 6),
            (instruction,),
            source_signature="visual-state:transient",
        )
        self.assertIsNone(exhausted.action)
        self.assertEqual(restored.occluded_route_wait_count, 0)
        self.assertEqual(restored.queue, [])

    def test_instruction_material_is_identity_free(self) -> None:
        mapping = occluded_target_route_instruction_mapping()

        self.assertEqual(
            mapping["operator_id"],
            OCCLUDED_TARGET_ROUTE_OPERATOR,
        )
        self.assertEqual(forbidden_runtime_paths(mapping), ())


if __name__ == "__main__":
    unittest.main()
