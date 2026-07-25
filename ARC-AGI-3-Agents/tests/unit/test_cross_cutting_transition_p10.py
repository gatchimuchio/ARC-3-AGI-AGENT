from __future__ import annotations

import unittest

from arc3_agi_agent.cross_cutting_transition import (
    C2C3CapabilityProbe,
    VisibleStateAbstraction,
    observe_visible_transition,
)
from arc3_agi_agent.schema import forbidden_runtime_paths
from arc3_agi_agent.visual_explorer import (
    VisualAction,
    analyze_scene,
)

Grid = tuple[tuple[int, ...], ...]


def _grid(
    *,
    color: int = 8,
    x: int = 1,
    y: int = 1,
    width: int = 6,
    height: int = 6,
) -> Grid:
    rows = [[0 for _x in range(width)] for _y in range(height)]
    rows[y][x] = color
    rows[y][x + 1] = color
    rows[y + 1][x] = color
    rows[y + 1][x + 1] = color
    return tuple(tuple(row) for row in rows)


def _action(action_id: int = 1) -> VisualAction:
    return VisualAction(
        key=f"simple:{action_id}",
        action_id=action_id,
        group=0,
        evidence=("available-action-surface",),
    )


class CrossCuttingTransitionP10Tests(unittest.TestCase):
    def test_visible_effect_model_separates_no_change_motion_and_redraw(
        self,
    ) -> None:
        before = _grid()
        moved = _grid(x=2)
        redraw = tuple(tuple(9 for _x in row) for row in before)
        before_scene = analyze_scene(before, (1, 2, 3, 4))
        moved_scene = analyze_scene(moved, (1, 2, 3, 4))
        redraw_scene = analyze_scene(redraw, (1, 2, 3, 4))

        no_change = observe_visible_transition(
            before_grid=before,
            after_grid=before,
            before_scene=before_scene,
            after_scene=before_scene,
            action=_action(),
            terminal_state="NOT_FINISHED",
            progress_observed=False,
        )
        motion = observe_visible_transition(
            before_grid=before,
            after_grid=moved,
            before_scene=before_scene,
            after_scene=moved_scene,
            action=_action(),
            terminal_state="NOT_FINISHED",
            progress_observed=False,
        )
        global_redraw = observe_visible_transition(
            before_grid=before,
            after_grid=redraw,
            before_scene=before_scene,
            after_scene=redraw_scene,
            action=_action(),
            terminal_state="NOT_FINISHED",
            progress_observed=False,
        )

        self.assertEqual(
            no_change.effect_classes,
            ("NO_VISIBLE_CHANGE",),
        )
        self.assertIn("COMPONENT_MOTION", motion.effect_classes)
        self.assertIn("VISIBLE_STATE_CHANGE", motion.effect_classes)
        self.assertIn("GLOBAL_REDRAW", global_redraw.effect_classes)
        self.assertEqual(no_change.boundary_label, "NO_VISIBLE_COMMIT")
        self.assertEqual(motion.boundary_label, "TRANSITION_NO_COMMIT")

    def test_commit_and_hazard_are_explicit_not_proxy_effects(self) -> None:
        before = _grid()
        after = _grid(x=2)
        before_scene = analyze_scene(before, (1, 2, 3, 4))
        after_scene = analyze_scene(after, (1, 2, 3, 4))
        commit = observe_visible_transition(
            before_grid=before,
            after_grid=after,
            before_scene=before_scene,
            after_scene=after_scene,
            action=_action(),
            terminal_state="NOT_FINISHED",
            progress_observed=True,
        )
        hazard = observe_visible_transition(
            before_grid=before,
            after_grid=after,
            before_scene=before_scene,
            after_scene=after_scene,
            action=_action(),
            terminal_state="GAME_OVER",
            progress_observed=False,
        )
        self.assertEqual(commit.boundary_label, "COMMIT")
        self.assertIn("PROGRESS_BOUNDARY", commit.effect_classes)
        self.assertEqual(hazard.boundary_label, "HAZARD")
        self.assertIn("IRREVERSIBLE_HAZARD", hazard.effect_classes)

    def test_cross_context_prediction_is_non_authoritative(self) -> None:
        probe = C2C3CapabilityProbe()
        first_before = _grid(color=8, x=1)
        first_after = _grid(color=8, x=2)
        second_before = _grid(color=12, x=2, width=8)
        second_after = _grid(color=12, x=3, width=8)
        for before, after in (
            (first_before, first_after),
            (second_before, second_after),
        ):
            probe.observe(
                before_grid=before,
                after_grid=after,
                before_scene=analyze_scene(before, (1, 2, 3, 4)),
                after_scene=analyze_scene(after, (1, 2, 3, 4)),
                action=_action(),
                terminal_state="NOT_FINISHED",
                progress_observed=True,
            )

        unseen = _grid(color=10, x=1, width=10)
        prediction = probe.predict(
            VisibleStateAbstraction.from_scene(
                analyze_scene(unseen, (1, 2, 3, 4))
            ),
            _action(),
        )
        self.assertEqual(prediction.status, "COMMIT_LIKELY")
        self.assertEqual(prediction.context_support, 2)
        self.assertFalse(prediction.action_selection_authorized)
        self.assertFalse(prediction.memory_write_authorized)
        self.assertFalse(prediction.runtime_p_promotion_authorized)

    def test_probe_payload_is_identity_free_and_shadow_only(self) -> None:
        probe = C2C3CapabilityProbe()
        before = _grid()
        after = _grid(x=2)
        probe.observe(
            before_grid=before,
            after_grid=after,
            before_scene=analyze_scene(before, (1, 2, 3, 4)),
            after_scene=analyze_scene(after, (1, 2, 3, 4)),
            action=_action(),
            terminal_state="NOT_FINISHED",
            progress_observed=False,
        )
        payload = probe.to_payload()
        self.assertEqual(payload["candidate_tier"], "LOCAL_PROBE")
        self.assertEqual(payload["runtime_decision_use"], "FORBIDDEN")
        self.assertFalse(payload["action_selection_influence"])
        self.assertEqual(forbidden_runtime_paths(payload), ())
        self.assertFalse(hasattr(probe, "select_action"))
        self.assertFalse(hasattr(probe, "emit"))
        self.assertFalse(hasattr(probe, "promote"))

    def test_shadow_fault_is_audited_without_authority(self) -> None:
        probe = C2C3CapabilityProbe()
        probe.record_fault("FRAME_MISSING")

        payload = probe.to_payload()

        self.assertEqual(payload["observation_count"], 0)
        self.assertEqual(payload["fault_count"], 1)
        self.assertEqual(payload["fault_counts"], {"FRAME_MISSING": 1})
        self.assertFalse(payload["action_selection_influence"])
        self.assertEqual(payload["runtime_decision_use"], "FORBIDDEN")


if __name__ == "__main__":
    unittest.main()
