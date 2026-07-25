from __future__ import annotations

import copy
import unittest

from arc3_agi_agent.schema import digest_object
from p10_runtime_retention_audit import build_runtime_retention_audit


def _report(*, probe_format: str) -> dict[str, object]:
    return {
        "phase": "P10",
        "operation_mode": "offline",
        "environment_count": 1,
        "completed_count": 1,
        "complete_game_count": 0,
        "completed_levels": 0,
        "total_levels": 8,
        "all_complete": False,
        "error_count": 0,
        "max_actions": 450,
        "instruction_variant": "hybrid",
        "reports": [
            {
                "game_id": "external-worker-identity",
                "actions": 450,
                "levels_completed": 0,
                "win_levels": 8,
                "emitted_steps": [[{"action_id": 1}]],
                "decision_statuses": ["ACCEPT"],
                "verification_statuses": ["PASS"],
                "trace_events": [[{"event": "closed"}]],
                "development_transition_probe": {
                    "format": probe_format,
                    "action_selection_influence": False,
                },
            }
        ],
        "errors": [],
    }


class P10RuntimeRetentionAuditTests(unittest.TestCase):
    def test_shadow_probe_change_is_excluded_but_agent_behavior_is_bound(
        self,
    ) -> None:
        baseline = _report(probe_format="v1")
        fresh = _report(probe_format="v2")

        audit = build_runtime_retention_audit(
            baseline_report=baseline,
            fresh_report=fresh,
            baseline_report_descriptor={"path": "baseline"},
            fresh_report_descriptor={"path": "fresh"},
            baseline_timing={"maximum_rss_kb": 1_666_868},
            fresh_timing={
                "maximum_rss_kb": 109_920,
                "swaps": 0,
            },
        )

        self.assertTrue(all(audit["checks"].values()))
        judgment = audit["hds_judgment"]
        self.assertEqual(judgment["resource_headroom_status"], "PASS")
        self.assertEqual(
            judgment["failure_signature_status"],
            "RESOLVED",
        )
        self.assertEqual(
            audit["baseline"]["behavior_projection_digest"],
            audit["fresh"]["behavior_projection_digest"],
        )
        body = copy.deepcopy(audit)
        claimed = body.pop("content_digest")
        self.assertEqual(
            claimed,
            "arc3_p10_runtime_retention_audit:" + digest_object(body),
        )

    def test_agent_behavior_drift_fails_closed(self) -> None:
        baseline = _report(probe_format="v1")
        fresh = _report(probe_format="v2")
        reports = fresh["reports"]
        assert isinstance(reports, list)
        reports[0]["actions"] = 449

        with self.assertRaisesRegex(
            ValueError,
            "agent_behavior_projection_equal",
        ):
            build_runtime_retention_audit(
                baseline_report=baseline,
                fresh_report=fresh,
                baseline_report_descriptor={"path": "baseline"},
                fresh_report_descriptor={"path": "fresh"},
                baseline_timing={"maximum_rss_kb": 1_666_868},
                fresh_timing={
                    "maximum_rss_kb": 109_920,
                    "swaps": 0,
                },
            )


if __name__ == "__main__":
    unittest.main()
