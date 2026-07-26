from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from arc_agi import Arcade, OperationMode
from arc_agi.local_wrapper import LocalEnvironmentWrapper

from arc3_agi_agent.s5_policy import load_s5_rendered_policy_body
from arc3_agi_agent.s5_runner import execute_s5_rendered_policy
from arc3_agi_agent.schema import digest_object

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]


class S5RenderedRuntimeIntegrationTests(unittest.TestCase):
    def test_rendered_runtime_closes_reset_and_failure_sample(self) -> None:
        with tempfile.TemporaryDirectory(prefix="arc3-s5-runtime-") as temp:
            arcade = Arcade(
                operation_mode=OperationMode.OFFLINE,
                environments_dir=str(
                    REPOSITORY_ROOT / "environment_files"
                ),
                recordings_dir=temp,
            )
            scorecard = arcade.open_scorecard(
                tags=["s5-rendered-runtime-integration"]
            )
            full_trace: list[dict[str, object]] = []
            try:
                environment = arcade.make(
                    "bp35-0a0ad940",
                    scorecard_id=scorecard,
                    save_recording=False,
                    include_frame_data=True,
                )
                self.assertIsInstance(
                    environment,
                    LocalEnvironmentWrapper,
                )
                report = execute_s5_rendered_policy(
                    environment=environment,
                    instruction_body=load_s5_rendered_policy_body(),
                    max_actions=4096,
                    trace_sink=full_trace.append,
                )
            finally:
                arcade.close_scorecard(scorecard)

        self.assertTrue(report["complete"])
        self.assertEqual(report["final_state"], "WIN")
        self.assertEqual(report["completed_levels"], 9)
        self.assertEqual(report["actions_executed"], 524)
        self.assertEqual(
            report["hds_compute_command_count"],
            report["actions_executed"],
        )
        self.assertGreater(report["policy_reset_count"], 0)
        self.assertGreater(report["game_over_observation_count"], 0)
        self.assertGreater(report["outcome_retention_count"], 0)
        self.assertGreater(
            report["memory_influenced_decision_count"],
            0,
        )
        self.assertEqual(len(full_trace), report["actions_executed"])
        self.assertEqual(
            digest_object(
                [
                    {
                        key: event[key]
                        for key in (
                            "action_id",
                            "after_state",
                            "authority_decision_id",
                            "before_state",
                            "hds_status",
                            "instruction_query_digest",
                            "levels_completed",
                            "memory_version",
                            "outcome_retained",
                            "policy_reset",
                            "trace_digest",
                        )
                    }
                    for event in full_trace
                ]
            ),
            report["runtime_trace_digest"],
        )
        self.assertTrue(
            all(event["kernel_trace"] for event in full_trace)
        )
        self.assertTrue(
            any(
                event["follow_up_authority_decision"]
                for event in full_trace
            )
        )


if __name__ == "__main__":
    unittest.main()
