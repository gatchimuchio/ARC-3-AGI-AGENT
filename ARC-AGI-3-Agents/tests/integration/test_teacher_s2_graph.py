from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from arc3_agi_agent.teacher.s2_graph_compiler import (
    compile_s2_policy_graph,
)
from arc3_agi_agent.teacher.s2_graph_executor import (
    run_s2_policy_graph,
)
from arc3_agi_agent.teacher.s2_graph_schema import all_mapping_keys

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class TeacherS2GraphIntegrationTests(unittest.TestCase):
    def test_role_graph_closes_without_absolute_target_input(self) -> None:
        with (
            tempfile.TemporaryDirectory(
                prefix="arc3-teacher-s2-"
            ) as temporary,
            patch.dict(
                os.environ,
                {"OPERATION_MODE": "offline"},
                clear=False,
            ),
        ):
            temporary_root = Path(temporary)
            graph_path = temporary_root / "graph.json"
            graph = compile_s2_policy_graph(
                environments_dir=REPOSITORY_ROOT / "environment_files",
                s1_policy_graph_path=(
                    REPOSITORY_ROOT
                    / "analysis"
                    / "teacher"
                    / "S1_STATE_CONDITIONED_POLICY_GRAPH.json"
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
            report = run_s2_policy_graph(
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
        self.assertFalse(report["literal_coordinate_stored"])
        self.assertFalse(report["literal_coordinate_decision_used"])
        self.assertEqual(
            report["role_selector_resolution_count"],
            report[
                "environment_api_pointer_payload_generated_count"
            ],
        )
        self.assertEqual(
            all_mapping_keys(graph).intersection(
                {
                    "absolute_horizontal_index",
                    "absolute_vertical_index",
                    "action_data",
                    "column",
                    "coordinate",
                    "row",
                    "x",
                    "y",
                }
            ),
            set(),
        )


if __name__ == "__main__":
    unittest.main()
