"""Date edge-case tests for the yield-curve status logic.

CLAUDE.md requires at least one month-boundary and one year-boundary test for
any date logic. Both live here, plus a leap-day clamping test, so the
12-month elevated window cannot drift silently.

Synthetic series use consecutive calendar days generated with
datetime.timedelta — the date library handles month and year rollovers.
Python datetime months are 1-indexed (January = 1).
"""
from __future__ import annotations

import sys
import unittest
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from update_data import classify_yield_curve, find_sustained_inversions


def days_ending(end: date, count: int) -> list[date]:
    """Return ``count`` consecutive calendar days ending at ``end``."""
    return [end - timedelta(days=offset) for offset in range(count - 1, -1, -1)]


def series(segments: list[tuple[date, int, float]]) -> tuple[list[str], list[float | None]]:
    """Build (dates, values) from (segment_end, n_days, value) tuples."""
    dates: list[str] = []
    values: list[float | None] = []
    for end, count, value in segments:
        for day in days_ending(end, count):
            dates.append(day.isoformat())
            values.append(value)
    return dates, values


PARAMS = {"sustained_inversion_min_observations": 60, "elevated_window_months": 12}


class TestSustainedInversions(unittest.TestCase):
    def test_short_blip_is_not_sustained(self):
        dates, values = series(
            [
                (date(2025, 6, 1), 100, 0.5),
                (date(2025, 6, 20), 19, -0.1),  # 19 negative observations only
                (date(2026, 7, 1), 100, 0.6),
            ]
        )
        self.assertEqual(find_sustained_inversions(dates, values, 60), [])
        status, _ = classify_yield_curve(dates, values, PARAMS)
        self.assertEqual(status, "benign")

    def test_missing_observations_do_not_break_a_run(self):
        dates, values = series(
            [
                (date(2025, 1, 31), 40, -0.2),
            ]
        )
        dates.append(date(2025, 2, 1).isoformat())
        values.append(None)  # holiday inside the run
        more_dates, more_values = series([(date(2025, 3, 15), 40, -0.2)])
        dates += more_dates
        values += more_values
        episodes = find_sustained_inversions(dates, values, 60)
        self.assertEqual(len(episodes), 1)
        self.assertEqual(episodes[0][1], "2025-03-15")


class TestClassifyYieldCurve(unittest.TestCase):
    def test_watch_when_currently_inverted(self):
        dates, values = series([(date(2026, 7, 1), 90, -0.15)])
        status, _ = classify_yield_curve(dates, values, PARAMS)
        self.assertEqual(status, "watch")

    def test_month_boundary_window_is_inclusive_then_expires(self):
        # Sustained inversion ends 2025-01-31. The 12-month window closes at
        # 2026-01-31 inclusive (month boundary: 31 January maps to 31 January).
        inversion = (date(2025, 1, 31), 70, -0.3)

        at_boundary = series([inversion, (date(2026, 1, 31), 300, 0.4)])
        status, _ = classify_yield_curve(*at_boundary, PARAMS)
        self.assertEqual(status, "elevated")

        past_boundary = series([inversion, (date(2026, 2, 1), 301, 0.4)])
        status, _ = classify_yield_curve(*past_boundary, PARAMS)
        self.assertEqual(status, "benign")

    def test_year_boundary_window(self):
        # Sustained inversion ends 2024-12-31; the window crosses the year
        # boundary and closes at 2025-12-31 inclusive.
        inversion = (date(2024, 12, 31), 70, -0.3)

        inside = series([inversion, (date(2025, 12, 31), 300, 0.2)])
        status, _ = classify_yield_curve(*inside, PARAMS)
        self.assertEqual(status, "elevated")

        outside = series([inversion, (date(2026, 1, 1), 301, 0.2)])
        status, _ = classify_yield_curve(*outside, PARAMS)
        self.assertEqual(status, "benign")

    def test_leap_day_window_clamps_to_february_end(self):
        # Sustained inversion ends on leap day 2024-02-29. relativedelta
        # clamps 2024-02-29 + 12 months to 2025-02-28, so 2025-02-28 is the
        # last elevated day and 2025-03-01 falls outside the window.
        inversion = (date(2024, 2, 29), 70, -0.3)

        inside = series([inversion, (date(2025, 2, 28), 300, 0.3)])
        status, _ = classify_yield_curve(*inside, PARAMS)
        self.assertEqual(status, "elevated")

        outside = series([inversion, (date(2025, 3, 1), 301, 0.3)])
        status, _ = classify_yield_curve(*outside, PARAMS)
        self.assertEqual(status, "benign")


if __name__ == "__main__":
    unittest.main()
