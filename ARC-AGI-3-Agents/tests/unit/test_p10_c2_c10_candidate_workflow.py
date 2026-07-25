from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any

from arc3_agi_agent.p10_c2_c10_candidate_workflow import (
    P10C2C10Probe,
    execute_p10_c2_c10_candidate_workflow,
)
from arc3_agi_agent.p10_instruction_compiler import (
    P10_C2_C10_SYMBOLIC_FILENAME,
)
from arc3_agi_agent.schema import digest_object

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
SOURCE_BUNDLE_DIR = PACKAGE_ROOT / "arc3_agi_agent" / "bundles"


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _bundle_fixture(output: Path) -> None:
    active = json.loads(
        (SOURCE_BUNDLE_DIR / "p10_manifest.json").read_text(
            encoding="utf-8"
        )
    )
    for entry in active["bundles"].values():
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


def _composition_audit() -> dict[str, object]:
    body: dict[str, object] = {
        "schema_version": (
            "arc3-p10-c2-c10-composition-removal-audit-v1"
        ),
        "artifact_type": "arc3_p10_c2_c10_composition_removal_audit",
        "phase": "P10_COMPLETE_ARC3_SAMPLE_SOLVING",
        "development_only": True,
        "runtime_use": "FORBIDDEN",
        "candidate_tier": "COMPOSABLE",
        "source_evidence": {
            "c2_c3_content_digest": "c2-c3:source",
            "c10_content_digest": "c10:source",
        },
        "candidate_contract": {
            "history_depth": 1,
            "visible_only": True,
        },
        "removal_evaluation": {
            "remove_c2_delta_milli": 77,
            "remove_c10_delta_milli": 367,
            "held_out_positive_count": 2,
        },
        "integrity_checks": {
            "source_digest": True,
            "identity_free": True,
        },
        "composable_checks": {
            "remove_c2": True,
            "remove_c10": True,
            "held_out": True,
        },
        "hds_judgment": {
            "composable_status": "PASS",
            "runtime_p_candidate_compile_authorized": True,
            "runtime_p_active_compile_authorized": False,
            "runtime_p_promotion_authorized": False,
        },
    }
    return {
        **body,
        "content_digest": "arc3_p10_c2_c10_composition_audit:"
        + digest_object(body),
    }


def _probes() -> tuple[P10C2C10Probe, ...]:
    return (
        P10C2C10Probe("stable-alpha", "stable", 8),
        P10C2C10Probe("discovery-alpha", "discovery", 8),
        P10C2C10Probe("held-alpha", "held-out", 8),
        P10C2C10Probe("held-beta", "held-out", 8),
    )


def _runner(*, improve: bool) -> Any:
    def run(**kwargs: Any) -> dict[str, Any]:
        selector = str(kwargs["requested_games"][0])
        lifecycle = str(kwargs["instruction_lifecycle"])
        candidate = lifecycle == "candidate"
        if candidate:
            assert kwargs["p_update_authority"] is not None
            assert kwargs["p_update_decision"] is not None
            assert kwargs["candidate_bundle"] is not None
        else:
            assert kwargs["p_update_authority"] is None
            assert kwargs["p_update_decision"] is None
            assert kwargs["candidate_bundle"] is None
        stable = selector.startswith("stable")
        completed = 2 if stable else (1 if candidate and improve else 0)
        total = 2 if stable else 3
        all_complete = completed == total
        body_version = (
            "p10-p-a-symbolic-c2-c10-v1"
            if candidate
            else "p10-p-a-symbolic-v27"
        )
        body_digest = (
            "candidate-body-digest"
            if candidate
            else "active-body-digest"
        )
        report = {
            "game_id": selector,
            "actions": 4,
            "recoveries": 0,
            "search_resets": 0,
            "final_status": "WIN" if all_complete else "MAX_ACTIONS",
            "max_action_exhausted": not all_complete,
            "instruction_body_versions": [body_version] * 4,
            "instruction_body_digests": [body_digest] * 4,
            "instruction_query_digests": ["query"] * 4,
            "emitted_steps": [[{"action_id": 1}]] * 4,
            "trace_digests": ["trace"] * 4,
            "development_transition_probe": {"transition_count": 1},
        }
        return {
            "operation_mode": "offline",
            "instruction_variant": "P-A",
            "instruction_lifecycle": lifecycle,
            "completed_levels": completed,
            "total_levels": total,
            "complete_game_count": int(all_complete),
            "all_complete": all_complete,
            "error_count": 0,
            "reports": [report],
            "errors": [],
        }

    return run


class P10C2C10CandidateWorkflowTests(unittest.TestCase):
    def test_positive_probe_holds_candidate_without_active_change(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle_dir = root / "bundles"
            environments_dir = root / "environments"
            bundle_dir.mkdir()
            environments_dir.mkdir()
            _bundle_fixture(bundle_dir)
            composition_path = root / "composition.json"
            output_path = root / "evidence" / "intervention.json"
            _write_json(composition_path, _composition_audit())
            active_before = (bundle_dir / "p10_manifest.json").read_bytes()

            result = execute_p10_c2_c10_candidate_workflow(
                environments_dir=environments_dir,
                bundle_dir=bundle_dir,
                composition_audit_path=composition_path,
                output_path=output_path,
                probes=_probes(),
                runner=_runner(improve=True),
            )

            judgment = result["hds_judgment"]
            assert isinstance(judgment, dict)
            self.assertEqual(judgment["status"], "HOLD")
            self.assertTrue(
                judgment["bounded_all_sample_regression_authorized"]
            )
            self.assertFalse(judgment["runtime_p_promotion_authorized"])
            self.assertTrue(judgment["candidate_slot_retained"])
            self.assertEqual(
                (bundle_dir / "p10_manifest.json").read_bytes(),
                active_before,
            )
            candidate_manifest = json.loads(
                (bundle_dir / "p10_candidate_manifest.json").read_text(
                    encoding="utf-8"
                )
            )
            self.assertEqual(candidate_manifest["lifecycle"], "CANDIDATE")
            self.assertEqual(
                candidate_manifest["candidate_target_component"],
                "P-A",
            )
            self.assertTrue(
                (bundle_dir / P10_C2_C10_SYMBOLIC_FILENAME).is_file()
            )
            self.assertTrue(output_path.is_file())
            body = dict(result)
            claimed = body.pop("content_digest")
            self.assertEqual(
                claimed,
                "arc3_p10_c2_c10_candidate_intervention:"
                + digest_object(body),
            )

    def test_no_target_improvement_rejects_and_restores_candidate_slot(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle_dir = root / "bundles"
            environments_dir = root / "environments"
            bundle_dir.mkdir()
            environments_dir.mkdir()
            _bundle_fixture(bundle_dir)
            composition_path = root / "composition.json"
            output_path = root / "evidence" / "intervention.json"
            _write_json(composition_path, _composition_audit())
            prior_candidate = (
                bundle_dir / "p10_candidate_manifest.json"
            ).read_bytes()

            result = execute_p10_c2_c10_candidate_workflow(
                environments_dir=environments_dir,
                bundle_dir=bundle_dir,
                composition_audit_path=composition_path,
                output_path=output_path,
                probes=_probes(),
                runner=_runner(improve=False),
            )

            judgment = result["hds_judgment"]
            assert isinstance(judgment, dict)
            self.assertEqual(judgment["status"], "REJECT")
            self.assertFalse(
                judgment["bounded_all_sample_regression_authorized"]
            )
            self.assertFalse(judgment["candidate_slot_retained"])
            self.assertEqual(
                (bundle_dir / "p10_candidate_manifest.json").read_bytes(),
                prior_candidate,
            )
            self.assertFalse(
                (bundle_dir / P10_C2_C10_SYMBOLIC_FILENAME).exists()
            )
            archive = output_path.parent / "c2_c10_candidate_archive"
            self.assertTrue(
                (archive / P10_C2_C10_SYMBOLIC_FILENAME).is_file()
            )
            evaluation = result["evaluation"]
            assert isinstance(evaluation, dict)
            self.assertFalse(evaluation["target_improved"])

    def test_tampered_composition_fails_before_candidate_compile(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle_dir = root / "bundles"
            environments_dir = root / "environments"
            bundle_dir.mkdir()
            environments_dir.mkdir()
            _bundle_fixture(bundle_dir)
            composition = _composition_audit()
            composition["content_digest"] = "tampered"
            composition_path = root / "composition.json"
            _write_json(composition_path, composition)
            prior_candidate = (
                bundle_dir / "p10_candidate_manifest.json"
            ).read_bytes()

            with self.assertRaisesRegex(
                ValueError,
                "COMPOSITION_DIGEST_INVALID",
            ):
                execute_p10_c2_c10_candidate_workflow(
                    environments_dir=environments_dir,
                    bundle_dir=bundle_dir,
                    composition_audit_path=composition_path,
                    output_path=root / "evidence.json",
                    probes=_probes(),
                    runner=_runner(improve=True),
                )

            self.assertEqual(
                (bundle_dir / "p10_candidate_manifest.json").read_bytes(),
                prior_candidate,
            )
            self.assertFalse(
                (bundle_dir / P10_C2_C10_SYMBOLIC_FILENAME).exists()
            )


if __name__ == "__main__":
    unittest.main()
