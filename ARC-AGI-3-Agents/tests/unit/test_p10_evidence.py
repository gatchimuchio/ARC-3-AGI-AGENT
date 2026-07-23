from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path

from arc3_agi_agent.p10_evidence import (
    P10_EVIDENCE_SCHEMA_VERSION,
    build_p10_variant_evidence,
    stable_p10_run,
)
from arc3_agi_agent.schema import digest_object

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
FT09_EVIDENCE = (
    REPOSITORY_ROOT / "evidence" / "p10" / "ft09_variant_comparison.json"
)


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
                "max_action_exhausted": not complete,
                "trace_events": [[{"stage": "COMPUTE"}]],
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
        self.assertEqual(
            first["variant_summaries"]["P-B"]["completed_levels"],
            0,
        )

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
