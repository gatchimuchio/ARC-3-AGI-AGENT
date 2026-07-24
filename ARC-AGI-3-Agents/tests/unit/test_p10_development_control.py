from __future__ import annotations

import hashlib
import json
import unittest
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
CONTROL_DIR = REPOSITORY_ROOT / "control" / "p10"
BUNDLE_DIR = (
    REPOSITORY_ROOT / "ARC-AGI-3-Agents" / "arc3_agi_agent" / "bundles"
)
AUTHORITY_PATH = (
    REPOSITORY_ROOT
    / "docs"
    / "roadmap"
    / "ARC3_CODEX_DEVELOPMENT_TRINITY_P_UPDATE_CORRECTION_ROADMAP.md"
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
        expected = frame["authority"]["repository_sha256_lf"]

        self.assertEqual(
            hashlib.sha256(AUTHORITY_PATH.read_bytes()).hexdigest(),
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

    def test_v18_shape_push_promotion_is_current_control_authority(
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
            "p10-v18-shape-push-promotion-v1",
        )
        self.assertEqual(frame["self_check"]["stable_completed_levels"], 32)
        self.assertEqual(capabilities["stable_completed_levels"], 32)
        self.assertEqual(
            registry["active_manifest_digest"],
            "9beb81c420fff3b4bc453edc960300eb5912035a4efe871b57498adabf8d9584",
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
        shape_decision = next(
            item
            for item in decisions
            if item["decision_id"]
            == "j-dev:p10-shape-push-probe-v18"
        )
        self.assertEqual(shape_decision["status"], "PROBE")
        self.assertEqual(
            shape_decision["selected_hypothesis"],
            "H18-outline-interior-shape-role-representation",
        )
        promotion = next(
            item
            for item in decisions
            if item.get("decision_digest")
            == registry["hds_decision_digest"]
        )
        self.assertEqual(promotion["status"], "PROMOTE")
        self.assertTrue(promotion["allow_p_promote"])

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
