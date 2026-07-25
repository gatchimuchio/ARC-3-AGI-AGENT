from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path
from typing import Any

from arc3_agi_agent.schema import digest_object

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
CONTROL_DIR = REPOSITORY_ROOT / "control" / "p10"
BUNDLE_DIR = (
    REPOSITORY_ROOT / "ARC-AGI-3-Agents" / "arc3_agi_agent" / "bundles"
)
REQUIRED_CONTROL_FILES = frozenset(
    {
        "CURRENT_FRAME.json",
        "ACTIVE_HYPOTHESES.json",
        "REJECTED_HYPOTHESES.json",
        "CAPABILITY_REGISTRY.json",
        "FAILURE_SIGNATURE_REGISTRY.json",
        "EXPERIMENT_REGISTRY.json",
        "DEV_MEMORY.json",
        "DEV_METHOD_BODY.json",
        "P_UPDATE_REGISTRY.json",
        "DECISION_LOG.json",
    }
)


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected object: {path}")
    return value


class P10DevelopmentControlTests(unittest.TestCase):
    def test_required_management_artifacts_are_present_and_valid_json(self) -> None:
        names = {path.name for path in CONTROL_DIR.glob("*.json")}

        self.assertEqual(names, REQUIRED_CONTROL_FILES)
        for name in sorted(REQUIRED_CONTROL_FILES):
            self.assertIn("schema_version", _json(CONTROL_DIR / name), name)

    def test_repository_authority_copy_digest_is_fixed(self) -> None:
        frame = _json(CONTROL_DIR / "CURRENT_FRAME.json")
        authority_path = REPOSITORY_ROOT / frame["authority"]["document"]
        expected = frame["authority"]["repository_sha256_lf"]

        self.assertEqual(
            hashlib.sha256(authority_path.read_bytes()).hexdigest(),
            expected,
        )

    def test_h1_h2_h3_are_compared_and_h3_is_selected(self) -> None:
        hypotheses = _json(CONTROL_DIR / "ACTIVE_HYPOTHESES.json")[
            "hypotheses"
        ]
        kinds = {item["kind"] for item in hypotheses}
        decisions = _json(CONTROL_DIR / "DECISION_LOG.json")["decisions"]
        dev_decision = next(
            item
            for item in decisions
            if item["authority"] == "development-hds-only"
        )

        self.assertTrue({"H1", "H2", "H3"} <= kinds)
        self.assertEqual(dev_decision["status"], "PROBE")
        self.assertEqual(
            dev_decision["selected_hypothesis"],
            "H3-isolated-P-update-composition",
        )

    def test_promoted_candidate_is_bound_to_active_manifest(self) -> None:
        active_manifest = _json(BUNDLE_DIR / "p10_manifest.json")
        candidate_manifest = _json(BUNDLE_DIR / "p10_candidate_manifest.json")

        self.assertEqual(
            candidate_manifest["lifecycle"],
            "PROMOTED",
        )
        self.assertEqual(active_manifest["lifecycle"], "ACTIVE")
        self.assertEqual(
            active_manifest["promotion_decision_digest"],
            candidate_manifest["promotion_decision_digest"],
        )
        for variant in ("P-A", "P-B", "hybrid"):
            self.assertEqual(
                active_manifest["bundles"][variant]["content_digest"],
                candidate_manifest["bundles"][variant]["content_digest"],
                variant,
            )

    def test_learned_parametric_candidate_is_promoted(self) -> None:
        registry = _json(CONTROL_DIR / "P_UPDATE_REGISTRY.json")
        previous = registry["previous_stable"]
        candidate = registry["candidate"]["P-B"]

        self.assertNotEqual(
            previous["parameter_digest"],
            candidate["parameter_digest"],
        )
        self.assertEqual(candidate["status"], "PROMOTED")
        self.assertEqual(registry["hds_decision"], "PROMOTE")

    def test_v25_control_preserves_v21_active_p(
        self,
    ) -> None:
        frame = _json(CONTROL_DIR / "CURRENT_FRAME.json")
        capabilities = _json(
            CONTROL_DIR / "CAPABILITY_REGISTRY.json"
        )
        registry = _json(CONTROL_DIR / "P_UPDATE_REGISTRY.json")
        active_manifest = _json(BUNDLE_DIR / "p10_manifest.json")
        decisions = _json(CONTROL_DIR / "DECISION_LOG.json")[
            "decisions"
        ]

        self.assertEqual(
            frame["frame_id"],
            "p10-v25-c7-c5-closed-negative-audit",
        )
        self.assertEqual(frame["self_check"]["stable_completed_levels"], 35)
        self.assertEqual(capabilities["stable_completed_levels"], 35)
        self.assertEqual(
            registry["active_manifest_digest"],
            "6b67437d771d2a31f4c93303dee858f5151120412c2b7cf3ce55061b987aa2e1",
        )
        for variant in ("P-A", "P-B", "hybrid"):
            self.assertEqual(
                registry["active"][variant]["version"],
                active_manifest["bundles"][variant]["body_version"],
            )
            self.assertEqual(
                registry["active"][variant]["content_digest"],
                active_manifest["bundles"][variant]["content_digest"],
            )
        route_decision = next(
            item
            for item in decisions
            if item["decision_id"]
            == "j-dev:p10-directional-force-state-probe-v21"
        )
        self.assertEqual(route_decision["status"], "PROBE")
        self.assertEqual(
            route_decision["selected_hypothesis"],
            "H27-rendered-directional-charge-portal-state",
        )
        promotion = next(
            item
            for item in decisions
            if item.get("decision_digest")
            == registry["hds_decision_digest"]
        )
        self.assertEqual(promotion["status"], "PROMOTE")
        self.assertTrue(promotion["allow_p_promote"])

        strategy = next(
            item
            for item in decisions
            if item["decision_id"]
            == "j-dev:p10-all-task-capability-strategy-v22"
        )
        self.assertEqual(
            strategy["selected_hypothesis"],
            "H30-restore-task-aware-development-memory-and-late-subtraction",
        )
        self.assertEqual(
            strategy["rejected_hypothesis"],
            "H29-continue-per-level-dedicated-operator-loop",
        )
        probe = next(
            item
            for item in decisions
            if item["decision_id"]
            == "j-dev:p10-c2-c3-shadow-tier-v22"
        )
        self.assertEqual(probe["tier_decisions"]["LOCAL_PROBE"], "PASS")
        self.assertEqual(
            probe["tier_decisions"]["CLUSTER_STABLE"],
            "HOLD",
        )
        self.assertFalse(probe["allow_action_influence"])
        self.assertFalse(probe["allow_p_compile"])
        self.assertFalse(probe["allow_p_promote"])

    def test_v22b_bounded_runtime_memory_is_infrastructure_only(
        self,
    ) -> None:
        hypotheses = _json(CONTROL_DIR / "ACTIVE_HYPOTHESES.json")[
            "hypotheses"
        ]
        by_id = {item["hypothesis_id"]: item for item in hypotheses}
        decisions = _json(CONTROL_DIR / "DECISION_LOG.json")["decisions"]
        experiments = _json(CONTROL_DIR / "EXPERIMENT_REGISTRY.json")[
            "experiments"
        ]
        resource_audit = _json(
            REPOSITORY_ROOT
            / "evidence"
            / "p10"
            / "development"
            / "P10_BOUNDED_RUNTIME_MEMORY_V14_AUDIT.json"
        )

        self.assertEqual(
            by_id[
                "H32-increase-budget-or-parallelism-with-unbounded-retention"
            ]["status"],
            "REJECTED",
        )
        self.assertEqual(
            by_id[
                "H33-drop-history-or-candidate-tail-without-obligations"
            ]["status"],
            "REJECTED",
        )
        self.assertEqual(
            by_id[
                "H34-bounded-history-window-and-frontier-composition"
            ]["status"],
            "RUNTIME_INFRASTRUCTURE_ACCEPTED",
        )
        decision = next(
            item
            for item in decisions
            if item["decision_id"]
            == "j-dev:p10-bounded-runtime-memory-v22b"
        )
        self.assertEqual(decision["status"], "PASS")
        self.assertFalse(decision["allow_action_influence"])
        self.assertFalse(decision["allow_p_compile"])
        self.assertFalse(decision["allow_p_promote"])
        experiment = next(
            item
            for item in experiments
            if item["experiment_id"]
            == "p10-bounded-runtime-memory-v22b"
        )
        self.assertEqual(
            experiment["status"],
            "PASS_WORKER_COMPLETION_FAIL_RESOURCE_HEADROOM_P_UNCHANGED",
        )
        audit_body = dict(resource_audit)
        claimed_digest = audit_body.pop("content_digest")
        self.assertEqual(
            claimed_digest,
            "arc3_p10_bounded_runtime_memory_audit:"
            + digest_object(audit_body),
        )
        self.assertTrue(
            resource_audit["semantic_obligations"][
                "default_p6_history_remains_unbounded"
            ]
        )
        self.assertFalse(
            resource_audit["semantic_obligations"]["active_p_changed"]
        )
        self.assertEqual(
            resource_audit["hds_judgment"]["score_progress_status"],
            "NOT_CLAIMED",
        )
        self.assertEqual(
            resource_audit["hds_judgment"][
                "full_all_25_standard_budget_status"
            ],
            "PASS_REPORT_GENERATION",
        )
        self.assertEqual(
            resource_audit["hds_judgment"]["resource_headroom_status"],
            "FAIL_HIGH_WATER",
        )

    def test_v24_resource_predictive_and_causal_judgments_are_bound(
        self,
    ) -> None:
        evidence_dir = (
            REPOSITORY_ROOT
            / "evidence"
            / "p10"
            / "development"
            / "c2_c3_transition_all25_max450_v2"
        )
        retention = _json(
            evidence_dir / "P10_RUNTIME_RETENTION_AUDIT.json"
        )
        standard = _json(
            evidence_dir / "P10_STANDARD_BUDGET_AUDIT.json"
        )
        predictive = _json(
            evidence_dir / "C2_C3_PREDICTIVE_CLUSTER_AUDIT.json"
        )
        temporal = _json(
            evidence_dir / "C10_TEMPORAL_CAUSAL_CONTRAST_AUDIT.json"
        )
        composition = _json(
            evidence_dir / "C2_C10_COMPOSITION_REMOVAL_AUDIT.json"
        )
        intervention = _json(
            REPOSITORY_ROOT
            / "evidence"
            / "p10"
            / "development"
            / "c2_c10_candidate_intervention_v1"
            / "C2_C10_CANDIDATE_INTERVENTION_AUDIT.json"
        )
        for prefix, audit in (
            ("arc3_p10_runtime_retention_audit:", retention),
            ("arc3_p10_standard_budget_all25_audit:", standard),
            ("arc3_c2_c3_predictive_cluster_audit:", predictive),
            ("arc3_c10_temporal_causal_contrast_audit:", temporal),
            ("arc3_p10_c2_c10_composition_audit:", composition),
            ("arc3_p10_c2_c10_candidate_intervention:", intervention),
        ):
            body = dict(audit)
            claimed = body.pop("content_digest")
            self.assertEqual(claimed, prefix + digest_object(body))

        self.assertTrue(all(retention["checks"].values()))
        self.assertEqual(
            retention["fresh"]["timing"]["maximum_rss_kb"],
            110792,
        )
        self.assertEqual(
            retention["hds_judgment"]["resource_headroom_status"],
            "PASS",
        )
        self.assertTrue(all(standard["checks"].values()))
        self.assertEqual(
            standard["resource_measurement"]["maximum_worker"][
                "maximum_rss_kb"
            ],
            143852,
        )
        self.assertEqual(
            standard["resource_measurement"]["worker_swap_count"],
            0,
        )
        self.assertEqual(standard["summary"]["completed_levels"], 35)
        self.assertTrue(all(predictive["c2_observer_checks"].values()))
        self.assertFalse(
            all(predictive["c3_predictive_checks"].values())
        )
        self.assertEqual(
            predictive["hds_judgment"][
                "c2_cluster_stable_observer_status"
            ],
            "PASS",
        )
        self.assertEqual(
            predictive["hds_judgment"][
                "c3_cluster_stable_predictor_status"
            ],
            "HOLD",
        )
        self.assertEqual(
            temporal["summary"][
                "ambiguous_same_frame_action_group_count"
            ],
            81,
        )
        self.assertEqual(
            temporal["summary"]["one_step_separable_group_count"],
            80,
        )
        self.assertEqual(
            temporal["hds_judgment"]["cluster_stable_status"],
            "PASS",
        )
        self.assertEqual(
            composition["hds_judgment"]["composable_status"],
            "PASS",
        )
        self.assertEqual(
            intervention["hds_judgment"]["status"],
            "REJECT",
        )
        self.assertFalse(
            intervention["hds_judgment"]["allow_p_promote"]
        )
        self.assertFalse(intervention["active_manifest_changed"])
        self.assertFalse(
            intervention["hds_judgment"]["candidate_slot_retained"]
        )

        hypotheses = _json(
            CONTROL_DIR / "ACTIVE_HYPOTHESES.json"
        )["hypotheses"]
        by_id = {item["hypothesis_id"]: item for item in hypotheses}
        self.assertEqual(
            by_id["H37-hds-closed-cycle-heavy-binding-release"][
                "status"
            ],
            "RUNTIME_INFRASTRUCTURE_ACCEPTED",
        )
        self.assertEqual(
            by_id["H38-credit-post-action-boundary-as-prediction"][
                "status"
            ],
            "REJECTED",
        )
        self.assertEqual(
            by_id["H40-one-step-visible-causal-context"]["status"],
            "COMPOSABLE_POLICY_REJECTED",
        )
        decisions = _json(
            CONTROL_DIR / "DECISION_LOG.json"
        )["decisions"]
        c2_c3 = next(
            item
            for item in decisions
            if item["decision_id"]
            == "j-dev:p10-c2-c3-predictive-tier-v23"
        )
        self.assertEqual(c2_c3["status"], "HOLD")
        self.assertEqual(
            c2_c3["tier_decisions"][
                "C2_OBSERVER_CLUSTER_STABLE"
            ],
            "PASS",
        )
        self.assertEqual(
            c2_c3["tier_decisions"][
                "C3_PREDICTOR_CLUSTER_STABLE"
            ],
            "HOLD",
        )
        self.assertFalse(c2_c3["allow_p_compile"])
        self.assertFalse(c2_c3["allow_p_promote"])
        c2_c10 = next(
            item
            for item in decisions
            if item["decision_id"]
            == "j-dev:p10-c2-c10-candidate-intervention-v24"
        )
        self.assertEqual(c2_c10["status"], "REJECT")
        self.assertEqual(
            c2_c10["tier_decisions"]["C10_CLUSTER_STABLE"],
            "PASS",
        )
        self.assertEqual(
            c2_c10["tier_decisions"]["C2_C10_COMPOSABLE"],
            "PASS",
        )
        self.assertEqual(
            c2_c10["tier_decisions"]["CANDIDATE_P_A_INTERVENTION"],
            "REJECT",
        )
        self.assertFalse(c2_c10["allow_p_compile"])
        self.assertFalse(c2_c10["allow_p_promote"])

    def test_v25_c7_and_directional_settle_closed_negative_are_bound(
        self,
    ) -> None:
        evidence_root = (
            REPOSITORY_ROOT / "evidence" / "p10" / "development"
        )
        c7_dir = evidence_root / "c7_target_contact_closed_negative_v1"
        settle_dir = (
            evidence_root / "directional_settle_composition_v1"
        )
        c7 = _json(c7_dir / "C7_CLOSED_NEGATIVE_ADMISSION_AUDIT.json")
        composition = _json(
            settle_dir / "DIRECTIONAL_SETTLE_COMPOSITION_AUDIT.json"
        )
        intervention = _json(
            settle_dir
            / "DIRECTIONAL_SETTLE_CANDIDATE_INTERVENTION_AUDIT.json"
        )
        failure = _json(
            settle_dir / "DIRECTIONAL_SETTLE_FAILURE_AUDIT.json"
        )
        for prefix, audit in (
            ("arc3_p10_c7_closed_negative_admission:", c7),
            (
                "arc3_p10_directional_settle_composition_audit:",
                composition,
            ),
            (
                "arc3_p10_directional_settle_candidate_intervention:",
                intervention,
            ),
            (
                "arc3_p10_directional_settle_failure_audit:",
                failure,
            ),
        ):
            body = dict(audit)
            claimed = body.pop("content_digest")
            self.assertEqual(claimed, prefix + digest_object(body))

        retained_c7 = (
            c7_dir
            / "LEGACY_C7_TARGET_CONTACT_BOUNDARY_CAPABILITY.json"
        )
        self.assertEqual(
            hashlib.sha256(retained_c7.read_bytes()).hexdigest(),
            c7["source_evidence"]["sha256"],
        )
        self.assertEqual(
            c7["retained_measurements"][
                "progress_separator_variable_count"
            ],
            0,
        )
        self.assertEqual(
            c7["hds_judgment"]["causal_result"],
            "CLOSED_NEGATIVE",
        )
        self.assertFalse(
            c7["hds_judgment"]["same_surface_retry_authorized"]
        )

        self.assertEqual(
            intervention["hds_judgment"]["status"],
            "REJECT",
        )
        self.assertIn(
            "failed-evaluation-check-target-improved",
            intervention["hds_judgment"]["reason_codes"],
        )
        self.assertNotIn(
            "target_improved",
            intervention["hds_judgment"]["reason_codes"],
        )
        self.assertFalse(
            intervention["hds_judgment"]["candidate_slot_retained"]
        )
        self.assertEqual(
            failure["failure_signature"]["bounded_replay_count"],
            8,
        )
        self.assertEqual(
            failure["failure_signature"][
                "generic_fallback_action_ordinal"
            ],
            202,
        )
        self.assertEqual(
            failure["hds_judgment"]["causal_result"],
            "CLOSED_NEGATIVE",
        )
        self.assertFalse(
            failure["hds_judgment"][
                "same_candidate_retry_authorized"
            ]
        )

        hypotheses = _json(
            CONTROL_DIR / "ACTIVE_HYPOTHESES.json"
        )["hypotheses"]
        by_hypothesis = {
            item["hypothesis_id"]: item for item in hypotheses
        }
        self.assertEqual(
            by_hypothesis[
                "H41-reuse-legacy-target-contact-surface"
            ]["status"],
            "CLOSED_NEGATIVE",
        )
        self.assertEqual(
            by_hypothesis[
                "H42-bounded-old-directional-action-replay"
            ]["status"],
            "CLOSED_NEGATIVE",
        )
        self.assertEqual(
            by_hypothesis[
                "H43-visible-successor-obligation-composition"
            ]["status"],
            "UNOBSERVED_HOLD",
        )

        decisions = _json(
            CONTROL_DIR / "DECISION_LOG.json"
        )["decisions"]
        c7_decision = next(
            item
            for item in decisions
            if item["decision_id"]
            == "j-dev:p10-c7-target-contact-negative-admission-v25"
        )
        settle_decision = next(
            item
            for item in decisions
            if item["decision_id"]
            == "j-dev:p10-directional-settle-candidate-v25"
        )
        self.assertEqual(c7_decision["status"], "REJECT")
        self.assertEqual(
            c7_decision["tier_decisions"]["LOCAL_PROBE"],
            "CLOSED_NEGATIVE",
        )
        self.assertEqual(settle_decision["status"], "REJECT")
        self.assertEqual(
            settle_decision["tier_decisions"][
                "EXISTING_CAPABILITY_COMPOSITION"
            ],
            "PASS",
        )
        self.assertFalse(settle_decision["allow_p_promote"])

        capabilities = _json(
            CONTROL_DIR / "CAPABILITY_REGISTRY.json"
        )["capabilities"]
        by_capability = {
            item["capability_id"]: item for item in capabilities
        }
        self.assertEqual(
            by_capability[
                "C7-target-contact-boundary-verifier"
            ]["status"],
            "LOCAL_PROBE_CLOSED_NEGATIVE_NEGATIVE_ONLY",
        )
        self.assertEqual(
            by_capability[
                "C5-stale-settle-frame-controller"
            ]["status"],
            "LOCAL_PROBE_CLOSED_NEGATIVE_AXIS",
        )
        self.assertFalse(
            by_capability[
                "C7-target-contact-boundary-verifier"
            ]["runtime_admitted"]
        )
        self.assertFalse(
            by_capability[
                "C5-stale-settle-frame-controller"
            ]["runtime_admitted"]
        )

        memory_entries = _json(
            CONTROL_DIR / "DEV_MEMORY.json"
        )["entries"]
        memory = next(
            item
            for item in memory_entries
            if item["memory_id"]
            == "m-dev:p10-c7-c5-closed-negative-v25"
        )
        self.assertIn(
            "select WB-C12_layout_mode_commit_discriminator "
            "as the next coverage-ranked work block",
            memory["resume_conditions"],
        )

    def test_v14_standard_budget_and_stable_regression_audits_are_bound(
        self,
    ) -> None:
        evidence_dir = REPOSITORY_ROOT / "evidence" / "p10" / "development"
        standard = _json(
            evidence_dir / "P10_ACTIVE_ALL25_MAX450_V14_AUDIT.json"
        )
        regression = _json(
            evidence_dir / "P10_V14_STABLE_REGRESSION_AUDIT.json"
        )
        for prefix, audit in (
            ("arc3_p10_standard_budget_all25_audit:", standard),
            ("arc3_p10_stable_regression_audit:", regression),
        ):
            body = dict(audit)
            claimed = body.pop("content_digest")
            self.assertEqual(claimed, prefix + digest_object(body))

        self.assertTrue(all(standard["checks"].values()))
        self.assertEqual(standard["summary"]["completed_levels"], 35)
        self.assertEqual(
            standard["summary"]["official_rhae_score_percent"],
            18.821945363,
        )
        self.assertEqual(
            standard["hds_judgment"]["resource_headroom_status"],
            "FAIL_HIGH_WATER",
        )
        self.assertTrue(all(regression["checks"].values()))
        self.assertEqual(
            regression["summary"]["behavior_projection_match_count"],
            5,
        )
        self.assertEqual(
            regression["hds_judgment"]["stable_regression_status"],
            "PASS",
        )

    def test_v14_hypotheses_and_hds_promotion_are_recorded(self) -> None:
        hypotheses = _json(CONTROL_DIR / "ACTIVE_HYPOTHESES.json")[
            "hypotheses"
        ]
        by_id = {item["hypothesis_id"]: item for item in hypotheses}
        decisions = _json(CONTROL_DIR / "DECISION_LOG.json")["decisions"]

        self.assertTrue(
            {
                "H4-terminal-actor-anchor-observation",
                "H5-farthest-safe-target-assignment",
                "H6-ring-safe-route-step",
                "H7-terminal-actor-protection",
            }
            <= by_id.keys()
        )
        self.assertEqual(
            by_id["H7-terminal-actor-protection"]["status"],
            "PROMOTED",
        )
        promotion = next(
            item for item in decisions if item["status"] == "PROMOTE"
        )
        self.assertTrue(promotion["allow_p_promote"])


if __name__ == "__main__":
    unittest.main()
