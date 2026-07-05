"""Tests for the weekly digest: date look-back boundaries, the combined-signal
roll-up (mirrors template.html), and the week-over-week diff.

All pure functions — no git, no network, no SMTP. The git/email plumbing in
weekly_digest.py is exercised manually with --print / --send.
"""
from __future__ import annotations

import sys
import unittest
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from weekly_digest import (
    combined_state,
    diff_snapshots,
    lookback_cutoff,
    parse_recipients,
    render_subject,
    snapshot,
)


def make_indicator(ind_id, status, value=1.0, name=None, unit="index", decimals=1, signed=False):
    return {
        "id": ind_id, "name": name or ind_id, "status": status, "value": value,
        "unit": unit, "decimals": decimals, "signed": signed, "as_of": "2026-07-02",
    }


def make_lens1(statuses):
    # Seven-indicator lens; the last is valuation context (unranked), as live.
    ids = ["yield_curve_10y3m", "sahm_rule", "hy_credit_spreads", "pmi_manufacturing_proxy",
           "leading_indicators", "labour_market", "shiller_cape"]
    inds = [make_indicator(i, s) for i, s in zip(ids, statuses)]
    inds[-1]["status"] = "context"  # valuation never ranks
    return {"lens": 1, "indicators": inds}


def make_lens2(share_pct, triggered, alarm_state, alarm_share=62.5, gauges=8):
    # A single triggerable gauge stands in for the composite detail rows.
    return {
        "lens": 2,
        "indicators": [make_indicator("growth_expectation_pe", "triggered", 32.15, unit="ratio")],
        "composite": {
            "gauge_count": gauges, "triggered_count": triggered, "eased_count": 0,
            "share_pct": share_pct, "alarm_share_pct": alarm_share, "alarm_state": alarm_state,
        },
    }


def make_lens3(status):
    return {"lens": 3, "indicators": [make_indicator("sma_trend_sp500", status, 7483.24, unit="index", decimals=2)]}


class LookbackDates(unittest.TestCase):
    """CLAUDE.md requires a month-boundary and a year-boundary edge case."""

    def test_month_boundary(self):
        # 2026 is not a leap year, so February has 28 days.
        self.assertEqual(lookback_cutoff(date(2026, 3, 3), 7), date(2026, 2, 24))

    def test_year_boundary(self):
        self.assertEqual(lookback_cutoff(date(2026, 1, 3), 7), date(2025, 12, 27))

    def test_leap_year_february(self):
        # 2028 is a leap year: February has 29 days.
        self.assertEqual(lookback_cutoff(date(2028, 3, 5), 7), date(2028, 2, 27))


class CombinedSignal(unittest.TestCase):
    def test_no_signal(self):
        state, _ = combined_state(
            make_lens1(["benign"] * 7), make_lens2(50.0, 4, "below"), make_lens3("benign"))
        self.assertEqual(state, "none")

    def test_armed_on_lens1(self):
        state, msg = combined_state(
            make_lens1(["elevated", "benign", "benign", "benign", "benign", "benign", "context"]),
            make_lens2(50.0, 4, "below"), make_lens3("benign"))
        self.assertEqual(state, "armed")
        self.assertIn("recession risk is elevated (1 of 6 indicators)", msg)

    def test_armed_on_lens2_alarm(self):
        state, _ = combined_state(
            make_lens1(["benign"] * 7), make_lens2(62.5, 5, "at_or_above"), make_lens3("benign"))
        self.assertEqual(state, "armed")

    def test_fired_needs_lens3_confirmation(self):
        state, msg = combined_state(
            make_lens1(["benign"] * 7), make_lens2(62.5, 5, "at_or_above"), make_lens3("elevated"))
        self.assertEqual(state, "fired")
        self.assertIn("FIRED", msg)

    def test_lens3_alone_does_not_fire(self):
        # Trend break without either lens armed is not a signal.
        state, _ = combined_state(
            make_lens1(["benign"] * 7), make_lens2(50.0, 4, "below"), make_lens3("elevated"))
        self.assertEqual(state, "none")


class Diff(unittest.TestCase):
    def _snap(self, l1, l2, l3):
        return snapshot(l1, l2, l3)

    def test_no_change(self):
        s = self._snap(make_lens1(["benign"] * 7), make_lens2(50.0, 4, "below"), make_lens3("benign"))
        self.assertEqual(diff_snapshots(s, s), [])

    def test_missing_baseline_returns_no_changes(self):
        s = self._snap(make_lens1(["benign"] * 7), make_lens2(50.0, 4, "below"), make_lens3("benign"))
        self.assertEqual(diff_snapshots(None, s), [])

    def test_indicator_flip(self):
        old = self._snap(make_lens1(["benign"] * 7), make_lens2(50.0, 4, "below"), make_lens3("benign"))
        new = self._snap(
            make_lens1(["benign", "watch", "benign", "benign", "benign", "benign", "context"]),
            make_lens2(50.0, 4, "below"), make_lens3("benign"))
        changes = diff_snapshots(old, new)
        self.assertTrue(any(c["kind"] == "indicator" and "Benign → Watch" in c["headline"] for c in changes))

    def test_composite_share_move(self):
        old = self._snap(make_lens1(["benign"] * 7), make_lens2(50.0, 4, "below"), make_lens3("benign"))
        new = self._snap(make_lens1(["benign"] * 7), make_lens2(62.5, 5, "below"), make_lens3("benign"))
        changes = diff_snapshots(old, new)
        self.assertTrue(any(c["kind"] == "composite_share" and "50% → 62.5%" in c["headline"] for c in changes))

    def test_alarm_crossing_and_signal_change(self):
        old = self._snap(make_lens1(["benign"] * 7), make_lens2(50.0, 4, "below"), make_lens3("benign"))
        new = self._snap(make_lens1(["benign"] * 7), make_lens2(62.5, 5, "at_or_above"), make_lens3("benign"))
        changes = diff_snapshots(old, new)
        kinds = {c["kind"] for c in changes}
        self.assertIn("combined", kinds)        # none -> armed
        self.assertIn("composite_alarm", kinds)  # crossed the alarm
        # The combined change is ranked first.
        self.assertEqual(changes[0]["kind"], "combined")


class Subject(unittest.TestCase):
    def test_quiet_week(self):
        new = snapshot(make_lens1(["benign"] * 7), make_lens2(50.0, 4, "below"), make_lens3("benign"))
        subject = render_subject(new, [])
        self.assertIn("quiet week", subject)
        self.assertIn("froth 50%", subject)

    def test_change_week_leads_with_top_change(self):
        new = snapshot(make_lens1(["benign"] * 7), make_lens2(62.5, 5, "at_or_above"), make_lens3("benign"))
        changes = [
            {"kind": "combined", "headline": "Risk-reduction signal: No signal → ARMED", "detail": ""},
            {"kind": "composite_alarm", "headline": "Lens 2 froth composite crossed its alarm", "detail": ""},
        ]
        subject = render_subject(new, changes)
        self.assertIn("No signal → ARMED", subject)
        self.assertIn("+1 more", subject)


class Recipients(unittest.TestCase):
    def test_single(self):
        self.assertEqual(parse_recipients("phuazz@gmail.com"), ["phuazz@gmail.com"])

    def test_multiple_with_spaces(self):
        self.assertEqual(
            parse_recipients("phuazz@gmail.com, eileen@example.com"),
            ["phuazz@gmail.com", "eileen@example.com"],
        )

    def test_tolerates_trailing_comma_and_blanks(self):
        self.assertEqual(
            parse_recipients("phuazz@gmail.com,, eileen@example.com ,"),
            ["phuazz@gmail.com", "eileen@example.com"],
        )

    def test_empty_or_none(self):
        self.assertEqual(parse_recipients(""), [])
        self.assertEqual(parse_recipients(None), [])


if __name__ == "__main__":
    unittest.main()
