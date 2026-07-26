"""Run the rendered-only S5 Runtime Student over retained OFFLINE samples."""

from __future__ import annotations

import argparse
import dataclasses
import gc
import gzip
import hashlib
import json
import os
import random
from collections.abc import Callable, Iterable, Mapping, Sequence
from pathlib import Path
from typing import Any, Protocol

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
from .schema import canonical_json, digest_object

S5_CLOSURE_REPORT_SCHEMA_VERSION = (
    "arc3-s5-rendered-only-runtime-closure-report-v1"
)
S5_CLOSURE_REPORT_DIGEST_PREFIX = "arc3_s5_rendered_runtime_closure:"
S5_DEFAULT_DETERMINISTIC_SEED = 0
S5_EXECUTION_TRACE_MANIFEST_SCHEMA_VERSION = (
    "arc3-s5-full-execution-trace-manifest-v1"
)
S5_EXECUTION_TRACE_MANIFEST_DIGEST_PREFIX = (
    "arc3_s5_full_execution_trace_manifest:"
)
S5_RUNTIME_TRACE_SUMMARY_FIELDS = (
    "action_id",
    "after_state",
    "authority_decision_id",
    "before_state",
    "hds_status",
    "instruction_query_digest",
    "levels_completed",
    "memory_version",
    "outcome_retained",
    "policy_reset",
    "trace_digest",
)
S5_RUNTIME_TRACE_REQUIRED_FIELDS = (
    *S5_RUNTIME_TRACE_SUMMARY_FIELDS,
    "action_index",
    "after_observation_signature",
    "candidates",
    "closures",
    "compute_memory_digest",
    "compute_memory_version",
    "decision",
    "emission_result",
    "follow_up_authority_decision",
    "hypotheses",
    "instruction_body_digest",
    "instruction_body_format",
    "instruction_body_version",
    "kernel_trace",
    "memory_influenced_decision",
    "memory_result",
    "observation",
    "outcome_retention_result",
    "policy_reset_execution",
)


class _BinaryWriter(Protocol):
    def write(self, data: bytes, /) -> int: ...


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


def _file_sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _serialized(value: object) -> object:
    return json.loads(canonical_json(value))


def _public_dataclass(value: object | None) -> object | None:
    if value is None:
        return None
    if not dataclasses.is_dataclass(value):
        raise TypeError("S5_TRACE_DATACLASS_REQUIRED")
    return {
        item.name: _serialized(getattr(value, item.name))
        for item in dataclasses.fields(value)
        if not item.name.startswith("_") and item.name != "reset_frame"
    }


def _summary_trace_event(
    event: Mapping[str, object],
) -> dict[str, object]:
    missing = [
        field
        for field in S5_RUNTIME_TRACE_SUMMARY_FIELDS
        if field not in event
    ]
    if missing:
        raise ValueError(
            "S5_TRACE_SUMMARY_FIELD_MISSING:" + ",".join(missing)
        )
    return {
        field: event[field]
        for field in S5_RUNTIME_TRACE_SUMMARY_FIELDS
    }


def _trace_integer(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("S5_TRACE_INTEGER_REQUIRED")
    return value


def _contains_runtime_identity_key(value: object) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            normalized = (
                str(key)
                .casefold()
                .replace("_", "")
                .replace("-", "")
            )
            if normalized in {
                "evaluationenvironment",
                "gameid",
                "levelid",
                "taskid",
            }:
                return True
            if _contains_runtime_identity_key(item):
                return True
    elif isinstance(value, (list, tuple)):
        return any(_contains_runtime_identity_key(item) for item in value)
    return False


def _validate_full_runtime_trace_event(
    event: Mapping[str, object],
    *,
    action_index: int,
    evaluation_environment: str,
) -> None:
    missing = [
        field
        for field in S5_RUNTIME_TRACE_REQUIRED_FIELDS
        if field not in event
    ]
    if missing:
        raise ValueError(
            "S5_TRACE_FULL_FIELD_MISSING:" + ",".join(missing)
        )
    if (
        _trace_integer(event["action_index"]) != action_index
        or _contains_runtime_identity_key(event)
        or evaluation_environment in canonical_json(event)
    ):
        raise ValueError("S5_TRACE_RUNTIME_IDENTITY_OR_INDEX_INVALID")
    for field in (
        "action_id",
        "compute_memory_version",
        "levels_completed",
        "memory_version",
    ):
        _trace_integer(event[field])
    for field in (
        "after_observation_signature",
        "authority_decision_id",
        "compute_memory_digest",
        "hds_status",
        "instruction_body_digest",
        "instruction_body_format",
        "instruction_body_version",
        "instruction_query_digest",
        "trace_digest",
    ):
        if not isinstance(event[field], str) or not event[field]:
            raise TypeError(f"S5_TRACE_STRING_REQUIRED:{field}")
    for field in ("candidates", "closures", "hypotheses"):
        if not isinstance(event[field], list):
            raise TypeError(f"S5_TRACE_LIST_REQUIRED:{field}")
    if (
        not isinstance(event["observation"], Mapping)
        or not isinstance(event["decision"], Mapping)
        or not isinstance(event["memory_influenced_decision"], bool)
        or not isinstance(event["outcome_retained"], bool)
        or not isinstance(event["policy_reset"], bool)
    ):
        raise TypeError("S5_TRACE_RUNTIME_EVENT_TYPE_INVALID")
    for field in (
        "emission_result",
        "follow_up_authority_decision",
        "memory_result",
        "outcome_retention_result",
        "policy_reset_execution",
    ):
        if event[field] is not None and not isinstance(
            event[field],
            Mapping,
        ):
            raise TypeError(f"S5_TRACE_RESULT_INVALID:{field}")
    reset = event["policy_reset"] is True
    retained = event["outcome_retained"] is True
    if (
        (event["policy_reset_execution"] is not None) != reset
        or (event["outcome_retention_result"] is not None) != retained
        or (event["emission_result"] is None) == (not reset)
        or (
            event["follow_up_authority_decision"] is not None
        )
        != (reset or retained)
    ):
        raise ValueError("S5_TRACE_RESULT_RELATION_INVALID")
    kernel_trace = event["kernel_trace"]
    if (
        not isinstance(kernel_trace, list)
        or not kernel_trace
        or digest_object(kernel_trace) != event["trace_digest"]
    ):
        raise ValueError("S5_TRACE_KERNEL_DIGEST_INVALID")


def _write_json_lines(
    path: Path,
    records: Sequence[Mapping[str, object]],
) -> str:
    path.parent.mkdir(parents=True, exist_ok=True)
    record_hasher = hashlib.sha256()

    def emit(stream: _BinaryWriter) -> None:
        record_hasher.update(b"[")
        for index, record in enumerate(records):
            encoded = canonical_json(record).encode("utf-8")
            if index:
                record_hasher.update(b",")
            record_hasher.update(encoded)
            stream.write(encoded + b"\n")
        record_hasher.update(b"]")

    if path.name.endswith(".jsonl.gz"):
        with path.open("wb") as raw_stream:
            with gzip.GzipFile(
                filename="",
                mode="wb",
                compresslevel=9,
                fileobj=raw_stream,
                mtime=0,
            ) as compressed_stream:
                emit(compressed_stream)
        return record_hasher.hexdigest()
    if path.name.endswith(".jsonl"):
        with path.open("wb") as raw_stream:
            emit(raw_stream)
        return record_hasher.hexdigest()
    else:
        raise ValueError("S5_TRACE_FILE_EXTENSION_INVALID")


def _trace_format(path: Path) -> str:
    if path.name.endswith(".jsonl.gz"):
        return "canonical-json-lines+gzip"
    if path.name.endswith(".jsonl"):
        return "canonical-json-lines"
    raise ValueError("S5_TRACE_FILE_EXTENSION_INVALID")


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
    trace_sink: Callable[[dict[str, object]], None] | None = None,
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
        trace_event: dict[str, object] = {
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
        trace.append(trace_event)
        if trace_sink is not None:
            emission = result.emission_result
            after_observation_signature = (
                emission.result_observation_signature
                if emission is not None
                else runtime.runtime.frame_adapter.signature(
                    step.after_frame
                )
            )
            trace_sink(
                {
                    **trace_event,
                    "action_index": action_count - 1,
                    "after_observation_signature": (
                        after_observation_signature
                    ),
                    "candidates": _serialized(result.candidates),
                    "closures": _serialized(result.closures),
                    "compute_memory_digest": (
                        result.compute_memory_digest
                    ),
                    "compute_memory_version": (
                        result.compute_memory_version
                    ),
                    "decision": _public_dataclass(result.decision),
                    "emission_result": _public_dataclass(
                        result.emission_result
                    ),
                    "follow_up_authority_decision": (
                        _public_dataclass(
                            step.follow_up_authority_decision
                        )
                    ),
                    "hypotheses": _serialized(result.hypotheses),
                    "instruction_body_digest": (
                        result.instruction_body_digest
                    ),
                    "instruction_body_format": (
                        result.instruction_body_format
                    ),
                    "instruction_body_version": (
                        result.instruction_body_version
                    ),
                    "kernel_trace": _serialized(result.trace),
                    "memory_influenced_decision": (
                        result.memory_influenced_decision
                    ),
                    "memory_result": _public_dataclass(
                        result.memory_result
                    ),
                    "observation": _serialized(result.observation),
                    "outcome_retention_result": _public_dataclass(
                        step.outcome_retention
                    ),
                    "policy_reset_execution": _public_dataclass(
                        step.policy_reset
                    ),
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
    trace_jsonl_path: Path | None = None,
    trace_manifest_path: Path | None = None,
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
    if (trace_jsonl_path is None) != (trace_manifest_path is None):
        raise ValueError("S5_TRACE_OUTPUT_PAIR_REQUIRED")
    if (
        trace_jsonl_path is not None
        and trace_manifest_path is not None
        and trace_jsonl_path.resolve() == trace_manifest_path.resolve()
    ):
        raise ValueError("S5_TRACE_OUTPUT_PATH_COLLISION")
    if (
        trace_jsonl_path is not None
        and trace_manifest_path is not None
        and trace_jsonl_path.resolve().parent
        != trace_manifest_path.resolve().parent
    ):
        raise ValueError("S5_TRACE_OUTPUT_DIRECTORY_MISMATCH")
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
    traced_games: list[tuple[str, list[dict[str, object]]]] = []
    trace_enabled = trace_jsonl_path is not None
    for evaluation_identifier in selected:
        game_trace: list[dict[str, object]] = []
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
                trace_sink=game_trace.append if trace_enabled else None,
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
        if trace_enabled:
            traced_games.append((evaluation_identifier, game_trace))
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
    closure_report = {
        **body,
        "content_digest": (
            S5_CLOSURE_REPORT_DIGEST_PREFIX + digest_object(body)
        ),
    }
    if trace_jsonl_path is not None and trace_manifest_path is not None:
        write_s5_execution_trace_artifact(
            closure_report=closure_report,
            traced_games=traced_games,
            trace_jsonl_path=trace_jsonl_path,
            trace_manifest_path=trace_manifest_path,
            max_actions=max_actions,
        )
    return closure_report


def write_s5_execution_trace_artifact(
    *,
    closure_report: Mapping[str, Any],
    traced_games: Sequence[
        tuple[str, Sequence[Mapping[str, object]]]
    ],
    trace_jsonl_path: Path,
    trace_manifest_path: Path,
    max_actions: int,
) -> dict[str, Any]:
    """Persist every S5 runtime cycle without feeding identity to policy."""

    if trace_jsonl_path.resolve() == trace_manifest_path.resolve():
        raise ValueError("S5_TRACE_OUTPUT_PATH_COLLISION")
    if (
        trace_jsonl_path.resolve().parent
        != trace_manifest_path.resolve().parent
    ):
        raise ValueError("S5_TRACE_OUTPUT_DIRECTORY_MISMATCH")
    report_by_environment = {
        str(item["game_id"]): item
        for item in closure_report.get("reports", ())
        if isinstance(item, Mapping) and "game_id" in item
    }
    records: list[dict[str, object]] = []
    game_traces: list[dict[str, object]] = []
    seen: set[str] = set()
    for evaluation_environment, events in traced_games:
        if (
            not evaluation_environment
            or evaluation_environment in seen
        ):
            raise ValueError("S5_TRACE_ENVIRONMENT_ID_INVALID")
        seen.add(evaluation_environment)
        start = len(records)
        summaries: list[dict[str, object]] = []
        for action_index, raw_event in enumerate(events):
            event = dict(raw_event)
            _validate_full_runtime_trace_event(
                event,
                action_index=action_index,
                evaluation_environment=evaluation_environment,
            )
            summaries.append(_summary_trace_event(event))
            records.append(
                {
                    "action_index": action_index,
                    "evaluation_environment": (
                        evaluation_environment
                    ),
                    "record_index": len(records),
                    "runtime_event": event,
                }
            )
        report = report_by_environment.get(evaluation_environment)
        completed_levels = (
            int(report["completed_levels"])
            if report is not None
            else _trace_integer(
                events[-1].get("levels_completed", 0)
            )
            if events
            else 0
        )
        runtime_trace_digest = digest_object(summaries)
        if (
            report is not None
            and report.get("runtime_trace_digest")
            != runtime_trace_digest
        ):
            raise ValueError("S5_TRACE_CLOSURE_DIGEST_MISMATCH")
        game_traces.append(
            {
                "action_count": len(events),
                "complete": bool(
                    report is not None
                    and report.get("complete") is True
                ),
                "completed_levels": completed_levels,
                "end_record_index_exclusive": len(records),
                "evaluation_environment": evaluation_environment,
                "runtime_trace_digest": runtime_trace_digest,
                "start_record_index": start,
            }
        )
    record_stream_digest = _write_json_lines(
        trace_jsonl_path,
        records,
    )
    trace_sha256 = _file_sha256(trace_jsonl_path)
    record_count = len(records)
    complete_coverage = (
        closure_report.get("all_complete") is True
        and len(game_traces)
        == int(closure_report.get("environment_count", -1))
        and record_count
        == int(closure_report.get("actions_executed", -1))
        and sum(
            _trace_integer(item["completed_levels"])
            for item in game_traces
        )
        == int(closure_report.get("completed_levels", -1))
        and all(item["complete"] is True for item in game_traces)
    )
    body: dict[str, Any] = {
        "schema_version": (
            S5_EXECUTION_TRACE_MANIFEST_SCHEMA_VERSION
        ),
        "phase": "P10-R5-FULL-EXECUTION-TRACE",
        "privilege_stage": "S5",
        "operation_mode": "offline",
        "complete_inventory": closure_report.get(
            "complete_inventory"
        ),
        "all_complete": closure_report.get("all_complete"),
        "complete_execution_trace_coverage": complete_coverage,
        "environment_count": closure_report.get(
            "environment_count"
        ),
        "completed_levels": closure_report.get("completed_levels"),
        "record_count": record_count,
        "deterministic_seed": closure_report.get(
            "deterministic_seed"
        ),
        "max_actions": max_actions,
        "closure_content_digest": closure_report.get(
            "content_digest"
        ),
        "instruction_body_version": closure_report.get(
            "instruction_body_version"
        ),
        "instruction_body_digest": closure_report.get(
            "instruction_body_digest"
        ),
        "trace_format": _trace_format(trace_jsonl_path),
        "trace_filename": trace_jsonl_path.name,
        "trace_jsonl_sha256": trace_sha256,
        "record_stream_digest": record_stream_digest,
        "runtime_summary_fields": list(
            S5_RUNTIME_TRACE_SUMMARY_FIELDS
        ),
        "evaluation_identity_use": (
            "ORCHESTRATION_AND_ATTRIBUTION_ONLY"
        ),
        "action_selection_receives_environment_identity": False,
        "runtime_event_contains_environment_identity": False,
        "game_traces": game_traces,
    }
    manifest = {
        **body,
        "content_digest": (
            S5_EXECUTION_TRACE_MANIFEST_DIGEST_PREFIX
            + digest_object(body)
        ),
    }
    _write_json(trace_manifest_path, manifest)
    return manifest


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


def load_s5_execution_trace_manifest(
    manifest_path: Path,
    *,
    closure_path: Path | None = None,
) -> dict[str, Any]:
    value = json.loads(manifest_path.read_text(encoding="utf-8"))
    if not isinstance(value, Mapping):
        raise TypeError("S5_TRACE_MANIFEST_OBJECT_REQUIRED")
    manifest = dict(value)
    body = dict(manifest)
    claimed = body.pop("content_digest", None)
    if (
        manifest.get("schema_version")
        != S5_EXECUTION_TRACE_MANIFEST_SCHEMA_VERSION
        or claimed
        != S5_EXECUTION_TRACE_MANIFEST_DIGEST_PREFIX
        + digest_object(body)
    ):
        raise ValueError("S5_TRACE_MANIFEST_DIGEST_INVALID")
    trace_filename = manifest.get("trace_filename")
    if (
        not isinstance(trace_filename, str)
        or Path(trace_filename).name != trace_filename
    ):
        raise ValueError("S5_TRACE_FILENAME_INVALID")
    trace_path = manifest_path.parent / trace_filename
    if (
        _file_sha256(trace_path)
        != manifest.get("trace_jsonl_sha256")
        or manifest.get("trace_format") != _trace_format(trace_path)
    ):
        raise ValueError("S5_TRACE_FILE_DIGEST_INVALID")
    game_traces = manifest.get("game_traces")
    if not isinstance(game_traces, list):
        raise TypeError("S5_TRACE_GAME_INDEX_REQUIRED")
    expected_start = 0
    completed_levels = 0
    descriptors: list[dict[str, object]] = []
    seen_environments: set[str] = set()
    for game_trace in game_traces:
        if not isinstance(game_trace, Mapping):
            raise TypeError("S5_TRACE_GAME_DESCRIPTOR_INVALID")
        start = _trace_integer(
            game_trace.get("start_record_index")
        )
        end = _trace_integer(
            game_trace.get("end_record_index_exclusive")
        )
        environment = game_trace.get("evaluation_environment")
        action_count = _trace_integer(game_trace.get("action_count"))
        if (
            start != expected_start
            or end < start
            or end - start != action_count
            or not isinstance(environment, str)
            or not environment
            or environment in seen_environments
            or game_trace.get("complete") is not True
        ):
            raise ValueError("S5_TRACE_GAME_RANGE_INVALID")
        seen_environments.add(environment)
        descriptors.append(dict(game_trace))
        expected_start = end
        completed_levels += _trace_integer(
            game_trace["completed_levels"]
        )
    if (
        expected_start != manifest.get("record_count")
        or len(game_traces) != manifest.get("environment_count")
        or completed_levels != manifest.get("completed_levels")
    ):
        raise ValueError("S5_TRACE_COVERAGE_ACCOUNTING_INVALID")

    record_hasher = hashlib.sha256()
    record_hasher.update(b"[")
    record_count = 0
    game_index = 0
    summaries: list[dict[str, object]] = []

    def finish_empty_or_complete_games() -> None:
        nonlocal game_index, summaries
        while game_index < len(descriptors):
            descriptor = descriptors[game_index]
            end = _trace_integer(
                descriptor["end_record_index_exclusive"]
            )
            if record_count < end:
                break
            if digest_object(summaries) != descriptor.get(
                "runtime_trace_digest"
            ):
                raise ValueError("S5_TRACE_GAME_DIGEST_INVALID")
            summaries = []
            game_index += 1

    def consume(trace_lines: Iterable[bytes]) -> None:
        nonlocal record_count, game_index, summaries
        for line_number, raw_line in enumerate(
            trace_lines,
            start=1,
        ):
            if not raw_line.endswith(b"\n"):
                raise ValueError("S5_TRACE_FILE_TERMINATOR_INVALID")
            encoded = raw_line[:-1]
            record = json.loads(encoded.decode("utf-8"))
            if not isinstance(record, Mapping):
                raise TypeError(
                    "S5_TRACE_RECORD_OBJECT_REQUIRED:"
                    f"{line_number}"
                )
            canonical = canonical_json(record).encode("utf-8")
            if canonical != encoded:
                raise ValueError("S5_TRACE_RECORD_NOT_CANONICAL")
            finish_empty_or_complete_games()
            if game_index >= len(descriptors):
                raise ValueError("S5_TRACE_RECORD_OVERFLOW")
            descriptor = descriptors[game_index]
            start = _trace_integer(
                descriptor["start_record_index"]
            )
            environment = descriptor["evaluation_environment"]
            action_index = record_count - start
            event = record.get("runtime_event")
            if (
                record.get("record_index") != record_count
                or record.get("action_index") != action_index
                or record.get("evaluation_environment")
                != environment
            ):
                raise ValueError("S5_TRACE_RECORD_INDEX_INVALID")
            if not isinstance(event, Mapping):
                raise TypeError("S5_TRACE_RUNTIME_EVENT_REQUIRED")
            _validate_full_runtime_trace_event(
                event,
                action_index=action_index,
                evaluation_environment=str(environment),
            )
            summaries.append(_summary_trace_event(event))
            if record_count:
                record_hasher.update(b",")
            record_hasher.update(encoded)
            record_count += 1

    if _trace_format(trace_path) == "canonical-json-lines+gzip":
        with gzip.open(trace_path, "rb") as compressed_trace_stream:
            consume(compressed_trace_stream)
    else:
        with trace_path.open("rb") as raw_trace_stream:
            consume(raw_trace_stream)
    finish_empty_or_complete_games()
    record_hasher.update(b"]")
    if (
        record_count != manifest.get("record_count")
        or game_index != len(descriptors)
        or record_hasher.hexdigest()
        != manifest.get("record_stream_digest")
    ):
        raise ValueError("S5_TRACE_RECORD_STREAM_INVALID")
    if closure_path is not None:
        closure = load_s5_closure_report(closure_path)
        if (
            manifest.get("closure_content_digest")
            != closure.get("content_digest")
            or manifest.get("record_count")
            != closure.get("actions_executed")
            or manifest.get("environment_count")
            != closure.get("environment_count")
            or manifest.get("completed_levels")
            != closure.get("completed_levels")
        ):
            raise ValueError("S5_TRACE_CLOSURE_BINDING_INVALID")
        closure_reports = {
            str(item["game_id"]): item
            for item in closure.get("reports", ())
            if isinstance(item, Mapping) and "game_id" in item
        }
        if set(closure_reports) != seen_environments:
            raise ValueError(
                "S5_TRACE_CLOSURE_ENVIRONMENT_SET_INVALID"
            )
        for game_trace in game_traces:
            environment = str(
                game_trace["evaluation_environment"]
            )
            report = closure_reports.get(environment)
            if (
                report is None
                or report.get("runtime_trace_digest")
                != game_trace.get("runtime_trace_digest")
                or report.get("actions_executed")
                != game_trace.get("action_count")
            ):
                raise ValueError(
                    "S5_TRACE_CLOSURE_GAME_BINDING_INVALID"
                )
    if (
        manifest.get("complete_inventory") is not True
        or manifest.get("all_complete") is not True
        or manifest.get("complete_execution_trace_coverage") is not True
        or manifest.get("operation_mode") != "offline"
        or manifest.get("privilege_stage") != "S5"
        or manifest.get("runtime_event_contains_environment_identity")
        is not False
        or manifest.get(
            "action_selection_receives_environment_identity"
        )
        is not False
    ):
        raise ValueError("S5_TRACE_MANIFEST_NOT_COMPLETE")
    return manifest


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Execute rendered-only S5 Runtime Student."
    )
    parser.add_argument("--environments-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--recordings-dir", type=Path)
    parser.add_argument("--trace-jsonl", type=Path)
    parser.add_argument("--trace-manifest", type=Path)
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
        trace_jsonl_path=args.trace_jsonl,
        trace_manifest_path=args.trace_manifest,
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
    "S5_EXECUTION_TRACE_MANIFEST_DIGEST_PREFIX",
    "S5_EXECUTION_TRACE_MANIFEST_SCHEMA_VERSION",
    "S5_RUNTIME_TRACE_REQUIRED_FIELDS",
    "S5_RUNTIME_TRACE_SUMMARY_FIELDS",
    "execute_s5_rendered_policy",
    "load_s5_closure_report",
    "load_s5_execution_trace_manifest",
    "run_s5_rendered_policy",
    "write_s5_execution_trace_artifact",
]
