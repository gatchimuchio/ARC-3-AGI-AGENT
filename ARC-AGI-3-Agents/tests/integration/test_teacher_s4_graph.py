from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from arc3_agi_agent.teacher.s4_graph_compiler import (
    compile_s4_policy_graph,
)
from arc3_agi_agent.teacher.s4_graph_executor import (
    run_s4_policy_graph,
)
from arc3_agi_agent.teacher.s4_graph_schema import (
    all_mapping_keys,
    identity_literal_values,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SMOKE_ENVIRONMENTS = (
    "bp35-0a0ad940",
    "ft09-0d8bbf25",
    "lf52-271a04aa",
    "ls20-9607627b",
)


class TeacherS4GraphIntegrationTests(unittest.TestCase):
    def test_graph_closes_without_source_or_hidden_state(self) -> None:
        with (
            tempfile.TemporaryDirectory(
                prefix="arc3-teacher-s4-"
            ) as temporary,
            patch.dict(
                os.environ,
                {"OPERATION_MODE": "offline"},
                clear=False,
            ),
        ):
            temporary_root = Path(temporary)
            graph_path = temporary_root / "graph.json"
            graph = compile_s4_policy_graph(
                environments_dir=(
                    REPOSITORY_ROOT / "environment_files"
                ),
                s3_policy_graph_path=(
                    REPOSITORY_ROOT
                    / "analysis"
                    / "teacher"
                    / "S3_GLOBAL_IDENTITY_FREE_POLICY_GRAPH.json"
                ),
                requested_games=SMOKE_ENVIRONMENTS,
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
            report = run_s4_policy_graph(
                environments_dir=REPOSITORY_ROOT / "environment_files",
                policy_graph_path=graph_path,
                requested_games=SMOKE_ENVIRONMENTS,
                recordings_dir=temporary_root / "recordings",
            )

        self.assertTrue(report["all_complete"])
        self.assertEqual(report["environment_count"], 4)
        self.assertEqual(report["completed_levels"], 32)
        self.assertEqual(report["level_count"], 32)
        self.assertEqual(report["error_count"], 0)
        self.assertEqual(report["identity_routing_decision_count"], 0)
        self.assertEqual(report["source_hidden_decision_count"], 0)
        self.assertEqual(report["policy_partition_count"], 1)
        self.assertFalse(
            report["action_selection_receives_environment_identity"]
        )
        self.assertFalse(
            report["action_selection_receives_environment_wrapper"]
        )
        self.assertFalse(
            report["action_selection_receives_source_or_hidden_state"]
        )
        self.assertFalse(
            report["decision_uses_source_or_hidden_state"]
        )
        self.assertEqual(graph["policy_partition_count"], 1)
        self.assertEqual(graph["identity_routing_key_count"], 0)
        self.assertEqual(graph["source_hidden_decision_key_count"], 0)
        self.assertEqual(identity_literal_values(graph), set())
        self.assertEqual(
            all_mapping_keys(graph).intersection(
                {
                    "current_level_data",
                    "custom_hidden_state",
                    "environment_id",
                    "game_class",
                    "game_id",
                    "hidden_state",
                    "level_id",
                    "levels_completed",
                    "source_fields",
                    "source_state_digest",
                    "task_id",
                }
            ),
            set(),
        )


if __name__ == "__main__":
    unittest.main()
