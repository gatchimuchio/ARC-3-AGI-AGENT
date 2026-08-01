"""PH-D05 ARC3 raw teacher trajectory normalization.

This module is a pure, dependency-free transformation boundary.  It consumes
one already acquired and content-verified raw recording plus frozen source and
environment bindings.  It never reads environment source, performs network
I/O, executes a trajectory, generates a hypothesis, or promotes a rule.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterator, Mapping, Sequence
from itertools import chain
from typing import Any, Final, Never, cast

from .canonical import (
    CONTENT_ID_DOMAIN,
    LOGICAL_DIGEST_DOMAIN,
    DigestExclusionPolicy,
    canonical_json_bytes,
    canonical_trajectory_digest,
    logical_content_digest,
    raw_trajectory_digest,
)
from .scope_contract import teacher_bound

type JsonScalar = None | bool | int | str
type JsonValue = JsonScalar | list[JsonValue] | dict[str, JsonValue]
type JsonObject = dict[str, JsonValue]

TRAJECTORY_VERSION: Final = "arc3-canonical-teacher-trajectory-v1"
ACTION_RECORD_VERSION: Final = "arc3-action-record-v1"
FRAME_RECORD_VERSION: Final = "arc3-canonical-frame-rle-v1"
VISIBLE_DIFF_VERSION: Final = "arc3-visible-diff-span-v1"
PACKAGE_VERSION: Final = "hds-arc3-teacher-trajectory-package-v1"
OBSERVATION_PROJECTION_VERSION: Final = "arc3-rendered-frame-lossless-rle-v1"
SOURCE_PROFILE_ID: Final = "arc3-raw-teacher-recordings"
ENVIRONMENT_MANIFEST_ID: Final = "arc3-replay-environment-ph-d01b"
EXPECTED_ENVIRONMENT_MANIFEST_DIGEST: Final = (
    "hds-environment-manifest:"
    "1d116488cd85ee5ad9d641aeb2af66187572b181cb03d819fac1cdba3252cfe0"
)
EXPECTED_SOURCE_MANIFEST_DIGEST: Final = (
    "hds-source-content-manifest:"
    "3098feb7241e4ea3444b5942ab8ba0371d8168a51f32a1f3d44c0e09db36eda9"
)
EXPECTED_ARC_AGI_WHEEL_SHA256: Final = (
    "aeca1663db342e91cb8fc96cf0c83e2fa39db1640bc1298e80a8d522e3af70f3"
)
EXPECTED_ARCENGINE_WHEEL_SHA256: Final = (
    "5f9739d6d0055780a4581fd6fe09066bb08775c4c8212c9adcca2eb008aef59c"
)
VARIABLE_METADATA_FIELDS: Final = (
    "absolute_path",
    "acquired_at",
    "guid",
    "reasoning",
    "result_timestamp",
    "timestamp",
)

_SELF_POLICY = DigestExclusionPolicy(
    id_fields=frozenset(
        {
            "action_record_id",
            "certificate_id",
            "frame_id",
            "package_id",
            "trajectory_id",
        }
    ),
    digest_fields=frozenset({"content_digest"}),
)


class TrajectoryNormalizationError(ValueError):
    """A stable fail-closed PH-D05 normalization failure."""


def _fail(code: str, context: str = "") -> Never:
    raise TrajectoryNormalizationError(code + (":" + context if context else ""))


def _domain_hash(domain: bytes, namespace: str, payload: bytes) -> str:
    return (
        namespace
        + ":"
        + hashlib.sha256(
            domain + namespace.encode("ascii") + b"\0" + payload
        ).hexdigest()
    )


def _bind_content_and_id(
    value: Mapping[str, object],
    *,
    content_namespace: str,
    id_namespace: str,
) -> tuple[str, str]:
    """Bind one logical body twice without canonicalizing it twice."""

    logical_body = {
        key: item
        for key, item in value.items()
        if key not in _SELF_POLICY.excluded_fields
    }
    payload = json.dumps(
        logical_body,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return (
        _domain_hash(LOGICAL_DIGEST_DOMAIN, content_namespace, payload),
        _domain_hash(CONTENT_ID_DOMAIN, id_namespace, payload),
    )


def _integer(value: object, field: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        _fail("PH_D05_INTEGER_REQUIRED", field)
    return value


def _string(value: object, field: str) -> str:
    if not isinstance(value, str) or not value:
        _fail("PH_D05_STRING_REQUIRED", field)
    return value


def _mapping(value: object, field: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        _fail("PH_D05_OBJECT_REQUIRED", field)
    return cast(Mapping[str, Any], value)


def _sequence(value: object, field: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(
        value,
        str | bytes | bytearray,
    ):
        _fail("PH_D05_ARRAY_REQUIRED", field)
    return cast(Sequence[object], value)


def _strict_pairs(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            _fail("PH_D05_DUPLICATE_JSON_KEY", key)
        result[key] = value
    return result


def _reject_constant(value: str) -> object:
    _fail("PH_D05_NONFINITE_JSON_TOKEN", value)


def _iter_events(raw_payload: bytes) -> Iterator[dict[str, Any]]:
    try:
        text = raw_payload.decode("utf-8", errors="strict")
    except UnicodeDecodeError as error:
        raise TrajectoryNormalizationError(
            "PH_D05_RAW_RECORDING_UTF8_INVALID"
        ) from error
    decoder = json.JSONDecoder(
        object_pairs_hook=_strict_pairs,
        parse_constant=_reject_constant,
    )
    index = 0
    while index < len(text) and text[index].isspace():
        index += 1
    if index >= len(text) or text[index] != "[":
        _fail("PH_D05_RAW_RECORDING_ARRAY_REQUIRED")
    index += 1
    event_index = 0
    while True:
        while index < len(text) and text[index].isspace():
            index += 1
        if index < len(text) and text[index] == "]":
            index += 1
            break
        try:
            item, index = decoder.raw_decode(text, index)
        except json.JSONDecodeError as error:
            raise TrajectoryNormalizationError(
                f"PH_D05_RAW_RECORDING_JSON_INVALID:{event_index}"
            ) from error
        if not isinstance(item, dict):
            _fail("PH_D05_EVENT_OBJECT_REQUIRED", str(event_index))
        yield cast(dict[str, Any], item)
        event_index += 1
        while index < len(text) and text[index].isspace():
            index += 1
        if index < len(text) and text[index] == ",":
            index += 1
            continue
        if index < len(text) and text[index] == "]":
            index += 1
            break
        _fail("PH_D05_EVENT_SEPARATOR_INVALID", str(event_index))
    if text[index:].strip():
        _fail("PH_D05_RAW_RECORDING_TRAILING_DATA")


def _action_id(value: object, field: str) -> int:
    if isinstance(value, bool):
        _fail("PH_D05_ACTION_ID_INVALID", field)
    if isinstance(value, int):
        result = value
    elif isinstance(value, str):
        normalized = value.strip().upper()
        if normalized == "RESET":
            result = 0
        elif normalized.startswith("ACTION"):
            suffix = normalized.removeprefix("ACTION")
            if not suffix.isdecimal():
                _fail("PH_D05_ACTION_ID_INVALID", field)
            result = int(suffix)
        elif normalized.isdecimal():
            result = int(normalized)
        else:
            _fail("PH_D05_ACTION_ID_INVALID", field)
    else:
        _fail("PH_D05_ACTION_ID_INVALID", field)
    if not 0 <= result <= 7:
        _fail("PH_D05_ACTION_ID_OUT_OF_RANGE", field)
    return result


def _action_enum(action_id: int) -> str:
    return "RESET" if action_id == 0 else f"ACTION{action_id}"


def _action_payload(
    action_id: int,
    value: object,
    field: str,
    *,
    source_case_ref: str,
) -> JsonObject:
    raw = _mapping(value, field)
    unknown = sorted(set(raw) - {"game_id", "x", "y"})
    if unknown:
        _fail("PH_D05_ACTION_PAYLOAD_FIELD_INVALID", ",".join(unknown))
    if "game_id" in raw:
        routed_case_ref = _string(raw["game_id"], field + ".game_id")
        if routed_case_ref.split("-", 1)[0] != source_case_ref.split("-", 1)[0]:
            _fail("PH_D05_ACTION_GAME_FAMILY_MISMATCH", field)
    semantic_payload = {key: raw[key] for key in ("x", "y") if key in raw}
    if action_id == 6:
        if set(semantic_payload) != {"x", "y"}:
            _fail("PH_D05_ACTION6_XY_REQUIRED", field)
        return {
            "x": _integer(semantic_payload["x"], field + ".x"),
            "y": _integer(semantic_payload["y"], field + ".y"),
        }
    if semantic_payload:
        _fail("PH_D05_NON_ACTION6_PAYLOAD_FORBIDDEN", field)
    return {}


def _available_actions(value: object, field: str) -> list[JsonValue]:
    actions = [_integer(item, field + "[]") for item in _sequence(value, field)]
    if any(not 1 <= item <= 7 for item in actions):
        _fail("PH_D05_AVAILABLE_ACTION_OUT_OF_RANGE", field)
    if len(actions) != len(set(actions)):
        _fail("PH_D05_AVAILABLE_ACTION_DUPLICATE", field)
    return cast(list[JsonValue], sorted(actions))


def _terminal_state(value: object, field: str) -> str:
    state = _string(value, field).upper()
    if state == "NOT_FINISHED":
        return "CONTINUE"
    if state not in {"CONTINUE", "WIN", "GAME_OVER"}:
        _fail("PH_D05_TERMINAL_STATE_INVALID", state)
    return state


def _frame(value: object, field: str) -> list[list[list[int]]]:
    layers_raw = _sequence(value, field)
    if not layers_raw:
        _fail("PH_D05_FRAME_LAYER_REQUIRED", field)
    layers: list[list[list[int]]] = []
    row_count: int | None = None
    column_count: int | None = None
    for layer_index, layer_raw in enumerate(layers_raw):
        rows_raw = _sequence(layer_raw, f"{field}[{layer_index}]")
        if not rows_raw:
            _fail("PH_D05_FRAME_ROW_REQUIRED", field)
        rows: list[list[int]] = []
        for row_index, row_raw in enumerate(rows_raw):
            cells_raw = _sequence(
                row_raw,
                f"{field}[{layer_index}][{row_index}]",
            )
            if not cells_raw:
                _fail("PH_D05_FRAME_COLUMN_REQUIRED", field)
            cells = [
                _integer(
                    item,
                    f"{field}[{layer_index}][{row_index}][]",
                )
                for item in cells_raw
            ]
            if any(not 0 <= item <= 255 for item in cells):
                _fail("PH_D05_FRAME_CELL_OUT_OF_RANGE", field)
            if column_count is None:
                column_count = len(cells)
            elif len(cells) != column_count:
                _fail("PH_D05_FRAME_NOT_RECTANGULAR", field)
            rows.append(cells)
        if row_count is None:
            row_count = len(rows)
        elif len(rows) != row_count:
            _fail("PH_D05_FRAME_LAYER_SHAPE_MISMATCH", field)
        layers.append(rows)
    return layers


def _flatten(frame: Sequence[Sequence[Sequence[int]]]) -> list[int]:
    return [cell for layer in frame for row in layer for cell in row]


def encode_frame_rle(frame: object) -> JsonObject:
    """Return the lossless canonical RLE representation of one ARC3 frame."""

    normalized = _frame(frame, "frame")
    shape = [len(normalized), len(normalized[0]), len(normalized[0][0])]
    flat = _flatten(normalized)
    runs: list[JsonValue] = []
    current = flat[0]
    count = 1
    for value in flat[1:]:
        if value == current:
            count += 1
            continue
        runs.append(cast(JsonValue, [current, count]))
        current = value
        count = 1
    runs.append(cast(JsonValue, [current, count]))
    return {
        "encoding": FRAME_RECORD_VERSION,
        "shape": cast(JsonValue, shape),
        "runs": runs,
    }


def decode_frame_rle(value: Mapping[str, object]) -> list[list[list[int]]]:
    """Invert one canonical ARC3 frame RLE record exactly."""

    if value.get("encoding") != FRAME_RECORD_VERSION:
        _fail("PH_D05_FRAME_RLE_VERSION_INVALID")
    shape = [
        _integer(item, "shape[]") for item in _sequence(value.get("shape"), "shape")
    ]
    if len(shape) != 3 or any(item < 1 for item in shape):
        _fail("PH_D05_FRAME_RLE_SHAPE_INVALID")
    flat: list[int] = []
    for index, raw_run in enumerate(_sequence(value.get("runs"), "runs")):
        run = _sequence(raw_run, f"runs[{index}]")
        if len(run) != 2:
            _fail("PH_D05_FRAME_RLE_RUN_INVALID", str(index))
        color = _integer(run[0], f"runs[{index}][0]")
        count = _integer(run[1], f"runs[{index}][1]")
        if not 0 <= color <= 255 or count < 1:
            _fail("PH_D05_FRAME_RLE_RUN_INVALID", str(index))
        flat.extend([color] * count)
    expected = shape[0] * shape[1] * shape[2]
    if len(flat) != expected:
        _fail("PH_D05_FRAME_RLE_ELEMENT_COUNT_MISMATCH")
    offset = 0
    layers: list[list[list[int]]] = []
    for _layer in range(shape[0]):
        rows: list[list[int]] = []
        for _row in range(shape[1]):
            rows.append(flat[offset : offset + shape[2]])
            offset += shape[2]
        layers.append(rows)
    return layers


def _raw_frame_digest(frame: Sequence[Sequence[Sequence[int]]]) -> str:
    payload = json.dumps(
        frame,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
    ).encode("utf-8")
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def _frame_record(frame: object) -> JsonObject:
    normalized = _frame(frame, "frame")
    rle = encode_frame_rle(normalized)
    body: dict[str, object] = {
        "schema_version": "hds-arc3-canonical-frame-record-v1",
        "frame_record_version": FRAME_RECORD_VERSION,
        "raw_frame_digest": _raw_frame_digest(normalized),
        "canonical_frame": rle,
        "inverse_mapping": "RLE_ROW_MAJOR_EXACT",
        "digest_excluded_fields": ["content_digest", "frame_id"],
    }
    content_digest, frame_id = _bind_content_and_id(
        body,
        content_namespace="hds-canonical-frame",
        id_namespace="hds-canonical-frame-id",
    )
    body["content_digest"] = content_digest
    body["frame_id"] = frame_id
    return cast(JsonObject, body)


def visible_diff(before: object, after: object) -> JsonObject:
    """Return deterministic changed spans that exactly reconstruct ``after``."""

    before_frame = _frame(before, "before")
    after_frame = _frame(after, "after")
    before_shape = (
        len(before_frame),
        len(before_frame[0]),
        len(before_frame[0][0]),
    )
    after_shape = (
        len(after_frame),
        len(after_frame[0]),
        len(after_frame[0][0]),
    )
    if before_shape != after_shape:
        changed_cell_count = max(
            before_shape[0] * before_shape[1] * before_shape[2],
            after_shape[0] * after_shape[1] * after_shape[2],
        )
        replacement_body: JsonObject = {
            "encoding": VISIBLE_DIFF_VERSION,
            "mode": "FULL_FRAME_REPLACEMENT",
            "before_shape": cast(JsonValue, list(before_shape)),
            "after_shape": cast(JsonValue, list(after_shape)),
            "changed_cell_count": changed_cell_count,
            "before_raw_frame_digest": _raw_frame_digest(before_frame),
            "after_frame": cast(JsonValue, encode_frame_rle(after_frame)),
        }
        replacement_body["content_digest"] = logical_content_digest(
            "hds-visible-diff",
            replacement_body,
            policy=DigestExclusionPolicy(digest_fields=frozenset({"content_digest"})),
        )
        return replacement_body
    spans: list[JsonValue] = []
    changed = 0
    for layer_index in range(before_shape[0]):
        for row_index in range(before_shape[1]):
            left = before_frame[layer_index][row_index]
            right = after_frame[layer_index][row_index]
            column = 0
            while column < before_shape[2]:
                if left[column] == right[column]:
                    column += 1
                    continue
                start = column
                before_values: list[int] = []
                after_values: list[int] = []
                while column < before_shape[2] and left[column] != right[column]:
                    before_values.append(left[column])
                    after_values.append(right[column])
                    changed += 1
                    column += 1
                spans.append(
                    cast(
                        JsonValue,
                        {
                            "layer": layer_index,
                            "row": row_index,
                            "x_start": start,
                            "before_values": before_values,
                            "after_values": after_values,
                        },
                    )
                )
    body: JsonObject = {
        "encoding": VISIBLE_DIFF_VERSION,
        "mode": "CELL_SPANS",
        "shape": cast(JsonValue, list(before_shape)),
        "changed_cell_count": changed,
        "spans": spans,
    }
    body["content_digest"] = logical_content_digest(
        "hds-visible-diff",
        body,
        policy=DigestExclusionPolicy(digest_fields=frozenset({"content_digest"})),
    )
    return body


def apply_visible_diff(
    before: object, diff: Mapping[str, object]
) -> list[list[list[int]]]:
    """Apply a canonical visible diff and fail on inconsistent before values."""

    frame = _frame(before, "before")
    if diff.get("encoding") != VISIBLE_DIFF_VERSION:
        _fail("PH_D05_VISIBLE_DIFF_VERSION_INVALID")
    mode = diff.get("mode", "CELL_SPANS")
    if mode == "FULL_FRAME_REPLACEMENT":
        before_shape = [
            _integer(item, "before_shape[]")
            for item in _sequence(diff.get("before_shape"), "before_shape")
        ]
        actual_shape = [len(frame), len(frame[0]), len(frame[0][0])]
        if before_shape != actual_shape:
            _fail("PH_D05_VISIBLE_DIFF_BEFORE_SHAPE_MISMATCH")
        if diff.get("before_raw_frame_digest") != _raw_frame_digest(frame):
            _fail("PH_D05_VISIBLE_DIFF_BEFORE_DIGEST_MISMATCH")
        after_frame = decode_frame_rle(_mapping(diff.get("after_frame"), "after_frame"))
        after_shape = [
            _integer(item, "after_shape[]")
            for item in _sequence(diff.get("after_shape"), "after_shape")
        ]
        if after_shape != [
            len(after_frame),
            len(after_frame[0]),
            len(after_frame[0][0]),
        ]:
            _fail("PH_D05_VISIBLE_DIFF_AFTER_SHAPE_MISMATCH")
        return after_frame
    if mode != "CELL_SPANS":
        _fail("PH_D05_VISIBLE_DIFF_MODE_INVALID")
    shape = [
        _integer(item, "shape[]") for item in _sequence(diff.get("shape"), "shape")
    ]
    actual_shape = [len(frame), len(frame[0]), len(frame[0][0])]
    if shape != actual_shape:
        _fail("PH_D05_VISIBLE_DIFF_SHAPE_MISMATCH")
    changed = 0
    for index, raw_span in enumerate(_sequence(diff.get("spans"), "spans")):
        span = _mapping(raw_span, f"spans[{index}]")
        layer = _integer(span.get("layer"), f"spans[{index}].layer")
        row = _integer(span.get("row"), f"spans[{index}].row")
        start = _integer(span.get("x_start"), f"spans[{index}].x_start")
        before_values = [
            _integer(item, f"spans[{index}].before_values[]")
            for item in _sequence(
                span.get("before_values"),
                f"spans[{index}].before_values",
            )
        ]
        after_values = [
            _integer(item, f"spans[{index}].after_values[]")
            for item in _sequence(
                span.get("after_values"),
                f"spans[{index}].after_values",
            )
        ]
        if not before_values or len(before_values) != len(after_values):
            _fail("PH_D05_VISIBLE_DIFF_SPAN_LENGTH_INVALID", str(index))
        if (
            not 0 <= layer < shape[0]
            or not 0 <= row < shape[1]
            or not 0 <= start
            or start + len(before_values) > shape[2]
        ):
            _fail("PH_D05_VISIBLE_DIFF_SPAN_RANGE_INVALID", str(index))
        actual_before = frame[layer][row][start : start + len(before_values)]
        if actual_before != before_values:
            _fail("PH_D05_VISIBLE_DIFF_BEFORE_MISMATCH", str(index))
        frame[layer][row][start : start + len(after_values)] = after_values
        changed += len(after_values)
    if changed != _integer(diff.get("changed_cell_count"), "changed_cell_count"):
        _fail("PH_D05_VISIBLE_DIFF_COUNT_MISMATCH")
    return frame


def _level_index(levels_completed: int, target_levels: int, state: str) -> int:
    if state == "WIN":
        return target_levels
    return min(target_levels, levels_completed + 1)


def _action_record(
    *,
    action_input: Mapping[str, Any],
    action_id: int,
    payload: JsonObject,
    step_index: int,
    source_event_index: int,
    available_before: list[JsonValue],
    available_after: list[JsonValue],
    full_reset: bool,
) -> JsonObject:
    raw_action_digest = (
        "hds-raw-action:"
        + hashlib.sha256(canonical_json_bytes(action_input)).hexdigest()
    )
    body: dict[str, object] = {
        "schema_version": "hds-arc3-detailed-action-record-v1",
        "action_record_version": ACTION_RECORD_VERSION,
        "step_index": step_index,
        "source_event_index": source_event_index,
        "action_id": action_id,
        "action_enum": _action_enum(action_id),
        "payload": payload,
        "available_actions_before": available_before,
        "available_actions_after": available_after,
        "is_complex": action_id == 6,
        "full_reset": full_reset,
        "reset_scope": (
            "FULL_RESET"
            if action_id == 0 and full_reset
            else "LEVEL_COMPATIBILITY"
            if action_id == 0
            else "NOT_APPLICABLE"
        ),
        "raw_action_digest": raw_action_digest,
        "semantic_hypothesis_id": None,
        "digest_excluded_fields": ["action_record_id", "content_digest"],
    }
    content_digest, action_record_id = _bind_content_and_id(
        body,
        content_namespace="hds-arc3-detailed-action-record",
        id_namespace="hds-arc3-detailed-action-record-id",
    )
    body["content_digest"] = content_digest
    body["action_record_id"] = action_record_id
    return cast(JsonObject, body)


def _d02b_action_projection(
    *,
    action: Mapping[str, object],
    before_frame: Mapping[str, object],
    after_frame: Mapping[str, object],
    diff: Mapping[str, object],
    terminal_after: str,
    progress_delta: int,
) -> JsonObject | None:
    action_id = _integer(action.get("action_id"), "action.action_id")
    if action_id == 0:
        return None
    body: dict[str, object] = {
        "schema_version": "hds-arc3-action-record-v1",
        "step_index": _integer(action.get("step_index"), "action.step_index"),
        "action_id": action_id,
        "action_payload": action.get("payload"),
        "available_actions_before": action.get("available_actions_before"),
        "canonical_frame_before_digest": before_frame.get("content_digest"),
        "canonical_frame_after_digest": after_frame.get("content_digest"),
        "terminal_state_after": terminal_after,
        "visible_diff": {
            "changed_cell_count": diff.get("changed_cell_count"),
            "visible_diff_digest": diff.get("content_digest"),
        },
        "progress_delta": progress_delta,
        "digest_excluded_fields": ["action_record_id", "content_digest"],
    }
    content_digest, action_record_id = _bind_content_and_id(
        body,
        content_namespace="hds-arc3-action-record",
        id_namespace="hds-arc3-action-record-id",
    )
    body["content_digest"] = content_digest
    body["action_record_id"] = action_record_id
    return cast(JsonObject, body)


def _event_data(event: Mapping[str, Any], event_index: int) -> Mapping[str, Any]:
    return _mapping(event.get("data"), f"events[{event_index}].data")


def _observation(
    data: Mapping[str, Any],
    context: str,
    *,
    source_case_ref: str,
) -> dict[str, Any]:
    observed_case_ref = _string(data.get("game_id"), context + ".game_id")
    if observed_case_ref != source_case_ref:
        _fail("PH_D05_OBSERVATION_GAME_ID_MISMATCH", context)
    state = _terminal_state(data.get("state"), context + ".state")
    levels_completed = _integer(
        data.get("levels_completed"),
        context + ".levels_completed",
    )
    return {
        "frame": _frame(data.get("frame"), context + ".frame"),
        "available_actions": _available_actions(
            data.get("available_actions"),
            context + ".available_actions",
        ),
        "terminal_state": state,
        "levels_completed": levels_completed,
    }


def _replay_observation(value: object, context: str) -> dict[str, Any]:
    raw = _mapping(value, context)
    frame = _frame(raw.get("frame"), context + ".frame")
    frame_digest = _string(
        raw.get("frame_digest"),
        context + ".frame_digest",
    )
    if frame_digest != _raw_frame_digest(frame):
        _fail("PH_D05_REPLAY_FRAME_DIGEST_MISMATCH", context)
    return {
        "frame": frame,
        "available_actions": _available_actions(
            raw.get("available_actions"),
            context + ".available_actions",
        ),
        "terminal_state": _terminal_state(
            raw.get("terminal_state"),
            context + ".terminal_state",
        ),
        "levels_completed": _integer(
            raw.get("levels_completed"),
            context + ".levels_completed",
        ),
    }


def _replay_capture(
    value: Mapping[str, object],
    *,
    source_case_ref: str,
    target_levels: int,
) -> tuple[dict[str, Any], list[Mapping[str, Any]], str]:
    if value.get("schema_version") != "hds-arc3-ph-d05-replay-capture-v1":
        _fail("PH_D05_REPLAY_CAPTURE_VERSION_MISMATCH", source_case_ref)
    if (
        value.get("game_id") != source_case_ref
        or value.get("target_levels") != target_levels
    ):
        _fail("PH_D05_REPLAY_CAPTURE_IDENTITY_MISMATCH", source_case_ref)
    content_digest = _string(
        value.get("content_digest"),
        "replay_capture.content_digest",
    )
    body = dict(value)
    body.pop("content_digest", None)
    if content_digest != "hds-arc3-replay-capture:" + _plain_digest(body):
        _fail("PH_D05_REPLAY_CAPTURE_DIGEST_MISMATCH", source_case_ref)
    initial = _replay_observation(value.get("initial"), "replay_capture.initial")
    raw_steps = _sequence(value.get("steps"), "replay_capture.steps")
    steps = [
        _mapping(item, f"replay_capture.steps[{index}]")
        for index, item in enumerate(raw_steps)
    ]
    if not steps:
        _fail("PH_D05_REPLAY_CAPTURE_STEPS_EMPTY", source_case_ref)
    return initial, steps, content_digest


def _plain_digest(value: object) -> str:
    payload = json.dumps(
        value,
        allow_nan=False,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
    ).encode("utf-8")
    return hashlib.sha256(payload).hexdigest()


def _normalization_certificate(
    *,
    raw_digest: str,
    canonical_digest: str,
    replay_capture_digest: str,
) -> JsonObject:
    body: dict[str, object] = {
        "schema_version": "hds-normalization-certificate-v1",
        "normalization_class": "LOSSLESS_NORMALIZATION",
        "source_record_digest": raw_digest,
        "canonical_record_digest": canonical_digest,
        "rewrite_rule_ref": None,
        "variable_mapping": {
            "action_input.id": "steps[].action.action_id",
            "action_input.data": "steps[].action.payload",
            "available_actions": "steps[].available_actions_after",
            "frame": "frame_records[].canonical_frame",
            "levels_completed": "steps[].levels_completed_after",
            "state": "steps[].terminal_state_after",
        },
        "inverse_mapping": {
            "canonical_frame": "RLE_ROW_MAJOR_EXACT",
            "visible_diff": "APPLY_SPANS_TO_BEFORE_FRAME",
            "raw_recording": "RESOLVE_BY_RAW_TRAJECTORY_DIGEST",
        },
        "required_assumptions": [
            "EQUIVALENCE_SCOPE_ACTION_STATE_EFFECT_PROJECTION",
            "RAW_RECORDING_REMAINS_CONTENT_ADDRESSABLE",
        ],
        "equivalence_evidence_refs": [replay_capture_digest],
        "information_loss": "NONE",
        "status": "VERIFIED",
        "digest_excluded_fields": ["certificate_id", "content_digest"],
    }
    content_digest, certificate_id = _bind_content_and_id(
        body,
        content_namespace="hds-normalization-certificate",
        id_namespace="hds-normalization-certificate-id",
    )
    body["content_digest"] = content_digest
    body["certificate_id"] = certificate_id
    return cast(JsonObject, body)


def _raw_override_trajectory(
    raw_recording: bytes,
    *,
    source_case_ref: str,
    target_levels: int,
    expected_recorded_actions: int,
) -> JsonObject:
    events = _iter_events(raw_recording)
    try:
        initial_event = next(events)
    except StopIteration:
        _fail("PH_D05_RAW_OVERRIDE_INITIAL_EVENT_MISSING", source_case_ref)
    initial_data = _event_data(initial_event, 0)
    initial_action_input = _mapping(
        initial_data.get("action_input"),
        "raw_override.events[0].action_input",
    )
    if _action_id(initial_action_input.get("id"), "raw_override.initial") != 0:
        _fail("PH_D05_RAW_OVERRIDE_INITIAL_RESET_REQUIRED", source_case_ref)
    prior = _observation(
        initial_data,
        "raw_override.events[0].data",
        source_case_ref=source_case_ref,
    )
    raw_steps: list[JsonValue] = []
    recorded_action_count = 0
    post_terminal_action_count = 0
    solution_closed = False
    for source_event_index, event in enumerate(events, start=1):
        recorded_action_count += 1
        data = _event_data(event, source_event_index)
        if solution_closed:
            post_terminal_action_count += 1
            continue
        action_input = _mapping(
            data.get("action_input"),
            f"raw_override.events[{source_event_index}].action_input",
        )
        action_id = _action_id(
            action_input.get("id"),
            f"raw_override.events[{source_event_index}].action_id",
        )
        payload = _action_payload(
            action_id,
            action_input.get("data", {}),
            f"raw_override.events[{source_event_index}].action_data",
            source_case_ref=source_case_ref,
        )
        after = _observation(
            data,
            f"raw_override.events[{source_event_index}].data",
            source_case_ref=source_case_ref,
        )
        raw_steps.append(
            cast(
                JsonValue,
                {
                    "step_index": len(raw_steps),
                    "source_event_index": source_event_index,
                    "before_frame_digest": _raw_frame_digest(prior["frame"]),
                    "available_actions_before": prior["available_actions"],
                    "terminal_state_before": prior["terminal_state"],
                    "levels_completed_before": prior["levels_completed"],
                    "action_id": action_id,
                    "action_payload": payload,
                    "after_frame_digest": _raw_frame_digest(after["frame"]),
                    "available_actions_after": after["available_actions"],
                    "terminal_state_after": after["terminal_state"],
                    "levels_completed_after": after["levels_completed"],
                },
            )
        )
        solution_closed = (
            after["terminal_state"] == "WIN"
            and after["levels_completed"] == target_levels
        )
        prior = after
    if recorded_action_count != expected_recorded_actions:
        _fail("PH_D05_RAW_OVERRIDE_ACTION_COUNT_MISMATCH", source_case_ref)
    if not solution_closed:
        _fail("PH_D05_RAW_OVERRIDE_NOT_CLOSED", source_case_ref)
    body: JsonObject = {
        "schema_version": "hds-arc3-raw-teacher-trajectory-projection-v1",
        "game_id": source_case_ref,
        "trajectory_source": "PUBLIC_WINNING_HUMAN_RECORDING",
        "recorded_action_count": recorded_action_count,
        "successful_prefix_action_count": len(raw_steps),
        "post_terminal_action_count": post_terminal_action_count,
        "level_completion_count": target_levels,
        "steps": raw_steps,
    }
    body["content_digest"] = (
        "hds-arc3-raw-teacher-trajectory-projection:" + _plain_digest(body)
    )
    return body


def _capture_event(
    capture_step: Mapping[str, Any],
    *,
    source_case_ref: str,
) -> dict[str, Any]:
    after = _mapping(capture_step.get("after"), "capture_step.after")
    action_id = _integer(capture_step.get("action_id"), "capture_step.action_id")
    return {
        "data": {
            "action_input": {
                "id": str(action_id),
                "data": capture_step.get("action_data"),
                "reasoning": None,
            },
            "available_actions": after.get("available_actions"),
            "frame": after.get("frame"),
            "full_reset": (
                action_id == 0 and capture_step.get("reset_scope") == "RECORDED_ACTION"
            ),
            "game_id": source_case_ref,
            "guid": "REPLAY_CAPTURE_EXCLUDED_FROM_CANONICAL_DIGEST",
            "levels_completed": after.get("levels_completed"),
            "state": after.get("terminal_state"),
            "win_levels": None,
        }
    }


@teacher_bound
def normalize_teacher_recording(
    raw_recording: bytes,
    *,
    source_binding: Mapping[str, object],
    environment_binding: Mapping[str, object],
    replay_capture: Mapping[str, object],
) -> JsonObject:
    """Normalize one pinned winning recording into a PH-D05 package."""

    if not isinstance(raw_recording, bytes):
        raise TypeError("PH_D05_RAW_RECORDING_BYTES_REQUIRED")
    source_case_ref = _string(source_binding.get("game_id"), "source.game_id")
    recording_file = _string(
        source_binding.get("recording_file"),
        "source.recording_file",
    )
    target_levels = _integer(
        source_binding.get("target_levels"),
        "source.target_levels",
    )
    expected_recorded_actions = _integer(
        source_binding.get("expected_actions"),
        "source.expected_actions",
    )
    expected_size = _integer(
        source_binding.get("size_bytes"),
        "source.size_bytes",
    )
    expected_sha = _string(
        source_binding.get("sha256"),
        "source.sha256",
    )
    canonical_action_source = str(
        source_binding.get("canonical_action_source", "RAW_RECORDING")
    )
    if canonical_action_source not in {
        "RAW_RECORDING",
        "VERIFIED_LOCAL_SOLUTION_OVERRIDE",
    }:
        _fail("PH_D05_CANONICAL_ACTION_SOURCE_INVALID", source_case_ref)
    canonical_override = canonical_action_source == "VERIFIED_LOCAL_SOLUTION_OVERRIDE"
    if len(raw_recording) != expected_size:
        _fail("PH_D05_RAW_RECORDING_SIZE_MISMATCH", source_case_ref)
    physical_sha = hashlib.sha256(raw_recording).hexdigest()
    if physical_sha != expected_sha:
        _fail("PH_D05_RAW_RECORDING_SHA_MISMATCH", source_case_ref)
    if environment_binding.get("content_digest") != (
        EXPECTED_ENVIRONMENT_MANIFEST_DIGEST
    ):
        _fail("PH_D05_ENVIRONMENT_BINDING_DIGEST_MISMATCH")
    if environment_binding.get("manifest_id") != ENVIRONMENT_MANIFEST_ID:
        _fail("PH_D05_ENVIRONMENT_BINDING_ID_MISMATCH")

    replay_initial, replay_steps, replay_capture_digest = _replay_capture(
        replay_capture,
        source_case_ref=source_case_ref,
        target_levels=target_levels,
    )
    events = _iter_events(raw_recording)
    try:
        first_event = next(events)
    except StopIteration:
        _fail("PH_D05_INITIAL_EVENT_MISSING", source_case_ref)
    first_data = _event_data(first_event, 0)
    first_action_input = _mapping(
        first_data.get("action_input"),
        "events[0].data.action_input",
    )
    first_action_id = _action_id(
        first_action_input.get("id"),
        "events[0].action_id",
    )
    action_events: Iterator[tuple[int, dict[str, Any]]]
    if first_action_id == 0:
        _action_payload(
            0,
            first_action_input.get("data", {}),
            "events[0].action_data",
            source_case_ref=source_case_ref,
        )
        raw_initial_observation = _observation(
            first_data,
            "events[0].data",
            source_case_ref=source_case_ref,
        )
        if (
            raw_initial_observation["levels_completed"] != 0
            or raw_initial_observation["terminal_state"] != "CONTINUE"
        ):
            _fail("PH_D05_INITIAL_OBSERVATION_INVALID", source_case_ref)
        action_events = enumerate(events, start=1)
        raw_initial_source = "RAW_RECORDING_INITIAL_OBSERVATION"
    else:
        raw_initial_observation = replay_initial
        action_events = chain(((0, first_event),), enumerate(events, start=1))
        raw_initial_source = "REPLAY_INITIAL_OBSERVATION_RAW_PRE_ACTION_ABSENT"
    raw_override_trajectory: JsonObject | None = None
    if canonical_override:
        raw_override_trajectory = _raw_override_trajectory(
            raw_recording,
            source_case_ref=source_case_ref,
            target_levels=target_levels,
            expected_recorded_actions=expected_recorded_actions,
        )
        action_events = enumerate(
            (
                _capture_event(step, source_case_ref=source_case_ref)
                for step in replay_steps
            ),
            start=0,
        )
        raw_initial_observation = replay_initial
        raw_initial_source = "VERIFIED_LOCAL_SOLUTION_OVERRIDE_REPLAY"
    initial_observation = replay_initial

    frame_index: dict[str, JsonObject] = {}

    def register_frame(frame: object) -> JsonObject:
        record = _frame_record(frame)
        digest = str(record["content_digest"])
        previous = frame_index.get(digest)
        if previous is not None:
            if previous != record:
                _fail("PH_D05_FRAME_DIGEST_COLLISION", digest)
            return previous
        decoded = decode_frame_rle(
            cast(Mapping[str, object], record["canonical_frame"])
        )
        if decoded != _frame(frame, "frame"):
            _fail("PH_D05_FRAME_RLE_INVERSE_MISMATCH", source_case_ref)
        frame_index[digest] = record
        return record

    initial_frame_record = register_frame(initial_observation["frame"])
    prior_frame_record = initial_frame_record
    prior = initial_observation
    raw_prior = raw_initial_observation
    steps: list[JsonValue] = []
    projections: list[JsonValue] = []
    replay_trace: list[dict[str, object]] = []
    recorded_action_count = 0
    post_terminal_action_count = 0
    solution_closed = False
    action_surface_counts = {index: 0 for index in range(8)}

    replay_step_index = 0
    source_frame_difference_count = 0

    for source_event_index, event in action_events:
        recorded_action_count += 1
        data = _event_data(event, source_event_index)
        if solution_closed:
            post_terminal_action_count += 1
            continue
        action_input = _mapping(
            data.get("action_input"),
            f"events[{source_event_index}].data.action_input",
        )
        action_id = _action_id(
            action_input.get("id"),
            f"events[{source_event_index}].action_id",
        )
        payload = _action_payload(
            action_id,
            action_input.get("data", {}),
            f"events[{source_event_index}].action_data",
            source_case_ref=source_case_ref,
        )
        raw_after = _observation(
            data,
            f"events[{source_event_index}].data",
            source_case_ref=source_case_ref,
        )
        if replay_step_index >= len(replay_steps):
            _fail("PH_D05_REPLAY_CAPTURE_STEP_MISSING", source_case_ref)
        captured_step = replay_steps[replay_step_index]
        if (
            captured_step.get("step") != replay_step_index + 1
            or captured_step.get("action_id") != action_id
            or captured_step.get("action_data") != payload
        ):
            _fail(
                "PH_D05_RAW_REPLAY_ACTION_MISMATCH",
                f"{source_case_ref}:{replay_step_index + 1}",
            )
        after = _replay_observation(
            captured_step.get("after"),
            f"replay_capture.steps[{replay_step_index}].after",
        )
        if (
            raw_after["available_actions"] != after["available_actions"]
            or raw_after["terminal_state"] != after["terminal_state"]
            or raw_after["levels_completed"] != after["levels_completed"]
        ):
            _fail(
                "PH_D05_RAW_REPLAY_TRANSITION_MISMATCH",
                f"{source_case_ref}:{replay_step_index + 1}",
            )
        before_available = cast(list[JsonValue], prior["available_actions"])
        after_available = cast(list[JsonValue], after["available_actions"])
        if action_id != 0 and action_id not in before_available:
            _fail(
                "PH_D05_ACTION_NOT_AVAILABLE",
                f"{source_case_ref}:{source_event_index}:{action_id}",
            )
        before_frame_record = prior_frame_record
        after_frame_record = register_frame(after["frame"])
        diff = visible_diff(prior["frame"], after["frame"])
        if (
            apply_visible_diff(prior["frame"], cast(Mapping[str, object], diff))
            != after["frame"]
        ):
            _fail("PH_D05_VISIBLE_DIFF_INVERSE_MISMATCH", source_case_ref)
        step_index = len(steps)
        full_reset = data.get("full_reset") is True
        reset_scope = (
            "LEVEL_COMPATIBILITY"
            if action_id == 0 and not full_reset
            else "RECORDED_ACTION"
        )
        if captured_step.get("reset_scope") != reset_scope:
            _fail(
                "PH_D05_REPLAY_RESET_SCOPE_MISMATCH",
                f"{source_case_ref}:{replay_step_index + 1}",
            )
        action = _action_record(
            action_input=action_input,
            action_id=action_id,
            payload=payload,
            step_index=step_index,
            source_event_index=source_event_index,
            available_before=before_available,
            available_after=after_available,
            full_reset=full_reset,
        )
        before_levels = _integer(
            prior["levels_completed"],
            "prior.levels_completed",
        )
        after_levels = _integer(
            after["levels_completed"],
            "after.levels_completed",
        )
        if after_levels < before_levels or after_levels > target_levels:
            _fail("PH_D05_PROGRESS_TRANSITION_INVALID", source_case_ref)
        before_terminal = _string(
            prior["terminal_state"],
            "prior.terminal_state",
        )
        after_terminal = _string(
            after["terminal_state"],
            "after.terminal_state",
        )
        progress_delta = after_levels - before_levels
        raw_before_frame_digest = _raw_frame_digest(raw_prior["frame"])
        raw_after_frame_digest = _raw_frame_digest(raw_after["frame"])
        source_frame_match = (
            raw_after_frame_digest == after_frame_record["raw_frame_digest"]
        )
        if captured_step.get("source_frame_digest") != raw_after_frame_digest:
            _fail(
                "PH_D05_RAW_REPLAY_SOURCE_DIGEST_MISMATCH",
                f"{source_case_ref}:{replay_step_index + 1}",
            )
        if captured_step.get("source_frame_match") is not source_frame_match:
            _fail(
                "PH_D05_REPLAY_SOURCE_FRAME_FLAG_MISMATCH",
                f"{source_case_ref}:{replay_step_index + 1}",
            )
        if not source_frame_match:
            source_frame_difference_count += 1
        step: dict[str, object] = {
            "step_index": step_index,
            "source_event_index": source_event_index,
            "raw_before_frame_digest": raw_before_frame_digest,
            "raw_before_frame_source": (
                raw_initial_source if step_index == 0 else "RAW_RECORDING"
            ),
            "raw_after_frame_digest": raw_after_frame_digest,
            "raw_after_frame_source": "RAW_RECORDING",
            "raw_to_canonical_after_frame_match": source_frame_match,
            "before_frame_digest": before_frame_record["raw_frame_digest"],
            "before_canonical_frame_ref": before_frame_record["frame_id"],
            "before_canonical_frame_digest": before_frame_record["content_digest"],
            "level_index_before": _level_index(
                before_levels,
                target_levels,
                before_terminal,
            ),
            "levels_completed_before": before_levels,
            "terminal_state_before": before_terminal,
            "available_actions_before": before_available,
            "action": action,
            "after_frame_digest": after_frame_record["raw_frame_digest"],
            "after_canonical_frame_ref": after_frame_record["frame_id"],
            "after_canonical_frame_digest": after_frame_record["content_digest"],
            "level_index_after": _level_index(
                after_levels,
                target_levels,
                after_terminal,
            ),
            "levels_completed_after": after_levels,
            "terminal_state_after": after_terminal,
            "available_actions_after": after_available,
            "visible_diff": diff,
            "progress_delta": progress_delta,
        }
        steps.append(cast(JsonValue, step))
        projection = _d02b_action_projection(
            action=action,
            before_frame=before_frame_record,
            after_frame=after_frame_record,
            diff=diff,
            terminal_after=after_terminal,
            progress_delta=progress_delta,
        )
        if projection is not None:
            projections.append(projection)
        replay_trace.append(
            {
                "step": step_index + 1,
                "action_id": action_id,
                "action_data": payload,
                "state": (
                    "NOT_FINISHED" if after_terminal == "CONTINUE" else after_terminal
                ),
                "levels_completed": after_levels,
                "frame_digest": after_frame_record["raw_frame_digest"],
                "reset_scope": reset_scope,
            }
        )
        action_surface_counts[action_id] += 1
        solution_closed = after_terminal == "WIN" and after_levels == target_levels
        prior = after
        prior_frame_record = after_frame_record
        raw_prior = raw_after
        replay_step_index += 1

    canonical_input_action_count = recorded_action_count
    if canonical_override:
        if canonical_input_action_count != len(replay_steps):
            _fail(
                "PH_D05_OVERRIDE_CANONICAL_ACTION_COUNT_MISMATCH",
                source_case_ref,
            )
        if raw_override_trajectory is None:
            _fail("PH_D05_RAW_OVERRIDE_TRAJECTORY_MISSING", source_case_ref)
        recorded_action_count = expected_recorded_actions
        post_terminal_action_count = _integer(
            raw_override_trajectory.get("post_terminal_action_count"),
            "raw_override.post_terminal_action_count",
        )
    elif recorded_action_count != expected_recorded_actions:
        _fail(
            "PH_D05_RECORDED_ACTION_COUNT_MISMATCH",
            f"{source_case_ref}:{recorded_action_count}:{expected_recorded_actions}",
        )
    if not solution_closed:
        _fail("PH_D05_SUCCESS_PREFIX_NOT_CLOSED", source_case_ref)
    if replay_step_index != len(replay_steps):
        _fail(
            "PH_D05_REPLAY_CAPTURE_ACTION_COUNT_MISMATCH",
            f"{source_case_ref}:{replay_step_index}:{len(replay_steps)}",
        )
    if prior["terminal_state"] != "WIN" or prior["levels_completed"] != target_levels:
        _fail("PH_D05_FINAL_STATE_INVALID", source_case_ref)

    canonical_steps: list[JsonValue] = []
    for raw_step in steps:
        canonical_step = cast(Mapping[str, Any], raw_step)
        canonical_action = cast(Mapping[str, Any], canonical_step["action"])
        canonical_steps.append(
            cast(
                JsonValue,
                {
                    "step_index": canonical_step["step_index"],
                    "action_id": canonical_action["action_id"],
                    "action_payload": canonical_action["payload"],
                    "reset_scope": canonical_action["reset_scope"],
                    "available_actions_before": canonical_step[
                        "available_actions_before"
                    ],
                    "available_actions_after": canonical_step[
                        "available_actions_after"
                    ],
                    "before_canonical_frame_digest": canonical_step[
                        "before_canonical_frame_digest"
                    ],
                    "after_canonical_frame_digest": canonical_step[
                        "after_canonical_frame_digest"
                    ],
                    "terminal_state_before": canonical_step[
                        "terminal_state_before"
                    ],
                    "terminal_state_after": canonical_step["terminal_state_after"],
                    "level_index_before": canonical_step["level_index_before"],
                    "level_index_after": canonical_step["level_index_after"],
                    "levels_completed_before": canonical_step[
                        "levels_completed_before"
                    ],
                    "levels_completed_after": canonical_step[
                        "levels_completed_after"
                    ],
                    "visible_diff_digest": cast(
                        Mapping[str, Any], canonical_step["visible_diff"]
                    )["content_digest"],
                    "progress_delta": canonical_step["progress_delta"],
                },
            )
        )
    canonical_core: dict[str, object] = {
        "trajectory_version": TRAJECTORY_VERSION,
        "observation_projection_version": OBSERVATION_PROJECTION_VERSION,
        "seed": 0,
        "reset_mode": "OFFLINE_FULL_RESET_PER_REPLAY",
        "initial_frame_digest": initial_frame_record["content_digest"],
        "initial_available_actions": initial_observation["available_actions"],
        "initial_terminal_state": initial_observation["terminal_state"],
        "initial_levels_completed": initial_observation["levels_completed"],
        "steps": canonical_steps,
        "final_terminal_state": "WIN",
        "level_completion_count": target_levels,
        "score_or_progress": target_levels,
    }
    raw_digest = raw_trajectory_digest(raw_recording)
    canonical_digest = canonical_trajectory_digest(
        canonical_core,
        policy=DigestExclusionPolicy(),
    )
    frame_records = sorted(
        frame_index.values(),
        key=lambda item: str(item["frame_id"]),
    )
    frame_bindings = [
        {
            "frame_id": item["frame_id"],
            "content_digest": item["content_digest"],
            "raw_frame_digest": item["raw_frame_digest"],
        }
        for item in frame_records
    ]
    frame_store_binding: dict[str, object] = {
        "schema_version": "hds-arc3-canonical-frame-store-binding-v1",
        "frame_count": len(frame_records),
        "frame_bindings": frame_bindings,
    }
    frame_store_digest = logical_content_digest(
        "hds-arc3-canonical-frame-store",
        frame_store_binding,
        policy=DigestExclusionPolicy(),
    )
    frame_store_body: dict[str, object] = {
        "schema_version": "hds-arc3-canonical-frame-store-v1",
        "frame_count": len(frame_records),
        "frame_bindings": frame_bindings,
        "frames": frame_records,
        "logical_binding_projection": frame_store_binding,
        "content_digest_scope": "LOGICAL_FRAME_BINDING_PROJECTION",
        "digest_excluded_fields": ["content_digest", "frames"],
        "content_digest": frame_store_digest,
    }
    expected_replay_trace_digest = _plain_digest(replay_trace)
    if replay_capture.get("actual_trace_digest") != expected_replay_trace_digest:
        _fail("PH_D05_REPLAY_TRACE_DIGEST_MISMATCH", source_case_ref)
    if replay_capture.get("source_frame_difference_count") != (
        source_frame_difference_count
    ):
        _fail(
            "PH_D05_SOURCE_FRAME_DIFFERENCE_COUNT_MISMATCH",
            source_case_ref,
        )
    trajectory_body: dict[str, object] = {
        "schema_version": "hds-arc3-detailed-teacher-trajectory-v1",
        "trajectory_version": TRAJECTORY_VERSION,
        "domain": "ARC3",
        "source_content_manifest_id": "source-content-arc3-raw-teacher-recordings",
        "source_content_manifest_digest": EXPECTED_SOURCE_MANIFEST_DIGEST,
        "source_profile_ref": SOURCE_PROFILE_ID,
        "game_id": source_case_ref,
        "recording_file": recording_file,
        "environment_manifest_ref": ENVIRONMENT_MANIFEST_ID,
        "environment_artifact_digest": environment_binding["content_digest"],
        "environment_version": "ARC3_PUBLIC_SAMPLE_2026_04_17",
        "arc_agi_wheel_digest": "sha256:" + EXPECTED_ARC_AGI_WHEEL_SHA256,
        "arcengine_wheel_digest": "sha256:" + EXPECTED_ARCENGINE_WHEEL_SHA256,
        "python_version": "3.12.13",
        "os_manifest_digest": environment_binding.get("content_digest"),
        "seed": 0,
        "reset_mode": "OFFLINE_FULL_RESET_PER_REPLAY",
        "observation_projection_version": OBSERVATION_PROJECTION_VERSION,
        "trajectory_source": "PUBLIC_WINNING_HUMAN_RECORDING",
        "canonical_action_source": canonical_action_source,
        "raw_canonical_action_alignment": (
            "DIVERGENT_VERIFIED_OVERRIDE" if canonical_override else "STEPWISE_ALIGNED"
        ),
        "verification_method": (
            "PINNED_SHA256_NORMALIZATION_AND_STRICT_OFFLINE_REPLAY_X3"
        ),
        "raw_recording_digest": raw_digest,
        "raw_recording_sha256": physical_sha,
        "raw_source_trajectory_projection_digest": (
            raw_override_trajectory.get("content_digest")
            if raw_override_trajectory is not None
            else None
        ),
        "replay_capture_digest": replay_capture_digest,
        "canonical_trajectory_digest": canonical_digest,
        "initial_raw_frame_digest": _raw_frame_digest(raw_initial_observation["frame"]),
        "initial_raw_frame_source": raw_initial_source,
        "initial_frame_digest": initial_frame_record["raw_frame_digest"],
        "initial_canonical_frame_ref": initial_frame_record["frame_id"],
        "initial_canonical_frame_digest": initial_frame_record["content_digest"],
        "initial_reset_action_id": 0 if first_action_id == 0 else None,
        "raw_initial_observation_event_present": first_action_id == 0,
        "initial_reset_transition_observed": False,
        "steps": steps,
        "final_terminal_state": "WIN",
        "level_completion_count": target_levels,
        "score_or_progress": target_levels,
        "recorded_action_count": recorded_action_count,
        "canonical_success_prefix_action_count": len(steps),
        "canonical_override_action_reduction_count": (
            recorded_action_count - len(steps) if canonical_override else 0
        ),
        "post_terminal_action_count": post_terminal_action_count,
        "source_frame_difference_count": source_frame_difference_count,
        "action_surface_counts": {
            str(key): action_surface_counts[key]
            for key in sorted(action_surface_counts)
        },
        "frame_store_digest": frame_store_body["content_digest"],
        "expected_replay_trace_digest": expected_replay_trace_digest,
        "variable_metadata_excluded_from_canonical_digest": list(
            VARIABLE_METADATA_FIELDS
        ),
        "claim_boundary": (
            "Successful action-state-effect observation only; no necessity, "
            "irreversibility, ordering, mechanism, or promotion claim."
        ),
        "digest_excluded_fields": ["content_digest", "trajectory_id"],
    }
    content_digest, trajectory_id = _bind_content_and_id(
        trajectory_body,
        content_namespace="hds-arc3-detailed-teacher-trajectory",
        id_namespace="hds-arc3-detailed-teacher-trajectory-id",
    )
    trajectory_body["content_digest"] = content_digest
    trajectory_body["trajectory_id"] = trajectory_id

    projection_refs = [
        str(cast(Mapping[str, Any], item)["action_record_id"]) for item in projections
    ]
    d02b_body: dict[str, object] = {
        "schema_version": "hds-arc3-teacher-trajectory-v1",
        "domain": "ARC3",
        "source_profile_ref": SOURCE_PROFILE_ID,
        "environment_manifest_ref": ENVIRONMENT_MANIFEST_ID,
        "raw_trajectory_digest": raw_digest,
        "canonical_trajectory_digest": canonical_digest,
        "action_record_refs": projection_refs,
        "raw_observation_refs": [],
        "level_count": target_levels,
        "terminal_state": "WIN",
        "digest_excluded_fields": ["content_digest", "trajectory_id"],
    }
    content_digest, trajectory_id = _bind_content_and_id(
        d02b_body,
        content_namespace="hds-arc3-teacher-trajectory",
        id_namespace="hds-arc3-teacher-trajectory-id",
    )
    d02b_body["content_digest"] = content_digest
    d02b_body["trajectory_id"] = trajectory_id
    certificate = _normalization_certificate(
        raw_digest=raw_digest,
        canonical_digest=canonical_digest,
        replay_capture_digest=replay_capture_digest,
    )
    package_body: dict[str, object] = {
        "schema_version": PACKAGE_VERSION,
        "phase_id": "PH-D05",
        "game_id": source_case_ref,
        "detailed_trajectory": trajectory_body,
        "frame_store": frame_store_body,
        "ph_d02b_action_record_projections": projections,
        "ph_d02b_teacher_trajectory_projection": d02b_body,
        "normalization_certificate": certificate,
        "raw_source_trajectory_projection": raw_override_trajectory,
        "source_access": (
            "DISTILLATION_EXECUTOR_RAW_RECORDING_AND_REPLAY_CAPTURE_ONLY"
        ),
        "environment_source_access": False,
        "hypothesis_generation_count": 0,
        "causal_assertion_count": 0,
        "rule_promotion_count": 0,
        "digest_excluded_fields": [
            "content_digest",
            "package_id",
            "detailed_trajectory",
            "frame_store",
            "normalization_certificate",
            "ph_d02b_action_record_projections",
            "ph_d02b_teacher_trajectory_projection",
            "raw_source_trajectory_projection",
        ],
    }
    package_binding: dict[str, object] = {
        "schema_version": "hds-arc3-teacher-trajectory-package-binding-v1",
        "phase_id": "PH-D05",
        "game_id": source_case_ref,
        "detailed_trajectory_digest": trajectory_body["content_digest"],
        "frame_store_digest": frame_store_body["content_digest"],
        "normalization_certificate_digest": certificate["content_digest"],
        "raw_source_trajectory_projection_digest": (
            raw_override_trajectory.get("content_digest")
            if raw_override_trajectory is not None
            else None
        ),
        "ph_d02b_action_record_digests": [
            cast(Mapping[str, object], item)["content_digest"] for item in projections
        ],
        "ph_d02b_teacher_trajectory_digest": d02b_body["content_digest"],
        "source_access": package_body["source_access"],
        "environment_source_access": False,
        "hypothesis_generation_count": 0,
        "causal_assertion_count": 0,
        "rule_promotion_count": 0,
    }
    package_body["logical_binding_projection"] = package_binding
    package_body["content_digest_scope"] = "LOGICAL_COMPONENT_BINDING_PROJECTION"
    content_digest, package_id = _bind_content_and_id(
        package_binding,
        content_namespace="hds-arc3-teacher-trajectory-package",
        id_namespace="hds-arc3-teacher-trajectory-package-id",
    )
    package_body["content_digest"] = content_digest
    package_body["package_id"] = package_id
    return cast(JsonObject, package_body)


def canonical_invariance_projection(package: Mapping[str, object]) -> JsonObject:
    """Return the exact metadata-free record bound by trajectory hashing."""

    trajectory = _mapping(package.get("detailed_trajectory"), "trajectory")
    steps = _sequence(trajectory.get("steps"), "trajectory.steps")
    canonical_steps: list[JsonValue] = []
    for index, raw_step in enumerate(steps):
        step = _mapping(raw_step, f"steps[{index}]")
        action = _mapping(step.get("action"), f"steps[{index}].action")
        diff = _mapping(step.get("visible_diff"), f"steps[{index}].visible_diff")
        canonical_steps.append(
            cast(
                JsonValue,
                {
                    "step_index": step["step_index"],
                    "action_id": action["action_id"],
                    "action_payload": action["payload"],
                    "reset_scope": action["reset_scope"],
                    "available_actions_before": step["available_actions_before"],
                    "available_actions_after": step["available_actions_after"],
                    "before_canonical_frame_digest": step[
                        "before_canonical_frame_digest"
                    ],
                    "after_canonical_frame_digest": step[
                        "after_canonical_frame_digest"
                    ],
                    "terminal_state_before": step["terminal_state_before"],
                    "terminal_state_after": step["terminal_state_after"],
                    "level_index_before": step["level_index_before"],
                    "level_index_after": step["level_index_after"],
                    "levels_completed_before": step["levels_completed_before"],
                    "levels_completed_after": step["levels_completed_after"],
                    "visible_diff_digest": diff["content_digest"],
                    "progress_delta": step["progress_delta"],
                },
            )
        )
    initial_frame = _string(
        trajectory.get("initial_canonical_frame_digest"),
        "initial_canonical_frame_digest",
    )
    return {
        "trajectory_version": TRAJECTORY_VERSION,
        "observation_projection_version": OBSERVATION_PROJECTION_VERSION,
        "seed": 0,
        "reset_mode": "OFFLINE_FULL_RESET_PER_REPLAY",
        "initial_frame_digest": initial_frame,
        "initial_available_actions": cast(
            JsonValue,
            cast(Mapping[str, Any], steps[0])["available_actions_before"],
        ),
        "initial_terminal_state": "CONTINUE",
        "initial_levels_completed": 0,
        "steps": canonical_steps,
        "final_terminal_state": "WIN",
        "level_completion_count": _integer(
            trajectory.get("level_completion_count"),
            "level_completion_count",
        ),
        "score_or_progress": _integer(
            trajectory.get("score_or_progress"),
            "score_or_progress",
        ),
    }


__all__ = [
    "ACTION_RECORD_VERSION",
    "FRAME_RECORD_VERSION",
    "OBSERVATION_PROJECTION_VERSION",
    "PACKAGE_VERSION",
    "TRAJECTORY_VERSION",
    "TrajectoryNormalizationError",
    "apply_visible_diff",
    "canonical_invariance_projection",
    "decode_frame_rle",
    "encode_frame_rle",
    "normalize_teacher_recording",
    "visible_diff",
]
