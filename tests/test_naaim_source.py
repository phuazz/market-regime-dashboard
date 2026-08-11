"""Offline tests for the NAAIM exposure scraper (rewritten 2026-08-11).

The previous implementation anchored on the phrase "Exposure Index number is"
on naaim.org. NAAIM migrated the number into widgets served from
index.naaim.org, that phrase vanished, and build_naaim failed every scheduled
run from at least 2026-08-04 while the dashboard silently retained a previous
value for the row. Nothing noticed, because the daily workflow publishes what
succeeded and exits 1, and no one was reading the red.

Two behaviours are pinned here, and they must stay distinct:

  * a real dated reading inside the freshness budget parses and carries its
    own week-ending date -- the old code returned as_of=None and the builder
    stamped collection time instead, which is how a value of unknown vintage
    came to be displayed as though current;
  * a feed whose newest row is beyond the budget raises, and the message says
    STALE rather than "layout changed". They are different faults: one is a
    parser to repair, the other a sourcing decision for the operator.

The fixture is a trimmed copy of the real table markup. No network.
"""
from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from sources import sentiment
from sources.scrape import ScrapeError

TABLE_HTML = """
<table><thead><tr><th>Date</th><th>NAAIM Number</th><th>Bearish</th></tr></thead>
<tbody>
<tr><td>04/15/2026</td><td>79.49</td><td>-200</td></tr>
<tr><td>04/22/2026</td><td>94.15</td><td>0</td></tr>
<tr><td>04/29/2026</td><td>93.79</td><td>-50</td></tr>
</tbody></table>
"""


def _one_row(us_date: str, value: str) -> str:
    """Table markup with a single dated row, for unambiguous boundary cases."""
    return (
        "<table><tbody>"
        f"<tr><td>{us_date}</td><td>{value}</td><td>0</td></tr>"
        "</tbody></table>"
    )


class TestFetchNaaim(unittest.TestCase):
    def _patch(self, html):
        return mock.patch.object(sentiment, "fetch_text", return_value=html)

    def test_parses_newest_row_with_its_own_date(self):
        with self._patch(TABLE_HTML):
            got = sentiment.fetch_naaim(today=date(2026, 5, 6))
        self.assertEqual(got, {"exposure": 93.79, "as_of": "2026-04-29"})

    def test_newest_row_wins_regardless_of_document_order(self):
        shuffled = TABLE_HTML.replace(
            "<tr><td>04/29/2026</td><td>93.79</td><td>-50</td></tr>", ""
        ).replace(
            "<tbody>", "<tbody><tr><td>04/29/2026</td><td>93.79</td><td>-50</td></tr>"
        )
        with self._patch(shuffled):
            got = sentiment.fetch_naaim(today=date(2026, 5, 6))
        self.assertEqual(got["as_of"], "2026-04-29")

    def test_stale_feed_raises_and_says_stale_not_layout(self):
        with self._patch(TABLE_HTML):
            with self.assertRaises(ScrapeError) as ctx:
                sentiment.fetch_naaim(today=date(2026, 8, 11))
        msg = str(ctx.exception)
        self.assertIn("stale", msg.lower())
        self.assertIn("2026-04-29", msg)
        self.assertIn("104 days old", msg)
        self.assertNotIn("layout changed", msg)

    def test_boundary_exactly_at_budget_is_accepted(self):
        """Exactly NAAIM_MAX_AGE_DAYS old passes; the guard is > not >=."""
        self.assertEqual((date(2026, 5, 20) - date(2026, 4, 29)).days,
                         sentiment.NAAIM_MAX_AGE_DAYS)
        with self._patch(TABLE_HTML):
            got = sentiment.fetch_naaim(today=date(2026, 5, 20))
        self.assertEqual(got["exposure"], 93.79)

    def test_one_day_past_budget_raises(self):
        with self._patch(TABLE_HTML):
            with self.assertRaises(ScrapeError):
                sentiment.fetch_naaim(today=date(2026, 5, 21))

    def test_month_boundary_age_arithmetic(self):
        """Vault date rule: a month boundary case for the age calculation.

        Single-row fixtures here on purpose. An earlier draft of this test
        rewrote the newest date in the three-row table, which merely demoted
        that row and left a different one newest -- the function was right and
        the test was wrong.
        """
        html = _one_row("07/31/2026", "61.20")
        with self._patch(html):                     # 31 Jul -> 11 Aug, crosses the month
            got = sentiment.fetch_naaim(today=date(2026, 8, 11))
        self.assertEqual(got, {"exposure": 61.20, "as_of": "2026-07-31"})
        with self._patch(html):                     # 22 days later, one past budget
            with self.assertRaises(ScrapeError):
                sentiment.fetch_naaim(today=date(2026, 8, 22))

    def test_year_boundary_age_arithmetic(self):
        """Vault date rule: a year boundary case for the age calculation."""
        html = _one_row("12/31/2025", "55.05")
        with self._patch(html):                     # 31 Dec -> 14 Jan, crosses the year
            got = sentiment.fetch_naaim(today=date(2026, 1, 14))
        self.assertEqual(got, {"exposure": 55.05, "as_of": "2025-12-31"})
        with self._patch(html):
            with self.assertRaises(ScrapeError):
                sentiment.fetch_naaim(today=date(2026, 1, 22))

    def test_no_rows_reports_a_layout_change_not_staleness(self):
        with self._patch("<html><body>Welcome!</body></html>"):
            with self.assertRaises(ScrapeError) as ctx:
                sentiment.fetch_naaim(today=date(2026, 5, 6))
        self.assertIn("layout changed", str(ctx.exception))

    def test_history_is_not_returned(self):
        """Licence discipline: only the current headline leaves this function."""
        with self._patch(TABLE_HTML):
            got = sentiment.fetch_naaim(today=date(2026, 5, 6))
        self.assertEqual(set(got), {"exposure", "as_of"})
        self.assertNotIsInstance(got["exposure"], list)


class TestBuildNaaimParking(unittest.TestCase):
    """The builder's policy layer: park a stale feed, still fail a broken parser.

    `today` is injected rather than patched -- datetime.date is immutable, so
    mock.patch.object on date.today raises TypeError.
    """

    @classmethod
    def setUpClass(cls):
        import json
        cls.thresholds = json.loads(
            (Path(__file__).resolve().parent.parent / "data" / "thresholds.json")
            .read_text(encoding="utf-8")
        )

    def _build(self, html, today):
        """Build the row with no side effects.

        append_scrape_history is stubbed deliberately. Without it the non-parked
        path writes to data/history/naaim_exposure.json, and an earlier draft of
        these tests did exactly that -- committing a fixture value of 61.2
        "as of 2026-08-05" into the real accumulated history. A unit test must
        not be able to contaminate published data.
        """
        import lens2
        with mock.patch.object(sentiment, "fetch_text", return_value=html), \
             mock.patch.object(lens2, "append_scrape_history") as appended:
            row = lens2.build_naaim(self.thresholds, today=today)
        self._appended = appended
        return row

    def test_parked_row_does_not_append_to_history(self):
        self._build(TABLE_HTML, date(2026, 8, 11))
        self._appended.assert_not_called()

    def test_fresh_row_does_append_to_history(self):
        self._build(_one_row("08/05/2026", "61.20"), date(2026, 8, 11))
        self._appended.assert_called_once()

    def test_stale_feed_parks_instead_of_failing_the_build(self):
        row = self._build(TABLE_HTML, date(2026, 8, 11))
        self.assertEqual(row["status"], "context")
        self.assertFalse(row["in_composite"], "a stale row must not drive the composite")
        self.assertEqual(row["as_of"], "2026-04-29", "must carry the true week-ending date")
        self.assertEqual(row["value"], 93.79)
        self.assertIn("PARKED", row["notes"])
        self.assertIn("104 days", row["notes"])

    def test_parked_row_keeps_a_renderable_value(self):
        """template.html formatValue calls toLocaleString; null would throw."""
        row = self._build(TABLE_HTML, date(2026, 8, 11))
        self.assertIsInstance(row["value"], float)

    def test_fresh_feed_is_not_parked(self):
        row = self._build(_one_row("08/05/2026", "61.20"), date(2026, 8, 11))
        self.assertTrue(row["in_composite"], "a fresh reading must rejoin the composite")
        self.assertNotEqual(row["status"], "context")
        self.assertEqual(row["as_of"], "2026-08-05")
        self.assertNotIn("PARKED", row["notes"])

    def test_unparks_on_the_first_fresh_run(self):
        """Same fixture, two clocks: parked, then not, with no code change."""
        html = _one_row("08/05/2026", "61.20")
        self.assertFalse(self._build(html, date(2026, 9, 30))["in_composite"])
        self.assertTrue(self._build(html, date(2026, 8, 11))["in_composite"])

    def test_layout_change_still_fails_the_build(self):
        import lens2
        with mock.patch.object(sentiment, "fetch_text",
                               return_value="<html><body>Welcome!</body></html>"):
            with self.assertRaises(ScrapeError) as ctx:
                lens2.build_naaim(self.thresholds, today=date(2026, 8, 11))
        self.assertIn("layout changed", str(ctx.exception))


if __name__ == "__main__":
    unittest.main()
