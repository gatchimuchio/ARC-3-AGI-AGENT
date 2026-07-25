from __future__ import annotations

import json
import shutil
import tempfile
import unittest
from pathlib import Path
from typing import Any

from arc3_agi_agent.p10_directional_settle_candidate_workflow import (
    P10DirectionalSettleProbe,
    execute_p10_directional_settle_candidate_workflow,
)
from arc3_agi_agent.p10_directional_settle_composition_audit import (
    build_p10_directional_settle_composition_audit,
)
from arc3_agi_agent.p10_instruction_compiler import (
    P10_DIRECTIONAL_SETTLE_HYBRID_FILENAME,
    P10_DIRECTIONAL_SETTLE_HYBRID_VERSION,
)
from arc3_agi_agent.schema import digest_object

PACKAGE_ROOT = Path(__file__).resolve().parents[2]
REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
SOURCE_BUNDLE_DIR = PACKAGE_ROOT / "arc3_agi_agent" / "bundles"
ACTIVE_COMPACT = (
    REPOSITORY_ROOT
    / "evidence"
    / "p10"
    / "development"
    / "stable_regression_v14"
    / "ka59_max200.compact.json"
)


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected object: {path}")
    return value


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(value, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _bundle_fixture(output: Path) -> None:
    active = _json(SOURCE_BUNDLE_DIR / "p10_manifest.json")
    bundles = active["bundles"]
    assert isinstance(bundles, dict)
    for entry in bundles.values():
        assert isinstance(entry, dict)
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
    return build_p10_directional_settle_composition_audit(
        _json(ACTIVE_COMPACT)
    )


def _probes() -> tuple[P10DirectionalSettleProbe, ...]:
    return (
        P10DirectionalSettleProbe("stable-alpha", "stable", 16),
        P10DirectionalSettleProbe("target-alpha", "target", 32),
    )


def _runner(*, improve: bool, fail_candidate: bool = False) -> Any:
    def run(**kwargs: Any) -> dict[str, Any]:
        selector = str(kwargs["requested_games"][0])
        lifecycle = str(kwargs["instruction_lifecycle"])
        candidate = lifecycle == "candidate"
        if candidate:
            assert kwargs["p_update_authority"] is not None
            assert kwargs["p_update_decision"] is not None
            assert kwargs["candidate_bundle"] is not None
            if fail_candidate:
                raise RuntimeError("synthetic candidate failure")
        else:
            assert kwargs["p_update_authority"] is None
            assert kwargs["p_update_decision"] is None
            assert kwargs["candidate_bundle"] is None
        stable = selector.startswith("stable")
        completed = (
            2
            if stable
            else (7 if candidate and improve else 6)
        )
        total = 2 if stable else 7
        all_complete = completed == total
        body_version = (
            P10_DIRECTIONAL_SETTLE_HYBRID_VERSION
            if candidate
            else "p10-hybrid-v27"
        )
        body_digest = (
            "candidate-body-digest"
            if candidate
            else "active-body-digest"
        )
        report = {
            "game_id": selector,
            "actions": 8,
            "recoveries": 0,
            "search_resets": 0,
            "final_status": "WIN" if all_complete else "MAX_ACTIONS",
            "max_action_exhausted": not all_complete,
            "instruction_body_versions": [body_version] * 8,
            "instruction_body_digests": [body_digest] * 8,
            "instruction_query_digests": ["query"] * 8,
            "emitted_steps": [[{"action_id": 1}]] * 8,
            "emitted_provenance": [["operator:synthetic"]] * 8,
            "trace_digests": ["trace"] * 8,
        }
        return {
            "operation_mode": "offline",
            "instruction_variant": "hybrid",
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


class P10DirectionalSettleCandidateWorkflowTests(unittest.TestCase):
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

            result = execute_p10_directional_settle_candidate_workflow(
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
            candidate_manifest = _json(
                bundle_dir / "p10_candidate_manifest.json"
            )
            self.assertEqual(candidate_manifest["lifecycle"], "CANDIDATE")
            self.assertEqual(
                candidate_manifest["candidate_target_component"],
                "hybrid-P-B",
            )
            self.assertEqual(
                candidate_manifest[
                    "maximum_transition_observations"
                ],
                8,
            )
            self.assertTrue(
                (
                    bundle_dir
                    / P10_DIRECTIONAL_SETTLE_HYBRID_FILENAME
                ).is_file()
            )
            body = dict(result)
            claimed = body.pop("content_digest")
            self.assertEqual(
                claimed,
                "arc3_p10_directional_settle_candidate_intervention:"
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

            result = execute_p10_directional_settle_candidate_workflow(
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
                (
                    bundle_dir
                    / P10_DIRECTIONAL_SETTLE_HYBRID_FILENAME
                ).exists()
            )
            archive = (
                output_path.parent
                / "directional_settle_candidate_archive"
            )
            self.assertTrue(
                (
                    archive
                    / P10_DIRECTIONAL_SETTLE_HYBRID_FILENAME
                ).is_file()
            )
            evaluation = result["evaluation"]
            assert isinstance(evaluation, dict)
            self.assertFalse(evaluation["target_improved"])
            self.assertFalse(evaluation["bounded_positive"])
            judgment = result["hds_judgment"]
            assert isinstance(judgment, dict)
            reason_codes = judgment["reason_codes"]
            self.assertIn(
                "failed-evaluation-check-target-improved",
                reason_codes,
            )
            self.assertIn(
                "failed-evaluation-check-bounded-positive",
                reason_codes,
            )
            self.assertNotIn("target_improved", reason_codes)
            self.assertNotIn("bounded_positive", reason_codes)

    def test_runner_failure_restores_candidate_slot(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle_dir = root / "bundles"
            environments_dir = root / "environments"
            bundle_dir.mkdir()
            environments_dir.mkdir()
            _bundle_fixture(bundle_dir)
            composition_path = root / "composition.json"
            _write_json(composition_path, _composition_audit())
            prior_candidate = (
                bundle_dir / "p10_candidate_manifest.json"
            ).read_bytes()

            with self.assertRaisesRegex(
                RuntimeError,
                "synthetic candidate failure",
            ):
                execute_p10_directional_settle_candidate_workflow(
                    environments_dir=environments_dir,
                    bundle_dir=bundle_dir,
                    composition_audit_path=composition_path,
                    output_path=root / "evidence.json",
                    probes=_probes(),
                    runner=_runner(
                        improve=True,
                        fail_candidate=True,
                    ),
                )

            self.assertEqual(
                (bundle_dir / "p10_candidate_manifest.json").read_bytes(),
                prior_candidate,
            )
            self.assertFalse(
                (
                    bundle_dir
                    / P10_DIRECTIONAL_SETTLE_HYBRID_FILENAME
                ).exists()
            )

    def test_checkpoints_are_reused_without_collapsing_repetitions(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle_dir = root / "bundles"
            environments_dir = root / "environments"
            checkpoint_dir = root / "checkpoints"
            bundle_dir.mkdir()
            environments_dir.mkdir()
            _bundle_fixture(bundle_dir)
            composition_path = root / "composition.json"
            _write_json(composition_path, _composition_audit())

            first = execute_p10_directional_settle_candidate_workflow(
                environments_dir=environments_dir,
                bundle_dir=bundle_dir,
                composition_audit_path=composition_path,
                output_path=root / "first.json",
                probes=_probes(),
                checkpoint_dir=checkpoint_dir,
                runner=_runner(improve=True),
            )
            first_checkpoints = first["run_checkpoints"]
            assert isinstance(first_checkpoints, dict)
            self.assertEqual(first_checkpoints["cache_hits"], 0)
            self.assertEqual(first_checkpoints["cache_misses"], 8)

            def must_not_run(**kwargs: Any) -> dict[str, Any]:
                raise AssertionError(f"unexpected run: {kwargs}")

            second = execute_p10_directional_settle_candidate_workflow(
                environments_dir=environments_dir,
                bundle_dir=bundle_dir,
                composition_audit_path=composition_path,
                output_path=root / "second.json",
                probes=_probes(),
                checkpoint_dir=checkpoint_dir,
                runner=must_not_run,
            )
            second_checkpoints = second["run_checkpoints"]
            assert isinstance(second_checkpoints, dict)
            self.assertEqual(second_checkpoints["cache_hits"], 8)
            self.assertEqual(second_checkpoints["cache_misses"], 0)
            runs = second["runs"]
            assert isinstance(runs, dict)
            self.assertEqual(
                runs["active_first"],
                runs["active_second"],
            )
            self.assertEqual(
                runs["candidate_first"],
                runs["candidate_second"],
            )

    def test_interrupted_checkpoint_transaction_recovers_original_slot(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            bundle_dir = root / "bundles"
            environments_dir = root / "environments"
            checkpoint_dir = root / "checkpoints"
            bundle_dir.mkdir()
            environments_dir.mkdir()
            _bundle_fixture(bundle_dir)
            composition_path = root / "composition.json"
            _write_json(composition_path, _composition_audit())
            prior_candidate = (
                bundle_dir / "p10_candidate_manifest.json"
            ).read_bytes()
            base_runner = _runner(improve=False)
            call_count = 0

            def interrupt_second(**kwargs: Any) -> dict[str, Any]:
                nonlocal call_count
                call_count += 1
                if call_count == 2:
                    raise KeyboardInterrupt
                return base_runner(**kwargs)

            with self.assertRaises(KeyboardInterrupt):
                execute_p10_directional_settle_candidate_workflow(
                    environments_dir=environments_dir,
                    bundle_dir=bundle_dir,
                    composition_audit_path=composition_path,
                    output_path=root / "interrupted.json",
                    probes=_probes(),
                    checkpoint_dir=checkpoint_dir,
                    runner=interrupt_second,
                )

            self.assertNotEqual(
                (bundle_dir / "p10_candidate_manifest.json").read_bytes(),
                prior_candidate,
            )
            self.assertTrue(
                (
                    checkpoint_dir
                    / (
                        "directional_settle_candidate_slot_"
                        "transaction.json"
                    )
                ).is_file()
            )

            resumed = execute_p10_directional_settle_candidate_workflow(
                environments_dir=environments_dir,
                bundle_dir=bundle_dir,
                composition_audit_path=composition_path,
                output_path=root / "resumed.json",
                probes=_probes(),
                checkpoint_dir=checkpoint_dir,
                runner=base_runner,
            )

            judgment = resumed["hds_judgment"]
            assert isinstance(judgment, dict)
            self.assertEqual(judgment["status"], "REJECT")
            self.assertEqual(
                (bundle_dir / "p10_candidate_manifest.json").read_bytes(),
                prior_candidate,
            )
            self.assertFalse(
                (
                    bundle_dir
                    / P10_DIRECTIONAL_SETTLE_HYBRID_FILENAME
                ).exists()
            )
            self.assertFalse(
                (
                    checkpoint_dir
                    / (
                        "directional_settle_candidate_slot_"
                        "transaction.json"
                    )
                ).exists()
            )
            checkpoint_summary = resumed["run_checkpoints"]
            assert isinstance(checkpoint_summary, dict)
            self.assertEqual(checkpoint_summary["cache_hits"], 1)
            self.assertEqual(checkpoint_summary["cache_misses"], 7)

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
                "AUDIT_DIGEST_INVALID",
            ):
                execute_p10_directional_settle_candidate_workflow(
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
                (
                    bundle_dir
                    / P10_DIRECTIONAL_SETTLE_HYBRID_FILENAME
                ).exists()
            )


if __name__ == "__main__":
    unittest.main()
