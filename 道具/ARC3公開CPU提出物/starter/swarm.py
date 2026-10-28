from __future__ import annotations

import json
import logging
import os
from threading import Thread
from typing import TYPE_CHECKING, Optional, Type

from arc_agi import Arcade, OperationMode
from arc_agi.scorecard import EnvironmentScorecard

if TYPE_CHECKING:
    from .agent import Agent

logger = logging.getLogger()


class Swarm:
    """Orchestration for many agents playing many ARC-AGI-3 games."""

    GAMES: list[str]
    ROOT_URL: str
    COUNT: int
    agent_name: str
    agent_class: Type[Agent]
    threads: list[Thread]
    agents: list[Agent]
    record_games: list[str]
    cleanup_threads: list[Thread]
    headers: dict[str, str]
    card_id: Optional[str]
    _arc: Arcade

    def __init__(
        self,
        agent: str,
        ROOT_URL: str,
        games: list[str],
        tags: list[str] = [],
    ) -> None:
        from . import AVAILABLE_AGENTS

        self.GAMES = games
        self.ROOT_URL = ROOT_URL
        self.agent_name = agent
        self.agent_class = AVAILABLE_AGENTS[agent]
        self.threads = []
        self.agents = []
        self.cleanup_threads = []
        self.headers = {
            "X-API-Key": os.getenv("ARC_API_KEY", ""),
            "Accept": "application/json",
        }
        self.tags = tags.copy() if tags is not None else []
        self._arc = Arcade()

        # Set up base tags for tracing
        if self.agent_name.endswith(".recording.jsonl"):
            # Extract GUID from playback filename
            # Format: game.agent.count.guid.recording.jsonl
            parts = self.agent_name.split(".")
            guid = parts[-3] if len(parts) >= 4 else "unknown"
            self.tags.extend(["playback", guid])
        else:
            self.tags.extend(["agent", self.agent_name])

    def main(self) -> EnvironmentScorecard | None:
        """Run each game independently; close once and propagate failures."""
        import json as _json
        from threading import Lock

        failures = []
        counters = []
        failure_lock = Lock()
        def failed(kind: str) -> None:
            with failure_lock:
                failures.append(kind)
        def run_one(agent: Agent, counter: dict) -> None:
            try:
                agent.main()
                if getattr(agent, "_safe_stop", False):
                    failed("agent_safe_stop")
                elif counter["responses"] == 0:
                    failed("no_step_response")
            except BaseException:
                # Do not disclose exception content, game identifier, or frame.
                failed("agent")

        card_id = self.open_scorecard()
        if not card_id:
            raise RuntimeError("scorecard open failed")
        self.card_id = card_id
        scorecard = None
        try:
            for game in self.GAMES:
                try:
                    env = self._arc.make(game, scorecard_id=card_id)
                    if env is None:
                        raise RuntimeError("environment unavailable")
                    counter = {"attempts": 0, "responses": 0}
                    original_step = env.step
                    def counted_step(*args, _original=original_step, _counter=counter, **kwargs):
                        _counter["attempts"] += 1
                        response = _original(*args, **kwargs)
                        _counter["responses"] += int(response is not None)
                        return response
                    env.step = counted_step
                    agent = self.agent_class(card_id=card_id, game_id=game,
                                             agent_name=self.agent_name, ROOT_URL=self.ROOT_URL,
                                             record=False, arc_env=env, tags=self.tags)
                    self.agents.append(agent)
                    counters.append(counter)
                except (Exception, SystemExit):
                    failed("init")
            for agent, counter in zip(self.agents, counters, strict=True):
                thread = Thread(target=run_one, args=(agent, counter), daemon=True)
                self.threads.append(thread)
                try:
                    thread.start()
                except (Exception, SystemExit):
                    self.threads.pop()
                    failed("thread_start")
            for thread in self.threads:
                thread.join()
        finally:
            try:
                scorecard = self.close_scorecard(card_id)
                if scorecard is None:
                    failed("close")
            except (Exception, SystemExit):
                failed("close")
            # Independent cleanup means one failure does not skip other agents.
            for agent in self.agents:
                try:
                    agent.cleanup(scorecard)
                except (Exception, SystemExit):
                    failed("cleanup")
        summary = {"constructed": len(self.agents), "started": len(self.threads), "failed": len(failures),
                   "agent_iterations": sum(getattr(a, "action_counter", 0) for a in self.agents),
                   "sdk_step_attempts": sum(c["attempts"] for c in counters),
                   "sdk_step_nonnull_responses": sum(c["responses"] for c in counters),
                   "failure_categories": {kind: failures.count(kind) for kind in sorted(set(failures))},
                   "close_ok": "close" not in failures}
        print("ARC3_RUN_SUMMARY " + _json.dumps(summary, sort_keys=True), flush=True)
        if failures:
            raise RuntimeError("one or more ARC3 run stages failed")
        return scorecard

    def open_scorecard(self) -> str:
        return self._arc.open_scorecard(tags=self.tags)  # type: ignore[no-any-return]

    def close_scorecard(self, card_id: str) -> Optional[EnvironmentScorecard]:
        self.card_id = None

        return self._arc.close_scorecard(card_id)

    def cleanup(self, scorecard: Optional[EnvironmentScorecard] = None) -> None:
        """Cleanup all agents."""
        for a in self.agents:
            a.cleanup(scorecard)
        if hasattr(self, "_session"):
            self._session.close()
