from __future__ import annotations

import unittest
from dataclasses import replace

from arc3_agi_agent.p_update import (
    CandidatePBundle,
    HDSPUpdateAuthority,
    PBundleLifecycle,
    PRegressionReport,
    PUpdateDecision,
    PUpdateEvidenceSet,
    PUpdateProposal,
)
from arc3_agi_agent.protocol import AuthorityViolation


def _proposal() -> PUpdateProposal:
    return PUpdateProposal(
        proposal_id="proposal:failure-conditioned-information-head",
        source_p_version="parametric-stable-v1",
        source_p_digest="body:stable",
        target_component="P-B",
        update_type="head-parameter",
        evidence_refs=("evidence:stagnation",),
        expected_effect="change-failure-conditioned-information-ranking",
        expected_affected_capabilities=("failure-conditioned-exploration",),
        expected_unaffected_capabilities=("stable-action-effect-ranking",),
        falsifiers=("same-input-output-remains-identical",),
        rollback_target="parametric-stable-v1",
        provenance=("memory-snapshot:approved",),
    )


def _evidence(proposal: PUpdateProposal) -> PUpdateEvidenceSet:
    return PUpdateEvidenceSet(
        evidence_set_id="evidence-set:approved-contrast-v1",
        proposal_digest=proposal.digest,
        memory_snapshot_digest="memory-snapshot:one",
        approved_memory_refs=("memory:failure", "memory:positive"),
        hds_memory_decision_digests=("hds-memory-decision:one",),
        failure_refs=("failure:candidate-surface-stagnation",),
        contradiction_refs=("contradiction:predicted-progress-absent",),
        positive_contrast_refs=("contrast:visible-progress",),
        negative_contrast_refs=("contrast:repeated-no-progress",),
        holdout_refs=("holdout:stable-structure",),
        replay_audit_refs=("audit:identity-free-no-replay",),
        provenance=("runtime-memory:authorized",),
    )


def _bundle(
    *,
    lifecycle: str,
    version: str,
    body_digest: str,
    source_version: str,
    source_digest: str,
    proposal_digest: str = "proposal:foundation",
    directive_digest: str = "compile:foundation",
    parameter_digest: str = "parameter:new",
    predecessor_parameter_digest: str = "parameter:old",
    old_output: str = "output:old",
    new_output: str = "output:new",
) -> CandidatePBundle:
    return CandidatePBundle(
        candidate_id=f"bundle:{version}:{lifecycle.lower()}",
        proposal_digest=proposal_digest,
        compile_directive_digest=directive_digest,
        target_component="P-B",
        body_version=version,
        body_digest=body_digest,
        source_body_version=source_version,
        source_body_digest=source_digest,
        provenance_digest=f"provenance:{version}",
        manifest_digest=f"manifest:{version}",
        deterministic_rebuild_digest=f"rebuild:{version}",
        rollback_target=source_version,
        parameter_digest=parameter_digest,
        predecessor_parameter_digest=predecessor_parameter_digest,
        same_input_predecessor_output_digest=old_output,
        same_input_candidate_output_digest=new_output,
        parameter_change_attribution="failure-feature-to-information-head",
        lifecycle=lifecycle,
    )


def _report(candidate: CandidatePBundle, baseline: CandidatePBundle) -> PRegressionReport:
    return PRegressionReport(
        report_id="regression:candidate-v2",
        candidate_bundle_digest=candidate.digest,
        baseline_bundle_digest=baseline.digest,
        target_metric="failure-conditioned-information-separation",
        baseline_target_value=0.1,
        candidate_target_value=0.3,
        stable_regression_delta=0.0,
        holdout_delta=0.0,
        forgetting_measure=0.0,
        maximum_forgetting=0.0,
        schema_digest_provenance_pass=True,
        identity_free_pass=True,
        deterministic_rebuild_pass=True,
        target_improved=True,
        stable_non_regression=True,
        holdout_non_degradation=True,
        catastrophic_forgetting_within_bound=True,
        hds_boundary_pass=True,
        reproducible_pass=True,
        rollback_pass=True,
        evidence_refs=("regression:target", "regression:holdout"),
    )


class PUpdateTests(unittest.TestCase):
    def test_hds_compile_grant_is_owner_bound_and_single_use(self) -> None:
        proposal = _proposal()
        evidence = _evidence(proposal)
        hds = HDSPUpdateAuthority()
        decision = hds.decide(
            proposal,
            status="COMPILE",
            reason_codes=("approved-memory-contrast-is-closed",),
            evidence_set=evidence,
        )
        directive = hds.issue_compile_directive(
            proposal,
            evidence,
            decision,
            target_body_version="parametric-candidate-v2",
            seed=0,
        )

        directive.consume(decision, hds)
        self.assertTrue(directive.consumed)
        with self.assertRaisesRegex(
            AuthorityViolation,
            "P_COMPILE_DIRECTIVE_ALREADY_CONSUMED",
        ):
            directive.consume(decision, hds)

    def test_manual_decision_cannot_authorize_compile(self) -> None:
        proposal = _proposal()
        evidence = _evidence(proposal)
        hds = HDSPUpdateAuthority()
        manual = PUpdateDecision(
            decision_id="manual",
            proposal_digest=proposal.digest,
            status="COMPILE",
            reason_codes=("manual",),
            evidence_set_digest=evidence.digest,
            allow_p_compile=True,
        )

        with self.assertRaisesRegex(
            AuthorityViolation,
            "P_COMPILE_DECISION_NOT_HDS_OWNED",
        ):
            hds.issue_compile_directive(
                proposal,
                evidence,
                manual,
                target_body_version="parametric-candidate-v2",
                seed=0,
            )

    def test_p_b_candidate_rejects_version_only_update(self) -> None:
        candidate = _bundle(
            lifecycle="CANDIDATE",
            version="parametric-candidate-v2",
            body_digest="body:candidate",
            source_version="parametric-stable-v1",
            source_digest="body:stable",
            parameter_digest="parameter:same",
            predecessor_parameter_digest="parameter:same",
            old_output="output:same",
            new_output="output:same",
        )

        self.assertIn(
            "P_CANDIDATE_P_B_PARAMETER_DIGEST_UNCHANGED",
            candidate.validate(),
        )
        self.assertIn(
            "P_CANDIDATE_P_B_SAME_INPUT_OUTPUT_UNCHANGED",
            candidate.validate(),
        )

    def test_failed_regression_gate_prevents_promote_decision(self) -> None:
        proposal = _proposal()
        active = _bundle(
            lifecycle="ACTIVE",
            version="parametric-stable-v1",
            body_digest="body:stable",
            source_version="parametric-predecessor-v0",
            source_digest="body:predecessor",
        )
        candidate = _bundle(
            lifecycle="CANDIDATE",
            version="parametric-candidate-v2",
            body_digest="body:candidate",
            source_version=active.body_version,
            source_digest=active.body_digest,
            proposal_digest=proposal.digest,
        )
        failed = replace(
            _report(candidate, active),
            holdout_delta=-0.1,
            holdout_non_degradation=False,
        )

        with self.assertRaisesRegex(
            ValueError,
            "P_UPDATE_PROMOTION_GATE_FAILED:HOLDOUT_NON_DEGRADATION",
        ):
            HDSPUpdateAuthority().decide(
                proposal,
                status="PROMOTE",
                reason_codes=("target-improved",),
                candidate_bundle=candidate,
                regression_report=failed,
            )

    def test_promote_then_hds_rollback_restores_stable_bundle(self) -> None:
        proposal = _proposal()
        evidence = _evidence(proposal)
        hds = HDSPUpdateAuthority()
        active = _bundle(
            lifecycle="ACTIVE",
            version="parametric-stable-v1",
            body_digest="body:stable",
            source_version="parametric-predecessor-v0",
            source_digest="body:predecessor",
        )
        compile_decision = hds.decide(
            proposal,
            status="COMPILE",
            reason_codes=("evidence-closed",),
            evidence_set=evidence,
        )
        compile_directive = hds.issue_compile_directive(
            proposal,
            evidence,
            compile_decision,
            target_body_version="parametric-candidate-v2",
            seed=0,
        )
        compile_directive.consume(compile_decision, hds)
        candidate = _bundle(
            lifecycle="CANDIDATE",
            version="parametric-candidate-v2",
            body_digest="body:candidate",
            source_version=active.body_version,
            source_digest=active.body_digest,
            proposal_digest=proposal.digest,
            directive_digest=compile_directive.digest,
        )
        registry = PBundleLifecycle(active=active)
        registry.stage_candidate(candidate, compile_directive)
        report = _report(candidate, active)
        promote_decision = hds.decide(
            proposal,
            status="PROMOTE",
            reason_codes=("all-ten-gates-pass",),
            candidate_bundle=candidate,
            regression_report=report,
        )
        promote = hds.issue_promotion_directive(
            proposal,
            candidate,
            report,
            promote_decision,
            expected_active_bundle_digest=active.digest,
        )

        receipt = registry.promote(
            promote,
            promote_decision,
            report,
            hds,
        )

        self.assertEqual(registry.active.body_digest, "body:candidate")
        self.assertEqual(
            registry.previous_stable.body_digest
            if registry.previous_stable is not None
            else None,
            "body:stable",
        )
        self.assertEqual(receipt.previous_active_bundle_digest, active.digest)

        rollback_decision = hds.decide(
            proposal,
            status="ROLLBACK",
            reason_codes=("post-promotion-falsifier-observed",),
            candidate_bundle=registry.active,
        )
        assert registry.previous_stable is not None
        rollback = hds.issue_rollback_directive(
            proposal,
            registry.active,
            rollback_decision,
            rollback_bundle_digest=registry.previous_stable.digest,
        )
        restored = registry.rollback(rollback, rollback_decision, hds)

        self.assertEqual(restored.body_digest, "body:stable")
        self.assertEqual(registry.active.lifecycle, "ACTIVE")
        self.assertEqual(registry.rejected[-1].body_digest, "body:candidate")


if __name__ == "__main__":
    unittest.main()
