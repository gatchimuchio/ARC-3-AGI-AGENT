"""Identity-routing-free state conditions for privileged S3 execution.

S3 still permits source and hidden state, but explicit task/game/level
identity and progress counters may not participate in action selection.  The
resulting signature is shared across every retained OFFLINE environment and
is looked up in one global policy index.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence

from arc_agi.local_wrapper import (  # type: ignore[import-untyped]
    LocalEnvironmentWrapper,
)
from arcengine import FrameDataRaw

from ..schema import digest_object
from .render_state import rendered_frame_digest
from .s1_state import source_state_body

S3_STATE_CONDITION_SCHEMA_VERSION = (
    "arc3-teacher-s3-identity-free-state-condition-v1"
)
S3_STATE_SIGNATURE_PREFIX = "arc3_teacher_s3_state:"
S3_SOURCE_STATE_DIGEST_PREFIX = "arc3_teacher_s3_source_state:"
S3_ACTION_EFFECT_HISTORY_LIMIT = 4

_IDENTITY_OR_ORDINAL_SOURCE_FIELDS = frozenset(
    {
        "_action_count",
        "_current_level_index",
        "_game_id",
    }
)


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


def identity_routing_free_source_body(
    raw_body: Mapping[str, object],
) -> dict[str, object]:
    """Remove explicit source identity and trajectory counters.

    Structural source values and hidden state remain available until S4.  The
    function intentionally removes the concrete game class, current level
    index, and cumulative action count instead of merely hiding them behind a
    digest.
    """

    raw_fields = raw_body.get("source_fields")
    if not isinstance(raw_fields, Mapping):
        raise TypeError("S3_SOURCE_FIELDS_INVALID")
    source_fields = {
        str(key): value
        for key, value in raw_fields.items()
        if str(key) not in _IDENTITY_OR_ORDINAL_SOURCE_FIELDS
    }
    removed_count = len(raw_fields) - len(source_fields)
    if "game_class" not in raw_body:
        raise ValueError("S3_SOURCE_GAME_CLASS_EVIDENCE_MISSING")
    return {
        "source_fields": source_fields,
        "current_level_data": raw_body.get("current_level_data"),
        "custom_hidden_state": raw_body.get("custom_hidden_state"),
        "previous_environment_action": raw_body.get(
            "previous_environment_action"
        ),
        "excluded_unstable_or_unbounded_source_field_count": raw_body.get(
            "excluded_unstable_or_unbounded_source_field_count"
        ),
        "excluded_identity_or_ordinal_source_field_count": (
            removed_count + 1
        ),
        "selection_exclusions": [
            "TASK_ID",
            "GAME_ID",
            "LEVEL_ID",
            "GAME_CLASS",
            "LEVEL_PROGRESS_COUNTER",
            "REPLAY_POSITION",
            "ACTION_ORDINAL",
            "FIXED_ACTION_LIST",
            "SOURCE_REASONING_METADATA",
        ],
    }


def s3_source_state_digest(
    environment: LocalEnvironmentWrapper,
) -> str:
    """Bind permitted source/hidden structure without identity routing."""

    raw_body = source_state_body(
        environment,
        include_previous_action_payload=False,
    )
    body = identity_routing_free_source_body(raw_body)
    return S3_SOURCE_STATE_DIGEST_PREFIX + digest_object(body)


def state_condition_descriptor(
    *,
    environment: LocalEnvironmentWrapper,
    frame: FrameDataRaw,
    action_effect_history: Sequence[Mapping[str, object]] = (),
    current_rendered_frame_digest: str | None = None,
) -> dict[str, object]:
    """Build one globally addressable S3 condition without identity keys."""

    if not isinstance(frame, FrameDataRaw):
        raise TypeError("S3_FRAME_REQUIRED")
    bounded_history = list(
        action_effect_history[-S3_ACTION_EFFECT_HISTORY_LIMIT:]
    )
    return {
        "schema_version": S3_STATE_CONDITION_SCHEMA_VERSION,
        "rendered_frame_digest": (
            current_rendered_frame_digest
            if current_rendered_frame_digest is not None
            else rendered_frame_digest(frame)
        ),
        "terminal_state": _frame_state(frame),
        "available_actions": _available_action_ids(frame),
        "source_state_digest": s3_source_state_digest(environment),
        "bounded_action_effect_history": bounded_history,
        "action_effect_history_limit": S3_ACTION_EFFECT_HISTORY_LIMIT,
    }


def state_condition_signature(
    *,
    environment: LocalEnvironmentWrapper,
    frame: FrameDataRaw,
    action_effect_history: Sequence[Mapping[str, object]] = (),
    current_rendered_frame_digest: str | None = None,
) -> tuple[str, dict[str, object]]:
    """Return the identity-routing-free state signature and descriptor."""

    descriptor = state_condition_descriptor(
        environment=environment,
        frame=frame,
        action_effect_history=action_effect_history,
        current_rendered_frame_digest=current_rendered_frame_digest,
    )
    return S3_STATE_SIGNATURE_PREFIX + digest_object(descriptor), descriptor


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
    """Record an observed effect without identity or progress counters."""

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
    "S3_ACTION_EFFECT_HISTORY_LIMIT",
    "S3_SOURCE_STATE_DIGEST_PREFIX",
    "S3_STATE_CONDITION_SCHEMA_VERSION",
    "S3_STATE_SIGNATURE_PREFIX",
    "identity_routing_free_source_body",
    "s3_source_state_digest",
    "state_condition_descriptor",
    "state_condition_signature",
    "transition_effect_record",
]
