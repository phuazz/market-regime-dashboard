"""Lens 2 alarm level on the gauge set now running — the 2026-09-12 recalibration.

Frozen with PREREG.md in the same commit, before any figure was computed.

WHAT IT DOES. Reconstructs the Lens 2 froth composite monthly, point in time, on two
gauge sets that differ in exactly one gauge:

    set A — the eight live at the 2026-07-03 alarm decision (includes NAAIM)
    set B — the seven live today (set A less NAAIM)

and reports, for each candidate arming level, the months each set arms. The criterion is
episode capture, not forward returns: the composite level's lack of a standalone
forward-return edge is already filed (2026-07-03-market-regime-dashboard-1) and is not
re-tested here.

WHAT IS DIFFERENT FROM THE FILED 2026-07-03 RUN.
  * NAAIM history comes from the frozen licensed copy in the sibling sentiment-composite
    repo. naaim.org withdrew the public workbook when it moved to subscription access on
    2026-08-01, so scripts/alarm_calibration.py can no longer fetch it.
  * The IPO gauge is COMPUTED rather than excluded-and-mapped. The filed study inferred
    its 2021 contribution; that inference is silent-failure mode 2 in PREREG.md.

Everything else — the expanding-window percentile discipline, the as-of lookups, the
month-end grid — is imported from scripts/alarm_calibration.py so both studies compute
the same way.

Licence discipline: every history is used in memory. Nothing licensed is written to disk.
Date handling: Python datetime months are 1-indexed; month arithmetic via dateutil only.
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import date
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from alarm_calibration import (          # noqa: E402  the filed run's own helpers
    expanding_percentile_rank,
    fetch_aaii_history,
    last_at_or_before,
    month_ends_from_daily,
    series_upto,
)
from sources import sentiment            # noqa: E402
from sources.fred import fetch_series    # noqa: E402
from sources.prices import fetch_yahoo_daily  # noqa: E402
from util import percentile_rank         # noqa: E402
from dateutil.relativedelta import relativedelta  # noqa: E402

NAAIM_FROZEN = Path(r"C:\dev\sentiment-composite\archive\naaim.csv")
IPO_HISTORY = REPO / "data" / "history" / "renaissance_ipo_proceeds.json"
OUT = Path(__file__).resolve().parent / "result.json"

# Set A is the eight gauges live when 62.5% was adopted; set B drops NAAIM.
SET_A = ("umcsent", "aaii", "pe", "rule20", "nfci", "vvg", "ipo", "naaim")
SET_B = tuple(g for g in SET_A if g != "naaim")

# Candidate levels. Counts matter more than percentages on a seven-gauge set: only
# eight composite values exist, so a level is really a choice of "k of 7".
CANDIDATES = (42.9, 50.0, 57.1, 62.5, 71.4, 75.0, 87.5)
ADOPTED = 62.5

# Windows named in the filed 2026-07-03 study, so the comparison is like for like.
WINDOWS = {
    "2000 top": ("1999-01", "2001-06"),
    "2021 top": ("2021-01", "2022-06"),
    "melt-up 1991-98": ("1991-01", "1998-12"),
    "melt-up 2003-04": ("2003-01", "2004-12"),
    "melt-up 2016-18": ("2016-01", "2018-12"),
    "melt-up 2020-08": ("2020-06", "2020-12"),
}

EPS = 1e-9


def clean_series(dates, values):
    """FRED rows with a value, sorted. Mirrors the filed script's own cleaning."""
    pairs = [(d, v) for d, v in zip(dates, values) if v is not None]
    pairs.sort()
    return [d for d, _ in pairs], [v for _, v in pairs]


def load_frozen_naaim() -> tuple[list[str], list[float]]:
    """The licensed NAAIM history, read in memory and never rewritten.

    Frozen 2026-07-29 by the sibling project when NAAIM paywalled the series.
    """
    if not NAAIM_FROZEN.exists():
        raise SystemExit(f"Frozen NAAIM history not found at {NAAIM_FROZEN}")
    rows = []
    with NAAIM_FROZEN.open(encoding="utf-8", newline="") as handle:
        for row in csv.DictReader(handle):
            rows.append((row["date"], float(row["exposure"])))
    rows.sort()
    return [d for d, _ in rows], [v for _, v in rows]


def load_ipo_annual() -> dict[int, float]:
    """Completed-year US IPO proceeds, USD bn. The current year is dropped."""
    payload = json.loads(IPO_HISTORY.read_text(encoding="utf-8"))
    annual = {}
    for iso, value in zip(payload["dates"], payload["values"]):
        if iso.endswith("-12-31"):                     # completed years only
            annual[int(iso[:4])] = float(value)
    return annual


def ipo_status(year: int, annual: dict[int, float], lag: int, min_priors: int = 3):
    """The IPO gauge as known inside `year`. None when it cannot be evaluated.

    lag=1 is the pre-registered primary: inside year Y a reader knows year Y-1's
    completed proceeds, not Y's. lag=0 is the declared sensitivity and uses the
    current year's completed total, which is look-ahead inside the year.

    The trigger is the live rule: percentile_rank of the reading within the prior
    years available, at or above 80. With three to five priors that rank is coarse
    (multiples of 100/n), so in practice it means "above every prior year".
    """
    reading_year = year - lag
    if reading_year not in annual:
        return None
    priors = [v for y, v in annual.items() if y < reading_year]
    if len(priors) < min_priors:
        return None
    return percentile_rank(priors, annual[reading_year]) >= 80.0


def build_grid(lag: int) -> list[dict]:
    """One row per S&P 500 month-end: per-gauge status, and each set's share."""
    print(f"Fetching histories (in memory, IPO lag={lag})...", file=sys.stderr)
    aaii_d, aaii_v = fetch_aaii_history()
    naaim_d, naaim_v = load_frozen_naaim()
    pe_d, pe_v, _ = sentiment.fetch_multpl_pe_history()
    umc_d, umc_v = clean_series(*fetch_series("UMCSENT"))
    cpi_d, cpi_v = clean_series(*fetch_series("CPIAUCSL"))
    nfci_d, nfci_v = clean_series(*fetch_series("NFCI"))
    rpg_d, rpg_v = fetch_yahoo_daily("RPG", period1=0)
    rpv_d, rpv_v = fetch_yahoo_daily("RPV", period1=0)
    ipo_annual = load_ipo_annual()

    gspc = json.loads((REPO / "data" / "history" / "gspc.json").read_text(encoding="utf-8"))
    spx_ends = month_ends_from_daily(gspc["dates"])

    cpi_by = dict(zip(cpi_d, cpi_v))
    cpi_yoy_by_month: dict[str, float] = {}
    for month in cpi_d:
        # Python months are 1-indexed; relativedelta does the year step.
        base = (date.fromisoformat(month) - relativedelta(years=1)).isoformat()
        if base in cpi_by:
            cpi_yoy_by_month[month] = (cpi_by[month] / cpi_by[base] - 1.0) * 100.0

    def cpi_yoy_at(iso: str):
        month = next((d for d in reversed(cpi_d) if d <= iso), None)
        return cpi_yoy_by_month.get(month) if month else None

    rule20_dates, rule20_sums = [], []
    for d, v in zip(pe_d, pe_v):
        if d >= "1948-01-01" and d[:8] + "01" in cpi_yoy_by_month:
            rule20_dates.append(d)
            rule20_sums.append(v + cpi_yoy_by_month[d[:8] + "01"])

    rpg_by, rpv_by = dict(zip(rpg_d, rpg_v)), dict(zip(rpv_d, rpv_v))
    common_px = sorted(set(rpg_d) & set(rpv_d))

    def value_growth_spread_at(iso: str):
        window = [d for d in common_px if d <= iso]
        if len(window) < 127:
            return None
        last, past = window[-1], window[-127]
        return ((rpg_by[last] / rpg_by[past]) - (rpv_by[last] / rpv_by[past])) * 100.0

    naaim_last = naaim_d[-1] if naaim_d else None

    grid = []
    for iso in spx_ends:
        if date.fromisoformat(iso) < date(1988, 1, 1):
            continue
        statuses: dict[str, bool] = {}

        aaii_hist = series_upto(aaii_d, aaii_v, iso)
        aaii_now = last_at_or_before(aaii_d, aaii_v, iso)
        if aaii_now is not None and len(aaii_hist) >= 156:      # 3-year burn-in
            line = sorted(aaii_hist)[int(0.9 * (len(aaii_hist) - 1))]
            statuses["aaii"] = aaii_now >= line

        pe_hist = series_upto(pe_d, pe_v, iso)
        pe_now = last_at_or_before(pe_d, pe_v, iso)
        if pe_now is not None and pe_hist:
            statuses["pe"] = expanding_percentile_rank(pe_hist, pe_now) >= 90.0

        yoy = cpi_yoy_at(iso)
        if pe_now is not None and yoy is not None:
            sums_hist = series_upto(rule20_dates, rule20_sums, iso)
            total = pe_now + yoy
            statuses["rule20"] = bool(
                sums_hist and total > 20.0
                and expanding_percentile_rank(sums_hist, total) >= 80.0
            )

        nfci_hist = series_upto(nfci_d, nfci_v, iso)
        nfci_now = last_at_or_before(nfci_d, nfci_v, iso)
        if nfci_now is not None and nfci_hist:
            statuses["nfci"] = expanding_percentile_rank(nfci_hist, nfci_now) <= 20.0

        umc_hist = series_upto(umc_d, umc_v, iso)
        umc_now = last_at_or_before(umc_d, umc_v, iso)
        if umc_now is not None and umc_hist:
            statuses["umcsent"] = expanding_percentile_rank(umc_hist, umc_now) >= 75.0

        vvg = value_growth_spread_at(iso)
        if vvg is not None:
            statuses["vvg"] = vvg >= 10.0

        ipo = ipo_status(int(iso[:4]), ipo_annual, lag)
        if ipo is not None:
            statuses["ipo"] = ipo

        # Set A only, and only where the frozen history reaches.
        naaim_now = last_at_or_before(naaim_d, naaim_v, iso)
        if naaim_now is not None and naaim_last is not None and iso <= naaim_last:
            statuses["naaim"] = naaim_now >= 90.0

        row = {"iso": iso, "statuses": statuses}
        for name, members in (("A", SET_A), ("B", SET_B)):
            present = {g: s for g, s in statuses.items() if g in members}
            row[f"n_{name}"] = len(present)
            row[f"k_{name}"] = sum(present.values())
            row[f"share_{name}"] = (100.0 * sum(present.values()) / len(present)
                                    if present else None)
        grid.append(row)
    return grid


def armed_months(grid: list[dict], set_name: str, level: float) -> list[str]:
    key = f"share_{set_name}"
    return [r["iso"] for r in grid if r[key] is not None and r[key] >= level - EPS]


def episodes(months: list[str]) -> list[str]:
    """Group consecutive month-ends into runs, rendered as YYYY-MM or a range."""
    if not months:
        return []
    runs, start, prev = [], months[0], months[0]
    for iso in months[1:]:
        step = (date.fromisoformat(prev[:8] + "01") + relativedelta(months=1)).isoformat()[:7]
        if iso[:7] == step:
            prev = iso
            continue
        runs.append((start, prev))
        start = prev = iso
    runs.append((start, prev))
    return [a[:7] if a[:7] == b[:7] else f"{a[:7]}->{b[:7]}" for a, b in runs]


def in_window(iso: str, window: tuple[str, str]) -> bool:
    return window[0] <= iso[:7] <= window[1]


def summarise(grid: list[dict]) -> dict:
    out: dict = {"levels": {}, "windows": {}}
    for level in CANDIDATES:
        entry = {}
        for set_name in ("A", "B"):
            months = armed_months(grid, set_name, level)
            entry[set_name] = {"months": len(months), "episodes": episodes(months)}
        out["levels"][f"{level:g}"] = entry

    for label, window in WINDOWS.items():
        rows = [r for r in grid if in_window(r["iso"], window)]
        peak = {}
        for set_name in ("A", "B"):
            scored = [r for r in rows if r[f"share_{set_name}"] is not None]
            if not scored:
                peak[set_name] = None
                continue
            best = max(scored, key=lambda r: r[f"share_{set_name}"])
            peak[set_name] = {
                "iso": best["iso"],
                "k": best[f"k_{set_name}"],
                "n": best[f"n_{set_name}"],
                "share": round(best[f"share_{set_name}"], 1),
                "triggered": sorted(g for g, s in best["statuses"].items()
                                    if s and g in (SET_A if set_name == "A" else SET_B)),
            }
        armed = {set_name: {f"{level:g}": [r["iso"][:7] for r in rows
                                           if r[f"share_{set_name}"] is not None
                                           and r[f"share_{set_name}"] >= level - EPS]
                            for level in CANDIDATES}
                 for set_name in ("A", "B")}
        out["windows"][label] = {"peak": peak, "armed": armed}
    return out


def main() -> int:
    primary = build_grid(lag=1)
    sensitivity = build_grid(lag=0)
    payload = {
        "generated_at": date.today().isoformat(),
        "prereg": "reviews/2026-09-12_alarm-recalibration/PREREG.md",
        "set_A": list(SET_A),
        "set_B": list(SET_B),
        "adopted_level": ADOPTED,
        "naaim_frozen_through": load_frozen_naaim()[0][-1],
        "grid_months": len(primary),
        "primary_ipo_lag_1": summarise(primary),
        "sensitivity_ipo_lag_0": summarise(sensitivity),
        "grid": [{k: v for k, v in r.items() if k != "statuses"} | {
            "triggered": sorted(g for g, s in r["statuses"].items() if s)} for r in primary],
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")

    print("\nARMING EPISODES (primary, IPO lag 1)")
    for level, entry in payload["primary_ipo_lag_1"]["levels"].items():
        print(f"  level {level}%  A: {entry['A']['months']:>3} months  "
              f"B: {entry['B']['months']:>3} months")
    for label in WINDOWS:
        w = payload["primary_ipo_lag_1"]["windows"][label]
        print(f"\n{label}")
        for set_name in ("A", "B"):
            p = w["peak"][set_name]
            if p:
                print(f"  peak {set_name}: {p['iso'][:7]} {p['k']} of {p['n']} "
                      f"({p['share']}%) — {', '.join(p['triggered'])}")
            armed = w["armed"][set_name].get(f"{ADOPTED:g}", [])
            print(f"  armed {set_name} at {ADOPTED}%: {armed or 'never'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
