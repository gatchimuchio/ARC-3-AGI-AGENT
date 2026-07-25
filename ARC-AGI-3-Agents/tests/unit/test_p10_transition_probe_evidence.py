from __future__ import annotations

import copy
import hashlib
import json
import unittest
from pathlib import Path

from arc3_agi_agent.p10_transition_probe_evidence import (
    build_c2_c3_probe_audit,
)
from arc3_agi_agent.schema import digest_object


class P10TransitionProbeEvidenceTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repository_root = Path(__file__).resolve().parents[3]
        cls.evidence_root = (
            cls.repository_root
            / "evidence"
            / "p10"
            / "development"
            / "c2_c3_local_probe_all25_max1_v14"
        )
        cls.audit = json.loads(
            (
                cls.evidence_root / "C2_C3_LOCAL_PROBE_AUDIT.json"
            ).read_text(encoding="utf-8")
        )
        cls.raw_report_path = (
            cls.evidence_root / "p10_all25_active_max1_raw.json"
        )
        cls.compact_evidence_path = (
            cls.evidence_root / "p10_all25_active_max1_compact.json"
        )
        cls.raw_report = json.loads(
            cls.raw_report_path.read_text(encoding="utf-8")
        )
        cls.compact_evidence = json.loads(
            cls.compact_evidence_path.read_text(encoding="utf-8")
        )

    def test_all_25_shadow_probes_are_bound_without_runtime_authority(
        self,
    ) -> None:
        audit = self.audit
        self.assertTrue(audit["development_only"])
        self.assertEqual(audit["runtime_use"], "FORBIDDEN")
        self.assertEqual(audit["candidate_tier"], "LOCAL_PROBE")
        self.assertEqual(
            audit["capability_ids"],
            [
                "C2_visible_effect_transition_model",
                "C3_commit_boundary_predictor",
            ],
        )
        self.assertEqual(audit["summary"]["game_count"], 25)
        self.assertEqual(audit["summary"]["action_count"], 25)
        self.assertEqual(audit["summary"]["observation_count"], 25)
        self.assertEqual(audit["summary"]["error_count"], 0)
        self.assertEqual(audit["summary"]["fault_count"], 0)
        self.assertEqual(
            audit["summary"]["boundary_counts"],
            {
                "NO_VISIBLE_COMMIT": 3,
                "TRANSITION_NO_COMMIT": 22,
            },
        )
        self.assertTrue(all(audit["checks"].values()))
        self.assertTrue(audit["checks"]["compact_matches_raw_report"])
        self.assertTrue(
            audit["checks"]["checkpoint_conditions_digest_valid"]
        )
        self.assertTrue(
            all(
                not row["action_selection_influence"]
                for row in audit["rows"]
            )
        )

    def test_local_probe_pass_does_not_claim_cluster_or_promotion(
        self,
    ) -> None:
        judgment = self.audit["hds_judgment"]
        self.assertEqual(judgment["local_probe_status"], "PASS")
        self.assertEqual(judgment["cluster_stable_status"], "HOLD")
        self.assertEqual(judgment["composable_status"], "HOLD")
        self.assertFalse(judgment["runtime_p_promotion_authorized"])
        self.assertFalse(judgment["score_claim_authorized"])

    def test_audit_and_compact_evidence_are_content_bound(self) -> None:
        body = copy.deepcopy(self.audit)
        claimed = body.pop("content_digest")
        self.assertEqual(
            claimed,
            "arc3_c2_c3_local_probe_audit:" + digest_object(body),
        )
        compact = json.loads(
            (
                self.evidence_root / "p10_all25_active_max1_compact.json"
            ).read_text(encoding="utf-8")
        )
        compact_body = copy.deepcopy(compact)
        compact_claimed = compact_body.pop("content_digest")
        self.assertEqual(compact_claimed, digest_object(compact_body))
        self.assertEqual(
            len(compact["compact_run"]["reports"]),
            25,
        )
        self.assertTrue(
            all(
                "development_transition_probe" in report
                for report in compact["compact_run"]["reports"]
            )
        )

    def test_checkpoint_conditions_and_zero_replay_resume_are_bound(
        self,
    ) -> None:
        conditions = self.audit["source_evidence"]["conditions"]
        self.assertEqual(conditions["operation_mode"], "offline")
        self.assertEqual(conditions["instruction_lifecycle"], "active")
        self.assertEqual(conditions["max_actions"], 1)
        self.assertEqual(conditions["arc_agi_version"], "0.9.8")
        self.assertEqual(
            conditions["runtime_source_inventory_digest"],
            "8ade5406134a6ff077934da8dc44eae979d9046dcfb1ca1e33a329c5acbd259b",
        )
        self.assertTrue(conditions["environment_inventory_digest"])

        index = json.loads(
            (
                self.evidence_root
                / "checkpoints"
                / "CHECKPOINT_INDEX.json"
            ).read_text(encoding="utf-8")
        )
        index_body = copy.deepcopy(index)
        index_claimed = index_body.pop("content_digest")
        self.assertEqual(index_claimed, digest_object(index_body))
        self.assertEqual(len(index["completed_game_ids"]), 25)
        self.assertEqual(len(index["reused_game_ids"]), 25)
        self.assertEqual(index["remaining_game_ids"], [])
        self.assertEqual(
            index["conditions"]["conditions_digest"],
            conditions["conditions_digest"],
        )

    def test_reported_games_must_match_checkpoint_conditions(self) -> None:
        raw_report = copy.deepcopy(self.raw_report)
        conditions = raw_report["checkpointing"]["conditions"]
        conditions["game_ids"][0] = "different-game"
        conditions_body = copy.deepcopy(conditions)
        conditions_body.pop("conditions_digest")
        conditions["conditions_digest"] = digest_object(conditions_body)
        with self.assertRaisesRegex(
            ValueError,
            "reported_games_match_checkpoint_conditions",
        ):
            build_c2_c3_probe_audit(
                raw_report=raw_report,
                raw_report_sha256=hashlib.sha256(
                    self.raw_report_path.read_bytes()
                ).hexdigest(),
                compact_evidence=self.compact_evidence,
                compact_evidence_sha256=hashlib.sha256(
                    self.compact_evidence_path.read_bytes()
                ).hexdigest(),
            )


if __name__ == "__main__":
    unittest.main()
