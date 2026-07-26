"""Coordinate-free state conditions for privileged S2 Teacher execution."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from arc_agi.local_wrapper import (  # type: ignore[import-untyped]
    LocalEnvironmentWrapper,
)
from arcengine import FrameDataRaw

from ..schema import digest_object
from .render_state import rendered_frame_digest
from .s1_state import source_state_body

S2_STATE_CONDITION_SCHEMA_VERSION = "arc3-teacher-s2-state-condition-v1"
S2_STATE_SIGNATURE_PREFIX = "arc3_teacher_s2_state:"
S2_SOURCE_STATE_DIGEST_PREFIX = "arc3_teacher_s2_source_state:"
S2_ACTION_EFFECT_HISTORY_LIMIT = 4


def _integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    return value


def _frame_state(frame: FrameDataRaw) -> str:
    raw = getattr(frame.state, "value", frame.state)
    return str(raw).upper()


def _available_action_ids(frame: FrameDataRaw) -> list[int]:
    return [
        _integer(
            getattr(raw, "value", raw),
            "available_actions[]",
        )
        for raw in frame.available_actions
    ]


def s2_source_state_digest(
    environment: LocalEnvironmentWrapper,
) -> str:
    """Bind source/hidden state while excluding prior pointer payloads."""

    body = source_state_body(
        environment,
        include_previous_action_payload=False,
    )
    return S2_SOURCE_STATE_DIGEST_PREFIX + digest_object(body)


def state_condition_descriptor(
    *,
    environment: LocalEnvironmentWrapper,
    frame: FrameDataRaw,
    action_effect_history: Sequence[Mapping[str, object]] = (),
    current_rendered_frame_digest: str | None = None,
) -> dict[str, object]:
    """Build the recomputable S2 condition with no absolute target data."""

    if not isinstance(frame, FrameDataRaw):
        raise TypeError("S2_FRAME_REQUIRED")
    bounded_history = list(
        action_effect_history[-S2_ACTION_EFFECT_HISTORY_LIMIT:]
    )
    return {
        "schema_version": S2_STATE_CONDITION_SCHEMA_VERSION,
        "game_id": str(getattr(frame, "game_id", "") or ""),
        "rendered_frame_digest": (
            current_rendered_frame_digest
            if current_rendered_frame_digest is not None
            else rendered_frame_digest(frame)
        ),
        "levels_completed": _integer(
            frame.levels_completed,
            "levels_completed",
        ),
        "terminal_state": _frame_state(frame),
        "available_actions": _available_action_ids(frame),
        "source_state_digest": s2_source_state_digest(environment),
        "bounded_action_effect_history": bounded_history,
        "action_effect_history_limit": S2_ACTION_EFFECT_HISTORY_LIMIT,
    }


def state_condition_signature(
    *,
    environment: LocalEnvironmentWrapper,
    frame: FrameDataRaw,
    action_effect_history: Sequence[Mapping[str, object]] = (),
    current_rendered_frame_digest: str | None = None,
) -> tuple[str, dict[str, object]]:
    """Return the content-bound S2 state signature and descriptor."""

    descriptor = state_condition_descriptor(
        environment=environment,
        frame=frame,
        action_effect_history=action_effect_history,
        current_rendered_frame_digest=current_rendered_frame_digest,
    )
    return S2_STATE_SIGNATURE_PREFIX + digest_object(descriptor), descriptor


def transition_effect_record(
    *,
    before: FrameDataRaw,
    action_id: int,
    reset_scope: str,
    target_selector_digest: str | None,
    after: FrameDataRaw,
    before_rendered_frame_digest: str | None = None,
    after_rendered_frame_digest: str | None = None,
) -> dict[str, object]:
    """Record an action effect while omitting the emitted pointer payload."""

    return {
        "before_rendered_frame_digest": (
            before_rendered_frame_digest
            if before_rendered_frame_digest is not None
            else rendered_frame_digest(before)
        ),
        "before_levels_completed": _integer(
            before.levels_completed,
            "before.levels_completed",
        ),
        "before_terminal_state": _frame_state(before),
        "action_id": _integer(action_id, "action_id"),
        "reset_scope": reset_scope,
        "target_selector_digest": target_selector_digest,
        "after_rendered_frame_digest": (
            after_rendered_frame_digest
            if after_rendered_frame_digest is not None
            else rendered_frame_digest(after)
        ),
        "after_levels_completed": _integer(
            after.levels_completed,
            "after.levels_completed",
        ),
        "after_terminal_state": _frame_state(after),
        "after_available_actions": _available_action_ids(after),
    }


__all__ = [
    "S2_ACTION_EFFECT_HISTORY_LIMIT",
    "S2_STATE_CONDITION_SCHEMA_VERSION",
    "S2_STATE_SIGNATURE_PREFIX",
    "S2_SOURCE_STATE_DIGEST_PREFIX",
    "s2_source_state_digest",
    "state_condition_descriptor",
    "state_condition_signature",
    "transition_effect_record",
]
