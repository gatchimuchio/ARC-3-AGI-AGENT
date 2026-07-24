from __future__ import annotations

import unittest
from dataclasses import replace

from arc3_agi_agent.instruction_body import SemanticOperatorInstruction
from arc3_agi_agent.schema import digest_object
from arc3_agi_agent.semantic_operators import SemanticPlannerState
from arc3_agi_agent.shape_push import (
    MARKER_SHAPE_PUSH_TARGET_OPERATOR,
    _canonical_positions,
    _is_goal,
    _positions_between_transition,
    _shape_push_model,
    _ShapePushModel,
    _ShapePushParameters,
    _transition,
    marker_shape_push_observation_status,
    marker_shape_push_target_plan,
)


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
        "marker_divisor": 3,
        "target_inset": 1,
        "minimum_pushable_count": 1,
        "maximum_pushable_count": 8,
        "minimum_target_side": 3,
        "maximum_target_side": 16,
        "minimum_push_steps": 5,
        "maximum_push_steps": 32,
        "push_through_color": 15,
        "maximum_search_states": maximum_search_states,
        "maximum_plan_actions": 192,
        "maximum_transition_observations": 8,
    }
    return SemanticOperatorInstruction(
        operator_id=MARKER_SHAPE_PUSH_TARGET_OPERATOR,
        action_id=6,
        detector="rendered actor, filled shapes, and outline targets",
        transform="bounded actor-mediated impulse-push search",
        parameter_items=tuple(sorted(parameters.items())),
        preconditions=("rendered roles close",),
        falsification_conditions=("reobserved state differs",),
        provenance=("identity-free-synthetic-fixture",),
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


def _filled_shape(
    grid: list[list[int]],
    *,
    x: int,
    y: int,
    mask: tuple[tuple[int, int], ...],
    color: int,
) -> None:
    for dx, dy in mask:
        grid[y + dy][x + dx] = color


def _outline_target(
    grid: list[list[int]],
    *,
    goal_x: int,
    goal_y: int,
    mask: tuple[tuple[int, int], ...],
    color: int = 4,
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
        grid[y][x] = color


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


def _shape_grid(
    *,
    shift_x: int = 0,
) -> tuple[tuple[int, ...], ...]:
    grid = [[1 for _x in range(64)] for _y in range(64)]
    grid[-1] = [2 for _x in range(64)]
    plus = _plus_mask()
    _actor(grid, x=44 + shift_x, y=14)
    _outline_target(
        grid,
        goal_x=35 + shift_x,
        goal_y=29,
        mask=tuple(
            sorted(
                (x, y)
                for y in range(3)
                for x in range(3)
            )
        ),
    )
    _filled_shape(
        grid,
        x=50 + shift_x,
        y=20,
        mask=plus,
        color=11,
    )
    _filled_shape(
        grid,
        x=20 + shift_x,
        y=35,
        mask=plus,
        color=11,
    )
    _outline_target(
        grid,
        goal_x=20 + shift_x,
        goal_y=20,
        mask=plus,
    )
    _outline_target(
        grid,
        goal_x=35 + shift_x,
        goal_y=35,
        mask=plus,
    )
    return tuple(tuple(row) for row in grid)


def _dynamic_footer_grid(
    grid: tuple[tuple[int, ...], ...],
    *,
    progress: int,
) -> tuple[tuple[int, ...], ...]:
    rows = [list(row) for row in grid[:62]]
    width = len(rows[0])
    rows.append([2 for _x in range(width)])
    rows.append(
        [
            4 if x < progress else 0
            for x in range(width)
        ]
    )
    return tuple(tuple(row) for row in rows)


def _render_state(
    model: _ShapePushModel,
    state: tuple[tuple[int, int], ...],
) -> tuple[tuple[int, ...], ...]:
    grid = [list(row) for row in model.terrain]
    for index, entity in enumerate(model.entities):
        x0, y0 = state[index]
        for dx, dy in entity.mask:
            grid[y0 + dy][x0 + dx] = entity.color
        if entity.role == "actor":
            marker_x = x0 + entity.width // 2
            marker_y = y0 + entity.height // 2
            grid[marker_y][marker_x] = (
                model.parameters.selected_marker_color
            )
    return tuple(tuple(row) for row in grid)


class MarkerShapePushTests(unittest.TestCase):
    def test_plan_closes_actor_and_shape_target_obligations(self) -> None:
        instruction = _instruction()
        parameters = _ShapePushParameters.from_instruction(instruction)
        self.assertIsNotNone(parameters)
        assert parameters is not None
        model = _shape_push_model(_shape_grid(), parameters)
        self.assertIsNotNone(model)
        assert model is not None

        plan = marker_shape_push_target_plan(
            _shape_grid(),
            (1, 2, 3, 4, 6),
            instruction,
        )

        self.assertTrue(plan)
        state = model.initial_positions
        for action in plan:
            state = _transition(model, state, action.action_id)
        self.assertTrue(_is_goal(model, state))

    def test_translation_preserves_actions_without_literal_routing(
        self,
    ) -> None:
        instruction = _instruction()

        first = marker_shape_push_target_plan(
            _shape_grid(),
            (1, 2, 3, 4, 6),
            instruction,
        )
        translated = marker_shape_push_target_plan(
            _shape_grid(shift_x=-3),
            (1, 2, 3, 4, 6),
            instruction,
        )

        self.assertEqual(
            [action.action_id for action in first],
            [action.action_id for action in translated],
        )
        self.assertTrue(
            all(action.x is None and action.y is None for action in first)
        )

    def test_open_outline_and_search_bound_fail_closed(self) -> None:
        instruction = _instruction()
        open_grid = [list(row) for row in _shape_grid()]
        open_grid[19][23] = 1

        self.assertEqual(
            marker_shape_push_target_plan(
                tuple(tuple(row) for row in open_grid),
                (1, 2, 3, 4, 6),
                instruction,
            ),
            (),
        )
        self.assertEqual(
            marker_shape_push_target_plan(
                _shape_grid(),
                (1, 2, 3, 4, 6),
                _instruction(maximum_search_states=1),
            ),
            (),
        )

    def test_queued_state_requires_coherent_predecessor(self) -> None:
        instruction = _instruction()
        grid = _shape_grid()
        parameters = _ShapePushParameters.from_instruction(instruction)
        self.assertIsNotNone(parameters)
        assert parameters is not None
        model = _shape_push_model(grid, parameters)
        self.assertIsNotNone(model)
        assert model is not None
        plan = marker_shape_push_target_plan(
            grid,
            (1, 2, 3, 4, 6),
            instruction,
        )
        self.assertGreaterEqual(len(plan), 2)

        self.assertEqual(
            marker_shape_push_observation_status(
                grid,
                instruction,
                plan[0],
            ),
            "MISMATCH",
        )
        self.assertEqual(
            marker_shape_push_observation_status(
                grid,
                instruction,
                plan[1],
            ),
            "UNAVAILABLE",
        )
        expected = _transition(
            model,
            model.initial_positions,
            plan[0].action_id,
        )
        self.assertEqual(
            marker_shape_push_observation_status(
                _render_state(model, expected),
                instruction,
                plan[1],
            ),
            "MATCH",
        )
        tampered_action = replace(
            plan[1],
            evidence=tuple(
                (
                    "shape-push-predecessor-action:7"
                    if item.startswith(
                        "shape-push-predecessor-action:"
                    )
                    else item
                )
                for item in plan[1].evidence
            ),
        )
        self.assertEqual(
            marker_shape_push_observation_status(
                _render_state(model, expected),
                instruction,
                tampered_action,
            ),
            "MISMATCH",
        )
        self.assertEqual(
            marker_shape_push_observation_status(
                _render_state(model, expected),
                instruction,
                replace(plan[1], action_id=7),
            ),
            "MISMATCH",
        )
        changed_terrain = [
            list(row) for row in _render_state(model, expected)
        ]
        changed_terrain[0][0] = 13
        self.assertEqual(
            marker_shape_push_observation_status(
                tuple(tuple(row) for row in changed_terrain),
                instruction,
                plan[1],
            ),
            "MISMATCH",
        )

    def test_dynamic_footer_is_excluded_from_queue_evidence(
        self,
    ) -> None:
        instruction = _instruction()
        parameters = _ShapePushParameters.from_instruction(instruction)
        self.assertIsNotNone(parameters)
        assert parameters is not None
        first_grid = _dynamic_footer_grid(
            _shape_grid(),
            progress=12,
        )
        second_grid = _dynamic_footer_grid(
            _shape_grid(),
            progress=29,
        )
        first_model = _shape_push_model(first_grid, parameters)
        second_model = _shape_push_model(second_grid, parameters)
        self.assertIsNotNone(first_model)
        self.assertIsNotNone(second_model)
        assert first_model is not None
        assert second_model is not None
        self.assertEqual(first_model.height, 62)
        self.assertEqual(first_model.terrain, second_model.terrain)

        plan = marker_shape_push_target_plan(
            first_grid,
            (1, 2, 3, 4, 6),
            instruction,
        )
        self.assertGreaterEqual(len(plan), 2)
        expected = _transition(
            first_model,
            first_model.initial_positions,
            plan[0].action_id,
        )

        for progress in (13, 41):
            observed = _dynamic_footer_grid(
                _render_state(first_model, expected),
                progress=progress,
            )
            self.assertEqual(
                marker_shape_push_observation_status(
                    observed,
                    instruction,
                    plan[1],
                ),
                "MATCH",
            )

    def test_impulse_transition_accepts_only_bounded_axis_progress(
        self,
    ) -> None:
        predecessor = ((9, 9), (12, 15), (30, 30))
        expected = ((9, 9), (27, 15), (30, 30))

        self.assertTrue(
            _positions_between_transition(
                predecessor,
                expected,
                ((9, 9), (18, 15), (30, 30)),
                stride=3,
            )
        )
        self.assertFalse(
            _positions_between_transition(
                predecessor,
                expected,
                ((9, 9), (18, 18), (30, 30)),
                stride=3,
            )
        )
        self.assertFalse(
            _positions_between_transition(
                predecessor,
                expected,
                ((9, 9), (27, 15), (30, 30)),
                stride=3,
            )
        )

    def test_rendered_impulse_intermediate_is_bounded_reobservation(
        self,
    ) -> None:
        instruction = _instruction()
        parameters = _ShapePushParameters.from_instruction(instruction)
        self.assertIsNotNone(parameters)
        assert parameters is not None
        model = _shape_push_model(_shape_grid(), parameters)
        self.assertIsNotNone(model)
        assert model is not None
        plan = marker_shape_push_target_plan(
            _shape_grid(),
            (1, 2, 3, 4, 6),
            instruction,
        )
        states = [
            _canonical_positions(
                model,
                list(model.initial_positions),
            )
        ]
        for action in plan:
            states.append(
                _transition(model, states[-1], action.action_id)
            )
        transition_index = next(
            index
            for index, (before, after) in enumerate(
                zip(states[:-1], states[1:], strict=True)
            )
            if (
                index + 1 < len(plan)
                and any(
                    abs(end[0] - start[0])
                    + abs(end[1] - start[1])
                    > model.stride
                    for start, end in zip(before, after, strict=True)
                )
            )
        )
        predecessor = states[transition_index]
        expected = states[transition_index + 1]
        intermediate = tuple(
            (
                start[0]
                + (
                    (end[0] > start[0])
                    - (end[0] < start[0])
                )
                * model.stride,
                start[1]
                + (
                    (end[1] > start[1])
                    - (end[1] < start[1])
                )
                * model.stride,
            )
            for start, end in zip(
                predecessor,
                expected,
                strict=True,
            )
        )
        queued_action = plan[transition_index + 1]

        self.assertEqual(
            marker_shape_push_observation_status(
                _render_state(model, intermediate),
                instruction,
                queued_action,
            ),
            "UNAVAILABLE",
        )
        self.assertEqual(
            marker_shape_push_observation_status(
                _render_state(model, expected),
                instruction,
                queued_action,
            ),
            "MATCH",
        )

    def test_walkable_hint_recovers_model_with_occupied_targets(
        self,
    ) -> None:
        instruction = _instruction()
        parameters = _ShapePushParameters.from_instruction(instruction)
        self.assertIsNotNone(parameters)
        assert parameters is not None
        model = _shape_push_model(_shape_grid(), parameters)
        self.assertIsNotNone(model)
        assert model is not None
        plan = marker_shape_push_target_plan(
            _shape_grid(),
            (1, 2, 3, 4, 6),
            instruction,
        )
        state = model.initial_positions
        for action in plan:
            state = _transition(model, state, action.action_id)
        self.assertTrue(_is_goal(model, state))

        recovered = _shape_push_model(
            _render_state(model, state),
            parameters,
            walkable_hint=model.walkable_color,
        )

        self.assertIsNotNone(recovered)

    def test_transient_shape_frames_are_bounded(self) -> None:
        instruction = _instruction()
        grid = _shape_grid()
        plan = marker_shape_push_target_plan(
            grid,
            (1, 2, 3, 4, 6),
            instruction,
        )
        self.assertGreaterEqual(len(plan), 2)
        transient = [list(row) for row in grid]
        transient[23][50] = 12
        transient_grid = tuple(tuple(row) for row in transient)
        planner = SemanticPlannerState(
            queue=list(plan[1:]),
            active_operator=instruction.operator_id,
            active_instruction_digest=digest_object(instruction),
            active_plan_signature="semantic-plan:shape-transient",
            source_signature="visual-state:fixture",
        )

        for expected_count in range(1, 9):
            expected_action = plan[expected_count]
            decision = planner.decide(
                transient_grid,
                (1, 2, 3, 4, 6),
                (instruction,),
                source_signature="visual-state:transient",
            )
            self.assertEqual(decision.action, expected_action)
            self.assertEqual(
                planner.shape_push_wait_count,
                expected_count,
            )
            self.assertEqual(
                len(planner.queue),
                len(plan) - 1 - expected_count,
            )

        exhausted = planner.decide(
            transient_grid,
            (1, 2, 3, 4, 6),
            (instruction,),
            source_signature="visual-state:transient",
        )
        self.assertIsNone(exhausted.action)
        self.assertEqual(planner.shape_push_wait_count, 0)
        self.assertEqual(planner.queue, [])


if __name__ == "__main__":
    unittest.main()
