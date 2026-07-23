"""Standalone HDS judgment subject with no compute, storage, or effect authority."""

from __future__ import annotations

import dataclasses
import math
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from .schema import digest_object, forbidden_runtime_paths

JUDGMENT_SCHEMA_VERSION = "arc3-hds-frame-v1"
JUDGMENT_SUBJECT_REMOVAL_WITNESS = (
    "JUDGMENT_SUBJECT_REMOVED_NO_G2_ACCEPTANCE_STOP_OR_AUTHORIZATION"
)
JUDGMENT_STATUSES = frozenset(
    {
        "COMPUTE_REQUEST",
        "ACCEPT",
        "REJECT",
        "REOBSERVE",
        "SUSPEND",
        "STOP",
        "ROLLBACK",
    }
)
_FORBIDDEN_VALUE_PATTERNS = (
    re.compile(
        r"(?i)(?:^|[^a-z0-9])[a-z]{1,3}\d{2}-[0-9a-f]{8}"
        r"(?:$|[^a-z0-9])"
    ),
    re.compile(r"(?i)(?:^|[^a-z0-9])(?:game|task|level)[-_ ]?(?:id|\d+)"),
    re.compile(r"(?i)(?:/mnt/|[a-z]:\\|environment_files/|\.json\b|\.py\b)"),
)


def _text_tuple_valid(values: object) -> bool:
    return (
        isinstance(values, tuple)
        and all(isinstance(item, str) and bool(item.strip()) for item in values)
    )


def _forbidden_value_paths(value: object, path: str = "$") -> tuple[str, ...]:
    failures: list[str] = []
    stack: list[tuple[str, object]] = [(path, value)]
    while stack:
        current_path, item = stack.pop()
        if isinstance(item, Mapping):
            stack.extend(
                (f"{current_path}.{key}", child)
                for key, child in item.items()
            )
        elif isinstance(item, Sequence) and not isinstance(
            item, (str, bytes, bytearray)
        ):
            stack.extend(
                (f"{current_path}[{index}]", child)
                for index, child in enumerate(item)
            )
        elif isinstance(item, str) and any(
            pattern.search(item) for pattern in _FORBIDDEN_VALUE_PATTERNS
        ):
            failures.append(current_path)
    return tuple(sorted(set(failures)))


@dataclass(frozen=True, slots=True)
class HDSX:
    targets: tuple[str, ...]
    candidate_ids: tuple[str, ...]
    observation_scope: tuple[str, ...]

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not _text_tuple_valid(self.targets) or not self.targets:
            failures.append("HDS_X_TARGET_MISSING")
        if not _text_tuple_valid(self.candidate_ids):
            failures.append("HDS_X_CANDIDATE_IDS_INVALID")
        if len(set(self.candidate_ids)) != len(self.candidate_ids):
            failures.append("HDS_X_CANDIDATE_IDS_DUPLICATE")
        if not _text_tuple_valid(self.observation_scope) or not self.observation_scope:
            failures.append("HDS_X_OBSERVATION_SCOPE_MISSING")
        return tuple(sorted(set(failures)))


@dataclass(frozen=True, slots=True)
class HDSR:
    relations: tuple[str, ...]
    evidence_links: tuple[str, ...]
    counter_evidence_links: tuple[str, ...]

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not _text_tuple_valid(self.relations) or not self.relations:
            failures.append("HDS_R_RELATION_MISSING")
        if not _text_tuple_valid(self.evidence_links):
            failures.append("HDS_R_EVIDENCE_INVALID")
        if not _text_tuple_valid(self.counter_evidence_links):
            failures.append("HDS_R_COUNTER_EVIDENCE_INVALID")
        return tuple(sorted(set(failures)))


@dataclass(frozen=True, slots=True)
class HDSMc:
    identity: str
    boundary: str
    acceptance_criteria: tuple[str, ...]
    rejection_criteria: tuple[str, ...]
    stop_on: tuple[str, ...]
    max_risk: float = 1.0
    allow_memory_write: bool = True
    allow_external_emit: bool = True

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not isinstance(self.identity, str) or not self.identity.strip():
            failures.append("HDS_MC_IDENTITY_MISSING")
        if not isinstance(self.boundary, str) or not self.boundary.strip():
            failures.append("HDS_MC_BOUNDARY_MISSING")
        for name, values in (
            ("ACCEPTANCE", self.acceptance_criteria),
            ("REJECTION", self.rejection_criteria),
            ("STOP", self.stop_on),
        ):
            if not _text_tuple_valid(values) or not values:
                failures.append(f"HDS_MC_{name}_CRITERIA_MISSING")
        if (
            isinstance(self.max_risk, bool)
            or not isinstance(self.max_risk, (int, float))
            or not math.isfinite(float(self.max_risk))
            or not 0.0 <= float(self.max_risk) <= 1.0
        ):
            failures.append("HDS_MC_MAX_RISK_INVALID")
        if not isinstance(self.allow_memory_write, bool):
            failures.append("HDS_MC_MEMORY_AUTHORIZATION_INVALID")
        if not isinstance(self.allow_external_emit, bool):
            failures.append("HDS_MC_EMIT_AUTHORIZATION_INVALID")
        return tuple(sorted(set(failures)))


@dataclass(frozen=True, slots=True)
class HDSFramePolicy:
    """Versionable J-side policy used by the integrated Frame adapter."""

    policy_id: str = "hds-frame-policy:default-v1"
    purpose: str = "select-safe-closed-action-candidate"
    boundary: str = "rendered-observation-only"
    acceptance_criteria: tuple[str, ...] = ("W_X_R_MC_CLOSED",)
    rejection_criteria: tuple[str, ...] = (
        "hazard",
        "contradiction",
        "closure-invalid",
    )
    stop_on: tuple[str, ...] = (
        "terminal-win",
        "hazard",
        "budget-exhaustion",
    )
    additional_stopping_conditions: tuple[str, ...] = ()
    max_risk: float = 1.0
    allow_memory_write: bool = True
    allow_external_emit: bool = True

    @property
    def digest(self) -> str:
        return digest_object(self)

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        for name, value in (
            ("ID", self.policy_id),
            ("PURPOSE", self.purpose),
            ("BOUNDARY", self.boundary),
        ):
            if not isinstance(value, str) or not value.strip():
                failures.append(f"HDS_FRAME_POLICY_{name}_MISSING")
        for name, values, required in (
            ("ACCEPTANCE", self.acceptance_criteria, True),
            ("REJECTION", self.rejection_criteria, True),
            ("STOP", self.stop_on, True),
            (
                "ADDITIONAL_STOPPING",
                self.additional_stopping_conditions,
                False,
            ),
        ):
            if not _text_tuple_valid(values) or (required and not values):
                failures.append(f"HDS_FRAME_POLICY_{name}_INVALID")
        if (
            isinstance(self.max_risk, bool)
            or not isinstance(self.max_risk, (int, float))
            or not math.isfinite(float(self.max_risk))
            or not 0.0 <= float(self.max_risk) <= 1.0
        ):
            failures.append("HDS_FRAME_POLICY_MAX_RISK_INVALID")
        if not isinstance(self.allow_memory_write, bool):
            failures.append("HDS_FRAME_POLICY_MEMORY_FLAG_INVALID")
        if not isinstance(self.allow_external_emit, bool):
            failures.append("HDS_FRAME_POLICY_EMIT_FLAG_INVALID")
        serializable = dataclasses.asdict(self)
        failures.extend(
            f"HDS_FRAME_POLICY_RUNTIME_IDENTITY_FORBIDDEN:{path}"
            for path in (
                *forbidden_runtime_paths(serializable),
                *_forbidden_value_paths(serializable),
            )
        )
        return tuple(sorted(set(failures)))


@dataclass(frozen=True, slots=True)
class JudgmentCandidate:
    candidate_id: str
    predicted_outcomes: tuple[str, ...]
    evidence_refs: tuple[str, ...]
    counter_evidence_refs: tuple[str, ...]
    preconditions: tuple[str, ...]
    falsification_conditions: tuple[str, ...]
    score: float
    risk: float
    hazard: bool = False
    admissible: bool = True
    rejected: bool = False
    reversible: bool = False
    rollback_reference: str | None = None
    reason_codes: tuple[str, ...] = ()

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not isinstance(self.candidate_id, str) or not self.candidate_id.strip():
            failures.append("JUDGMENT_CANDIDATE_ID_MISSING")
        for name, values, required in (
            ("OUTCOME", self.predicted_outcomes, True),
            ("EVIDENCE", self.evidence_refs, False),
            ("COUNTER_EVIDENCE", self.counter_evidence_refs, False),
            ("PRECONDITION", self.preconditions, True),
            ("FALSIFIER", self.falsification_conditions, True),
            ("REASON", self.reason_codes, False),
        ):
            if not _text_tuple_valid(values) or (required and not values):
                failures.append(f"JUDGMENT_CANDIDATE_{name}_INVALID")
        for name, value in (("SCORE", self.score), ("RISK", self.risk)):
            if (
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                or not 0.0 <= float(value) <= 1.0
            ):
                failures.append(f"JUDGMENT_CANDIDATE_{name}_INVALID")
        if not isinstance(self.hazard, bool):
            failures.append("JUDGMENT_CANDIDATE_HAZARD_INVALID")
        if not isinstance(self.admissible, bool):
            failures.append("JUDGMENT_CANDIDATE_ADMISSIBLE_INVALID")
        if not isinstance(self.rejected, bool):
            failures.append("JUDGMENT_CANDIDATE_REJECTED_INVALID")
        if not isinstance(self.reversible, bool):
            failures.append("JUDGMENT_CANDIDATE_REVERSIBLE_INVALID")
        if self.rollback_reference is not None and (
            not isinstance(self.rollback_reference, str)
            or not self.rollback_reference.strip()
        ):
            failures.append("JUDGMENT_CANDIDATE_ROLLBACK_REFERENCE_INVALID")
        return tuple(sorted(set(failures)))


@dataclass(frozen=True, slots=True)
class HDSFrame:
    frame_id: str
    purpose: str
    x: HDSX | None
    r: HDSR | None
    mc: HDSMc | None
    observation_boundary: str
    candidates: tuple[JudgmentCandidate, ...]
    evidence: tuple[str, ...]
    counter_evidence: tuple[str, ...]
    risk: float
    hazard: bool
    budget: int
    unknowns: tuple[str, ...]
    stopping_conditions: tuple[str, ...]
    contradiction: bool = False
    rollback_condition: str | None = None
    rollback_reference: str | None = None
    observation_available: bool = True
    schema_version: str = JUDGMENT_SCHEMA_VERSION
    runtime_identity_free: bool = True

    @property
    def digest(self) -> str:
        return digest_object(self)

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if self.schema_version != JUDGMENT_SCHEMA_VERSION:
            failures.append("HDS_FRAME_SCHEMA_INVALID")
        if self.runtime_identity_free is not True:
            failures.append("HDS_FRAME_RUNTIME_IDENTITY_FLAG_INVALID")
        if not isinstance(self.frame_id, str) or not self.frame_id.strip():
            failures.append("HDS_FRAME_ID_MISSING")
        if not isinstance(self.purpose, str) or not self.purpose.strip():
            failures.append("HDS_PURPOSE_MISSING")
        if self.x is None:
            failures.append("HDS_X_MISSING")
        else:
            failures.extend(self.x.validate())
        if self.r is None:
            failures.append("HDS_R_MISSING")
        else:
            failures.extend(self.r.validate())
        if self.mc is None:
            failures.append("HDS_MC_MISSING")
        else:
            failures.extend(self.mc.validate())
            if self.observation_boundary != self.mc.boundary:
                failures.append("HDS_OBSERVATION_BOUNDARY_MISMATCH")
        if (
            not isinstance(self.observation_boundary, str)
            or not self.observation_boundary.strip()
        ):
            failures.append("HDS_OBSERVATION_BOUNDARY_MISSING")
        if not isinstance(self.candidates, tuple):
            failures.append("HDS_CANDIDATE_SET_INVALID")
        else:
            failures.extend(
                failure
                for candidate in self.candidates
                for failure in candidate.validate()
            )
            candidate_ids = tuple(
                candidate.candidate_id for candidate in self.candidates
            )
            if len(set(candidate_ids)) != len(candidate_ids):
                failures.append("HDS_CANDIDATE_ID_DUPLICATE")
            if self.x is not None and set(candidate_ids) != set(
                self.x.candidate_ids
            ):
                failures.append("HDS_X_CANDIDATE_SET_MISMATCH")
        for name, values in (
            ("EVIDENCE", self.evidence),
            ("COUNTER_EVIDENCE", self.counter_evidence),
            ("UNKNOWNS", self.unknowns),
            ("STOPPING_CONDITIONS", self.stopping_conditions),
        ):
            if not _text_tuple_valid(values):
                failures.append(f"HDS_FRAME_{name}_INVALID")
        if (
            isinstance(self.risk, bool)
            or not isinstance(self.risk, (int, float))
            or not math.isfinite(float(self.risk))
            or not 0.0 <= float(self.risk) <= 1.0
        ):
            failures.append("HDS_FRAME_RISK_INVALID")
        if not isinstance(self.hazard, bool):
            failures.append("HDS_FRAME_HAZARD_INVALID")
        if (
            isinstance(self.budget, bool)
            or not isinstance(self.budget, int)
            or self.budget < 0
        ):
            failures.append("HDS_FRAME_BUDGET_INVALID")
        for name, value in (
            ("CONTRADICTION", self.contradiction),
            ("OBSERVATION_AVAILABLE", self.observation_available),
        ):
            if not isinstance(value, bool):
                failures.append(f"HDS_FRAME_{name}_INVALID")
        if self.rollback_condition is not None and (
            not isinstance(self.rollback_condition, str)
            or not self.rollback_condition.strip()
        ):
            failures.append("HDS_FRAME_ROLLBACK_CONDITION_INVALID")
        if self.rollback_reference is not None and (
            not isinstance(self.rollback_reference, str)
            or not self.rollback_reference.strip()
        ):
            failures.append("HDS_FRAME_ROLLBACK_REFERENCE_INVALID")
        serializable = dataclasses.asdict(self)
        failures.extend(
            f"HDS_FRAME_RUNTIME_IDENTITY_FORBIDDEN:{path}"
            for path in (
                *forbidden_runtime_paths(serializable),
                *_forbidden_value_paths(serializable),
            )
        )
        return tuple(sorted(set(failures)))


@dataclass(frozen=True, slots=True)
class JudgmentComputeRequest:
    request_id: str
    frame_digest: str
    purpose: str
    required_outputs: tuple[str, ...] = (
        "hypotheses",
        "counter-hypotheses",
        "predictions",
        "candidates",
        "uncertainty",
        "provenance",
    )
    operation: str = "LLM_COMPUTE"


@dataclass(frozen=True, slots=True)
class StandaloneJudgmentDecision:
    decision_id: str
    frame_digest: str
    status: str
    reason_codes: tuple[str, ...]
    selected_candidate_id: str | None = None
    compute_request: JudgmentComputeRequest | None = None
    allow_memory_write: bool = False
    allow_external_emit: bool = False
    rollback_reference: str | None = None
    next_observation: str | None = None
    authority: str = "hds-judgment-only"

    @property
    def digest(self) -> str:
        return digest_object(self)

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not self.decision_id:
            failures.append("JUDGMENT_DECISION_ID_MISSING")
        if not self.frame_digest:
            failures.append("JUDGMENT_FRAME_DIGEST_MISSING")
        if self.status not in JUDGMENT_STATUSES:
            failures.append("JUDGMENT_STATUS_INVALID")
        if not self.reason_codes:
            failures.append("JUDGMENT_REASON_MISSING")
        if self.authority != "hds-judgment-only":
            failures.append("JUDGMENT_AUTHORITY_INVALID")
        if self.status == "ACCEPT" and not self.selected_candidate_id:
            failures.append("JUDGMENT_ACCEPT_CANDIDATE_MISSING")
        if self.status == "COMPUTE_REQUEST" and self.compute_request is None:
            failures.append("JUDGMENT_COMPUTE_REQUEST_MISSING")
        if self.status != "COMPUTE_REQUEST" and self.compute_request is not None:
            failures.append("JUDGMENT_COMPUTE_REQUEST_UNEXPECTED")
        if self.status != "ACCEPT" and (
            self.allow_memory_write or self.allow_external_emit
        ):
            failures.append("JUDGMENT_EFFECT_AUTHORIZATION_INVALID")
        if self.status == "ROLLBACK" and not self.rollback_reference:
            failures.append("JUDGMENT_ROLLBACK_REFERENCE_MISSING")
        return tuple(sorted(set(failures)))


@dataclass(frozen=True, slots=True)
class HDSJudgmentSubject:
    """Close a supplied frame without creating candidates or applying effects."""

    def _decision(
        self,
        frame: HDSFrame,
        *,
        status: str,
        reason_codes: tuple[str, ...],
        selected_candidate_id: str | None = None,
        compute_request: JudgmentComputeRequest | None = None,
        allow_memory_write: bool = False,
        allow_external_emit: bool = False,
        rollback_reference: str | None = None,
        next_observation: str | None = None,
    ) -> StandaloneJudgmentDecision:
        seed = {
            "frame": frame.digest,
            "status": status,
            "reason_codes": reason_codes,
            "selected_candidate_id": selected_candidate_id,
            "compute_request": compute_request,
            "rollback_reference": rollback_reference,
            "next_observation": next_observation,
        }
        decision = StandaloneJudgmentDecision(
            decision_id="judgment:" + digest_object(seed)[:24],
            frame_digest=frame.digest,
            status=status,
            reason_codes=reason_codes,
            selected_candidate_id=selected_candidate_id,
            compute_request=compute_request,
            allow_memory_write=allow_memory_write,
            allow_external_emit=allow_external_emit,
            rollback_reference=rollback_reference,
            next_observation=next_observation,
        )
        failures = decision.validate()
        if failures:
            raise ValueError(";".join(failures))
        return decision

    def judge(self, frame: HDSFrame) -> StandaloneJudgmentDecision:
        """Return a deterministic judgment over only the supplied HDS Frame."""

        failures = frame.validate()
        if failures:
            return self._decision(
                frame,
                status="SUSPEND",
                reason_codes=tuple(
                    f"FRAME_UNCLOSED:{failure}" for failure in failures
                ),
            )
        assert frame.mc is not None

        if frame.stopping_conditions:
            return self._decision(
                frame,
                status="STOP",
                reason_codes=frame.stopping_conditions,
            )
        if frame.hazard:
            return self._decision(
                frame,
                status="REJECT",
                reason_codes=("HAZARD_ACTION_VETO",),
            )
        if frame.unknowns:
            reason_codes = (
                ("TERMINAL_UNOBSERVED",)
                if "terminal-state-unobserved" in frame.unknowns
                else ("EVIDENCE_INSUFFICIENT_REOBSERVE",)
            )
            return self._decision(
                frame,
                status="REOBSERVE",
                reason_codes=reason_codes,
                next_observation=frame.observation_boundary,
            )
        if frame.budget == 0:
            return self._decision(
                frame,
                status="STOP",
                reason_codes=("ACTION_BUDGET_EXHAUSTED",),
            )
        if frame.rollback_condition is not None:
            if frame.rollback_reference is None:
                return self._decision(
                    frame,
                    status="SUSPEND",
                    reason_codes=("ROLLBACK_REFERENCE_MISSING",),
                )
            return self._decision(
                frame,
                status="ROLLBACK",
                reason_codes=("ROLLBACK_CONDITION_SATISFIED",),
                rollback_reference=frame.rollback_reference,
            )
        if frame.contradiction:
            return self._decision(
                frame,
                status="REJECT",
                reason_codes=("CONTRADICTION_ESTABLISHED",),
            )
        if not frame.candidates:
            compute_request = JudgmentComputeRequest(
                request_id="compute-request:" + frame.digest[:24],
                frame_digest=frame.digest,
                purpose=frame.purpose,
            )
            return self._decision(
                frame,
                status="COMPUTE_REQUEST",
                reason_codes=("NO_CANDIDATE_REQUEST_COMPUTE",),
                compute_request=compute_request,
            )

        admissible = tuple(
            candidate
            for candidate in frame.candidates
            if (
                candidate.admissible
                and not candidate.rejected
                and not candidate.hazard
                and candidate.risk <= frame.mc.max_risk
                and candidate.evidence_refs
            )
        )
        if admissible:
            selected = sorted(
                admissible,
                key=lambda item: (-item.score, item.risk, item.candidate_id),
            )[0]
            return self._decision(
                frame,
                status="ACCEPT",
                reason_codes=selected.reason_codes
                or ("W_X_R_MC_CLOSED",),
                selected_candidate_id=selected.candidate_id,
                allow_memory_write=frame.mc.allow_memory_write,
                allow_external_emit=frame.mc.allow_external_emit,
            )

        rejected = tuple(
            candidate
            for candidate in frame.candidates
            if candidate.rejected or candidate.hazard
        )
        if rejected:
            reasons = tuple(
                sorted(
                    {
                        reason
                        for candidate in rejected
                        for reason in (
                            candidate.reason_codes
                            or (
                                "CANDIDATE_HAZARD_VETO"
                                if candidate.hazard
                                else "CANDIDATE_REJECTED",
                            )
                        )
                    }
                )
            )
            return self._decision(
                frame,
                status="REJECT",
                reason_codes=reasons,
            )

        nonclosure_reasons = tuple(
            sorted(
                {
                    reason
                    for candidate in frame.candidates
                    if not candidate.admissible
                    for reason in candidate.reason_codes
                }
            )
        )
        if frame.observation_available:
            return self._decision(
                frame,
                status="REOBSERVE",
                reason_codes=nonclosure_reasons
                or ("EVIDENCE_INSUFFICIENT_REOBSERVE",),
                next_observation=frame.observation_boundary,
            )
        return self._decision(
            frame,
            status="SUSPEND",
            reason_codes=("NO_CLOSED_ACTION_CANDIDATE",),
        )


@dataclass(frozen=True, slots=True)
class StandaloneJudgmentHarness:
    judgment_subject: HDSJudgmentSubject | None

    def run(self, frame: HDSFrame) -> StandaloneJudgmentDecision:
        if self.judgment_subject is None:
            raise RuntimeError(JUDGMENT_SUBJECT_REMOVAL_WITNESS)
        return self.judgment_subject.judge(frame)


__all__ = [
    "HDSFrame",
    "HDSFramePolicy",
    "HDSJudgmentSubject",
    "HDSMc",
    "HDSR",
    "HDSX",
    "JUDGMENT_SCHEMA_VERSION",
    "JUDGMENT_STATUSES",
    "JUDGMENT_SUBJECT_REMOVAL_WITNESS",
    "JudgmentCandidate",
    "JudgmentComputeRequest",
    "StandaloneJudgmentDecision",
    "StandaloneJudgmentHarness",
]
