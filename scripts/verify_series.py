"""Repeatable two-source verification checks for the dashboard's series.

Usage:
    python scripts/verify_series.py

Runs the automatable identity checks and prints PASS/FAIL per check, exiting
non-zero on any failure. Results belong in VERIFICATION.md alongside the
manual second-source entries (S&P Global PMI, Conference Board LEI, multpl
CAPE, DOL claims), which require reading originating publications.

Checks:
1. T10Y3M equals DGS10 - DGS3MO across the latest 250 common observations.
2. The Sahm construction recomputed from UNRATE matches SAHMREALTIME and
   SAHMCURRENT for the latest month (vintage effects can shift earlier
   months by a few hundredths; the latest month must agree).
3. FRED UNRATE / PAYEMS / UEMP27OV match the BLS public API (originating
   agency) exactly over the trailing twelve months.
"""
from __future__ import annotations

from datetime import date

from sources.bls import BLS_EQUIVALENTS, fetch_bls_series
from sources.fred import fetch_series
from util import clean_series


def check_t10y3m_identity() -> tuple[bool, str]:
    spread = dict(zip(*clean_series(*fetch_series("T10Y3M"))))
    ten = dict(zip(*clean_series(*fetch_series("DGS10"))))
    three = dict(zip(*clean_series(*fetch_series("DGS3MO"))))
    common = sorted(set(spread) & set(ten) & set(three))[-250:]
    worst = max(abs(spread[d] - (ten[d] - three[d])) for d in common)
    ok = worst <= 0.011  # both sides publish at two decimals
    return ok, (
        f"T10Y3M vs DGS10-DGS3MO over {len(common)} recent observations: "
        f"max abs difference {worst:.4f}"
    )


def recompute_sahm(unrate: list[float]) -> float:
    avg3 = [sum(unrate[i - 2 : i + 1]) / 3 for i in range(2, len(unrate))]
    return round(avg3[-1] - min(avg3[-13:-1]), 2)


def check_sahm_recompute() -> tuple[bool, str]:
    _, unrate = clean_series(*fetch_series("UNRATE"))
    rt_dates, rt_values = clean_series(*fetch_series("SAHMREALTIME"))
    cu_dates, cu_values = clean_series(*fetch_series("SAHMCURRENT"))
    ours = recompute_sahm(unrate)
    ok = abs(ours - rt_values[-1]) <= 0.005 and abs(ours - cu_values[-1]) <= 0.005
    return ok, (
        f"Sahm latest ({rt_dates[-1]}): recomputed {ours:+.2f}, "
        f"SAHMREALTIME {rt_values[-1]:+.2f}, SAHMCURRENT {cu_values[-1]:+.2f}"
    )


def check_bls_vs_fred() -> tuple[bool, str]:
    year = date.today().year
    bls = fetch_bls_series(list(BLS_EQUIVALENTS.values()), year - 1, year)
    mismatches = []
    months_checked = 0
    for fred_id, bls_id in BLS_EQUIVALENTS.items():
        dates, values = clean_series(*fetch_series(fred_id))
        recent = dict(zip(dates, values))
        for d, v in bls[bls_id].items():
            if d in recent:
                months_checked += 1
                if abs(recent[d] - v) > 0.051:
                    mismatches.append(f"{fred_id} {d}: FRED {recent[d]} vs BLS {v}")
    ok = not mismatches and months_checked >= 12
    detail = f"{months_checked} month-values compared across three series"
    if mismatches:
        detail += "; mismatches: " + "; ".join(mismatches[:5])
    return ok, detail


def main() -> int:
    checks = [
        ("T10Y3M identity (spread equals components)", check_t10y3m_identity),
        ("Sahm recomputation from UNRATE", check_sahm_recompute),
        ("BLS API vs FRED labour series", check_bls_vs_fred),
    ]
    failed = 0
    for name, check in checks:
        try:
            ok, detail = check()
        except Exception as error:  # noqa: BLE001 — report and continue
            ok, detail = False, f"check crashed: {error}"
        print(f"{'PASS' if ok else 'FAIL'}  {name} — {detail}")
        failed += 0 if ok else 1

    print(
        "Manual-log reminders (see VERIFICATION.md): S&P Global PMI release, "
        "Conference Board LEI release, multpl CAPE vs GuruFocus, DOL claims "
        "release vs CCSA."
    )
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
