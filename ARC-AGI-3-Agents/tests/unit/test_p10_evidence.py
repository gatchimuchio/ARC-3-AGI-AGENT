from __future__ import annotations

import copy
import hashlib
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
ITERATION_16_EVIDENCE = (
    REPOSITORY_ROOT
    / "evidence"
    / "p10"
    / "p_update"
    / "iteration_16_regression"
)
ITERATION_17_EVIDENCE = (
    REPOSITORY_ROOT
    / "evidence"
    / "p10"
    / "p_update"
    / "iteration_17_regression"
)
ITERATION_19_EVIDENCE = (
    REPOSITORY_ROOT
    / "evidence"
    / "p10"
    / "p_update"
    / "iteration_19_regression"
)
ITERATION_20_EVIDENCE = (
    REPOSITORY_ROOT
    / "evidence"
    / "p10"
    / "p_update"
    / "iteration_20_regression"
)
ITERATION_21_EVIDENCE = (
    REPOSITORY_ROOT
    / "evidence"
    / "p10"
    / "p_update"
    / "iteration_21_regression"
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
    def test_iteration_21_promotion_evidence_is_content_bound(self) -> None:
        trace = json.loads(
            (
                ITERATION_21_EVIDENCE
                / "p10_candidate_compile_trace_v1.json"
            ).read_text(encoding="utf-8")
        )
        claimed_trace_digest = trace.pop("content_digest")
        self.assertEqual(
            claimed_trace_digest,
            "p10-p-update-workflow:" + digest_object(trace),
        )
        runtime = trace["candidate_runtime_regression"]
        self.assertEqual(runtime["stable_active_value"], 29)
        self.assertEqual(runtime["stable_candidate_value"], 29)
        self.assertEqual(runtime["baseline_target_value"], 5.0)
        self.assertEqual(runtime["candidate_target_value"], 6.0)
        self.assertTrue(runtime["stable_non_regression"])
        self.assertTrue(runtime["target_improved"])
        self.assertTrue(runtime["reproducible"])
        self.assertEqual(trace["promotion_failures"], [])

        receipt = json.loads(
            (
                ITERATION_21_EVIDENCE
                / "p10_promotion_receipt_v1.json"
            ).read_text(encoding="utf-8")
        )
        claimed_receipt_digest = receipt.pop("content_digest")
        self.assertEqual(
            claimed_receipt_digest,
            "p10-promotion-evidence:" + digest_object(receipt),
        )
        self.assertEqual(receipt["hds_decision"]["status"], "PROMOTE")
        self.assertTrue(receipt["hds_decision"]["allow_p_promote"])
        self.assertEqual(receipt["promotion_failures"], [])
        self.assertEqual(
            receipt["after_active_manifest_digest"],
            "6b67437d771d2a31f4c93303dee858f5151120412c2b7cf3ce55061b987aa2e1",
        )

        active_path = (
            ITERATION_21_EVIDENCE
            / "p10_active_post_promotion_ka59.json"
        )
        self.assertEqual(
            hashlib.sha256(active_path.read_bytes()).hexdigest(),
            "c62255320609042e0aa59b5769132480388f51e44ec85ca48bc51922dc8bef3e",
        )
        active = json.loads(active_path.read_text(encoding="utf-8"))
        self.assertEqual(active["operation_mode"], "offline")
        self.assertEqual(active["instruction_lifecycle"], "active")
        self.assertEqual(active["completed_levels"], 6)
        self.assertEqual(active["total_levels"], 7)
        self.assertEqual(active["error_count"], 0)
        self.assertFalse(active["all_complete"])
        self.assertEqual(
            set(active["reports"][0]["instruction_body_versions"]),
            {"p10-hybrid-v26"},
        )

    def test_iteration_20_promotion_evidence_is_content_bound(self) -> None:
        trace = json.loads(
            (
                ITERATION_20_EVIDENCE
                / "p10_candidate_compile_trace_v1.json"
            ).read_text(encoding="utf-8")
        )
        claimed_trace_digest = trace.pop("content_digest")
        self.assertEqual(
            claimed_trace_digest,
            "p10-p-update-workflow:" + digest_object(trace),
        )
        runtime = trace["candidate_runtime_regression"]
        self.assertEqual(runtime["stable_active_value"], 29)
        self.assertEqual(runtime["stable_candidate_value"], 29)
        self.assertEqual(runtime["baseline_target_value"], 4.0)
        self.assertEqual(runtime["candidate_target_value"], 5.0)
        self.assertTrue(runtime["stable_non_regression"])
        self.assertTrue(runtime["target_improved"])
        self.assertTrue(runtime["reproducible"])
        self.assertEqual(trace["promotion_failures"], [])

        receipt = json.loads(
            (
                ITERATION_20_EVIDENCE
                / "p10_promotion_receipt_v1.json"
            ).read_text(encoding="utf-8")
        )
        claimed_receipt_digest = receipt.pop("content_digest")
        self.assertEqual(
            claimed_receipt_digest,
            "p10-promotion-evidence:" + digest_object(receipt),
        )
        self.assertEqual(receipt["hds_decision"]["status"], "PROMOTE")
        self.assertTrue(receipt["hds_decision"]["allow_p_promote"])
        self.assertEqual(receipt["promotion_failures"], [])
        self.assertEqual(
            receipt["after_active_manifest_digest"],
            "66ab43152ef7eb4512679ca4a683a3c4963a2bb8147daaa743fe70f9f9b5ceba",
        )

        active_path = (
            ITERATION_20_EVIDENCE
            / "p10_active_post_promotion_ka59.json"
        )
        self.assertEqual(
            hashlib.sha256(active_path.read_bytes()).hexdigest(),
            "0b7e4d9436d4aa930ef0eb09b75513ee07c046e396ad8d2af17da171bf4bbd92",
        )
        active = json.loads(active_path.read_text(encoding="utf-8"))
        self.assertEqual(active["operation_mode"], "offline")
        self.assertEqual(active["instruction_lifecycle"], "active")
        self.assertEqual(active["completed_levels"], 5)
        self.assertEqual(active["total_levels"], 7)
        self.assertEqual(active["error_count"], 0)
        self.assertFalse(active["all_complete"])
        self.assertEqual(
            set(active["reports"][0]["instruction_body_versions"]),
            {"p10-hybrid-v25"},
        )

    def test_iteration_19_promotion_evidence_is_content_bound(self) -> None:
        trace = json.loads(
            (
                ITERATION_19_EVIDENCE
                / "p10_candidate_compile_trace_v1.json"
            ).read_text(encoding="utf-8")
        )
        claimed_trace_digest = trace.pop("content_digest")
        self.assertEqual(
            claimed_trace_digest,
            "p10-p-update-workflow:" + digest_object(trace),
        )
        runtime = trace["candidate_runtime_regression"]
        self.assertEqual(runtime["stable_active_value"], 29)
        self.assertEqual(runtime["stable_candidate_value"], 29)
        self.assertEqual(runtime["baseline_target_value"], 3.0)
        self.assertEqual(runtime["candidate_target_value"], 4.0)
        self.assertTrue(runtime["stable_non_regression"])
        self.assertTrue(runtime["target_improved"])
        self.assertTrue(runtime["reproducible"])
        self.assertEqual(trace["promotion_failures"], [])

        receipt = json.loads(
            (
                ITERATION_19_EVIDENCE
                / "p10_promotion_receipt_v1.json"
            ).read_text(encoding="utf-8")
        )
        claimed_receipt_digest = receipt.pop("content_digest")
        self.assertEqual(
            claimed_receipt_digest,
            "p10-promotion-evidence:" + digest_object(receipt),
        )
        self.assertEqual(receipt["hds_decision"]["status"], "PROMOTE")
        self.assertTrue(receipt["hds_decision"]["allow_p_promote"])
        self.assertEqual(receipt["promotion_failures"], [])
        self.assertEqual(
            receipt["after_active_manifest_digest"],
            "ed005422ea68a7cc42bad99a10817ba7b6b7ab337bdb8993a750d781fba21c2c",
        )

        active_path = (
            ITERATION_19_EVIDENCE
            / "p10_active_post_promotion_ka59.json"
        )
        self.assertEqual(
            hashlib.sha256(active_path.read_bytes()).hexdigest(),
            "f232d7c660e87e120581c37a83422732e680fc429938c4964fe5b96e86e31dce",
        )
        active = json.loads(active_path.read_text(encoding="utf-8"))
        self.assertEqual(active["operation_mode"], "offline")
        self.assertEqual(active["instruction_lifecycle"], "active")
        self.assertEqual(active["completed_levels"], 4)
        self.assertEqual(active["total_levels"], 7)
        self.assertEqual(active["error_count"], 0)
        self.assertFalse(active["all_complete"])
        self.assertEqual(
            set(active["reports"][0]["instruction_body_versions"]),
            {"p10-hybrid-v24"},
        )

    def test_iteration_17_promotion_evidence_is_content_bound(self) -> None:
        trace = json.loads(
            (
                ITERATION_17_EVIDENCE
                / "p10_candidate_compile_trace_v1.json"
            ).read_text(encoding="utf-8")
        )
        claimed_trace_digest = trace.pop("content_digest")
        self.assertEqual(
            claimed_trace_digest,
            "p10-p-update-workflow:" + digest_object(trace),
        )
        runtime = trace["candidate_runtime_regression"]
        self.assertEqual(runtime["stable_active_value"], 29)
        self.assertEqual(runtime["stable_candidate_value"], 29)
        self.assertEqual(runtime["baseline_target_value"], 1.0)
        self.assertEqual(runtime["candidate_target_value"], 2.0)
        self.assertTrue(runtime["stable_non_regression"])
        self.assertTrue(runtime["target_improved"])
        self.assertTrue(runtime["reproducible"])
        self.assertEqual(trace["promotion_failures"], [])

        receipt = json.loads(
            (
                ITERATION_17_EVIDENCE
                / "p10_promotion_receipt_v1.json"
            ).read_text(encoding="utf-8")
        )
        claimed_receipt_digest = receipt.pop("content_digest")
        self.assertEqual(
            claimed_receipt_digest,
            "p10-promotion-evidence:" + digest_object(receipt),
        )
        self.assertEqual(receipt["hds_decision"]["status"], "PROMOTE")
        self.assertTrue(receipt["hds_decision"]["allow_p_promote"])
        self.assertEqual(receipt["promotion_failures"], [])
        self.assertEqual(
            receipt["after_active_manifest_digest"],
            "8db83a354c334811870bca13f72ea49b329dd35fb11fd77cb3cc92a07d400da3",
        )

        active_path = (
            ITERATION_17_EVIDENCE
            / "p10_active_post_promotion_ka59.json"
        )
        self.assertEqual(
            hashlib.sha256(active_path.read_bytes()).hexdigest(),
            "080ff6e7c90a1fd2a988c9a948c41e0082c5e08e8075f8224a7d40267e005332",
        )
        active = json.loads(active_path.read_text(encoding="utf-8"))
        self.assertEqual(active["operation_mode"], "offline")
        self.assertEqual(active["completed_levels"], 2)
        self.assertEqual(active["total_levels"], 7)
        self.assertEqual(active["error_count"], 0)
        self.assertFalse(active["all_complete"])

    def test_iteration_16_promotion_evidence_is_content_bound(self) -> None:
        trace = json.loads(
            (
                ITERATION_16_EVIDENCE
                / "p10_candidate_compile_trace_v1.json"
            ).read_text(encoding="utf-8")
        )
        claimed_trace_digest = trace.pop("content_digest")
        self.assertEqual(
            claimed_trace_digest,
            "p10-p-update-workflow:" + digest_object(trace),
        )
        runtime = trace["candidate_runtime_regression"]
        self.assertEqual(runtime["stable_active_value"], 29)
        self.assertEqual(runtime["stable_candidate_value"], 29)
        self.assertEqual(runtime["baseline_target_value"], 0.0)
        self.assertEqual(runtime["candidate_target_value"], 1.0)
        self.assertTrue(runtime["stable_non_regression"])
        self.assertTrue(runtime["target_improved"])
        self.assertTrue(runtime["reproducible"])
        self.assertEqual(trace["promotion_failures"], [])

        receipt = json.loads(
            (
                ITERATION_16_EVIDENCE
                / "p10_promotion_receipt_v1.json"
            ).read_text(encoding="utf-8")
        )
        claimed_receipt_digest = receipt.pop("content_digest")
        self.assertEqual(
            claimed_receipt_digest,
            "p10-promotion-evidence:" + digest_object(receipt),
        )
        self.assertEqual(receipt["hds_decision"]["status"], "PROMOTE")
        self.assertTrue(receipt["hds_decision"]["allow_p_promote"])
        self.assertEqual(receipt["promotion_failures"], [])
        self.assertEqual(
            receipt["after_active_manifest_digest"],
            "4e19e461a7f0d65573782be5e2bddc873ba62d5bfe76ef2f1e42293ac2dd32cc",
        )

        active_path = (
            ITERATION_16_EVIDENCE
            / "p10_active_post_promotion_ka59.json"
        )
        self.assertEqual(
            hashlib.sha256(active_path.read_bytes()).hexdigest(),
            "a5028b3aef42edcaf92720430075087dbd64c79c483c8a896c4ee7de0eab3325",
        )
        active = json.loads(active_path.read_text(encoding="utf-8"))
        self.assertEqual(active["operation_mode"], "offline")
        self.assertEqual(active["completed_levels"], 1)
        self.assertEqual(active["total_levels"], 7)
        self.assertEqual(active["error_count"], 0)
        self.assertFalse(active["all_complete"])

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
