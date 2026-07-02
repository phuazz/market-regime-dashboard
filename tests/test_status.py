"""Threshold-boundary tests for the Lens 1 classifiers.

Each classifier is a pure function over (data, params) so these tests run
without network access. Boundary cases are tested on both sides.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from lens1 import (
    classify_hy_oas,
    classify_labour,
    classify_lei,
    classify_pmi,
    classify_sahm,
    three_month_average_rise,
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
        self.assertEqual(classify_labour(healthy_labour_inputs(), LABOUR_PARAMS)[0], "benign")

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
        self.assertEqual(classify_labour(inputs, LABOUR_PARAMS)[0], "watch")

    def test_three_month_average_rise(self):
        values = [4.0] * 13 + [4.1, 4.2]
        self.assertAlmostEqual(three_month_average_rise(values), 0.10, places=2)


if __name__ == "__main__":
    unittest.main()
