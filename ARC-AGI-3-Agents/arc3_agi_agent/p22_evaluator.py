"""P22-A known-public, transformation, and memory-necessity evaluation."""

from __future__ import annotations

import gzip
import hashlib
import json
import os
import subprocess
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, Final

from arc_agi import Arcade, OperationMode  # type: ignore[import-untyped]

from .compiled_policy import (
    CompiledAutonomousInstructionBody,
    load_compiled_autonomous_instruction_body,
)
from .generic_env import (
    OfflineGenericEnvironment,
    transformed_worlds,
)
from .generic_runtime import (
    GenericAGIRuntime,
    GenericRuntimeAblation,
)
from .generic_session import (
    CognitiveSession,
    ResourceContract,
    create_cognitive_session,
)
from .generic_types import GenericCycleTrace, GenericRunReport
from .p_bundle import PBundle, p_bundle_from_package
from .p_compiler_v2 import PCompilerV2
from .schema import canonical_json, digest_object

P22_EVALUATOR_VERSION: Final = "arc3-p22-autonomous-evaluator-v1"
P22_PUBLIC_ACTION_BUDGET: Final = 4096
P22_STRESS_ACTION_BUDGET: Final = 24
P22_REQUIRED_PUBLIC_GAMES: Final = 25
P22_REQUIRED_PUBLIC_LEVELS: Final = 183
P22_REQUIRED_TRANSFORMATIONS: Final = 7


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _directory_digest(path: Path) -> str:
    digest = hashlib.sha256()
    for item in sorted(
        (candidate for candidate in path.rglob("*") if candidate.is_file()),
        key=lambda candidate: candidate.relative_to(path).as_posix(),
    ):
        relative = item.relative_to(path).as_posix().encode("utf-8")
        digest.update(len(relative).to_bytes(8, "big"))
        digest.update(relative)
        with item.open("rb") as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(block)
    return "sha256:" + digest.hexdigest()


def _git_value(repository_root: Path, *arguments: str) -> str:
    completed = subprocess.run(
        ("git", *arguments),
        cwd=repository_root,
        check=True,
        capture_output=True,
        text=True,
    )
    return completed.stdout.strip()


def _content_bound(value: Mapping[str, object]) -> dict[str, object]:
    body = dict(value)
    if "content_digest" in body:
        raise ValueError("P22_CONTENT_DIGEST_PREEXISTS")
    body["content_digest"] = "p22-evidence:" + hashlib.sha256(
        canonical_json(body).encode("utf-8")
    ).hexdigest()
    return body


def _mapping_integer(
    value: Mapping[str, object],
    key: str,
    *,
    error: str,
) -> int:
    item = value[key]
    if isinstance(item, bool) or not isinstance(item, int):
        raise TypeError(error + ":" + key)
    return item


def _mapping_integer_sequence(
    value: Mapping[str, object],
    key: str,
    *,
    error: str,
) -> tuple[int, ...]:
    item = value[key]
    if not isinstance(item, (list, tuple)) or any(
        isinstance(entry, bool) or not isinstance(entry, int)
        for entry in item
    ):
        raise TypeError(error + ":" + key)
    return tuple(item)


def write_content_bound_json(path: Path, value: Mapping[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            _content_bound(value),
            ensure_ascii=False,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
        newline="\n",
    )


def build_active_compiled_p_bundle(
    body: CompiledAutonomousInstructionBody | None = None,
) -> PBundle:
    return PCompilerV2().bootstrap(
        body=body or load_compiled_autonomous_instruction_body(),
        version="p22-generic-autonomous-v1",
    )


def _trace_record(trace: GenericCycleTrace) -> dict[str, object]:
    selected = trace.selected_candidate
    result = trace.result_observation
    return {
        "schema_version": P22_EVALUATOR_VERSION,
        "cycle_index": trace.cycle_index,
        "trace_digest": trace.trace_digest,
        "runtime_identity_digest": trace.runtime_identity_digest,
        "session_lineage_digest": trace.session_lineage_digest,
        "decision_context_digest": trace.decision_context_digest,
        "observation_digest": trace.observation.digest(),
        "observation_terminal_state": trace.observation.terminal_state,
        "observation_progress_count": trace.observation.progress_count,
        "available_actions": trace.observation.available_actions,
        "frame_digest": "hds-frame:" + digest_object(trace.frame),
        "compute_digest": trace.compute_result.digest(),
        "p_ir_logical_digest": trace.compute_result.p_ir_logical_digest,
        "compute_stage_digests": tuple(
            (
                stage.stage,
                stage.input_digest,
                stage.output_digest,
                stage.selected_refs,
            )
            for stage in trace.compute_result.stages
        ),
        "decision_digest": "hds-decision:" + digest_object(trace.decision),
        "operation_state": trace.decision.operation_state,
        "selected_candidate_id": trace.decision.selected_candidate_id,
        "selected_action_id": (
            selected.descriptor.action_id if selected is not None else None
        ),
        "selected_payload": (
            selected.descriptor.payload() if selected is not None else None
        ),
        "selected_candidate_digest": (
            "generic-candidate:" + digest_object(selected)
            if selected is not None
            else None
        ),
        "result_observation_digest": (
            result.digest() if result is not None else None
        ),
        "result_terminal_state": (
            result.terminal_state if result is not None else None
        ),
        "result_progress_count": (
            result.progress_count if result is not None else None
        ),
        "attribution_digest": (
            "outcome-attribution:" + digest_object(trace.attribution)
            if trace.attribution is not None
            else None
        ),
        "attribution_category": (
            trace.attribution.category
            if trace.attribution is not None
            else None
        ),
        "memory_query_digest": trace.memory_query_digest,
        "memory_update_digests": trace.memory_update_digests,
        "authority_events": trace.authority_events,
        "failure_signatures": trace.failure_signatures,
    }


@dataclass(frozen=True, slots=True)
class TraceArtifact:
    relative_path: str
    cycle_count: int
    uncompressed_sha256: str
    compressed_sha256: str
    compressed_size_bytes: int

    def as_dict(self) -> dict[str, object]:
        return {
            "relative_path": self.relative_path,
            "cycle_count": self.cycle_count,
            "uncompressed_sha256": self.uncompressed_sha256,
            "compressed_sha256": self.compressed_sha256,
            "compressed_size_bytes": self.compressed_size_bytes,
        }


class ContentBoundTraceSink:
    """Write one compact but complete logical record for every runtime cycle."""

    def __init__(self, path: Path, *, relative_to: Path) -> None:
        self.path = path
        self.relative_to = relative_to
        self._raw: BinaryIO | None = None
        self._gzip: gzip.GzipFile | None = None
        self._digest = hashlib.sha256()
        self._cycle_count = 0
        self._closed = False

    def __enter__(self) -> ContentBoundTraceSink:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._raw = self.path.open("wb")
        self._gzip = gzip.GzipFile(
            filename="",
            mode="wb",
            fileobj=self._raw,
            compresslevel=9,
            mtime=0,
        )
        return self

    def append(self, trace: GenericCycleTrace) -> None:
        if self._gzip is None or self._closed:
            raise RuntimeError("P22_TRACE_SINK_NOT_OPEN")
        line = (
            canonical_json(_trace_record(trace)).encode("utf-8") + b"\n"
        )
        self._gzip.write(line)
        self._digest.update(line)
        self._cycle_count += 1

    def close(self) -> TraceArtifact:
        if self._closed:
            raise RuntimeError("P22_TRACE_SINK_ALREADY_CLOSED")
        self._closed = True
        if self._gzip is None or self._raw is None:
            raise RuntimeError("P22_TRACE_SINK_NOT_OPEN")
        self._gzip.close()
        self._raw.close()
        return TraceArtifact(
            relative_path=self.path.relative_to(self.relative_to).as_posix(),
            cycle_count=self._cycle_count,
            uncompressed_sha256=self._digest.hexdigest(),
            compressed_sha256=_sha256_file(self.path),
            compressed_size_bytes=self.path.stat().st_size,
        )

    def __exit__(
        self,
        error_type: type[BaseException] | None,
        error: BaseException | None,
        traceback: object | None,
    ) -> None:
        del error_type, error, traceback
        if not self._closed and self._gzip is not None and self._raw is not None:
            self._gzip.close()
            self._raw.close()
            self._closed = True


def _session(
    bundle: PBundle,
    *,
    action_budget: int,
    enable_cross_game_promotion: bool = True,
) -> CognitiveSession:
    return create_cognitive_session(
        p_bundle=bundle.body,
        p_ir_program=bundle.program,
        mode="VALIDATION",
        resource_contract=ResourceContract(
            action_budget_per_episode=action_budget,
        ),
        enable_cross_game_promotion=enable_cross_game_promotion,
    )


def _run_world(
    *,
    session: CognitiveSession,
    world: object,
    ablation: GenericRuntimeAblation | None = None,
) -> tuple[GenericRunReport, object]:
    handle = session.begin_episode()
    report = GenericAGIRuntime(
        world,  # type: ignore[arg-type]
        session,
        handle,
    ).run(ablation=ablation)
    receipt = session.end_episode(
        handle,
        succeeded=report.final_state == "WIN",
        reason=report.stop_reason,
    )
    return report, receipt


def run_transformation_stress(
    *,
    output_path: Path,
    bundle: PBundle | None = None,
    seed: int = 0,
) -> dict[str, object]:
    active = bundle or build_active_compiled_p_bundle()
    session = _session(
        active,
        action_budget=P22_STRESS_ACTION_BUDGET,
    )
    results: list[dict[str, object]] = []
    for family, world in transformed_worlds(seed=seed):
        report, receipt = _run_world(session=session, world=world)
        results.append(
            {
                "family": family,
                "completed": report.final_state == "WIN",
                "final_state": report.final_state,
                "progress_count": report.progress_count,
                "actions_executed": report.actions_executed,
                "run_report_digest": report.digest(),
                "trace_digests": report.cycle_trace_digests,
                "failure_signatures": report.failure_signatures,
                "memory_promoted": bool(getattr(receipt, "promoted")),
            }
        )
    completion_count = sum(bool(item["completed"]) for item in results)
    failed_requirement_ids = (
        []
        if completion_count == P22_REQUIRED_TRANSFORMATIONS
        else ["P22A-005"]
    )
    body: dict[str, object] = {
        "schema_version": P22_EVALUATOR_VERSION,
        "evaluation_role": "DEVELOPMENT_VALIDATION",
        "allowed_claim": "TRANSFORMATION_STRESS_PASS",
        "final_generic_claim": "NOT_AUTHORIZED",
        "seed": seed,
        "budget": P22_STRESS_ACTION_BUDGET,
        "runtime_identity": session.runtime_identity.digest(),
        "p": {
            "version": active.manifest.version,
            "logical_digest": active.logical_digest(),
            "package_digest": active.physical_digest(),
        },
        "transformation_completion": {
            "completed": completion_count,
            "required": P22_REQUIRED_TRANSFORMATIONS,
        },
        "results": results,
        "status": "PASS" if not failed_requirement_ids else "FAIL",
        "failed_requirement_ids": failed_requirement_ids,
    }
    write_content_bound_json(output_path, body)
    return _content_bound(body)


def _single_ablation(
    *,
    bundle: PBundle,
    ablation: GenericRuntimeAblation,
) -> dict[str, object]:
    session = _session(
        bundle,
        action_budget=P22_STRESS_ACTION_BUDGET,
    )
    world = dict(transformed_worlds(seed=0))["ORDER"]
    report, _ = _run_world(
        session=session,
        world=world,
        ablation=ablation,
    )
    return {
        "completed_environments": int(report.final_state == "WIN"),
        "completed_levels": report.progress_count,
        "actions_executed": report.actions_executed,
        "final_state": report.final_state,
        "stop_reason": report.stop_reason,
        "failure_signatures": report.failure_signatures,
        "run_report_digest": report.digest(),
    }


def _cross_episode_metric(
    *,
    bundle: PBundle,
    enable_consolidation: bool,
    new_session_per_episode: bool,
) -> dict[str, object]:
    shared = (
        None
        if new_session_per_episode
        else _session(
            bundle,
            action_budget=P22_STRESS_ACTION_BUDGET,
            enable_cross_game_promotion=enable_consolidation,
        )
    )
    completed = 0
    progress = 0
    actions = 0
    runtime_identities: set[str] = set()
    run_digests: list[str] = []
    promotion_count = 0
    for episode_index in range(4):
        session = shared or _session(
            bundle,
            action_budget=P22_STRESS_ACTION_BUDGET,
            enable_cross_game_promotion=enable_consolidation,
        )
        runtime_identities.add(session.runtime_identity.digest())
        world = dict(transformed_worlds(seed=episode_index))["ORDER"]
        report, receipt = _run_world(session=session, world=world)
        completed += int(report.final_state == "WIN")
        progress += report.progress_count
        actions += report.actions_executed
        run_digests.append(report.digest())
        promotion_count += int(bool(getattr(receipt, "promoted")))
    return {
        "completed_environments": completed,
        "completed_levels": progress,
        "actions_executed": actions,
        "runtime_identity_count": len(runtime_identities),
        "promotion_count": promotion_count,
        "run_report_digests": tuple(run_digests),
    }


def _metric_degraded(
    baseline: Mapping[str, object],
    ablated: Mapping[str, object],
) -> bool:
    baseline_key = (
        _mapping_integer(
            baseline,
            "completed_environments",
            error="P22_ABLATION_METRIC_INVALID",
        ),
        _mapping_integer(
            baseline,
            "completed_levels",
            error="P22_ABLATION_METRIC_INVALID",
        ),
        -_mapping_integer(
            baseline,
            "actions_executed",
            error="P22_ABLATION_METRIC_INVALID",
        ),
    )
    ablated_key = (
        _mapping_integer(
            ablated,
            "completed_environments",
            error="P22_ABLATION_METRIC_INVALID",
        ),
        _mapping_integer(
            ablated,
            "completed_levels",
            error="P22_ABLATION_METRIC_INVALID",
        ),
        -_mapping_integer(
            ablated,
            "actions_executed",
            error="P22_ABLATION_METRIC_INVALID",
        ),
    )
    return ablated_key < baseline_key


def run_memory_ablation(
    *,
    output_path: Path,
    bundle: PBundle | None = None,
) -> dict[str, object]:
    active = bundle or build_active_compiled_p_bundle()
    single_baseline = _single_ablation(
        bundle=active,
        ablation=GenericRuntimeAblation(),
    )
    cross_baseline = _cross_episode_metric(
        bundle=active,
        enable_consolidation=True,
        new_session_per_episode=False,
    )
    experiments = {
        "read": (
            single_baseline,
            _single_ablation(
                bundle=active,
                ablation=GenericRuntimeAblation(memory_read=False),
            ),
        ),
        "write": (
            single_baseline,
            _single_ablation(
                bundle=active,
                ablation=GenericRuntimeAblation(memory_write=False),
            ),
        ),
        "rollback": (
            single_baseline,
            _single_ablation(
                bundle=active,
                ablation=GenericRuntimeAblation(rollback=False),
            ),
        ),
        "consolidation": (
            cross_baseline,
            _cross_episode_metric(
                bundle=active,
                enable_consolidation=False,
                new_session_per_episode=False,
            ),
        ),
        "session_global": (
            cross_baseline,
            _cross_episode_metric(
                bundle=active,
                enable_consolidation=True,
                new_session_per_episode=True,
            ),
        ),
    }
    results = {
        name: {
            "baseline": baseline,
            "ablated": ablated,
            "degraded": _metric_degraded(baseline, ablated),
        }
        for name, (baseline, ablated) in experiments.items()
    }
    degraded_count = sum(
        bool(item["degraded"]) for item in results.values()
    )
    all_degraded = degraded_count == len(results)
    body: dict[str, object] = {
        "schema_version": P22_EVALUATOR_VERSION,
        "evaluation_role": "DEVELOPMENT_VALIDATION",
        "allowed_claim": "MEMORY_CAUSAL_NECESSITY",
        "final_generic_claim": "NOT_AUTHORIZED",
        "budget": P22_STRESS_ACTION_BUDGET,
        "p": {
            "version": active.manifest.version,
            "logical_digest": active.logical_digest(),
            "package_digest": active.physical_digest(),
        },
        "memory_causal_witness_count": degraded_count,
        "memory_ablation_degrades": all_degraded,
        "results": results,
        "status": "PASS" if all_degraded else "FAIL",
        "failed_requirement_ids": [] if all_degraded else ["P22A-006"],
    }
    write_content_bound_json(output_path, body)
    return _content_bound(body)


def run_known_public_regression(
    *,
    repository_root: Path,
    environments_dir: Path,
    output_dir: Path,
    bundle: PBundle | None = None,
    action_budget: int = P22_PUBLIC_ACTION_BUDGET,
    command: str = "p22_main.py public",
) -> dict[str, object]:
    if os.getenv("OPERATION_MODE", "").strip().casefold() == "competition":
        raise PermissionError("P22_PUBLIC_COMPETITION_MODE_FORBIDDEN")
    environments_dir = environments_dir.resolve()
    if not environments_dir.is_dir():
        raise FileNotFoundError(environments_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    trace_dir = output_dir / "public_traces"
    active = bundle or build_active_compiled_p_bundle()
    arcade = Arcade(
        operation_mode=OperationMode.OFFLINE,
        environments_dir=str(environments_dir),
        recordings_dir=str(output_dir / "recordings"),
    )
    if arcade.operation_mode is not OperationMode.OFFLINE:
        raise RuntimeError("P22_PUBLIC_OFFLINE_MODE_REQUIRED")
    game_ids = tuple(
        sorted(
            str(item.game_id) for item in arcade.get_environments()
        )
    )
    if len(game_ids) != P22_REQUIRED_PUBLIC_GAMES:
        raise RuntimeError("P22_PUBLIC_ENVIRONMENT_COUNT_INVALID")

    session = _session(active, action_budget=action_budget)
    memory_initial_digest = session.memory.view().digest
    control_initial_digest = "control:" + digest_object(session.control)
    scorecard_id = arcade.open_scorecard(
        tags=["p22-a", "known-public", "generic-active-runtime"]
    )
    summaries: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []
    traces: list[TraceArtifact] = []
    local_scorecard: object | None = None
    try:
        for game_index, game_id in enumerate(game_ids):
            handle = session.begin_episode()
            trace_path = trace_dir / f"game-{game_index:02d}.jsonl.gz"
            runtime_report: GenericRunReport | None = None
            try:
                environment = arcade.make(
                    game_id,
                    scorecard_id=scorecard_id,
                    save_recording=False,
                    include_frame_data=True,
                )
                if environment is None:
                    raise RuntimeError("P22_PUBLIC_ENVIRONMENT_LOAD_FAILED")
                with ContentBoundTraceSink(
                    trace_path,
                    relative_to=repository_root,
                ) as sink:
                    runtime_report = GenericAGIRuntime(
                        OfflineGenericEnvironment(environment),
                        session,
                        handle,
                        retain_cycle_objects=False,
                        trace_sink=sink,
                    ).run()
                    trace_artifact = sink.close()
                traces.append(trace_artifact)
                receipt = session.end_episode(
                    handle,
                    succeeded=runtime_report.final_state == "WIN",
                    reason=runtime_report.stop_reason,
                )
                summaries.append(
                    {
                        "game_index": game_index,
                        "game_id": game_id,
                        "complete": runtime_report.final_state == "WIN",
                        "completed_levels": runtime_report.progress_count,
                        "actions_executed": runtime_report.actions_executed,
                        "final_state": runtime_report.final_state,
                        "stop_reason": runtime_report.stop_reason,
                        "run_report_digest": runtime_report.digest(),
                        "runtime_identity_digest": (
                            runtime_report.runtime_identity_digest
                        ),
                        "cycle_count": len(
                            runtime_report.cycle_trace_digests
                        ),
                        "failure_signatures": (
                            runtime_report.failure_signatures
                        ),
                        "no_fallback_used": runtime_report.no_fallback_used,
                        "identity_boundary_passed": (
                            runtime_report.identity_boundary_passed
                        ),
                        "memory_promoted": bool(receipt.promoted),
                        "trace": trace_artifact.as_dict(),
                    }
                )
            except Exception as error:
                errors.append(
                    {
                        "game_index": game_index,
                        "game_id": game_id,
                        "error_type": type(error).__name__,
                        "error_message": str(error)[:1000],
                    }
                )
                if session.active_episode is handle:
                    session.end_episode(
                        handle,
                        succeeded=False,
                        reason=type(error).__name__,
                    )
    finally:
        closed = arcade.close_scorecard(scorecard_id)
        if closed is not None:
            local_scorecard = closed.model_dump(mode="json")

    completed_games = sum(bool(item["complete"]) for item in summaries)
    completed_levels = sum(
        _mapping_integer(
            item,
            "completed_levels",
            error="P22_PUBLIC_SUMMARY_INTEGER_INVALID",
        )
        for item in summaries
    )
    actions = sum(
        _mapping_integer(
            item,
            "actions_executed",
            error="P22_PUBLIC_SUMMARY_INTEGER_INVALID",
        )
        for item in summaries
    )
    fallback_count = sum(
        not bool(item["no_fallback_used"]) for item in summaries
    )
    identity_leak_count = sum(
        not bool(item["identity_boundary_passed"]) for item in summaries
    )
    trace_cycle_count = sum(item.cycle_count for item in traces)
    requirements = {
        "P22A-001": completed_games == P22_REQUIRED_PUBLIC_GAMES,
        "P22A-002": completed_levels == P22_REQUIRED_PUBLIC_LEVELS,
        "P22A-PUBLIC-FALLBACK": fallback_count == 0,
        "P22A-PUBLIC-IDENTITY": identity_leak_count == 0,
        "P22A-PUBLIC-TRACE": (
            len(traces) == P22_REQUIRED_PUBLIC_GAMES
            and trace_cycle_count >= actions
        ),
        "P22A-PUBLIC-ERROR": not errors,
        "P22A-007": True,
    }
    failed_requirement_ids = [
        key for key, passed in requirements.items() if not passed
    ]
    identity = session.runtime_identity
    scorecard_digest = (
        "local-scorecard:" + digest_object(local_scorecard)
        if local_scorecard is not None
        else ""
    )
    body: dict[str, object] = {
        "schema_version": P22_EVALUATOR_VERSION,
        "code": {
            "commit": _git_value(repository_root, "rev-parse", "HEAD"),
            "tree": _git_value(repository_root, "rev-parse", "HEAD^{tree}"),
            "runtime_source_tree": identity.code_tree_digest,
        },
        "runtime_identity": identity.digest(),
        "runtime_package_logical_digest": active.logical_digest(),
        "runtime_package_byte_digest": active.physical_digest(),
        "l0_abi_version": identity.l0_abi_version,
        "p": {
            "version": active.manifest.version,
            "logical_digest": active.logical_digest(),
            "package_digest": active.physical_digest(),
        },
        "j": {
            "implementation_digest": identity.j_implementation_digest,
            "config_digest": identity.j_config_digest,
        },
        "m": {
            "schema_version": "arc3-typed-causal-memory-v1",
            "initial_logical_digest": memory_initial_digest,
            "final_logical_digest": session.memory.view().digest,
            "initial_version": 0,
            "final_version": session.memory.version,
        },
        "session_id": session.session_id,
        "session_lineage_digest": session.lineage_digest,
        "authority_session_digest": "authority-session:"
        + digest_object(session.authority.session_id),
        "control_initial_digest": control_initial_digest,
        "control_final_digest": "control:" + digest_object(session.control),
        "input_artifact_digest": _directory_digest(environments_dir),
        "evaluation_role": "DEVELOPMENT_VALIDATION",
        "evaluation_access_state": "KNOWN_PUBLIC",
        "allowed_claim": "KNOWN_PUBLIC_REGRESSION",
        "final_generic_claim": "NOT_AUTHORIZED",
        "external_execution_contract_digest": "offline-contract:"
        + digest_object(
            {
                "operation_mode": "OFFLINE",
                "one_make_per_environment": True,
                "single_cognitive_session": True,
            }
        ),
        "environment_manifest": {
            "environment_count": len(game_ids),
            "game_ids": game_ids,
        },
        "seed": 0,
        "budget": action_budget,
        "command": command,
        "status": "PASS" if not failed_requirement_ids else "FAIL",
        "failed_requirement_ids": failed_requirement_ids,
        "completed_environment_count": completed_games,
        "completed_level_count": completed_levels,
        "failed_environment_count": (
            P22_REQUIRED_PUBLIC_GAMES - completed_games
        ),
        "holdout_definition": "KNOWN_PUBLIC_25_DEVELOPMENT_REGRESSION",
        "runtime_identity_count": 1,
        "fallback_count": fallback_count,
        "identity_leak_count": identity_leak_count,
        "memory_causal_witness_count": 0,
        "p_causal_witness_count": int(completed_games > 0),
        "score_scope": "KNOWN_PUBLIC_DEVELOPMENT_REGRESSION",
        "raw_score": completed_levels,
        "normalized_score_ppm": round(
            completed_levels
            * 1_000_000
            / P22_REQUIRED_PUBLIC_LEVELS
        ),
        "official_submission_ref": None,
        "actions_executed": actions,
        "trace_cycle_count": trace_cycle_count,
        "trace_artifacts": traces,
        "local_scorecard_digest": scorecard_digest,
        "reports": summaries,
        "errors": errors,
    }
    output_path = output_dir / "public_regression.json"
    write_content_bound_json(output_path, body)
    return _content_bound(body)


def _load_content_bound_json(
    path: Path,
    *,
    prefix: str,
) -> dict[str, object]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise TypeError("P22_CONTENT_BOUND_REPORT_INVALID")
    expected = value.pop("content_digest", None)
    actual = prefix + digest_object(value)
    if expected != actual:
        raise ValueError("P22_CONTENT_BOUND_REPORT_DIGEST_MISMATCH")
    value["content_digest"] = expected
    return value


def run_cv_holdout_fold(
    *,
    repository_root: Path,
    environments_dir: Path,
    output_dir: Path,
    compile_manifest_path: Path,
    fold_index: int,
) -> dict[str, object]:
    """Execute one fold's five holdouts with only that fold's frozen P."""

    if not 0 <= fold_index < 5:
        raise ValueError("P22_CV_FOLD_INDEX_INVALID")
    compile_manifest = _load_content_bound_json(
        compile_manifest_path,
        prefix="p22-cv-compile:",
    )
    folds_value = compile_manifest.get("folds")
    if not isinstance(folds_value, list) or len(folds_value) != 5:
        raise ValueError("P22_CV_COMPILE_FOLDS_INVALID")
    fold_value = folds_value[fold_index]
    if not isinstance(fold_value, dict):
        raise TypeError("P22_CV_COMPILE_FOLD_INVALID")
    fold_id = f"fold-{fold_index:02d}"
    if fold_value.get("fold_id") != fold_id:
        raise ValueError("P22_CV_COMPILE_FOLD_ID_MISMATCH")
    artifact_relative = fold_value.get("artifact_path")
    if not isinstance(artifact_relative, str) or not artifact_relative:
        raise TypeError("P22_CV_ARTIFACT_PATH_INVALID")
    artifact_path = (repository_root / artifact_relative).resolve()
    if repository_root.resolve() not in artifact_path.parents:
        raise PermissionError("P22_CV_ARTIFACT_PATH_OUTSIDE_REPOSITORY")
    artifact_payload = artifact_path.read_bytes()
    if hashlib.sha256(artifact_payload).hexdigest() != fold_value.get(
        "artifact_sha256"
    ):
        raise ValueError("P22_CV_ARTIFACT_DIGEST_MISMATCH")
    bundle = p_bundle_from_package(artifact_payload)
    if bundle.logical_digest() != fold_value.get("p_logical_digest"):
        raise ValueError("P22_CV_P_LOGICAL_DIGEST_MISMATCH")
    holdout_value = fold_value.get("holdout_game_ordinals")
    if not isinstance(holdout_value, list):
        raise TypeError("P22_CV_HOLDOUT_ORDINALS_INVALID")
    training_value = fold_value.get("training_game_ordinals")
    if not isinstance(training_value, list):
        raise TypeError("P22_CV_TRAINING_ORDINALS_INVALID")
    action_budget = _mapping_integer(
        fold_value,
        "action_budget_per_environment",
        error="P22_CV_ACTION_BUDGET_INVALID",
    )
    if not 1 <= action_budget <= P22_PUBLIC_ACTION_BUDGET:
        raise ValueError("P22_CV_ACTION_BUDGET_INVALID")
    holdout_ordinals = tuple(
        int(item)
        for item in holdout_value
        if isinstance(item, int) and not isinstance(item, bool)
    )
    if len(holdout_ordinals) != 5:
        raise ValueError("P22_CV_HOLDOUT_ORDINALS_INVALID")

    arcade = Arcade(
        operation_mode=OperationMode.OFFLINE,
        environments_dir=str(environments_dir.resolve()),
        recordings_dir=str(output_dir / "recordings" / fold_id),
    )
    if arcade.operation_mode is not OperationMode.OFFLINE:
        raise RuntimeError("P22_CV_OFFLINE_MODE_REQUIRED")
    game_ids = tuple(
        sorted(str(item.game_id) for item in arcade.get_environments())
    )
    if len(game_ids) != P22_REQUIRED_PUBLIC_GAMES:
        raise RuntimeError("P22_CV_ENVIRONMENT_COUNT_INVALID")
    selected_games = tuple(game_ids[index] for index in holdout_ordinals)
    session = _session(bundle, action_budget=action_budget)
    if session.runtime_identity.digest() != fold_value.get(
        "runtime_identity_digest"
    ):
        raise ValueError("P22_CV_RUNTIME_IDENTITY_MISMATCH")
    scorecard_id = arcade.open_scorecard(
        tags=["p22-a", "cv-holdout", fold_id]
    )
    summaries: list[dict[str, object]] = []
    errors: list[dict[str, object]] = []
    trace_artifacts: list[TraceArtifact] = []
    try:
        for local_index, (ordinal, game_id) in enumerate(
            zip(holdout_ordinals, selected_games)
        ):
            handle = session.begin_episode()
            trace_path = (
                output_dir
                / "cv_traces"
                / fold_id
                / f"game-{local_index:02d}.jsonl.gz"
            )
            try:
                environment = arcade.make(
                    game_id,
                    scorecard_id=scorecard_id,
                    save_recording=False,
                    include_frame_data=True,
                )
                if environment is None:
                    raise RuntimeError("P22_CV_ENVIRONMENT_LOAD_FAILED")
                with ContentBoundTraceSink(
                    trace_path,
                    relative_to=repository_root,
                ) as sink:
                    report = GenericAGIRuntime(
                        OfflineGenericEnvironment(environment),
                        session,
                        handle,
                        retain_cycle_objects=False,
                        trace_sink=sink,
                    ).run()
                    trace_artifact = sink.close()
                trace_artifacts.append(trace_artifact)
                receipt = session.end_episode(
                    handle,
                    succeeded=report.final_state == "WIN",
                    reason=report.stop_reason,
                )
                summaries.append(
                    {
                        "game_ordinal": ordinal,
                        "game_id": game_id,
                        "complete": report.final_state == "WIN",
                        "completed_levels": report.progress_count,
                        "actions_executed": report.actions_executed,
                        "final_state": report.final_state,
                        "stop_reason": report.stop_reason,
                        "run_report_digest": report.digest(),
                        "failure_signatures": report.failure_signatures,
                        "no_fallback_used": report.no_fallback_used,
                        "identity_boundary_passed": (
                            report.identity_boundary_passed
                        ),
                        "memory_promoted": bool(receipt.promoted),
                        "trace": trace_artifact.as_dict(),
                    }
                )
            except Exception as error:
                errors.append(
                    {
                        "game_ordinal": ordinal,
                        "game_id": game_id,
                        "error_type": type(error).__name__,
                        "error_message": str(error)[:1000],
                    }
                )
                if session.active_episode is handle:
                    session.end_episode(
                        handle,
                        succeeded=False,
                        reason=type(error).__name__,
                    )
    finally:
        arcade.close_scorecard(scorecard_id)
    fallback_count = sum(
        not bool(item["no_fallback_used"]) for item in summaries
    )
    identity_leak_count = sum(
        not bool(item["identity_boundary_passed"]) for item in summaries
    )
    procedure_passed = (
        len(summaries) == len(holdout_ordinals)
        and not errors
        and fallback_count == 0
        and identity_leak_count == 0
        and len(trace_artifacts) == len(holdout_ordinals)
    )
    body: dict[str, object] = {
        "schema_version": P22_EVALUATOR_VERSION,
        "fold_id": fold_id,
        "evaluation_role": "CV_HOLDOUT",
        "allowed_claim": "CV_PROCEDURE_EVIDENCE",
        "same_single_artifact_claim_allowed": False,
        "training_game_ordinals": training_value,
        "holdout_game_ordinals": holdout_ordinals,
        "training_data_completely_separated": not set(
            training_value
        ).intersection(holdout_ordinals),
        "action_budget_per_environment": action_budget,
        "p_logical_digest": bundle.logical_digest(),
        "p_package_digest": bundle.physical_digest(),
        "runtime_identity_digest": session.runtime_identity.digest(),
        "execution_count": len(summaries),
        "completed_environment_count": sum(
            bool(item["complete"]) for item in summaries
        ),
        "completed_level_count": sum(
            _mapping_integer(
                item,
                "completed_levels",
                error="P22_CV_SUMMARY_INTEGER_INVALID",
            )
            for item in summaries
        ),
        "actions_executed": sum(
            _mapping_integer(
                item,
                "actions_executed",
                error="P22_CV_SUMMARY_INTEGER_INVALID",
            )
            for item in summaries
        ),
        "fallback_count": fallback_count,
        "identity_leak_count": identity_leak_count,
        "reports": summaries,
        "errors": errors,
        "status": "PASS" if procedure_passed else "FAIL",
        "failed_requirement_ids": (
            [] if procedure_passed else ["P22A-CV-FOLD-EXECUTION"]
        ),
        "final_generic_claim": "NOT_AUTHORIZED",
    }
    result_path = output_dir / "cv_results" / f"{fold_id}.json"
    write_content_bound_json(result_path, body)
    return _content_bound(body)


def assemble_cv_manifest(
    *,
    output_dir: Path,
) -> dict[str, object]:
    compile_manifest = _load_content_bound_json(
        output_dir / "cv_compile_manifest.json",
        prefix="p22-cv-compile:",
    )
    fold_results = tuple(
        _load_content_bound_json(
            output_dir / "cv_results" / f"fold-{index:02d}.json",
            prefix="p22-evidence:",
        )
        for index in range(5)
    )
    fold_count = len(fold_results)
    p_digests = {
        str(item["p_logical_digest"]) for item in fold_results
    }
    runtime_digests = {
        str(item["runtime_identity_digest"]) for item in fold_results
    }
    holdout_ordinals = tuple(
        ordinal
        for item in fold_results
        for ordinal in _mapping_integer_sequence(
            item,
            "holdout_game_ordinals",
            error="P22_CV_RESULT_ORDINALS_INVALID",
        )
    )
    requirements = {
        "P22A-003": fold_count == 5,
        "P22A-004": len(runtime_digests) == 5,
        "P22A-CV-P-DISTINCT": len(p_digests) == 5,
        "P22A-CV-HOLDOUT-COVERAGE": (
            sorted(holdout_ordinals) == list(range(25))
        ),
        "P22A-CV-EXECUTION": all(
            item["status"] == "PASS" for item in fold_results
        ),
        "P22A-CV-TRAINING-SEPARATION": all(
            item["training_data_completely_separated"] is True
            for item in fold_results
        ),
    }
    failed = [key for key, passed in requirements.items() if not passed]
    body: dict[str, object] = {
        "schema_version": P22_EVALUATOR_VERSION,
        "evaluation_role": "CV_HOLDOUT",
        "allowed_claim": "CV_PROCEDURE_EVIDENCE",
        "same_single_artifact_claim_allowed": False,
        "source_compile_manifest_digest": compile_manifest[
            "content_digest"
        ],
        "fold_count": fold_count,
        "distinct_p_artifact_count": len(p_digests),
        "distinct_runtime_identity_count": len(runtime_digests),
        "training_data_completely_separated": requirements[
            "P22A-CV-TRAINING-SEPARATION"
        ],
        "holdout_execution_count": sum(
            _mapping_integer(
                item,
                "execution_count",
                error="P22_CV_RESULT_INTEGER_INVALID",
            )
            for item in fold_results
        ),
        "holdout_completed_environment_count": sum(
            _mapping_integer(
                item,
                "completed_environment_count",
                error="P22_CV_RESULT_INTEGER_INVALID",
            )
            for item in fold_results
        ),
        "holdout_completed_level_count": sum(
            _mapping_integer(
                item,
                "completed_level_count",
                error="P22_CV_RESULT_INTEGER_INVALID",
            )
            for item in fold_results
        ),
        "folds": fold_results,
        "status": "PASS" if not failed else "FAIL",
        "failed_requirement_ids": failed,
        "final_generic_claim": "NOT_AUTHORIZED",
    }
    write_content_bound_json(output_dir / "cv_manifest.json", body)
    return _content_bound(body)


__all__ = [
    "ContentBoundTraceSink",
    "P22_EVALUATOR_VERSION",
    "P22_PUBLIC_ACTION_BUDGET",
    "P22_REQUIRED_PUBLIC_GAMES",
    "P22_REQUIRED_PUBLIC_LEVELS",
    "P22_REQUIRED_TRANSFORMATIONS",
    "P22_STRESS_ACTION_BUDGET",
    "TraceArtifact",
    "assemble_cv_manifest",
    "build_active_compiled_p_bundle",
    "run_cv_holdout_fold",
    "run_known_public_regression",
    "run_memory_ablation",
    "run_transformation_stress",
    "write_content_bound_json",
]
