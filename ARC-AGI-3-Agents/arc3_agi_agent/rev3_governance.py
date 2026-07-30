"""Fail-closed governance boundary for the rev3 distillation-first strategy.

PH-R00 defined the only source class that a future rev3 production runtime
may accept and rejected all historical S5/P22 capability paths as parents,
active policies, or fallbacks. PH-D00A froze dependencies and authority.
PH-D00B bootstrapped the isolated distillation scope. PH-D01A inventoried
source dialect, split, answer visibility, use, and contamination. PH-D01B
freezes content, acquisition, environment, and run manifests only; none of
these phases constructs or activates an AGI runtime.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Final

REV3_STRATEGY_ID: Final = (
    "ARC3_HDS_DISTILLATION_FIRST_AUTONOMOUS_COMPLETION_SPEC_REV3"
)
REV3_ACTIVE_PHASE: Final = "PH-D01B"
REV3_PHASE_ORDER: Final = (
    "PH-R00",
    "PH-D00A",
    "PH-D00B",
    "PH-D01A",
    "PH-D01B",
    "PH-D02A",
    "PH-D02B",
    "PH-D02C",
    "PH-D03A",
    "PH-D03B",
    "PH-D05",
    "PH-D06",
    "PH-D07A",
    "PH-D07B",
    "PH-D08",
    "PH-D09",
    "PH-D10",
    "PH-D11",
    "PH-D12",
    "PH-D13",
    "PH-D14",
    "PH-B00",
    "PH-B01",
    "PH-B02",
    "PH-B03",
    "PH-B04",
    "PH-B05",
    "PH-B06",
    "PH-A00",
    "PH-A01",
    "PH-A02",
    "PH-A03",
    "PH-A04",
    "PH-A05",
    "PH-A06",
    "PH-A07",
    "PH-A08",
    "PH-E00",
    "PH-E01",
    "PH-E02",
    "PH-E03",
    "PH-E04",
)

DISTILLED_RUNTIME_SOURCE_KIND: Final = "DISTILLED_INITIAL_STATE_BUNDLE"
QUARANTINED_RUNTIME_SOURCE_KINDS: Final = frozenset(
    {
        "S5_RUNTIME",
        "S5_COMPILED_POLICY",
        "HISTORICAL_KNOWN_SAMPLE_STUDENT",
        "P22_COMPILED_POLICY",
        "P22_CV_ARTIFACT",
        "REV1_GENERIC_RUNTIME",
        "TEACHER_TRAJECTORY",
    }
)
FORBIDDEN_PRODUCTION_IMPORT_ROOTS: Final = frozenset(
    {
        "compiled_policy",
        "p22_evaluator",
        "s5_authority",
        "s5_compute",
        "s5_policy",
        "s5_runner",
        "s5_runtime",
        "s5_score_adapter",
        "teacher",
    }
)


def _bound_digest(value: str, field_name: str) -> str | None:
    if not value or ":" not in value:
        return field_name + "_MISSING_OR_UNBOUND"
    namespace, digest = value.split(":", 1)
    if not namespace or len(digest) != 64:
        return field_name + "_MISSING_OR_UNBOUND"
    try:
        int(digest, 16)
    except ValueError:
        return field_name + "_MISSING_OR_UNBOUND"
    return None


@dataclass(frozen=True, slots=True)
class Rev3ProductionSelection:
    """Content-bound future production selection.

    Creating this value does not grant approval.  The caller must supply an
    Owner approval digest that is already part of the approved bundle.
    """

    source_kind: str
    structure_bundle_digest: str
    initial_state_bundle_digest: str
    owner_approval_digest: str
    runtime_artifact_digest: str
    fallback_source_kinds: tuple[str, ...] = ()

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if self.source_kind in QUARANTINED_RUNTIME_SOURCE_KINDS:
            failures.append("REV3_QUARANTINED_SOURCE_SELECTED")
        if self.source_kind != DISTILLED_RUNTIME_SOURCE_KIND:
            failures.append("REV3_DISTILLED_SOURCE_REQUIRED")
        for field_name, value in (
            ("STRUCTURE_BUNDLE_DIGEST", self.structure_bundle_digest),
            (
                "INITIAL_STATE_BUNDLE_DIGEST",
                self.initial_state_bundle_digest,
            ),
            ("OWNER_APPROVAL_DIGEST", self.owner_approval_digest),
            ("RUNTIME_ARTIFACT_DIGEST", self.runtime_artifact_digest),
        ):
            failure = _bound_digest(value, field_name)
            if failure is not None:
                failures.append(failure)
        if self.fallback_source_kinds:
            failures.append("REV3_PRODUCTION_FALLBACK_FORBIDDEN")
        return tuple(sorted(set(failures)))


def require_rev3_production_selection(
    selection: Rev3ProductionSelection,
) -> Rev3ProductionSelection:
    """Reject every non-distilled or fallback-bearing production selection."""

    failures = selection.validate()
    if failures:
        raise PermissionError(
            "REV3_PRODUCTION_SELECTION_REJECTED:" + ",".join(failures)
        )
    return selection


def audit_rev3_production_imports(
    imported_roots: tuple[str, ...],
) -> tuple[str, ...]:
    """Return deterministic findings for forbidden historical imports."""

    normalized = {
        item.strip().lstrip(".").split(".", 1)[0]
        for item in imported_roots
        if item.strip()
    }
    return tuple(
        "REV3_FORBIDDEN_PRODUCTION_IMPORT:" + item
        for item in sorted(normalized & FORBIDDEN_PRODUCTION_IMPORT_ROOTS)
    )


__all__ = [
    "DISTILLED_RUNTIME_SOURCE_KIND",
    "FORBIDDEN_PRODUCTION_IMPORT_ROOTS",
    "QUARANTINED_RUNTIME_SOURCE_KINDS",
    "REV3_ACTIVE_PHASE",
    "REV3_PHASE_ORDER",
    "REV3_STRATEGY_ID",
    "Rev3ProductionSelection",
    "audit_rev3_production_imports",
    "require_rev3_production_selection",
]
