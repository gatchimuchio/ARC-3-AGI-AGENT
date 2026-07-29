"""Runtime taint labels for coordinates and non-semantic control values."""

from __future__ import annotations

from collections.abc import Mapping, Sequence

COORDINATE_PROVENANCE_NONE = "NONE"
COORDINATE_PROVENANCE_CURRENT_RENDER = "CURRENT_RENDER_DERIVED"
COORDINATE_PROVENANCE_PRECOMPUTED = "PRECOMPUTED"
COORDINATE_PROVENANCE_TRAJECTORY = "TRAJECTORY_DERIVED"
COORDINATE_PROVENANCE_ORCHESTRATION = "ORCHESTRATION_DERIVED"
COORDINATE_PROVENANCE_VALUES = frozenset(
    {
        COORDINATE_PROVENANCE_NONE,
        COORDINATE_PROVENANCE_CURRENT_RENDER,
        COORDINATE_PROVENANCE_PRECOMPUTED,
        COORDINATE_PROVENANCE_TRAJECTORY,
        COORDINATE_PROVENANCE_ORCHESTRATION,
    }
)


def validate_coordinate_provenance(
    *,
    payload_items: Sequence[tuple[str, int]],
    coordinate_provenance: str,
    coordinate_observation_digest: str,
    current_observation_digest: str,
    rendered_layers: Sequence[Sequence[Sequence[int]]],
) -> tuple[str, ...]:
    failures: list[str] = []
    if coordinate_provenance not in COORDINATE_PROVENANCE_VALUES:
        failures.append("COORDINATE_PROVENANCE_INVALID")
    payload: Mapping[str, int] = dict(payload_items)
    has_coordinate = "x" in payload or "y" in payload
    if not has_coordinate:
        if (
            coordinate_provenance != COORDINATE_PROVENANCE_NONE
            or coordinate_observation_digest
        ):
            failures.append("COORDINATE_PROVENANCE_WITHOUT_COORDINATE")
        return tuple(sorted(set(failures)))
    if set(("x", "y")).difference(payload):
        failures.append("COORDINATE_PAIR_INCOMPLETE")
    if coordinate_provenance != COORDINATE_PROVENANCE_CURRENT_RENDER:
        failures.append("PRECOMPUTED_COORDINATE_REJECTED")
    if coordinate_observation_digest != current_observation_digest:
        failures.append("COORDINATE_OBSERVATION_BINDING_INVALID")
    if rendered_layers:
        layer = rendered_layers[-1]
        height = len(layer)
        width = len(layer[0]) if layer else 0
        x = payload.get("x", -1)
        y = payload.get("y", -1)
        if not (0 <= x < width and 0 <= y < height):
            failures.append("DYNAMIC_COORDINATE_OUTSIDE_CURRENT_RENDER")
    else:
        failures.append("DYNAMIC_COORDINATE_RENDER_REQUIRED")
    return tuple(sorted(set(failures)))


__all__ = [
    "COORDINATE_PROVENANCE_CURRENT_RENDER",
    "COORDINATE_PROVENANCE_NONE",
    "COORDINATE_PROVENANCE_ORCHESTRATION",
    "COORDINATE_PROVENANCE_PRECOMPUTED",
    "COORDINATE_PROVENANCE_TRAJECTORY",
    "COORDINATE_PROVENANCE_VALUES",
    "validate_coordinate_provenance",
]
