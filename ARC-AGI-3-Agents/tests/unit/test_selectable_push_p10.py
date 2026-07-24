from __future__ import annotations

import unittest

from arc3_agi_agent.instruction_body import SemanticOperatorInstruction
from arc3_agi_agent.selectable_push import (
    SELECTABLE_PUSH_TARGET_OPERATOR,
    selectable_push_target_plan,
)


def _instruction() -> SemanticOperatorInstruction:
    return SemanticOperatorInstruction(
        operator_id=SELECTABLE_PUSH_TARGET_OPERATOR,
        action_id=6,
        detector="paired rendered border objects and enclosing targets",
        transform="derive actions from current geometry",
        parameter_items=tuple(
            sorted(
                {
                    "click_action": 6,
                    "up_action": 1,
                    "down_action": 2,
                    "left_action": 3,
                    "right_action": 4,
                    "required_pair_count": 2,
                    "target_inset": 1,
                    "minimum_block_side": 2,
                    "maximum_block_side": 8,
                    "minimum_barrier_area_ratio": 4,
                }.items()
            )
        ),
        preconditions=("rendered roles close",),
        falsification_conditions=("derived transition fails",),
        provenance=("identity-free-unit-fixture",),
    )


def _ring(
    grid: list[list[int]],
    *,
    x: int,
    y: int,
    side: int,
    color: int,
) -> None:
    for offset in range(side):
        grid[y][x + offset] = color
        grid[y + side - 1][x + offset] = color
        grid[y + offset][x] = color
        grid[y + offset][x + side - 1] = color


def _grid(offset_x: int = 0) -> tuple[tuple[int, ...], ...]:
    grid = [[1 for _x in range(48)] for _y in range(42)]
    _ring(grid, x=10 + offset_x, y=20, side=3, color=14)
    _ring(grid, x=19 + offset_x, y=20, side=3, color=14)
    grid[21][11 + offset_x] = 0
    grid[21][20 + offset_x] = 5
    _ring(grid, x=3 + offset_x, y=22, side=5, color=4)
    _ring(grid, x=34 + offset_x, y=16, side=5, color=4)
    for y in range(10, 31):
        for x in range(25 + offset_x, 28 + offset_x):
            grid[y][x] = 15
    return tuple(tuple(row) for row in grid)


class SelectablePushTests(unittest.TestCase):
    def test_plan_is_derived_from_rendered_relations(self) -> None:
        plan = selectable_push_target_plan(
            _grid(),
            (1, 2, 3, 4, 6),
            _instruction(),
        )

        self.assertTrue(plan)
        self.assertEqual(plan[0].action_id, 4)
        clicks = [action for action in plan if action.action_id == 6]
        self.assertEqual(len(clicks), 2)
        self.assertEqual((clicks[0].x, clicks[0].y), (33, 21))
        self.assertEqual((clicks[1].x, clicks[1].y), (14, 21))

    def test_translation_changes_clicks_without_changing_action_schema(
        self,
    ) -> None:
        first = selectable_push_target_plan(
            _grid(),
            (1, 2, 3, 4, 6),
            _instruction(),
        )
        shifted = selectable_push_target_plan(
            _grid(offset_x=2),
            (1, 2, 3, 4, 6),
            _instruction(),
        )

        self.assertEqual(
            [action.action_id for action in first],
            [action.action_id for action in shifted],
        )
        first_clicks = [
            (action.x, action.y) for action in first if action.action_id == 6
        ]
        shifted_clicks = [
            (action.x, action.y)
            for action in shifted
            if action.action_id == 6
        ]
        self.assertEqual(
            shifted_clicks,
            [(x + 2, y) for x, y in first_clicks],
        )

    def test_ambiguous_or_missing_roles_rejects(self) -> None:
        grid = [list(row) for row in _grid()]
        _ring(grid, x=2, y=2, side=3, color=14)

        plan = selectable_push_target_plan(
            tuple(tuple(row) for row in grid),
            (1, 2, 3, 4, 6),
            _instruction(),
        )

        self.assertEqual(plan, ())


if __name__ == "__main__":
    unittest.main()
