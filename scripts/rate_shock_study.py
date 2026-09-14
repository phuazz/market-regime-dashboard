"""Rate-shock study — does a spike in the 10-year Treasury yield derail an equity bull market?

Runs the battery frozen in `reviews/2026-09-13_rate-shock_PREREG.md` (Amendment 1,
2026-09-14). Read that document before changing anything here: every threshold, arm,
null and gate in this file is pre-registered, and a change to one of them is not a code
change, it is a protocol breach.

Run on demand. This is deliberately NOT wired into any scheduled workflow, following the
`forward_returns.py` precedent — a study is run once and filed, not refreshed nightly.

    python scripts/rate_shock_study.py --step0    # availability probes, FAIL_STOP
    python scripts/rate_shock_study.py --run      # the battery, writes the results files

Standard library plus `dateutil` only, matching the rest of this repository. Nothing here
adds a dependency: an import missing from requirements.txt silently broke the daily
refresh once already (2026-07-04, fixed in 8c14518), and every workflow gates on
`unittest discover`.

DATES: all month arithmetic through `dateutil` (Python months are 1-indexed). Session
offsets are INDEX offsets into the common trading-session list, never calendar-day
arithmetic — the prereg requires this, and it is also the only way 63 sessions means the
same thing in 1966 and 2026.
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from datetime import date

from dateutil.parser import isoparse

from sources.fred import fetch_series
from sources.prices import fetch_yahoo_daily

# --- pre-registered constants (PREREG §3, §4). Do not tune. ----------------------------
DGS10_SERIES = "DGS10"
SPX_SYMBOL = "^GSPC"

WINDOW_START = date(1962, 1, 1)
SEEN_ARM_START = date(1995, 1, 1)      # the BCA chart's window; SEEN, no confirmatory status
CONFIRM_ARM_END = date(1994, 12, 31)   # downgraded to probably-unseen by Amendment 1

SHOCK_SESSIONS = 63                    # ~3 months, the claim as published
REARM_SESSIONS = 126                   # ~6 months between triggers; episode = trigger
VOL_WINDOW_YEARS = 10                  # A3 scaling window, closing at t-63
HORIZONS = (63, 126, 252)              # headline 252
HEADLINE_HORIZON = 252
PERCENTILES = (90, 95, 99)             # our thresholds; headline p95
HEADLINE_PERCENTILE = 95
BCA_REPLICATION_BP = 100.0             # their published line — replication target ONLY

# Step-0 FAIL_STOP bars (PREREG §3).
MIN_DGS10_OBS = 15_000
MIN_SPX_OBS = 15_000
MIN_CONFIRM_SESSIONS = 8_000
MIN_ALIGNMENT_SHARE = 0.98
FIRST_DATE_NO_LATER_THAN = date(1962, 1, 31)
MAX_SESSION_GAP = 15                   # consecutive-observation gap, in observations of the other series


class Step0Failure(RuntimeError):
    """Raised when a pre-registered availability probe fails. No partial run follows."""


# --- data layer -----------------------------------------------------------------------

def load_yields() -> dict[str, float]:
    """DGS10 as {iso date: percent}. FRED writes '.' for a non-publication day."""
    dates, values = fetch_series(DGS10_SERIES)
    return {d: float(v) for d, v in zip(dates, values) if v is not None}


def load_spx() -> dict[str, float]:
    """^GSPC daily closes as {iso date: close}.

    Price-only, no dividends — disclosed in PREREG §3. Conditional and base statistics
    are computed on the identical basis, so the comparison stays like-for-like; absolute
    return levels are understated throughout and the write-up must say so.
    """
    dates, values = fetch_yahoo_daily(SPX_SYMBOL)
    return {d: float(v) for d, v in zip(dates, values) if v is not None}


def common_sessions(yields: dict[str, float], spx: dict[str, float]) -> list[str]:
    """Sorted dates on which BOTH series print, from WINDOW_START.

    This list IS the trading calendar for the study. Every offset in the battery — the
    63-session shock window, the 126-session re-arm, the 252-session outcome horizon — is
    an index offset into it, so alignment between the two series is guaranteed by
    construction rather than asserted.
    """
    start = WINDOW_START.isoformat()
    return sorted(d for d in (yields.keys() & spx.keys()) if d >= start)


# --- Step 0: availability probes (PREREG §3). Any failure stops the study. -------------

def _max_gap(sessions: list[str], universe: list[str]) -> tuple[int, str]:
    """Largest run of `universe` dates missing between consecutive `sessions` entries."""
    index = {d: i for i, d in enumerate(universe)}
    worst, where = 0, ""
    for earlier, later in zip(sessions, sessions[1:]):
        gap = index[later] - index[earlier] - 1
        if gap > worst:
            worst, where = gap, f"{earlier} to {later}"
    return worst, where


def step0(verbose: bool = True) -> dict:
    """Run every pre-registered probe. Raises Step0Failure on the first bar missed."""
    checks: list[tuple[str, bool, str]] = []

    yields = load_yields()
    spx = load_spx()

    y_dates = sorted(yields)
    s_dates = sorted(spx)
    y_first = isoparse(y_dates[0]).date()
    s_first = isoparse(s_dates[0]).date()

    checks.append((
        f"{DGS10_SERIES} observation count",
        len(y_dates) >= MIN_DGS10_OBS,
        f"{len(y_dates):,} (bar {MIN_DGS10_OBS:,})"))
    checks.append((
        f"{DGS10_SERIES} starts on or before {FIRST_DATE_NO_LATER_THAN}",
        y_first <= FIRST_DATE_NO_LATER_THAN,
        f"first observation {y_first}"))
    checks.append((
        f"{SPX_SYMBOL} observation count",
        len(s_dates) >= MIN_SPX_OBS,
        f"{len(s_dates):,} (bar {MIN_SPX_OBS:,})"))
    checks.append((
        f"{SPX_SYMBOL} starts on or before {FIRST_DATE_NO_LATER_THAN}",
        s_first <= FIRST_DATE_NO_LATER_THAN,
        f"first observation {s_first}"))

    sessions = common_sessions(yields, spx)
    confirm = [d for d in sessions if d <= CONFIRM_ARM_END.isoformat()]
    seen = [d for d in sessions if d >= SEEN_ARM_START.isoformat()]

    checks.append((
        f"confirmatory arm {WINDOW_START.year}-{CONFIRM_ARM_END.year} common sessions",
        len(confirm) >= MIN_CONFIRM_SESSIONS,
        f"{len(confirm):,} (bar {MIN_CONFIRM_SESSIONS:,})"))

    # Alignment: of the equity sessions inside the window, how many also carry a yield?
    in_window = [d for d in s_dates if d >= WINDOW_START.isoformat()]
    share = len(sessions) / len(in_window) if in_window else 0.0
    checks.append((
        "yield/equity session alignment",
        share >= MIN_ALIGNMENT_SHARE,
        f"{share:.4%} of {len(in_window):,} equity sessions (bar {MIN_ALIGNMENT_SHARE:.0%})"))

    gap, where = _max_gap(sessions, in_window)
    checks.append((
        "largest run of equity sessions with no yield print",
        gap <= MAX_SESSION_GAP,
        f"{gap} sessions{(' at ' + where) if where else ''} (bar {MAX_SESSION_GAP})"))

    if verbose:
        for label, ok, detail in checks:
            print(f"  {'PASS' if ok else 'FAIL'}  {label:<58} {detail}")
        print(f"\n  common sessions {sessions[0]} to {sessions[-1]}: {len(sessions):,}")
        print(f"  confirmatory arm (to {CONFIRM_ARM_END}): {len(confirm):,}")
        print(f"  seen arm (from {SEEN_ARM_START}):        {len(seen):,}")

    failed = [label for label, ok, _ in checks if not ok]
    if failed:
        raise Step0Failure(
            "Step-0 probes failed, so the study does not run and no partial result is "
            f"filed (PREREG §3): {'; '.join(failed)}")

    return {"yields": yields, "spx": spx, "sessions": sessions,
            "confirm_sessions": confirm, "seen_sessions": seen}


def main(argv: list[str]) -> int:
    if "--step0" in argv:
        try:
            step0()
        except Step0Failure as exc:
            print(f"\n  --> STOP: {exc}")
            return 1
        print("\n  --> step0: all probes pass; the battery may run")
        return 0
    print(__doc__)
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
