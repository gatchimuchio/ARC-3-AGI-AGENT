"""Relational Layer-0 and subordinate compute subject for GenericAGIRuntime."""

from __future__ import annotations

import math
from collections import Counter, deque
from dataclasses import dataclass, field
from functools import lru_cache
from typing import Protocol, Sequence

from .authority_state import AuthorityState
from .evidence_binding import (
    TypedCandidateProvenance,
    bind_candidate_records,
    build_evidence_binding_key,
    record_matches_binding_prefix,
)
from .generic_memory import (
    SemanticMemoryQuery,
    SemanticMemoryQueryResult,
    SemanticRecord,
)
from .generic_types import (
    ActionDescriptor,
    ActionEffectRecord,
    GenericCandidate,
    GenericComputeCommand,
    GenericComputeResult,
    GenericHypothesis,
    GenericObservation,
    GenericPrediction,
    Layer0StageTrace,
    ObjectRole,
    RelationalRepresentation,
)
from .p_ir_types import PIRProgram
from .schema import digest_object
from .taint import COORDINATE_PROVENANCE_CURRENT_RENDER

GENERIC_COMPUTE_VERSION = "arc3-generic-compute-v1"
GENERIC_P_REMOVAL_WITNESS = "GENERIC_EXECUTABLE_INSTRUCTION_BODY_REQUIRED"
GENERIC_SERIAL_DEPTH_WITNESS = "GENERIC_EFFECTIVE_SERIAL_DEPTH_REMOVED"


def _bounded(value: float) -> float:
    return max(0.0, min(1.0, value))


def _sigmoid(value: float) -> float:
    if value >= 0.0:
        inverse = math.exp(-value)
        return 1.0 / (1.0 + inverse)
    direct = math.exp(value)
    return direct / (1.0 + direct)


def _component_shape(
    cells: Sequence[tuple[int, int]],
) -> tuple[str, int, int, int]:
    ys = [item[0] for item in cells]
    xs = [item[1] for item in cells]
    height = max(ys) - min(ys) + 1
    width = max(xs) - min(xs) + 1
    cell_set = set(cells)
    perimeter = sum(
        1
        for y, x in cells
        for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1))
        if (y + dy, x + dx) not in cell_set
    )
    ordered_dimensions = tuple(sorted((height, width)))
    density_bucket = round(len(cells) / float(height * width), 1)
    signature = (
        f"a{len(cells)}:"
        f"d{ordered_dimensions[0]}x{ordered_dimensions[1]}:"
        f"p{perimeter}:q{density_bucket:.1f}"
    )
    return signature, height, width, perimeter


def _components(
    matrix: tuple[tuple[int, ...], ...],
) -> tuple[tuple[tuple[int, int], ...], ...]:
    if not matrix:
        return ()
    height = len(matrix)
    width = len(matrix[0])
    background = Counter(cell for row in matrix for cell in row).most_common(1)[0][0]
    visited: set[tuple[int, int]] = set()
    output: list[tuple[tuple[int, int], ...]] = []
    for y in range(height):
        for x in range(width):
            color = matrix[y][x]
            if color == background or (y, x) in visited:
                continue
            queue: deque[tuple[int, int]] = deque([(y, x)])
            visited.add((y, x))
            cells: list[tuple[int, int]] = []
            while queue:
                current_y, current_x = queue.popleft()
                cells.append((current_y, current_x))
                for dy, dx in ((-1, 0), (1, 0), (0, -1), (0, 1)):
                    next_y = current_y + dy
                    next_x = current_x + dx
                    if (
                        0 <= next_y < height
                        and 0 <= next_x < width
                        and (next_y, next_x) not in visited
                        and matrix[next_y][next_x] == color
                    ):
                        visited.add((next_y, next_x))
                        queue.append((next_y, next_x))
            ordered_cells = tuple(sorted(cells))
            if all(
                cell_y in {0, height - 1} or cell_x in {0, width - 1}
                for cell_y, cell_x in ordered_cells
            ):
                # Border-only components are rendered interface evidence, not
                # board affordances. They remain observable through effects.
                continue
            output.append(ordered_cells)
    output.sort(
        key=lambda item: (
            -len(item),
            _component_shape(item)[0],
            round(sum(y for y, _ in item) / len(item), 4),
            round(sum(x for _, x in item) / len(item), 4),
        )
    )
    return tuple(output)


def _relative_band(value: float) -> str:
    if value < 1.0 / 3.0:
        return "low"
    if value > 2.0 / 3.0:
        return "high"
    return "middle"


def represent_observation(
    observation: GenericObservation,
    *,
    goal_tokens: Sequence[str],
) -> RelationalRepresentation:
    """Build color-name-free role and relation features from current render."""

    failures = observation.validate()
    if failures:
        raise ValueError(";".join(failures))
    matrix = observation.rendered_layers[-1] if observation.rendered_layers else ()
    raw_components = _components(matrix)
    height = len(matrix) if matrix else 1
    width = len(matrix[0]) if matrix else 1
    roles: list[ObjectRole] = []
    centroids: list[tuple[float, float]] = []
    for index, cells in enumerate(raw_components[:32]):
        centroid_y = sum(y for y, _ in cells) / len(cells)
        centroid_x = sum(x for _, x in cells) / len(cells)
        centroids.append((centroid_y, centroid_x))
        shape_signature, _, _, _ = _component_shape(cells)
        area = len(cells)
        # The center of a rendered component is a stronger generic pointer
        # affordance than an arbitrary colored edge cell.  It also remains
        # role-relative when the component is hollow or multicolored.
        target_y = round(centroid_y)
        target_x = round(centroid_x)
        if area == 1:
            area_bucket = "point"
        elif area <= 4:
            area_bucket = "small"
        elif area <= 64:
            area_bucket = "medium"
        else:
            area_bucket = "large"
        roles.append(
            ObjectRole(
                role_id=f"role:{index:02d}:{area_bucket}:{shape_signature}",
                area_rank=index,
                area_bucket=area_bucket,
                shape_signature=shape_signature,
                relative_vertical=_relative_band(centroid_y / max(1, height - 1)),
                relative_horizontal=_relative_band(centroid_x / max(1, width - 1)),
                neighbor_count=0,
                target_x=max(0, min(63, target_x)),
                target_y=max(0, min(63, target_y)),
            )
        )
    neighbor_counts = [0 for _ in roles]
    relations: set[str] = set()
    for left in range(len(roles)):
        for right in range(left + 1, len(roles)):
            left_y, left_x = centroids[left]
            right_y, right_x = centroids[right]
            vertical = "above" if left_y < right_y else "below"
            horizontal = "left-of" if left_x < right_x else "right-of"
            relations.add(f"{roles[left].role_id}:{vertical}:{roles[right].role_id}")
            relations.add(f"{roles[left].role_id}:{horizontal}:{roles[right].role_id}")
            distance = abs(left_y - right_y) + abs(left_x - right_x)
            if distance <= max(2.0, min(height, width) / 8.0):
                neighbor_counts[left] += 1
                neighbor_counts[right] += 1
                relations.add(f"{roles[left].role_id}:near:{roles[right].role_id}")
    roles = [
        ObjectRole(
            role_id=role.role_id,
            area_rank=role.area_rank,
            area_bucket=role.area_bucket,
            shape_signature=role.shape_signature,
            relative_vertical=role.relative_vertical,
            relative_horizontal=role.relative_horizontal,
            neighbor_count=neighbor_counts[index],
            target_x=role.target_x,
            target_y=role.target_y,
        )
        for index, role in enumerate(roles)
    ]
    topology_tokens = {
        f"object-count:{len(roles)}",
        f"relation-count:{len(relations)}",
        f"action-count:{len(observation.available_actions)}",
        f"terminal:{observation.terminal_state.casefold()}",
    }
    topology_tokens.update(token for role in roles for token in role.semantic_tokens())
    role_tuple = tuple(roles)
    relation_tuple = tuple(sorted(relations))
    topology_tuple = tuple(sorted(topology_tokens))
    goal_tuple = tuple(sorted(set(goal_tokens)))
    digest_value = "generic-representation:" + digest_object(
        {
            "observation_signature": observation.signature,
            "roles": role_tuple,
            "relations": relation_tuple,
            "topology_tokens": topology_tuple,
            "goal_tokens": goal_tuple,
        }
    )
    representation = RelationalRepresentation(
        observation_signature=observation.signature,
        roles=role_tuple,
        relations=relation_tuple,
        topology_tokens=topology_tuple,
        goal_tokens=goal_tuple,
        digest_value=digest_value,
    )
    representation_failures = representation.validate()
    if representation_failures:
        raise ValueError(";".join(representation_failures))
    return representation


def action_descriptors(
    observation: GenericObservation,
    representation: RelationalRepresentation,
) -> tuple[ActionDescriptor, ...]:
    """Bind every legal action to role-relative targets when required."""

    payload_schema = dict(observation.action_payload_schema)
    descriptors: list[ActionDescriptor] = []
    matrix = observation.rendered_layers[-1] if observation.rendered_layers else ()
    matrix_height = len(matrix) if matrix else 64
    matrix_width = len(matrix[0]) if matrix else 64
    components = _components(matrix)[:32]
    for ordinal, action_id in enumerate(observation.available_actions):
        fields = payload_schema.get(action_id, ())
        if set(fields) == {"x", "y"}:
            targets = tuple(
                sorted(
                    representation.roles,
                    key=lambda role: (
                        {
                            "medium": 0,
                            "small": 1,
                            "point": 2,
                            "large": 3,
                        }.get(role.area_bucket, 4),
                        role.area_rank,
                        -role.neighbor_count,
                        role.role_id,
                    ),
                )
            ) or (
                ObjectRole(
                    role_id="role:synthetic:center",
                    area_rank=0,
                    area_bucket="unknown",
                    shape_signature="unknown",
                    relative_vertical="middle",
                    relative_horizontal="middle",
                    neighbor_count=0,
                    target_x=32,
                    target_y=32,
                ),
            )
            role_anchors: list[tuple[ObjectRole, tuple[tuple[str, int, int], ...]]] = []
            for role in targets[:32]:
                cells = (
                    components[role.area_rank]
                    if role.area_rank < len(components)
                    else ()
                )
                if cells:
                    centroid_y = sum(y for y, _ in cells) / len(cells)
                    centroid_x = sum(x for _, x in cells) / len(cells)
                    nearest_y, nearest_x = min(
                        cells,
                        key=lambda item: (
                            (item[0] - centroid_y) ** 2 + (item[1] - centroid_x) ** 2,
                            item[0],
                            item[1],
                        ),
                    )
                else:
                    nearest_x = role.target_x
                    nearest_y = role.target_y
                raw_anchors = (
                    ("center", role.target_x, role.target_y),
                    ("interior", nearest_x, nearest_y),
                    ("north", role.target_x, role.target_y - 1),
                    ("south", role.target_x, role.target_y + 1),
                    ("west", role.target_x - 1, role.target_y),
                    ("east", role.target_x + 1, role.target_y),
                )
                seen_coordinates: set[tuple[int, int]] = set()
                role_anchor_values: list[tuple[str, int, int]] = []
                for anchor_name, target_x, target_y in raw_anchors:
                    coordinate = (
                        max(0, min(matrix_width - 1, target_x)),
                        max(0, min(matrix_height - 1, target_y)),
                    )
                    if coordinate in seen_coordinates:
                        continue
                    seen_coordinates.add(coordinate)
                    role_anchor_values.append(
                        (anchor_name, coordinate[0], coordinate[1])
                    )
                role_anchors.append((role, tuple(role_anchor_values)))
            max_anchor_count = max(
                (len(anchors) for _, anchors in role_anchors),
                default=0,
            )
            for anchor_index in range(max_anchor_count):
                for role_index, (role, anchors) in enumerate(role_anchors):
                    if anchor_index > 0 and role_index >= 8:
                        continue
                    if anchor_index >= len(anchors):
                        continue
                    anchor_name, target_x, target_y = anchors[anchor_index]
                    descriptors.append(
                        ActionDescriptor(
                            action_id=action_id,
                            surface_ordinal=ordinal,
                            semantic_key=(
                                f"surface:{ordinal}:target:"
                                + ":".join(role.semantic_tokens())
                                + f":anchor:{anchor_name}"
                            ),
                            payload_items=(
                                ("x", target_x),
                                ("y", target_y),
                            ),
                            target_role=role.role_id,
                            coordinate_provenance=(
                                COORDINATE_PROVENANCE_CURRENT_RENDER
                            ),
                            coordinate_observation_digest=observation.digest(),
                        )
                    )
        else:
            descriptors.append(
                ActionDescriptor(
                    action_id=action_id,
                    surface_ordinal=ordinal,
                    semantic_key=f"surface:{ordinal}:untargeted",
                )
            )
    if not descriptors:
        raise ValueError("GENERIC_LEGAL_ACTION_DESCRIPTOR_MISSING")
    return tuple(descriptors)


class SemanticMemoryReader(Protocol):
    @property
    def version(self) -> int: ...

    def query(self, query: SemanticMemoryQuery) -> SemanticMemoryQueryResult: ...


@dataclass(frozen=True, slots=True)
class InstructionBodyResult:
    predictions: tuple[GenericPrediction, ...]
    query_digest: str
    selected_instruction_refs: tuple[str, ...]
    control_operation: str = ""
    control_instruction_refs: tuple[str, ...] = ()


class GenericInstructionBody(Protocol):
    def format_id(self) -> str: ...

    def body_version(self) -> str: ...

    def provenance_digest(self) -> str: ...

    def digest(self) -> str: ...

    def validate(self) -> tuple[str, ...]: ...

    def query(
        self,
        representation: RelationalRepresentation,
        descriptors: tuple[ActionDescriptor, ...],
        records: tuple[SemanticRecord, ...],
        *,
        observation: GenericObservation | None = None,
        action_history: tuple[ActionEffectRecord, ...] = (),
    ) -> InstructionBodyResult: ...


def _record_statistics(
    descriptor: ActionDescriptor,
    records: Sequence[SemanticRecord],
    *,
    representation: RelationalRepresentation,
) -> tuple[float, float, float, float, float, tuple[str, ...]]:
    successes = 0.0
    hazards = 0.0
    no_effects = 0.0
    visible_changes = 0.0
    refs: list[str] = []
    binding_prefix = build_evidence_binding_key(
        topology_tokens=representation.topology_tokens,
        relations=representation.relations,
        descriptor_semantic_key=descriptor.semantic_key,
        action_id=descriptor.action_id,
        target_role=descriptor.target_role,
        payload_fields=tuple(key for key, _ in descriptor.payload_items),
        # Statistics consume records already emitted by a prediction.  The
        # action-relation key binds the expected-effect class while the exact
        # effect set remains isolated in predicted_effect_digest.
        predicted_effects=("EXPECTED_EFFECT_FAMILY",),
    )
    for record in records:
        if descriptor.semantic_key not in record.semantic_tokens:
            continue
        if not record_matches_binding_prefix(record, binding_prefix):
            continue
        refs.append(record.memory_id)
        payload = record.payload()
        for key, target in (
            ("success_count", "success"),
            ("hazard_count", "hazard"),
            ("no_effect_count", "no_effect"),
            ("visible_change_count", "visible_change"),
        ):
            value = payload.get(key, 0)
            if isinstance(value, int) and not isinstance(value, bool):
                if target == "success":
                    successes += value
                elif target == "hazard":
                    hazards += value
                elif target == "no_effect":
                    no_effects += value
                else:
                    visible_changes += value
    total = successes + hazards + no_effects + visible_changes
    if total <= 0:
        return 0.0, 0.0, 0.0, 0.0, 0.0, tuple(sorted(set(refs)))
    return (
        successes / total,
        hazards / total,
        no_effects / total,
        visible_changes / total,
        total,
        tuple(sorted(set(refs))),
    )


def _memory_effects(
    records: Sequence[SemanticRecord],
    record_ids: set[str],
) -> tuple[str, ...]:
    effects: set[str] = set()
    for record in records:
        if record.memory_id not in record_ids:
            continue
        value = record.payload().get("learned_effects", ())
        if isinstance(value, (str, bytes)) or not isinstance(value, Sequence):
            continue
        effects.update(str(item) for item in value if isinstance(item, str) and item)
    return tuple(sorted(effects))


@dataclass(frozen=True, slots=True)
class SymbolicRelationalInstructionBody:
    """Non-neural P-A based on reusable relation/action-effect instructions."""

    version: str = "generic-symbolic-relational-v1"
    provenance: str = "hand-audited-generic-prior:no-environment-identity"

    def format_id(self) -> str:
        return "generic-symbolic-relational"

    def body_version(self) -> str:
        return self.version

    @lru_cache(maxsize=128)
    def provenance_digest(self) -> str:
        return "generic-p-provenance:" + digest_object(self.provenance)

    @lru_cache(maxsize=128)
    def digest(self) -> str:
        return "generic-symbolic-p:" + digest_object(self)

    @lru_cache(maxsize=128)
    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not self.version or not self.provenance:
            failures.append("GENERIC_SYMBOLIC_P_METADATA_MISSING")
        lowered = self.provenance.casefold()
        if any(
            term in lowered
            for term in ("game_id", "level_id", "task_id", "replay", "answer")
        ):
            failures.append("GENERIC_SYMBOLIC_P_IDENTITY_CONTAMINATED")
        return tuple(sorted(set(failures)))

    def query(
        self,
        representation: RelationalRepresentation,
        descriptors: tuple[ActionDescriptor, ...],
        records: tuple[SemanticRecord, ...],
        *,
        observation: GenericObservation | None = None,
        action_history: tuple[ActionEffectRecord, ...] = (),
    ) -> InstructionBodyResult:
        predictions: list[GenericPrediction] = []
        for descriptor in descriptors:
            (
                success,
                hazard,
                no_effect,
                visible_change,
                sample_count,
                memory_refs,
            ) = _record_statistics(
                descriptor,
                records,
                representation=representation,
            )
            observed = success + hazard + no_effect + visible_change > 0.0
            continue_visible_effect = (
                visible_change > 0.0
                and hazard == 0.0
                and no_effect == 0.0
                and sample_count <= 4.0
            )
            progress = _bounded(0.15 + 0.75 * success - 0.2 * no_effect)
            risk = _bounded(0.08 + 0.85 * hazard)
            information = _bounded(
                0.9
                if not observed
                else 1.0
                if continue_visible_effect
                else (
                    0.2
                    + no_effect * 0.3
                    + visible_change * 0.65 / math.sqrt(sample_count)
                )
            )
            prior = _bounded(0.3 + 0.45 * progress + 0.2 * information - 0.35 * risk)
            effects = {"VISIBLE_STATE_CHANGE"}
            if progress >= 0.5:
                effects.add("LEVEL_PROGRESS")
            if risk >= 0.5:
                effects.add("IRREVERSIBLE_FAILURE")
            if no_effect >= 0.5:
                effects.add("NO_VISIBLE_CHANGE")
            predictions.append(
                GenericPrediction(
                    descriptor=descriptor,
                    predicted_effects=tuple(sorted(effects)),
                    progress_likelihood=progress,
                    hazard_likelihood=risk,
                    information_gain=information,
                    prior=prior,
                    uncertainty=_bounded(0.8 if not observed else 0.25),
                    instruction_refs=(
                        self.digest(),
                        "rule:novel-action-as-bounded-probe",
                        "rule:reuse-progress-avoid-hazard",
                    ),
                    memory_refs=memory_refs,
                )
            )
        query_digest = "generic-symbolic-query:" + digest_object(
            {
                "representation": representation.digest_value,
                "descriptors": descriptors,
                "records": tuple(record.citation() for record in records),
                "predictions": predictions,
            }
        )
        return InstructionBodyResult(
            predictions=tuple(predictions),
            query_digest=query_digest,
            selected_instruction_refs=(
                "rule:novel-action-as-bounded-probe",
                "rule:reuse-progress-avoid-hazard",
            ),
        )


@dataclass(frozen=True, slots=True)
class ParametricRelationalInstructionBody:
    """P-B: shared action scorer with a nonlinear hidden state."""

    version: str = "generic-parametric-relational-v1"
    provenance: str = "deterministic-generic-prior:no-environment-identity"
    hidden_weights: tuple[tuple[float, ...], ...] = (
        (0.7, -0.2, 0.1, 0.4, 1.2, -1.0, -0.3, 0.8),
        (-0.4, 0.8, 0.2, 0.3, 0.9, -1.4, -0.5, 1.0),
        (0.2, 0.1, 0.7, -0.2, 1.4, -1.2, -0.6, 0.6),
        (0.1, -0.3, 0.4, 0.8, 1.0, -1.6, -0.4, 0.9),
    )
    progress_weights: tuple[float, ...] = (1.1, 0.7, 0.5, 0.9)
    hazard_weights: tuple[float, ...] = (-0.6, -0.9, -0.7, -1.0)
    information_weights: tuple[float, ...] = (0.8, 1.0, 0.9, 0.7)
    action_bias_items: tuple[tuple[str, float], ...] = ()

    def format_id(self) -> str:
        return "generic-parametric-relational"

    def body_version(self) -> str:
        return self.version

    @lru_cache(maxsize=128)
    def provenance_digest(self) -> str:
        return "generic-p-provenance:" + digest_object(self.provenance)

    @lru_cache(maxsize=128)
    def digest(self) -> str:
        return "generic-parametric-p:" + digest_object(self)

    @lru_cache(maxsize=128)
    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if len(self.hidden_weights) < 2:
            failures.append("GENERIC_PARAMETRIC_P_NONLINEAR_DEPTH_MISSING")
        if any(len(row) != 8 for row in self.hidden_weights):
            failures.append("GENERIC_PARAMETRIC_P_HIDDEN_WIDTH_INVALID")
        hidden = len(self.hidden_weights)
        if any(
            len(values) != hidden
            for values in (
                self.progress_weights,
                self.hazard_weights,
                self.information_weights,
            )
        ):
            failures.append("GENERIC_PARAMETRIC_P_OUTPUT_WIDTH_INVALID")
        if tuple(key for key, _ in self.action_bias_items) != tuple(
            sorted(set(key for key, _ in self.action_bias_items))
        ):
            failures.append("GENERIC_PARAMETRIC_P_BIAS_INVALID")
        lowered = self.provenance.casefold()
        if any(
            term in lowered
            for term in ("game_id", "level_id", "task_id", "replay", "answer")
        ):
            failures.append("GENERIC_PARAMETRIC_P_IDENTITY_CONTAMINATED")
        return tuple(sorted(set(failures)))

    def _features(
        self,
        representation: RelationalRepresentation,
        descriptor: ActionDescriptor,
        records: tuple[SemanticRecord, ...],
        descriptor_count: int,
    ) -> tuple[tuple[float, ...], tuple[str, ...]]:
        (
            success,
            hazard,
            no_effect,
            visible_change,
            sample_count,
            memory_refs,
        ) = _record_statistics(
            descriptor,
            records,
            representation=representation,
        )
        observed = 1.0 if success + hazard + no_effect + visible_change > 0.0 else 0.0
        continue_visible_effect = (
            visible_change > 0.0
            and hazard == 0.0
            and no_effect == 0.0
            and sample_count <= 4.0
        )
        ordinal = descriptor.surface_ordinal / max(1, descriptor_count - 1)
        return (
            (
                ordinal,
                1.0 if descriptor.target_role is not None else 0.0,
                min(1.0, len(representation.roles) / 16.0),
                min(1.0, len(representation.relations) / 64.0),
                success,
                hazard,
                no_effect,
                max(
                    1.0 if continue_visible_effect else 0.0,
                    1.0 - observed,
                ),
            ),
            memory_refs,
        )

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
        action_bias = dict(self.action_bias_items)
        predictions: list[GenericPrediction] = []
        for descriptor in descriptors:
            features, memory_refs = self._features(
                representation, descriptor, records, len(descriptors)
            )
            hidden = tuple(
                math.tanh(sum(weight * value for weight, value in zip(row, features)))
                for row in self.hidden_weights
            )
            progress = _sigmoid(
                sum(
                    weight * value
                    for weight, value in zip(self.progress_weights, hidden)
                )
                - 1.2
                + action_bias.get(descriptor.semantic_key, 0.0)
            )
            hazard = _sigmoid(
                sum(
                    weight * value for weight, value in zip(self.hazard_weights, hidden)
                )
                - 2.0
            )
            information = _sigmoid(
                sum(
                    weight * value
                    for weight, value in zip(self.information_weights, hidden)
                )
                - 0.5
            )
            prior = _bounded(
                0.55 * progress + 0.35 * information - 0.45 * hazard + 0.25
            )
            effects = {"VISIBLE_STATE_CHANGE"}
            if progress >= 0.5:
                effects.add("LEVEL_PROGRESS")
            if hazard >= 0.5:
                effects.add("IRREVERSIBLE_FAILURE")
            predictions.append(
                GenericPrediction(
                    descriptor=descriptor,
                    predicted_effects=tuple(sorted(effects)),
                    progress_likelihood=progress,
                    hazard_likelihood=hazard,
                    information_gain=information,
                    prior=prior,
                    uncertainty=_bounded(1.0 - max(progress, hazard)),
                    instruction_refs=(
                        self.digest(),
                        "shared-action-embedding",
                        "nonlinear-hidden-transform",
                        "legal-action-mask",
                    ),
                    memory_refs=memory_refs,
                )
            )
        query_digest = "generic-parametric-query:" + digest_object(
            {
                "representation": representation.digest_value,
                "descriptors": descriptors,
                "records": tuple(record.citation() for record in records),
                "predictions": predictions,
            }
        )
        return InstructionBodyResult(
            predictions=tuple(predictions),
            query_digest=query_digest,
            selected_instruction_refs=(
                "shared-action-embedding",
                "nonlinear-hidden-transform",
                "legal-action-mask",
            ),
        )

    def with_action_bias(
        self,
        *,
        version: str,
        action_bias: dict[str, float],
        provenance: str,
    ) -> ParametricRelationalInstructionBody:
        return ParametricRelationalInstructionBody(
            version=version,
            provenance=provenance,
            hidden_weights=self.hidden_weights,
            progress_weights=self.progress_weights,
            hazard_weights=self.hazard_weights,
            information_weights=self.information_weights,
            action_bias_items=tuple(sorted(action_bias.items())),
        )


@dataclass(frozen=True, slots=True)
class HybridRelationalInstructionBody:
    symbolic: SymbolicRelationalInstructionBody = field(
        default_factory=SymbolicRelationalInstructionBody
    )
    parametric: ParametricRelationalInstructionBody = field(
        default_factory=ParametricRelationalInstructionBody
    )
    version: str = "generic-hybrid-relational-v1"

    def format_id(self) -> str:
        return "generic-hybrid-relational"

    def body_version(self) -> str:
        return self.version

    @lru_cache(maxsize=128)
    def provenance_digest(self) -> str:
        return "generic-p-provenance:" + digest_object(
            (self.symbolic.provenance_digest(), self.parametric.provenance_digest())
        )

    @lru_cache(maxsize=128)
    def digest(self) -> str:
        return "generic-hybrid-p:" + digest_object(self)

    @lru_cache(maxsize=128)
    def validate(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                set(
                    (
                        *self.symbolic.validate(),
                        *self.parametric.validate(),
                    )
                )
            )
        )

    def query(
        self,
        representation: RelationalRepresentation,
        descriptors: tuple[ActionDescriptor, ...],
        records: tuple[SemanticRecord, ...],
        *,
        observation: GenericObservation | None = None,
        action_history: tuple[ActionEffectRecord, ...] = (),
    ) -> InstructionBodyResult:
        symbolic = self.symbolic.query(
            representation,
            descriptors,
            records,
            observation=observation,
            action_history=action_history,
        )
        parametric = self.parametric.query(
            representation,
            descriptors,
            records,
            observation=observation,
            action_history=action_history,
        )
        symbolic_by_key = {
            item.descriptor.semantic_key: item for item in symbolic.predictions
        }
        predictions: list[GenericPrediction] = []
        for item in parametric.predictions:
            other = symbolic_by_key[item.descriptor.semantic_key]
            predictions.append(
                GenericPrediction(
                    descriptor=item.descriptor,
                    predicted_effects=tuple(
                        sorted(
                            set(
                                (
                                    *item.predicted_effects,
                                    *other.predicted_effects,
                                )
                            )
                        )
                    ),
                    progress_likelihood=(
                        item.progress_likelihood + other.progress_likelihood
                    )
                    / 2.0,
                    hazard_likelihood=max(
                        item.hazard_likelihood, other.hazard_likelihood
                    ),
                    information_gain=(item.information_gain + other.information_gain)
                    / 2.0,
                    prior=(item.prior + other.prior) / 2.0,
                    uncertainty=max(item.uncertainty, other.uncertainty),
                    instruction_refs=tuple(
                        sorted(set((*item.instruction_refs, *other.instruction_refs)))
                    ),
                    memory_refs=tuple(
                        sorted(set((*item.memory_refs, *other.memory_refs)))
                    ),
                )
            )
        return InstructionBodyResult(
            predictions=tuple(predictions),
            query_digest="generic-hybrid-query:"
            + digest_object(
                {
                    "symbolic": symbolic.query_digest,
                    "parametric": parametric.query_digest,
                    "predictions": predictions,
                }
            ),
            selected_instruction_refs=tuple(
                sorted(
                    set(
                        (
                            *symbolic.selected_instruction_refs,
                            *parametric.selected_instruction_refs,
                        )
                    )
                )
            ),
        )


@dataclass(frozen=True, slots=True)
class ComputeAblation:
    selective_retrieval: bool = True
    effective_serial_depth: bool = True
    counter_hypothesis: bool = True
    candidate_diversity: bool = True


@dataclass(slots=True)
class GenericComputeSubject:
    """C: executes L0+P but owns no final judgment or side effect."""

    authority_state: AuthorityState = field(repr=False)

    @property
    def authority_token(self) -> object:
        """Compatibility view; capability state remains session-owned."""

        return self.authority_state.live_token

    def _require_command(
        self,
        command: GenericComputeCommand,
        observation: GenericObservation,
        memory_version: int,
    ) -> None:
        self.authority_state.require_live_token(
            command._authority_token,
            error="GENERIC_COMPUTE_COMMAND_NOT_HDS_AUTHORIZED",
        )
        if command.observation_signature != observation.signature:
            raise PermissionError("GENERIC_COMPUTE_OBSERVATION_BINDING_INVALID")
        if command.memory_version != memory_version:
            raise RuntimeError("GENERIC_COMPUTE_MEMORY_VERSION_CONFLICT")
        binding_digest = digest_object(
            {
                "purpose": command.purpose,
                "goal_tokens": command.goal_tokens,
                "required_outputs": command.required_outputs,
                "observation_signature": command.observation_signature,
                "memory_version": command.memory_version,
            }
        )
        self.authority_state.consume(
            command.command_id,
            kind="HDS_COMPUTE",
            binding_digest=binding_digest,
            unknown_error="GENERIC_COMPUTE_COMMAND_NOT_HDS_AUTHORIZED",
            reused_error="GENERIC_COMPUTE_COMMAND_REUSED",
            binding_error="GENERIC_COMPUTE_COMMAND_BINDING_INVALID",
        )

    def compute(
        self,
        *,
        command: GenericComputeCommand,
        observation: GenericObservation,
        memory: SemanticMemoryReader,
        instruction_body: GenericInstructionBody | None,
        p_ir_program: PIRProgram | None = None,
        action_history: tuple[ActionEffectRecord, ...] = (),
        ablation: ComputeAblation | None = None,
    ) -> GenericComputeResult:
        from .p_ir import compatibility_p_ir_program
        from .p_ir_interpreter import (
            FixedL0PIRInterpreter,
            PIRExecutionContext,
        )

        selected_ablation = ablation or ComputeAblation()
        self._require_command(command, observation, memory.version)
        if instruction_body is None:
            raise RuntimeError(GENERIC_P_REMOVAL_WITNESS)
        body_failures = instruction_body.validate()
        if body_failures:
            raise RuntimeError(
                GENERIC_P_REMOVAL_WITNESS + ":" + ",".join(body_failures)
            )
        if not selected_ablation.effective_serial_depth:
            raise RuntimeError(GENERIC_SERIAL_DEPTH_WITNESS)
        history_failures = tuple(
            failure for record in action_history for failure in record.validate()
        )
        if history_failures:
            raise ValueError(";".join(sorted(set(history_failures))))

        selected_program = p_ir_program or compatibility_p_ir_program()
        interpreter = FixedL0PIRInterpreter()
        representation_execution = interpreter.execute_representation(
            selected_program,
            PIRExecutionContext(
                observation=observation,
                goal_tokens=command.goal_tokens,
            ),
        )
        representation = representation_execution.representation
        stages: list[Layer0StageTrace] = [
            Layer0StageTrace(
                stage="represent",
                input_digest=observation.digest(),
                output_digest=representation.digest_value,
                selected_refs=(
                    selected_program.program_id,
                    representation_execution.trace.graph_id,
                    *representation_execution.trace.ordered_node_ids,
                ),
            )
        ]
        pre_retrieval_execution = interpreter.execute(
            selected_program,
            PIRExecutionContext(
                observation=observation,
                goal_tokens=command.goal_tokens,
            ),
            representation_execution=representation_execution,
        )
        if pre_retrieval_execution.representation != representation:
            raise RuntimeError("P_IR_REPRESENTATION_REEXECUTION_MISMATCH")
        preliminary_descriptors = pre_retrieval_execution.action_bindings

        query_tokens = tuple(
            sorted(
                set(
                    (
                        *command.goal_tokens,
                        *representation.topology_tokens,
                        *representation.relations,
                        *(
                            descriptor.semantic_key
                            for descriptor in preliminary_descriptors
                        ),
                    )
                )
            )
        )
        if selected_ablation.selective_retrieval:
            memory_query = memory.query(
                SemanticMemoryQuery(
                    query_id="memory-query:"
                    + digest_object(
                        {
                            "command": command.command_id,
                            "tokens": query_tokens,
                            "version": memory.version,
                        }
                    )[:24],
                    semantic_tokens=query_tokens,
                    limit=128,
                )
            )
            records = memory_query.records
            memory_query_digest = memory_query.digest
        else:
            records = ()
            memory_query_digest = "semantic-memory-query:ABLATION_DISABLED"
        citations = tuple(record.citation() for record in records)
        p_ir_execution = interpreter.execute(
            selected_program,
            PIRExecutionContext(
                observation=observation,
                goal_tokens=command.goal_tokens,
                memory_records=records,
            ),
            representation_execution=representation_execution,
        )
        if p_ir_execution.representation != representation:
            raise RuntimeError("P_IR_REPRESENTATION_REEXECUTION_MISMATCH")
        descriptors = p_ir_execution.action_bindings
        stages.append(
            Layer0StageTrace(
                stage="retrieve",
                input_digest=representation.digest_value,
                output_digest=memory_query_digest,
                selected_refs=tuple(item.memory_id for item in citations),
            )
        )

        instruction_result = instruction_body.query(
            representation,
            descriptors,
            records,
            observation=observation,
            action_history=action_history,
        )
        descriptor_order: dict[ActionDescriptor, int] = {
            descriptor: index for index, descriptor in enumerate(descriptors)
        }
        for prediction in instruction_result.predictions:
            descriptor_failures = prediction.descriptor.validate(observation)
            if descriptor_failures:
                raise ValueError(";".join(descriptor_failures))
            if prediction.descriptor not in descriptor_order:
                descriptor_order[prediction.descriptor] = len(descriptor_order)
        ranked_predictions = tuple(
            sorted(
                instruction_result.predictions,
                key=lambda item: (
                    -item.prior,
                    item.hazard_likelihood,
                    -item.information_gain,
                    descriptor_order[item.descriptor],
                ),
            )
        )
        if not ranked_predictions:
            raise RuntimeError("GENERIC_P_PREDICTION_MISSING")
        primary = ranked_predictions[0]
        alternative = (
            ranked_predictions[1]
            if len(ranked_predictions) > 1
            else ranked_predictions[0]
        )
        hypotheses = [
            GenericHypothesis(
                hypothesis_id="hypothesis:baseline:" + digest_object(primary)[:20],
                model_type="baseline",
                statement=(
                    "The highest supported legal action relation can advance "
                    "the current goal."
                ),
                predictions=primary.predicted_effects,
                falsification_conditions=tuple(
                    sorted(
                        (
                            "selected action repeatedly produces no effect",
                            "selected action produces irreversible failure",
                        )
                    )
                ),
                supporting_evidence=tuple(
                    sorted(set((*primary.instruction_refs, *primary.memory_refs)))
                ),
                confidence=primary.prior,
            ),
            GenericHypothesis(
                hypothesis_id="hypothesis:alternative:"
                + digest_object(alternative)[:20],
                model_type="alternative",
                statement=(
                    "A different legal action or role binding explains the "
                    "transition better."
                ),
                predictions=alternative.predicted_effects,
                falsification_conditions=(
                    "alternative action has lower observed information and progress",
                ),
                supporting_evidence=tuple(
                    sorted(
                        set((*alternative.instruction_refs, *alternative.memory_refs))
                    )
                ),
                confidence=alternative.prior,
            ),
        ]
        if selected_ablation.counter_hypothesis:
            hypotheses.extend(
                (
                    GenericHypothesis(
                        hypothesis_id="hypothesis:counter:"
                        + digest_object(
                            tuple(item.hazard_likelihood for item in ranked_predictions)
                        )[:20],
                        model_type="counter_hypothesis",
                        statement=(
                            "The apparent progress prior may be a hazard or "
                            "non-causal visual change."
                        ),
                        predictions=(
                            "IRREVERSIBLE_FAILURE",
                            "NO_VISIBLE_CHANGE",
                        ),
                        falsification_conditions=(
                            "bounded probes repeatedly produce safe progress",
                        ),
                        contradicting_evidence=tuple(
                            sorted(
                                {
                                    ref
                                    for item in ranked_predictions
                                    for ref in item.memory_refs
                                }
                            )
                        ),
                        confidence=max(
                            item.hazard_likelihood for item in ranked_predictions
                        ),
                    ),
                    GenericHypothesis(
                        hypothesis_id="hypothesis:null:"
                        + digest_object(representation.digest_value)[:20],
                        model_type="null_model",
                        statement=(
                            "No legal action has yet been shown to cause progress; "
                            "observation error or delayed effect remains possible."
                        ),
                        predictions=(
                            "DELAYED_EFFECT",
                            "NO_VISIBLE_CHANGE",
                            "OBSERVATION_ERROR",
                        ),
                        falsification_conditions=(
                            "one action has reproducible immediate progress",
                        ),
                        confidence=max(item.uncertainty for item in ranked_predictions),
                    ),
                )
            )
        stages.append(
            Layer0StageTrace(
                stage="model",
                input_digest=memory_query_digest,
                output_digest="generic-model-set:" + digest_object(hypotheses),
                selected_refs=tuple(item.hypothesis_id for item in hypotheses),
            )
        )
        stages.append(
            Layer0StageTrace(
                stage="predict",
                input_digest=instruction_result.query_digest,
                output_digest="generic-predictions:"
                + digest_object(ranked_predictions),
                selected_refs=instruction_result.selected_instruction_refs,
            )
        )

        candidates: list[GenericCandidate] = []
        for prediction in ranked_predictions:
            evidence_binding_key = build_evidence_binding_key(
                topology_tokens=representation.topology_tokens,
                relations=representation.relations,
                descriptor_semantic_key=prediction.descriptor.semantic_key,
                action_id=prediction.descriptor.action_id,
                target_role=prediction.descriptor.target_role,
                payload_fields=tuple(
                    key for key, _ in prediction.descriptor.payload_items
                ),
                predicted_effects=prediction.predicted_effects,
            )
            evidence_bindings = bind_candidate_records(
                key=evidence_binding_key,
                records=records,
            )
            prediction_ref = "prediction:" + digest_object(prediction)
            memory_binding_refs = tuple(
                sorted({binding.record_digest for binding in evidence_bindings})
            )
            counter_evidence_refs = tuple(
                sorted(
                    {
                        binding.record_digest
                        for binding in evidence_bindings
                        if (
                            binding.hazard_count > 0
                            or binding.contradiction_count > 0
                            or not binding.precondition_match
                            or not binding.effect_compatible
                            or not binding.scope_applicable
                        )
                    }
                )
            )
            bound_record_ids = {binding.record_id for binding in evidence_bindings}
            memory_effects = _memory_effects(
                records,
                bound_record_ids,
            )
            operation = (
                "ACTION"
                if prediction.progress_likelihood >= 0.55
                and prediction.hazard_likelihood <= 0.25
                and prediction.memory_refs
                else "BOUNDED_PROBE"
            )
            candidates.append(
                GenericCandidate(
                    candidate_id="candidate:generic:"
                    + digest_object(
                        {
                            "command": command.command_id,
                            "descriptor": prediction.descriptor,
                        }
                    )[:24],
                    descriptor=prediction.descriptor,
                    operation=operation,
                    expected_progress=prediction.progress_likelihood,
                    expected_information_gain=prediction.information_gain,
                    expected_risk=prediction.hazard_likelihood,
                    uncertainty=prediction.uncertainty,
                    prediction_refs=(prediction_ref,),
                    provenance=(
                        instruction_body.digest(),
                        instruction_result.query_digest,
                        representation.digest_value,
                        p_ir_execution.program_logical_digest,
                        GENERIC_COMPUTE_VERSION,
                    ),
                    evidence_binding_key=evidence_binding_key,
                    evidence_bindings=evidence_bindings,
                    typed_provenance=TypedCandidateProvenance(
                        p_instruction_refs=tuple(
                            sorted(set(prediction.instruction_refs))
                        ),
                        representation_refs=(representation.digest_value,),
                        prediction_refs=(prediction_ref,),
                        memory_binding_refs=memory_binding_refs,
                        counter_evidence_refs=counter_evidence_refs,
                        runtime_version=GENERIC_COMPUTE_VERSION,
                    ),
                    memory_effects=memory_effects,
                )
            )
        if not selected_ablation.candidate_diversity:
            candidates = candidates[:1]
        stages.append(
            Layer0StageTrace(
                stage="candidate",
                input_digest="generic-predictions:" + digest_object(ranked_predictions),
                output_digest="generic-candidates:" + digest_object(candidates),
                selected_refs=tuple(item.candidate_id for item in candidates),
            )
        )
        result = GenericComputeResult(
            command_id=command.command_id,
            representation=representation,
            memory_citations=citations,
            hypotheses=tuple(hypotheses),
            predictions=ranked_predictions,
            candidates=tuple(candidates),
            stages=tuple(stages),
            instruction_body_format=instruction_body.format_id(),
            instruction_body_version=instruction_body.body_version(),
            instruction_body_digest=instruction_body.digest(),
            p_ir_logical_digest=p_ir_execution.program_logical_digest,
            p_ir_execution_digest=p_ir_execution.execution_digest,
            l0_abi_version=selected_program.l0_abi_version,
            uncertainty=max(item.uncertainty for item in ranked_predictions),
            provenance=(
                instruction_body.provenance_digest(),
                memory_query_digest,
                p_ir_execution.program_logical_digest,
                p_ir_execution.execution_digest,
                GENERIC_COMPUTE_VERSION,
            ),
            control_operation=instruction_result.control_operation,
            control_instruction_refs=(instruction_result.control_instruction_refs),
        )
        return result


__all__ = [
    "ComputeAblation",
    "GENERIC_COMPUTE_VERSION",
    "GENERIC_P_REMOVAL_WITNESS",
    "GENERIC_SERIAL_DEPTH_WITNESS",
    "GenericComputeSubject",
    "GenericInstructionBody",
    "HybridRelationalInstructionBody",
    "InstructionBodyResult",
    "ParametricRelationalInstructionBody",
    "SemanticMemoryReader",
    "SymbolicRelationalInstructionBody",
    "action_descriptors",
    "represent_observation",
]
