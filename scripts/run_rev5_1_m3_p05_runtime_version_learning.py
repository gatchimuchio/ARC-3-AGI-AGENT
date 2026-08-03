#!/usr/bin/env python3
"""Execute and seal rev5.1 runtime-M and version-learning separation."""

from __future__ import annotations

import argparse
import hashlib
import json
import secrets
import sys
from dataclasses import asdict, replace
from functools import lru_cache
from pathlib import Path
from typing import Final, Sequence, cast
from unittest.mock import patch

REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[1]
PACKAGE_ROOT: Final = REPOSITORY_ROOT / "ARC-AGI-3-Agents"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from arc3_agi_agent.causal_record import (  # noqa: E402
    CausalRecord,
    causal_record,
    causal_record_from_semantic,
    is_typed_causal_record,
)
from arc3_agi_agent.evidence_policy import evidence_group  # noqa: E402
from arc3_agi_agent.generic_env import MechanismWorld  # noqa: E402
from arc3_agi_agent.generic_memory import (  # noqa: E402
    MemoryMutationProposal,
    SemanticRecord,
)
from arc3_agi_agent.generic_runtime import GenericAGIRuntime  # noqa: E402
from arc3_agi_agent.generic_session import (  # noqa: E402
    CognitiveSession,
    ResourceContract,
    create_cognitive_session,
)
from arc3_agi_agent.initial_state_compiler import (  # noqa: E402
    InitialStateBundle,
    initial_state_from_package,
    restart_from_initial_state_package,
)
from arc3_agi_agent.negative_transfer import (  # noqa: E402
    assess_negative_transfer,
    invalidation_proposal,
)
from arc3_agi_agent.product_capability import (  # noqa: E402
    load_product_initial_state,
)
from arc3_agi_agent.product_runner import create_product_session  # noqa: E402
from arc3_agi_agent.product_version_learning import (  # noqa: E402
    ProductVersionLearningAssessment,
    ProductVersionLearningGate,
)
from arc3_agi_agent.runtime_identity import build_runtime_identity  # noqa: E402
from arc3_agi_agent.schema import digest_object  # noqa: E402

OUTPUT_PATH: Final = Path(
    "analysis/product/rev5_1/m3_p05_runtime_version_learning.json"
)
CANDIDATE_PACKAGE_PATH: Final = Path(
    "analysis/product/rev5_1/m3_p05_next_initial_state_candidate.zip"
)
BUNDLE_PATH: Final = Path(
    "ARC-AGI-3-Agents/arc3_agi_agent/bundles/arc3_product_initial_state_v1.json"
)
BUNDLE_PACKAGE_PATH: Final = Path(
    "ARC-AGI-3-Agents/arc3_agi_agent/bundles/arc3_product_initial_state_v1.zip"
)
P04_PATH: Final = Path(
    "analysis/product/rev5_1/m3_p04_applicability_counterfactual.json"
)
VERSION_GATE_SOURCE_PATH: Final = Path(
    "ARC-AGI-3-Agents/arc3_agi_agent/product_version_learning.py"
)
CONSOLIDATION_SOURCE_PATH: Final = Path(
    "ARC-AGI-3-Agents/arc3_agi_agent/memory_consolidation.py"
)
NEGATIVE_TRANSFER_SOURCE_PATH: Final = Path(
    "ARC-AGI-3-Agents/arc3_agi_agent/negative_transfer.py"
)
INITIAL_STATE_SOURCE_PATH: Final = Path(
    "ARC-AGI-3-Agents/arc3_agi_agent/initial_state_compiler.py"
)
ACTION_SURFACE: Final = (11, 29)
WINNING_ORDINALS: Final = (0,)
ACTION_BUDGET: Final = 6
TARGET_VERSION: Final = "arc3-product-initial-state-v1-m3-p05-candidate"


class _DeterministicNonceSource:
    """Reproducible independent nonces for this isolated audit only."""

    def __init__(self) -> None:
        self._ordinal = 0

    def __call__(self, nbytes: int = 24) -> str:
        self._ordinal += 1
        width = nbytes * 2
        return f"{self._ordinal:0{width}x}"[-width:]


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical_json(value: object) -> bytes:
    return json.dumps(
        value,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")


def _encoded(value: object) -> bytes:
    return (
        json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    ).encode("utf-8")


def _require(condition: bool, failure: str) -> None:
    if not condition:
        raise RuntimeError(failure)


def _world() -> MechanismWorld:
    return MechanismWorld(
        ACTION_SURFACE,
        WINNING_ORDINALS,
        required_progress=1,
        max_turns=ACTION_BUDGET,
    )


def _typed_records(records: Sequence[SemanticRecord]) -> tuple[SemanticRecord, ...]:
    return tuple(
        sorted(
            (record for record in records if is_typed_causal_record(record)),
            key=lambda record: record.memory_id,
        )
    )


def _typed_summary(records: Sequence[SemanticRecord]) -> list[dict[str, object]]:
    output: list[dict[str, object]] = []
    for record in _typed_records(records):
        typed = causal_record_from_semantic(record)
        output.append(
            {
                "record_id": typed.record_id,
                "kind": typed.kind,
                "state": typed.state,
                "support_count": typed.support_count,
                "distinct_run_support": typed.distinct_episode_support,
                "contradiction_count": typed.contradiction_count,
                "hazard_count": typed.hazard_count,
                "no_effect_count": typed.no_effect_count,
                "execute_eligibility": typed.execute_eligibility,
            }
        )
    return output


def _active_memory_digest(session: CognitiveSession) -> str:
    return "active-memory:" + digest_object(session.memory.view().active)


def _action_sequence(report: object) -> list[int]:
    cycles = getattr(report, "cycles")
    return [
        cycle.selected_candidate.descriptor.action_id
        for cycle in cycles
        if cycle.selected_candidate is not None
    ]


def _run_training_episode(
    session: CognitiveSession,
    *,
    ordinal: int,
) -> tuple[dict[str, object], tuple[SemanticRecord, ...]]:
    world = _world()
    before_version = session.memory.version
    handle = session.begin_episode()
    report = GenericAGIRuntime(world, session, handle).run()
    _require(report.final_state == "WIN", "M3_P05_TRAINING_EPISODE_NOT_WIN")
    _require(bool(report.cycles), "M3_P05_TRAINING_CYCLE_MISSING")
    _require(
        all(
            cycle.decision.memory_update_authorized
            and cycle.decision.external_action_authorized
            for cycle in report.cycles
        ),
        "M3_P05_RUNTIME_J_AUTHORIZATION_MISSING",
    )
    receipt = session.end_episode(
        handle,
        succeeded=True,
        reason=report.stop_reason,
    )
    after_records = session.memory.view().active
    summary = {
        "run_ordinal": ordinal,
        "final_state": report.final_state,
        "stop_reason": report.stop_reason,
        "action_sequence": _action_sequence(report),
        "action_count": report.actions_executed,
        "outcome_sequence": [
            cycle.attribution.category
            for cycle in report.cycles
            if cycle.attribution is not None
        ],
        "all_external_actions_J_authorized": True,
        "all_runtime_M_updates_J_authorized": True,
        "memory_version_before": before_version,
        "memory_version_after": session.memory.version,
        "runtime_M_changed": session.memory.version > before_version,
        "episode_overlay_consolidated": receipt.promoted,
        "version_candidate_created": False,
        "global_causal_records": _typed_summary(after_records),
    }
    return summary, _typed_records(after_records)


def _isolated_run(
    initial: InitialStateBundle,
    *,
    initial_memory_records: tuple[SemanticRecord, ...],
) -> dict[str, object]:
    session = create_cognitive_session(
        p_bundle=initial.p_bundle.body,
        p_ir_program=initial.p_bundle.program,
        mode="VALIDATION",
        hds_configuration=initial.j0,
        initial_memory_records=initial_memory_records,
        resource_contract=ResourceContract(action_budget_per_episode=ACTION_BUDGET),
    )
    world = _world()
    observation = world.observe()
    handle = session.begin_episode()
    report = GenericAGIRuntime(world, session, handle).run()
    actions = _action_sequence(report)
    all_authorized = all(
        cycle.decision.external_action_authorized for cycle in report.cycles
    )
    session.end_episode(
        handle,
        succeeded=report.final_state == "WIN",
        reason=report.stop_reason,
    )
    return {
        "observation_digest": observation.digest(),
        "final_state": report.final_state,
        "stop_reason": report.stop_reason,
        "action_sequence": actions,
        "action_count": report.actions_executed,
        "first_action": actions[0] if actions else None,
        "all_external_actions_J_authorized": all_authorized,
    }


def _restart_run(payload: bytes) -> dict[str, object]:
    session = restart_from_initial_state_package(payload, mode="VALIDATION")
    world = _world()
    observation = world.observe()
    handle = session.begin_episode()
    report = GenericAGIRuntime(world, session, handle).run()
    actions = _action_sequence(report)
    memory_citation_ids = sorted(
        {
            citation.memory_id
            for cycle in report.cycles
            for citation in cycle.compute_result.memory_citations
        }
    )
    plan_memory_refs = sorted(
        {
            ref
            for cycle in report.cycles
            if cycle.selected_candidate is not None
            for ref in cycle.selected_candidate.plan.memory_refs
        }
    )
    typed_memory_binding_refs = sorted(
        {
            ref
            for cycle in report.cycles
            if cycle.selected_candidate is not None
            for ref in cycle.selected_candidate.typed_provenance.memory_binding_refs
        }
    )
    execute_eligible_binding_count = sum(
        binding.execute_eligible
        for cycle in report.cycles
        if cycle.selected_candidate is not None
        for binding in cycle.selected_candidate.evidence_bindings
    )
    session.end_episode(
        handle,
        succeeded=report.final_state == "WIN",
        reason=report.stop_reason,
    )
    return {
        "observation_digest": observation.digest(),
        "final_state": report.final_state,
        "stop_reason": report.stop_reason,
        "action_sequence": actions,
        "action_count": report.actions_executed,
        "first_action": actions[0] if actions else None,
        "memory_citation_ids": memory_citation_ids,
        "plan_memory_refs": plan_memory_refs,
        "typed_memory_binding_refs": typed_memory_binding_refs,
        "execute_eligible_binding_count": execute_eligible_binding_count,
        "fresh_CognitiveSession": True,
        "mutable_training_memory_reused": False,
        "loaded_from_compiled_initial_state_package": True,
    }


def _false_learning_record(stable: CausalRecord) -> SemanticRecord:
    binding = replace(
        stable.binding_key,
        action_relation_digest="action-relation:m3-p05-false-learning",
    )
    groups = (
        evidence_group(
            outcome="SUPPORT",
            normalized_before_pattern_digest=(binding.normalized_state_pattern_digest),
            action_relation_digest=binding.action_relation_digest,
            normalized_after_effect_digest="normalized-effect:false-support",
            delay_min_steps=0,
            delay_max_steps=0,
            episode_nonce="m3-p05-false-support-run",
            event_ids=("m3-p05:false-support-event",),
        ),
        evidence_group(
            outcome="CONTRADICTION",
            normalized_before_pattern_digest=(binding.normalized_state_pattern_digest),
            action_relation_digest=binding.action_relation_digest,
            normalized_after_effect_digest=("normalized-effect:false-contradiction"),
            delay_min_steps=0,
            delay_max_steps=0,
            episode_nonce="m3-p05-false-contradiction-run",
            event_ids=("m3-p05:false-contradiction-event",),
        ),
    )
    return causal_record(
        kind="ACTION_EFFECT",
        binding_key=binding,
        scope_class="SESSION_GLOBAL",
        statement=(
            "A deliberately contradicted relation used only to verify invalidation."
        ),
        semantic_tokens=("m3-p05:false-learning", "surface:false:untargeted"),
        relations=("action-relation:false-learning",),
        applicability_predicates=("current-legal-action",),
        evidence_groups=groups,
        falsification_condition=(
            "independent contradiction invalidates the deliberately false relation"
        ),
    ).to_semantic_record()


def _false_learning_audit(
    session: CognitiveSession,
    stable_record: SemanticRecord,
) -> dict[str, object]:
    world = _world()
    handle = session.begin_episode()
    report = GenericAGIRuntime(world, session, handle).run()
    _require(report.final_state == "WIN", "M3_P05_FALSE_PROBE_RUNTIME_FAILED")
    decision = report.cycles[-1].decision
    _require(
        decision.memory_update_authorized,
        "M3_P05_FALSE_PROBE_MEMORY_NOT_AUTHORIZED",
    )
    rollback_version = session.memory.version
    rollback_digest = _active_memory_digest(session)
    false_record = _false_learning_record(causal_record_from_semantic(stable_record))
    add_proposal = MemoryMutationProposal(
        operation="ADD",
        target_id=false_record.memory_id,
        record=false_record,
        evidence=("m3-p05-controlled-false-learning-injection",),
        counter_evidence=("m3-p05-independent-contradiction",),
        scope=("M3_P05_FALSE_LEARNING_TEST", "SESSION_GLOBAL"),
        falsification_condition=false_record.falsification_condition,
        reason="inject contradicted learning solely for invalidation audit",
    )
    add_authorization = session.hds.authorize_memory(
        decision,
        add_proposal,
        memory_version=session.memory.version,
    )
    add_receipt = session.executor.execute_memory(
        session.memory,
        add_proposal,
        add_authorization,
    )
    _require(
        false_record.memory_id
        in {record.memory_id for record in session.memory.view().active},
        "M3_P05_FALSE_RECORD_ADD_FAILED",
    )
    assessment = assess_negative_transfer(false_record)
    _require(
        assessment.decision == "INVALIDATE",
        "M3_P05_FALSE_RECORD_NOT_INVALIDATED",
    )
    invalidate = invalidation_proposal(false_record, assessment)
    invalidate_authorization = session.hds.authorize_memory(
        decision,
        invalidate,
        memory_version=session.memory.version,
    )
    invalidate_receipt = session.executor.execute_memory(
        session.memory,
        invalidate,
        invalidate_authorization,
    )
    invalidated = next(
        (
            record
            for record in session.memory.view().active
            if record.memory_id == false_record.memory_id
        ),
        None,
    )
    invalidated_suspended = (
        invalidated is not None
        and invalidated.state == "SUSPENDED"
        and causal_record_from_semantic(invalidated).execute_eligibility is False
    )
    rollback = MemoryMutationProposal(
        operation="ROLLBACK",
        target_id="m3-p05-false-learning-rollback",
        record=None,
        evidence=(invalidate_receipt.event_digest,),
        counter_evidence=assessment.reasons,
        scope=("M3_P05_FALSE_LEARNING_TEST",),
        falsification_condition="the pre-injection memory version is unavailable",
        reason="restore the exact pre-injection runtime-M image",
        rollback_version=rollback_version,
    )
    rollback_authorization = session.hds.authorize_overlay_discard(
        rollback,
        memory_version=session.memory.version,
    )
    rollback_receipt = session.executor.execute_memory(
        session.memory,
        rollback,
        rollback_authorization,
    )
    restored = _active_memory_digest(session) == rollback_digest
    absent_after_rollback = false_record.memory_id not in {
        record.memory_id for record in session.memory.view().active
    }
    session.end_episode(
        handle,
        succeeded=False,
        reason="M3_P05_CONTROLLED_FALSE_LEARNING_AUDIT",
    )
    _require(invalidated_suspended, "M3_P05_INVALIDATION_NOT_EFFECTIVE")
    _require(restored, "M3_P05_ROLLBACK_NOT_EFFECTIVE")
    _require(absent_after_rollback, "M3_P05_ROLLBACK_FALSE_RECORD_RETAINED")
    return {
        "injected_record_id": false_record.memory_id,
        "injected_record_state": false_record.state,
        "negative_transfer_decision": assessment.decision,
        "negative_transfer_reasons": list(assessment.reasons),
        "add_J_authorized": bool(add_authorization.authorization_id),
        "invalidation_J_authorized": bool(invalidate_authorization.authorization_id),
        "rollback_J_authorized": bool(rollback_authorization.authorization_id),
        "add_receipt_operation": add_receipt.operation,
        "invalidation_receipt_operation": invalidate_receipt.operation,
        "rollback_receipt_operation": rollback_receipt.operation,
        "false_record_suspended_after_invalidation": invalidated_suspended,
        "false_record_execute_eligible_after_invalidation": False,
        "false_record_absent_after_rollback": absent_after_rollback,
        "pre_injection_active_memory_restored": restored,
        "admitted_to_candidate_input": False,
    }


def _assessment_mapping(
    assessment: ProductVersionLearningAssessment,
) -> dict[str, object]:
    value = asdict(assessment)
    value["candidate_record_count"] = assessment.candidate_record_count
    return cast(dict[str, object], value)


def _build_outputs(root: Path) -> tuple[dict[str, object], bytes]:
    bundle_payload_before = (root / BUNDLE_PATH).read_bytes()
    active_package_payload_before = (root / BUNDLE_PACKAGE_PATH).read_bytes()
    p04_payload = (root / P04_PATH).read_bytes()
    p04 = json.loads(p04_payload.decode("utf-8"))
    _require(
        isinstance(p04, dict) and p04.get("status") == "M3_P04_PASS",
        "M3_P05_P04_BINDING_INVALID",
    )
    initial = load_product_initial_state()
    gate = ProductVersionLearningGate()
    training_session = create_product_session(
        action_budget=ACTION_BUDGET,
        mode="VALIDATION",
    )
    training_runs: list[dict[str, object]] = []
    first_records: tuple[SemanticRecord, ...] = ()
    stable_source_records: tuple[SemanticRecord, ...] = ()
    for ordinal in range(1, 4):
        summary, records = _run_training_episode(
            training_session,
            ordinal=ordinal,
        )
        training_runs.append(summary)
        if ordinal == 1:
            first_records = records
        if ordinal == 3:
            stable_source_records = records
    one_success_assessment = gate.assess(
        first_records,
        contradiction_test_passed=True,
        deletion_test_passed=True,
        focused_regression_passed=True,
    )
    _require(
        one_success_assessment.decision == "HOLD_RUNTIME_M"
        and one_success_assessment.candidate_record_count == 0,
        "M3_P05_ONE_SUCCESS_PROMOTION_LEAK",
    )
    stable_records = tuple(
        record
        for record in stable_source_records
        if (
            (typed := causal_record_from_semantic(record)).state == "ACTIVE"
            and typed.distinct_episode_support >= 3
            and typed.contradiction_count == 0
            and typed.hazard_count == 0
        )
    )
    _require(len(stable_records) == 1, "M3_P05_STABLE_RECORD_COUNT")
    preflight_control = _isolated_run(
        initial,
        initial_memory_records=initial.m0,
    )
    merged_preflight_memory = {record.memory_id: record for record in initial.m0}
    merged_preflight_memory.update(
        {record.memory_id: record for record in stable_records}
    )
    preflight_candidate = _isolated_run(
        initial,
        initial_memory_records=tuple(
            merged_preflight_memory[key] for key in sorted(merged_preflight_memory)
        ),
    )
    deletion_test_passed = (
        preflight_control["observation_digest"]
        == preflight_candidate["observation_digest"]
        and preflight_control["first_action"] != preflight_candidate["first_action"]
    )
    focused_regression_passed = (
        preflight_control["final_state"] == "WIN"
        and preflight_candidate["final_state"] == "WIN"
        and cast(int, preflight_candidate["action_count"])
        <= cast(int, preflight_control["action_count"])
        and preflight_candidate["all_external_actions_J_authorized"] is True
    )
    contradiction_assessments = tuple(
        assess_negative_transfer(record) for record in stable_records
    )
    contradiction_test_passed = all(
        assessment.decision == "ACCEPT" for assessment in contradiction_assessments
    )
    stable_assessment = gate.assess(
        stable_source_records,
        contradiction_test_passed=contradiction_test_passed,
        deletion_test_passed=deletion_test_passed,
        focused_regression_passed=focused_regression_passed,
    )
    _require(
        stable_assessment.decision == "PROMOTE_TO_VERSION_CANDIDATE"
        and stable_assessment.candidate_record_count == 1,
        "M3_P05_STABLE_CANDIDATE_GATE_FAILED",
    )
    false_learning = _false_learning_audit(
        training_session,
        stable_records[0],
    )
    candidate = gate.compile_candidate(
        parent=initial,
        records=stable_source_records,
        assessment=stable_assessment,
        target_version=TARGET_VERSION,
    )
    candidate_payload = candidate.package_bytes()
    restored = initial_state_from_package(candidate_payload)
    _require(
        restored.package_bytes() == candidate_payload,
        "M3_P05_CANDIDATE_PACKAGE_ROUNDTRIP_FAILED",
    )
    control_restart = _restart_run(initial.package_bytes())
    candidate_restart = _restart_run(candidate_payload)
    acquired_record_ids = set(stable_assessment.eligible_record_ids)
    acquired_record_retrieved = acquired_record_ids.issubset(
        set(cast(list[str], candidate_restart["memory_citation_ids"]))
    ) and acquired_record_ids.isdisjoint(
        set(cast(list[str], control_restart["memory_citation_ids"]))
    )
    acquired_record_bound = (
        bool(cast(list[str], candidate_restart["typed_memory_binding_refs"]))
        and cast(int, candidate_restart["execute_eligible_binding_count"]) > 0
    )
    restart_causal = (
        control_restart["observation_digest"] == candidate_restart["observation_digest"]
        and control_restart["first_action"] != candidate_restart["first_action"]
        and candidate_restart["final_state"] == "WIN"
        and cast(int, candidate_restart["action_count"])
        <= cast(int, control_restart["action_count"])
        and acquired_record_retrieved
        and acquired_record_bound
    )
    _require(restart_causal, "M3_P05_RESTART_CAPABILITY_NOT_CAUSAL")
    _require(
        (root / BUNDLE_PATH).read_bytes() == bundle_payload_before
        and (root / BUNDLE_PACKAGE_PATH).read_bytes() == active_package_payload_before,
        "M3_P05_ACTIVE_PRODUCT_BUNDLE_CHANGED",
    )
    parent_identity = build_runtime_identity(
        p_bundle=initial.p_bundle.body,
        p_ir_program=initial.p_bundle.program,
        hds_configuration=initial.j0,
        initial_memory_records=initial.m0,
    )
    candidate_identity = build_runtime_identity(
        p_bundle=candidate.p_bundle.body,
        p_ir_program=candidate.p_bundle.program,
        hds_configuration=candidate.j0,
        initial_memory_records=candidate.m0,
    )
    transition_digest = "runtime-version-candidate-transition:" + digest_object(
        {
            "parent_runtime": parent_identity.digest(),
            "parent_initial_state": initial.logical_digest,
            "candidate_runtime": candidate_identity.digest(),
            "candidate_initial_state": candidate.logical_digest,
            "assessment": stable_assessment.assessment_digest,
            "status": "CANDIDATE_PENDING_M3_P06",
        }
    )
    source_bindings = {
        path.as_posix(): _sha256((root / path).read_bytes())
        for path in (
            VERSION_GATE_SOURCE_PATH,
            CONSOLIDATION_SOURCE_PATH,
            NEGATIVE_TRANSFER_SOURCE_PATH,
            INITIAL_STATE_SOURCE_PATH,
        )
    }
    report: dict[str, object] = {
        "schema_version": "arc3-rev5-1-m3-p05-runtime-version-learning-v1",
        "artifact_type": "RuntimeVersionLearningEvidence",
        "point_id": "M3-P05_RUNTIME_VERSION_LEARNING",
        "runtime_product": "ARC3CompletionAgent",
        "asset_stage": "ACTIVE_DEV",
        "status": "M3_P05_PASS",
        "evidence_bindings": {
            "active_product_descriptor": {
                "path": BUNDLE_PATH.as_posix(),
                "sha256": _sha256(bundle_payload_before),
            },
            "active_product_package": {
                "path": BUNDLE_PACKAGE_PATH.as_posix(),
                "sha256": _sha256(active_package_payload_before),
            },
            "m3_p04_applicability_counterfactual": {
                "path": P04_PATH.as_posix(),
                "sha256": _sha256(p04_payload),
            },
            "implementation_sources": source_bindings,
        },
        "runtime_learning": {
            "run_count": len(training_runs),
            "runs": training_runs,
            "runtime_experience_updates_M_first": True,
            "runtime_M_consolidation_is_version_promotion": False,
            "first_run_global_causal_state": "PROBATION",
            "first_run_version_candidate_created": False,
        },
        "one_success_gate": _assessment_mapping(one_success_assessment),
        "multi_run_gate": {
            **_assessment_mapping(stable_assessment),
            "contradiction_assessments": [
                {
                    "record_id": item.record_id,
                    "decision": item.decision,
                    "reasons": list(item.reasons),
                    "assessment_digest": item.assessment_digest,
                }
                for item in contradiction_assessments
            ],
        },
        "deletion_and_focused_regression": {
            "control_without_acquired_record": preflight_control,
            "candidate_with_acquired_record": preflight_candidate,
            "same_observation": deletion_test_passed,
            "acquired_record_deletion_changes_action": deletion_test_passed,
            "candidate_non_degrading_on_representative_world": (
                focused_regression_passed
            ),
        },
        "false_learning_control": false_learning,
        "next_version_candidate": {
            "status": "CANDIDATE_PENDING_M3_P06",
            "activation_performed": False,
            "package_path": CANDIDATE_PACKAGE_PATH.as_posix(),
            "package_sha256": _sha256(candidate_payload),
            "package_size_bytes": len(candidate_payload),
            "package_roundtrip_byte_identical": True,
            "parent_initial_state_logical_digest": initial.logical_digest,
            "candidate_initial_state_logical_digest": candidate.logical_digest,
            "parent_P_logical_digest": initial.p_bundle.logical_digest(),
            "candidate_P_logical_digest": candidate.p_bundle.logical_digest(),
            "parent_J0_digest": "j0:" + digest_object(initial.j0),
            "candidate_J0_digest": "j0:" + digest_object(candidate.j0),
            "parent_M0_digest": "m0:" + digest_object(initial.m0),
            "candidate_M0_digest": "m0:" + digest_object(candidate.m0),
            "parent_M0_record_count": len(initial.m0),
            "candidate_M0_record_count": len(candidate.m0),
            "compiled_acquired_record_ids": list(stable_assessment.eligible_record_ids),
            "rejected_or_invalid_record_ids": [
                item[0] for item in stable_assessment.rejected_records
            ],
            "false_learning_record_compiled": False,
        },
        "restart_evidence": {
            "control_parent_initial_state": control_restart,
            "candidate_compiled_initial_state": candidate_restart,
            "same_observation": (
                control_restart["observation_digest"]
                == candidate_restart["observation_digest"]
            ),
            "acquired_capability_changes_restart_behavior": restart_causal,
            "acquired_record_retrieved": acquired_record_retrieved,
            "acquired_record_bound_to_selected_candidate": acquired_record_bound,
            "training_SemanticMemory_object_reused": False,
        },
        "version_lineage_candidate": {
            "parent_runtime_identity_digest": parent_identity.digest(),
            "candidate_runtime_identity_digest": candidate_identity.digest(),
            "parent_version": initial.version,
            "candidate_version": candidate.version,
            "transition_digest": transition_digest,
            "candidate_status": "CANDIDATE_PENDING_M3_P06",
            "active_runtime_count": 1,
            "activation_event_count": 0,
            "full_regression_required_before_activation": True,
        },
        "summary": {
            "runtime_experience_updates_M_first": True,
            "one_success_release_candidate_count": (
                one_success_assessment.candidate_record_count
            ),
            "stable_multi_run_candidate_count": (
                stable_assessment.candidate_record_count
            ),
            "false_learning_invalidated": (
                false_learning["negative_transfer_decision"] == "INVALIDATE"
            ),
            "false_learning_rollback_effective": false_learning[
                "pre_injection_active_memory_restored"
            ],
            "restart_uses_compiled_initial_state": True,
            "restart_acquired_capability_causal": restart_causal,
            "active_runtime_bundle_unchanged": True,
            "active_development_product_bundle_count": 1,
        },
        "claim_boundary": {
            "allowed_claim": "M3_P05_RUNTIME_VERSION_LEARNING_ONLY",
            "candidate_is_active_product": False,
            "full_sample_regression_complete": False,
            "M3_complete": False,
            "product_completion_established": False,
            "release_established": False,
            "next_point": "M3-P06_CONFORMANCE_FULL_REGRESSION",
        },
    }
    report["logical_content_sha256"] = _sha256(_canonical_json(report))
    return report, candidate_payload


@lru_cache(maxsize=2)
def build_outputs(root: Path = REPOSITORY_ROOT) -> tuple[dict[str, object], bytes]:
    nonce_source = _DeterministicNonceSource()
    with patch.object(secrets, "token_hex", side_effect=nonce_source):
        return _build_outputs(root.resolve())


def build_report(root: Path = REPOSITORY_ROOT) -> dict[str, object]:
    return build_outputs(root)[0]


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=REPOSITORY_ROOT)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    report, candidate_payload = build_outputs(root)
    expected = _encoded(report)
    output = root / OUTPUT_PATH
    candidate_output = root / CANDIDATE_PACKAGE_PATH
    if arguments.write:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_bytes(expected)
        candidate_output.write_bytes(candidate_payload)
        status = "WRITTEN"
        success = True
    else:
        success = (
            output.is_file()
            and output.read_bytes() == expected
            and candidate_output.is_file()
            and candidate_output.read_bytes() == candidate_payload
        )
        status = "PASS" if success else "STALE"
    print(
        json.dumps(
            {
                "candidate_package": CANDIDATE_PACKAGE_PATH.as_posix(),
                "output": OUTPUT_PATH.as_posix(),
                "point_status": report["status"],
                "status": status,
            },
            sort_keys=True,
        )
    )
    return 0 if success else 1


if __name__ == "__main__":
    raise SystemExit(main())
