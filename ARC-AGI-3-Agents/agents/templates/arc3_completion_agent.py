"""Product entrypoint for the endpoint-driven ARC3 completion agent."""

from __future__ import annotations

from .generic_agi_agent import GenericAGIAgent, GenericAGIAgentReport

ARC3_COMPLETION_AGENT_PRODUCT_VERSION = "arc3-completion-agent-product-v0.1"


class ARC3CompletionAgent(GenericAGIAgent):
    """Runnable product shell backed by the active C/J/M/P runtime.

    The current implementation intentionally reuses the proven official adapter,
    authority boundary, and GenericAGIRuntime. Product capability is upgraded by
    replacing the session P/J0/M0 bundle and its runtime configuration, not by
    creating a parallel agent path.
    """

    PRODUCT_ID = "ARC3CompletionAgent"
    PRODUCT_VERSION = ARC3_COMPLETION_AGENT_PRODUCT_VERSION


__all__ = [
    "ARC3_COMPLETION_AGENT_PRODUCT_VERSION",
    "ARC3CompletionAgent",
    "GenericAGIAgentReport",
]
