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

    def test_v22_all_task_compilation_preserves_v21_active_p(
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
            "p10-v22-all-task-capability-compilation-v1",
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
