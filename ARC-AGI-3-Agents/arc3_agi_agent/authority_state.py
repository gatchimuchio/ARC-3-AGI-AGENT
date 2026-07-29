"""Process-local capability state for one cognitive session.

The live token and capability registry are deliberately non-serializable.
Persisted traces may retain capability identifiers, but never enough material
to make an old authorization live again.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .schema import digest_object

AUTHORITY_STATE_VERSION = "arc3-authority-state-v1"


@dataclass(frozen=True, slots=True)
class IssuedCapability:
    capability_id: str
    kind: str
    binding_digest: str


@dataclass(slots=True)
class AuthorityState:
    """Own all issued/consumed capabilities for one process-local session."""

    session_id: str
    _live_token: object = field(
        default_factory=object,
        init=False,
        repr=False,
        metadata={"serialize": False},
    )
    _issue_sequence: int = field(
        default=0,
        init=False,
        repr=False,
        metadata={"serialize": False},
    )
    _issued: dict[str, IssuedCapability] = field(
        default_factory=dict,
        init=False,
        repr=False,
        metadata={"serialize": False},
    )
    _consumed: set[str] = field(
        default_factory=set,
        init=False,
        repr=False,
        metadata={"serialize": False},
    )
    _decisions: dict[str, object] = field(
        default_factory=dict,
        init=False,
        repr=False,
        metadata={"serialize": False},
    )

    def __post_init__(self) -> None:
        if not isinstance(self.session_id, str) or not self.session_id:
            raise ValueError("AUTHORITY_SESSION_ID_REQUIRED")

    @property
    def live_token(self) -> object:
        """Return the live in-process token without making it serializable."""

        return self._live_token

    @property
    def issued_count(self) -> int:
        return len(self._issued)

    @property
    def consumed_count(self) -> int:
        return len(self._consumed)

    def require_live_token(self, token: object, *, error: str) -> None:
        if token is not self._live_token:
            raise PermissionError(error)

    def issue(self, kind: str, binding_digest: str) -> str:
        """Issue a unique capability bound to an already validated operation."""

        if not isinstance(kind, str) or not kind:
            raise ValueError("AUTHORITY_CAPABILITY_KIND_REQUIRED")
        if not isinstance(binding_digest, str) or not binding_digest:
            raise ValueError("AUTHORITY_CAPABILITY_BINDING_REQUIRED")
        self._issue_sequence += 1
        capability_id = (
            kind.casefold().replace("_", "-")
            + ":"
            + digest_object(
                {
                    "session_id": self.session_id,
                    "sequence": self._issue_sequence,
                    "kind": kind,
                    "binding_digest": binding_digest,
                }
            )[:24]
        )
        if capability_id in self._issued:
            raise RuntimeError("AUTHORITY_CAPABILITY_COLLISION")
        self._issued[capability_id] = IssuedCapability(
            capability_id=capability_id,
            kind=kind,
            binding_digest=binding_digest,
        )
        return capability_id

    def require_available(
        self,
        capability_id: str,
        *,
        kind: str,
        binding_digest: str | None = None,
        unknown_error: str = "AUTHORITY_CAPABILITY_NOT_ISSUED",
        reused_error: str = "AUTHORITY_CAPABILITY_REUSED",
        binding_error: str = "AUTHORITY_CAPABILITY_BINDING_INVALID",
    ) -> None:
        issued = self._issued.get(capability_id)
        if issued is None or issued.kind != kind:
            raise PermissionError(unknown_error)
        if capability_id in self._consumed:
            raise PermissionError(reused_error)
        if (
            binding_digest is not None
            and issued.binding_digest != binding_digest
        ):
            raise PermissionError(binding_error)

    def consume(
        self,
        capability_id: str,
        *,
        kind: str,
        binding_digest: str | None = None,
        unknown_error: str = "AUTHORITY_CAPABILITY_NOT_ISSUED",
        reused_error: str = "AUTHORITY_CAPABILITY_REUSED",
        binding_error: str = "AUTHORITY_CAPABILITY_BINDING_INVALID",
    ) -> None:
        self.require_available(
            capability_id,
            kind=kind,
            binding_digest=binding_digest,
            unknown_error=unknown_error,
            reused_error=reused_error,
            binding_error=binding_error,
        )
        self._consumed.add(capability_id)

    def register_decision(self, decision_id: str, decision: object) -> None:
        if not isinstance(decision_id, str) or not decision_id:
            raise ValueError("AUTHORITY_DECISION_ID_REQUIRED")
        if decision_id in self._decisions:
            raise PermissionError("AUTHORITY_DECISION_DUPLICATE")
        self._decisions[decision_id] = decision

    def require_decision(
        self,
        decision_id: str,
        decision: object,
        *,
        error: str,
    ) -> None:
        if self._decisions.get(decision_id) != decision:
            raise PermissionError(error)


__all__ = [
    "AUTHORITY_STATE_VERSION",
    "AuthorityState",
    "IssuedCapability",
]
