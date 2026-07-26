from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from arc3_agi_agent.teacher.replay_runner import run_teacher_corpus

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class TeacherS0ReplayIntegrationTests(unittest.TestCase):
    def test_override_and_level_reset_compatibility_close_selected_games(
        self,
    ) -> None:
        with (
            tempfile.TemporaryDirectory(
                prefix="arc3-teacher-recordings-"
            ) as recordings,
            patch.dict(os.environ, {"OPERATION_MODE": "offline"}, clear=False),
        ):
            report = run_teacher_corpus(
                environments_dir=REPOSITORY_ROOT / "environment_files",
                corpus_path=(
                    REPOSITORY_ROOT
                    / "analysis"
                    / "teacher"
                    / "FULL_SOLUTION_CORPUS.json"
                ),
                requested_games=(
                    "ft09-0d8bbf25",
                    "r11l-495a7899",
                ),
                recordings_dir=Path(recordings),
            )

        self.assertTrue(report["all_complete"])
        self.assertEqual(report["game_count"], 2)
        self.assertEqual(report["completed_levels"], 12)
        self.assertEqual(report["level_count"], 12)
        self.assertEqual(report["actions_executed"], 227)
        self.assertEqual(report["error_count"], 0)
        self.assertEqual(report["available_action_mismatch_count"], 0)
        self.assertEqual(report["level_reset_compatibility_count"], 4)


if __name__ == "__main__":
    unittest.main()
