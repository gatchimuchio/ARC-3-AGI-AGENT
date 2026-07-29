from __future__ import annotations

import hashlib
import inspect
import json
from dataclasses import fields
from pathlib import Path

from arc3_agi_agent.causal_record import (
    causal_record,
    causal_record_from_semantic,
)
from arc3_agi_agent.control_state import ControlState
from arc3_agi_agent.evidence_binding import (
    EvidenceBindingKey,
    bind_candidate_records,
    build_evidence_binding_key,
    candidate_hazard_veto,
    candidate_reproduced,
)
from arc3_agi_agent.evidence_policy import EvidenceGroup, EvidencePolicy, evidence_group
from arc3_agi_agent.generic_compute import (
    ParametricRelationalInstructionBody,
    SymbolicRelationalInstructionBody,
    action_descriptors,
    represent_observation,
)
from arc3_agi_agent.generic_env import MechanismWorld
from arc3_agi_agent.generic_hds import GenericHDSJudgementSubject
from arc3_agi_agent.generic_memory import semantic_record
from arc3_agi_agent.generic_runtime import GenericAGIRuntime
from arc3_agi_agent.generic_session import (
    ResourceContract,
    create_cognitive_session,
)
from arc3_agi_agent.generic_types import GenericObservation
from arc3_agi_agent.memory_consolidation import MemoryConsolidator
from arc3_agi_agent.memory_retrieval import rank_memory_records
from arc3_agi_agent.negative_transfer import (
    assess_negative_transfer,
    invalidation_proposal,
)


def _key(
    *,
    state: str = "state-pattern:normalized",
    action: str = "action-relation:move-role",
    effect: str = "predicted-effect:progress",
) -> EvidenceBindingKey:
    return EvidenceBindingKey(
        normalized_state_pattern_digest=state,
        action_relation_digest=action,
        precondition_digest="precondition:role-open",
        predicted_effect_digest=effect,
        applicability_scope_digest="applicability-scope:normalized",
    )


def _group(
    index: int,
    *,
    episode: str,
    outcome: str = "SUPPORT",
    key: EvidenceBindingKey | None = None,
    delay: tuple[int, int] = (0, 0),
) -> EvidenceGroup:
    selected = key or _key()
    return evidence_group(
        outcome=outcome,
        normalized_before_pattern_digest=(
            selected.normalized_state_pattern_digest
        ),
        action_relation_digest=selected.action_relation_digest,
        normalized_after_effect_digest=f"normalized-effect:{index}",
        delay_min_steps=delay[0],
        delay_max_steps=delay[1],
        episode_nonce=episode,
        event_ids=(f"event:{episode}:{index}:{outcome}",),
    )


def _record(
    groups: tuple[EvidenceGroup, ...],
    *,
    scope: str = "SESSION_GLOBAL",
    key: EvidenceBindingKey | None = None,
    kind: str = "ACTION_EFFECT",
    semantic_key: str = "surface:1:untargeted",
):
    selected = key or _key()
    return causal_record(
        kind=kind,
        binding_key=selected,
        scope_class=scope,
        statement="A normalized action relation causes a rendered effect.",
        semantic_tokens=("goal:progress", semantic_key),
        relations=(f"action-relation:{semantic_key}",),
        applicability_predicates=(
            "current-legal-action",
            "normalized-role-topology",
        ),
        evidence_groups=groups,
        falsification_condition=(
            "independent evidence contradicts this causal transition"
        ),
    )


def test_support_contradiction_confidence() -> None:
    policy = EvidencePolicy()
    evaluation = policy.evaluate(
        (
            _group(0, episode="ep-a"),
            _group(1, episode="ep-b"),
            _group(2, episode="ep-c", outcome="CONTRADICTION"),
        ),
        scope_class="SESSION_GLOBAL",
    )

    assert evaluation.support_count == 2
    assert evaluation.contradiction_count == 1
    assert evaluation.hazard_count == 0
    assert evaluation.confidence_ppm == 600_000
    assert evaluation.state == "SUSPENDED"


def test_duplicate_evidence_not_double_counted() -> None:
    group = _group(0, episode="ep-a")
    evaluation = EvidencePolicy().evaluate(
        (group, group, group),
        scope_class="EPISODE_OVERLAY",
    )

    assert evaluation.support_count == 1
    assert evaluation.support_group_ids == (group.group_id,)


def test_delayed_effect_record() -> None:
    record = _record(
        (_group(0, episode="ep-a", delay=(2, 4)),),
        scope="EPISODE_OVERLAY",
    )
    restored = causal_record_from_semantic(record.to_semantic_record())

    assert record.delay_window == (2, 4)
    assert restored.delay_window == (2, 4)
    assert restored.evidence_groups[0].delay_min_steps == 2
    assert restored.evidence_groups[0].delay_max_steps == 4


def test_exact_hazard_veto() -> None:
    selected = _key()
    record = _record(
        (
            _group(
                0,
                episode="ep-hazard",
                outcome="HAZARD",
                key=selected,
            ),
        ),
        key=selected,
        kind="HAZARD_MODEL",
    ).to_semantic_record()
    bindings = bind_candidate_records(key=selected, records=(record,))

    assert bindings
    assert bindings[0].hazard_count == 1
    assert candidate_hazard_veto(bindings) is True
    assert candidate_reproduced(
        bindings,
        retrieved_citation_digests=(record.citation().content_digest,),
    ) is False


def test_one_episode_record_is_probation() -> None:
    local = _record(
        (
            _group(0, episode="ep-a"),
            _group(1, episode="ep-a"),
            _group(2, episode="ep-a"),
        ),
        scope="EPISODE_OVERLAY",
    ).to_semantic_record()
    plan = MemoryConsolidator().plan(
        base_records=(),
        episode_records=(local,),
        succeeded=True,
    )
    promoted = causal_record_from_semantic(plan.proposals[0].record)  # type: ignore[arg-type]

    assert promoted.scope_class == "SESSION_GLOBAL"
    assert promoted.distinct_episode_support == 1
    assert promoted.state == "PROBATION"
    assert promoted.execute_eligibility is False


def test_two_episode_support_can_activate() -> None:
    local_a = _record(
        (
            _group(0, episode="ep-a"),
            _group(1, episode="ep-a"),
        ),
        scope="EPISODE_OVERLAY",
    ).to_semantic_record()
    first_plan = MemoryConsolidator().plan(
        base_records=(),
        episode_records=(local_a,),
        succeeded=True,
    )
    first_global = first_plan.proposals[0].record
    assert first_global is not None
    local_b = _record(
        (_group(2, episode="ep-b"),),
        scope="EPISODE_OVERLAY",
    ).to_semantic_record()
    second_plan = MemoryConsolidator().plan(
        base_records=(first_global,),
        episode_records=(local_b,),
        succeeded=True,
    )
    second_global = second_plan.proposals[0].record
    assert second_global is not None
    promoted = causal_record_from_semantic(second_global)

    assert promoted.support_count == 3
    assert promoted.distinct_episode_support == 2
    assert promoted.confidence_ppm == 800_000
    assert promoted.state == "ACTIVE"
    assert promoted.execute_eligibility is True


def test_cross_level_transfer() -> None:
    rendered = (
        (
            (0, 0, 0, 0),
            (0, 2, 2, 0),
            (0, 2, 2, 0),
            (0, 0, 0, 0),
        ),
    )
    first = GenericObservation(
        signature="level-one-signature",
        available_actions=(11,),
        rendered_layers=rendered,
        terminal_state="NOT_FINISHED",
    )
    second = GenericObservation(
        signature="level-two-different-signature",
        available_actions=(11,),
        rendered_layers=rendered,
        terminal_state="NOT_FINISHED",
    )
    first_representation = represent_observation(
        first,
        goal_tokens=("goal:progress",),
    )
    second_representation = represent_observation(
        second,
        goal_tokens=("goal:progress",),
    )
    first_descriptor = action_descriptors(first, first_representation)[0]
    second_descriptor = action_descriptors(second, second_representation)[0]

    def binding(observation: GenericObservation, representation, descriptor):
        del observation
        return build_evidence_binding_key(
            topology_tokens=representation.topology_tokens,
            relations=representation.relations,
            descriptor_semantic_key=descriptor.semantic_key,
            action_id=descriptor.action_id,
            target_role=descriptor.target_role,
            payload_fields=tuple(
                key for key, _ in descriptor.payload_items
            ),
            predicted_effects=("LEVEL_PROGRESS",),
        )

    first_key = binding(first, first_representation, first_descriptor)
    second_key = binding(second, second_representation, second_descriptor)
    assert first_key == second_key
    active = _record(
        (
            _group(0, episode="ep-a", key=first_key),
            _group(1, episode="ep-a", key=first_key),
            _group(2, episode="ep-b", key=first_key),
        ),
        key=first_key,
        semantic_key=first_descriptor.semantic_key,
    ).to_semantic_record()
    bindings = bind_candidate_records(key=second_key, records=(active,))

    assert bindings[0].execute_eligible is True
    assert "level-one-signature" not in str(active.payload())
    assert "level-two-different-signature" not in str(active.payload())


def test_cross_game_transfer_after_activation() -> None:
    local_a = _record(
        (
            _group(0, episode="game-a"),
            _group(1, episode="game-a"),
        ),
        scope="EPISODE_OVERLAY",
    ).to_semantic_record()
    first = MemoryConsolidator().plan(
        base_records=(),
        episode_records=(local_a,),
        succeeded=True,
    ).proposals[0].record
    assert first is not None
    local_b = _record(
        (_group(2, episode="game-b"),),
        scope="EPISODE_OVERLAY",
    ).to_semantic_record()
    second = MemoryConsolidator().plan(
        base_records=(first,),
        episode_records=(local_b,),
        succeeded=True,
    ).proposals[0].record
    assert second is not None
    typed = causal_record_from_semantic(second)
    bindings = bind_candidate_records(key=_key(), records=(second,))

    assert typed.state == "ACTIVE"
    assert typed.distinct_episode_support == 2
    assert candidate_reproduced(
        bindings,
        retrieved_citation_digests=(second.citation().content_digest,),
    )


def test_irrelevant_prior_invariance() -> None:
    relevant = _record(
        (
            _group(0, episode="ep-a"),
            _group(1, episode="ep-a"),
            _group(2, episode="ep-b"),
        ),
        semantic_key="relation:target",
    ).to_semantic_record()
    irrelevant_key = _key(
        state="state-pattern:other",
        action="action-relation:other",
        effect="predicted-effect:other",
    )
    irrelevant = _record(
        (
            _group(0, episode="other-a", key=irrelevant_key),
            _group(1, episode="other-a", key=irrelevant_key),
            _group(2, episode="other-b", key=irrelevant_key),
        ),
        key=irrelevant_key,
        semantic_key="relation:irrelevant",
    ).to_semantic_record()
    baseline = rank_memory_records(
        records=(relevant,),
        query_tokens=("relation:target",),
        kinds=(),
        current_version=9,
        limit=16,
    )
    with_irrelevant = rank_memory_records(
        records=(irrelevant, relevant),
        query_tokens=("relation:target",),
        kinds=(),
        current_version=9,
        limit=16,
    )

    assert baseline == with_irrelevant


def test_game_order_permutation() -> None:
    first = _record(
        (
            _group(0, episode="game-a"),
            _group(1, episode="game-a"),
        ),
        scope="EPISODE_OVERLAY",
    ).to_semantic_record()
    second = _record(
        (_group(2, episode="game-b"),),
        scope="EPISODE_OVERLAY",
    ).to_semantic_record()
    consolidator = MemoryConsolidator()
    forward = consolidator.plan(
        base_records=(),
        episode_records=(first, second),
        succeeded=True,
    )
    reverse = consolidator.plan(
        base_records=(),
        episode_records=(second, first),
        succeeded=True,
    )

    assert forward == reverse
    assert forward.active_record_count == 1


def test_adversarial_record_rejected() -> None:
    adversarial = semantic_record(
        memory_id="adversarial-untyped-execute",
        kind="ACTION_EFFECT",
        statement="Claims execution authority without causal witnesses.",
        semantic_tokens=("goal:progress", "relation:adversarial"),
        evidence=("unverified-claim",),
        falsification_condition="any schema audit rejects this record",
        payload={
            **_key().payload(),
            "support_count": 99,
            "confidence_ppm": 1_000_000,
            "execute_eligibility": True,
        },
    )
    assessment = assess_negative_transfer(adversarial)

    assert assessment.decision == "REJECT"
    assert assessment.reasons == ("UNTYPED_EXECUTE_ELIGIBILITY",)


def test_negative_transfer_invalidated() -> None:
    groups = (
        _group(0, episode="ep-a"),
        _group(1, episode="ep-a"),
        _group(2, episode="ep-b"),
        _group(3, episode="ep-c", outcome="CONTRADICTION"),
        _group(4, episode="ep-d", outcome="CONTRADICTION"),
    )
    record = _record(groups).to_semantic_record()
    assessment = assess_negative_transfer(record)
    proposal = invalidation_proposal(record, assessment)

    assert record.state == "SUSPENDED"
    assert assessment.decision == "INVALIDATE"
    assert proposal.operation == "INVALIDATE"
    assert proposal.validate() == ()


def test_j_has_no_private_world_learning_state() -> None:
    control_fields = {item.name for item in fields(ControlState)}
    hds_source = inspect.getsource(GenericHDSJudgementSubject)

    assert "selector_deltas" not in control_fields
    assert "value_actions" not in control_fields
    assert "selector_deltas" not in hds_source
    assert "value_actions" not in hds_source


def test_memory_ablation_changes_future_action() -> None:
    observation = GenericObservation(
        signature="future-action-observation",
        available_actions=(11, 29),
        rendered_layers=(
            (
                (0, 0, 0, 0),
                (0, 2, 2, 0),
                (0, 2, 2, 0),
                (0, 0, 0, 0),
            ),
        ),
        terminal_state="NOT_FINISHED",
    )
    representation = represent_observation(
        observation,
        goal_tokens=("goal:progress",),
    )
    descriptors = action_descriptors(observation, representation)
    target = next(item for item in descriptors if item.action_id == 29)
    target_key = build_evidence_binding_key(
        topology_tokens=representation.topology_tokens,
        relations=representation.relations,
        descriptor_semantic_key=target.semantic_key,
        action_id=target.action_id,
        target_role=target.target_role,
        payload_fields=tuple(key for key, _ in target.payload_items),
        predicted_effects=("EXPECTED_EFFECT_FAMILY",),
    )
    memory_record = _record(
        (
            _group(0, episode="ep-a", key=target_key),
            _group(1, episode="ep-a", key=target_key),
            _group(2, episode="ep-b", key=target_key),
        ),
        key=target_key,
        semantic_key=target.semantic_key,
    ).to_semantic_record()
    body = SymbolicRelationalInstructionBody()
    without_memory = body.query(representation, descriptors, ())
    with_memory = body.query(
        representation,
        descriptors,
        (memory_record,),
    )
    without_action = max(
        without_memory.predictions,
        key=lambda item: item.prior,
    ).descriptor.action_id
    with_action = max(
        with_memory.predictions,
        key=lambda item: item.prior,
    ).descriptor.action_id

    assert without_action == 11
    assert with_action == 29
    assert with_action != without_action


def test_runtime_cross_game_promotion_reaches_active() -> None:
    session = create_cognitive_session(
        p_bundle=ParametricRelationalInstructionBody(),
        resource_contract=ResourceContract(action_budget_per_episode=8),
    )
    receipts = []
    for _ in range(3):
        handle = session.begin_episode()
        report = GenericAGIRuntime(
            MechanismWorld((11, 29), (0,), required_progress=1),
            session,
            handle,
        ).run()
        receipts.append(
            session.end_episode(
                handle,
                succeeded=report.final_state == "WIN",
                reason=report.stop_reason,
            )
        )
    causal_records = tuple(
        causal_record_from_semantic(record)
        for record in session.memory.view().active
        if record.payload().get("causal_schema_version") == 1
    )

    assert all(item.promoted for item in receipts)
    assert any(
        item.scope_class == "SESSION_GLOBAL"
        and item.state == "ACTIVE"
        and item.support_count >= 3
        and item.distinct_episode_support >= 2
        for item in causal_records
    )


def test_p19_phase_state_is_content_bound() -> None:
    root = Path(__file__).resolve().parents[3]
    path = root / "control" / "p19" / "P19_PHASE_STATE.json"
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
    assert data["metrics"]["memory_causal_witness_count"] > 0
    assert data["metrics"]["hidden_j_world_knowledge_count"] == 0
    assert data["metrics"]["cross_game_semantic_promotion"] == "ENABLED"
