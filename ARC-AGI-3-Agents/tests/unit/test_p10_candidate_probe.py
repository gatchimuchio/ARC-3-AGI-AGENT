from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from arc_agi import OperationMode
from arc_agi.local_wrapper import LocalEnvironmentWrapper
from arcengine import FrameDataRaw, GameAction

from arc3_agi_agent.instruction_body import (
    ParametricInstructionBody,
    load_instruction_body,
    load_p10_hybrid_instruction_body,
)
from arc3_agi_agent.p10_runtime import P10OfflineSampleRuntime
from arc3_agi_agent.p_update import (
    CandidatePBundle,
    HDSPUpdateAuthority,
    PUpdateDecision,
    PUpdateProposal,
    parameter_digest,
)
from arc3_agi_agent.protocol import AuthorityViolation

BUNDLE_DIR = Path(__file__).resolve().parents[2] / "arc3_agi_agent" / "bundles"


class _FakeOfflineEnvironment(LocalEnvironmentWrapper):
    def __init__(self) -> None:
        self._last_response = FrameDataRaw()

    def step(
        self,
        action: GameAction,
        *,
        data: dict[str, int],
        reasoning: dict[str, str],
    ) -> FrameDataRaw:
        raise AssertionError("candidate loader test must not emit")


def _proposal() -> PUpdateProposal:
    return PUpdateProposal(
        proposal_id="proposal:isolated-candidate-probe",
        source_p_version="p10-active-instruction-body-set",
        source_p_digest="manifest:active",
        target_component="instruction-body-set",
        update_type="symbolic-parametric-composition",
        evidence_refs=("evidence:approved-runtime-memory",),
        expected_effect="measure-isolated-candidate-behavior",
        expected_affected_capabilities=("candidate-composed-control",),
        expected_unaffected_capabilities=("active-runtime-selection",),
        falsifiers=("candidate-does-not-change-future-compute",),
        rollback_target="p10-active-instruction-body-set",
        provenance=("hds:bounded-offline-probe",),
    )


def _candidate(proposal: PUpdateProposal) -> CandidatePBundle:
    active = load_p10_hybrid_instruction_body()
    candidate = load_instruction_body(BUNDLE_DIR / "p10_hybrid_v7.json")
    if not isinstance(candidate, ParametricInstructionBody):
        raise TypeError("candidate probe fixture must be parametric")
    return CandidatePBundle(
        candidate_id="candidate:p10-hybrid-isolated-probe",
        proposal_digest=proposal.digest,
        compile_directive_digest="compile:hds-authorized",
        target_component="hybrid-P-B",
        body_version=candidate.body_version,
        body_digest=candidate.digest(),
        source_body_version=active.body_version,
        source_body_digest=active.digest(),
        provenance_digest=candidate.provenance_digest,
        manifest_digest="manifest:candidate",
        deterministic_rebuild_digest="rebuild:candidate",
        rollback_target=active.body_version,
        parameter_digest=parameter_digest(candidate.weights),
        predecessor_parameter_digest=parameter_digest(active.weights),
        same_input_predecessor_output_digest="output:active",
        same_input_candidate_output_digest="output:candidate",
        parameter_change_attribution="approved-memory-to-parametric-heads",
    )


class P10CandidateProbeTests(unittest.TestCase):
    def test_candidate_runtime_requires_hds_owned_probe_decision(self) -> None:
        with self.assertRaisesRegex(
            AuthorityViolation,
            "P10_CANDIDATE_PROBE_HDS_AUTHORIZATION_REQUIRED",
        ):
            P10OfflineSampleRuntime(
                environment=object(),
                operation_mode=OperationMode.OFFLINE,
                instruction_lifecycle="candidate",
            )

    def test_manual_probe_decision_cannot_load_candidate(self) -> None:
        proposal = _proposal()
        candidate = _candidate(proposal)
        authority = HDSPUpdateAuthority()
        manual = PUpdateDecision(
            decision_id="decision:manual-probe",
            proposal_digest=proposal.digest,
            status="PROBE",
            reason_codes=("manual-decision-must-not-authorize",),
            candidate_bundle_digest=candidate.digest,
        )

        with self.assertRaisesRegex(
            AuthorityViolation,
            "P10_CANDIDATE_PROBE_DECISION_NOT_HDS_OWNED",
        ):
            P10OfflineSampleRuntime(
                environment=object(),
                operation_mode=OperationMode.OFFLINE,
                instruction_lifecycle="candidate",
                p_update_authority=authority,
                p_update_decision=manual,
                candidate_bundle=candidate,
            )

    def test_hds_probe_loads_candidate_without_changing_active_loader(
        self,
    ) -> None:
        proposal = _proposal()
        candidate = _candidate(proposal)
        authority = HDSPUpdateAuthority()
        decision = authority.decide(
            proposal,
            status="PROBE",
            reason_codes=("bounded-offline-regression-authorized",),
            candidate_bundle=candidate,
        )

        probe_body = load_instruction_body(BUNDLE_DIR / "p10_hybrid_v7.json")
        with patch(
            "arc3_agi_agent.p10_runtime."
            "load_p10_candidate_hybrid_instruction_body",
            return_value=probe_body,
        ):
            runtime = P10OfflineSampleRuntime(
                environment=_FakeOfflineEnvironment(),
                operation_mode=OperationMode.OFFLINE,
                instruction_lifecycle="candidate",
                p_update_authority=authority,
                p_update_decision=decision,
                candidate_bundle=candidate,
            )

        self.assertEqual(
            runtime.components.instruction_body.body_version,
            candidate.body_version,
        )
        self.assertEqual(
            runtime.components.instruction_body.digest(),
            candidate.body_digest,
        )
        self.assertNotEqual(
            load_p10_hybrid_instruction_body().digest(),
            candidate.body_digest,
        )

    def test_active_runtime_rejects_candidate_probe_binding(self) -> None:
        proposal = _proposal()
        candidate = _candidate(proposal)
        authority = HDSPUpdateAuthority()
        decision = authority.decide(
            proposal,
            status="PROBE",
            reason_codes=("candidate-only-binding",),
            candidate_bundle=candidate,
        )

        with self.assertRaisesRegex(
            AuthorityViolation,
            "P10_ACTIVE_RUNTIME_REJECTS_PROBE_BINDING",
        ):
            P10OfflineSampleRuntime(
                environment=object(),
                operation_mode=OperationMode.OFFLINE,
                p_update_authority=authority,
                p_update_decision=decision,
                candidate_bundle=candidate,
            )


if __name__ == "__main__":
    unittest.main()
