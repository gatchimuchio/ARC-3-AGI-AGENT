from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from arc3_agi_agent.teacher.s1_graph_compiler import (
    compile_s1_policy_graph,
)
from arc3_agi_agent.teacher.s1_graph_executor import (
    run_s1_policy_graph,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class TeacherS1GraphIntegrationTests(unittest.TestCase):
    def test_state_graph_closes_without_executor_corpus_input(self) -> None:
        with (
            tempfile.TemporaryDirectory(
                prefix="arc3-teacher-s1-"
            ) as temporary,
            patch.dict(
                os.environ,
                {"OPERATION_MODE": "offline"},
                clear=False,
            ),
        ):
            temporary_root = Path(temporary)
            graph_path = temporary_root / "graph.json"
            graph = compile_s1_policy_graph(
                environments_dir=REPOSITORY_ROOT / "environment_files",
                corpus_path=(
                    REPOSITORY_ROOT
                    / "analysis"
                    / "teacher"
                    / "FULL_SOLUTION_CORPUS.json"
                ),
                requested_games=("ft09-0d8bbf25",),
                recordings_dir=temporary_root / "compile-recordings",
            )
            graph_path.write_text(
                json.dumps(
                    graph,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n",
                encoding="utf-8",
                newline="\n",
            )
            report = run_s1_policy_graph(
                environments_dir=REPOSITORY_ROOT / "environment_files",
                policy_graph_path=graph_path,
                requested_games=("ft09-0d8bbf25",),
                recordings_dir=temporary_root / "execute-recordings",
            )

        self.assertTrue(report["all_complete"])
        self.assertEqual(report["game_count"], 1)
        self.assertEqual(report["completed_levels"], 6)
        self.assertEqual(report["level_count"], 6)
        self.assertEqual(report["error_count"], 0)
        self.assertFalse(report["fixed_action_sequence_used"])
        self.assertEqual(
            report["strict_distance_decrease_count"],
            report["actions_executed"],
        )


if __name__ == "__main__":
    unittest.main()
