from __future__ import annotations

import copy
import json
import unittest
from pathlib import Path
from typing import Any

from arc3_agi_agent.instruction_body import (
    load_p10_hybrid_instruction_body,
)
from arc3_agi_agent.p10_prospective_obligation_composition_audit import (
    build_p10_prospective_obligation_composition_audit,
)
from arc3_agi_agent.schema import digest_object

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
DEVELOPMENT_ROOT = REPOSITORY_ROOT / "analysis" / "development"
EVIDENCE_ROOT = (
    REPOSITORY_ROOT
    / "evidence"
    / "p10"
    / "development"
)


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def _kwargs() -> dict[str, object]:
    return {
        "cluster_audit": _json(
            EVIDENCE_ROOT
            / "prospective_obligation_relation_v1"
            / "PROSPECTIVE_RELATION_CLUSTER_AUDIT.json"
        ),
        "active_compact": _json(
            EVIDENCE_ROOT
            / "active_all25_max450_v14"
            / "checkpoints"
            / "ka59-38d34dbb.checkpoint.json"
        ),
        "ledger": _json(
            DEVELOPMENT_ROOT / "LEGACY_LEVEL_ANALYSIS_LEDGER.json"
        ),
        "reconciliation": _json(
            DEVELOPMENT_ROOT / "ANALYSIS_RECONCILIATION_MATRIX.json"
        ),
        "coverage": _json(
            DEVELOPMENT_ROOT / "CAPABILITY_COVERAGE_MATRIX.json"
        ),
        "queue": _json(
            DEVELOPMENT_ROOT / "CAPABILITY_BUILD_QUEUE.json"
        ),
        "active_operator_ids": tuple(
            instruction.operator_id
            for instruction in (
                load_p10_hybrid_instruction_body().operator_instructions
            )
        ),
    }


class ProspectiveObligationCompositionAuditTests(unittest.TestCase):
    def test_h3_is_the_only_authorized_composable_candidate(self) -> None:
        audit = build_p10_prospective_obligation_composition_audit(
            **_kwargs()
        )
        body = dict(audit)
        claimed = body.pop("content_digest")

        self.assertEqual(
            claimed,
            "arc3_p10_prospective_obligation_composition_audit:"
            + digest_object(body),
        )
        self.assertEqual(audit["candidate_tier"], "COMPOSABLE")
        self.assertTrue(all(audit["composable_checks"].values()))
        self.assertEqual(
            audit["x_r_mc"]["decision"]["selected_hypothesis_id"],
            "hypothesis:h3-existing-capability-composition",
        )
        self.assertEqual(
            audit["candidate_contract"]["new_operator_count"],
            0,
        )
        self.assertTrue(
            audit["identity_subtraction"]["runtime_identity_free"]
        )
        judgment = audit["hds_judgment"]
        self.assertTrue(
            judgment["isolated_candidate_compile_authorized"]
        )
        self.assertFalse(judgment["active_p_compile_authorized"])
        self.assertFalse(judgment["runtime_p_promotion_authorized"])

    def test_tampered_cluster_audit_is_rejected(self) -> None:
        kwargs = _kwargs()
        cluster = copy.deepcopy(kwargs["cluster_audit"])
        cluster["content_digest"] = "tampered"
        kwargs["cluster_audit"] = cluster

        with self.assertRaisesRegex(
            ValueError,
            "SOURCE_INTEGRITY_FAILED",
        ):
            build_p10_prospective_obligation_composition_audit(
                **kwargs
            )

    def test_missing_existing_capability_holds_compile(self) -> None:
        kwargs = _kwargs()
        kwargs["active_operator_ids"] = (
            "multi-actor-shape-target-route-v4",
        )

        audit = build_p10_prospective_obligation_composition_audit(
            **kwargs
        )

        self.assertEqual(audit["candidate_tier"], "CLUSTER_STABLE")
        self.assertFalse(
            audit["hds_judgment"][
                "isolated_candidate_compile_authorized"
            ]
        )


if __name__ == "__main__":
    unittest.main()
