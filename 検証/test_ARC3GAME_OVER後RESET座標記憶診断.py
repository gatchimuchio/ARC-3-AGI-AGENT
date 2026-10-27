import unittest

from 検証.ARC3GAME_OVER後RESET座標記憶診断 import _summarize


class GameOverResetCoordinateCacheDiagnosticTest(unittest.TestCase):
    def test_再訪割合とseed数からablation適格性を判定する(self):
        samples = [
            {"seed": 7, "cache_hit": True, "cached_fraction": 0.1},
            {"seed": 7, "cache_hit": True, "cached_fraction": 0.2},
            {"seed": 7, "cache_hit": True, "cached_fraction": 0.3},
            {"seed": 7, "cache_hit": True, "cached_fraction": 0.4},
            {"seed": 7, "cache_hit": True, "cached_fraction": 0.5},
            {"seed": 31, "cache_hit": True, "cached_fraction": 0.3},
            {"seed": 31, "cache_hit": True, "cached_fraction": 0.4},
            {"seed": 31, "cache_hit": True, "cached_fraction": 0.5},
            {"seed": 31, "cache_hit": True, "cached_fraction": 0.6},
            {"seed": 31, "cache_hit": True, "cached_fraction": 0.7},
        ]

        result = _summarize(samples)

        self.assertEqual(result["reset_revisits"], 10)
        self.assertEqual(result["same_board_with_prior_coordinate_cache"], 10)
        self.assertEqual(result["cache_hit_seed_count"], 2)
        self.assertEqual(result["median_cached_coordinate_fraction_on_hits"], 0.4)
        self.assertTrue(result["ablation_preconditions"]["at_least_10_cache_hits_across_two_seeds"])
        self.assertTrue(
            result["ablation_preconditions"]["median_cached_fraction_at_least_20_percent"]
        )
        self.assertEqual(
            result["per_seed_summary"][0]["cache_hit_events"],
            "suppressed (<10)",
        )

    def test_少数再訪ではcache割合を出さず適格化しない(self):
        samples = [
            {"seed": 7, "cache_hit": True, "cached_fraction": 0.8},
            {"seed": 7, "cache_hit": True, "cached_fraction": 0.8},
            {"seed": 31, "cache_hit": False, "cached_fraction": 0.0},
        ]

        result = _summarize(samples)

        self.assertEqual(result["same_board_with_prior_coordinate_cache"], 2)
        self.assertFalse(
            result["ablation_preconditions"]["at_least_10_cache_hits_across_two_seeds"]
        )
        self.assertEqual(result["per_seed_summary"][0]["cache_hit_events"], "suppressed (<10)")
        self.assertNotIn(
            "median_cached_coordinate_fraction",
            result["per_seed_summary"][0],
        )

    def test_cache_hitなしなら割合をnullにする(self):
        result = _summarize([{"seed": 73, "cache_hit": False, "cached_fraction": 0.0}])

        self.assertIsNone(result["median_cached_coordinate_fraction_on_hits"])
        self.assertFalse(
            result["ablation_preconditions"]["median_cached_fraction_at_least_20_percent"]
        )


if __name__ == "__main__":
    unittest.main()
