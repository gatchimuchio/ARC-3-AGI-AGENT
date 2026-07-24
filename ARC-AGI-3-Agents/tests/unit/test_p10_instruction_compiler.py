from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from arc3_agi_agent.instruction_body import (
    load_p10_candidate_hybrid_instruction_body,
    load_p10_candidate_parametric_instruction_body,
    load_p10_candidate_symbolic_instruction_body,
    load_p10_hybrid_instruction_body,
    load_p10_parametric_instruction_body,
    load_p10_symbolic_instruction_body,
)
from arc3_agi_agent.p10_instruction_compiler import (
    P10_CANDIDATE_SET_VERSION,
    P10_COMPILER_SEED,
    active_p10_manifest_digest,
    compile_p10_instruction_bodies,
)
from arc3_agi_agent.p_b_learning import PBLearningResult
from arc3_agi_agent.p_update import (
    HDSPUpdateAuthority,
    PUpdateEvidenceSet,
    PUpdateProposal,
    parameter_digest,
)
from arc3_agi_agent.schema import digest_object
from arc3_agi_agent.semantic_operators import (
    FRUIT_MERGE_TERMINAL_ACTOR_PROTECTION_CANDIDATE_OPERATOR,
    OBJECT_TARGET_CONTROL_OPERATOR,
    RELATION_TOGGLE_OPERATOR,
    SELECTABLE_PUSH_TARGET_OPERATOR,
    SELECTABLE_ROUTE_TARGET_OPERATOR,
    SYMBOLIC_REWRITE_OPERATOR,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
BUNDLE_DIR = PACKAGE_ROOT / "arc3_agi_agent" / "bundles"


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _learning_result() -> PBLearningResult:
    source = load_p10_parametric_instruction_body()
    mutable = [list(row) for row in source.weights]
    mutable[0][0] = round(mutable[0][0] + 0.001, 12)
    candidate = tuple(tuple(row) for row in mutable)
    return PBLearningResult(
        source_parameter_digest=parameter_digest(source.weights),
        candidate_parameter_digest=parameter_digest(candidate),
        candidate_weights=candidate,
        source_train_loss=1.0,
        candidate_train_loss=0.9,
        source_holdout_loss=1.0,
        candidate_holdout_loss=1.0,
        learning_rate=0.001,
        epochs=1,
        seed=0,
        dataset_digest="dataset:authorized",
        training_example_count=4,
        holdout_example_count=1,
        same_input_example_digest="example:witness",
        source_same_input_output_digest=digest_object(("source",)),
        candidate_same_input_output_digest=digest_object(("candidate",)),
        changed_parameters=("effect:bias",),
        attribution="unit-fixture-authorized-learning-result",
    )


def _compile_authorization() -> tuple[
    HDSPUpdateAuthority,
    object,
    object,
]:
    source_digest = active_p10_manifest_digest(BUNDLE_DIR)
    proposal = PUpdateProposal(
        proposal_id="proposal:instruction-body-set",
        source_p_version="p10-active-set",
        source_p_digest=source_digest,
        target_component="instruction-body-set",
        update_type="symbolic-parametric-composition",
        evidence_refs=("evidence:authorized-learning",),
        expected_effect="compile-isolated-candidate-set",
        expected_affected_capabilities=("candidate-instruction-body-set",),
        expected_unaffected_capabilities=("stable-active-runtime",),
        falsifiers=("candidate-rebuild-differs",),
        rollback_target="p10-active-set",
        provenance=("memory:approved",),
    )
    evidence = PUpdateEvidenceSet(
        evidence_set_id="evidence-set:instruction-body-set",
        proposal_digest=proposal.digest,
        memory_snapshot_digest="memory-snapshot:authorized",
        approved_memory_refs=("memory:learning",),
        hds_memory_decision_digests=("hds-decision:learning",),
        failure_refs=("failure:stagnation",),
        contradiction_refs=("contradiction:prediction",),
        positive_contrast_refs=("contrast:positive",),
        negative_contrast_refs=("contrast:negative",),
        holdout_refs=("holdout:structure",),
        replay_audit_refs=("audit:no-replay",),
        provenance=("runtime-memory:authorized",),
    )
    hds = HDSPUpdateAuthority()
    decision = hds.decide(
        proposal,
        status="COMPILE",
        reason_codes=("evidence-set-closed",),
        evidence_set=evidence,
    )
    directive = hds.issue_compile_directive(
        proposal,
        evidence,
        decision,
        target_body_version=P10_CANDIDATE_SET_VERSION,
        seed=P10_COMPILER_SEED,
    )
    return hds, decision, directive


class P10InstructionCompilerTests(unittest.TestCase):
    def test_candidate_variants_have_explicit_operator_separation(self) -> None:
        symbolic = load_p10_candidate_symbolic_instruction_body()
        parametric = load_p10_candidate_parametric_instruction_body()
        hybrid = load_p10_candidate_hybrid_instruction_body()

        self.assertEqual(symbolic.validate(), ())
        self.assertEqual(parametric.validate(), ())
        self.assertEqual(hybrid.validate(), ())
        self.assertEqual(
            tuple(item.operator_id for item in symbolic.operator_instructions),
            (
                OBJECT_TARGET_CONTROL_OPERATOR,
                RELATION_TOGGLE_OPERATOR,
                FRUIT_MERGE_TERMINAL_ACTOR_PROTECTION_CANDIDATE_OPERATOR,
                SYMBOLIC_REWRITE_OPERATOR,
                SELECTABLE_PUSH_TARGET_OPERATOR,
                SELECTABLE_ROUTE_TARGET_OPERATOR,
            ),
        )
        self.assertEqual(parametric.operator_instructions, ())
        self.assertEqual(
            tuple(item.operator_id for item in hybrid.operator_instructions),
            (
                OBJECT_TARGET_CONTROL_OPERATOR,
                RELATION_TOGGLE_OPERATOR,
                FRUIT_MERGE_TERMINAL_ACTOR_PROTECTION_CANDIDATE_OPERATOR,
                SYMBOLIC_REWRITE_OPERATOR,
                SELECTABLE_PUSH_TARGET_OPERATOR,
                SELECTABLE_ROUTE_TARGET_OPERATOR,
            ),
        )
        fruit_instruction = next(
            item
            for item in hybrid.operator_instructions
            if item.operator_id
            == FRUIT_MERGE_TERMINAL_ACTOR_PROTECTION_CANDIDATE_OPERATOR
        )
        self.assertEqual(
            fruit_instruction.parameters()["actor_divert_interval"],
            1,
        )
        self.assertEqual(
            fruit_instruction.parameters()[
                "maximum_transition_observations"
            ],
            4,
        )
        self.assertNotEqual(symbolic.digest(), hybrid.digest())
        self.assertNotEqual(parametric.digest(), hybrid.digest())

    def test_compiler_is_byte_deterministic(self) -> None:
        with (
            tempfile.TemporaryDirectory() as first_temporary,
            tempfile.TemporaryDirectory() as second_temporary,
        ):
            first_output = Path(first_temporary)
            second_output = Path(second_temporary)
            first_hds, first_decision, first_directive = (
                _compile_authorization()
            )
            second_hds, second_decision, second_directive = (
                _compile_authorization()
            )
            compile_p10_instruction_bodies(
                base_bundle_dir=BUNDLE_DIR,
                output_dir=first_output,
                compile_directive=first_directive,
                compile_decision=first_decision,
                hds_authority=first_hds,
                learning_result=_learning_result(),
            )
            compile_p10_instruction_bodies(
                base_bundle_dir=BUNDLE_DIR,
                output_dir=second_output,
                compile_directive=second_directive,
                compile_decision=second_decision,
                hds_authority=second_hds,
                learning_result=_learning_result(),
            )
            for filename in (
                "p10_p_a_symbolic_v23.json",
                "p10_p_b_parametric_v23.json",
                "p10_hybrid_v22.json",
                "p10_candidate_manifest.json",
            ):
                self.assertEqual(
                    (first_output / filename).read_bytes(),
                    (second_output / filename).read_bytes(),
                    filename,
                )

    def test_candidate_manifest_binds_each_variant(self) -> None:
        manifest = _json(BUNDLE_DIR / "p10_candidate_manifest.json")
        expected_digests = {
            "P-A": load_p10_candidate_symbolic_instruction_body().digest(),
            "P-B": load_p10_candidate_parametric_instruction_body().digest(),
            "hybrid": load_p10_candidate_hybrid_instruction_body().digest(),
        }

        self.assertEqual(manifest["seed"], P10_COMPILER_SEED)
        self.assertTrue(manifest["runtime_identity_free"])
        self.assertEqual(manifest["lifecycle"], "PROMOTED")
        self.assertEqual(
            manifest["activation_authority"],
            "hds-promotion-required",
        )
        for variant, expected_digest in expected_digests.items():
            entry = manifest["bundles"][variant]
            path = BUNDLE_DIR / entry["filename"]
            self.assertEqual(entry["content_digest"], expected_digest)
            self.assertEqual(entry["sha256"], _sha256(path))

    def test_runtime_loaders_resolve_promoted_active_and_archive(self) -> None:
        active = (
            load_p10_symbolic_instruction_body(),
            load_p10_parametric_instruction_body(),
            load_p10_hybrid_instruction_body(),
        )
        candidate = (
            load_p10_candidate_symbolic_instruction_body(),
            load_p10_candidate_parametric_instruction_body(),
            load_p10_candidate_hybrid_instruction_body(),
        )

        self.assertEqual(
            tuple(body.body_version for body in active),
            (
                "p10-p-a-symbolic-v23",
                "p10-p-b-parametric-v23",
                "p10-hybrid-v22",
            ),
        )
        self.assertTrue(
            all(
                active_body.digest() == candidate_body.digest()
                for active_body, candidate_body in zip(
                    active,
                    candidate,
                    strict=True,
                )
            )
        )

    def test_compiler_rejects_noncanonical_seed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            hds, decision, directive = _compile_authorization()
            with self.assertRaisesRegex(ValueError, "seed is fixed at 0"):
                compile_p10_instruction_bodies(
                    base_bundle_dir=BUNDLE_DIR,
                    output_dir=Path(temporary),
                    compile_directive=directive,
                    compile_decision=decision,
                    hds_authority=hds,
                    learning_result=_learning_result(),
                    seed=1,
                )


if __name__ == "__main__":
    unittest.main()
