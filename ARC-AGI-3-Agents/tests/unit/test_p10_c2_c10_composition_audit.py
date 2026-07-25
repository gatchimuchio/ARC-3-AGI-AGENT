from __future__ import annotations

import copy
import unittest

from arc3_agi_agent.p10_c2_c10_composition_audit import (
    build_c2_c10_composition_audit,
)
from arc3_agi_agent.schema import digest_object


def _with_digest(
    body: dict[str, object],
    prefix: str,
) -> dict[str, object]:
    return {
        **body,
        "content_digest": prefix + digest_object(body),
    }


def _c2_c3_audit() -> dict[str, object]:
    return _with_digest(
        {
            "schema_version": (
                "arc3-c2-c3-predictive-cluster-audit-v2"
            ),
            "development_only": True,
            "runtime_use": "FORBIDDEN",
            "capability_tiers": {
                "C2_visible_effect_transition_model": (
                    "CLUSTER_STABLE"
                ),
                "C3_commit_boundary_predictor": "LOCAL_PROBE",
            },
            "hds_judgment": {
                "c2_cluster_stable_observer_status": "PASS",
                "c3_cluster_stable_predictor_status": "HOLD",
            },
        },
        "arc3_c2_c3_predictive_cluster_audit:",
    )


def _c10_audit() -> dict[str, object]:
    return _with_digest(
        {
            "schema_version": (
                "arc3-p10-c10-temporal-causal-contrast-audit-v2"
            ),
            "development_only": True,
            "runtime_use": "FORBIDDEN",
            "candidate_tier": "CLUSTER_STABLE",
            "predictive_checks": {
                "prequential": True,
                "held_out": True,
                "removal": True,
            },
            "summary": {
                "prequential_all_accuracy_delta_milli": 13,
                "held_out_positive_game_count": 2,
            },
            "predictive_evaluation": {
                "within_game_prequential": {
                    "ambiguous_baseline": {
                        "accuracy_milli": 291,
                    },
                    "ambiguous_context": {
                        "accuracy_milli": 658,
                    },
                    "ambiguous_action_only": {
                        "accuracy_milli": 581,
                    },
                },
            },
            "hds_judgment": {
                "cluster_stable_status": "PASS",
                "cross_game_outcome_mapping_status": "HOLD",
            },
        },
        "arc3_c10_temporal_causal_contrast_audit:",
    )


class P10C2C10CompositionAuditTests(unittest.TestCase):
    def test_removal_and_held_out_controls_authorize_candidate_compile(
        self,
    ) -> None:
        audit = build_c2_c10_composition_audit(
            c2_c3_audit=_c2_c3_audit(),
            c10_audit=_c10_audit(),
        )

        self.assertTrue(all(audit["integrity_checks"].values()))
        self.assertTrue(all(audit["composable_checks"].values()))
        self.assertEqual(audit["candidate_tier"], "COMPOSABLE")
        judgment = audit["hds_judgment"]
        self.assertEqual(judgment["composable_status"], "PASS")
        self.assertTrue(
            judgment["runtime_p_candidate_compile_authorized"]
        )
        self.assertFalse(
            judgment["runtime_p_active_compile_authorized"]
        )
        self.assertFalse(judgment["runtime_p_promotion_authorized"])
        body = copy.deepcopy(audit)
        claimed = body.pop("content_digest")
        self.assertEqual(
            claimed,
            "arc3_p10_c2_c10_composition_audit:"
            + digest_object(body),
        )

    def test_missing_c2_removal_delta_holds_composition(self) -> None:
        c10 = _c10_audit()
        evaluation = c10["predictive_evaluation"]
        assert isinstance(evaluation, dict)
        prequential = evaluation["within_game_prequential"]
        assert isinstance(prequential, dict)
        action_only = prequential["ambiguous_action_only"]
        assert isinstance(action_only, dict)
        action_only["accuracy_milli"] = 658
        body = dict(c10)
        body.pop("content_digest")
        c10 = _with_digest(
            body,
            "arc3_c10_temporal_causal_contrast_audit:",
        )

        audit = build_c2_c10_composition_audit(
            c2_c3_audit=_c2_c3_audit(),
            c10_audit=c10,
        )

        self.assertEqual(audit["candidate_tier"], "CLUSTER_STABLE")
        judgment = audit["hds_judgment"]
        self.assertEqual(judgment["composable_status"], "HOLD")
        self.assertFalse(
            judgment["runtime_p_candidate_compile_authorized"]
        )

    def test_tampered_source_digest_fails_closed(self) -> None:
        c10 = _c10_audit()
        c10["content_digest"] = "tampered"

        with self.assertRaisesRegex(
            ValueError,
            "c10_content_digest_valid",
        ):
            build_c2_c10_composition_audit(
                c2_c3_audit=_c2_c3_audit(),
                c10_audit=c10,
            )


if __name__ == "__main__":
    unittest.main()
