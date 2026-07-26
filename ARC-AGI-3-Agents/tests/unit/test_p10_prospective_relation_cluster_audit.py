from __future__ import annotations

import copy
import unittest

from arc3_agi_agent.p10_prospective_relation_cluster_audit import (
    build_p10_prospective_relation_cluster_audit,
)
from arc3_agi_agent.prospective_relation import (
    PROSPECTIVE_RELATION_PROBE_FORMAT,
)
from arc3_agi_agent.schema import digest_object


def _report(index: int) -> dict[str, object]:
    first_label = (
        "SUSPEND_AND_REQUEST_ROLLBACK"
        if index == 0
        else (
            "REOBSERVE_COMMIT_STATE"
            if index == 1
            else "FOLLOW_RELATION_DELTA"
        )
    )
    labels = [
        first_label,
        *(["FOLLOW_RELATION_DELTA"] * 7),
        *(["VERIFY_RELATION_SETTLE"] * 8),
    ]
    records: list[dict[str, object]] = []
    known = 0
    correct = 0
    for ordinal, label in enumerate(labels, start=1):
        prediction = "UNKNOWN" if ordinal == 1 else label
        known += int(prediction != "UNKNOWN")
        correct += int(prediction == label)
        records.append(
            {
                "ordinal": ordinal,
                "observed_obligation": label,
                "relation_delta": (
                    "RELATION_CHANGED"
                    if ordinal % 2
                    else "RELATION_STABLE"
                ),
                "prediction_before_update": {"label": prediction},
            }
        )
    probe = {
        "format": PROSPECTIVE_RELATION_PROBE_FORMAT,
        "candidate_tier": "LOCAL_PROBE",
        "runtime_use": "FORBIDDEN",
        "runtime_decision_use": "FORBIDDEN",
        "action_selection_influence": False,
        "memory_write_authority": False,
        "external_emit_authority": False,
        "runtime_p_promotion_authority": False,
        "raw_grid_retention": False,
        "observation_count": 16,
        "fault_count": 0,
        "known_prediction_count": known,
        "correct_prediction_count": correct,
        "records": records,
    }
    return {
        "game_id": f"development-selector-{index:02d}",
        "development_prospective_relation_probe": probe,
    }


def _source() -> dict[str, object]:
    return {
        "phase": "P10",
        "operation_mode": "offline",
        "environment_count": 25,
        "completed_count": 25,
        "error_count": 0,
        "max_actions": 16,
        "instruction_variant": "hybrid",
        "instruction_lifecycle": "active",
        "reports": [_report(index) for index in range(25)],
        "errors": [],
    }


class ProspectiveRelationClusterAuditTests(unittest.TestCase):
    def test_positive_all25_shadow_contrast_is_cluster_stable(self) -> None:
        audit = build_p10_prospective_relation_cluster_audit(
            _source(),
            source_sha256="a" * 64,
            source_bytes=1234,
        )
        body = dict(audit)
        claimed = body.pop("content_digest")

        self.assertEqual(
            claimed,
            "arc3_p10_prospective_relation_cluster_audit:"
            + digest_object(body),
        )
        self.assertEqual(audit["candidate_tier"], "CLUSTER_STABLE")
        self.assertTrue(all(audit["cluster_checks"].values()))
        self.assertEqual(audit["aggregate"]["observation_count"], 400)
        judgment = audit["hds_judgment"]
        self.assertEqual(judgment["cluster_stable_status"], "PASS")
        self.assertTrue(judgment["composition_input_authorized"])
        self.assertFalse(judgment["runtime_p_compile_authorized"])

    def test_runtime_authority_contamination_holds_cluster(self) -> None:
        source = copy.deepcopy(_source())
        source["reports"][0][
            "development_prospective_relation_probe"
        ]["action_selection_influence"] = True

        audit = build_p10_prospective_relation_cluster_audit(
            source,
            source_sha256="b" * 64,
            source_bytes=1234,
        )

        self.assertEqual(audit["candidate_tier"], "LOCAL_PROBE")
        self.assertEqual(
            audit["hds_judgment"]["cluster_stable_status"],
            "HOLD",
        )
        self.assertFalse(
            audit["cluster_checks"][
                "passive_identity_free_boundary_pass"
            ]
        )


if __name__ == "__main__":
    unittest.main()
