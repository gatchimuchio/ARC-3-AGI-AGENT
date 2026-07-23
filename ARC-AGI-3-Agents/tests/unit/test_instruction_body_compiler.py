from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from arc3_agi_agent.instruction_body import (
    PARAMETRIC_FEATURES,
    PARAMETRIC_HEADS,
    ParametricInstructionBody,
    SymbolicInstructionBody,
    instruction_body_from_mapping,
    load_default_parametric_instruction_body,
    load_default_symbolic_instruction_body,
    seal_instruction_bundle,
)
from arc3_agi_agent.instruction_compiler import compile_instruction_bodies

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = PACKAGE_ROOT.parent
BUNDLE_DIR = PACKAGE_ROOT / "arc3_agi_agent" / "bundles"
DATASET_DIR = REPOSITORY_ROOT / "datasets"
DATASET_MANIFEST = REPOSITORY_ROOT / "manifests" / "dataset_manifest.json"


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected object: {path}")
    return value


def _sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


class InstructionBodyBundleTests(unittest.TestCase):
    def test_committed_symbolic_body_is_executable_and_complete(self) -> None:
        body = load_default_symbolic_instruction_body()

        self.assertIsInstance(body, SymbolicInstructionBody)
        self.assertEqual(body.validate(), ())
        self.assertEqual({rule.action_id for rule in body.rules}, set(range(1, 8)))
        self.assertGreaterEqual(len(body.nodes), 8)
        self.assertGreaterEqual(len(body.edges), 7)
        self.assertEqual(len(body.rules), 7)
        self.assertTrue(body.contract.bound)
        self.assertTrue(body.contract.runtime_identity_free)

    def test_committed_parametric_body_is_trained_not_placeholder(self) -> None:
        body = load_default_parametric_instruction_body()
        flattened = tuple(value for row in body.weights for value in row)

        self.assertIsInstance(body, ParametricInstructionBody)
        self.assertEqual(body.validate(), ())
        self.assertEqual(body.feature_names, PARAMETRIC_FEATURES)
        self.assertEqual(body.heads, PARAMETRIC_HEADS)
        self.assertEqual(body.parameter_count, 72)
        self.assertEqual(len(flattened), 72)
        self.assertTrue(all(abs(value) > 1e-12 for value in flattened))
        self.assertGreater(body.training_record_count, 0)
        self.assertGreater(body.holdout_record_count, 0)

    def test_manifest_binds_bundle_hashes_and_learning_evidence(self) -> None:
        manifest = _json(BUNDLE_DIR / "manifest.json")
        symbolic = manifest["bundles"]["P-A"]
        parametric = manifest["bundles"]["P-B"]
        metrics = parametric["training_metrics"]

        self.assertEqual(
            symbolic["sha256"],
            _sha256(BUNDLE_DIR / symbolic["filename"]),
        )
        self.assertEqual(
            parametric["sha256"],
            _sha256(BUNDLE_DIR / parametric["filename"]),
        )
        self.assertEqual(
            symbolic["content_digest"],
            load_default_symbolic_instruction_body().digest(),
        )
        self.assertEqual(
            parametric["content_digest"],
            load_default_parametric_instruction_body().digest(),
        )
        self.assertLess(
            metrics["trained_train_bce"],
            metrics["baseline_train_bce"],
        )
        self.assertLess(
            metrics["trained_holdout_bce"],
            metrics["baseline_holdout_bce"],
        )
        self.assertGreater(metrics["validation_example_count"], 0)
        self.assertEqual(manifest["runtime_use"], "BUNDLE_INDEX_ONLY")

    def test_compiler_is_byte_deterministic_from_p3_fixtures(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            compile_instruction_bodies(
                dataset_dir=DATASET_DIR,
                dataset_manifest_path=DATASET_MANIFEST,
                output_dir=output_dir,
            )
            for filename in (
                "p_a_symbolic_v1.json",
                "p_b_parametric_v1.json",
                "manifest.json",
            ):
                self.assertEqual(
                    (output_dir / filename).read_bytes(),
                    (BUNDLE_DIR / filename).read_bytes(),
                    filename,
                )

    def test_compiler_rejects_noncanonical_seed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "seed is fixed at 0"):
                compile_instruction_bodies(
                    dataset_dir=DATASET_DIR,
                    dataset_manifest_path=DATASET_MANIFEST,
                    output_dir=Path(temporary),
                    seed=1,
                )

    def test_bundle_rejects_digest_schema_and_identity_tampering(self) -> None:
        original = _json(BUNDLE_DIR / "p_a_symbolic_v1.json")

        digest_tampered = copy.deepcopy(original)
        digest_tampered["body_version"] = "tampered"
        with self.assertRaisesRegex(
            ValueError,
            "INSTRUCTION_BODY_CONTENT_DIGEST_MISMATCH",
        ):
            instruction_body_from_mapping(digest_tampered)

        schema_tampered = copy.deepcopy(original)
        schema_tampered["contract"]["schema_version"] = "wrong-schema"
        schema_tampered = seal_instruction_bundle(schema_tampered)
        with self.assertRaisesRegex(
            ValueError,
            "INSTRUCTION_BODY_CONTRACT_SCHEMA_VERSION_INVALID",
        ):
            instruction_body_from_mapping(schema_tampered)

        identity_tampered = copy.deepcopy(original)
        identity_tampered["payload"]["task_id"] = "ls20-deadbeef"
        identity_tampered = seal_instruction_bundle(identity_tampered)
        with self.assertRaisesRegex(
            ValueError,
            "INSTRUCTION_BODY_RUNTIME_IDENTITY_FORBIDDEN",
        ):
            instruction_body_from_mapping(identity_tampered)


if __name__ == "__main__":
    unittest.main()
