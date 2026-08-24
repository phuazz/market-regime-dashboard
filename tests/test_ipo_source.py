"""Offline tests for the Renaissance Capital IPO stats scraper (rewritten 2026-08-24).

The previous parser matched series with a regex that required "data" before
"name" inside a series object. The annual chart writes them in that order; the
per-year monthly charts write "name" first. When the page began emitting the
monthly charts that way the monthly series stopped being found, `pick("Number
of IPOs", 12)` raised, and build_ipo failed on every monthly-group run from
2026-08-10 onwards.

The rewrite parses each `var ChartOptions = {...}` object as JSON, so key order
is irrelevant, and pins two things the length-matching approach left to luck:

  * the monthly chart is bound to the current year by its render target. The
    page carries the prior year's monthly chart as well, also twelve points
    long, and "first twelve-point series wins" selected the right one only
    because 2026 is printed above 2025;
  * the monthly counts must sum to the annual count for that year. Taking the
    wrong year's chart would shift months_elapsed and therefore the annualised
    issuance pace -- the number the trigger is evaluated on -- while producing
    nothing that looks wrong on the card.

The fixture reproduces the real page's structure, including the differing key
order between the two charts and the braces inside "pointFormat" that a naive
brace scan would trip on. Values are the real 2026 and 2025 series as published
on 2026-08-24. No network.
"""
from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from sources import sentiment
from sources.scrape import ScrapeError

YEARS = [2016, 2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024, 2025, 2026]
PROCEEDS = [18.8, 35.5, 46.9, 46.3, 78.2, 142.4, 7.7, 19.5, 29.6, 44.0, 145.8]
COUNTS = [105, 160, 193, 163, 221, 397, 71, 109, 150, 202, 104]
MONTHLY_2026 = [11, 15, 8, 15, 14, 19, 11, 11, 0, 0, 0, 0]  # 104 through August
MONTHLY_2025 = [17, 18, 18, 16, 12, 16, 26, 19, 19, 22, 11, 8]  # 202 full year

MONTH_NAMES = (
    '"January","February","March","April","May","June",'
    '"July","August","September","October","November","December"'
)
CREDITS = '"credits":{"text":"www.renaissancecapital.com as of 08/24/2026"}'
# The tooltip braces are real and sit inside a string value; the config scanner
# has to stay inside the string rather than counting them as nesting.
TOOLTIP = '"tooltip":{"pointFormat":"{series.name}: <b>{point.y}</b><br/>","shared":true}'


def _points(values) -> str:
    return ",".join('{"y":%.1f}' % v for v in values)


# The annual chart writes "data" before "name".
ANNUAL_CHART = (
    "<script>function createChartchart2() {var ChartOptions = {"
    + TOOLTIP
    + ',"xAxis":[{"categories":['
    + ",".join('"%d"' % y for y in YEARS)
    + "]}],"
    + CREDITS
    + ',"chart":{"renderTo":"chart2"},"series":['
    + '{"data":[' + _points(PROCEEDS) + '],"type":"column","name":"Proceeds in Billions (US$)"},'
    + '{"data":[' + _points(COUNTS) + '],"type":"spline","name":"Number of IPOs"}'
    + "]};Highcharts.chart(\"chart2\",ChartOptions);}</script>"
)


def _monthly_chart(year: int, values) -> str:
    """A per-year monthly chart, writing "name" before "data" as the page does."""
    return (
        "<script>function createChartpricings%d() {var ChartOptions = {" % year
        + '"xAxis":[{"categories":[' + MONTH_NAMES + "]}],"
        + CREDITS
        + ',"chart":{"renderTo":"pricings%dChart"},"title":{"text":"%d IPOs"},' % (year, year)
        + '"series":[{"name":"Number of IPOs","data":[' + _points(values) + '],"type":"column"}]'
        + '};Highcharts.chart("pricings%dChart",ChartOptions);}</script>' % year
    )


PAGE = ANNUAL_CHART + _monthly_chart(2026, MONTHLY_2026) + _monthly_chart(2025, MONTHLY_2025)


class TestFetchRenaissanceIpoStats(unittest.TestCase):
    def _fetch(self, page: str) -> dict:
        with mock.patch.object(sentiment, "fetch_text", return_value=page):
            return sentiment.fetch_renaissance_ipo_stats()

    def test_parses_name_before_data_ordering(self):
        got = self._fetch(PAGE)
        self.assertEqual(got["current_year"], 2026)
        self.assertEqual(got["ytd_proceeds_bn"], 145.8)
        self.assertEqual(got["ytd_count"], 104)
        self.assertEqual(got["months_elapsed"], 8)
        self.assertEqual(got["as_of"], "2026-08-24")

    def test_annual_history_covers_every_year_on_the_axis(self):
        got = self._fetch(PAGE)
        self.assertEqual(sorted(got["annual_proceeds_bn"]), YEARS)
        self.assertEqual(got["annual_proceeds_bn"][2021], 142.4)
        self.assertEqual(got["annual_counts"][2022], 71)

    def test_monthly_chart_is_bound_to_the_current_year(self):
        """A full prior year in the same page must not set months_elapsed to 12."""
        reordered = ANNUAL_CHART + _monthly_chart(2025, MONTHLY_2025) + _monthly_chart(2026, MONTHLY_2026)
        self.assertEqual(self._fetch(reordered)["months_elapsed"], 8)

    def test_missing_current_year_monthly_chart_raises(self):
        page = ANNUAL_CHART + _monthly_chart(2025, MONTHLY_2025)
        with self.assertRaises(ScrapeError) as ctx:
            self._fetch(page)
        self.assertIn("pricings2026Chart", str(ctx.exception))

    def test_monthly_total_must_match_the_annual_count(self):
        """The cross-check that catches a wrong-year or wrong-series selection."""
        wrong = ANNUAL_CHART + _monthly_chart(2026, MONTHLY_2025) + _monthly_chart(2025, MONTHLY_2025)
        with self.assertRaises(ScrapeError) as ctx:
            self._fetch(wrong)
        self.assertIn("mismatch", str(ctx.exception))

    def test_short_month_axis_raises(self):
        page = ANNUAL_CHART + _monthly_chart(2026, MONTHLY_2026[:6]) + _monthly_chart(2025, MONTHLY_2025)
        with self.assertRaises(ScrapeError) as ctx:
            self._fetch(page)
        self.assertIn("expected 12", str(ctx.exception))

    def test_no_chart_config_raises(self):
        with self.assertRaises(ScrapeError) as ctx:
            self._fetch("<html><body>The IPO Center is temporarily unavailable.</body></html>")
        self.assertIn("no Highcharts config", str(ctx.exception))

    def test_january_run_reports_one_month_elapsed(self):
        """Year boundary: a January-only year is one month elapsed, not zero."""
        january_only = [7] + [0] * 11
        counts = COUNTS[:-1] + [7]
        annual = ANNUAL_CHART.replace(_points(COUNTS), _points(counts))
        page = annual + _monthly_chart(2026, january_only) + _monthly_chart(2025, MONTHLY_2025)
        self.assertEqual(self._fetch(page)["months_elapsed"], 1)

    def test_month_boundary_zero_issuance_month_does_not_end_the_count(self):
        """A blank month mid-year must not truncate the elapsed count."""
        with_gap = [11, 0, 8, 15, 14, 19, 11, 11, 0, 0, 0, 0]
        counts = COUNTS[:-1] + [89]
        annual = ANNUAL_CHART.replace(_points(COUNTS), _points(counts))
        page = annual + _monthly_chart(2026, with_gap) + _monthly_chart(2025, MONTHLY_2025)
        self.assertEqual(self._fetch(page)["months_elapsed"], 8)


if __name__ == "__main__":
    unittest.main()
