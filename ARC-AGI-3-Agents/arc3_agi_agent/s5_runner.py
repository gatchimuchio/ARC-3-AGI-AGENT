"""Run the rendered-only S5 Runtime Student over retained OFFLINE samples."""

from __future__ import annotations

import argparse
import gc
import json
import os
import random
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import numpy as np
from arc_agi import Arcade, OperationMode  # type: ignore[import-untyped]
from arc_agi.local_wrapper import (  # type: ignore[import-untyped]
    LocalEnvironmentWrapper,
)
from arcengine import FrameDataRaw

from .protocol import AuthorityViolation
from .s5_policy import (
    S5_POINTER_ACTION_ID,
    S5_RESET_ACTION_ID,
    S5RenderedPolicyBody,
    load_s5_rendered_policy_body,
)
from .s5_runtime import S5OfflineSampleRuntime
from .schema import digest_object

S5_CLOSURE_REPORT_SCHEMA_VERSION = (
    "arc3-s5-rendered-only-runtime-closure-report-v1"
)
S5_CLOSURE_REPORT_DIGEST_PREFIX = "arc3_s5_rendered_runtime_closure:"
S5_DEFAULT_DETERMINISTIC_SEED = 0


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            value,
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def _discover_environment_ids(environments_dir: Path) -> list[str]:
    identifiers: list[str] = []
    for metadata_path in sorted(
        environments_dir.glob("*/*/metadata.json")
    ):
        value = json.loads(metadata_path.read_text(encoding="utf-8"))
        if not isinstance(value, Mapping):
            raise TypeError("S5_ENVIRONMENT_METADATA_INVALID")
        identifier = value.get("game_id")
        if not isinstance(identifier, str) or not identifier:
            raise ValueError("S5_ENVIRONMENT_METADATA_ID_INVALID")
        expected = (
            metadata_path.parent.parent.name
            + "-"
            + metadata_path.parent.name
        )
        if identifier != expected:
            raise ValueError("S5_ENVIRONMENT_METADATA_PATH_DIVERGED")
        identifiers.append(identifier)
    if not identifiers or len(identifiers) != len(set(identifiers)):
        raise ValueError("S5_ENVIRONMENT_INVENTORY_INVALID")
    return identifiers


def _state(frame: FrameDataRaw) -> str:
    return str(frame.state.value).upper()


def execute_s5_rendered_policy(
    *,
    environment: LocalEnvironmentWrapper,
    instruction_body: S5RenderedPolicyBody,
    max_actions: int,
) -> dict[str, Any]:
    """Execute one environment; identity is absent from the runtime API."""

    runtime = S5OfflineSampleRuntime(
        environment=environment,
        operation_mode=OperationMode.OFFLINE,
        max_actions=max_actions,
        instruction_body=instruction_body,
    )
    frame = environment.observation_space
    if not isinstance(frame, FrameDataRaw):
        raise RuntimeError("S5_INITIAL_FRAME_MISSING")
    prior_levels = int(frame.levels_completed)
    action_count = 0
    actions_in_level = 0
    level_action_counts: list[int] = []
    pointer_actions = 0
    policy_resets = 0
    game_over_observations = 0
    outcome_retentions = 0
    memory_influenced_decisions = 0
    standard_emissions = 0
    hds_compute_commands = 0
    trace: list[dict[str, object]] = []
    reset_decision_ids: list[str] = []
    retention_decision_ids: list[str] = []

    while _state(frame) != "WIN":
        if action_count >= max_actions:
            raise RuntimeError("S5_MAX_ACTION_STOP")
        before_state = _state(frame)
        step = runtime.run_cycle(
            frame,
            action_count=action_count,
        )
        result = step.kernel_cycle.kernel_result
        hds_compute_commands += 1
        memory_influenced_decisions += int(
            result.memory_influenced_decision
        )
        action_count += 1
        actions_in_level += 1
        pointer_actions += int(step.action_id == S5_POINTER_ACTION_ID)
        if step.policy_reset is not None:
            if step.action_id != S5_RESET_ACTION_ID:
                raise RuntimeError("S5_RESET_ACTION_MISMATCH")
            policy_resets += 1
            reset_decision_ids.append(step.authority_decision_id)
        else:
            standard_emissions += 1
        if step.outcome_retention is not None:
            if _state(step.after_frame) != "GAME_OVER":
                raise RuntimeError("S5_OUTCOME_RETENTION_WITHOUT_FAILURE")
            outcome_retentions += 1
            retention_decision_ids.append(step.authority_decision_id)
        if _state(step.after_frame) == "GAME_OVER":
            game_over_observations += 1

        current_levels = int(step.after_frame.levels_completed)
        if current_levels == prior_levels + 1:
            level_action_counts.append(actions_in_level)
            actions_in_level = 0
        elif current_levels != prior_levels:
            raise RuntimeError(
                f"S5_LEVEL_PROGRESS_INVALID:{prior_levels}:{current_levels}"
            )
        trace.append(
            {
                "action_id": step.action_id,
                "after_state": _state(step.after_frame),
                "authority_decision_id": step.authority_decision_id,
                "before_state": before_state,
                "hds_status": result.status,
                "instruction_query_digest": (
                    result.instruction_query_digest
                ),
                "levels_completed": current_levels,
                "memory_version": runtime.components.memory.version
                if runtime.components.memory is not None
                else -1,
                "outcome_retained": step.outcome_retention is not None,
                "policy_reset": step.policy_reset is not None,
                "trace_digest": result.trace_digest,
            }
        )
        prior_levels = current_levels
        frame = step.after_frame

    completed_levels = int(frame.levels_completed)
    if (
        completed_levels <= 0
        or len(level_action_counts) != completed_levels
        or actions_in_level != 0
        or sum(level_action_counts) != action_count
    ):
        raise RuntimeError("S5_FINAL_LEVEL_ACCOUNTING_INVALID")
    memory = runtime.components.memory
    if memory is None:
        raise RuntimeError("S5_MEMORY_SUBJECT_MISSING")
    context = runtime.context_state.snapshot()
    if context.actions_used != action_count:
        raise RuntimeError("S5_CONTEXT_ACTION_ACCOUNTING_INVALID")
    return {
        "actions_executed": action_count,
        "complete": True,
        "completed_levels": completed_levels,
        "final_memory_version": memory.version,
        "final_state": _state(frame),
        "game_over_observation_count": game_over_observations,
        "hds_compute_command_count": hds_compute_commands,
        "level_action_counts": level_action_counts,
        "memory_influenced_decision_count": (
            memory_influenced_decisions
        ),
        "normal_external_emit_count": standard_emissions,
        "outcome_retention_count": outcome_retentions,
        "outcome_retention_decision_digest": digest_object(
            retention_decision_ids
        ),
        "pointer_payload_generated_count": pointer_actions,
        "policy_reset_count": policy_resets,
        "policy_reset_decision_digest": digest_object(reset_decision_ids),
        "runtime_trace_digest": digest_object(trace),
    }


def run_s5_rendered_policy(
    *,
    environments_dir: Path,
    requested_games: Sequence[str] = (),
    recordings_dir: Path | None = None,
    max_actions: int = 4096,
    deterministic_seed: int = S5_DEFAULT_DETERMINISTIC_SEED,
) -> dict[str, Any]:
    if os.getenv("OPERATION_MODE", "").strip().casefold() == "competition":
        raise AuthorityViolation("COMPETITION_MODE_FORBIDDEN_DURING_S5")
    if (
        isinstance(deterministic_seed, bool)
        or not 0 <= deterministic_seed <= 0xFFFF_FFFF
    ):
        raise ValueError("S5_DETERMINISTIC_SEED_INVALID")
    environments_dir = environments_dir.resolve()
    if not environments_dir.is_dir():
        raise FileNotFoundError(
            f"sample environment directory not found: {environments_dir}"
        )
    discovered = _discover_environment_ids(environments_dir)
    requested = tuple(dict.fromkeys(str(item) for item in requested_games))
    unknown = sorted(set(requested).difference(discovered))
    if unknown:
        raise ValueError(
            "S5_REQUESTED_ENVIRONMENT_UNKNOWN:" + ",".join(unknown)
        )
    selected = sorted(requested) if requested else sorted(discovered)
    complete_inventory = not requested and selected == sorted(discovered)
    output_dir = (
        recordings_dir.resolve()
        if recordings_dir is not None
        else environments_dir.parent / "recordings"
    )
    arcade = Arcade(
        operation_mode=OperationMode.OFFLINE,
        environments_dir=str(environments_dir),
        recordings_dir=str(output_dir),
    )
    if arcade.operation_mode is not OperationMode.OFFLINE:
        raise AuthorityViolation("OFFLINE_SAMPLE_MODE_NOT_EFFECTIVE")
    instruction_body = load_s5_rendered_policy_body()
    reports: list[dict[str, Any]] = []
    errors: list[dict[str, str]] = []
    for evaluation_identifier in selected:
        random.seed(deterministic_seed)
        np.random.seed(deterministic_seed)
        scorecard_id = arcade.open_scorecard(
            tags=["p10-r5", "s5-runtime-student", "rendered-only"]
        )
        try:
            environment = arcade.make(
                evaluation_identifier,
                scorecard_id=scorecard_id,
                save_recording=False,
                include_frame_data=True,
            )
            if not isinstance(environment, LocalEnvironmentWrapper):
                raise RuntimeError("S5_ENVIRONMENT_LOAD_FAILED")
            action_report = execute_s5_rendered_policy(
                environment=environment,
                instruction_body=instruction_body,
                max_actions=max_actions,
            )
            report = {
                "game_id": evaluation_identifier,
                **action_report,
            }
            reports.append(report)
            print(
                json.dumps(
                    {
                        "event": "S5_RENDERED_RUNTIME_EXECUTED",
                        "evaluation_environment": evaluation_identifier,
                        "completed_levels": report["completed_levels"],
                        "actions_executed": report["actions_executed"],
                        "policy_resets": report["policy_reset_count"],
                    },
                    sort_keys=True,
                ),
                flush=True,
            )
        except Exception as error:
            errors.append(
                {
                    "game_id": evaluation_identifier,
                    "error_type": type(error).__name__,
                    "message": str(error),
                }
            )
        finally:
            arcade.close_scorecard(scorecard_id)
            gc.collect()
    reports.sort(key=lambda item: str(item["game_id"]))
    errors.sort(key=lambda item: str(item["game_id"]))
    completed_levels = sum(
        int(report["completed_levels"]) for report in reports
    )
    actions_executed = sum(
        int(report["actions_executed"]) for report in reports
    )
    all_complete = (
        not errors
        and len(reports) == len(selected)
        and all(
            report.get("complete") is True
            and report.get("final_state") == "WIN"
            for report in reports
        )
    )
    body: dict[str, Any] = {
        "schema_version": S5_CLOSURE_REPORT_SCHEMA_VERSION,
        "phase": "P10-R5-RENDERED-ONLY-RUNTIME-P-COMPILATION",
        "privilege_stage": "S5",
        "runtime_student": True,
        "operation_mode": "offline",
        "complete_inventory": complete_inventory,
        "environment_count": len(selected),
        "completed_environment_count": len(reports),
        "completed_levels": completed_levels,
        "actions_executed": actions_executed,
        "deterministic_seed": deterministic_seed,
        "error_count": len(errors),
        "all_complete": all_complete,
        "hds_stage_decision": "PASS" if all_complete else "HOLD",
        "next_stage_authorized": all_complete and complete_inventory,
        "instruction_body_format": instruction_body.format_id,
        "instruction_body_version": instruction_body.body_version,
        "instruction_body_digest": instruction_body.digest(),
        "instruction_body_parameter_count": (
            instruction_body.parameter_count
        ),
        "hds_compute_command_count": sum(
            int(report["hds_compute_command_count"])
            for report in reports
        ),
        "normal_external_emit_count": sum(
            int(report["normal_external_emit_count"])
            for report in reports
        ),
        "policy_reset_count": sum(
            int(report["policy_reset_count"]) for report in reports
        ),
        "game_over_observation_count": sum(
            int(report["game_over_observation_count"])
            for report in reports
        ),
        "outcome_retention_count": sum(
            int(report["outcome_retention_count"])
            for report in reports
        ),
        "pointer_payload_generated_count": sum(
            int(report["pointer_payload_generated_count"])
            for report in reports
        ),
        "memory_influenced_decision_count": sum(
            int(report["memory_influenced_decision_count"])
            for report in reports
        ),
        "evaluation_identity_use": (
            "ORCHESTRATION_AND_ATTRIBUTION_ONLY"
        ),
        "action_selection_receives_environment_identity": False,
        "action_selection_receives_environment_wrapper": False,
        "action_selection_receives_source_or_hidden_state": False,
        "runtime_imports_teacher_package": False,
        "runtime_reads_teacher_artifact": False,
        "decision_uses_task_game_level_identity": False,
        "decision_uses_level_progress_counter": False,
        "decision_uses_per_game_policy_partition": False,
        "decision_uses_source_or_hidden_state": False,
        "decision_uses_answer_or_replay_graph": False,
        "decision_uses_fixed_action_sequence": False,
        "decision_uses_literal_coordinate_table": False,
        "pointer_payload_generated_transiently": True,
        "runtime_inputs": [
            "rendered observation",
            "available actions",
            "bounded action effect history",
            "HDS approved passive memory",
            "identity free compiled P",
        ],
        "reports": reports,
        "errors": errors,
    }
    return {
        **body,
        "content_digest": (
            S5_CLOSURE_REPORT_DIGEST_PREFIX + digest_object(body)
        ),
    }


def load_s5_closure_report(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise TypeError("S5 closure report must be an object")
    report = dict(value)
    content_digest = report.pop("content_digest", None)
    if content_digest != (
        S5_CLOSURE_REPORT_DIGEST_PREFIX + digest_object(report)
    ):
        raise ValueError("S5_CLOSURE_REPORT_DIGEST_MISMATCH")
    return dict(value)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Execute rendered-only S5 Runtime Student."
    )
    parser.add_argument("--environments-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--recordings-dir", type=Path)
    parser.add_argument("--max-actions", type=int, default=4096)
    parser.add_argument(
        "--seed",
        type=int,
        default=S5_DEFAULT_DETERMINISTIC_SEED,
    )
    parser.add_argument("--game", action="append", default=[])
    return parser


def main() -> int:
    args = _parser().parse_args()
    report = run_s5_rendered_policy(
        environments_dir=args.environments_dir,
        requested_games=args.game,
        recordings_dir=args.recordings_dir,
        max_actions=args.max_actions,
        deterministic_seed=args.seed,
    )
    _write_json(args.output, report)
    print(
        json.dumps(
            {
                "output": str(args.output.resolve()),
                "environment_count": report["environment_count"],
                "completed_levels": report["completed_levels"],
                "actions_executed": report["actions_executed"],
                "error_count": report["error_count"],
                "all_complete": report["all_complete"],
                "content_digest": report["content_digest"],
            },
            sort_keys=True,
        )
    )
    return int(report["all_complete"] is not True)


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "S5_CLOSURE_REPORT_SCHEMA_VERSION",
    "S5_DEFAULT_DETERMINISTIC_SEED",
    "execute_s5_rendered_policy",
    "load_s5_closure_report",
    "run_s5_rendered_policy",
]
