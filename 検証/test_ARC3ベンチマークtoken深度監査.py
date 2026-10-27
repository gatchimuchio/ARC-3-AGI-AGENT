from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from ARC3ベンチマークtoken深度監査 import audit_token_depth


class TokenDepthAuditTests(unittest.TestCase):
    def test_joins_public_depth_and_emits_only_aggregate_data(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            events = root / "events"
            events.mkdir()
            (events / "public-a_p0_events.jsonl").write_text(
                "\n".join(
                    json.dumps(row)
                    for row in [
                        {"type": "initial", "level": 1},
                        {"type": "action", "level": 1},
                        {"type": "action", "level": 2},
                    ]
                ),
                encoding="utf-8",
            )
            (events / "public-b_p0_events.jsonl").write_text(
                "\n".join(
                    json.dumps(row)
                    for row in [
                        {"type": "initial", "level": 1},
                        {"type": "action", "level": 1},
                    ]
                ),
                encoding="utf-8",
            )
            benchmark = {
                "start_time": "2026-10-23T20:00:00",
                "end_time": "2026-10-23T20:00:10",
                "game_runs": [
                    {
                        "game_id": "public-a",
                        "history": [
                            {
                                "generated_tokens": 2,
                                "uncached_input_tokens": 0,
                                "wallclock_seconds": 1,
                            },
                            {
                                "generated_tokens": 4,
                                "uncached_input_tokens": 0,
                                "wallclock_seconds": 2,
                            },
                        ],
                    },
                    {
                        "game_id": "public-b",
                        "history": [
                            {
                                "generated_tokens": 0,
                                "uncached_input_tokens": 0,
                                "wallclock_seconds": 3,
                            },
                        ],
                    },
                ],
            }
            result = audit_token_depth(benchmark, events, "total tokens: 6\n", max_actions=2)

        self.assertEqual(result["event_history_aligned_runs"], 2)
        self.assertEqual(result["action_count"], 3)
        self.assertEqual(result["termination_groups"]["action_limit_reached"]["run_count"], 1)
        self.assertEqual(result["termination_groups"]["below_action_limit"]["run_count"], 1)
        self.assertEqual(result["public_level_depth"][0]["depth"], 1)
        self.assertEqual(result["public_level_depth"][0]["action_count"], 3)
        self.assertEqual(result["public_level_depth"][0]["generated_tokens_total"], 6)
        self.assertTrue(result["telemetry"]["generated_tokens_match_summary"])
        rendered = json.dumps(result)
        for forbidden in ("game_id", "filename", "board", "action_name", "trajectory"):
            self.assertNotIn(forbidden, rendered)

    def test_rejects_history_that_does_not_align_with_events(self):
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp)
            (root / "public-a_p0_events.jsonl").write_text(
                '{"type":"initial","level":1}\n{"type":"action","level":1}\n',
                encoding="utf-8",
            )
            benchmark = {
                "start_time": "2026-10-23T20:00:00",
                "end_time": "2026-10-23T20:00:10",
                "game_runs": [
                    {
                        "game_id": "public-a",
                        "history": [],
                    }
                ],
            }
            with self.assertRaisesRegex(ValueError, "does not align"):
                audit_token_depth(benchmark, root, "total tokens: 0\n")


if __name__ == "__main__":
    unittest.main()
