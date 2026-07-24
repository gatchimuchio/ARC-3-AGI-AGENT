from __future__ import annotations

import unittest

import arc3_agi_agent.fruit_merge as fruit
from arc3_agi_agent.fruit_merge import (
    FRUIT_MERGE_CANDIDATE_OPERATOR,
    FRUIT_MERGE_INTERFACE_OBSERVATION_CANDIDATE_OPERATOR,
    FRUIT_MERGE_NO_PLAN_ROLLBACK_CANDIDATE_OPERATOR,
    FRUIT_MERGE_OPERATOR,
    FRUIT_MERGE_REPEAT_PENDING_CANDIDATE_OPERATOR,
    FRUIT_MERGE_ROUTE_ACTOR_DIVERSION_CANDIDATE_OPERATOR,
    FRUIT_MERGE_ROUTE_CONTINUATION_CANDIDATE_OPERATOR,
    FRUIT_MERGE_ROUTE_SAFE_OBSERVATION_CANDIDATE_OPERATOR,
    FRUIT_MERGE_SAFE_OBSERVATION_CANDIDATE_OPERATOR,
    FRUIT_MERGE_TARGET_ACTOR_ANCHOR_CANDIDATE_OPERATOR,
    FRUIT_MERGE_TERMINAL_ACTOR_FIRST_CANDIDATE_OPERATOR,
    FRUIT_MERGE_TERMINAL_ACTOR_PROTECTION_CANDIDATE_OPERATOR,
    FRUIT_MERGE_TRANSITION_CANDIDATE_OPERATOR,
    FruitMergeState,
)
from arc3_agi_agent.instruction_body import SemanticOperatorInstruction
from arc3_agi_agent.schema import forbidden_runtime_paths
from arc3_agi_agent.semantic_operators import SemanticPlannerState


def instruction(
    *,
    target_max_area: int = 80,
    operator_id: str = FRUIT_MERGE_OPERATOR,
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
        },
        {
            "kind": "actor-b",
            "color": 14,
            "width": 5,
            "height": 4,
            "mask": [
                [2, 0],
                [1, 1],
                [3, 1],
                [0, 2],
                [2, 2],
                [4, 2],
                [1, 3],
                [3, 3],
            ],
        },
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
        "actor_fruit_rank_delta": -1,
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
        "actor_merge_chain": ["actor-a", "actor-b"],
    }
    if operator_id in {
        FRUIT_MERGE_TRANSITION_CANDIDATE_OPERATOR,
        FRUIT_MERGE_SAFE_OBSERVATION_CANDIDATE_OPERATOR,
        FRUIT_MERGE_REPEAT_PENDING_CANDIDATE_OPERATOR,
        FRUIT_MERGE_ROUTE_CONTINUATION_CANDIDATE_OPERATOR,
        FRUIT_MERGE_INTERFACE_OBSERVATION_CANDIDATE_OPERATOR,
        FRUIT_MERGE_ROUTE_SAFE_OBSERVATION_CANDIDATE_OPERATOR,
        FRUIT_MERGE_ROUTE_ACTOR_DIVERSION_CANDIDATE_OPERATOR,
        FRUIT_MERGE_TARGET_ACTOR_ANCHOR_CANDIDATE_OPERATOR,
        FRUIT_MERGE_TERMINAL_ACTOR_PROTECTION_CANDIDATE_OPERATOR,
    }:
        parameters["maximum_transition_observations"] = 2
    return SemanticOperatorInstruction(
        operator_id=operator_id,
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

    def test_candidate_observes_multi_frame_effect_before_bounded_undo(
        self,
    ) -> None:
        candidate = instruction(
            operator_id=FRUIT_MERGE_TRANSITION_CANDIDATE_OPERATOR,
        )
        state = FruitMergeState()
        initial = state.decide(fruit_grid(), (6, 7), candidate)
        missing = tuple(
            tuple(2 for _ in range(64)) for _ in range(64)
        )

        first = state.decide(missing, (6, 7), candidate)
        restored = FruitMergeState.from_payload(state.to_payload())
        second = restored.decide(missing, (6, 7), candidate)
        bounded_undo = restored.decide(missing, (6, 7), candidate)

        self.assertIsNotNone(initial.action)
        self.assertIsNotNone(first.action)
        self.assertIsNotNone(second.action)
        self.assertIsNotNone(bounded_undo.action)
        assert first.action is not None
        assert second.action is not None
        assert bounded_undo.action is not None
        self.assertEqual(first.action.action_id, 7)
        self.assertEqual(second.action.action_id, 7)
        self.assertIn("effect-observation", first.reason)
        self.assertIn("effect-observation", second.reason)
        self.assertIn("observation-limit-undo", bounded_undo.reason)
        assert initial.action is not None
        self.assertEqual(
            restored.blocked_clicks,
            [(initial.action.x, initial.action.y)],
        )

    def test_safe_observation_candidate_uses_nonsemantic_click(
        self,
    ) -> None:
        candidate = instruction(
            operator_id=FRUIT_MERGE_SAFE_OBSERVATION_CANDIDATE_OPERATOR,
        )
        grid = fruit_grid()
        surface = fruit._surface_from_grid(grid, (6, 7), candidate)
        self.assertIsNotNone(surface)
        assert surface is not None
        state = FruitMergeState()
        state.decide(grid, (6, 7), candidate)
        missing = tuple(
            tuple(2 for _ in range(64)) for _ in range(64)
        )

        observation = state.decide(missing, (6, 7), candidate)

        self.assertIsNotNone(observation.action)
        assert observation.action is not None
        self.assertEqual(observation.action.action_id, 6)
        self.assertIsNotNone(observation.action.x)
        self.assertIsNotNone(observation.action.y)
        assert observation.action.x is not None
        assert observation.action.y is not None
        click = (observation.action.x, observation.action.y)
        self.assertEqual(fruit._affected_fruits(surface, click), ())
        self.assertEqual(fruit._affected_actors(surface, click), ())
        self.assertTrue(
            all(
                fruit._bbox_distance_sq(target.bbox, click)
                > surface.parameters.click_radius**2
                for target in surface.targets
            )
        )

    def test_candidate_retains_semantic_ownership_during_partial_effect(
        self,
    ) -> None:
        candidate = instruction(
            operator_id=FRUIT_MERGE_TRANSITION_CANDIDATE_OPERATOR,
        )
        rows = [list(row) for row in fruit_grid(merged=True)]
        actor_mask = (
            (2, 0),
            (1, 1),
            (3, 1),
            (0, 2),
            (4, 2),
            (1, 3),
            (2, 3),
            (3, 3),
        )
        for x, y in actor_mask:
            rows[2 + y][4 + x] = 7
            rows[24 + y][24 + x] = 7
        for y in range(40, 49):
            for x in range(20, 29):
                if y in {40, 41, 47, 48} or x in {20, 21, 27, 28}:
                    rows[y][x] = 9
        complete_surface = tuple(tuple(row) for row in rows)
        partial_rows = [list(row) for row in complete_surface]
        for x, y in actor_mask:
            partial_rows[24 + y][24 + x] = 2
        partial_surface = tuple(tuple(row) for row in partial_rows)
        state = FruitMergeState()

        staged = state.decide(complete_surface, (6, 7), candidate)
        observation = state.decide(partial_surface, (6, 7), candidate)

        self.assertIsNotNone(staged.action)
        self.assertIsNotNone(observation.action)
        assert observation.action is not None
        self.assertEqual(observation.action.action_id, 7)
        self.assertIn("effect-observation", observation.reason)
        self.assertEqual(state.blocked_clicks, [])

    def test_no_plan_candidate_rolls_back_and_blocks_staged_action(
        self,
    ) -> None:
        candidate = instruction(
            operator_id=FRUIT_MERGE_NO_PLAN_ROLLBACK_CANDIDATE_OPERATOR,
        )
        rows = [list(row) for row in fruit_grid(merged=True)]
        actor_mask = (
            (2, 0),
            (1, 1),
            (3, 1),
            (0, 2),
            (4, 2),
            (1, 3),
            (2, 3),
            (3, 3),
        )
        for x, y in actor_mask:
            rows[2 + y][4 + x] = 7
            rows[24 + y][24 + x] = 7
        for y in range(40, 49):
            for x in range(20, 29):
                if y in {40, 41, 47, 48} or x in {20, 21, 27, 28}:
                    rows[y][x] = 9
        complete_surface = tuple(tuple(row) for row in rows)
        partial_rows = [list(row) for row in complete_surface]
        for x, y in actor_mask:
            partial_rows[24 + y][24 + x] = 2
        partial_surface = tuple(tuple(row) for row in partial_rows)
        state = FruitMergeState()

        staged = state.decide(complete_surface, (6, 7), candidate)
        rollback = state.decide(partial_surface, (6, 7), candidate)

        self.assertIsNotNone(staged.action)
        self.assertIsNotNone(rollback.action)
        assert staged.action is not None
        assert rollback.action is not None
        self.assertEqual(rollback.action.action_id, 7)
        self.assertIn("goal-plan-unavailable-undo", rollback.reason)
        self.assertEqual(
            state.blocked_clicks,
            [(staged.action.x, staged.action.y)],
        )
        self.assertIsNone(state.pending_effect_click)

    def test_repeat_pending_candidate_advances_same_semantic_intent(
        self,
    ) -> None:
        candidate = instruction(
            operator_id=FRUIT_MERGE_REPEAT_PENDING_CANDIDATE_OPERATOR,
        )
        state = FruitMergeState()
        staged = state.decide(fruit_grid(), (6, 7), candidate)
        missing = tuple(
            tuple(2 for _ in range(64)) for _ in range(64)
        )

        repeated = state.decide(missing, (6, 7), candidate)

        self.assertIsNotNone(staged.action)
        self.assertIsNotNone(repeated.action)
        assert staged.action is not None
        assert repeated.action is not None
        self.assertEqual(repeated.action.action_id, 6)
        self.assertEqual(
            (repeated.action.x, repeated.action.y),
            (staged.action.x, staged.action.y),
        )
        self.assertIn("effect-observation", repeated.reason)
        self.assertEqual(state.blocked_clicks, [])

    def test_route_continuation_candidate_repeats_only_route_intent(
        self,
    ) -> None:
        candidate = instruction(
            operator_id=FRUIT_MERGE_ROUTE_CONTINUATION_CANDIDATE_OPERATOR,
        )
        missing = tuple(
            tuple(2 for _ in range(64)) for _ in range(64)
        )
        route_state = FruitMergeState()
        route = route_state.decide(
            fruit_grid(merged=True),
            (6, 7),
            candidate,
        )
        continuation = route_state.decide(missing, (6, 7), candidate)
        merge_state = FruitMergeState()
        merge = merge_state.decide(fruit_grid(), (6, 7), candidate)
        rollback = merge_state.decide(missing, (6, 7), candidate)

        self.assertIsNotNone(route.action)
        self.assertIsNotNone(continuation.action)
        self.assertIsNotNone(merge.action)
        self.assertIsNotNone(rollback.action)
        assert route.action is not None
        assert continuation.action is not None
        assert rollback.action is not None
        self.assertIn("required-fruit-route", route.reason)
        self.assertEqual(continuation.action.action_id, 6)
        self.assertEqual(
            (continuation.action.x, continuation.action.y),
            (route.action.x, route.action.y),
        )
        self.assertIn("effect-observation", continuation.reason)
        self.assertEqual(rollback.action.action_id, 7)
        self.assertIn("observation-limit-undo", rollback.reason)

    def test_interface_observation_candidate_uses_rendered_background(
        self,
    ) -> None:
        candidate = instruction(
            operator_id=FRUIT_MERGE_INTERFACE_OBSERVATION_CANDIDATE_OPERATOR,
        )
        grid = fruit_grid()
        state = FruitMergeState()
        staged = state.decide(grid, (6, 7), candidate)
        missing = tuple(
            tuple(2 for _ in range(64)) for _ in range(64)
        )

        observation = state.decide(missing, (6, 7), candidate)

        self.assertIsNotNone(staged.action)
        self.assertIsNotNone(observation.action)
        assert staged.action is not None
        assert observation.action is not None
        self.assertEqual(observation.action.action_id, 6)
        self.assertIsNotNone(observation.action.x)
        self.assertIsNotNone(observation.action.y)
        assert observation.action.x is not None
        assert observation.action.y is not None
        self.assertLessEqual(observation.action.y, 9)
        self.assertEqual(
            grid[observation.action.y][observation.action.x],
            2,
        )
        self.assertNotEqual(
            (observation.action.x, observation.action.y),
            (staged.action.x, staged.action.y),
        )
        self.assertIn("effect-observation", observation.reason)

    def test_route_safe_observation_candidate_uses_empty_playfield(
        self,
    ) -> None:
        candidate = instruction(
            operator_id=FRUIT_MERGE_ROUTE_SAFE_OBSERVATION_CANDIDATE_OPERATOR,
        )
        grid = fruit_grid(merged=True)
        surface = fruit._surface_from_grid(grid, (6, 7), candidate)
        self.assertIsNotNone(surface)
        assert surface is not None
        state = FruitMergeState()
        route = state.decide(grid, (6, 7), candidate)
        missing = tuple(
            tuple(2 for _ in range(64)) for _ in range(64)
        )

        observation = state.decide(missing, (6, 7), candidate)

        self.assertIsNotNone(route.action)
        self.assertIsNotNone(observation.action)
        assert route.action is not None
        assert observation.action is not None
        self.assertIn("required-fruit-route", route.reason)
        self.assertEqual(observation.action.action_id, 6)
        self.assertIsNotNone(observation.action.x)
        self.assertIsNotNone(observation.action.y)
        assert observation.action.x is not None
        assert observation.action.y is not None
        click = (observation.action.x, observation.action.y)
        self.assertGreaterEqual(observation.action.y, 10)
        self.assertNotEqual(
            click,
            (route.action.x, route.action.y),
        )
        self.assertEqual(fruit._affected_fruits(surface, click), ())
        self.assertEqual(fruit._affected_actors(surface, click), ())

    def test_route_actor_diversion_candidate_moves_actor_from_fruit(
        self,
    ) -> None:
        candidate = instruction(
            operator_id=FRUIT_MERGE_ROUTE_ACTOR_DIVERSION_CANDIDATE_OPERATOR,
        )
        rows = [list(row) for row in fruit_grid(merged=True)]
        actor_mask = (
            (2, 0),
            (1, 1),
            (3, 1),
            (0, 2),
            (4, 2),
            (1, 3),
            (2, 3),
            (3, 3),
        )
        for x, y in actor_mask:
            rows[16 + y][20 + x] = 7
            rows[2 + y][40 + x] = 7
        for y in range(40, 49):
            for x in range(20, 29):
                if y in {40, 41, 47, 48} or x in {20, 21, 27, 28}:
                    rows[y][x] = 9
        grid = tuple(tuple(row) for row in rows)
        surface = fruit._surface_from_grid(grid, (6, 7), candidate)
        self.assertIsNotNone(surface)
        assert surface is not None
        diversion = FruitMergeState().decide(grid, (6, 7), candidate)

        self.assertIsNotNone(diversion.action)
        assert diversion.action is not None
        self.assertIn("actor-hazard-divert", diversion.reason)
        self.assertEqual(diversion.action.action_id, 6)
        self.assertIsNotNone(diversion.action.x)
        self.assertIsNotNone(diversion.action.y)
        assert diversion.action.x is not None
        assert diversion.action.y is not None
        click = (diversion.action.x, diversion.action.y)
        affected = fruit._affected_actors(surface, click)
        self.assertEqual(len(affected), 1)
        self.assertEqual(fruit._affected_fruits(surface, click), ())
        actor = surface.actors[affected[0]]
        predicted = fruit._moved_actor_center(
            actor,
            click,
            surface.parameters.actor_move_distance,
            surface,
        )
        current_risk = min(
            fruit._distance_sq(actor.center, item.center)
            for item in surface.fruits
        )
        predicted_risk = min(
            fruit._distance_sq(predicted, item.center)
            for item in surface.fruits
        )
        self.assertGreater(predicted_risk, current_risk)

    def test_target_actor_anchor_advances_route_transition_in_place(
        self,
    ) -> None:
        candidate = instruction(
            operator_id=FRUIT_MERGE_TARGET_ACTOR_ANCHOR_CANDIDATE_OPERATOR,
        )
        rows = [list(row) for row in fruit_grid(merged=True)]
        actor_b = (
            (2, 0),
            (1, 1),
            (3, 1),
            (0, 2),
            (2, 2),
            (4, 2),
            (1, 3),
            (3, 3),
        )
        for y in range(40, 49):
            for x in range(20, 29):
                if y in {40, 41, 47, 48} or x in {20, 21, 27, 28}:
                    rows[y][x] = 9
        for offset_x, offset_y in actor_b:
            rows[2 + offset_y][40 + offset_x] = 14
            rows[42 + offset_y][22 + offset_x] = 14
        grid = tuple(tuple(row) for row in rows)
        surface = fruit._surface_from_grid(grid, (6, 7), candidate)
        self.assertIsNotNone(surface)
        assert surface is not None
        state = FruitMergeState()

        route = state.decide(grid, (6, 7), candidate)
        missing = tuple(tuple(2 for _ in range(64)) for _ in range(64))
        observation = state.decide(missing, (6, 7), candidate)

        self.assertIsNotNone(route.action)
        self.assertIn("required-fruit-route", route.reason)
        self.assertIsNotNone(observation.action)
        assert observation.action is not None
        self.assertEqual(observation.action.action_id, 6)
        click = (observation.action.x, observation.action.y)
        target_actor = next(
            actor
            for actor in surface.actors
            if actor.kind == "actor-b"
        )
        self.assertEqual(click, target_actor.center)
        self.assertEqual(fruit._affected_fruits(surface, click), ())
        self.assertIn("effect-observation", observation.reason)

    def test_terminal_actor_is_protected_before_required_fruit_route(
        self,
    ) -> None:
        candidate = instruction(
            operator_id=(
                FRUIT_MERGE_TERMINAL_ACTOR_PROTECTION_CANDIDATE_OPERATOR
            ),
        )
        rows = [list(row) for row in fruit_grid(merged=True)]
        actor_b = (
            (2, 0),
            (1, 1),
            (3, 1),
            (0, 2),
            (2, 2),
            (4, 2),
            (1, 3),
            (3, 3),
        )
        for offset_x, offset_y in actor_b:
            rows[2 + offset_y][40 + offset_x] = 14
            rows[30 + offset_y][28 + offset_x] = 14
        for y in range(40, 49):
            for x in range(20, 29):
                if y in {40, 41, 47, 48} or x in {20, 21, 27, 28}:
                    rows[y][x] = 9
        grid = tuple(tuple(row) for row in rows)
        surface = fruit._surface_from_grid(grid, (6, 7), candidate)
        self.assertIsNotNone(surface)
        assert surface is not None

        decision = FruitMergeState().decide(grid, (6, 7), candidate)

        self.assertIsNotNone(decision.action)
        self.assertIn("actor-hazard-divert", decision.reason)
        assert decision.action is not None
        assert decision.action.x is not None
        assert decision.action.y is not None
        click = (decision.action.x, decision.action.y)
        affected = fruit._affected_actors(surface, click)
        self.assertEqual(len(affected), 1)
        actor = surface.actors[affected[0]]
        self.assertEqual(actor.kind, "actor-b")
        predicted = fruit._moved_actor_center(
            actor,
            click,
            surface.parameters.actor_move_distance,
            surface,
        )
        self.assertGreater(
            min(
                fruit._distance_sq(predicted, item.center)
                for item in surface.fruits
            ),
            fruit._actor_risk(surface, actor),
        )

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
            rows[50 + offset_y][50 + offset_x] = 7
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

    def test_at_risk_actor_is_diverted_before_fruit_route(self) -> None:
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
            rows[20 + offset_y][18 + offset_x] = 7

        grid = tuple(tuple(row) for row in rows)
        state = FruitMergeState()

        decision = state.decide(
            grid,
            (6, 7),
            instruction(),
        )
        next_decision = state.decide(
            grid,
            (6, 7),
            instruction(),
        )

        self.assertIsNotNone(decision.action)
        self.assertIn("actor-hazard-divert", decision.reason)
        self.assertIsNotNone(next_decision.action)
        self.assertIn("required-fruit-route", next_decision.reason)

    def test_diversion_prioritizes_actor_nearest_to_fruit(self) -> None:
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
        for actor_x in (30, 50):
            for offset_x, offset_y in mask:
                rows[20 + offset_y][actor_x + offset_x] = 7
        grid = tuple(tuple(row) for row in rows)
        surface = fruit._surface_from_grid(grid, (6, 7), instruction())
        self.assertIsNotNone(surface)
        assert surface is not None
        state = FruitMergeState()
        state.decide(grid, (6, 7), instruction())
        state.fruit_action_streak = 1

        decision = state.decide(grid, (6, 7), instruction())

        self.assertIsNotNone(decision.action)
        assert decision.action is not None
        assert decision.action.x is not None
        assert decision.action.y is not None
        affected = fruit._affected_actors(
            surface,
            (decision.action.x, decision.action.y),
        )
        self.assertEqual(affected, (0,))
        self.assertLess(
            fruit._actor_risk(surface, surface.actors[0]),
            fruit._actor_risk(surface, surface.actors[1]),
        )

    def test_actor_routes_toward_higher_rank_fruit_for_reduction(
        self,
    ) -> None:
        rows = [list(row) for row in fruit_grid()]
        rows[20][10] = 2
        rows[20][16] = 2
        for y in range(20, 24):
            for x in range(24, 28):
                rows[y][x] = 11
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
            rows[20 + offset_y][4 + offset_x] = 7
        grid = tuple(tuple(row) for row in rows)
        surface = fruit._surface_from_grid(grid, (6, 7), instruction())
        self.assertIsNotNone(surface)
        assert surface is not None
        before = fruit._distance_sq(
            surface.actors[0].center,
            surface.fruits[0].center,
        )

        decision = FruitMergeState().decide(
            grid,
            (6, 7),
            instruction(),
        )

        self.assertIsNotNone(decision.action)
        assert decision.action is not None
        assert decision.action.x is not None
        assert decision.action.y is not None
        self.assertIn("actor-fruit-rank-reduction", decision.reason)
        predicted = fruit._moved_actor_center(
            surface.actors[0],
            (decision.action.x, decision.action.y),
            surface.parameters.actor_move_distance,
            surface,
        )
        self.assertLess(
            fruit._distance_sq(predicted, surface.fruits[0].center),
            before,
        )

    def test_near_actor_uses_empty_click_to_continue_rank_reduction(
        self,
    ) -> None:
        rows = [list(row) for row in fruit_grid()]
        rows[20][10] = 2
        rows[20][16] = 2
        for y in range(20, 24):
            for x in range(24, 28):
                rows[y][x] = 11
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
            rows[20 + offset_y][16 + offset_x] = 7
        grid = tuple(tuple(row) for row in rows)
        surface = fruit._surface_from_grid(grid, (6, 7), instruction())
        self.assertIsNotNone(surface)
        assert surface is not None

        decision = FruitMergeState().decide(
            grid,
            (6, 7),
            instruction(),
        )

        self.assertIsNotNone(decision.action)
        assert decision.action is not None
        assert decision.action.x is not None
        assert decision.action.y is not None
        click = (decision.action.x, decision.action.y)
        self.assertIn("actor-chase-rank-reduction", decision.reason)
        self.assertEqual(fruit._affected_actors(surface, click), ())
        self.assertEqual(fruit._affected_fruits(surface, click), ())

    def test_missing_inventory_is_merged_before_higher_rank_reduction(
        self,
    ) -> None:
        rows = [list(row) for row in fruit_grid(merged=True)]
        for y in range(4, 6):
            for x in range(34, 36):
                rows[y][x] = 6
        for y in range(40, 49):
            for x in range(20, 29):
                if y in {40, 41, 47, 48} or x in {20, 21, 27, 28}:
                    rows[y][x] = 9
        rows[20][16] = 10
        rows[20][22] = 10
        for y in range(20, 24):
            for x in range(40, 44):
                rows[y][x] = 11
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
            rows[50 + offset_y][50 + offset_x] = 7
        grid = tuple(tuple(row) for row in rows)

        decision = FruitMergeState().decide(
            grid,
            (6, 7),
            instruction(),
        )

        self.assertIsNotNone(decision.action)
        self.assertIn("equal-rank-merge", decision.reason)

    def test_lower_kind_actors_are_merged_before_target_placement(
        self,
    ) -> None:
        rows = [[2] * 64 for _ in range(64)]
        actor_a = (
            (2, 0),
            (1, 1),
            (3, 1),
            (0, 2),
            (4, 2),
            (1, 3),
            (2, 3),
            (3, 3),
        )
        actor_b = (
            (2, 0),
            (1, 1),
            (3, 1),
            (0, 2),
            (2, 2),
            (4, 2),
            (1, 3),
            (3, 3),
        )
        for offset_x, offset_y in actor_b:
            rows[2 + offset_y][40 + offset_x] = 14
        for actor_x in (10, 26):
            for offset_x, offset_y in actor_a:
                rows[20 + offset_y][actor_x + offset_x] = 7
        for y in range(40, 49):
            for x in range(40, 49):
                if y in {40, 41, 47, 48} or x in {40, 41, 47, 48}:
                    rows[y][x] = 9
        grid = tuple(tuple(row) for row in rows)

        decision = FruitMergeState().decide(
            grid,
            (6, 7),
            instruction(),
        )

        self.assertIsNotNone(decision.action)
        self.assertIn("equal-kind-actor", decision.reason)

    def test_nonrequired_actor_is_diverted_during_actor_placement(
        self,
    ) -> None:
        rows = [list(row) for row in fruit_grid(merged=True)]
        actor_a = (
            (2, 0),
            (1, 1),
            (3, 1),
            (0, 2),
            (4, 2),
            (1, 3),
            (2, 3),
            (3, 3),
        )
        actor_b = (
            (2, 0),
            (1, 1),
            (3, 1),
            (0, 2),
            (2, 2),
            (4, 2),
            (1, 3),
            (3, 3),
        )
        for offset_x, offset_y in actor_b:
            rows[2 + offset_y][40 + offset_x] = 14
            rows[30 + offset_y][30 + offset_x] = 14
        for offset_x, offset_y in actor_a:
            rows[20 + offset_y][13 + offset_x] = 7
        for y in range(40, 49):
            for x in range(20, 29):
                if y in {40, 41, 47, 48} or x in {20, 21, 27, 28}:
                    rows[y][x] = 9
        grid = tuple(tuple(row) for row in rows)
        surface = fruit._surface_from_grid(
            grid,
            (6, 7),
            instruction(),
        )
        self.assertIsNotNone(surface)
        assert surface is not None

        decision = FruitMergeState().decide(
            grid,
            (6, 7),
            instruction(),
        )

        self.assertIsNotNone(decision.action)
        assert decision.action is not None
        assert decision.action.x is not None
        assert decision.action.y is not None
        self.assertIn("actor-hazard-divert", decision.reason)
        affected = fruit._affected_actors(
            surface,
            (decision.action.x, decision.action.y),
        )
        self.assertEqual(len(affected), 1)
        self.assertEqual(surface.actors[affected[0]].kind, "actor-a")

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

    def test_candidate_places_fruit_before_mobile_required_actor(
        self,
    ) -> None:
        rows = [list(row) for row in fruit_grid(merged=True)]
        actor_b = (
            (2, 0),
            (1, 1),
            (3, 1),
            (0, 2),
            (2, 2),
            (4, 2),
            (1, 3),
            (3, 3),
        )
        for offset_x, offset_y in actor_b:
            rows[2 + offset_y][40 + offset_x] = 14
            rows[30 + offset_y][28 + offset_x] = 14
        for y in range(40, 49):
            for x in range(20, 29):
                if y in {40, 41, 47, 48} or x in {20, 21, 27, 28}:
                    rows[y][x] = 9
        grid = tuple(tuple(row) for row in rows)

        active = FruitMergeState().decide(
            grid,
            (6, 7),
            instruction(),
        )
        candidate = FruitMergeState().decide(
            grid,
            (6, 7),
            instruction(operator_id=FRUIT_MERGE_CANDIDATE_OPERATOR),
        )
        terminal_actor_first = FruitMergeState().decide(
            grid,
            (6, 7),
            instruction(
                operator_id=(
                    FRUIT_MERGE_TERMINAL_ACTOR_FIRST_CANDIDATE_OPERATOR
                )
            ),
        )

        self.assertIn("required-actor-route", active.reason)
        self.assertIn("required-fruit-route", candidate.reason)
        self.assertIsNotNone(candidate.action)
        self.assertIn(
            "required-actor-route",
            terminal_actor_first.reason,
        )
        self.assertIsNotNone(terminal_actor_first.action)


if __name__ == "__main__":
    unittest.main()
