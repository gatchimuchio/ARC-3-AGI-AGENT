"""Append-only raw experience ledger for one cognitive-session lineage."""

from __future__ import annotations

import threading
from dataclasses import dataclass, field
from typing import Mapping

from .schema import digest_object

EXPERIENCE_LEDGER_VERSION = "arc3-experience-ledger-v1"


@dataclass(frozen=True, slots=True)
class ExperienceEvent:
    ordinal: int
    event_type: str
    payload_digest: str
    previous_event_digest: str
    event_digest: str


@dataclass(slots=True)
class EventSourcedExperienceLedger:
    """Retain raw evidence ordering without granting decision authority."""

    _events: list[ExperienceEvent] = field(
        default_factory=list,
        init=False,
        repr=False,
    )
    _lock: threading.RLock = field(
        default_factory=threading.RLock,
        init=False,
        repr=False,
    )

    def append(
        self,
        event_type: str,
        payload: Mapping[str, object],
    ) -> str:
        if not isinstance(event_type, str) or not event_type:
            raise ValueError("EXPERIENCE_LEDGER_EVENT_TYPE_REQUIRED")
        payload_digest = "experience-payload:" + digest_object(payload)
        with self._lock:
            previous = (
                self._events[-1].event_digest if self._events else ""
            )
            ordinal = len(self._events)
            event_digest = "experience-event:" + digest_object(
                {
                    "ordinal": ordinal,
                    "event_type": event_type,
                    "payload_digest": payload_digest,
                    "previous_event_digest": previous,
                }
            )
            self._events.append(
                ExperienceEvent(
                    ordinal=ordinal,
                    event_type=event_type,
                    payload_digest=payload_digest,
                    previous_event_digest=previous,
                    event_digest=event_digest,
                )
            )
            return event_digest

    def events(self) -> tuple[ExperienceEvent, ...]:
        with self._lock:
            return tuple(self._events)

    def digest(self) -> str:
        with self._lock:
            return "experience-ledger:" + digest_object(
                tuple(self._events)
            )


__all__ = [
    "EXPERIENCE_LEDGER_VERSION",
    "EventSourcedExperienceLedger",
    "ExperienceEvent",
]
