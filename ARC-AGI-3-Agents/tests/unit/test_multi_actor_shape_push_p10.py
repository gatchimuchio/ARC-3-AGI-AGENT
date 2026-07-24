from __future__ import annotations

import unittest
from dataclasses import replace

from arc3_agi_agent.instruction_body import SemanticOperatorInstruction
from arc3_agi_agent.multi_actor_shape_push import (
    MULTI_ACTOR_SHAPE_PUSH_TARGET_OPERATOR,
    _canonical_state,
    _is_goal,
    _Model,
    _model,
    _Parameters,
    _search,
    _transition,
    multi_actor_shape_push_observation_status,
    multi_actor_shape_push_target_plan,
)
from arc3_agi_agent.p10_instruction_compiler import (
    multi_actor_shape_push_target_instruction_mapping,
)
from arc3_agi_agent.schema import digest_object, forbidden_runtime_paths
from arc3_agi_agent.semantic_operators import SemanticPlannerState

Mask = tuple[tuple[int, int], ...]


def _instruction(
    *,
    maximum_search_states: int = 600000,
) -> SemanticOperatorInstruction:
    mapping = multi_actor_shape_push_target_instruction_mapping()
    parameters = dict(mapping["parameters"])
    parameters["maximum_search_states"] = maximum_search_states
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


def _rectangle_mask(width: int, height: int) -> Mask:
    return tuple(
        sorted(
            (x, y)
            for y in range(height)
            for x in range(width)
        )
    )


def _plus_mask() -> Mask:
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
    mask: Mask,
    color: int,
) -> None:
    for dx, dy in mask:
        grid[y + dy][x + dx] = color


def _outline_target(
    grid: list[list[int]],
    *,
    goal_x: int,
    goal_y: int,
    mask: Mask,
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
    marker: int,
) -> None:
    for dy in range(3):
        for dx in range(3):
            grid[y + dy][x + dx] = 14
    grid[y + 1][x + 1] = marker


def _multi_shape_grid(
    *,
    shift_x: int = 0,
    footer_progress: int | None = None,
) -> tuple[tuple[int, ...], ...]:
    grid = [[2 for _x in range(64)] for _y in range(64)]
    for y in range(6, 38):
        for x in range(5 + shift_x, 59 + shift_x):
            grid[y][x] = 1
    for y in range(44, 59):
        for x in range(5 + shift_x, 44 + shift_x):
            grid[y][x] = 1
    for y in range(38, 44):
        for x in range(5 + shift_x, 44 + shift_x):
            grid[y][x] = 15

    square = _rectangle_mask(3, 3)
    plus = _plus_mask()
    _outline_target(
        grid,
        goal_x=50 + shift_x,
        goal_y=29,
        mask=square,
    )
    _outline_target(
        grid,
        goal_x=38 + shift_x,
        goal_y=53,
        mask=square,
    )
    _outline_target(
        grid,
        goal_x=35 + shift_x,
        goal_y=8,
        mask=plus,
    )
    _actor(
        grid,
        x=20 + shift_x,
        y=29,
        marker=0,
    )
    _actor(
        grid,
        x=29 + shift_x,
        y=32,
        marker=5,
    )
    _filled_shape(
        grid,
        x=20 + shift_x,
        y=50,
        mask=plus,
        color=11,
    )
    if footer_progress is None:
        grid[-1] = [2 for _x in range(64)]
    else:
        grid[-2] = [2 for _x in range(64)]
        grid[-1] = [
            4 if x < footer_progress else 0
            for x in range(64)
        ]
    return tuple(tuple(row) for row in grid)


def _render_state(
    model: _Model,
    state: tuple[tuple[tuple[int, int], ...], int],
) -> tuple[tuple[int, ...], ...]:
    positions, selected = state
    grid = [list(row) for row in model.terrain]
    grid.extend(
        [[2 for _x in range(model.width)] for _y in range(4)]
    )
    for index, entity in enumerate(model.entities):
        x0, y0 = positions[index]
        for dx, dy in entity.mask:
            grid[y0 + dy][x0 + dx] = entity.color
        if entity.selectable:
            grid[y0 + entity.height // 2][
                x0 + entity.width // 2
            ] = (
                model.parameters.selected_marker_color
                if index == selected
                else model.parameters.released_marker_color
            )
    return tuple(tuple(row) for row in grid)


class MultiActorShapePushTests(unittest.TestCase):
    def test_plan_closes_selection_push_and_shape_obligations(
        self,
    ) -> None:
        instruction = _instruction()
        parameters = _Parameters.from_instruction(instruction)
        self.assertIsNotNone(parameters)
        assert parameters is not None
        model = _model(_multi_shape_grid(), parameters)
        self.assertIsNotNone(model)
        assert model is not None

        search_plan = _search(model)
        public_plan = multi_actor_shape_push_target_plan(
            _multi_shape_grid(),
            (1, 2, 3, 4, 6),
            instruction,
        )

        self.assertTrue(search_plan)
        self.assertEqual(len(search_plan), len(public_plan))
        self.assertGreaterEqual(
            sum(kind == "select" for kind, _value in search_plan),
            2,
        )
        state = _canonical_state(
            model,
            model.initial_positions,
            model.selected_index,
        )
        for action in search_plan:
            state = _transition(model, state, action)
        self.assertTrue(_is_goal(model, state))

    def test_translation_preserves_actions_and_moves_click_points(
        self,
    ) -> None:
        instruction = _instruction()

        first = multi_actor_shape_push_target_plan(
            _multi_shape_grid(),
            (1, 2, 3, 4, 6),
            instruction,
        )
        translated = multi_actor_shape_push_target_plan(
            _multi_shape_grid(shift_x=-3),
            (1, 2, 3, 4, 6),
            instruction,
        )

        self.assertEqual(
            [action.action_id for action in first],
            [action.action_id for action in translated],
        )
        self.assertEqual(
            [
                (
                    None if action.x is None else action.x - 3,
                    action.y,
                )
                for action in first
            ],
            [(action.x, action.y) for action in translated],
        )

    def test_single_actor_missing_pushable_and_low_bound_fail_closed(
        self,
    ) -> None:
        instruction = _instruction()
        single_actor = [list(row) for row in _multi_shape_grid()]
        for y in range(32, 35):
            for x in range(29, 32):
                single_actor[y][x] = 1
        no_pushable = [list(row) for row in _multi_shape_grid()]
        for dx, dy in _plus_mask():
            no_pushable[50 + dy][20 + dx] = 1

        self.assertEqual(
            multi_actor_shape_push_target_plan(
                tuple(tuple(row) for row in single_actor),
                (1, 2, 3, 4, 6),
                instruction,
            ),
            (),
        )
        self.assertEqual(
            multi_actor_shape_push_target_plan(
                tuple(tuple(row) for row in no_pushable),
                (1, 2, 3, 4, 6),
                instruction,
            ),
            (),
        )
        self.assertEqual(
            multi_actor_shape_push_target_plan(
                _multi_shape_grid(),
                (1, 2, 3, 4, 6),
                _instruction(maximum_search_states=1),
            ),
            (),
        )

    def test_queued_state_matches_only_coherent_transition(
        self,
    ) -> None:
        instruction = _instruction()
        parameters = _Parameters.from_instruction(instruction)
        self.assertIsNotNone(parameters)
        assert parameters is not None
        grid = _multi_shape_grid()
        model = _model(grid, parameters)
        self.assertIsNotNone(model)
        assert model is not None
        search_plan = _search(model)
        public_plan = multi_actor_shape_push_target_plan(
            grid,
            (1, 2, 3, 4, 6),
            instruction,
        )
        self.assertGreaterEqual(len(public_plan), 2)
        start = _canonical_state(
            model,
            model.initial_positions,
            model.selected_index,
        )
        expected = _transition(model, start, search_plan[0])

        self.assertEqual(
            multi_actor_shape_push_observation_status(
                _render_state(model, expected),
                instruction,
                public_plan[1],
            ),
            "MATCH",
        )
        self.assertEqual(
            multi_actor_shape_push_observation_status(
                grid,
                instruction,
                public_plan[0],
            ),
            "MISMATCH",
        )
        tampered = replace(
            public_plan[1],
            evidence=tuple(
                (
                    'multi-shape-predecessor-action:["move",7]'
                    if item.startswith(
                        "multi-shape-predecessor-action:"
                    )
                    else item
                )
                for item in public_plan[1].evidence
            ),
        )
        self.assertEqual(
            multi_actor_shape_push_observation_status(
                _render_state(model, expected),
                instruction,
                tampered,
            ),
            "MISMATCH",
        )

    def test_dynamic_footer_does_not_change_plan(self) -> None:
        instruction = _instruction()

        first = multi_actor_shape_push_target_plan(
            _multi_shape_grid(footer_progress=7),
            (1, 2, 3, 4, 6),
            instruction,
        )
        second = multi_actor_shape_push_target_plan(
            _multi_shape_grid(footer_progress=41),
            (1, 2, 3, 4, 6),
            instruction,
        )

        self.assertTrue(first)
        self.assertEqual(
            [(action.action_id, action.x, action.y) for action in first],
            [(action.action_id, action.x, action.y) for action in second],
        )

    def test_transient_queue_is_bounded_and_serialized(self) -> None:
        instruction = _instruction()
        plan = multi_actor_shape_push_target_plan(
            _multi_shape_grid(),
            (1, 2, 3, 4, 6),
            instruction,
        )
        self.assertGreaterEqual(len(plan), 14)
        transient = [list(row) for row in _multi_shape_grid()]
        transient[11][44] = 1
        transient_grid = tuple(tuple(row) for row in transient)
        planner = SemanticPlannerState(
            queue=list(plan[1:]),
            active_operator=instruction.operator_id,
            active_instruction_digest=digest_object(instruction),
            active_plan_signature="semantic-plan:multi-shape-transient",
            source_signature="visual-state:fixture",
        )

        for expected_count in range(1, 13):
            expected_action = plan[expected_count]
            decision = planner.decide(
                transient_grid,
                (1, 2, 3, 4, 6),
                (instruction,),
                source_signature="visual-state:transient",
            )
            self.assertEqual(decision.action, expected_action)
            self.assertEqual(
                planner.multi_shape_push_wait_count,
                expected_count,
            )

        restored = SemanticPlannerState.from_payload(
            planner.to_payload()
        )
        self.assertEqual(
            restored.multi_shape_push_wait_count,
            12,
        )
        exhausted = restored.decide(
            transient_grid,
            (1, 2, 3, 4, 6),
            (instruction,),
            source_signature="visual-state:transient",
        )
        self.assertIsNone(exhausted.action)
        self.assertEqual(restored.multi_shape_push_wait_count, 0)
        self.assertEqual(restored.queue, [])

    def test_instruction_material_is_identity_free(self) -> None:
        mapping = multi_actor_shape_push_target_instruction_mapping()

        self.assertEqual(
            mapping["operator_id"],
            MULTI_ACTOR_SHAPE_PUSH_TARGET_OPERATOR,
        )
        self.assertEqual(forbidden_runtime_paths(mapping), ())


if __name__ == "__main__":
    unittest.main()
