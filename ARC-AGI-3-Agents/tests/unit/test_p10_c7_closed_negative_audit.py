from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from arc3_agi_agent.p10_c7_closed_negative_audit import (
    build_p10_c7_closed_negative_audit,
)
from arc3_agi_agent.schema import digest_object

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_DIR = (
    REPOSITORY_ROOT
    / "evidence"
    / "p10"
    / "development"
    / "c7_target_contact_closed_negative_v1"
)
PROVENANCE_MANIFEST = REPOSITORY_ROOT / "manifests" / (
    "provenance_manifest.json"
)
LEGACY_ARTIFACT = EVIDENCE_DIR / (
    "LEGACY_C7_TARGET_CONTACT_BOUNDARY_CAPABILITY.json"
)
ADMISSION_AUDIT = EVIDENCE_DIR / (
    "C7_CLOSED_NEGATIVE_ADMISSION_AUDIT.json"
)


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected object: {path}")
    return value


class P10C7ClosedNegativeAuditTests(unittest.TestCase):
    def test_rebuilds_negative_only_admission_from_frozen_source(
        self,
    ) -> None:
        rebuilt = build_p10_c7_closed_negative_audit(
            provenance_manifest=_json(PROVENANCE_MANIFEST),
            legacy_artifact=_json(LEGACY_ARTIFACT),
            legacy_artifact_path=LEGACY_ARTIFACT,
        )

        self.assertEqual(rebuilt, _json(ADMISSION_AUDIT))
        body = dict(rebuilt)
        claimed = body.pop("content_digest")
        self.assertEqual(
            claimed,
            "arc3_p10_c7_closed_negative_admission:"
            + digest_object(body),
        )
        retained = rebuilt["retained_measurements"]
        self.assertEqual(retained["total_probe_count"], 288)
        self.assertEqual(retained["changed_probe_count"], 228)
        self.assertEqual(retained["contact_gain_probe_count"], 63)
        self.assertEqual(retained["total_progress_count"], 0)
        self.assertEqual(
            retained["promotion_eligible_variable_count"],
            0,
        )
        scope = rebuilt["admission_scope"]
        self.assertTrue(
            scope["admitted_for_negative_surface_closure"]
        )
        self.assertFalse(scope["admitted_for_runtime_compile"])
        self.assertTrue(
            scope["legacy_contract_spec_mismatch_quarantined"]
        )
        judgment = rebuilt["hds_judgment"]
        self.assertEqual(judgment["causal_result"], "CLOSED_NEGATIVE")
        self.assertFalse(judgment["same_surface_retry_authorized"])
        self.assertEqual(
            judgment["next_work_block_id"],
            "WB-C12_layout_mode_commit_discriminator",
        )

    def test_source_byte_drift_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            drifted = Path(temporary) / LEGACY_ARTIFACT.name
            drifted.write_bytes(LEGACY_ARTIFACT.read_bytes() + b"\n")

            with self.assertRaisesRegex(
                ValueError,
                "FROZEN_SOURCE_INVALID",
            ):
                build_p10_c7_closed_negative_audit(
                    provenance_manifest=_json(PROVENANCE_MANIFEST),
                    legacy_artifact=_json(LEGACY_ARTIFACT),
                    legacy_artifact_path=drifted,
                )

    def test_positive_claim_drift_is_rejected(self) -> None:
        artifact = _json(LEGACY_ARTIFACT)
        summary = artifact["summary"]
        assert isinstance(summary, dict)
        summary["total_progress_count"] = 1
        provenance = _json(PROVENANCE_MANIFEST)
        with tempfile.TemporaryDirectory() as temporary:
            altered_path = Path(temporary) / LEGACY_ARTIFACT.name
            altered_path.write_text(
                json.dumps(artifact, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            for descriptor in provenance["sources"]:
                if (
                    descriptor["path"]
                    == (
                        "analysis/"
                        "c7_target_contact_boundary_capability_latest.json"
                    )
                ):
                    descriptor["bytes"] = altered_path.stat().st_size
                    descriptor["sha256"] = hashlib.sha256(
                        altered_path.read_bytes()
                    ).hexdigest()
                    break

            with self.assertRaisesRegex(
                ValueError,
                "NEGATIVE_EVIDENCE_INVALID",
            ):
                build_p10_c7_closed_negative_audit(
                    provenance_manifest=provenance,
                    legacy_artifact=artifact,
                    legacy_artifact_path=altered_path,
                )


if __name__ == "__main__":
    unittest.main()
