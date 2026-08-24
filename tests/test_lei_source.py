"""Offline tests for the Conference Board LEI scraper (rewritten 2026-08-24).

The previous parser took the six-month change from a single sentence shape,
`(down|up|grew|contracted) X.X% over the six-month`. The July 2026 release
reworded that sentence to "the LEI's six-month growth rate turned positive, to
an increase of 0.2% between January and July 2026", the match failed,
six_month_pct came back None, and classify_lei refused to classify. Every
monthly-group run failed from 2026-07-27 onwards while the dashboard retained
the May 2026 row -- 99.3, "watch", six-month -0.3% -- as though it were
current, three months after the reading had turned positive.

Three behaviours are pinned here:

  * both published wordings parse, with the right sign. The August 2026
    sentence ends "a sharp reversal from its 1.3% contraction over the previous
    six months", and picking up that 1.3% would report -1.3% where the release
    says +0.2%: a wrong number that reads as plausible, which is the failure
    this file exists to prevent;
  * the LEI's numbers are taken from the LEI paragraph. The release repeats the
    same sentence shapes for the Coincident and Lagging indexes, and in the May
    2026 release the CEI reports +0.6% over the same six months against the
    LEI's -0.3%. The previous parser searched the whole page and was correct
    only because the LEI happens to be printed first;
  * an implausible magnitude raises rather than classifying.

Both fixtures are the real releases, trimmed: the August 2026 text from the
live page and the May 2026 text from the Internet Archive capture of
2026-06-20. No network.
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from sources import scrape
from sources.scrape import ScrapeError

# The meta tags and the H2 headline both name the LEI and both precede the
# release itself, so they are kept in the fixtures: they are the decoys the
# anchor has to walk past.
PAGE_CHROME = """
<meta name="description" content="The Conference Board Leading Economic Index (LEI) for the United States">
<h2 class="textCenter esfIntrotext">The Conference Board Leading Economic Index (LEI) for the US Edged Up in July</h2>
<h3>Latest Press Release</h3>
<p><em><strong>About the Composite Indexes</strong>: The Leading Economic Index (LEI) provides an early
indication of turning points. The Coincident Economic Index (CEI) is a measure of current conditions.</em></p>
"""

# Conference Board release of 2026-08-21, reporting July 2026.
RELEASE_JULY_2026 = """
<p><strong>The Conference Board Leading Economic Index&reg; </strong>(LEI) for the US increased by 0.2%
in July 2026 to 99.5 (2016=100), after an upwardly revised decline of 0.1% in June. As a result, the
LEI&rsquo;s six-month growth rate turned positive, to an increase of 0.2% between January and July 2026,
a sharp reversal from its 1.3% contraction over the previous six months.</p>
<p><strong>The Conference Board Coincident Economic Index&reg;</strong> (CEI) for the US increased by 0.2%
in July 2026 to 114.8 (2016=100), following a 0.2% increase in June. Overall, the CEI expanded by 0.5%
over the six months between January and July 2026, after remaining flat over the previous six months.</p>
"""

# Conference Board release of 2026-06-19, reporting May 2026. This is the print
# the dashboard has been stuck on since the parser broke.
RELEASE_MAY_2026 = """
<p><strong>The Conference Board Leading Economic Index&reg; </strong>(LEI) for the US increased slightly
by 0.1% in May 2026 to 99.3 (2016=100), following a 0.2% increase in April. After these two consecutive
increases, the LEI is down just 0.3% over the six months between November 2025 and May 2026, a much
smaller rate of decline than its 1.3% contraction over the previous six months (May to November 2025).</p>
<p>&ldquo;Despite two consecutive monthly increases, the LEI&rsquo;s six- and twelve-month growth rates
were still negative, suggesting slower economic expansion ahead.&rdquo;</p>
<p><strong>The Conference Board Coincident Economic Index&reg;</strong> (CEI) for the US increased by 0.2%
in May 2026 to 114.6 (2016=100), after a marginal increase of 0.1% in April. Overall, the CEI expanded by
0.6% over the six months between November 2025 and May 2026, an improvement from its growth of 0.2% over
the previous six months.</p>
<p><strong>The Conference Board Lagging Economic Index&reg;</strong> (LAG) for the US dipped by 0.1% to
120.5 (2016=100) in May 2026, after a 0.5% increase in April. However, the LAG&rsquo;s six-month change
was firmly in positive territory at 0.9% growth between November 2025 and May 2026.</p>
"""


class TestFetchConferenceBoardLei(unittest.TestCase):
    def _fetch(self, release: str) -> dict:
        with mock.patch.object(scrape, "fetch_text", return_value=PAGE_CHROME + release):
            return scrape.fetch_conference_board_lei()

    def test_july_2026_wording(self):
        """The rewritten sentence: growth rate turned positive, to an increase of 0.2%."""
        got = self._fetch(RELEASE_JULY_2026)
        self.assertEqual(got["level"], 99.5)
        self.assertEqual(got["mom_pct"], 0.2)
        self.assertEqual(got["six_month_pct"], 0.2)
        self.assertEqual(got["reference_month"], "2026-07-01")

    def test_july_2026_does_not_take_the_previous_window(self):
        """+0.2% is the current six months; the 1.3% contraction is the prior six."""
        self.assertNotEqual(self._fetch(RELEASE_JULY_2026)["six_month_pct"], -1.3)

    def test_may_2026_wording(self):
        """The earlier sentence: the LEI is down just 0.3% over the six months."""
        got = self._fetch(RELEASE_MAY_2026)
        self.assertEqual(got["level"], 99.3)
        self.assertEqual(got["mom_pct"], 0.1)
        self.assertEqual(got["six_month_pct"], -0.3)
        self.assertEqual(got["reference_month"], "2026-05-01")

    def test_may_2026_does_not_take_the_cei_six_month(self):
        """The CEI reports +0.6% over the same window; the LEI reports -0.3%."""
        self.assertEqual(self._fetch(RELEASE_MAY_2026)["six_month_pct"], -0.3)

    def test_level_is_the_lei_not_the_cei(self):
        """Both indexes print "increased by 0.2% in July 2026 to <level>"."""
        self.assertEqual(self._fetch(RELEASE_JULY_2026)["level"], 99.5)

    def test_negative_month_over_month_keeps_its_sign(self):
        release = RELEASE_JULY_2026.replace(
            "(LEI) for the US increased by 0.2%", "(LEI) for the US fell by 0.2%"
        )
        self.assertEqual(self._fetch(release)["mom_pct"], -0.2)

    def test_missing_lei_sentence_raises_layout_changed(self):
        with mock.patch.object(scrape, "fetch_text", return_value=PAGE_CHROME):
            with self.assertRaises(ScrapeError) as ctx:
                scrape.fetch_conference_board_lei()
        self.assertIn("layout changed", str(ctx.exception))

    def test_implausible_six_month_change_raises(self):
        """A magnitude no release has printed means the wrong number was picked up."""
        release = RELEASE_JULY_2026.replace("to an increase of 0.2%", "to an increase of 42.0%")
        with self.assertRaises(ScrapeError) as ctx:
            self._fetch(release)
        self.assertIn("implausible", str(ctx.exception))

    def test_absent_six_month_sentence_returns_none_rather_than_guessing(self):
        """The level still parses; the caller decides what to do with no rate."""
        # The fixture is laid out across several lines, so the sentence is cut
        # with a whitespace-tolerant pattern rather than a literal replace.
        release = re.sub(r"As a result,.*?previous six months\.", "", RELEASE_JULY_2026, flags=re.DOTALL)
        self.assertNotIn("six-month", release)
        got = self._fetch(release)
        self.assertIsNone(got["six_month_pct"])
        self.assertEqual(got["level"], 99.5)


if __name__ == "__main__":
    unittest.main()
