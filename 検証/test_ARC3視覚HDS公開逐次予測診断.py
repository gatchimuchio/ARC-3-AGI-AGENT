from collections import Counter
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from ARC3視覚HDS公開逐次予測診断 import _majority, _record_response


class PrequentialMajorityContractTests(unittest.TestCase):
    def test_current_response_never_enters_its_own_majority_comparator(self):
        previous, counts = Counter(), Counter()
        _record_response(previous, {"盤面変化"}, None, "盤面変化", counts)
        self.assertEqual(counts["forecast_covered_without_previous_majority"], 1)
        self.assertEqual(counts["same_covered_steps_with_majority"], 0)
        _record_response(previous, {"可視変化なし"}, None, "可視変化なし", counts)
        self.assertEqual(counts["same_covered_steps_with_majority"], 1)
        self.assertEqual(counts["target_matches_on_majority_comparable_steps"], 1)
        self.assertEqual(counts["majority_matches_on_same_covered_steps"], 0)
        self.assertEqual(previous, Counter({"盤面変化": 1, "可視変化なし": 1}))

    def test_uncovered_responses_enter_future_majority_without_entering_comparison(self):
        previous, counts = Counter(), Counter()
        _record_response(previous, set(), "no_active_target_rule", "GAME_OVER", counts)
        self.assertEqual(_majority(previous), ("GAME_OVER", False))
        self.assertEqual(counts["same_covered_steps_with_majority"], 0)
        _record_response(previous, {"盤面変化", "GAME_OVER"}, None, "盤面変化", counts)
        self.assertEqual(counts["target_qualified_multiple_values"], 1)
        self.assertEqual(counts["target_qualified_unique_forecasts"], 0)


if __name__ == "__main__":
    unittest.main()
