from __future__ import annotations

import unittest

from arc3_agi_agent.instruction_body import SemanticOperatorInstruction
from arc3_agi_agent.schema import digest_object
from arc3_agi_agent.selectable_route import (
    SELECTABLE_ROUTE_TARGET_OPERATOR,
    _route_model,
    _route_objects_from_sizes,
    _RouteParameters,
    _transition,
    selectable_route_action_matches_state,
    selectable_route_target_plan,
)
from arc3_agi_agent.semantic_operators import SemanticPlannerState


def _instruction(
    *,
    maximum_search_states: int = 200000,
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
        "push_through_color": 15,
        "target_inset": 1,
        "minimum_object_count": 4,
        "maximum_object_count": 8,
        "minimum_push_steps": 5,
        "maximum_push_steps": 32,
        "maximum_search_states": maximum_search_states,
        "maximum_plan_actions": 128,
        "maximum_transition_observations": 8,
    }
    return SemanticOperatorInstruction(
        operator_id=SELECTABLE_ROUTE_TARGET_OPERATOR,
        action_id=6,
        detector="rendered selectable objects and matched targets",
        transform="bounded observation-state search",
        parameter_items=tuple(sorted(parameters.items())),
        preconditions=("rendered roles close",),
        falsification_conditions=("reobserved transition differs",),
        provenance=("identity-free-synthetic-fixture",),
    )


def _ring(
    grid: list[list[int]],
    *,
    x: int,
    y: int,
    width: int,
    height: int,
) -> None:
    for cell_x in range(x, x + width):
        grid[y][cell_x] = 4
        grid[y + height - 1][cell_x] = 4
    for cell_y in range(y, y + height):
        grid[cell_y][x] = 4
        grid[cell_y][x + width - 1] = 4


def _object(
    grid: list[list[int]],
    *,
    x: int,
    y: int,
    width: int,
    height: int,
    selected: bool,
) -> None:
    for cell_y in range(y, y + height):
        for cell_x in range(x, x + width):
            grid[cell_y][cell_x] = 14
    marker_width = width // 3
    marker_height = height // 3
    marker_x = x + (width - marker_width) // 2
    marker_y = y + (height - marker_height) // 2
    for cell_y in range(marker_y, marker_y + marker_height):
        for cell_x in range(marker_x, marker_x + marker_width):
            grid[cell_y][cell_x] = 0 if selected else 5


def _simple_grid(
    *,
    shift_x: int = 0,
) -> tuple[tuple[int, ...], ...]:
    grid = [[1 for _x in range(44)] for _y in range(40)]
    grid[-1] = [2 for _x in range(44)]
    objects = (
        (3 + shift_x, 3, 3, 3, True),
        (3 + shift_x, 15, 3, 6, False),
        (21 + shift_x, 3, 6, 3, False),
        (21 + shift_x, 18, 6, 6, False),
    )
    goals = (
        (9 + shift_x, 3, 3, 3),
        (9 + shift_x, 15, 3, 6),
        (21 + shift_x, 9, 6, 3),
        (21 + shift_x, 27, 6, 6),
    )
    for x, y, width, height, selected in objects:
        _object(
            grid,
            x=x,
            y=y,
            width=width,
            height=height,
            selected=selected,
        )
    for x, y, width, height in goals:
        _ring(
            grid,
            x=x - 1,
            y=y - 1,
            width=width + 2,
            height=height + 2,
        )
    return tuple(tuple(row) for row in grid)


def _push_grid() -> tuple[tuple[int, ...], ...]:
    grid = [[1 for _x in range(44)] for _y in range(40)]
    grid[-1] = [2 for _x in range(44)]
    objects = (
        (15, 3, 3, 3, False),
        (9, 3, 3, 6, True),
        (3, 27, 6, 3, False),
        (21, 27, 6, 6, False),
    )
    goals = (
        (30, 3, 3, 3),
        (9, 15, 3, 6),
        (12, 27, 6, 3),
        (30, 27, 6, 6),
    )
    for x, y, width, height, selected in objects:
        _object(
            grid,
            x=x,
            y=y,
            width=width,
            height=height,
            selected=selected,
        )
    for x, y, width, height in goals:
        _ring(
            grid,
            x=x - 1,
            y=y - 1,
            width=width + 2,
            height=height + 2,
        )
    for y in range(13):
        for x in range(21, 24):
            grid[y][x] = 15
    return tuple(tuple(row) for row in grid)


class SelectableRouteTests(unittest.TestCase):
    def test_plan_reaches_all_dimension_matched_targets(self) -> None:
        instruction = _instruction()
        grid = _simple_grid()
        parameters = _RouteParameters.from_instruction(instruction)
        self.assertIsNotNone(parameters)
        assert parameters is not None
        model = _route_model(grid, parameters)
        self.assertIsNotNone(model)
        assert model is not None

        plan = selectable_route_target_plan(
            grid,
            (1, 2, 3, 4, 6),
            instruction,
        )
        self.assertTrue(plan)
        state = (model.initial_positions, model.selected_index)
        for action in plan:
            if action.action_id == instruction.action_id:
                matches = tuple(
                    index
                    for index, position in enumerate(state[0])
                    if (
                        action.x is not None
                        and action.y is not None
                        and position[0] <= action.x
                        < position[0] + model.sizes[index][0]
                        and position[1] <= action.y
                        < position[1] + model.sizes[index][1]
                    )
                )
                self.assertEqual(len(matches), 1)
                state = _transition(
                    model,
                    state,
                    ("select", matches[0]),
                )
            else:
                state = _transition(
                    model,
                    state,
                    ("move", action.action_id),
                )

        self.assertEqual(state[0], model.goals)

    def test_translation_moves_clicks_without_fixed_coordinates(self) -> None:
        instruction = _instruction()
        first = selectable_route_target_plan(
            _simple_grid(),
            (1, 2, 3, 4, 6),
            instruction,
        )
        shifted = selectable_route_target_plan(
            _simple_grid(shift_x=2),
            (1, 2, 3, 4, 6),
            instruction,
        )

        self.assertEqual(
            [action.action_id for action in first],
            [action.action_id for action in shifted],
        )
        first_clicks = [
            (action.x, action.y)
            for action in first
            if action.action_id == instruction.action_id
        ]
        shifted_clicks = [
            (action.x, action.y)
            for action in shifted
            if action.action_id == instruction.action_id
        ]
        self.assertEqual(
            shifted_clicks,
            [
                (x + 2, y)
                for x, y in first_clicks
                if x is not None
            ],
        )

    def test_push_transition_crosses_only_push_through_terrain(self) -> None:
        instruction = _instruction()
        parameters = _RouteParameters.from_instruction(instruction)
        self.assertIsNotNone(parameters)
        assert parameters is not None
        model = _route_model(_push_grid(), parameters)
        self.assertIsNotNone(model)
        assert model is not None
        state = (model.initial_positions, model.selected_index)

        first = _transition(model, state, ("move", 4))
        pushed = _transition(model, first, ("move", 4))
        self.assertEqual(first[0][1], (12, 3))
        self.assertEqual(pushed[0][0], (30, 3))
        self.assertEqual(pushed[0][1], (12, 3))

        selected_small = (state[0], 0)
        before_barrier = _transition(
            model,
            selected_small,
            ("move", 4),
        )
        blocked = _transition(
            model,
            before_barrier,
            ("move", 4),
        )
        self.assertEqual(before_barrier[0][0], (18, 3))
        self.assertEqual(blocked, before_barrier)

    def test_queued_action_requires_matching_reobservation(self) -> None:
        instruction = _instruction()
        grid = _simple_grid()
        plan = selectable_route_target_plan(
            grid,
            (1, 2, 3, 4, 6),
            instruction,
        )
        self.assertGreaterEqual(len(plan), 2)

        self.assertTrue(
            selectable_route_action_matches_state(
                grid,
                instruction,
                plan[0],
            )
        )
        self.assertFalse(
            selectable_route_action_matches_state(
                grid,
                instruction,
                plan[1],
            )
        )

    def test_released_selection_marker_remains_a_detectable_object(
        self,
    ) -> None:
        grid = [list(row) for row in _simple_grid()]
        grid[4][4] = 4
        for y in range(20, 22):
            for x in range(23, 25):
                grid[y][x] = 0
        instruction = _instruction()
        parameters = _RouteParameters.from_instruction(instruction)
        self.assertIsNotNone(parameters)
        assert parameters is not None

        model = _route_model(tuple(tuple(row) for row in grid), parameters)

        self.assertIsNotNone(model)
        assert model is not None
        self.assertEqual(model.selected_index, 3)
        self.assertEqual(model.objects[0].marker_color, 4)

    def test_transient_frames_are_bounded_reobservations(self) -> None:
        instruction = _instruction()
        grid = _simple_grid()
        plan = selectable_route_target_plan(
            grid,
            (1, 2, 3, 4, 6),
            instruction,
        )
        self.assertGreaterEqual(len(plan), 2)
        transient = [list(row) for row in grid]
        transient[15][3] = 0
        transient_grid = tuple(tuple(row) for row in transient)
        planner = SemanticPlannerState(
            queue=list(plan[1:]),
            active_operator=instruction.operator_id,
            active_instruction_digest=digest_object(instruction),
            active_plan_signature="semantic-plan:transient-fixture",
            source_signature="visual-state:fixture",
        )

        for expected_count in range(1, 9):
            decision = planner.decide(
                transient_grid,
                (1, 2, 3, 4, 6),
                (instruction,),
                source_signature="visual-state:transient",
            )
            self.assertEqual(decision.action, plan[1])
            self.assertEqual(
                planner.selectable_route_wait_count,
                expected_count,
            )
            self.assertEqual(len(planner.queue), len(plan) - 1)

        exhausted = planner.decide(
            transient_grid,
            (1, 2, 3, 4, 6),
            (instruction,),
            source_signature="visual-state:transient",
        )
        self.assertIsNone(exhausted.action)
        self.assertEqual(planner.selectable_route_wait_count, 0)
        self.assertEqual(planner.queue, [])

    def test_ambiguous_target_or_search_bound_rejects(self) -> None:
        grid = [list(row) for row in _simple_grid()]
        _ring(grid, x=34, y=2, width=5, height=5)
        ambiguous = tuple(tuple(row) for row in grid)

        self.assertEqual(
            selectable_route_target_plan(
                ambiguous,
                (1, 2, 3, 4, 6),
                _instruction(),
            ),
            (),
        )
        self.assertEqual(
            selectable_route_target_plan(
                _simple_grid(),
                (1, 2, 3, 4, 6),
                _instruction(maximum_search_states=1),
            ),
            (),
        )

    def test_object_assignment_respects_the_p_search_bound(self) -> None:
        grid = [list(row) for row in _simple_grid()]
        _object(
            grid,
            x=33,
            y=30,
            width=3,
            height=3,
            selected=False,
        )
        rendered = tuple(tuple(row) for row in grid)
        sizes = ((3, 3), (3, 6), (6, 3), (6, 6))

        bounded = _RouteParameters.from_instruction(
            _instruction(maximum_search_states=1)
        )
        sufficient = _RouteParameters.from_instruction(
            _instruction(maximum_search_states=2)
        )
        self.assertIsNotNone(bounded)
        self.assertIsNotNone(sufficient)
        assert bounded is not None
        assert sufficient is not None

        self.assertEqual(
            _route_objects_from_sizes(
                rendered,
                sizes,
                bounded,
                stride=3,
            ),
            (),
        )
        self.assertEqual(
            len(
                _route_objects_from_sizes(
                    rendered,
                    sizes,
                    sufficient,
                    stride=3,
                )
            ),
            4,
        )


if __name__ == "__main__":
    unittest.main()
