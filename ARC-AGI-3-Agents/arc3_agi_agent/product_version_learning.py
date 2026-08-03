"""Fail-closed runtime-M to next-version initial-state candidate boundary."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final, Sequence

from .causal_record import causal_record_from_semantic, is_typed_causal_record
from .generic_memory import SemanticRecord
from .initial_state_compiler import InitialStateBundle, InitialStateCompiler
from .schema import digest_object

PRODUCT_VERSION_LEARNING_VERSION: Final = "arc3-product-version-learning-v1"
PRODUCT_VERSION_MIN_DISTINCT_RUN_SUPPORT: Final = 3
PRODUCT_VERSION_CANDIDATE_DECISIONS: Final = frozenset(
    {"HOLD_RUNTIME_M", "PROMOTE_TO_VERSION_CANDIDATE"}
)


@dataclass(frozen=True, slots=True)
class ProductVersionLearningAssessment:
    source_record_ids: tuple[str, ...]
    eligible_record_ids: tuple[str, ...]
    rejected_records: tuple[tuple[str, tuple[str, ...]], ...]
    required_distinct_run_support: int
    contradiction_test_passed: bool
    deletion_test_passed: bool
    focused_regression_passed: bool
    decision: str
    reasons: tuple[str, ...]
    assessment_digest: str

    @property
    def candidate_record_count(self) -> int:
        return (
            len(self.eligible_record_ids)
            if self.decision == ("PROMOTE_TO_VERSION_CANDIDATE")
            else 0
        )

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if self.source_record_ids != tuple(sorted(set(self.source_record_ids))):
            failures.append("VERSION_LEARNING_SOURCE_IDS_INVALID")
        if self.eligible_record_ids != tuple(sorted(set(self.eligible_record_ids))):
            failures.append("VERSION_LEARNING_ELIGIBLE_IDS_INVALID")
        rejected_ids = tuple(item[0] for item in self.rejected_records)
        if rejected_ids != tuple(sorted(set(rejected_ids))):
            failures.append("VERSION_LEARNING_REJECTED_IDS_INVALID")
        if any(
            not reasons or reasons != tuple(sorted(set(reasons)))
            for _, reasons in self.rejected_records
        ):
            failures.append("VERSION_LEARNING_REJECTION_REASON_INVALID")
        if set(self.eligible_record_ids) & set(rejected_ids):
            failures.append("VERSION_LEARNING_RECORD_PARTITION_OVERLAP")
        if set(self.source_record_ids) != set(self.eligible_record_ids) | set(
            rejected_ids
        ):
            failures.append("VERSION_LEARNING_RECORD_PARTITION_INCOMPLETE")
        if self.required_distinct_run_support < 3:
            failures.append("VERSION_LEARNING_RUN_THRESHOLD_TOO_LOW")
        if self.decision not in PRODUCT_VERSION_CANDIDATE_DECISIONS:
            failures.append("VERSION_LEARNING_DECISION_INVALID")
        gates_passed = all(
            (
                self.contradiction_test_passed,
                self.deletion_test_passed,
                self.focused_regression_passed,
            )
        )
        expected_decision = (
            "PROMOTE_TO_VERSION_CANDIDATE"
            if self.eligible_record_ids and gates_passed
            else "HOLD_RUNTIME_M"
        )
        if self.decision != expected_decision:
            failures.append("VERSION_LEARNING_DECISION_INCONSISTENT")
        if not self.reasons or self.reasons != tuple(sorted(set(self.reasons))):
            failures.append("VERSION_LEARNING_REASONS_INVALID")
        expected_digest = "product-version-learning-assessment:" + digest_object(
            {
                "source_record_ids": self.source_record_ids,
                "eligible_record_ids": self.eligible_record_ids,
                "rejected_records": self.rejected_records,
                "required_distinct_run_support": (self.required_distinct_run_support),
                "contradiction_test_passed": self.contradiction_test_passed,
                "deletion_test_passed": self.deletion_test_passed,
                "focused_regression_passed": self.focused_regression_passed,
                "decision": self.decision,
                "reasons": self.reasons,
            }
        )
        if self.assessment_digest != expected_digest:
            failures.append("VERSION_LEARNING_ASSESSMENT_DIGEST_INVALID")
        return tuple(sorted(set(failures)))


@dataclass(frozen=True, slots=True)
class ProductVersionLearningGate:
    min_distinct_run_support: int = PRODUCT_VERSION_MIN_DISTINCT_RUN_SUPPORT
    version: str = PRODUCT_VERSION_LEARNING_VERSION

    def assess(
        self,
        records: Sequence[SemanticRecord],
        *,
        contradiction_test_passed: bool,
        deletion_test_passed: bool,
        focused_regression_passed: bool,
    ) -> ProductVersionLearningAssessment:
        by_id = {record.memory_id: record for record in records}
        source_ids = tuple(sorted(by_id))
        eligible: list[str] = []
        rejected: list[tuple[str, tuple[str, ...]]] = []
        for record_id in source_ids:
            record = by_id[record_id]
            reasons: list[str] = []
            if not is_typed_causal_record(record):
                reasons.append("TYPED_CAUSAL_RECORD_REQUIRED")
            else:
                try:
                    causal = causal_record_from_semantic(record)
                except (KeyError, TypeError, ValueError):
                    reasons.append("CAUSAL_SCHEMA_OR_POLICY_INVALID")
                else:
                    if causal.scope_class != "SESSION_GLOBAL":
                        reasons.append("SESSION_GLOBAL_SCOPE_REQUIRED")
                    if causal.state != "ACTIVE":
                        reasons.append("ACTIVE_RUNTIME_M_REQUIRED")
                    if causal.support_count < self.min_distinct_run_support:
                        reasons.append("TOTAL_SUPPORT_INSUFFICIENT")
                    if causal.distinct_episode_support < (
                        self.min_distinct_run_support
                    ):
                        reasons.append("DISTINCT_RUN_SUPPORT_INSUFFICIENT")
                    if causal.contradiction_count != 0:
                        reasons.append("CONTRADICTION_PRESENT")
                    if causal.hazard_count != 0:
                        reasons.append("HAZARD_PRESENT")
                    if causal.execute_eligibility is not True:
                        reasons.append("EXECUTE_ELIGIBILITY_REQUIRED")
            if reasons:
                rejected.append((record_id, tuple(sorted(set(reasons)))))
            else:
                eligible.append(record_id)
        gate_reasons: list[str] = []
        if not eligible:
            gate_reasons.append("NO_STABLE_MULTI_RUN_RECORD")
        if not contradiction_test_passed:
            gate_reasons.append("CONTRADICTION_TEST_REQUIRED")
        if not deletion_test_passed:
            gate_reasons.append("DELETION_TEST_REQUIRED")
        if not focused_regression_passed:
            gate_reasons.append("FOCUSED_REGRESSION_REQUIRED")
        if not gate_reasons:
            gate_reasons.append("VERSION_CANDIDATE_GATES_PASSED")
        decision = (
            "PROMOTE_TO_VERSION_CANDIDATE"
            if eligible
            and contradiction_test_passed
            and deletion_test_passed
            and focused_regression_passed
            else "HOLD_RUNTIME_M"
        )
        payload = {
            "source_record_ids": source_ids,
            "eligible_record_ids": tuple(eligible),
            "rejected_records": tuple(rejected),
            "required_distinct_run_support": self.min_distinct_run_support,
            "contradiction_test_passed": contradiction_test_passed,
            "deletion_test_passed": deletion_test_passed,
            "focused_regression_passed": focused_regression_passed,
            "decision": decision,
            "reasons": tuple(sorted(set(gate_reasons))),
        }
        assessment = ProductVersionLearningAssessment(
            source_record_ids=source_ids,
            eligible_record_ids=tuple(eligible),
            rejected_records=tuple(rejected),
            required_distinct_run_support=self.min_distinct_run_support,
            contradiction_test_passed=contradiction_test_passed,
            deletion_test_passed=deletion_test_passed,
            focused_regression_passed=focused_regression_passed,
            decision=decision,
            reasons=tuple(sorted(set(gate_reasons))),
            assessment_digest="product-version-learning-assessment:"
            + digest_object(payload),
        )
        failures = assessment.validate()
        if failures:
            raise ValueError(";".join(failures))
        return assessment

    def compile_candidate(
        self,
        *,
        parent: InitialStateBundle,
        records: Sequence[SemanticRecord],
        assessment: ProductVersionLearningAssessment,
        target_version: str,
    ) -> InitialStateBundle:
        failures = assessment.validate()
        if failures:
            raise ValueError(";".join(failures))
        if assessment.decision != "PROMOTE_TO_VERSION_CANDIDATE":
            raise PermissionError("VERSION_LEARNING_CANDIDATE_GATE_REQUIRED")
        by_id = {record.memory_id: record for record in records}
        if not set(assessment.eligible_record_ids).issubset(by_id):
            raise PermissionError("VERSION_LEARNING_EVIDENCE_BINDING_INVALID")
        selected = tuple(by_id[item] for item in assessment.eligible_record_ids)
        reassessed = self.assess(
            selected,
            contradiction_test_passed=assessment.contradiction_test_passed,
            deletion_test_passed=assessment.deletion_test_passed,
            focused_regression_passed=assessment.focused_regression_passed,
        )
        if (
            reassessed.decision != "PROMOTE_TO_VERSION_CANDIDATE"
            or reassessed.eligible_record_ids != assessment.eligible_record_ids
        ):
            raise PermissionError("VERSION_LEARNING_EVIDENCE_RECHECK_FAILED")
        merged = {record.memory_id: record for record in parent.m0}
        merged.update({record.memory_id: record for record in selected})
        candidate = InitialStateCompiler(adapter_digest=parent.adapter_digest).compile(
            p_bundle=parent.p_bundle,
            j0=parent.j0,
            memory_records=tuple(merged.values()),
            version=target_version,
        )
        if candidate.p_bundle.logical_digest() != parent.p_bundle.logical_digest():
            raise RuntimeError("VERSION_LEARNING_PARENT_P_CHANGED")
        if candidate.j0 != parent.j0:
            raise RuntimeError("VERSION_LEARNING_PARENT_J0_CHANGED")
        if not set(assessment.eligible_record_ids).issubset(
            {record.memory_id for record in candidate.m0}
        ):
            raise RuntimeError("VERSION_LEARNING_CANDIDATE_M0_MISSING")
        return candidate


__all__ = [
    "PRODUCT_VERSION_CANDIDATE_DECISIONS",
    "PRODUCT_VERSION_LEARNING_VERSION",
    "PRODUCT_VERSION_MIN_DISTINCT_RUN_SUPPORT",
    "ProductVersionLearningAssessment",
    "ProductVersionLearningGate",
]
