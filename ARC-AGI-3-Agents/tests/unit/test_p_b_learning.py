from __future__ import annotations

import json
import unittest

from arc3_agi_agent.context import ContextSnapshot
from arc3_agi_agent.instruction_body import (
    InstructionQueryResult,
    load_p10_parametric_instruction_body,
)
from arc3_agi_agent.ir import ActionPredictionIR, ObservationIR
from arc3_agi_agent.memory import MemoryEntry, MemorySnapshot
from arc3_agi_agent.p_b_learning import (
    P_B_LEARNING_MEMORY_KEY,
    P_B_LEARNING_SCHEMA_VERSION,
    build_p_b_learning_dataset,
    merge_p_b_learning_memory_snapshots,
    p_b_learning_memory_evidence_mapping,
    p_b_learning_memory_from_mapping,
    train_p_b_from_memory,
    update_p_b_learning_memory,
)
from arc3_agi_agent.p_update import PUpdateEvidenceSet


def _raw_example(
    example_id: str,
    *,
    split: str,
    kinds: list[str],
    feature_shift: float = 0.0,
) -> dict[str, object]:
    return {
        "schema_version": P_B_LEARNING_SCHEMA_VERSION,
        "example_id": example_id,
        "feature_vector": [
            1.0,
            0.5 + feature_shift,
            0.5,
            1.0,
            1.0,
            1.0,
            1.0,
            0.25,
            0.25,
            1.0,
            1.0,
            1.0,
        ],
        "targets": [1.0, 1.0, 0.0, 1.0, 1.0, 0.0],
        "split": split,
        "evidence_kinds": kinds,
        "evidence_refs": [f"evidence:{example_id}"],
        "runtime_identity_free": True,
    }


def _memory(
    *,
    authorized: bool = True,
    suffix: str = "",
) -> MemorySnapshot:
    provenance = (
        ("hds-command:learning", "hds-decision:learning")
        if authorized
        else ("low-level-write",)
    )
    payload = {
        P_B_LEARNING_MEMORY_KEY: {
            "schema_version": P_B_LEARNING_SCHEMA_VERSION,
            "buffer_limit": 128,
            "examples": [
                _raw_example(
                    f"example:positive{suffix}",
                    split="TRAIN",
                    kinds=["EXPERIENCE", "POSITIVE"],
                ),
                _raw_example(
                    f"example:negative{suffix}",
                    split="TRAIN",
                    kinds=["EXPERIENCE", "NEGATIVE"],
                    feature_shift=0.05,
                ),
                _raw_example(
                    f"example:failure{suffix}",
                    split="TRAIN",
                    kinds=["EXPERIENCE", "FAILURE"],
                    feature_shift=0.1,
                ),
                _raw_example(
                    f"example:contradiction{suffix}",
                    split="TRAIN",
                    kinds=["EXPERIENCE", "CONTRADICTION"],
                    feature_shift=0.15,
                ),
                _raw_example(
                    f"example:holdout{suffix}",
                    split="HOLDOUT",
                    kinds=["EXPERIENCE", "POSITIVE"],
                    feature_shift=0.075,
                ),
            ],
            "pending": None,
            "runtime_identity_free": True,
        }
    }
    entry = MemoryEntry(
        target="visual-runtime-state",
        operation="REPLACE",
        lifecycle="PROPOSED",
        evidence_signature=f"evidence:authorized-learning{suffix}",
        payload_json=json.dumps(payload, sort_keys=True),
        version=1,
        provenance=provenance,
        created_version=1,
    )
    return MemorySnapshot(version=1, entries=(entry,))


def _evidence(memory: MemorySnapshot) -> PUpdateEvidenceSet:
    return PUpdateEvidenceSet(
        evidence_set_id="evidence-set:p-b-learning",
        proposal_digest="proposal:p-b-learning",
        memory_snapshot_digest=memory.digest,
        approved_memory_refs=("visual-runtime-state",),
        hds_memory_decision_digests=("hds-decision:learning",),
        failure_refs=("failure:bounded-stagnation",),
        contradiction_refs=("contradiction:effect-mismatch",),
        positive_contrast_refs=("contrast:visible-progress",),
        negative_contrast_refs=("contrast:no-visible-progress",),
        holdout_refs=("holdout:unseen-structure",),
        replay_audit_refs=("audit:no-id-no-replay",),
        provenance=("runtime-memory:authorized",),
    )


def _observation(
    *,
    signature: str,
    structural_signature: str,
    effects: tuple[str, ...],
) -> ObservationIR:
    return ObservationIR(
        frame_signature=signature,
        structural_signature=structural_signature,
        mechanic_signature="mechanic:visible",
        dimensions=(2, 2),
        available_actions=(1,),
        visible_effects=effects,
        terminal_state="NOT_FINISHED",
        rendered_layers=(((0, 1), (1, 0)),),
    )


def _context(observation: ObservationIR) -> ContextSnapshot:
    return ContextSnapshot(
        current_observation=observation,
        previous_observation=None,
        action_history=(),
        effect_history=(),
        hypotheses=(),
        failures=(),
        action_budget=8,
        actions_used=0,
        open_items=(),
        version=1,
    )


def _query() -> InstructionQueryResult:
    return InstructionQueryResult(
        body_format="parametric-sigmoid-matrix",
        body_version="active",
        body_digest="body:active",
        query_digest="query:active",
        representations=("rendered",),
        retrieved_items=("parameters",),
        hypotheses=(),
        predictions=(
            ActionPredictionIR(
                action_id=1,
                predicted_effects=("VISIBLE_STATE_CHANGE",),
                progress_likelihood=0.8,
                hazard_likelihood=0.1,
                information_gain=0.8,
                candidate_prior=0.8,
                uncertainty=0.2,
            ),
        ),
        controls=(),
        uncertainty=0.2,
        falsification_conditions=("observed-effect-differs",),
        provenance=("active-p",),
    )


class PBLearningTests(unittest.TestCase):
    def test_memory_buffer_finalizes_previous_pending_observation(self) -> None:
        before = _observation(
            signature="observation:before",
            structural_signature="structure:shared",
            effects=(),
        )
        pending_payload = update_p_b_learning_memory(
            MemorySnapshot(version=0, entries=()),
            before,
            _context(before),
            _query(),
            selected_action_id=1,
        )
        entry = MemoryEntry(
            target="visual-runtime-state",
            operation="ADD",
            lifecycle="PROPOSED",
            evidence_signature="evidence:first",
            payload_json=json.dumps(
                {P_B_LEARNING_MEMORY_KEY: pending_payload},
                sort_keys=True,
            ),
            version=1,
            provenance=("hds-command:first", "hds-decision:first"),
            created_version=1,
        )
        after = _observation(
            signature="observation:after",
            structural_signature="structure:shared",
            effects=("NO_VISIBLE_CHANGE",),
        )

        finalized = update_p_b_learning_memory(
            MemorySnapshot(version=1, entries=(entry,)),
            after,
            _context(after),
            _query(),
            selected_action_id=1,
        )

        examples = finalized["examples"]
        self.assertIsInstance(examples, list)
        assert isinstance(examples, list)
        self.assertEqual(len(examples), 1)
        self.assertIn("NEGATIVE", examples[0]["evidence_kinds"])
        self.assertIn("CONTRADICTION", examples[0]["evidence_kinds"])

    def test_dataset_rejects_non_hds_memory_provenance(self) -> None:
        memory = _memory(authorized=False)
        with self.assertRaisesRegex(
            ValueError,
            "P_B_DATASET_MEMORY_ENTRY_NOT_HDS_AUTHORIZED",
        ):
            build_p_b_learning_dataset(memory, _evidence(memory))

    def test_distinct_episode_memory_merge_round_trips(self) -> None:
        merged = merge_p_b_learning_memory_snapshots(
            (_memory(suffix=":a"), _memory(suffix=":b"))
        )
        mapping = p_b_learning_memory_evidence_mapping(merged)

        restored = p_b_learning_memory_from_mapping(mapping)

        self.assertEqual(restored, merged)
        self.assertEqual(restored.digest, merged.digest)
        self.assertEqual(len(restored.entries), 2)

    def test_training_changes_parameters_and_same_input_output(self) -> None:
        memory = _memory()
        dataset = build_p_b_learning_dataset(memory, _evidence(memory))
        source = load_p10_parametric_instruction_body()

        first = train_p_b_from_memory(source, dataset)
        second = train_p_b_from_memory(source, dataset)

        self.assertEqual(first, second)
        self.assertEqual(first.validate(), ())
        self.assertNotEqual(
            first.source_parameter_digest,
            first.candidate_parameter_digest,
        )
        self.assertNotEqual(
            first.source_same_input_output_digest,
            first.candidate_same_input_output_digest,
        )
        self.assertLess(
            first.candidate_train_loss,
            first.source_train_loss,
        )
        self.assertLessEqual(
            first.candidate_holdout_loss,
            first.source_holdout_loss,
        )


if __name__ == "__main__":
    unittest.main()
