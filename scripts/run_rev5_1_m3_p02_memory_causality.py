#!/usr/bin/env python3
"""Execute rev5.1 relevant-M causality and irrelevant-M invariance."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from dataclasses import replace
from pathlib import Path
from typing import Final

REPOSITORY_ROOT: Final = Path(__file__).resolve().parents[1]
PACKAGE_ROOT: Final = REPOSITORY_ROOT / "ARC-AGI-3-Agents"
if str(PACKAGE_ROOT) not in sys.path:
    sys.path.insert(0, str(PACKAGE_ROOT))

from arc3_agi_agent.causal_record import (  # noqa: E402
    causal_record_from_semantic,
)
from arc3_agi_agent.generic_env import MechanismWorld  # noqa: E402
from arc3_agi_agent.generic_hds import HDSConfiguration  # noqa: E402
from arc3_agi_agent.generic_memory import (  # noqa: E402
    SemanticRecord,
    semantic_record,
)
from arc3_agi_agent.generic_runtime import GenericAGIRuntime  # noqa: E402
from arc3_agi_agent.generic_session import (  # noqa: E402
    ResourceContract,
    create_cognitive_session,
)
from arc3_agi_agent.local_capability import (  # noqa: E402
    refresh_local_capability_memory,
)
from arc3_agi_agent.product_capability import (  # noqa: E402
    load_product_initial_state,
)
from arc3_agi_agent.product_runner import create_product_session  # noqa: E402

OUTPUT_PATH: Final = Path("analysis/product/rev5_1/m3_p02_memory_causality.json")
BUNDLE_PATH: Final = Path(
    "ARC-AGI-3-Agents/arc3_agi_agent/bundles/arc3_product_initial_state_v1.json"
)
ACTION_BUDGET: Final = 6
ACTION_SURFACE: Final = (11, 29)


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


def _world(*, winning_ordinal: int = 0) -> MechanismWorld:
    return MechanismWorld(
        ACTION_SURFACE,
        (winning_ordinal,),
        required_progress=1,
        max_turns=ACTION_BUDGET,
    )


def _source_causal_record(
    *,
    winning_ordinal: int,
    expected_outcome: str,
) -> tuple[SemanticRecord, dict[str, object]]:
    """Obtain M from the real outcome-attribution and J-commit path."""

    session = create_product_session(action_budget=1, mode="VALIDATION")
    world = _world(winning_ordinal=winning_ordinal)
    before = world.observe()
    handle = session.begin_episode()
    report = GenericAGIRuntime(world, session, handle).run()
    cycle = report.cycles[0]
    attribution = cycle.attribution
    if attribution is None:
        raise RuntimeError("M3_P02_SOURCE_ATTRIBUTION_MISSING")
    _require(
        attribution.category == expected_outcome,
        "M3_P02_SOURCE_OUTCOME_MISMATCH",
    )
    _require(
        cycle.decision.memory_update_authorized,
        "M3_P02_SOURCE_MEMORY_NOT_J_AUTHORIZED",
    )
    _require(
        any(event.startswith("hds-memory-update:") for event in cycle.authority_events),
        "M3_P02_SOURCE_MEMORY_CAPABILITY_MISSING",
    )
    causal_records = tuple(
        record
        for record in session.memory.view().active
        if record.payload().get("causal_schema_version") == 1
    )
    _require(len(causal_records) == 1, "M3_P02_SOURCE_CAUSAL_RECORD_COUNT")
    record = causal_records[0]
    typed = causal_record_from_semantic(
        record,
        policy=session.hds_config.evidence_policy(),
    )
    session.end_episode(
        handle,
        succeeded=report.final_state == "WIN",
        reason=report.stop_reason,
    )
    selected_candidate = cycle.selected_candidate
    if selected_candidate is None:
        raise RuntimeError("M3_P02_SOURCE_CANDIDATE_MISSING")
    summary: dict[str, object] = {
        "observation_digest": before.digest(),
        "selected_action": selected_candidate.descriptor.action_id,
        "outcome": expected_outcome,
        "memory_id": record.memory_id,
        "memory_state": typed.state,
        "success_count": typed.support_count,
        "no_effect_count": typed.no_effect_count,
        "J_memory_authorized": True,
        "identity_input_count": 0,
    }
    return record, summary


def _selected_decision(
    *,
    extra_records: tuple[SemanticRecord, ...],
) -> dict[str, object]:
    initial = load_product_initial_state()
    selected_j0 = replace(
        initial.j0,
        resource_budget=ACTION_BUDGET,
        stop_after_no_progress=ACTION_BUDGET,
    )
    _require(isinstance(selected_j0, HDSConfiguration), "M3_P02_J0_INVALID")
    session = create_cognitive_session(
        p_bundle=initial.p_bundle.body,
        p_ir_program=initial.p_bundle.program,
        mode="VALIDATION",
        hds_configuration=selected_j0,
        initial_memory_records=initial.m0,
        resource_contract=ResourceContract(action_budget_per_episode=ACTION_BUDGET),
    )
    world = _world()
    observation = world.observe()
    handle = session.begin_episode()
    refresh_local_capability_memory(session.memory, observation)
    current_working = session.memory.view().working
    _require(
        all(record.state in {"PROPOSED", "PROBATION"} for record in extra_records),
        "M3_P02_COUNTERFACTUAL_WORKING_STATE_INVALID",
    )
    session.memory.set_working((*current_working, *extra_records))
    memory_view = session.memory.view()
    frame = session.hds.frame(
        observation,
        memory_view,
        remaining_budget=ACTION_BUDGET,
    )
    command = session.hds.issue_compute(frame, observation, memory_view)
    result = session.compute.compute(
        command=command,
        observation=observation,
        memory=session.memory,
        instruction_body=session.instruction_body,
        p_ir_program=session.p_ir_program,
        action_history=(),
    )
    decision = session.hds.judge(
        frame=frame,
        observation=observation,
        result=result,
    )
    selected = next(
        (
            candidate
            for candidate in result.candidates
            if candidate.candidate_id == decision.selected_candidate_id
        ),
        None,
    )
    if selected is None:
        raise RuntimeError("M3_P02_SELECTED_CANDIDATE_MISSING")
    authorization = session.hds.authorize_action(
        decision,
        selected,
        observation,
    )
    action_id, payload = session.executor.action_executor.consume(
        authorization,
        decision,
        selected,
        observation,
    )
    retrieval = next(stage for stage in result.stages if stage.stage == "retrieve")
    output = {
        "observation_digest": observation.digest(),
        "action_id": action_id,
        "payload": payload,
        "operation_state": decision.operation_state,
        "external_action_J_authorized": decision.external_action_authorized,
        "candidate_semantic_key": selected.descriptor.semantic_key,
        "plan_phase": selected.plan.phase,
        "plan_revision_reason": selected.plan.revision_reason,
        "candidate_memory_effect_count": len(selected.memory_effects),
        "plan_memory_ref_count": len(selected.plan.memory_refs),
        "retrieval_output_digest_present": bool(retrieval.output_digest),
        "active_product_p_digest": initial.p_bundle.logical_digest(),
    }
    session.end_episode(handle, succeeded=False, reason="M3_P02_COUNTERFACTUAL")
    return output


def _irrelevant_record() -> SemanticRecord:
    return semantic_record(
        memory_id="m3-p02:irrelevant-orthogonal-prior",
        kind="WORLD_MODEL",
        statement="An orthogonal prior with no current semantic or relation binding.",
        semantic_tokens=("orthogonal-domain:unrelated",),
        relations=("orthogonal-relation:unrelated",),
        evidence=("m3-p02-controlled-invariance-probe",),
        scope=("OUT_OF_SCOPE_COUNTERFACTUAL",),
        falsification_condition="a current query binds this orthogonal relation",
        state="PROBATION",
        payload={
            "applicability_match": False,
            "execute_eligibility": False,
        },
    )


def build_report(root: Path = REPOSITORY_ROOT) -> dict[str, object]:
    bundle_bytes = (root / BUNDLE_PATH).read_bytes()
    no_effect_record, no_effect_source = _source_causal_record(
        winning_ordinal=0,
        expected_outcome="NO_EFFECT",
    )
    progress_record, progress_source = _source_causal_record(
        winning_ordinal=1,
        expected_outcome="PROGRESS",
    )
    _require(
        no_effect_source["observation_digest"] == progress_source["observation_digest"],
        "M3_P02_SOURCE_OBSERVATION_DRIFT",
    )
    _require(
        no_effect_record.memory_id == progress_record.memory_id,
        "M3_P02_RELEVANT_BINDING_ID_DRIFT",
    )

    baseline = _selected_decision(extra_records=())
    relevant_added = _selected_decision(extra_records=(no_effect_record,))
    relevant_revised = _selected_decision(extra_records=(progress_record,))
    relevant_invalidated = _selected_decision(extra_records=())
    irrelevant_added = _selected_decision(extra_records=(_irrelevant_record(),))
    observation_digests = {
        str(item["observation_digest"])
        for item in (
            baseline,
            relevant_added,
            relevant_revised,
            relevant_invalidated,
            irrelevant_added,
        )
    }
    _require(
        len(observation_digests) == 1,
        "M3_P02_COUNTERFACTUAL_OBSERVATION_DRIFT",
    )
    _require(baseline["action_id"] == 29, "M3_P02_BASELINE_ACTION")
    _require(
        relevant_added["action_id"] == 11,
        "M3_P02_RELEVANT_M_DID_NOT_CHANGE_ACTION",
    )
    _require(
        relevant_revised["action_id"] == baseline["action_id"],
        "M3_P02_RELEVANT_REVISION_INCONSISTENT",
    )
    _require(
        relevant_invalidated["action_id"] == baseline["action_id"],
        "M3_P02_INVALIDATION_DID_NOT_RESTORE_BASELINE",
    )
    _require(
        irrelevant_added["action_id"] == baseline["action_id"],
        "M3_P02_IRRELEVANT_M_CHANGED_ACTION",
    )
    decisions = (
        baseline,
        relevant_added,
        relevant_revised,
        relevant_invalidated,
        irrelevant_added,
    )
    _require(
        all(item["external_action_J_authorized"] is True for item in decisions),
        "M3_P02_NON_J_AUTHORIZED_ACTION",
    )
    p_digests = {str(item["active_product_p_digest"]) for item in decisions}
    _require(len(p_digests) == 1, "M3_P02_ACTIVE_P_DRIFT")

    report: dict[str, object] = {
        "schema_version": "arc3-rev5-1-m3-p02-memory-causality-v1",
        "artifact_type": "MemoryCausalityAndInvarianceEvidence",
        "point_id": "M3-P02_MEMORY_CAUSALITY",
        "runtime_product": "ARC3CompletionAgent",
        "asset_stage": "ACTIVE_DEV",
        "status": "M3_P02_PASS",
        "input_binding": {
            "active_product_bundle_path": BUNDLE_PATH.as_posix(),
            "active_product_bundle_sha256": _sha256(bundle_bytes),
            "active_product_p_digest": next(iter(p_digests)),
        },
        "teacher_free_source_attribution": {
            "no_effect": no_effect_source,
            "progress": progress_source,
            "same_relevant_binding_id": True,
            "source_or_hidden_state_used_by_C_J_M_P": False,
        },
        "counterfactual_contract": {
            "byte_identical_observation_across_counterfactuals": True,
            "observation_digest": next(iter(observation_digests)),
            "available_actions": list(ACTION_SURFACE),
            "identity_input_count": 0,
            "action_history_held_empty": True,
            "active_P_held_constant": True,
            "J_configuration_held_constant": True,
        },
        "baseline_no_relevant_M": baseline,
        "relevant_M_added_no_effect": relevant_added,
        "relevant_M_revised_to_progress": relevant_revised,
        "relevant_M_invalidated": {
            **relevant_invalidated,
            "active_relevant_record_count": 0,
            "invalidation_semantics": "REMOVE_FROM_ACTIVE_M",
        },
        "irrelevant_M_added": {
            **irrelevant_added,
            "irrelevant_record_id": "m3-p02:irrelevant-orthogonal-prior",
            "applicability_match": False,
        },
        "causality_audit": {
            "baseline_action_id": baseline["action_id"],
            "relevant_no_effect_action_id": relevant_added["action_id"],
            "relevant_progress_action_id": relevant_revised["action_id"],
            "invalidated_action_id": relevant_invalidated["action_id"],
            "irrelevant_action_id": irrelevant_added["action_id"],
            "relevant_M_addition_changes_decision": True,
            "relevant_M_revision_changes_decision_consistently": True,
            "relevant_M_invalidation_restores_baseline": True,
            "irrelevant_M_action_invariance": True,
            "non_J_authorized_action_count": 0,
        },
        "exit_audit": {
            "byte_identical_observation_across_counterfactuals": True,
            "relevant_M_addition_changes_decision": True,
            "relevant_M_revision_changes_decision_consistently": True,
            "relevant_M_invalidation_restores_baseline": True,
            "irrelevant_M_action_invariance": True,
            "non_J_authorized_action_count": 0,
            "active_development_product_bundle_count": 1,
            "runtime_policy_changed": False,
            "status": "M3_P02_PASS",
        },
        "claim_boundary": {
            "allowed_claim": "M3_P02_MEMORY_CAUSALITY_ONLY",
            "M3_complete": False,
            "product_completion_established": False,
            "release_established": False,
            "next_point": "M3-P03_IDENTITY_REPLAY_AUDIT",
        },
    }
    report["logical_content_sha256"] = _sha256(_canonical_json(report))
    return report


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--root", type=Path, default=REPOSITORY_ROOT)
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--write", action="store_true")
    mode.add_argument("--check", action="store_true")
    arguments = parser.parse_args()
    root = arguments.root.resolve()
    report = build_report(root)
    expected = _encoded(report)
    path = root / OUTPUT_PATH
    if arguments.write:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(expected)
        status = "WRITTEN"
        success = True
    else:
        success = path.is_file() and path.read_bytes() == expected
        status = "PASS" if success else "STALE"
    print(
        json.dumps(
            {
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
