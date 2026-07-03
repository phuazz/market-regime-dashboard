"""Boundary tests for the Lens 2 classifiers and the composite summary."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from lens2 import (
    classify_aaii,
    classify_confidence,
    classify_ipo,
    classify_naaim,
    classify_nfci,
    classify_pe,
    classify_rule_of_20,
    classify_value_growth,
    summarise,
)


class TestClassifiers(unittest.TestCase):
    def test_confidence_percentile_boundary(self):
        params = {"trigger_percentile": 75}
        self.assertEqual(classify_confidence(74.9, params)[0], "quiet")
        self.assertEqual(classify_confidence(75.0, params)[0], "triggered")

    def test_aaii_decile_and_eased(self):
        params = {"eased_below_pp": 0}
        self.assertEqual(classify_aaii(28.3, 28.3, params)[0], "triggered")
        self.assertEqual(classify_aaii(15.0, 28.3, params)[0], "quiet")
        self.assertEqual(classify_aaii(-0.1, 28.3, params)[0], "eased")
        self.assertEqual(classify_aaii(0.0, 28.3, params)[0], "quiet")

    def test_naaim_boundary(self):
        params = {"trigger_level": 90}
        self.assertEqual(classify_naaim(89.9, params)[0], "quiet")
        self.assertEqual(classify_naaim(90.0, params)[0], "triggered")

    def test_pe_percentile_boundary(self):
        params = {"trigger_percentile": 90}
        self.assertEqual(classify_pe(89.9, params)[0], "quiet")
        self.assertEqual(classify_pe(90.0, params)[0], "triggered")

    def test_rule_of_20_requires_both_conditions(self):
        params = {"fair_value_sum": 20, "trigger_percentile": 80}
        self.assertEqual(classify_rule_of_20(36.3, 95.0, params)[0], "triggered")
        self.assertEqual(classify_rule_of_20(21.0, 60.0, params)[0], "quiet")  # above 20, tail no
        self.assertEqual(classify_rule_of_20(18.0, 95.0, params)[0], "quiet")  # tail yes, level no

    def test_value_growth_boundaries(self):
        params = {"trigger_pp": 10, "eased_below_pp": 0}
        self.assertEqual(classify_value_growth(10.0, params)[0], "triggered")
        self.assertEqual(classify_value_growth(9.9, params)[0], "quiet")
        self.assertEqual(classify_value_growth(-0.1, params)[0], "eased")

    def test_nfci_loose_tail(self):
        params = {"trigger_percentile": 20}
        self.assertEqual(classify_nfci(-0.6, 20.0, params)[0], "triggered")
        self.assertEqual(classify_nfci(-0.5, 30.0, params)[0], "quiet")

    def test_ipo_percentile_of_prior_years(self):
        params = {"trigger_percentile": 80}
        prior = [18.8, 35.5, 46.9, 46.3, 78.2, 142.4, 7.7, 19.5, 29.6, 44.0]
        self.assertEqual(classify_ipo(229.4, prior, params)[0], "triggered")  # above all priors
        self.assertEqual(classify_ipo(30.0, prior, params)[0], "quiet")


def gauge(status: str, in_composite: bool = True) -> dict:
    return {"status": status, "in_composite": in_composite}


class TestSummarise(unittest.TestCase):
    def test_share_counts_only_composite_gauges(self):
        indicators = [
            gauge("triggered"), gauge("triggered"), gauge("quiet"), gauge("eased"),
            gauge("context", in_composite=False),
        ]
        composite = summarise(indicators, None)
        self.assertEqual(composite["gauge_count"], 4)
        self.assertEqual(composite["triggered_count"], 2)
        self.assertEqual(composite["eased_count"], 1)
        self.assertEqual(composite["share_pct"], 50.0)
        self.assertEqual(composite["alarm_state"], "pending")

    def test_alarm_states(self):
        indicators = [gauge("triggered")] * 3 + [gauge("quiet")]
        self.assertEqual(summarise(indicators, 75.0)["alarm_state"], "at_or_above")
        self.assertEqual(summarise(indicators, 80.0)["alarm_state"], "below")

    def test_empty_composite_is_safe(self):
        composite = summarise([gauge("context", in_composite=False)], None)
        self.assertEqual(composite["gauge_count"], 0)
        self.assertEqual(composite["share_pct"], 0.0)


if __name__ == "__main__":
    unittest.main()
