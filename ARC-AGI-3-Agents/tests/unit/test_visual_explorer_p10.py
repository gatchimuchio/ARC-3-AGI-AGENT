from __future__ import annotations

import unittest

from arc3_agi_agent.visual_explorer import (
    DeterministicVisualExplorer,
    analyze_scene,
    connected_components,
    last_rendered_grid,
    normalized_grid,
    status_mask,
)


class VisualExplorerP10Tests(unittest.TestCase):
    def test_grid_normalization_and_last_layer_are_deterministic(self) -> None:
        grid = ((0, 0), (1, 1))
        self.assertEqual(normalized_grid(grid), grid)
        self.assertEqual(last_rendered_grid(((), grid)), grid)
        self.assertEqual(normalized_grid(((0,), (0, 1))), ())

    def test_connected_components_return_real_click_pixels(self) -> None:
        grid = (
            (0, 0, 0, 0),
            (0, 8, 8, 0),
            (0, 8, 0, 0),
            (0, 0, 0, 0),
        )
        components = connected_components(grid)
        red = next(component for component in components if component.color == 8)
        self.assertEqual(red.area, 3)
        self.assertIn(red.click_point, red.pixels)

    def test_status_mask_uses_edge_geometry_not_identity(self) -> None:
        grid = tuple(
            tuple(9 if y == 0 else 0 for _ in range(12))
            for y in range(12)
        )
        mask = status_mask(grid)
        self.assertEqual(len(mask), 12)
        self.assertTrue(all((x, 0) in mask for x in range(12)))

    def test_scene_candidate_order_is_stable_and_observation_derived(
        self,
    ) -> None:
        grid = (
            (0, 0, 0, 0, 0),
            (0, 8, 8, 0, 0),
            (0, 8, 8, 0, 0),
            (0, 0, 0, 0, 0),
        )
        first = analyze_scene(grid, (1, 2, 6))
        second = analyze_scene(grid, (1, 2, 6))
        self.assertEqual(first, second)
        click = next(item for item in first.candidates if item.action_id == 6)
        self.assertEqual((click.x, click.y), (1, 1))
        self.assertNotIn("game", repr(first).casefold())
        self.assertNotIn("level", repr(first).casefold())

    def test_no_change_memory_changes_next_action(self) -> None:
        grid = (
            (0, 0, 0),
            (0, 8, 0),
            (0, 0, 0),
        )
        scene = analyze_scene(grid, (1, 2))
        explorer = DeterministicVisualExplorer()
        explorer.observe(
            scene,
            terminal_state="NOT_FINISHED",
            level_progress=False,
        )
        first = explorer.decide(scene)
        self.assertIsNotNone(first.action)
        explorer.observe(
            scene,
            terminal_state="NOT_FINISHED",
            level_progress=False,
        )
        second = explorer.decide(scene)
        self.assertIsNotNone(second.action)
        assert first.action is not None
        assert second.action is not None
        self.assertNotEqual(first.action.key, second.action.key)
        self.assertTrue(second.memory_influenced)
        self.assertGreater(explorer.memory_read_count, 0)

    def test_transition_graph_returns_to_frontier(self) -> None:
        first_scene = analyze_scene(
            ((0, 0, 0), (0, 8, 0), (0, 0, 0)),
            (1,),
        )
        second_scene = analyze_scene(
            ((0, 0, 0), (0, 9, 0), (0, 0, 0)),
            (1, 2),
        )
        explorer = DeterministicVisualExplorer()
        explorer.observe(
            first_scene,
            terminal_state="NOT_FINISHED",
            level_progress=False,
        )
        first = explorer.decide(first_scene)
        self.assertIsNotNone(first.action)
        explorer.observe(
            second_scene,
            terminal_state="NOT_FINISHED",
            level_progress=False,
        )
        second = explorer.decide(second_scene)
        self.assertIsNotNone(second.action)
        explorer.observe(
            first_scene,
            terminal_state="NOT_FINISHED",
            level_progress=False,
        )
        routed = explorer.decide(first_scene)
        self.assertEqual(routed.reason, "VISUAL_TRANSITION_GRAPH_ROUTE")
        self.assertEqual(routed.frontier_distance, 1)

    def test_hazard_is_retained_and_not_reselected(self) -> None:
        grid = (
            (0, 0, 0),
            (0, 8, 0),
            (0, 0, 0),
        )
        scene = analyze_scene(grid, (1, 2))
        explorer = DeterministicVisualExplorer()
        explorer.observe(
            scene,
            terminal_state="NOT_FINISHED",
            level_progress=False,
        )
        first = explorer.decide(scene)
        explorer.observe(
            scene,
            terminal_state="GAME_OVER",
            level_progress=False,
        )
        second = explorer.decide(scene)
        assert first.action is not None
        assert second.action is not None
        self.assertNotEqual(first.action.key, second.action.key)
        self.assertEqual(explorer.failure_count, 1)

    def test_rejected_result_can_commit_hazard_without_pending_state(
        self,
    ) -> None:
        scene = analyze_scene(
            ((0, 0, 0), (0, 8, 0), (0, 0, 0)),
            (1, 2),
        )
        explorer = DeterministicVisualExplorer()
        first = scene.candidates[0]
        explorer.record_hazard(scene.signature, first)
        selected = explorer.decide(scene)
        assert selected.action is not None
        self.assertNotEqual(selected.action.key, first.key)
        self.assertTrue(selected.memory_influenced)

    def test_serialization_round_trip_preserves_decision(self) -> None:
        scene = analyze_scene(
            ((0, 0, 0), (0, 8, 0), (0, 0, 0)),
            (1, 2, 6),
        )
        explorer = DeterministicVisualExplorer()
        explorer.observe(
            scene,
            terminal_state="NOT_FINISHED",
            level_progress=False,
        )
        explorer.decide(scene)
        explorer.observe(
            scene,
            terminal_state="NOT_FINISHED",
            level_progress=False,
        )
        restored = DeterministicVisualExplorer.from_payload(
            explorer.to_payload()
        )
        self.assertEqual(restored.digest, explorer.digest)
        self.assertEqual(restored.decide(scene), explorer.decide(scene))


if __name__ == "__main__":
    unittest.main()
