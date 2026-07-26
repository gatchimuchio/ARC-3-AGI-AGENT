"""Identity-free pre-action relation and successor-obligation probe.

This module is development telemetry only.  It compiles rendered geometry
available before an action into a bounded relation class, predicts the visible
successor obligation from evidence retained *before* the current outcome, and
then records the observed obligation after re-observation.  It has no action,
memory-write, judgment, emission, or Runtime-P promotion authority.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping
from dataclasses import dataclass, field
from math import gcd
from typing import Literal

from .cross_cutting_transition import (
    BoundaryLabel,
    observe_visible_transition,
)
from .schema import digest_object, forbidden_runtime_paths
from .visual_explorer import (
    Grid,
    VisualAction,
    VisualComponent,
    VisualScene,
    masked_grid,
)

PROSPECTIVE_RELATION_PROBE_FORMAT = (
    "arc3-prospective-obligation-relation-probe-v1"
)
PROSPECTIVE_RELATION_CAPABILITY_IDS = (
    "prospective_rendered_relation_compiler",
    "visible_successor_obligation_predictor",
)
PROSPECTIVE_RELATION_MODEL_LIMIT = 512
PROSPECTIVE_RELATION_CONTEXT_LIMIT = 512
PROSPECTIVE_RELATION_RECORD_LIMIT = 512
PROSPECTIVE_RELATION_COMPONENT_LIMIT = 32

SuccessorObligation = Literal[
    "REOBSERVE_COMMIT_STATE",
    "SUSPEND_AND_REQUEST_ROLLBACK",
    "FOLLOW_RELATION_DELTA",
    "RECLASSIFY_VISIBLE_SUCCESSOR",
    "CHANGE_RELATION_OR_WAIT",
    "VERIFY_RELATION_SETTLE",
]
PredictionLabel = Literal[
    "REOBSERVE_COMMIT_STATE",
    "SUSPEND_AND_REQUEST_ROLLBACK",
    "FOLLOW_RELATION_DELTA",
    "RECLASSIFY_VISIBLE_SUCCESSOR",
    "CHANGE_RELATION_OR_WAIT",
    "VERIFY_RELATION_SETTLE",
    "UNKNOWN",
]

_COUNT_BUCKETS = (0, 1, 2, 4, 8, 16, 32)
_RATIO_BUCKETS = (1, 5, 20, 100, 250, 500, 1000)
_GAP_BUCKETS = (0, 1, 2, 4, 8, 16)


def _bucket(value: int, thresholds: tuple[int, ...]) -> str:
    if value < 0:
        raise ValueError("prospective relation bucket value must be nonnegative")
    for threshold in thresholds:
        if value <= threshold:
            return str(threshold)
    return f"{thresholds[-1]}+"


def _component_shape(component: VisualComponent) -> str:
    scale = gcd(component.width, component.height)
    fill_milli = round(
        1000 * component.area / (component.width * component.height)
    )
    return ":".join(
        (
            f"aspect={component.width // scale}x{component.height // scale}",
            f"fill={_bucket(fill_milli, _RATIO_BUCKETS)}",
            f"rect={int(component.rectangular)}",
        )
    )


def _component_role(
    component: VisualComponent,
    *,
    scene_area: int,
    width: int,
    height: int,
    include_color: bool,
) -> str:
    min_x, min_y, max_x, max_y = component.bbox
    edge_sides = "".join(
        (
            "L" if min_x == 0 else "",
            "R" if max_x == width - 1 else "",
            "T" if min_y == 0 else "",
            "B" if max_y == height - 1 else "",
        )
    )
    area_milli = round(1000 * component.area / max(1, scene_area))
    fields = [
        _component_shape(component),
        f"area={_bucket(area_milli, _RATIO_BUCKETS)}",
        f"twins={_bucket(component.twin_count, _COUNT_BUCKETS)}",
        f"edge={edge_sides or 'INTERIOR'}",
    ]
    if include_color:
        fields.insert(0, f"color={component.color}")
    return "|".join(fields)


def _bbox_contains(
    outer: VisualComponent,
    inner: VisualComponent,
) -> bool:
    return (
        outer.bbox[0] <= inner.bbox[0]
        and outer.bbox[1] <= inner.bbox[1]
        and outer.bbox[2] >= inner.bbox[2]
        and outer.bbox[3] >= inner.bbox[3]
    )


def _axis_relation(
    first_min: int,
    first_max: int,
    second_min: int,
    second_max: int,
) -> tuple[str, int]:
    if first_max < second_min:
        return ("BEFORE", second_min - first_max - 1)
    if second_max < first_min:
        return ("AFTER", first_min - second_max - 1)
    return ("OVERLAP", 0)


def _pair_relation(
    first: VisualComponent,
    second: VisualComponent,
    *,
    include_color: bool,
) -> str:
    horizontal, horizontal_gap = _axis_relation(
        first.bbox[0],
        first.bbox[2],
        second.bbox[0],
        second.bbox[2],
    )
    vertical, vertical_gap = _axis_relation(
        first.bbox[1],
        first.bbox[3],
        second.bbox[1],
        second.bbox[3],
    )
    normalizer = max(
        1,
        first.width,
        first.height,
        second.width,
        second.height,
    )
    gap_quarters = round(
        4 * (horizontal_gap + vertical_gap) / normalizer
    )
    touching = (
        (horizontal_gap == 0 and vertical == "OVERLAP")
        or (vertical_gap == 0 and horizontal == "OVERLAP")
    ) and not (
        horizontal == "OVERLAP" and vertical == "OVERLAP"
    )
    containment = (
        "FIRST_CONTAINS"
        if _bbox_contains(first, second)
        else (
            "SECOND_CONTAINS"
            if _bbox_contains(second, first)
            else "NONE"
        )
    )
    fields = [
        f"x={horizontal}",
        f"y={vertical}",
        f"gap={_bucket(gap_quarters, _GAP_BUCKETS)}",
        f"touch={int(touching)}",
        f"contain={containment}",
        f"shape_match={int(_component_shape(first) == _component_shape(second))}",
    ]
    if include_color:
        fields.append(f"color_match={int(first.color == second.color)}")
    return "|".join(fields)


def _background_color(grid: Grid, scene: VisualScene) -> int:
    normalized = masked_grid(grid, scene.status_mask)
    counts = Counter(value for row in normalized for value in row)
    if not counts:
        raise ValueError("prospective relation rendered grid is empty")
    return max(counts.items(), key=lambda item: (item[1], -item[0]))[0]


def _salient_components(
    grid: Grid,
    scene: VisualScene,
) -> tuple[VisualComponent, ...]:
    background = _background_color(grid, scene)
    foreground = tuple(
        component
        for component in scene.components
        if component.color != background
    )
    candidates = foreground or tuple(
        sorted(
            scene.components,
            key=lambda component: (
                -component.area,
                component.color,
                component.bbox,
            ),
        )[1:]
    )
    return tuple(
        sorted(
            candidates,
            key=lambda component: (
                -component.area,
                component.color,
                _component_shape(component),
                component.bbox,
            ),
        )[:PROSPECTIVE_RELATION_COMPONENT_LIMIT]
    )


def _counter_tokens(
    prefix: str,
    counts: Counter[str],
) -> tuple[str, ...]:
    return tuple(
        f"{prefix}:{key}:count={_bucket(count, _COUNT_BUCKETS)}"
        for key, count in sorted(counts.items())
    )


def _target_component(
    action: VisualAction,
    components: tuple[VisualComponent, ...],
) -> VisualComponent | None:
    if action.action_id != 6 or action.x is None or action.y is None:
        return None
    action_x = action.x
    action_y = action.y
    point = (action_x, action_y)
    containing = tuple(
        component for component in components if point in component.pixels
    )
    if containing:
        return min(
            containing,
            key=lambda component: (
                component.area,
                component.color,
                component.bbox,
            ),
        )
    if not components:
        return None
    return min(
        components,
        key=lambda component: (
            max(
                component.bbox[0] - action_x,
                0,
                action_x - component.bbox[2],
            )
            + max(
                component.bbox[1] - action_y,
                0,
                action_y - component.bbox[3],
            ),
            component.area,
            component.color,
            component.bbox,
        ),
    )


@dataclass(frozen=True, slots=True)
class ProspectiveRelationState:
    """Bounded relation material available before one action."""

    relation_class: str
    cluster_class: str
    action_class: str
    action_prototype: str
    relation_features: tuple[str, ...]
    cluster_features: tuple[str, ...]
    motif_features: tuple[str, ...]

    def to_payload(self) -> dict[str, object]:
        return {
            "relation_class": self.relation_class,
            "cluster_class": self.cluster_class,
            "action_class": self.action_class,
            "action_prototype": self.action_prototype,
            "relation_features": list(self.relation_features),
            "cluster_features": list(self.cluster_features),
            "motif_features": list(self.motif_features),
        }


def compile_prospective_relation(
    *,
    rendered_grid: Grid,
    scene: VisualScene,
    action: VisualAction,
) -> ProspectiveRelationState:
    """Compile an identity-free relation class using pre-action render only."""

    if not rendered_grid:
        raise ValueError("prospective relation rendered grid is required")
    if len(rendered_grid) != scene.height or len(rendered_grid[0]) != scene.width:
        raise ValueError("prospective relation scene dimensions mismatch")
    components = _salient_components(rendered_grid, scene)
    scene_area = scene.width * scene.height
    colored_roles = Counter(
        _component_role(
            component,
            scene_area=scene_area,
            width=scene.width,
            height=scene.height,
            include_color=True,
        )
        for component in components
    )
    structural_roles = Counter(
        _component_role(
            component,
            scene_area=scene_area,
            width=scene.width,
            height=scene.height,
            include_color=False,
        )
        for component in components
    )
    colored_pairs: Counter[str] = Counter()
    structural_pairs: Counter[str] = Counter()
    for index, first in enumerate(components):
        for second in components[index + 1 :]:
            colored_pairs[
                _pair_relation(first, second, include_color=True)
            ] += 1
            structural_pairs[
                _pair_relation(first, second, include_color=False)
            ] += 1

    component_cardinality = (
        "NONE"
        if not components
        else (
            "ONE"
            if len(components) == 1
            else ("FEW" if len(components) <= 4 else "MANY")
        )
    )
    color_count = len({item.color for item in components})
    color_cardinality = (
        "NONE"
        if color_count == 0
        else (
            "ONE"
            if color_count == 1
            else ("FEW" if color_count <= 4 else "MANY")
        )
    )
    shape_counts = Counter(_component_shape(item) for item in components)
    color_counts = Counter(item.color for item in components)
    motif_features: tuple[str, ...] = (
        f"motif:component-cardinality:{component_cardinality}",
        f"motif:color-cardinality:{color_cardinality}",
        (
            "motif:repeated-shape:"
            + str(int(any(count > 1 for count in shape_counts.values())))
        ),
        (
            "motif:repeated-color:"
            + str(int(any(count > 1 for count in color_counts.values())))
        ),
        (
            "motif:edge-role:"
            + str(
                int(
                    any(
                        component.bbox[0] == 0
                        or component.bbox[1] == 0
                        or component.bbox[2] == scene.width - 1
                        or component.bbox[3] == scene.height - 1
                        for component in components
                    )
                )
            )
        ),
        (
            "motif:touching-pair:"
            + str(
                int(
                    any(
                        "touch=1" in relation
                        for relation in structural_pairs
                    )
                )
            )
        ),
        (
            "motif:containment-pair:"
            + str(
                int(
                    any(
                        "contain=NONE" not in relation
                        for relation in structural_pairs
                    )
                )
            )
        ),
        (
            "motif:shape-match-pair:"
            + str(
                int(
                    any(
                        "shape_match=1" in relation
                        for relation in structural_pairs
                    )
                )
            )
        ),
        (
            "motif:horizontal-alignment:"
            + str(
                int(
                    any(
                        "y=OVERLAP" in relation
                        for relation in structural_pairs
                    )
                )
            )
        ),
        (
            "motif:vertical-alignment:"
            + str(
                int(
                    any(
                        "x=OVERLAP" in relation
                        for relation in structural_pairs
                    )
                )
            )
        ),
    )

    action_class = f"action-channel:{action.action_id}:group:{action.group}"
    relation_features = (
        f"component-count={_bucket(len(components), _COUNT_BUCKETS)}",
        f"color-count={_bucket(len({item.color for item in components}), _COUNT_BUCKETS)}",
        *_counter_tokens("role", colored_roles),
        *_counter_tokens("pair", colored_pairs),
    )
    cluster_features = (
        f"component-count={_bucket(len(components), _COUNT_BUCKETS)}",
        *_counter_tokens("role", structural_roles),
        *_counter_tokens("pair", structural_pairs),
    )
    target = _target_component(action, components)
    if target is not None:
        target_shape = _component_shape(target)
        target_neighbors = tuple(
            other for other in components if other is not target
        )
        relation_features += (
            "action-target:"
            + _component_role(
                target,
                scene_area=scene_area,
                width=scene.width,
                height=scene.height,
                include_color=True,
            ),
        )
        cluster_features += (
            "action-target:"
            + _component_role(
                target,
                scene_area=scene_area,
                width=scene.width,
                height=scene.height,
                include_color=False,
            ),
        )
        neighbor_relations = Counter(
            _pair_relation(target, other, include_color=False)
            for other in target_neighbors
        )
        cluster_features += _counter_tokens(
            "target-neighbor",
            neighbor_relations,
        )
        motif_features += (
            "motif:action-target:1",
            (
                "motif:target-repeated-shape:"
                + str(int(shape_counts[target_shape] > 1))
            ),
            (
                "motif:target-twin:"
                + str(int(target.twin_count > 0))
            ),
            (
                "motif:target-touching-neighbor:"
                + str(
                    int(
                        any(
                            "touch=1" in relation
                            for relation in neighbor_relations
                        )
                    )
                )
            ),
            (
                "motif:target-aligned-neighbor:"
                + str(
                    int(
                        any(
                            "x=OVERLAP" in relation
                            or "y=OVERLAP" in relation
                            for relation in neighbor_relations
                        )
                    )
                )
            ),
        )
    else:
        motif_features += ("motif:action-target:0",)

    relation_core = {
        "action_class": action_class,
        "action_prototype": action.prototype_key,
        "features": relation_features,
    }
    cluster_core = {
        "action_class": action_class,
        "features": cluster_features,
    }
    return ProspectiveRelationState(
        relation_class=(
            "prospective-relation:" + digest_object(relation_core)[:24]
        ),
        cluster_class=(
            "prospective-cluster:" + digest_object(cluster_core)[:24]
        ),
        action_class=action_class,
        action_prototype=action.prototype_key,
        relation_features=relation_features,
        cluster_features=cluster_features,
        motif_features=(action_class, *motif_features),
    )


@dataclass(frozen=True, slots=True)
class ObligationPrediction:
    label: PredictionLabel
    evidence_count: int
    context_support: int
    confidence_milli: int
    reason_codes: tuple[str, ...]
    action_selection_authorized: bool = False
    memory_write_authorized: bool = False
    runtime_p_promotion_authorized: bool = False

    def to_payload(self) -> dict[str, object]:
        return {
            "label": self.label,
            "evidence_count": self.evidence_count,
            "context_support": self.context_support,
            "confidence_milli": self.confidence_milli,
            "reason_codes": list(self.reason_codes),
            "action_selection_authorized": (
                self.action_selection_authorized
            ),
            "memory_write_authorized": self.memory_write_authorized,
            "runtime_p_promotion_authorized": (
                self.runtime_p_promotion_authorized
            ),
        }


def _predict_from_counts(
    counts: Mapping[str, int],
    *,
    context_support: int,
    model_scope: str,
) -> ObligationPrediction:
    total = sum(int(value) for value in counts.values())
    if total < 1:
        return ObligationPrediction(
            label="UNKNOWN",
            evidence_count=0,
            context_support=0,
            confidence_milli=0,
            reason_codes=("NO_PRIOR_RELATION_EVIDENCE",),
        )
    ordered = sorted(
        ((int(count), label) for label, count in counts.items()),
        key=lambda item: (-item[0], item[1]),
    )
    best_count, best_label = ordered[0]
    tied = sum(count == best_count for count, _label in ordered) > 1
    if tied:
        return ObligationPrediction(
            label="UNKNOWN",
            evidence_count=total,
            context_support=context_support,
            confidence_milli=0,
            reason_codes=("OBLIGATION_LABEL_TIE", model_scope),
        )
    return ObligationPrediction(
        label=best_label,  # type: ignore[arg-type]
        evidence_count=total,
        context_support=context_support,
        confidence_milli=round(1000 * best_count / total),
        reason_codes=(f"DOMINANT_{best_label}", model_scope),
    )


def _successor_obligation(
    *,
    boundary_label: BoundaryLabel,
    effect_classes: tuple[str, ...],
    relation_changed: bool,
) -> SuccessorObligation:
    if boundary_label == "HAZARD":
        return "SUSPEND_AND_REQUEST_ROLLBACK"
    if boundary_label == "COMMIT":
        return "REOBSERVE_COMMIT_STATE"
    if "NO_VISIBLE_CHANGE" in effect_classes:
        return "CHANGE_RELATION_OR_WAIT"
    if "GLOBAL_REDRAW" in effect_classes:
        return "RECLASSIFY_VISIBLE_SUCCESSOR"
    if relation_changed:
        return "FOLLOW_RELATION_DELTA"
    return "VERIFY_RELATION_SETTLE"


@dataclass(frozen=True, slots=True)
class ProspectiveRelationRecord:
    ordinal: int
    pre_action_relation: ProspectiveRelationState
    prediction: ObligationPrediction
    observed_obligation: SuccessorObligation
    observed_boundary: BoundaryLabel
    effect_classes: tuple[str, ...]
    relation_delta: str

    @property
    def prediction_match(self) -> bool | None:
        if self.prediction.label == "UNKNOWN":
            return None
        return self.prediction.label == self.observed_obligation

    @property
    def digest(self) -> str:
        return "prospective-obligation:" + digest_object(
            self.to_payload()
        )[:24]

    def to_payload(self) -> dict[str, object]:
        return {
            "ordinal": self.ordinal,
            "pre_action_relation": self.pre_action_relation.to_payload(),
            "prediction_before_update": self.prediction.to_payload(),
            "observed_obligation": self.observed_obligation,
            "observed_boundary": self.observed_boundary,
            "effect_classes": list(self.effect_classes),
            "relation_delta": self.relation_delta,
            "prediction_match": self.prediction_match,
        }


@dataclass(slots=True)
class ProspectiveObligationRelationProbe:
    """Prequential, shadow-only relation/obligation evidence collector."""

    observation_count: int = 0
    fault_count: int = 0
    known_prediction_count: int = 0
    correct_prediction_count: int = 0
    obligation_counts: Counter[str] = field(default_factory=Counter)
    relation_delta_counts: Counter[str] = field(default_factory=Counter)
    fault_counts: Counter[str] = field(default_factory=Counter)
    exact_models: dict[str, Counter[str]] = field(default_factory=dict)
    cluster_models: dict[str, Counter[str]] = field(default_factory=dict)
    motif_models: dict[str, Counter[str]] = field(default_factory=dict)
    cluster_contexts: dict[str, set[str]] = field(default_factory=dict)
    records: list[ProspectiveRelationRecord] = field(default_factory=list)
    model_overflow_count: int = 0
    context_overflow_count: int = 0
    record_overflow_count: int = 0
    overflow_digest_chain: str = ""
    observation_digest_chain: str = ""
    last_record: ProspectiveRelationRecord | None = None

    def record_fault(self, reason: str) -> None:
        if not reason or not reason.replace("_", "").isalnum():
            raise ValueError("PROSPECTIVE_RELATION_FAULT_REASON_INVALID")
        self.fault_count += 1
        self.fault_counts[reason] += 1

    @staticmethod
    def _exact_key(state: ProspectiveRelationState) -> str:
        return digest_object(
            {
                "relation_class": state.relation_class,
                "action_prototype": state.action_prototype,
            }
        )

    @staticmethod
    def _cluster_key(state: ProspectiveRelationState) -> str:
        return digest_object(
            {
                "cluster_class": state.cluster_class,
                "action_class": state.action_class,
            }
        )

    @staticmethod
    def _motif_keys(
        state: ProspectiveRelationState,
    ) -> tuple[str, ...]:
        return tuple(
            digest_object(
                {
                    "action_class": state.action_class,
                    "motif": motif,
                }
            )
            for motif in state.motif_features
        )

    def predict(
        self,
        state: ProspectiveRelationState,
    ) -> ObligationPrediction:
        exact = self.exact_models.get(self._exact_key(state))
        if exact:
            return _predict_from_counts(
                exact,
                context_support=1,
                model_scope="EXACT_PRE_ACTION_RELATION",
            )
        cluster_key = self._cluster_key(state)
        cluster = self.cluster_models.get(cluster_key)
        if cluster:
            return _predict_from_counts(
                cluster,
                context_support=len(
                    self.cluster_contexts.get(cluster_key, set())
                ),
                model_scope="CROSS_RELATION_CLUSTER",
            )
        motif_counts: Counter[str] = Counter()
        motif_support = 0
        for motif_key in self._motif_keys(state):
            counts = self.motif_models.get(motif_key)
            if not counts:
                continue
            motif_counts.update(counts)
            motif_support += 1
        if motif_counts:
            return _predict_from_counts(
                motif_counts,
                context_support=motif_support,
                model_scope="SHARED_RELATION_MOTIFS",
            )
        return _predict_from_counts(
            {},
            context_support=0,
            model_scope="NO_MODEL",
        )

    def _retain_model(
        self,
        models: dict[str, Counter[str]],
        key: str,
        obligation: SuccessorObligation,
    ) -> bool:
        counts = models.get(key)
        if counts is None:
            if len(models) >= PROSPECTIVE_RELATION_MODEL_LIMIT:
                self.model_overflow_count += 1
                return False
            counts = Counter()
            models[key] = counts
        counts[obligation] += 1
        return True

    def observe(
        self,
        *,
        before_grid: Grid,
        after_grid: Grid,
        before_scene: VisualScene,
        after_scene: VisualScene,
        action: VisualAction,
        terminal_state: str,
        progress_observed: bool,
    ) -> ProspectiveRelationRecord:
        pre_action = compile_prospective_relation(
            rendered_grid=before_grid,
            scene=before_scene,
            action=action,
        )
        prediction = self.predict(pre_action)
        successor = compile_prospective_relation(
            rendered_grid=after_grid,
            scene=after_scene,
            action=action,
        )
        transition = observe_visible_transition(
            before_grid=before_grid,
            after_grid=after_grid,
            before_scene=before_scene,
            after_scene=after_scene,
            action=action,
            terminal_state=terminal_state,
            progress_observed=progress_observed,
        )
        relation_changed = (
            pre_action.relation_class != successor.relation_class
        )
        relation_delta = (
            "RELATION_CHANGED" if relation_changed else "RELATION_STABLE"
        )
        obligation = _successor_obligation(
            boundary_label=transition.boundary_label,
            effect_classes=transition.effect_classes,
            relation_changed=relation_changed,
        )
        ordinal = self.observation_count + 1
        record = ProspectiveRelationRecord(
            ordinal=ordinal,
            pre_action_relation=pre_action,
            prediction=prediction,
            observed_obligation=obligation,
            observed_boundary=transition.boundary_label,
            effect_classes=transition.effect_classes,
            relation_delta=relation_delta,
        )

        exact_key = self._exact_key(pre_action)
        cluster_key = self._cluster_key(pre_action)
        self._retain_model(self.exact_models, exact_key, obligation)
        self._retain_model(self.cluster_models, cluster_key, obligation)
        for motif_key in self._motif_keys(pre_action):
            self._retain_model(self.motif_models, motif_key, obligation)
        contexts = self.cluster_contexts.setdefault(cluster_key, set())
        if pre_action.relation_class in contexts:
            pass
        elif len(contexts) < PROSPECTIVE_RELATION_CONTEXT_LIMIT:
            contexts.add(pre_action.relation_class)
        else:
            self.context_overflow_count += 1

        self.observation_count = ordinal
        self.obligation_counts[obligation] += 1
        self.relation_delta_counts[relation_delta] += 1
        if record.prediction_match is not None:
            self.known_prediction_count += 1
            self.correct_prediction_count += int(record.prediction_match)
        self.observation_digest_chain = digest_object(
            {
                "previous": self.observation_digest_chain,
                "current": record.digest,
                "ordinal": ordinal,
            }
        )
        if len(self.records) < PROSPECTIVE_RELATION_RECORD_LIMIT:
            self.records.append(record)
        else:
            self.record_overflow_count += 1
        if (
            self.model_overflow_count
            or self.context_overflow_count
            or self.record_overflow_count
        ):
            self.overflow_digest_chain = digest_object(
                {
                    "previous": self.overflow_digest_chain,
                    "observation": record.digest,
                    "model_overflow_count": self.model_overflow_count,
                    "context_overflow_count": self.context_overflow_count,
                    "record_overflow_count": self.record_overflow_count,
                }
            )
        self.last_record = record
        return record

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "format": PROSPECTIVE_RELATION_PROBE_FORMAT,
            "work_block_id": (
                "WB-PROSPECTIVE-OBLIGATION-RELATION-COMPILER"
            ),
            "capability_ids": list(
                PROSPECTIVE_RELATION_CAPABILITY_IDS
            ),
            "candidate_tier": "LOCAL_PROBE",
            "runtime_use": "FORBIDDEN",
            "runtime_decision_use": "FORBIDDEN",
            "action_selection_influence": False,
            "memory_write_authority": False,
            "external_emit_authority": False,
            "runtime_p_promotion_authority": False,
            "raw_grid_retention": False,
            "prediction_causality": (
                "PRE_ACTION_RELATION_AND_PRIOR_OBSERVATIONS_ONLY"
            ),
            "retention_limits": {
                "component_count": PROSPECTIVE_RELATION_COMPONENT_LIMIT,
                "model_count_per_scope": (
                    PROSPECTIVE_RELATION_MODEL_LIMIT
                ),
                "context_count_per_cluster": (
                    PROSPECTIVE_RELATION_CONTEXT_LIMIT
                ),
                "record_count": PROSPECTIVE_RELATION_RECORD_LIMIT,
            },
            "observation_count": self.observation_count,
            "fault_count": self.fault_count,
            "fault_counts": dict(sorted(self.fault_counts.items())),
            "known_prediction_count": self.known_prediction_count,
            "correct_prediction_count": self.correct_prediction_count,
            "obligation_counts": dict(
                sorted(self.obligation_counts.items())
            ),
            "relation_delta_counts": dict(
                sorted(self.relation_delta_counts.items())
            ),
            "exact_models": {
                key: dict(sorted(counts.items()))
                for key, counts in sorted(self.exact_models.items())
            },
            "cluster_models": {
                key: dict(sorted(counts.items()))
                for key, counts in sorted(self.cluster_models.items())
            },
            "motif_models": {
                key: dict(sorted(counts.items()))
                for key, counts in sorted(self.motif_models.items())
            },
            "cluster_context_support": {
                key: len(contexts)
                for key, contexts in sorted(
                    self.cluster_contexts.items()
                )
            },
            "records": [record.to_payload() for record in self.records],
            "model_overflow_count": self.model_overflow_count,
            "context_overflow_count": self.context_overflow_count,
            "record_overflow_count": self.record_overflow_count,
            "overflow_digest_chain": self.overflow_digest_chain,
            "observation_digest_chain": self.observation_digest_chain,
            "last_record": (
                None
                if self.last_record is None
                else self.last_record.to_payload()
            ),
        }
        forbidden = forbidden_runtime_paths(payload)
        if forbidden:
            raise ValueError(
                "PROSPECTIVE_RELATION_RUNTIME_IDENTITY_FORBIDDEN:"
                + ",".join(forbidden)
            )
        return payload


__all__ = [
    "ObligationPrediction",
    "PROSPECTIVE_RELATION_CAPABILITY_IDS",
    "PROSPECTIVE_RELATION_COMPONENT_LIMIT",
    "PROSPECTIVE_RELATION_CONTEXT_LIMIT",
    "PROSPECTIVE_RELATION_MODEL_LIMIT",
    "PROSPECTIVE_RELATION_PROBE_FORMAT",
    "PROSPECTIVE_RELATION_RECORD_LIMIT",
    "PredictionLabel",
    "ProspectiveObligationRelationProbe",
    "ProspectiveRelationRecord",
    "ProspectiveRelationState",
    "SuccessorObligation",
    "compile_prospective_relation",
]
