"""HDS-authorized PBundle staging, promotion, rollback, and lineage."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Final

from .p_bundle import PBundle
from .p_evaluator import PBundleEvaluation
from .schema import digest_object

P_REGISTRY_VERSION: Final = "arc3-p-registry-v1"


@dataclass(frozen=True, slots=True)
class PPromotionAuthorization:
    authorization_id: str
    active_logical_digest: str
    candidate_logical_digest: str
    evaluation_digest: str
    _authority_token: object = field(
        repr=False,
        compare=False,
        metadata={"serialize": False},
    )


@dataclass(frozen=True, slots=True)
class PRollbackAuthorization:
    authorization_id: str
    active_logical_digest: str
    rollback_target_digest: str
    reason_digest: str
    _authority_token: object = field(
        repr=False,
        compare=False,
        metadata={"serialize": False},
    )


@dataclass(frozen=True, slots=True)
class PRejectionAuthorization:
    authorization_id: str
    active_logical_digest: str
    candidate_logical_digest: str
    evaluation_digest: str
    reason_digest: str
    _authority_token: object = field(
        repr=False,
        compare=False,
        metadata={"serialize": False},
    )


@dataclass(frozen=True, slots=True)
class PRegistryEvent:
    ordinal: int
    operation: str
    source_digest: str
    target_digest: str
    evidence_digest: str
    previous_event_digest: str
    event_digest: str


@dataclass(slots=True)
class PRegistryAuthority:
    _token: object = field(default_factory=object, repr=False)
    _consumed: set[str] = field(default_factory=set, repr=False)

    def authorize_promotion(
        self,
        *,
        active: PBundle,
        candidate: PBundle,
        evaluation: PBundleEvaluation,
    ) -> PPromotionAuthorization:
        if not evaluation.passed():
            raise PermissionError("P_REGISTRY_PROMOTION_GATES_FAILED")
        if (
            evaluation.baseline_logical_digest != active.logical_digest()
            or evaluation.candidate_logical_digest
            != candidate.logical_digest()
        ):
            raise PermissionError("P_REGISTRY_PROMOTION_BINDING_INVALID")
        return PPromotionAuthorization(
            authorization_id="p-promotion-authorization:"
            + digest_object(
                (
                    active.logical_digest(),
                    candidate.logical_digest(),
                    evaluation.digest(),
                )
            )[:32],
            active_logical_digest=active.logical_digest(),
            candidate_logical_digest=candidate.logical_digest(),
            evaluation_digest=evaluation.digest(),
            _authority_token=self._token,
        )

    def authorize_rollback(
        self,
        *,
        active: PBundle,
        rollback_target: PBundle,
        reason: str,
    ) -> PRollbackAuthorization:
        if not reason:
            raise ValueError("P_REGISTRY_ROLLBACK_REASON_REQUIRED")
        return PRollbackAuthorization(
            authorization_id="p-rollback-authorization:"
            + digest_object(
                (
                    active.logical_digest(),
                    rollback_target.logical_digest(),
                    reason,
                )
            )[:32],
            active_logical_digest=active.logical_digest(),
            rollback_target_digest=rollback_target.logical_digest(),
            reason_digest=digest_object(reason),
            _authority_token=self._token,
        )

    def authorize_rejection(
        self,
        *,
        active: PBundle,
        candidate: PBundle,
        evaluation: PBundleEvaluation,
        reason: str,
    ) -> PRejectionAuthorization:
        if not reason:
            raise ValueError("P_REGISTRY_REJECTION_REASON_REQUIRED")
        if evaluation.passed():
            raise PermissionError("P_REGISTRY_PASSING_CANDIDATE_REJECTION")
        if (
            evaluation.baseline_logical_digest != active.logical_digest()
            or evaluation.candidate_logical_digest
            != candidate.logical_digest()
        ):
            raise PermissionError("P_REGISTRY_REJECTION_BINDING_INVALID")
        return PRejectionAuthorization(
            authorization_id="p-rejection-authorization:"
            + digest_object(
                (
                    active.logical_digest(),
                    candidate.logical_digest(),
                    evaluation.digest(),
                    reason,
                )
            )[:32],
            active_logical_digest=active.logical_digest(),
            candidate_logical_digest=candidate.logical_digest(),
            evaluation_digest=evaluation.digest(),
            reason_digest=digest_object(reason),
            _authority_token=self._token,
        )

    def consume(self, authorization: object) -> None:
        token = getattr(authorization, "_authority_token", None)
        identifier = getattr(authorization, "authorization_id", None)
        if token is not self._token or not isinstance(identifier, str):
            raise PermissionError("P_REGISTRY_AUTHORIZATION_INVALID")
        if identifier in self._consumed:
            raise PermissionError("P_REGISTRY_AUTHORIZATION_REUSED")
        self._consumed.add(identifier)


@dataclass(slots=True)
class PRegistry:
    active: PBundle
    candidates: dict[str, PBundle] = field(default_factory=dict)
    previous_stable: list[PBundle] = field(default_factory=list)
    rejected: list[PBundle] = field(default_factory=list)
    lineage: list[PRegistryEvent] = field(default_factory=list)

    def __post_init__(self) -> None:
        failures = self.active.validate()
        if failures:
            raise ValueError(";".join(failures))
        if self.active.manifest.lifecycle != "ACTIVE":
            raise ValueError("P_REGISTRY_ACTIVE_BUNDLE_REQUIRED")

    def _append_event(
        self,
        *,
        operation: str,
        source: str,
        target: str,
        evidence: str,
    ) -> None:
        previous = (
            self.lineage[-1].event_digest
            if self.lineage
            else "p-registry-genesis"
        )
        ordinal = len(self.lineage)
        event_digest = "p-registry-event:" + digest_object(
            {
                "ordinal": ordinal,
                "operation": operation,
                "source": source,
                "target": target,
                "evidence": evidence,
                "previous": previous,
            }
        )
        self.lineage.append(
            PRegistryEvent(
                ordinal=ordinal,
                operation=operation,
                source_digest=source,
                target_digest=target,
                evidence_digest=evidence,
                previous_event_digest=previous,
                event_digest=event_digest,
            )
        )

    def stage_candidate(self, candidate: PBundle) -> None:
        failures = candidate.validate()
        if failures:
            raise ValueError(";".join(failures))
        if candidate.manifest.lifecycle != "CANDIDATE":
            raise ValueError("P_REGISTRY_CANDIDATE_LIFECYCLE_REQUIRED")
        if (
            candidate.manifest.parent_logical_digest
            != self.active.logical_digest()
        ):
            raise PermissionError("P_REGISTRY_CANDIDATE_PARENT_INVALID")
        digest = candidate.logical_digest()
        existing = self.candidates.get(digest)
        if existing is not None and existing != candidate:
            raise RuntimeError("P_REGISTRY_CANDIDATE_DIGEST_COLLISION")
        self.candidates[digest] = candidate
        self._append_event(
            operation="STAGE",
            source=self.active.logical_digest(),
            target=digest,
            evidence=candidate.manifest.evidence_selection_digest,
        )

    def promote(
        self,
        *,
        candidate_digest: str,
        evaluation: PBundleEvaluation,
        authorization: PPromotionAuthorization,
        authority: PRegistryAuthority,
    ) -> PBundle:
        candidate = self.candidates.get(candidate_digest)
        if candidate is None:
            raise KeyError("P_REGISTRY_CANDIDATE_UNKNOWN")
        if (
            authorization.active_logical_digest
            != self.active.logical_digest()
            or authorization.candidate_logical_digest != candidate_digest
            or authorization.evaluation_digest != evaluation.digest()
        ):
            raise PermissionError("P_REGISTRY_PROMOTION_BINDING_INVALID")
        authority.consume(authorization)
        previous = replace(
            self.active,
            manifest=replace(
                self.active.manifest,
                lifecycle="PREVIOUS_STABLE",
            ),
        )
        promoted = replace(
            candidate,
            manifest=replace(candidate.manifest, lifecycle="ACTIVE"),
            evaluation_report=(
                ("dataset_role", evaluation.dataset_role),
                ("evaluation_digest", evaluation.digest()),
                ("result", "PASS"),
            ),
            promotion_report=(
                ("authorization_id", authorization.authorization_id),
                ("decision", "PROMOTE"),
            ),
        )
        self.previous_stable.append(previous)
        del self.candidates[candidate_digest]
        source = self.active.logical_digest()
        self.active = promoted
        self._append_event(
            operation="PROMOTE",
            source=source,
            target=promoted.logical_digest(),
            evidence=evaluation.digest(),
        )
        return promoted

    def rollback(
        self,
        *,
        authorization: PRollbackAuthorization,
        authority: PRegistryAuthority,
    ) -> PBundle:
        target = next(
            (
                item
                for item in reversed(self.previous_stable)
                if item.logical_digest()
                == authorization.rollback_target_digest
            ),
            None,
        )
        if target is None:
            raise KeyError("P_REGISTRY_ROLLBACK_TARGET_UNKNOWN")
        if (
            authorization.active_logical_digest
            != self.active.logical_digest()
        ):
            raise PermissionError("P_REGISTRY_ROLLBACK_BINDING_INVALID")
        authority.consume(authorization)
        source = self.active
        self.rejected.append(
            replace(
                source,
                manifest=replace(source.manifest, lifecycle="REJECTED"),
                promotion_report=(
                    (
                        "authorization_id",
                        authorization.authorization_id,
                    ),
                    ("decision", "ROLLBACK"),
                    ("reason_digest", authorization.reason_digest),
                ),
            )
        )
        self.active = replace(
            target,
            manifest=replace(target.manifest, lifecycle="ACTIVE"),
        )
        self.previous_stable = [
            item
            for item in self.previous_stable
            if item.logical_digest() != target.logical_digest()
        ]
        self._append_event(
            operation="ROLLBACK",
            source=source.logical_digest(),
            target=self.active.logical_digest(),
            evidence=authorization.reason_digest,
        )
        return self.active

    def reject_candidate(
        self,
        *,
        candidate_digest: str,
        evaluation: PBundleEvaluation,
        authorization: PRejectionAuthorization,
        authority: PRegistryAuthority,
    ) -> PBundle:
        candidate = self.candidates.get(candidate_digest)
        if candidate is None:
            raise KeyError("P_REGISTRY_CANDIDATE_UNKNOWN")
        if (
            authorization.active_logical_digest
            != self.active.logical_digest()
            or authorization.candidate_logical_digest != candidate_digest
            or authorization.evaluation_digest != evaluation.digest()
        ):
            raise PermissionError("P_REGISTRY_REJECTION_BINDING_INVALID")
        authority.consume(authorization)
        rejected = replace(
            candidate,
            manifest=replace(candidate.manifest, lifecycle="REJECTED"),
            evaluation_report=(
                ("dataset_role", evaluation.dataset_role),
                ("evaluation_digest", evaluation.digest()),
                ("result", "FAIL"),
            ),
            promotion_report=(
                ("authorization_id", authorization.authorization_id),
                ("decision", "REJECT"),
                ("reason_digest", authorization.reason_digest),
            ),
        )
        del self.candidates[candidate_digest]
        self.rejected.append(rejected)
        self._append_event(
            operation="REJECT",
            source=self.active.logical_digest(),
            target=rejected.logical_digest(),
            evidence=evaluation.digest(),
        )
        return rejected

    def digest(self) -> str:
        return "p-registry:" + digest_object(
            {
                "version": P_REGISTRY_VERSION,
                "active": self.active.logical_digest(),
                "candidates": tuple(sorted(self.candidates)),
                "previous": tuple(
                    item.logical_digest() for item in self.previous_stable
                ),
                "rejected": tuple(
                    item.logical_digest() for item in self.rejected
                ),
                "lineage": tuple(self.lineage),
            }
        )


__all__ = [
    "P_REGISTRY_VERSION",
    "PPromotionAuthorization",
    "PRejectionAuthorization",
    "PRollbackAuthorization",
    "PRegistry",
    "PRegistryAuthority",
    "PRegistryEvent",
]
