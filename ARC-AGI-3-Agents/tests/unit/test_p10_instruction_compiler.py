from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from arc3_agi_agent.instruction_body import (
    InstructionBody,
    instruction_body_from_mapping,
    load_p10_candidate_hybrid_instruction_body,
    load_p10_candidate_parametric_instruction_body,
    load_p10_candidate_symbolic_instruction_body,
    load_p10_hybrid_instruction_body,
    load_p10_parametric_instruction_body,
    load_p10_symbolic_instruction_body,
)
from arc3_agi_agent.p10_instruction_compiler import (
    P10_C2_C10_CANDIDATE_SET_VERSION,
    P10_C2_C10_SYMBOLIC_FILENAME,
    P10_CANDIDATE_SET_VERSION,
    P10_COMPILER_SEED,
    P10_DIRECTIONAL_SETTLE_CANDIDATE_SET_VERSION,
    P10_DIRECTIONAL_SETTLE_HYBRID_FILENAME,
    active_p10_manifest_digest,
    compile_p10_c2_c10_symbolic_candidate,
    compile_p10_directional_settle_hybrid_candidate,
    compile_p10_instruction_bodies,
)
from arc3_agi_agent.p_b_learning import PBLearningResult
from arc3_agi_agent.p_update import (
    HDSPUpdateAuthority,
    InstructionBodyCompileDirective,
    PUpdateDecision,
    PUpdateEvidenceSet,
    PUpdateProposal,
    parameter_digest,
)
from arc3_agi_agent.schema import digest_object
from arc3_agi_agent.semantic_operators import (
    DIRECTIONAL_FORCE_ROUTE_OPERATOR,
    FRUIT_MERGE_TERMINAL_ACTOR_PROTECTION_CANDIDATE_OPERATOR,
    MULTI_ACTOR_SHAPE_PUSH_TARGET_OPERATOR,
    OBJECT_TARGET_CONTROL_OPERATOR,
    OCCLUDED_TARGET_ROUTE_OPERATOR,
    RELATION_TOGGLE_OPERATOR,
    SELECTABLE_PUSH_TARGET_OPERATOR,
    SELECTABLE_ROUTE_TARGET_OPERATOR,
    SYMBOLIC_REWRITE_OPERATOR,
)
from arc3_agi_agent.shape_push import MARKER_SHAPE_PUSH_TARGET_OPERATOR
from arc3_agi_agent.visual_explorer import (
    ONE_STEP_VISIBLE_CAUSAL_CONTEXT_POLICY,
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
    PUpdateDecision,
    InstructionBodyCompileDirective,
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


def _c2_c10_compile_authorization() -> tuple[
    HDSPUpdateAuthority,
    PUpdateDecision,
    InstructionBodyCompileDirective,
]:
    source_digest = active_p10_manifest_digest(BUNDLE_DIR)
    proposal = PUpdateProposal(
        proposal_id="proposal:c2-c10-symbolic",
        source_p_version="p10-active-set",
        source_p_digest=source_digest,
        target_component="P-A",
        update_type="symbolic-capability-composition",
        evidence_refs=("evidence:c2-c10-composable",),
        expected_effect="bounded-visible-context-reopens-safe-action",
        expected_affected_capabilities=("causal-context-exploration",),
        expected_unaffected_capabilities=("active-runtime-manifest",),
        falsifiers=("stable-regression-decreases",),
        rollback_target="p10-p-a-symbolic-v27",
        provenance=("development-memory:hds-accepted",),
    )
    evidence = PUpdateEvidenceSet(
        evidence_set_id="evidence-set:c2-c10-composable",
        proposal_digest=proposal.digest,
        memory_snapshot_digest="memory-snapshot:c2-c10-composable",
        approved_memory_refs=("memory:c2-observer", "memory:c10-context"),
        hds_memory_decision_digests=("hds-decision:c2-c10",),
        failure_refs=("failure:context-ambiguity",),
        contradiction_refs=("contradiction:action-only-prediction",),
        positive_contrast_refs=("contrast:full-composition",),
        negative_contrast_refs=("contrast:remove-c2", "contrast:remove-c10"),
        holdout_refs=("holdout:mechanism-transfer",),
        replay_audit_refs=("audit:identity-free",),
        provenance=("development-evidence:content-addressed",),
    )
    hds = HDSPUpdateAuthority()
    decision = hds.decide(
        proposal,
        status="COMPILE",
        reason_codes=("c2-c10-composable-pass",),
        evidence_set=evidence,
    )
    directive = hds.issue_compile_directive(
        proposal,
        evidence,
        decision,
        target_body_version=P10_C2_C10_CANDIDATE_SET_VERSION,
        seed=P10_COMPILER_SEED,
    )
    return hds, decision, directive


def _directional_settle_compile_authorization() -> tuple[
    HDSPUpdateAuthority,
    PUpdateDecision,
    InstructionBodyCompileDirective,
]:
    source_digest = active_p10_manifest_digest(BUNDLE_DIR)
    proposal = PUpdateProposal(
        proposal_id="proposal:directional-settle-hybrid",
        source_p_version="p10-active-set",
        source_p_digest=source_digest,
        target_component="hybrid-P-B",
        update_type="transition-parameter",
        evidence_refs=("evidence:directional-settle-composable",),
        expected_effect="bounded-post-progress-reobservation",
        expected_affected_capabilities=("directional-force-obligation",),
        expected_unaffected_capabilities=("active-runtime-manifest",),
        falsifiers=("stable-regression-decreases",),
        rollback_target="p10-hybrid-v26",
        provenance=("development-memory:hds-accepted",),
    )
    evidence = PUpdateEvidenceSet(
        evidence_set_id="evidence-set:directional-settle-composable",
        proposal_digest=proposal.digest,
        memory_snapshot_digest="memory-snapshot:directional-settle",
        approved_memory_refs=("memory:c2-observer", "memory:c5-settle"),
        hds_memory_decision_digests=("hds-decision:directional-settle",),
        failure_refs=("failure:stale-transition-frame",),
        contradiction_refs=("contradiction:parseable-successor",),
        positive_contrast_refs=("contrast:bounded-settle",),
        negative_contrast_refs=("contrast:no-settle",),
        holdout_refs=("holdout:reflected-and-rotated-structure",),
        replay_audit_refs=("audit:identity-free",),
        provenance=("development-evidence:content-addressed",),
    )
    hds = HDSPUpdateAuthority()
    decision = hds.decide(
        proposal,
        status="COMPILE",
        reason_codes=("directional-settle-composition-probe",),
        evidence_set=evidence,
    )
    directive = hds.issue_compile_directive(
        proposal,
        evidence,
        decision,
        target_body_version=P10_DIRECTIONAL_SETTLE_CANDIDATE_SET_VERSION,
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
                DIRECTIONAL_FORCE_ROUTE_OPERATOR,
                MARKER_SHAPE_PUSH_TARGET_OPERATOR,
                MULTI_ACTOR_SHAPE_PUSH_TARGET_OPERATOR,
                OBJECT_TARGET_CONTROL_OPERATOR,
                OCCLUDED_TARGET_ROUTE_OPERATOR,
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
                DIRECTIONAL_FORCE_ROUTE_OPERATOR,
                MARKER_SHAPE_PUSH_TARGET_OPERATOR,
                MULTI_ACTOR_SHAPE_PUSH_TARGET_OPERATOR,
                OBJECT_TARGET_CONTROL_OPERATOR,
                OCCLUDED_TARGET_ROUTE_OPERATOR,
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
                "p10_p_a_symbolic_v27.json",
                "p10_p_b_parametric_v27.json",
                "p10_hybrid_v26.json",
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
        active: tuple[InstructionBody, ...] = (
            load_p10_symbolic_instruction_body(),
            load_p10_parametric_instruction_body(),
            load_p10_hybrid_instruction_body(),
        )
        candidate: tuple[InstructionBody, ...] = (
            load_p10_candidate_symbolic_instruction_body(),
            load_p10_candidate_parametric_instruction_body(),
            load_p10_candidate_hybrid_instruction_body(),
        )

        self.assertEqual(
            tuple(body.body_version for body in active),
            (
                "p10-p-a-symbolic-v27",
                "p10-p-b-parametric-v27",
                "p10-hybrid-v26",
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

    def test_c2_c10_compiler_changes_only_candidate_p_a(self) -> None:
        active_manifest_before = (
            BUNDLE_DIR / "p10_manifest.json"
        ).read_bytes()
        active = _json(BUNDLE_DIR / "p10_manifest.json")
        active_bundles = active.get("bundles")
        if not isinstance(active_bundles, dict):
            raise TypeError("active manifest bundles invalid")
        active_files_before = {
            str(entry["filename"]): (
                BUNDLE_DIR / str(entry["filename"])
            ).read_bytes()
            for entry in active_bundles.values()
            if isinstance(entry, dict)
        }
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            hds, decision, directive = _c2_c10_compile_authorization()
            manifest = compile_p10_c2_c10_symbolic_candidate(
                base_bundle_dir=BUNDLE_DIR,
                output_dir=output,
                compile_directive=directive,
                compile_decision=decision,
                hds_authority=hds,
                composition_audit_digest=(
                    "arc3_p10_c2_c10_composition_audit:unit"
                ),
            )
            candidate = instruction_body_from_mapping(
                _json(output / P10_C2_C10_SYMBOLIC_FILENAME)
            )
            operator_ids = tuple(
                item.operator_id for item in candidate.operator_instructions
            )

            self.assertTrue(directive.consumed)
            self.assertEqual(manifest["lifecycle"], "CANDIDATE")
            self.assertEqual(manifest["candidate_target_component"], "P-A")
            self.assertEqual(
                operator_ids.count(ONE_STEP_VISIBLE_CAUSAL_CONTEXT_POLICY),
                1,
            )
            self.assertNotIn(
                ONE_STEP_VISIBLE_CAUSAL_CONTEXT_POLICY,
                tuple(
                    item.operator_id
                    for item in load_p10_symbolic_instruction_body()
                    .operator_instructions
                ),
            )
            manifest_bundles = manifest.get("bundles")
            if not isinstance(manifest_bundles, dict):
                raise TypeError("candidate manifest bundles invalid")
            for variant in ("P-B", "hybrid"):
                self.assertEqual(
                    manifest_bundles[variant],
                    active_bundles[variant],
                )

        self.assertEqual(
            (BUNDLE_DIR / "p10_manifest.json").read_bytes(),
            active_manifest_before,
        )
        for filename, content in active_files_before.items():
            self.assertEqual((BUNDLE_DIR / filename).read_bytes(), content)

    def test_c2_c10_compiler_is_byte_deterministic(self) -> None:
        with (
            tempfile.TemporaryDirectory() as first_temporary,
            tempfile.TemporaryDirectory() as second_temporary,
        ):
            outputs = (Path(first_temporary), Path(second_temporary))
            for output in outputs:
                hds, decision, directive = _c2_c10_compile_authorization()
                compile_p10_c2_c10_symbolic_candidate(
                    base_bundle_dir=BUNDLE_DIR,
                    output_dir=output,
                    compile_directive=directive,
                    compile_decision=decision,
                    hds_authority=hds,
                    composition_audit_digest=(
                        "arc3_p10_c2_c10_composition_audit:unit"
                    ),
                )
            active_bundles = _json(
                BUNDLE_DIR / "p10_manifest.json"
            )["bundles"]
            reused_filenames = tuple(
                str(active_bundles[variant]["filename"])
                for variant in ("P-B", "hybrid")
            )
            compared = (
                P10_C2_C10_SYMBOLIC_FILENAME,
                *reused_filenames,
                "p10_candidate_manifest.json",
            )
            for filename in compared:
                self.assertEqual(
                    (outputs[0] / filename).read_bytes(),
                    (outputs[1] / filename).read_bytes(),
                    filename,
                )

    def test_directional_settle_compiler_changes_only_candidate_hybrid(
        self,
    ) -> None:
        active_manifest_before = (
            BUNDLE_DIR / "p10_manifest.json"
        ).read_bytes()
        active = _json(BUNDLE_DIR / "p10_manifest.json")
        active_bundles = active.get("bundles")
        if not isinstance(active_bundles, dict):
            raise TypeError("active manifest bundles invalid")
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary)
            hds, decision, directive = (
                _directional_settle_compile_authorization()
            )
            manifest = compile_p10_directional_settle_hybrid_candidate(
                base_bundle_dir=BUNDLE_DIR,
                output_dir=output,
                compile_directive=directive,
                compile_decision=decision,
                hds_authority=hds,
                composition_audit_digest=(
                    "arc3_p10_directional_settle_composition_audit:unit"
                ),
                maximum_transition_observations=8,
            )
            candidate = instruction_body_from_mapping(
                _json(output / P10_DIRECTIONAL_SETTLE_HYBRID_FILENAME)
            )
            directional = next(
                item
                for item in candidate.operator_instructions
                if item.operator_id == DIRECTIONAL_FORCE_ROUTE_OPERATOR
            )

            self.assertTrue(directive.consumed)
            self.assertEqual(manifest["lifecycle"], "CANDIDATE")
            self.assertEqual(
                manifest["candidate_target_component"],
                "hybrid-P-B",
            )
            self.assertEqual(
                directional.parameters()[
                    "maximum_transition_observations"
                ],
                8,
            )
            manifest_bundles = manifest.get("bundles")
            if not isinstance(manifest_bundles, dict):
                raise TypeError("candidate manifest bundles invalid")
            for variant in ("P-A", "P-B"):
                self.assertEqual(
                    manifest_bundles[variant],
                    active_bundles[variant],
                )
            self.assertNotEqual(
                manifest_bundles["hybrid"],
                active_bundles["hybrid"],
            )

        self.assertEqual(
            (BUNDLE_DIR / "p10_manifest.json").read_bytes(),
            active_manifest_before,
        )
        active_directional = next(
            item
            for item in load_p10_hybrid_instruction_body()
            .operator_instructions
            if item.operator_id == DIRECTIONAL_FORCE_ROUTE_OPERATOR
        )
        self.assertNotIn(
            "maximum_transition_observations",
            active_directional.parameters(),
        )

    def test_directional_settle_compiler_is_byte_deterministic(
        self,
    ) -> None:
        with (
            tempfile.TemporaryDirectory() as first_temporary,
            tempfile.TemporaryDirectory() as second_temporary,
        ):
            outputs = (Path(first_temporary), Path(second_temporary))
            for output in outputs:
                hds, decision, directive = (
                    _directional_settle_compile_authorization()
                )
                compile_p10_directional_settle_hybrid_candidate(
                    base_bundle_dir=BUNDLE_DIR,
                    output_dir=output,
                    compile_directive=directive,
                    compile_decision=decision,
                    hds_authority=hds,
                    composition_audit_digest=(
                        "arc3_p10_directional_settle_composition_audit:unit"
                    ),
                )
            active_bundles = _json(
                BUNDLE_DIR / "p10_manifest.json"
            )["bundles"]
            reused_filenames = tuple(
                str(active_bundles[variant]["filename"])
                for variant in ("P-A", "P-B")
            )
            compared = (
                P10_DIRECTIONAL_SETTLE_HYBRID_FILENAME,
                *reused_filenames,
                "p10_candidate_manifest.json",
            )
            for filename in compared:
                self.assertEqual(
                    (outputs[0] / filename).read_bytes(),
                    (outputs[1] / filename).read_bytes(),
                    filename,
                )


if __name__ == "__main__":
    unittest.main()
