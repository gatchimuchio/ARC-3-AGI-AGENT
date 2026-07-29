"""Separate-authority version learning for the GenericAGIRuntime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Sequence

from .generic_compute import ParametricRelationalInstructionBody
from .generic_hds import HDSConfiguration
from .generic_memory import SemanticRecord
from .p_bundle import PBundle
from .p_compiler_v2 import EvidenceSelectionManifest, PCompilerV2
from .schema import digest_object

GENERIC_LEARNING_VERSION = "arc3-generic-version-learning-v1"
GENERIC_LEARNING_V2_VERSION = "arc3-generic-version-learning-v2"


def compile_p_bundle_v2_candidate(
    *,
    mode: str,
    parent: PBundle,
    evidence: Sequence[SemanticRecord],
    evidence_manifest: EvidenceSelectionManifest,
    target_version: str,
) -> PBundle:
    """Compile one isolated v2 candidate without mutating the active bundle."""

    return PCompilerV2().compile(
        mode=mode,
        parent=parent,
        records=evidence,
        evidence_manifest=evidence_manifest,
        target_version=target_version,
    )


def _payload_count(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return 0


@dataclass(frozen=True, slots=True)
class PUpdateProposal:
    proposal_id: str
    active_p_digest: str
    evidence_record_ids: tuple[str, ...]
    target_version: str
    update_scope: str
    expected_improvement: str
    rollback_target: str

    def digest(self) -> str:
        return "generic-p-update-proposal:" + digest_object(self)


@dataclass(frozen=True, slots=True)
class PCompileAuthorization:
    authorization_id: str
    proposal_digest: str
    active_p_digest: str
    evidence_digest: str
    _authority_token: object = field(
        repr=False,
        compare=False,
        metadata={"serialize": False},
    )


@dataclass(frozen=True, slots=True)
class CandidatePBundle:
    candidate_id: str
    proposal_digest: str
    body: ParametricRelationalInstructionBody
    evidence_digest: str
    active_p_digest: str
    isolated_from_active: bool
    compiler_version: str

    def digest(self) -> str:
        return "generic-candidate-p:" + digest_object(self)


@dataclass(frozen=True, slots=True)
class VersionMetric:
    completed: int
    progress: int
    actions: int
    crashes: int
    identity_leaks: int

    def utility(self) -> tuple[int, int, int, int, int]:
        return (
            self.completed,
            self.progress,
            -self.crashes,
            -self.identity_leaks,
            -self.actions,
        )


@dataclass(frozen=True, slots=True)
class PVersionRegression:
    baseline: VersionMetric
    candidate: VersionMetric
    known_sample_regression_passed: bool
    holdout_improved: bool
    candidate_non_degrading: bool
    evaluator_digest: str

    def passed(self) -> bool:
        return (
            self.known_sample_regression_passed
            and self.holdout_improved
            and self.candidate_non_degrading
            and self.candidate.crashes == 0
            and self.candidate.identity_leaks == 0
        )


@dataclass(frozen=True, slots=True)
class PPromotionDecision:
    decision_id: str
    status: str
    candidate_digest: str
    active_p_digest: str
    reasons: tuple[str, ...]
    rollback_target: str
    promoted_p_digest: str | None


@dataclass(frozen=True, slots=True)
class GenericInitialStateBundle:
    version: str
    p_body: ParametricRelationalInstructionBody
    j0: HDSConfiguration
    m0: tuple[SemanticRecord, ...]
    source_candidate_digest: str
    digest_value: str

    @property
    def digest(self) -> str:
        return self.digest_value


@dataclass(slots=True)
class HDSPVersionAuthority:
    """Separate version-loop HDS authority; runtime cannot invoke it."""

    authority_token: object = field(default_factory=object, repr=False)
    _consumed_compile: set[str] = field(default_factory=set, init=False)

    def propose(
        self,
        *,
        active_p: ParametricRelationalInstructionBody,
        evidence: Sequence[SemanticRecord],
        target_version: str,
    ) -> PUpdateProposal:
        usable = tuple(
            sorted(
                record.memory_id
                for record in evidence
                if record.kind in {"PROCEDURE_CAPABILITY", "ACTION_EFFECT"}
            )
        )
        if not usable:
            raise ValueError("GENERIC_P_UPDATE_EVIDENCE_MISSING")
        body = {
            "active": active_p.digest(),
            "evidence": usable,
            "target_version": target_version,
        }
        return PUpdateProposal(
            proposal_id="generic-p-update:" + digest_object(body)[:24],
            active_p_digest=active_p.digest(),
            evidence_record_ids=usable,
            target_version=target_version,
            update_scope="shared-action-effect-bias",
            expected_improvement="blind holdout action efficiency or completion",
            rollback_target=active_p.digest(),
        )

    def authorize_compile(
        self,
        proposal: PUpdateProposal,
        *,
        active_p: ParametricRelationalInstructionBody,
        evidence: Sequence[SemanticRecord],
    ) -> PCompileAuthorization:
        evidence_digest = "generic-p-evidence:" + digest_object(
            tuple(sorted(evidence, key=lambda item: item.memory_id))
        )
        if proposal.active_p_digest != active_p.digest():
            raise PermissionError("GENERIC_P_ACTIVE_BINDING_INVALID")
        if not set(proposal.evidence_record_ids).issubset(
            {item.memory_id for item in evidence}
        ):
            raise PermissionError("GENERIC_P_EVIDENCE_BINDING_INVALID")
        return PCompileAuthorization(
            authorization_id="generic-p-compile-authorization:"
            + digest_object(
                {
                    "proposal": proposal.digest(),
                    "active": active_p.digest(),
                    "evidence": evidence_digest,
                }
            )[:24],
            proposal_digest=proposal.digest(),
            active_p_digest=active_p.digest(),
            evidence_digest=evidence_digest,
            _authority_token=self.authority_token,
        )

    def compile_candidate(
        self,
        proposal: PUpdateProposal,
        authorization: PCompileAuthorization,
        *,
        active_p: ParametricRelationalInstructionBody,
        evidence: Sequence[SemanticRecord],
    ) -> CandidatePBundle:
        if authorization._authority_token is not self.authority_token:
            raise PermissionError("GENERIC_P_COMPILE_AUTHORITY_INVALID")
        if authorization.authorization_id in self._consumed_compile:
            raise PermissionError("GENERIC_P_COMPILE_AUTHORIZATION_REUSED")
        evidence_tuple = tuple(sorted(evidence, key=lambda item: item.memory_id))
        evidence_digest = "generic-p-evidence:" + digest_object(evidence_tuple)
        if (
            authorization.proposal_digest != proposal.digest()
            or authorization.active_p_digest != active_p.digest()
            or authorization.evidence_digest != evidence_digest
        ):
            raise PermissionError("GENERIC_P_COMPILE_BINDING_INVALID")
        biases: dict[str, float] = {}
        for record in evidence_tuple:
            if record.memory_id not in proposal.evidence_record_ids:
                continue
            payload = record.payload()
            key = next(
                (
                    token
                    for token in record.semantic_tokens
                    if token.startswith("surface:")
                ),
                None,
            )
            if key is None:
                continue
            success = _payload_count(payload.get("success_count", 0))
            hazard = _payload_count(payload.get("hazard_count", 0))
            no_effect = _payload_count(payload.get("no_effect_count", 0))
            total = max(1, success + hazard + no_effect)
            biases[key] = (
                2.0 * success
                - 2.5 * hazard
                - 0.8 * no_effect
            ) / total
        if not biases:
            raise ValueError("GENERIC_P_COMPILE_NO_REUSABLE_ACTION_BIAS")
        candidate_body = active_p.with_action_bias(
            version=proposal.target_version,
            action_bias=biases,
            provenance=(
                GENERIC_LEARNING_VERSION
                + ":hds-authorized-semantic-memory:"
                + evidence_digest
            ),
        )
        failures = candidate_body.validate()
        if failures:
            raise ValueError(";".join(failures))
        self._consumed_compile.add(authorization.authorization_id)
        return CandidatePBundle(
            candidate_id="candidate-p:" + digest_object(
                {
                    "proposal": proposal.digest(),
                    "body": candidate_body.digest(),
                }
            )[:24],
            proposal_digest=proposal.digest(),
            body=candidate_body,
            evidence_digest=evidence_digest,
            active_p_digest=active_p.digest(),
            isolated_from_active=candidate_body.digest() != active_p.digest(),
            compiler_version=GENERIC_LEARNING_VERSION,
        )

    def blind_regression(
        self,
        candidate: CandidatePBundle,
        *,
        active_p: ParametricRelationalInstructionBody,
        evaluator: Callable[
            [ParametricRelationalInstructionBody], VersionMetric
        ],
        evaluator_digest: str,
        known_sample_regression_passed: bool,
    ) -> PVersionRegression:
        if candidate.active_p_digest != active_p.digest():
            raise PermissionError("GENERIC_P_REGRESSION_ACTIVE_BINDING_INVALID")
        baseline = evaluator(active_p)
        candidate_metric = evaluator(candidate.body)
        holdout_improved = candidate_metric.utility() > baseline.utility()
        non_degrading = (
            candidate_metric.completed >= baseline.completed
            and candidate_metric.progress >= baseline.progress
            and candidate_metric.crashes <= baseline.crashes
            and candidate_metric.identity_leaks <= baseline.identity_leaks
        )
        return PVersionRegression(
            baseline=baseline,
            candidate=candidate_metric,
            known_sample_regression_passed=known_sample_regression_passed,
            holdout_improved=holdout_improved,
            candidate_non_degrading=non_degrading,
            evaluator_digest=evaluator_digest,
        )

    def decide_promotion(
        self,
        candidate: CandidatePBundle,
        regression: PVersionRegression,
    ) -> PPromotionDecision:
        passed = regression.passed()
        reasons: list[str] = []
        if not regression.known_sample_regression_passed:
            reasons.append("KNOWN_SAMPLE_REGRESSION_FAILED")
        if not regression.holdout_improved:
            reasons.append("BLIND_HOLDOUT_NOT_IMPROVED")
        if not regression.candidate_non_degrading:
            reasons.append("CANDIDATE_DEGRADED")
        if regression.candidate.crashes:
            reasons.append("CANDIDATE_CRASHED")
        if regression.candidate.identity_leaks:
            reasons.append("CANDIDATE_IDENTITY_LEAK")
        if passed:
            reasons.append("HDS_PROMOTION_GATES_PASSED")
        return PPromotionDecision(
            decision_id="generic-p-promotion-decision:"
            + digest_object((candidate.digest(), regression))[:24],
            status="PROMOTE" if passed else "ROLLBACK",
            candidate_digest=candidate.digest(),
            active_p_digest=candidate.active_p_digest,
            reasons=tuple(sorted(set(reasons))),
            rollback_target=candidate.active_p_digest,
            promoted_p_digest=candidate.body.digest() if passed else None,
        )

    def compile_initial_state(
        self,
        candidate: CandidatePBundle,
        decision: PPromotionDecision,
        *,
        j0: HDSConfiguration,
        memory_records: Sequence[SemanticRecord],
    ) -> GenericInitialStateBundle:
        if (
            decision.status != "PROMOTE"
            or decision.candidate_digest != candidate.digest()
            or decision.promoted_p_digest != candidate.body.digest()
        ):
            raise PermissionError("GENERIC_INITIAL_STATE_PROMOTION_REQUIRED")
        m0 = tuple(
            sorted(
                (
                    record
                    for record in memory_records
                    if record.kind
                    in {
                        "PROCEDURE_CAPABILITY",
                        "FAILURE_SIGNATURE",
                        "PURPOSE_BOUNDARY",
                    }
                    and record.state in {"ACTIVE", "PROBATION"}
                ),
                key=lambda item: item.memory_id,
            )
        )
        body = {
            "version": candidate.body.body_version(),
            "p": candidate.body.digest(),
            "j0": j0,
            "m0": m0,
            "candidate": candidate.digest(),
        }
        return GenericInitialStateBundle(
            version=candidate.body.body_version(),
            p_body=candidate.body,
            j0=j0,
            m0=m0,
            source_candidate_digest=candidate.digest(),
            digest_value="generic-initial-state:" + digest_object(body),
        )


__all__ = [
    "CandidatePBundle",
    "GENERIC_LEARNING_VERSION",
    "GENERIC_LEARNING_V2_VERSION",
    "GenericInitialStateBundle",
    "HDSPVersionAuthority",
    "PCompileAuthorization",
    "PPromotionDecision",
    "PUpdateProposal",
    "PVersionRegression",
    "VersionMetric",
    "compile_p_bundle_v2_candidate",
]
