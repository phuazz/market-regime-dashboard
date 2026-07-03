"""Span-encoding tests for the signal map."""
from __future__ import annotations

import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from signal_map import spans_from_flags


def grid(flags: list[bool]) -> list[dict]:
    return [{"iso": f"2020-{i + 1:02d}-28", "x": None, "flag": f} for i, f in enumerate(flags)]


class TestSpans(unittest.TestCase):
    def test_single_run(self):
        spans = spans_from_flags(grid([False, True, True, False]), "flag")
        self.assertEqual(spans, [{"start": "2020-02-28", "end": "2020-03-28"}])

    def test_open_ended_run(self):
        spans = spans_from_flags(grid([False, True, True]), "flag")
        self.assertEqual(spans, [{"start": "2020-02-28", "end": "2020-03-28"}])

    def test_multiple_and_single_month_runs(self):
        spans = spans_from_flags(grid([True, False, True, False, True]), "flag")
        self.assertEqual(len(spans), 3)
        self.assertEqual(spans[1], {"start": "2020-03-28", "end": "2020-03-28"})

    def test_no_runs(self):
        self.assertEqual(spans_from_flags(grid([False, False]), "flag"), [])


if __name__ == "__main__":
    unittest.main()
