from __future__ import annotations

import unittest

from arc3_agi_agent.instruction_body import SemanticOperatorInstruction
from arc3_agi_agent.schema import digest_object
from arc3_agi_agent.semantic_operators import (
    OBJECT_TARGET_CONTROL_OPERATOR,
    RELATION_TOGGLE_OPERATOR,
    SemanticPlannerState,
    _TargetSearchSurface,
    object_target_control_plan,
    relation_toggle_plan,
)
from arc3_agi_agent.visual_explorer import VisualAction


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


def object_target_instruction() -> SemanticOperatorInstruction:
    parameters: dict[str, object] = {
        "left_control_color": 8,
        "right_control_color": 14,
        "state_excluded_colors": [3, 4, 5],
        "minimum_control_area": 8,
        "maximum_control_area": 16,
        "goal_to_corner_width_ratio": 2,
        "target_corner_stride_ratio": 3,
        "paired_far_tolerance_in_corner_widths": 12,
        "near_tolerance_in_corner_widths": 3,
        "far_tolerance_in_corner_widths": 15,
        "vertical_far_tolerance_in_corner_widths": 27,
        "minimum_guided_cost_per_goal": 4,
        "maximum_search_states": 4096,
        "maximum_control_cycle_steps": 32,
        "minimum_model_observations_per_action": 2,
        "maximum_model_plan_depth": 12,
        "maximum_mechanism_slots": 96,
        "minimum_dense_model_slots": 32,
    }
    return SemanticOperatorInstruction(
        operator_id=OBJECT_TARGET_CONTROL_OPERATOR,
        action_id=6,
        detector="rendered four-corner targets and compact controls",
        transform="single-step goal-displacement control with reobservation",
        parameter_items=tuple(sorted(parameters.items())),
        preconditions=("ACTION6_AVAILABLE", "RENDERED_TARGET_MARKER"),
        falsification_conditions=(
            "target marker detector does not close",
            "selected control does not move a rendered goal",
        ),
        provenance=("compiled-identity-free-object-evidence",),
    )


def object_target_grid(
    *,
    scale: int = 1,
    shift: int = 0,
    role_color: int = 11,
    goal_logical_x: int = 21,
) -> tuple[tuple[int, ...], ...]:
    logical = [[4] * 36 for _ in range(24)]

    def sprite(
        x: int,
        y: int,
        pixels: tuple[tuple[int, ...], ...],
    ) -> None:
        for dy, row in enumerate(pixels):
            for dx, value in enumerate(row):
                if value >= 0:
                    logical[y + shift + dy][x + shift + dx] = value

    for x, y in ((5, 2), (8, 2), (5, 5), (8, 5)):
        sprite(x, y, ((role_color,),))
    sprite(
        goal_logical_x,
        3,
        ((role_color, role_color), (role_color, role_color)),
    )
    sprite(
        1,
        8,
        ((-1, 8, 8), (8, 8, 8), (8, 8, 8), (-1, 8, 8)),
    )
    sprite(
        30,
        8,
        ((14, 14, -1), (14, 14, 14), (14, 14, 14), (14, 14, -1)),
    )
    return tuple(
        tuple(
            logical[y // scale][x // scale]
            for x in range(len(logical[0]) * scale)
        )
        for y in range(len(logical) * scale)
    )


def paired_object_target_grid(
    *,
    after_top_control: bool,
) -> tuple[tuple[int, ...], ...]:
    rows = [[4] * 64 for _ in range(64)]

    def sprite(
        x: int,
        y: int,
        pixels: tuple[tuple[int, ...], ...],
    ) -> None:
        for dy, row in enumerate(pixels):
            for dx, value in enumerate(row):
                if value >= 0:
                    rows[y + dy][x + dx] = value

    for top_y in (25, 34):
        for x, y in (
            (34, top_y),
            (37, top_y),
            (34, top_y + 3),
            (37, top_y + 3),
        ):
            sprite(x, y, ((11,),))
    upper_goal = (35, 17) if after_top_control else (32, 17)
    lower_goal = (23, 35) if after_top_control else (23, 38)
    for x, y in (upper_goal, lower_goal):
        sprite(x, y, ((11, 11), (11, 11)))
    left_arrow = (
        (-1, 8, 8),
        (8, 8, 8),
        (8, 8, 8),
        (-1, 8, 8),
    )
    right_arrow = (
        (14, 14, -1),
        (14, 14, 14),
        (14, 14, 14),
        (14, 14, -1),
    )
    for left_x, right_x, y in (
        (19, 38, 16),
        (13, 47, 25),
        (13, 47, 34),
    ):
        sprite(left_x, y, left_arrow)
        sprite(right_x, y, right_arrow)
    return tuple(tuple(row) for row in rows)


def dual_object_target_grid() -> tuple[tuple[int, ...], ...]:
    rows = [[4] * 64 for _ in range(64)]

    def sprite(
        x: int,
        y: int,
        pixels: tuple[tuple[int, ...], ...],
    ) -> None:
        for dy, row in enumerate(pixels):
            for dx, value in enumerate(row):
                if value >= 0:
                    rows[y + dy][x + dx] = value

    for color, left_x in ((11, 44), (12, 50)):
        for x, y in (
            (left_x, 44),
            (left_x + 3, 44),
            (left_x, 47),
            (left_x + 3, 47),
        ):
            sprite(x, y, ((color,),))
    for color, x, y in ((11, 39, 15), (12, 15, 48)):
        sprite(x, y, ((color, color), (color, color)))
    left_arrow = (
        (-1, 8, 8),
        (8, 8, 8),
        (8, 8, 8),
        (-1, 8, 8),
    )
    right_arrow = (
        (14, 14, -1),
        (14, 14, 14),
        (14, 14, 14),
        (14, 14, -1),
    )
    for x, y in (
        (5, 14),
        (35, 14),
        (14, 24),
        (44, 24),
        (5, 44),
        (35, 44),
        (14, 54),
        (44, 54),
    ):
        sprite(x, y, left_arrow)
    for x, y in (
        (14, 5),
        (44, 5),
        (24, 14),
        (54, 14),
        (14, 35),
        (44, 35),
        (24, 44),
        (54, 44),
    ):
        sprite(x, y, right_arrow)
    return tuple(tuple(row) for row in rows)


def search_object_target_grid(
    *,
    goal_x: int,
    token_color: int = 9,
) -> tuple[tuple[int, ...], ...]:
    rows = [[4] * 64 for _ in range(64)]

    def sprite(
        x: int,
        y: int,
        pixels: tuple[tuple[int, ...], ...],
    ) -> None:
        for dy, row in enumerate(pixels):
            for dx, value in enumerate(row):
                if value >= 0:
                    rows[y + dy][x + dx] = value

    for marker_x in (15, 39):
        for x, y in (
            (marker_x, 4),
            (marker_x + 3, 4),
            (marker_x, 7),
            (marker_x + 3, 7),
        ):
            sprite(x, y, ((11,),))
    for x, y in ((goal_x, 18), (29, 54)):
        sprite(x, y, ((11, 11), (11, 11)))
    sprite(20, 30, ((token_color, token_color), (token_color, token_color)))
    left_arrow = (
        (-1, 8, 8),
        (8, 8, 8),
        (8, 8, 8),
        (-1, 8, 8),
    )
    right_arrow = (
        (14, 14, -1),
        (14, 14, 14),
        (14, 14, 14),
        (14, 14, -1),
    )
    for x, y in ((7, 4), (9, 34)):
        sprite(x, y, left_arrow)
    for x, y in ((49, 4), (35, 34)):
        sprite(x, y, right_arrow)
    return tuple(tuple(row) for row in rows)


def target_control_action(key: str, *, x: int) -> VisualAction:
    return VisualAction(
        key=key,
        action_id=6,
        group=0,
        x=x,
        y=10,
        evidence=(
            OBJECT_TARGET_CONTROL_OPERATOR,
            f"operator-prototype:{OBJECT_TARGET_CONTROL_OPERATOR}",
        ),
    )


def target_search_surface(
    *,
    signature: str,
    cost: int,
    actions: tuple[VisualAction, ...],
    coordinate_descent: bool,
    colors: tuple[int, ...] = (),
    requirements: tuple[tuple[int, int], ...] = (),
) -> _TargetSearchSurface:
    return _TargetSearchSurface(
        state_signature=signature,
        target_cost=cost,
        cost_guidance_enabled=False,
        actions=actions,
        maximum_states=128,
        coordinate_descent_enabled=coordinate_descent,
        maximum_control_cycle_steps=8,
        mechanism_positions=tuple(
            (index, 0) for index in range(len(colors))
        ),
        mechanism_colors=colors,
        target_requirements=requirements,
        minimum_model_observations_per_action=2,
        maximum_model_plan_depth=8,
        minimum_dense_model_slots=2,
    )


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

    def test_p_removal_invalidates_operator_state_without_queue(
        self,
    ) -> None:
        planner = SemanticPlannerState(
            active_operator=OBJECT_TARGET_CONTROL_OPERATOR,
            active_instruction_digest=digest_object(
                object_target_instruction()
            ),
            target_initial_state="old-state",
            target_transitions={"old-state": {"control": "next-state"}},
        )
        planner.symbolic_rewrite.submit_count = 2

        decision = planner.decide(
            object_target_grid(),
            (6,),
            (),
            source_signature="visual-state:test",
        )

        self.assertIsNone(decision.action)
        self.assertEqual(planner.active_operator, "")
        self.assertEqual(planner.target_initial_state, "")
        self.assertEqual(planner.target_transitions, {})
        self.assertEqual(planner.symbolic_rewrite.submit_count, 0)

    def test_object_target_control_is_single_step_and_position_derived(
        self,
    ) -> None:
        instruction = object_target_instruction()
        plan = object_target_control_plan(
            object_target_grid(),
            (6,),
            instruction,
        )
        shifted = object_target_control_plan(
            object_target_grid(scale=2, shift=1, role_color=12),
            (6,),
            instruction,
        )

        self.assertEqual(len(plan), 1)
        self.assertEqual(len(shifted), 1)
        self.assertEqual(plan[0].action_id, 6)
        self.assertEqual(plan[0].step(), {"action_id": 6, "x": 2, "y": 9})
        self.assertEqual(
            shifted[0].step(),
            {"action_id": 6, "x": 6, "y": 21},
        )
        self.assertIn(
            "single-step-reobservation-required",
            plan[0].evidence,
        )

    def test_object_target_control_reverses_for_opposite_displacement(
        self,
    ) -> None:
        plan = object_target_control_plan(
            object_target_grid(goal_logical_x=1),
            (6,),
            object_target_instruction(),
        )

        self.assertEqual(len(plan), 1)
        self.assertEqual(
            plan[0].step(),
            {"action_id": 6, "x": 31, "y": 9},
        )

    def test_object_target_control_rejects_non_click_surface(self) -> None:
        self.assertEqual(
            object_target_control_plan(
                object_target_grid(),
                (1, 2),
                object_target_instruction(),
            ),
            (),
        )

    def test_object_target_control_reobserves_paired_goal_state(self) -> None:
        instruction = object_target_instruction()
        initial = object_target_control_plan(
            paired_object_target_grid(after_top_control=False),
            (6,),
            instruction,
        )
        after_top = object_target_control_plan(
            paired_object_target_grid(after_top_control=True),
            (6,),
            instruction,
        )

        self.assertEqual(
            initial[0].step(),
            {"action_id": 6, "x": 39, "y": 17},
        )
        self.assertEqual(
            after_top[0].step(),
            {"action_id": 6, "x": 48, "y": 35},
        )

    def test_object_target_control_uses_first_paired_control_row(
        self,
    ) -> None:
        plan = object_target_control_plan(
            dual_object_target_grid(),
            (6,),
            object_target_instruction(),
        )

        self.assertEqual(
            plan[0].step(),
            {"action_id": 6, "x": 25, "y": 15},
        )

    def test_object_target_state_graph_round_trip_influences_next_action(
        self,
    ) -> None:
        instruction = object_target_instruction()
        planner = SemanticPlannerState()
        first_grid = search_object_target_grid(goal_x=15)
        second_grid = search_object_target_grid(goal_x=17)

        first = planner.decide(
            first_grid,
            (6,),
            (instruction,),
            source_signature="visual:first",
        )
        restored = SemanticPlannerState.from_payload(planner.to_payload())
        second = restored.decide(
            second_grid,
            (6,),
            (instruction,),
            source_signature="visual:second",
        )

        self.assertIsNotNone(first.action)
        self.assertIsNotNone(second.action)
        self.assertIn("state-graph", first.reason)
        self.assertIn("state-graph", second.reason)
        self.assertFalse(first.memory_influenced)
        self.assertTrue(second.memory_influenced)
        self.assertEqual(restored.target_observation_count, 1)
        self.assertEqual(
            sum(len(edges) for edges in restored.target_transitions.values()),
            1,
        )

    def test_object_target_state_graph_excludes_failed_action(self) -> None:
        instruction = object_target_instruction()
        grid = search_object_target_grid(goal_x=15)
        planner = SemanticPlannerState()
        first = planner.decide(
            grid,
            (6,),
            (instruction,),
            source_signature="visual:first",
        )
        assert first.action is not None
        planner.record_target_hazard()
        planner.invalidate_active_plan()

        after_failure = planner.decide(
            grid,
            (6,),
            (instruction,),
            source_signature="visual:first",
        )

        self.assertIsNotNone(after_failure.action)
        assert after_failure.action is not None
        self.assertNotEqual(
            after_failure.action.key,
            first.action.key,
        )

    def test_observed_safe_target_action_is_not_reclassified_as_hazard(
        self,
    ) -> None:
        planner = SemanticPlannerState(
            target_pending_state="target-state",
            target_pending_action="target-action",
            target_safe_actions={"target-action"},
        )

        classified = planner.record_target_hazard()

        self.assertFalse(classified)
        self.assertEqual(planner.target_hazards, {})
        self.assertEqual(planner.target_pending_state, "")
        self.assertEqual(planner.target_pending_action, "")

    def test_object_target_state_ignores_excluded_interface_color(
        self,
    ) -> None:
        instruction = object_target_instruction()
        first = SemanticPlannerState()
        second = SemanticPlannerState()

        first_decision = first.decide(
            search_object_target_grid(goal_x=15, token_color=3),
            (6,),
            (instruction,),
            source_signature="visual:first",
        )
        second_decision = second.decide(
            search_object_target_grid(goal_x=15, token_color=5),
            (6,),
            (instruction,),
            source_signature="visual:second",
        )

        self.assertIsNotNone(first_decision.action)
        self.assertIsNotNone(second_decision.action)
        self.assertEqual(
            first.target_pending_state,
            second.target_pending_state,
        )

    def test_object_target_state_retains_visible_mechanism_phase(
        self,
    ) -> None:
        instruction = object_target_instruction()
        first = SemanticPlannerState()
        second = SemanticPlannerState()

        first.decide(
            search_object_target_grid(goal_x=15, token_color=9),
            (6,),
            (instruction,),
            source_signature="visual:first",
        )
        second.decide(
            search_object_target_grid(goal_x=15, token_color=10),
            (6,),
            (instruction,),
            source_signature="visual:second",
        )

        self.assertNotEqual(
            first.target_pending_state,
            second.target_pending_state,
        )

    def test_coordinate_descent_round_trip_commits_best_cycle_phase(
        self,
    ) -> None:
        action = target_control_action("control:a", x=10)
        base = target_search_surface(
            signature="target:base",
            cost=8,
            actions=(action,),
            coordinate_descent=True,
        )
        improved = target_search_surface(
            signature="target:improved",
            cost=3,
            actions=(action,),
            coordinate_descent=True,
        )

        self.assertEqual(
            SemanticPlannerState()._target_coordinate_action(base),
            action,
        )
        planner = SemanticPlannerState()
        self.assertEqual(planner._target_coordinate_action(base), action)
        planner._observe_target_coordinate(improved, action.key)
        self.assertEqual(planner.target_coordinate_best_step, 1)
        self.assertEqual(planner._target_coordinate_action(improved), action)
        planner._observe_target_coordinate(base, action.key)
        self.assertEqual(planner.target_coordinate_phase, "commit")
        self.assertEqual(planner.target_coordinate_commit_remaining, 1)

        restored = SemanticPlannerState.from_payload(planner.to_payload())
        self.assertEqual(
            restored._target_coordinate_action(base),
            action,
        )
        restored._observe_target_coordinate(improved, action.key)
        self.assertEqual(restored.target_coordinate_phase, "probe")
        self.assertEqual(restored.target_coordinate_completed_passes, 1)
        self.assertEqual(
            restored._target_coordinate_action(improved),
            action,
        )
        restored._observe_target_coordinate(base, action.key)
        self.assertEqual(restored._target_coordinate_action(base), action)
        restored._observe_target_coordinate(improved, action.key)

        self.assertEqual(restored.target_coordinate_phase, "done")
        self.assertEqual(restored.target_coordinate_completed_passes, 2)
        self.assertFalse(restored.target_coordinate_abandoned)

    def test_permutation_model_compiles_and_round_trips_future_plan(
        self,
    ) -> None:
        rotate = target_control_action("control:rotate", x=10)
        swap = target_control_action("control:swap", x=20)
        surface = target_search_surface(
            signature="target:model",
            cost=1,
            actions=(rotate, swap),
            coordinate_descent=False,
            colors=(1, 2, 3),
            requirements=((0, 3), (1, 1)),
        )
        planner = SemanticPlannerState(
            target_model_positions=surface.mechanism_positions,
            target_model_requirements=surface.target_requirements,
            target_permutation_candidates={
                rotate.key: ((2,), (0,), (1,)),
                swap.key: ((1,), (0,), (2,)),
            },
            target_permutation_observations={
                rotate.key: 2,
                swap.key: 2,
            },
        )

        selected = planner._target_model_action(surface)

        self.assertEqual(selected, rotate)
        self.assertEqual(planner.target_model_expected_colors, (3, 1, 2))
        self.assertEqual(planner.target_model_plan_count, 1)
        restored = SemanticPlannerState.from_payload(planner.to_payload())
        self.assertEqual(
            restored.target_permutation_candidates,
            planner.target_permutation_candidates,
        )
        self.assertEqual(
            restored.target_model_expected_colors,
            (3, 1, 2),
        )

    def test_model_prediction_mismatch_clears_plan_and_refines_evidence(
        self,
    ) -> None:
        action = target_control_action("control:rotate", x=10)
        surface = target_search_surface(
            signature="target:model-after",
            cost=1,
            actions=(action,),
            coordinate_descent=False,
            colors=(2, 3, 1),
            requirements=((0, 1),),
        )
        planner = SemanticPlannerState(
            target_model_positions=surface.mechanism_positions,
            target_model_requirements=surface.target_requirements,
            target_pending_mechanism=(1, 2, 3),
            target_permutation_candidates={
                action.key: ((0, 1, 2), (0, 1, 2), (0, 1, 2)),
            },
            target_model_plan=[action.key],
            target_model_expected_colors=(3, 1, 2),
        )

        planner._observe_target_model(
            surface,
            pending_action=action.key,
        )

        self.assertEqual(planner.target_model_mismatch_count, 1)
        self.assertEqual(planner.target_model_plan, [])
        self.assertEqual(
            planner.target_permutation_candidates[action.key],
            ((1,), (2,), (0,)),
        )
        self.assertEqual(
            planner.target_permutation_observations[action.key],
            1,
        )


if __name__ == "__main__":
    unittest.main()
