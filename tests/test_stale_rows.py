"""Tests for marking and parking rows whose builder failed (added 2026-08-25).

A failing builder has always been non-fatal: the previous JSON entry is kept and
the process exits 1. What was missing is that the kept entry looked exactly like
a fresh one. The Conference Board LEI row read "99.3, watch, six-month -0.3%, as
of May 2026" for four weeks after the reading had turned positive, and nothing
on the page or in the digest said the number had stopped refreshing. The red run
was the only signal, and it was an identical email every Monday.

What is pinned here:

  * the clock starts at the first failed run, not at the row's as_of. as_of is a
    reference date -- a freshly published LEI row is dated the first of the
    reference month and is already weeks old on the day it lands -- so an as_of
    budget would park healthy rows and miss broken ones;
  * `stale.since` survives repeated failures, so the reported age is the length
    of the outage rather than the time since the last run;
  * below the budget nothing about the row changes. A single failed poll is a
    blip, and flipping a gauge to context on a transient network error would
    move the Lens 2 composite for no reason;
  * past the budget the row parks on the NAAIM terms: context, out of the
    composite, value and as_of untouched, and a message that says how long and
    why;
  * a successful rebuild unparks it, because the built row replaces the old one
    whole;
  * a failed builder is attributed to its row through the builder name the row
    itself records, and a failure that cannot be attributed is reported rather
    than passed over.

No network.
"""
from __future__ import annotations

import json
import sys
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

import update_data
from lens2 import summarise

ROOT = Path(__file__).resolve().parent.parent


def utc(year: int, month: int, day: int) -> datetime:
    """A UTC instant. Python months are 1-indexed."""
    return datetime(year, month, day, tzinfo=timezone.utc)


def gauge(ind_id: str, status: str = "triggered", in_composite: bool = True) -> dict:
    return {
        "id": ind_id,
        "name": ind_id.replace("_", " ").title(),
        "lens": 2,
        "in_composite": in_composite,
        "value": 42.0,
        "status": status,
        "as_of": "2026-06-01",
        "builder": f"build_{ind_id}",
    }


LENS1_ROW = {
    "id": "leading_indicators",
    "name": "Leading Economic Index",
    "lens": 1,
    "value": 99.3,
    "status": "watch",
    "as_of": "2026-05-01",
    "builder": "build_lei",
}


class TestMarkRetained(unittest.TestCase):
    def test_first_failure_records_the_clock_and_changes_nothing_else(self):
        marked = update_data.mark_retained(gauge("deal_ipo_froth"), "monthly", "boom", utc(2026, 8, 25))
        self.assertEqual(marked["status"], "triggered")
        self.assertTrue(marked["in_composite"])
        self.assertFalse(marked["stale"]["parked"])
        self.assertEqual(marked["stale"]["days"], 0)
        self.assertEqual(marked["stale"]["since"], "2026-08-25T00:00:00Z")
        self.assertNotIn("message", marked["stale"])

    def test_since_survives_repeated_failures(self):
        first = update_data.mark_retained(gauge("deal_ipo_froth"), "monthly", "boom", utc(2026, 8, 1))
        second = update_data.mark_retained(first, "monthly", "boom", utc(2026, 8, 8))
        third = update_data.mark_retained(second, "monthly", "boom", utc(2026, 8, 22))
        self.assertEqual(third["stale"]["since"], "2026-08-01T00:00:00Z")
        self.assertEqual(third["stale"]["days"], 21)
        self.assertTrue(third["stale"]["parked"])

    def test_parks_at_the_budget_not_before(self):
        row = update_data.mark_retained(gauge("deal_ipo_froth"), "monthly", "boom", utc(2026, 8, 1))
        day15 = update_data.mark_retained(row, "monthly", "boom", utc(2026, 8, 16))
        self.assertEqual(day15["stale"]["days"], 15)
        self.assertFalse(day15["stale"]["parked"])
        day16 = update_data.mark_retained(row, "monthly", "boom", utc(2026, 8, 17))
        self.assertEqual(day16["stale"]["days"], 16)
        self.assertTrue(day16["stale"]["parked"])

    def test_daily_group_has_a_shorter_budget(self):
        row = update_data.mark_retained(gauge("value_vs_growth"), "daily", "boom", utc(2026, 8, 1))
        self.assertFalse(update_data.mark_retained(row, "daily", "boom", utc(2026, 8, 4))["stale"]["parked"])
        self.assertTrue(update_data.mark_retained(row, "daily", "boom", utc(2026, 8, 5))["stale"]["parked"])

    def test_parked_row_cannot_fire_a_trigger_or_drive_the_composite(self):
        row = update_data.mark_retained(gauge("deal_ipo_froth"), "monthly", "boom", utc(2026, 8, 1))
        parked = update_data.mark_retained(row, "monthly", "boom", utc(2026, 8, 25))
        self.assertEqual(parked["status"], "context")
        self.assertFalse(parked["in_composite"])
        self.assertEqual(parked["stale"]["status_before"], "triggered")
        self.assertTrue(parked["stale"]["was_in_composite"])

    def test_parked_row_keeps_its_value_and_date(self):
        """The last successful read is dated and verifiable; blanking it is not better."""
        row = update_data.mark_retained(gauge("deal_ipo_froth"), "monthly", "boom", utc(2026, 8, 1))
        parked = update_data.mark_retained(row, "monthly", "boom", utc(2026, 8, 25))
        self.assertEqual(parked["value"], 42.0)
        self.assertEqual(parked["as_of"], "2026-06-01")

    def test_message_names_the_date_the_age_and_the_reason(self):
        row = update_data.mark_retained(LENS1_ROW, "monthly", "six-month change unavailable", utc(2026, 7, 27))
        parked = update_data.mark_retained(row, "monthly", "six-month change unavailable", utc(2026, 8, 25))
        message = parked["stale"]["message"]
        self.assertIn("2026-07-27", message)
        self.assertIn("29 days", message)
        self.assertIn("six-month change unavailable", message)
        self.assertNotIn("'", message)  # house style: no contractions anywhere

    def test_lens1_row_does_not_gain_an_in_composite_key(self):
        row = update_data.mark_retained(LENS1_ROW, "monthly", "boom", utc(2026, 7, 27))
        parked = update_data.mark_retained(row, "monthly", "boom", utc(2026, 8, 25))
        self.assertNotIn("in_composite", parked)
        self.assertEqual(parked["stale"]["status_before"], "watch")

    def test_status_before_is_captured_once_not_overwritten_by_context(self):
        row = update_data.mark_retained(gauge("deal_ipo_froth"), "monthly", "boom", utc(2026, 8, 1))
        parked = update_data.mark_retained(row, "monthly", "boom", utc(2026, 8, 25))
        again = update_data.mark_retained(parked, "monthly", "boom", utc(2026, 9, 1))
        self.assertEqual(again["stale"]["status_before"], "triggered")

    def test_month_boundary(self):
        """January has 31 days; the difference is taken by the date library."""
        row = update_data.mark_retained(gauge("value_vs_growth"), "daily", "boom", utc(2026, 1, 30))
        crossed = update_data.mark_retained(row, "daily", "boom", utc(2026, 2, 3))
        self.assertEqual(crossed["stale"]["days"], 4)
        self.assertTrue(crossed["stale"]["parked"])

    def test_year_boundary(self):
        row = update_data.mark_retained(gauge("value_vs_growth"), "daily", "boom", utc(2025, 12, 28))
        crossed = update_data.mark_retained(row, "daily", "boom", utc(2026, 1, 5))
        self.assertEqual(crossed["stale"]["days"], 8)
        self.assertTrue(crossed["stale"]["parked"])


class TestCompositeExcludesParked(unittest.TestCase):
    def test_parked_gauge_leaves_the_share(self):
        rows = [gauge("a"), gauge("b"), gauge("c", status="quiet"), gauge("d", status="quiet")]
        before = summarise(rows, 62.5)
        self.assertEqual((before["gauge_count"], before["triggered_count"]), (4, 2))

        stale = update_data.mark_retained(rows[0], "monthly", "boom", utc(2026, 8, 1))
        rows[0] = update_data.mark_retained(stale, "monthly", "boom", utc(2026, 8, 25))
        after = summarise(rows, 62.5)
        self.assertEqual((after["gauge_count"], after["triggered_count"]), (3, 1))
        self.assertEqual(after["share_pct"], 33.3)


class TestMergeAndAttribution(unittest.TestCase):
    """Exercises the file-level merge against a temporary data directory."""

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.data = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        patcher = mock.patch.object(update_data, "DATA_DIR", self.data)
        patcher.start()
        self.addCleanup(patcher.stop)
        self._write(1, [LENS1_ROW])
        self._write(2, [gauge("deal_ipo_froth"), gauge("rule_of_20")])
        self._write(3, [])

    def _write(self, lens: int, indicators: list[dict]) -> None:
        (self.data / f"lens{lens}.json").write_text(
            json.dumps({"lens": lens, "indicators": indicators}), encoding="utf-8"
        )

    def _read(self, lens: int) -> dict:
        return json.loads((self.data / f"lens{lens}.json").read_text(encoding="utf-8"))

    def test_failure_is_attributed_through_the_builder_the_row_records(self):
        marks, unattributed = update_data.attribute_failures([("build_lei", "monthly", "boom")])
        self.assertEqual(marks, {1: {"leading_indicators": ("monthly", "boom")}})
        self.assertEqual(unattributed, [])

    def test_unknown_builder_is_reported_not_silently_dropped(self):
        marks, unattributed = update_data.attribute_failures([("build_brand_new", "daily", "boom")])
        self.assertEqual(marks, {})
        self.assertEqual(unattributed, ["build_brand_new"])

    def test_merge_marks_the_retained_row_and_recomputes_the_composite(self):
        marks = {"deal_ipo_froth": ("monthly", "boom")}
        update_data.update_lens_file(2, [], {"lens2_composite": {"alarm_share_pct": 62.5}},
                                     marks, utc(2026, 8, 1))
        update_data.update_lens_file(2, [], {"lens2_composite": {"alarm_share_pct": 62.5}},
                                     marks, utc(2026, 8, 25))
        payload = self._read(2)
        parked = next(i for i in payload["indicators"] if i["id"] == "deal_ipo_froth")
        self.assertTrue(parked["stale"]["parked"])
        self.assertEqual(payload["composite"]["gauge_count"], 1)

    def test_successful_rebuild_unparks_the_row(self):
        marks = {"deal_ipo_froth": ("monthly", "boom")}
        thresholds = {"lens2_composite": {"alarm_share_pct": 62.5}}
        update_data.update_lens_file(2, [], thresholds, marks, utc(2026, 8, 1))
        update_data.update_lens_file(2, [], thresholds, marks, utc(2026, 8, 25))
        self.assertTrue(next(i for i in self._read(2)["indicators"]
                             if i["id"] == "deal_ipo_froth")["stale"]["parked"])

        fresh = gauge("deal_ipo_froth")
        update_data.update_lens_file(2, [fresh], thresholds, None, utc(2026, 8, 26))
        rebuilt = next(i for i in self._read(2)["indicators"] if i["id"] == "deal_ipo_froth")
        self.assertNotIn("stale", rebuilt)
        self.assertEqual(rebuilt["status"], "triggered")
        self.assertTrue(rebuilt["in_composite"])
        self.assertEqual(self._read(2)["composite"]["gauge_count"], 2)


class TestEndToEnd(unittest.TestCase):
    """The whole path: a builder raises, its row is found, marked, and parked.

    The row is seeded with an outage that started long ago, so a single run
    crosses the budget without needing to inject a clock into main().
    """

    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.data = Path(self._tmp.name)
        self.addCleanup(self._tmp.cleanup)
        for target in ("DATA_DIR",):
            patcher = mock.patch.object(update_data, target, self.data)
            patcher.start()
            self.addCleanup(patcher.stop)
        (self.data / "thresholds.json").write_text(
            json.dumps({"lens2_composite": {"alarm_share_pct": 62.5}}), encoding="utf-8")

        def build_deal_ipo_froth(thresholds):
            raise RuntimeError("Renaissance layout changed: no monthly chart")

        self.failing = build_deal_ipo_froth
        patcher = mock.patch.object(
            update_data, "GROUPS",
            {"daily": [], "monthly": [build_deal_ipo_froth], "quarterly": []})
        patcher.start()
        self.addCleanup(patcher.stop)

        long_outage = dict(gauge("deal_ipo_froth"),
                           stale={"kind": "builder_failure", "since": "2026-07-01T00:00:00Z"})
        for lens, rows in ((1, []), (2, [long_outage, gauge("rule_of_20")]), (3, [])):
            (self.data / f"lens{lens}.json").write_text(
                json.dumps({"lens": lens, "indicators": rows}), encoding="utf-8")

    def test_failed_builder_parks_its_row_and_exits_non_zero(self):
        with mock.patch("builtins.print"):
            self.assertEqual(update_data.main(["--group", "monthly"]), 1)
        payload = json.loads((self.data / "lens2.json").read_text(encoding="utf-8"))
        row = next(i for i in payload["indicators"] if i["id"] == "deal_ipo_froth")
        self.assertTrue(row["stale"]["parked"])
        self.assertEqual(row["status"], "context")
        self.assertFalse(row["in_composite"])
        self.assertIn("Renaissance layout changed", row["stale"]["reason"])
        self.assertEqual(payload["composite"]["gauge_count"], 1)

    def test_row_that_records_no_builder_is_reported_as_unmarkable(self):
        orphan = gauge("deal_ipo_froth")
        del orphan["builder"]
        (self.data / "lens2.json").write_text(
            json.dumps({"lens": 2, "indicators": [orphan]}), encoding="utf-8")
        with mock.patch("builtins.print") as printed:
            update_data.main(["--group", "monthly"])
        said = " ".join(str(call.args[0]) for call in printed.call_args_list)
        self.assertIn("WARNING build_deal_ipo_froth", said)
        self.assertIn("cannot be marked stale", said)


class TestBuilderAttributionIsComplete(unittest.TestCase):
    """Guard on the committed data: a row nobody can attribute cannot be parked."""

    def _rows(self):
        for lens in update_data.LENSES:
            payload = json.loads((ROOT / "data" / f"lens{lens}.json").read_text(encoding="utf-8"))
            for row in payload["indicators"]:
                yield lens, row

    def test_every_committed_row_records_its_builder(self):
        missing = [f"lens{lens}:{row['id']}" for lens, row in self._rows() if not row.get("builder")]
        self.assertEqual(missing, [], "Run python scripts/update_data.py --group all and commit the result.")

    def test_every_recorded_builder_still_exists(self):
        known = {fn.__name__ for group in update_data.GROUPS.values() for fn in group}
        unknown = sorted({row["builder"] for _, row in self._rows()
                          if row.get("builder") and row["builder"] not in known})
        self.assertEqual(unknown, [], "A builder was renamed or removed. Run update_data and commit.")


if __name__ == "__main__":
    unittest.main()
