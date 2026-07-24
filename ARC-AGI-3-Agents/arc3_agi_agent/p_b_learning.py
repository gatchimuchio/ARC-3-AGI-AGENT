"""Deterministic P-B learning from bounded HDS-authorized runtime memory."""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Mapping, Sequence

from .context import ContextSnapshot
from .instruction_body import (
    PARAMETRIC_FEATURES,
    PARAMETRIC_HEADS,
    InstructionQueryResult,
    ParametricInstructionBody,
    runtime_feature_vector,
)
from .ir import ObservationIR
from .memory import MemoryEntry, MemorySnapshot
from .p_update import PUpdateEvidenceSet, parameter_digest
from .schema import canonical_json, digest_object, forbidden_runtime_paths

P_B_LEARNING_SCHEMA_VERSION = "arc3-p-b-learning-v1"
P_B_LEARNING_MEMORY_KEY = "p_b_learning"
P_B_LEARNING_BUFFER_LIMIT = 128
P_B_LEARNING_SPLITS = frozenset({"TRAIN", "HOLDOUT"})
P_B_EVIDENCE_KINDS = frozenset(
    {"EXPERIENCE", "FAILURE", "CONTRADICTION", "POSITIVE", "NEGATIVE"}
)
P_B_REQUIRED_DATASET_KINDS = frozenset(
    {"FAILURE", "CONTRADICTION", "POSITIVE", "NEGATIVE"}
)
P_B_TRAINER_SEED = 0
P_B_HOLDOUT_TOLERANCE = 1e-9


def _text(value: object) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _float_tuple(
    value: object,
    *,
    expected_length: int,
    name: str,
) -> tuple[float, ...]:
    if not isinstance(value, Sequence) or isinstance(
        value,
        (str, bytes, bytearray),
    ):
        raise TypeError(f"{name} must be an array")
    converted: list[float] = []
    for item in value:
        if (
            isinstance(item, bool)
            or not isinstance(item, (int, float))
            or not math.isfinite(float(item))
        ):
            raise ValueError(f"{name} contains a non-finite number")
        converted.append(float(item))
    result = tuple(converted)
    if len(result) != expected_length:
        raise ValueError(
            f"{name} length mismatch:"
            f"expected={expected_length}:actual={len(result)}"
        )
    return result


def _sigmoid(value: float) -> float:
    if value >= 0.0:
        exponential = math.exp(-min(value, 60.0))
        return 1.0 / (1.0 + exponential)
    exponential = math.exp(max(value, -60.0))
    return exponential / (1.0 + exponential)


def _prediction_vector(
    weights: tuple[tuple[float, ...], ...],
    features: tuple[float, ...],
) -> tuple[float, ...]:
    return tuple(
        _sigmoid(
            sum(
                weight * feature
                for weight, feature in zip(row, features, strict=True)
            )
        )
        for row in weights
    )


def _binary_cross_entropy(
    predictions: tuple[float, ...],
    targets: tuple[float, ...],
) -> float:
    epsilon = 1e-12
    return sum(
        -(
            target * math.log(max(epsilon, min(1.0 - epsilon, prediction)))
            + (1.0 - target)
            * math.log(
                max(epsilon, min(1.0 - epsilon, 1.0 - prediction))
            )
        )
        for prediction, target in zip(predictions, targets, strict=True)
    ) / len(targets)


@dataclass(frozen=True, slots=True)
class PBLearningExample:
    example_id: str
    feature_vector: tuple[float, ...]
    targets: tuple[float, ...]
    split: str
    evidence_kinds: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    source_memory_target: str
    source_memory_version: int
    source_memory_evidence_signature: str
    authorization_refs: tuple[str, ...]
    runtime_identity_free: bool = True
    schema_version: str = P_B_LEARNING_SCHEMA_VERSION

    @property
    def digest(self) -> str:
        return digest_object(self)

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if self.schema_version != P_B_LEARNING_SCHEMA_VERSION:
            failures.append("P_B_EXAMPLE_SCHEMA_INVALID")
        for name, value in (
            ("ID", self.example_id),
            ("SOURCE_MEMORY_TARGET", self.source_memory_target),
            (
                "SOURCE_MEMORY_EVIDENCE_SIGNATURE",
                self.source_memory_evidence_signature,
            ),
        ):
            if not _text(value):
                failures.append(f"P_B_EXAMPLE_{name}_MISSING")
        if len(self.feature_vector) != len(PARAMETRIC_FEATURES) or any(
            not math.isfinite(value) for value in self.feature_vector
        ):
            failures.append("P_B_EXAMPLE_FEATURE_VECTOR_INVALID")
        if len(self.targets) != len(PARAMETRIC_HEADS) or any(
            not math.isfinite(value) or not 0.0 <= value <= 1.0
            for value in self.targets
        ):
            failures.append("P_B_EXAMPLE_TARGET_VECTOR_INVALID")
        if self.split not in P_B_LEARNING_SPLITS:
            failures.append("P_B_EXAMPLE_SPLIT_INVALID")
        if (
            not self.evidence_kinds
            or not set(self.evidence_kinds) <= P_B_EVIDENCE_KINDS
        ):
            failures.append("P_B_EXAMPLE_EVIDENCE_KIND_INVALID")
        if not self.evidence_refs or any(
            not _text(item) for item in self.evidence_refs
        ):
            failures.append("P_B_EXAMPLE_EVIDENCE_REF_INVALID")
        if not self.authorization_refs or any(
            not item.startswith(("hds-command:", "hds-decision:"))
            for item in self.authorization_refs
        ):
            failures.append("P_B_EXAMPLE_HDS_AUTHORIZATION_MISSING")
        if (
            isinstance(self.source_memory_version, bool)
            or not isinstance(self.source_memory_version, int)
            or self.source_memory_version < 1
        ):
            failures.append("P_B_EXAMPLE_MEMORY_VERSION_INVALID")
        if self.runtime_identity_free is not True:
            failures.append("P_B_EXAMPLE_IDENTITY_FLAG_INVALID")
        failures.extend(
            f"P_B_EXAMPLE_RUNTIME_IDENTITY_FORBIDDEN:{path}"
            for path in forbidden_runtime_paths(self)
        )
        return tuple(sorted(set(failures)))

    def to_mapping(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "example_id": self.example_id,
            "feature_vector": list(self.feature_vector),
            "targets": list(self.targets),
            "split": self.split,
            "evidence_kinds": list(self.evidence_kinds),
            "evidence_refs": list(self.evidence_refs),
            "runtime_identity_free": self.runtime_identity_free,
        }


@dataclass(frozen=True, slots=True)
class PBLearningDataset:
    dataset_id: str
    memory_snapshot_digest: str
    evidence_set_digest: str
    examples: tuple[PBLearningExample, ...]
    replay_audit_digest: str
    runtime_identity_free: bool = True
    schema_version: str = P_B_LEARNING_SCHEMA_VERSION

    @property
    def digest(self) -> str:
        return digest_object(self)

    @property
    def train(self) -> tuple[PBLearningExample, ...]:
        return tuple(item for item in self.examples if item.split == "TRAIN")

    @property
    def holdout(self) -> tuple[PBLearningExample, ...]:
        return tuple(item for item in self.examples if item.split == "HOLDOUT")

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if self.schema_version != P_B_LEARNING_SCHEMA_VERSION:
            failures.append("P_B_DATASET_SCHEMA_INVALID")
        for name, value in (
            ("ID", self.dataset_id),
            ("MEMORY_SNAPSHOT_DIGEST", self.memory_snapshot_digest),
            ("EVIDENCE_SET_DIGEST", self.evidence_set_digest),
            ("REPLAY_AUDIT_DIGEST", self.replay_audit_digest),
        ):
            if not _text(value):
                failures.append(f"P_B_DATASET_{name}_MISSING")
        failures.extend(
            failure
            for example in self.examples
            for failure in example.validate()
        )
        if not self.train:
            failures.append("P_B_DATASET_TRAIN_SPLIT_MISSING")
        if not self.holdout:
            failures.append("P_B_DATASET_HOLDOUT_SPLIT_MISSING")
        kinds = {
            kind for example in self.examples for kind in example.evidence_kinds
        }
        if not P_B_REQUIRED_DATASET_KINDS <= kinds:
            failures.append(
                "P_B_DATASET_REQUIRED_EVIDENCE_KINDS_MISSING:"
                + ",".join(sorted(P_B_REQUIRED_DATASET_KINDS - kinds))
            )
        if len({item.example_id for item in self.examples}) != len(
            self.examples
        ):
            failures.append("P_B_DATASET_EXAMPLE_ID_DUPLICATE")
        if self.runtime_identity_free is not True:
            failures.append("P_B_DATASET_IDENTITY_FLAG_INVALID")
        return tuple(sorted(set(failures)))


@dataclass(frozen=True, slots=True)
class PBLearningResult:
    source_parameter_digest: str
    candidate_parameter_digest: str
    candidate_weights: tuple[tuple[float, ...], ...]
    source_train_loss: float
    candidate_train_loss: float
    source_holdout_loss: float
    candidate_holdout_loss: float
    learning_rate: float
    epochs: int
    seed: int
    dataset_digest: str
    training_example_count: int
    holdout_example_count: int
    same_input_example_digest: str
    source_same_input_output_digest: str
    candidate_same_input_output_digest: str
    changed_parameters: tuple[str, ...]
    attribution: str

    @property
    def digest(self) -> str:
        return digest_object(self)

    @property
    def target_improved(self) -> bool:
        return self.candidate_train_loss < self.source_train_loss

    @property
    def holdout_non_degradation(self) -> bool:
        return (
            self.candidate_holdout_loss
            <= self.source_holdout_loss + P_B_HOLDOUT_TOLERANCE
        )

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        for name, value in (
            ("SOURCE_PARAMETER_DIGEST", self.source_parameter_digest),
            ("CANDIDATE_PARAMETER_DIGEST", self.candidate_parameter_digest),
            ("DATASET_DIGEST", self.dataset_digest),
            ("SAME_INPUT_EXAMPLE_DIGEST", self.same_input_example_digest),
            (
                "SOURCE_SAME_INPUT_OUTPUT_DIGEST",
                self.source_same_input_output_digest,
            ),
            (
                "CANDIDATE_SAME_INPUT_OUTPUT_DIGEST",
                self.candidate_same_input_output_digest,
            ),
            ("ATTRIBUTION", self.attribution),
        ):
            if not _text(value):
                failures.append(f"P_B_RESULT_{name}_MISSING")
        if self.source_parameter_digest == self.candidate_parameter_digest:
            failures.append("P_B_RESULT_PARAMETER_DIGEST_UNCHANGED")
        if self.candidate_parameter_digest != parameter_digest(
            self.candidate_weights
        ):
            failures.append("P_B_RESULT_PARAMETER_DIGEST_MISMATCH")
        if (
            self.source_same_input_output_digest
            == self.candidate_same_input_output_digest
        ):
            failures.append("P_B_RESULT_SAME_INPUT_OUTPUT_UNCHANGED")
        if not self.target_improved:
            failures.append("P_B_RESULT_TARGET_NOT_IMPROVED")
        if not self.holdout_non_degradation:
            failures.append("P_B_RESULT_HOLDOUT_DEGRADED")
        if not self.changed_parameters:
            failures.append("P_B_RESULT_CHANGED_PARAMETER_MISSING")
        if self.training_example_count < 1:
            failures.append("P_B_RESULT_TRAINING_EXAMPLE_MISSING")
        if self.holdout_example_count < 1:
            failures.append("P_B_RESULT_HOLDOUT_EXAMPLE_MISSING")
        if self.seed != P_B_TRAINER_SEED:
            failures.append("P_B_RESULT_SEED_INVALID")
        return tuple(sorted(set(failures)))


def _latest_learning_state(memory: MemorySnapshot) -> dict[str, object]:
    for entry in sorted(memory.entries, key=lambda item: item.version, reverse=True):
        payload = entry.payload
        learning = payload.get(P_B_LEARNING_MEMORY_KEY)
        if learning is None:
            continue
        if not isinstance(learning, dict):
            raise ValueError("P-B learning memory payload invalid")
        return learning
    return {}


def _split_for_structure(structural_signature: str) -> str:
    value = int(digest_object(structural_signature)[:8], 16)
    return "HOLDOUT" if value % 5 == 0 else "TRAIN"


def _prediction_targets(
    pending: Mapping[str, object],
    observation: ObservationIR,
    context: ContextSnapshot,
) -> tuple[tuple[float, ...], tuple[str, ...], tuple[str, ...]]:
    effects = set(observation.visible_effects)
    visible_change = bool(
        effects & {"VISIBLE_STATE_CHANGE", "LEVEL_PROGRESS", "WIN_TERMINAL"}
    )
    progress = bool(effects & {"LEVEL_PROGRESS", "WIN_TERMINAL"})
    hazard = observation.terminal_state == "GAME_OVER" or bool(
        effects & {"GAME_OVER", "HAZARD"}
    )
    no_change = "NO_VISIBLE_CHANGE" in effects or not visible_change
    information_gain = visible_change or observation.frame_signature != pending.get(
        "observation_signature"
    )
    targets = (
        float(visible_change),
        float(progress),
        float(hazard),
        float(information_gain),
        1.0 if progress else 0.7 if visible_change and not hazard else 0.0,
        0.1 if progress else 0.9 if hazard or no_change else 0.4,
    )
    predictions = _float_tuple(
        pending.get("predictions"),
        expected_length=len(PARAMETRIC_HEADS),
        name="pending.predictions",
    )
    contradictory = any(
        (prediction >= 0.5) != (target >= 0.5)
        for prediction, target in zip(predictions, targets, strict=True)
    )
    kinds = {"EXPERIENCE"}
    if visible_change or progress:
        kinds.add("POSITIVE")
    if no_change:
        kinds.add("NEGATIVE")
    if hazard or context.failures:
        kinds.add("FAILURE")
    if contradictory:
        kinds.add("CONTRADICTION")
    evidence_refs = tuple(
        sorted(
            {
                *effects,
                *context.failures,
                "observed-result:" + observation.frame_signature,
            }
        )
    )
    return targets, tuple(sorted(kinds)), evidence_refs


def update_p_b_learning_memory(
    memory: MemorySnapshot,
    observation: ObservationIR,
    context: ContextSnapshot,
    query: InstructionQueryResult,
    *,
    selected_action_id: int | None,
) -> dict[str, object]:
    """Return a bounded payload; HDS still decides whether M receives it."""

    state = _latest_learning_state(memory)
    raw_examples = state.get("examples", [])
    if not isinstance(raw_examples, list):
        raise ValueError("P-B learning examples must be an array")
    examples = [
        item
        for item in raw_examples
        if isinstance(item, dict)
    ][-P_B_LEARNING_BUFFER_LIMIT:]
    pending = state.get("pending")
    if pending is not None and not isinstance(pending, dict):
        raise ValueError("P-B learning pending value invalid")
    if isinstance(pending, dict):
        features = _float_tuple(
            pending.get("feature_vector"),
            expected_length=len(PARAMETRIC_FEATURES),
            name="pending.feature_vector",
        )
        structural_signature = pending.get("structural_signature")
        if not _text(structural_signature):
            raise ValueError("P-B pending structural signature missing")
        targets, kinds, evidence_refs = _prediction_targets(
            pending,
            observation,
            context,
        )
        example_seed = {
            "pending": pending,
            "targets": targets,
            "kinds": kinds,
            "evidence": evidence_refs,
        }
        example = {
            "schema_version": P_B_LEARNING_SCHEMA_VERSION,
            "example_id": "p-b-example:" + digest_object(example_seed)[:24],
            "feature_vector": list(features),
            "targets": list(targets),
            "split": _split_for_structure(str(structural_signature)),
            "evidence_kinds": list(kinds),
            "evidence_refs": list(evidence_refs),
            "runtime_identity_free": True,
        }
        by_id = {
            str(item.get("example_id")): item for item in examples
        }
        by_id[str(example["example_id"])] = example
        examples = list(by_id.values())[-P_B_LEARNING_BUFFER_LIMIT:]

    next_pending: dict[str, object] | None = None
    if selected_action_id is not None:
        prediction = next(
            (
                item
                for item in query.predictions
                if item.action_id == selected_action_id
            ),
            None,
        )
        if prediction is None:
            raise ValueError("selected action prediction missing")
        features = runtime_feature_vector(
            selected_action_id,
            observation,
            context,
            memory,
        )
        next_pending = {
            "action_id": selected_action_id,
            "feature_vector": list(features),
            "observation_signature": observation.frame_signature,
            "predictions": [
                float(
                    "VISIBLE_STATE_CHANGE" in prediction.predicted_effects
                ),
                prediction.progress_likelihood,
                prediction.hazard_likelihood,
                prediction.information_gain,
                prediction.candidate_prior,
                prediction.uncertainty,
            ],
            "structural_signature": observation.structural_signature,
        }
    return {
        "schema_version": P_B_LEARNING_SCHEMA_VERSION,
        "buffer_limit": P_B_LEARNING_BUFFER_LIMIT,
        "examples": examples,
        "pending": next_pending,
        "runtime_identity_free": True,
    }


def _authorization_refs(entry: MemoryEntry) -> tuple[str, ...]:
    return tuple(
        item
        for item in entry.provenance
        if item.startswith(("hds-command:", "hds-decision:"))
    )


def build_p_b_learning_dataset(
    memory: MemorySnapshot,
    evidence_set: PUpdateEvidenceSet,
) -> PBLearningDataset:
    """Extract only evidence-set-approved, HDS-provenance-bound M entries."""

    evidence_failures = evidence_set.validate()
    if evidence_failures:
        raise ValueError(";".join(evidence_failures))
    if evidence_set.memory_snapshot_digest != memory.digest:
        raise ValueError("P_B_DATASET_MEMORY_SNAPSHOT_MISMATCH")
    examples: dict[str, PBLearningExample] = {}
    for entry in memory.entries:
        if (
            entry.target not in evidence_set.approved_memory_refs
            or not entry.valid
            or entry.archived
        ):
            continue
        authorization_refs = _authorization_refs(entry)
        if len(authorization_refs) < 2:
            raise ValueError(
                "P_B_DATASET_MEMORY_ENTRY_NOT_HDS_AUTHORIZED:"
                + entry.target
            )
        learning = entry.payload.get(P_B_LEARNING_MEMORY_KEY)
        if not isinstance(learning, dict):
            continue
        raw_examples = learning.get("examples")
        if not isinstance(raw_examples, list):
            raise ValueError("P_B_DATASET_MEMORY_EXAMPLES_INVALID")
        for raw in raw_examples:
            if not isinstance(raw, Mapping):
                raise ValueError("P_B_DATASET_MEMORY_EXAMPLE_INVALID")
            example = PBLearningExample(
                example_id=str(raw.get("example_id", "")),
                feature_vector=_float_tuple(
                    raw.get("feature_vector"),
                    expected_length=len(PARAMETRIC_FEATURES),
                    name="example.feature_vector",
                ),
                targets=_float_tuple(
                    raw.get("targets"),
                    expected_length=len(PARAMETRIC_HEADS),
                    name="example.targets",
                ),
                split=str(raw.get("split", "")),
                evidence_kinds=tuple(
                    str(item) for item in raw.get("evidence_kinds", ())
                ),
                evidence_refs=tuple(
                    str(item) for item in raw.get("evidence_refs", ())
                ),
                source_memory_target=entry.target,
                source_memory_version=entry.version,
                source_memory_evidence_signature=entry.evidence_signature,
                authorization_refs=authorization_refs,
                runtime_identity_free=(
                    raw.get("runtime_identity_free") is True
                ),
                schema_version=str(raw.get("schema_version", "")),
            )
            example_failures = example.validate()
            if example_failures:
                raise ValueError(";".join(example_failures))
            examples[example.example_id] = example
    replay_audit_digest = digest_object(
        {
            "audit": "no-id-no-replay-no-fixed-sequence",
            "refs": evidence_set.replay_audit_refs,
            "examples": tuple(sorted(examples)),
        }
    )
    dataset = PBLearningDataset(
        dataset_id="p-b-dataset:"
        + digest_object(
            {
                "memory": memory.digest,
                "evidence": evidence_set.digest,
                "examples": tuple(
                    item.digest
                    for item in sorted(
                        examples.values(),
                        key=lambda value: value.example_id,
                    )
                ),
            }
        )[:24],
        memory_snapshot_digest=memory.digest,
        evidence_set_digest=evidence_set.digest,
        examples=tuple(
            sorted(examples.values(), key=lambda item: item.example_id)
        ),
        replay_audit_digest=replay_audit_digest,
    )
    failures = dataset.validate()
    if failures:
        raise ValueError(";".join(failures))
    return dataset


def merge_p_b_learning_memory_snapshots(
    snapshots: tuple[MemorySnapshot, ...],
) -> MemorySnapshot:
    """Merge distinct authorized episode memories by content, never by identity."""

    if len(snapshots) < 2:
        raise ValueError("P_B_MEMORY_MERGE_REQUIRES_MULTIPLE_EPISODES")
    entries_by_digest: dict[str, MemoryEntry] = {}
    for snapshot in snapshots:
        for entry in snapshot.entries:
            learning = entry.payload.get(P_B_LEARNING_MEMORY_KEY)
            if not isinstance(learning, dict):
                continue
            authorization_refs = _authorization_refs(entry)
            if len(authorization_refs) < 2:
                raise ValueError(
                    "P_B_MEMORY_MERGE_ENTRY_NOT_HDS_AUTHORIZED:"
                    + entry.target
                )
            payload = {
                P_B_LEARNING_MEMORY_KEY: learning,
                "source_memory_snapshot_digest": snapshot.digest,
            }
            content_digest = digest_object(
                {
                    "payload": payload,
                    "evidence": entry.evidence_signature,
                    "authorization": authorization_refs,
                }
            )
            entries_by_digest[content_digest] = MemoryEntry(
                target="p-b-learning-memory:" + content_digest[:24],
                operation="MERGE",
                lifecycle="ACTIVE",
                evidence_signature=entry.evidence_signature,
                payload_json=canonical_json(payload),
                version=0,
                provenance=tuple(
                    sorted(
                        {
                            *entry.provenance,
                            "source-memory-snapshot:" + snapshot.digest,
                        }
                    )
                ),
                valid=True,
                archived=False,
                index_terms=(
                    "p-b-learning",
                    "hds-authorized",
                    "identity-free",
                ),
                created_version=0,
            )
    if len(entries_by_digest) < 2:
        raise ValueError("P_B_MEMORY_MERGE_DISTINCT_EPISODES_MISSING")
    ordered = tuple(
        MemoryEntry(
            target=entry.target,
            operation=entry.operation,
            lifecycle=entry.lifecycle,
            evidence_signature=entry.evidence_signature,
            payload_json=entry.payload_json,
            version=index,
            provenance=entry.provenance,
            valid=entry.valid,
            archived=entry.archived,
            index_terms=entry.index_terms,
            created_version=index,
        )
        for index, entry in enumerate(
            (
                entries_by_digest[key]
                for key in sorted(entries_by_digest)
            ),
            start=1,
        )
    )
    return MemorySnapshot(version=len(ordered), entries=ordered)


def p_b_learning_memory_evidence_mapping(
    memory: MemorySnapshot,
) -> dict[str, object]:
    """Serialize a merged learning-memory snapshot with a bound digest."""

    entries = [
        {
            "target": entry.target,
            "operation": entry.operation,
            "lifecycle": entry.lifecycle,
            "evidence_signature": entry.evidence_signature,
            "payload": entry.payload,
            "version": entry.version,
            "provenance": list(entry.provenance),
            "valid": entry.valid,
            "archived": entry.archived,
            "index_terms": list(entry.index_terms),
            "created_version": entry.created_version,
            "supersedes_version": entry.supersedes_version,
        }
        for entry in memory.entries
    ]
    core: dict[str, object] = {
        "schema_version": "arc3-p-b-learning-memory-evidence-v1",
        "runtime_identity_free": True,
        "memory_version": memory.version,
        "memory_snapshot_digest": memory.digest,
        "entries": entries,
    }
    return {
        **core,
        "content_digest": "p-b-learning-memory-evidence:"
        + digest_object(core),
    }


def p_b_learning_memory_from_mapping(
    value: Mapping[str, object],
) -> MemorySnapshot:
    """Load and verify a serialized merged learning-memory snapshot."""

    if (
        value.get("schema_version")
        != "arc3-p-b-learning-memory-evidence-v1"
    ):
        raise ValueError("P_B_MEMORY_EVIDENCE_SCHEMA_INVALID")
    if value.get("runtime_identity_free") is not True:
        raise ValueError("P_B_MEMORY_EVIDENCE_IDENTITY_FLAG_INVALID")
    raw_entries = value.get("entries")
    if not isinstance(raw_entries, list):
        raise TypeError("P_B_MEMORY_EVIDENCE_ENTRIES_INVALID")
    entries: list[MemoryEntry] = []
    for raw in raw_entries:
        if not isinstance(raw, Mapping):
            raise TypeError("P_B_MEMORY_EVIDENCE_ENTRY_INVALID")
        payload = raw.get("payload")
        if not isinstance(payload, Mapping):
            raise TypeError("P_B_MEMORY_EVIDENCE_PAYLOAD_INVALID")
        entries.append(
            MemoryEntry(
                target=str(raw.get("target", "")),
                operation=str(raw.get("operation", "")),
                lifecycle=str(raw.get("lifecycle", "")),
                evidence_signature=str(
                    raw.get("evidence_signature", "")
                ),
                payload_json=canonical_json(dict(payload)),
                version=int(raw.get("version", -1)),
                provenance=tuple(
                    str(item) for item in raw.get("provenance", ())
                ),
                valid=raw.get("valid") is True,
                archived=raw.get("archived") is True,
                index_terms=tuple(
                    str(item) for item in raw.get("index_terms", ())
                ),
                created_version=int(raw.get("created_version", -1)),
                supersedes_version=(
                    int(raw["supersedes_version"])
                    if raw.get("supersedes_version") is not None
                    else None
                ),
            )
        )
    memory_version = value.get("memory_version")
    if (
        isinstance(memory_version, bool)
        or not isinstance(memory_version, int)
        or memory_version < 0
    ):
        raise ValueError("P_B_MEMORY_EVIDENCE_VERSION_INVALID")
    memory = MemorySnapshot(version=memory_version, entries=tuple(entries))
    if value.get("memory_snapshot_digest") != memory.digest:
        raise ValueError("P_B_MEMORY_EVIDENCE_SNAPSHOT_DIGEST_MISMATCH")
    core = dict(value)
    provided_digest = core.pop("content_digest", None)
    expected_digest = "p-b-learning-memory-evidence:" + digest_object(core)
    if provided_digest != expected_digest:
        raise ValueError("P_B_MEMORY_EVIDENCE_CONTENT_DIGEST_MISMATCH")
    if forbidden_runtime_paths(value):
        raise ValueError("P_B_MEMORY_EVIDENCE_RUNTIME_IDENTITY_FORBIDDEN")
    return memory


def _dataset_loss(
    weights: tuple[tuple[float, ...], ...],
    examples: tuple[PBLearningExample, ...],
) -> float:
    if not examples:
        raise ValueError("P-B loss requires examples")
    return sum(
        _binary_cross_entropy(
            _prediction_vector(weights, example.feature_vector),
            example.targets,
        )
        for example in examples
    ) / len(examples)


def _train_candidate(
    source: tuple[tuple[float, ...], ...],
    examples: tuple[PBLearningExample, ...],
    *,
    learning_rate: float,
    epochs: int,
) -> tuple[tuple[float, ...], ...]:
    weights = [list(row) for row in source]
    for _ in range(epochs):
        gradients = [
            [0.0 for _ in PARAMETRIC_FEATURES] for _ in PARAMETRIC_HEADS
        ]
        for example in examples:
            features = example.feature_vector
            predictions = _prediction_vector(
                tuple(tuple(row) for row in weights),
                features,
            )
            for head_index, (prediction, target) in enumerate(
                zip(predictions, example.targets, strict=True)
            ):
                residual = prediction - target
                for feature_index, feature in enumerate(features):
                    gradients[head_index][feature_index] += residual * feature
        scale = learning_rate / len(examples)
        for head_index, row in enumerate(weights):
            for feature_index in range(len(row)):
                row[feature_index] = round(
                    row[feature_index]
                    - scale * gradients[head_index][feature_index],
                    12,
                )
    return tuple(tuple(row) for row in weights)


def train_p_b_from_memory(
    source: ParametricInstructionBody,
    dataset: PBLearningDataset,
    *,
    seed: int = P_B_TRAINER_SEED,
) -> PBLearningResult:
    """Train with deterministic early selection and a strict holdout gate."""

    if seed != P_B_TRAINER_SEED:
        raise ValueError("P-B trainer seed is fixed at 0")
    source_failures = source.validate()
    if source_failures:
        raise ValueError(";".join(source_failures))
    dataset_failures = dataset.validate()
    if dataset_failures:
        raise ValueError(";".join(dataset_failures))
    source_train_loss = _dataset_loss(source.weights, dataset.train)
    source_holdout_loss = _dataset_loss(source.weights, dataset.holdout)
    candidates: list[
        tuple[
            float,
            float,
            float,
            int,
            tuple[tuple[float, ...], ...],
        ]
    ] = []
    for learning_rate in (
        0.1,
        0.03,
        0.01,
        0.003,
        0.001,
        0.0003,
        0.0001,
        0.00003,
        0.00001,
        0.000003,
        0.000001,
        0.0000001,
        0.00000001,
        0.000000001,
        0.0000000001,
        0.00000000001,
    ):
        for epochs in (1, 2, 4, 8, 16):
            weights = _train_candidate(
                source.weights,
                dataset.train,
                learning_rate=learning_rate,
                epochs=epochs,
            )
            if weights == source.weights:
                continue
            train_loss = _dataset_loss(weights, dataset.train)
            holdout_loss = _dataset_loss(weights, dataset.holdout)
            if (
                train_loss < source_train_loss
                and holdout_loss
                <= source_holdout_loss + P_B_HOLDOUT_TOLERANCE
            ):
                candidates.append(
                    (
                        train_loss,
                        holdout_loss,
                        learning_rate,
                        epochs,
                        weights,
                    )
                )
    if not candidates:
        raise ValueError("P_B_TRAINING_NO_HOLDOUT_SAFE_UPDATE")
    (
        candidate_train_loss,
        candidate_holdout_loss,
        learning_rate,
        epochs,
        candidate_weights,
    ) = min(
        candidates,
        key=lambda item: (
            item[0],
            item[1],
            item[2],
            item[3],
            parameter_digest(item[4]),
        ),
    )
    witness = dataset.train[0]
    source_output = _prediction_vector(
        source.weights,
        witness.feature_vector,
    )
    candidate_output = _prediction_vector(
        candidate_weights,
        witness.feature_vector,
    )
    changed_parameters = tuple(
        f"{PARAMETRIC_HEADS[head_index]}:{PARAMETRIC_FEATURES[feature_index]}"
        for head_index, (before_row, after_row) in enumerate(
            zip(source.weights, candidate_weights, strict=True)
        )
        for feature_index, (before, after) in enumerate(
            zip(before_row, after_row, strict=True)
        )
        if before != after
    )
    result = PBLearningResult(
        source_parameter_digest=parameter_digest(source.weights),
        candidate_parameter_digest=parameter_digest(candidate_weights),
        candidate_weights=candidate_weights,
        source_train_loss=source_train_loss,
        candidate_train_loss=candidate_train_loss,
        source_holdout_loss=source_holdout_loss,
        candidate_holdout_loss=candidate_holdout_loss,
        learning_rate=learning_rate,
        epochs=epochs,
        seed=seed,
        dataset_digest=dataset.digest,
        training_example_count=len(dataset.train),
        holdout_example_count=len(dataset.holdout),
        same_input_example_digest=witness.digest,
        source_same_input_output_digest=digest_object(source_output),
        candidate_same_input_output_digest=digest_object(candidate_output),
        changed_parameters=changed_parameters,
        attribution=(
            "full-batch-logistic-gradient-from-HDS-approved-M;"
            "train-only-gradient;holdout-selection-gate"
        ),
    )
    failures = result.validate()
    if failures:
        raise ValueError(";".join(failures))
    return result


__all__ = [
    "P_B_EVIDENCE_KINDS",
    "P_B_HOLDOUT_TOLERANCE",
    "P_B_LEARNING_BUFFER_LIMIT",
    "P_B_LEARNING_MEMORY_KEY",
    "P_B_LEARNING_SCHEMA_VERSION",
    "P_B_LEARNING_SPLITS",
    "P_B_REQUIRED_DATASET_KINDS",
    "P_B_TRAINER_SEED",
    "PBLearningDataset",
    "PBLearningExample",
    "PBLearningResult",
    "build_p_b_learning_dataset",
    "merge_p_b_learning_memory_snapshots",
    "p_b_learning_memory_evidence_mapping",
    "p_b_learning_memory_from_mapping",
    "train_p_b_from_memory",
    "update_p_b_learning_memory",
]
