from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field, replace
from unittest.mock import Mock

import numpy as np
import pytest
from arc_agi.local_wrapper import LocalEnvironmentWrapper  # type: ignore[import-untyped]
from arcengine import FrameDataRaw, GameAction, GameState

from arc3_agi_agent.evidence_binding import build_evidence_binding_key
from arc3_agi_agent.generic_env import OfflineGenericEnvironment
from arc3_agi_agent.generic_memory import SemanticMemory, semantic_record
from arc3_agi_agent.identity_boundary import IdentityBoundary, Tainted
from arc3_agi_agent.sample_observation import SampleFrameAdapter
from arc3_agi_agent.schema import canonical_json, digest_object


def _frame(values: list[list[int]], *, levels_completed: int = 0) -> FrameDataRaw:
    result = FrameDataRaw(
        game_id="orchestration-only",
        state=GameState.NOT_FINISHED,
        levels_completed=levels_completed,
        win_levels=3,
        available_actions=[1],
    )
    result.frame = [np.asarray(values, dtype=np.int8)]
    return result


class _FakeOfflineEnvironment(LocalEnvironmentWrapper):  # type: ignore[misc]
    def __init__(self, before: FrameDataRaw, after: FrameDataRaw) -> None:
        self._last_response = before
        self.after = after

    def step(
        self,
        action: GameAction,
        *,
        data: dict[str, int],
        reasoning: dict[str, str],
    ) -> FrameDataRaw:
        del action, data, reasoning
        self._last_response = self.after
        return self.after


def test_identity_boundary_single_walk_preserves_fail_closed_results() -> None:
    boundary = IdentityBoundary()

    assert boundary.inspect_decision_context({"safe": ("value", 1)}) == ()
    assert boundary.inspect_decision_context({"game_id": "forbidden"}) == (
        "$[0].game_id:FORBIDDEN_KEY",
        "$[0].game_id:ORCHESTRATION_KEY",
    )
    assert boundary.inspect_decision_context({"scorecard_id": "forbidden"}) == (
        "$[0].scorecard_id:ORCHESTRATION_KEY",
    )
    assert boundary.inspect_decision_context({"safe": Tainted("secret")}) == (
        "$[0]:TAINTED_VALUE",
    )
    with pytest.raises(TypeError):
        boundary.inspect_decision_context({"safe": {"unsupported"}})


def test_identity_boundary_ignores_explicit_nonserialized_cache_fields() -> None:
    @dataclass(frozen=True)
    class _DecisionValue:
        safe: str
        cache: object = field(metadata={"serialize": False})

    assert (
        IdentityBoundary().inspect_decision_context(
            _DecisionValue("visible", Tainted("cache-only"))
        )
        == ()
    )


def test_semantic_record_citation_cache_preserves_canonical_identity() -> None:
    record = semantic_record(
        memory_id="performance-cache-record",
        kind="HYPOTHESIS",
        statement="cache only immutable semantic identity",
        semantic_tokens=("goal:progress", "test:cache"),
        evidence=("event:cache",),
    )
    before = canonical_json(record)
    first = record.citation()
    second = record.citation()

    assert first is second
    assert first.content_digest == "semantic-record:" + digest_object(record)
    assert canonical_json(record) == before

    revised = replace(record, statement="revised immutable semantic identity")
    assert revised.citation().content_digest != first.content_digest


def test_semantic_region_digest_matches_canonical_contract() -> None:
    records = {
        identifier: semantic_record(
            memory_id=identifier,
            kind="HYPOTHESIS",
            statement=f"canonical region record {identifier}",
            semantic_tokens=(f"test:{identifier}",),
            evidence=(f"event:{identifier}",),
        )
        for identifier in ("b", "a")
    }
    canonical_digest = digest_object(tuple(records[key] for key in sorted(records)))

    assert SemanticMemory._active_digest_for(records) == (
        "semantic-active:" + canonical_digest
    )
    assert SemanticMemory._archive_digest_for(records) == (
        "semantic-archive:" + canonical_digest
    )


def test_cached_semantic_payload_is_deeply_immutable() -> None:
    record = semantic_record(
        memory_id="immutable-payload",
        kind="HYPOTHESIS",
        statement="cached payload cannot be changed behind its digest",
        semantic_tokens=("test:immutable",),
        evidence=("event:immutable",),
        payload={"nested": {"values": [1, 2]}},
    )
    nested = record.payload()["nested"]

    assert isinstance(nested, Mapping)
    assert nested["values"] == (1, 2)
    with pytest.raises(TypeError):
        nested["values"] = (3,)  # type: ignore[index]


def test_evidence_binding_cache_normalizes_sequence_inputs() -> None:
    first = build_evidence_binding_key(
        topology_tokens=["b", "a", "a"],
        relations=["right", "left"],
        descriptor_semantic_key="surface:1:action:1",
        action_id=1,
        target_role=None,
        payload_fields=[],
        predicted_effects=["VISIBLE_STATE_CHANGE"],
    )
    second = build_evidence_binding_key(
        topology_tokens=("a", "b"),
        relations=("left", "right"),
        descriptor_semantic_key="surface:1:action:1",
        action_id=1,
        target_role=None,
        payload_fields=(),
        predicted_effects=("VISIBLE_STATE_CHANGE",),
    )

    assert first == second
    assert first is second


def test_offline_environment_projects_each_raw_frame_once() -> None:
    before = _frame([[0, 0], [0, 1]])
    after = _frame([[0, 1], [0, 1]], levels_completed=1)
    adapter = Mock(wraps=SampleFrameAdapter())
    environment = OfflineGenericEnvironment(
        _FakeOfflineEnvironment(before, after),
        frame_adapter=adapter,
    )

    initial = environment.observe()
    repeated = environment.observe()
    result = environment.step(1, payload={}, request_id="project-once")

    assert initial == repeated
    assert result.progress_count == 1
    assert "LEVEL_PROGRESS" in result.visible_effects
    assert adapter.project.call_count == 2
