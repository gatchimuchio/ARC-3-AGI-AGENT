from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sample_main import run_offline_samples


class OfflineSampleRunnerIntegrationTests(unittest.TestCase):
    def test_all_bundled_samples_cross_hds_offline_boundary_once(self) -> None:
        environments = Path(__file__).resolve().parents[3] / "environment_files"
        with (
            tempfile.TemporaryDirectory(prefix="arc3-p1-recordings-") as output,
            patch.dict(os.environ, {"OPERATION_MODE": "offline"}, clear=False),
            patch(
                "requests.sessions.Session.request",
                side_effect=AssertionError("network request forbidden in P1"),
            ),
            patch(
                "socket.create_connection",
                side_effect=AssertionError("network socket forbidden in P1"),
            ),
        ):
            result = run_offline_samples(
                environments_dir=environments,
                all_samples=True,
                max_actions=1,
                recordings_dir=Path(output),
            )

        self.assertEqual(result["operation_mode"], "offline")
        self.assertEqual(result["environment_count"], 25)
        self.assertEqual(result["completed_count"], 25)
        self.assertEqual(result["error_count"], 0, result["errors"])
        for report in result["reports"]:
            self.assertEqual(report["actions"], 1)
            self.assertEqual(report["context_actions_used"], 1)
            self.assertEqual(report["memory_version"], 1)
            self.assertTrue(report["previous_observation_present"])
            self.assertEqual(report["decision_statuses"], ("EMIT", "STOP"))
            self.assertEqual(report["verification_statuses"], ("SUSPEND",))
            self.assertGreaterEqual(len(report["trace_digests"]), 2)

    def test_recording_is_written_without_leaking_directory_state(self) -> None:
        environments = Path(__file__).resolve().parents[3] / "environment_files"
        with (
            tempfile.TemporaryDirectory(prefix="arc3-p1-recordings-") as output,
            patch.dict(
                os.environ,
                {
                    "OPERATION_MODE": "offline",
                    "RECORDINGS_DIR": "preexisting-recordings-directory",
                },
                clear=False,
            ),
            patch(
                "requests.sessions.Session.request",
                side_effect=AssertionError("network request forbidden in P1"),
            ),
            patch(
                "socket.create_connection",
                side_effect=AssertionError("network socket forbidden in P1"),
            ),
        ):
            result = run_offline_samples(
                environments_dir=environments,
                requested_games=["LS20"],
                max_actions=1,
                record=True,
                recordings_dir=Path(output),
            )
            restored = os.environ["RECORDINGS_DIR"]
            recordings = tuple(Path(output).glob("*.recording.jsonl"))
            recording_line_count = (
                len(recordings[0].read_text(encoding="utf-8").splitlines())
                if recordings
                else 0
            )

        self.assertEqual(result["completed_count"], 1)
        self.assertEqual(result["error_count"], 0, result["errors"])
        self.assertEqual(restored, "preexisting-recordings-directory")
        self.assertEqual(len(recordings), 1)
        self.assertGreaterEqual(recording_line_count, 2)


if __name__ == "__main__":
    unittest.main()
