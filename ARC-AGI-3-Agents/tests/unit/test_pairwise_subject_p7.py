from __future__ import annotations

import dataclasses
import unittest

from arc3_agi_agent.pairwise import (
    PAIR_EXPECTATIONS,
    PAIR_FAILURE_WITNESSES,
    PAIR_ORDER,
    ComputeJudgmentPair,
    ComputeMemoryPair,
    JudgmentMemoryPair,
    PairwiseObligationFailure,
    run_pairwise_subject_audit,
)
from arc3_agi_agent.schema import forbidden_runtime_paths


def raw_observation() -> dict[str, object]:
    return {
        "frame": [[0, 1], [1, 0]],
        "dimensions": [2, 2],
        "available_actions": [1, 2, 3],
        "objects": [
            {
                "entity_id": "actor",
                "features": ["controllable", "foreground"],
            }
        ],
        "relations": ["adjacent"],
        "resources": ["bounded-action-budget"],
        "terminal_state": "RUNNING",
    }


class PairwiseSubjectAuditTests(unittest.TestCase):
    def test_all_pairs_execute_available_responsibilities_then_fail_uniquely(
        self,
    ) -> None:
        report = run_pairwise_subject_audit(raw_observation())

        self.assertTrue(report.passed)
        self.assertEqual(
            tuple(case.members for case in report.cases),
            PAIR_ORDER,
        )
        self.assertEqual(report.functional_equivalent_leak_count, 0)
        self.assertEqual(
            {case.failure_witness for case in report.cases},
            set(PAIR_FAILURE_WITNESSES.values()),
        )
        for case in report.cases:
            with self.subTest(pair=case.pair_id):
                self.assertTrue(case.passed)
                self.assertEqual(
                    dict(case.obligation_statuses),
                    PAIR_EXPECTATIONS[case.members],
                )
                self.assertEqual(case.overall, "FAIL")
                self.assertEqual(case.evidence.validate(), ())

    def test_cj_computes_and_judges_but_has_no_memory_carrier(self) -> None:
        pair = ComputeJudgmentPair()
        evidence = pair.exercise(raw_observation())

        self.assertGreaterEqual(evidence.hypothesis_count, 2)
        self.assertGreaterEqual(evidence.generated_candidate_count, 2)
        self.assertEqual(evidence.judgment_status, "ACCEPT")
        self.assertTrue(evidence.external_emit_authorization)
        self.assertFalse(evidence.memory_write_authorization)
        self.assertFalse(hasattr(pair, "memory_subject"))
        self.assertFalse(evidence.memory_before_digest)
        self.assertFalse(evidence.memory_after_digest)
        with self.assertRaisesRegex(
            PairwiseObligationFailure,
            "^NO_PERSISTENT_EXPERIENCE_CAUSALITY$",
        ):
            pair.require_full_obligations()

    def test_cm_computes_from_retained_state_but_cannot_confirm_write(
        self,
    ) -> None:
        pair = ComputeMemoryPair()
        evidence = pair.exercise(raw_observation())

        self.assertGreaterEqual(evidence.hypothesis_count, 2)
        self.assertGreaterEqual(evidence.generated_candidate_count, 2)
        self.assertTrue(evidence.unauthorized_write_rejected)
        self.assertEqual(
            evidence.memory_before_digest,
            evidence.memory_after_digest,
        )
        self.assertFalse(hasattr(pair, "judgment_subject"))
        self.assertEqual(pair.memory_subject.version, 1)
        with self.assertRaisesRegex(
            PairwiseObligationFailure,
            "^NO_JUDGMENT_OR_AUTHORIZATION$",
        ):
            pair.require_full_obligations()

    def test_jm_judges_supplied_candidate_and_retains_without_computing(
        self,
    ) -> None:
        pair = JudgmentMemoryPair()
        evidence = pair.exercise(raw_observation())

        self.assertEqual(evidence.hypothesis_count, 0)
        self.assertEqual(evidence.generated_candidate_count, 0)
        self.assertEqual(evidence.externally_supplied_candidate_count, 1)
        self.assertEqual(evidence.judgment_status, "ACCEPT")
        self.assertTrue(evidence.memory_write_authorization)
        self.assertEqual(
            evidence.memory_before_digest,
            evidence.memory_after_digest,
        )
        self.assertFalse(hasattr(pair, "compute_subject"))
        self.assertEqual(pair.memory_subject.version, 1)
        with self.assertRaisesRegex(
            PairwiseObligationFailure,
            "^NO_GENERATIVE_COMPUTATION$",
        ):
            pair.require_full_obligations()

    def test_pair_audit_is_deterministic_and_runtime_identity_free(self) -> None:
        first = run_pairwise_subject_audit(raw_observation())
        second = run_pairwise_subject_audit(raw_observation())

        self.assertEqual(first, second)
        self.assertEqual(first.digest, second.digest)
        self.assertEqual(
            forbidden_runtime_paths(dataclasses.asdict(first)),
            (),
        )

    def test_pair_instances_contain_only_the_named_subjects(self) -> None:
        pairs = {
            ("C", "J"): ComputeJudgmentPair(),
            ("C", "M"): ComputeMemoryPair(),
            ("J", "M"): JudgmentMemoryPair(),
        }
        fields = {
            "C": "compute_subject",
            "J": "judgment_subject",
            "M": "memory_subject",
        }
        for members, pair in pairs.items():
            with self.subTest(members=members):
                for subject, field_name in fields.items():
                    self.assertEqual(
                        hasattr(pair, field_name),
                        subject in members,
                    )

    def test_each_pair_harness_is_repeatable_without_hidden_state_drift(
        self,
    ) -> None:
        for pair in (
            ComputeJudgmentPair(),
            ComputeMemoryPair(),
            JudgmentMemoryPair(),
        ):
            with self.subTest(pair=type(pair).__name__):
                self.assertEqual(
                    pair.exercise(raw_observation()),
                    pair.exercise(raw_observation()),
                )


if __name__ == "__main__":
    unittest.main()
