from __future__ import annotations

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from arc3_agi_agent.teacher.s3_graph_compiler import (
    compile_s3_policy_graph,
)
from arc3_agi_agent.teacher.s3_graph_executor import (
    run_s3_policy_graph,
)
from arc3_agi_agent.teacher.s3_graph_schema import (
    all_mapping_keys,
    identity_literal_values,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SMOKE_ENVIRONMENTS = (
    "bp35-0a0ad940",
    "ft09-0d8bbf25",
    "lf52-271a04aa",
)


class TeacherS3GraphIntegrationTests(unittest.TestCase):
    def test_global_graph_closes_without_identity_routing(self) -> None:
        with (
            tempfile.TemporaryDirectory(
                prefix="arc3-teacher-s3-"
            ) as temporary,
            patch.dict(
                os.environ,
                {"OPERATION_MODE": "offline"},
                clear=False,
            ),
        ):
            temporary_root = Path(temporary)
            graph_path = temporary_root / "graph.json"
            graph = compile_s3_policy_graph(
                environments_dir=REPOSITORY_ROOT / "environment_files",
                s2_policy_graph_path=(
                    REPOSITORY_ROOT
                    / "analysis"
                    / "teacher"
                    / "S2_ROLE_RELATIVE_POLICY_GRAPH.json"
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
            report = run_s3_policy_graph(
                environments_dir=REPOSITORY_ROOT / "environment_files",
                policy_graph_path=graph_path,
                requested_games=SMOKE_ENVIRONMENTS,
                recordings_dir=temporary_root / "execute-recordings",
            )

        self.assertTrue(report["all_complete"])
        self.assertEqual(report["environment_count"], 3)
        self.assertEqual(report["completed_levels"], 25)
        self.assertEqual(report["level_count"], 25)
        self.assertEqual(report["error_count"], 0)
        self.assertEqual(report["identity_routing_decision_count"], 0)
        self.assertEqual(report["policy_partition_count"], 1)
        self.assertFalse(
            report["action_selection_receives_environment_identity"]
        )
        self.assertFalse(
            report["decision_uses_task_game_level_identity"]
        )
        self.assertFalse(report["decision_uses_level_progress_counter"])
        self.assertFalse(
            report["decision_uses_per_game_graph_partition"]
        )
        self.assertEqual(graph["policy_partition_count"], 1)
        self.assertEqual(graph["identity_routing_key_count"], 0)
        self.assertEqual(identity_literal_values(graph), set())
        self.assertEqual(
            all_mapping_keys(graph).intersection(
                {
                    "environment_id",
                    "game_class",
                    "game_id",
                    "games",
                    "level_id",
                    "levels_completed",
                    "target_levels",
                    "task_id",
                }
            ),
            set(),
        )


if __name__ == "__main__":
    unittest.main()
