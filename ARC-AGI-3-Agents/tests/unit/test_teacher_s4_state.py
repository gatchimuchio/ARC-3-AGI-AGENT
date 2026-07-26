from __future__ import annotations

import inspect
import unittest

from arc3_agi_agent.teacher.s4_state import (
    S4_ACTION_EFFECT_HISTORY_LIMIT,
    descriptor_from_s3_condition,
    state_condition_descriptor,
    state_condition_signature,
)


class TeacherS4StateTests(unittest.TestCase):
    def test_source_digest_is_required_as_subtraction_evidence_only(
        self,
    ) -> None:
        descriptor = descriptor_from_s3_condition(
            {
                "schema_version": (
                    "arc3-teacher-s3-identity-free-state-condition-v1"
                ),
                "rendered_frame_digest": "render:abc",
                "terminal_state": "NOT_FINISHED",
                "available_actions": [1, 2, 6],
                "source_state_digest": "source:must-not-survive",
                "bounded_action_effect_history": [
                    {
                        "action_id": 2,
                        "after_rendered_frame_digest": "render:abc",
                    }
                ],
                "action_effect_history_limit": (
                    S4_ACTION_EFFECT_HISTORY_LIMIT
                ),
            }
        )

        self.assertNotIn("source_state_digest", descriptor)
        self.assertNotIn("hidden_state", descriptor)
        self.assertEqual(
            descriptor["rendered_frame_digest"],
            "render:abc",
        )
        self.assertEqual(descriptor["available_actions"], [1, 2, 6])

    def test_missing_source_subtraction_evidence_fails_closed(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "S4_SOURCE_CONDITION_FIELD_MISSING:source_state_digest",
        ):
            descriptor_from_s3_condition(
                {
                    "rendered_frame_digest": "render:abc",
                    "terminal_state": "NOT_FINISHED",
                    "available_actions": [1],
                    "bounded_action_effect_history": [],
                    "action_effect_history_limit": (
                        S4_ACTION_EFFECT_HISTORY_LIMIT
                    ),
                }
            )

    def test_runtime_state_api_accepts_no_environment_or_source(self) -> None:
        expected = {
            "frame",
            "action_effect_history",
            "current_rendered_frame_digest",
        }
        self.assertEqual(
            set(inspect.signature(state_condition_descriptor).parameters),
            expected,
        )
        self.assertEqual(
            set(inspect.signature(state_condition_signature).parameters),
            expected,
        )


if __name__ == "__main__":
    unittest.main()
