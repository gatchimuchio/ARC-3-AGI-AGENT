from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from arc3_agi_agent.p10_c1_closed_negative_audit import (
    build_p10_c1_closed_negative_audit,
)
from arc3_agi_agent.schema import digest_object

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_DIR = (
    REPOSITORY_ROOT
    / "evidence"
    / "p10"
    / "development"
    / "c1_rendered_affordance_closed_negative_v1"
)
PROVENANCE_MANIFEST = REPOSITORY_ROOT / "manifests" / (
    "provenance_manifest.json"
)
LEGACY_ARTIFACT = EVIDENCE_DIR / (
    "LEGACY_C1_RENDERED_AFFORDANCE_OBJECTIZER_CAPABILITY.json"
)
ADMISSION_AUDIT = EVIDENCE_DIR / (
    "C1_CLOSED_NEGATIVE_ADMISSION_AUDIT.json"
)


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected object: {path}")
    return value


def _update_descriptor(
    provenance: dict[str, Any],
    artifact_path: Path,
) -> None:
    source_path = (
        "analysis/"
        "c1_rendered_affordance_objectizer_capability_latest.json"
    )
    for descriptor in provenance["sources"]:
        if descriptor["path"] == source_path:
            descriptor["bytes"] = artifact_path.stat().st_size
            descriptor["sha256"] = hashlib.sha256(
                artifact_path.read_bytes()
            ).hexdigest()
            return
    raise AssertionError(f"source descriptor missing: {source_path}")


class P10C1ClosedNegativeAuditTests(unittest.TestCase):
    def test_rebuilds_negative_only_admission(self) -> None:
        rebuilt = build_p10_c1_closed_negative_audit(
            provenance_manifest=_json(PROVENANCE_MANIFEST),
            legacy_artifact=_json(LEGACY_ARTIFACT),
            legacy_artifact_path=LEGACY_ARTIFACT,
        )

        self.assertEqual(rebuilt, _json(ADMISSION_AUDIT))
        body = dict(rebuilt)
        claimed = body.pop("content_digest")
        self.assertEqual(
            claimed,
            "arc3_p10_c1_closed_negative_admission:"
            + digest_object(body),
        )
        retained = rebuilt["retained_measurements"]
        self.assertEqual(retained["total_probe_count"], 1768)
        self.assertEqual(retained["prefix_progress_count"], 2)
        self.assertEqual(retained["non_prefix_candidate_count"], 1720)
        self.assertEqual(retained["non_prefix_progress_count"], 0)
        self.assertEqual(
            retained["promotion_eligible_variable_count"],
            0,
        )
        scope = rebuilt["admission_scope"]
        self.assertTrue(scope["task_aware_prefix_progress_quarantined"])
        self.assertFalse(scope["admitted_for_runtime_compile"])
        judgment = rebuilt["hds_judgment"]
        self.assertEqual(judgment["causal_result"], "CLOSED_NEGATIVE")
        self.assertFalse(judgment["same_surface_retry_authorized"])
        self.assertEqual(
            judgment["next_work_block_id"],
            "WB-C14_symbolic_relation_commit_model",
        )

    def test_source_byte_drift_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            drifted = Path(temporary) / LEGACY_ARTIFACT.name
            drifted.write_bytes(LEGACY_ARTIFACT.read_bytes() + b"\n")

            with self.assertRaisesRegex(
                ValueError,
                "FROZEN_SOURCE_INVALID",
            ):
                build_p10_c1_closed_negative_audit(
                    provenance_manifest=_json(PROVENANCE_MANIFEST),
                    legacy_artifact=_json(LEGACY_ARTIFACT),
                    legacy_artifact_path=drifted,
                )

    def test_non_prefix_positive_claim_drift_is_rejected(self) -> None:
        artifact = _json(LEGACY_ARTIFACT)
        games = artifact["games"]
        assert isinstance(games, list)
        bp35 = games[0]
        assert isinstance(bp35, dict)
        summary = bp35["summary"]
        assert isinstance(summary, dict)
        summary["post_level1_progress_count"] = 1
        provenance = _json(PROVENANCE_MANIFEST)
        with tempfile.TemporaryDirectory() as temporary:
            altered_path = Path(temporary) / LEGACY_ARTIFACT.name
            altered_path.write_text(
                json.dumps(artifact, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            _update_descriptor(provenance, altered_path)

            with self.assertRaisesRegex(
                ValueError,
                "NEGATIVE_EVIDENCE_INVALID",
            ):
                build_p10_c1_closed_negative_audit(
                    provenance_manifest=provenance,
                    legacy_artifact=artifact,
                    legacy_artifact_path=altered_path,
                )

    def test_promotion_variable_drift_is_rejected(self) -> None:
        artifact = _json(LEGACY_ARTIFACT)
        support = artifact["support_variables"]
        assert isinstance(support, list)
        first = support[0]
        assert isinstance(first, dict)
        first["promotion_eligible"] = True
        provenance = _json(PROVENANCE_MANIFEST)
        with tempfile.TemporaryDirectory() as temporary:
            altered_path = Path(temporary) / LEGACY_ARTIFACT.name
            altered_path.write_text(
                json.dumps(artifact, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            _update_descriptor(provenance, altered_path)

            with self.assertRaisesRegex(
                ValueError,
                "NEGATIVE_EVIDENCE_INVALID",
            ):
                build_p10_c1_closed_negative_audit(
                    provenance_manifest=provenance,
                    legacy_artifact=artifact,
                    legacy_artifact_path=altered_path,
                )


if __name__ == "__main__":
    unittest.main()
