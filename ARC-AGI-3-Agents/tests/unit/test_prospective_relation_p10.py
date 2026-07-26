from __future__ import annotations

import unittest

from arc3_agi_agent.prospective_relation import (
    PROSPECTIVE_RELATION_RECORD_LIMIT,
    ProspectiveObligationRelationProbe,
    compile_prospective_relation,
)
from arc3_agi_agent.schema import forbidden_runtime_paths
from arc3_agi_agent.visual_explorer import VisualAction, analyze_scene

Grid = tuple[tuple[int, ...], ...]


def _grid(
    *,
    width: int = 12,
    height: int = 12,
    offset_x: int = 0,
    offset_y: int = 0,
) -> Grid:
    rows = [[0 for _x in range(width)] for _y in range(height)]
    for y in range(2 + offset_y, 4 + offset_y):
        for x in range(2 + offset_x, 4 + offset_x):
            rows[y][x] = 8
    for y in range(2 + offset_y, 4 + offset_y):
        rows[y][7 + offset_x] = 9
    return tuple(tuple(row) for row in rows)


def _scaled_grid(scale: int) -> Grid:
    base = _grid(width=10, height=8)
    return tuple(
        tuple(value for value in row for _x in range(scale))
        for row in base
        for _y in range(scale)
    )


def _action(*, x: int = 2, y: int = 2) -> VisualAction:
    return VisualAction(
        key="click:synthetic",
        action_id=6,
        group=0,
        x=x,
        y=y,
        evidence=(
            "rendered-connected-component",
            "component-prototype:synthetic",
        ),
    )


class ProspectiveRelationP10Tests(unittest.TestCase):
    def test_relation_class_is_translation_and_uniform_scale_invariant(
        self,
    ) -> None:
        base = _grid()
        translated = _grid(offset_x=1, offset_y=2)
        base_state = compile_prospective_relation(
            rendered_grid=base,
            scene=analyze_scene(base, (6,)),
            action=_action(),
        )
        translated_state = compile_prospective_relation(
            rendered_grid=translated,
            scene=analyze_scene(translated, (6,)),
            action=_action(x=3, y=4),
        )
        self.assertEqual(
            base_state.relation_class,
            translated_state.relation_class,
        )
        self.assertEqual(
            base_state.cluster_class,
            translated_state.cluster_class,
        )

        scale_one = _scaled_grid(1)
        scale_two = _scaled_grid(2)
        state_one = compile_prospective_relation(
            rendered_grid=scale_one,
            scene=analyze_scene(scale_one, (6,)),
            action=_action(),
        )
        state_two = compile_prospective_relation(
            rendered_grid=scale_two,
            scene=analyze_scene(scale_two, (6,)),
            action=_action(x=4, y=4),
        )
        self.assertEqual(state_one.relation_class, state_two.relation_class)
        self.assertEqual(state_one.cluster_class, state_two.cluster_class)

    def test_prediction_is_made_before_current_outcome_updates_model(
        self,
    ) -> None:
        probe = ProspectiveObligationRelationProbe()
        before = _grid()
        after_rows = [list(row) for row in before]
        after_rows[2][7] = 0
        after_rows[3][7] = 0
        after_rows[2][6] = 9
        after_rows[3][6] = 9
        after = tuple(tuple(row) for row in after_rows)
        kwargs = {
            "before_grid": before,
            "after_grid": after,
            "before_scene": analyze_scene(before, (6,)),
            "after_scene": analyze_scene(after, (6,)),
            "action": _action(),
            "terminal_state": "NOT_FINISHED",
            "progress_observed": False,
        }

        first = probe.observe(**kwargs)
        second = probe.observe(**kwargs)

        self.assertEqual(first.prediction.label, "UNKNOWN")
        self.assertIsNone(first.prediction_match)
        self.assertNotEqual(second.prediction.label, "UNKNOWN")
        self.assertTrue(second.prediction_match)
        self.assertEqual(probe.known_prediction_count, 1)
        self.assertEqual(probe.correct_prediction_count, 1)

    def test_outcome_obligations_are_explicit_and_post_observation_only(
        self,
    ) -> None:
        before = _grid()
        scene = analyze_scene(before, (6,))
        action = _action()
        progress_probe = ProspectiveObligationRelationProbe()
        progress = progress_probe.observe(
            before_grid=before,
            after_grid=before,
            before_scene=scene,
            after_scene=scene,
            action=action,
            terminal_state="NOT_FINISHED",
            progress_observed=True,
        )
        hazard_probe = ProspectiveObligationRelationProbe()
        hazard = hazard_probe.observe(
            before_grid=before,
            after_grid=before,
            before_scene=scene,
            after_scene=scene,
            action=action,
            terminal_state="GAME_OVER",
            progress_observed=False,
        )
        no_change_probe = ProspectiveObligationRelationProbe()
        no_change = no_change_probe.observe(
            before_grid=before,
            after_grid=before,
            before_scene=scene,
            after_scene=scene,
            action=action,
            terminal_state="NOT_FINISHED",
            progress_observed=False,
        )

        self.assertEqual(
            progress.observed_obligation,
            "REOBSERVE_COMMIT_STATE",
        )
        self.assertEqual(
            hazard.observed_obligation,
            "SUSPEND_AND_REQUEST_ROLLBACK",
        )
        self.assertEqual(
            no_change.observed_obligation,
            "CHANGE_RELATION_OR_WAIT",
        )
        self.assertEqual(
            progress.pre_action_relation,
            hazard.pre_action_relation,
        )
        self.assertEqual(
            hazard.pre_action_relation,
            no_change.pre_action_relation,
        )

    def test_payload_is_identity_free_bounded_and_non_authoritative(
        self,
    ) -> None:
        probe = ProspectiveObligationRelationProbe()
        before = _grid()
        scene = analyze_scene(before, (6,))
        for _index in range(PROSPECTIVE_RELATION_RECORD_LIMIT + 2):
            probe.observe(
                before_grid=before,
                after_grid=before,
                before_scene=scene,
                after_scene=scene,
                action=_action(),
                terminal_state="NOT_FINISHED",
                progress_observed=False,
            )

        payload = probe.to_payload()

        self.assertEqual(payload["candidate_tier"], "LOCAL_PROBE")
        self.assertEqual(payload["runtime_use"], "FORBIDDEN")
        self.assertFalse(payload["action_selection_influence"])
        self.assertFalse(payload["memory_write_authority"])
        self.assertFalse(payload["external_emit_authority"])
        self.assertFalse(payload["runtime_p_promotion_authority"])
        self.assertFalse(payload["raw_grid_retention"])
        self.assertEqual(
            len(payload["records"]),
            PROSPECTIVE_RELATION_RECORD_LIMIT,
        )
        self.assertEqual(payload["record_overflow_count"], 2)
        self.assertTrue(payload["overflow_digest_chain"])
        self.assertEqual(forbidden_runtime_paths(payload), ())
        self.assertFalse(hasattr(probe, "select_action"))
        self.assertFalse(hasattr(probe, "emit"))
        self.assertFalse(hasattr(probe, "promote"))

    def test_fault_is_visible_without_runtime_authority(self) -> None:
        probe = ProspectiveObligationRelationProbe()
        probe.record_fault("FRAME_MISSING")

        payload = probe.to_payload()

        self.assertEqual(payload["observation_count"], 0)
        self.assertEqual(payload["fault_count"], 1)
        self.assertEqual(payload["fault_counts"], {"FRAME_MISSING": 1})
        self.assertFalse(payload["action_selection_influence"])


if __name__ == "__main__":
    unittest.main()
