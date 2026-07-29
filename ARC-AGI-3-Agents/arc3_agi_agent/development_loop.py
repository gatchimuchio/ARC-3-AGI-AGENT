"""Governed train/validation candidate loop with one active runtime."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final, Sequence

from .evaluation_registry import EvaluationRegistry
from .generic_hds import HDSConfiguration
from .generic_memory import SemanticRecord
from .initial_state_compiler import InitialStateBundle, InitialStateCompiler
from .p_bundle import PBundle
from .p_compiler_v2 import PCompilerV2, evidence_selection_manifest
from .p_evaluator import (
    IsolatedPBundleEvaluator,
    PBundleEvaluation,
    PVersionMetric,
)
from .p_registry import PRegistry, PRegistryAuthority
from .runtime_identity import build_runtime_identity
from .schema import digest_object
from .version_lineage import (
    CodeUpdateManifest,
    MemorySchemaMigration,
    VersionLineage,
)

DEVELOPMENT_LOOP_VERSION: Final = "arc3-governed-development-loop-v1"
DEVELOPMENT_TRIGGERS: Final = frozenset(
    {
        "MANUAL",
        "EVIDENCE_THRESHOLD",
        "PHASE_END",
        "FAILURE_CLUSTER",
        "PLATEAU",
        "DEV_VALIDATION_REGRESSION",
    }
)


@dataclass(frozen=True, slots=True)
class DevelopmentRunReport:
    run_id: str
    trigger: str
    train_access_event_digests: tuple[str, ...]
    validation_access_event_digests: tuple[str, ...]
    failure_cluster_digest: str
    m_dev_digest: str
    parent_p_logical_digest: str
    candidate_p_logical_digest: str
    evaluation_digest: str
    decision: str
    active_p_logical_digest: str
    active_runtime_identity_digest: str
    active_initial_state_logical_digest: str
    code_regression_passed: bool
    fallback_count: int
    closed: bool

    def digest(self) -> str:
        return "development-run-report:" + digest_object(self)


@dataclass(slots=True)
class GovernedDevelopmentLoop:
    evaluation_registry: EvaluationRegistry
    p_registry: PRegistry
    p_authority: PRegistryAuthority
    version_lineage: VersionLineage
    active_initial_state: InitialStateBundle
    hds_configuration: HDSConfiguration
    memory_schema_version: str
    m_dev_records: dict[str, SemanticRecord]
    compiler: PCompilerV2 = field(default_factory=PCompilerV2)
    evaluator: IsolatedPBundleEvaluator = field(
        default_factory=IsolatedPBundleEvaluator
    )
    _runs: list[DevelopmentRunReport] = field(
        default_factory=list,
        repr=False,
    )

    @classmethod
    def bootstrap(
        cls,
        *,
        evaluation_registry: EvaluationRegistry,
        active_p: PBundle,
        hds_configuration: HDSConfiguration,
        memory_records: Sequence[SemanticRecord],
        version_id: str,
        code_commit: str,
        memory_schema_version: str = "arc3-semantic-memory-v1",
    ) -> GovernedDevelopmentLoop:
        initial_state = InitialStateCompiler().compile(
            p_bundle=active_p,
            j0=hds_configuration,
            memory_records=memory_records,
            version=version_id,
        )
        runtime_identity = build_runtime_identity(
            p_bundle=active_p.body,
            p_ir_program=active_p.program,
            hds_configuration=hds_configuration,
            initial_memory_records=initial_state.m0,
        )
        lineage = VersionLineage.bootstrap(
            version_id=version_id,
            runtime_identity=runtime_identity,
            initial_state_logical_digest=initial_state.logical_digest,
            p_logical_digest=active_p.logical_digest(),
            code_commit=code_commit,
            memory_schema_version=memory_schema_version,
        )
        return cls(
            evaluation_registry=evaluation_registry,
            p_registry=PRegistry(active_p),
            p_authority=PRegistryAuthority(),
            version_lineage=lineage,
            active_initial_state=initial_state,
            hds_configuration=hds_configuration,
            memory_schema_version=memory_schema_version,
            m_dev_records={
                item.memory_id: item for item in memory_records
            },
        )

    @property
    def runs(self) -> tuple[DevelopmentRunReport, ...]:
        return tuple(self._runs)

    @property
    def active_runtime_count(self) -> int:
        return self.version_lineage.active_runtime_count

    @property
    def fallback_count(self) -> int:
        return 0

    @property
    def development_loop_closed(self) -> bool:
        return bool(self._runs) and all(item.closed for item in self._runs)

    @property
    def m_dev_digest(self) -> str:
        return "m-dev:" + digest_object(
            tuple(
                self.m_dev_records[key]
                for key in sorted(self.m_dev_records)
            )
        )

    def request_legacy_fallback(self, reason: str) -> None:
        if not reason:
            raise ValueError("DEVELOPMENT_LOOP_FALLBACK_REASON_REQUIRED")
        raise PermissionError("DEVELOPMENT_LOOP_FALLBACK_FORBIDDEN")

    def invariant_failures(self) -> tuple[str, ...]:
        failures = list(self.version_lineage.validate())
        active_version = self.version_lineage.active
        active_p_digest = self.p_registry.active.logical_digest()
        if active_version.p_logical_digest != active_p_digest:
            failures.append("DEVELOPMENT_LOOP_ACTIVE_P_LINEAGE_MISMATCH")
        if (
            self.active_initial_state.p_bundle.logical_digest()
            != active_p_digest
        ):
            failures.append("DEVELOPMENT_LOOP_INITIAL_P_MISMATCH")
        if (
            self.active_initial_state.logical_digest
            != active_version.initial_state_logical_digest
        ):
            failures.append("DEVELOPMENT_LOOP_INITIAL_LINEAGE_MISMATCH")
        if self.active_initial_state.j0 != self.hds_configuration:
            failures.append("DEVELOPMENT_LOOP_J0_MISMATCH")
        if self.active_runtime_count != 1:
            failures.append("DEVELOPMENT_LOOP_ACTIVE_RUNTIME_COUNT_INVALID")
        return tuple(sorted(set(failures)))

    def _report(
        self,
        *,
        trigger: str,
        train_access_event_digests: tuple[str, ...],
        validation_access_event_digests: tuple[str, ...],
        failure_cluster_digest: str,
        parent_p_logical_digest: str,
        candidate_p_logical_digest: str,
        evaluation: PBundleEvaluation,
        decision: str,
        code_regression_passed: bool,
    ) -> DevelopmentRunReport:
        report = DevelopmentRunReport(
            run_id="development-run:"
            + digest_object(
                {
                    "ordinal": len(self._runs),
                    "trigger": trigger,
                    "candidate": candidate_p_logical_digest,
                    "evaluation": evaluation.digest(),
                }
            )[:32],
            trigger=trigger,
            train_access_event_digests=train_access_event_digests,
            validation_access_event_digests=(
                validation_access_event_digests
            ),
            failure_cluster_digest=failure_cluster_digest,
            m_dev_digest=self.m_dev_digest,
            parent_p_logical_digest=parent_p_logical_digest,
            candidate_p_logical_digest=candidate_p_logical_digest,
            evaluation_digest=evaluation.digest(),
            decision=decision,
            active_p_logical_digest=self.p_registry.active.logical_digest(),
            active_runtime_identity_digest=(
                self.version_lineage.active.runtime_identity_digest
            ),
            active_initial_state_logical_digest=(
                self.active_initial_state.logical_digest
            ),
            code_regression_passed=code_regression_passed,
            fallback_count=self.fallback_count,
            closed=True,
        )
        self._runs.append(report)
        return report

    def run_iteration(
        self,
        *,
        trigger: str,
        train_dataset_id: str,
        validation_dataset_id: str,
        records: Sequence[SemanticRecord],
        baseline_metric: PVersionMetric,
        candidate_metric: PVersionMetric,
        target_version: str,
        external_code_commit: str,
        known_regression_non_degrading: bool,
        full_code_regression_passed: bool,
        candidate_hds_configuration: HDSConfiguration | None = None,
        candidate_memory_records: Sequence[SemanticRecord] | None = None,
        target_memory_schema_version: str | None = None,
        memory_migration: MemorySchemaMigration | None = None,
    ) -> DevelopmentRunReport:
        if trigger not in DEVELOPMENT_TRIGGERS:
            raise PermissionError("DEVELOPMENT_LOOP_TRIGGER_FORBIDDEN")
        if not records:
            raise ValueError("DEVELOPMENT_LOOP_TRAIN_RECORDS_REQUIRED")
        for record in records:
            failures = record.validate()
            if failures:
                raise ValueError(";".join(failures))
        parent = self.p_registry.active
        active_version = self.version_lineage.active
        train_grants = tuple(
            self.evaluation_registry.request_access(
                dataset_id=train_dataset_id,
                purpose=purpose,
                actor_scope="DEVELOPMENT_LOOP",
                runtime_identity_digest=(
                    active_version.runtime_identity_digest
                ),
                artifact_digest=self.active_initial_state.logical_digest,
            )
            for purpose in (
                "TRAIN_RUN",
                "M_DEV_UPDATE",
                "FAILURE_CLUSTER",
                "CANDIDATE_COMPILE",
            )
        )
        for grant in train_grants:
            self.evaluation_registry.require_development_trigger(grant)
        for record in records:
            self.m_dev_records[record.memory_id] = record
        failure_cluster_digest = "failure-cluster:" + digest_object(
            tuple(
                sorted(
                    (
                        item.memory_id,
                        item.citation().content_digest,
                    )
                    for item in records
                )
            )
        )
        evidence_manifest = evidence_selection_manifest(
            parent=parent,
            records=records,
            ledger_event_digests=tuple(
                item.access_event_digest for item in train_grants
            ),
            manifest_id="development-loop-evidence:" + target_version,
        )
        candidate = self.compiler.compile_hybrid(
            parent=parent,
            records=records,
            evidence_manifest=evidence_manifest,
            target_version=target_version,
        )
        self.p_registry.stage_candidate(candidate)
        evaluation_grant = self.evaluation_registry.request_access(
            dataset_id=validation_dataset_id,
            purpose="CANDIDATE_EVALUATION",
            actor_scope="DEVELOPMENT_LOOP",
            runtime_identity_digest=active_version.runtime_identity_digest,
            artifact_digest=candidate.logical_digest(),
        )
        self.evaluation_registry.require_development_trigger(
            evaluation_grant
        )
        evaluation = self.evaluator.evaluate(
            baseline_bundle=parent,
            candidate_bundle=candidate,
            baseline_metric=baseline_metric,
            candidate_metric=candidate_metric,
            dataset_role=evaluation_grant.role,
            known_regression_non_degrading=(
                known_regression_non_degrading
            ),
        )
        decision_grant = self.evaluation_registry.request_access(
            dataset_id=validation_dataset_id,
            purpose="PROMOTION_DECISION",
            actor_scope="DEVELOPMENT_LOOP",
            runtime_identity_digest=active_version.runtime_identity_digest,
            artifact_digest=candidate.logical_digest(),
        )
        self.evaluation_registry.require_development_trigger(decision_grant)
        validation_event_digests = (
            evaluation_grant.access_event_digest,
            decision_grant.access_event_digest,
        )
        if not evaluation.passed():
            authorization = self.p_authority.authorize_rejection(
                active=parent,
                candidate=candidate,
                evaluation=evaluation,
                reason="development validation gates failed",
            )
            self.p_registry.reject_candidate(
                candidate_digest=candidate.logical_digest(),
                evaluation=evaluation,
                authorization=authorization,
                authority=self.p_authority,
            )
            return self._report(
                trigger=trigger,
                train_access_event_digests=tuple(
                    item.access_event_digest for item in train_grants
                ),
                validation_access_event_digests=validation_event_digests,
                failure_cluster_digest=failure_cluster_digest,
                parent_p_logical_digest=parent.logical_digest(),
                candidate_p_logical_digest=candidate.logical_digest(),
                evaluation=evaluation,
                decision="REJECT",
                code_regression_passed=False,
            )
        promotion = self.p_authority.authorize_promotion(
            active=parent,
            candidate=candidate,
            evaluation=evaluation,
        )
        promoted = self.p_registry.promote(
            candidate_digest=candidate.logical_digest(),
            evaluation=evaluation,
            authorization=promotion,
            authority=self.p_authority,
        )
        selected_hds = (
            candidate_hds_configuration or self.hds_configuration
        )
        selected_memory = tuple(
            candidate_memory_records
            or (
                self.m_dev_records[key]
                for key in sorted(self.m_dev_records)
            )
        )
        try:
            next_initial_state = InitialStateCompiler().compile(
                p_bundle=promoted,
                j0=selected_hds,
                memory_records=selected_memory,
                version=target_version,
            )
            if not full_code_regression_passed:
                rollback = self.p_authority.authorize_rollback(
                    active=promoted,
                    rollback_target=self.p_registry.previous_stable[-1],
                    reason="full code regression failed",
                )
                self.p_registry.rollback(
                    authorization=rollback,
                    authority=self.p_authority,
                )
                return self._report(
                    trigger=trigger,
                    train_access_event_digests=tuple(
                        item.access_event_digest for item in train_grants
                    ),
                    validation_access_event_digests=(
                        validation_event_digests
                    ),
                    failure_cluster_digest=failure_cluster_digest,
                    parent_p_logical_digest=parent.logical_digest(),
                    candidate_p_logical_digest=candidate.logical_digest(),
                    evaluation=evaluation,
                    decision="ROLLBACK",
                    code_regression_passed=False,
                )
            next_identity = build_runtime_identity(
                p_bundle=promoted.body,
                p_ir_program=promoted.program,
                hds_configuration=selected_hds,
                initial_memory_records=next_initial_state.m0,
            )
            next_memory_schema = (
                target_memory_schema_version or self.memory_schema_version
            )
            abi_changed = (
                active_version.l0_abi_version
                != next_identity.l0_abi_version
            )
            code_update = CodeUpdateManifest(
                external_commit=external_code_commit,
                source_tree_digest=next_identity.code_tree_digest,
                from_l0_abi_version=active_version.l0_abi_version,
                to_l0_abi_version=next_identity.l0_abi_version,
                p_migration_disposition=(
                    "MIGRATED" if abi_changed else "NOT_REQUIRED"
                ),
                migrated_p_logical_digest=(
                    promoted.logical_digest() if abi_changed else ""
                ),
                full_regression_passed=True,
            )
            self.version_lineage.append_successor(
                version_id=target_version,
                runtime_identity=next_identity,
                initial_state_logical_digest=(
                    next_initial_state.logical_digest
                ),
                p_logical_digest=promoted.logical_digest(),
                memory_schema_version=next_memory_schema,
                code_update=code_update,
                memory_migration=memory_migration,
            )
        except Exception:
            if self.p_registry.active.logical_digest() == (
                promoted.logical_digest()
            ):
                rollback = self.p_authority.authorize_rollback(
                    active=promoted,
                    rollback_target=self.p_registry.previous_stable[-1],
                    reason="post-promotion transition failed",
                )
                self.p_registry.rollback(
                    authorization=rollback,
                    authority=self.p_authority,
                )
            raise
        self.active_initial_state = next_initial_state
        self.hds_configuration = selected_hds
        self.memory_schema_version = next_memory_schema
        return self._report(
            trigger=trigger,
            train_access_event_digests=tuple(
                item.access_event_digest for item in train_grants
            ),
            validation_access_event_digests=validation_event_digests,
            failure_cluster_digest=failure_cluster_digest,
            parent_p_logical_digest=parent.logical_digest(),
            candidate_p_logical_digest=candidate.logical_digest(),
            evaluation=evaluation,
            decision="PROMOTE",
            code_regression_passed=True,
        )

    def metrics(self) -> dict[str, object]:
        return {
            "data_access_violation_count": (
                self.evaluation_registry.ledger.data_access_violation_count
            ),
            "locked_final_access_count": (
                self.evaluation_registry.ledger.locked_final_access_count
            ),
            "version_lineage": (
                "PASS" if not self.invariant_failures() else "FAIL"
            ),
            "active_runtime_count": self.active_runtime_count,
            "development_loop_closed": self.development_loop_closed,
            "fallback_count": self.fallback_count,
            "m_dev_digest": self.m_dev_digest,
        }


__all__ = [
    "DEVELOPMENT_LOOP_VERSION",
    "DEVELOPMENT_TRIGGERS",
    "DevelopmentRunReport",
    "GovernedDevelopmentLoop",
]
