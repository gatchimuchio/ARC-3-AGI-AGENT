from __future__ import annotations

import unittest
from dataclasses import replace

from arc3_agi_agent.directional_force_route import (
    _DirectionalForceParameters,
    _force_route_model,
    _render_state,
    _shape_solved,
    _stage,
    _transition,
    directional_force_route_observation_matches,
    directional_force_route_plan,
)
from arc3_agi_agent.instruction_body import SemanticOperatorInstruction
from arc3_agi_agent.p10_instruction_compiler import (
    directional_force_route_instruction_mapping,
)


def _instruction(
    **parameter_overrides: int,
) -> SemanticOperatorInstruction:
    mapping = directional_force_route_instruction_mapping()
    parameters = dict(mapping["parameters"])
    parameters.update(parameter_overrides)
    return SemanticOperatorInstruction(
        operator_id=str(mapping["operator_id"]),
        action_id=int(mapping["action_id"]),
        detector=str(mapping["detector"]),
        transform=str(mapping["transform"]),
        parameter_items=tuple(sorted(parameters.items())),
        preconditions=tuple(str(item) for item in mapping["preconditions"]),
        falsification_conditions=tuple(
            str(item) for item in mapping["falsification_conditions"]
        ),
        provenance=tuple(str(item) for item in mapping["provenance"]),
    )


def _plus_mask() -> tuple[tuple[int, int], ...]:
    return tuple(
        sorted(
            (x, y)
            for y in range(9)
            for x in range(9)
            if 3 <= x <= 5 or 3 <= y <= 5
        )
    )


def _filled(
    grid: list[list[int]],
    *,
    x: int,
    y: int,
    mask: tuple[tuple[int, int], ...],
    color: int,
) -> None:
    for dx, dy in mask:
        grid[y + dy][x + dx] = color


def _outline(
    grid: list[list[int]],
    *,
    goal_x: int,
    goal_y: int,
    mask: tuple[tuple[int, int], ...],
) -> None:
    interior = {
        (goal_x + dx, goal_y + dy)
        for dx, dy in mask
    }
    outline = {
        (x + dx, y + dy)
        for x, y in interior
        for dx in (-1, 0, 1)
        for dy in (-1, 0, 1)
    } - interior
    for x, y in outline:
        grid[y][x] = 4


def _actor(
    grid: list[list[int]],
    *,
    x: int,
    y: int,
) -> None:
    for dy in range(3):
        for dx in range(3):
            grid[y + dy][x + dx] = 14
    grid[y + 1][x + 1] = 0


def _force(
    grid: list[list[int]],
    *,
    x: int,
    y: int,
    direction: tuple[int, int],
    phase: int,
) -> None:
    for dy in range(6):
        for dx in range(6):
            charged = (
                (direction == (0, 1) and dy < phase)
                or (direction == (0, -1) and dy >= 6 - phase)
                or (direction == (1, 0) and dx < phase)
                or (direction == (-1, 0) and dx >= 6 - phase)
            )
            grid[y + dy][x + dx] = 12 if charged else 13


def _force_grid(
    *,
    phase: int = 0,
) -> tuple[tuple[int, ...], ...]:
    grid = [[1 for _x in range(64)] for _y in range(64)]
    for x in range(64):
        grid[0][x] = 2
    for y in range(63):
        grid[y][0] = 2
        grid[y][63] = 2
    for y in range(36):
        for x in range(30, 33):
            grid[y][x] = 2
    for y in range(30, 36):
        for x in range(1, 63):
            grid[y][x] = 15
        for x in range(30, 33):
            grid[y][x] = 2
    for y in range(51, 54):
        for x in range(3, 60):
            grid[y][x] = 2
    _outline(
        grid,
        goal_x=48,
        goal_y=21,
        mask=tuple((x, y) for y in range(3) for x in range(3)),
    )
    plus = _plus_mask()
    _outline(grid, goal_x=3, goal_y=3, mask=plus)
    _filled(grid, x=6, y=15, mask=plus, color=11)
    _force(grid, x=24, y=15, direction=(0, 1), phase=phase)
    _force(grid, x=33, y=15, direction=(0, 1), phase=phase)
    _force(grid, x=42, y=45, direction=(0, -1), phase=phase)
    _actor(grid, x=51, y=48)
    grid[63] = [4 if x < 40 else 0 for x in range(64)]
    return tuple(tuple(row) for row in grid)


def _mirror(
    grid: tuple[tuple[int, ...], ...],
) -> tuple[tuple[int, ...], ...]:
    return tuple(tuple(reversed(row)) for row in grid)


def _rotate_clockwise(
    grid: tuple[tuple[int, ...], ...],
) -> tuple[tuple[int, ...], ...]:
    return tuple(
        tuple(grid[len(grid) - 1 - x][y] for x in range(len(grid)))
        for y in range(len(grid[0]))
    )


def _solve_rendered(
    grid: tuple[tuple[int, ...], ...],
    instruction: SemanticOperatorInstruction,
) -> tuple[int, ...]:
    parameters = _DirectionalForceParameters.from_instruction(instruction)
    assert parameters is not None
    actions: list[int] = []
    current = grid
    for _iteration in range(8):
        model = _force_route_model(current, parameters)
        if model is None:
            break
        if (
            _shape_solved(model, model.initial_state)
            and model.initial_state.positions[0] == model.shape.actor_goal
        ):
            return tuple(actions)
        plan = directional_force_route_plan(
            current,
            (1, 2, 3, 4, 6),
            instruction,
        )
        if not plan:
            break
        state = model.initial_state
        for action in plan:
            state = _transition(model, state, action.action_id)
            actions.append(action.action_id)
        if (
            _shape_solved(model, state)
            and state.positions[0] == model.shape.actor_goal
        ):
            return tuple(actions)
        current = _render_state(model, state)
    return ()


class DirectionalForceRouteTests(unittest.TestCase):
    def test_bounded_rendered_stage_search_closes_both_obligations(
        self,
    ) -> None:
        instruction = _instruction()
        parameters = _DirectionalForceParameters.from_instruction(
            instruction
        )
        self.assertIsNotNone(parameters)
        assert parameters is not None
        self.assertEqual(parameters.maximum_search_states, 2000)

        actions = _solve_rendered(_force_grid(), instruction)

        self.assertTrue(actions)
        self.assertLessEqual(len(actions), 64)

    def test_horizontal_reflection_remains_solvable(self) -> None:
        actions = _solve_rendered(_mirror(_force_grid()), _instruction())

        self.assertTrue(actions)
        self.assertLessEqual(len(actions), 64)

    def test_quarter_turn_remains_solvable(self) -> None:
        actions = _solve_rendered(
            _rotate_clockwise(_force_grid()),
            _instruction(),
        )

        self.assertTrue(actions)
        self.assertLessEqual(len(actions), 64)

    def test_stage_plan_is_derived_from_rendered_phase(self) -> None:
        instruction = _instruction()
        parameters = _DirectionalForceParameters.from_instruction(
            instruction
        )
        self.assertIsNotNone(parameters)
        assert parameters is not None
        model = _force_route_model(_force_grid(phase=2), parameters)
        self.assertIsNotNone(model)
        assert model is not None

        self.assertEqual(model.initial_state.phase, 2)
        self.assertEqual(_stage(model, model.initial_state), "enter-shape-region")
        plan = directional_force_route_plan(
            _force_grid(phase=2),
            (1, 2, 3, 4, 6),
            instruction,
        )
        self.assertTrue(plan)
        self.assertTrue(all(action.x is None for action in plan))
        self.assertTrue(all(action.y is None for action in plan))

    def test_queued_action_requires_expected_rendered_state(self) -> None:
        instruction = _instruction()
        parameters = _DirectionalForceParameters.from_instruction(
            instruction
        )
        self.assertIsNotNone(parameters)
        assert parameters is not None
        model = _force_route_model(_force_grid(), parameters)
        self.assertIsNotNone(model)
        assert model is not None
        plan = directional_force_route_plan(
            _force_grid(),
            (1, 2, 3, 4, 6),
            instruction,
        )
        self.assertGreaterEqual(len(plan), 2)
        expected = _transition(
            model,
            model.initial_state,
            plan[0].action_id,
        )
        expected_grid = _render_state(model, expected)

        self.assertTrue(
            directional_force_route_observation_matches(
                expected_grid,
                instruction,
                plan[1],
            )
        )
        changed = [list(row) for row in expected_grid]
        changed[10][10] = 9
        self.assertFalse(
            directional_force_route_observation_matches(
                tuple(tuple(row) for row in changed),
                instruction,
                plan[1],
            )
        )
        self.assertFalse(
            directional_force_route_observation_matches(
                expected_grid,
                instruction,
                replace(plan[1], action_id=7),
            )
        )

    def test_ambiguous_charge_and_search_bound_fail_closed(self) -> None:
        instruction = _instruction()
        inconsistent = [list(row) for row in _force_grid(phase=1)]
        for x in range(24, 30):
            inconsistent[16][x] = 12
        additional_actor = [list(row) for row in _force_grid()]
        additional_actor[57][55] = 5

        self.assertEqual(
            directional_force_route_plan(
                tuple(tuple(row) for row in inconsistent),
                (1, 2, 3, 4, 6),
                instruction,
            ),
            (),
        )
        self.assertEqual(
            directional_force_route_plan(
                tuple(tuple(row) for row in additional_actor),
                (1, 2, 3, 4, 6),
                instruction,
            ),
            (),
        )
        self.assertEqual(
            directional_force_route_plan(
                _force_grid(),
                (1, 2, 3, 4, 6),
                _instruction(maximum_search_states=1),
            ),
            (),
        )

    def test_instruction_surface_is_identity_free(self) -> None:
        self.assertEqual(_instruction().validate(), ())


if __name__ == "__main__":
    unittest.main()
