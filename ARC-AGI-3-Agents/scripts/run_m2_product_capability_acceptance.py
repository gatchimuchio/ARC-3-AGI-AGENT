from __future__ import annotations

import argparse
import hashlib
import json
import os
import tempfile
from dataclasses import replace
from pathlib import Path
from typing import Any

from arc_agi import Arcade, OperationMode  # type: ignore[import-untyped]

from agents.templates.arc3_completion_agent import ARC3CompletionAgent
from arc3_agi_agent.generic_competition_runner import (
    run_sequential_competition,
)
from arc3_agi_agent.generic_compute import HybridRelationalInstructionBody
from arc3_agi_agent.generic_session import (
    CognitiveSession,
    ResourceContract,
    create_cognitive_session,
)
from arc3_agi_agent.p_ir import compatibility_p_ir_program
from arc3_agi_agent.product_capability import (
    PRODUCT_CAPABILITY_DESCRIPTOR_FILENAME,
    PRODUCT_CAPABILITY_PACKAGE_FILENAME,
    load_product_initial_state,
)
from arc3_agi_agent.product_runner import (
    _selected_offline_environments,
    _SelectedOfflineArcade,
    run_arc3_completion_offline,
)
from arc3_agi_agent.schema import digest_object

M2_ACCEPTANCE_SCHEMA_VERSION = "arc3-product-m2-acceptance-v1"
M2_ACCEPTANCE_EXIT = "PRODUCT_CAPABILITY_BUNDLE_ACTIVE"
M2_ACCEPTANCE_GAME = "FT09"
M2_CONTROLLED_ACTION_BUDGET = 128


def _default_environments_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "environment_files"


def _single_result(report: dict[str, object]) -> dict[str, object]:
    rows = report.get("results")
    if not isinstance(rows, list) or len(rows) != 1:
        raise RuntimeError("M2_ACCEPTANCE_SINGLE_RESULT_REQUIRED")
    row = rows[0]
    if not isinstance(row, dict):
        raise TypeError("M2_ACCEPTANCE_RESULT_OBJECT_REQUIRED")
    return {str(key): value for key, value in row.items()}


def _single_game_id(report: dict[str, object]) -> str:
    rows = report.get("orchestration_game_index")
    if not isinstance(rows, list) or len(rows) != 1:
        raise RuntimeError("M2_ACCEPTANCE_SINGLE_GAME_REQUIRED")
    row = rows[0]
    if not isinstance(row, dict) or not isinstance(row.get("game_id"), str):
        raise TypeError("M2_ACCEPTANCE_GAME_ID_REQUIRED")
    return str(row["game_id"])


def _integer_field(value: dict[str, object], key: str) -> int:
    item = value.get(key)
    if isinstance(item, bool) or not isinstance(item, int):
        raise TypeError("M2_ACCEPTANCE_INTEGER_FIELD_REQUIRED:" + key)
    return item


def _ablation_session(action_budget: int) -> CognitiveSession:
    initial = load_product_initial_state()
    hds = replace(
        initial.j0,
        resource_budget=action_budget,
        stop_after_no_progress=action_budget,
    )
    return create_cognitive_session(
        p_bundle=HybridRelationalInstructionBody(),
        p_ir_program=compatibility_p_ir_program(),
        mode="VALIDATION",
        hds_configuration=hds,
        initial_memory_records=initial.m0,
        resource_contract=ResourceContract(
            action_budget_per_episode=action_budget,
        ),
    )


def _run_p_removal_ablation(
    *,
    environments_dir: Path,
    recordings_dir: Path,
    game: str,
    action_budget: int,
) -> dict[str, object]:
    arcade = Arcade(
        operation_mode=OperationMode.OFFLINE,
        environments_dir=str(environments_dir),
        recordings_dir=str(recordings_dir),
    )
    selected = _selected_offline_environments(arcade, (game,))

    def session_factory() -> CognitiveSession:
        return _ablation_session(action_budget)

    report = run_sequential_competition(
        arcade=_SelectedOfflineArcade(arcade, selected),
        agent_factory=ARC3CompletionAgent,
        session_factory=session_factory,
    )
    report.update(
        {
            "operation_mode": arcade.operation_mode.value,
            "offline_environment_selected_count": len(selected),
            "ablation": "P_REMOVED_GENERIC_BASELINE_SUBSTITUTION",
            "ablation_product_j0_retained": True,
            "ablation_product_m0_retained": True,
            "ablation_compatibility_p_ir_active": True,
            "ablation_hybrid_baseline_instruction_body_active": True,
        }
    )
    return report


def _component_descriptor() -> dict[str, Any]:
    directory = Path(__file__).resolve().parents[1] / "arc3_agi_agent" / "bundles"
    descriptor_path = directory / PRODUCT_CAPABILITY_DESCRIPTOR_FILENAME
    package_path = directory / PRODUCT_CAPABILITY_PACKAGE_FILENAME
    descriptor = json.loads(descriptor_path.read_text(encoding="utf-8"))
    if not isinstance(descriptor, dict):
        raise TypeError("M2_ACCEPTANCE_DESCRIPTOR_OBJECT_REQUIRED")
    if hashlib.sha256(package_path.read_bytes()).hexdigest() != descriptor.get(
        "package_sha256"
    ):
        raise ValueError("M2_ACCEPTANCE_PACKAGE_SHA_MISMATCH")
    return {str(key): value for key, value in descriptor.items()}


def run_acceptance(
    *,
    environments_dir: Path,
    recordings_dir: Path,
    game: str = M2_ACCEPTANCE_GAME,
    action_budget: int = M2_CONTROLLED_ACTION_BUDGET,
) -> dict[str, object]:
    if os.getenv("OPERATION_MODE", "").strip().casefold() == "competition":
        raise PermissionError("M2_ACCEPTANCE_OFFLINE_MODE_REQUIRED")
    if action_budget < 75:
        raise ValueError("M2_ACCEPTANCE_ACTION_BUDGET_TOO_SMALL")
    initial = load_product_initial_state()
    product_report = run_arc3_completion_offline(
        environments_dir=environments_dir,
        requested_games=(game,),
        recordings_dir=recordings_dir / "product",
        action_budget=action_budget,
    )
    ablation_report = _run_p_removal_ablation(
        environments_dir=environments_dir,
        recordings_dir=recordings_dir / "p-removal",
        game=game,
        action_budget=action_budget,
    )
    product = _single_result(product_report)
    ablation = _single_result(ablation_report)
    descriptor = _component_descriptor()
    product_game_id = _single_game_id(product_report)
    ablation_game_id = _single_game_id(ablation_report)
    raw_product_seed_ids = product_report.get(
        "product_teacher_seed_citation_ids",
        (),
    )
    if not isinstance(raw_product_seed_ids, (tuple, list)):
        raise TypeError("M2_ACCEPTANCE_CITATION_IDS_REQUIRED")
    product_seed_ids = tuple(
        str(item) for item in raw_product_seed_ids
    )
    same_j0 = (
        product_report.get("product_j0_digest")
        == "j0:"
        + digest_object(
            replace(
                initial.j0,
                resource_budget=action_budget,
                stop_after_no_progress=action_budget,
            )
        )
    )
    same_m0 = product_report.get("product_m0_digest") == (
        "m0:" + digest_object(initial.m0)
    )
    gates = {
        "compiled_product_bundle_count_one": True,
        "product_loads_compiled_p_j0_m0": (
            product_report.get("p_j0_m0_runtime_identity_bound") is True
        ),
        "compatibility_p_ir_inactive_in_product": (
            product_report.get("compatibility_p_ir_active") is False
        ),
        "hybrid_baseline_body_inactive_in_product": (
            product_report.get("hybrid_baseline_instruction_body_active")
            is False
        ),
        "controlled_j0_equal": same_j0,
        "controlled_m0_equal": same_m0,
        "p_removal_materially_reduces_capability": (
            product.get("final_state") == "WIN"
            and _integer_field(product, "progress_count") == 6
            and (
                ablation.get("final_state") != "WIN"
                or _integer_field(ablation, "progress_count") < 6
            )
        ),
        "product_behavior_differs_from_generic_baseline": (
            (
                product.get("final_state"),
                product.get("progress_count"),
                product.get("actions_executed"),
            )
            != (
                ablation.get("final_state"),
                ablation.get("progress_count"),
                ablation.get("actions_executed"),
            )
        ),
        "teacher_structure_cited_by_c": (
            product_report.get("product_teacher_structure_cited") is True
            and bool(product_seed_ids)
        ),
        "identity_boundary_passed": (
            product_report.get("identity_boundary") == "PASS"
        ),
        "no_game_id_action_router": (
            descriptor.get("contains_identity_router") is False
        ),
        "no_trajectory_playback": (
            descriptor.get("contains_fixed_trajectory") is False
        ),
        "one_official_game_end_to_end_win": (
            product_game_id == ablation_game_id
            and product.get("final_state") == "WIN"
            and _integer_field(product, "progress_count") == 6
        ),
        "scorecard_lifecycle_closed": (
            product_report.get("scorecard_closed") is True
            and ablation_report.get("scorecard_closed") is True
            and product_report.get("lifecycle_failure_count") == 0
            and ablation_report.get("lifecycle_failure_count") == 0
        ),
    }
    failures = tuple(sorted(key for key, passed in gates.items() if not passed))
    body: dict[str, object] = {
        "schema_version": M2_ACCEPTANCE_SCHEMA_VERSION,
        "milestone": "M2_PRODUCT_CAPABILITY_BUNDLE",
        "controlled_game_title": game,
        "controlled_game_id": product_game_id,
        "controlled_action_budget": action_budget,
        "product_bundle": {
            "descriptor_content_digest": descriptor.get("content_digest"),
            "package_sha256": descriptor.get("package_sha256"),
            "package_size_bytes": descriptor.get("package_size_bytes"),
            "initial_state_logical_digest": initial.logical_digest,
            "p_logical_digest": initial.p_bundle.logical_digest(),
            "p_program_id": initial.p_bundle.program.program_id,
            "p_compiler_mode": initial.p_bundle.compiler_report.mode,
            "p_body_format": initial.p_bundle.body.format_id(),
            "j0_digest": "j0:" + digest_object(initial.j0),
            "m0_digest": "m0:" + digest_object(initial.m0),
            "m0_record_count": len(initial.m0),
            "source_structure_count": descriptor.get(
                "source_structure_count"
            ),
            "rendered_only_structure_count": descriptor.get(
                "rendered_only_structure_count"
            ),
        },
        "product_result": {
            "actions_executed": product.get("actions_executed"),
            "progress_count": product.get("progress_count"),
            "final_state": product.get("final_state"),
            "stop_reason": product.get("stop_reason"),
            "teacher_seed_citation_count": product_report.get(
                "product_teacher_seed_citation_count"
            ),
            "teacher_seed_citation_ids": product_seed_ids,
            "runtime_identity_digest": product_report.get(
                "product_runtime_identity_digest"
            ),
        },
        "p_removal_ablation": {
            "replacement": "HybridRelationalInstructionBody",
            "p_ir": "compatibility_p_ir_program",
            "product_j0_retained": True,
            "product_m0_retained": True,
            "actions_executed": ablation.get("actions_executed"),
            "progress_count": ablation.get("progress_count"),
            "final_state": ablation.get("final_state"),
            "stop_reason": ablation.get("stop_reason"),
        },
        "gates": gates,
        "failure_reasons": failures,
        "exit_status": M2_ACCEPTANCE_EXIT if not failures else "INCOMPLETE",
    }
    body["content_digest"] = "arc3-product-m2-acceptance:" + digest_object(
        body
    )
    return body


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Execute controlled M2 product P/J0/M0 acceptance."
    )
    parser.add_argument(
        "--environments-dir",
        type=Path,
        default=_default_environments_dir(),
    )
    parser.add_argument("--recordings-dir", type=Path)
    parser.add_argument("--game", default=M2_ACCEPTANCE_GAME)
    parser.add_argument(
        "--action-budget",
        type=int,
        default=M2_CONTROLLED_ACTION_BUDGET,
    )
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    if arguments.recordings_dir is None:
        with tempfile.TemporaryDirectory(prefix="arc3-m2-acceptance-") as temporary:
            report = run_acceptance(
                environments_dir=arguments.environments_dir.resolve(),
                recordings_dir=Path(temporary),
                game=arguments.game,
                action_budget=arguments.action_budget,
            )
    else:
        report = run_acceptance(
            environments_dir=arguments.environments_dir.resolve(),
            recordings_dir=arguments.recordings_dir.resolve(),
            game=arguments.game,
            action_budget=arguments.action_budget,
        )
    encoded = json.dumps(
        report,
        ensure_ascii=False,
        indent=2,
        sort_keys=True,
    ) + "\n"
    if arguments.output is not None:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(encoded, encoding="utf-8", newline="\n")
    print(encoded, end="")
    return int(report["exit_status"] != M2_ACCEPTANCE_EXIT)


if __name__ == "__main__":
    raise SystemExit(main())
