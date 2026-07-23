from __future__ import annotations

import inspect
import unittest
from collections import Counter
from pathlib import Path
from typing import cast

from arc3_agi_agent.context import BoundedContextState
from arc3_agi_agent.instruction_body import InstructionBody
from arc3_agi_agent.kernel import Layer0Components, Layer0Kernel
from arc3_agi_agent.memory import (
    ALL_MEMORY_OPERATIONS,
    MEMORY_SUBJECT_REMOVAL_WITNESS,
    MemoryEntry,
    MemoryMutationResult,
    MemoryOperation,
    MemoryOperationError,
    MemoryProvenanceEvent,
    MemoryQuery,
    MemoryQueryResult,
    MemorySnapshot,
    MemoryVersionConflict,
    PassiveMemory,
    StandaloneMemoryHarness,
)
from arc3_agi_agent.memory_fixtures import load_memory_lifecycle_fixtures
from arc3_agi_agent.protocol import AuthorityViolation
from arc3_agi_agent.roles import (
    DeterministicCandidateSurface,
    DeterministicSuccessCriterion,
    DeterministicSymbolSpace,
    DeterministicWorldModel,
    Layer0FunctionalLoss,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
MEMORY_FIXTURES = (
    REPOSITORY_ROOT / "datasets" / "memory_lifecycles" / "records.jsonl"
)


def retained_payload(
    *,
    state: str = "observed",
    evidence: str = "rendered-delta",
) -> dict[str, object]:
    return {
        "current_purpose": "evaluate-observed-transition",
        "current_state": state,
        "hypothesis": "action may change rendered state",
        "support": 1,
        "contradiction": 0,
        "failure": (),
        "evidence": (evidence,),
        "lifecycle": "ACTIVE",
        "unresolved_item": "terminal remains unobserved",
        "provenance": ("observation:current",),
        "version": "caller-proposed",
        "rollback_reference": "snapshot:0",
    }


def mutation(
    memory: PassiveMemory,
    operation: str,
    target: str,
    *,
    payload: dict[str, object] | None = None,
    lifecycle: str = "ACTIVE",
    source_targets: tuple[str, ...] = (),
    destination_targets: tuple[str, ...] = (),
    rollback_version: int | None = None,
) -> MemoryOperation:
    return MemoryOperation(
        operation=operation,
        target=target,
        expected_version=memory.version,
        lifecycle=lifecycle,
        evidence_signature=f"evidence:{operation.casefold()}",
        payload_items=tuple(sorted((payload or {}).items())),
        source_targets=source_targets,
        destination_targets=destination_targets,
        rollback_version=rollback_version,
        provenance=(f"test-operation:{operation.casefold()}",),
    )


def apply(
    memory: PassiveMemory,
    operation: MemoryOperation,
) -> MemoryMutationResult:
    result = memory.execute_storage(operation)
    if not isinstance(result, MemoryMutationResult):
        raise TypeError("expected MemoryMutationResult")
    return result


def raw_observation() -> dict[str, object]:
    return {
        "frame": [[0, 1], [1, 0]],
        "dimensions": [2, 2],
        "available_actions": [1, 2],
        "objects": [
            {
                "entity_id": "actor",
                "features": ["controllable", "foreground"],
            }
        ],
        "relations": ["adjacent"],
        "resources": ["bounded-action-budget"],
        "terminal_state": "RUNNING",
    }


class StandaloneMemoryOperationTests(unittest.TestCase):
    def test_all_storage_operations_have_distinct_working_semantics(self) -> None:
        memory = PassiveMemory(max_entries=8)
        observed_operations: set[str] = set()

        add_a = apply(
            memory,
            mutation(memory, "ADD", "experience:a", payload=retained_payload()),
        )
        observed_operations.add(add_a.operation)
        self.assertEqual(add_a.version, 1)

        read_result = memory.execute_storage(
            MemoryOperation(operation="READ", target="experience:a")
        )
        observed_operations.add("READ")
        self.assertIsInstance(read_result, MemoryEntry)
        assert isinstance(read_result, MemoryEntry)
        self.assertEqual(read_result.payload["current_state"], "observed")

        revise = apply(
            memory,
            mutation(
                memory,
                "REVISE",
                "experience:a",
                payload={"current_state": "revised", "support": 2},
            ),
        )
        observed_operations.add(revise.operation)
        revised = memory.read("experience:a")
        assert revised is not None
        self.assertEqual(revised.payload["current_state"], "revised")
        self.assertEqual(revised.payload["hypothesis"], read_result.payload["hypothesis"])

        apply(
            memory,
            mutation(
                memory,
                "ADD",
                "experience:b",
                payload={"evidence": ("second",), "support": 1},
            ),
        )
        observed_operations.add("ADD")
        merge = apply(
            memory,
            mutation(
                memory,
                "MERGE",
                "experience:merged",
                payload={"support": 3},
                source_targets=("experience:a", "experience:b"),
            ),
        )
        observed_operations.add(merge.operation)
        self.assertIsNone(memory.read("experience:a"))
        self.assertIsNone(memory.read("experience:b"))
        merged = memory.read("experience:merged")
        assert merged is not None
        self.assertEqual(merged.payload["support"], 3)

        split = apply(
            memory,
            mutation(
                memory,
                "SPLIT",
                "experience:merged",
                payload={
                    "parts": {
                        "experience:left": {
                            "branch": "left",
                            "evidence": ("left-evidence",),
                        },
                        "experience:right": {
                            "branch": "right",
                            "evidence": ("right-evidence",),
                        },
                    }
                },
                destination_targets=("experience:left", "experience:right"),
            ),
        )
        observed_operations.add(split.operation)
        self.assertIsNone(memory.read("experience:merged"))
        self.assertIsNotNone(memory.read("experience:left"))
        self.assertIsNotNone(memory.read("experience:right"))

        replace_result = apply(
            memory,
            mutation(
                memory,
                "REPLACE",
                "experience:left",
                payload={"replacement": "only-new-content"},
            ),
        )
        observed_operations.add(replace_result.operation)
        left = memory.read("experience:left")
        assert left is not None
        self.assertEqual(left.payload, {"replacement": "only-new-content"})

        invalidate = apply(
            memory,
            mutation(
                memory,
                "INVALIDATE",
                "experience:left",
                payload={"invalidation_reason": "counter-evidence"},
            ),
        )
        observed_operations.add(invalidate.operation)
        invalid = memory.read("experience:left")
        assert invalid is not None
        self.assertFalse(invalid.valid)
        self.assertEqual(invalid.lifecycle, "REJECTED")

        reindex = apply(
            memory,
            mutation(memory, "REINDEX", "experience:right"),
        )
        observed_operations.add(reindex.operation)
        right = memory.read("experience:right")
        assert right is not None
        self.assertIn("right", right.index_terms)

        archive = apply(
            memory,
            mutation(memory, "ARCHIVE", "experience:right"),
        )
        observed_operations.add(archive.operation)
        self.assertIsNone(memory.read("experience:right"))
        archived = memory.read("experience:right", include_archive=True)
        assert archived is not None
        self.assertTrue(archived.archived)
        self.assertEqual(archived.lifecycle, "ARCHIVED")

        query = MemoryQuery(
            terms=("right",),
            include_invalid=True,
            include_archive=True,
        )
        query_result = memory.execute_storage(
            MemoryOperation(operation="QUERY", query=query)
        )
        observed_operations.add("QUERY")
        self.assertIsInstance(query_result, MemoryQueryResult)
        assert isinstance(query_result, MemoryQueryResult)
        self.assertEqual(
            tuple(entry.target for entry in query_result.entries),
            ("experience:right",),
        )
        self.assertEqual(query_result, memory.query(query))

        historical_version = split.version
        delete = apply(
            memory,
            mutation(memory, "DELETE", "experience:left"),
        )
        observed_operations.add(delete.operation)
        self.assertIsNone(memory.read("experience:left", include_archive=True))

        version_result = memory.execute_storage(
            MemoryOperation(operation="VERSION")
        )
        observed_operations.add("VERSION")
        self.assertEqual(version_result, memory.version)

        snapshot_result = memory.execute_storage(
            MemoryOperation(
                operation="SNAPSHOT",
                expected_version=historical_version,
            )
        )
        observed_operations.add("SNAPSHOT")
        self.assertIsInstance(snapshot_result, MemorySnapshot)
        assert isinstance(snapshot_result, MemorySnapshot)
        self.assertEqual(snapshot_result.version, historical_version)

        provenance_result = memory.execute_storage(
            MemoryOperation(operation="PROVENANCE")
        )
        observed_operations.add("PROVENANCE")
        self.assertIsInstance(provenance_result, tuple)
        assert isinstance(provenance_result, tuple)
        self.assertTrue(
            all(
                isinstance(item, MemoryProvenanceEvent)
                for item in provenance_result
            )
        )

        rollback = apply(
            memory,
            mutation(
                memory,
                "ROLLBACK",
                "memory-state",
                rollback_version=historical_version,
            ),
        )
        observed_operations.add(rollback.operation)
        self.assertEqual(rollback.rollback_to_version, historical_version)
        self.assertGreater(rollback.version, delete.version)
        self.assertEqual(
            {entry.target for entry in memory.view().entries},
            {"experience:left", "experience:right"},
        )
        self.assertEqual(memory.view().archive_entries, ())

        self.assertEqual(observed_operations, ALL_MEMORY_OPERATIONS)

    def test_stale_version_is_rejected_without_state_change(self) -> None:
        memory = PassiveMemory()
        stale = mutation(
            memory,
            "ADD",
            "experience:stale",
            payload=retained_payload(),
        )
        apply(
            memory,
            mutation(
                memory,
                "ADD",
                "experience:fresh",
                payload=retained_payload(state="fresh"),
            ),
        )
        before = memory.view()

        with self.assertRaisesRegex(
            MemoryVersionConflict,
            "MEMORY_VERSION_CONFLICT",
        ):
            memory.execute_storage(stale)

        self.assertEqual(memory.view(), before)

    def test_query_is_deterministic_and_active_archive_are_separate(self) -> None:
        memory = PassiveMemory(max_entries=1)
        apply(
            memory,
            mutation(
                memory,
                "ADD",
                "experience:first",
                payload={"evidence": ("alpha",)},
            ),
        )
        apply(
            memory,
            mutation(
                memory,
                "ADD",
                "experience:second",
                payload={"evidence": ("beta",)},
            ),
        )
        snapshot = memory.view()
        self.assertEqual(
            tuple(entry.target for entry in snapshot.entries),
            ("experience:second",),
        )
        self.assertEqual(
            tuple(entry.target for entry in snapshot.archive_entries),
            ("experience:first",),
        )
        query = MemoryQuery(include_archive=True, include_invalid=True)
        self.assertEqual(memory.query(query), memory.query(query))

    def test_invalid_split_merge_and_identity_inputs_fail_closed(self) -> None:
        memory = PassiveMemory()
        apply(
            memory,
            mutation(
                memory,
                "ADD",
                "experience:source",
                payload={"evidence": ("safe",)},
            ),
        )
        bad_split = mutation(
            memory,
            "SPLIT",
            "experience:source",
            payload={"parts": {"experience:a": {"value": 1}}},
            destination_targets=("experience:a", "experience:b"),
        )
        with self.assertRaisesRegex(
            MemoryOperationError,
            "MEMORY_SPLIT_PARTS_MISMATCH",
        ):
            memory.execute_storage(bad_split)
        contaminated = mutation(
            memory,
            "REVISE",
            "experience:source",
            payload={"note": "task LS20-deadbeef"},
        )
        with self.assertRaisesRegex(
            MemoryOperationError,
            "MEMORY_RUNTIME_IDENTITY_FORBIDDEN",
        ):
            memory.execute_storage(contaminated)

        recursive: dict[str, object] = {}
        recursive["cycle"] = recursive
        noncanonical = mutation(
            memory,
            "REVISE",
            "experience:source",
            payload=recursive,
        )
        before = memory.view()
        with self.assertRaisesRegex(
            MemoryOperationError,
            "MEMORY_PAYLOAD_NOT_CANONICALIZABLE",
        ):
            memory.execute_storage(noncanonical)
        self.assertEqual(memory.view(), before)

    def test_reads_do_not_autonomously_mutate_or_judge(self) -> None:
        memory = PassiveMemory()
        before = memory.view()
        self.assertIsNone(memory.read("missing"))
        self.assertEqual(memory.query(MemoryQuery()).entries, ())
        self.assertEqual(memory.provenance(), ())
        self.assertEqual(memory.view(), before)

        source = Path(inspect.getsourcefile(PassiveMemory) or "").read_text(
            encoding="utf-8"
        )
        self.assertNotIn("HypothesisIR", source)
        self.assertNotIn("CandidateIR", source)
        self.assertNotIn("HDSJudgmentSubject", source)
        self.assertNotIn("execute_emission", source)

    def test_memory_removal_has_fixed_witness(self) -> None:
        harness = StandaloneMemoryHarness(memory_subject=None)
        with self.assertRaisesRegex(
            RuntimeError,
            MEMORY_SUBJECT_REMOVAL_WITNESS,
        ):
            harness.view()

        with self.assertRaises(Layer0FunctionalLoss) as raised:
            Layer0Kernel(
                Layer0Components(memory=None)
            ).run_cycle(raw_observation())
        self.assertEqual(raised.exception.role, "MEMORY_SUBJECT")
        self.assertEqual(
            raised.exception.reason,
            MEMORY_SUBJECT_REMOVAL_WITNESS,
        )
        self.assertEqual(raised.exception.stage, "RETRIEVE")
        self.assertTrue(raised.exception.removed)


class MemoryFixtureAndAuthorityTests(unittest.TestCase):
    def test_all_p3_memory_fixtures_are_typed_and_cover_mutations(self) -> None:
        fixtures = load_memory_lifecycle_fixtures(MEMORY_FIXTURES)
        counts = Counter(
            operation
            for fixture in fixtures
            for operation in fixture.operation_candidates
        )

        self.assertEqual(len(fixtures), 687)
        self.assertTrue(all(fixture.validate() == () for fixture in fixtures))
        self.assertEqual(set(counts), ALL_MEMORY_OPERATIONS - {
            "READ",
            "QUERY",
            "VERSION",
            "SNAPSHOT",
            "PROVENANCE",
        })
        self.assertEqual(counts["DELETE"], 1)
        self.assertEqual(counts["ROLLBACK"], 677)

    def test_runtime_rejects_stale_authorized_mutation(self) -> None:
        components = Layer0Components()
        memory = components.memory
        assert memory is not None
        symbol_space = cast(
            DeterministicSymbolSpace,
            components.symbol_space,
        )
        context_state = cast(BoundedContextState, components.context_state)
        world_model = cast(
            DeterministicWorldModel,
            components.world_model,
        )
        candidate_surface = cast(
            DeterministicCandidateSurface,
            components.candidate_surface,
        )
        instruction_body = cast(InstructionBody, components.instruction_body)
        success_criterion = cast(
            DeterministicSuccessCriterion,
            components.success_criterion,
        )
        observation = symbol_space.encode(raw_observation())
        context = context_state.ingest(observation)
        initial_memory = memory.view()
        command = components.hds.issue_compute(
            observation,
            context,
            initial_memory,
        )
        assert components.compute is not None
        proposal = components.compute.compute(
            command,
            components.hds,
            observation,
            context,
            initial_memory,
            world_model,
            candidate_surface,
            instruction_body,
        )
        context = context_state.condition(proposal.hypotheses)
        closures = success_criterion.evaluate(
            observation,
            context,
            proposal.hypotheses,
            proposal.candidates,
        )
        decision = components.hds.judge(
            command,
            proposal,
            closures,
            observation,
            context,
        )
        selected = next(
            item
            for item in proposal.candidates
            if item.candidate_id == decision.candidate_id
        )
        emission_directive = components.hds.emission_directive(
            decision,
            selected,
        )
        emission_result = components.compute.execute_emission(
            emission_directive,
            decision,
            selected,
            observation,
            components.emission_interface,
        )
        components.hds.observe_emission_result(
            decision,
            emission_directive,
            selected,
            observation,
            emission_result,
        )
        self.assertEqual(
            components.hds.judge_emission_result(decision, emission_result),
            "PASS",
        )
        memory_directive = components.hds.memory_directive(
            decision,
            proposal.memory_proposal,
        )
        self.assertEqual(memory_directive.expected_version, 0)

        apply(
            memory,
            mutation(
                memory,
                "ADD",
                "experience:competing",
                payload={"evidence": ("competing-write",)},
            ),
        )
        with self.assertRaisesRegex(
            AuthorityViolation,
            "MEMORY_VERSION_CONFLICT",
        ):
            components.compute.execute_memory(
                memory_directive,
                decision,
                proposal.memory_proposal,
                memory,
            )
        self.assertFalse(memory_directive.is_consumed)


if __name__ == "__main__":
    unittest.main()
