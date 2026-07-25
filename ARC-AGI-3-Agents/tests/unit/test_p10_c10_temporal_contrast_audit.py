from __future__ import annotations

import copy
import unittest

from arc3_agi_agent.cross_cutting_transition import C2_C3_PROBE_FORMAT
from arc3_agi_agent.schema import digest_object
from p10_c10_temporal_contrast_audit import (
    build_c10_temporal_contrast_audit,
)


def _record(
    *,
    ordinal: int,
    action: int,
    effects: list[str],
    boundary: str,
) -> dict[str, object]:
    return {
        "ordinal": ordinal,
        "source_structure_class": "structure-class:shared",
        "target_structure_class": "structure-class:shared",
        "action_prototype": f"prototype:{action}",
        "action_class": f"action:{action}",
        "effect_classes": effects,
        "changed_cell_milli": (
            0 if effects == ["NO_VISIBLE_CHANGE"] else 10
        ),
        "component_added": int("COMPONENT_APPEAR" in effects),
        "component_removed": 0,
        "component_moved": 0,
        "terminal_state": (
            "GAME_OVER" if boundary == "HAZARD" else "NOT_FINISHED"
        ),
        "progress_observed": False,
        "observed_boundary": boundary,
        "predicted_boundary": boundary,
        "contrast_role": (
            "HAZARD" if boundary == "HAZARD" else "NEGATIVE"
        ),
        "reobserve_obligation": (
            "SUSPEND_AND_REQUEST_ROLLBACK"
            if boundary == "HAZARD"
            else (
                "WAIT_REOBSERVE_OR_REPLAN"
                if boundary == "NO_VISIBLE_COMMIT"
                else "REOBSERVE_BEFORE_CONTINUATION"
            )
        ),
        "transition_digest": f"visible-transition:{ordinal}",
    }


def _game_report(game_id: str, *, ambiguous: bool) -> dict[str, object]:
    if ambiguous:
        records = [
            _record(
                ordinal=1,
                action=1,
                effects=["NO_VISIBLE_CHANGE"],
                boundary="NO_VISIBLE_COMMIT",
            ),
            _record(
                ordinal=2,
                action=2,
                effects=["NO_VISIBLE_CHANGE"],
                boundary="NO_VISIBLE_COMMIT",
            ),
            _record(
                ordinal=3,
                action=1,
                effects=["COMPONENT_APPEAR", "VISIBLE_STATE_CHANGE"],
                boundary="TRANSITION_NO_COMMIT",
            ),
            _record(
                ordinal=4,
                action=2,
                effects=["IRREVERSIBLE_HAZARD", "NO_VISIBLE_CHANGE"],
                boundary="HAZARD",
            ),
            _record(
                ordinal=5,
                action=1,
                effects=["NO_VISIBLE_CHANGE"],
                boundary="NO_VISIBLE_COMMIT",
            ),
            _record(
                ordinal=6,
                action=2,
                effects=["NO_VISIBLE_CHANGE"],
                boundary="NO_VISIBLE_COMMIT",
            ),
            _record(
                ordinal=7,
                action=1,
                effects=["COMPONENT_APPEAR", "VISIBLE_STATE_CHANGE"],
                boundary="TRANSITION_NO_COMMIT",
            ),
            _record(
                ordinal=8,
                action=2,
                effects=["IRREVERSIBLE_HAZARD", "NO_VISIBLE_CHANGE"],
                boundary="HAZARD",
            ),
        ]
        sources: tuple[str, ...] = (
            "a",
            "same",
            "b",
            "same",
            "c",
            "same",
            "d",
            "same",
        )
    else:
        records = [
            _record(
                ordinal=1,
                action=1,
                effects=["NO_VISIBLE_CHANGE"],
                boundary="NO_VISIBLE_COMMIT",
            )
        ]
        sources = ("unique",)
    emitted_steps = [
        [
            {
                "action_id": int(
                    str(record["action_class"]).split(":")[-1]
                ),
                "visual_source_signature": f"visual-state:{source}",
            }
        ]
        for source, record in zip(sources, records, strict=True)
    ]
    return {
        "game_id": game_id,
        "actions": len(records),
        "emitted_steps": emitted_steps,
        "development_transition_probe": {
            "format": C2_C3_PROBE_FORMAT,
            "candidate_tier": "LOCAL_PROBE",
            "runtime_decision_use": "FORBIDDEN",
            "action_selection_influence": False,
            "memory_write_authority": False,
            "external_emit_authority": False,
            "runtime_p_promotion_authority": False,
            "observation_count": len(records),
            "fault_count": 0,
            "model_overflow_count": 0,
            "context_overflow_count": 0,
            "contrast_overflow_count": 0,
            "contrast_records": records,
        },
    }


def _raw_report() -> dict[str, object]:
    reports = [
        _game_report(
            f"g{index:02d}-sample",
            ambiguous=index < 3,
        )
        for index in range(25)
    ]
    return {
        "phase": "P10",
        "operation_mode": "offline",
        "environment_count": 25,
        "error_count": 0,
        "errors": [],
        "max_actions": 450,
        "instruction_lifecycle": "active",
        "instruction_variant": "hybrid",
        "reports": reports,
    }


class P10C10TemporalContrastAuditTests(unittest.TestCase):
    def test_cross_game_causal_context_reopens_probe_only(self) -> None:
        audit = build_c10_temporal_contrast_audit(
            raw_report=_raw_report(),
            raw_report_sha256="raw",
        )

        contract_checks = audit["contract_checks"]
        evidence_checks = audit["evidence_checks"]
        summary = audit["summary"]
        judgment = audit["hds_judgment"]
        assert isinstance(contract_checks, dict)
        assert isinstance(evidence_checks, dict)
        assert isinstance(summary, dict)
        assert isinstance(judgment, dict)
        self.assertTrue(all(contract_checks.values()))
        self.assertTrue(all(evidence_checks.values()))
        predictive_checks = audit["predictive_checks"]
        assert isinstance(predictive_checks, dict)
        self.assertTrue(all(predictive_checks.values()))
        self.assertEqual(summary["ambiguous_game_count"], 3)
        self.assertEqual(summary["separable_game_count"], 3)
        self.assertEqual(
            summary["one_step_separable_group_count"],
            3,
        )
        self.assertGreater(
            summary["prequential_ambiguous_accuracy_delta_milli"],
            0,
        )
        self.assertEqual(
            summary["held_out_positive_game_count"],
            2,
        )
        self.assertEqual(audit["candidate_tier"], "CLUSTER_STABLE")
        self.assertEqual(judgment["c10_reopen_probe_status"], "PASS")
        self.assertEqual(judgment["cluster_stable_status"], "PASS")
        self.assertEqual(judgment["composable_status"], "HOLD")
        self.assertFalse(judgment["runtime_p_compile_authorized"])
        self.assertFalse(judgment["runtime_p_promotion_authorized"])
        body = copy.deepcopy(audit)
        claimed = body.pop("content_digest")
        self.assertEqual(
            claimed,
            "arc3_c10_temporal_causal_contrast_audit:"
            + digest_object(body),
        )

    def test_shadow_action_influence_fails_closed(self) -> None:
        raw = _raw_report()
        reports = raw["reports"]
        assert isinstance(reports, list)
        probe = reports[0]["development_transition_probe"]
        assert isinstance(probe, dict)
        probe["action_selection_influence"] = True

        with self.assertRaisesRegex(
            ValueError,
            "action_influence_absent",
        ):
            build_c10_temporal_contrast_audit(
                raw_report=raw,
                raw_report_sha256="raw",
            )

    def test_static_separation_without_prior_prediction_stays_local(
        self,
    ) -> None:
        raw = _raw_report()
        reports = raw["reports"]
        assert isinstance(reports, list)
        for report in reports[:3]:
            probe = report["development_transition_probe"]
            assert isinstance(probe, dict)
            records = probe["contrast_records"]
            steps = report["emitted_steps"]
            assert isinstance(records, list)
            assert isinstance(steps, list)
            del records[4:]
            del steps[4:]
            probe["observation_count"] = 4
            report["actions"] = 4

        audit = build_c10_temporal_contrast_audit(
            raw_report=raw,
            raw_report_sha256="raw",
        )

        self.assertEqual(audit["candidate_tier"], "LOCAL_PROBE")
        judgment = audit["hds_judgment"]
        assert isinstance(judgment, dict)
        self.assertEqual(judgment["local_probe_status"], "PASS")
        self.assertEqual(judgment["cluster_stable_status"], "HOLD")
        predictive_checks = audit["predictive_checks"]
        assert isinstance(predictive_checks, dict)
        self.assertFalse(all(predictive_checks.values()))


if __name__ == "__main__":
    unittest.main()
