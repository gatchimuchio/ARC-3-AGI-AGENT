from __future__ import annotations

import unittest

from arc3_agi_agent.checkpoint import CheckpointManager
from arc3_agi_agent.ir import (
    CandidateIR,
    ClosureIR,
    CompiledRecord,
    EntityIR,
    HypothesisIR,
    ObservationIR,
    ProofObligationIR,
    TransitionIR,
)
from arc3_agi_agent.protocol import (
    DEFAULT_INSTRUCTION_BODY_CONTRACT,
    EmissionDirective,
    ComputeRequest,
    HDSDecision,
    MemoryDirective,
    TrinityLifecycle,
)
from arc3_agi_agent.schema import (
    SCHEMA_VERSION,
    digest_object,
    record_from_dict,
    record_to_dict,
    validate_record,
    validate_runtime_bundle,
)
from arc3_agi_agent.verification import (
    RenderedObservation,
    verify_rendered_transition,
)


class ProtocolTests(unittest.TestCase):
    def test_default_contract_and_request_validate(self) -> None:
        contract = DEFAULT_INSTRUCTION_BODY_CONTRACT
        self.assertEqual(contract.validate(), ())
        request = ComputeRequest(
            command_id="cmd-1",
            operation="LLM_COMPUTE",
            observation_signature="frame:abc",
            feature_tokens=("object_relation",),
        )
        self.assertEqual(request.validate(contract), ())

    def test_memory_and_emission_require_explicit_hds_permission(self) -> None:
        denied = HDSDecision(
            command_id="cmd-1",
            decision_id="decision-1",
            status="SUSPEND",
        )
        memory = MemoryDirective(
            command_id="cmd-1",
            decision_id="decision-1",
            operation="ADD",
            target="hypothesis:h1",
            lifecycle="PROPOSED",
            evidence_signature="evidence:1",
        )
        emission = EmissionDirective(
            command_id="cmd-1",
            decision_id="decision-1",
            action_id=1,
            reasoning_digest="digest:1",
        )
        self.assertIn("MEMORY_WRITE_NOT_AUTHORIZED", memory.validate(denied))
        self.assertIn("EXTERNAL_EMIT_NOT_AUTHORIZED", emission.validate(denied))

        allowed = HDSDecision(
            command_id="cmd-1",
            decision_id="decision-1",
            status="EMIT",
            candidate_id="c1",
            closure_signature="closure:1",
            allow_memory_write=True,
            allow_external_emit=True,
        )
        self.assertEqual(allowed.validate(), ())
        self.assertEqual(memory.validate(allowed), ())
        self.assertEqual(emission.validate(allowed), ())

    def test_lifecycle_rejects_invalid_transition(self) -> None:
        lifecycle = TrinityLifecycle()
        self.assertEqual(lifecycle.transition("SELF_CHECK"), "SELF_CHECK")
        self.assertEqual(lifecycle.transition("FRAME"), "FRAME")
        with self.assertRaises(ValueError):
            lifecycle.transition("ACT")

        stopped = TrinityLifecycle("SUSPEND")
        self.assertEqual(stopped.transition("STOP"), "STOP")
        with self.assertRaises(ValueError):
            stopped.transition("REFRAME")


class SchemaTests(unittest.TestCase):
    def make_record(self) -> CompiledRecord:
        observation = ObservationIR(
            frame_signature="frame:1",
            structural_signature="struct:1",
            mechanic_signature="mechanic:1",
            dimensions=(64, 64),
            available_actions=(1, 2, 6),
            entities=(EntityIR("entity:1", ("controllable",)),),
            relations=("adjacent",),
            terminal_state="RUNNING",
        )
        transition = TransitionIR(
            before="frame:0",
            after="frame:1",
            action_class="keyboard",
            effects=("MOVED",),
            confidence=0.8,
        )
        hypothesis = HypothesisIR(
            hypothesis_id="h1",
            hypothesis_type="movement",
            claims=("action1 moves controllable",),
            predictions=("MOVED",),
            falsification_conditions=("NO_EFFECT",),
            confidence=0.7,
        )
        candidate = CandidateIR(
            candidate_id="c1",
            mode="PROBE",
            steps=({"action_id": 1},),
            preconditions=("ACTION1_AVAILABLE",),
            expected_effects_by_hypothesis={"h1": ("MOVED",)},
            expected_information_gain=0.5,
        )
        closure = ClosureIR(
            candidate_id="c1",
            x={"observation": "frame:1"},
            r={"prediction": "MOVED"},
            mc={"stop_on": "DIVERGENCE"},
            status="PROBE",
            confidence=0.7,
        )
        obligation = ProofObligationIR(
            obligation_id="o1",
            kind="transition_effect",
            status="OPEN",
            reopen_condition="observe positive and negative contrast",
            evidence_boundary="rendered frames only",
        )
        return CompiledRecord(
            observation=observation,
            transition=transition,
            hypotheses=(hypothesis,),
            candidates=(candidate,),
            closures=(closure,),
            proof_obligations=(obligation,),
            evidence_state="BOUNDED_SUSPEND",
            source_provenance_digest="source:abc",
        )

    def test_record_round_trip_is_deterministic(self) -> None:
        record = self.make_record()
        self.assertEqual(validate_record(record), [])
        encoded = record_to_dict(record)
        decoded = record_from_dict(encoded)
        self.assertEqual(decoded, record)
        self.assertEqual(digest_object(record), digest_object(decoded))

    def test_runtime_bundle_rejects_task_identity(self) -> None:
        bundle = {
            "schema_version": SCHEMA_VERSION,
            "runtime_identity_free": True,
            "entry_count": 1,
            "entries": [
                {
                    "entry_id": "entry:1",
                    "runtime_identity_free": True,
                    "selectors": {"replayIndex": 3},
                    "payload": {"effect": "MOVED"},
                    "support": 1,
                    "confidence": 0.8,
                }
            ],
        }
        failures = validate_runtime_bundle(bundle)
        self.assertTrue(
            any("forbidden runtime identity field" in failure for failure in failures)
        )


class VerificationTests(unittest.TestCase):
    def observation(
        self,
        signature: str,
        *,
        levels: int = 0,
        state: str = "RUNNING",
        progress: bool = False,
        effects: tuple[str, ...] = (),
        action_count: int = 0,
    ) -> RenderedObservation:
        return RenderedObservation(
            signature=signature,
            levels_completed=levels,
            terminal_state=state,
            visible_progress=progress,
            visible_effects=effects,
            available_actions=(1, 2, 3, 4, 6, 7),
            action_count=action_count,
            max_actions=80,
        )

    def test_expected_effect_can_commit_transition(self) -> None:
        before = self.observation("before")
        after = self.observation("after", effects=("MOVED",), action_count=1)
        result = verify_rendered_transition(before, after, 1, ("MOVED",))
        self.assertEqual(result.commitment_status, "PASS")
        self.assertEqual(result.status, "SUSPEND")
        self.assertIn("NO_HAZARD_OBSERVED", result.reason_codes)

    def test_level_progress_passes_and_game_over_fails(self) -> None:
        before = self.observation("before")
        progressed = self.observation(
            "after", levels=1, state="NOT_FINISHED", action_count=1
        )
        result = verify_rendered_transition(before, progressed, 1, ())
        self.assertEqual(result.status, "PASS")
        self.assertTrue(result.evidence_checkpoint_eligible)

        failed = self.observation(
            "failed", state="GAME_OVER", effects=("HAZARD",), action_count=1
        )
        failure_result = verify_rendered_transition(before, failed, 1, ("MOVED",))
        self.assertEqual(failure_result.status, "FAIL")
        self.assertFalse(failure_result.evidence_checkpoint_eligible)

    def test_unknown_terminal_does_not_close_even_with_progress(self) -> None:
        before = self.observation("before")
        after = self.observation(
            "after", levels=1, state="UNKNOWN", action_count=1
        )
        result = verify_rendered_transition(before, after, 1, ())
        self.assertEqual(result.status, "SUSPEND")
        self.assertFalse(result.evidence_checkpoint_eligible)

    def test_checkpoint_manager_is_bounded(self) -> None:
        manager = CheckpointManager(max_checkpoints=2)
        manager.save(self.observation("one"))
        manager.save(self.observation("two", action_count=1))
        manager.save(self.observation("three", action_count=2))
        evidence = manager.evidence()
        self.assertEqual(len(evidence), 2)
        self.assertEqual(evidence[0].observation.signature, "two")
        self.assertEqual(manager.latest().observation.signature, "three")


if __name__ == "__main__":
    unittest.main()
