from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from arc3_agi_agent.instruction_body import (
    load_p10_hybrid_instruction_body,
    load_p10_parametric_instruction_body,
    load_p10_symbolic_instruction_body,
)
from arc3_agi_agent.p10_instruction_compiler import (
    P10_COMPILER_SEED,
    compile_p10_instruction_bodies,
)
from arc3_agi_agent.semantic_operators import (
    OBJECT_TARGET_CONTROL_OPERATOR,
    RELATION_TOGGLE_OPERATOR,
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


class P10InstructionCompilerTests(unittest.TestCase):
    def test_committed_variants_have_explicit_operator_separation(self) -> None:
        symbolic = load_p10_symbolic_instruction_body()
        parametric = load_p10_parametric_instruction_body()
        hybrid = load_p10_hybrid_instruction_body()

        self.assertEqual(symbolic.validate(), ())
        self.assertEqual(parametric.validate(), ())
        self.assertEqual(hybrid.validate(), ())
        self.assertEqual(
            tuple(item.operator_id for item in symbolic.operator_instructions),
            (
                OBJECT_TARGET_CONTROL_OPERATOR,
                RELATION_TOGGLE_OPERATOR,
                SYMBOLIC_REWRITE_OPERATOR,
            ),
        )
        self.assertEqual(parametric.operator_instructions, ())
        self.assertEqual(
            tuple(item.operator_id for item in hybrid.operator_instructions),
            (
                OBJECT_TARGET_CONTROL_OPERATOR,
                RELATION_TOGGLE_OPERATOR,
                SYMBOLIC_REWRITE_OPERATOR,
            ),
        )
        self.assertNotEqual(symbolic.digest(), hybrid.digest())
        self.assertNotEqual(parametric.digest(), hybrid.digest())

    def test_compiler_is_byte_deterministic(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output_dir = Path(temporary)
            compile_p10_instruction_bodies(
                base_bundle_dir=BUNDLE_DIR,
                output_dir=output_dir,
            )
            for filename in (
                "p10_p_a_symbolic_v4.json",
                "p10_p_b_parametric_v4.json",
                "p10_hybrid_v3.json",
                "p10_manifest.json",
            ):
                self.assertEqual(
                    (output_dir / filename).read_bytes(),
                    (BUNDLE_DIR / filename).read_bytes(),
                    filename,
                )

    def test_manifest_binds_each_variant(self) -> None:
        manifest = _json(BUNDLE_DIR / "p10_manifest.json")
        expected_digests = {
            "P-A": load_p10_symbolic_instruction_body().digest(),
            "P-B": load_p10_parametric_instruction_body().digest(),
            "hybrid": load_p10_hybrid_instruction_body().digest(),
        }

        self.assertEqual(manifest["seed"], P10_COMPILER_SEED)
        self.assertTrue(manifest["runtime_identity_free"])
        for variant, expected_digest in expected_digests.items():
            entry = manifest["bundles"][variant]
            path = BUNDLE_DIR / entry["filename"]
            self.assertEqual(entry["content_digest"], expected_digest)
            self.assertEqual(entry["sha256"], _sha256(path))

    def test_compiler_rejects_noncanonical_seed(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "seed is fixed at 0"):
                compile_p10_instruction_bodies(
                    base_bundle_dir=BUNDLE_DIR,
                    output_dir=Path(temporary),
                    seed=1,
                )


if __name__ == "__main__":
    unittest.main()
