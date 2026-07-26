"""Source/hidden-state-free observation conditions for privileged S4."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from arcengine import FrameDataRaw

from ..schema import digest_object
from .render_state import rendered_frame_digest

S4_STATE_CONDITION_SCHEMA_VERSION = (
    "arc3-teacher-s4-observation-history-state-condition-v1"
)
S4_STATE_SIGNATURE_PREFIX = "arc3_teacher_s4_state:"
S4_ACTION_EFFECT_HISTORY_LIMIT = 4


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


def descriptor_from_s3_condition(
    source_condition: Mapping[str, object],
) -> dict[str, object]:
    """Subtract source/hidden digest from a compiled S3 condition."""

    required = {
        "rendered_frame_digest",
        "terminal_state",
        "available_actions",
        "bounded_action_effect_history",
        "action_effect_history_limit",
        "source_state_digest",
    }
    missing = sorted(required.difference(source_condition))
    if missing:
        raise ValueError(
            "S4_SOURCE_CONDITION_FIELD_MISSING:" + ",".join(missing)
        )
    raw_available = source_condition.get("available_actions")
    if not isinstance(raw_available, list):
        raise TypeError("S4_SOURCE_AVAILABLE_ACTIONS_INVALID")
    raw_history = source_condition.get("bounded_action_effect_history")
    if not isinstance(raw_history, list):
        raise TypeError("S4_SOURCE_HISTORY_INVALID")
    history_limit = _integer(
        source_condition.get("action_effect_history_limit"),
        "action_effect_history_limit",
    )
    if history_limit != S4_ACTION_EFFECT_HISTORY_LIMIT:
        raise ValueError("S4_SOURCE_HISTORY_LIMIT_INVALID")
    return {
        "schema_version": S4_STATE_CONDITION_SCHEMA_VERSION,
        "rendered_frame_digest": str(
            source_condition.get("rendered_frame_digest", "")
        ),
        "terminal_state": str(
            source_condition.get("terminal_state", "")
        ),
        "available_actions": [
            _integer(item, "available_actions[]")
            for item in raw_available
        ],
        "bounded_action_effect_history": list(raw_history),
        "action_effect_history_limit": history_limit,
    }


def state_condition_descriptor(
    *,
    frame: FrameDataRaw,
    action_effect_history: Sequence[Mapping[str, object]] = (),
    current_rendered_frame_digest: str | None = None,
) -> dict[str, object]:
    """Build the S4 condition without an environment/source object."""

    if not isinstance(frame, FrameDataRaw):
        raise TypeError("S4_FRAME_REQUIRED")
    bounded_history = list(
        action_effect_history[-S4_ACTION_EFFECT_HISTORY_LIMIT:]
    )
    return {
        "schema_version": S4_STATE_CONDITION_SCHEMA_VERSION,
        "rendered_frame_digest": (
            current_rendered_frame_digest
            if current_rendered_frame_digest is not None
            else rendered_frame_digest(frame)
        ),
        "terminal_state": _frame_state(frame),
        "available_actions": _available_action_ids(frame),
        "bounded_action_effect_history": bounded_history,
        "action_effect_history_limit": S4_ACTION_EFFECT_HISTORY_LIMIT,
    }


def state_condition_signature(
    *,
    frame: FrameDataRaw,
    action_effect_history: Sequence[Mapping[str, object]] = (),
    current_rendered_frame_digest: str | None = None,
) -> tuple[str, dict[str, object]]:
    """Return the source/hidden-state-free state signature."""

    descriptor = state_condition_descriptor(
        frame=frame,
        action_effect_history=action_effect_history,
        current_rendered_frame_digest=current_rendered_frame_digest,
    )
    return S4_STATE_SIGNATURE_PREFIX + digest_object(descriptor), descriptor


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
    """Record an observation-only action effect."""

    return {
        "before_rendered_frame_digest": (
            before_rendered_frame_digest
            if before_rendered_frame_digest is not None
            else rendered_frame_digest(before)
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
        "after_terminal_state": _frame_state(after),
        "after_available_actions": _available_action_ids(after),
    }


__all__ = [
    "S4_ACTION_EFFECT_HISTORY_LIMIT",
    "S4_STATE_CONDITION_SCHEMA_VERSION",
    "S4_STATE_SIGNATURE_PREFIX",
    "descriptor_from_s3_condition",
    "state_condition_descriptor",
    "state_condition_signature",
    "transition_effect_record",
]
