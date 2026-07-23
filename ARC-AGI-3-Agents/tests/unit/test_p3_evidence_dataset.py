from __future__ import annotations

import hashlib
import json
import re
import unittest
from pathlib import Path
from typing import Any

from arc3_agi_agent.evidence_compiler import CATEGORIES


class P3EvidenceDatasetAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repository_root = Path(__file__).resolve().parents[3]
        cls.dataset_root = cls.repository_root / "datasets"
        cls.manifest_root = cls.repository_root / "manifests"
        cls.dataset_manifest = cls.load_json(
            cls.manifest_root / "dataset_manifest.json"
        )
        cls.provenance = cls.load_json(
            cls.manifest_root / "provenance_manifest.json"
        )
        cls.identity_audit = cls.load_json(
            cls.manifest_root / "identity_free_audit.json"
        )
        cls.holdouts = cls.load_json(
            cls.dataset_root / "holdout_families" / "manifest.json"
        )
        cls.records_by_category = {
            category: cls.load_jsonl(
                cls.dataset_root / category / "records.jsonl"
            )
            for category in CATEGORIES
        }
        cls.records = {
            record["record_id"]: record
            for records in cls.records_by_category.values()
            for record in records
        }

    @staticmethod
    def load_json(path: Path) -> dict[str, Any]:
        value = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(value, dict):
            raise TypeError(f"expected object: {path}")
        return value

    @staticmethod
    def load_jsonl(path: Path) -> list[dict[str, Any]]:
        values = [
            json.loads(line)
            for line in path.read_text(encoding="utf-8").splitlines()
            if line
        ]
        if not all(isinstance(value, dict) for value in values):
            raise TypeError(f"expected object records: {path}")
        return values

    def test_all_current_sources_are_accounted_without_parse_error(self) -> None:
        manifest = self.dataset_manifest
        self.assertEqual(manifest["source_file_count"], 730)
        self.assertEqual(manifest["source_accounted_count"], 730)
        self.assertEqual(manifest["source_materialized_count"], 705)
        self.assertEqual(manifest["source_no_runtime_material_count"], 25)
        self.assertEqual(manifest["source_parse_error_count"], 0)
        self.assertEqual(
            manifest["source_inventory_digest"],
            "7f3afe283d53d6cc6d1486bdd5ef407cb2fb193d41cabd155c09189bca9192a7",
        )
        self.assertEqual(len(self.provenance["sources"]), 730)
        self.assertTrue(
            all(
                source["parse_status"] == "PARSED"
                for source in self.provenance["sources"]
            )
        )

    def test_dataset_files_match_manifest_hashes_and_counts(self) -> None:
        manifest = self.dataset_manifest
        self.assertEqual(manifest["runtime_record_count"], len(self.records))
        self.assertEqual(
            manifest["runtime_record_count"],
            sum(manifest["category_counts"].values()),
        )
        for category in CATEGORIES:
            self.assertEqual(
                manifest["category_counts"][category],
                len(self.records_by_category[category]),
            )
        for relative_path, expected in manifest["output_hashes"].items():
            path = self.repository_root / relative_path
            self.assertTrue(path.is_file(), relative_path)
            self.assertEqual(
                hashlib.sha256(path.read_bytes()).hexdigest(),
                expected,
                relative_path,
            )

    def test_c_j_and_m_fixtures_are_separate_and_nonempty(self) -> None:
        fixtures = self.dataset_manifest["fixture_sets"]
        self.assertEqual(
            tuple(fixtures["C"]),
            (
                "observations",
                "transitions",
                "effects",
                "hazards",
                "progress",
                "contradictions",
            ),
        )
        self.assertEqual(tuple(fixtures["J"]), ("hds_frames",))
        self.assertEqual(tuple(fixtures["M"]), ("memory_lifecycles",))
        self.assertEqual(
            set(fixtures["C"]) | set(fixtures["J"]) | set(fixtures["M"]),
            set(CATEGORIES),
        )
        self.assertTrue(
            all(self.records_by_category[category] for category in CATEGORIES)
        )

    def test_provenance_is_bidirectional_and_family_split_isolated(self) -> None:
        sources = {
            source["source_index"]: source
            for source in self.provenance["sources"]
        }
        provenance_records = {
            record["record_id"]: record
            for record in self.provenance["records"]
        }
        self.assertEqual(set(provenance_records), set(self.records))

        for record_id, record in provenance_records.items():
            runtime = self.records[record_id]
            self.assertEqual(record["split"], runtime["split"])
            for source_index in record["source_indices"]:
                source = sources[source_index]
                self.assertIn(record_id, source["record_ids"])
                self.assertEqual(
                    source["family_split"],
                    runtime["split"]["family"],
                )
        for source in sources.values():
            for record_id in source["record_ids"]:
                self.assertIn(source["source_index"], provenance_records[record_id]["source_indices"])

    def test_holdout_groups_are_single_split_and_runtime_groups_agree(self) -> None:
        allowed = {"train", "validation", "holdout"}
        self.assertEqual(
            self.holdouts["perturbations"],
            {
                "layout": "required",
                "color": "required",
                "position": "required",
            },
        )
        for group_name in (
            "family_groups",
            "structure_groups",
            "action_mechanism_groups",
        ):
            groups = self.holdouts[group_name]
            self.assertTrue(groups)
            self.assertTrue(set(groups.values()) <= allowed)

        family_groups = self.holdouts["family_groups"]
        for source in self.provenance["sources"]:
            self.assertEqual(
                family_groups[source["family_group"]],
                source["family_split"],
            )
        for record in self.records.values():
            structure_group = record["split_groups"]["structure"]
            mechanism_group = record["split_groups"]["action_mechanism"]
            self.assertEqual(
                self.holdouts["structure_groups"][structure_group],
                record["split"]["structure"],
            )
            self.assertEqual(
                self.holdouts["action_mechanism_groups"][mechanism_group],
                record["split"]["action_mechanism"],
            )

    def test_runtime_corpus_has_no_identity_key_path_or_source_name(self) -> None:
        runtime_text = "\n".join(
            (self.dataset_root / category / "records.jsonl")
            .read_text(encoding="utf-8")
            .casefold()
            for category in CATEGORIES
        )
        identity_tokens: set[str] = set()
        for metadata in (
            self.repository_root / "environment_files"
        ).glob("*/*/metadata.json"):
            value = self.load_json(metadata)
            identity_tokens.update(
                (
                    metadata.parent.parent.name.casefold(),
                    metadata.parent.name.casefold(),
                )
            )
            for key in ("game_id", "title"):
                identity = value.get(key)
                if isinstance(identity, str):
                    identity_tokens.add(identity.casefold())
        source_names = {
            Path(source["path"]).name.casefold()
            for source in self.provenance["sources"]
        }
        self.assertFalse(
            {
                token
                for token in identity_tokens
                if len(token) >= 4 and token in runtime_text
            }
        )
        self.assertFalse({name for name in source_names if name in runtime_text})

        forbidden_key = re.compile(
            r"(?i)(game.?id|task.?id|level.?id|level.?number|"
            r"replay.?index|answer.?map|baseline.?actions?|"
            r"literal.?coordinates?|source.?state|file.?path|file.?name)"
        )
        for record in self.records.values():
            self.assertRegex(record["record_id"], r"^evidence:\d{24}$")
            stack: list[object] = [record]
            while stack:
                item = stack.pop()
                if isinstance(item, dict):
                    self.assertFalse(
                        any(forbidden_key.search(str(key)) for key in item)
                    )
                    stack.extend(item.values())
                elif isinstance(item, list | tuple):
                    stack.extend(item)

        self.assertTrue(self.dataset_manifest["runtime_identity_free"])
        self.assertTrue(self.identity_audit["runtime_identity_free"])
        self.assertEqual(self.identity_audit["forbidden_path_count"], 0)

    def test_memory_fixture_covers_all_required_operations(self) -> None:
        operations = {
            operation
            for record in self.records_by_category["memory_lifecycles"]
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


if __name__ == "__main__":
    unittest.main()
