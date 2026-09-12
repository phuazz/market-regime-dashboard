"""Guard: the Lens 2 alarm must not change what it demands without a decision.

The alarm is stored as a SHARE (62.5%), so what it actually demands depends on
how many gauges are in the composite, and a share threshold on a small
denominator is lumpy. 62.5% is exactly 5 of 8 at eight gauges; at seven the
lowest share at or above it is 5 of 7, because 4 of 7 is 57.1% and sits below
the line. When the NAAIM row parked on 2026-08-25 the count fell from eight to
seven and the alarm tightened with it — unannounced, undecided, and invisible in
every artefact the dashboard publishes. The row was removed on 2026-09-12 and
the recalibration endorsed 62.5% on the seven
(reviews/2026-09-12_lens2-alarm-recalibration.md), but the silence is the defect
these tests exist to prevent repeating.

WHAT IS GUARDED HERE, AND WHAT IS NOT. A permanent change to the set — a gauge
added or deleted — fails these tests, so the next one is a decision rather than
an accident. A gauge that PARKS does not fail them: parking is temporary, the
refresh workflow runs this suite BEFORE it rebuilds data, and a guard that
halted every refresh for the duration of an upstream outage would be traded away
inside a week. The temporary case is reported instead by the weekly digest,
which names the effective bite for as long as it lasts.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))

from lens2 import summarise                      # noqa: E402
from util import COMPOSITE_SET, minimum_triggered  # noqa: E402


def _load(name: str) -> dict:
    return json.loads((ROOT / "data" / name).read_text(encoding="utf-8"))


class MinimumTriggered(unittest.TestCase):
    """The arithmetic the whole guard rests on."""

    def test_the_counts_that_62_5_percent_has_meant(self):
        self.assertEqual(minimum_triggered(62.5, 8), 5)   # as adopted, 2026-07-03
        self.assertEqual(minimum_triggered(62.5, 7), 5)   # as running since 2026-08-25
        self.assertEqual(minimum_triggered(62.5, 6), 4)   # were another gauge to go

    def test_the_same_share_demands_a_larger_fraction_of_a_smaller_set(self):
        """The silent re-cut, stated as the arithmetic that caused it."""
        eight = minimum_triggered(62.5, 8) / 8
        seven = minimum_triggered(62.5, 7) / 7
        self.assertAlmostEqual(eight, 0.625)
        self.assertAlmostEqual(seven, 5 / 7)
        self.assertGreater(seven, eight)

    def test_it_mirrors_the_live_rounding_rather_than_re_deriving_it(self):
        """summarise rounds the share to 1dp before comparing; so must this.

        Without the rounding, 5 of 7 computes as 71.42857... and any alarm set
        between 71.4 and 71.43 would disagree with the live code at the boundary.
        """
        armed = summarise(
            [{"in_composite": True, "status": "triggered"} for _ in range(5)]
            + [{"in_composite": True, "status": "quiet"} for _ in range(2)],
            71.4,
        )
        self.assertEqual(armed["share_pct"], 71.4)
        self.assertEqual(armed["alarm_state"], "at_or_above")
        self.assertEqual(minimum_triggered(71.4, 7), 5)

    def test_a_zero_gauge_set_is_refused(self):
        with self.assertRaises(ValueError):
            minimum_triggered(62.5, 0)


class CommittedCompositeSet(unittest.TestCase):
    """The committed data must agree with the named membership."""

    def setUp(self):
        self.lens2 = _load("lens2.json")
        self.thresholds = _load("thresholds.json")["lens2_composite"]
        self.rows = {row["id"]: row for row in self.lens2["indicators"]}

    def test_every_named_member_is_present(self):
        missing = [i for i in COMPOSITE_SET if i not in self.rows]
        self.assertEqual(missing, [], "A composite gauge left data/lens2.json. If that is "
                                      "deliberate, remove it from util.COMPOSITE_SET, update "
                                      "lens2_composite.expected_gauge_count, and file the "
                                      "decision — the alarm's bite changes with the count.")

    def test_no_row_is_in_the_composite_without_being_a_named_member(self):
        extra = sorted(row["id"] for row in self.lens2["indicators"]
                       if row.get("in_composite") and row["id"] not in COMPOSITE_SET)
        self.assertEqual(extra, [], "A gauge entered the composite without being named in "
                                    "util.COMPOSITE_SET. Adding one loosens the alarm: at eight "
                                    "gauges 62.5% is 5 of 8, at seven it is 5 of 7.")

    def test_a_member_is_either_in_the_composite_or_parked_with_a_reason(self):
        """The only acceptable absence is a declared, temporary one."""
        unexplained = []
        for ind_id in COMPOSITE_SET:
            row = self.rows.get(ind_id)
            if row is None or row.get("in_composite"):
                continue
            if not (row.get("stale") or {}).get("parked"):
                unexplained.append(ind_id)
        self.assertEqual(unexplained, [], "A named gauge is out of the composite without a "
                                          "parked stale block to explain it. Either the builder "
                                          "stopped setting in_composite, or the row was retired "
                                          "without updating util.COMPOSITE_SET.")

    def test_the_recorded_expectation_matches_the_named_membership(self):
        self.assertEqual(self.thresholds["expected_gauge_count"], len(COMPOSITE_SET))

    def test_the_recorded_bite_matches_the_arithmetic(self):
        needed = minimum_triggered(self.thresholds["alarm_share_pct"],
                                   self.thresholds["expected_gauge_count"])
        self.assertEqual(
            self.thresholds["alarm_bite"],
            f"{needed} of {self.thresholds['expected_gauge_count']}",
            "thresholds.json records an alarm bite that the share no longer produces.",
        )

    def test_the_live_composite_block_counts_only_unparked_members(self):
        live = sum(1 for i in COMPOSITE_SET
                   if self.rows.get(i, {}).get("in_composite"))
        self.assertEqual(self.lens2["composite"]["gauge_count"], live)


if __name__ == "__main__":
    unittest.main()
