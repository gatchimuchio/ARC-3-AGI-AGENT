from __future__ import annotations

import unittest

from 道具.benchmark_telemetry_audit import audit_benchmark


class BenchmarkTelemetryAuditTests(unittest.TestCase):
    def test_separates_job_elapsed_from_cumulative_game_clocks(self):
        data = {
            "start_time": "2026-10-23T20:00:00",
            "end_time": "2026-10-23T20:01:40",
            "game_runs": [
                {"game_id": "a", "final_wallclock_seconds": 30.0},
                {"game_id": "b", "final_wallclock_seconds": 100.0},
            ],
        }
        result = audit_benchmark(data, "total wallclock: 130.0s\n")

        self.assertEqual(result["job_elapsed_seconds"], 100.0)
        self.assertEqual(result["game_runs"][1]["elapsed_since_previous_game_seconds"], 70.0)
        self.assertEqual(result["sum_of_cumulative_wallclocks_seconds"], 130.0)
        self.assertFalse(result["summary_wallclock_matches_job_elapsed_1s_tolerance"])
        self.assertTrue(result["summary_wallclock_matches_cumulative_sum_0_11s_tolerance"])

    def test_compares_history_solver_note_and_final_token_fields(self):
        data = {
            "start_time": "2026-10-23T20:00:00",
            "end_time": "2026-10-23T20:00:02",
            "game_runs": [
                {
                    "history": [{"generated_tokens": 11}, {"generated_tokens": 7}],
                    "solver_note": "solver result tokens=20",
                    "final_generated_tokens": 0,
                },
                {
                    "history": [{"generated_tokens": 5}],
                    "solver_note": "tokens=5",
                    "final_generated_tokens": 0,
                },
            ],
        }
        result = audit_benchmark(data, "total tokens: 23\n")

        self.assertEqual(result["total_history_generated_tokens"], 23)
        self.assertEqual(result["total_solver_note_tokens"], 25)
        self.assertEqual(result["game_runs"][0]["solver_note_minus_history_tokens"], 2)
        self.assertEqual(result["total_final_generated_tokens_field"], 0)
        self.assertTrue(result["summary_tokens_match_history_1_token_tolerance"])

    def test_rejects_decreasing_cumulative_clock(self):
        data = {
            "start_time": "2026-10-23T20:00:00",
            "end_time": "2026-10-23T20:01:00",
            "game_runs": [
                {"final_wallclock_seconds": 40.0},
                {"final_wallclock_seconds": 39.0},
            ],
        }

        with self.assertRaisesRegex(ValueError, "cumulative and nondecreasing"):
            audit_benchmark(data)