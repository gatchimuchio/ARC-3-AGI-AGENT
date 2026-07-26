from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any

from arc3_agi_agent.directional_force_multi_actor import (
    COMPOSITION_EVIDENCE,
)
from arc3_agi_agent.p10_instruction_compiler import (
    P10_PROSPECTIVE_COMPOSITION_HYBRID_FILENAME,
    P10_PROSPECTIVE_COMPOSITION_HYBRID_VERSION,
)
from arc3_agi_agent.p10_prospective_composition_candidate_workflow import (
    execute_p10_prospective_composition_candidate_workflow,
)

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SOURCE_BUNDLE_DIR = PACKAGE_ROOT / "arc3_agi_agent" / "bundles"
COMPOSITION_AUDIT = (
    REPOSITORY_ROOT
    / "evidence"
    / "p10"
    / "development"
    / "prospective_obligation_relation_v1"
    / "PROSPECTIVE_OBLIGATION_COMPOSITION_AUDIT.json"
)


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def _bundle_fixture(output: Path) -> None:
    active = _json(SOURCE_BUNDLE_DIR / "p10_manifest.json")
    bundles = active["bundles"]
    if not isinstance(bundles, dict):
        raise TypeError("active bundles invalid")
    for entry in bundles.values():
        if not isinstance(entry, dict):
            raise TypeError("active bundle entry invalid")
        filename = str(entry["filename"])
        shutil.copyfile(
            SOURCE_BUNDLE_DIR / filename,
            output / filename,
        )
    shutil.copyfile(
        SOURCE_BUNDLE_DIR / "p10_manifest.json",
        output / "p10_manifest.json",
    )
    shutil.copyfile(
        SOURCE_BUNDLE_DIR / "p10_candidate_manifest.json",
        output / "p10_candidate_manifest.json",
    )


def _runner(
    *,
    improve: bool,
    fail: bool = False,
) -> Any:
    def run(**kwargs: Any) -> dict[str, Any]:
        if fail:
            raise RuntimeError("synthetic candidate failure")
        if kwargs["instruction_lifecycle"] != "candidate":
            raise AssertionError("candidate lifecycle required")
        if kwargs["p_update_authority"] is None:
            raise AssertionError("candidate authority required")
        if kwargs["p_update_decision"] is None:
            raise AssertionError("candidate decision required")
        if kwargs["candidate_bundle"] is None:
            raise AssertionError("candidate descriptor required")
        completed = 7 if improve else 6
        all_complete = completed == 7
        provenance = (
            [[COMPOSITION_EVIDENCE, "synthetic"]]
            if improve
            else [["synthetic"]]
        )
        report = {
            "game_id": str(kwargs["requested_games"][0]),
            "actions": 326 if improve else 450,
            "recoveries": 0,
            "search_resets": 0,
            "final_status": "STOP" if improve else "MAX_ACTION_STOP",
            "max_action_exhausted": not improve,
            "instruction_body_versions": [
                P10_PROSPECTIVE_COMPOSITION_HYBRID_VERSION
            ],
            "instruction_body_digests": ["candidate-body"],
            "instruction_query_digests": ["query"],
            "emitted_steps": [[{"action_id": 1}]],
            "emitted_provenance": provenance,
            "trace_digests": ["trace"],
            "development_prospective_relation_probe": {
                "format": "synthetic"
            },
        }
        return {
            "phase": "P10",
            "operation_mode": "offline",
            "environment_count": 1,
            "completed_count": 1,
            "complete_game_count": int(all_complete),
            "completed_levels": completed,
            "total_levels": 7,
            "all_complete": all_complete,
            "error_count": 0,
            "max_actions": 450,
            "instruction_variant": "hybrid",
            "instruction_lifecycle": "candidate",
            "reports": [report],
            "errors": [],
        }

    return run


class ProspectiveCompositionCandidateWorkflowTests(
    unittest.TestCase
):
    def test_positive_target_retains_candidate_without_active_change(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle_dir = root / "bundles"
            environments_dir = root / "environments"
            bundle_dir.mkdir()
            environments_dir.mkdir()
            _bundle_fixture(bundle_dir)
            active_before = (
                bundle_dir / "p10_manifest.json"
            ).read_bytes()
            output = root / "evidence" / "target.json"

            result = (
                execute_p10_prospective_composition_candidate_workflow(
                    environments_dir=environments_dir,
                    bundle_dir=bundle_dir,
                    composition_audit_path=COMPOSITION_AUDIT,
                    output_path=output,
                    environment_selector="development-target",
                    runner=_runner(improve=True),
                )
            )

            self.assertTrue(result["evaluation"]["bounded_positive"])
            self.assertEqual(
                result["hds_judgment"]["status"],
                "HOLD",
            )
            self.assertTrue(
                result["hds_judgment"][
                    "all_sample_regression_authorized"
                ]
            )
            self.assertFalse(
                result["hds_judgment"][
                    "runtime_p_promotion_authorized"
                ]
            )
            self.assertEqual(
                (bundle_dir / "p10_manifest.json").read_bytes(),
                active_before,
            )
            self.assertTrue(
                (
                    bundle_dir
                    / P10_PROSPECTIVE_COMPOSITION_HYBRID_FILENAME
                ).is_file()
            )

    def test_flat_target_rejects_and_restores_candidate_slot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle_dir = root / "bundles"
            environments_dir = root / "environments"
            bundle_dir.mkdir()
            environments_dir.mkdir()
            _bundle_fixture(bundle_dir)
            candidate_before = (
                bundle_dir / "p10_candidate_manifest.json"
            ).read_bytes()

            result = (
                execute_p10_prospective_composition_candidate_workflow(
                    environments_dir=environments_dir,
                    bundle_dir=bundle_dir,
                    composition_audit_path=COMPOSITION_AUDIT,
                    output_path=root / "evidence" / "target.json",
                    environment_selector="development-target",
                    runner=_runner(improve=False),
                )
            )

            self.assertFalse(result["evaluation"]["bounded_positive"])
            self.assertEqual(
                result["hds_judgment"]["status"],
                "REJECT",
            )
            self.assertEqual(
                (
                    bundle_dir / "p10_candidate_manifest.json"
                ).read_bytes(),
                candidate_before,
            )
            self.assertFalse(
                (
                    bundle_dir
                    / P10_PROSPECTIVE_COMPOSITION_HYBRID_FILENAME
                ).exists()
            )

    def test_runner_failure_restores_candidate_slot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle_dir = root / "bundles"
            environments_dir = root / "environments"
            bundle_dir.mkdir()
            environments_dir.mkdir()
            _bundle_fixture(bundle_dir)
            candidate_before = (
                bundle_dir / "p10_candidate_manifest.json"
            ).read_bytes()

            with self.assertRaisesRegex(
                RuntimeError,
                "synthetic candidate failure",
            ):
                execute_p10_prospective_composition_candidate_workflow(
                    environments_dir=environments_dir,
                    bundle_dir=bundle_dir,
                    composition_audit_path=COMPOSITION_AUDIT,
                    output_path=root / "evidence" / "target.json",
                    environment_selector="development-target",
                    runner=_runner(improve=True, fail=True),
                )

            self.assertEqual(
                (
                    bundle_dir / "p10_candidate_manifest.json"
                ).read_bytes(),
                candidate_before,
            )
            self.assertFalse(
                (
                    bundle_dir
                    / P10_PROSPECTIVE_COMPOSITION_HYBRID_FILENAME
                ).exists()
            )


if __name__ == "__main__":
    unittest.main()
