"""Threshold-boundary tests for the Lens 1 classifiers.

Each classifier is a pure function over (data, params) so these tests run
without network access. Boundary cases are tested on both sides.
"""
from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from lens1 import (
    classify_hy_oas,
    classify_labour,
    classify_lei,
    classify_pmi,
    classify_sahm,
    prior_year_same_month,
    three_month_average_rise,
    unpublished_yoy_note,
    yoy_percent_if_observed,
)

SAHM_PARAMS = {"watch_level": 0.35, "elevated_level": 0.50}
HY_PARAMS = {
    "watch_level": 4.0,
    "elevated_level": 5.5,
    "complacency_level": 3.0,
    "watch_rise_bp": 100,
    "elevated_rise_bp": 200,
}
PMI_PARAMS = {"watch_level": 50.0, "elevated_level": 48.0}
LEI_PARAMS = {"elevated_six_month_pct": -2.0}
LABOUR_PARAMS = {
    "watch_rise": 0.20,
    "elevated_rise": 0.35,
    "watch_payroll_3mo_avg_thousands": 75,
    "watch_uemp27ov_yoy_pct": 15,
    "watch_ccsa_26wk_pct": 5,
}


def healthy_labour_inputs() -> dict:
    return {
        "rise": 0.05,
        "payroll_3mo_avg_thousands": 150.0,
        "uemp27ov_yoy_pct": 2.0,
        "ccsa_26wk_pct": 1.0,
    }


class TestSahm(unittest.TestCase):
    def test_boundaries(self):
        self.assertEqual(classify_sahm(0.34, SAHM_PARAMS)[0], "benign")
        self.assertEqual(classify_sahm(0.35, SAHM_PARAMS)[0], "watch")
        self.assertEqual(classify_sahm(0.49, SAHM_PARAMS)[0], "watch")
        self.assertEqual(classify_sahm(0.50, SAHM_PARAMS)[0], "elevated")


class TestHyOas(unittest.TestCase):
    def test_tight_and_calm_is_benign_with_complacency_note(self):
        values = [2.8] * 100  # tight and flat
        status, detail, _ = classify_hy_oas(values, HY_PARAMS)
        self.assertEqual(status, "benign")
        self.assertIn("Complacency", detail)  # 2.8 is at or below 3.00

    def test_watch_at_level_boundary(self):
        self.assertEqual(classify_hy_oas([3.99] * 100, HY_PARAMS)[0], "benign")
        self.assertEqual(classify_hy_oas([4.00] * 100, HY_PARAMS)[0], "watch")

    def test_elevated_at_level_boundary(self):
        self.assertEqual(classify_hy_oas([5.49] * 100, HY_PARAMS)[0], "watch")
        self.assertEqual(classify_hy_oas([5.50] * 100, HY_PARAMS)[0], "elevated")

    def test_watch_by_widening_below_watch_level(self):
        values = [2.5] * 100
        values[-1] = 3.6  # +110 bp over 63 trading days, level still below 4.00
        status, _, stats = classify_hy_oas(values, HY_PARAMS)
        self.assertEqual(status, "watch")
        self.assertGreaterEqual(stats["rise_63d_bp"], 100)

    def test_elevated_by_widening_below_elevated_level(self):
        values = [2.5] * 100
        values[-1] = 4.7  # +220 bp over 63 trading days, level still below 5.50
        status, _, stats = classify_hy_oas(values, HY_PARAMS)
        self.assertEqual(status, "elevated")
        self.assertGreaterEqual(stats["rise_63d_bp"], 200)

    def test_short_history_has_no_widening_input(self):
        status, _, stats = classify_hy_oas([2.8] * 30, HY_PARAMS)
        self.assertEqual(status, "benign")
        self.assertIsNone(stats["rise_63d_bp"])


class TestPmi(unittest.TestCase):
    def test_expansion_is_benign(self):
        self.assertEqual(classify_pmi(53.9, 55.1, PMI_PARAMS)[0], "benign")

    def test_contraction_is_watch(self):
        self.assertEqual(classify_pmi(49.5, 51.0, PMI_PARAMS)[0], "watch")

    def test_deep_and_falling_is_elevated(self):
        self.assertEqual(classify_pmi(47.5, 50.1, PMI_PARAMS)[0], "elevated")

    def test_deep_but_rising_is_watch(self):
        self.assertEqual(classify_pmi(47.5, 47.0, PMI_PARAMS)[0], "watch")

    def test_deep_without_trend_history_is_watch(self):
        # Missing three-month history must not manufacture an elevated signal.
        self.assertEqual(classify_pmi(47.5, None, PMI_PARAMS)[0], "watch")


class TestLei(unittest.TestCase):
    def test_boundaries(self):
        self.assertEqual(classify_lei(0.2, LEI_PARAMS)[0], "benign")
        self.assertEqual(classify_lei(0.0, LEI_PARAMS)[0], "benign")
        self.assertEqual(classify_lei(-0.3, LEI_PARAMS)[0], "watch")
        self.assertEqual(classify_lei(-2.0, LEI_PARAMS)[0], "elevated")

    def test_missing_six_month_change_refuses_to_classify(self):
        with self.assertRaises(ValueError):
            classify_lei(None, LEI_PARAMS)


class TestLabour(unittest.TestCase):
    def test_healthy_is_benign(self):
        status, detail = classify_labour(healthy_labour_inputs(), LABOUR_PARAMS)
        self.assertEqual(status, "benign")
        self.assertEqual(
            detail,
            "Headline and internals are steady: unemployment rise +0.05 pp, payroll "
            "3-month average +150k, long-term unemployed +2% YoY, continued claims "
            "+1.0% over 26 weeks.",
        )

    def test_rise_boundary(self):
        inputs = healthy_labour_inputs()
        inputs["rise"] = 0.19
        self.assertEqual(classify_labour(inputs, LABOUR_PARAMS)[0], "benign")
        inputs["rise"] = 0.20
        self.assertEqual(classify_labour(inputs, LABOUR_PARAMS)[0], "watch")
        inputs["rise"] = 0.35
        self.assertEqual(classify_labour(inputs, LABOUR_PARAMS)[0], "elevated")

    def test_negative_payrolls_is_elevated(self):
        inputs = healthy_labour_inputs()
        inputs["payroll_3mo_avg_thousands"] = -5.0
        self.assertEqual(classify_labour(inputs, LABOUR_PARAMS)[0], "elevated")

    def test_soft_internals_require_both_conditions(self):
        inputs = healthy_labour_inputs()
        inputs["uemp27ov_yoy_pct"] = 20.0
        inputs["ccsa_26wk_pct"] = 4.0  # claims steady: no watch
        self.assertEqual(classify_labour(inputs, LABOUR_PARAMS)[0], "benign")
        inputs["ccsa_26wk_pct"] = 6.0  # both soft: watch
        status, detail = classify_labour(inputs, LABOUR_PARAMS)
        self.assertEqual(status, "watch")
        self.assertEqual(
            detail,
            "Watch: internals softening (long-term unemployed +20% YoY, "
            "continued claims +6.0% over 26 weeks).",
        )

    def test_missing_yoy_on_benign_path_does_not_format_none(self):
        # 7 Nov 2026 refresh: rise 0.0 and payroll +137k are inside the
        # benign lines, and UEMP27OV has no 2025-10-01 observation.
        inputs = healthy_labour_inputs()
        inputs["rise"] = 0.0
        inputs["payroll_3mo_avg_thousands"] = 137.0
        inputs["uemp27ov_yoy_pct"] = None
        inputs["ccsa_26wk_pct"] = -2.3
        status, detail = classify_labour(inputs, LABOUR_PARAMS)
        self.assertEqual(status, "benign")
        self.assertEqual(
            detail,
            "Headline is steady: unemployment rise +0.00 pp, payroll "
            "3-month average +137k. Available internals: continued claims "
            "-2.3% over 26 weeks. Long-term unemployed year-over-year change "
            "is unavailable, so that input is omitted from the internals check.",
        )
        self.assertNotIn("None", detail)

    def test_missing_claims_on_benign_path_keeps_known_yoy(self):
        inputs = healthy_labour_inputs()
        inputs["ccsa_26wk_pct"] = None
        status, detail = classify_labour(inputs, LABOUR_PARAMS)
        self.assertEqual(status, "benign")
        self.assertIn("long-term unemployed +2% YoY", detail)
        self.assertIn("Continued claims change over 26 weeks is unavailable", detail)
        self.assertNotIn("None", detail)

    def test_both_internals_missing_on_benign_path(self):
        inputs = healthy_labour_inputs()
        inputs["uemp27ov_yoy_pct"] = None
        inputs["ccsa_26wk_pct"] = None
        status, detail = classify_labour(inputs, LABOUR_PARAMS)
        self.assertEqual(status, "benign")
        self.assertEqual(
            detail,
            "Headline is steady: unemployment rise +0.05 pp, payroll "
            "3-month average +150k. Long-term unemployed year-over-year change "
            "and continued claims change over 26 weeks are unavailable, so those "
            "inputs are omitted from the internals check.",
        )

    def test_one_soft_internal_and_one_missing_stays_benign(self):
        inputs = healthy_labour_inputs()
        inputs["uemp27ov_yoy_pct"] = 20.0
        inputs["ccsa_26wk_pct"] = None
        status, detail = classify_labour(inputs, LABOUR_PARAMS)
        self.assertEqual(status, "benign")
        self.assertIn("long-term unemployed +20% YoY", detail)
        self.assertNotIn("softening", detail)

        inputs = healthy_labour_inputs()
        inputs["uemp27ov_yoy_pct"] = None
        inputs["ccsa_26wk_pct"] = 6.0
        status, detail = classify_labour(inputs, LABOUR_PARAMS)
        self.assertEqual(status, "benign")
        self.assertIn("continued claims +6.0% over 26 weeks", detail)
        self.assertNotIn("softening", detail)

    def test_missing_yoy_does_not_change_watch_or_elevated_branches(self):
        watch = healthy_labour_inputs()
        watch["uemp27ov_yoy_pct"] = None
        watch["payroll_3mo_avg_thousands"] = 74.0
        status, detail = classify_labour(watch, LABOUR_PARAMS)
        self.assertEqual(status, "watch")
        self.assertIn("payroll 3-month average +74k", detail)
        self.assertIn("unavailable", detail)

        rise_watch = healthy_labour_inputs()
        rise_watch["uemp27ov_yoy_pct"] = None
        rise_watch["rise"] = 0.20
        self.assertEqual(classify_labour(rise_watch, LABOUR_PARAMS)[0], "watch")

        elevated = healthy_labour_inputs()
        elevated["uemp27ov_yoy_pct"] = None
        elevated["payroll_3mo_avg_thousands"] = -5.0
        status, detail = classify_labour(elevated, LABOUR_PARAMS)
        self.assertEqual(status, "elevated")
        self.assertIn("(-5k)", detail)
        self.assertIn("unavailable", detail)
        self.assertNotIn("None", detail)

        rise_elevated = healthy_labour_inputs()
        rise_elevated["ccsa_26wk_pct"] = None
        rise_elevated["rise"] = 0.35
        status, detail = classify_labour(rise_elevated, LABOUR_PARAMS)
        self.assertEqual(status, "elevated")
        self.assertIn("Continued claims change over 26 weeks is unavailable", detail)

    def test_payroll_boundary_with_missing_yoy(self):
        inputs = healthy_labour_inputs()
        inputs["uemp27ov_yoy_pct"] = None
        inputs["payroll_3mo_avg_thousands"] = 75.0
        self.assertEqual(classify_labour(inputs, LABOUR_PARAMS)[0], "benign")
        inputs["payroll_3mo_avg_thousands"] = 74.0
        self.assertEqual(classify_labour(inputs, LABOUR_PARAMS)[0], "watch")

    def test_complete_data_watch_and_elevated_text_unchanged(self):
        watch = healthy_labour_inputs()
        watch["payroll_3mo_avg_thousands"] = 50.0
        self.assertEqual(
            classify_labour(watch, LABOUR_PARAMS)[1],
            "Watch: payroll 3-month average +50k.",
        )
        elevated = healthy_labour_inputs()
        elevated["rise"] = 0.35
        self.assertEqual(
            classify_labour(elevated, LABOUR_PARAMS)[1],
            "Unemployment rise of +0.35 pp or negative three-month average payroll "
            "change (+150k) signals a turning labour market.",
        )

    def test_three_month_average_rise(self):
        values = [4.0] * 13 + [4.1, 4.2]
        self.assertAlmostEqual(three_month_average_rise(values), 0.10, places=2)


class TestLabourYearOverYear(unittest.TestCase):
    def test_year_boundary(self):
        # January maps to January of the previous year.
        self.assertEqual(prior_year_same_month(date(2026, 1, 1)), date(2025, 1, 1))
        self.assertEqual(prior_year_same_month(date(2026, 1, 31)), date(2025, 1, 31))

    def test_month_boundary(self):
        # March follows the February month boundary. 2026 is not a leap year.
        self.assertEqual(prior_year_same_month(date(2026, 3, 1)), date(2025, 3, 1))
        self.assertEqual(prior_year_same_month(date(2026, 3, 31)), date(2025, 3, 31))

    def test_leap_day_clamps_to_february_28(self):
        # relativedelta clamps 29 February onto 28 February in a non-leap year.
        self.assertEqual(prior_year_same_month(date(2024, 2, 29)), date(2023, 2, 28))

    def test_missing_year_ago_month_is_not_filled_from_neighbours(self):
        # The published gap: 2025-10-01 is blank, with September and November present.
        dates = ["2025-09-01", "2025-11-01", "2026-10-01"]
        values = [100.0, 200.0, 150.0]
        self.assertIsNone(yoy_percent_if_observed(dates, values))
        self.assertEqual(
            unpublished_yoy_note("UEMP27OV", "2025-10-01", None),
            " No UEMP27OV observation is published for 2025-10-01, so no "
            "year-over-year change is calculated.",
        )

    def test_year_boundary_series_uses_january_only(self):
        dates = ["2024-12-01", "2025-01-01", "2025-02-01", "2026-01-01"]
        values = [50.0, 80.0, 90.0, 100.0]
        self.assertEqual(yoy_percent_if_observed(dates, values), 25.0)

    def test_month_boundary_series_does_not_use_february_or_april(self):
        dates = ["2025-02-01", "2025-04-01", "2026-03-01"]
        values = [100.0, 300.0, 200.0]
        self.assertIsNone(yoy_percent_if_observed(dates, values))
        present = ["2025-02-01", "2025-03-01", "2025-04-01", "2026-03-01"]
        values = [100.0, 160.0, 300.0, 200.0]
        self.assertEqual(yoy_percent_if_observed(present, values), 25.0)

    def test_published_year_ago_month_note_is_empty(self):
        self.assertEqual(unpublished_yoy_note("UEMP27OV", "2025-09-01", 8.2), "")


if __name__ == "__main__":
    unittest.main()
