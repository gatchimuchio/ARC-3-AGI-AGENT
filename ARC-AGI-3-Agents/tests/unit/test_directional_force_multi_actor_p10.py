from __future__ import annotations

import unittest
from dataclasses import replace

from arc3_agi_agent.directional_force_multi_actor import (
    DIRECTION_PROBE_EVIDENCE,
    _composed_model,
    _ComposedState,
    _CompositionParameters,
    _is_goal,
    _render_state,
    _search,
    _transition,
    _visual_action,
    directional_force_multi_actor_observation_status,
    directional_force_multi_actor_plan,
    directional_force_multi_actor_successor_observation_status,
    directional_force_multi_actor_transition_observation_limit,
    is_directional_force_multi_actor_probe_action,
)
from arc3_agi_agent.instruction_body import SemanticOperatorInstruction
from arc3_agi_agent.p10_instruction_compiler import (
    directional_force_route_instruction_mapping,
    multi_actor_shape_push_target_instruction_mapping,
)
from arc3_agi_agent.schema import digest_object, forbidden_runtime_paths
from arc3_agi_agent.semantic_operators import SemanticPlannerState

Mask = tuple[tuple[int, int], ...]
Grid = tuple[tuple[int, ...], ...]


def _instruction(mapping: dict[str, object]) -> SemanticOperatorInstruction:
    return SemanticOperatorInstruction(
        operator_id=str(mapping["operator_id"]),
        action_id=int(mapping["action_id"]),
        detector=str(mapping["detector"]),
        transform=str(mapping["transform"]),
        parameter_items=tuple(
            sorted(dict(mapping["parameters"]).items())
        ),
        preconditions=tuple(str(item) for item in mapping["preconditions"]),
        falsification_conditions=tuple(
            str(item) for item in mapping["falsification_conditions"]
        ),
        provenance=tuple(str(item) for item in mapping["provenance"]),
    )


def _directional_instruction(
    *,
    navigation_states: int = 100,
    search_states: int = 100,
    plan_actions: int = 32,
) -> SemanticOperatorInstruction:
    return _instruction(
        directional_force_route_instruction_mapping(
            maximum_transition_observations=2,
            multi_actor_composition_enabled=True,
            maximum_composition_navigation_states=navigation_states,
            maximum_composition_search_states=search_states,
            maximum_composition_plan_actions=plan_actions,
        )
    )


def _multi_instruction() -> SemanticOperatorInstruction:
    return _instruction(
        multi_actor_shape_push_target_instruction_mapping()
    )


def _rectangle_mask(width: int, height: int) -> Mask:
    return tuple(
        (x, y)
        for y in range(height)
        for x in range(width)
    )


def _plus_mask() -> Mask:
    return tuple(
        (x, y)
        for y in range(9)
        for x in range(9)
        if 3 <= x <= 5 or 3 <= y <= 5
    )


def _fill(
    grid: list[list[int]],
    *,
    x: int,
    y: int,
    mask: Mask,
    color: int,
) -> None:
    for dx, dy in mask:
        grid[y + dy][x + dx] = color


def _outline(
    grid: list[list[int]],
    *,
    goal_x: int,
    goal_y: int,
    mask: Mask,
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
    marker: int,
) -> None:
    for dy in range(3):
        for dx in range(3):
            grid[y + dy][x + dx] = 14
    grid[y + 1][x + 1] = marker


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


def _composition_grid(
    *,
    phase: int,
    shift_x: int = 0,
    first_direction: tuple[int, int] = (0, 1),
) -> Grid:
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
    _outline(
        grid,
        goal_x=50 + shift_x,
        goal_y=29,
        mask=square,
    )
    _outline(
        grid,
        goal_x=38 + shift_x,
        goal_y=53,
        mask=square,
    )
    _outline(
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
    _fill(
        grid,
        x=20 + shift_x,
        y=50,
        mask=plus,
        color=11,
    )
    _force(
        grid,
        x=8 + shift_x,
        y=32,
        direction=first_direction,
        phase=phase,
    )
    _force(
        grid,
        x=32 + shift_x,
        y=44,
        direction=(0, -1),
        phase=phase,
    )
    return tuple(tuple(row) for row in grid)


def _compact_model(
    *,
    shift_x: int = 0,
):
    directional = _directional_instruction()
    multi_instruction = _multi_instruction()
    parsed = _composed_model(
        _composition_grid(phase=1, shift_x=shift_x),
        directional,
        multi_instruction,
    )
    assert parsed is not None
    multi = replace(
        parsed.multi,
        goal_families=(
            (((0,), ((35 + shift_x, 50),))),
            (
                (1, 2),
                (
                    (14 + shift_x, 50),
                    (29 + shift_x, 32),
                ),
            ),
        ),
    )
    positions = (
        (20 + shift_x, 50),
        (29 + shift_x, 32),
        (14 + shift_x, 50),
        *parsed.initial_state.positions[parsed.multi_count :],
    )
    state = _ComposedState(
        positions=positions,
        selected=2,
        marker_colors=(None, 5, 0),
        phase=1,
    )
    return replace(
        parsed,
        multi=multi,
        initial_state=state,
    )


class DirectionalForceMultiActorTests(unittest.TestCase):
    def test_composition_is_instruction_gated_and_identity_free(
        self,
    ) -> None:
        active_mapping = directional_force_route_instruction_mapping()
        active = _instruction(active_mapping)
        candidate_mapping = (
            directional_force_route_instruction_mapping(
                multi_actor_composition_enabled=True
            )
        )
        candidate = _instruction(candidate_mapping)

        self.assertIsNone(
            _CompositionParameters.from_instruction(active)
        )
        self.assertIsNotNone(
            _CompositionParameters.from_instruction(candidate)
        )
        self.assertNotIn(
            "multi_actor_composition_enabled",
            active.parameters(),
        )
        self.assertEqual(
            candidate.operator_id,
            active.operator_id,
        )
        self.assertEqual(
            directional_force_multi_actor_transition_observation_limit(
                active
            ),
            0,
        )
        self.assertEqual(
            directional_force_multi_actor_transition_observation_limit(
                candidate
            ),
            8,
        )
        self.assertEqual(candidate.validate(), ())
        self.assertEqual(forbidden_runtime_paths(candidate_mapping), ())

    def test_idle_direction_uses_one_reversible_observation_probe(
        self,
    ) -> None:
        directional = _directional_instruction()
        multi_instruction = _multi_instruction()
        grid = _composition_grid(phase=0)
        model = _composed_model(
            grid,
            directional,
            multi_instruction,
        )
        self.assertIsNotNone(model)
        assert model is not None
        self.assertFalse(model.force_directions_observed)

        plan = directional_force_multi_actor_plan(
            grid,
            (1, 2, 3, 4, 6),
            directional,
            multi_instruction,
        )

        self.assertEqual(len(plan), 1)
        probe = plan[0]
        self.assertTrue(
            is_directional_force_multi_actor_probe_action(probe)
        )
        self.assertIn(DIRECTION_PROBE_EVIDENCE, probe.evidence)
        self.assertEqual(
            directional_force_multi_actor_observation_status(
                grid,
                directional,
                multi_instruction,
                probe,
            ),
            "MATCH",
        )

        true_model = _composed_model(
            grid,
            directional,
            multi_instruction,
            force_direction_hints=((0, 1), (0, -1)),
            force_position_hints=tuple(
                force.position for force in model.forces
            ),
        )
        self.assertIsNotNone(true_model)
        assert true_model is not None
        successor = _transition(
            true_model,
            true_model.initial_state,
            ("move", probe.action_id),
        )
        charged = _render_state(true_model, successor)
        reparsed = _composed_model(
            charged,
            directional,
            multi_instruction,
        )
        self.assertIsNotNone(reparsed)
        assert reparsed is not None
        self.assertTrue(reparsed.force_directions_observed)
        self.assertEqual(
            directional_force_multi_actor_successor_observation_status(
                charged,
                directional,
                multi_instruction,
                probe,
            ),
            "MISMATCH",
        )

    def test_relation_event_search_closes_generated_composition(
        self,
    ) -> None:
        model = _compact_model()

        plan = _search(model)
        state = model.initial_state
        for action in plan:
            state = _transition(model, state, action)

        self.assertTrue(plan)
        self.assertLessEqual(len(plan), 32)
        self.assertTrue(_is_goal(model, state))

    def test_translation_preserves_relation_event_actions(
        self,
    ) -> None:
        first = _search(_compact_model())
        translated = _search(_compact_model(shift_x=-3))

        self.assertEqual(first, translated)

    def test_queued_transition_requires_direction_and_state_evidence(
        self,
    ) -> None:
        directional = _directional_instruction()
        multi_instruction = _multi_instruction()
        model = _composed_model(
            _composition_grid(phase=1),
            directional,
            multi_instruction,
        )
        self.assertIsNotNone(model)
        assert model is not None
        action = ("move", 1)
        public_action = _visual_action(
            model,
            directional,
            multi_instruction,
            state=model.initial_state,
            action=action,
            index=0,
            plan_digest=digest_object(("generated", action)),
        )
        successor = _transition(
            model,
            model.initial_state,
            action,
        )

        self.assertEqual(
            directional_force_multi_actor_observation_status(
                _render_state(model, model.initial_state),
                directional,
                multi_instruction,
                public_action,
            ),
            "MATCH",
        )
        self.assertEqual(
            directional_force_multi_actor_successor_observation_status(
                _render_state(model, successor),
                directional,
                multi_instruction,
                public_action,
            ),
            "MATCH",
        )
        animated_footer = [
            list(row) for row in _render_state(model, successor)
        ]
        animated_footer[model.multi.height][0] = (
            model.multi.walkable_color
        )
        self.assertEqual(
            directional_force_multi_actor_successor_observation_status(
                tuple(tuple(row) for row in animated_footer),
                directional,
                multi_instruction,
                public_action,
            ),
            "MATCH",
        )
        marker_variation = [
            list(row) for row in _render_state(model, successor)
        ]
        selected = successor.selected
        selected_position = successor.positions[selected]
        selected_entity = model.multi.entities[selected]
        marker_x, marker_y = selected_entity.mask[-1]
        marker_variation[
            selected_position[1] + marker_y
        ][selected_position[0] + marker_x] = (
            model.directional_parameters.selected_marker_color
        )
        self.assertEqual(
            directional_force_multi_actor_successor_observation_status(
                tuple(tuple(row) for row in marker_variation),
                directional,
                multi_instruction,
                public_action,
            ),
            "MATCH",
        )
        tampered = replace(
            public_action,
            evidence=tuple(
                (
                    "directional-force-composition-directions:[[1,0]]"
                    if item.startswith(
                        "directional-force-composition-directions:"
                    )
                    else item
                )
                for item in public_action.evidence
            ),
        )
        self.assertEqual(
            directional_force_multi_actor_observation_status(
                _render_state(model, model.initial_state),
                directional,
                multi_instruction,
                tampered,
            ),
            "MISMATCH",
        )

    def test_visible_charge_direction_overrides_nearby_hazard_guess(
        self,
    ) -> None:
        model = _composed_model(
            _composition_grid(
                phase=1,
                first_direction=(1, 0),
            ),
            _directional_instruction(),
            _multi_instruction(),
        )

        self.assertIsNotNone(model)
        assert model is not None
        self.assertTrue(model.force_directions_observed)
        self.assertIn(
            (1, 0),
            tuple(force.direction for force in model.forces),
        )

    def test_transient_composed_frame_advances_bounded_queue_once(
        self,
    ) -> None:
        directional = _directional_instruction()
        multi_instruction = _multi_instruction()
        model = _composed_model(
            _composition_grid(phase=1),
            directional,
            multi_instruction,
        )
        self.assertIsNotNone(model)
        assert model is not None
        first_state = _transition(
            model,
            model.initial_state,
            ("move", 1),
        )
        queued = _visual_action(
            model,
            directional,
            multi_instruction,
            state=first_state,
            action=("move", 2),
            index=1,
            plan_digest=digest_object(("generated-transient",)),
        )
        transient = [list(row) for row in _render_state(model, first_state)]
        force_position = first_state.positions[model.multi_count]
        transient[force_position[1]][force_position[0]] = (
            model.multi.walkable_color
        )
        planner = SemanticPlannerState(
            queue=[queued],
            active_operator=directional.operator_id,
            active_instruction_digest=digest_object(directional),
            active_plan_signature="semantic-plan:generated-transient",
            source_signature="rendered-composition-transient",
        )

        decision = planner.decide(
            tuple(tuple(row) for row in transient),
            (1, 2, 3, 4, 6),
            (directional, multi_instruction),
            source_signature="rendered-composition-transient",
        )

        self.assertEqual(decision.action, queued)
        self.assertIn("transition-reobserve", decision.reason)
        self.assertEqual(planner.queue, [])
        self.assertEqual(planner.directional_force_wait_count, 1)


if __name__ == "__main__":
    unittest.main()
