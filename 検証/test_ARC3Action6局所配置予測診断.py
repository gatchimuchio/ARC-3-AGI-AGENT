from __future__ import annotations

from dataclasses import replace
import pathlib
import sys
import unittest

ROOT = pathlib.Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "検証"))

from ARC3Action6局所配置予測診断 import (
    _EmpiricalForecast,
    _Sample,
    _evaluate_folds,
    _fold_assignment,
    _policy_type,
    _prerequisite_gate,
    _sample_transition,
    _target_topology,
)
from 接続.ARC3境界 import 観測する
from 接続.観測駆動探索Action import 探索Action, 観測駆動探索方針


def _observation(board, number=0, state="NOT_FINISHED", levels=0):
    return 観測する(
        {
            "game_id": "synthetic-boundary-test",
            "state": state,
            "levels_completed": levels,
            "win_levels": 5,
            "available_actions": [6],
            "frame": [board],
        },
        観測通番=number,
    )


class OrientedTopologyDiagnosticTests(unittest.TestCase):
    def test_color_permutation_preserves_equality_topology(self):
        before = ((2, 2, 1), (3, 2, 1), (3, 4, 2))
        permutation = {1: 13, 2: 7, 3: 1, 4: 9}
        renamed = tuple(tuple(permutation[value] for value in row) for row in before)
        self.assertEqual(_target_topology(before, 1, 1), _target_topology(renamed, 1, 1))
        self.assertEqual(set(_target_topology(before, 0, 0)), {"same", "different", "outside"})

    def test_orientation_is_retained_instead_of_neighbor_count_only(self):
        north = ((0, 1, 0), (0, 1, 0), (0, 0, 0))
        east = ((0, 0, 0), (0, 1, 1), (0, 0, 0))
        self.assertNotEqual(_target_topology(north, 1, 1), _target_topology(east, 1, 1))
        self.assertEqual(_target_topology(north, 1, 1).count("same"), 1)
        self.assertEqual(_target_topology(east, 1, 1).count("same"), 1)

    def test_transition_feature_uses_pre_action_board_and_terminal_label(self):
        before = _observation(((0, 1, 0), (0, 1, 0), (0, 0, 0)))
        after = _observation(((0, 0, 0), (0, 1, 1), (0, 0, 0)), 1, "GAME_OVER")
        sample = _sample_transition(2, before, 探索Action(6, {"x": 1, "y": 1}), after)
        self.assertEqual(sample.topology, _target_topology(before.最新盤面, 1, 1))
        self.assertNotEqual(sample.topology, _target_topology(after.最新盤面, 1, 1))
        self.assertEqual(sample.outcome, "game_over")

    def test_observer_leaves_selection_and_public_reward_unchanged(self):
        samples = []
        observer_type = _policy_type(samples, 0)
        self.assertIs(observer_type.選ぶ, 観測駆動探索方針.選ぶ)
        self.assertIs(observer_type._未試行座標を選ぶ, 観測駆動探索方針._未試行座標を選ぶ)
        baseline = 観測駆動探索方針(乱数種=19, 可視変化係数=0.0)
        observer = observer_type(乱数種=19, 可視変化係数=0.0)
        before = _observation(((0, 1), (2, 1)))
        baseline_action = baseline.選ぶ(before)
        observed_action = observer.選ぶ(before)
        self.assertEqual(baseline_action, observed_action)
        after = _observation(((0, 2), (2, 1)), 1)
        self.assertEqual(
            baseline.応答を記録する(before, baseline_action, after),
            observer.応答を記録する(before, observed_action, after),
        )
        self.assertEqual(baseline._rng.getstate(), observer._rng.getstate())
        self.assertEqual(len(samples), 1)

    def test_support_requires_three_samples_and_two_training_games(self):
        topology = ("same",) * 8
        other = ("different",) * 8
        one_game = _EmpiricalForecast([_Sample(0, topology, "no_op")] * 3)
        self.assertEqual(one_game.predict(topology), (one_game.marginal, False, 3, 1))
        too_few = _EmpiricalForecast(
            [_Sample(0, topology, "no_op"), _Sample(1, topology, "board_change")]
        )
        self.assertEqual(too_few.predict(topology), (too_few.marginal, False, 2, 2))
        enough = _EmpiricalForecast(
            [
                _Sample(0, topology, "no_op"),
                _Sample(1, topology, "board_change"),
                _Sample(1, topology, "board_change"),
                _Sample(2, other, "game_over"),
            ]
        )
        probabilities, eligible, support, games = enough.predict(topology)
        self.assertTrue(eligible)
        self.assertEqual((support, games), (3, 2))
        self.assertAlmostEqual(sum(probabilities), 1.0)
        self.assertAlmostEqual(probabilities[3], (2 + 3 * 0.5) / 6)
        self.assertEqual(enough.predict(("outside",) * 8)[0], enough.marginal)

    def test_fold_test_labels_cannot_enter_its_training_distribution(self):
        topology = ("same",) * 8
        samples = [
            _Sample(0, topology, "board_change"),
            _Sample(0, topology, "board_change"),
            _Sample(1, topology, "board_change"),
            _Sample(2, topology, "no_op"),
            _Sample(3, topology, "no_op"),
        ]
        assignments = (0, 0, 1, 1)
        first = _evaluate_folds(samples, assignments)["folds"][1]
        changed = [
            replace(sample, outcome="win") if sample.game_group in (2, 3) else sample
            for sample in samples
        ]
        second = _evaluate_folds(changed, assignments)["folds"][1]
        self.assertEqual(first["training_outcomes"], second["training_outcomes"])
        self.assertEqual(first["training_samples"], 3)
        self.assertEqual(first["forecast_eligible_test_samples"], 2)
        self.assertEqual(second["forecast_eligible_test_samples"], 2)
        self.assertNotEqual(first["test_outcomes"], second["test_outcomes"])
        self.assertEqual(first["marginal_brier"], 2.0)
        self.assertEqual(first["forecast_brier"], 2.0)

    def test_fixed_folds_group_games_not_seed_samples(self):
        assignments = _fold_assignment(25)
        self.assertEqual(assignments, _fold_assignment(25))
        self.assertEqual([assignments.count(fold) for fold in range(5)], [5] * 5)

    def test_prerequisite_gate_needs_all_prediction_conditions_and_grants_no_adoption(self):
        evaluation = {
            "aggregate": {
                "macro_forecast_brier": 0.95,
                "macro_marginal_brier": 1.0,
                "forecast_coverage": 0.25,
            },
            "folds": [
                {
                    "test_samples": 10,
                    "brier_delta_forecast_minus_marginal": delta,
                }
                for delta in (-0.1, -0.1, -0.1, 0.0, 0.05)
            ],
        }
        gate = _prerequisite_gate(evaluation)
        self.assertTrue(gate["passed"])
        self.assertFalse(gate["runtime_adoption_justified"])
        self.assertFalse(gate["score_gain_claim_justified"])
        evaluation["aggregate"]["forecast_coverage"] = 0.249
        self.assertFalse(_prerequisite_gate(evaluation)["passed"])
        evaluation["aggregate"]["forecast_coverage"] = 0.25
        evaluation["folds"][3]["test_samples"] = 0
        self.assertFalse(_prerequisite_gate(evaluation)["passed"])
        evaluation["folds"][3]["test_samples"] = 10
        evaluation["folds"][3]["brier_delta_forecast_minus_marginal"] = 0.01
        self.assertFalse(_prerequisite_gate(evaluation)["passed"])


if __name__ == "__main__":
    unittest.main()
