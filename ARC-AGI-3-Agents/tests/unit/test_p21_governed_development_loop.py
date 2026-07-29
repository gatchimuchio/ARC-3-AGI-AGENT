from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from arc3_agi_agent.development_loop import GovernedDevelopmentLoop
from arc3_agi_agent.evaluation_registry import EvaluationRegistry
from arc3_agi_agent.generic_compute import (
    ParametricRelationalInstructionBody,
)
from arc3_agi_agent.generic_hds import HDSConfiguration
from arc3_agi_agent.generic_memory import SemanticRecord, semantic_record
from arc3_agi_agent.p_compiler_v2 import PCompilerV2
from arc3_agi_agent.p_evaluator import PVersionMetric
from arc3_agi_agent.runtime_identity import RuntimeIdentity
from arc3_agi_agent.version_lineage import (
    CodeUpdateManifest,
    MemorySchemaMigration,
    VersionLineage,
)


def _record() -> SemanticRecord:
    return semantic_record(
        memory_id="causal:normalized-progress-p21",
        kind="ACTION_EFFECT",
        statement="A normalized relation causes rendered progress.",
        semantic_tokens=(
            "goal:progress",
            "shape:block",
            "surface:0:untargeted",
        ),
        relations=("relation:actor-near-target",),
        evidence=("event:independent-development-support",),
        counter_evidence=("counter:none-observed",),
        scope=("SESSION_GLOBAL",),
        falsification_condition=(
            "independent repetition contradicts the predicted effect"
        ),
        state="ACTIVE",
        payload={
            "support_count": 4,
            "contradiction_count": 0,
            "hazard_count": 0,
        },
    )


def _metric(
    *,
    completed_environments: int,
    completed_levels: int,
    true_progress: int,
    actions: int,
) -> PVersionMetric:
    return PVersionMetric(
        completed_environments=completed_environments,
        completed_levels=completed_levels,
        true_progress=true_progress,
        crashes=0,
        invalid_actions=0,
        identity_leaks=0,
        actions=actions,
        memory_cost=8,
        resource_cost=100,
    )


def _identity(label: str, *, abi: str = "arc3-l0-abi-v1") -> RuntimeIdentity:
    return RuntimeIdentity(
        code_tree_digest="sha256:code-" + label,
        l0_abi_version=abi,
        p_logical_digest="p-runtime-logical:" + label,
        j_implementation_digest="sha256:j-" + label,
        j_config_digest="j0:" + label,
        m0_logical_digest="m0:" + label,
        adapter_digest="sha256:adapter-" + label,
        dependency_lock_digest="sha256:lock-" + label,
    )


def _code_update(
    label: str,
    *,
    from_abi: str = "arc3-l0-abi-v1",
    to_abi: str = "arc3-l0-abi-v1",
    disposition: str = "NOT_REQUIRED",
    migrated_p: str = "",
) -> CodeUpdateManifest:
    digit = {"v2": "2", "v3": "3", "abi": "a", "memory": "b"}[label]
    source_label = {
        "v2": "v2",
        "v3": "v3",
        "abi": "abi-v2",
        "memory": "memory-v2",
    }[label]
    return CodeUpdateManifest(
        external_commit=digit * 40,
        source_tree_digest="sha256:code-" + source_label,
        from_l0_abi_version=from_abi,
        to_l0_abi_version=to_abi,
        p_migration_disposition=disposition,
        migrated_p_logical_digest=migrated_p,
        full_regression_passed=True,
    )


def _evaluation_registry() -> EvaluationRegistry:
    registry = EvaluationRegistry()
    registry.register_dataset(
        dataset_id="development-train-public",
        dataset_digest="sha256:development-train",
        owner="development-owner",
        role="DEVELOPMENT_TRAIN",
    )
    registry.register_dataset(
        dataset_id="development-validation-public",
        dataset_digest="sha256:development-validation",
        owner="validation-owner",
        role="DEVELOPMENT_VALIDATION",
    )
    registry.register_dataset(
        dataset_id="cv-holdout-procedure",
        dataset_digest="sha256:cv-holdout",
        owner="cv-owner",
        role="CV_HOLDOUT",
    )
    registry.register_dataset(
        dataset_id="locked-final-rev2",
        dataset_digest="sha256:locked-final-contract-only",
        owner="sealed-owner",
        role="LOCKED_FINAL",
        access_state="FROZEN_UNACCESSED",
    )
    return registry


def _loop() -> GovernedDevelopmentLoop:
    active = PCompilerV2().bootstrap(
        body=ParametricRelationalInstructionBody(),
        version="p21-runtime-v1",
    )
    return GovernedDevelopmentLoop.bootstrap(
        evaluation_registry=_evaluation_registry(),
        active_p=active,
        hds_configuration=HDSConfiguration(),
        memory_records=(_record(),),
        version_id="runtime-v1",
        code_commit="1" * 40,
    )


def _run_iteration(
    loop: GovernedDevelopmentLoop,
    *,
    improving: bool,
    target_version: str = "runtime-v2",
    external_code_commit: str = "2" * 40,
) -> object:
    return loop.run_iteration(
        trigger="FAILURE_CLUSTER",
        train_dataset_id="development-train-public",
        validation_dataset_id="development-validation-public",
        records=(_record(),),
        baseline_metric=_metric(
            completed_environments=2,
            completed_levels=4,
            true_progress=10,
            actions=20,
        ),
        candidate_metric=_metric(
            completed_environments=3 if improving else 1,
            completed_levels=5 if improving else 100,
            true_progress=12 if improving else 1_000,
            actions=22 if improving else 1,
        ),
        target_version=target_version,
        external_code_commit=external_code_commit,
        known_regression_non_degrading=improving,
        full_code_regression_passed=True,
    )


def _lineage() -> VersionLineage:
    return VersionLineage.bootstrap(
        version_id="runtime-v1",
        runtime_identity=_identity("v1"),
        initial_state_logical_digest="initial-state:v1",
        p_logical_digest="p:v1",
        code_commit="1" * 40,
        memory_schema_version="memory-schema-v1",
    )


def test_dataset_role_access_control() -> None:
    registry = _evaluation_registry()
    train = registry.request_access(
        dataset_id="development-train-public",
        purpose="TRAIN_RUN",
        actor_scope="DEVELOPMENT_LOOP",
        runtime_identity_digest="runtime:active",
        artifact_digest="artifact:active",
    )
    validation = registry.request_access(
        dataset_id="development-validation-public",
        purpose="CANDIDATE_EVALUATION",
        actor_scope="DEVELOPMENT_LOOP",
        runtime_identity_digest="runtime:active",
        artifact_digest="artifact:candidate",
    )

    registry.require_development_trigger(train)
    registry.require_development_trigger(validation)
    with pytest.raises(PermissionError, match="EVALUATION_ACCESS_REJECTED"):
        registry.request_access(
            dataset_id="cv-holdout-procedure",
            purpose="TRAIN_RUN",
            actor_scope="DEVELOPMENT_LOOP",
            runtime_identity_digest="runtime:active",
            artifact_digest="artifact:active",
        )
    assert registry.ledger.data_access_violation_count == 0
    assert registry.ledger.denied_request_count == 1
    assert registry.ledger.validate_chain() == ()


def test_locked_final_access_rejected() -> None:
    registry = _evaluation_registry()

    with pytest.raises(PermissionError, match="EVALUATION_ACCESS_REJECTED"):
        registry.request_access(
            dataset_id="locked-final-rev2",
            purpose="TRAIN_RUN",
            actor_scope="DEVELOPMENT_LOOP",
            runtime_identity_digest="runtime:active",
            artifact_digest="artifact:active",
        )

    assert registry.ledger.locked_final_access_count == 0
    assert registry.ledger.data_access_violation_count == 0
    locked = next(
        item
        for item in registry.datasets
        if item.dataset_id == "locked-final-rev2"
    )
    assert locked.access_state == "FROZEN_UNACCESSED"
    assert locked.execution_count == 0


def test_cv_artifacts_are_distinct() -> None:
    registry = _evaluation_registry()
    first = registry.register_cv_artifact(
        fold_id="fold-1",
        dataset_id="cv-holdout-procedure",
        p_logical_digest="p:cv-fold-1",
        initial_state_logical_digest="initial:cv-fold-1",
        runtime_identity=_identity("cv-fold-1"),
    )
    second = registry.register_cv_artifact(
        fold_id="fold-2",
        dataset_id="cv-holdout-procedure",
        p_logical_digest="p:cv-fold-2",
        initial_state_logical_digest="initial:cv-fold-2",
        runtime_identity=_identity("cv-fold-2"),
    )

    assert first.artifact_digest != second.artifact_digest
    assert first.p_logical_digest != second.p_logical_digest
    assert first.runtime_identity_digest != second.runtime_identity_digest


def test_cv_not_counted_as_same_runtime() -> None:
    registry = _evaluation_registry()
    for ordinal in (1, 2, 3):
        registry.register_cv_artifact(
            fold_id=f"fold-{ordinal}",
            dataset_id="cv-holdout-procedure",
            p_logical_digest=f"p:cv-fold-{ordinal}",
            initial_state_logical_digest=f"initial:cv-fold-{ordinal}",
            runtime_identity=_identity(f"cv-fold-{ordinal}"),
        )

    summary = registry.cv_procedure_summary()
    assert summary.fold_count == 3
    assert summary.distinct_p_artifact_count == 3
    assert summary.distinct_runtime_identity_count == 3
    assert summary.allowed_claim == "CV_PROCEDURE_EVIDENCE"
    assert summary.same_single_artifact_claim_allowed is False


def test_three_version_lineage() -> None:
    lineage = _lineage()
    lineage.append_successor(
        version_id="runtime-v2",
        runtime_identity=_identity("v2"),
        initial_state_logical_digest="initial-state:v2",
        p_logical_digest="p:v2",
        memory_schema_version="memory-schema-v1",
        code_update=_code_update("v2"),
    )
    lineage.append_successor(
        version_id="runtime-v3",
        runtime_identity=_identity("v3"),
        initial_state_logical_digest="initial-state:v3",
        p_logical_digest="p:v3",
        memory_schema_version="memory-schema-v1",
        code_update=_code_update("v3"),
    )

    assert tuple(item.version_id for item in lineage.versions) == (
        "runtime-v1",
        "runtime-v2",
        "runtime-v3",
    )
    assert tuple(item.parent_version_id for item in lineage.versions) == (
        None,
        "runtime-v1",
        "runtime-v2",
    )
    assert lineage.active.version_id == "runtime-v3"
    assert lineage.active_runtime_count == 1
    assert lineage.validate() == ()


def test_code_abi_migration() -> None:
    lineage = _lineage()
    abi_v2 = "arc3-l0-abi-v2"
    target = _identity("abi-v2", abi=abi_v2)

    with pytest.raises(
        ValueError,
        match="VERSION_LINEAGE_ABI_MIGRATION_REQUIRED",
    ):
        lineage.append_successor(
            version_id="runtime-abi-v2",
            runtime_identity=target,
            initial_state_logical_digest="initial-state:abi-v2",
            p_logical_digest="p:abi-v2",
            memory_schema_version="memory-schema-v1",
            code_update=replace(
                _code_update("abi"),
                to_l0_abi_version=abi_v2,
            ),
        )
    migrated = lineage.append_successor(
        version_id="runtime-abi-v2",
        runtime_identity=target,
        initial_state_logical_digest="initial-state:abi-v2",
        p_logical_digest="p:abi-v2",
        memory_schema_version="memory-schema-v1",
        code_update=_code_update(
            "abi",
            to_abi=abi_v2,
            disposition="MIGRATED",
            migrated_p="p:abi-v2",
        ),
    )

    assert migrated.l0_abi_version == abi_v2
    assert lineage.active == migrated
    assert lineage.active_runtime_count == 1


def test_memory_schema_migration() -> None:
    lineage = _lineage()
    target = _identity("memory-v2")
    update = _code_update("memory")

    with pytest.raises(
        PermissionError,
        match="MEMORY_SCHEMA_MIGRATION_REQUIRED",
    ):
        lineage.append_successor(
            version_id="runtime-memory-v2",
            runtime_identity=target,
            initial_state_logical_digest="initial-state:memory-v2",
            p_logical_digest="p:memory-v2",
            memory_schema_version="memory-schema-v2",
            code_update=update,
        )
    migrated = lineage.append_successor(
        version_id="runtime-memory-v2",
        runtime_identity=target,
        initial_state_logical_digest="initial-state:memory-v2",
        p_logical_digest="p:memory-v2",
        memory_schema_version="memory-schema-v2",
        code_update=update,
        memory_migration=MemorySchemaMigration(
            migration_id="memory-v1-to-v2",
            from_schema_version="memory-schema-v1",
            to_schema_version="memory-schema-v2",
            deterministic=True,
            full_regression_passed=True,
        ),
    )

    assert migrated.memory_schema_version == "memory-schema-v2"
    assert lineage.active_runtime_count == 1


def test_rejected_candidate_preserves_active() -> None:
    loop = _loop()
    before_p = loop.p_registry.active.logical_digest()
    before_runtime = loop.version_lineage.active.runtime_identity_digest

    report = _run_iteration(loop, improving=False)

    assert getattr(report, "decision") == "REJECT"
    assert loop.p_registry.active.logical_digest() == before_p
    assert loop.version_lineage.active.runtime_identity_digest == before_runtime
    assert loop.p_registry.candidates == {}
    assert len(loop.p_registry.rejected) == 1
    assert loop.active_runtime_count == 1


def test_active_runtime_count_one() -> None:
    loop = _loop()

    report = _run_iteration(loop, improving=True)

    assert getattr(report, "decision") == "PROMOTE"
    assert loop.active_runtime_count == 1
    assert loop.version_lineage.active.version_id == "runtime-v2"
    assert tuple(
        item.status for item in loop.version_lineage.versions
    ) == ("PREVIOUS_STABLE", "ACTIVE")
    metrics = loop.metrics()
    assert metrics == {
        "data_access_violation_count": 0,
        "locked_final_access_count": 0,
        "version_lineage": "PASS",
        "active_runtime_count": 1,
        "development_loop_closed": True,
        "fallback_count": 0,
        "m_dev_digest": loop.m_dev_digest,
    }
    assert tuple(
        item.purpose for item in loop.evaluation_registry.ledger.events
    ) == (
        "TRAIN_RUN",
        "M_DEV_UPDATE",
        "FAILURE_CLUSTER",
        "CANDIDATE_COMPILE",
        "CANDIDATE_EVALUATION",
        "PROMOTION_DECISION",
    )


def test_no_s5_fallback() -> None:
    loop = _loop()

    with pytest.raises(
        PermissionError,
        match="DEVELOPMENT_LOOP_FALLBACK_FORBIDDEN",
    ):
        loop.request_legacy_fallback("candidate regression")

    assert loop.fallback_count == 0
    assert loop.active_runtime_count == 1


def test_transition_failure_rolls_back_active() -> None:
    loop = _loop()
    before_p = loop.p_registry.active.logical_digest()
    before_runtime = loop.version_lineage.active.runtime_identity_digest

    with pytest.raises(
        ValueError,
        match="VERSION_LINEAGE_EXTERNAL_COMMIT_INVALID",
    ):
        _run_iteration(
            loop,
            improving=True,
            external_code_commit="not-a-commit",
        )

    assert loop.p_registry.active.logical_digest() == before_p
    assert loop.version_lineage.active.runtime_identity_digest == before_runtime
    assert loop.active_runtime_count == 1
    assert loop.p_registry.candidates == {}
    assert loop.p_registry.lineage[-1].operation == "ROLLBACK"


def test_p21_phase_state_is_content_bound() -> None:
    root = Path(__file__).resolve().parents[3]
    path = root / "control" / "p21" / "P21_PHASE_STATE.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    expected_digest = data.pop("content_digest")
    actual_digest = hashlib.sha256(
        json.dumps(
            data,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    ).hexdigest()

    assert expected_digest == actual_digest
    assert data["status"] == "PASS"
    assert data["failed_requirement_ids"] == []
    assert set(data["gates"].values()) == {"PASS"}
    assert data["metrics"]["data_access_violation_count"] == 0
    assert data["metrics"]["locked_final_access_count"] == 0
    assert data["metrics"]["active_runtime_count"] == 1
    assert data["metrics"]["fallback_count"] == 0
