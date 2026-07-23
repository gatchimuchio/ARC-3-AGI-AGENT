from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from typing import cast

from arc3_agi_agent.p10_evidence import (
    P10_COMPACT_EVIDENCE_SCHEMA_VERSION,
    P10_COMPACT_RUN_EVIDENCE_SCHEMA_VERSION,
    P10_EVIDENCE_SCHEMA_VERSION,
    build_p10_compact_run_evidence,
    build_p10_compact_variant_evidence,
    build_p10_variant_evidence,
    compact_p10_run,
    stable_p10_run,
)
from arc3_agi_agent.schema import digest_object

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
FT09_EVIDENCE = (
    REPOSITORY_ROOT / "evidence" / "p10" / "ft09_variant_comparison.json"
)
ACTIVE_COMPACT_EVIDENCE = {
    "ft09_hybrid_active_compact.json": (6, 75),
    "lp85_hybrid_compact.json": (8, 235),
    "tr87_hybrid_compact.json": (6, 308),
}


def run(variant: str, completed: int) -> dict[str, object]:
    complete = completed == 1
    return {
        "phase": "P10",
        "operation_mode": "offline",
        "environment_count": 1,
        "completed_count": 1,
        "complete_game_count": int(complete),
        "completed_levels": completed,
        "total_levels": 1,
        "all_complete": complete,
        "error_count": 0,
        "max_actions": 16,
        "instruction_variant": variant,
        "reports": [
            {
                "game_id": "evidence-only-sample",
                "actions": 3 if complete else 16,
                "recoveries": 0,
                "search_resets": 0,
                "levels_completed": completed,
                "win_levels": 1,
                "terminal_state": "WIN" if complete else "NOT_FINISHED",
                "final_status": "STOP" if complete else "MAX_ACTION_STOP",
                "complete": complete,
                "max_action_exhausted": not complete,
                "memory_version": 4,
                "memory_influenced_cycle_count": 2,
                "visual_operator_version": "test-operator-v1",
                "instruction_body_formats": ["test-format"],
                "instruction_body_versions": [f"test-{variant}"],
                "instruction_body_digests": ["instruction-digest"],
                "instruction_query_digests": ["query-digest"],
                "decision_statuses": ["EMIT"],
                "verification_statuses": ["PASS"],
                "emitted_steps": [[{"action": 1}]],
                "emitted_provenance": [["unit-test"]],
                "emitted_level_counts": [completed],
                "trace_digests": ["trace-digest"],
                "trace_events": [[{"stage": "COMPUTE"}]],
                "rollback_decision_ids": [],
                "rollback_memory_versions": [],
                "failure_payload_digests": [],
                "search_reset_decision_ids": [],
                "search_reset_memory_versions": [],
                "search_reset_payload_digests": [],
                "search_reset_evidence_signatures": [],
            }
        ],
        "errors": [],
        "local_scorecard": {
            "scorecard_id": "nondeterministic-local-id",
        },
    }


class P10EvidenceTests(unittest.TestCase):
    def test_checked_in_ft09_evidence_is_content_bound(self) -> None:
        evidence = json.loads(FT09_EVIDENCE.read_text(encoding="utf-8"))
        claimed_digest = evidence.pop("content_digest")

        self.assertEqual(claimed_digest, digest_object(evidence))
        summaries = evidence["variant_summaries"]
        self.assertEqual(summaries["P-A"]["completed_levels"], 6)
        self.assertEqual(summaries["P-B"]["completed_levels"], 0)
        self.assertEqual(summaries["hybrid"]["completed_levels"], 6)
        self.assertEqual(
            {
                variant: summary["error_count"]
                for variant, summary in summaries.items()
            },
            {"P-A": 0, "P-B": 0, "hybrid": 0},
        )

    def test_stable_projection_removes_only_local_scorecard(self) -> None:
        source = run("hybrid", 1)
        stable = stable_p10_run(source)

        self.assertNotIn("local_scorecard", stable)
        self.assertEqual(
            stable["reports"],
            source["reports"],
        )

    def test_checked_in_active_compact_evidence_is_bound(self) -> None:
        for filename, (levels, actions) in (
            ACTIVE_COMPACT_EVIDENCE.items()
        ):
            with self.subTest(filename=filename):
                path = REPOSITORY_ROOT / "evidence" / "p10" / filename
                evidence = json.loads(path.read_text(encoding="utf-8"))
                claimed_digest = evidence.pop("content_digest")
                self.assertEqual(claimed_digest, digest_object(evidence))
                self.assertEqual(
                    evidence["schema_version"],
                    P10_COMPACT_RUN_EVIDENCE_SCHEMA_VERSION,
                )
                summary = evidence["summary"]
                self.assertEqual(summary["completed_levels"], levels)
                self.assertEqual(summary["action_count"], actions)
                self.assertTrue(summary["all_complete"])
                self.assertEqual(summary["error_count"], 0)
                self.assertEqual(
                    summary["max_action_exhausted_count"],
                    0,
                )
                report = evidence["compact_run"]["reports"][0]
                self.assertEqual(report["trace_cycle_count"], actions)
                self.assertEqual(len(report["trace_digests"]), actions)
                self.assertEqual(report["recoveries"], 0)
                self.assertEqual(report["search_resets"], 0)

    def test_three_variant_evidence_is_deterministic_and_bound(self) -> None:
        runs = {
            "P-A": run("P-A", 1),
            "P-B": run("P-B", 0),
            "hybrid": run("hybrid", 1),
        }
        first = build_p10_variant_evidence(runs)
        altered = copy.deepcopy(runs)
        altered["hybrid"]["local_scorecard"] = {"scorecard_id": "other"}
        second = build_p10_variant_evidence(altered)

        self.assertEqual(first, second)
        self.assertEqual(
            first["schema_version"],
            P10_EVIDENCE_SCHEMA_VERSION,
        )
        content_digest = first.pop("content_digest")
        self.assertEqual(content_digest, digest_object(first))
        summaries = cast(
            dict[str, dict[str, object]],
            first["variant_summaries"],
        )
        self.assertEqual(
            summaries["P-B"]["completed_levels"],
            0,
        )

    def test_compact_projection_binds_omitted_trace_events(self) -> None:
        source = run("hybrid", 1)
        compact = compact_p10_run(source)
        compact_reports = cast(
            list[dict[str, object]],
            compact["reports"],
        )
        compact_report = compact_reports[0]
        source_reports = cast(
            list[dict[str, object]],
            source["reports"],
        )

        self.assertNotIn("trace_events", compact_report)
        self.assertEqual(compact_report["trace_cycle_count"], 1)
        self.assertEqual(
            compact_report["trace_events_digest"],
            digest_object(source_reports[0]["trace_events"]),
        )
        self.assertEqual(
            compact_report["emitted_steps"],
            [[{"action": 1}]],
        )

    def test_compact_variant_evidence_is_content_bound(self) -> None:
        evidence = build_p10_compact_variant_evidence(
            {
                "P-A": run("P-A", 1),
                "P-B": run("P-B", 0),
                "hybrid": run("hybrid", 1),
            }
        )

        self.assertEqual(
            evidence["schema_version"],
            P10_COMPACT_EVIDENCE_SCHEMA_VERSION,
        )
        claimed_digest = evidence.pop("content_digest")
        self.assertEqual(claimed_digest, digest_object(evidence))
        summaries = cast(
            dict[str, dict[str, object]],
            evidence["variant_summaries"],
        )
        self.assertEqual(
            summaries["P-B"]["completed_levels"],
            0,
        )

    def test_compact_single_run_evidence_is_content_bound(self) -> None:
        evidence = build_p10_compact_run_evidence(run("hybrid", 1))

        self.assertEqual(
            evidence["schema_version"],
            P10_COMPACT_RUN_EVIDENCE_SCHEMA_VERSION,
        )
        claimed_digest = evidence.pop("content_digest")
        self.assertEqual(claimed_digest, digest_object(evidence))
        summary = cast(dict[str, object], evidence["summary"])
        self.assertEqual(summary["completed_levels"], 1)
        self.assertEqual(summary["action_count"], 3)

    def test_mismatched_conditions_are_rejected(self) -> None:
        runs = {
            "P-A": run("P-A", 1),
            "P-B": run("P-B", 0),
            "hybrid": run("hybrid", 1),
        }
        runs["P-B"]["max_actions"] = 17

        with self.assertRaisesRegex(
            ValueError,
            "P10_VARIANT_CONDITIONS_DIFFER",
        ):
            build_p10_variant_evidence(runs)


if __name__ == "__main__":
    unittest.main()
