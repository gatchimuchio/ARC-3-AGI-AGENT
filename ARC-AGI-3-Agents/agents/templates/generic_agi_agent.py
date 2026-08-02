"""Competition entrypoint for the identity-free GenericAGIRuntime."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Any

from arcengine import FrameData, FrameDataRaw, GameAction, GameState

from arc3_agi_agent.generic_env import CompetitionGenericEnvironment
from arc3_agi_agent.generic_runtime import GenericAGIRuntime
from arc3_agi_agent.generic_session import (
    CognitiveSession,
    EpisodeHandle,
)
from arc3_agi_agent.generic_types import GenericEnvironment

from ..agent import Agent

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class GenericAGIAgentReport:
    """Small orchestration report; the full rendered trace is not retained."""

    actions_executed: int
    progress_count: int
    final_state: str
    stop_reason: str
    runtime_report_digest: str
    failure_signatures: tuple[str, ...]
    no_fallback_used: bool
    runtime_identity_received: bool
    runtime_identity_digest: str
    session_lineage_digest: str
    identity_boundary_passed: bool
    memory_citation_count: int
    memory_citation_ids: tuple[str, ...]


class GenericAGIAgent(Agent):
    """Run one official game exclusively through HDS-authorized emissions."""

    MAX_ACTIONS = 128

    def __init__(
        self,
        *args: Any,
        cognitive_session: CognitiveSession,
        episode_handle: EpisodeHandle,
        max_actions: int | None = None,
        **kwargs: Any,
    ) -> None:
        selected_max_actions = (
            cognitive_session.resource_contract.action_budget_per_episode
            if max_actions is None
            else max_actions
        )
        if (
            isinstance(selected_max_actions, bool)
            or not isinstance(selected_max_actions, int)
            or not 1 <= selected_max_actions <= 100_000
        ):
            raise ValueError("GENERIC_COMPETITION_ACTION_BUDGET_INVALID")
        if (
            selected_max_actions
            != cognitive_session.resource_contract.action_budget_per_episode
        ):
            raise ValueError("GENERIC_COMPETITION_SESSION_BUDGET_MISMATCH")
        cognitive_session.require_episode(episode_handle)
        super().__init__(*args, **kwargs)
        self.cognitive_session = cognitive_session
        self.episode_handle = episode_handle
        self.MAX_ACTIONS = selected_max_actions
        self.action_counter = 0
        self.frames: list[FrameData] = []
        self.runtime_report: GenericAGIAgentReport | None = None

    def _runtime_environment(self) -> GenericEnvironment:
        """Build the identity-free remote adapter used by this entrypoint."""

        return CompetitionGenericEnvironment(self.arc_env)

    def main(self) -> None:
        """Execute the frozen generic C/J/M/P loop against one remote wrapper."""

        self.timer = time.time()
        try:
            current = self.arc_env.observation_space
            if not isinstance(current, FrameDataRaw) or current.is_empty():
                raise RuntimeError("GENERIC_COMPETITION_INITIAL_OBSERVATION_MISSING")
            self.append_frame(self._convert_raw_frame_data(current))
            report = GenericAGIRuntime(
                environment=self._runtime_environment(),
                session=self.cognitive_session,
                episode_handle=self.episode_handle,
            ).run()
            memory_citations = tuple(
                citation
                for cycle in report.cycles
                for citation in cycle.compute_result.memory_citations
            )
            self.action_counter = report.actions_executed
            self.runtime_report = GenericAGIAgentReport(
                actions_executed=report.actions_executed,
                progress_count=report.progress_count,
                final_state=report.final_state,
                stop_reason=report.stop_reason,
                runtime_report_digest=report.digest(),
                failure_signatures=report.failure_signatures,
                no_fallback_used=report.no_fallback_used,
                runtime_identity_received=report.runtime_identity_received,
                runtime_identity_digest=report.runtime_identity_digest,
                session_lineage_digest=report.session_lineage_digest,
                identity_boundary_passed=report.identity_boundary_passed,
                memory_citation_count=len(memory_citations),
                memory_citation_ids=tuple(
                    sorted({item.memory_id for item in memory_citations})
                ),
            )
            final_raw = self.arc_env.observation_space
            if isinstance(final_raw, FrameDataRaw):
                self.append_frame(self._convert_raw_frame_data(final_raw))
            logger.info(
                (
                    "GenericAGIRuntime finished: game=%s actions=%s progress=%s "
                    "state=%s stop=%s failures=%s digest=%s"
                ),
                self.game_id,
                report.actions_executed,
                report.progress_count,
                report.final_state,
                report.stop_reason,
                report.failure_signatures,
                report.digest(),
            )
        except Exception:
            logger.exception("GenericAGIRuntime competition execution failed")
            raise
        finally:
            self.cleanup()

    def is_done(
        self,
        frames: list[FrameData],
        latest_frame: FrameData,
    ) -> bool:
        del frames
        return latest_frame.state in {GameState.WIN, GameState.GAME_OVER}

    def choose_action(
        self,
        frames: list[FrameData],
        latest_frame: FrameData,
    ) -> GameAction:
        del frames, latest_frame
        raise PermissionError("GENERIC_DIRECT_ACTION_SELECTION_FORBIDDEN")

    def take_action(self, action: GameAction) -> FrameData | None:
        del action
        raise PermissionError("GENERIC_DIRECT_ACTION_EMISSION_FORBIDDEN")

    def do_action_request(self, action: GameAction) -> FrameData:
        del action
        raise PermissionError("GENERIC_DIRECT_ENVIRONMENT_STEP_FORBIDDEN")


__all__ = ["GenericAGIAgent", "GenericAGIAgentReport"]
