from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

from arc3_agi_agent.p10_directional_settle_failure_audit import (
    build_p10_directional_settle_failure_audit,
)
from arc3_agi_agent.schema import digest_object

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_DIR = (
    REPOSITORY_ROOT
    / "evidence"
    / "p10"
    / "development"
    / "directional_settle_composition_v1"
)
INTERVENTION = (
    EVIDENCE_DIR
    / "DIRECTIONAL_SETTLE_CANDIDATE_INTERVENTION_AUDIT.json"
)
CANDIDATE_COMPACT = (
    EVIDENCE_DIR / "DIRECTIONAL_SETTLE_CANDIDATE_TARGET_COMPACT.json"
)
FAILURE_AUDIT = EVIDENCE_DIR / "DIRECTIONAL_SETTLE_FAILURE_AUDIT.json"


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected object: {path}")
    return value


class P10DirectionalSettleFailureAuditTests(unittest.TestCase):
    def test_rebuilds_closed_negative_from_retained_evidence(
        self,
    ) -> None:
        rebuilt = build_p10_directional_settle_failure_audit(
            _json(INTERVENTION),
            _json(CANDIDATE_COMPACT),
        )

        self.assertEqual(rebuilt, _json(FAILURE_AUDIT))
        body = dict(rebuilt)
        claimed = body.pop("content_digest")
        self.assertEqual(
            claimed,
            "arc3_p10_directional_settle_failure_audit:"
            + digest_object(body),
        )
        signature = rebuilt["failure_signature"]
        self.assertEqual(signature["progress_boundary_action_ordinal"], 193)
        self.assertEqual(
            signature["bounded_replay_first_action_ordinal"],
            194,
        )
        self.assertEqual(
            signature["bounded_replay_last_action_ordinal"],
            201,
        )
        self.assertEqual(
            signature["generic_fallback_action_ordinal"],
            202,
        )
        self.assertEqual(signature["target_completion_delta"], 0)
        judgment = rebuilt["hds_judgment"]
        self.assertEqual(judgment["causal_result"], "CLOSED_NEGATIVE")
        self.assertFalse(judgment["same_candidate_retry_authorized"])
        self.assertFalse(judgment["runtime_p_promotion_authorized"])

    def test_tampered_intervention_is_rejected(self) -> None:
        intervention = _json(INTERVENTION)
        intervention["content_digest"] = "tampered"

        with self.assertRaisesRegex(
            ValueError,
            "INTERVENTION_INVALID",
        ):
            build_p10_directional_settle_failure_audit(
                intervention,
                _json(CANDIDATE_COMPACT),
            )

    def test_tampered_candidate_trace_is_rejected(self) -> None:
        compact = _json(CANDIDATE_COMPACT)
        compact["content_digest"] = "tampered"

        with self.assertRaisesRegex(
            ValueError,
            "DIAGNOSTIC_DIGEST_INVALID",
        ):
            build_p10_directional_settle_failure_audit(
                _json(INTERVENTION),
                compact,
            )


if __name__ == "__main__":
    unittest.main()
