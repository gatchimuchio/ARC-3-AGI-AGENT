from __future__ import annotations

import hashlib
import json
from dataclasses import replace
from pathlib import Path

import pytest

from arc3_agi_agent.generic_compute import (
    ParametricRelationalInstructionBody,
)
from arc3_agi_agent.generic_env import MechanismWorld
from arc3_agi_agent.generic_hds import HDSConfiguration
from arc3_agi_agent.generic_memory import SemanticRecord, semantic_record
from arc3_agi_agent.generic_runtime import GenericAGIRuntime
from arc3_agi_agent.generic_session import (
    ResourceContract,
    create_cognitive_session,
)
from arc3_agi_agent.initial_state_compiler import (
    InitialStateCompiler,
    initial_state_from_package,
    restart_from_initial_state_package,
)
from arc3_agi_agent.p_bundle import (
    PBundle,
    p_bundle_from_package,
)
from arc3_agi_agent.p_compiler_v2 import (
    EvidenceSelectionManifest,
    PCompilerV2,
    evidence_selection_manifest,
)
from arc3_agi_agent.p_evaluator import (
    IsolatedPBundleEvaluator,
    PBundleEvaluation,
    PVersionMetric,
)
from arc3_agi_agent.p_ir_abi import L0_ABI_VERSION
from arc3_agi_agent.p_ir_validator import validate_p_ir_program
from arc3_agi_agent.p_registry import PRegistry, PRegistryAuthority


def _evidence(*, contaminated: bool = False) -> SemanticRecord:
    payload = {
        "support_count": 3,
        "contradiction_count": 0,
        "hazard_count": 0,
    }
    if contaminated:
        payload["game_id"] = "game-identity-forbidden"
    return semantic_record(
        memory_id="causal:normalized-progress",
        kind="ACTION_EFFECT",
        statement="A normalized action relation causes rendered progress.",
        semantic_tokens=(
            "goal:progress",
            "shape:block",
            "surface:0:untargeted",
        ),
        relations=("relation:actor-near-target",),
        evidence=("event:independent-support",),
        counter_evidence=("counter:none-observed",),
        scope=("SESSION_GLOBAL",),
        falsification_condition=(
            "independent repetition contradicts the predicted effect"
        ),
        state="ACTIVE",
        payload=payload,
    )


def _compiled() -> tuple[
    PCompilerV2,
    PBundle,
    EvidenceSelectionManifest,
    PBundle,
    PBundle,
    PBundle,
]:
    compiler = PCompilerV2()
    active = compiler.bootstrap(
        body=ParametricRelationalInstructionBody(),
    )
    record = _evidence()
    manifest = evidence_selection_manifest(
        parent=active,
        records=(record,),
        ledger_event_digests=("ledger:event:0001",),
    )
    symbolic = compiler.compile_symbolic(
        parent=active,
        records=(record,),
        evidence_manifest=manifest,
        target_version="p-symbolic-v2",
    )
    parametric = compiler.compile_parametric(
        parent=active,
        records=(record,),
        evidence_manifest=manifest,
        target_version="p-parametric-v2",
    )
    hybrid = compiler.compile_hybrid(
        parent=active,
        records=(record,),
        evidence_manifest=manifest,
        target_version="p-hybrid-v2",
    )
    return compiler, active, manifest, symbolic, parametric, hybrid


def _metrics(
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


def _passing_evaluation(
    active: PBundle,
    candidate: PBundle,
) -> PBundleEvaluation:
    return IsolatedPBundleEvaluator().evaluate(
        baseline_bundle=active,
        candidate_bundle=candidate,
        baseline_metric=_metrics(
            completed_environments=2,
            completed_levels=4,
            true_progress=10,
            actions=20,
        ),
        candidate_metric=_metrics(
            completed_environments=3,
            completed_levels=5,
            true_progress=12,
            actions=22,
        ),
        dataset_role="DEVELOPMENT_VALIDATION",
        known_regression_non_degrading=True,
    )


def test_compile_symbolic_p_ir() -> None:
    _, _, _, symbolic, _, _ = _compiled()

    assert symbolic.compiler_report.mode == "SYMBOLIC"
    assert symbolic.body.format_id() == "generic-symbolic-relational"
    assert symbolic.tensors == ()
    assert validate_p_ir_program(symbolic.program) == ()
    assert symbolic.manifest.lifecycle == "CANDIDATE"


def test_compile_parametric_tensors() -> None:
    _, _, _, _, parametric, _ = _compiled()

    assert parametric.compiler_report.mode == "PARAMETRIC"
    assert parametric.tensors
    assert all(item.dtype == "ppm_i64" for item in parametric.tensors)
    assert tuple(item.name for item in parametric.tensors) == tuple(
        sorted(item.name for item in parametric.tensors)
    )
    assert p_bundle_from_package(parametric.package_bytes()) == parametric


def test_compile_hybrid_bundle() -> None:
    _, _, _, _, _, hybrid = _compiled()

    assert hybrid.compiler_report.mode == "HYBRID"
    assert hybrid.body.format_id() == "generic-hybrid-relational"
    assert hybrid.compiler_report.compiled_targets == tuple(
        sorted(hybrid.compiler_report.compiled_targets)
    )
    assert hybrid.validate() == ()


def test_candidate_isolated_from_active() -> None:
    _, active, _, _, _, hybrid = _compiled()
    before = active.package_bytes()

    assert active.manifest.lifecycle == "ACTIVE"
    assert hybrid.manifest.parent_logical_digest == active.logical_digest()
    assert hybrid.logical_digest() != active.logical_digest()
    assert active.package_bytes() == before


def test_same_l0_p_swap() -> None:
    _, active, _, _, _, hybrid = _compiled()
    reports = []
    for bundle in (active, hybrid):
        session = create_cognitive_session(
            p_bundle=bundle.body,
            p_ir_program=bundle.program,
            resource_contract=ResourceContract(action_budget_per_episode=4),
        )
        runtime = GenericAGIRuntime(
            MechanismWorld((11, 29), (0,), required_progress=1),
            session,
            session.begin_episode(),
        )
        reports.append(runtime.run())

    first = reports[0].cycles[0].compute_result
    second = reports[1].cycles[0].compute_result
    assert first.l0_abi_version == second.l0_abi_version == L0_ABI_VERSION
    assert first.p_ir_logical_digest != second.p_ir_logical_digest
    assert reports[0].final_state == reports[1].final_state == "WIN"


def test_evidence_manifest_complete() -> None:
    compiler, active, manifest, _, _, _ = _compiled()
    incomplete = replace(manifest, selected_record_digests=("wrong",))

    assert manifest.validate() == ()
    assert manifest.selected_ledger_event_digests == ("ledger:event:0001",)
    with pytest.raises(
        PermissionError,
        match="P_COMPILER_EVIDENCE_DIGESTS_INCOMPLETE",
    ):
        compiler.compile_hybrid(
            parent=active,
            records=(_evidence(),),
            evidence_manifest=incomplete,
            target_version="p-invalid-v2",
        )


def test_identity_taint_rejected() -> None:
    compiler, active, _, _, _, _ = _compiled()
    contaminated = _evidence(contaminated=True)
    manifest = evidence_selection_manifest(
        parent=active,
        records=(contaminated,),
    )

    with pytest.raises(PermissionError, match="P_COMPILER_IDENTITY_TAINT"):
        compiler.compile_hybrid(
            parent=active,
            records=(contaminated,),
            evidence_manifest=manifest,
            target_version="p-contaminated-v2",
        )


def test_known_regression_non_degrading() -> None:
    _, active, _, _, _, hybrid = _compiled()
    evaluation = _passing_evaluation(active, hybrid)

    assert evaluation.known_regression_non_degrading is True
    assert evaluation.dev_validation_improved is True
    assert evaluation.passed() is True


def test_dev_validation_completion_first() -> None:
    _, active, _, _, _, hybrid = _compiled()
    evaluator = IsolatedPBundleEvaluator()
    baseline = _metrics(
        completed_environments=2,
        completed_levels=4,
        true_progress=10,
        actions=20,
    )
    fewer_completions = evaluator.evaluate(
        baseline_bundle=active,
        candidate_bundle=hybrid,
        baseline_metric=baseline,
        candidate_metric=_metrics(
            completed_environments=1,
            completed_levels=100,
            true_progress=1_000,
            actions=1,
        ),
        dataset_role="DEVELOPMENT_VALIDATION",
        known_regression_non_degrading=False,
    )
    more_completions = evaluator.evaluate(
        baseline_bundle=active,
        candidate_bundle=hybrid,
        baseline_metric=baseline,
        candidate_metric=_metrics(
            completed_environments=3,
            completed_levels=4,
            true_progress=10,
            actions=200,
        ),
        dataset_role="DEVELOPMENT_VALIDATION",
        known_regression_non_degrading=True,
    )

    assert fewer_completions.dev_validation_improved is False
    assert more_completions.dev_validation_improved is True
    with pytest.raises(PermissionError, match="P_EVALUATOR_ROLE_FORBIDDEN"):
        evaluator.evaluate(
            baseline_bundle=active,
            candidate_bundle=hybrid,
            baseline_metric=baseline,
            candidate_metric=baseline,
            dataset_role="LOCKED_FINAL",
            known_regression_non_degrading=True,
        )


def test_promotion() -> None:
    _, active, _, _, _, hybrid = _compiled()
    evaluation = _passing_evaluation(active, hybrid)
    authority = PRegistryAuthority()
    registry = PRegistry(active)
    registry.stage_candidate(hybrid)
    authorization = authority.authorize_promotion(
        active=registry.active,
        candidate=hybrid,
        evaluation=evaluation,
    )

    promoted = registry.promote(
        candidate_digest=hybrid.logical_digest(),
        evaluation=evaluation,
        authorization=authorization,
        authority=authority,
    )

    assert promoted.manifest.lifecycle == "ACTIVE"
    assert registry.active.logical_digest() == hybrid.logical_digest()
    assert registry.previous_stable[-1].logical_digest() == active.logical_digest()
    assert registry.lineage[-1].operation == "PROMOTE"


def test_rollback() -> None:
    _, active, _, _, _, hybrid = _compiled()
    evaluation = _passing_evaluation(active, hybrid)
    authority = PRegistryAuthority()
    registry = PRegistry(active)
    registry.stage_candidate(hybrid)
    promotion = authority.authorize_promotion(
        active=active,
        candidate=hybrid,
        evaluation=evaluation,
    )
    registry.promote(
        candidate_digest=hybrid.logical_digest(),
        evaluation=evaluation,
        authorization=promotion,
        authority=authority,
    )
    rollback = authority.authorize_rollback(
        active=registry.active,
        rollback_target=registry.previous_stable[-1],
        reason="independent falsifier observed",
    )

    restored = registry.rollback(
        authorization=rollback,
        authority=authority,
    )

    assert restored.logical_digest() == active.logical_digest()
    assert registry.rejected[-1].logical_digest() == hybrid.logical_digest()
    assert registry.lineage[-1].operation == "ROLLBACK"


def test_restart_from_promoted_initial_state() -> None:
    _, active, _, _, _, hybrid = _compiled()
    evaluation = _passing_evaluation(active, hybrid)
    authority = PRegistryAuthority()
    registry = PRegistry(active)
    registry.stage_candidate(hybrid)
    authorization = authority.authorize_promotion(
        active=active,
        candidate=hybrid,
        evaluation=evaluation,
    )
    promoted = registry.promote(
        candidate_digest=hybrid.logical_digest(),
        evaluation=evaluation,
        authorization=authorization,
        authority=authority,
    )
    initial = InitialStateCompiler().compile(
        p_bundle=promoted,
        j0=HDSConfiguration(),
        memory_records=(_evidence(),),
        version="initial-state-v2",
    )
    payload = initial.package_bytes()

    restored = initial_state_from_package(payload)
    session = restart_from_initial_state_package(payload)

    assert restored == initial
    assert restored.package_bytes() == payload
    assert session.p_bundle.program_logical_digest == (
        promoted.manifest.program_logical_digest
    )
    assert any(
        item.memory_id == _evidence().memory_id
        for item in session.memory.view().active
    )


def test_bundle_byte_reproducibility() -> None:
    _, _, _, _, _, hybrid = _compiled()
    first = hybrid.package_bytes()
    second = hybrid.package_bytes()
    restored = p_bundle_from_package(first)

    assert first == second
    assert restored.package_bytes() == first
    assert restored.logical_digest() == hybrid.logical_digest()
    assert restored.physical_digest() == hybrid.physical_digest()


def test_p20b_phase_state_is_content_bound() -> None:
    root = Path(__file__).resolve().parents[3]
    path = root / "control" / "p20b" / "P20B_PHASE_STATE.json"
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
    assert data["metrics"]["compiler_semantics_versioned"] is True
    assert data["metrics"]["identity_leak_count"] == 0
