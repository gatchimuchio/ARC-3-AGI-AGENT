from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from arc3_agi_agent.p10_c12_closed_negative_audit import (
    build_p10_c12_closed_negative_audit,
)
from arc3_agi_agent.schema import digest_object

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_DIR = (
    REPOSITORY_ROOT
    / "evidence"
    / "p10"
    / "development"
    / "c12_layout_mode_closed_negative_v1"
)
PROVENANCE_MANIFEST = REPOSITORY_ROOT / "manifests" / (
    "provenance_manifest.json"
)
PRIMARY_ARTIFACT = EVIDENCE_DIR / (
    "LEGACY_C12_LAYOUT_MODE_COMMIT_DISCRIMINATOR_CAPABILITY.json"
)
AUXILIARY_ARTIFACT = EVIDENCE_DIR / (
    "LEGACY_LAYOUT_MODE_DISCRIMINATOR_HARNESS.json"
)
ADMISSION_AUDIT = EVIDENCE_DIR / (
    "C12_CLOSED_NEGATIVE_ADMISSION_AUDIT.json"
)


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected object: {path}")
    return value


def _update_descriptor(
    provenance: dict[str, Any],
    *,
    source_path: str,
    artifact_path: Path,
) -> None:
    for descriptor in provenance["sources"]:
        if descriptor["path"] == source_path:
            descriptor["bytes"] = artifact_path.stat().st_size
            descriptor["sha256"] = hashlib.sha256(
                artifact_path.read_bytes()
            ).hexdigest()
            return
    raise AssertionError(f"source descriptor missing: {source_path}")


class P10C12ClosedNegativeAuditTests(unittest.TestCase):
    def test_rebuilds_two_source_negative_only_admission(
        self,
    ) -> None:
        rebuilt = build_p10_c12_closed_negative_audit(
            provenance_manifest=_json(PROVENANCE_MANIFEST),
            primary_artifact=_json(PRIMARY_ARTIFACT),
            primary_artifact_path=PRIMARY_ARTIFACT,
            auxiliary_artifact=_json(AUXILIARY_ARTIFACT),
            auxiliary_artifact_path=AUXILIARY_ARTIFACT,
        )

        self.assertEqual(rebuilt, _json(ADMISSION_AUDIT))
        body = dict(rebuilt)
        claimed = body.pop("content_digest")
        self.assertEqual(
            claimed,
            "arc3_p10_c12_closed_negative_admission:"
            + digest_object(body),
        )
        retained = rebuilt["retained_measurements"]
        self.assertEqual(retained["combined_probe_count"], 388)
        self.assertEqual(retained["combined_changed_probe_count"], 226)
        self.assertEqual(retained["combined_progress_count"], 0)
        self.assertEqual(
            retained["promotion_eligible_variable_count"],
            0,
        )
        self.assertEqual(
            retained["quarantined_stale_primary_score_fields"],
            {
                "layout_commit_score_advance_probe_count": 36,
                "layout_commit_score_regression_probe_count": 164,
                "public_total_levels": 76,
                "public_total_win_levels": 183,
            },
        )
        scope = rebuilt["admission_scope"]
        self.assertTrue(
            scope["admitted_for_negative_surface_closure"]
        )
        self.assertFalse(scope["admitted_for_runtime_compile"])
        self.assertTrue(
            scope["auxiliary_public_replay_bootstrap_quarantined"]
        )
        judgment = rebuilt["hds_judgment"]
        self.assertEqual(judgment["causal_result"], "CLOSED_NEGATIVE")
        self.assertFalse(judgment["same_surface_retry_authorized"])
        self.assertEqual(
            judgment["next_work_block_id"],
            "WB-C1_rendered_affordance_objectizer",
        )

    def test_each_source_byte_drift_is_rejected(self) -> None:
        cases = (
            (PRIMARY_ARTIFACT, AUXILIARY_ARTIFACT),
            (AUXILIARY_ARTIFACT, PRIMARY_ARTIFACT),
        )
        for drift_source, stable_source in cases:
            with self.subTest(source=drift_source.name):
                with tempfile.TemporaryDirectory() as temporary:
                    drifted = Path(temporary) / drift_source.name
                    drifted.write_bytes(drift_source.read_bytes() + b"\n")
                    primary_path = (
                        drifted
                        if drift_source == PRIMARY_ARTIFACT
                        else stable_source
                    )
                    auxiliary_path = (
                        drifted
                        if drift_source == AUXILIARY_ARTIFACT
                        else stable_source
                    )
                    with self.assertRaisesRegex(
                        ValueError,
                        "FROZEN_SOURCE_INVALID",
                    ):
                        build_p10_c12_closed_negative_audit(
                            provenance_manifest=_json(
                                PROVENANCE_MANIFEST
                            ),
                            primary_artifact=_json(PRIMARY_ARTIFACT),
                            primary_artifact_path=primary_path,
                            auxiliary_artifact=_json(
                                AUXILIARY_ARTIFACT
                            ),
                            auxiliary_artifact_path=auxiliary_path,
                        )

    def test_primary_positive_claim_drift_is_rejected(self) -> None:
        artifact = _json(PRIMARY_ARTIFACT)
        summary = artifact["summary"]
        assert isinstance(summary, dict)
        summary["total_progress_count"] = 1
        provenance = _json(PROVENANCE_MANIFEST)
        with tempfile.TemporaryDirectory() as temporary:
            altered_path = Path(temporary) / PRIMARY_ARTIFACT.name
            altered_path.write_text(
                json.dumps(artifact, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            _update_descriptor(
                provenance,
                source_path=(
                    "analysis/"
                    "c12_layout_mode_commit_discriminator_"
                    "capability_latest.json"
                ),
                artifact_path=altered_path,
            )

            with self.assertRaisesRegex(
                ValueError,
                "NEGATIVE_EVIDENCE_INVALID",
            ):
                build_p10_c12_closed_negative_audit(
                    provenance_manifest=provenance,
                    primary_artifact=artifact,
                    primary_artifact_path=altered_path,
                    auxiliary_artifact=_json(AUXILIARY_ARTIFACT),
                    auxiliary_artifact_path=AUXILIARY_ARTIFACT,
                )

    def test_auxiliary_positive_variable_drift_is_rejected(
        self,
    ) -> None:
        artifact = _json(AUXILIARY_ARTIFACT)
        summary = artifact["summary"]
        assert isinstance(summary, dict)
        summary["positive_pre_action_variable_count"] = 1
        summary["positive_pre_action_variables"] = ["drift"]
        provenance = _json(PROVENANCE_MANIFEST)
        with tempfile.TemporaryDirectory() as temporary:
            altered_path = Path(temporary) / AUXILIARY_ARTIFACT.name
            altered_path.write_text(
                json.dumps(artifact, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            _update_descriptor(
                provenance,
                source_path=(
                    "analysis/"
                    "layout_mode_discriminator_harness_analysis.json"
                ),
                artifact_path=altered_path,
            )

            with self.assertRaisesRegex(
                ValueError,
                "NEGATIVE_EVIDENCE_INVALID",
            ):
                build_p10_c12_closed_negative_audit(
                    provenance_manifest=provenance,
                    primary_artifact=_json(PRIMARY_ARTIFACT),
                    primary_artifact_path=PRIMARY_ARTIFACT,
                    auxiliary_artifact=artifact,
                    auxiliary_artifact_path=altered_path,
                )


if __name__ == "__main__":
    unittest.main()
