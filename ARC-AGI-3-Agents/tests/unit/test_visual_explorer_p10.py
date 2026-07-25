from __future__ import annotations

import unittest

from arc3_agi_agent.visual_explorer import (
    VISUAL_EXPLORER_FORMAT,
    VISUAL_EXPLORER_MAX_ACTIONS_PER_NODE,
    VISUAL_EXPLORER_MAX_CONTEXTS_PER_NODE,
    VISUAL_EXPLORER_MAX_NODES,
    DeterministicVisualExplorer,
    VisualAction,
    VisualScene,
    analyze_scene,
    connected_components,
    last_rendered_grid,
    normalized_grid,
    status_mask,
)


def manual_scene(
    signature: str,
    candidates: tuple[VisualAction, ...],
) -> VisualScene:
    return VisualScene(
        signature=signature,
        grid_digest=signature,
        structural_digest=signature,
        width=4,
        height=4,
        status_mask=frozenset(),
        components=(),
        candidates=candidates,
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

    def test_component_prototype_is_camera_scale_invariant(self) -> None:
        shape = (
            (0, 8, 8, 0, 0),
            (0, 8, 8, 0, 0),
            (0, 8, 8, 0, 0),
            (0, 8, 8, 0, 0),
            (0, 0, 0, 0, 0),
        )
        scaled = tuple(
            tuple(value for value in row for _ in range(2))
            for row in shape
            for _ in range(2)
        )
        first = analyze_scene(
            shape,
            (6,),
            fixed_status_mask=frozenset(),
        )
        second = analyze_scene(
            scaled,
            (6,),
            fixed_status_mask=frozenset(),
        )
        first_foreground = next(
            action for action in first.candidates if action.group == 0
        )
        second_foreground = next(
            action for action in second.candidates if action.group == 0
        )

        self.assertEqual(
            first_foreground.prototype_key,
            second_foreground.prototype_key,
        )

    def test_state_identity_keeps_full_render_while_structure_uses_mask(
        self,
    ) -> None:
        first_grid = tuple(
            tuple(9 if y == 0 else 0 for _ in range(12))
            for y in range(12)
        )
        second_grid = tuple(
            tuple(8 if y == 0 else 0 for _ in range(12))
            for y in range(12)
        )
        first = analyze_scene(first_grid, (1,))
        second = analyze_scene(second_grid, (1,))
        self.assertNotEqual(first.signature, second.signature)
        self.assertNotEqual(first.grid_digest, second.grid_digest)
        self.assertEqual(first.structural_digest, second.structural_digest)

    def test_state_identity_includes_the_rendered_action_surface(self) -> None:
        grid = (
            (0, 0, 0),
            (0, 8, 0),
            (0, 0, 0),
        )

        first = analyze_scene(grid, (1,))
        second = analyze_scene(grid, (1, 2))

        self.assertEqual(first.grid_digest, second.grid_digest)
        self.assertNotEqual(first.signature, second.signature)

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

    def test_disconnected_frontier_requires_reset_but_total_exhaustion_does_not(
        self,
    ) -> None:
        initial = analyze_scene(
            ((0, 0, 0), (0, 8, 0), (0, 0, 0)),
            (1, 2),
        )
        dead_end = analyze_scene(
            ((0, 0, 0), (0, 9, 0), (0, 0, 0)),
            (1,),
        )
        explorer = DeterministicVisualExplorer()
        explorer.observe(
            initial,
            terminal_state="NOT_FINISHED",
            level_progress=False,
        )
        first = explorer.decide(initial)
        self.assertEqual(first.action, initial.candidates[0])
        explorer.observe(
            dead_end,
            terminal_state="NOT_FINISHED",
            level_progress=False,
        )
        explorer.decide(dead_end)
        explorer.observe(
            dead_end,
            terminal_state="NOT_FINISHED",
            level_progress=False,
        )

        reset_required = explorer.decide(dead_end)
        self.assertIsNone(reset_required.action)
        self.assertEqual(
            reset_required.reason,
            "VISUAL_BRANCH_EXHAUSTED_RESET_REQUIRED",
        )

        explorer.observe(
            initial,
            terminal_state="NOT_FINISHED",
            level_progress=False,
        )
        second = explorer.decide(initial)
        self.assertEqual(second.action, initial.candidates[1])
        explorer.observe(
            initial,
            terminal_state="NOT_FINISHED",
            level_progress=False,
        )
        exhausted = explorer.decide(initial)
        self.assertIsNone(exhausted.action)
        self.assertEqual(exhausted.reason, "VISUAL_FRONTIER_EXHAUSTED")

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

    def test_affordance_prototype_defers_known_hazard_across_positions(
        self,
    ) -> None:
        first = VisualAction(
            key="first-position",
            action_id=6,
            group=0,
            x=1,
            y=1,
            evidence=("component-prototype:known-hazard",),
        )
        moved = VisualAction(
            key="moved-position",
            action_id=6,
            group=0,
            x=2,
            y=2,
            evidence=("component-prototype:known-hazard",),
        )
        unseen = VisualAction(
            key="unseen-affordance",
            action_id=6,
            group=0,
            x=3,
            y=3,
            evidence=("component-prototype:unseen",),
        )
        explorer = DeterministicVisualExplorer()
        explorer.record_hazard("visual-state:source", first)

        selected = explorer.decide(
            manual_scene(
                "visual-state:other",
                (moved, unseen),
            )
        )

        self.assertEqual(selected.action, unseen)
        self.assertEqual(
            explorer.prototype_outcomes[first.prototype_key]["HAZARD"],
            1,
        )

    def test_progress_affordance_is_prioritized_on_next_structure(self) -> None:
        progress_action = VisualAction(
            key="progress-first",
            action_id=6,
            group=0,
            x=1,
            y=1,
            evidence=("component-prototype:progress",),
        )
        next_progress_action = VisualAction(
            key="progress-next",
            action_id=6,
            group=0,
            x=2,
            y=2,
            evidence=("component-prototype:progress",),
        )
        unseen = VisualAction(
            key="unseen-first-in-order",
            action_id=6,
            group=0,
            x=3,
            y=3,
            evidence=("component-prototype:unseen",),
        )
        first_scene = manual_scene(
            "visual-state:first",
            (progress_action,),
        )
        next_scene = manual_scene(
            "visual-state:next",
            (unseen, next_progress_action),
        )
        explorer = DeterministicVisualExplorer()
        explorer.observe(
            first_scene,
            terminal_state="NOT_FINISHED",
            level_progress=False,
        )
        explorer.decide(first_scene)
        explorer.observe(
            next_scene,
            terminal_state="NOT_FINISHED",
            level_progress=True,
        )

        selected = explorer.decide(next_scene)

        self.assertEqual(selected.action, next_progress_action)
        self.assertEqual(
            explorer.progress_prototypes[progress_action.prototype_key],
            1,
        )

    def test_novelty_first_policy_defers_known_transition(self) -> None:
        known = VisualAction(
            key="known-transition",
            action_id=1,
            group=0,
        )
        unseen = VisualAction(
            key="unseen-action",
            action_id=2,
            group=0,
        )
        explorer = DeterministicVisualExplorer()
        explorer.prototype_outcomes[known.prototype_key] = {
            "TRANSITION": 3,
        }

        legacy = explorer.decide(
            manual_scene("visual-state:legacy", (known, unseen))
        )
        novelty_first = explorer.decide(
            manual_scene("visual-state:novelty", (known, unseen)),
            prototype_priority_mode="novelty-first",
        )

        self.assertEqual(legacy.action, known)
        self.assertEqual(novelty_first.action, unseen)
        self.assertEqual(
            novelty_first.reason,
            "VISUAL_UNTESTED_CANDIDATE_NOVELTY_FIRST",
        )

    def test_one_step_context_reopens_no_change_once_per_context(
        self,
    ) -> None:
        scene = manual_scene(
            "visual-state:context-reopen",
            (
                VisualAction(key="first", action_id=1, group=0),
                VisualAction(key="second", action_id=2, group=0),
            ),
        )
        explorer = DeterministicVisualExplorer()
        explorer.observe(
            scene,
            terminal_state="NOT_FINISHED",
            level_progress=False,
        )

        first = explorer.decide(
            scene,
            causal_context_mode="one-step-visible",
        )
        explorer.observe(
            scene,
            terminal_state="NOT_FINISHED",
            level_progress=False,
        )
        second = explorer.decide(
            scene,
            causal_context_mode="one-step-visible",
        )
        explorer.observe(
            scene,
            terminal_state="NOT_FINISHED",
            level_progress=False,
        )
        third = explorer.decide(
            scene,
            causal_context_mode="one-step-visible",
        )

        self.assertIsNotNone(first.action)
        self.assertIsNotNone(second.action)
        self.assertIsNotNone(third.action)
        assert first.action is not None
        assert second.action is not None
        assert third.action is not None
        self.assertEqual(first.action.key, "first")
        self.assertEqual(second.action.key, "second")
        self.assertEqual(third.action.key, "first")
        self.assertEqual(
            second.reason,
            "VISUAL_CONTEXT_UNTESTED_CANDIDATE",
        )

    def test_one_step_context_never_reopens_global_hazard(self) -> None:
        scene = manual_scene(
            "visual-state:context-hazard",
            (
                VisualAction(key="hazard", action_id=1, group=0),
                VisualAction(key="safe", action_id=2, group=0),
            ),
        )
        explorer = DeterministicVisualExplorer()
        explorer.observe(
            scene,
            terminal_state="NOT_FINISHED",
            level_progress=False,
        )
        first = explorer.decide(
            scene,
            causal_context_mode="one-step-visible",
        )
        assert first.action is not None
        self.assertEqual(first.action.key, "hazard")
        explorer.observe(
            scene,
            terminal_state="GAME_OVER",
            level_progress=False,
        )

        second = explorer.decide(
            scene,
            causal_context_mode="one-step-visible",
        )

        assert second.action is not None
        self.assertEqual(second.action.key, "safe")

    def test_one_step_context_round_trip_and_bound(self) -> None:
        scene = manual_scene(
            "visual-state:context-round-trip",
            (VisualAction(key="first", action_id=1, group=0),),
        )
        explorer = DeterministicVisualExplorer()
        explorer.observe(
            scene,
            terminal_state="NOT_FINISHED",
            level_progress=False,
        )
        explorer.decide(
            scene,
            causal_context_mode="one-step-visible",
        )
        explorer.observe(
            scene,
            terminal_state="NOT_FINISHED",
            level_progress=False,
        )
        for index in range(
            VISUAL_EXPLORER_MAX_CONTEXTS_PER_NODE + 2
        ):
            explorer.causal_context_token = f"causal-context:{index:02d}"
            explorer.decide(
                scene,
                causal_context_mode="one-step-visible",
            )
            explorer.observe(
                scene,
                terminal_state="NOT_FINISHED",
                level_progress=False,
            )

        payload = explorer.to_payload()
        restored = DeterministicVisualExplorer.from_payload(payload)

        self.assertEqual(restored.to_payload(), payload)
        node = next(iter(restored.nodes.values()))
        self.assertLessEqual(
            len(node.context_outcomes),
            VISUAL_EXPLORER_MAX_CONTEXTS_PER_NODE,
        )
        self.assertGreater(restored.context_eviction_count, 0)

    def test_disabled_context_keeps_active_payload_shape_unchanged(
        self,
    ) -> None:
        scene = manual_scene(
            "visual-state:active-payload-shape",
            (VisualAction(key="advance", action_id=1, group=0),),
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

        payload = explorer.to_payload()

        for key in (
            "causal_context_extension_format",
            "max_contexts_per_node",
            "causal_context_token",
            "pending_causal_context_token",
            "context_eviction_count",
        ):
            self.assertNotIn(key, payload)
        node = next(iter(payload["nodes"].values()))
        self.assertNotIn("context_order", node)
        self.assertNotIn("context_outcomes", node)

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

    def test_legacy_payload_reads_and_rewrites_as_bounded_v2(self) -> None:
        scene = manual_scene(
            "visual-state:legacy-payload",
            (VisualAction(key="advance", action_id=1, group=0),),
        )
        explorer = DeterministicVisualExplorer()
        explorer.observe(
            scene,
            terminal_state="NOT_FINISHED",
            level_progress=False,
        )
        legacy = explorer.to_payload()
        legacy["format"] = "arc3-visual-explorer-v1"
        legacy.pop("max_nodes")
        legacy.pop("max_actions_per_node")
        legacy.pop("node_lru")

        restored = DeterministicVisualExplorer.from_payload(legacy)

        self.assertEqual(
            restored.to_payload()["format"],
            VISUAL_EXPLORER_FORMAT,
        )
        self.assertEqual(restored.decide(scene), explorer.decide(scene))

    def test_bounded_payload_rejects_bound_drift(self) -> None:
        scene = manual_scene("visual-state:bound-drift", ())
        explorer = DeterministicVisualExplorer()
        explorer.observe(
            scene,
            terminal_state="NOT_FINISHED",
            level_progress=False,
        )
        payload = explorer.to_payload()
        payload["max_nodes"] = VISUAL_EXPLORER_MAX_NODES + 1

        with self.assertRaisesRegex(
            ValueError,
            "visual explorer payload bounds invalid",
        ):
            DeterministicVisualExplorer.from_payload(payload)

    def test_action_window_pages_beyond_the_first_bounded_slice(self) -> None:
        candidates = tuple(
            VisualAction(
                key=f"candidate-{index:03d}",
                action_id=1,
                group=0,
            )
            for index in range(VISUAL_EXPLORER_MAX_ACTIONS_PER_NODE + 7)
        )
        scene = manual_scene("visual-state:paged-actions", candidates)
        explorer = DeterministicVisualExplorer()
        explorer.observe(
            scene,
            terminal_state="NOT_FINISHED",
            level_progress=False,
        )
        selected: list[str] = []

        for _ in range(VISUAL_EXPLORER_MAX_ACTIONS_PER_NODE + 1):
            decision = explorer.decide(scene)
            self.assertIsNotNone(decision.action)
            assert decision.action is not None
            selected.append(decision.action.key)
            explorer.observe(
                scene,
                terminal_state="NOT_FINISHED",
                level_progress=False,
            )
            self.assertLessEqual(
                len(explorer.nodes[scene.signature].actions),
                VISUAL_EXPLORER_MAX_ACTIONS_PER_NODE,
            )

        self.assertEqual(len(set(selected)), len(selected))
        self.assertIn(
            candidates[VISUAL_EXPLORER_MAX_ACTIONS_PER_NODE].key,
            selected,
        )

    def test_node_lru_is_bounded_and_round_trip_is_deterministic(self) -> None:
        scenes = tuple(
            manual_scene(
                f"visual-state:bounded-{index:03d}",
                (
                    VisualAction(
                        key=f"advance-{index:03d}",
                        action_id=1,
                        group=0,
                    ),
                ),
            )
            for index in range(VISUAL_EXPLORER_MAX_NODES + 9)
        )
        explorer = DeterministicVisualExplorer()
        explorer.observe(
            scenes[0],
            terminal_state="NOT_FINISHED",
            level_progress=False,
        )
        for index, scene in enumerate(scenes[:-1]):
            decision = explorer.decide(scene)
            self.assertIsNotNone(decision.action)
            explorer.observe(
                scenes[index + 1],
                terminal_state="NOT_FINISHED",
                level_progress=False,
            )

        self.assertLessEqual(len(explorer.nodes), VISUAL_EXPLORER_MAX_NODES)
        self.assertIn(explorer.initial_signature, explorer.nodes)
        self.assertTrue(
            all(
                len(node.actions) <= VISUAL_EXPLORER_MAX_ACTIONS_PER_NODE
                for node in explorer.nodes.values()
            )
        )
        restored = DeterministicVisualExplorer.from_payload(
            explorer.to_payload()
        )
        self.assertEqual(restored.digest, explorer.digest)
        self.assertLessEqual(len(restored.nodes), VISUAL_EXPLORER_MAX_NODES)

    def test_evicted_transition_target_reopens_source_action(self) -> None:
        scenes = tuple(
            manual_scene(
                f"visual-state:eviction-{index:03d}",
                (
                    VisualAction(
                        key=f"advance-{index:03d}",
                        action_id=1,
                        group=0,
                    ),
                ),
            )
            for index in range(VISUAL_EXPLORER_MAX_NODES + 4)
        )
        explorer = DeterministicVisualExplorer()
        explorer.observe(
            scenes[0],
            terminal_state="NOT_FINISHED",
            level_progress=False,
        )
        first_action = scenes[0].candidates[0]

        for index, scene in enumerate(scenes[:-1]):
            decision = explorer.decide(scene)
            self.assertIsNotNone(decision.action)
            explorer.observe(
                scenes[index + 1],
                terminal_state="NOT_FINISHED",
                level_progress=False,
            )

        self.assertNotIn(scenes[1].signature, explorer.nodes)
        self.assertIsNone(
            explorer.known_outcome(
                scenes[0].signature,
                first_action.key,
            )
        )
        reopened = explorer.decide(scenes[0])
        self.assertEqual(reopened.action, first_action)

    def test_semantic_action_uses_compact_pending_state(self) -> None:
        first_scene = manual_scene("visual-state:first", ())
        second_scene = manual_scene("visual-state:second", ())
        action = VisualAction(
            key="semantic-action",
            action_id=6,
            group=0,
            x=1,
            y=1,
            evidence=("operator-prototype:semantic-test",),
        )
        explorer = DeterministicVisualExplorer()
        explorer.observe(
            first_scene,
            terminal_state="NOT_FINISHED",
            level_progress=False,
        )

        self.assertTrue(explorer.stage_action(first_scene, action))
        restored = DeterministicVisualExplorer.from_payload(
            explorer.to_payload()
        )
        restored.observe(
            second_scene,
            terminal_state="NOT_FINISHED",
            level_progress=False,
        )

        self.assertEqual(restored.transition_count, 1)
        self.assertEqual(len(restored.nodes), 1)
        self.assertIsNone(restored.semantic_pending_action)
        self.assertEqual(
            restored.prototype_outcomes[action.prototype_key]["TRANSITION"],
            1,
        )


if __name__ == "__main__":
    unittest.main()
