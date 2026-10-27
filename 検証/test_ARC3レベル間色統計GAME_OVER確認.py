import unittest

from 検証.ARC3レベル間色統計GAME_OVER確認 import _gate


def _holdout_result(candidate_game_over=(5, 5, 6)):
    previous = {}
    candidate = {}
    for seed, candidate_over in zip((7, 31, 73), candidate_game_over):
        key = str(seed)
        previous[key] = {
            "levels_completed": 2,
            "no_op_actions": 100,
            "game_over_events": 6,
        }
        candidate[key] = {
            "levels_completed": 2,
            "no_op_actions": 100,
            "game_over_events": candidate_over,
            "policy_holds": 0,
            "illegal_action_attempts": 0,
            "duplicate_observation_steps": 0,
        }
    return {
        "previous": previous,
        "candidate": candidate,
        "previous_matches_C2-003": {
            str(seed): {"all_metrics": True} for seed in (7, 31, 73)
        },
        "same_public_start_pairs": {str(seed): 20 for seed in (7, 31, 73)},
        "paired_environment_runs": {str(seed): 20 for seed in (7, 31, 73)},
    }


class ColorResetGameOverHoldoutTests(unittest.TestCase):
    def test_requires_repeated_gameover_reduction_without_other_regression(self):
        gate = _gate(_holdout_result())

        self.assertTrue(gate["passed"])

    def test_rejects_single_seed_or_single_event_reduction(self):
        gate = _gate(_holdout_result((5, 6, 6)))

        self.assertFalse(gate["passed"])
        self.assertFalse(gate["checks"]["total_game_over_reduction_at_least_two"])
        self.assertFalse(gate["checks"]["game_over_reduced_in_at_least_two_seeds"])

    def test_rejects_any_level_or_noop_regression(self):
        result = _holdout_result()
        result["candidate"]["31"]["levels_completed"] = 1
        result["candidate"]["73"]["no_op_actions"] = 101

        gate = _gate(result)

        self.assertFalse(gate["passed"])
        self.assertFalse(gate["checks"]["levels_not_lower_each_seed"])
        self.assertFalse(gate["checks"]["no_op_not_higher_each_seed"])


if __name__ == "__main__":
    unittest.main()
