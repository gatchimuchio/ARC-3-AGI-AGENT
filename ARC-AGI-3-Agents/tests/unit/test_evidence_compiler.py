from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from arc3_agi_agent.evidence_compiler import CATEGORIES, compile_evidence


class EvidenceCompilerTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary_directory = tempfile.TemporaryDirectory(
            prefix="arc3-evidence-compiler-"
        )
        self.root = Path(self.temporary_directory.name)
        self.analysis = self.root / "analysis"
        self.environments = self.root / "environment_files"
        self.analysis.mkdir()
        metadata = self.environments / "xy99" / "deadbeef" / "metadata.json"
        metadata.parent.mkdir(parents=True)
        metadata.write_text(
            json.dumps(
                {
                    "game_id": "xy99-deadbeef",
                    "title": "XY99",
                    "baseline_actions": [1, 2, 3],
                    "local_dir": "/mnt/private/environment_files/xy99/deadbeef",
                    "tags": ["observation", "action", "visible"],
                }
            ),
            encoding="utf-8",
        )
        (self.analysis / "evidence.json").write_text(
            json.dumps(
                {
                    "game_id": "xy99-deadbeef",
                    "task_id": "secret-task",
                    "level_number": 4,
                    "source_state": {"hidden": "do-not-use"},
                    "replay_index": 12,
                    "observation": {
                        "frame": [[1, 1], [0, 2]],
                        "visible": True,
                        "objects": ["object", "relation"],
                    },
                    "transition": {
                        "before": "active",
                        "after": "progress",
                        "action": 1,
                        "effect": "visible state change",
                    },
                    "hazard": {
                        "risk": 0.5,
                        "failure": "unsafe",
                        "recovery": "rollback",
                    },
                    "contradiction": {
                        "counter_evidence": "negative falsifier",
                        "decision": "reject",
                    },
                    "hds_frame": {
                        "purpose": "evaluate evidence",
                        "candidate": "bounded probe",
                        "budget": 1,
                        "stop": "suspend",
                    },
                    "memory_lifecycle": {
                        "hypothesis": "active",
                        "version": 2,
                        "operation": "merge split revise archive",
                    },
                }
            ),
            encoding="utf-8",
        )
        (self.analysis / "identity_only.json").write_text(
            json.dumps(
                {
                    "game_id": "ab12-01234567",
                    "title": "AB12",
                    "level_number": 9,
                    "replay_actions": [1, 2],
                    "answer_map": {"ab12": [3]},
                }
            ),
            encoding="utf-8",
        )

    def tearDown(self) -> None:
        self.temporary_directory.cleanup()

    def compile(self, output_name: str = "output") -> tuple[Path, dict[str, object]]:
        output = self.root / output_name
        manifest = compile_evidence(
            analysis_dir=self.analysis,
            environment_dir=self.environments,
            output_dir=output,
            source_revision="fixture-revision",
        )
        return output, manifest

    @staticmethod
    def jsonl(path: Path) -> list[dict[str, object]]:
        return [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line
        ]

    def test_every_source_is_accounted_and_identity_only_source_is_visible(self) -> None:
        output, manifest = self.compile()
        provenance = json.loads(
            (output / "manifests" / "provenance_manifest.json").read_text(
                encoding="utf-8"
            )
        )

        self.assertEqual(manifest["source_file_count"], 3)
        self.assertEqual(manifest["source_accounted_count"], 3)
        self.assertEqual(manifest["source_parse_error_count"], 0)
        self.assertEqual(provenance["runtime_use"], "FORBIDDEN")
        identity_only = next(
            item
            for item in provenance["sources"]
            if item["path"] == "analysis/identity_only.json"
        )
        self.assertEqual(
            identity_only["extraction_status"],
            "ACCOUNTED_NO_RUNTIME_MATERIAL",
        )

    def test_runtime_records_are_identity_free_and_provenance_is_separated(self) -> None:
        output, manifest = self.compile()
        runtime_text = "\n".join(
            (output / category / "records.jsonl").read_text(encoding="utf-8")
            for category in CATEGORIES
        ).casefold()
        identity_audit = json.loads(
            (output / "manifests" / "identity_free_audit.json").read_text(
                encoding="utf-8"
            )
        )
        provenance_text = (
            output / "manifests" / "provenance_manifest.json"
        ).read_text(encoding="utf-8")

        for forbidden in (
            "xy99",
            "deadbeef",
            "secret-task",
            "identity_only.json",
            "/mnt/private",
            "replay_index",
            "level_number",
            "source_state",
        ):
            self.assertNotIn(forbidden, runtime_text)
        self.assertIn("environment_metadata/xy99/deadbeef/metadata.json", provenance_text)
        self.assertTrue(manifest["runtime_identity_free"])
        self.assertTrue(identity_audit["runtime_identity_free"])
        self.assertEqual(identity_audit["forbidden_path_count"], 0)
        self.assertEqual(identity_audit["forbidden_identity_token_count"], 3)

        for category in CATEGORIES:
            for record in self.jsonl(output / category / "records.jsonl"):
                self.assertRegex(record["record_id"], r"^evidence:\d{24}$")
                signature = record["selectors"]["semantic_signature"]
                if signature.startswith("semantic:"):
                    self.assertRegex(signature, r"^semantic:\d{20}$")

    def test_compilation_is_byte_deterministic(self) -> None:
        first, first_manifest = self.compile("first")
        second, second_manifest = self.compile("second")

        first_files = {
            path.relative_to(first).as_posix(): path.read_bytes()
            for path in first.rglob("*")
            if path.is_file()
        }
        second_files = {
            path.relative_to(second).as_posix(): path.read_bytes()
            for path in second.rglob("*")
            if path.is_file()
        }
        self.assertEqual(first_files, second_files)
        self.assertEqual(
            first_manifest["source_inventory_digest"],
            second_manifest["source_inventory_digest"],
        )

    def test_c_j_and_m_fixture_sets_are_nonempty(self) -> None:
        output, manifest = self.compile()
        counts = manifest["category_counts"]
        self.assertIsInstance(counts, dict)
        for category in manifest["fixture_sets"]["C"]:
            self.assertGreater(counts[category], 0)
        self.assertGreater(counts["hds_frames"], 0)
        self.assertGreater(counts["memory_lifecycles"], 0)

        for category in CATEGORIES:
            for record in self.jsonl(output / category / "records.jsonl"):
                self.assertTrue(record["runtime_identity_free"])

    def test_memory_templates_cover_the_full_p6_operation_vocabulary(self) -> None:
        output, _ = self.compile()
        records = self.jsonl(output / "memory_lifecycles" / "records.jsonl")
        operations = {
            operation
            for record in records
            for operation in record["payload"]["operation_candidates"]
        }
        self.assertEqual(
            operations,
            {
                "ADD",
                "REVISE",
                "MERGE",
                "SPLIT",
                "REPLACE",
                "INVALIDATE",
                "DELETE",
                "REINDEX",
                "ROLLBACK",
                "ARCHIVE",
            },
        )

    def test_holdout_groups_have_one_split_and_required_perturbations(self) -> None:
        output, _ = self.compile()
        holdouts = json.loads(
            (output / "holdout_families" / "manifest.json").read_text(
                encoding="utf-8"
            )
        )
        allowed = {"train", "validation", "holdout"}
        for group_name in (
            "family_groups",
            "structure_groups",
            "action_mechanism_groups",
        ):
            self.assertTrue(holdouts[group_name])
            self.assertTrue(set(holdouts[group_name].values()) <= allowed)
        self.assertEqual(
            holdouts["perturbations"],
            {"layout": "required", "color": "required", "position": "required"},
        )

    def test_nonzero_seed_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "seed is fixed at 0"):
            compile_evidence(
                analysis_dir=self.analysis,
                environment_dir=self.environments,
                output_dir=self.root / "invalid-seed",
                source_revision="fixture-revision",
                seed=1,
            )


if __name__ == "__main__":
    unittest.main()
