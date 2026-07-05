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
    compute_moves,
    diff_snapshots,
    headroom,
    headroom_text,
    lookback_cutoff,
    narrative,
    parse_recipients,
    rank_movers,
    render_subject,
    snapshot,
)

LENS1_IDS = ["yield_curve_10y3m", "sahm_rule", "hy_credit_spreads", "pmi_manufacturing_proxy",
             "leading_indicators", "labour_market", "shiller_cape"]


def make_indicator(ind_id, status, value=1.0, name=None, unit="index", decimals=1, signed=False):
    return {
        "id": ind_id, "name": name or ind_id, "status": status, "value": value,
        "unit": unit, "decimals": decimals, "signed": signed, "as_of": "2026-07-02",
    }


def make_lens1(statuses):
    # Seven-indicator lens; the last is valuation context (unranked), as live.
    inds = [make_indicator(i, s) for i, s in zip(LENS1_IDS, statuses)]
    inds[-1]["status"] = "context"  # valuation never ranks
    return {"lens": 1, "indicators": inds}


def make_lens1_vals(values, statuses=None):
    """Lens 1 with specific per-id values (for move/headroom tests)."""
    statuses = statuses or ["benign"] * 7
    inds = [make_indicator(i, s) for i, s in zip(LENS1_IDS, statuses)]
    inds[-1]["status"] = "context"
    for ind in inds:
        if ind["id"] in values:
            ind["value"] = values[ind["id"]]
    return {"lens": 1, "indicators": inds}


def make_lens3_val(value, status="benign"):
    return {"lens": 3, "indicators": [make_indicator("sma_trend_sp500", status, value, unit="index", decimals=2)]}


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


class Headroom(unittest.TestCase):
    """Distance-to-trigger is claimed only where the value is the trigger quantity."""

    def test_level_below_sahm(self):
        room, name = headroom({"id": "sahm_rule", "value": 0.07, "decimals": 2})
        self.assertAlmostEqual(room, 0.28)  # 0.35 watch - 0.07
        self.assertIn("watch", name)

    def test_level_above_yield_curve(self):
        room, _ = headroom({"id": "yield_curve_10y3m", "value": 0.67, "decimals": 2})
        self.assertAlmostEqual(room, 0.67)  # above inversion at zero

    def test_chart_line_positive_polarity_triggered(self):
        # Growth P/E above its trigger line reads as negative room (past the line).
        room, _ = headroom({"id": "growth_expectation_pe", "value": 32.15, "decimals": 2, "chart_line": 23.65})
        self.assertAlmostEqual(room, -8.5)

    def test_chart_line_negative_polarity_nfci(self):
        # NFCI triggers when loose enough (value <= line); above the tail is positive room.
        room, _ = headroom({"id": "credit_complacency_nfci", "value": -0.504, "decimals": 2, "chart_line": -0.633})
        self.assertAlmostEqual(room, 0.129)

    def test_none_where_trigger_is_derived(self):
        self.assertIsNone(headroom({"id": "leading_indicators", "value": 99.3, "decimals": 1}))
        self.assertIsNone(headroom({"id": "labour_market", "value": 4.2, "decimals": 1}))

    def test_text_from_and_past(self):
        self.assertIn("from", headroom_text({"id": "sahm_rule", "value": 0.07, "decimals": 2}))
        self.assertIn("past", headroom_text({"id": "value_vs_growth", "value": 15.4, "decimals": 1}))


class Moves(unittest.TestCase):
    def _snap(self, l1, l2, l3):
        return snapshot(l1, l2, l3)

    def test_no_baseline_is_empty(self):
        s = self._snap(make_lens1(["benign"] * 7), make_lens2(50.0, 4, "below"), make_lens3("benign"))
        self.assertEqual(compute_moves(None, s), {})

    def test_direction_sense_by_polarity(self):
        # Spread widening = worse (polarity +1); curve steepening = better (polarity -1).
        old = self._snap(make_lens1_vals({"hy_credit_spreads": 2.5, "yield_curve_10y3m": 0.5}),
                         make_lens2(50.0, 4, "below"), make_lens3("benign"))
        new = self._snap(make_lens1_vals({"hy_credit_spreads": 2.7, "yield_curve_10y3m": 0.7}),
                         make_lens2(50.0, 4, "below"), make_lens3("benign"))
        moves = compute_moves(old, new)
        self.assertEqual(moves["hy_credit_spreads"]["arrow"], "up")
        self.assertEqual(moves["hy_credit_spreads"]["sense"], "worse")
        self.assertEqual(moves["yield_curve_10y3m"]["sense"], "better")

    def test_trend_delta_is_percentage(self):
        old = self._snap(make_lens1(["benign"] * 7), make_lens2(50.0, 4, "below"), make_lens3_val(7000.0))
        new = self._snap(make_lens1(["benign"] * 7), make_lens2(50.0, 4, "below"), make_lens3_val(7140.0))
        mv = compute_moves(old, new)["sma_trend_sp500"]
        self.assertTrue(mv["is_pct"])
        self.assertAlmostEqual(mv["delta"], 2.0)  # +2%

    def test_no_new_print_labelled(self):
        s = self._snap(make_lens1(["benign"] * 7), make_lens2(50.0, 4, "below"), make_lens3("benign"))
        self.assertEqual(compute_moves(s, s)["sahm_rule"]["text"], "no new print")


class Movers(unittest.TestCase):
    def _snap(self, l1, l2, l3):
        return snapshot(l1, l2, l3)

    def test_status_flip_ranks_first(self):
        old = self._snap(make_lens1(["benign"] * 7), make_lens2(50.0, 4, "below"), make_lens3("benign"))
        new = self._snap(make_lens1(["benign", "benign", "benign", "benign", "watch", "benign", "context"]),
                         make_lens2(50.0, 4, "below"), make_lens3("benign"))
        movers = rank_movers(new, compute_moves(old, new))
        self.assertTrue(movers)
        self.assertEqual(movers[0]["id"], "leading_indicators")

    def test_move_closer_to_trigger_outranks_far_move(self):
        # HY eats half its remaining room to the watch line; PMI barely dents its own.
        old = self._snap(make_lens1_vals({"hy_credit_spreads": 3.9, "pmi_manufacturing_proxy": 60.0}),
                         make_lens2(50.0, 4, "below"), make_lens3("benign"))
        new = self._snap(make_lens1_vals({"hy_credit_spreads": 3.95, "pmi_manufacturing_proxy": 59.0}),
                         make_lens2(50.0, 4, "below"), make_lens3("benign"))
        ids = [m["id"] for m in rank_movers(new, compute_moves(old, new))]
        self.assertIn("hy_credit_spreads", ids)
        self.assertIn("pmi_manufacturing_proxy", ids)
        self.assertLess(ids.index("hy_credit_spreads"), ids.index("pmi_manufacturing_proxy"))


class Narrative(unittest.TestCase):
    def test_no_baseline_flags_history_window(self):
        new = snapshot(make_lens1(["benign"] * 7), make_lens2(50.0, 4, "below"), make_lens3("benign"))
        text = narrative(new, [], has_baseline=False, changes=[])
        self.assertIn("No risk-reduction signal", text)
        self.assertIn("history", text)

    def test_quiet_week_reports_lens_on_watch(self):
        new = snapshot(make_lens1(["benign", "benign", "benign", "benign", "watch", "benign", "context"]),
                       make_lens2(50.0, 4, "below"), make_lens3("benign"))
        text = narrative(new, [], has_baseline=True, changes=[])
        self.assertIn("Quiet week", text)
        self.assertIn("on watch", text)

    def test_fired_leads(self):
        new = snapshot(make_lens1(["elevated", "benign", "benign", "benign", "benign", "benign", "context"]),
                       make_lens2(62.5, 5, "at_or_above"), make_lens3("elevated"))
        self.assertIn("fired", narrative(new, [], True, []).lower())


if __name__ == "__main__":
    unittest.main()
