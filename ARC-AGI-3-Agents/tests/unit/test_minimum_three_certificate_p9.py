from __future__ import annotations

import dataclasses
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from arc3_agi_agent.certificate import (
    P9_ARTIFACT_FILENAMES,
    SUBSET_EXPECTATIONS,
    SUBSET_FAILURE_WITNESSES,
    SUBSET_ORDER,
    ComputeOnlyHarness,
    EmptySubsetHarness,
    JudgmentOnlyHarness,
    MemoryOnlyHarness,
    build_p9_artifacts,
    default_certificate_observation,
    run_eight_subset_audit,
    write_p9_artifacts,
)
from arc3_agi_agent.schema import forbidden_runtime_paths

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
OBLIGATION_GRAPH_PATH = (
    REPOSITORY_ROOT / "docs" / "architecture" / "AGI_OBLIGATION_GRAPH.json"
)
CHECKED_IN_ARTIFACT_DIR = REPOSITORY_ROOT / "certificates" / "p9"


def _load_obligation_graph() -> dict[str, object]:
    value = json.loads(OBLIGATION_GRAPH_PATH.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("obligation graph must be an object")
    return value


class MinimumThreeCertificateTests(unittest.TestCase):
    def test_finite_enumeration_contains_each_subset_exactly_once(self) -> None:
        report = run_eight_subset_audit(default_certificate_observation())

        self.assertEqual(len(report.cases), 8)
        self.assertEqual(
            tuple(case.members for case in report.cases),
            SUBSET_ORDER,
        )
        self.assertEqual(len(set(SUBSET_ORDER)), 8)

    def test_only_full_set_passes_all_obligations(self) -> None:
        report = run_eight_subset_audit(default_certificate_observation())

        self.assertTrue(report.passed)
        self.assertTrue(report.full_set_pass)
        self.assertEqual(report.proper_subset_pass_count, 0)
        self.assertEqual(report.single_removal_fail_count, 3)
        self.assertEqual(report.pair_subset_fail_count, 3)
        self.assertTrue(report.two_cycle_causality_pass)
        self.assertEqual(report.functional_equivalent_leak_count, 0)
        self.assertEqual(
            [case.overall for case in report.cases],
            ["FAIL"] * 7 + ["PASS"],
        )

    def test_measured_matrix_and_unique_witnesses_match_spec(self) -> None:
        report = run_eight_subset_audit(default_certificate_observation())

        for case in report.cases:
            with self.subTest(subset=case.subset_id):
                self.assertEqual(
                    dict(case.obligation_statuses),
                    SUBSET_EXPECTATIONS[case.members],
                )
                self.assertEqual(
                    case.failure_witness,
                    SUBSET_FAILURE_WITNESSES.get(case.members, ""),
                )
                self.assertTrue(case.passed)
        self.assertEqual(
            {item.failure_witness for item in report.removal_witnesses},
            {
                "NO_PERSISTENT_EXPERIENCE_CAUSALITY",
                "NO_JUDGMENT_OR_AUTHORIZATION",
                "NO_GENERATIVE_COMPUTATION",
            },
        )

    def test_single_harnesses_have_only_named_subjects_and_outputs(
        self,
    ) -> None:
        harnesses = {
            (): EmptySubsetHarness(),
            ("C",): ComputeOnlyHarness(),
            ("J",): JudgmentOnlyHarness(),
            ("M",): MemoryOnlyHarness(),
        }
        subject_fields = {
            "C": "compute_subject",
            "J": "judgment_subject",
            "M": "memory_subject",
        }
        for members, harness in harnesses.items():
            with self.subTest(members=members):
                evidence = harness.exercise(default_certificate_observation())
                self.assertEqual(evidence.members, members)
                self.assertEqual(
                    evidence.functional_equivalent_responsibility_leaks,
                    (),
                )
                for subject, field_name in subject_fields.items():
                    self.assertEqual(
                        hasattr(harness, field_name),
                        subject in members,
                    )

    def test_report_is_deterministic_and_runtime_identity_free(self) -> None:
        first = run_eight_subset_audit(default_certificate_observation())
        second = run_eight_subset_audit(default_certificate_observation())

        self.assertEqual(first, second)
        self.assertEqual(first.digest, second.digest)
        self.assertEqual(
            forbidden_runtime_paths(dataclasses.asdict(first)),
            (),
        )

    def test_artifact_builder_emits_exact_required_set_and_conditions(
        self,
    ) -> None:
        outputs = build_p9_artifacts(_load_obligation_graph())
        certificate = json.loads(
            outputs["agi_minimum_three_certificate.json"]
        )

        self.assertEqual(tuple(outputs), P9_ARTIFACT_FILENAMES)
        self.assertEqual(certificate["artifact_count"], 5)
        self.assertTrue(certificate["full_set_pass"])
        self.assertEqual(certificate["proper_subset_pass_count"], 0)
        self.assertEqual(certificate["proper_subset_fail_count"], 7)
        self.assertEqual(certificate["single_removal_fail_count"], 3)
        self.assertEqual(certificate["pair_subset_fail_count"], 3)
        self.assertTrue(certificate["two_cycle_causality_pass"])
        self.assertEqual(
            certificate["functional_equivalent_leak_count"],
            0,
        )

    def test_certificate_content_and_artifact_digests_validate(self) -> None:
        outputs = build_p9_artifacts(_load_obligation_graph())
        certificate = json.loads(
            outputs["agi_minimum_three_certificate.json"]
        )
        claimed_content_digest = certificate.pop("content_digest")
        encoded_core = (
            json.dumps(
                certificate,
                ensure_ascii=False,
                indent=2,
                sort_keys=True,
            )
            + "\n"
        ).encode("utf-8")

        self.assertEqual(
            claimed_content_digest,
            hashlib.sha256(encoded_core).hexdigest(),
        )
        for name, expected_digest in certificate[
            "artifact_digests"
        ].items():
            self.assertEqual(
                hashlib.sha256(outputs[name]).hexdigest(),
                expected_digest,
            )

    def test_checked_in_artifacts_rebuild_byte_identically(self) -> None:
        expected = build_p9_artifacts(_load_obligation_graph())
        self.assertEqual(
            {path.name for path in CHECKED_IN_ARTIFACT_DIR.iterdir()},
            set(P9_ARTIFACT_FILENAMES),
        )
        for name, content in expected.items():
            with self.subTest(name=name):
                self.assertEqual(
                    (CHECKED_IN_ARTIFACT_DIR / name).read_bytes(),
                    content,
                )

        with tempfile.TemporaryDirectory() as temporary:
            written = write_p9_artifacts(
                obligation_graph_path=OBLIGATION_GRAPH_PATH,
                output_dir=Path(temporary),
            )
            self.assertEqual(
                tuple(path.name for path in written),
                P9_ARTIFACT_FILENAMES,
            )
            for path in written:
                self.assertEqual(path.read_bytes(), expected[path.name])

    def test_empty_observation_is_not_silently_replaced_by_default(self) -> None:
        with self.assertRaises((KeyError, ValueError)):
            build_p9_artifacts(
                _load_obligation_graph(),
                raw_observation={},
            )


if __name__ == "__main__":
    unittest.main()
