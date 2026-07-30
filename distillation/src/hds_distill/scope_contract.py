"""Trusted static markers for the PH-D00B distillation boundary.

The Scope Guard trusts these markers only when import provenance resolves to
this module. A marker is descriptive, not an authorization token: the guard
still verifies callable inputs and every other forbidden behavior.
"""

from __future__ import annotations

from collections.abc import Callable

_MARKER_ATTRIBUTE = "__hds_distill_scope_contracts__"


def _mark[CallableT: Callable[..., object]](
    function: CallableT,
    marker: str,
) -> CallableT:
    existing = getattr(function, _MARKER_ATTRIBUTE, ())
    markers = tuple(sorted({*(str(item) for item in existing), marker}))
    setattr(function, _MARKER_ATTRIBUTE, markers)
    return function


def teacher_bound[CallableT: Callable[..., object]](
    function: CallableT,
) -> CallableT:
    """Mark a callable that requires explicit labeled teacher evidence."""

    return _mark(function, "teacher_bound")


def offline_interpreter[CallableT: Callable[..., object]](
    function: CallableT,
) -> CallableT:
    """Mark a deterministic local program/model interpreter."""

    return _mark(function, "offline_interpreter")


__all__ = ["offline_interpreter", "teacher_bound"]
