"""Dataset role governance and cross-validation artifact separation."""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from typing import Final

from .data_access_ledger import DataAccessLedger
from .runtime_identity import RuntimeIdentity
from .schema import digest_object

EVALUATION_REGISTRY_VERSION: Final = "arc3-evaluation-registry-v1"
DATASET_ROLES: Final = frozenset(
    {
        "DEVELOPMENT_TRAIN",
        "DEVELOPMENT_VALIDATION",
        "CV_HOLDOUT",
        "LOCKED_FINAL",
        "OFFICIAL_PUBLIC",
        "OFFICIAL_PRIVATE",
    }
)
DEVELOPMENT_TRAIN_PURPOSES: Final = frozenset(
    {
        "TRAIN_RUN",
        "M_DEV_UPDATE",
        "FAILURE_CLUSTER",
        "CANDIDATE_COMPILE",
    }
)
DEVELOPMENT_VALIDATION_PURPOSES: Final = frozenset(
    {
        "CANDIDATE_EVALUATION",
        "PROMOTION_DECISION",
        "KNOWN_REGRESSION",
    }
)


@dataclass(frozen=True, slots=True)
class DatasetRegistration:
    dataset_id: str
    dataset_digest: str
    owner: str
    role: str
    access_state: str
    first_access_event_digest: str = ""
    execution_count: int = 0
    consumed: bool = False

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not self.dataset_id or not self.dataset_digest or not self.owner:
            failures.append("EVALUATION_DATASET_METADATA_MISSING")
        if self.role not in DATASET_ROLES:
            failures.append("EVALUATION_DATASET_ROLE_INVALID")
        if not self.access_state:
            failures.append("EVALUATION_ACCESS_STATE_MISSING")
        if (
            isinstance(self.execution_count, bool)
            or not isinstance(self.execution_count, int)
            or self.execution_count < 0
        ):
            failures.append("EVALUATION_EXECUTION_COUNT_INVALID")
        return tuple(sorted(set(failures)))


@dataclass(frozen=True, slots=True)
class EvaluationAccessGrant:
    dataset_id: str
    dataset_digest: str
    role: str
    purpose: str
    actor_scope: str
    runtime_identity_digest: str
    artifact_digest: str
    access_event_digest: str
    _registry_token: object = field(
        repr=False,
        compare=False,
        metadata={"serialize": False},
    )


@dataclass(frozen=True, slots=True)
class CVFoldArtifact:
    fold_id: str
    dataset_id: str
    p_logical_digest: str
    initial_state_logical_digest: str
    runtime_identity_digest: str
    access_event_digest: str
    artifact_digest: str
    allowed_claim: str = "CV_PROCEDURE_EVIDENCE"


@dataclass(frozen=True, slots=True)
class CVProcedureSummary:
    fold_count: int
    distinct_p_artifact_count: int
    distinct_runtime_identity_count: int
    allowed_claim: str
    same_single_artifact_claim_allowed: bool


@dataclass(slots=True)
class EvaluationRegistry:
    ledger: DataAccessLedger = field(default_factory=DataAccessLedger)
    _token: object = field(default_factory=object, repr=False)
    _datasets: dict[str, DatasetRegistration] = field(
        default_factory=dict,
        repr=False,
    )
    _cv_artifacts: dict[str, CVFoldArtifact] = field(
        default_factory=dict,
        repr=False,
    )

    @property
    def datasets(self) -> tuple[DatasetRegistration, ...]:
        return tuple(
            self._datasets[key] for key in sorted(self._datasets)
        )

    @property
    def cv_artifacts(self) -> tuple[CVFoldArtifact, ...]:
        return tuple(
            self._cv_artifacts[key] for key in sorted(self._cv_artifacts)
        )

    def register_dataset(
        self,
        *,
        dataset_id: str,
        dataset_digest: str,
        owner: str,
        role: str,
        access_state: str = "REGISTERED_UNACCESSED",
    ) -> DatasetRegistration:
        if dataset_id in self._datasets:
            raise KeyError("EVALUATION_DATASET_ALREADY_REGISTERED")
        registration = DatasetRegistration(
            dataset_id=dataset_id,
            dataset_digest=dataset_digest,
            owner=owner,
            role=role,
            access_state=access_state,
        )
        failures = registration.validate()
        if failures:
            raise ValueError(";".join(failures))
        self._datasets[dataset_id] = registration
        return registration

    def _policy_decision(
        self,
        registration: DatasetRegistration,
        *,
        purpose: str,
        actor_scope: str,
    ) -> tuple[bool, str]:
        if registration.consumed:
            return False, "DATASET_CONSUMED"
        if actor_scope == "DEVELOPMENT_LOOP":
            if (
                registration.role == "DEVELOPMENT_TRAIN"
                and purpose in DEVELOPMENT_TRAIN_PURPOSES
            ):
                return True, "DEVELOPMENT_TRAIN_ALLOWED"
            if (
                registration.role == "DEVELOPMENT_VALIDATION"
                and purpose in DEVELOPMENT_VALIDATION_PURPOSES
            ):
                return True, "DEVELOPMENT_VALIDATION_ALLOWED"
            return False, "DEVELOPMENT_ROLE_OR_PURPOSE_FORBIDDEN"
        if (
            actor_scope == "CV_EVALUATOR"
            and registration.role == "CV_HOLDOUT"
            and purpose == "CV_PROCEDURE_EVALUATION"
        ):
            return True, "CV_PROCEDURE_ALLOWED"
        if (
            actor_scope == "SEALED_FINAL_EVALUATOR"
            and registration.role == "LOCKED_FINAL"
            and purpose == "SEALED_FINAL_EXECUTION"
            and registration.access_state == "FROZEN_UNACCESSED"
            and registration.execution_count == 0
        ):
            return True, "LOCKED_FINAL_SINGLE_EXECUTION_ALLOWED"
        if (
            actor_scope == "OFFICIAL_EXECUTOR"
            and registration.role
            in {"OFFICIAL_PUBLIC", "OFFICIAL_PRIVATE"}
            and purpose == "OFFICIAL_OBSERVATION"
        ):
            return True, "OFFICIAL_OBSERVATION_ALLOWED"
        return False, "ACTOR_ROLE_PURPOSE_FORBIDDEN"

    def request_access(
        self,
        *,
        dataset_id: str,
        purpose: str,
        actor_scope: str,
        runtime_identity_digest: str,
        artifact_digest: str,
    ) -> EvaluationAccessGrant:
        registration = self._datasets.get(dataset_id)
        if registration is None:
            raise KeyError("EVALUATION_DATASET_NOT_REGISTERED")
        allowed, reason = self._policy_decision(
            registration,
            purpose=purpose,
            actor_scope=actor_scope,
        )
        event = self.ledger.record_decision(
            dataset_id=registration.dataset_id,
            dataset_role=registration.role,
            purpose=purpose,
            actor_scope=actor_scope,
            runtime_identity_digest=runtime_identity_digest,
            artifact_digest=artifact_digest,
            access_granted=allowed,
            decision_reason=reason,
        )
        if not allowed:
            raise PermissionError("EVALUATION_ACCESS_REJECTED:" + reason)
        next_state = registration.access_state
        if registration.role == "LOCKED_FINAL":
            next_state = "EXECUTED_ONCE"
        elif registration.access_state == "REGISTERED_UNACCESSED":
            next_state = "ACCESSED"
        self._datasets[dataset_id] = replace(
            registration,
            access_state=next_state,
            first_access_event_digest=(
                registration.first_access_event_digest
                or event.event_digest
            ),
            execution_count=registration.execution_count + 1,
        )
        return EvaluationAccessGrant(
            dataset_id=registration.dataset_id,
            dataset_digest=registration.dataset_digest,
            role=registration.role,
            purpose=purpose,
            actor_scope=actor_scope,
            runtime_identity_digest=runtime_identity_digest,
            artifact_digest=artifact_digest,
            access_event_digest=event.event_digest,
            _registry_token=self._token,
        )

    def require_development_trigger(
        self,
        grant: EvaluationAccessGrant,
    ) -> None:
        if (
            grant._registry_token is not self._token
            or grant.actor_scope != "DEVELOPMENT_LOOP"
            or grant.role
            not in {"DEVELOPMENT_TRAIN", "DEVELOPMENT_VALIDATION"}
        ):
            raise PermissionError("EVALUATION_DEVELOPMENT_TRIGGER_FORBIDDEN")

    def register_cv_artifact(
        self,
        *,
        fold_id: str,
        dataset_id: str,
        p_logical_digest: str,
        initial_state_logical_digest: str,
        runtime_identity: RuntimeIdentity,
    ) -> CVFoldArtifact:
        if not fold_id or fold_id in self._cv_artifacts:
            raise ValueError("CV_FOLD_ID_INVALID")
        identity_failures = runtime_identity.validate()
        if identity_failures:
            raise ValueError(";".join(identity_failures))
        runtime_digest = runtime_identity.digest()
        if any(
            item.runtime_identity_digest == runtime_digest
            for item in self._cv_artifacts.values()
        ):
            raise PermissionError("CV_RUNTIME_IDENTITY_REUSED")
        if any(
            item.p_logical_digest == p_logical_digest
            for item in self._cv_artifacts.values()
        ):
            raise PermissionError("CV_P_ARTIFACT_REUSED")
        artifact_digest = "cv-fold-artifact:" + digest_object(
            {
                "fold_id": fold_id,
                "dataset_id": dataset_id,
                "p_logical_digest": p_logical_digest,
                "initial_state_logical_digest": initial_state_logical_digest,
                "runtime_identity_digest": runtime_digest,
            }
        )
        grant = self.request_access(
            dataset_id=dataset_id,
            purpose="CV_PROCEDURE_EVALUATION",
            actor_scope="CV_EVALUATOR",
            runtime_identity_digest=runtime_digest,
            artifact_digest=artifact_digest,
        )
        artifact = CVFoldArtifact(
            fold_id=fold_id,
            dataset_id=dataset_id,
            p_logical_digest=p_logical_digest,
            initial_state_logical_digest=initial_state_logical_digest,
            runtime_identity_digest=runtime_digest,
            access_event_digest=grant.access_event_digest,
            artifact_digest=artifact_digest,
        )
        self._cv_artifacts[fold_id] = artifact
        return artifact

    def cv_procedure_summary(self) -> CVProcedureSummary:
        artifacts = self.cv_artifacts
        return CVProcedureSummary(
            fold_count=len(artifacts),
            distinct_p_artifact_count=len(
                {item.p_logical_digest for item in artifacts}
            ),
            distinct_runtime_identity_count=len(
                {item.runtime_identity_digest for item in artifacts}
            ),
            allowed_claim="CV_PROCEDURE_EVIDENCE",
            same_single_artifact_claim_allowed=False,
        )

    def digest(self) -> str:
        failures = self.ledger.validate_chain()
        if failures:
            raise RuntimeError(";".join(failures))
        return "evaluation-registry:" + digest_object(
            {
                "version": EVALUATION_REGISTRY_VERSION,
                "datasets": self.datasets,
                "cv_artifacts": self.cv_artifacts,
                "access_ledger": self.ledger.digest(),
            }
        )


__all__ = [
    "DATASET_ROLES",
    "DEVELOPMENT_TRAIN_PURPOSES",
    "DEVELOPMENT_VALIDATION_PURPOSES",
    "EVALUATION_REGISTRY_VERSION",
    "CVFoldArtifact",
    "CVProcedureSummary",
    "DatasetRegistration",
    "EvaluationAccessGrant",
    "EvaluationRegistry",
]
