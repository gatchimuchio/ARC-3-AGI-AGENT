"""Identity-free C2/C3 visible-transition and commit-boundary probe.

The probe is deliberately non-authoritative: it observes rendered pre/post
state, aggregates reusable effect and boundary evidence, and returns
predictions as computation material only.  It cannot select or emit actions,
write passive memory, judge promotion, or mutate Runtime P.
"""

from __future__ import annotations

from collections import Counter
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Literal

from .schema import digest_object, forbidden_runtime_paths
from .visual_explorer import Grid, VisualAction, VisualComponent, VisualScene

C2_C3_PROBE_FORMAT = "arc3-c2-c3-cross-cutting-probe-v2"
C2_C3_LEGACY_PROBE_FORMATS = ("arc3-c2-c3-cross-cutting-probe-v1",)
C2_C3_MODEL_LIMIT = 512
C2_C3_CONTEXT_LIMIT_PER_ACTION = 512
C2_C3_CONTRAST_RECORD_LIMIT = 512
C2_C3_CAPABILITY_IDS = (
    "C2_visible_effect_transition_model",
    "C3_commit_boundary_predictor",
)

BoundaryLabel = Literal[
    "COMMIT",
    "HAZARD",
    "TRANSITION_NO_COMMIT",
    "NO_VISIBLE_COMMIT",
]
PredictionStatus = Literal[
    "COMMIT_LIKELY",
    "HAZARD_LIKELY",
    "TRANSITION_ONLY_LIKELY",
    "NO_VISIBLE_COMMIT_LIKELY",
    "UNKNOWN",
]
ContrastRole = Literal["POSITIVE", "NEGATIVE", "HAZARD"]
ReobserveObligation = Literal[
    "REOBSERVE_COMMIT_STATE",
    "SUSPEND_AND_REQUEST_ROLLBACK",
    "REOBSERVE_BEFORE_CONTINUATION",
    "WAIT_REOBSERVE_OR_REPLAN",
]


def _integer(value: object, field_name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    return value


def _component_shape(component: VisualComponent) -> str:
    scale = max(1, min(component.width, component.height))
    return (
        f"shape:{component.width // scale}x{component.height // scale}:"
        "fill:"
        f"{round(1000 * component.area / max(1, component.width * component.height))}:"
        f"rect:{int(component.rectangular)}:twins:{component.twin_count}"
    )


def _component_descriptor(component: VisualComponent) -> tuple[object, ...]:
    return (
        component.color,
        component.area,
        component.width,
        component.height,
        component.rectangular,
    )


def _component_positions(
    components: Sequence[VisualComponent],
) -> dict[tuple[object, ...], tuple[tuple[int, int, int, int], ...]]:
    positions: dict[
        tuple[object, ...],
        list[tuple[int, int, int, int]],
    ] = {}
    for component in components:
        positions.setdefault(
            _component_descriptor(component),
            [],
        ).append(component.bbox)
    return {
        descriptor: tuple(sorted(boxes))
        for descriptor, boxes in positions.items()
    }


def _shape_multiset(scene: VisualScene) -> tuple[str, ...]:
    counts = Counter(_component_shape(component) for component in scene.components)
    return tuple(
        f"{shape}:count:{count}"
        for shape, count in sorted(counts.items())
    )


def _action_surface(scene: VisualScene) -> tuple[str, ...]:
    counts = Counter(
        f"action:{action.action_id}:group:{action.group}"
        for action in scene.candidates
    )
    return tuple(
        f"{action_class}:count:{count}"
        for action_class, count in sorted(counts.items())
    )


@dataclass(frozen=True, slots=True)
class VisibleStateAbstraction:
    """Position- and identity-independent class plus rendered state digests."""

    rendered_signature: str
    structural_signature: str
    structure_class: str
    component_count: int
    shape_multiset: tuple[str, ...]
    action_surface: tuple[str, ...]

    @classmethod
    def from_scene(cls, scene: VisualScene) -> VisibleStateAbstraction:
        shapes = _shape_multiset(scene)
        actions = _action_surface(scene)
        structure_material = {
            "aspect_class": (
                "square"
                if scene.width == scene.height
                else "wide"
                if scene.width > scene.height
                else "tall"
            ),
            "component_count_bucket": min(
                32,
                len(scene.components),
            ),
            "shape_multiset": shapes,
            "action_surface": actions,
        }
        return cls(
            rendered_signature=scene.signature,
            structural_signature=scene.structural_digest,
            structure_class=(
                "structure-class:"
                + digest_object(structure_material)[:24]
            ),
            component_count=len(scene.components),
            shape_multiset=shapes,
            action_surface=actions,
        )

    def to_payload(self) -> dict[str, object]:
        return {
            "rendered_signature": self.rendered_signature,
            "structural_signature": self.structural_signature,
            "structure_class": self.structure_class,
            "component_count": self.component_count,
            "shape_multiset": list(self.shape_multiset),
            "action_surface": list(self.action_surface),
        }


def _changed_cell_milli(before: Grid, after: Grid) -> int:
    if not before or not after:
        return 1000
    if len(before) != len(after) or len(before[0]) != len(after[0]):
        return 1000
    total = len(before) * len(before[0])
    changed = sum(
        before[y][x] != after[y][x]
        for y in range(len(before))
        for x in range(len(before[0]))
    )
    return round(1000 * changed / max(1, total))


def _component_delta(
    before: VisualScene,
    after: VisualScene,
) -> tuple[int, int, int]:
    before_positions = _component_positions(before.components)
    after_positions = _component_positions(after.components)
    before_counts = Counter(
        {
            descriptor: len(boxes)
            for descriptor, boxes in before_positions.items()
        }
    )
    after_counts = Counter(
        {
            descriptor: len(boxes)
            for descriptor, boxes in after_positions.items()
        }
    )
    removed = sum((before_counts - after_counts).values())
    added = sum((after_counts - before_counts).values())
    moved = 0
    for descriptor in before_counts.keys() & after_counts.keys():
        before_boxes = before_positions[descriptor]
        after_boxes = after_positions[descriptor]
        paired = min(len(before_boxes), len(after_boxes))
        moved += sum(
            before_boxes[index] != after_boxes[index]
            for index in range(paired)
        )
    return added, removed, moved


def _effect_classes(
    *,
    before_grid: Grid,
    after_grid: Grid,
    before_scene: VisualScene,
    after_scene: VisualScene,
    changed_cell_milli: int,
    component_added: int,
    component_removed: int,
    component_moved: int,
    terminal_state: str,
    progress_observed: bool,
) -> tuple[str, ...]:
    effects: set[str] = set()
    if before_scene.grid_digest == after_scene.grid_digest:
        effects.add("NO_VISIBLE_CHANGE")
    else:
        effects.add("VISIBLE_STATE_CHANGE")
        if changed_cell_milli <= 50:
            effects.add("LOCAL_PIXEL_DELTA")
        elif changed_cell_milli <= 250:
            effects.add("REGIONAL_REDRAW")
        else:
            effects.add("GLOBAL_REDRAW")
    if (
        len(before_grid) != len(after_grid)
        or (
            before_grid
            and after_grid
            and len(before_grid[0]) != len(after_grid[0])
        )
    ):
        effects.add("DIMENSION_CHANGE")
    if component_added:
        effects.add("COMPONENT_APPEAR")
    if component_removed:
        effects.add("COMPONENT_DISAPPEAR")
    if component_moved:
        effects.add("COMPONENT_MOTION")
    if before_scene.structural_digest != after_scene.structural_digest:
        effects.add("STRUCTURAL_CHANGE")
    if _action_surface(before_scene) != _action_surface(after_scene):
        effects.add("ACTION_SURFACE_CHANGE")
    if progress_observed:
        effects.add("PROGRESS_BOUNDARY")
    if terminal_state == "WIN":
        effects.add("WIN_TERMINAL")
    elif terminal_state == "GAME_OVER":
        effects.add("IRREVERSIBLE_HAZARD")
    return tuple(sorted(effects))


def _boundary_label(
    *,
    effects: Sequence[str],
    terminal_state: str,
    progress_observed: bool,
) -> BoundaryLabel:
    if terminal_state == "GAME_OVER":
        return "HAZARD"
    if progress_observed or terminal_state == "WIN":
        return "COMMIT"
    if "VISIBLE_STATE_CHANGE" in effects:
        return "TRANSITION_NO_COMMIT"
    return "NO_VISIBLE_COMMIT"


def _contrast_role(label: BoundaryLabel) -> ContrastRole:
    if label == "COMMIT":
        return "POSITIVE"
    if label == "HAZARD":
        return "HAZARD"
    return "NEGATIVE"


def _reobserve_obligation(
    label: BoundaryLabel,
) -> ReobserveObligation:
    if label == "COMMIT":
        return "REOBSERVE_COMMIT_STATE"
    if label == "HAZARD":
        return "SUSPEND_AND_REQUEST_ROLLBACK"
    if label == "TRANSITION_NO_COMMIT":
        return "REOBSERVE_BEFORE_CONTINUATION"
    return "WAIT_REOBSERVE_OR_REPLAN"


@dataclass(frozen=True, slots=True)
class VisibleTransitionEvidence:
    """One rendered pre/post contrast produced without task identity."""

    source: VisibleStateAbstraction
    target: VisibleStateAbstraction
    action_prototype: str
    action_class: str
    effect_classes: tuple[str, ...]
    changed_cell_milli: int
    component_added: int
    component_removed: int
    component_moved: int
    terminal_state: str
    progress_observed: bool
    boundary_label: BoundaryLabel

    @property
    def digest(self) -> str:
        return "visible-transition:" + digest_object(self.to_payload())[:24]

    def to_payload(self) -> dict[str, object]:
        payload = {
            "source": self.source.to_payload(),
            "target": self.target.to_payload(),
            "action_prototype": self.action_prototype,
            "action_class": self.action_class,
            "effect_classes": list(self.effect_classes),
            "changed_cell_milli": self.changed_cell_milli,
            "component_added": self.component_added,
            "component_removed": self.component_removed,
            "component_moved": self.component_moved,
            "terminal_state": self.terminal_state,
            "progress_observed": self.progress_observed,
            "boundary_label": self.boundary_label,
        }
        forbidden = forbidden_runtime_paths(payload)
        if forbidden:
            raise ValueError(
                "C2_C3_TRANSITION_IDENTITY_FORBIDDEN:"
                + ",".join(forbidden)
            )
        return payload


@dataclass(frozen=True, slots=True)
class TransitionContrastRecord:
    """Bounded row for independent cross-context development audit."""

    ordinal: int
    source_structure_class: str
    target_structure_class: str
    action_prototype: str
    action_class: str
    effect_classes: tuple[str, ...]
    changed_cell_milli: int
    component_added: int
    component_removed: int
    component_moved: int
    terminal_state: str
    progress_observed: bool
    observed_boundary: BoundaryLabel
    predicted_boundary: BoundaryLabel
    contrast_role: ContrastRole
    reobserve_obligation: ReobserveObligation
    transition_digest: str

    @classmethod
    def from_evidence(
        cls,
        evidence: VisibleTransitionEvidence,
        *,
        ordinal: int,
    ) -> TransitionContrastRecord:
        predicted = _boundary_label(
            effects=evidence.effect_classes,
            terminal_state=evidence.terminal_state,
            progress_observed=evidence.progress_observed,
        )
        return cls(
            ordinal=ordinal,
            source_structure_class=evidence.source.structure_class,
            target_structure_class=evidence.target.structure_class,
            action_prototype=evidence.action_prototype,
            action_class=evidence.action_class,
            effect_classes=evidence.effect_classes,
            changed_cell_milli=evidence.changed_cell_milli,
            component_added=evidence.component_added,
            component_removed=evidence.component_removed,
            component_moved=evidence.component_moved,
            terminal_state=evidence.terminal_state,
            progress_observed=evidence.progress_observed,
            observed_boundary=evidence.boundary_label,
            predicted_boundary=predicted,
            contrast_role=_contrast_role(evidence.boundary_label),
            reobserve_obligation=_reobserve_obligation(
                evidence.boundary_label
            ),
            transition_digest=evidence.digest,
        )

    def to_payload(self) -> dict[str, object]:
        payload = {
            "ordinal": self.ordinal,
            "source_structure_class": self.source_structure_class,
            "target_structure_class": self.target_structure_class,
            "action_prototype": self.action_prototype,
            "action_class": self.action_class,
            "effect_classes": list(self.effect_classes),
            "changed_cell_milli": self.changed_cell_milli,
            "component_added": self.component_added,
            "component_removed": self.component_removed,
            "component_moved": self.component_moved,
            "terminal_state": self.terminal_state,
            "progress_observed": self.progress_observed,
            "observed_boundary": self.observed_boundary,
            "predicted_boundary": self.predicted_boundary,
            "contrast_role": self.contrast_role,
            "reobserve_obligation": self.reobserve_obligation,
            "transition_digest": self.transition_digest,
        }
        forbidden = forbidden_runtime_paths(payload)
        if forbidden:
            raise ValueError(
                "C2_C3_CONTRAST_IDENTITY_FORBIDDEN:"
                + ",".join(forbidden)
            )
        return payload


def observe_visible_transition(
    *,
    before_grid: Grid,
    after_grid: Grid,
    before_scene: VisualScene,
    after_scene: VisualScene,
    action: VisualAction,
    terminal_state: str,
    progress_observed: bool,
) -> VisibleTransitionEvidence:
    """Compute C2 effect evidence and an explicit C3 boundary label."""

    if terminal_state not in {"NOT_FINISHED", "WIN", "GAME_OVER"}:
        raise ValueError("C2_C3_TERMINAL_STATE_INVALID")
    changed = _changed_cell_milli(before_grid, after_grid)
    added, removed, moved = _component_delta(before_scene, after_scene)
    effects = _effect_classes(
        before_grid=before_grid,
        after_grid=after_grid,
        before_scene=before_scene,
        after_scene=after_scene,
        changed_cell_milli=changed,
        component_added=added,
        component_removed=removed,
        component_moved=moved,
        terminal_state=terminal_state,
        progress_observed=progress_observed,
    )
    return VisibleTransitionEvidence(
        source=VisibleStateAbstraction.from_scene(before_scene),
        target=VisibleStateAbstraction.from_scene(after_scene),
        action_prototype=action.prototype_key,
        action_class=f"action:{action.action_id}",
        effect_classes=effects,
        changed_cell_milli=changed,
        component_added=added,
        component_removed=removed,
        component_moved=moved,
        terminal_state=terminal_state,
        progress_observed=progress_observed,
        boundary_label=_boundary_label(
            effects=effects,
            terminal_state=terminal_state,
            progress_observed=progress_observed,
        ),
    )


@dataclass(frozen=True, slots=True)
class CommitBoundaryPrediction:
    """Non-authoritative C output for later HDS evaluation."""

    status: PredictionStatus
    evidence_count: int
    context_support: int
    confidence_milli: int
    reason_codes: tuple[str, ...]
    action_selection_authorized: bool = False
    memory_write_authorized: bool = False
    runtime_p_promotion_authorized: bool = False

    def to_payload(self) -> dict[str, object]:
        return {
            "status": self.status,
            "evidence_count": self.evidence_count,
            "context_support": self.context_support,
            "confidence_milli": self.confidence_milli,
            "reason_codes": list(self.reason_codes),
            "action_selection_authorized": self.action_selection_authorized,
            "memory_write_authorized": self.memory_write_authorized,
            "runtime_p_promotion_authorized": (
                self.runtime_p_promotion_authorized
            ),
        }


def _model_key(structure_class: str, action_prototype: str) -> str:
    return (
        "transition-model:"
        + digest_object(
            {
                "structure_class": structure_class,
                "action_prototype": action_prototype,
            }
        )[:24]
    )


def _global_key(action_class: str) -> str:
    return "global-action-model:" + digest_object(action_class)[:24]


def _prediction(
    counts: Mapping[str, int],
    *,
    context_support: int,
) -> CommitBoundaryPrediction:
    total = sum(int(value) for value in counts.values())
    if total < 1:
        return CommitBoundaryPrediction(
            status="UNKNOWN",
            evidence_count=0,
            context_support=0,
            confidence_milli=0,
            reason_codes=("NO_MATCHING_TRANSITION_EVIDENCE",),
        )
    ordered = sorted(
        ((int(count), label) for label, count in counts.items()),
        key=lambda item: (-item[0], item[1]),
    )
    best_count, best_label = ordered[0]
    tied = sum(count == best_count for count, _label in ordered) > 1
    status_by_label: dict[str, PredictionStatus] = {
        "COMMIT": "COMMIT_LIKELY",
        "HAZARD": "HAZARD_LIKELY",
        "TRANSITION_NO_COMMIT": "TRANSITION_ONLY_LIKELY",
        "NO_VISIBLE_COMMIT": "NO_VISIBLE_COMMIT_LIKELY",
    }
    return CommitBoundaryPrediction(
        status="UNKNOWN" if tied else status_by_label[best_label],
        evidence_count=total,
        context_support=context_support,
        confidence_milli=(
            0 if tied else round(1000 * best_count / total)
        ),
        reason_codes=(
            ("BOUNDARY_LABEL_TIE",)
            if tied
            else (
                f"DOMINANT_{best_label}",
                (
                    "CROSS_CONTEXT_SUPPORT"
                    if context_support >= 2
                    else "LOCAL_CONTEXT_ONLY"
                ),
            )
        ),
    )


@dataclass(slots=True)
class C2C3CapabilityProbe:
    """Aggregate identity-free transition evidence without policy influence."""

    observation_count: int = 0
    fault_count: int = 0
    effect_counts: Counter[str] = field(default_factory=Counter)
    boundary_counts: Counter[str] = field(default_factory=Counter)
    fault_counts: Counter[str] = field(default_factory=Counter)
    exact_boundary_models: dict[str, Counter[str]] = field(
        default_factory=dict
    )
    global_boundary_models: dict[str, Counter[str]] = field(
        default_factory=dict
    )
    global_contexts: dict[str, set[str]] = field(default_factory=dict)
    contrast_records: list[TransitionContrastRecord] = field(
        default_factory=list
    )
    model_overflow_count: int = 0
    context_overflow_count: int = 0
    contrast_overflow_count: int = 0
    overflow_digest_chain: str = ""
    transition_digest_chain: str = ""
    last_evidence: VisibleTransitionEvidence | None = None

    def record_fault(self, reason: str) -> None:
        """Retain a shadow-observer fault without changing runtime control."""

        if not reason or not reason.replace("_", "").isalnum():
            raise ValueError("C2_C3_PROBE_FAULT_REASON_INVALID")
        self.fault_count += 1
        self.fault_counts[reason] += 1

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
    ) -> VisibleTransitionEvidence:
        evidence = observe_visible_transition(
            before_grid=before_grid,
            after_grid=after_grid,
            before_scene=before_scene,
            after_scene=after_scene,
            action=action,
            terminal_state=terminal_state,
            progress_observed=progress_observed,
        )
        exact_key = _model_key(
            evidence.source.structure_class,
            evidence.action_prototype,
        )
        global_key = _global_key(evidence.action_class)
        exact_counts = self.exact_boundary_models.get(exact_key)
        if exact_counts is None:
            if len(self.exact_boundary_models) < C2_C3_MODEL_LIMIT:
                exact_counts = Counter()
                self.exact_boundary_models[exact_key] = exact_counts
            else:
                self.model_overflow_count += 1
        if exact_counts is not None:
            exact_counts[evidence.boundary_label] += 1
        self.global_boundary_models.setdefault(
            global_key,
            Counter(),
        )[evidence.boundary_label] += 1
        contexts = self.global_contexts.setdefault(global_key, set())
        if evidence.source.structure_class in contexts:
            pass
        elif len(contexts) < C2_C3_CONTEXT_LIMIT_PER_ACTION:
            contexts.add(evidence.source.structure_class)
        else:
            self.context_overflow_count += 1
        self.effect_counts.update(evidence.effect_classes)
        self.boundary_counts[evidence.boundary_label] += 1
        self.observation_count += 1
        self.transition_digest_chain = digest_object(
            {
                "previous": self.transition_digest_chain,
                "current": evidence.digest,
                "ordinal": self.observation_count,
            }
        )
        if len(self.contrast_records) < C2_C3_CONTRAST_RECORD_LIMIT:
            self.contrast_records.append(
                TransitionContrastRecord.from_evidence(
                    evidence,
                    ordinal=self.observation_count,
                )
            )
        else:
            self.contrast_overflow_count += 1
        if (
            self.model_overflow_count
            or self.context_overflow_count
            or self.contrast_overflow_count
        ):
            self.overflow_digest_chain = digest_object(
                {
                    "previous": self.overflow_digest_chain,
                    "transition": evidence.digest,
                    "model_overflow_count": self.model_overflow_count,
                    "context_overflow_count": self.context_overflow_count,
                    "contrast_overflow_count": (
                        self.contrast_overflow_count
                    ),
                }
            )
        self.last_evidence = evidence
        return evidence

    def predict(
        self,
        state: VisibleStateAbstraction,
        action: VisualAction,
    ) -> CommitBoundaryPrediction:
        """Return evidence material only; never authorize selection or emit."""

        exact_key = _model_key(
            state.structure_class,
            action.prototype_key,
        )
        exact = self.exact_boundary_models.get(exact_key)
        if exact:
            return _prediction(exact, context_support=1)
        global_key = _global_key(
            f"action:{action.action_id}"
        )
        global_counts = self.global_boundary_models.get(global_key, Counter())
        return _prediction(
            global_counts,
            context_support=len(self.global_contexts.get(global_key, set())),
        )

    def to_payload(self) -> dict[str, object]:
        payload: dict[str, object] = {
            "format": C2_C3_PROBE_FORMAT,
            "capability_ids": list(C2_C3_CAPABILITY_IDS),
            "candidate_tier": "LOCAL_PROBE",
            "runtime_decision_use": "FORBIDDEN",
            "action_selection_influence": False,
            "memory_write_authority": False,
            "external_emit_authority": False,
            "runtime_p_promotion_authority": False,
            "retention_limits": {
                "exact_model_count": C2_C3_MODEL_LIMIT,
                "context_count_per_action": (
                    C2_C3_CONTEXT_LIMIT_PER_ACTION
                ),
                "contrast_record_count": C2_C3_CONTRAST_RECORD_LIMIT,
            },
            "observation_count": self.observation_count,
            "fault_count": self.fault_count,
            "fault_counts": dict(sorted(self.fault_counts.items())),
            "effect_counts": dict(sorted(self.effect_counts.items())),
            "boundary_counts": dict(sorted(self.boundary_counts.items())),
            "exact_boundary_models": {
                key: dict(sorted(counts.items()))
                for key, counts in sorted(
                    self.exact_boundary_models.items()
                )
            },
            "global_boundary_models": {
                key: dict(sorted(counts.items()))
                for key, counts in sorted(
                    self.global_boundary_models.items()
                )
            },
            "global_context_support": {
                key: len(contexts)
                for key, contexts in sorted(self.global_contexts.items())
            },
            "contrast_records": [
                record.to_payload() for record in self.contrast_records
            ],
            "model_overflow_count": self.model_overflow_count,
            "context_overflow_count": self.context_overflow_count,
            "contrast_overflow_count": self.contrast_overflow_count,
            "overflow_digest_chain": self.overflow_digest_chain,
            "transition_digest_chain": self.transition_digest_chain,
            "last_evidence": (
                None
                if self.last_evidence is None
                else self.last_evidence.to_payload()
            ),
        }
        forbidden = forbidden_runtime_paths(payload)
        if forbidden:
            raise ValueError(
                "C2_C3_PROBE_RUNTIME_IDENTITY_FORBIDDEN:"
                + ",".join(forbidden)
            )
        return payload


def visual_action_from_emission(
    *,
    candidate_id: str,
    step: Mapping[str, object],
    provenance: Sequence[str],
) -> VisualAction:
    """Project an HDS-selected emission into an identity-free action class."""

    raw_action_id = step.get("action_id")
    action_id = _integer(raw_action_id, "action_id")
    if not 1 <= action_id <= 7:
        raise ValueError("C2_C3_ACTION_ID_INVALID")
    x_value = step.get("x")
    y_value = step.get("y")
    x = (
        x_value
        if isinstance(x_value, int) and not isinstance(x_value, bool)
        else None
    )
    y = (
        y_value
        if isinstance(y_value, int) and not isinstance(y_value, bool)
        else None
    )
    raw_key = step.get("visual_action_key")
    key = (
        str(raw_key)
        if isinstance(raw_key, str) and raw_key
        else "emitted-action:"
        + digest_object(
            {
                "candidate": candidate_id,
                "action": action_id,
                "provenance": list(provenance),
            }
        )[:24]
    )
    evidence = tuple(str(item) for item in provenance)
    group = 0 if action_id <= 5 else 3
    return VisualAction(
        key=key,
        action_id=action_id,
        group=group,
        x=x,
        y=y,
        evidence=evidence,
    )


__all__ = [
    "BoundaryLabel",
    "C2_C3_CAPABILITY_IDS",
    "C2_C3_CONTRAST_RECORD_LIMIT",
    "C2_C3_CONTEXT_LIMIT_PER_ACTION",
    "C2_C3_LEGACY_PROBE_FORMATS",
    "C2_C3_MODEL_LIMIT",
    "C2_C3_PROBE_FORMAT",
    "C2C3CapabilityProbe",
    "CommitBoundaryPrediction",
    "ContrastRole",
    "PredictionStatus",
    "ReobserveObligation",
    "TransitionContrastRecord",
    "VisibleStateAbstraction",
    "VisibleTransitionEvidence",
    "observe_visible_transition",
    "visual_action_from_emission",
]
