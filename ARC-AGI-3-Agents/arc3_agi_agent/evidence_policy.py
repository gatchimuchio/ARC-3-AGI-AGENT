"""Independent evidence groups and deterministic causal-state policy."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

from .schema import digest_object

EVIDENCE_POLICY_VERSION = "arc3-evidence-policy-v1"
EVIDENCE_OUTCOMES = frozenset(
    {"SUPPORT", "CONTRADICTION", "HAZARD", "NO_EFFECT"}
)
CAUSAL_SCOPE_CLASSES = frozenset(
    {"LEVEL_OVERLAY", "EPISODE_OVERLAY", "SESSION_GLOBAL"}
)


def _sorted_unique(values: Sequence[str]) -> tuple[str, ...]:
    return tuple(sorted(set(values)))


@dataclass(frozen=True, slots=True)
class EvidenceGroup:
    """One independent causal observation; duplicate traces share one ID."""

    group_id: str
    outcome: str
    normalized_before_pattern_digest: str
    action_relation_digest: str
    normalized_after_effect_digest: str
    delay_min_steps: int
    delay_max_steps: int
    episode_nonce: str
    event_ids: tuple[str, ...]

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        for name in (
            "group_id",
            "normalized_before_pattern_digest",
            "action_relation_digest",
            "normalized_after_effect_digest",
            "episode_nonce",
        ):
            value = getattr(self, name)
            if not isinstance(value, str) or not value:
                failures.append("EVIDENCE_GROUP_TEXT_INVALID:" + name)
        if self.outcome not in EVIDENCE_OUTCOMES:
            failures.append("EVIDENCE_GROUP_OUTCOME_INVALID")
        if (
            isinstance(self.delay_min_steps, bool)
            or isinstance(self.delay_max_steps, bool)
            or not isinstance(self.delay_min_steps, int)
            or not isinstance(self.delay_max_steps, int)
            or self.delay_min_steps < 0
            or self.delay_max_steps < self.delay_min_steps
        ):
            failures.append("EVIDENCE_GROUP_DELAY_INVALID")
        if (
            not self.event_ids
            or self.event_ids != _sorted_unique(self.event_ids)
            or any(not isinstance(item, str) or not item for item in self.event_ids)
        ):
            failures.append("EVIDENCE_GROUP_EVENT_IDS_INVALID")
        expected = build_evidence_group_id(
            normalized_before_pattern_digest=(
                self.normalized_before_pattern_digest
            ),
            action_relation_digest=self.action_relation_digest,
            normalized_after_effect_digest=(
                self.normalized_after_effect_digest
            ),
            delay_min_steps=self.delay_min_steps,
            delay_max_steps=self.delay_max_steps,
            episode_nonce=self.episode_nonce,
        )
        if self.group_id != expected:
            failures.append("EVIDENCE_GROUP_ID_INVALID")
        return tuple(sorted(set(failures)))

    def retrieval_digest(self) -> str:
        """Digest causal content without the independence-only episode nonce."""

        return "evidence-causal-content:" + digest_object(
            {
                "before": self.normalized_before_pattern_digest,
                "action_relation": self.action_relation_digest,
                "after": self.normalized_after_effect_digest,
                "delay": (self.delay_min_steps, self.delay_max_steps),
            }
        )


def build_evidence_group_id(
    *,
    normalized_before_pattern_digest: str,
    action_relation_digest: str,
    normalized_after_effect_digest: str,
    delay_min_steps: int,
    delay_max_steps: int,
    episode_nonce: str,
) -> str:
    return "evidence-group:" + digest_object(
        {
            "normalized_before_pattern": normalized_before_pattern_digest,
            "action_relation": action_relation_digest,
            "normalized_after_effect": normalized_after_effect_digest,
            "temporal_window": (delay_min_steps, delay_max_steps),
            "non_search_episode_nonce": episode_nonce,
        }
    )


def evidence_group(
    *,
    outcome: str,
    normalized_before_pattern_digest: str,
    action_relation_digest: str,
    normalized_after_effect_digest: str,
    delay_min_steps: int,
    delay_max_steps: int,
    episode_nonce: str,
    event_ids: Sequence[str],
) -> EvidenceGroup:
    group = EvidenceGroup(
        group_id=build_evidence_group_id(
            normalized_before_pattern_digest=(
                normalized_before_pattern_digest
            ),
            action_relation_digest=action_relation_digest,
            normalized_after_effect_digest=(
                normalized_after_effect_digest
            ),
            delay_min_steps=delay_min_steps,
            delay_max_steps=delay_max_steps,
            episode_nonce=episode_nonce,
        ),
        outcome=outcome,
        normalized_before_pattern_digest=(
            normalized_before_pattern_digest
        ),
        action_relation_digest=action_relation_digest,
        normalized_after_effect_digest=normalized_after_effect_digest,
        delay_min_steps=delay_min_steps,
        delay_max_steps=delay_max_steps,
        episode_nonce=episode_nonce,
        event_ids=_sorted_unique(tuple(event_ids)),
    )
    failures = group.validate()
    if failures:
        raise ValueError(";".join(failures))
    return group


@dataclass(frozen=True, slots=True)
class EvidenceEvaluation:
    support_group_ids: tuple[str, ...]
    contradiction_group_ids: tuple[str, ...]
    hazard_group_ids: tuple[str, ...]
    no_effect_group_ids: tuple[str, ...]
    support_count: int
    contradiction_count: int
    hazard_count: int
    no_effect_count: int
    distinct_episode_support: int
    confidence_ppm: int
    contradiction_ratio_ppm: int
    state: str
    execute_eligibility: bool
    probe_eligibility: bool


@dataclass(frozen=True, slots=True)
class EvidencePolicy:
    """Versioned HDS evidence thresholds with integer-only arithmetic."""

    version: str = EVIDENCE_POLICY_VERSION
    local_min_support: int = 2
    session_min_total_support: int = 3
    session_min_distinct_episode_support: int = 2
    active_confidence_ppm: int = 800_000
    max_contradiction_ratio_ppm: int = 100_000
    max_hazard_for_execute: int = 0
    rejected_min_contradictions: int = 2

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        for name in (
            "local_min_support",
            "session_min_total_support",
            "session_min_distinct_episode_support",
            "active_confidence_ppm",
            "max_contradiction_ratio_ppm",
            "max_hazard_for_execute",
            "rejected_min_contradictions",
        ):
            value = getattr(self, name)
            if (
                isinstance(value, bool)
                or not isinstance(value, int)
                or value < 0
            ):
                failures.append("EVIDENCE_POLICY_INTEGER_INVALID:" + name)
        if not self.version:
            failures.append("EVIDENCE_POLICY_VERSION_MISSING")
        if not 0 <= self.active_confidence_ppm <= 1_000_000:
            failures.append("EVIDENCE_POLICY_CONFIDENCE_INVALID")
        if not 0 <= self.max_contradiction_ratio_ppm <= 1_000_000:
            failures.append("EVIDENCE_POLICY_CONTRADICTION_RATIO_INVALID")
        if self.local_min_support <= 0:
            failures.append("EVIDENCE_POLICY_LOCAL_SUPPORT_INVALID")
        if self.session_min_total_support < self.local_min_support:
            failures.append("EVIDENCE_POLICY_SESSION_SUPPORT_INVALID")
        if self.session_min_distinct_episode_support <= 0:
            failures.append("EVIDENCE_POLICY_EPISODE_SUPPORT_INVALID")
        return tuple(sorted(set(failures)))

    @staticmethod
    def confidence_ppm(
        *,
        support_count: int,
        contradiction_count: int,
        hazard_count: int,
    ) -> int:
        return (
            1_000_000
            * (1 + support_count)
            // (
                2
                + support_count
                + contradiction_count
                + 2 * hazard_count
            )
        )

    def evaluate(
        self,
        groups: Sequence[EvidenceGroup],
        *,
        scope_class: str,
        applicability_known: bool = True,
    ) -> EvidenceEvaluation:
        failures = self.validate()
        if failures:
            raise ValueError(";".join(failures))
        if scope_class not in CAUSAL_SCOPE_CLASSES:
            raise ValueError("EVIDENCE_POLICY_SCOPE_INVALID")

        unique: dict[str, EvidenceGroup] = {}
        for group in groups:
            group_failures = group.validate()
            if group_failures:
                raise ValueError(";".join(group_failures))
            prior = unique.get(group.group_id)
            if prior is not None and prior != group:
                raise ValueError("EVIDENCE_GROUP_ID_CONTENT_CONFLICT")
            unique[group.group_id] = group
        ordered = tuple(unique[key] for key in sorted(unique))
        support = tuple(
            item for item in ordered if item.outcome == "SUPPORT"
        )
        contradiction = tuple(
            item for item in ordered if item.outcome == "CONTRADICTION"
        )
        hazard = tuple(
            item for item in ordered if item.outcome == "HAZARD"
        )
        no_effect = tuple(
            item for item in ordered if item.outcome == "NO_EFFECT"
        )
        support_count = len(support)
        contradiction_count = len(contradiction)
        hazard_count = len(hazard)
        no_effect_count = len(no_effect)
        distinct_episode_support = len(
            {item.episode_nonce for item in support}
        )
        confidence_ppm = self.confidence_ppm(
            support_count=support_count,
            contradiction_count=contradiction_count,
            hazard_count=hazard_count,
        )
        contradiction_ratio_ppm = (
            1_000_000
            * contradiction_count
            // max(1, support_count + contradiction_count)
        )

        if not applicability_known:
            state = "SUSPENDED"
        elif hazard_count > self.max_hazard_for_execute:
            state = "SUSPENDED"
        elif (
            contradiction_count >= self.rejected_min_contradictions
            and contradiction_count > support_count
        ):
            state = "REJECTED"
        elif contradiction_ratio_ppm > self.max_contradiction_ratio_ppm:
            state = "SUSPENDED"
        elif support_count == 0:
            state = "PROPOSED"
        else:
            if scope_class == "SESSION_GLOBAL":
                support_ready = (
                    support_count >= self.session_min_total_support
                    and distinct_episode_support
                    >= self.session_min_distinct_episode_support
                )
            else:
                support_ready = support_count >= self.local_min_support
            # Two local supports yield 750k under the required formula and are
            # allowed for bounded episode-local execution. Session-global
            # activation always uses the configured 800k threshold.
            confidence_ready = (
                confidence_ppm >= self.active_confidence_ppm
                if scope_class == "SESSION_GLOBAL"
                else confidence_ppm
                >= min(self.active_confidence_ppm, 750_000)
            )
            state = (
                "ACTIVE"
                if support_ready and confidence_ready
                else "PROBATION"
            )
        execute_eligibility = bool(
            state == "ACTIVE"
            and contradiction_count == 0
            and hazard_count <= self.max_hazard_for_execute
        )
        probe_eligibility = state in {"PROBATION", "ACTIVE"}
        return EvidenceEvaluation(
            support_group_ids=tuple(item.group_id for item in support),
            contradiction_group_ids=tuple(
                item.group_id for item in contradiction
            ),
            hazard_group_ids=tuple(item.group_id for item in hazard),
            no_effect_group_ids=tuple(item.group_id for item in no_effect),
            support_count=support_count,
            contradiction_count=contradiction_count,
            hazard_count=hazard_count,
            no_effect_count=no_effect_count,
            distinct_episode_support=distinct_episode_support,
            confidence_ppm=confidence_ppm,
            contradiction_ratio_ppm=contradiction_ratio_ppm,
            state=state,
            execute_eligibility=execute_eligibility,
            probe_eligibility=probe_eligibility,
        )


__all__ = [
    "CAUSAL_SCOPE_CLASSES",
    "EVIDENCE_OUTCOMES",
    "EVIDENCE_POLICY_VERSION",
    "EvidenceEvaluation",
    "EvidenceGroup",
    "EvidencePolicy",
    "build_evidence_group_id",
    "evidence_group",
]
