from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from p10_standard_budget_audit import _resource_rows


class P10StandardBudgetAuditTests(unittest.TestCase):
    def test_split_worker_and_timing_logs_bind_swap_measurement(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            worker_logs = root / "worker"
            timing_logs = root / "timing"
            worker_logs.mkdir()
            timing_logs.mkdir()
            game_id = "g00-sample"
            (worker_logs / f"{game_id}.log").write_text(
                '{"status": "EXECUTED", "game_id": "g00-sample"}\n',
                encoding="utf-8",
            )
            (timing_logs / f"{game_id}.time.log").write_text(
                "elapsed=12.50 max_rss_kb=98765 swaps=0 exit=0\n",
                encoding="utf-8",
            )

            rows, complete = _resource_rows(
                game_ids=[game_id],
                log_dirs=[worker_logs, timing_logs],
            )

        self.assertTrue(complete)
        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["elapsed_wall_seconds"], 12.5)
        self.assertEqual(rows[0]["maximum_rss_kb"], 98_765)
        self.assertEqual(rows[0]["swaps"], 0)
        self.assertEqual(rows[0]["exit_code"], 0)

    def test_legacy_combined_log_remains_readable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            game_id = "g00-sample"
            (root / f"{game_id}.log").write_text(
                '{"status": "EXECUTED"}\n'
                "elapsed=12.50 max_rss_kb=98765\n",
                encoding="utf-8",
            )

            rows, complete = _resource_rows(
                game_ids=[game_id],
                log_dirs=[root],
            )

        self.assertTrue(complete)
        self.assertEqual(rows[0]["swaps"], None)
        self.assertEqual(rows[0]["exit_code"], None)

    def test_split_log_retains_nonzero_exit_for_fail_closed_audit(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            worker_logs = root / "worker"
            timing_logs = root / "timing"
            worker_logs.mkdir()
            timing_logs.mkdir()
            game_id = "g00-sample"
            (worker_logs / f"{game_id}.log").write_text(
                '{"status": "EXECUTED"}\n',
                encoding="utf-8",
            )
            (timing_logs / f"{game_id}.time.log").write_text(
                "elapsed=3.25 max_rss_kb=100000 swaps=0 exit=7\n",
                encoding="utf-8",
            )

            rows, complete = _resource_rows(
                game_ids=[game_id],
                log_dirs=[worker_logs, timing_logs],
            )

        self.assertTrue(complete)
        self.assertEqual(rows[0]["exit_code"], 7)


if __name__ == "__main__":
    unittest.main()
