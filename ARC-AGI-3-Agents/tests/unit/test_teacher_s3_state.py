from __future__ import annotations

import unittest

from arc3_agi_agent.teacher.s3_state import (
    identity_routing_free_source_body,
)


class TeacherS3StateTests(unittest.TestCase):
    def test_explicit_identity_and_ordinal_fields_are_removed(self) -> None:
        body = identity_routing_free_source_body(
            {
                "game_class": "ExampleGame42",
                "source_fields": {
                    "_action_count": 19,
                    "_current_level_index": 4,
                    "_game_id": "example-identity",
                    "_state": "NOT_FINISHED",
                    "mechanic_state": {"phase": 2},
                },
                "current_level_data": {"objects": 3},
                "custom_hidden_state": {"energy": 7},
                "previous_environment_action": {
                    "action_id": 2,
                    "action_data": {},
                },
                "excluded_unstable_or_unbounded_source_field_count": 5,
                "selection_exclusions": [],
            }
        )

        self.assertNotIn("game_class", body)
        self.assertEqual(
            body["source_fields"],
            {
                "_state": "NOT_FINISHED",
                "mechanic_state": {"phase": 2},
            },
        )
        self.assertEqual(
            body[
                "excluded_identity_or_ordinal_source_field_count"
            ],
            4,
        )
        self.assertIn("GAME_ID", body["selection_exclusions"])
        self.assertIn("LEVEL_ID", body["selection_exclusions"])
        self.assertIn("ACTION_ORDINAL", body["selection_exclusions"])

    def test_missing_game_class_evidence_fails_closed(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "S3_SOURCE_GAME_CLASS_EVIDENCE_MISSING",
        ):
            identity_routing_free_source_body(
                {
                    "source_fields": {},
                }
            )


if __name__ == "__main__":
    unittest.main()
