from __future__ import annotations

import unittest

from 検証.ARC3Frame特徴crossGameTransfer import _leave_one_environment_out
from 検証.ARC3Frame特徴crossGameTransfer import (
    _MAX_TRAINING_SAMPLES_PER_ENVIRONMENT,
)
from 検証.ARC3Frame特徴crossGameTransfer import _evenly_spaced


class CrossGameTransferTests(unittest.TestCase):
    def test_leave_one_out各foldのheldout標本を学習から除く(self):
        environments = [
            [{"marker": 0}, {"marker": 0}],
            [{"marker": 1}],
            [{"marker": 2}, {"marker": 2}, {"marker": 2}],
        ]

        folds = _leave_one_environment_out(environments)

        self.assertEqual(len(folds), 3)
        for heldout_index, (training, heldout) in enumerate(folds):
            self.assertEqual({item["marker"] for item in heldout}, {heldout_index})
            self.assertNotIn(heldout_index, {item["marker"] for item in training})
            self.assertEqual(
                len(training),
                sum(
                    min(len(group), _MAX_TRAINING_SAMPLES_PER_ENVIRONMENT)
                    for index, group in enumerate(environments)
                    if index != heldout_index
                ),
            )

    def test_訓練標本は時系列全体へ均等配置する(self):
        samples = [{"step": index} for index in range(101)]

        selected = _evenly_spaced(samples, 15)

        self.assertEqual(len(selected), 15)
        self.assertEqual(selected[0]["step"], 0)
        self.assertEqual(selected[-1]["step"], 100)
        self.assertEqual(
            sorted({item["step"] for item in selected}), [item["step"] for item in selected]
        )

    def test一環境のみではfoldを構成しない(self):
        with self.assertRaises(ValueError):
            _leave_one_environment_out([[{"marker": 1}]])


if __name__ == "__main__":
    unittest.main()
