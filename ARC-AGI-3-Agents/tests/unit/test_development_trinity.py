from __future__ import annotations

import unittest

from arc3_agi_agent.development_trinity import (
    DEVELOPMENT_STAGES,
    DevelopmentDecision,
    DevelopmentFrame,
    DevelopmentHDS,
    DevelopmentHypothesis,
    DevelopmentWorkBlockTrace,
)


def _frame() -> DevelopmentFrame:
    return DevelopmentFrame(
        frame_id="frame:p-update-lifecycle",
        phase="P10",
        x_observe=("active-candidate-alias",),
        x_change=("p-update-control-layer",),
        x_evidence_use=("stable-bundle-digests",),
        x_evidence_exclude=("source-state",),
        r_hypotheses=("H1", "H2", "H3"),
        r_predictions=("candidate-remains-inactive",),
        r_comparators=("stable-active", "isolated-candidate"),
        r_expected_transitions=("uncontrolled-to-hds-controlled",),
        r_falsification_relations=("unowned-directive-succeeds",),
        mc_identity="generic-p-update-control",
        mc_boundary="offline-local-control-plane",
        mc_acceptance=("three-hypotheses", "authority-tests-pass"),
        mc_stop=("authority-bypass",),
        mc_rollback=("keep-stable-active",),
        mc_completion=("all-nine-stages-accounted",),
        non_goals=("sample-score-optimization",),
        evidence_boundary=("rendered-and-content-addressed-evidence",),
        falsifiers=("candidate-loads-as-active",),
        regression_line=("unit-suite",),
        maximum_work_scope=("control-contract-and-manifest-separation",),
    )


def _hypothesis(kind: str) -> DevelopmentHypothesis:
    return DevelopmentHypothesis(
        hypothesis_id=f"hypothesis:{kind.lower()}",
        kind=kind,
        summary=f"{kind} bounded candidate",
        predicted_effects=("authority-bound-change",),
        applicability=("generic-p-update",),
        required_evidence=("stable-and-candidate-digest",),
        falsifiers=("authority-bypass-remains",),
        implementation_cost=2,
        rollback_cost=1,
        generality=0.8,
        information_gain=0.8,
        contamination_risk=0.0,
        regression_risk=0.1,
    )


class DevelopmentTrinityTests(unittest.TestCase):
    def test_hds_requires_h1_h2_h3_and_binds_decision(self) -> None:
        frame = _frame()
        hypotheses = tuple(_hypothesis(kind) for kind in ("H1", "H2", "H3"))
        hds = DevelopmentHDS()

        decision = hds.judge(
            frame,
            hypotheses,
            status="PROBE",
            selected_hypothesis_id="hypothesis:h3",
            reason_codes=("highest-reversible-information-gain",),
            maximum_information_gain_next="compile-authority-negative-test",
        )

        self.assertEqual(decision.validate(), ())
        self.assertTrue(decision.is_owned_by(hds))
        self.assertEqual(decision.selected_hypothesis_id, "hypothesis:h3")

    def test_hds_rejects_single_candidate_shortcut(self) -> None:
        with self.assertRaisesRegex(
            ValueError,
            "DEV_HYPOTHESIS_MINIMUM_THREE_REQUIRED",
        ):
            DevelopmentHDS().judge(
                _frame(),
                (_hypothesis("H1"),),
                status="PROBE",
                selected_hypothesis_id="hypothesis:h1",
                reason_codes=("only-candidate",),
                maximum_information_gain_next="none",
            )

    def test_directly_constructed_decision_has_no_hds_owner(self) -> None:
        decision = DevelopmentDecision(
            decision_id="manual",
            frame_digest=_frame().digest,
            status="PROBE",
            selected_hypothesis_id="hypothesis:h3",
            reason_codes=("manual",),
            maximum_information_gain_next="unknown",
        )

        self.assertFalse(decision.is_owned_by(DevelopmentHDS()))

    def test_work_block_trace_requires_all_stages_in_order(self) -> None:
        trace = DevelopmentWorkBlockTrace(
            work_block_id="work-block:p-update-control",
            frame_digest=_frame().digest,
            hypothesis_digests=("digest:h1", "digest:h2", "digest:h3"),
            decision_digest="digest:decision",
            stage_evidence=tuple(
                (stage, f"evidence:{stage.lower()}")
                for stage in DEVELOPMENT_STAGES
            ),
            predicted_changes=("candidate-separation",),
            observed_changes=("candidate-separation",),
            unchanged=("stable-runtime",),
            regressions=(),
            unobserved=("full-sample-score",),
            m_dev_update_digest="digest:m-dev",
            p_dev_candidate_digest=None,
        )

        self.assertEqual(trace.validate(), ())


if __name__ == "__main__":
    unittest.main()
