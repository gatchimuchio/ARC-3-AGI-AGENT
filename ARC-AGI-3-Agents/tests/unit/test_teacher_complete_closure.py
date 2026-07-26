from __future__ import annotations

import json
import unittest
from pathlib import Path
from typing import Any

from arc3_agi_agent.schema import digest_object
from arc3_agi_agent.teacher.human_replay_corpus import (
    _normalized_action_id,
    load_full_solution_corpus,
    load_source_manifest,
    source_manifest_digest,
)
from arc3_agi_agent.teacher.local_solution_overlay import (
    load_local_override_manifest,
)
from arc3_agi_agent.teacher.solution_graph_compiler import (
    CROSS_GAME_GRAMMAR_DIGEST_PREFIX,
    INTRA_GAME_GRAPH_DIGEST_PREFIX,
    LEVEL_GRAPH_DIGEST_PREFIX,
    LEVEL_GRAPH_LEDGER_DIGEST_PREFIX,
    PRIVILEGE_MATRIX_DIGEST_PREFIX,
    RUNTIME_P_REPORT_DIGEST_PREFIX,
    SOURCE_GAME_REGISTRY_ENTRY_DIGEST_PREFIX,
    load_teacher_closure_report,
)
from arc3_agi_agent.teacher.source_semantics import (
    GAME_SOURCE_CONTRACT_DIGEST_PREFIX,
    LEVEL_SOURCE_CONTRACT_DIGEST_PREFIX,
    SOURCE_SEMANTICS_DIGEST_PREFIX,
    compile_source_causal_semantics,
    source_contract_index,
)

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
TEACHER_ANALYSIS = REPOSITORY_ROOT / "analysis" / "teacher"
PACKAGE_ROOT = (
    REPOSITORY_ROOT / "ARC-AGI-3-Agents" / "arc3_agi_agent"
)


def _json(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError(f"expected JSON object: {path}")
    return value


def _assert_digest(
    testcase: unittest.TestCase,
    value: dict[str, Any],
    prefix: str,
) -> None:
    body = dict(value)
    claimed = body.pop("content_digest")
    testcase.assertEqual(claimed, prefix + digest_object(body))


class TeacherCompleteClosureTests(unittest.TestCase):
    def test_source_manifest_pins_one_full_win_for_all_samples(self) -> None:
        manifest = load_source_manifest(
            TEACHER_ANALYSIS
            / "HUMAN_WINNING_REPLAY_SOURCE_MANIFEST.json"
        )

        self.assertEqual(manifest["selected_game_count"], 25)
        self.assertEqual(manifest["selected_level_count"], 183)
        self.assertEqual(manifest["selected_expected_actions"], 11648)
        self.assertEqual(
            len({row["game_id"] for row in manifest["rows"]}),
            25,
        )
        self.assertEqual(
            len(manifest["pinned_trajectory_sha256_by_game"]),
            25,
        )

    def test_action_identifier_normalizes_both_dataset_formats(self) -> None:
        self.assertEqual(_normalized_action_id("ACTION3", "action"), 3)
        self.assertEqual(_normalized_action_id("6", "action"), 6)
        self.assertEqual(_normalized_action_id("RESET", "action"), 0)
        self.assertEqual(_normalized_action_id(7, "action"), 7)
        with self.assertRaises(ValueError):
            _normalized_action_id("ACTION9", "action")

    def test_corpus_is_complete_and_local_override_is_audited(self) -> None:
        corpus = load_full_solution_corpus(
            TEACHER_ANALYSIS / "FULL_SOLUTION_CORPUS.json"
        )
        override = load_local_override_manifest(
            TEACHER_ANALYSIS / "LOCAL_SOLUTION_OVERRIDE_MANIFEST.json"
        )

        self.assertTrue(corpus["complete_inventory"])
        self.assertEqual(corpus["game_count"], 25)
        self.assertEqual(corpus["level_count"], 183)
        self.assertEqual(corpus["source_recorded_action_count"], 11648)
        self.assertEqual(corpus["action_count"], 11574)
        self.assertEqual(corpus["local_solution_override_count"], 1)
        self.assertEqual(len(override["overrides"]), 1)
        manifest = load_source_manifest(
            TEACHER_ANALYSIS
            / "HUMAN_WINNING_REPLAY_SOURCE_MANIFEST.json"
        )
        self.assertEqual(
            corpus["source_manifest_digest"],
            source_manifest_digest(manifest),
        )
        ft09 = next(
            game
            for game in corpus["games"]
            if game["game_id"] == "ft09-0d8bbf25"
        )
        self.assertEqual(ft09["action_count"], 75)
        self.assertEqual(
            ft09["solution_origin"],
            "PINNED_LOCAL_SUCCESS_EVIDENCE_OVERRIDE",
        )

    def test_checked_in_teacher_report_closes_all_183_levels(self) -> None:
        report = load_teacher_closure_report(
            TEACHER_ANALYSIS / "TEACHER_S0_CLOSURE_REPORT.json"
        )

        self.assertTrue(report["all_complete"])
        self.assertEqual(report["completed_game_count"], 25)
        self.assertEqual(report["completed_levels"], 183)
        self.assertEqual(report["actions_executed"], 11574)
        self.assertEqual(report["error_count"], 0)
        self.assertEqual(report["available_action_mismatch_count"], 0)
        self.assertEqual(report["level_reset_compatibility_count"], 64)
        self.assertEqual(report["frame_digest_mismatch_count"], 542)

    def test_level_graph_ledger_has_one_content_bound_graph_per_level(
        self,
    ) -> None:
        ledger = _json(
            TEACHER_ANALYSIS / "LEVEL_SOLUTION_GRAPH_LEDGER.json"
        )
        _assert_digest(
            self,
            ledger,
            LEVEL_GRAPH_LEDGER_DIGEST_PREFIX,
        )

        self.assertEqual(ledger["level_graph_count"], 183)
        self.assertEqual(ledger["fully_replay_grounded_count"], 183)
        self.assertEqual(ledger["causal_semantic_complete_count"], 183)
        self.assertEqual(
            ledger["success_failure_contrast_complete_count"],
            183,
        )
        self.assertEqual(ledger["source_goal_witness_bound_count"], 183)
        self.assertEqual(ledger["source_hazard_witness_bound_count"], 183)
        self.assertEqual(
            ledger["hidden_state_boundary_bound_count"],
            183,
        )
        self.assertEqual(ledger["source_game_registry_count"], 25)
        for source_game in ledger[
            "source_game_causal_contract_registry"
        ]:
            body = dict(source_game)
            claimed = body.pop("registry_entry_digest")
            self.assertEqual(
                claimed,
                SOURCE_GAME_REGISTRY_ENTRY_DIGEST_PREFIX
                + digest_object(body),
            )
        self.assertEqual(
            ledger["state_and_level_transition_mismatch_count"],
            0,
        )
        self.assertEqual(
            ledger["source_frame_digest_mismatch_count"],
            542,
        )
        self.assertFalse(ledger["strict_source_frame_equivalence"])
        for graph in ledger["graphs"]:
            _assert_digest(self, graph, LEVEL_GRAPH_DIGEST_PREFIX)
            self.assertTrue(graph["causal_semantic_complete"])
            self.assertTrue(
                all(
                    graph[
                        "causal_semantic_completion_check"
                    ].values()
                )
            )
            self.assertTrue(graph["solution_trajectory"])
            self.assertIn("goal_predicate", graph)
            self.assertIn("progress_predicate", graph)
            self.assertIn("hazard_predicate", graph)
            self.assertIn("commit_predicate", graph)
            self.assertIn("necessary_conditions", graph)
            self.assertIn("sufficient_conditions", graph)
            self.assertEqual(
                graph["success_failure_contrast"]["status"],
                "SOURCE_CAUSAL_CONTRAST_COMPLETE",
            )
            self.assertFalse(
                graph["success_failure_contrast"][
                    "negative_execution_observed"
                ]
            )
            self.assertTrue(
                graph["goal_predicate"]["source_causal_witnesses"]
            )
            self.assertTrue(
                graph["hazard_predicate"]["source_causal_witnesses"]
            )
            self.assertIn(
                graph["hidden_variables"][0]["causal_role_status"],
                {
                    "CUSTOM_HIDDEN_STATE_EXPORT_SOURCE_BOUND",
                    "EXPLICIT_NO_CUSTOM_HIDDEN_STATE_EXPORT",
                },
            )
            self.assertTrue(
                graph["privilege_dependencies"][
                    "source_or_hidden_state"
                ]
            )
            source_roles = {
                role["role"]: role
                for role in graph["roles"]
                if role["role"]
                in {
                    "ACTOR_OR_MANIPULAND_SET",
                    "GOAL_STATE_PARTICIPANT_SET",
                    "HAZARD_STATE_PARTICIPANT_SET",
                }
            }
            self.assertEqual(len(source_roles), 3)
            for role in source_roles.values():
                binding = role["binding"]
                self.assertTrue(
                    binding["source_object_refs"]
                    or binding["source_state_symbols"]
                )

    def test_source_semantics_bind_all_current_environment_sources(
        self,
    ) -> None:
        semantics = compile_source_causal_semantics(
            environments_dir=REPOSITORY_ROOT / "environment_files",
            development_level_ledger_path=(
                REPOSITORY_ROOT
                / "analysis"
                / "development"
                / "LEGACY_LEVEL_ANALYSIS_LEDGER.json"
            ),
        )
        _assert_digest(
            self,
            semantics,
            SOURCE_SEMANTICS_DIGEST_PREFIX,
        )

        self.assertEqual(semantics["game_count"], 25)
        self.assertEqual(semantics["level_count"], 183)
        self.assertEqual(
            semantics["source_causal_complete_game_count"],
            25,
        )
        self.assertEqual(
            semantics["source_causal_complete_level_count"],
            183,
        )
        self.assertEqual(semantics["goal_witness_count"], 25)
        self.assertEqual(semantics["hazard_witness_count"], 43)
        self.assertEqual(
            semantics["custom_hidden_state_export_game_count"]
            + semantics[
                "explicit_no_custom_hidden_state_export_game_count"
            ],
            25,
        )
        self.assertEqual(len(source_contract_index(semantics)), 183)
        for game in semantics["games"]:
            _assert_digest(
                self,
                game,
                GAME_SOURCE_CONTRACT_DIGEST_PREFIX,
            )
            self.assertTrue(game["source_causal_complete"])
            self.assertTrue(game["goal_witnesses"])
            self.assertTrue(game["hazard_witnesses"])
            self.assertEqual(
                len(game["levels"]),
                game["level_count"],
            )
            for level in game["levels"]:
                _assert_digest(
                    self,
                    level,
                    LEVEL_SOURCE_CONTRACT_DIGEST_PREFIX,
                )
                self.assertTrue(level["object_families"])
                self.assertTrue(
                    level["development_mechanic_model"][
                        "mechanics_id"
                    ]
                )

        checked_ledger = _json(
            TEACHER_ANALYSIS / "LEVEL_SOLUTION_GRAPH_LEDGER.json"
        )
        self.assertEqual(
            checked_ledger["source_causal_semantics_digest"],
            semantics["content_digest"],
        )

    def test_progression_grammar_and_subtraction_gates_fail_closed(
        self,
    ) -> None:
        intra = _json(
            TEACHER_ANALYSIS / "INTRA_GAME_PROGRESSION_GRAPH.json"
        )
        grammar = _json(
            TEACHER_ANALYSIS / "CROSS_GAME_STRUCTURAL_GRAMMAR.json"
        )
        matrix = _json(
            TEACHER_ANALYSIS / "PRIVILEGE_SUBTRACTION_MATRIX.json"
        )
        runtime = _json(
            TEACHER_ANALYSIS / "RUNTIME_P_COMPILATION_REPORT.json"
        )
        _assert_digest(self, intra, INTRA_GAME_GRAPH_DIGEST_PREFIX)
        _assert_digest(self, grammar, CROSS_GAME_GRAMMAR_DIGEST_PREFIX)
        _assert_digest(self, matrix, PRIVILEGE_MATRIX_DIGEST_PREFIX)
        _assert_digest(self, runtime, RUNTIME_P_REPORT_DIGEST_PREFIX)

        self.assertEqual(intra["game_count"], 25)
        self.assertEqual(intra["progression_edge_count"], 158)
        self.assertEqual(
            intra["source_causal_progression_status"],
            "COMPLETE_158_OF_158",
        )
        self.assertTrue(grammar["identity_free_artifact"])
        self.assertFalse(grammar["contains_literal_coordinates"])
        self.assertEqual(
            grammar["coverage"][
                "source_causal_semantic_complete_count"
            ],
            183,
        )
        self.assertEqual(
            grammar["proof_status"][
                "source_causal_semantic_factorization"
            ],
            "PASS_183_OF_183",
        )
        self.assertEqual(matrix["stage_summary"]["S0"]["status"], "PASS")
        self.assertEqual(
            matrix["source_or_hidden_state_dependent_count"],
            183,
        )
        for stage in ("S1", "S2", "S3", "S4", "S5", "S6"):
            self.assertEqual(
                matrix["stage_summary"][stage]["status"],
                "NOT_RUN",
            )
        self.assertFalse(runtime["compilation"]["runtime_p_modified"])
        self.assertEqual(
            runtime["claims"]["source_causal_semantics_183"],
            "PASS",
        )
        self.assertEqual(
            runtime["claims"]["intra_game_progression_158"],
            "PASS",
        )
        self.assertEqual(
            runtime["claims"]["rendered_only_183"],
            "NOT_PROVEN",
        )

    def test_runtime_package_does_not_import_teacher_artifacts(self) -> None:
        forbidden = (
            "arc3_agi_agent.teacher",
            "from .teacher",
            "from ..teacher",
            "FULL_SOLUTION_CORPUS",
            "LEVEL_SOLUTION_GRAPH_LEDGER",
            "PRIVILEGE_SUBTRACTION_MATRIX",
        )
        violations: list[str] = []
        teacher_root = PACKAGE_ROOT / "teacher"
        for path in PACKAGE_ROOT.rglob("*.py"):
            if path.is_relative_to(teacher_root):
                continue
            text = path.read_text(encoding="utf-8")
            for token in forbidden:
                if token in text:
                    violations.append(
                        f"{path.relative_to(PACKAGE_ROOT)}:{token}"
                    )

        self.assertEqual(violations, [])

    def test_privileged_teacher_score_is_separate_and_content_bound(
        self,
    ) -> None:
        oracle = _json(
            TEACHER_ANALYSIS / "TEACHER_S0_LOCAL_SCORE_ORACLE.json"
        )
        current = oracle["current_local_result"]

        self.assertEqual(current["completed_levels"], 183)
        self.assertEqual(current["completion_rate_percent"], 100.0)
        self.assertEqual(
            current["official_rhae_score_percent"],
            99.446886157,
        )
        self.assertEqual(current["error_count"], 0)
        self.assertFalse(
            current["evaluation_provenance"][
                "architecture_evidence_eligible"
            ]
        )


if __name__ == "__main__":
    unittest.main()
