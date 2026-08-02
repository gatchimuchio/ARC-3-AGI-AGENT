"""Compiled rendered-policy P for the active GenericAGIRuntime.

This module contains only identity-free runtime inference.  Development
examples, environment identities, source state, hidden state, answer maps, and
recorded action sequences are not accepted by its public contract.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Final

import numpy as np

from .generic_compute import (
    GenericInstructionBody,
    HybridRelationalInstructionBody,
    InstructionBodyResult,
)
from .generic_memory import SemanticRecord
from .generic_types import (
    ActionDescriptor,
    ActionEffectRecord,
    GenericObservation,
    GenericPrediction,
    RelationalRepresentation,
)
from .schema import canonical_json, digest_object, forbidden_runtime_paths
from .taint import COORDINATE_PROVENANCE_CURRENT_RENDER

COMPILED_POLICY_SCHEMA_VERSION: Final = "arc3-generic-compiled-policy-v1"
COMPILED_POLICY_FORMAT_ID: Final = "generic-autonomous-rendered-hybrid"
COMPILED_POLICY_BODY_VERSION: Final = (
    "generic-autonomous-rendered-hybrid-v1"
)
COMPILED_POLICY_MANIFEST_FILENAME: Final = (
    "generic_autonomous_policy_v1.json"
)
COMPILED_POLICY_WEIGHTS_FILENAME: Final = (
    "generic_autonomous_policy_v1.npz"
)
COMPILED_POLICY_FEATURE_COUNT: Final = 2360
COMPILED_POLICY_FRAME_SIDE: Final = 64
COMPILED_POLICY_PALETTE_SIZE: Final = 16
COMPILED_POLICY_HISTORY_LIMIT: Final = 16
COMPILED_POLICY_POINTER_ACTION_ID: Final = 6
COMPILED_POLICY_RESET_ACTION_ID: Final = 0


def _bundle_path(filename: str) -> Path:
    return Path(__file__).resolve().parent / "bundles" / filename


def compiled_policy_manifest_digest(
    value: Mapping[str, object],
) -> str:
    normalized = dict(value)
    normalized["content_digest"] = ""
    return "compiled-policy:" + hashlib.sha256(
        canonical_json(normalized).encode("utf-8")
    ).hexdigest()


def _integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    return value


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


def _rendered_matrix(observation: GenericObservation) -> np.ndarray:
    if not observation.rendered_layers:
        raise ValueError("COMPILED_POLICY_RENDERED_OBSERVATION_MISSING")
    matrix = np.asarray(observation.rendered_layers[-1], dtype=np.uint8)
    if matrix.shape != (
        COMPILED_POLICY_FRAME_SIDE,
        COMPILED_POLICY_FRAME_SIDE,
    ):
        raise ValueError("COMPILED_POLICY_RENDERED_DIMENSIONS_INVALID")
    if int(matrix.max(initial=0)) >= COMPILED_POLICY_PALETTE_SIZE:
        raise ValueError("COMPILED_POLICY_RENDERED_PALETTE_INVALID")
    return matrix


def compiled_policy_feature_vector(
    rendered: np.ndarray,
    available_actions: tuple[int, ...],
    history: tuple[ActionEffectRecord, ...],
) -> np.ndarray:
    """Compile a fixed rendered/action/effect feature vector."""

    if len(history) > COMPILED_POLICY_HISTORY_LIMIT:
        raise ValueError("COMPILED_POLICY_HISTORY_LIMIT_EXCEEDED")
    matrix = np.asarray(rendered, dtype=np.uint8)
    expected_shape = (
        COMPILED_POLICY_FRAME_SIDE,
        COMPILED_POLICY_FRAME_SIDE,
    )
    if matrix.shape != expected_shape:
        raise ValueError("COMPILED_POLICY_RENDERED_DIMENSIONS_INVALID")
    if int(matrix.max(initial=0)) >= COMPILED_POLICY_PALETTE_SIZE:
        raise ValueError("COMPILED_POLICY_RENDERED_PALETTE_INVALID")
    blocks = (
        matrix.reshape(8, 8, 8, 8)
        .transpose(0, 2, 1, 3)
        .reshape(64, 64)
    )
    block_frequencies = np.stack(
        [
            (blocks == color).mean(axis=1)
            for color in range(COMPILED_POLICY_PALETTE_SIZE)
        ],
        axis=1,
    ).ravel().astype(np.float32)
    downsampled = (
        matrix[::2, ::2].ravel()
        / np.float32(COMPILED_POLICY_PALETTE_SIZE - 1)
    ).astype(np.float32)
    palette_stats = np.zeros(
        (COMPILED_POLICY_PALETTE_SIZE, 3),
        dtype=np.float32,
    )
    for color in range(COMPILED_POLICY_PALETTE_SIZE):
        vertical, horizontal = np.where(matrix == color)
        if len(horizontal):
            palette_stats[color] = (
                len(horizontal)
                / (
                    COMPILED_POLICY_FRAME_SIDE
                    * COMPILED_POLICY_FRAME_SIDE
                ),
                horizontal.mean() / (COMPILED_POLICY_FRAME_SIDE - 1),
                vertical.mean() / (COMPILED_POLICY_FRAME_SIDE - 1),
            )
    available_mask = np.zeros(8, dtype=np.float32)
    for action_id in available_actions:
        if not 1 <= action_id <= 7:
            raise ValueError("COMPILED_POLICY_AVAILABLE_ACTION_INVALID")
        available_mask[action_id] = 1.0
    history_features = np.zeros(
        (COMPILED_POLICY_HISTORY_LIMIT, 16),
        dtype=np.float32,
    )
    for slot, record in enumerate(
        history,
        COMPILED_POLICY_HISTORY_LIMIT - len(history),
    ):
        failures = record.validate()
        if failures:
            raise ValueError(";".join(failures))
        if not 0 <= record.action_id <= 7:
            raise ValueError("COMPILED_POLICY_HISTORY_ACTION_INVALID")
        history_features[slot, record.action_id] = 1.0
        if record.action_id == COMPILED_POLICY_POINTER_ACTION_ID:
            payload = record.payload()
            history_features[slot, 8:11] = (
                payload["x"] / (COMPILED_POLICY_FRAME_SIDE - 1),
                payload["y"] / (COMPILED_POLICY_FRAME_SIDE - 1),
                record.target_palette
                / (COMPILED_POLICY_PALETTE_SIZE - 1),
            )
        history_features[slot, 11:] = (
            record.visible_change,
            record.compatibility_reset,
            record.action_id == COMPILED_POLICY_RESET_ACTION_ID,
            record.action_id == COMPILED_POLICY_POINTER_ACTION_ID,
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
    if features.shape != (COMPILED_POLICY_FEATURE_COUNT,):
        raise ValueError("COMPILED_POLICY_FEATURE_SHAPE_INVALID")
    if not np.isfinite(features).all():
        raise ValueError("COMPILED_POLICY_FEATURE_NONFINITE")
    return features


@dataclass(frozen=True, slots=True)
class CompiledDenseHead:
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
            failures.append("COMPILED_POLICY_HEAD_ID_MISSING")
        if len(self.classes) < 2:
            failures.append("COMPILED_POLICY_HEAD_CLASS_COUNT_INVALID")
        if len(set(self.classes)) != len(self.classes):
            failures.append("COMPILED_POLICY_HEAD_CLASSES_DUPLICATE")
        if self.weight0.shape[0] != COMPILED_POLICY_FEATURE_COUNT:
            failures.append("COMPILED_POLICY_HEAD_INPUT_SHAPE_INVALID")
        if self.bias0.shape != (self.weight0.shape[1],):
            failures.append("COMPILED_POLICY_HEAD_HIDDEN_BIAS_SHAPE_INVALID")
        expected_output = 1 if len(self.classes) == 2 else len(self.classes)
        if self.weight1.shape != (
            self.weight0.shape[1],
            expected_output,
        ):
            failures.append("COMPILED_POLICY_HEAD_OUTPUT_SHAPE_INVALID")
        if self.bias1.shape != (expected_output,):
            failures.append("COMPILED_POLICY_HEAD_OUTPUT_BIAS_SHAPE_INVALID")
        if any(
            not np.isfinite(value).all()
            for value in (
                self.weight0,
                self.bias0,
                self.weight1,
                self.bias1,
            )
        ):
            failures.append("COMPILED_POLICY_HEAD_PARAMETER_NONFINITE")
        result = tuple(sorted(set(failures)))
        object.__setattr__(self, "_validation_cache", result)
        return result

    def predict(self, features: np.ndarray) -> tuple[int, float]:
        failures = self.validate()
        if failures:
            raise ValueError(";".join(failures))
        if features.shape != (COMPILED_POLICY_FEATURE_COUNT,):
            raise ValueError("COMPILED_POLICY_HEAD_FEATURE_SHAPE_INVALID")
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
class CompiledPolicyDecision:
    action_id: int
    horizontal: int
    vertical: int
    target_palette: int
    head_id: str
    action_margin: float
    feature_digest: str
    memory_influenced: bool


@dataclass(frozen=True, slots=True)
class CompiledAutonomousInstructionBody:
    """One composable P: compiled rendered policy plus structural grammar."""

    _manifest: Mapping[str, Any] = field(repr=False, compare=False)
    _manifest_bytes: bytes = field(repr=False, compare=False)
    _weights_sha256: str
    action_heads: Mapping[tuple[int, ...], CompiledDenseHead] = field(
        repr=False,
        compare=False,
    )
    horizontal_head: CompiledDenseHead = field(repr=False, compare=False)
    vertical_head: CompiledDenseHead = field(repr=False, compare=False)
    structural: GenericInstructionBody = field(
        default_factory=HybridRelationalInstructionBody,
        repr=False,
    )
    _validation_cache: tuple[str, ...] | None = field(
        default=None,
        init=False,
        repr=False,
        compare=False,
    )

    def format_id(self) -> str:
        return COMPILED_POLICY_FORMAT_ID

    def body_version(self) -> str:
        return str(self._manifest.get("body_version", ""))

    def provenance_digest(self) -> str:
        return str(self._manifest.get("provenance_digest", ""))

    def digest(self) -> str:
        return str(self._manifest.get("content_digest", ""))

    def serialize(self) -> bytes:
        return self._manifest_bytes

    @property
    def parameter_count(self) -> int:
        return sum(
            head.parameter_count for head in self.action_heads.values()
        ) + self.horizontal_head.parameter_count + self.vertical_head.parameter_count

    def tensor_arrays(self) -> dict[str, np.ndarray]:
        heads = (
            *tuple(self.action_heads.values()),
            self.horizontal_head,
            self.vertical_head,
        )
        return {
            f"{head.head_id}_{suffix}": np.asarray(value, dtype=np.float16)
            for head in heads
            for suffix, value in (
                ("w0", head.weight0),
                ("b0", head.bias0),
                ("w1", head.weight1),
                ("b1", head.bias1),
            )
        }

    def validate(self) -> tuple[str, ...]:
        if self._validation_cache is not None:
            return self._validation_cache
        failures: list[str] = []
        if self._manifest.get("schema_version") != (
            COMPILED_POLICY_SCHEMA_VERSION
        ):
            failures.append("COMPILED_POLICY_SCHEMA_INVALID")
        if self._manifest.get("format_id") != COMPILED_POLICY_FORMAT_ID:
            failures.append("COMPILED_POLICY_FORMAT_INVALID")
        if self.body_version() != COMPILED_POLICY_BODY_VERSION:
            failures.append("COMPILED_POLICY_VERSION_INVALID")
        if self._manifest.get("runtime_identity_free") is not True:
            failures.append("COMPILED_POLICY_IDENTITY_FLAG_INVALID")
        if (
            self._manifest.get("runtime_artifact_contains_examples")
            is not False
        ):
            failures.append("COMPILED_POLICY_EXAMPLE_BOUNDARY_INVALID")
        if self._manifest.get("weights_sha256") != self._weights_sha256:
            failures.append("COMPILED_POLICY_WEIGHTS_DIGEST_MISMATCH")
        if self._manifest.get("content_digest") != (
            compiled_policy_manifest_digest(self._manifest)
        ):
            failures.append("COMPILED_POLICY_CONTENT_DIGEST_MISMATCH")
        if self._manifest.get("structural_body_digest") != (
            self.structural.digest()
        ):
            failures.append("COMPILED_POLICY_STRUCTURAL_BINDING_MISMATCH")
        if forbidden_runtime_paths(self._manifest):
            failures.append("COMPILED_POLICY_RUNTIME_IDENTITY_FORBIDDEN")
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
            failures.append("COMPILED_POLICY_ACTION_SURFACE_MISMATCH")
        failures.extend(self.structural.validate())
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
            failures.append("COMPILED_POLICY_PARAMETER_COUNT_MISMATCH")
        result = tuple(sorted(set(failures)))
        object.__setattr__(self, "_validation_cache", result)
        return result

    def supports(self, observation: GenericObservation) -> bool:
        if tuple(observation.available_actions) not in self.action_heads:
            return False
        if not observation.rendered_layers:
            return False
        matrix = observation.rendered_layers[-1]
        return (
            len(matrix) == COMPILED_POLICY_FRAME_SIDE
            and all(
                len(row) == COMPILED_POLICY_FRAME_SIDE for row in matrix
            )
            and all(
                0 <= value < COMPILED_POLICY_PALETTE_SIZE
                for row in matrix
                for value in row
            )
        )

    def semantic_causal_memory_required(
        self,
        observation: GenericObservation,
    ) -> bool:
        """Use semantic M only when the structural fallback is active."""

        return not self.supports(observation)

    def explicit_rollback_cycle_required(
        self,
        observation: GenericObservation,
    ) -> bool:
        """Let compiled control states consume their trained reset cycle."""

        return (
            observation.terminal_state == "GAME_OVER"
            and self.supports(observation)
        )

    def predict(
        self,
        observation: GenericObservation,
        history: tuple[ActionEffectRecord, ...],
    ) -> CompiledPolicyDecision:
        if not self.supports(observation):
            raise ValueError("COMPILED_POLICY_INPUT_UNSUPPORTED")
        features = compiled_policy_feature_vector(
            _rendered_matrix(observation),
            tuple(observation.available_actions),
            history,
        )
        head = self.action_heads[tuple(observation.available_actions)]
        action_id, action_margin = head.predict(features)
        horizontal = -1
        vertical = -1
        target_palette = 0
        if action_id == COMPILED_POLICY_POINTER_ACTION_ID:
            horizontal, _ = self.horizontal_head.predict(features)
            vertical, _ = self.vertical_head.predict(features)
            if not (
                0 <= horizontal < COMPILED_POLICY_FRAME_SIDE
                and 0 <= vertical < COMPILED_POLICY_FRAME_SIDE
            ):
                raise ValueError(
                    "COMPILED_POLICY_POINTER_PREDICTION_OUT_OF_BOUNDS"
                )
            target_palette = int(
                _rendered_matrix(observation)[vertical, horizontal]
            )
        return CompiledPolicyDecision(
            action_id=action_id,
            horizontal=horizontal,
            vertical=vertical,
            target_palette=target_palette,
            head_id=head.head_id,
            action_margin=action_margin,
            feature_digest="compiled-policy-feature:"
            + hashlib.sha256(features.tobytes(order="C")).hexdigest(),
            memory_influenced=bool(history),
        )

    @staticmethod
    def _existing_descriptor(
        descriptors: Sequence[ActionDescriptor],
        action_id: int,
    ) -> ActionDescriptor:
        try:
            return next(
                descriptor
                for descriptor in descriptors
                if descriptor.action_id == action_id
            )
        except StopIteration as error:
            raise ValueError(
                "COMPILED_POLICY_LEGAL_DESCRIPTOR_MISSING"
            ) from error

    def _selected_descriptor(
        self,
        *,
        decision: CompiledPolicyDecision,
        observation: GenericObservation,
        descriptors: tuple[ActionDescriptor, ...],
    ) -> ActionDescriptor:
        if decision.action_id != COMPILED_POLICY_POINTER_ACTION_ID:
            return self._existing_descriptor(
                descriptors,
                decision.action_id,
            )
        ordinal = observation.available_actions.index(
            COMPILED_POLICY_POINTER_ACTION_ID
        )
        descriptor = ActionDescriptor(
            action_id=COMPILED_POLICY_POINTER_ACTION_ID,
            surface_ordinal=ordinal,
            semantic_key=f"surface:{ordinal}:dynamic-rendered-pointer",
            payload_items=(
                ("x", decision.horizontal),
                ("y", decision.vertical),
            ),
            target_role=None,
            coordinate_provenance=COORDINATE_PROVENANCE_CURRENT_RENDER,
            coordinate_observation_digest=observation.digest(),
        )
        failures = descriptor.validate(observation)
        if failures:
            raise ValueError(";".join(failures))
        return descriptor

    def query(
        self,
        representation: RelationalRepresentation,
        descriptors: tuple[ActionDescriptor, ...],
        records: tuple[SemanticRecord, ...],
        *,
        observation: GenericObservation | None = None,
        action_history: tuple[ActionEffectRecord, ...] = (),
    ) -> InstructionBodyResult:
        failures = self.validate()
        if failures:
            raise ValueError(";".join(failures))
        if observation is None or not self.supports(observation):
            return self.structural.query(
                representation,
                descriptors,
                records,
                observation=observation,
                action_history=action_history,
            )
        if observation.terminal_state == "GAME_OVER":
            history_ref = "bounded-action-effect-memory:" + digest_object(
                action_history
            )
            rollback_refs = tuple(
                sorted(
                    (
                        self.provenance_digest(),
                        "compiled-policy-control:game-over-rollback",
                        history_ref,
                    )
                )
            )
            return InstructionBodyResult(
                predictions=(),
                query_digest="compiled-policy-query:"
                + digest_object(
                    {
                        "body": self.digest(),
                        "observation": observation.digest(),
                        "representation": representation.digest_value,
                        "history": history_ref,
                        "control": "ROLLBACK",
                    }
                ),
                selected_instruction_refs=rollback_refs,
                control_operation="ROLLBACK",
                control_instruction_refs=rollback_refs,
            )
        decision = self.predict(observation, action_history)
        uncertainty = min(
            0.49,
            1.0 / (1.0 + max(0.0, decision.action_margin)),
        )
        history_ref = "bounded-action-effect-memory:" + digest_object(
            action_history
        )
        common_refs = (
            self.provenance_digest(),
            decision.head_id,
            decision.feature_digest,
            history_ref,
        )
        predictions: list[GenericPrediction] = []
        control_operation = ""
        control_refs: tuple[str, ...] = ()
        if decision.action_id == COMPILED_POLICY_RESET_ACTION_ID:
            control_operation = "ROLLBACK"
            control_refs = common_refs
        else:
            selected = self._selected_descriptor(
                decision=decision,
                observation=observation,
                descriptors=descriptors,
            )
            predictions.append(
                GenericPrediction(
                    descriptor=selected,
                    predicted_effects=(
                        "LEVEL_PROGRESS",
                        "VISIBLE_STATE_CHANGE",
                    ),
                    progress_likelihood=0.999,
                    hazard_likelihood=0.001,
                    information_gain=0.25,
                    prior=0.999,
                    uncertainty=uncertainty,
                    instruction_refs=tuple(sorted(common_refs)),
                )
            )
        represented_actions = {
            prediction.descriptor.action_id for prediction in predictions
        }
        for action_id in observation.available_actions:
            if action_id in represented_actions:
                continue
            descriptor = self._existing_descriptor(descriptors, action_id)
            predictions.append(
                GenericPrediction(
                    descriptor=descriptor,
                    predicted_effects=("NO_VISIBLE_CHANGE",),
                    progress_likelihood=0.001,
                    hazard_likelihood=0.01,
                    information_gain=0.05,
                    prior=0.001,
                    uncertainty=max(uncertainty, 0.25),
                    instruction_refs=tuple(sorted(common_refs)),
                )
            )
        query_digest = "compiled-policy-query:" + digest_object(
            {
                "body": self.digest(),
                "observation": observation.digest(),
                "representation": representation.digest_value,
                "history": history_ref,
                "decision": decision,
                "control": control_operation,
            }
        )
        return InstructionBodyResult(
            predictions=tuple(predictions),
            query_digest=query_digest,
            selected_instruction_refs=tuple(sorted(common_refs)),
            control_operation=control_operation,
            control_instruction_refs=tuple(sorted(control_refs)),
        )


def _load_head(
    arrays: Mapping[str, np.ndarray],
    *,
    head_id: str,
    classes: tuple[int, ...],
) -> CompiledDenseHead:
    required = tuple(
        f"{head_id}_{suffix}" for suffix in ("w0", "b0", "w1", "b1")
    )
    if any(name not in arrays for name in required):
        raise ValueError("COMPILED_POLICY_HEAD_ARRAY_MISSING:" + head_id)
    parameters = [
        np.asarray(arrays[name], dtype=np.float32)
        for name in required
    ]
    for parameter in parameters:
        parameter.setflags(write=False)
    return CompiledDenseHead(
        head_id=head_id,
        classes=classes,
        weight0=parameters[0],
        bias0=parameters[1],
        weight1=parameters[2],
        bias1=parameters[3],
    )


def _compiled_body_from_arrays(
    *,
    manifest: Mapping[str, Any],
    manifest_bytes: bytes,
    arrays: Mapping[str, np.ndarray],
    weights_sha256: str,
) -> CompiledAutonomousInstructionBody:
    expected_array_names: set[str] = set()
    action_heads: dict[tuple[int, ...], CompiledDenseHead] = {}
    for raw in _sequence(manifest.get("action_heads"), "action_heads"):
        item = _mapping(raw, "action head")
        head_id = str(item.get("head_id", ""))
        expected_array_names.update(
            f"{head_id}_{suffix}" for suffix in ("w0", "b0", "w1", "b1")
        )
        classes = tuple(
            _integer(entry, "classes[]")
            for entry in _sequence(item.get("classes"), "classes")
        )
        surface = tuple(
            _integer(entry, "surface[]")
            for entry in _sequence(item.get("surface"), "surface")
        )
        if surface in action_heads:
            raise ValueError("COMPILED_POLICY_ACTION_SURFACE_DUPLICATE")
        action_heads[surface] = _load_head(
            arrays,
            head_id=head_id,
            classes=classes,
        )
    pointer = _mapping(manifest.get("pointer_heads"), "pointer_heads")
    horizontal_meta = _mapping(
        pointer.get("horizontal"),
        "horizontal head",
    )
    vertical_meta = _mapping(pointer.get("vertical"), "vertical head")
    for metadata in (horizontal_meta, vertical_meta):
        head_id = str(metadata.get("head_id", ""))
        expected_array_names.update(
            f"{head_id}_{suffix}" for suffix in ("w0", "b0", "w1", "b1")
        )
    if set(arrays) != expected_array_names:
        raise ValueError("COMPILED_POLICY_ARTIFACT_ARRAY_SET_INVALID")
    horizontal = _load_head(
        arrays,
        head_id=str(horizontal_meta.get("head_id", "")),
        classes=tuple(
            _integer(entry, "horizontal classes[]")
            for entry in _sequence(
                horizontal_meta.get("classes"),
                "horizontal classes",
            )
        ),
    )
    vertical = _load_head(
        arrays,
        head_id=str(vertical_meta.get("head_id", "")),
        classes=tuple(
            _integer(entry, "vertical classes[]")
            for entry in _sequence(
                vertical_meta.get("classes"),
                "vertical classes",
            )
        ),
    )
    body = CompiledAutonomousInstructionBody(
        _manifest=manifest,
        _manifest_bytes=manifest_bytes,
        _weights_sha256=weights_sha256,
        action_heads=action_heads,
        horizontal_head=horizontal,
        vertical_head=vertical,
    )
    failures = body.validate()
    if failures:
        raise ValueError(";".join(failures))
    return body


def compiled_autonomous_instruction_body_from_artifact(
    *,
    manifest_bytes: bytes,
    tensor_arrays: Mapping[str, np.ndarray],
) -> CompiledAutonomousInstructionBody:
    """Rebuild compiled P from its canonical manifest and float16 tensors."""

    value = json.loads(manifest_bytes.decode("utf-8"))
    manifest = _mapping(value, "compiled policy manifest")
    arrays = {
        str(name): np.asarray(array, dtype=np.float16)
        for name, array in tensor_arrays.items()
    }
    return _compiled_body_from_arrays(
        manifest=manifest,
        manifest_bytes=manifest_bytes,
        arrays=arrays,
        weights_sha256=str(manifest.get("weights_sha256", "")),
    )


def load_compiled_autonomous_instruction_body(
    *,
    manifest_path: Path | None = None,
    weights_path: Path | None = None,
) -> CompiledAutonomousInstructionBody:
    manifest_path = manifest_path or _bundle_path(
        COMPILED_POLICY_MANIFEST_FILENAME
    )
    weights_path = weights_path or _bundle_path(
        COMPILED_POLICY_WEIGHTS_FILENAME
    )
    manifest_bytes = manifest_path.read_bytes()
    value = json.loads(manifest_bytes.decode("utf-8"))
    manifest = _mapping(value, "compiled policy manifest")
    weights_bytes = weights_path.read_bytes()
    weights_sha256 = hashlib.sha256(weights_bytes).hexdigest()
    with np.load(weights_path, allow_pickle=False) as loaded:
        arrays = {
            name: np.array(loaded[name], copy=True)
            for name in loaded.files
        }
    return _compiled_body_from_arrays(
        manifest=manifest,
        manifest_bytes=manifest_bytes,
        arrays=arrays,
        weights_sha256=weights_sha256,
    )


__all__ = [
    "COMPILED_POLICY_BODY_VERSION",
    "COMPILED_POLICY_FEATURE_COUNT",
    "COMPILED_POLICY_FORMAT_ID",
    "COMPILED_POLICY_HISTORY_LIMIT",
    "COMPILED_POLICY_MANIFEST_FILENAME",
    "COMPILED_POLICY_SCHEMA_VERSION",
    "COMPILED_POLICY_WEIGHTS_FILENAME",
    "CompiledAutonomousInstructionBody",
    "CompiledDenseHead",
    "CompiledPolicyDecision",
    "compiled_autonomous_instruction_body_from_artifact",
    "compiled_policy_feature_vector",
    "compiled_policy_manifest_digest",
    "load_compiled_autonomous_instruction_body",
]
