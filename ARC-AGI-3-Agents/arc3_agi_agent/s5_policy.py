"""Rendered-only S5 instruction body and bounded action/effect history.

The runtime path in this module accepts only the rendered observation,
available actions, bounded HDS-approved passive memory, and the current
HDS-bound context.  Development Teacher packages and environment identity are
deliberately absent.
"""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import numpy as np

from .context import ContextSnapshot
from .instruction_body import (
    ControlInstruction,
    InstructionQueryResult,
)
from .ir import ActionPredictionIR, HypothesisIR, ObservationIR
from .memory import MemorySnapshot
from .protocol import ComputeRequest, InstructionBodyContract
from .schema import canonical_json, digest_object, forbidden_runtime_paths

S5_POLICY_SCHEMA_VERSION = "arc3-s5-rendered-policy-v1"
S5_POLICY_FORMAT_ID = "rendered-history-mlp"
S5_POLICY_BODY_VERSION = "s5-rendered-history-mlp-v1"
S5_POLICY_MANIFEST_FILENAME = "s5_rendered_policy_v1.json"
S5_POLICY_WEIGHTS_FILENAME = "s5_rendered_policy_v1.npz"
S5_HISTORY_FORMAT = "arc3-s5-rendered-history-v1"
S5_HISTORY_TARGET = "s5-rendered-history"
S5_HISTORY_LIMIT = 16
S5_FEATURE_COUNT = 2360
S5_FRAME_SIDE = 64
S5_PALETTE_SIZE = 16
S5_POINTER_ACTION_ID = 6
S5_RESET_ACTION_ID = 0

_CONTROL_MODES = ("PLAN", "REOBSERVE", "ROLLBACK", "STOP", "SUSPEND")


def _bundle_path(filename: str) -> Path:
    return Path(__file__).resolve().parent / "bundles" / filename


def s5_policy_manifest_digest(value: Mapping[str, object]) -> str:
    """Digest a policy manifest with its self-reference blanked."""

    normalized = dict(value)
    normalized["content_digest"] = ""
    return "sha256:" + hashlib.sha256(
        canonical_json(normalized).encode("utf-8")
    ).hexdigest()


def _integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    return value


def _float(value: object, field_name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be numeric")
    result = float(value)
    if not math.isfinite(result):
        raise ValueError(f"{field_name} must be finite")
    return result


def _mapping(value: object, field_name: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise TypeError(f"{field_name} must be an object")
    return value


def _sequence(value: object, field_name: str) -> Sequence[object]:
    if not isinstance(value, Sequence) or isinstance(
        value,
        (str, bytes, bytearray),
    ):
        raise TypeError(f"{field_name} must be an array")
    return value


@dataclass(frozen=True, slots=True)
class S5HistoryRecord:
    """One observed runtime action and its rendered effect."""

    action_id: int
    horizontal: int = -1
    vertical: int = -1
    target_palette: int = 0
    visible_change: bool = False
    compatibility_reset: bool = False
    source_render_digest: str = ""

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not 0 <= self.action_id <= 7:
            failures.append("S5_HISTORY_ACTION_INVALID")
        if self.action_id == S5_POINTER_ACTION_ID:
            if not 0 <= self.horizontal < S5_FRAME_SIDE:
                failures.append("S5_HISTORY_HORIZONTAL_INVALID")
            if not 0 <= self.vertical < S5_FRAME_SIDE:
                failures.append("S5_HISTORY_VERTICAL_INVALID")
            if not 0 <= self.target_palette < S5_PALETTE_SIZE:
                failures.append("S5_HISTORY_PALETTE_INVALID")
        elif (
            self.horizontal != -1
            or self.vertical != -1
            or self.target_palette != 0
        ):
            failures.append("S5_HISTORY_NON_POINTER_PAYLOAD_PRESENT")
        if self.compatibility_reset != (
            self.action_id == S5_RESET_ACTION_ID
        ):
            failures.append("S5_HISTORY_RESET_SCOPE_INVALID")
        return tuple(sorted(set(failures)))

    def to_payload(self, *, include_effect: bool) -> dict[str, object]:
        payload: dict[str, object] = {
            "action": self.action_id,
            "compatibility_reset": self.compatibility_reset,
            "horizontal": self.horizontal,
            "palette": self.target_palette,
            "source_render": self.source_render_digest,
            "vertical": self.vertical,
        }
        if include_effect:
            payload["changed"] = self.visible_change
        return payload

    @classmethod
    def from_payload(
        cls,
        value: object,
        *,
        include_effect: bool,
    ) -> S5HistoryRecord:
        raw = _mapping(value, "S5 history record")
        expected = {
            "action",
            "compatibility_reset",
            "horizontal",
            "palette",
            "source_render",
            "vertical",
            *(("changed",) if include_effect else ()),
        }
        if set(raw) != expected:
            raise ValueError("S5_HISTORY_RECORD_SCHEMA_INVALID")
        record = cls(
            action_id=_integer(raw["action"], "history.action"),
            horizontal=_integer(raw["horizontal"], "history.horizontal"),
            vertical=_integer(raw["vertical"], "history.vertical"),
            target_palette=_integer(raw["palette"], "history.palette"),
            visible_change=(
                raw["changed"] is True if include_effect else False
            ),
            compatibility_reset=raw["compatibility_reset"] is True,
            source_render_digest=str(raw["source_render"]),
        )
        failures = record.validate()
        if failures:
            raise ValueError(";".join(failures))
        return record


@dataclass(frozen=True, slots=True)
class S5HistoryState:
    """Bounded state materialized solely from passive M."""

    history: tuple[S5HistoryRecord, ...] = ()
    pending: S5HistoryRecord | None = None

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if len(self.history) > S5_HISTORY_LIMIT:
            failures.append("S5_HISTORY_LIMIT_EXCEEDED")
        failures.extend(
            failure
            for record in self.history
            for failure in record.validate()
        )
        if self.pending is not None:
            failures.extend(self.pending.validate())
            if self.pending.visible_change:
                failures.append("S5_PENDING_EFFECT_PREMATURE")
            if not self.pending.source_render_digest:
                failures.append("S5_PENDING_SOURCE_RENDER_MISSING")
        return tuple(sorted(set(failures)))

    def finalize_pending(
        self,
        observation: ObservationIR,
    ) -> S5HistoryState:
        if self.pending is None:
            return self
        changed = (
            self.pending.source_render_digest
            != s5_render_digest(_rendered_matrix(observation))
        )
        finalized = S5HistoryRecord(
            action_id=self.pending.action_id,
            horizontal=self.pending.horizontal,
            vertical=self.pending.vertical,
            target_palette=self.pending.target_palette,
            visible_change=changed,
            compatibility_reset=self.pending.compatibility_reset,
            source_render_digest=self.pending.source_render_digest,
        )
        return S5HistoryState(
            history=(*self.history, finalized)[-S5_HISTORY_LIMIT:],
        )

    def with_pending(self, record: S5HistoryRecord) -> S5HistoryState:
        if self.pending is not None:
            raise ValueError("S5_PENDING_ACTION_ALREADY_PRESENT")
        failures = record.validate()
        if failures:
            raise ValueError(";".join(failures))
        return S5HistoryState(history=self.history, pending=record)

    def retain_observed(
        self,
        record: S5HistoryRecord,
    ) -> S5HistoryState:
        failures = record.validate()
        if failures:
            raise ValueError(";".join(failures))
        return S5HistoryState(
            history=(*self.history, record)[-S5_HISTORY_LIMIT:],
        )

    def to_payload(
        self,
        *,
        input_memory_digest: str,
        policy_digest: str,
        memory_influenced_decision: bool,
    ) -> dict[str, object]:
        return {
            "format": S5_HISTORY_FORMAT,
            "history": [
                item.to_payload(include_effect=True)
                for item in self.history
            ],
            "input_memory_digest": input_memory_digest,
            "memory_influenced_decision": memory_influenced_decision,
            "pending": (
                None
                if self.pending is None
                else self.pending.to_payload(include_effect=False)
            ),
            "policy_digest": policy_digest,
        }


def s5_history_from_memory(memory: MemorySnapshot) -> S5HistoryState:
    entries = tuple(
        entry for entry in memory.entries if entry.target == S5_HISTORY_TARGET
    )
    if not entries:
        return S5HistoryState()
    if len(entries) != 1:
        raise ValueError("S5_HISTORY_TARGET_DUPLICATE")
    payload = entries[0].payload
    if payload.get("format") != S5_HISTORY_FORMAT:
        raise ValueError("S5_HISTORY_FORMAT_INVALID")
    raw_history = _sequence(payload.get("history"), "history")
    raw_pending = payload.get("pending")
    state = S5HistoryState(
        history=tuple(
            S5HistoryRecord.from_payload(item, include_effect=True)
            for item in raw_history
        ),
        pending=(
            None
            if raw_pending is None
            else S5HistoryRecord.from_payload(
                raw_pending,
                include_effect=False,
            )
        ),
    )
    failures = state.validate()
    if failures:
        raise ValueError(";".join(failures))
    return state


def _rendered_matrix(observation: ObservationIR) -> np.ndarray:
    if not observation.rendered_layers:
        raise ValueError("S5_RENDERED_OBSERVATION_MISSING")
    matrix = np.asarray(observation.rendered_layers[-1], dtype=np.uint8)
    if matrix.shape != (S5_FRAME_SIDE, S5_FRAME_SIDE):
        raise ValueError("S5_RENDERED_DIMENSIONS_INVALID")
    if int(matrix.max(initial=0)) >= S5_PALETTE_SIZE:
        raise ValueError("S5_RENDERED_PALETTE_INVALID")
    return matrix


def s5_render_digest(rendered: np.ndarray) -> str:
    matrix = np.asarray(rendered, dtype=np.uint8)
    if matrix.shape != (S5_FRAME_SIDE, S5_FRAME_SIDE):
        raise ValueError("S5_RENDERED_DIMENSIONS_INVALID")
    return "s5-render:" + hashlib.sha256(
        matrix.tobytes(order="C")
    ).hexdigest()


def s5_feature_vector(
    observation: ObservationIR,
    history: tuple[S5HistoryRecord, ...],
) -> np.ndarray:
    """Compile the fixed S5 feature alphabet without identity or source state."""

    return s5_feature_vector_from_render(
        _rendered_matrix(observation),
        observation.available_actions,
        history,
    )


def s5_feature_vector_from_render(
    rendered: np.ndarray,
    available_actions: tuple[int, ...],
    history: tuple[S5HistoryRecord, ...],
) -> np.ndarray:
    """Compile the same feature alphabet from one already-projected render."""

    if len(history) > S5_HISTORY_LIMIT:
        raise ValueError("S5_HISTORY_LIMIT_EXCEEDED")
    matrix = np.asarray(rendered, dtype=np.uint8)
    if matrix.shape != (S5_FRAME_SIDE, S5_FRAME_SIDE):
        raise ValueError("S5_RENDERED_DIMENSIONS_INVALID")
    if int(matrix.max(initial=0)) >= S5_PALETTE_SIZE:
        raise ValueError("S5_RENDERED_PALETTE_INVALID")
    blocks = (
        matrix.reshape(8, 8, 8, 8)
        .transpose(0, 2, 1, 3)
        .reshape(64, 64)
    )
    block_frequencies = np.stack(
        [
            (blocks == color).mean(axis=1)
            for color in range(S5_PALETTE_SIZE)
        ],
        axis=1,
    ).ravel().astype(np.float32)
    downsampled = (
        matrix[::2, ::2].ravel() / np.float32(S5_PALETTE_SIZE - 1)
    ).astype(np.float32)
    palette_stats = np.zeros((S5_PALETTE_SIZE, 3), dtype=np.float32)
    for color in range(S5_PALETTE_SIZE):
        vertical, horizontal = np.where(matrix == color)
        if len(horizontal):
            palette_stats[color] = (
                len(horizontal) / (S5_FRAME_SIDE * S5_FRAME_SIDE),
                horizontal.mean() / (S5_FRAME_SIDE - 1),
                vertical.mean() / (S5_FRAME_SIDE - 1),
            )
    available_mask = np.zeros(8, dtype=np.float32)
    for action_id in available_actions:
        if not 1 <= action_id <= 7:
            raise ValueError("S5_AVAILABLE_ACTION_INVALID")
        available_mask[action_id] = 1.0
    history_features = np.zeros(
        (S5_HISTORY_LIMIT, 16),
        dtype=np.float32,
    )
    for slot, record in enumerate(
        history,
        S5_HISTORY_LIMIT - len(history),
    ):
        failures = record.validate()
        if failures:
            raise ValueError(";".join(failures))
        history_features[slot, record.action_id] = 1.0
        if record.action_id == S5_POINTER_ACTION_ID:
            history_features[slot, 8:11] = (
                record.horizontal / (S5_FRAME_SIDE - 1),
                record.vertical / (S5_FRAME_SIDE - 1),
                record.target_palette / (S5_PALETTE_SIZE - 1),
            )
        history_features[slot, 11:] = (
            record.visible_change,
            record.compatibility_reset,
            record.action_id == S5_RESET_ACTION_ID,
            record.action_id == S5_POINTER_ACTION_ID,
            True,
        )
    features = np.concatenate(
        (
            block_frequencies,
            downsampled,
            palette_stats.ravel(),
            available_mask,
            history_features.ravel(),
        )
    ).astype(np.float32, copy=False)
    if features.shape != (S5_FEATURE_COUNT,):
        raise ValueError("S5_FEATURE_SHAPE_INVALID")
    if not np.isfinite(features).all():
        raise ValueError("S5_FEATURE_NONFINITE")
    return features


@dataclass(frozen=True, slots=True)
class S5MLPHead:
    head_id: str
    classes: tuple[int, ...]
    weight0: np.ndarray = field(repr=False, compare=False)
    bias0: np.ndarray = field(repr=False, compare=False)
    weight1: np.ndarray = field(repr=False, compare=False)
    bias1: np.ndarray = field(repr=False, compare=False)
    _validation_cache: tuple[str, ...] | None = field(
        default=None,
        init=False,
        repr=False,
        compare=False,
    )

    @property
    def parameter_count(self) -> int:
        return sum(
            int(value.size)
            for value in (
                self.weight0,
                self.bias0,
                self.weight1,
                self.bias1,
            )
        )

    def validate(self) -> tuple[str, ...]:
        if self._validation_cache is not None:
            return self._validation_cache
        failures: list[str] = []
        if not self.head_id:
            failures.append("S5_HEAD_ID_MISSING")
        if len(self.classes) < 2:
            failures.append("S5_HEAD_CLASS_COUNT_INVALID")
        if len(set(self.classes)) != len(self.classes):
            failures.append("S5_HEAD_CLASSES_DUPLICATE")
        if self.weight0.shape[0] != S5_FEATURE_COUNT:
            failures.append("S5_HEAD_INPUT_SHAPE_INVALID")
        if self.bias0.shape != (self.weight0.shape[1],):
            failures.append("S5_HEAD_HIDDEN_BIAS_SHAPE_INVALID")
        expected_output = 1 if len(self.classes) == 2 else len(self.classes)
        if self.weight1.shape != (self.weight0.shape[1], expected_output):
            failures.append("S5_HEAD_OUTPUT_SHAPE_INVALID")
        if self.bias1.shape != (expected_output,):
            failures.append("S5_HEAD_OUTPUT_BIAS_SHAPE_INVALID")
        if any(
            not np.isfinite(value).all()
            for value in (
                self.weight0,
                self.bias0,
                self.weight1,
                self.bias1,
            )
        ):
            failures.append("S5_HEAD_PARAMETER_NONFINITE")
        result = tuple(sorted(set(failures)))
        object.__setattr__(self, "_validation_cache", result)
        return result

    def predict(self, features: np.ndarray) -> tuple[int, float]:
        failures = self.validate()
        if failures:
            raise ValueError(";".join(failures))
        if features.shape != (S5_FEATURE_COUNT,):
            raise ValueError("S5_HEAD_FEATURE_SHAPE_INVALID")
        hidden = np.maximum(features @ self.weight0 + self.bias0, 0.0)
        logits = hidden @ self.weight1 + self.bias1
        if logits.shape == (1,):
            index = int(logits[0] > 0.0)
            margin = abs(float(logits[0]))
        else:
            index = int(np.argmax(logits))
            ordered = np.partition(logits, -2)
            margin = float(ordered[-1] - ordered[-2])
        return self.classes[index], margin


@dataclass(frozen=True, slots=True)
class S5PolicyDecision:
    action_id: int
    horizontal: int
    vertical: int
    target_palette: int
    compatibility_reset: bool
    action_head_id: str
    action_margin: float
    horizontal_margin: float | None
    vertical_margin: float | None
    feature_digest: str
    source_render_digest: str
    history_count: int
    memory_influenced: bool

    def pending_record(self) -> S5HistoryRecord:
        return S5HistoryRecord(
            action_id=self.action_id,
            horizontal=self.horizontal,
            vertical=self.vertical,
            target_palette=self.target_palette,
            compatibility_reset=self.compatibility_reset,
            source_render_digest=self.source_render_digest,
        )


@dataclass(frozen=True, slots=True)
class S5InstructionQueryResult(InstructionQueryResult):
    policy_decision: S5PolicyDecision | None = None
    finalized_history: S5HistoryState = field(
        default_factory=S5HistoryState
    )


@dataclass(frozen=True, slots=True)
class S5RenderedPolicyBody:
    """Versioned, addressable P compiled into fixed MLP parameters."""

    _manifest: Mapping[str, Any]
    _manifest_bytes: bytes = field(repr=False, compare=False)
    _weights_sha256: str
    contract: InstructionBodyContract
    action_heads: Mapping[tuple[int, ...], S5MLPHead] = field(
        repr=False,
        compare=False,
    )
    horizontal_head: S5MLPHead = field(repr=False, compare=False)
    vertical_head: S5MLPHead = field(repr=False, compare=False)
    _validation_cache: tuple[str, ...] | None = field(
        default=None,
        init=False,
        repr=False,
        compare=False,
    )

    @property
    def format_id(self) -> str:
        return S5_POLICY_FORMAT_ID

    @property
    def body_version(self) -> str:
        return self.contract.body_version

    @property
    def provenance_digest(self) -> str:
        return self.contract.provenance_digest

    def digest(self) -> str:
        return self.contract.content_digest

    def serialize(self) -> bytes:
        return self._manifest_bytes

    @property
    def parameter_count(self) -> int:
        return sum(
            head.parameter_count for head in self.action_heads.values()
        ) + self.horizontal_head.parameter_count + self.vertical_head.parameter_count

    def validate(self) -> tuple[str, ...]:
        if self._validation_cache is not None:
            return self._validation_cache
        failures = list(self.contract.validate())
        if self.format_id != S5_POLICY_FORMAT_ID:
            failures.append("S5_POLICY_FORMAT_INVALID")
        if self.body_version != S5_POLICY_BODY_VERSION:
            failures.append("S5_POLICY_VERSION_INVALID")
        if self._manifest.get("schema_version") != S5_POLICY_SCHEMA_VERSION:
            failures.append("S5_POLICY_SCHEMA_INVALID")
        if self._manifest.get("runtime_identity_free") is not True:
            failures.append("S5_POLICY_IDENTITY_FLAG_INVALID")
        if self._manifest.get("weights_sha256") != self._weights_sha256:
            failures.append("S5_POLICY_WEIGHTS_DIGEST_MISMATCH")
        if self._manifest.get("content_digest") != s5_policy_manifest_digest(
            self._manifest
        ):
            failures.append("S5_POLICY_CONTENT_DIGEST_MISMATCH")
        if self.digest() != self._manifest.get("content_digest"):
            failures.append("S5_POLICY_CONTRACT_DIGEST_MISMATCH")
        if self.provenance_digest != self._manifest.get("provenance_digest"):
            failures.append("S5_POLICY_PROVENANCE_MISMATCH")
        if forbidden_runtime_paths(self._manifest):
            failures.append("S5_POLICY_RUNTIME_IDENTITY_FORBIDDEN")
        expected_surfaces = {
            tuple(
                _integer(item, "surface[]")
                for item in _sequence(
                    _mapping(raw, "action head").get("surface"),
                    "surface",
                )
            )
            for raw in _sequence(
                self._manifest.get("action_heads"),
                "action_heads",
            )
        }
        if set(self.action_heads) != expected_surfaces:
            failures.append("S5_POLICY_ACTION_SURFACE_MISMATCH")
        failures.extend(
            failure
            for head in (
                *self.action_heads.values(),
                self.horizontal_head,
                self.vertical_head,
            )
            for failure in head.validate()
        )
        if self.parameter_count != self._manifest.get("parameter_count"):
            failures.append("S5_POLICY_PARAMETER_COUNT_MISMATCH")
        result = tuple(sorted(set(failures)))
        object.__setattr__(self, "_validation_cache", result)
        return result

    def _bound_history(
        self,
        observation: ObservationIR,
        context: ContextSnapshot,
        memory: MemorySnapshot,
    ) -> S5HistoryState:
        state = s5_history_from_memory(memory).finalize_pending(observation)
        known_actions = tuple(item.action_id for item in state.history)
        if known_actions and (
            context.action_history[-len(known_actions) :] != known_actions
        ):
            raise ValueError("S5_CONTEXT_MEMORY_HISTORY_MISMATCH")
        if not known_actions and context.action_history:
            raise ValueError("S5_CONTEXT_HISTORY_NOT_RETAINED")
        return state

    def predict(
        self,
        observation: ObservationIR,
        context: ContextSnapshot,
        memory: MemorySnapshot,
    ) -> tuple[S5PolicyDecision, S5HistoryState]:
        state = self._bound_history(observation, context, memory)
        features = s5_feature_vector(observation, state.history)
        surface = tuple(observation.available_actions)
        action_head = self.action_heads.get(surface)
        if action_head is None:
            raise ValueError("S5_ACTION_SURFACE_UNKNOWN")
        action_id, action_margin = action_head.predict(features)
        if action_id != S5_RESET_ACTION_ID and action_id not in surface:
            raise ValueError("S5_PREDICTED_ACTION_UNAVAILABLE")
        horizontal = vertical = -1
        horizontal_margin: float | None = None
        vertical_margin: float | None = None
        target_palette = 0
        if action_id == S5_POINTER_ACTION_ID:
            horizontal, horizontal_margin = self.horizontal_head.predict(
                features
            )
            vertical, vertical_margin = self.vertical_head.predict(features)
            matrix = _rendered_matrix(observation)
            if not (
                0 <= horizontal < S5_FRAME_SIDE
                and 0 <= vertical < S5_FRAME_SIDE
            ):
                raise ValueError("S5_POINTER_PREDICTION_OUT_OF_BOUNDS")
            target_palette = int(matrix[vertical, horizontal])
        decision = S5PolicyDecision(
            action_id=action_id,
            horizontal=horizontal,
            vertical=vertical,
            target_palette=target_palette,
            compatibility_reset=action_id == S5_RESET_ACTION_ID,
            action_head_id=action_head.head_id,
            action_margin=action_margin,
            horizontal_margin=horizontal_margin,
            vertical_margin=vertical_margin,
            feature_digest="s5-feature:" + hashlib.sha256(
                features.tobytes(order="C")
            ).hexdigest(),
            source_render_digest=s5_render_digest(
                _rendered_matrix(observation)
            ),
            history_count=len(state.history),
            memory_influenced=bool(state.history),
        )
        return decision, state

    def query(
        self,
        request: ComputeRequest,
        observation: ObservationIR,
        context: ContextSnapshot,
        memory_view: MemorySnapshot,
    ) -> S5InstructionQueryResult:
        failures = list(self.validate())
        failures.extend(request.validate(self.contract))
        if request.observation_signature != observation.frame_signature:
            failures.append("S5_QUERY_OBSERVATION_MISMATCH")
        if request.context_signature != context.digest:
            failures.append("S5_QUERY_CONTEXT_MISMATCH")
        if request.memory_signature != memory_view.digest:
            failures.append("S5_QUERY_MEMORY_MISMATCH")
        if context.current_observation != observation:
            failures.append("S5_QUERY_CONTEXT_OBSERVATION_MISMATCH")
        if failures:
            raise ValueError(";".join(sorted(set(failures))))
        decision, state = self.predict(
            observation,
            context,
            memory_view,
        )
        uncertainty = min(1.0, 1.0 / (1.0 + decision.action_margin))
        prediction_items = tuple(
            ActionPredictionIR(
                action_id=action_id,
                predicted_effects=(
                    "NO_VISIBLE_CHANGE",
                    "VISIBLE_STATE_CHANGE",
                ),
                progress_likelihood=(
                    0.95 if action_id == decision.action_id else 0.05
                ),
                hazard_likelihood=0.01,
                information_gain=0.5,
                candidate_prior=(
                    0.99 if action_id == decision.action_id else 0.01
                ),
                uncertainty=uncertainty,
                evidence_refs=(
                    self.provenance_digest,
                    decision.feature_digest,
                ),
                instruction_refs=(decision.action_head_id,),
                preconditions=(f"ACTION{action_id}_AVAILABLE",),
                falsification_conditions=(
                    "observed action effect contradicts rendered policy",
                ),
            )
            for action_id in observation.available_actions
        )
        hypothesis_seed = {
            "body": self.digest(),
            "feature": decision.feature_digest,
            "action": decision.action_id,
        }
        hypothesis_suffix = digest_object(hypothesis_seed)[:20]
        hypotheses = (
            HypothesisIR(
                hypothesis_id=f"hypothesis:s5:{hypothesis_suffix}:primary",
                hypothesis_type="rendered-history-policy",
                claims=("selected action advances the rendered policy",),
                predictions=("VISIBLE_STATE_CHANGE",),
                falsification_conditions=(
                    "rendered transition diverges from policy prediction",
                ),
                support=(
                    self.provenance_digest,
                    decision.feature_digest,
                ),
                confidence=1.0 - uncertainty,
                state="PROPOSED",
            ),
            HypothesisIR(
                hypothesis_id=f"hypothesis:s5:{hypothesis_suffix}:counter",
                hypothesis_type="counter-hypothesis",
                claims=("selected action may preserve the rendered state",),
                predictions=("NO_VISIBLE_CHANGE",),
                falsification_conditions=(
                    "rendered transition changes under selected action",
                ),
                support=(self.provenance_digest,),
                confidence=uncertainty,
                state="PROPOSED",
            ),
        )
        controls = tuple(
            ControlInstruction(
                mode=mode,
                preconditions=("rendered observation is available",),
                expected_progress=0.0,
                information_gain=0.1,
                expected_risk=0.0,
                repetition_cost=0.0,
                rollback_cost=0.0,
                falsification_conditions=(
                    "a closed rendered action candidate is available",
                ),
                provenance=(self.provenance_digest,),
            )
            for mode in _CONTROL_MODES
        )
        representations = (
            f"available-action-count:{len(observation.available_actions)}",
            f"bounded-history-count:{len(state.history)}",
            "rendered-frame:present",
            f"terminal:{observation.terminal_state.casefold()}",
        )
        query_digest = "query:s5:" + digest_object(
            {
                "request": request,
                "body": self.digest(),
                "feature": decision.feature_digest,
                "memory": memory_view.digest,
                "action": decision.action_id,
            }
        )[:24]
        result = S5InstructionQueryResult(
            body_format=self.format_id,
            body_version=self.body_version,
            body_digest=self.digest(),
            query_digest=query_digest,
            representations=representations,
            retrieved_items=(
                decision.action_head_id,
                "bounded-rendered-history",
            ),
            hypotheses=hypotheses,
            predictions=prediction_items,
            controls=controls,
            uncertainty=uncertainty,
            falsification_conditions=(
                "selected action is unavailable",
                "observed transition leaves the compiled policy support",
            ),
            provenance=(
                self.provenance_digest,
                self.digest(),
                decision.feature_digest,
            ),
            policy_decision=decision,
            finalized_history=state,
        )
        result_failures = result.validate(observation)
        if result_failures:
            raise ValueError(";".join(result_failures))
        return result


def _load_head(
    arrays: Mapping[str, np.ndarray],
    *,
    head_id: str,
    classes: tuple[int, ...],
) -> S5MLPHead:
    required = tuple(f"{head_id}_{suffix}" for suffix in ("w0", "b0", "w1", "b1"))
    if any(name not in arrays for name in required):
        raise ValueError(f"S5_HEAD_ARRAY_MISSING:{head_id}")
    parameters = [
        np.asarray(arrays[name], dtype=np.float32)
        for name in required
    ]
    for parameter in parameters:
        parameter.setflags(write=False)
    return S5MLPHead(
        head_id=head_id,
        classes=classes,
        weight0=parameters[0],
        bias0=parameters[1],
        weight1=parameters[2],
        bias1=parameters[3],
    )


def load_s5_rendered_policy_body(
    *,
    manifest_path: Path | None = None,
    weights_path: Path | None = None,
) -> S5RenderedPolicyBody:
    manifest_path = manifest_path or _bundle_path(S5_POLICY_MANIFEST_FILENAME)
    weights_path = weights_path or _bundle_path(S5_POLICY_WEIGHTS_FILENAME)
    manifest_bytes = manifest_path.read_bytes()
    value = json.loads(manifest_bytes.decode("utf-8"))
    manifest = _mapping(value, "S5 policy manifest")
    weights_bytes = weights_path.read_bytes()
    weights_sha256 = hashlib.sha256(weights_bytes).hexdigest()
    with np.load(weights_path, allow_pickle=False) as loaded:
        arrays = {name: np.array(loaded[name], copy=True) for name in loaded.files}
    action_heads: dict[tuple[int, ...], S5MLPHead] = {}
    for raw in _sequence(manifest.get("action_heads"), "action_heads"):
        item = _mapping(raw, "action head")
        head_id = str(item.get("head_id", ""))
        classes = tuple(
            _integer(value, "classes[]")
            for value in _sequence(item.get("classes"), "classes")
        )
        surface = tuple(
            _integer(value, "surface[]")
            for value in _sequence(item.get("surface"), "surface")
        )
        if surface in action_heads:
            raise ValueError("S5_ACTION_SURFACE_DUPLICATE")
        action_heads[surface] = _load_head(
            arrays,
            head_id=head_id,
            classes=classes,
        )
    pointer = _mapping(manifest.get("pointer_heads"), "pointer_heads")
    horizontal_meta = _mapping(pointer.get("horizontal"), "horizontal head")
    vertical_meta = _mapping(pointer.get("vertical"), "vertical head")
    horizontal_head = _load_head(
        arrays,
        head_id=str(horizontal_meta.get("head_id", "")),
        classes=tuple(
            _integer(value, "horizontal classes[]")
            for value in _sequence(
                horizontal_meta.get("classes"),
                "horizontal classes",
            )
        ),
    )
    vertical_head = _load_head(
        arrays,
        head_id=str(vertical_meta.get("head_id", "")),
        classes=tuple(
            _integer(value, "vertical classes[]")
            for value in _sequence(
                vertical_meta.get("classes"),
                "vertical classes",
            )
        ),
    )
    contract = InstructionBodyContract(
        format_id=S5_POLICY_FORMAT_ID,
        schema_version=S5_POLICY_SCHEMA_VERSION,
        body_version=str(manifest.get("body_version", "")),
        content_digest=str(manifest.get("content_digest", "")),
        provenance_digest=str(manifest.get("provenance_digest", "")),
        input_contract=(
            "compute-request",
            "rendered-observation",
            "available-actions",
            "bounded-action-effect-history",
            "hds-approved-passive-memory",
        ),
        state_contract=(
            "immutable-parameter-body",
            "bounded-history-16",
            "explicit-development-compile-only",
        ),
        output_contract=(
            "hypotheses",
            "counter-hypotheses",
            "action-prediction",
            "transient-pointer-payload",
            "uncertainty",
            "falsification-conditions",
        ),
        compile_contract=(
            "development-only-privileged-input",
            "runtime-artifact-excludes-training-examples",
            "deterministic-seed",
            "content-addressed-output",
        ),
        bound=True,
    )
    body = S5RenderedPolicyBody(
        _manifest=dict(manifest),
        _manifest_bytes=manifest_bytes,
        _weights_sha256=weights_sha256,
        contract=contract,
        action_heads=action_heads,
        horizontal_head=horizontal_head,
        vertical_head=vertical_head,
    )
    failures = body.validate()
    if failures:
        raise ValueError(";".join(failures))
    return body


__all__ = [
    "S5_FEATURE_COUNT",
    "S5_FRAME_SIDE",
    "S5_HISTORY_FORMAT",
    "S5_HISTORY_LIMIT",
    "S5_HISTORY_TARGET",
    "S5_POINTER_ACTION_ID",
    "S5_POLICY_BODY_VERSION",
    "S5_POLICY_FORMAT_ID",
    "S5_POLICY_MANIFEST_FILENAME",
    "S5_POLICY_SCHEMA_VERSION",
    "S5_POLICY_WEIGHTS_FILENAME",
    "S5HistoryRecord",
    "S5HistoryState",
    "S5InstructionQueryResult",
    "S5PolicyDecision",
    "S5RenderedPolicyBody",
    "load_s5_rendered_policy_body",
    "s5_feature_vector",
    "s5_feature_vector_from_render",
    "s5_history_from_memory",
    "s5_policy_manifest_digest",
    "s5_render_digest",
]
