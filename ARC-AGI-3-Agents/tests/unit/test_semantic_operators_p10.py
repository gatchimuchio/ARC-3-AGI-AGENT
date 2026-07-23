from __future__ import annotations

import unittest

from arc3_agi_agent.instruction_body import SemanticOperatorInstruction
from arc3_agi_agent.schema import digest_object
from arc3_agi_agent.semantic_operators import (
    RELATION_TOGGLE_OPERATOR,
    SemanticPlannerState,
    relation_toggle_plan,
)


def toggle_instruction() -> SemanticOperatorInstruction:
    parameters: dict[str, object] = {
        "tile_size": 3,
        "neighbor_stride": 4,
        "mask_color": 6,
        "equality_relation_color": 0,
        "excluded_colors": [0, 2, 3, 4, 5, 7],
        "relation_colors": [0, 2, 3],
        "status_scan_width": 6,
        "status_scan_height": 10,
        "max_camera_scale": 4,
        "minimum_cell_count": 2,
    }
    return SemanticOperatorInstruction(
        operator_id=RELATION_TOGGLE_OPERATOR,
        action_id=6,
        detector="rendered relation tile lattice",
        transform="constraint options plus dynamic gf2 solve",
        parameter_items=tuple(sorted(parameters.items())),
        preconditions=("ACTION6_AVAILABLE", "RENDERED_RELATION_GRID"),
        falsification_conditions=(
            "relation grid detector does not close",
            "planned action does not change rendered state",
        ),
        provenance=("compiled-identity-free-toggle-evidence",),
    )


def relation_grid(
    *,
    shift: int = 0,
    first_color: int = 9,
    second_color: int = 8,
) -> tuple[tuple[int, ...], ...]:
    rows = [[5] * 14 for _ in range(14)]
    for x, color in (
        (1 + shift, first_color),
        (5 + shift, second_color),
    ):
        for y in range(1 + shift, 4 + shift):
            for cell_x in range(x, x + 3):
                rows[y][cell_x] = color
    constraint = [[2] * 3 for _ in range(3)]
    constraint[1][1] = second_color
    constraint[0][0] = 0
    for dy in range(3):
        for dx in range(3):
            rows[5 + shift + dy][5 + shift + dx] = constraint[dy][dx]
    return tuple(tuple(row) for row in rows)


class P10SemanticOperatorTests(unittest.TestCase):
    def test_relation_toggle_plan_is_observation_derived(self) -> None:
        instruction = toggle_instruction()
        plan = relation_toggle_plan(relation_grid(), (6,), instruction)
        shifted = relation_toggle_plan(
            relation_grid(
                shift=1,
                first_color=11,
                second_color=10,
            ),
            (6,),
            instruction,
        )

        self.assertEqual(
            tuple(action.step() for action in plan),
            (
                {"action_id": 6, "x": 2, "y": 2},
                {"action_id": 6, "x": 6, "y": 2},
            ),
        )
        self.assertEqual(
            tuple(action.step() for action in shifted),
            (
                {"action_id": 6, "x": 3, "y": 3},
                {"action_id": 6, "x": 7, "y": 3},
            ),
        )
        self.assertTrue(
            all(
                RELATION_TOGGLE_OPERATOR in action.evidence
                for action in plan
            )
        )

    def test_passive_queue_round_trip_changes_future_action(self) -> None:
        grid = relation_grid()
        signature = "visual-state:" + digest_object(grid)[:24]
        planner = SemanticPlannerState()

        first = planner.decide(
            grid,
            (6,),
            (toggle_instruction(),),
            source_signature=signature,
        )
        restored = SemanticPlannerState.from_payload(planner.to_payload())
        second = restored.decide(
            grid,
            (6,),
            (toggle_instruction(),),
            source_signature=signature,
        )

        self.assertIsNotNone(first.action)
        self.assertIsNotNone(second.action)
        assert first.action is not None
        assert second.action is not None
        self.assertNotEqual(first.action.step(), second.action.step())
        self.assertFalse(first.memory_influenced)
        self.assertTrue(second.memory_influenced)
        self.assertEqual(restored.plan_count, 1)
        self.assertEqual(restored.memory_read_count, 1)

    def test_failed_plan_is_blocked_in_same_rendered_state(self) -> None:
        grid = relation_grid()
        signature = "visual-state:" + digest_object(grid)[:24]
        planner = SemanticPlannerState()
        first = planner.decide(
            grid,
            (6,),
            (toggle_instruction(),),
            source_signature=signature,
        )
        self.assertIsNotNone(first.action)
        planner.invalidate_active_plan()

        blocked = planner.decide(
            grid,
            (6,),
            (toggle_instruction(),),
            source_signature=signature,
        )

        self.assertIsNone(blocked.action)
        self.assertEqual(
            blocked.reason,
            "NO_SEMANTIC_OPERATOR_APPLICABLE",
        )
        self.assertTrue(blocked.memory_influenced)

    def test_operator_rejects_wrong_action_surface(self) -> None:
        self.assertEqual(
            relation_toggle_plan(
                relation_grid(),
                (1, 2),
                toggle_instruction(),
            ),
            (),
        )

    def test_queued_plan_is_invalidated_when_p_is_removed(self) -> None:
        grid = relation_grid()
        signature = "visual-state:" + digest_object(grid)[:24]
        planner = SemanticPlannerState()
        first = planner.decide(
            grid,
            (6,),
            (toggle_instruction(),),
            source_signature=signature,
        )
        self.assertIsNotNone(first.action)

        after_p_removal = planner.decide(
            grid,
            (6,),
            (),
            source_signature=signature,
        )

        self.assertIsNone(after_p_removal.action)
        self.assertEqual(
            after_p_removal.reason,
            "NO_SEMANTIC_OPERATOR_APPLICABLE",
        )
        self.assertEqual(planner.queue, [])
        self.assertEqual(planner.active_operator, "")


if __name__ == "__main__":
    unittest.main()
