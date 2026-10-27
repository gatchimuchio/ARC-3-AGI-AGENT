from collections import Counter
from pathlib import Path
import sys
from types import SimpleNamespace
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ARC3HDS対象経路公開逐次比較 import _Collector


class PairedPastMajorityTests(unittest.TestCase):
    def test_two_arms_use_identical_previous_labels_and_add_current_label_once(self):
        collector = _Collector()
        collector.current = SimpleNamespace(
            pending={"whole": {"native_status": "断定保留"}, "scoped": {"native_status": "出力"}},
            runtime=SimpleNamespace(_target_forecast=lambda result: (None, {"可視変化なし"})),
        )
        previous, whole = Counter({"盤面変化": 1}), Counter()
        collector.score(previous, {"盤面変化"}, None, "可視変化なし", whole)
        self.assertEqual(previous, Counter({"盤面変化": 1, "可視変化なし": 1}))
        self.assertEqual(whole["same_covered_steps_with_majority"], 1)
        self.assertEqual(collector.scoped_counts["same_covered_steps_with_majority"], 1)
        self.assertEqual(whole["majority_matches_on_same_covered_steps"], 0)
        self.assertEqual(collector.scoped_counts["majority_matches_on_same_covered_steps"], 0)
        self.assertEqual(whole["target_unique_matches"], 0)
        self.assertEqual(collector.scoped_counts["target_unique_matches"], 1)
        self.assertEqual(collector.pairs["identical_strictly_previous_majority_counter_steps"], 1)

    def test_first_response_is_not_available_to_either_arm_majority(self):
        collector = _Collector()
        collector.current = SimpleNamespace(
            pending={"whole": {"native_status": "断定保留"}, "scoped": {"native_status": "出力"}},
            runtime=SimpleNamespace(_target_forecast=lambda result: (None, {"盤面変化"})),
        )
        previous, whole = Counter(), Counter()
        collector.score(previous, {"盤面変化"}, None, "盤面変化", whole)
        self.assertEqual(previous.total(), 1)
        self.assertEqual(whole["forecast_covered_without_previous_majority"], 1)
        self.assertEqual(collector.scoped_counts["forecast_covered_without_previous_majority"], 1)
        self.assertEqual(collector.pairs["both_covered_with_previous_majority"], 0)


if __name__ == "__main__":
    unittest.main()
