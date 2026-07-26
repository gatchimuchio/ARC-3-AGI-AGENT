from __future__ import annotations

import unittest

from arc3_agi_agent.memory import PassiveMemory
from arc3_agi_agent.protocol import AuthorityViolation
from arc3_agi_agent.s5_authority import (
    HDSOutcomeRetentionController,
    HDSPolicyResetController,
    PureLLMOutcomeRetentionExecutor,
    S5PolicyResetDecision,
    require_s5_policy_reset_directive,
)
from arc3_agi_agent.s5_policy import S5PolicyDecision


def _reset_policy_decision() -> S5PolicyDecision:
    return S5PolicyDecision(
        action_id=0,
        horizontal=-1,
        vertical=-1,
        target_palette=0,
        compatibility_reset=True,
        action_head_id="action-surface",
        action_margin=9.0,
        horizontal_margin=None,
        vertical_margin=None,
        feature_digest="s5-feature:abc",
        source_render_digest="s5-render:def",
        history_count=3,
        memory_influenced=True,
    )


class S5AuthorityTests(unittest.TestCase):
    def test_outcome_retention_requires_hds_capability_and_is_single_use(
        self,
    ) -> None:
        controller = HDSOutcomeRetentionController()
        decision = controller.judge(
            observation_signature="frame:observed",
            result_signature="result:observed",
            candidate_digest="candidate:observed",
            memory_version=0,
        )
        payload = {"format": "rendered-outcome"}
        directive = controller.directive(
            decision,
            memory_target="s5-rendered-history",
            memory_payload=payload,
        )
        memory = PassiveMemory(max_entries=1)
        executor = PureLLMOutcomeRetentionExecutor()
        result = executor.execute(
            directive,
            decision,
            payload,
            memory,
        )
        self.assertEqual(result.version, 1)
        self.assertEqual(memory.version, 1)
        with self.assertRaises(AuthorityViolation):
            executor.execute(
                directive,
                decision,
                payload,
                memory,
            )

    def test_policy_reset_directive_is_hds_owned_and_single_use(self) -> None:
        controller = HDSPolicyResetController()
        decision = controller.judge(
            observation_signature="frame:reset",
            terminal_state="GAME_OVER",
            policy_digest="policy:abc",
            query_digest="query:abc",
            policy_decision=_reset_policy_decision(),
            memory_version=2,
        )
        directive = controller.directive(
            decision,
            memory_target="s5-rendered-history",
            memory_payload={"format": "rendered-reset"},
        )
        directive.consume_memory(decision)
        require_s5_policy_reset_directive(
            directive,
            decision,
            executor="pure-llm",
        )
        with self.assertRaises(AuthorityViolation):
            require_s5_policy_reset_directive(
                directive,
                decision,
                executor="pure-llm",
            )

    def test_forged_reset_decision_is_rejected(self) -> None:
        forged = S5PolicyResetDecision(
            decision_id="forged",
            observation_signature="frame:reset",
            policy_digest="policy:abc",
            query_digest="query:abc",
            feature_digest="s5-feature:abc",
            memory_version=0,
            reset_reference="s5-rendered-reset:abc",
            terminal_state="NOT_FINISHED",
        )
        self.assertIn(
            "S5_RESET_NOT_ISSUED_BY_HDS",
            forged.validate(),
        )

    def test_non_reset_policy_output_cannot_authorize_reset(self) -> None:
        invalid = S5PolicyDecision(
            action_id=3,
            horizontal=-1,
            vertical=-1,
            target_palette=0,
            compatibility_reset=False,
            action_head_id="action-surface",
            action_margin=9.0,
            horizontal_margin=None,
            vertical_margin=None,
            feature_digest="s5-feature:abc",
            source_render_digest="s5-render:def",
            history_count=3,
            memory_influenced=True,
        )
        with self.assertRaises(AuthorityViolation):
            HDSPolicyResetController().judge(
                observation_signature="frame:reset",
                terminal_state="NOT_FINISHED",
                policy_digest="policy:abc",
                query_digest="query:abc",
                policy_decision=invalid,
                memory_version=0,
            )


if __name__ == "__main__":
    unittest.main()
