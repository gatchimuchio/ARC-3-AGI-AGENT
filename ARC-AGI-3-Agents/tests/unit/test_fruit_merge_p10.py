from __future__ import annotations

import unittest

import arc3_agi_agent.fruit_merge as fruit
from arc3_agi_agent.fruit_merge import (
    FRUIT_MERGE_OPERATOR,
    FruitMergeState,
)
from arc3_agi_agent.instruction_body import SemanticOperatorInstruction
from arc3_agi_agent.schema import forbidden_runtime_paths
from arc3_agi_agent.semantic_operators import SemanticPlannerState


def instruction(
    *,
    target_max_area: int = 80,
) -> SemanticOperatorInstruction:
    actor_masks: list[dict[str, object]] = [
        {
            "kind": "actor-a",
            "color": 7,
            "width": 5,
            "height": 4,
            "mask": [
                [2, 0],
                [1, 1],
                [3, 1],
                [0, 2],
                [4, 2],
                [1, 3],
                [2, 3],
                [3, 3],
            ],
        }
    ]
    parameters: dict[str, object] = {
        "click_action": 6,
        "undo_action": 7,
        "click_x_origin": 0,
        "click_y_origin": 10,
        "click_step": 4,
        "click_radius": 8,
        "fruit_move_step": 4,
        "actor_move_distance": 14,
        "actor_chase_risk_distance": 24,
        "actor_divert_interval": 1,
        "interface_max_y": 9,
        "playfield_min_y": 10,
        "playfield_max_y": 62,
        "target_color": 9,
        "target_min_side": 8,
        "target_max_side": 10,
        "target_min_area": 35,
        "target_max_area": target_max_area,
        "rank_specs": [
            {"rank": 0, "color": 10, "side": 1},
            {"rank": 1, "color": 6, "side": 2},
            {"rank": 2, "color": 15, "side": 3},
            {"rank": 3, "color": 11, "side": 4},
        ],
        "actor_specs": actor_masks,
    }
    return SemanticOperatorInstruction(
        operator_id=FRUIT_MERGE_OPERATOR,
        action_id=6,
        detector="rendered goal glyphs, fruits, actors, and targets",
        transform="single-step merge and target placement",
        parameter_items=tuple(sorted(parameters.items())),
        preconditions=("ACTION6_AND_ACTION7_AVAILABLE",),
        falsification_conditions=("goal-aware surface does not close",),
        provenance=("compiled-rendered-fruit-evidence",),
    )


def fruit_grid(
    *,
    merged: bool = False,
    target_shift: int = 0,
) -> tuple[tuple[int, ...], ...]:
    rows = [[2] * 64 for _ in range(64)]

    # Rendered interface asks for one rank-1 square.
    for y in range(4, 6):
        for x in range(30, 32):
            rows[y][x] = 6

    # Irregular rendered target zone.
    target_x = 40 + target_shift
    target_y = 40
    for y in range(target_y, target_y + 9):
        for x in range(target_x, target_x + 9):
            if (
                y in {
                    target_y,
                    target_y + 1,
                    target_y + 7,
                    target_y + 8,
                }
                or x
                in {
                    target_x,
                    target_x + 1,
                    target_x + 7,
                    target_x + 8,
                }
            ):
                rows[y][x] = 9

    if merged:
        for y in range(20, 22):
            for x in range(10, 12):
                rows[y][x] = 6
    else:
        rows[20][10] = 10
        rows[20][16] = 10
    return tuple(tuple(row) for row in rows)


class P10FruitMergeTests(unittest.TestCase):
    def test_visible_goal_drives_equal_rank_merge(self) -> None:
        state = FruitMergeState()

        decision = state.decide(
            fruit_grid(),
            (6, 7),
            instruction(),
        )

        self.assertIsNotNone(decision.action)
        assert decision.action is not None
        self.assertEqual(decision.action.action_id, 6)
        self.assertIsNotNone(decision.action.x)
        self.assertIsNotNone(decision.action.y)
        self.assertIn("equal-rank-merge", decision.reason)
        self.assertIn(FRUIT_MERGE_OPERATOR, decision.action.evidence)

    def test_merged_required_rank_is_routed_from_current_render(
        self,
    ) -> None:
        first = FruitMergeState().decide(
            fruit_grid(merged=True),
            (6, 7),
            instruction(),
        )
        shifted = FruitMergeState().decide(
            fruit_grid(merged=True, target_shift=-32),
            (6, 7),
            instruction(),
        )

        self.assertIsNotNone(first.action)
        self.assertIsNotNone(shifted.action)
        assert first.action is not None
        assert shifted.action is not None
        self.assertIn("required-fruit-route", first.reason)
        self.assertNotEqual(first.action.step(), shifted.action.step())

    def test_state_round_trip_and_instruction_change_fail_closed(
        self,
    ) -> None:
        state = FruitMergeState()
        state.decide(fruit_grid(), (6, 7), instruction())
        restored = FruitMergeState.from_payload(state.to_payload())
        restored.actor_action_count = 3
        original_digest = restored.instruction_digest
        self.assertEqual(restored.last_click, state.last_click)

        restored.decide(
            fruit_grid(),
            (6, 7),
            instruction(target_max_area=79),
        )

        self.assertNotEqual(restored.instruction_digest, original_digest)
        self.assertEqual(restored.actor_action_count, 0)
        self.assertEqual(forbidden_runtime_paths(restored.to_payload()), ())

    def test_surface_loss_issues_one_observation_bound_undo(
        self,
    ) -> None:
        state = FruitMergeState()
        state.decide(fruit_grid(), (6, 7), instruction())
        missing = tuple(
            tuple(2 for _ in range(64)) for _ in range(64)
        )

        undo = state.decide(missing, (6, 7), instruction())
        repeated = state.decide(missing, (6, 7), instruction())

        self.assertIsNotNone(undo.action)
        assert undo.action is not None
        self.assertEqual(undo.action.action_id, 7)
        self.assertIn("surface-loss-undo", undo.reason)
        self.assertTrue(undo.memory_influenced)
        self.assertIsNone(repeated.action)
        self.assertTrue(state.undo_pending)
        self.assertEqual(state.fruit_action_streak, 1)
        self.assertEqual(state.blocked_clicks, [state.last_click])

    def test_semantic_planner_preserves_passive_operator_state(self) -> None:
        planner = SemanticPlannerState()
        first = planner.decide(
            fruit_grid(),
            (6, 7),
            (instruction(),),
            source_signature="visual-state:first",
        )
        restored = SemanticPlannerState.from_payload(planner.to_payload())
        second = restored.decide(
            fruit_grid(),
            (6, 7),
            (instruction(),),
            source_signature="visual-state:second",
        )

        self.assertIsNotNone(first.action)
        self.assertIsNotNone(second.action)
        self.assertEqual(restored.fruit_merge.decision_count, 2)
        self.assertTrue(second.memory_influenced)

    def test_non_click_or_missing_goal_surface_is_rejected(self) -> None:
        state = FruitMergeState()
        missing_action = state.decide(fruit_grid(), (6,), instruction())
        empty = state.decide(
            tuple(tuple(2 for _ in range(64)) for _ in range(64)),
            (6, 7),
            instruction(),
        )

        self.assertIsNone(missing_action.action)
        self.assertIsNone(empty.action)

    def test_framed_interface_legend_is_not_a_goal_requirement(
        self,
    ) -> None:
        rows = [[2] * 64 for _ in range(64)]
        for x in range(16):
            rows[0][x] = 5
            rows[3][x] = 5
        for y in range(4):
            rows[y][0] = 5
            rows[y][15] = 5
        for y in range(1, 3):
            for x in range(5, 7):
                rows[y][x] = 6
        for y in range(3, 7):
            for x in range(30, 34):
                rows[y][x] = 11
        for y in range(40, 49):
            for x in range(40, 49):
                if y in {40, 41, 47, 48} or x in {40, 41, 47, 48}:
                    rows[y][x] = 9
        for y in range(20, 24):
            for x in range(10, 14):
                rows[y][x] = 11

        surface = fruit._surface_from_grid(
            tuple(tuple(row) for row in rows),
            (6, 7),
            instruction(),
        )

        self.assertIsNotNone(surface)
        assert surface is not None
        self.assertEqual(surface.required_ranks, ((3, 1),))

    def test_full_width_interface_backdrop_does_not_hide_goal(
        self,
    ) -> None:
        rows = [list(row) for row in fruit_grid(merged=True)]
        for y in range(10):
            for x in range(64):
                rows[y][x] = 4
        for y in range(4, 6):
            for x in range(30, 32):
                rows[y][x] = 6

        surface = fruit._surface_from_grid(
            tuple(tuple(row) for row in rows),
            (6, 7),
            instruction(),
        )

        self.assertIsNotNone(surface)
        assert surface is not None
        self.assertEqual(surface.required_ranks, ((1, 1),))

    def test_nonrequired_actor_diversion_is_periodic_not_starving(
        self,
    ) -> None:
        rows = [list(row) for row in fruit_grid()]
        mask = (
            (2, 0),
            (1, 1),
            (3, 1),
            (0, 2),
            (4, 2),
            (1, 3),
            (2, 3),
            (3, 3),
        )
        for offset_x, offset_y in mask:
            rows[20 + offset_y][30 + offset_x] = 7
        grid = tuple(tuple(row) for row in rows)
        state = FruitMergeState()

        first = state.decide(grid, (6, 7), instruction())
        state.fruit_action_streak = 1
        periodic = state.decide(grid, (6, 7), instruction())
        missing = tuple(
            tuple(2 for _ in range(64)) for _ in range(64)
        )
        undo = state.decide(missing, (6, 7), instruction())
        streak_after_undo = state.fruit_action_streak
        alternative = state.decide(grid, (6, 7), instruction())

        self.assertIn("equal-rank", first.reason)
        self.assertIn("actor-hazard-divert", periodic.reason)
        self.assertIsNotNone(periodic.action)
        self.assertIsNotNone(undo.action)
        self.assertIsNotNone(alternative.action)
        assert periodic.action is not None
        assert alternative.action is not None
        self.assertEqual(streak_after_undo, 0)
        self.assertIn("equal-rank", alternative.reason)
        self.assertNotEqual(
            periodic.action.step(),
            alternative.action.step(),
        )

    def test_actor_requirement_is_detected_from_interface_pattern(
        self,
    ) -> None:
        rows = [list(row) for row in fruit_grid(merged=True)]
        mask = (
            (2, 0),
            (1, 1),
            (3, 1),
            (0, 2),
            (4, 2),
            (1, 3),
            (2, 3),
            (3, 3),
        )
        for offset_x, offset_y in mask:
            rows[2 + offset_y][40 + offset_x] = 7
            rows[20 + offset_y][30 + offset_x] = 7
        # The rendered interface requests one fruit and one actor, so expose
        # two independent target zones rather than an impossible one-slot
        # surface.
        for y in range(40, 49):
            for x in range(20, 29):
                if y in {40, 41, 47, 48} or x in {20, 21, 27, 28}:
                    rows[y][x] = 9
        surface = fruit._surface_from_grid(
            tuple(tuple(row) for row in rows),
            (6, 7),
            instruction(),
        )

        self.assertIsNotNone(surface)
        assert surface is not None
        self.assertEqual(surface.required_actors, (("actor-a", 1),))
        self.assertEqual(len(surface.actors), 1)


if __name__ == "__main__":
    unittest.main()
