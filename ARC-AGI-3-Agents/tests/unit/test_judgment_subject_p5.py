from __future__ import annotations

import dataclasses
import inspect
import unittest
from collections import Counter
from dataclasses import replace
from pathlib import Path

from arc3_agi_agent.judgment import (
    HDSR,
    HDSX,
    JUDGMENT_STATUSES,
    JUDGMENT_SUBJECT_REMOVAL_WITNESS,
    HDSFrame,
    HDSJudgmentSubject,
    HDSMc,
    JudgmentCandidate,
    StandaloneJudgmentHarness,
)
from arc3_agi_agent.judgment_fixtures import load_hds_frame_fixtures
from arc3_agi_agent.kernel import Layer0Components, Layer0Kernel
from arc3_agi_agent.protocol import HDSDecision
from arc3_agi_agent.roles import Layer0FunctionalLoss
from arc3_agi_agent.schema import forbidden_runtime_paths

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
HDS_FIXTURES = REPOSITORY_ROOT / "datasets" / "hds_frames" / "records.jsonl"


def candidate(
    candidate_id: str = "candidate:one",
    *,
    score: float = 0.8,
    risk: float = 0.1,
    evidence: tuple[str, ...] = ("evidence:observed",),
    counter_evidence: tuple[str, ...] = (),
    hazard: bool = False,
    admissible: bool = True,
    rejected: bool = False,
) -> JudgmentCandidate:
    return JudgmentCandidate(
        candidate_id=candidate_id,
        predicted_outcomes=("VISIBLE_STATE_CHANGE",),
        evidence_refs=evidence,
        counter_evidence_refs=counter_evidence,
        preconditions=("CURRENT_OBSERVATION_PRESENT",),
        falsification_conditions=("rendered effect contradicts prediction",),
        score=score,
        risk=risk,
        hazard=hazard,
        admissible=admissible,
        rejected=rejected,
        reversible=True,
        rollback_reference="snapshot:previous",
        reason_codes=("W_X_R_MC_CLOSED",),
    )


def frame(
    candidates: tuple[JudgmentCandidate, ...] | None = None,
) -> HDSFrame:
    supplied = candidates if candidates is not None else (candidate(),)
    return HDSFrame(
        frame_id="frame:p5-proof",
        purpose="select-safe-observed-candidate",
        x=HDSX(
            targets=("rendered-environment",),
            candidate_ids=tuple(item.candidate_id for item in supplied),
            observation_scope=("rendered-frame", "bounded-context"),
        ),
        r=HDSR(
            relations=("candidate-predicts-rendered-effect",),
            evidence_links=("evidence:observed",),
            counter_evidence_links=(),
        ),
        mc=HDSMc(
            identity="semantic:judgment-proof",
            boundary="rendered-and-admitted-evidence-only",
            acceptance_criteria=("W_X_R_MC_CLOSED",),
            rejection_criteria=("hazard", "contradiction"),
            stop_on=("terminal", "budget-exhaustion"),
            max_risk=0.5,
        ),
        observation_boundary="rendered-and-admitted-evidence-only",
        candidates=supplied,
        evidence=("evidence:observed",),
        counter_evidence=(),
        risk=0.1,
        hazard=False,
        budget=2,
        unknowns=(),
        stopping_conditions=(),
    )


def raw_observation() -> dict[str, object]:
    return {
        "frame": [[0, 1], [1, 0]],
        "dimensions": [2, 2],
        "available_actions": [1, 2],
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


class StandaloneJudgmentTests(unittest.TestCase):
    def setUp(self) -> None:
        self.subject = HDSJudgmentSubject()

    def test_complete_frame_is_accepted_without_generating_candidates(self) -> None:
        supplied = (
            candidate("candidate:lower", score=0.6),
            candidate("candidate:higher", score=0.9),
        )
        input_frame = frame(supplied)
        before = dataclasses.asdict(input_frame)

        decision = self.subject.judge(input_frame)

        self.assertEqual(decision.status, "ACCEPT")
        self.assertEqual(decision.selected_candidate_id, "candidate:higher")
        self.assertTrue(decision.allow_memory_write)
        self.assertTrue(decision.allow_external_emit)
        self.assertIsNone(decision.compute_request)
        self.assertNotIsInstance(decision, HDSDecision)
        self.assertEqual(dataclasses.asdict(input_frame), before)
        self.assertIn(
            decision.selected_candidate_id,
            {item.candidate_id for item in supplied},
        )

    def test_missing_purpose_x_r_or_mc_suspends(self) -> None:
        cases = {
            "purpose": replace(frame(), purpose=""),
            "x": replace(frame(), x=None),
            "r": replace(frame(), r=None),
            "mc": replace(frame(), mc=None),
        }
        for name, input_frame in cases.items():
            with self.subTest(name=name):
                decision = self.subject.judge(input_frame)
                self.assertEqual(decision.status, "SUSPEND")
                self.assertTrue(
                    any("FRAME_UNCLOSED" in code for code in decision.reason_codes)
                )
                self.assertFalse(decision.allow_memory_write)
                self.assertFalse(decision.allow_external_emit)

    def test_hazard_veto_precedes_unknown_and_budget(self) -> None:
        decision = self.subject.judge(
            replace(
                frame(),
                hazard=True,
                budget=0,
                unknowns=("terminal-state-unobserved",),
            )
        )

        self.assertEqual(decision.status, "REJECT")
        self.assertEqual(decision.reason_codes, ("HAZARD_ACTION_VETO",))

    def test_insufficient_evidence_reobserves(self) -> None:
        insufficient = candidate(evidence=())
        decision = self.subject.judge(frame((insufficient,)))

        self.assertEqual(decision.status, "REOBSERVE")
        self.assertEqual(
            decision.next_observation,
            "rendered-and-admitted-evidence-only",
        )

    def test_budget_exhaustion_stops(self) -> None:
        decision = self.subject.judge(replace(frame(), budget=0))

        self.assertEqual(decision.status, "STOP")
        self.assertEqual(decision.reason_codes, ("ACTION_BUDGET_EXHAUSTED",))

    def test_contradiction_rejects(self) -> None:
        decision = self.subject.judge(replace(frame(), contradiction=True))

        self.assertEqual(decision.status, "REJECT")
        self.assertEqual(decision.reason_codes, ("CONTRADICTION_ESTABLISHED",))

    def test_rollback_condition_returns_reference_without_applying_it(self) -> None:
        decision = self.subject.judge(
            replace(
                frame(),
                rollback_condition="new evidence falsifies active decision",
                rollback_reference="snapshot:previous",
            )
        )

        self.assertEqual(decision.status, "ROLLBACK")
        self.assertEqual(decision.rollback_reference, "snapshot:previous")
        self.assertFalse(decision.allow_memory_write)
        self.assertFalse(decision.allow_external_emit)
        self.assertFalse(hasattr(decision, "apply"))

    def test_no_candidate_requests_compute_without_computing(self) -> None:
        decision = self.subject.judge(frame(()))

        self.assertEqual(decision.status, "COMPUTE_REQUEST")
        self.assertIsNotNone(decision.compute_request)
        assert decision.compute_request is not None
        self.assertEqual(decision.compute_request.operation, "LLM_COMPUTE")
        self.assertFalse(hasattr(decision.compute_request, "execute"))

    def test_same_frame_has_same_judgment(self) -> None:
        input_frame = frame()
        self.assertEqual(
            self.subject.judge(input_frame),
            self.subject.judge(input_frame),
        )

    def test_task_identity_in_frame_is_suspended(self) -> None:
        contaminated = replace(frame(), purpose="solve task LS20-deadbeef")
        decision = self.subject.judge(contaminated)

        self.assertEqual(decision.status, "SUSPEND")
        self.assertTrue(
            any(
                "HDS_FRAME_RUNTIME_IDENTITY_FORBIDDEN" in code
                for code in decision.reason_codes
            )
        )

    def test_judgment_api_has_only_frame_input_and_no_c_p_m_import(self) -> None:
        parameters = tuple(inspect.signature(HDSJudgmentSubject.judge).parameters)
        source = Path(inspect.getsourcefile(HDSJudgmentSubject) or "").read_text(
            encoding="utf-8"
        )

        self.assertEqual(parameters, ("self", "frame"))
        self.assertNotIn("instruction_body", source)
        self.assertNotIn("PureLLMCompute", source)
        self.assertNotIn("PassiveMemory", source)
        self.assertNotIn("apply_authorized", source)
        self.assertNotIn("execute_emission", source)

    def test_j_removal_has_fixed_witness(self) -> None:
        harness = StandaloneJudgmentHarness(judgment_subject=None)
        with self.assertRaisesRegex(
            RuntimeError,
            JUDGMENT_SUBJECT_REMOVAL_WITNESS,
        ):
            harness.run(frame())


class JudgmentFixtureAndIntegrationTests(unittest.TestCase):
    def test_all_p3_hds_fixtures_are_typed_identity_free_and_deterministic(
        self,
    ) -> None:
        frames = load_hds_frame_fixtures(HDS_FIXTURES)
        subject = HDSJudgmentSubject()
        statuses: Counter[str] = Counter()

        self.assertEqual(len(frames), 676)
        for input_frame in frames:
            self.assertEqual(input_frame.validate(), ())
            self.assertEqual(
                forbidden_runtime_paths(dataclasses.asdict(input_frame)),
                (),
            )
            first = subject.judge(input_frame)
            second = subject.judge(input_frame)
            self.assertEqual(first, second)
            self.assertEqual(first.validate(), ())
            self.assertIn(first.status, JUDGMENT_STATUSES)
            if first.selected_candidate_id is not None:
                self.assertIn(
                    first.selected_candidate_id,
                    {item.candidate_id for item in input_frame.candidates},
                )
            statuses[first.status] += 1
        self.assertEqual(
            statuses,
            {
                "ACCEPT": 27,
                "REJECT": 613,
                "REOBSERVE": 2,
                "COMPUTE_REQUEST": 34,
            },
        )

    def test_integrated_kernel_uses_standalone_judgment_result(self) -> None:
        components = Layer0Components()
        result = Layer0Kernel(components).run_cycle(raw_observation())
        standalone = components.hds.standalone_judgment(result.decision)
        event = next(
            item
            for item in result.trace
            if item.operation == "CLOSURE_DECISION"
        )
        details = dict(event.details)

        self.assertEqual(standalone.status, "ACCEPT")
        self.assertEqual(result.decision.status, "EMIT")
        self.assertEqual(
            standalone.selected_candidate_id,
            result.decision.candidate_id,
        )
        self.assertEqual(details["frame"], standalone.frame_digest)
        self.assertEqual(
            details["standalone_decision"],
            standalone.decision_id,
        )
        self.assertEqual(details["standalone_status"], "ACCEPT")

    def test_integrated_j_removal_cannot_be_substituted(self) -> None:
        components = Layer0Components()
        components.hds.judgment_subject = None

        with self.assertRaises(Layer0FunctionalLoss) as raised:
            Layer0Kernel(components).run_cycle(raw_observation())

        self.assertEqual(raised.exception.role, "JUDGMENT_SUBJECT")
        self.assertEqual(
            raised.exception.reason,
            JUDGMENT_SUBJECT_REMOVAL_WITNESS,
        )
        self.assertTrue(raised.exception.removed)


if __name__ == "__main__":
    unittest.main()
