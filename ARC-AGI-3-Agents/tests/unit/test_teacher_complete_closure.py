from __future__ import annotations

import inspect
import json
import unittest
from decimal import Decimal
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
from arc3_agi_agent.teacher.s1_graph_executor import (
    S1_CLOSURE_REPORT_DIGEST_PREFIX,
    load_s1_closure_report,
)
from arc3_agi_agent.teacher.s1_graph_schema import (
    S1_GAME_GRAPH_DIGEST_PREFIX,
    S1_POLICY_GRAPH_DIGEST_PREFIX,
    load_s1_policy_graph,
)
from arc3_agi_agent.teacher.s1_score_adapter import (
    S1_SCORE_ADAPTER_DIGEST_PREFIX,
)
from arc3_agi_agent.teacher.s2_graph_executor import (
    S2_CLOSURE_REPORT_DIGEST_PREFIX,
    load_s2_closure_report,
)
from arc3_agi_agent.teacher.s2_graph_schema import (
    S2_GAME_GRAPH_DIGEST_PREFIX,
    S2_POLICY_GRAPH_DIGEST_PREFIX,
    all_mapping_keys,
    load_s2_policy_graph,
)
from arc3_agi_agent.teacher.s2_score_adapter import (
    S2_SCORE_ADAPTER_DIGEST_PREFIX,
)
from arc3_agi_agent.teacher.s3_graph_executor import (
    S3_CLOSURE_REPORT_DIGEST_PREFIX,
    load_s3_closure_report,
)
from arc3_agi_agent.teacher.s3_graph_schema import (
    S3_POLICY_GRAPH_DIGEST_PREFIX,
    identity_literal_values,
    load_s3_policy_graph,
)
from arc3_agi_agent.teacher.s3_graph_schema import (
    all_mapping_keys as s3_all_mapping_keys,
)
from arc3_agi_agent.teacher.s3_score_adapter import (
    S3_SCORE_ADAPTER_DIGEST_PREFIX,
)
from arc3_agi_agent.teacher.s4_graph_executor import (
    S4_CLOSURE_REPORT_DIGEST_PREFIX,
    load_s4_closure_report,
    select_s4_policy_edge,
)
from arc3_agi_agent.teacher.s4_graph_schema import (
    S4_POLICY_GRAPH_DIGEST_PREFIX,
    load_s4_policy_graph,
)
from arc3_agi_agent.teacher.s4_graph_schema import (
    all_mapping_keys as s4_all_mapping_keys,
)
from arc3_agi_agent.teacher.s4_graph_schema import (
    identity_literal_values as s4_identity_literal_values,
)
from arc3_agi_agent.teacher.s4_score_adapter import (
    S4_SCORE_ADAPTER_DIGEST_PREFIX,
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
        self.assertEqual(
            grammar["proof_status"][
                "identity_routing_free_execution"
            ],
            "PASS_183_OF_183",
        )
        self.assertEqual(
            grammar["proof_status"][
                "source_hidden_state_free_execution"
            ],
            "PASS_183_OF_183",
        )
        self.assertEqual(
            grammar["proof_status"]["rendered_only_execution"],
            "PASS_183_OF_183",
        )
        self.assertEqual(
            grammar["proof_status"]["generalization"],
            "MEASURED_NOT_PROVEN",
        )
        self.assertEqual(matrix["stage_summary"]["S0"]["status"], "PASS")
        self.assertEqual(
            matrix["source_or_hidden_state_dependent_count"],
            0,
        )
        self.assertEqual(
            matrix["s3_source_or_hidden_state_dependent_count"],
            183,
        )
        self.assertEqual(
            matrix["stage_summary"]["S1"]["status"],
            "PASS",
        )
        self.assertEqual(
            matrix["stage_summary"]["S1"]["completed_levels"],
            183,
        )
        self.assertEqual(
            matrix["stage_summary"]["S2"]["status"],
            "PASS",
        )
        self.assertEqual(
            matrix["stage_summary"]["S2"]["completed_levels"],
            183,
        )
        self.assertEqual(
            matrix["stage_summary"]["S3"]["status"],
            "PASS",
        )
        self.assertEqual(
            matrix["stage_summary"]["S3"]["completed_levels"],
            183,
        )
        self.assertEqual(
            matrix["stage_summary"]["S4"]["status"],
            "PASS",
        )
        self.assertEqual(
            matrix["stage_summary"]["S4"]["completed_levels"],
            183,
        )
        self.assertEqual(matrix["fixed_action_dependent_count"], 0)
        self.assertEqual(
            matrix["s0_fixed_action_dependent_count"],
            183,
        )
        self.assertEqual(matrix["literal_coordinate_dependent_count"], 0)
        self.assertEqual(
            matrix["s1_literal_coordinate_dependent_count"],
            125,
        )
        self.assertEqual(matrix["identity_routing_dependent_count"], 0)
        self.assertEqual(
            matrix["s2_identity_routing_dependent_count"],
            183,
        )
        self.assertEqual(
            matrix["stage_summary"]["S5"]["status"],
            "PASS",
        )
        self.assertEqual(
            matrix["stage_summary"]["S5"]["completed_levels"],
            183,
        )
        self.assertEqual(
            matrix["stage_summary"]["S6"]["status"],
            "MEASURED",
        )
        self.assertEqual(
            matrix["stage_summary"]["S6"]["measurement_count"],
            14_336,
        )
        self.assertEqual(matrix["generalization_proven_count"], 0)
        self.assertTrue(runtime["compilation"]["runtime_p_modified"])
        self.assertEqual(
            runtime["claims"]["source_causal_semantics_183"],
            "PASS",
        )
        self.assertEqual(
            runtime["claims"]["intra_game_progression_158"],
            "PASS",
        )
        self.assertEqual(
            runtime["claims"]["fixed_action_free_183"],
            "PASS",
        )
        self.assertEqual(
            runtime["claims"]["literal_coordinate_free_183"],
            "PASS",
        )
        self.assertEqual(
            runtime["claims"]["identity_routing_free_183"],
            "PASS",
        )
        self.assertEqual(
            runtime["claims"]["source_hidden_state_free_183"],
            "PASS",
        )
        self.assertEqual(
            runtime["compilation"]["first_required_stage"],
            "P11",
        )
        self.assertEqual(
            runtime["compilation"]["status"],
            "ADOPTED_RENDERED_ONLY_RUNTIME_P",
        )
        self.assertEqual(
            runtime["claims"]["rendered_only_183"],
            "PASS_183_OF_183",
        )
        self.assertEqual(
            runtime["claims"]["generalization"],
            "MEASURED_NOT_PROVEN",
        )

    def test_s1_graph_is_state_conditioned_and_closes_all_levels(
        self,
    ) -> None:
        graph = load_s1_policy_graph(
            TEACHER_ANALYSIS
            / "S1_STATE_CONDITIONED_POLICY_GRAPH.json"
        )
        report = load_s1_closure_report(
            TEACHER_ANALYSIS
            / "TEACHER_S1_CLOSURE_REPORT.json"
        )
        _assert_digest(
            self,
            graph,
            S1_POLICY_GRAPH_DIGEST_PREFIX,
        )
        _assert_digest(
            self,
            report,
            S1_CLOSURE_REPORT_DIGEST_PREFIX,
        )

        self.assertEqual(graph["game_count"], 25)
        self.assertEqual(graph["level_count"], 183)
        self.assertEqual(
            graph["source_transition_witness_count"],
            11574,
        )
        self.assertEqual(graph["strict_progress_game_count"], 25)
        self.assertEqual(graph["action_effect_history_limit"], 4)
        self.assertFalse(
            graph["remaining_privilege_dependencies"][
                "fixed_action_sequence"
            ]
        )
        self.assertTrue(
            graph["remaining_privilege_dependencies"][
                "task_game_identity"
            ]
        )
        self.assertTrue(
            graph["remaining_privilege_dependencies"][
                "source_or_hidden_state"
            ]
        )
        self.assertEqual(report["completed_levels"], 183)
        self.assertEqual(report["error_count"], 0)
        self.assertTrue(report["all_complete"])
        self.assertFalse(report["fixed_action_sequence_used"])
        self.assertFalse(report["decision_uses_replay_position"])
        self.assertFalse(report["decision_uses_action_ordinal"])
        self.assertEqual(
            report["strict_distance_decrease_count"],
            report["actions_executed"],
        )
        self.assertEqual(
            report["source_policy_graph_digest"],
            graph["content_digest"],
        )

        forbidden_node_keys = {
            "step",
            "source_step",
            "cursor",
            "replay_index",
            "action_ordinal",
            "source_order",
        }

        def collect_keys(value: object) -> set[str]:
            if isinstance(value, dict):
                return set(value).union(
                    *(
                        collect_keys(item)
                        for item in value.values()
                    ),
                    set(),
                )
            if isinstance(value, list):
                return set().union(
                    *(collect_keys(item) for item in value),
                    set(),
                )
            return set()

        self.assertEqual(
            collect_keys(graph).intersection(forbidden_node_keys),
            set(),
        )
        for game in graph["games"]:
            _assert_digest(
                self,
                game,
                S1_GAME_GRAPH_DIGEST_PREFIX,
            )
            self.assertTrue(game["strict_progress_policy"])
            for node in game["nodes"]:
                if node["goal_node"]:
                    self.assertIsNone(
                        node["selected_action_signature"]
                    )
                    continue
                selected = [
                    edge
                    for edge in node["outgoing_edges"]
                    if edge["action_signature"]
                    == node["selected_action_signature"]
                ]
                self.assertEqual(len(selected), 1)
                self.assertTrue(
                    selected[0]["strict_distance_decrease"]
                )
                self.assertTrue(
                    all(
                        distance < node["distance_to_goal"]
                        for distance in selected[0][
                            "target_distance_to_goal"
                        ]
                    )
                )

    def test_s1_executor_has_no_corpus_or_position_dependency(self) -> None:
        source = (
            PACKAGE_ROOT / "teacher" / "s1_graph_executor.py"
        ).read_text(encoding="utf-8")
        forbidden = (
            "FULL_SOLUTION_CORPUS",
            "human_replay_corpus",
            "source_step",
            "replay_index",
            "for raw_action in",
        )
        self.assertEqual(
            [token for token in forbidden if token in source],
            [],
        )

    def test_s2_graph_has_no_absolute_pointer_payload_and_closes(
        self,
    ) -> None:
        graph = load_s2_policy_graph(
            TEACHER_ANALYSIS / "S2_ROLE_RELATIVE_POLICY_GRAPH.json"
        )
        report = load_s2_closure_report(
            TEACHER_ANALYSIS / "TEACHER_S2_CLOSURE_REPORT.json"
        )
        _assert_digest(
            self,
            graph,
            S2_POLICY_GRAPH_DIGEST_PREFIX,
        )
        _assert_digest(
            self,
            report,
            S2_CLOSURE_REPORT_DIGEST_PREFIX,
        )

        self.assertEqual(graph["game_count"], 25)
        self.assertEqual(graph["level_count"], 183)
        self.assertEqual(
            graph["source_transition_witness_count"],
            10733,
        )
        self.assertEqual(graph["state_node_count"], 10758)
        self.assertEqual(graph["edge_count"], 10733)
        self.assertEqual(graph["role_selector_witness_count"], 3112)
        self.assertEqual(
            graph["boundary_selector_witness_count"],
            204,
        )
        self.assertEqual(
            graph["relative_constraint_witness_count"],
            26623,
        )
        self.assertEqual(graph["absolute_pointer_payload_count"], 0)
        self.assertFalse(
            graph["remaining_privilege_dependencies"][
                "literal_coordinate"
            ]
        )
        self.assertEqual(
            all_mapping_keys(graph).intersection(
                {
                    "absolute_horizontal_index",
                    "absolute_vertical_index",
                    "action_data",
                    "column",
                    "coordinate",
                    "row",
                    "x",
                    "y",
                }
            ),
            set(),
        )
        for game in graph["games"]:
            _assert_digest(
                self,
                game,
                S2_GAME_GRAPH_DIGEST_PREFIX,
            )
        self.assertEqual(report["completed_levels"], 183)
        self.assertEqual(report["actions_executed"], 10733)
        self.assertEqual(
            report["role_selector_resolution_count"],
            3112,
        )
        self.assertEqual(
            report["selector_resolution_failure_count"],
            0,
        )
        self.assertEqual(report["error_count"], 0)
        self.assertFalse(report["literal_coordinate_stored"])
        self.assertFalse(report["literal_coordinate_decision_used"])

    def test_s2_executor_has_no_s1_graph_or_corpus_dependency(self) -> None:
        source = (
            PACKAGE_ROOT / "teacher" / "s2_graph_executor.py"
        ).read_text(encoding="utf-8")
        forbidden = (
            "FULL_SOLUTION_CORPUS",
            "human_replay_corpus",
            "s1_graph",
            "source_pointer",
            "replay_index",
            "action_data",
        )
        self.assertEqual(
            [token for token in forbidden if token in source],
            [],
        )

    def test_s3_global_graph_has_no_identity_routing_and_closes(
        self,
    ) -> None:
        graph = load_s3_policy_graph(
            TEACHER_ANALYSIS
            / "S3_GLOBAL_IDENTITY_FREE_POLICY_GRAPH.json"
        )
        report = load_s3_closure_report(
            TEACHER_ANALYSIS / "TEACHER_S3_CLOSURE_REPORT.json"
        )
        _assert_digest(
            self,
            graph,
            S3_POLICY_GRAPH_DIGEST_PREFIX,
        )
        _assert_digest(
            self,
            report,
            S3_CLOSURE_REPORT_DIGEST_PREFIX,
        )

        self.assertEqual(graph["environment_count"], 25)
        self.assertEqual(graph["level_count"], 183)
        self.assertEqual(graph["policy_partition_count"], 1)
        self.assertEqual(graph["identity_routing_key_count"], 0)
        self.assertEqual(graph["explicit_identity_literal_count"], 0)
        self.assertEqual(
            graph["source_transition_witness_count"],
            10733,
        )
        self.assertEqual(graph["state_node_count"], 10758)
        self.assertEqual(graph["edge_count"], 10733)
        self.assertEqual(graph["branch_node_count"], 0)
        self.assertEqual(graph["nondeterministic_action_count"], 0)
        self.assertEqual(graph["role_selector_witness_count"], 3112)
        self.assertEqual(identity_literal_values(graph), set())
        self.assertEqual(
            s3_all_mapping_keys(graph).intersection(
                {
                    "environment_id",
                    "game_class",
                    "game_id",
                    "games",
                    "level_id",
                    "levels_completed",
                    "target_levels",
                    "task_id",
                }
            ),
            set(),
        )
        self.assertEqual(report["completed_levels"], 183)
        self.assertEqual(report["actions_executed"], 10733)
        self.assertEqual(report["identity_routing_decision_count"], 0)
        self.assertEqual(report["policy_partition_count"], 1)
        self.assertFalse(
            report["action_selection_receives_environment_identity"]
        )
        self.assertFalse(
            report["decision_uses_task_game_level_identity"]
        )
        self.assertFalse(report["decision_uses_level_progress_counter"])
        self.assertEqual(report["error_count"], 0)

    def test_s3_action_selection_has_no_identity_or_s2_dependency(
        self,
    ) -> None:
        source = (
            PACKAGE_ROOT / "teacher" / "s3_graph_executor.py"
        ).read_text(encoding="utf-8")
        selection_source = source.split(
            "def execute_s3_global_policy",
            maxsplit=1,
        )[1].split(
            "def _discover_environment_ids",
            maxsplit=1,
        )[0]
        forbidden_selection = (
            "game_id",
            "task_id",
            "level_id",
            "frame.game_id",
            "game_graph",
            "levels_completed",
        )
        self.assertEqual(
            [
                token
                for token in forbidden_selection
                if token in selection_source
            ],
            [],
        )
        forbidden_module = (
            "FULL_SOLUTION_CORPUS",
            "human_replay_corpus",
            "s1_graph",
            "s2_graph",
            "source_pointer",
            "replay_index",
        )
        self.assertEqual(
            [token for token in forbidden_module if token in source],
            [],
        )

    def test_s4_graph_has_no_source_or_hidden_state_and_closes(
        self,
    ) -> None:
        graph = load_s4_policy_graph(
            TEACHER_ANALYSIS
            / "S4_SOURCE_HIDDEN_FREE_POLICY_GRAPH.json"
        )
        report = load_s4_closure_report(
            TEACHER_ANALYSIS / "TEACHER_S4_CLOSURE_REPORT.json"
        )
        _assert_digest(
            self,
            graph,
            S4_POLICY_GRAPH_DIGEST_PREFIX,
        )
        _assert_digest(
            self,
            report,
            S4_CLOSURE_REPORT_DIGEST_PREFIX,
        )

        self.assertEqual(graph["environment_count"], 25)
        self.assertEqual(graph["level_count"], 183)
        self.assertEqual(graph["state_node_count"], 10758)
        self.assertEqual(graph["edge_count"], 10733)
        self.assertEqual(graph["branch_node_count"], 0)
        self.assertEqual(graph["merged_state_node_count"], 0)
        self.assertEqual(graph["nondeterministic_action_count"], 0)
        self.assertEqual(graph["role_selector_witness_count"], 3112)
        self.assertEqual(graph["policy_partition_count"], 1)
        self.assertEqual(graph["identity_routing_key_count"], 0)
        self.assertEqual(graph["source_hidden_decision_key_count"], 0)
        self.assertEqual(
            graph["target_environment_source_or_hidden_read_count"],
            0,
        )
        self.assertEqual(s4_identity_literal_values(graph), set())
        self.assertEqual(
            s4_all_mapping_keys(graph).intersection(
                {
                    "current_level_data",
                    "custom_hidden_state",
                    "environment_id",
                    "game_class",
                    "game_id",
                    "hidden_state",
                    "level_id",
                    "levels_completed",
                    "source_fields",
                    "source_state_digest",
                    "task_id",
                }
            ),
            set(),
        )
        self.assertEqual(report["completed_levels"], 183)
        self.assertEqual(report["actions_executed"], 10733)
        self.assertEqual(
            report["strict_distance_decrease_count"],
            10733,
        )
        self.assertEqual(report["role_selector_resolution_count"], 3112)
        self.assertEqual(report["identity_routing_decision_count"], 0)
        self.assertEqual(report["source_hidden_decision_count"], 0)
        self.assertEqual(report["error_count"], 0)
        self.assertFalse(
            report["action_selection_receives_environment_wrapper"]
        )
        self.assertFalse(
            report["action_selection_receives_source_or_hidden_state"]
        )
        self.assertFalse(
            report["decision_uses_source_or_hidden_state"]
        )
        self.assertTrue(
            report["remaining_privilege_dependencies"][
                "answer_or_replay_graph"
            ]
        )
        self.assertFalse(
            report["remaining_privilege_dependencies"][
                "rendered_only"
            ]
        )

    def test_s4_action_selector_accepts_observation_inputs_only(
        self,
    ) -> None:
        self.assertEqual(
            set(inspect.signature(select_s4_policy_edge).parameters),
            {
                "frame",
                "action_effect_history",
                "nodes",
                "current_rendered_frame_digest",
            },
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
        audit_only_modules = {"p12_audit.py"}
        for path in PACKAGE_ROOT.rglob("*.py"):
            if (
                path.is_relative_to(teacher_root)
                or path.relative_to(PACKAGE_ROOT).as_posix()
                in audit_only_modules
            ):
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

        s1_adapter = _json(
            TEACHER_ANALYSIS / "TEACHER_S1_ORACLE_ADAPTER_REPORT.json"
        )
        s1_oracle = _json(
            TEACHER_ANALYSIS / "TEACHER_S1_LOCAL_SCORE_ORACLE.json"
        )
        _assert_digest(
            self,
            s1_adapter,
            S1_SCORE_ADAPTER_DIGEST_PREFIX,
        )
        s1_current = s1_oracle["current_local_result"]
        self.assertEqual(s1_current["completed_levels"], 183)
        self.assertEqual(
            s1_current["completion_rate_percent"],
            100.0,
        )
        self.assertEqual(
            s1_current["official_rhae_score_percent"],
            99.619936696,
        )
        self.assertEqual(s1_current["error_count"], 0)
        self.assertEqual(
            Decimal(
                str(s1_current["official_rhae_score_percent"])
            )
            - Decimal(str(current["official_rhae_score_percent"])),
            Decimal("0.173050539"),
        )
        self.assertEqual(
            oracle["source"]["sample_zip_sha256"],
            "c72400a32db5e48da9014baf893b48016b300e9a6a77bd5d"
            "505de2b1ec61d645",
        )
        self.assertEqual(
            s1_oracle["source"]["sample_zip_sha256"],
            oracle["source"]["sample_zip_sha256"],
        )
        self.assertEqual(
            {
                tuple(report["instruction_body_versions"])
                for report in s1_adapter["reports"]
            },
            {("teacher-s1-graph-v2",)},
        )
        self.assertFalse(
            s1_current["evaluation_provenance"][
                "architecture_evidence_eligible"
            ]
        )

        s2_adapter = _json(
            TEACHER_ANALYSIS / "TEACHER_S2_ORACLE_ADAPTER_REPORT.json"
        )
        s2_oracle = _json(
            TEACHER_ANALYSIS / "TEACHER_S2_LOCAL_SCORE_ORACLE.json"
        )
        _assert_digest(
            self,
            s2_adapter,
            S2_SCORE_ADAPTER_DIGEST_PREFIX,
        )
        s2_current = s2_oracle["current_local_result"]
        self.assertEqual(s2_current["completed_levels"], 183)
        self.assertEqual(
            s2_current["completion_rate_percent"],
            100.0,
        )
        self.assertEqual(
            s2_current["official_rhae_score_percent"],
            99.619936696,
        )
        self.assertEqual(
            s2_current["official_rhae_score_percent"],
            s1_current["official_rhae_score_percent"],
        )
        self.assertEqual(s2_current["error_count"], 0)
        self.assertEqual(
            s2_oracle["source"]["sample_zip_sha256"],
            s1_oracle["source"]["sample_zip_sha256"],
        )
        self.assertEqual(
            {
                tuple(report["instruction_body_versions"])
                for report in s2_adapter["reports"]
            },
            {("teacher-s2-role-relative-graph-v1",)},
        )
        self.assertFalse(
            s2_current["evaluation_provenance"][
                "architecture_evidence_eligible"
            ]
        )

        s3_adapter = _json(
            TEACHER_ANALYSIS / "TEACHER_S3_ORACLE_ADAPTER_REPORT.json"
        )
        s3_oracle = _json(
            TEACHER_ANALYSIS / "TEACHER_S3_LOCAL_SCORE_ORACLE.json"
        )
        _assert_digest(
            self,
            s3_adapter,
            S3_SCORE_ADAPTER_DIGEST_PREFIX,
        )
        s3_current = s3_oracle["current_local_result"]
        self.assertEqual(s3_current["completed_levels"], 183)
        self.assertEqual(
            s3_current["completion_rate_percent"],
            100.0,
        )
        self.assertEqual(
            s3_current["official_rhae_score_percent"],
            99.619936696,
        )
        self.assertEqual(
            s3_current["official_rhae_score_percent"],
            s2_current["official_rhae_score_percent"],
        )
        self.assertEqual(s3_current["error_count"], 0)
        self.assertEqual(
            s3_oracle["source"]["sample_zip_sha256"],
            s2_oracle["source"]["sample_zip_sha256"],
        )
        self.assertEqual(
            {
                tuple(report["instruction_body_versions"])
                for report in s3_adapter["reports"]
            },
            {("teacher-s3-global-identity-free-graph-v1",)},
        )
        self.assertFalse(
            s3_current["evaluation_provenance"][
                "architecture_evidence_eligible"
            ]
        )

        s4_adapter = _json(
            TEACHER_ANALYSIS / "TEACHER_S4_ORACLE_ADAPTER_REPORT.json"
        )
        s4_oracle = _json(
            TEACHER_ANALYSIS / "TEACHER_S4_LOCAL_SCORE_ORACLE.json"
        )
        _assert_digest(
            self,
            s4_adapter,
            S4_SCORE_ADAPTER_DIGEST_PREFIX,
        )
        s4_current = s4_oracle["current_local_result"]
        self.assertEqual(s4_current["completed_levels"], 183)
        self.assertEqual(
            s4_current["completion_rate_percent"],
            100.0,
        )
        self.assertEqual(
            s4_current["official_rhae_score_percent"],
            99.619936696,
        )
        self.assertEqual(
            s4_current["official_rhae_score_percent"],
            s3_current["official_rhae_score_percent"],
        )
        self.assertEqual(s4_current["error_count"], 0)
        self.assertEqual(
            s4_oracle["source"]["sample_zip_sha256"],
            s3_oracle["source"]["sample_zip_sha256"],
        )
        self.assertEqual(
            {
                tuple(report["instruction_body_versions"])
                for report in s4_adapter["reports"]
            },
            {("teacher-s4-source-hidden-free-graph-v1",)},
        )
        self.assertFalse(
            s4_current["evaluation_provenance"][
                "architecture_evidence_eligible"
            ]
        )


if __name__ == "__main__":
    unittest.main()
