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
from arc3_agi_agent.p10_prospective_candidate_batch import (
    build_prospective_candidate_batch_conditions,
    load_prospective_candidate_context,
    run_prospective_candidate_checkpoint_worker,
)
from arc3_agi_agent.schema import digest_object

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SOURCE_BUNDLE_DIR = PACKAGE_ROOT / "arc3_agi_agent" / "bundles"
ENVIRONMENTS_DIR = REPOSITORY_ROOT / "environment_files"
EVIDENCE_DIR = (
    REPOSITORY_ROOT
    / "evidence"
    / "p10"
    / "development"
    / "prospective_obligation_relation_v1"
)
TARGET_WORKFLOW = (
    EVIDENCE_DIR / "PROSPECTIVE_COMPOSITION_TARGET_INTERVENTION.json"
)


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def _active_manifest_for_workflow() -> dict[str, Any]:
    workflow = _json(TARGET_WORKFLOW)
    expected = str(workflow["active_manifest_digest"])
    active = _json(SOURCE_BUNDLE_DIR / "p10_manifest.json")
    if digest_object(active) == expected:
        return active
    previous = _json(
        SOURCE_BUNDLE_DIR / "p10_previous_stable_manifest.json"
    )
    previous_manifest = previous.get("manifest")
    if (
        isinstance(previous_manifest, dict)
        and digest_object(previous_manifest) == expected
    ):
        return previous_manifest
    raise ValueError("target workflow active manifest fixture missing")


def _bundle_fixture(output: Path) -> None:
    active = _active_manifest_for_workflow()
    candidate = _json(
        EVIDENCE_DIR
        / "candidate_archive"
        / "p10_candidate_manifest_prospective_composition_v1.json"
    )
    for manifest in (active, candidate):
        bundles = manifest.get("bundles")
        if not isinstance(bundles, dict):
            raise TypeError("bundle fixture manifest invalid")
        for entry in bundles.values():
            if not isinstance(entry, dict):
                raise TypeError("bundle fixture entry invalid")
            filename = str(entry["filename"])
            source = SOURCE_BUNDLE_DIR / filename
            if not source.is_file():
                source = EVIDENCE_DIR / "candidate_archive" / filename
            shutil.copyfile(source, output / filename)
    (output / "p10_manifest.json").write_text(
        json.dumps(active, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    (output / "p10_candidate_manifest.json").write_text(
        json.dumps(candidate, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _runner(**kwargs: Any) -> dict[str, Any]:
    game_id = str(kwargs["requested_games"][0])
    report = {
        "game_id": game_id,
        "actions": 12,
        "levels_completed": 1,
        "win_levels": 2,
        "complete": False,
    }
    return {
        "phase": "P10",
        "operation_mode": "offline",
        "environment_count": 1,
        "completed_count": 1,
        "complete_game_count": 0,
        "completed_levels": 1,
        "total_levels": 2,
        "all_complete": False,
        "error_count": 0,
        "max_actions": 450,
        "instruction_variant": "hybrid",
        "instruction_lifecycle": "candidate",
        "reports": [report],
        "errors": [],
        "local_scorecard": {
            "environments": [
                {
                    "id": game_id,
                    "actions": 12,
                    "completed": False,
                    "level_count": 2,
                    "levels_completed": 1,
                    "runs": [],
                    "score": 0.0,
                }
            ]
        },
    }


class ProspectiveCandidateBatchTests(unittest.TestCase):
    def test_conditions_bind_active_candidate_and_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            bundle_dir = Path(temporary)
            _bundle_fixture(bundle_dir)
            workflow, _proposal, candidate = (
                load_prospective_candidate_context(
                    bundle_dir=bundle_dir,
                    target_workflow_path=TARGET_WORKFLOW,
                )
            )
            game_ids = sorted(
                path.parent.name + "-" + path.parent.parent.name
                for path in ENVIRONMENTS_DIR.glob("*/*/*.json")
                if path.name == "metadata.json"
            )
            if len(game_ids) != 25:
                game_ids = [
                    f"retained-sample-{index:02d}"
                    for index in range(25)
                ]

            first = build_prospective_candidate_batch_conditions(
                environments_dir=ENVIRONMENTS_DIR,
                game_ids=game_ids,
                bundle_dir=bundle_dir,
                workflow=workflow,
                candidate=candidate,
            )
            second = build_prospective_candidate_batch_conditions(
                environments_dir=ENVIRONMENTS_DIR,
                game_ids=game_ids,
                bundle_dir=bundle_dir,
                workflow=workflow,
                candidate=candidate,
            )

            self.assertEqual(first, second)
            self.assertEqual(
                first["active_manifest_digest"],
                active_p10_manifest_digest(bundle_dir),
            )
            self.assertEqual(
                first["candidate_descriptor_digest"],
                candidate.digest,
            )
            self.assertEqual(
                first["target_workflow_digest"],
                workflow["content_digest"],
            )

    def test_worker_checkpoint_is_content_bound_and_resumable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle_dir = root / "bundles"
            checkpoint_dir = root / "checkpoints"
            bundle_dir.mkdir()
            checkpoint_dir.mkdir()
            _bundle_fixture(bundle_dir)
            game_id = "ar25-0c556536"

            first = run_prospective_candidate_checkpoint_worker(
                environments_dir=ENVIRONMENTS_DIR,
                checkpoint_dir=checkpoint_dir,
                bundle_dir=bundle_dir,
                target_workflow_path=TARGET_WORKFLOW,
                game_id=game_id,
                runner=_runner,
            )
            second = run_prospective_candidate_checkpoint_worker(
                environments_dir=ENVIRONMENTS_DIR,
                checkpoint_dir=checkpoint_dir,
                bundle_dir=bundle_dir,
                target_workflow_path=TARGET_WORKFLOW,
                game_id=game_id,
                resume=True,
                runner=_runner,
            )

            self.assertEqual(first["status"], "EXECUTED")
            self.assertEqual(second["status"], "REUSED")
            self.assertEqual(
                first["conditions_digest"],
                second["conditions_digest"],
            )

    def test_tampered_target_workflow_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle_dir = root / "bundles"
            bundle_dir.mkdir()
            _bundle_fixture(bundle_dir)
            workflow = _json(TARGET_WORKFLOW)
            workflow["content_digest"] = "tampered"
            tampered = root / "target.json"
            tampered.write_text(
                json.dumps(workflow) + "\n",
                encoding="utf-8",
            )

            with self.assertRaisesRegex(
                ValueError,
                "WORKFLOW_DIGEST_INVALID",
            ):
                load_prospective_candidate_context(
                    bundle_dir=bundle_dir,
                    target_workflow_path=tampered,
                )


if __name__ == "__main__":
    unittest.main()
