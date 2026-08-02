"""Product entrypoint for the endpoint-driven ARC3 completion agent."""

from __future__ import annotations

from arc_agi.local_wrapper import (  # type: ignore[import-untyped]
    LocalEnvironmentWrapper,
)

from arc3_agi_agent.generic_env import OfflineGenericEnvironment
from arc3_agi_agent.generic_types import GenericEnvironment

from .generic_agi_agent import GenericAGIAgent, GenericAGIAgentReport

ARC3_COMPLETION_AGENT_PRODUCT_VERSION = "arc3-completion-agent-product-v1.0"


class ARC3CompletionAgent(GenericAGIAgent):
    """Runnable product shell backed by the active C/J/M/P runtime.

    The current implementation intentionally reuses the proven official adapter,
    authority boundary, and GenericAGIRuntime. Product capability is upgraded by
    replacing the session P/J0/M0 bundle and its runtime configuration, not by
    creating a parallel agent path.
    """

    PRODUCT_ID = "ARC3CompletionAgent"
    PRODUCT_VERSION = ARC3_COMPLETION_AGENT_PRODUCT_VERSION

    def _runtime_environment(self) -> GenericEnvironment:
        """Select only the official I/O adapter; retain one C/J/M/P runtime."""

        if isinstance(self.arc_env, LocalEnvironmentWrapper):
            return OfflineGenericEnvironment(self.arc_env)
        return super()._runtime_environment()


__all__ = [
    "ARC3_COMPLETION_AGENT_PRODUCT_VERSION",
    "ARC3CompletionAgent",
    "GenericAGIAgentReport",
]
