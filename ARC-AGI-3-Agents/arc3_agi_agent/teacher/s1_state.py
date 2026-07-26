"""Deterministic S1 Teacher state conditions.

S1 is still a privileged development stage.  Its condition may use game
identity, retained source state, and hidden state, but it must not use a replay
position, action ordinal, or fixed action list.  This module turns the current
OFFLINE environment state into a content signature that can be recomputed
before every decision.
"""

from __future__ import annotations

import hashlib
from collections.abc import Mapping, Sequence, Set
from enum import Enum
from typing import Any

from arc_agi.local_wrapper import (  # type: ignore[import-untyped]
    LocalEnvironmentWrapper,
)
from arcengine import FrameDataRaw

from ..protocol import AuthorityViolation
from ..schema import digest_object

S1_STATE_CONDITION_SCHEMA_VERSION = "arc3-teacher-s1-state-condition-v2"
S1_STATE_SIGNATURE_PREFIX = "arc3_teacher_s1_state:"
S1_SOURCE_STATE_DIGEST_PREFIX = "arc3_teacher_s1_source_state:"
S1_ACTION_EFFECT_HISTORY_LIMIT = 4

_SOURCE_STATE_EXCLUDED_FIELDS = frozenset(
    {
        "_action",
        "_camera",
        "_clean_levels",
        "_debug",
        "_game_id",
        "_levels",
        "_seed",
    }
)
_UNSTABLE_SOURCE_VALUE = object()
_SOURCE_CONTAINER_LIMIT = 128


def _normalized_value(
    value: object,
    *,
    active_object_ids: frozenset[int] = frozenset(),
) -> object:
    """Normalize trusted source values without retaining object identity."""

    if value is None or isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Enum):
        return {
            "enum_type": type(value).__name__,
            "value": _normalized_value(
                value.value,
                active_object_ids=active_object_ids,
            ),
        }

    tobytes = getattr(value, "tobytes", None)
    raw_shape = getattr(value, "shape", None)
    raw_dtype = getattr(value, "dtype", None)
    if callable(tobytes) and raw_shape is not None and raw_dtype is not None:
        raw_bytes = tobytes()
        if not isinstance(raw_bytes, (bytes, bytearray)):
            raise TypeError("S1_SOURCE_ARRAY_BYTES_INVALID")
        shape = [int(item) for item in raw_shape]
        return {
            "array_dtype": str(raw_dtype),
            "array_shape": shape,
            "array_sha256": hashlib.sha256(raw_bytes).hexdigest(),
        }

    object_id = id(value)
    if object_id in active_object_ids:
        return {"cycle_type": type(value).__name__}
    nested_ids = active_object_ids | {object_id}

    if isinstance(value, Mapping):
        entries = [
            {
                "key": _normalized_value(
                    key,
                    active_object_ids=nested_ids,
                ),
                "value": _normalized_value(
                    item,
                    active_object_ids=nested_ids,
                ),
            }
            for key, item in value.items()
        ]
        entries.sort(key=lambda item: digest_object(item["key"]))
        return {"mapping_entries": entries}
    if isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        return {
            "sequence_type": type(value).__name__,
            "items": [
                _normalized_value(
                    item,
                    active_object_ids=nested_ids,
                )
                for item in value
            ],
        }
    if isinstance(value, Set):
        items = [
            _normalized_value(
                item,
                active_object_ids=nested_ids,
            )
            for item in value
        ]
        items.sort(key=digest_object)
        return {"set_items": items}

    # Source objects can be large cyclic sprite graphs.  Their visible state is
    # already represented by the rendered frame; custom hidden exports and
    # level data carry the privileged non-rendered condition.  Retain only the
    # stable type here, never repr() or an address.
    return {"source_object_type": type(value).__name__}


def _stable_source_control_value(
    value: object,
    *,
    active_object_ids: frozenset[int] = frozenset(),
) -> object:
    """Keep bounded control values, excluding stochastic render caches."""

    if value is None or isinstance(value, (str, bool, int, float, Enum)):
        return _normalized_value(value)
    object_id = id(value)
    if object_id in active_object_ids:
        return _UNSTABLE_SOURCE_VALUE
    nested_ids = active_object_ids | {object_id}
    if isinstance(value, Mapping):
        if len(value) > _SOURCE_CONTAINER_LIMIT:
            return _UNSTABLE_SOURCE_VALUE
        entries: list[dict[str, object]] = []
        for key, item in value.items():
            normalized_key = _stable_source_control_value(
                key,
                active_object_ids=nested_ids,
            )
            normalized_item = _stable_source_control_value(
                item,
                active_object_ids=nested_ids,
            )
            if (
                normalized_key is _UNSTABLE_SOURCE_VALUE
                or normalized_item is _UNSTABLE_SOURCE_VALUE
            ):
                return _UNSTABLE_SOURCE_VALUE
            entries.append(
                {"key": normalized_key, "value": normalized_item}
            )
        entries.sort(key=lambda item: digest_object(item["key"]))
        return {"mapping_entries": entries}
    if isinstance(value, Sequence) and not isinstance(
        value,
        (str, bytes, bytearray),
    ):
        if len(value) > _SOURCE_CONTAINER_LIMIT:
            return _UNSTABLE_SOURCE_VALUE
        items: list[object] = []
        for item in value:
            normalized_item = _stable_source_control_value(
                item,
                active_object_ids=nested_ids,
            )
            if normalized_item is _UNSTABLE_SOURCE_VALUE:
                return _UNSTABLE_SOURCE_VALUE
            items.append(normalized_item)
        return {
            "sequence_type": type(value).__name__,
            "items": items,
        }
    if isinstance(value, Set):
        if len(value) > _SOURCE_CONTAINER_LIMIT:
            return _UNSTABLE_SOURCE_VALUE
        items = []
        for item in value:
            normalized_item = _stable_source_control_value(
                item,
                active_object_ids=nested_ids,
            )
            if normalized_item is _UNSTABLE_SOURCE_VALUE:
                return _UNSTABLE_SOURCE_VALUE
            items.append(normalized_item)
        items.sort(key=digest_object)
        return {"set_items": items}
    # Arrays and source objects are deliberately omitted here.  Rendered state,
    # level data, and the game's explicit hidden-state export are separately
    # content-bound.  This prevents random cosmetic frame caches from becoming
    # false decision identity.
    return _UNSTABLE_SOURCE_VALUE


def _frame_state(frame: FrameDataRaw) -> str:
    raw = getattr(frame.state, "value", frame.state)
    return str(raw).upper()


def _frame_levels(frame: FrameDataRaw) -> int:
    value = frame.levels_completed
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError("S1_FRAME_LEVELS_INVALID")
    return value


def _available_action_ids(frame: FrameDataRaw) -> list[int]:
    output: list[int] = []
    for raw in frame.available_actions:
        value = getattr(raw, "value", raw)
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError("S1_AVAILABLE_ACTION_INVALID")
        output.append(value)
    return output


def rendered_frame_digest(frame: FrameDataRaw) -> str:
    frames = list(frame.frame)
    if not frames:
        normalized: object = []
    else:
        final_frame = frames[-1]
        normalized = (
            final_frame.tolist()
            if hasattr(final_frame, "tolist")
            else final_frame
        )
    return "sha256:" + digest_object(normalized)


def _action_condition(game: Any) -> dict[str, object]:
    raw_action = getattr(game, "_action", None)
    if raw_action is None:
        return {"action_id": None, "action_data": {}}
    raw_id = getattr(raw_action, "id", None)
    action_id = getattr(raw_id, "value", raw_id)
    if isinstance(action_id, bool) or not isinstance(action_id, int):
        action_id = None
    raw_data = getattr(raw_action, "data", {})
    if not isinstance(raw_data, Mapping):
        raw_data = {}
    action_data: dict[str, int] = {}
    for key in ("x", "y"):
        value = raw_data.get(key)
        if isinstance(value, int) and not isinstance(value, bool):
            action_data[key] = value
    return {
        "action_id": action_id,
        "action_data": action_data,
    }


def source_state_descriptor(
    environment: LocalEnvironmentWrapper,
) -> dict[str, object]:
    """Read the current privileged source condition without replay position."""

    if not isinstance(environment, LocalEnvironmentWrapper):
        raise AuthorityViolation("S1_LOCAL_WRAPPER_REQUIRED")
    game = getattr(environment, "_game", None)
    if game is None:
        raise RuntimeError("S1_SOURCE_GAME_MISSING")
    level = getattr(game, "current_level", None)
    if level is None:
        raise RuntimeError("S1_SOURCE_LEVEL_MISSING")

    hidden_getter = getattr(game, "_get_hidden_state", None)
    if not callable(hidden_getter):
        raise RuntimeError("S1_HIDDEN_STATE_GETTER_MISSING")
    hidden_state = hidden_getter()
    level_attributes = getattr(level, "__dict__", {})
    if not isinstance(level_attributes, Mapping):
        raise TypeError("S1_SOURCE_LEVEL_ATTRIBUTES_INVALID")
    level_data = level_attributes.get("_data", {})

    game_attributes = getattr(game, "__dict__", {})
    if not isinstance(game_attributes, Mapping):
        raise TypeError("S1_SOURCE_GAME_ATTRIBUTES_INVALID")
    source_fields: dict[str, object] = {}
    excluded_source_field_count = 0
    for key, value in sorted(
        game_attributes.items(),
        key=lambda item: str(item[0]),
    ):
        field_name = str(key)
        if field_name in _SOURCE_STATE_EXCLUDED_FIELDS:
            continue
        normalized = _stable_source_control_value(value)
        if normalized is _UNSTABLE_SOURCE_VALUE:
            excluded_source_field_count += 1
            continue
        source_fields[field_name] = normalized
    body: dict[str, object] = {
        "game_class": type(game).__name__,
        "source_fields": source_fields,
        "current_level_data": _normalized_value(level_data),
        "custom_hidden_state": _normalized_value(hidden_state),
        "previous_environment_action": _action_condition(game),
        "excluded_unstable_or_unbounded_source_field_count": (
            excluded_source_field_count
        ),
        "selection_exclusions": [
            "REPLAY_POSITION",
            "ACTION_ORDINAL",
            "FIXED_ACTION_LIST",
            "SOURCE_REASONING_METADATA",
        ],
    }
    return {
        "schema_version": S1_STATE_CONDITION_SCHEMA_VERSION,
        "source_state_digest": (
            S1_SOURCE_STATE_DIGEST_PREFIX + digest_object(body)
        ),
    }


def state_condition_descriptor(
    *,
    environment: LocalEnvironmentWrapper,
    frame: FrameDataRaw,
    action_effect_history: Sequence[Mapping[str, object]] = (),
    current_rendered_frame_digest: str | None = None,
) -> dict[str, object]:
    """Build the complete recomputable condition used by the S1 policy."""

    if not isinstance(frame, FrameDataRaw):
        raise TypeError("S1_FRAME_REQUIRED")
    game_id = str(getattr(frame, "game_id", "") or "")
    source = source_state_descriptor(environment)
    bounded_history = list(
        action_effect_history[-S1_ACTION_EFFECT_HISTORY_LIMIT:]
    )
    return {
        "schema_version": S1_STATE_CONDITION_SCHEMA_VERSION,
        "game_id": game_id,
        "rendered_frame_digest": (
            current_rendered_frame_digest
            if current_rendered_frame_digest is not None
            else rendered_frame_digest(frame)
        ),
        "levels_completed": _frame_levels(frame),
        "terminal_state": _frame_state(frame),
        "available_actions": _available_action_ids(frame),
        "source_state_digest": source["source_state_digest"],
        "bounded_action_effect_history": bounded_history,
        "action_effect_history_limit": S1_ACTION_EFFECT_HISTORY_LIMIT,
    }


def state_condition_signature(
    *,
    environment: LocalEnvironmentWrapper,
    frame: FrameDataRaw,
    action_effect_history: Sequence[Mapping[str, object]] = (),
    current_rendered_frame_digest: str | None = None,
) -> tuple[str, dict[str, object]]:
    """Return a content signature and its auditable condition descriptor."""

    descriptor = state_condition_descriptor(
        environment=environment,
        frame=frame,
        action_effect_history=action_effect_history,
        current_rendered_frame_digest=current_rendered_frame_digest,
    )
    return (
        S1_STATE_SIGNATURE_PREFIX + digest_object(descriptor),
        descriptor,
    )


def transition_effect_record(
    *,
    before: FrameDataRaw,
    action: Mapping[str, object],
    after: FrameDataRaw,
    before_rendered_frame_digest: str | None = None,
    after_rendered_frame_digest: str | None = None,
) -> dict[str, object]:
    """Describe an observed effect without an ordinal or corpus position."""

    raw_action_data = action.get("action_data", {})
    if not isinstance(raw_action_data, Mapping):
        raise TypeError("S1_EFFECT_ACTION_DATA_INVALID")
    action_data = {
        str(key): int(value)
        for key, value in raw_action_data.items()
        if isinstance(value, int) and not isinstance(value, bool)
    }
    return {
        "before_rendered_frame_digest": (
            before_rendered_frame_digest
            if before_rendered_frame_digest is not None
            else rendered_frame_digest(before)
        ),
        "before_levels_completed": _frame_levels(before),
        "before_terminal_state": _frame_state(before),
        "action_id": action.get("action_id"),
        "action_data": action_data,
        "reset_scope": action.get("reset_scope"),
        "after_rendered_frame_digest": (
            after_rendered_frame_digest
            if after_rendered_frame_digest is not None
            else rendered_frame_digest(after)
        ),
        "after_levels_completed": _frame_levels(after),
        "after_terminal_state": _frame_state(after),
        "after_available_actions": _available_action_ids(after),
    }


__all__ = [
    "S1_STATE_CONDITION_SCHEMA_VERSION",
    "S1_STATE_SIGNATURE_PREFIX",
    "S1_ACTION_EFFECT_HISTORY_LIMIT",
    "source_state_descriptor",
    "rendered_frame_digest",
    "state_condition_descriptor",
    "state_condition_signature",
    "transition_effect_record",
]
