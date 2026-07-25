from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from arc3_agi_agent.development_analysis import (
    COVERAGE_FILENAME,
    LEDGER_FILENAME,
    QUEUE_FILENAME,
    RECONCILIATION_FILENAME,
    REQUIRED_LEDGER_FIELDS,
    LegacySourceDriftError,
    _current_game_index,
    _verified_analysis_source_descriptors,
    _verified_legacy_json,
)
from arc3_agi_agent.schema import digest_object


class P10DevelopmentAnalysisTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repository_root = Path(__file__).resolve().parents[3]
        cls.analysis_root = (
            cls.repository_root / "analysis" / "development"
        )
        cls.artifacts = {
            filename: json.loads(
                (cls.analysis_root / filename).read_text(encoding="utf-8")
            )
            for filename in (
                LEDGER_FILENAME,
                RECONCILIATION_FILENAME,
                COVERAGE_FILENAME,
                QUEUE_FILENAME,
            )
        }

    def test_all_artifacts_are_canonical_content_bound_and_runtime_forbidden(
        self,
    ) -> None:
        for filename, artifact in self.artifacts.items():
            self.assertTrue(artifact["development_only"], filename)
            self.assertEqual(artifact["runtime_use"], "FORBIDDEN", filename)
            body = copy.deepcopy(artifact)
            claimed = body.pop("content_digest")
            self.assertEqual(
                claimed,
                f"{body['artifact_type']}:{digest_object(body)}",
                filename,
            )
            canonical = (
                json.dumps(
                    artifact,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                + "\n"
            )
            self.assertEqual(
                (self.analysis_root / filename).read_text(encoding="utf-8"),
                canonical,
                filename,
            )

    def test_legacy_ledger_freezes_705_sources_and_all_183_levels(
        self,
    ) -> None:
        ledger = self.artifacts[LEDGER_FILENAME]
        snapshot = ledger["source_snapshot"]
        self.assertEqual(snapshot["analysis_source_count"], 705)
        self.assertEqual(len(snapshot["sources"]), 705)
        self.assertEqual(
            snapshot["source_inventory_digest"],
            "7f3afe283d53d6cc6d1486bdd5ef407cb2fb193d41cabd155c09189bca9192a7",
        )
        rows = ledger["rows"]
        self.assertEqual(len(rows), 183)
        self.assertEqual(
            len({(row["game_id"], row["level"]) for row in rows}),
            183,
        )
        self.assertEqual(len({row["game_id"] for row in rows}), 25)
        for row in rows:
            self.assertFalse(
                set(REQUIRED_LEDGER_FIELDS) - set(row),
                (row["game_id"], row["level"]),
            )
        self.assertEqual(
            ledger["summary"]["frontier_counts"],
            {
                "BLOCKED": 86,
                "CLOSED_LEGACY": 76,
                "CURRENT_FRONTIER": 21,
            },
        )
        self.assertFalse(ledger["field_policy"]["file_wide_quarantine"])
        self.assertIn(
            "only when COMPOSABLE",
            ledger["field_policy"]["runtime_subtraction_boundary"],
        )

    def test_reconciliation_is_conservative_and_preserves_35_boundary(
        self,
    ) -> None:
        reconciliation = self.artifacts[RECONCILIATION_FILENAME]
        self.assertEqual(
            reconciliation["summary"],
            {
                "current_completed_levels": 35,
                "current_game_count": 5,
                "status_counts": {
                    "CONFIRMED": 26,
                    "CONTRADICTED": 0,
                    "PARTIALLY_CONFIRMED": 1,
                    "STALE": 9,
                    "UNOBSERVED": 147,
                },
                "total_levels": 183,
            },
        )
        self.assertEqual(
            reconciliation["hds_judgment"]["status"],
            "HOLD",
        )
        self.assertFalse(
            reconciliation["hds_judgment"][
                "runtime_p_promotion_authorized"
            ]
        )

    def test_capability_coverage_and_priority_are_exact(self) -> None:
        coverage = self.artifacts[COVERAGE_FILENAME]
        expected = {
            "C2_visible_effect_transition_model": (21, 86),
            "C3_commit_boundary_predictor": (19, 78),
            "C10_phase_timer_unlock_model": (9, 35),
            "C7_target_contact_boundary_verifier": (7, 31),
            "C12_layout_mode_commit_discriminator": (5, 24),
            "C14_symbolic_relation_commit_model": (3, 12),
            "C8_helper_handoff_state_model": (3, 11),
            "C4_hazard_rollback_verifier": (3, 10),
            "C1_rendered_affordance_objectizer": (2, 15),
            "C6_action_channel_emitter_model": (2, 8),
            "C5_stale_settle_frame_controller": (2, 6),
            "C9_token_slot_submission_verifier": (2, 6),
            "C11_route_terminal_reachability_verifier": (2, 5),
            "C13_support_bridge_slider_model": (1, 3),
        }
        actual = {
            row["capability_id"]: (
                row["frontier_count"],
                row["blocked_inherited_level_count"],
            )
            for row in coverage["rows"]
        }
        self.assertEqual(actual, expected)
        self.assertEqual(
            coverage["summary"]["top_priority_capabilities"],
            [
                "C2_visible_effect_transition_model",
                "C3_commit_boundary_predictor",
                "C10_phase_timer_unlock_model",
            ],
        )
        status_by_capability = {
            row["capability_id"]: row["current_implementation_status"]
            for row in coverage["rows"]
        }
        self.assertEqual(
            status_by_capability[
                "C12_layout_mode_commit_discriminator"
            ],
            "LOCAL_PROBE_CLOSED_NEGATIVE_NEGATIVE_ONLY",
        )
        self.assertEqual(
            status_by_capability[
                "C1_rendered_affordance_objectizer"
            ],
            "LOCAL_PROBE_CLOSED_NEGATIVE_NEGATIVE_ONLY",
        )
        for capability_id in (
            "C14_symbolic_relation_commit_model",
            "C8_helper_handoff_state_model",
            "C4_hazard_rollback_verifier",
            "C6_action_channel_emitter_model",
            "C9_token_slot_submission_verifier",
            "C11_route_terminal_reachability_verifier",
            "C13_support_bridge_slider_model",
        ):
            with self.subTest(capability_status=capability_id):
                self.assertEqual(
                    status_by_capability[capability_id],
                    "LOCAL_PROBE_CLOSED_NEGATIVE_NEGATIVE_ONLY",
                )

    def test_queue_starts_with_cross_cutting_c2_c3_not_level_operator(
        self,
    ) -> None:
        queue = self.artifacts[QUEUE_FILENAME]
        first = queue["queue"][0]
        self.assertEqual(
            first["capability_ids"],
            [
                "C2_visible_effect_transition_model",
                "C3_commit_boundary_predictor",
            ],
        )
        self.assertEqual(first["coverage"]["c2_link_count"], 107)
        self.assertEqual(first["coverage"]["c3_link_count"], 97)
        self.assertEqual(first["coverage"]["overlap_count"], 97)
        self.assertEqual(first["coverage"]["union_level_count"], 107)
        self.assertEqual(
            first["candidate_tiers"],
            ["LOCAL_PROBE", "CLUSTER_STABLE", "COMPOSABLE"],
        )
        self.assertEqual(first["current_tier"], "LOCAL_PROBE")
        self.assertEqual(
            first["implementation_evidence"]["capability_tiers"],
            {
                "C2_visible_effect_transition_model": "CLUSTER_STABLE",
                "C3_commit_boundary_predictor": "LOCAL_PROBE",
            },
        )
        self.assertEqual(
            queue["queue"][1]["capability_ids"],
            ["C10_phase_timer_unlock_model"],
        )
        self.assertEqual(queue["queue"][1]["current_tier"], "COMPOSABLE")
        self.assertEqual(
            queue["queue"][1]["implementation_evidence"][
                "candidate_intervention_status"
            ],
            "REJECT",
        )
        self.assertEqual(
            queue["queue"][1]["implementation_evidence"][
                "candidate_target_completion_delta"
            ],
            0,
        )
        self.assertFalse(
            queue["queue"][1]["implementation_evidence"][
                "active_manifest_changed"
            ]
        )
        c7 = queue["queue"][2]
        self.assertEqual(
            c7["capability_ids"],
            ["C7_target_contact_boundary_verifier"],
        )
        self.assertEqual(c7["current_tier"], "LOCAL_PROBE")
        self.assertEqual(c7["work_status"], "CLOSED_NEGATIVE")
        self.assertEqual(
            c7["implementation_evidence"]["total_probe_count"],
            288,
        )
        self.assertEqual(
            c7["implementation_evidence"][
                "progress_separator_variable_count"
            ],
            0,
        )
        self.assertFalse(
            c7["implementation_evidence"][
                "same_surface_retry_authorized"
            ]
        )
        c12 = queue["queue"][3]
        self.assertEqual(
            c12["capability_ids"],
            ["C12_layout_mode_commit_discriminator"],
        )
        self.assertEqual(c12["current_tier"], "LOCAL_PROBE")
        self.assertEqual(c12["work_status"], "CLOSED_NEGATIVE")
        self.assertEqual(
            c12["implementation_evidence"]["combined_probe_count"],
            388,
        )
        self.assertEqual(
            c12["implementation_evidence"]["combined_progress_count"],
            0,
        )
        self.assertFalse(
            c12["implementation_evidence"][
                "same_surface_retry_authorized"
            ]
        )
        c1 = queue["queue"][4]
        self.assertEqual(
            c1["capability_ids"],
            ["C1_rendered_affordance_objectizer"],
        )
        self.assertEqual(c1["current_tier"], "LOCAL_PROBE")
        self.assertEqual(c1["work_status"], "CLOSED_NEGATIVE")
        self.assertEqual(
            c1["implementation_evidence"]["total_probe_count"],
            1768,
        )
        self.assertEqual(
            c1["implementation_evidence"][
                "non_prefix_progress_count"
            ],
            0,
        )
        self.assertTrue(
            c1["implementation_evidence"][
                "task_aware_prefix_progress_quarantined"
            ]
        )
        self.assertFalse(
            c1["implementation_evidence"][
                "same_surface_retry_authorized"
            ]
        )
        c5 = next(
            item
            for item in queue["queue"]
            if item["capability_ids"]
            == ["C5_stale_settle_frame_controller"]
        )
        self.assertEqual(c5["current_tier"], "LOCAL_PROBE")
        self.assertEqual(
            c5["work_status"],
            "LOCAL_AXIS_CLOSED_NEGATIVE",
        )
        self.assertEqual(
            c5["implementation_evidence"][
                "bounded_old_action_replay_count"
            ],
            8,
        )
        newly_closed = {
            "C14_symbolic_relation_commit_model": (252, 180, 0),
            "C8_helper_handoff_state_model": (203, 131, 0),
            "C4_hazard_rollback_verifier": (77, 77, 0),
            "C6_action_channel_emitter_model": (20, 20, 0),
            "C9_token_slot_submission_verifier": (154, 61, 0),
            "C11_route_terminal_reachability_verifier": (96, 0, 5),
            "C13_support_bridge_slider_model": (1397, 96, 0),
        }
        for capability_id, expected in newly_closed.items():
            with self.subTest(capability=capability_id):
                item = next(
                    row
                    for row in queue["queue"]
                    if row["capability_ids"] == [capability_id]
                )
                evidence = item["implementation_evidence"]
                self.assertEqual(item["current_tier"], "LOCAL_PROBE")
                self.assertEqual(
                    item["work_status"],
                    "LOCAL_PROBE_CLOSED_NEGATIVE_NEGATIVE_ONLY",
                )
                self.assertEqual(
                    (
                        evidence["total_probe_count"],
                        evidence["changed_probe_count"],
                        evidence["total_game_over_count"],
                    ),
                    expected,
                )
                self.assertEqual(evidence["total_progress_count"], 0)
                self.assertFalse(
                    evidence["same_surface_retry_authorized"]
                )
                self.assertFalse(
                    evidence["runtime_p_promotion_authorized"]
                )
        c11 = next(
            row
            for row in queue["queue"]
            if row["capability_ids"]
            == ["C11_route_terminal_reachability_verifier"]
        )
        self.assertTrue(
            c11["implementation_evidence"][
                "raw_game_over_is_not_reusable_separator"
            ]
        )
        self.assertTrue(
            all(
                not item["dedicated_level_operator_allowed"]
                for item in queue["queue"]
            )
        )
        composition = queue["composition_tests"][0]
        self.assertEqual(
            composition["test_id"],
            "COMPOSE-KA59-REMAINING-BOUNDARY",
        )
        self.assertFalse(composition["new_dedicated_operator_allowed"])
        self.assertEqual(
            composition["current_status"],
            "CLOSED_NEGATIVE_AXIS",
        )
        self.assertFalse(composition["same_axis_retry_authorized"])
        self.assertEqual(
            queue["hds_gate"]["next_work_block_id"],
            "WB-PROSPECTIVE-OBLIGATION-RELATION-COMPILER",
        )
        self.assertIn(
            "WB-C12_layout_mode_commit_discriminator",
            queue["hds_gate"]["closed_negative_work_blocks"],
        )
        self.assertIn(
            "WB-C1_rendered_affordance_objectizer",
            queue["hds_gate"]["closed_negative_work_blocks"],
        )
        self.assertIn(
            "WB-C13_support_bridge_slider_model",
            queue["hds_gate"]["closed_negative_work_blocks"],
        )

    def test_runtime_modules_do_not_import_development_analysis_artifacts(
        self,
    ) -> None:
        package_root = (
            self.repository_root
            / "ARC-AGI-3-Agents"
            / "arc3_agi_agent"
        )
        forbidden = (
            "analysis/development",
            LEDGER_FILENAME,
            RECONCILIATION_FILENAME,
            COVERAGE_FILENAME,
            QUEUE_FILENAME,
        )
        leaks: list[str] = []
        for path in package_root.rglob("*.py"):
            if path.name == "development_analysis.py":
                continue
            text = path.read_text(encoding="utf-8")
            if any(token in text for token in forbidden):
                leaks.append(path.relative_to(package_root).as_posix())
        self.assertEqual(leaks, [])

    def test_legacy_source_digest_drift_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            relative = "analysis/source.json"
            source = root / relative
            source.parent.mkdir(parents=True)
            source.write_text('{"value": 1}\n', encoding="utf-8")
            actual = hashlib.sha256(source.read_bytes()).hexdigest()
            value = _verified_legacy_json(
                legacy_repository_root=root,
                relative_path=relative,
                source_index={
                    relative: {
                        "sha256": actual,
                    }
                },
            )
            self.assertEqual(value, {"value": 1})
            source.write_text('{"value": 2}\n', encoding="utf-8")
            with self.assertRaisesRegex(
                LegacySourceDriftError,
                "LEGACY_SOURCE_DIGEST_DRIFT",
            ):
                _verified_legacy_json(
                    legacy_repository_root=root,
                    relative_path=relative,
                    source_index={
                        relative: {
                            "sha256": actual,
                        }
                    },
                )

    def test_explicit_candidate_report_is_not_current_active_evidence(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            report_path = root / "candidate.json"
            report_path.write_text(
                json.dumps(
                    {
                        "operation_mode": "offline",
                        "instruction_lifecycle": "candidate",
                        "environment_count": 1,
                        "error_count": 0,
                        "reports": [
                            {
                                "game_id": "g00-sample",
                                "levels_completed": 0,
                                "win_levels": 1,
                                "complete": False,
                                "max_action_exhausted": False,
                            }
                        ],
                    }
                )
                + "\n",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(
                ValueError,
                "CURRENT_REPORT_NOT_ACTIVE",
            ):
                _current_game_index(root, ("candidate.json",))

    def test_all_705_analysis_sources_are_verified_not_only_listed(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source_index: dict[str, dict[str, object]] = {}
            for index in range(705):
                relative = f"analysis/source-{index:03d}.json"
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                encoded = f'{{"index": {index}}}\n'.encode()
                path.write_bytes(encoded)
                source_index[relative] = {
                    "path": relative,
                    "kind": "analysis",
                    "bytes": len(encoded),
                    "sha256": hashlib.sha256(encoded).hexdigest(),
                    "parse_status": "PARSED",
                    "extraction_status": "MATERIALIZED",
                }

            descriptors = _verified_analysis_source_descriptors(
                legacy_repository_root=root,
                source_index=source_index,
            )
            self.assertEqual(len(descriptors), 705)

            first = root / "analysis/source-000.json"
            first.write_text('{"index": 9999}\n', encoding="utf-8")
            with self.assertRaisesRegex(
                LegacySourceDriftError,
                "LEGACY_ANALYSIS_SOURCE_SIZE_DRIFT",
            ):
                _verified_analysis_source_descriptors(
                    legacy_repository_root=root,
                    source_index=source_index,
                )


if __name__ == "__main__":
    unittest.main()
