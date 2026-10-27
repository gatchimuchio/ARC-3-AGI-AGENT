from __future__ import annotations

import copy
from types import SimpleNamespace
import unittest

from 検証.ARC3policy状態hashseed評価 import (
    _decision_seed,
    _seed_material,
    _現在観測決定seed方針,
)


def _observation(**updates):
    values = {
        "状態": "NOT_FINISHED",
        "最新盤面": ((1, 2), (2, 1)),
        "作用可能番号": frozenset({1, 2, 6}),
    }
    values.update(updates)
    return SimpleNamespace(**values)


class PolicyStateHashSeedTests(unittest.TestCase):
    def test_seed_material_is_id_free_and_repeatable(self):
        observation = _observation()
        policy = _現在観測決定seed方針(乱数種=3)
        first = _seed_material(observation, policy)
        second = _seed_material(observation, policy)
        banned = {
            "game_id",
            "level_id",
            "filename",
            "guid",
            "trajectory",
            "answer",
            "hidden",
            "board_hash",
        }

        self.assertEqual(first, second)
        self.assertFalse(banned.intersection(first))
        self.assertEqual(_decision_seed(observation, policy), _decision_seed(observation, policy))

    def test_public_state_and_policy_statistics_change_seed_material(self):
        observation = _observation()
        policy = _現在観測決定seed方針(乱数種=3)
        baseline = _seed_material(observation, policy)

        changes = (
            _observation(状態="GAME_OVER"),
            _observation(最新盤面=((1, 2), (2, 2))),
            _observation(作用可能番号=frozenset({1, 6})),
        )
        for changed in changes:
            self.assertNotEqual(baseline, _seed_material(changed, policy))

        policy._総作用数 = 1
        policy._回数[1] = 1
        policy._報酬合計[1] = 0.5
        self.assertNotEqual(baseline, _seed_material(observation, policy))

        policy._色回数[2] = 1
        policy._色報酬合計[2] = -0.25
        policy._座標試行[observation.最新盤面] = {(0, 0)}
        changed = _seed_material(observation, policy)
        self.assertEqual(changed["coordinate_attempt_count"], 1)
        self.assertNotEqual(baseline, changed)

    def test_identical_observation_and_statistics_choose_identically(self):
        observation = _observation()
        left = _現在観測決定seed方針(乱数種=1)
        right = _現在観測決定seed方針(乱数種=999)

        left_choice = left.選ぶ(observation)
        right_choice = right.選ぶ(observation)

        self.assertEqual(left_choice, right_choice)

    def test_material_uses_canonical_json_compatible_values(self):
        observation = _observation()
        policy = _現在観測決定seed方針(乱数種=3)
        material = _seed_material(observation, policy)
        encoded_once = __import__("json").dumps(
            material, ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        encoded_twice = __import__("json").dumps(
            copy.deepcopy(material), ensure_ascii=False, sort_keys=True, separators=(",", ":")
        )
        self.assertEqual(encoded_once, encoded_twice)


if __name__ == "__main__":
    unittest.main()
