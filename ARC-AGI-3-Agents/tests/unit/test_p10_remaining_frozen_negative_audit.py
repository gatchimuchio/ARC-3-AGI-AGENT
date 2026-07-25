from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from arc3_agi_agent.p10_remaining_frozen_negative_audit import (
    FROZEN_NEGATIVE_SPECS,
    build_all_remaining_frozen_negative_audits,
    build_frozen_negative_admission,
)
from arc3_agi_agent.schema import digest_object

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
EVIDENCE_DIR = (
    REPOSITORY_ROOT
    / "evidence"
    / "p10"
    / "development"
    / "remaining_frozen_negative_surfaces_v1"
)
PROVENANCE_MANIFEST = REPOSITORY_ROOT / "manifests" / (
    "provenance_manifest.json"
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


class P10RemainingFrozenNegativeAuditTests(unittest.TestCase):
    def test_rebuilds_all_admissions_and_strict_order_catalog(
        self,
    ) -> None:
        rebuilt = build_all_remaining_frozen_negative_audits(
            provenance_manifest=_json(PROVENANCE_MANIFEST),
            retained_dir=EVIDENCE_DIR,
        )

        self.assertEqual(
            set(rebuilt),
            {
                *(spec.audit_filename for spec in FROZEN_NEGATIVE_SPECS),
                "REMAINING_FROZEN_NEGATIVE_CATALOG.json",
            },
        )
        for filename, value in rebuilt.items():
            self.assertEqual(value, _json(EVIDENCE_DIR / filename))
            body = dict(value)
            claimed = body.pop("content_digest")
            prefix = (
                "arc3_p10_remaining_frozen_negative_catalog:"
                if filename == "REMAINING_FROZEN_NEGATIVE_CATALOG.json"
                else "arc3_p10_frozen_negative_admission:"
            )
            self.assertEqual(claimed, prefix + digest_object(body))

        catalog = rebuilt["REMAINING_FROZEN_NEGATIVE_CATALOG.json"]
        summary = catalog["summary"]
        self.assertEqual(summary["newly_closed_capability_count"], 7)
        self.assertEqual(summary["previously_closed_axis_count"], 1)
        self.assertEqual(summary["target_count"], 21)
        self.assertEqual(summary["probe_count"], 2199)
        self.assertEqual(summary["changed_probe_count"], 565)
        self.assertEqual(summary["progress_count"], 0)
        self.assertEqual(summary["game_over_count"], 5)
        steps = catalog["strict_queue_resolution"]
        self.assertEqual(
            [step["rank"] for step in steps],
            [6, 7, 8, 9, 10, 11, 12, 13],
        )
        self.assertEqual(
            steps[4]["resolution"],
            "PREVIOUSLY_CLOSED_NEGATIVE_AXIS",
        )
        judgment = catalog["hds_judgment"]
        self.assertTrue(judgment["all_frozen_surfaces_closed"])
        self.assertFalse(judgment["runtime_p_compile_authorized"])
        self.assertEqual(
            judgment["next_work_block_id"],
            "WB-PROSPECTIVE-OBLIGATION-RELATION-COMPILER",
        )

    def test_each_source_byte_drift_is_rejected(self) -> None:
        provenance = _json(PROVENANCE_MANIFEST)
        for spec in FROZEN_NEGATIVE_SPECS:
            with self.subTest(capability=spec.capability_id):
                source = EVIDENCE_DIR / spec.retained_filename
                with tempfile.TemporaryDirectory() as temporary:
                    drifted = Path(temporary) / source.name
                    drifted.write_bytes(source.read_bytes() + b"\n")
                    with self.assertRaisesRegex(
                        ValueError,
                        "SOURCE_INVALID",
                    ):
                        build_frozen_negative_admission(
                            spec=spec,
                            provenance_manifest=provenance,
                            legacy_artifact=_json(source),
                            legacy_artifact_path=drifted,
                        )

    def test_positive_progress_claim_drift_is_rejected(self) -> None:
        spec = FROZEN_NEGATIVE_SPECS[0]
        source = EVIDENCE_DIR / spec.retained_filename
        artifact = _json(source)
        artifact["summary"]["total_progress_count"] = 1
        provenance = _json(PROVENANCE_MANIFEST)
        with tempfile.TemporaryDirectory() as temporary:
            altered_path = Path(temporary) / source.name
            altered_path.write_text(
                json.dumps(artifact, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            _update_descriptor(
                provenance,
                source_path=spec.source_path,
                artifact_path=altered_path,
            )

            with self.assertRaisesRegex(
                ValueError,
                "EVIDENCE_INVALID",
            ):
                build_frozen_negative_admission(
                    spec=spec,
                    provenance_manifest=provenance,
                    legacy_artifact=artifact,
                    legacy_artifact_path=altered_path,
                )

    def test_c11_game_over_does_not_become_hazard_separator(
        self,
    ) -> None:
        spec = next(
            item
            for item in FROZEN_NEGATIVE_SPECS
            if item.capability_id
            == "C11_route_terminal_reachability_verifier"
        )
        source = EVIDENCE_DIR / spec.retained_filename
        artifact = _json(source)
        artifact["summary"]["hazard_separator_variable_count"] = 1
        provenance = _json(PROVENANCE_MANIFEST)
        with tempfile.TemporaryDirectory() as temporary:
            altered_path = Path(temporary) / source.name
            altered_path.write_text(
                json.dumps(artifact, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            _update_descriptor(
                provenance,
                source_path=spec.source_path,
                artifact_path=altered_path,
            )

            with self.assertRaisesRegex(
                ValueError,
                "EVIDENCE_INVALID",
            ):
                build_frozen_negative_admission(
                    spec=spec,
                    provenance_manifest=provenance,
                    legacy_artifact=artifact,
                    legacy_artifact_path=altered_path,
                )


if __name__ == "__main__":
    unittest.main()
