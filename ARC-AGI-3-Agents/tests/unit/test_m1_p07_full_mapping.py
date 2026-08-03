from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from types import ModuleType
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
BUILDER_PATH = REPOSITORY_ROOT / "scripts" / "build_rev5_1_full_mapping.py"
BUILDER_SPEC = importlib.util.spec_from_file_location(
    "arc3_rev5_1_full_mapping_test_target",
    BUILDER_PATH,
)
assert BUILDER_SPEC is not None and BUILDER_SPEC.loader is not None
BUILDER: ModuleType = importlib.util.module_from_spec(BUILDER_SPEC)
sys.modules[BUILDER_SPEC.name] = BUILDER
BUILDER_SPEC.loader.exec_module(BUILDER)


def _artifact() -> dict[str, Any]:
    value = BUILDER.build(REPOSITORY_ROOT)
    assert isinstance(value, dict)
    return value


def test_every_canonical_action_has_one_compressed_segment() -> None:
    artifact = _artifact()
    coverage = artifact["coverage_summary"]

    assert artifact["status"] == "M1_P07_COMPLETE"
    assert coverage["game_count"] == 25
    assert coverage["level_count"] == 183
    assert coverage["canonical_raw_action_count"] == 11_574
    assert coverage["mapped_raw_action_count"] == 11_574
    assert coverage["unmapped_raw_action_count"] == 0
    assert coverage["overlapping_raw_action_count"] == 0
    assert coverage["mechanism_segment_count"] == 521
    assert coverage["mapped_mechanism_segment_count"] == 521
    assert coverage["unmapped_mechanism_segment_count"] == 0
    assert coverage["action_category_counts"] == {
        "COMMIT_BOUNDARY": 183,
        "RECOVERY_AND_REPLAN": 64,
        "RELATION_BOUND_DISCRETE_TRANSITION": 8_172,
        "ROLE_BOUND_POINTER_INTERACTION": 2_968,
        "TEMPORAL_SETTLE_OR_NO_EFFECT": 187,
    }

    mapped_total = 0
    for game in artifact["game_mappings"]:
        assigned_steps: set[int] = set()
        for level in game["levels"]:
            level_steps: set[int] = set()
            for segment in level["segments"]:
                assert segment["mapping"]["target_id"]
                assert segment["mapping"]["asset_class"] in {
                    "CAPABILITY_FAMILY",
                    "DOMAIN_LOCAL_RESIDUE",
                }
                span_count = 0
                for start, end, count in segment["raw_step_spans"]:
                    assert count == end - start + 1
                    steps = set(range(start, end + 1))
                    assert not steps.intersection(level_steps)
                    level_steps.update(steps)
                    span_count += count
                assert span_count == segment["raw_action_count"]
            trace = level["source_trace_range"]
            expected = set(
                range(
                    trace["start_action_exclusive"] + 1,
                    trace["end_action_inclusive"] + 1,
                )
            )
            assert level_steps == expected
            assert not level_steps.intersection(assigned_steps)
            assigned_steps.update(level_steps)
        assert len(assigned_steps) == game["raw_action_count"]
        assert len(assigned_steps) == game["mapped_raw_action_count"]
        mapped_total += len(assigned_steps)
    assert mapped_total == 11_574


def test_asset_classification_preserves_promotion_boundary() -> None:
    artifact = _artifact()
    families = {
        item["family_id"]: item for item in artifact["capability_family_registry"]
    }

    assert set(families) == {
        "RELATION_BOUND_ACTION_EMISSION",
        "RESOURCE_AWARE_PLAN_AND_ROLLBACK",
        "TEMPORAL_SETTLE_AND_ATTRIBUTION",
    }
    assert families["RELATION_BOUND_ACTION_EMISSION"]["asset_state"] == ("ACTIVE_DEV")
    assert families["RESOURCE_AWARE_PLAN_AND_ROLLBACK"]["asset_state"] == (
        "PROBATION_DEV"
    )
    assert families["TEMPORAL_SETTLE_AND_ATTRIBUTION"]["asset_state"] == (
        "PROBATION_DEV"
    )
    assert all(
        item["runtime_execute_eligibility"] is False for item in families.values()
    )

    residues = artifact["domain_local_residue_registry"]
    assert len(residues) == 46
    assert all(
        residue["asset_state"] == "DOMAIN_LOCAL_RESIDUE"
        and residue["runtime_execute_eligibility"] is False
        and residue["runtime_selector"] == "NONE"
        and residue["applicability_status"]
        == "UNCOMPILED_CURRENT_OBSERVATION_PREDICATE_REQUIRED"
        for residue in residues
    )
    boundary = artifact["boundary_audit"]
    assert boundary["identity_action_router_added"] is False
    assert boundary["fixed_trajectory_runtime_path_added"] is False
    assert boundary["teacher_artifact_runtime_import_added"] is False
    assert boundary["domain_local_residue_runtime_selector_count"] == 0
    assert boundary["product_completion_claim"] is False
    assert boundary["genericity_claim"] is False


def test_all_primary_analysis_artifacts_are_consumed() -> None:
    artifact = _artifact()
    input_contract = artifact["input_contract"]
    primary = input_contract["primary_analysis_artifacts"]
    audit = artifact["primary_analysis_consumption_audit"]

    assert len(primary) == 8
    assert input_contract["unused_primary_analysis_artifact_ids"] == []
    assert all(
        item["consumption_status"] == "CONSUMED"
        and item["mapping_targets"]
        and item["content_digest"]
        for item in primary
    )
    assert audit == {
        "primary_analysis_artifact_count": 8,
        "consumed_primary_analysis_artifact_count": 8,
        "unused_primary_analysis_artifact_count": 0,
        "all_have_runtime_or_development_mapping": True,
    }


def test_mapping_is_bound_to_one_noncomplete_active_product_bundle() -> None:
    artifact = _artifact()
    bundle = artifact["active_development_product_bundle"]
    regression = artifact["observed_product_regression"]
    exit_audit = artifact["exit_audit"]

    assert bundle["count"] == 1
    assert bundle["product_id"] == "ARC3CompletionAgent"
    assert bundle["active_dev_mechanism_family_ids"] == [
        "RELATION_BOUND_ACTION_EMISSION"
    ]
    assert regression["individual_game_win_count"] == 25
    assert regression["individual_level_completion_count"] == 183
    assert regression["runtime_action_count"] == 10_733
    assert regression["canonical_teacher_action_count"] == 11_574
    assert regression["action_count_delta"] == 841
    assert exit_audit["active_development_product_bundle_count"] == 1
    assert exit_audit["M1_complete"] is True
    assert artifact["boundary_audit"]["product_completion_claim"] is False


def test_checked_artifact_is_byte_identical_to_compiler_output() -> None:
    output = REPOSITORY_ROOT / BUILDER.OUTPUT_PATH
    assert output.read_bytes() == BUILDER.output_bytes(REPOSITORY_ROOT)


def test_classification_priority_keeps_commit_and_reset_unambiguous() -> None:
    assert (
        BUILDER._category(
            primitive="RESET_LEVEL",
            source_step=10,
            commit_source_step=10,
            frame_unchanged=True,
        )
        == "COMMIT_BOUNDARY"
    )
    assert (
        BUILDER._category(
            primitive="RESET_LEVEL",
            source_step=9,
            commit_source_step=10,
            frame_unchanged=True,
        )
        == "RECOVERY_AND_REPLAN"
    )
    assert (
        BUILDER._category(
            primitive="INTERACT_AT_RENDERED_COORDINATE",
            source_step=9,
            commit_source_step=10,
            frame_unchanged=True,
        )
        == "TEMPORAL_SETTLE_OR_NO_EFFECT"
    )
    assert (
        BUILDER._category(
            primitive="INTERACT_AT_RENDERED_COORDINATE",
            source_step=9,
            commit_source_step=10,
            frame_unchanged=False,
        )
        == "ROLE_BOUND_POINTER_INTERACTION"
    )
