from __future__ import annotations

import hashlib
import itertools
import json
import unittest
from pathlib import Path


class AGIMinimumThreeAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.repository_root = Path(__file__).resolve().parents[3]
        cls.package_root = cls.repository_root / "ARC-AGI-3-Agents"
        cls.architecture_root = cls.repository_root / "docs" / "architecture"
        graph_path = cls.architecture_root / "AGI_OBLIGATION_GRAPH.json"
        cls.graph = json.loads(graph_path.read_text(encoding="utf-8"))

    def test_normative_roadmap_is_retained_without_content_drift(self) -> None:
        roadmap = (
            self.repository_root
            / "docs"
            / "roadmap"
            / "AGI_MINIMUM_THREE_IMPLEMENTATION_PROOF_ROADMAP.md"
        )
        self.assertTrue(roadmap.is_file())
        digest = hashlib.sha256(roadmap.read_bytes()).hexdigest()
        self.assertEqual(
            digest,
            "bd4e7545fcb6a6c25483ed86bfbedfa44f1ee731af687ed87806e2c6d98ad09b",
        )

    def test_all_required_p2_artifacts_exist(self) -> None:
        required = {
            "AGI_MINIMUM_THREE_SPEC.md",
            "AGI_OBLIGATION_GRAPH.json",
            "AGI_TRACEABILITY_MATRIX.md",
            "AGI_CLAIM_REGISTRY.md",
            "AGI_TEST_MATRIX.md",
            "AGI_CURRENT_IMPLEMENTATION_AUDIT.md",
        }
        present = {
            path.name
            for path in self.architecture_root.iterdir()
            if path.is_file()
        }
        self.assertTrue(required <= present)

    def test_obligation_and_subject_ownership_is_complete_and_unique(self) -> None:
        obligations = self.graph["obligations"]
        self.assertEqual({item["id"] for item in obligations}, {f"G{i}" for i in range(1, 6)})

        subjects = self.graph["subjects"]
        self.assertEqual({item["id"] for item in subjects}, {"C", "J", "M"})
        owners = {
            obligation
            for subject in subjects
            for obligation in subject["owns"]
        }
        self.assertEqual(owners, {"G1", "G2", "G3"})
        self.assertEqual(len(owners), sum(len(subject["owns"]) for subject in subjects))

    def test_every_audited_element_is_accounted_for(self) -> None:
        required = {
            "L0",
            "P",
            "C",
            "J",
            "M",
            "ENVIRONMENT_BOUNDARY",
            "LEARNING_COMPILER",
            "P0",
            "J0",
            "M0",
            "EXTERNAL_EMISSION",
            "MEMORY_WRITE",
            "HDS_FRAME",
            "CYCLE_TRANSITION",
            "STOPPING",
            "ROLLBACK",
        }
        elements = self.graph["elements"]
        self.assertEqual({item["id"] for item in elements}, required)
        self.assertTrue(
            all(
                item["current_status"]
                in {"SUPPORTED", "PARTIAL", "UNSUPPORTED", "REJECTED"}
                for item in elements
            )
        )

    def test_current_implementation_paths_exist_or_gap_is_explicit(self) -> None:
        for obligation in self.graph["obligations"]:
            paths = obligation["implementation_paths"]
            gaps = obligation["gaps"]
            if not paths:
                self.assertTrue(gaps, obligation["id"])
            for path_with_symbol in paths:
                relative_path = path_with_symbol.split("::", maxsplit=1)[0]
                self.assertTrue(
                    (self.repository_root / relative_path).is_file(),
                    path_with_symbol,
                )

    def test_all_eight_subject_subsets_are_enumerated_once(self) -> None:
        expected = {
            tuple(combo)
            for size in range(4)
            for combo in itertools.combinations(("C", "J", "M"), size)
        }
        observed = {
            tuple(item["members"])
            for item in self.graph["subset_expectations"]
        }
        self.assertEqual(observed, expected)
        self.assertEqual(len(self.graph["subset_expectations"]), 8)

    def test_only_full_set_is_expected_to_pass(self) -> None:
        passing = [
            tuple(item["members"])
            for item in self.graph["subset_expectations"]
            if item["overall"] == "PASS"
        ]
        self.assertEqual(passing, [("C", "J", "M")])
        full = next(
            item
            for item in self.graph["subset_expectations"]
            if tuple(item["members"]) == ("C", "J", "M")
        )
        self.assertTrue(all(full[f"G{i}"] == "PASS" for i in range(1, 6)))

    def test_pair_failure_witnesses_are_fixed_and_unique(self) -> None:
        expected = {
            "C+J": "NO_PERSISTENT_EXPERIENCE_CAUSALITY",
            "C+M": "NO_JUDGMENT_OR_AUTHORIZATION",
            "J+M": "NO_GENERATIVE_COMPUTATION",
        }
        witnesses = self.graph["pair_failure_witnesses"]
        self.assertEqual(witnesses, expected)
        self.assertEqual(len(set(witnesses.values())), 3)

    def test_supported_claims_have_existing_primary_evidence(self) -> None:
        for claim in self.graph["current_claims"]:
            primary = claim["primary_test"]
            if claim["status"] == "SUPPORTED":
                self.assertIsInstance(primary, str, claim["id"])
                self.assertTrue((self.package_root / primary).is_file(), claim["id"])
            else:
                self.assertIsNone(primary, claim["id"])

    def test_claim_registry_matches_machine_readable_statuses(self) -> None:
        registry = (
            self.architecture_root / "AGI_CLAIM_REGISTRY.md"
        ).read_text(encoding="utf-8")
        for claim in self.graph["current_claims"]:
            self.assertIn(f"`{claim['id']}`", registry)
            self.assertIn(f"`{claim['status']}`", registry)

    def test_blocking_findings_and_order_are_explicit(self) -> None:
        audit = (
            self.architecture_root / "AGI_CURRENT_IMPLEMENTATION_AUDIT.md"
        ).read_text(encoding="utf-8")
        for index in range(1, 11):
            self.assertIn(f"F-P2-{index:03d}", audit)
        for phase in range(3, 12):
            self.assertIn(f"P{phase}", audit)


if __name__ == "__main__":
    unittest.main()
