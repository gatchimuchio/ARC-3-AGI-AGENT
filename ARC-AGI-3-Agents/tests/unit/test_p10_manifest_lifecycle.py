from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any

from arc3_agi_agent.p10_instruction_compiler import (
    active_p10_manifest_digest,
)
from arc3_agi_agent.p10_manifest_lifecycle import (
    P10_CANDIDATE_MANIFEST_FILENAME,
    P10_PREVIOUS_STABLE_MANIFEST_FILENAME,
    P10_PROMOTED_MANIFEST_FILENAME,
    P10_REJECTED_MANIFEST_FILENAME,
    rollback_p10_active_manifest,
)
from arc3_agi_agent.p10_promotion import (
    p_update_proposal_from_mapping,
    promote_p10_candidate_from_trace,
)
from arc3_agi_agent.p_update import CandidatePBundle, HDSPUpdateAuthority

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_ROOT = Path(__file__).resolve().parents[2]
SOURCE_BUNDLE_DIR = PACKAGE_ROOT / "arc3_agi_agent" / "bundles"
SOURCE_TRACE = (
    REPOSITORY_ROOT
    / "evidence"
    / "p10"
    / "p_update"
    / "iteration_20_regression"
    / "p10_candidate_compile_trace_v1.json"
)


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected object: {path}")
    return value


def _write_json(path: Path, value: object) -> None:
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _restore_pre_promotion_fixture(bundle_dir: Path) -> None:
    previous = _json(
        bundle_dir / P10_PREVIOUS_STABLE_MANIFEST_FILENAME
    )["manifest"]
    promoted = _json(bundle_dir / P10_PROMOTED_MANIFEST_FILENAME)
    candidate = dict(promoted)
    candidate["lifecycle"] = "CANDIDATE"
    for key in (
        "promoted_active_manifest_digest",
        "promotion_decision_digest",
        "promotion_directive_digest",
        "regression_report_digest",
    ):
        candidate.pop(key, None)
    _write_json(bundle_dir / "p10_manifest.json", previous)
    _write_json(
        bundle_dir / P10_CANDIDATE_MANIFEST_FILENAME,
        candidate,
    )


class P10ManifestLifecycleTests(unittest.TestCase):
    def test_hds_promotion_then_rollback_restores_exact_active_manifest(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle_dir = root / "bundles"
            shutil.copytree(SOURCE_BUNDLE_DIR, bundle_dir)
            _restore_pre_promotion_fixture(bundle_dir)
            original = _json(bundle_dir / "p10_manifest.json")
            original_digest = active_p10_manifest_digest(bundle_dir)
            receipt_path = root / "promotion.json"

            promotion = promote_p10_candidate_from_trace(
                bundle_dir=bundle_dir,
                trace_path=SOURCE_TRACE,
                receipt_path=receipt_path,
            )

            promoted = _json(bundle_dir / "p10_manifest.json")
            candidate_archive = _json(
                bundle_dir / P10_CANDIDATE_MANIFEST_FILENAME
            )
            self.assertEqual(promoted["lifecycle"], "ACTIVE")
            self.assertEqual(
                promoted["bundles"]["hybrid"]["body_version"],
                "p10-hybrid-v25",
            )
            self.assertEqual(candidate_archive["lifecycle"], "PROMOTED")
            self.assertTrue(
                (bundle_dir / P10_PREVIOUS_STABLE_MANIFEST_FILENAME).is_file()
            )
            self.assertTrue(promotion["active_changed"])

            trace = _json(SOURCE_TRACE)
            proposal = p_update_proposal_from_mapping(trace["proposal"])
            failed_active = CandidatePBundle(
                **promotion["promoted_active_descriptor"]
            )
            rollback_authority = HDSPUpdateAuthority()
            rollback_decision = rollback_authority.decide(
                proposal,
                status="ROLLBACK",
                reason_codes=("bounded-rollback-proof",),
                candidate_bundle=failed_active,
            )
            rollback_directive = (
                rollback_authority.issue_rollback_directive(
                    proposal,
                    failed_active,
                    rollback_decision,
                    rollback_bundle_digest=original_digest,
                )
            )

            rollback_receipt = rollback_p10_active_manifest(
                bundle_dir=bundle_dir,
                failed_active=failed_active,
                decision=rollback_decision,
                directive=rollback_directive,
                authority=rollback_authority,
            )

            self.assertEqual(
                _json(bundle_dir / "p10_manifest.json"),
                original,
            )
            self.assertEqual(
                active_p10_manifest_digest(bundle_dir),
                original_digest,
            )
            self.assertEqual(
                rollback_receipt.restored_active_manifest_digest,
                original_digest,
            )
            self.assertTrue(
                (bundle_dir / P10_REJECTED_MANIFEST_FILENAME).is_file()
            )

    def test_tampered_trace_is_rejected_before_manifest_change(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle_dir = root / "bundles"
            shutil.copytree(SOURCE_BUNDLE_DIR, bundle_dir)
            _restore_pre_promotion_fixture(bundle_dir)
            before_digest = active_p10_manifest_digest(bundle_dir)
            trace = _json(SOURCE_TRACE)
            trace["promotion_failures"] = ["TAMPERED"]
            tampered = root / "tampered.json"
            tampered.write_text(
                json.dumps(trace, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ValueError,
                "P10_PROMOTION_TRACE_DIGEST_MISMATCH",
            ):
                promote_p10_candidate_from_trace(
                    bundle_dir=bundle_dir,
                    trace_path=tampered,
                    receipt_path=root / "receipt.json",
                )

            self.assertEqual(
                active_p10_manifest_digest(bundle_dir),
                before_digest,
            )


if __name__ == "__main__":
    unittest.main()
