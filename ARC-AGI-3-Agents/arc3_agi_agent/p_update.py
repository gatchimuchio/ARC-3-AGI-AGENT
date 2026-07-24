"""HDS-controlled, non-destructive instruction-body P update lifecycle."""

from __future__ import annotations

import dataclasses
import math
import re
from dataclasses import dataclass, field, replace
from typing import Mapping

from .protocol import AuthorityViolation
from .schema import digest_object, forbidden_runtime_paths

P_UPDATE_SCHEMA_VERSION = "arc3-p-update-v1"
P_UPDATE_DECISION_STATUSES = frozenset(
    {"PROBE", "COMPILE", "HOLD", "REJECT", "PROMOTE", "ROLLBACK"}
)
P_B_TARGET_COMPONENTS = frozenset({"P-B", "hybrid-P-B"})
P_B_UPDATE_TYPES = frozenset(
    {
        "weight",
        "bias",
        "embedding",
        "transition-parameter",
        "feature-mapping",
        "head-parameter",
    }
)
P_BUNDLE_LIFECYCLES = frozenset(
    {"ACTIVE", "CANDIDATE", "PREVIOUS_STABLE", "REJECTED"}
)
_FORBIDDEN_IDENTITY_PATTERN = re.compile(
    r"(?i)(?:^|[^a-z0-9])(?:game|task|level)[-_ ]?(?:id|\d+)"
)


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _texts(value: object, *, required: bool = True) -> bool:
    return (
        isinstance(value, tuple)
        and (bool(value) or not required)
        and all(_text(item) for item in value)
    )


def _finite(value: object) -> bool:
    return (
        not isinstance(value, bool)
        and isinstance(value, (int, float))
        and math.isfinite(float(value))
    )


def _identity_value_paths(
    value: object,
    path: str = "$",
) -> tuple[str, ...]:
    failures: list[str] = []
    stack: list[tuple[str, object]] = [(path, value)]
    while stack:
        current_path, item = stack.pop()
        if isinstance(item, Mapping):
            stack.extend(
                (f"{current_path}.{key}", child)
                for key, child in item.items()
            )
        elif isinstance(item, tuple | list):
            stack.extend(
                (f"{current_path}[{index}]", child)
                for index, child in enumerate(item)
            )
        elif isinstance(item, str) and _FORBIDDEN_IDENTITY_PATTERN.search(item):
            failures.append(current_path)
    return tuple(sorted(set(failures)))


def _identity_failures(value: object, prefix: str) -> tuple[str, ...]:
    if dataclasses.is_dataclass(value) and not isinstance(value, type):
        serializable: object = dataclasses.asdict(value)
    else:
        serializable = value
    paths = {
        *forbidden_runtime_paths(serializable),
        *_identity_value_paths(serializable),
    }
    return tuple(f"{prefix}_RUNTIME_IDENTITY_FORBIDDEN:{path}" for path in paths)


def parameter_digest(weights: tuple[tuple[float, ...], ...]) -> str:
    """Return the canonical digest used to prove a real P-B parameter change."""

    digits = str(int(digest_object(weights), 16)).zfill(78)
    return "parameter-matrix:" + digits[:40]


@dataclass(frozen=True, slots=True)
class PUpdateProposal:
    proposal_id: str
    source_p_version: str
    source_p_digest: str
    target_component: str
    update_type: str
    evidence_refs: tuple[str, ...]
    expected_effect: str
    expected_affected_capabilities: tuple[str, ...]
    expected_unaffected_capabilities: tuple[str, ...]
    falsifiers: tuple[str, ...]
    rollback_target: str
    provenance: tuple[str, ...]
    runtime_identity_free: bool = True
    schema_version: str = P_UPDATE_SCHEMA_VERSION

    @property
    def digest(self) -> str:
        return digest_object(self)

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if self.schema_version != P_UPDATE_SCHEMA_VERSION:
            failures.append("P_UPDATE_PROPOSAL_SCHEMA_INVALID")
        for name, value in (
            ("ID", self.proposal_id),
            ("SOURCE_VERSION", self.source_p_version),
            ("SOURCE_DIGEST", self.source_p_digest),
            ("TARGET_COMPONENT", self.target_component),
            ("UPDATE_TYPE", self.update_type),
            ("EXPECTED_EFFECT", self.expected_effect),
            ("ROLLBACK_TARGET", self.rollback_target),
        ):
            if not _text(value):
                failures.append(f"P_UPDATE_PROPOSAL_{name}_MISSING")
        for name, values in (
            ("EVIDENCE", self.evidence_refs),
            ("AFFECTED_CAPABILITY", self.expected_affected_capabilities),
            ("UNAFFECTED_CAPABILITY", self.expected_unaffected_capabilities),
            ("FALSIFIER", self.falsifiers),
            ("PROVENANCE", self.provenance),
        ):
            if not _texts(values):
                failures.append(f"P_UPDATE_PROPOSAL_{name}_INVALID")
        if self.runtime_identity_free is not True:
            failures.append("P_UPDATE_PROPOSAL_IDENTITY_FLAG_INVALID")
        if (
            self.target_component in P_B_TARGET_COMPONENTS
            and self.update_type not in P_B_UPDATE_TYPES
        ):
            failures.append("P_UPDATE_PROPOSAL_P_B_UPDATE_TYPE_INVALID")
        failures.extend(_identity_failures(self, "P_UPDATE_PROPOSAL"))
        return tuple(sorted(set(failures)))


@dataclass(frozen=True, slots=True)
class PUpdateEvidenceSet:
    evidence_set_id: str
    proposal_digest: str
    memory_snapshot_digest: str
    approved_memory_refs: tuple[str, ...]
    hds_memory_decision_digests: tuple[str, ...]
    failure_refs: tuple[str, ...]
    contradiction_refs: tuple[str, ...]
    positive_contrast_refs: tuple[str, ...]
    negative_contrast_refs: tuple[str, ...]
    holdout_refs: tuple[str, ...]
    replay_audit_refs: tuple[str, ...]
    provenance: tuple[str, ...]
    runtime_identity_free: bool = True
    schema_version: str = P_UPDATE_SCHEMA_VERSION

    @property
    def digest(self) -> str:
        return digest_object(self)

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if self.schema_version != P_UPDATE_SCHEMA_VERSION:
            failures.append("P_UPDATE_EVIDENCE_SCHEMA_INVALID")
        for name, value in (
            ("ID", self.evidence_set_id),
            ("PROPOSAL_DIGEST", self.proposal_digest),
            ("MEMORY_SNAPSHOT_DIGEST", self.memory_snapshot_digest),
        ):
            if not _text(value):
                failures.append(f"P_UPDATE_EVIDENCE_{name}_MISSING")
        for name, values in (
            ("APPROVED_MEMORY", self.approved_memory_refs),
            ("HDS_MEMORY_DECISION", self.hds_memory_decision_digests),
            ("FAILURE", self.failure_refs),
            ("CONTRADICTION", self.contradiction_refs),
            ("POSITIVE_CONTRAST", self.positive_contrast_refs),
            ("NEGATIVE_CONTRAST", self.negative_contrast_refs),
            ("HOLDOUT", self.holdout_refs),
            ("REPLAY_AUDIT", self.replay_audit_refs),
            ("PROVENANCE", self.provenance),
        ):
            if not _texts(values):
                failures.append(f"P_UPDATE_EVIDENCE_{name}_INVALID")
        if self.runtime_identity_free is not True:
            failures.append("P_UPDATE_EVIDENCE_IDENTITY_FLAG_INVALID")
        failures.extend(_identity_failures(self, "P_UPDATE_EVIDENCE"))
        return tuple(sorted(set(failures)))


@dataclass(frozen=True, slots=True)
class PUpdateDecision:
    """Owner-bound decision that only :class:`HDSPUpdateAuthority` can issue."""

    decision_id: str
    proposal_digest: str
    status: str
    reason_codes: tuple[str, ...]
    evidence_set_digest: str | None = None
    candidate_bundle_digest: str | None = None
    regression_report_digest: str | None = None
    allow_p_compile: bool = False
    allow_p_promote: bool = False
    allow_p_rollback: bool = False
    authority: str = "hds-p-update-only"
    _owner: object | None = field(
        default=None,
        repr=False,
        compare=False,
    )

    @property
    def digest(self) -> str:
        return digest_object(
            {
                "decision_id": self.decision_id,
                "proposal_digest": self.proposal_digest,
                "status": self.status,
                "reason_codes": self.reason_codes,
                "evidence_set_digest": self.evidence_set_digest,
                "candidate_bundle_digest": self.candidate_bundle_digest,
                "regression_report_digest": self.regression_report_digest,
                "allow_p_compile": self.allow_p_compile,
                "allow_p_promote": self.allow_p_promote,
                "allow_p_rollback": self.allow_p_rollback,
                "authority": self.authority,
            }
        )

    def is_owned_by(self, owner: object) -> bool:
        return self._owner is owner

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not _text(self.decision_id):
            failures.append("P_UPDATE_DECISION_ID_MISSING")
        if not _text(self.proposal_digest):
            failures.append("P_UPDATE_DECISION_PROPOSAL_DIGEST_MISSING")
        if self.status not in P_UPDATE_DECISION_STATUSES:
            failures.append("P_UPDATE_DECISION_STATUS_INVALID")
        if not _texts(self.reason_codes):
            failures.append("P_UPDATE_DECISION_REASON_MISSING")
        if self.authority != "hds-p-update-only":
            failures.append("P_UPDATE_DECISION_AUTHORITY_INVALID")
        expected_flags = {
            "COMPILE": (True, False, False),
            "PROMOTE": (False, True, False),
            "ROLLBACK": (False, False, True),
        }.get(self.status, (False, False, False))
        actual_flags = (
            self.allow_p_compile,
            self.allow_p_promote,
            self.allow_p_rollback,
        )
        if actual_flags != expected_flags:
            failures.append("P_UPDATE_DECISION_AUTHORIZATION_FLAGS_INVALID")
        if self.status == "COMPILE" and not _text(self.evidence_set_digest):
            failures.append("P_UPDATE_DECISION_COMPILE_EVIDENCE_MISSING")
        if self.status in {"PROMOTE", "ROLLBACK"} and not _text(
            self.candidate_bundle_digest
        ):
            failures.append("P_UPDATE_DECISION_CANDIDATE_MISSING")
        if self.status == "PROMOTE" and not _text(
            self.regression_report_digest
        ):
            failures.append("P_UPDATE_DECISION_REGRESSION_MISSING")
        return tuple(sorted(set(failures)))


@dataclass(slots=True)
class InstructionBodyCompileDirective:
    directive_id: str
    decision_digest: str
    proposal_digest: str
    evidence_set_digest: str
    source_p_digest: str
    target_body_version: str
    output_role: str
    seed: int
    _owner: object = field(repr=False, compare=False)
    _consumed: bool = field(default=False, repr=False, compare=False)

    @property
    def digest(self) -> str:
        return digest_object(
            {
                "directive_id": self.directive_id,
                "decision_digest": self.decision_digest,
                "proposal_digest": self.proposal_digest,
                "evidence_set_digest": self.evidence_set_digest,
                "source_p_digest": self.source_p_digest,
                "target_body_version": self.target_body_version,
                "output_role": self.output_role,
                "seed": self.seed,
            }
        )

    @property
    def consumed(self) -> bool:
        return self._consumed

    def validate(
        self,
        decision: PUpdateDecision,
        authority: HDSPUpdateAuthority,
    ) -> tuple[str, ...]:
        failures: list[str] = []
        for name, value in (
            ("ID", self.directive_id),
            ("DECISION_DIGEST", self.decision_digest),
            ("PROPOSAL_DIGEST", self.proposal_digest),
            ("EVIDENCE_SET_DIGEST", self.evidence_set_digest),
            ("SOURCE_P_DIGEST", self.source_p_digest),
            ("TARGET_VERSION", self.target_body_version),
        ):
            if not _text(value):
                failures.append(f"P_COMPILE_DIRECTIVE_{name}_MISSING")
        if self.output_role != "CANDIDATE":
            failures.append("P_COMPILE_DIRECTIVE_OUTPUT_ROLE_INVALID")
        if isinstance(self.seed, bool) or not isinstance(self.seed, int):
            failures.append("P_COMPILE_DIRECTIVE_SEED_INVALID")
        if self._owner is not authority:
            failures.append("P_COMPILE_DIRECTIVE_OWNER_INVALID")
        if not decision.is_owned_by(authority):
            failures.append("P_COMPILE_DECISION_NOT_HDS_OWNED")
        if not decision.allow_p_compile or decision.status != "COMPILE":
            failures.append("P_COMPILE_NOT_AUTHORIZED")
        if self.decision_digest != decision.digest:
            failures.append("P_COMPILE_DECISION_DIGEST_MISMATCH")
        if self.proposal_digest != decision.proposal_digest:
            failures.append("P_COMPILE_PROPOSAL_MISMATCH")
        if self.evidence_set_digest != decision.evidence_set_digest:
            failures.append("P_COMPILE_EVIDENCE_MISMATCH")
        if self._consumed:
            failures.append("P_COMPILE_DIRECTIVE_ALREADY_CONSUMED")
        return tuple(sorted(set(failures)))

    def consume(
        self,
        decision: PUpdateDecision,
        authority: HDSPUpdateAuthority,
    ) -> None:
        failures = self.validate(decision, authority)
        if failures:
            raise AuthorityViolation(";".join(failures))
        self._consumed = True


@dataclass(frozen=True, slots=True)
class CandidatePBundle:
    candidate_id: str
    proposal_digest: str
    compile_directive_digest: str
    target_component: str
    body_version: str
    body_digest: str
    source_body_version: str
    source_body_digest: str
    provenance_digest: str
    manifest_digest: str
    deterministic_rebuild_digest: str
    rollback_target: str
    parameter_digest: str | None = None
    predecessor_parameter_digest: str | None = None
    same_input_predecessor_output_digest: str | None = None
    same_input_candidate_output_digest: str | None = None
    parameter_change_attribution: str | None = None
    runtime_identity_free: bool = True
    lifecycle: str = "CANDIDATE"
    schema_version: str = P_UPDATE_SCHEMA_VERSION

    @property
    def digest(self) -> str:
        return digest_object(self)

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if self.schema_version != P_UPDATE_SCHEMA_VERSION:
            failures.append("P_CANDIDATE_SCHEMA_INVALID")
        for name, value in (
            ("ID", self.candidate_id),
            ("PROPOSAL_DIGEST", self.proposal_digest),
            ("COMPILE_DIRECTIVE_DIGEST", self.compile_directive_digest),
            ("TARGET_COMPONENT", self.target_component),
            ("BODY_VERSION", self.body_version),
            ("BODY_DIGEST", self.body_digest),
            ("SOURCE_BODY_VERSION", self.source_body_version),
            ("SOURCE_BODY_DIGEST", self.source_body_digest),
            ("PROVENANCE_DIGEST", self.provenance_digest),
            ("MANIFEST_DIGEST", self.manifest_digest),
            ("REBUILD_DIGEST", self.deterministic_rebuild_digest),
            ("ROLLBACK_TARGET", self.rollback_target),
        ):
            if not _text(value):
                failures.append(f"P_CANDIDATE_{name}_MISSING")
        if self.runtime_identity_free is not True:
            failures.append("P_CANDIDATE_IDENTITY_FLAG_INVALID")
        if self.lifecycle not in P_BUNDLE_LIFECYCLES:
            failures.append("P_CANDIDATE_LIFECYCLE_INVALID")
        if self.body_version == self.source_body_version:
            failures.append("P_CANDIDATE_VERSION_UNCHANGED")
        if self.body_digest == self.source_body_digest:
            failures.append("P_CANDIDATE_BODY_DIGEST_UNCHANGED")
        if self.target_component in P_B_TARGET_COMPONENTS:
            for name, optional_value in (
                ("PARAMETER_DIGEST", self.parameter_digest),
                (
                    "PREDECESSOR_PARAMETER_DIGEST",
                    self.predecessor_parameter_digest,
                ),
                (
                    "PREDECESSOR_OUTPUT_DIGEST",
                    self.same_input_predecessor_output_digest,
                ),
                (
                    "CANDIDATE_OUTPUT_DIGEST",
                    self.same_input_candidate_output_digest,
                ),
                ("PARAMETER_ATTRIBUTION", self.parameter_change_attribution),
            ):
                if not _text(optional_value):
                    failures.append(f"P_CANDIDATE_P_B_{name}_MISSING")
            if self.parameter_digest == self.predecessor_parameter_digest:
                failures.append("P_CANDIDATE_P_B_PARAMETER_DIGEST_UNCHANGED")
            if (
                self.same_input_candidate_output_digest
                == self.same_input_predecessor_output_digest
            ):
                failures.append("P_CANDIDATE_P_B_SAME_INPUT_OUTPUT_UNCHANGED")
        failures.extend(_identity_failures(self, "P_CANDIDATE"))
        return tuple(sorted(set(failures)))


@dataclass(frozen=True, slots=True)
class PRegressionReport:
    report_id: str
    candidate_bundle_digest: str
    baseline_bundle_digest: str
    target_metric: str
    baseline_target_value: float
    candidate_target_value: float
    stable_regression_delta: float
    holdout_delta: float
    forgetting_measure: float
    maximum_forgetting: float
    schema_digest_provenance_pass: bool
    identity_free_pass: bool
    deterministic_rebuild_pass: bool
    target_improved: bool
    stable_non_regression: bool
    holdout_non_degradation: bool
    catastrophic_forgetting_within_bound: bool
    hds_boundary_pass: bool
    reproducible_pass: bool
    rollback_pass: bool
    evidence_refs: tuple[str, ...]
    schema_version: str = P_UPDATE_SCHEMA_VERSION

    @property
    def digest(self) -> str:
        return digest_object(self)

    @property
    def promotion_failures(self) -> tuple[str, ...]:
        gates = (
            ("SCHEMA_DIGEST_PROVENANCE", self.schema_digest_provenance_pass),
            ("IDENTITY_FREE", self.identity_free_pass),
            ("DETERMINISTIC_REBUILD", self.deterministic_rebuild_pass),
            ("TARGET_IMPROVEMENT", self.target_improved),
            ("STABLE_NON_REGRESSION", self.stable_non_regression),
            ("HOLDOUT_NON_DEGRADATION", self.holdout_non_degradation),
            (
                "CATASTROPHIC_FORGETTING_BOUND",
                self.catastrophic_forgetting_within_bound,
            ),
            ("HDS_BOUNDARY", self.hds_boundary_pass),
            ("REPRODUCIBLE", self.reproducible_pass),
            ("ROLLBACK", self.rollback_pass),
        )
        return tuple(name for name, passed in gates if passed is not True)

    @property
    def promotion_ready(self) -> bool:
        return not self.validate() and not self.promotion_failures

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if self.schema_version != P_UPDATE_SCHEMA_VERSION:
            failures.append("P_REGRESSION_SCHEMA_INVALID")
        for name, value in (
            ("ID", self.report_id),
            ("CANDIDATE_DIGEST", self.candidate_bundle_digest),
            ("BASELINE_DIGEST", self.baseline_bundle_digest),
            ("TARGET_METRIC", self.target_metric),
        ):
            if not _text(value):
                failures.append(f"P_REGRESSION_{name}_MISSING")
        for name, metric_value in (
            ("BASELINE_TARGET", self.baseline_target_value),
            ("CANDIDATE_TARGET", self.candidate_target_value),
            ("STABLE_DELTA", self.stable_regression_delta),
            ("HOLDOUT_DELTA", self.holdout_delta),
            ("FORGETTING", self.forgetting_measure),
            ("MAXIMUM_FORGETTING", self.maximum_forgetting),
        ):
            if not _finite(metric_value):
                failures.append(f"P_REGRESSION_{name}_INVALID")
        if not _texts(self.evidence_refs):
            failures.append("P_REGRESSION_EVIDENCE_INVALID")
        if self.target_improved and not (
            self.candidate_target_value > self.baseline_target_value
        ):
            failures.append("P_REGRESSION_TARGET_IMPROVEMENT_INCONSISTENT")
        if self.stable_non_regression and self.stable_regression_delta < 0.0:
            failures.append("P_REGRESSION_STABLE_DELTA_INCONSISTENT")
        if self.holdout_non_degradation and self.holdout_delta < 0.0:
            failures.append("P_REGRESSION_HOLDOUT_DELTA_INCONSISTENT")
        if (
            self.catastrophic_forgetting_within_bound
            and self.forgetting_measure > self.maximum_forgetting
        ):
            failures.append("P_REGRESSION_FORGETTING_BOUND_INCONSISTENT")
        return tuple(sorted(set(failures)))


@dataclass(slots=True)
class PPromotionDirective:
    directive_id: str
    decision_digest: str
    proposal_digest: str
    candidate_bundle_digest: str
    regression_report_digest: str
    expected_active_bundle_digest: str
    _owner: object = field(repr=False, compare=False)
    _consumed: bool = field(default=False, repr=False, compare=False)

    @property
    def digest(self) -> str:
        return digest_object(
            {
                "directive_id": self.directive_id,
                "decision_digest": self.decision_digest,
                "proposal_digest": self.proposal_digest,
                "candidate_bundle_digest": self.candidate_bundle_digest,
                "regression_report_digest": self.regression_report_digest,
                "expected_active_bundle_digest": (
                    self.expected_active_bundle_digest
                ),
            }
        )

    @property
    def consumed(self) -> bool:
        return self._consumed

    def consume(
        self,
        decision: PUpdateDecision,
        authority: HDSPUpdateAuthority,
    ) -> None:
        failures: list[str] = []
        if self._consumed:
            failures.append("P_PROMOTION_DIRECTIVE_ALREADY_CONSUMED")
        if self._owner is not authority:
            failures.append("P_PROMOTION_DIRECTIVE_OWNER_INVALID")
        if not decision.is_owned_by(authority):
            failures.append("P_PROMOTION_DECISION_NOT_HDS_OWNED")
        if not decision.allow_p_promote or decision.status != "PROMOTE":
            failures.append("P_PROMOTION_NOT_AUTHORIZED")
        if self.decision_digest != decision.digest:
            failures.append("P_PROMOTION_DECISION_DIGEST_MISMATCH")
        if self.proposal_digest != decision.proposal_digest:
            failures.append("P_PROMOTION_PROPOSAL_MISMATCH")
        if self.candidate_bundle_digest != decision.candidate_bundle_digest:
            failures.append("P_PROMOTION_CANDIDATE_MISMATCH")
        if self.regression_report_digest != decision.regression_report_digest:
            failures.append("P_PROMOTION_REGRESSION_MISMATCH")
        if failures:
            raise AuthorityViolation(";".join(sorted(set(failures))))
        self._consumed = True


@dataclass(frozen=True, slots=True)
class PPromotionReceipt:
    receipt_id: str
    directive_digest: str
    decision_digest: str
    proposal_digest: str
    previous_active_bundle_digest: str
    promoted_bundle_digest: str
    previous_stable_bundle_digest: str
    registry_digest: str

    @property
    def digest(self) -> str:
        return digest_object(self)


@dataclass(slots=True)
class PRollbackDirective:
    directive_id: str
    decision_digest: str
    proposal_digest: str
    failed_active_bundle_digest: str
    rollback_bundle_digest: str
    _owner: object = field(repr=False, compare=False)
    _consumed: bool = field(default=False, repr=False, compare=False)

    @property
    def digest(self) -> str:
        return digest_object(
            {
                "directive_id": self.directive_id,
                "decision_digest": self.decision_digest,
                "proposal_digest": self.proposal_digest,
                "failed_active_bundle_digest": self.failed_active_bundle_digest,
                "rollback_bundle_digest": self.rollback_bundle_digest,
            }
        )

    @property
    def consumed(self) -> bool:
        return self._consumed

    def consume(
        self,
        decision: PUpdateDecision,
        authority: HDSPUpdateAuthority,
    ) -> None:
        failures: list[str] = []
        if self._consumed:
            failures.append("P_ROLLBACK_DIRECTIVE_ALREADY_CONSUMED")
        if self._owner is not authority:
            failures.append("P_ROLLBACK_DIRECTIVE_OWNER_INVALID")
        if not decision.is_owned_by(authority):
            failures.append("P_ROLLBACK_DECISION_NOT_HDS_OWNED")
        if not decision.allow_p_rollback or decision.status != "ROLLBACK":
            failures.append("P_ROLLBACK_NOT_AUTHORIZED")
        if self.decision_digest != decision.digest:
            failures.append("P_ROLLBACK_DECISION_DIGEST_MISMATCH")
        if self.proposal_digest != decision.proposal_digest:
            failures.append("P_ROLLBACK_PROPOSAL_MISMATCH")
        if self.failed_active_bundle_digest != decision.candidate_bundle_digest:
            failures.append("P_ROLLBACK_FAILED_BUNDLE_MISMATCH")
        if failures:
            raise AuthorityViolation(";".join(sorted(set(failures))))
        self._consumed = True


@dataclass(frozen=True, slots=True)
class HDSPUpdateAuthority:
    """The only issuer of P compile, promotion, and rollback grants."""

    def decide(
        self,
        proposal: PUpdateProposal,
        *,
        status: str,
        reason_codes: tuple[str, ...],
        evidence_set: PUpdateEvidenceSet | None = None,
        candidate_bundle: CandidatePBundle | None = None,
        regression_report: PRegressionReport | None = None,
    ) -> PUpdateDecision:
        failures = list(proposal.validate())
        if status not in P_UPDATE_DECISION_STATUSES:
            failures.append("P_UPDATE_DECISION_STATUS_INVALID")
        if not _texts(reason_codes):
            failures.append("P_UPDATE_DECISION_REASON_MISSING")
        if evidence_set is not None:
            failures.extend(evidence_set.validate())
            if evidence_set.proposal_digest != proposal.digest:
                failures.append("P_UPDATE_EVIDENCE_PROPOSAL_MISMATCH")
        if candidate_bundle is not None:
            failures.extend(candidate_bundle.validate())
            if candidate_bundle.proposal_digest != proposal.digest:
                failures.append("P_UPDATE_CANDIDATE_PROPOSAL_MISMATCH")
        if regression_report is not None:
            failures.extend(regression_report.validate())
            if candidate_bundle is None:
                failures.append("P_UPDATE_REGRESSION_CANDIDATE_MISSING")
            elif (
                regression_report.candidate_bundle_digest
                != candidate_bundle.digest
            ):
                failures.append("P_UPDATE_REGRESSION_CANDIDATE_MISMATCH")
        if status == "COMPILE" and evidence_set is None:
            failures.append("P_UPDATE_COMPILE_EVIDENCE_REQUIRED")
        if status == "PROMOTE":
            if candidate_bundle is None or regression_report is None:
                failures.append("P_UPDATE_PROMOTION_INPUT_MISSING")
            elif not regression_report.promotion_ready:
                failures.extend(
                    "P_UPDATE_PROMOTION_GATE_FAILED:" + failure
                    for failure in regression_report.promotion_failures
                )
        if status == "ROLLBACK" and candidate_bundle is None:
            failures.append("P_UPDATE_ROLLBACK_BUNDLE_REQUIRED")
        if failures:
            raise ValueError(";".join(sorted(set(failures))))
        seed = {
            "proposal": proposal.digest,
            "status": status,
            "reasons": reason_codes,
            "evidence": evidence_set.digest if evidence_set else None,
            "candidate": candidate_bundle.digest if candidate_bundle else None,
            "regression": regression_report.digest if regression_report else None,
        }
        decision = PUpdateDecision(
            decision_id="p-update-decision:" + digest_object(seed)[:24],
            proposal_digest=proposal.digest,
            status=status,
            reason_codes=reason_codes,
            evidence_set_digest=(
                evidence_set.digest if evidence_set is not None else None
            ),
            candidate_bundle_digest=(
                candidate_bundle.digest if candidate_bundle is not None else None
            ),
            regression_report_digest=(
                regression_report.digest
                if regression_report is not None
                else None
            ),
            allow_p_compile=status == "COMPILE",
            allow_p_promote=status == "PROMOTE",
            allow_p_rollback=status == "ROLLBACK",
            _owner=self,
        )
        decision_failures = decision.validate()
        if decision_failures:
            raise ValueError(";".join(decision_failures))
        return decision

    def issue_compile_directive(
        self,
        proposal: PUpdateProposal,
        evidence_set: PUpdateEvidenceSet,
        decision: PUpdateDecision,
        *,
        target_body_version: str,
        seed: int,
    ) -> InstructionBodyCompileDirective:
        if not decision.is_owned_by(self):
            raise AuthorityViolation("P_COMPILE_DECISION_NOT_HDS_OWNED")
        if (
            decision.status != "COMPILE"
            or not decision.allow_p_compile
            or decision.proposal_digest != proposal.digest
            or decision.evidence_set_digest != evidence_set.digest
        ):
            raise AuthorityViolation("P_COMPILE_DECISION_BINDING_INVALID")
        directive_seed = {
            "decision": decision.digest,
            "proposal": proposal.digest,
            "evidence": evidence_set.digest,
            "source": proposal.source_p_digest,
            "target": target_body_version,
            "seed": seed,
        }
        return InstructionBodyCompileDirective(
            directive_id="p-compile:" + digest_object(directive_seed)[:24],
            decision_digest=decision.digest,
            proposal_digest=proposal.digest,
            evidence_set_digest=evidence_set.digest,
            source_p_digest=proposal.source_p_digest,
            target_body_version=target_body_version,
            output_role="CANDIDATE",
            seed=seed,
            _owner=self,
        )

    def issue_promotion_directive(
        self,
        proposal: PUpdateProposal,
        candidate: CandidatePBundle,
        report: PRegressionReport,
        decision: PUpdateDecision,
        *,
        expected_active_bundle_digest: str,
    ) -> PPromotionDirective:
        if not decision.is_owned_by(self):
            raise AuthorityViolation("P_PROMOTION_DECISION_NOT_HDS_OWNED")
        if (
            decision.status != "PROMOTE"
            or not decision.allow_p_promote
            or decision.proposal_digest != proposal.digest
            or decision.candidate_bundle_digest != candidate.digest
            or decision.regression_report_digest != report.digest
            or not report.promotion_ready
        ):
            raise AuthorityViolation("P_PROMOTION_DECISION_BINDING_INVALID")
        directive_seed = {
            "decision": decision.digest,
            "candidate": candidate.digest,
            "regression": report.digest,
            "active": expected_active_bundle_digest,
        }
        return PPromotionDirective(
            directive_id="p-promote:" + digest_object(directive_seed)[:24],
            decision_digest=decision.digest,
            proposal_digest=proposal.digest,
            candidate_bundle_digest=candidate.digest,
            regression_report_digest=report.digest,
            expected_active_bundle_digest=expected_active_bundle_digest,
            _owner=self,
        )

    def issue_rollback_directive(
        self,
        proposal: PUpdateProposal,
        failed_active: CandidatePBundle,
        decision: PUpdateDecision,
        *,
        rollback_bundle_digest: str,
    ) -> PRollbackDirective:
        if not decision.is_owned_by(self):
            raise AuthorityViolation("P_ROLLBACK_DECISION_NOT_HDS_OWNED")
        if (
            decision.status != "ROLLBACK"
            or not decision.allow_p_rollback
            or decision.proposal_digest != proposal.digest
            or decision.candidate_bundle_digest != failed_active.digest
        ):
            raise AuthorityViolation("P_ROLLBACK_DECISION_BINDING_INVALID")
        directive_seed = {
            "decision": decision.digest,
            "failed": failed_active.digest,
            "rollback": rollback_bundle_digest,
        }
        return PRollbackDirective(
            directive_id="p-rollback:" + digest_object(directive_seed)[:24],
            decision_digest=decision.digest,
            proposal_digest=proposal.digest,
            failed_active_bundle_digest=failed_active.digest,
            rollback_bundle_digest=rollback_bundle_digest,
            _owner=self,
        )


@dataclass(slots=True)
class PBundleLifecycle:
    """Keep active, candidate, and previous-stable P in disjoint slots."""

    active: CandidatePBundle
    previous_stable: CandidatePBundle | None = None
    candidate: CandidatePBundle | None = None
    rejected: tuple[CandidatePBundle, ...] = ()

    @property
    def digest(self) -> str:
        return digest_object(
            {
                "active": self.active,
                "previous_stable": self.previous_stable,
                "candidate": self.candidate,
                "rejected": self.rejected,
            }
        )

    def validate(self) -> tuple[str, ...]:
        failures = list(self.active.validate())
        if self.active.lifecycle != "ACTIVE":
            failures.append("P_REGISTRY_ACTIVE_SLOT_INVALID")
        if self.previous_stable is not None:
            failures.extend(self.previous_stable.validate())
            if self.previous_stable.lifecycle != "PREVIOUS_STABLE":
                failures.append("P_REGISTRY_STABLE_SLOT_INVALID")
        if self.candidate is not None:
            failures.extend(self.candidate.validate())
            if self.candidate.lifecycle != "CANDIDATE":
                failures.append("P_REGISTRY_CANDIDATE_SLOT_INVALID")
        digests = [
            self.active.digest,
            *(
                (self.previous_stable.digest,)
                if self.previous_stable is not None
                else ()
            ),
            *((self.candidate.digest,) if self.candidate is not None else ()),
        ]
        if len(set(digests)) != len(digests):
            failures.append("P_REGISTRY_SLOT_ALIAS")
        return tuple(sorted(set(failures)))

    def stage_candidate(
        self,
        candidate: CandidatePBundle,
        compile_directive: InstructionBodyCompileDirective,
    ) -> None:
        failures = list(candidate.validate())
        if candidate.lifecycle != "CANDIDATE":
            failures.append("P_STAGE_LIFECYCLE_INVALID")
        if not compile_directive.consumed:
            failures.append("P_STAGE_COMPILE_DIRECTIVE_NOT_CONSUMED")
        if candidate.compile_directive_digest != compile_directive.digest:
            failures.append("P_STAGE_COMPILE_DIRECTIVE_MISMATCH")
        if candidate.source_body_digest != self.active.body_digest:
            failures.append("P_STAGE_SOURCE_NOT_ACTIVE")
        if self.candidate is not None:
            failures.append("P_STAGE_CANDIDATE_SLOT_OCCUPIED")
        if failures:
            raise AuthorityViolation(";".join(sorted(set(failures))))
        self.candidate = candidate

    def promote(
        self,
        directive: PPromotionDirective,
        decision: PUpdateDecision,
        report: PRegressionReport,
        authority: HDSPUpdateAuthority,
    ) -> PPromotionReceipt:
        if self.candidate is None:
            raise AuthorityViolation("P_PROMOTION_CANDIDATE_SLOT_EMPTY")
        if directive.expected_active_bundle_digest != self.active.digest:
            raise AuthorityViolation("P_PROMOTION_ACTIVE_COMPARE_AND_SWAP_FAILED")
        if directive.candidate_bundle_digest != self.candidate.digest:
            raise AuthorityViolation("P_PROMOTION_STAGED_CANDIDATE_MISMATCH")
        if report.candidate_bundle_digest != self.candidate.digest:
            raise AuthorityViolation("P_PROMOTION_REPORT_CANDIDATE_MISMATCH")
        if not report.promotion_ready:
            raise AuthorityViolation(
                "P_PROMOTION_GATE_FAILED:" + ",".join(report.promotion_failures)
            )
        directive.consume(decision, authority)
        old_active = self.active
        promoted = replace(self.candidate, lifecycle="ACTIVE")
        stable = replace(old_active, lifecycle="PREVIOUS_STABLE")
        self.active = promoted
        self.previous_stable = stable
        self.candidate = None
        registry_digest = self.digest
        return PPromotionReceipt(
            receipt_id="p-promotion-receipt:"
            + digest_object(
                {
                    "directive": directive.digest,
                    "old": old_active.digest,
                    "new": promoted.digest,
                    "stable": stable.digest,
                    "registry": registry_digest,
                }
            )[:24],
            directive_digest=directive.digest,
            decision_digest=decision.digest,
            proposal_digest=decision.proposal_digest,
            previous_active_bundle_digest=old_active.digest,
            promoted_bundle_digest=promoted.digest,
            previous_stable_bundle_digest=stable.digest,
            registry_digest=registry_digest,
        )

    def rollback(
        self,
        directive: PRollbackDirective,
        decision: PUpdateDecision,
        authority: HDSPUpdateAuthority,
    ) -> CandidatePBundle:
        if self.previous_stable is None:
            raise AuthorityViolation("P_ROLLBACK_STABLE_SLOT_EMPTY")
        if directive.failed_active_bundle_digest != self.active.digest:
            raise AuthorityViolation("P_ROLLBACK_ACTIVE_MISMATCH")
        if directive.rollback_bundle_digest != self.previous_stable.digest:
            raise AuthorityViolation("P_ROLLBACK_STABLE_MISMATCH")
        directive.consume(decision, authority)
        failed = replace(self.active, lifecycle="REJECTED")
        restored = replace(self.previous_stable, lifecycle="ACTIVE")
        self.active = restored
        self.previous_stable = None
        self.rejected = (*self.rejected, failed)
        return restored


__all__ = [
    "CandidatePBundle",
    "HDSPUpdateAuthority",
    "InstructionBodyCompileDirective",
    "P_BUNDLE_LIFECYCLES",
    "P_B_TARGET_COMPONENTS",
    "P_B_UPDATE_TYPES",
    "P_UPDATE_DECISION_STATUSES",
    "P_UPDATE_SCHEMA_VERSION",
    "PBundleLifecycle",
    "PPromotionDirective",
    "PPromotionReceipt",
    "PRegressionReport",
    "PRollbackDirective",
    "PUpdateDecision",
    "PUpdateEvidenceSet",
    "PUpdateProposal",
    "parameter_digest",
]
