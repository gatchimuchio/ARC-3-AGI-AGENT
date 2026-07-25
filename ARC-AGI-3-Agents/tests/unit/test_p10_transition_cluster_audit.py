from __future__ import annotations

import copy
import unittest

from arc3_agi_agent.cross_cutting_transition import C2_C3_PROBE_FORMAT
from arc3_agi_agent.p10_evidence import build_p10_compact_run_evidence
from arc3_agi_agent.p10_transition_cluster_audit import (
    build_c2_c3_cluster_audit,
)
from arc3_agi_agent.schema import digest_object


def _contrast_record(
    *,
    ordinal: int,
    game_index: int,
    boundary: str,
) -> dict[str, object]:
    action = f"action:{((game_index + ordinal) % 3) + 1}"
    if boundary == "COMMIT":
        effects = [
            "VISIBLE_STATE_CHANGE",
            "LOCAL_PIXEL_DELTA",
            "PROGRESS_BOUNDARY",
        ]
        terminal = "NOT_FINISHED"
        progress = True
        role = "POSITIVE"
        obligation = "REOBSERVE_COMMIT_STATE"
    elif boundary == "HAZARD":
        effects = [
            "VISIBLE_STATE_CHANGE",
            "LOCAL_PIXEL_DELTA",
            "IRREVERSIBLE_HAZARD",
        ]
        terminal = "GAME_OVER"
        progress = False
        role = "HAZARD"
        obligation = "SUSPEND_AND_REQUEST_ROLLBACK"
    elif boundary == "TRANSITION_NO_COMMIT":
        redraw = (
            "REGIONAL_REDRAW"
            if game_index % 2
            else "GLOBAL_REDRAW"
        )
        effects = [
            "VISIBLE_STATE_CHANGE",
            "COMPONENT_MOTION",
            redraw,
        ]
        terminal = "NOT_FINISHED"
        progress = False
        role = "NEGATIVE"
        obligation = "REOBSERVE_BEFORE_CONTINUATION"
    else:
        effects = ["NO_VISIBLE_CHANGE"]
        terminal = "NOT_FINISHED"
        progress = False
        role = "NEGATIVE"
        obligation = "WAIT_REOBSERVE_OR_REPLAN"
    return {
        "ordinal": ordinal,
        "source_structure_class": (
            f"structure-class:{game_index:02d}{ordinal:02d}"
        ),
        "target_structure_class": (
            f"structure-class:{game_index:02d}{ordinal + 1:02d}"
        ),
        "action_prototype": action.replace("action:", "prototype:"),
        "action_class": action,
        "effect_classes": effects,
        "changed_cell_milli": (
            0 if boundary == "NO_VISIBLE_COMMIT" else 100
        ),
        "component_added": 0,
        "component_removed": 0,
        "component_moved": (
            1 if boundary == "TRANSITION_NO_COMMIT" else 0
        ),
        "terminal_state": terminal,
        "progress_observed": progress,
        "observed_boundary": boundary,
        "predicted_boundary": boundary,
        "contrast_role": role,
        "reobserve_obligation": obligation,
        "transition_digest": (
            f"visible-transition:{game_index:02d}{ordinal:02d}"
        ),
    }


def _report() -> dict[str, object]:
    game_ids = [f"g{index:02d}-sample" for index in range(25)]
    reports: list[dict[str, object]] = []
    boundaries = (
        "COMMIT",
        "HAZARD",
        "TRANSITION_NO_COMMIT",
        "NO_VISIBLE_COMMIT",
    )
    for game_index, game_id in enumerate(game_ids):
        records = [
            _contrast_record(
                ordinal=ordinal,
                game_index=game_index,
                boundary=boundary,
            )
            for ordinal, boundary in enumerate(boundaries, start=1)
        ]
        reports.append(
            {
                "game_id": game_id,
                "actions": 4,
                "recoveries": 0,
                "search_resets": 0,
                "levels_completed": 0,
                "win_levels": 1,
                "terminal_state": "NOT_FINISHED",
                "final_status": "PASS",
                "complete": False,
                "max_action_exhausted": False,
                "memory_version": 4,
                "memory_influenced_cycle_count": 3,
                "visual_operator_version": (
                    "arc3-p10-visual-operator-v14"
                ),
                "instruction_body_formats": ["p10"],
                "instruction_body_versions": ["v1"],
                "instruction_body_digests": ["body"],
                "instruction_query_digests": ["query"],
                "decision_statuses": ["ACCEPT"],
                "verification_statuses": ["PASS"],
                "emitted_steps": [[{"action_id": 1}]],
                "emitted_provenance": [["synthetic"]],
                "emitted_level_counts": [0],
                "trace_digests": ["trace"],
                "trace_events": [[]],
                "rollback_decision_ids": [],
                "rollback_memory_versions": [],
                "failure_payload_digests": [],
                "search_reset_decision_ids": [],
                "search_reset_memory_versions": [],
                "search_reset_payload_digests": [],
                "search_reset_evidence_signatures": [],
                "development_transition_probe": {
                    "format": C2_C3_PROBE_FORMAT,
                    "capability_ids": [
                        "C2_visible_effect_transition_model",
                        "C3_commit_boundary_predictor",
                    ],
                    "candidate_tier": "LOCAL_PROBE",
                    "runtime_decision_use": "FORBIDDEN",
                    "action_selection_influence": False,
                    "memory_write_authority": False,
                    "external_emit_authority": False,
                    "runtime_p_promotion_authority": False,
                    "observation_count": 4,
                    "fault_count": 0,
                    "model_overflow_count": 0,
                    "context_overflow_count": 0,
                    "contrast_overflow_count": 0,
                    "contrast_records": records,
                },
            }
        )
    condition_body = {
        "schema_version": "arc3-p10-batch-conditions-v1",
        "operation_mode": "offline",
        "instruction_lifecycle": "active",
        "instruction_variant": "hybrid",
        "max_actions": 450,
        "game_ids": game_ids,
    }
    conditions = {
        **condition_body,
        "conditions_digest": digest_object(condition_body),
    }
    return {
        "phase": "P10",
        "operation_mode": "offline",
        "environment_count": 25,
        "completed_count": 25,
        "complete_game_count": 0,
        "completed_levels": 0,
        "total_levels": 25,
        "all_complete": False,
        "error_count": 0,
        "max_actions": 450,
        "instruction_variant": "hybrid",
        "instruction_lifecycle": "active",
        "reports": reports,
        "errors": [],
        "checkpointing": {
            "conditions": conditions,
        },
    }


class P10TransitionClusterAuditTests(unittest.TestCase):
    def test_cross_context_contrasts_reach_cluster_stable_only(self) -> None:
        raw = _report()
        compact = build_p10_compact_run_evidence(raw)

        audit = build_c2_c3_cluster_audit(
            raw_report=raw,
            raw_report_sha256="raw",
            compact_evidence=compact,
            compact_evidence_sha256="compact",
        )

        self.assertTrue(all(audit["checks"].values()))
        self.assertEqual(audit["candidate_tier"], "CLUSTER_STABLE")
        self.assertEqual(
            audit["summary"]["contrast_record_count"],
            100,
        )
        judgment = audit["hds_judgment"]
        self.assertEqual(judgment["cluster_stable_status"], "PASS")
        self.assertEqual(judgment["composable_status"], "HOLD")
        self.assertFalse(judgment["runtime_p_compile_authorized"])
        self.assertFalse(judgment["runtime_p_promotion_authorized"])
        body = copy.deepcopy(audit)
        claimed = body.pop("content_digest")
        self.assertEqual(
            claimed,
            "arc3_c2_c3_cluster_stable_audit:" + digest_object(body),
        )

    def test_semantic_prediction_drift_fails_closed(self) -> None:
        raw = _report()
        reports = raw["reports"]
        assert isinstance(reports, list)
        probe = reports[0]["development_transition_probe"]
        assert isinstance(probe, dict)
        records = probe["contrast_records"]
        assert isinstance(records, list)
        records[0]["predicted_boundary"] = "HAZARD"
        compact = build_p10_compact_run_evidence(raw)

        with self.assertRaisesRegex(
            ValueError,
            "all_record_semantics_recomputed",
        ):
            build_c2_c3_cluster_audit(
                raw_report=raw,
                raw_report_sha256="raw",
                compact_evidence=compact,
                compact_evidence_sha256="compact",
            )


if __name__ == "__main__":
    unittest.main()
