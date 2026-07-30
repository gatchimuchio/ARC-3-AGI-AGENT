from __future__ import annotations

import ast
from pathlib import Path
from typing import Mapping

import numpy as np
import pytest

from arc3_agi_agent.compiled_policy import (
    COMPILED_POLICY_HISTORY_LIMIT,
    compiled_policy_feature_vector,
    load_compiled_autonomous_instruction_body,
)
from arc3_agi_agent.generic_compute import (
    action_descriptors,
    represent_observation,
)
from arc3_agi_agent.generic_runtime import (
    GenericAGIRuntime,
    GenericRuntimeAblation,
    _action_effect_record,
)
from arc3_agi_agent.generic_session import (
    ResourceContract,
    create_cognitive_session,
)
from arc3_agi_agent.generic_types import (
    ActionEffectRecord,
    GenericObservation,
)
from arc3_agi_agent.p_bundle import p_bundle_from_package
from arc3_agi_agent.p_compiler_v2 import PCompilerV2
from arc3_agi_agent.s5_policy import (
    S5HistoryRecord,
    load_s5_rendered_policy_body,
    s5_feature_vector_from_render,
)
from arc3_agi_agent.taint import COORDINATE_PROVENANCE_CURRENT_RENDER

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
PACKAGE_ROOT = REPOSITORY_ROOT / "ARC-AGI-3-Agents"
CORPUS_PATH = (
    REPOSITORY_ROOT
    / "analysis"
    / "teacher"
    / "S5_RENDERED_POLICY_TRAINING_CORPUS.npz"
)


def _arrays() -> dict[str, np.ndarray]:
    with np.load(CORPUS_PATH, allow_pickle=False) as loaded:
        return {
            name: np.array(loaded[name], copy=True)
            for name in loaded.files
        }


def _surface(arrays: Mapping[str, np.ndarray], index: int) -> tuple[int, ...]:
    return tuple(
        int(item) for item in np.flatnonzero(arrays["available"][index])
    )


def _histories_before(
    arrays: Mapping[str, np.ndarray],
    index: int,
) -> tuple[tuple[S5HistoryRecord, ...], tuple[ActionEffectRecord, ...]]:
    ordinal = arrays["game_ordinal"][index]
    legacy: tuple[S5HistoryRecord, ...] = ()
    generic: tuple[ActionEffectRecord, ...] = ()
    for prior in range(max(0, index - COMPILED_POLICY_HISTORY_LIMIT), index):
        if arrays["game_ordinal"][prior] != ordinal:
            continue
        action_id = int(arrays["actions"][prior])
        horizontal = int(arrays["targets"][prior, 0])
        vertical = int(arrays["targets"][prior, 1])
        target_palette = (
            int(arrays["frames"][prior, vertical, horizontal])
            if action_id == 6
            else 0
        )
        visible_change = bool(
            np.any(
                arrays["frames"][prior]
                != arrays["frames"][prior + 1]
            )
        )
        compatibility_reset = bool(
            arrays["level_compatibility_reset"][prior]
        )
        legacy_record = S5HistoryRecord(
            action_id=action_id,
            horizontal=horizontal,
            vertical=vertical,
            target_palette=target_palette,
            visible_change=visible_change,
            compatibility_reset=compatibility_reset,
        )
        generic_record = ActionEffectRecord(
            action_id=action_id,
            payload_items=(
                (("x", horizontal), ("y", vertical))
                if action_id == 6
                else ()
            ),
            target_palette=target_palette,
            visible_change=visible_change,
            compatibility_reset=compatibility_reset,
        )
        legacy = (*legacy, legacy_record)[-COMPILED_POLICY_HISTORY_LIMIT:]
        generic = (*generic, generic_record)[-COMPILED_POLICY_HISTORY_LIMIT:]
    return legacy, generic


def _observation(
    arrays: Mapping[str, np.ndarray],
    index: int,
    *,
    signature: str | None = None,
) -> GenericObservation:
    matrix = tuple(
        tuple(int(cell) for cell in row)
        for row in arrays["frames"][index]
    )
    return GenericObservation(
        signature=signature or f"compiled-policy-test:{index}",
        available_actions=_surface(arrays, index),
        rendered_layers=(matrix,),
        terminal_state="NOT_FINISHED",
        action_payload_schema=(
            ((6, ("x", "y")),)
            if 6 in _surface(arrays, index)
            else ()
        ),
    )


def test_action_effect_history_ignores_non_policy_interface_layers() -> None:
    board = ((0, 1), (2, 3))
    before = GenericObservation(
        signature="before",
        available_actions=(1,),
        rendered_layers=(((0, 0), (0, 0)), board),
        terminal_state="NOT_FINISHED",
        progress_count=0,
    )
    interface_only = GenericObservation(
        signature="interface-only",
        available_actions=(1,),
        rendered_layers=(((1, 0), (0, 0)), board),
        terminal_state="NOT_FINISHED",
        progress_count=0,
    )
    board_change = GenericObservation(
        signature="board-change",
        available_actions=(1,),
        rendered_layers=(
            ((1, 0), (0, 0)),
            ((0, 1), (2, 4)),
        ),
        terminal_state="NOT_FINISHED",
        progress_count=0,
    )

    assert (
        _action_effect_record(
            action_id=1,
            payload={},
            before=before,
            after=interface_only,
        ).visible_change
        is False
    )
    assert (
        _action_effect_record(
            action_id=1,
            payload={},
            before=interface_only,
            after=board_change,
        ).visible_change
        is True
    )


def test_migrated_policy_matches_development_reference() -> None:
    arrays = _arrays()
    legacy_body = load_s5_rendered_policy_body()
    generic_body = load_compiled_autonomous_instruction_body()

    for index in (0, 9, 10, 535, 8647, 10_732):
        surface = _surface(arrays, index)
        legacy_history, generic_history = _histories_before(arrays, index)
        legacy_features = s5_feature_vector_from_render(
            arrays["frames"][index],
            surface,
            legacy_history,
        )
        generic_features = compiled_policy_feature_vector(
            arrays["frames"][index],
            surface,
            generic_history,
        )
        assert np.array_equal(generic_features, legacy_features)
        assert generic_body.action_heads[surface].predict(
            generic_features
        ) == legacy_body.action_heads[surface].predict(legacy_features)
        assert generic_body.predict(
            _observation(arrays, index),
            generic_history,
        ).action_id == int(arrays["actions"][index])


def test_same_render_changes_action_only_through_passive_m() -> None:
    arrays = _arrays()
    body = load_compiled_autonomous_instruction_body()
    first = 9
    second = 10
    assert np.array_equal(arrays["frames"][first], arrays["frames"][second])
    assert np.array_equal(
        arrays["available"][first],
        arrays["available"][second],
    )
    _, first_history = _histories_before(arrays, first)
    _, second_history = _histories_before(arrays, second)

    assert body.predict(_observation(arrays, first), first_history).action_id == 6
    assert body.predict(_observation(arrays, second), second_history).action_id == 3


def test_pointer_is_derived_from_current_render() -> None:
    arrays = _arrays()
    body = load_compiled_autonomous_instruction_body()
    _, history = _histories_before(arrays, 9)
    observation = _observation(arrays, 9)
    representation = represent_observation(
        observation,
        goal_tokens=("goal:progress",),
    )
    result = body.query(
        representation,
        action_descriptors(observation, representation),
        (),
        observation=observation,
        action_history=history,
    )
    selected = max(result.predictions, key=lambda item: item.prior).descriptor

    assert selected.action_id == 6
    assert selected.coordinate_provenance == (
        COORDINATE_PROVENANCE_CURRENT_RENDER
    )
    assert selected.coordinate_observation_digest == observation.digest()
    assert set(selected.payload()) == {"x", "y"}


class _ResetOnlyWorld:
    def __init__(self, observation: GenericObservation) -> None:
        self._observation = observation
        self.step_count = 0
        self.reset_count = 0

    def observe(self) -> GenericObservation:
        return self._observation

    def step(
        self,
        action_id: int,
        *,
        payload: Mapping[str, int],
        request_id: str,
    ) -> GenericObservation:
        del action_id, payload, request_id
        self.step_count += 1
        raise AssertionError("normal action must not execute for rollback")

    def reset_level(self, *, request_id: str) -> GenericObservation:
        assert request_id
        self.reset_count += 1
        matrix = [list(row) for row in self._observation.rendered_layers[-1]]
        matrix[0][0] = (matrix[0][0] + 1) % 16
        return GenericObservation(
            signature="reset-only-world:after",
            available_actions=self._observation.available_actions,
            rendered_layers=(
                tuple(tuple(row) for row in matrix),
            ),
            terminal_state="NOT_FINISHED",
            visible_effects=("LEVEL_RESET",),
            action_payload_schema=self._observation.action_payload_schema,
        )


def test_p_proposed_rollback_requires_hds_capability_and_updates_m() -> None:
    arrays = _arrays()
    observation = _observation(
        arrays,
        8647,
        signature="reset-only-world:before",
    )
    body = load_compiled_autonomous_instruction_body()
    assert body.predict(observation, ()).action_id == 0
    session = create_cognitive_session(
        p_bundle=body,
        resource_contract=ResourceContract(action_budget_per_episode=1),
    )
    handle = session.begin_episode()
    world = _ResetOnlyWorld(observation)

    report = GenericAGIRuntime(world, session, handle).run()

    assert world.step_count == 0
    assert world.reset_count == 1
    assert report.actions_executed == 1
    assert report.cycles[0].decision.operation_state == "ROLLBACK"
    assert report.cycles[0].selected_candidate is None
    assert report.cycles[0].attribution is not None
    assert report.cycles[0].attribution.action_semantic_key == "control:rollback"
    assert session.action_history.view()[-1].action_id == 0
    assert session.action_history.view()[-1].compatibility_reset is True
    assert len(report.cycles[0].authority_events) >= 3
    session.end_episode(handle, succeeded=False, reason=report.stop_reason)


def test_game_over_is_deferred_to_the_compiled_reset_cycle() -> None:
    arrays = _arrays()
    index = 535
    original = _observation(arrays, index)
    game_over = GenericObservation(
        signature="compiled-game-over",
        available_actions=original.available_actions,
        rendered_layers=original.rendered_layers,
        terminal_state="GAME_OVER",
        progress_count=1,
        action_payload_schema=original.action_payload_schema,
    )
    _, history = _histories_before(arrays, index)
    body = load_compiled_autonomous_instruction_body()

    assert int(arrays["actions"][index]) == 0
    assert body.predict(game_over, history).action_id == 0
    assert body.explicit_rollback_cycle_required(game_over) is True
    assert body.explicit_rollback_cycle_required(original) is False


class _TraceSink:
    def __init__(self) -> None:
        self.digests: list[str] = []

    def append(self, trace: object) -> None:
        self.digests.append(str(getattr(trace, "trace_digest")))


def test_full_trace_can_stream_without_retaining_cycle_objects() -> None:
    arrays = _arrays()
    observation = _observation(
        arrays,
        8647,
        signature="streamed-reset-world:before",
    )
    body = load_compiled_autonomous_instruction_body()
    session = create_cognitive_session(
        p_bundle=body,
        resource_contract=ResourceContract(action_budget_per_episode=1),
    )
    handle = session.begin_episode()
    sink = _TraceSink()

    report = GenericAGIRuntime(
        _ResetOnlyWorld(observation),
        session,
        handle,
        retain_cycle_objects=False,
        trace_sink=sink,
    ).run()

    assert report.cycles == ()
    assert report.cycle_trace_digests == tuple(sink.digests)
    assert len(report.cycle_trace_digests) == 1
    assert report.digest().startswith("generic-run:")
    session.end_episode(handle, succeeded=False, reason=report.stop_reason)


def test_rollback_ablation_blocks_hds_control_rollback() -> None:
    arrays = _arrays()
    observation = _observation(
        arrays,
        8647,
        signature="rollback-ablation-world:before",
    )
    session = create_cognitive_session(
        p_bundle=load_compiled_autonomous_instruction_body(),
        resource_contract=ResourceContract(action_budget_per_episode=1),
    )
    handle = session.begin_episode()
    world = _ResetOnlyWorld(observation)

    report = GenericAGIRuntime(world, session, handle).run(
        ablation=GenericRuntimeAblation(rollback=False)
    )

    assert world.reset_count == 0
    assert report.actions_executed == 0
    assert report.stop_reason == "ROLLBACK_ABLATED"
    assert "GENERIC_ROLLBACK_ABLATED" in report.failure_signatures
    session.end_episode(handle, succeeded=False, reason=report.stop_reason)


def test_active_generic_modules_do_not_import_legacy_runtime() -> None:
    active_modules = (
        "compiled_policy.py",
        "generic_compute.py",
        "generic_hds.py",
        "generic_runtime.py",
        "generic_session.py",
    )
    forbidden_roots = {
        "s5_authority",
        "s5_compute",
        "s5_policy",
        "s5_runner",
        "s5_runtime",
        "teacher",
    }
    for filename in active_modules:
        tree = ast.parse(
            (PACKAGE_ROOT / "arc3_agi_agent" / filename).read_text(
                encoding="utf-8"
            )
        )
        imported = {
            alias.name.split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.Import)
            for alias in node.names
        }
        imported.update(
            (node.module or "").lstrip(".").split(".")[0]
            for node in ast.walk(tree)
            if isinstance(node, ast.ImportFrom)
        )
        assert forbidden_roots.isdisjoint(imported)


def test_compiled_history_rejects_non_arc_action_ids() -> None:
    with pytest.raises(
        ValueError,
        match="COMPILED_POLICY_HISTORY_ACTION_INVALID",
    ):
        compiled_policy_feature_vector(
            np.zeros((64, 64), dtype=np.uint8),
            (1, 2),
            (ActionEffectRecord(action_id=29),),
        )


def test_compiled_policy_is_canonical_p_bundle_roundtrip() -> None:
    body = load_compiled_autonomous_instruction_body()
    bundle = PCompilerV2().bootstrap(
        body=body,
        version="p22-compiled-autonomous-v1",
    )
    payload = bundle.package_bytes()
    restored = p_bundle_from_package(payload)

    assert bundle.validate() == ()
    assert any(item.dtype == "f16le" for item in bundle.tensors)
    assert restored.package_bytes() == payload
    assert restored.logical_digest() == bundle.logical_digest()
    assert restored.body.digest() == body.digest()
    assert set(restored.body.tensor_arrays()) == set(body.tensor_arrays())
    assert all(
        np.array_equal(
            restored.body.tensor_arrays()[name],
            body.tensor_arrays()[name],
        )
        for name in body.tensor_arrays()
    )
