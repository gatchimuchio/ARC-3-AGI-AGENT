"""Append-only, content-bound dataset access decision ledger."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Final

from .schema import digest_object

DATA_ACCESS_LEDGER_VERSION: Final = "arc3-data-access-ledger-v1"


def _event_digest(
    *,
    ordinal: int,
    dataset_id: str,
    dataset_role: str,
    purpose: str,
    actor_scope: str,
    runtime_identity_digest: str,
    artifact_digest: str,
    access_granted: bool,
    policy_violation: bool,
    decision_reason: str,
    previous_event_digest: str,
) -> str:
    return "data-access-event:" + digest_object(
        {
            "version": DATA_ACCESS_LEDGER_VERSION,
            "ordinal": ordinal,
            "dataset_id": dataset_id,
            "dataset_role": dataset_role,
            "purpose": purpose,
            "actor_scope": actor_scope,
            "runtime_identity_digest": runtime_identity_digest,
            "artifact_digest": artifact_digest,
            "access_granted": access_granted,
            "policy_violation": policy_violation,
            "decision_reason": decision_reason,
            "previous_event_digest": previous_event_digest,
        }
    )


@dataclass(frozen=True, slots=True)
class DataAccessEvent:
    ordinal: int
    dataset_id: str
    dataset_role: str
    purpose: str
    actor_scope: str
    runtime_identity_digest: str
    artifact_digest: str
    access_granted: bool
    policy_violation: bool
    decision_reason: str
    previous_event_digest: str
    event_digest: str


@dataclass(slots=True)
class DataAccessLedger:
    _events: list[DataAccessEvent] = field(default_factory=list, repr=False)

    @property
    def events(self) -> tuple[DataAccessEvent, ...]:
        return tuple(self._events)

    @property
    def denied_request_count(self) -> int:
        return sum(not item.access_granted for item in self._events)

    @property
    def data_access_violation_count(self) -> int:
        return sum(item.policy_violation for item in self._events)

    @property
    def locked_final_access_count(self) -> int:
        return sum(
            item.access_granted and item.dataset_role == "LOCKED_FINAL"
            for item in self._events
        )

    def record_decision(
        self,
        *,
        dataset_id: str,
        dataset_role: str,
        purpose: str,
        actor_scope: str,
        runtime_identity_digest: str,
        artifact_digest: str,
        access_granted: bool,
        decision_reason: str,
        policy_violation: bool = False,
    ) -> DataAccessEvent:
        values = (
            dataset_id,
            dataset_role,
            purpose,
            actor_scope,
            runtime_identity_digest,
            artifact_digest,
            decision_reason,
        )
        if any(not isinstance(item, str) or not item for item in values):
            raise ValueError("DATA_ACCESS_EVENT_METADATA_MISSING")
        if not isinstance(access_granted, bool) or not isinstance(
            policy_violation, bool
        ):
            raise TypeError("DATA_ACCESS_EVENT_BOOLEAN_INVALID")
        if access_granted and policy_violation:
            raise PermissionError("DATA_ACCESS_POLICY_VIOLATION_REFUSED")
        ordinal = len(self._events)
        previous = (
            self._events[-1].event_digest
            if self._events
            else "data-access-genesis"
        )
        event = DataAccessEvent(
            ordinal=ordinal,
            dataset_id=dataset_id,
            dataset_role=dataset_role,
            purpose=purpose,
            actor_scope=actor_scope,
            runtime_identity_digest=runtime_identity_digest,
            artifact_digest=artifact_digest,
            access_granted=access_granted,
            policy_violation=policy_violation,
            decision_reason=decision_reason,
            previous_event_digest=previous,
            event_digest=_event_digest(
                ordinal=ordinal,
                dataset_id=dataset_id,
                dataset_role=dataset_role,
                purpose=purpose,
                actor_scope=actor_scope,
                runtime_identity_digest=runtime_identity_digest,
                artifact_digest=artifact_digest,
                access_granted=access_granted,
                policy_violation=policy_violation,
                decision_reason=decision_reason,
                previous_event_digest=previous,
            ),
        )
        self._events.append(event)
        return event

    def validate_chain(self) -> tuple[str, ...]:
        failures: list[str] = []
        previous = "data-access-genesis"
        for ordinal, event in enumerate(self._events):
            if event.ordinal != ordinal:
                failures.append("DATA_ACCESS_ORDINAL_INVALID")
            if event.previous_event_digest != previous:
                failures.append("DATA_ACCESS_PREVIOUS_DIGEST_INVALID")
            expected = _event_digest(
                ordinal=event.ordinal,
                dataset_id=event.dataset_id,
                dataset_role=event.dataset_role,
                purpose=event.purpose,
                actor_scope=event.actor_scope,
                runtime_identity_digest=event.runtime_identity_digest,
                artifact_digest=event.artifact_digest,
                access_granted=event.access_granted,
                policy_violation=event.policy_violation,
                decision_reason=event.decision_reason,
                previous_event_digest=event.previous_event_digest,
            )
            if event.event_digest != expected:
                failures.append("DATA_ACCESS_EVENT_DIGEST_INVALID")
            previous = event.event_digest
        return tuple(sorted(set(failures)))

    def digest(self) -> str:
        failures = self.validate_chain()
        if failures:
            raise RuntimeError(";".join(failures))
        return "data-access-ledger:" + digest_object(
            {
                "version": DATA_ACCESS_LEDGER_VERSION,
                "events": self.events,
            }
        )


__all__ = [
    "DATA_ACCESS_LEDGER_VERSION",
    "DataAccessEvent",
    "DataAccessLedger",
]
