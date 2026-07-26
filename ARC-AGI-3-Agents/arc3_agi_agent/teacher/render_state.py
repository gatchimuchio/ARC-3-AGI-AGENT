"""Shared deterministic rendered-frame normalization for Teacher stages."""

from __future__ import annotations

from arcengine import FrameDataRaw

from ..schema import digest_object


def rendered_frame_digest(frame: FrameDataRaw) -> str:
    """Hash only the final rendered frame, excluding transient animation."""

    frames = list(frame.frame)
    if not frames:
        normalized: object = []
    else:
        final_frame = frames[-1]
        normalized = (
            final_frame.tolist()
            if hasattr(final_frame, "tolist")
            else final_frame
        )
    return "sha256:" + digest_object(normalized)


__all__ = ["rendered_frame_digest"]
