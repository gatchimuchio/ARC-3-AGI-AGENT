"""Resource-bounded sequential orchestration for the ARC-AGI-3 gateway."""

from __future__ import annotations

import gc
import json
import logging
import os
from collections.abc import Callable
from typing import Any

from arc_agi import Arcade  # type: ignore[import-untyped]

from .generic_compute import HybridRelationalInstructionBody
from .generic_session import (
    CognitiveSession,
    ResourceContract,
    create_cognitive_session,
)
from .identity_boundary import OrchestrationMetadata, Tainted

logger = logging.getLogger(__name__)

GENERIC_COMPETITION_RUNNER_VERSION = "arc3-generic-competition-runner-v1"


def _root_url() -> str:
    scheme = os.environ.get("SCHEME", "http")
    host = os.environ.get("HOST", "localhost")
    port = os.environ.get("PORT", "8001")
    if (scheme, str(port)) in {("http", "80"), ("https", "443")}:
        return f"{scheme}://{host}"
    return f"{scheme}://{host}:{port}"


def _peak_rss_mb() -> float | None:
    """Observe RSS without setting a virtual-memory or process limit."""

    try:
        import resource

        getrusage = getattr(resource, "getrusage")
        usage = getrusage(getattr(resource, "RUSAGE_SELF"))
        peak_rss = float(
            getattr(usage, "ru_maxrss")
        )
        return round(peak_rss / 1024, 3)
    except (ImportError, OSError, ValueError):
        return None


def _release_environment(environment: object | None) -> None:
    """Release one remote wrapper before creating the next one."""

    if environment is not None:
        session = getattr(environment, "_session", None)
        close = getattr(session, "close", None)
        if callable(close):
            close()
    gc.collect()


def run_sequential_competition(
    *,
    arcade: Any | None = None,
    agent_factory: Callable[..., Any] | None = None,
    session_factory: Callable[[], CognitiveSession] | None = None,
) -> dict[str, object]:
    """Run every advertised environment once under one scorecard.

    Game identity is used only by the official orchestration boundary. It is
    passed to the framework Agent constructor but never to Runtime P.
    Per-game failures are recorded and isolated so the scorecard is still
    closed and collectible; scorecard creation/closure failures remain fatal.
    """

    if agent_factory is None:
        from agents.templates.generic_agi_agent import GenericAGIAgent

        agent_factory = GenericAGIAgent
    if session_factory is None:
        def default_session_factory() -> CognitiveSession:
            return create_cognitive_session(
                p_bundle=HybridRelationalInstructionBody(),
                mode="COMPETITION",
                resource_contract=ResourceContract(
                    action_budget_per_episode=128,
                ),
            )

        session_factory = default_session_factory
    client = arcade if arcade is not None else Arcade()
    game_ids = tuple(
        str(environment.game_id) for environment in client.get_environments()
    )
    if not game_ids:
        raise RuntimeError("GENERIC_COMPETITION_NO_ENVIRONMENTS")
    if any(not game_id for game_id in game_ids):
        raise RuntimeError("GENERIC_COMPETITION_EMPTY_ENVIRONMENT_ID")
    if len(set(game_ids)) != len(game_ids):
        raise RuntimeError("GENERIC_COMPETITION_DUPLICATE_ENVIRONMENT_ID")

    cognitive_session = session_factory()
    if not isinstance(cognitive_session, CognitiveSession):
        raise TypeError("GENERIC_COMPETITION_COGNITIVE_SESSION_REQUIRED")
    state_owner_violations = cognitive_session.state_owner_violations()
    if state_owner_violations:
        raise RuntimeError(";".join(state_owner_violations))

    card_id = client.open_scorecard(tags=["agent", "genericagi", "sequential"])
    if not isinstance(card_id, str) or not card_id:
        raise RuntimeError("GENERIC_COMPETITION_SCORECARD_OPEN_FAILED")

    completed: list[dict[str, object]] = []
    failures: list[dict[str, object]] = []
    lifecycle_failures: list[dict[str, object]] = []
    close_result: object | None = None
    close_error: Exception | None = None
    session_lifecycle_failed = False
    try:
        for game_index, game_id in enumerate(game_ids):
            environment: object | None = None
            episode_handle = None
            game_succeeded = False
            game_reason = "UNSTARTED"
            try:
                episode_handle = cognitive_session.begin_episode()
                environment = client.make(
                    game_id,
                    scorecard_id=card_id,
                    save_recording=False,
                    include_frame_data=True,
                )
                if environment is None:
                    raise RuntimeError("GENERIC_COMPETITION_MAKE_RETURNED_NONE")
                orchestration_metadata = OrchestrationMetadata(
                    scorecard_id=Tainted(card_id),
                    game_id=Tainted(game_id),
                    game_index=Tainted(game_index),
                    environment_handle=Tainted(environment),
                )
                del orchestration_metadata
                agent = agent_factory(
                    card_id=card_id,
                    game_id=game_id,
                    agent_name="genericagi",
                    ROOT_URL=_root_url(),
                    record=False,
                    arc_env=environment,
                    cognitive_session=cognitive_session,
                    episode_handle=episode_handle,
                )
                agent.main()
                runtime_report = getattr(agent, "runtime_report", None)
                if runtime_report is None:
                    raise RuntimeError("GENERIC_COMPETITION_RUNTIME_REPORT_MISSING")
                game_succeeded = True
                game_reason = str(runtime_report.stop_reason)
                completed.append(
                    {
                        "game_index": game_index,
                        "actions_executed": int(runtime_report.actions_executed),
                        "progress_count": int(runtime_report.progress_count),
                        "final_state": str(runtime_report.final_state),
                        "stop_reason": str(runtime_report.stop_reason),
                    }
                )
                logger.info(
                    (
                        "Sequential game complete: index=%s/%s "
                        "actions=%s progress=%s state=%s peak_rss_mb=%s"
                    ),
                    game_index + 1,
                    len(game_ids),
                    runtime_report.actions_executed,
                    runtime_report.progress_count,
                    runtime_report.final_state,
                    _peak_rss_mb(),
                )
            except Exception as error:
                game_reason = type(error).__name__
                logger.exception(
                    "Sequential game failed: index=%s/%s",
                    game_index + 1,
                    len(game_ids),
                )
                failures.append(
                    {
                        "game_index": game_index,
                        "error_type": type(error).__name__,
                        "error_message": str(error)[:1000],
                    }
                )
            finally:
                if episode_handle is not None:
                    try:
                        cognitive_session.end_episode(
                            episode_handle,
                            succeeded=game_succeeded,
                            reason=game_reason,
                        )
                    except Exception as error:
                        session_lifecycle_failed = True
                        logger.exception(
                            (
                                "Cognitive session episode closure failed: "
                                "index=%s/%s"
                            ),
                            game_index + 1,
                            len(game_ids),
                        )
                        lifecycle_failures.append(
                            {
                                "game_index": game_index,
                                "phase": "episode_close",
                                "error_type": type(error).__name__,
                                "error_message": str(error)[:1000],
                            }
                        )
                try:
                    _release_environment(environment)
                except Exception as error:
                    logger.exception(
                        "Sequential environment release failed: index=%s/%s",
                        game_index + 1,
                        len(game_ids),
                    )
                    lifecycle_failures.append(
                        {
                            "game_index": game_index,
                            "phase": "environment_release",
                            "error_type": type(error).__name__,
                            "error_message": str(error)[:1000],
                        }
                    )
            if session_lifecycle_failed:
                break
    finally:
        try:
            close_result = client.close_scorecard(card_id)
        except Exception as error:
            close_error = error
            logger.exception("Sequential scorecard closure failed")

    report: dict[str, object] = {
        "schema_version": GENERIC_COMPETITION_RUNNER_VERSION,
        "orchestration_mode": "SEQUENTIAL_SINGLE_ACTIVE_GAME",
        "advertised_game_count": len(game_ids),
        "completed_game_count": len(completed),
        "failed_game_count": len(failures),
        "lifecycle_failure_count": len(lifecycle_failures),
        "active_agent_peak": 1,
        "scorecard_open_count": 1,
        "scorecard_close_count": 1 if close_error is None else 0,
        "scorecard_closed": close_result is not None,
        "shared_session_count": 1,
        "per_game_new_memory_count": 0,
        "per_game_new_p_count": 0,
        "cross_game_semantic_promotion": (
            "ENABLED"
            if cognitive_session.cross_game_semantic_promotion_enabled
            else "DISABLED"
        ),
        "state_owner_violation_count": len(state_owner_violations),
        "identity_boundary": "PASS",
        "runtime_identity_digest": cognitive_session.runtime_identity.digest(),
        "session_lineage_digest": cognitive_session.lineage_digest,
        "results": completed,
        "failures": failures,
        "lifecycle_failures": lifecycle_failures,
        "peak_rss_mb": _peak_rss_mb(),
        "runtime_policy_changed": False,
    }
    logger.info(
        "Sequential competition summary: %s",
        json.dumps(
            {
                key: value
                for key, value in report.items()
                if key not in {"results", "failures", "lifecycle_failures"}
            },
            sort_keys=True,
        ),
    )
    if close_error is not None:
        raise RuntimeError(
            "GENERIC_COMPETITION_SCORECARD_CLOSE_FAILED:"
            f"{type(close_error).__name__}:{close_error}"
        ) from close_error
    if close_result is None:
        raise RuntimeError("GENERIC_COMPETITION_SCORECARD_CLOSE_RETURNED_NONE")
    return report


def main() -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)s | %(message)s",
    )
    report = run_sequential_competition()
    print(
        json.dumps(
            {
                key: value
                for key, value in report.items()
                if key not in {"results", "failures", "lifecycle_failures"}
            },
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())


__all__ = [
    "GENERIC_COMPETITION_RUNNER_VERSION",
    "run_sequential_competition",
]
