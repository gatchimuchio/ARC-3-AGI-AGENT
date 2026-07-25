from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

from arc3_agi_agent.p10_directional_settle_composition_audit import (
    build_p10_directional_settle_composition_audit,
)
from arc3_agi_agent.schema import digest_object

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
ACTIVE_COMPACT = (
    REPOSITORY_ROOT
    / "evidence"
    / "p10"
    / "development"
    / "stable_regression_v14"
    / "ka59_max200.compact.json"
)


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected object: {path}")
    return value


class DirectionalSettleCompositionAuditTests(unittest.TestCase):
    def test_observed_gap_authorizes_only_isolated_candidate_compile(
        self,
    ) -> None:
        audit = build_p10_directional_settle_composition_audit(
            _json(ACTIVE_COMPACT)
        )
        body = dict(audit)
        claimed = body.pop("content_digest")

        self.assertEqual(
            claimed,
            "arc3_p10_directional_settle_composition_audit:"
            + digest_object(body),
        )
        self.assertTrue(all(audit["contract_checks"].values()))
        self.assertEqual(audit["candidate_tier"], "LOCAL_PROBE")
        self.assertEqual(
            audit["observed_gap"]["progress_boundary_action_ordinal"],
            193,
        )
        self.assertEqual(
            audit["observed_gap"]["post_progress_action_ordinal"],
            194,
        )
        judgment = audit["hds_judgment"]
        self.assertEqual(judgment["local_probe_status"], "PASS")
        self.assertTrue(
            judgment["candidate_hybrid_compile_authorized"]
        )
        self.assertFalse(judgment["active_p_compile_authorized"])
        self.assertFalse(judgment["runtime_p_promotion_authorized"])
        self.assertFalse(judgment["score_progress_claim_authorized"])

    def test_tampered_source_digest_is_rejected(self) -> None:
        source = _json(ACTIVE_COMPACT)
        source["content_digest"] = "tampered"

        with self.assertRaisesRegex(
            ValueError,
            "SOURCE_CONTENT_DIGEST_INVALID",
        ):
            build_p10_directional_settle_composition_audit(source)


if __name__ == "__main__":
    unittest.main()
