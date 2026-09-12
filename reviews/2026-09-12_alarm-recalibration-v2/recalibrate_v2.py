"""Lens 2 alarm level on real-time data — the 2026-09-12 re-run.

Frozen with PREREG.md in the same commit, before any figure was computed.

WHY A SECOND RUN. The first study scored every gauge on today's vintage. NFCI is
re-estimated weekly across its whole history, and over 2016-2019 the revisions run one
way: 2017-08-25 read -0.87 on the vintage of the day (inside the loosest quintile) and
reads -0.56 today (outside it). Two of that study's three stated reasons were artefacts of
that. This run scores NFCI on the vintage a reader would have held, and adds the two things
the first study argued from but never computed: the joint rule, and the IPO gauge's
divergence from the live rule.

WHAT IS COMPUTED
  * the composite monthly, point in time, on two gauge sets (A = the eight live at the
    2026-07-03 decision, B = the seven live today) and two IPO arms (excluded / lagged
    proxy), with NFCI on ALFRED vintages;
  * the same grid with NFCI on current vintage, so the vintage effect is isolated rather
    than confounded with everything else;
  * Lens 3's bear condition to the live rule, so the risk-reduction signal itself can be
    evaluated instead of inferred from arming months;
  * for every candidate level: arming months, melt-up arms, the first arm at the 2021 top,
    and FIRED months under the joint rule.

Licence discipline: histories are used in memory. The NFCI vintage cache is written to the
session scratchpad, never into the repository.
Date handling: Python datetime months are 1-indexed; month arithmetic via dateutil only.
"""
from __future__ import annotations

import csv
import io
import json
import os
import sys
import time
import urllib.request
from datetime import date, timedelta
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(REPO / "scripts"))

from alarm_calibration import (          # noqa: E402  the filed run's own helpers
    expanding_percentile_rank,
    last_at_or_before,
    month_ends_from_daily,
    series_upto,
)
from sources import sentiment            # noqa: E402
from sources.fred import fetch_series    # noqa: E402
from sources.prices import fetch_yahoo_daily  # noqa: E402
from sources.sentiment import percentile_rank  # noqa: E402
from dateutil.relativedelta import relativedelta  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "result_v2.json"
NAAIM_FROZEN = Path(r"C:\dev\sentiment-composite\archive\naaim.csv")
AAII_CACHED = Path(r"C:\dev\sentiment-composite\archive\aaii.csv")
IPO_HISTORY = REPO / "data" / "history" / "renaissance_ipo_proceeds.json"

# Vintage cache. Outside the repo by design: it is bulky, derived, and refetchable.
CACHE = Path(os.environ.get("ALFRED_CACHE") or (
    Path(os.environ.get("TEMP", "/tmp")) / "claude" / "alfred_nfci_cache"))

CORE = ("umcsent", "aaii", "pe", "rule20", "nfci", "vvg")
SET_A = CORE + ("naaim",)          # the eight live at the 2026-07-03 decision, less IPO
SET_B = CORE                        # the seven live today, less IPO
CANDIDATES = (42.9, 50.0, 57.1, 62.5, 71.4, 75.0, 87.5)
ADOPTED = 62.5
VINTAGE_LAG_DAYS = 7                # declared in PREREG; sensitivity at 3 and 14
# ALFRED's earliest NFCI vintage, located by bisection. The index was introduced in
# 2011 and its history backfilled to 1971, so before this date the gauge did not exist
# for anyone to read. PREREG amendment 2.
FIRST_NFCI_VINTAGE = "2011-05-25"
SENSITIVITY_LAGS = (3, 14)
NEAR_LINE_RANK_PP = 5.0             # a gauge this close to its line is "cannot call"

WINDOWS = {
    "2000 top": ("1999-01", "2001-06"),
    "2021 top": ("2021-01", "2022-06"),
    "melt-up 1991-98": ("1991-01", "1998-12"),
    "melt-up 2003-04": ("2003-01", "2004-12"),
    "melt-up 2016-18": ("2016-01", "2018-12"),
    "melt-up 2020-08": ("2020-06", "2020-12"),
}
EPS = 1e-9


# --------------------------------------------------------------------------- #
# NFCI, as it stood at the time
# --------------------------------------------------------------------------- #
def alfred_nfci(vintage: str) -> list[tuple[str, float]]:
    """The whole NFCI history as published at `vintage`. Cached on disk."""
    CACHE.mkdir(parents=True, exist_ok=True)
    cached = CACHE / f"nfci_{vintage}.csv"
    if cached.exists():
        raw = cached.read_text(encoding="utf-8")
    else:
        url = ("https://alfred.stlouisfed.org/graph/alfredgraph.csv?id=NFCI"
               f"&vintage_date={vintage}&cosd=1971-01-08")
        for attempt in range(4):
            try:
                raw = urllib.request.urlopen(url, timeout=90).read().decode("utf-8")
                break
            except Exception as exc:                       # noqa: BLE001
                if attempt == 3:
                    raise RuntimeError(f"ALFRED failed for {vintage}: {exc}") from exc
                time.sleep(2 * (attempt + 1))
        cached.write_text(raw, encoding="utf-8")
        time.sleep(0.15)                                   # courtesy to ALFRED
    rows = []
    for row in csv.DictReader(io.StringIO(raw)):
        keys = list(row)
        value = row[keys[1]]
        if value not in (".", "", None):
            rows.append((row[keys[0]], float(value)))
    return rows


def nfci_at(month_end: str, lag_days: int) -> tuple[float, float] | None:
    """(value, expanding rank) for `month_end` on the vintage published `lag_days` later.

    The rank is computed from the vintage's OWN history, so the line moves as it moved in
    life: the Chicago Fed re-estimates the whole series, not just its tail.

    None before FIRST_NFCI_VINTAGE. ALFRED holds no vintage before 2011-05-25 because the
    NFCI did not exist before 2011 — the history to 1971 is backfilled. In a real-time
    reading the gauge is therefore simply absent in that era, not quiet. See PREREG
    amendment 2: this makes the credit-complacency gauge in every pre-2011 month of both
    prior studies a hindsight construct.
    """
    if month_end < FIRST_NFCI_VINTAGE:
        return None
    vintage = (date.fromisoformat(month_end) + timedelta(days=lag_days)).isoformat()
    if vintage < FIRST_NFCI_VINTAGE:
        vintage = FIRST_NFCI_VINTAGE
    if vintage > date.today().isoformat():
        vintage = date.today().isoformat()
    rows = alfred_nfci(vintage)
    hist = [v for d, v in rows if d <= month_end]
    if not hist:
        return None
    current = hist[-1]
    return current, 100.0 * sum(1 for v in hist if v <= current) / len(hist)


# --------------------------------------------------------------------------- #
# Other inputs
# --------------------------------------------------------------------------- #
def clean_series(dates, values):
    pairs = sorted((d, v) for d, v in zip(dates, values) if v is not None)
    return [d for d, _ in pairs], [v for _, v in pairs]


def load_cached_aaii() -> tuple[list[str], list[float]]:
    """AAII bull-bear spread from the sibling project's cache. PREREG amendment 1.

    aaii.com returns 403 and an HTML body to this client; the CI runner still fetches it,
    so the series is fine and this is a bot block on this address. The survey is never
    revised, so a cached copy equals a live fetch, and it was cross-checked against this
    repository's own scraped history (8 overlapping weeks, max difference 0.045 pp) before
    the run. Used in memory, never written here.
    """
    if not AAII_CACHED.exists():
        raise SystemExit(f"Cached AAII history not found at {AAII_CACHED}")
    with AAII_CACHED.open(encoding="utf-8", newline="") as handle:
        rows = sorted((r["date"], float(r["bullish"]) - float(r["bearish"]))
                      for r in csv.DictReader(handle))
    return [d for d, _ in rows], [v for _, v in rows]


def load_frozen_naaim() -> tuple[list[str], list[float]]:
    if not NAAIM_FROZEN.exists():
        raise SystemExit(f"Frozen NAAIM history not found at {NAAIM_FROZEN}")
    with NAAIM_FROZEN.open(encoding="utf-8", newline="") as handle:
        rows = sorted((r["date"], float(r["exposure"])) for r in csv.DictReader(handle))
    return [d for d, _ in rows], [v for _, v in rows]


def load_ipo_annual() -> dict[int, float]:
    payload = json.loads(IPO_HISTORY.read_text(encoding="utf-8"))
    return {int(iso[:4]): float(v) for iso, v in zip(payload["dates"], payload["values"])
            if iso.endswith("-12-31")}


def ipo_lagged(year: int, annual: dict[int, float], min_priors: int = 3):
    """The lagged-proxy arm. NOT the live rule — see PREREG change 2."""
    reading_year = year - 1
    if reading_year not in annual:
        return None
    priors = [v for y, v in annual.items() if y < reading_year]
    if len(priors) < min_priors:
        return None
    return percentile_rank(priors, annual[reading_year]) >= 80.0


def sma(values: list[float], window: int) -> list[float | None]:
    out: list[float | None] = [None] * len(values)
    running = 0.0
    for i, v in enumerate(values):
        running += v
        if i >= window:
            running -= values[i - window]
        if i >= window - 1:
            out[i] = running / window
    return out


def lens3_bear_months(dates: list[str], closes: list[float],
                      lookback: int = 20, tolerance: float = 0.1) -> dict[str, bool]:
    """Lens 3's bear condition per month-end, to the live rule in scripts/lens3.py.

    50-day below 150-day, and both slopes at or below +tolerance% over `lookback`
    sessions. Reconstructed because the risk-reduction signal needs Lens 3 and Lens 2 in
    the SAME month: the rule carries no memory of an earlier arm.
    """
    s50, s150 = sma(closes, 50), sma(closes, 150)
    out = {}
    for i, iso in enumerate(dates):
        a, b = s50[i], s150[i]
        if a is None or b is None or i < lookback:
            continue
        pa, pb = s50[i - lookback], s150[i - lookback]
        if pa is None or pb is None or pa == 0 or pb == 0:
            continue
        slope50 = (a / pa - 1.0) * 100.0
        slope150 = (b / pb - 1.0) * 100.0
        out[iso] = bool(a < b and slope50 <= tolerance and slope150 <= tolerance)
    return out


# --------------------------------------------------------------------------- #
# The grid
# --------------------------------------------------------------------------- #
def build_grid(nfci_mode: str, lag_days: int = VINTAGE_LAG_DAYS) -> list[dict]:
    """nfci_mode: 'vintage' (as published then) or 'current' (today's estimates)."""
    print(f"Building grid: NFCI {nfci_mode}, lag {lag_days}d", file=sys.stderr)
    aaii_d, aaii_v = load_cached_aaii()
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
    bear = lens3_bear_months(gspc["dates"], gspc["values"])

    cpi_by = dict(zip(cpi_d, cpi_v))
    cpi_yoy: dict[str, float] = {}
    for month in cpi_d:
        # Python months are 1-indexed; relativedelta does the year step.
        base = (date.fromisoformat(month) - relativedelta(years=1)).isoformat()
        if base in cpi_by:
            cpi_yoy[month] = (cpi_by[month] / cpi_by[base] - 1.0) * 100.0

    def cpi_yoy_at(iso: str):
        month = next((d for d in reversed(cpi_d) if d <= iso), None)
        return cpi_yoy.get(month) if month else None

    rule20_dates, rule20_sums = [], []
    for d, v in zip(pe_d, pe_v):
        if d >= "1948-01-01" and d[:8] + "01" in cpi_yoy:
            rule20_dates.append(d)
            rule20_sums.append(v + cpi_yoy[d[:8] + "01"])

    rpg_by, rpv_by = dict(zip(rpg_d, rpg_v)), dict(zip(rpv_d, rpv_v))
    common_px = sorted(set(rpg_d) & set(rpv_d))

    def vvg_at(iso: str):
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
        near: list[str] = []            # gauges within NEAR_LINE_RANK_PP of their line

        aaii_hist = series_upto(aaii_d, aaii_v, iso)
        aaii_now = last_at_or_before(aaii_d, aaii_v, iso)
        if aaii_now is not None and len(aaii_hist) >= 156:
            line = sorted(aaii_hist)[int(0.9 * (len(aaii_hist) - 1))]
            statuses["aaii"] = aaii_now >= line

        pe_hist = series_upto(pe_d, pe_v, iso)
        pe_now = last_at_or_before(pe_d, pe_v, iso)
        if pe_now is not None and pe_hist:
            rank = expanding_percentile_rank(pe_hist, pe_now)
            statuses["pe"] = rank >= 90.0
            if abs(rank - 90.0) <= NEAR_LINE_RANK_PP:
                near.append("pe")

        yoy = cpi_yoy_at(iso)
        if pe_now is not None and yoy is not None:
            sums_hist = series_upto(rule20_dates, rule20_sums, iso)
            total = pe_now + yoy
            if sums_hist:
                rank = expanding_percentile_rank(sums_hist, total)
                statuses["rule20"] = bool(total > 20.0 and rank >= 80.0)
                if total > 20.0 and abs(rank - 80.0) <= NEAR_LINE_RANK_PP:
                    near.append("rule20")

        if nfci_mode == "vintage":
            read = nfci_at(iso, lag_days)
            if read is not None:
                _, rank = read
                statuses["nfci"] = rank <= 20.0
                if abs(rank - 20.0) <= NEAR_LINE_RANK_PP:
                    near.append("nfci")
        else:
            hist = series_upto(nfci_d, nfci_v, iso)
            now = last_at_or_before(nfci_d, nfci_v, iso)
            if now is not None and hist:
                rank = expanding_percentile_rank(hist, now)
                statuses["nfci"] = rank <= 20.0
                if abs(rank - 20.0) <= NEAR_LINE_RANK_PP:
                    near.append("nfci")

        umc_hist = series_upto(umc_d, umc_v, iso)
        umc_now = last_at_or_before(umc_d, umc_v, iso)
        if umc_now is not None and umc_hist:
            rank = expanding_percentile_rank(umc_hist, umc_now)
            statuses["umcsent"] = rank >= 75.0
            if abs(rank - 75.0) <= NEAR_LINE_RANK_PP:
                near.append("umcsent")

        vvg = vvg_at(iso)
        if vvg is not None:
            statuses["vvg"] = vvg >= 10.0

        naaim_now = last_at_or_before(naaim_d, naaim_v, iso)
        if naaim_now is not None and naaim_last and iso <= naaim_last:
            statuses["naaim"] = naaim_now >= 90.0

        ipo = ipo_lagged(int(iso[:4]), ipo_annual)

        row = {"iso": iso, "near_line": near, "lens3_bear": bear.get(iso),
               "triggered": sorted(g for g, s in statuses.items() if s)}
        for set_name, members in (("A", SET_A), ("B", SET_B)):
            for arm in ("excl", "lag"):
                present = {g: s for g, s in statuses.items() if g in members}
                if arm == "lag" and ipo is not None:
                    present["ipo"] = ipo
                n, k = len(present), sum(present.values())
                row[f"n_{set_name}_{arm}"] = n
                row[f"k_{set_name}_{arm}"] = k
                row[f"share_{set_name}_{arm}"] = round(100.0 * k / n, 1) if n else None
        grid.append(row)
    return grid


# --------------------------------------------------------------------------- #
# Reporting
# --------------------------------------------------------------------------- #
def armed(grid, set_name, arm, level):
    key = f"share_{set_name}_{arm}"
    return [r["iso"] for r in grid if r[key] is not None and r[key] >= level - EPS]


def fired(grid, set_name, arm, level):
    """Lens 2 armed AND Lens 3 confirming in the same month — the rule as coded."""
    key = f"share_{set_name}_{arm}"
    return [r["iso"] for r in grid
            if r[key] is not None and r[key] >= level - EPS and r.get("lens3_bear")]


def episodes(months):
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


def summarise(grid) -> dict:
    out = {"levels": {}, "windows": {}, "lens3_bear_months": [r["iso"] for r in grid
                                                              if r.get("lens3_bear")]}
    for level in CANDIDATES:
        entry = {}
        for set_name in ("A", "B"):
            for arm in ("excl", "lag"):
                months = armed(grid, set_name, arm, level)
                entry[f"{set_name}_{arm}"] = {
                    "months": len(months),
                    "episodes": episodes(months),
                    "post_2006": [e for e in episodes(months) if e >= "2007"],
                    "fired": [m[:7] for m in fired(grid, set_name, arm, level)],
                }
        out["levels"][f"{level:g}"] = entry
    for label, (lo, hi) in WINDOWS.items():
        rows = [r for r in grid if lo <= r["iso"][:7] <= hi]
        out["windows"][label] = {
            f"{s}_{a}": {f"{lvl:g}": [r["iso"][:7] for r in rows
                                      if r[f"share_{s}_{a}"] is not None
                                      and r[f"share_{s}_{a}"] >= lvl - EPS]
                         for lvl in CANDIDATES}
            for s in ("A", "B") for a in ("excl", "lag")
        }
        out["windows"][label]["cannot_call"] = sorted(
            {r["iso"][:7] for r in rows if r["near_line"]})
    return out


def guard_lens3(grid) -> dict:
    """PREREG guard 3: the reconstruction must agree with the live lens3 status."""
    live = json.loads((REPO / "data" / "lens3.json").read_text(encoding="utf-8"))
    status = live["indicators"][0]["status"]
    latest = [r for r in grid if r.get("lens3_bear") is not None][-1]
    agrees = (status == "elevated") == bool(latest["lens3_bear"])
    return {"live_status": status, "reconstructed_latest": latest["iso"],
            "reconstructed_bear": latest["lens3_bear"], "agrees": agrees}


def main() -> int:
    vintage = build_grid("vintage")
    current = build_grid("current")
    sens = {f"lag_{d}": summarise(build_grid("vintage", lag_days=d)) for d in SENSITIVITY_LAGS}

    guard = guard_lens3(vintage)
    payload = {
        "generated_at": date.today().isoformat(),
        "prereg": "reviews/2026-09-12_alarm-recalibration-v2/PREREG.md",
        "set_A": list(SET_A), "set_B": list(SET_B),
        "vintage_lag_days": VINTAGE_LAG_DAYS,
        "lens3_guard": guard,
        "grid_months": len(vintage),
        "real_time": summarise(vintage),
        "current_vintage": summarise(current),
        "vintage_lag_sensitivity": sens,
        "grid": vintage,
    }
    OUT.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {OUT}")
    if not guard["agrees"]:
        print("GUARD FAILED: Lens 3 reconstruction disagrees with the live status.",
              file=sys.stderr)
        return 1

    for label, data in (("REAL-TIME NFCI", payload["real_time"]),
                        ("CURRENT-VINTAGE NFCI", payload["current_vintage"])):
        print(f"\n===== {label}")
        for level in CANDIDATES:
            e = data["levels"][f"{level:g}"]["B_excl"]
            f = data["levels"][f"{level:g}"]["B_lag"]
            print(f"  {level:>5}%  B excl: {e['months']:>3} armed / {len(e['fired'])} fired"
                  f"   B lag: {f['months']:>3} armed / {len(f['fired'])} fired")
        w = data["windows"]["2021 top"]
        for lvl in ("42.9", "57.1", "62.5", "71.4"):
            print(f"  2021 B_excl @{lvl}%: {[m[5:] for m in w['B_excl'][lvl]] or 'never'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
