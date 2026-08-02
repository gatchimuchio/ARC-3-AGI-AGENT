"""Executable M1 acceptance for the official ARC3 product I/O surface."""

from __future__ import annotations

import gc
import os
from pathlib import Path
from typing import Any, TypedDict

from arc_agi import Arcade, OperationMode  # type: ignore[import-untyped]
from arcengine import FrameDataRaw

from .generic_compute import (
    HybridRelationalInstructionBody,
    action_descriptors,
    represent_observation,
)
from .generic_env import OfflineGenericEnvironment
from .generic_runtime import GenericAGIRuntime
from .generic_session import ResourceContract, create_cognitive_session

M1_RUNTIME_SURFACE_VERSION = "arc3-product-m1-runtime-surface-v1"
M1_RUNTIME_SURFACE_EXIT = "OFFICIAL_RUNTIME_SURFACE_COMPLETE"
M1_POINTER_CATEGORIES = frozenset(
    {
        "object",
        "cell",
        "region",
        "boundary",
        "path",
        "ui",
        "candidate-position",
    }
)


class _SurfaceRow(TypedDict):
    game_ordinal: int
    raw_action_frame_count: int
    preserved_action_frame_count: int
    composited_view_preserved: bool
    normal_actions: list[int]
    legal_action_surface: list[int]
    represented_actions: list[int]
    pointer_categories: list[str]
    observation_failures: list[str]
    descriptor_failures: list[str]
    identity_failures: list[str]
    result_observation_failures: list[str]
    action_complete: bool
    full_reset: bool
    last_action_id: int
    win_level_count: int
    hds_authorization_valid: bool
    external_action_executed: bool
    reobservation_valid: bool
    result_action_frame_count: int


def _release_environment(environment: object | None) -> None:
    if environment is not None:
        session = getattr(environment, "_session", None)
        close = getattr(session, "close", None)
        if callable(close):
            close()
    gc.collect()


def inspect_official_runtime_surface(
    *,
    environments_dir: Path,
    recordings_dir: Path,
) -> dict[str, object]:
    """Measure the complete official initial I/O surface without game routing."""

    resolved_environments = environments_dir.resolve()
    resolved_recordings = recordings_dir.resolve()
    if not resolved_environments.is_dir():
        raise FileNotFoundError(
            "M1_ENVIRONMENT_DIRECTORY_MISSING:" + str(resolved_environments)
        )
    if os.getenv("OPERATION_MODE", "").strip().casefold() == "competition":
        raise PermissionError("M1_OFFLINE_COMPETITION_ENV_FORBIDDEN")
    resolved_recordings.mkdir(parents=True, exist_ok=True)
    arcade = Arcade(
        operation_mode=OperationMode.OFFLINE,
        environments_dir=str(resolved_environments),
        recordings_dir=str(resolved_recordings),
    )
    environments = tuple(
        sorted(arcade.get_environments(), key=lambda item: item.game_id)
    )
    cognitive_session = create_cognitive_session(
        p_bundle=HybridRelationalInstructionBody(),
        mode="VALIDATION",
        enable_cross_game_promotion=False,
        resource_contract=ResourceContract(action_budget_per_episode=1),
    )
    card_id = arcade.open_scorecard(tags=["product", "rev4", "m1-surface"])
    if not isinstance(card_id, str) or not card_id:
        raise RuntimeError("M1_SCORECARD_OPEN_FAILED")

    rows: list[_SurfaceRow] = []
    normal_action_union: set[int] = set()
    legal_action_union: set[int] = set()
    pointer_categories: set[str] = set()
    scorecard_closed = False
    try:
        for ordinal, advertised in enumerate(environments):
            environment: Any | None = None
            handle = None
            reason = "M1_SURFACE_INSPECTION"
            try:
                environment = arcade.make(
                    advertised.game_id,
                    scorecard_id=card_id,
                    save_recording=False,
                    include_frame_data=True,
                )
                if environment is None:
                    raise RuntimeError("M1_ENVIRONMENT_MAKE_RETURNED_NONE")
                raw = environment.observation_space
                if not isinstance(raw, FrameDataRaw):
                    raise TypeError("M1_INITIAL_FRAME_REQUIRED")
                adapter = OfflineGenericEnvironment(environment)
                observation = adapter.observe()
                raw_projection = adapter.frame_adapter.project(raw)
                observation_failures = observation.validate()
                identity_failures = (
                    cognitive_session.identity_boundary.inspect_decision_context(
                        observation
                    )
                )
                representation = represent_observation(
                    observation,
                    goal_tokens=("goal:progress",),
                )
                descriptors = action_descriptors(observation, representation)
                descriptor_failures = tuple(
                    sorted(
                        {
                            failure
                            for descriptor in descriptors
                            for failure in descriptor.validate(observation)
                        }
                    )
                )
                represented_actions = {
                    descriptor.action_id for descriptor in descriptors
                }
                row_pointer_categories = {
                    descriptor.semantic_key.split(":category:", 1)[1].split(":", 1)[0]
                    for descriptor in descriptors
                    if ":category:" in descriptor.semantic_key
                }
                normal_action_union.update(observation.available_actions)
                legal_action_union.update(observation.legal_action_surface)
                pointer_categories.update(row_pointer_categories)

                handle = cognitive_session.begin_episode()
                runtime_report = GenericAGIRuntime(
                    environment=adapter,
                    session=cognitive_session,
                    episode_handle=handle,
                ).run()
                reason = runtime_report.stop_reason
                if len(runtime_report.cycles) != 1:
                    raise RuntimeError("M1_SINGLE_CYCLE_TRACE_REQUIRED")
                cycle = runtime_report.cycles[0]
                result_observation = cycle.result_observation
                result_failures = (
                    result_observation.validate()
                    if result_observation is not None
                    else ("M1_RESULT_OBSERVATION_MISSING",)
                )
                result_identity_failures = (
                    cognitive_session.identity_boundary.inspect_decision_context(
                        result_observation
                    )
                    if result_observation is not None
                    else ("M1_RESULT_OBSERVATION_MISSING",)
                )
                authorization_valid = (
                    runtime_report.actions_executed == 1
                    and cycle.decision.external_action_authorized
                    and cycle.selected_candidate is not None
                    and len(cycle.authority_events) >= 3
                )
                reobservation_valid = (
                    result_observation is not None
                    and result_observation.action_complete
                    and len(result_observation.observation_history) >= 2
                    and not result_failures
                    and not result_identity_failures
                )
                rows.append(
                    {
                        "game_ordinal": ordinal,
                        "raw_action_frame_count": len(raw.frame),
                        "preserved_action_frame_count": (
                            observation.action_frame_count
                        ),
                        "composited_view_preserved": (
                            observation.composited_view
                            == raw_projection.composited_view
                        ),
                        "normal_actions": list(observation.available_actions),
                        "legal_action_surface": list(observation.legal_action_surface),
                        "represented_actions": sorted(represented_actions),
                        "pointer_categories": sorted(row_pointer_categories),
                        "observation_failures": list(observation_failures),
                        "descriptor_failures": list(descriptor_failures),
                        "identity_failures": list(
                            (*identity_failures, *result_identity_failures)
                        ),
                        "result_observation_failures": list(result_failures),
                        "action_complete": observation.action_complete,
                        "full_reset": observation.full_reset,
                        "last_action_id": observation.last_action_id,
                        "win_level_count": observation.win_level_count,
                        "hds_authorization_valid": authorization_valid,
                        "external_action_executed": (
                            runtime_report.actions_executed == 1
                        ),
                        "reobservation_valid": reobservation_valid,
                        "result_action_frame_count": (
                            result_observation.action_frame_count
                            if result_observation is not None
                            else 0
                        ),
                    }
                )
            except Exception as error:
                reason = type(error).__name__
                raise
            finally:
                if handle is not None:
                    cognitive_session.end_episode(
                        handle,
                        succeeded=False,
                        reason=reason,
                    )
                _release_environment(environment)
    finally:
        close_result = arcade.close_scorecard(card_id)
        scorecard_closed = close_result is not None

    failure_reasons: list[str] = []
    if len(environments) != 25 or len(rows) != 25:
        failure_reasons.append("M1_GAME_COVERAGE_MISMATCH")
    if sum(row["win_level_count"] for row in rows) != 183:
        failure_reasons.append("M1_LEVEL_TARGET_MISMATCH")
    if any(
        row["raw_action_frame_count"] != row["preserved_action_frame_count"]
        for row in rows
    ):
        failure_reasons.append("M1_ACTION_FRAME_PRESERVATION_FAILURE")
    if not all(bool(row["composited_view_preserved"]) for row in rows):
        failure_reasons.append("M1_COMPOSITED_VIEW_FAILURE")
    if normal_action_union != set(range(1, 8)):
        failure_reasons.append("M1_NORMAL_ACTION_SURFACE_MISMATCH")
    if legal_action_union != set(range(8)):
        failure_reasons.append("M1_LEGAL_ACTION_SURFACE_MISMATCH")
    if any(row["normal_actions"] != row["represented_actions"] for row in rows):
        failure_reasons.append("M1_ACTION_REPRESENTATION_FAILURE")
    if not M1_POINTER_CATEGORIES.issubset(pointer_categories):
        failure_reasons.append("M1_POINTER_CATEGORY_COVERAGE_FAILURE")
    if any(
        row["observation_failures"]
        or row["descriptor_failures"]
        or row["identity_failures"]
        or row["result_observation_failures"]
        for row in rows
    ):
        failure_reasons.append("M1_TYPED_OR_IDENTITY_BOUNDARY_FAILURE")
    if not all(bool(row["action_complete"]) for row in rows):
        failure_reasons.append("M1_ACTION_COMPLETE_FAILURE")
    if not all(bool(row["full_reset"]) for row in rows):
        failure_reasons.append("M1_INITIAL_FULL_RESET_FAILURE")
    if not all(row["last_action_id"] == 0 for row in rows):
        failure_reasons.append("M1_INITIAL_RESET_SURFACE_FAILURE")
    if not all(bool(row["hds_authorization_valid"]) for row in rows):
        failure_reasons.append("M1_HDS_AUTHORIZATION_FAILURE")
    if not all(bool(row["external_action_executed"]) for row in rows):
        failure_reasons.append("M1_EXTERNAL_ACTION_EXECUTION_FAILURE")
    if not all(bool(row["reobservation_valid"]) for row in rows):
        failure_reasons.append("M1_REOBSERVATION_FAILURE")
    if not scorecard_closed:
        failure_reasons.append("M1_SCORECARD_CLOSE_FAILURE")
    normalized_failures = tuple(sorted(set(failure_reasons)))
    return {
        "schema_version": M1_RUNTIME_SURFACE_VERSION,
        "operation_mode": "offline",
        "environment_source": "BUNDLED_OFFICIAL_SAMPLES",
        "advertised_game_count": len(environments),
        "inspected_game_count": len(rows),
        "total_win_level_count": sum(row["win_level_count"] for row in rows),
        "raw_action_frame_counts": [row["raw_action_frame_count"] for row in rows],
        "multi_frame_initial_game_count": sum(
            1 for row in rows if row["raw_action_frame_count"] > 1
        ),
        "normal_action_union": sorted(normal_action_union),
        "legal_action_union": sorted(legal_action_union),
        "pointer_categories": sorted(pointer_categories),
        "hds_authorized_game_count": sum(
            int(bool(row["hds_authorization_valid"])) for row in rows
        ),
        "external_action_game_count": sum(
            int(bool(row["external_action_executed"])) for row in rows
        ),
        "reobserved_game_count": sum(
            int(bool(row["reobservation_valid"])) for row in rows
        ),
        "single_cognitive_session_count": 1,
        "episode_count": len(rows),
        "scorecard_closed": scorecard_closed,
        "failure_reasons": list(normalized_failures),
        "exit_status": (
            M1_RUNTIME_SURFACE_EXIT
            if not normalized_failures
            else "M1_RUNTIME_SURFACE_INCOMPLETE"
        ),
        "rows": rows,
    }


__all__ = [
    "M1_POINTER_CATEGORIES",
    "M1_RUNTIME_SURFACE_EXIT",
    "M1_RUNTIME_SURFACE_VERSION",
    "inspect_official_runtime_surface",
]
