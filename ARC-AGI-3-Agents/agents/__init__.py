"""Lazy public surface for the optional ARC-AGI-3 agent implementations.

Importing a lightweight submodule such as ``agents.recorder`` must not import
every LLM, LangGraph, or observability dependency. Agent classes are resolved
only when callers request the corresponding export or registry entry.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator, Mapping
from importlib import import_module
from typing import Any, Final

from .recorder import Recorder

_load_dotenv: Callable[[], object] | None
try:
    from dotenv import load_dotenv as _dotenv_import
except ImportError:  # pragma: no cover - dotenv is a declared runtime dependency
    _load_dotenv = None
else:
    _load_dotenv = _dotenv_import

if _load_dotenv is not None:
    _load_dotenv()

_EXPORT_IMPORTS: Final[dict[str, tuple[str, str]]] = {
    "Agent": (".agent", "Agent"),
    "Playback": (".agent", "Playback"),
    "Swarm": (".swarm", "Swarm"),
    "Random": (".templates.random_agent", "Random"),
    "LangGraphFunc": (
        ".templates.langgraph_functional_agent",
        "LangGraphFunc",
    ),
    "LangGraphTextOnly": (
        ".templates.langgraph_functional_agent",
        "LangGraphTextOnly",
    ),
    "LangGraphThinking": (
        ".templates.langgraph_thinking",
        "LangGraphThinking",
    ),
    "LangGraphRandom": (
        ".templates.langgraph_random_agent",
        "LangGraphRandom",
    ),
    "Layer0SampleAgent": (
        ".templates.layer0_sample_agent",
        "Layer0SampleAgent",
    ),
    "P10SampleAgent": (
        ".templates.p10_sample_agent",
        "P10SampleAgent",
    ),
    "GenericAGIAgent": (
        ".templates.generic_agi_agent",
        "GenericAGIAgent",
    ),
    "LLM": (".templates.llm_agents", "LLM"),
    "FastLLM": (".templates.llm_agents", "FastLLM"),
    "ReasoningLLM": (".templates.llm_agents", "ReasoningLLM"),
    "GuidedLLM": (".templates.llm_agents", "GuidedLLM"),
    "ReasoningAgent": (
        ".templates.reasoning_agent",
        "ReasoningAgent",
    ),
    "SmolCodingAgent": (
        ".templates.smolagents",
        "SmolCodingAgent",
    ),
    "SmolVisionAgent": (
        ".templates.smolagents",
        "SmolVisionAgent",
    ),
    "MultiModalLLM": (".templates.multimodal", "MultiModalLLM"),
}

_AGENT_IMPORTS: Final[dict[str, tuple[str, str]]] = {
    "random": _EXPORT_IMPORTS["Random"],
    "langgraphfunc": _EXPORT_IMPORTS["LangGraphFunc"],
    "langgraphtextonly": _EXPORT_IMPORTS["LangGraphTextOnly"],
    "langgraphthinking": _EXPORT_IMPORTS["LangGraphThinking"],
    "langgraphrandom": _EXPORT_IMPORTS["LangGraphRandom"],
    "llm": _EXPORT_IMPORTS["LLM"],
    "fastllm": _EXPORT_IMPORTS["FastLLM"],
    "reasoningllm": _EXPORT_IMPORTS["ReasoningLLM"],
    "guidedllm": _EXPORT_IMPORTS["GuidedLLM"],
    "reasoningagent": _EXPORT_IMPORTS["ReasoningAgent"],
    "smolcodingagent": _EXPORT_IMPORTS["SmolCodingAgent"],
    "smolvisionagent": _EXPORT_IMPORTS["SmolVisionAgent"],
    "multimodalllm": _EXPORT_IMPORTS["MultiModalLLM"],
    "genericagi": _EXPORT_IMPORTS["GenericAGIAgent"],
}


def _load(module_name: str, attribute_name: str) -> Any:
    module = import_module(module_name, package=__name__)
    return getattr(module, attribute_name)


class _LazyAgentRegistry(Mapping[str, type[Any]]):
    """Resolve only the selected agent and keep recording names dynamic."""

    @staticmethod
    def _recordings() -> tuple[str, ...]:
        return tuple(sorted(set(Recorder.list())))

    def __getitem__(self, name: str) -> type[Any]:
        target = _AGENT_IMPORTS.get(name)
        if target is not None:
            value = _load(*target)
            if not isinstance(value, type):
                raise TypeError(f"agent export is not a class: {name}")
            return value
        if name in self._recordings():
            value = _load(*_EXPORT_IMPORTS["Playback"])
            if not isinstance(value, type):
                raise TypeError("Playback export is not a class")
            return value
        raise KeyError(name)

    def __iter__(self) -> Iterator[str]:
        names = tuple(_AGENT_IMPORTS)
        recordings = tuple(
            name for name in self._recordings() if name not in _AGENT_IMPORTS
        )
        return iter(names + recordings)

    def __len__(self) -> int:
        return len(tuple(iter(self)))


AVAILABLE_AGENTS: Mapping[str, type[Any]] = _LazyAgentRegistry()


def __getattr__(name: str) -> Any:
    target = _EXPORT_IMPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    value = _load(*target)
    globals()[name] = value
    return value


__all__ = [
    "AVAILABLE_AGENTS",
    "Agent",
    "FastLLM",
    "GuidedLLM",
    "GenericAGIAgent",
    "LLM",
    "LangGraphFunc",
    "LangGraphRandom",
    "LangGraphTextOnly",
    "LangGraphThinking",
    "Layer0SampleAgent",
    "MultiModalLLM",
    "P10SampleAgent",
    "Playback",
    "Random",
    "ReasoningAgent",
    "ReasoningLLM",
    "Recorder",
    "SmolCodingAgent",
    "SmolVisionAgent",
    "Swarm",
]
