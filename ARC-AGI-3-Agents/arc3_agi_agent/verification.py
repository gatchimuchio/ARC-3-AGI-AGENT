"""Conservative rendered-evidence verification for ARC-3 transitions.

The verifier never treats absence of a rendered hazard as proof that no hidden or
delayed hazard exists.  It only records what the current observation supports.
"""

from __future__ import annotations

from dataclasses import dataclass

TERMINAL_STATES = frozenset(
    {"RUNNING", "WIN", "NOT_FINISHED", "GAME_OVER", "UNKNOWN"}
)
HAZARD_EFFECTS = frozenset(
    {"HAZARD", "COLLISION", "IRREVERSIBLE_FAILURE", "RESOURCE_EXHAUSTED"}
)


@dataclass(frozen=True, slots=True)
class RenderedObservation:
    signature: str
    levels_completed: int
    terminal_state: str
    visible_progress: bool
    visible_effects: tuple[str, ...]
    available_actions: tuple[int, ...]
    action_count: int
    max_actions: int

    def validate(self) -> tuple[str, ...]:
        failures: list[str] = []
        if not self.signature:
            failures.append("signature_missing")
        if self.terminal_state not in TERMINAL_STATES:
            failures.append("invalid_terminal_state")
        if self.levels_completed < 0:
            failures.append("negative_level_count")
        if self.action_count < 0 or self.max_actions < 0:
            failures.append("negative_action_count")
        if self.action_count > self.max_actions:
            failures.append("action_count_exceeds_max")
        if any(action < 1 or action > 7 for action in self.available_actions):
            failures.append("invalid_available_action")
        return tuple(failures)


@dataclass(frozen=True, slots=True)
class VerificationResult:
    status: str
    progress_status: str
    terminal_status: str
    hazard_status: str
    commitment_status: str
    reason_codes: tuple[str, ...]
    safe_checkpoint: bool = False


def verify_progress(
    before: RenderedObservation,
    after: RenderedObservation,
) -> tuple[str, str]:
    if after.levels_completed > before.levels_completed:
        return "PASS", "LEVEL_PROGRESS"
    if after.terminal_state == "WIN":
        return "PASS", "WIN_TERMINAL"
    if after.visible_progress and after.signature != before.signature:
        return "PASS", "VISIBLE_PROGRESS"
    if after.signature == before.signature:
        return "SUSPEND", "NO_RENDERED_CHANGE"
    return "SUSPEND", "UNCOMMITTED_RENDERED_CHANGE"


def verify_terminal(observation: RenderedObservation) -> tuple[str, str]:
    if observation.terminal_state == "WIN":
        return "PASS", "WIN"
    if observation.terminal_state == "GAME_OVER":
        return "FAIL", "GAME_OVER"
    if observation.terminal_state in {"RUNNING", "NOT_FINISHED"}:
        return "PENDING", observation.terminal_state
    return "SUSPEND", "TERMINAL_UNKNOWN"


def verify_hazard(observation: RenderedObservation) -> tuple[str, str]:
    if observation.terminal_state == "GAME_OVER":
        return "FAIL", "GAME_OVER_HAZARD"
    if any(effect in HAZARD_EFFECTS for effect in observation.visible_effects):
        return "FAIL", "VISIBLE_HAZARD"
    return "CLEAR_RENDERED_ONLY", "NO_HAZARD_OBSERVED"


def verify_transition_commitment(
    before: RenderedObservation,
    after: RenderedObservation,
    action_id: int,
    expected_effects: tuple[str, ...],
) -> tuple[str, str]:
    if action_id not in before.available_actions:
        return "FAIL", "ACTION_NOT_AVAILABLE"
    if after.terminal_state == "GAME_OVER":
        return "FAIL", "TERMINAL_DIVERGENCE"
    if after.levels_completed > before.levels_completed or after.terminal_state == "WIN":
        return "PASS", "PROGRESS_COMMITMENT"
    if not expected_effects:
        return "SUSPEND", "EXPECTED_EFFECTS_MISSING"
    if any(effect in after.visible_effects for effect in expected_effects):
        return "PASS", "EXPECTED_EFFECT_OBSERVED"
    if after.signature == before.signature:
        return "SUSPEND", "NO_EFFECT_OBSERVED"
    return "FAIL", "OBSERVED_DIVERGENCE"


def verify_rendered_transition(
    before: RenderedObservation,
    after: RenderedObservation,
    action_id: int,
    expected_effects: tuple[str, ...],
) -> VerificationResult:
    failures = before.validate() + after.validate()
    if failures:
        return VerificationResult(
            status="SUSPEND",
            progress_status="SUSPEND",
            terminal_status="SUSPEND",
            hazard_status="SUSPEND",
            commitment_status="SUSPEND",
            reason_codes=tuple(f"INVALID_{failure}" for failure in failures),
            safe_checkpoint=False,
        )

    progress_status, progress_reason = verify_progress(before, after)
    terminal_status, terminal_reason = verify_terminal(after)
    hazard_status, hazard_reason = verify_hazard(after)
    commitment_status, commitment_reason = verify_transition_commitment(
        before, after, action_id, expected_effects
    )
    reasons = (progress_reason, terminal_reason, hazard_reason, commitment_reason)

    if "FAIL" in {hazard_status, terminal_status, commitment_status}:
        status = "FAIL"
    elif progress_status == "PASS" and commitment_status == "PASS":
        status = "PASS"
    else:
        status = "SUSPEND"

    return VerificationResult(
        status=status,
        progress_status=progress_status,
        terminal_status=terminal_status,
        hazard_status=hazard_status,
        commitment_status=commitment_status,
        reason_codes=reasons,
        safe_checkpoint=(status == "PASS" and hazard_status != "FAIL"),
    )


__all__ = [
    "HAZARD_EFFECTS",
    "RenderedObservation",
    "TERMINAL_STATES",
    "VerificationResult",
    "verify_hazard",
    "verify_progress",
    "verify_rendered_transition",
    "verify_terminal",
    "verify_transition_commitment",
]
