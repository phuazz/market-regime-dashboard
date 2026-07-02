"""Tests for the Lens 3 SMA computation and trend classifier.

Synthetic price paths are shaped so the SMA relationships under test are
unambiguous; each test also asserts the computed metrics so the scenario is
documented, not assumed.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from lens3 import classify_sma_trend, rolling_mean, slope_pct

PARAMS = {"slope_lookback_trading_days": 20, "flat_tolerance_pct": 0.1}


class TestRollingMean(unittest.TestCase):
    def test_values_and_warmup(self):
        means = rolling_mean([1.0, 2.0, 3.0, 4.0, 5.0], 3)
        self.assertEqual(means[:2], [None, None])
        self.assertAlmostEqual(means[2], 2.0)
        self.assertAlmostEqual(means[3], 3.0)
        self.assertAlmostEqual(means[4], 4.0)

    def test_slope_pct(self):
        series = [None] * 5 + [100.0] * 20 + [110.0]
        self.assertAlmostEqual(slope_pct(series, 20), 10.0)
        self.assertIsNone(slope_pct([100.0] * 10, 20))


class TestClassifySmaTrend(unittest.TestCase):
    def test_rising_market_is_benign(self):
        closes = [3000.0 + 5.0 * i for i in range(300)]
        status, _, metrics = classify_sma_trend(closes, PARAMS)
        self.assertEqual(status, "benign")
        self.assertGreater(metrics["sma50"], metrics["sma150"])

    def test_persistent_decline_is_elevated_with_context_note(self):
        # Long plateau then a deep persistent leg down: the 50-day sits well
        # below the 150-day and both slopes are flat or negative.
        closes = [5000.0] * 250 + [3500.0] * 100
        status, detail, metrics = classify_sma_trend(closes, PARAMS)
        self.assertEqual(status, "elevated")
        self.assertLess(metrics["sma50"], metrics["sma150"])
        self.assertLessEqual(metrics["sma50_slope_pct"], PARAMS["flat_tolerance_pct"])
        self.assertLessEqual(metrics["sma150_slope_pct"], PARAMS["flat_tolerance_pct"])
        self.assertIn("200-day", detail)  # close sits below the 200-day SMA

    def test_cross_without_slope_confirmation_is_watch(self):
        # Deep drop followed by a sharp 20-session recovery: the 50-day is
        # still below the 150-day, but its slope has turned positive.
        closes = [5000.0] * 250 + [3500.0] * 80 + [3500.0 + 50.0 * i for i in range(1, 21)]
        status, _, metrics = classify_sma_trend(closes, PARAMS)
        self.assertEqual(status, "watch")
        self.assertLess(metrics["sma50"], metrics["sma150"])
        self.assertGreater(metrics["sma50_slope_pct"], PARAMS["flat_tolerance_pct"])

    def test_insufficient_history_raises(self):
        with self.assertRaises(ValueError):
            classify_sma_trend([100.0] * 150, PARAMS)


if __name__ == "__main__":
    unittest.main()
