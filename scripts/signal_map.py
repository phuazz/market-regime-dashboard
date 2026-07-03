"""Signal map data (SPEC.md section 8).

Usage:
    python scripts/signal_map.py

Writes data/signal_map.json: monthly S&P 500 closes from 1990 for the
log-scale map, NBER recession spans (FRED `USREC`, verified against the
NBER chronology on 2026-07-03 — see VERIFICATION.md), Lens 1 core elevated
spans, Lens 2 alarm crossings, and combined act-rule spans. These are the
same point-in-time reconstructions filed with the phase 4 calibration and
the phase 5 forward-return study; this script only renders them spatially.
Run on demand, like scripts/forward_returns.py.

Window note: SPEC section 8 sketches 2006-present; the map starts 1990 so
the dot-com episode — the strongest act-rule case — stays visible. Trim by
changing START below.
"""
from __future__ import annotations

from forward_returns import build_signal_grid
from sources.fred import fetch_series
from util import DATA_DIR, ROOT, dump_json, utc_now_iso

START = "1990-01-01"


def spans_from_flags(grid: list[dict], key: str) -> list[dict]:
    """Contiguous True runs as {start, end} ISO spans (inclusive)."""
    spans: list[dict] = []
    run_start: str | None = None
    run_end: str | None = None
    for g in grid:
        if g[key]:
            if run_start is None:
                run_start = g["iso"]
            run_end = g["iso"]
        elif run_start is not None:
            spans.append({"start": run_start, "end": run_end})
            run_start = run_end = None
    if run_start is not None:
        spans.append({"start": run_start, "end": run_end})
    return spans


def usrec_spans(start_iso: str) -> list[dict]:
    dates, values = fetch_series("USREC")
    spans: list[dict] = []
    run_start: str | None = None
    run_end: str | None = None
    for d, v in zip(dates, values):
        if v == 1:
            if run_start is None:
                run_start = d
            run_end = d
        elif run_start is not None:
            spans.append({"start": run_start, "end": run_end})
            run_start = run_end = None
    if run_start is not None:
        spans.append({"start": run_start, "end": run_end})
    return [s for s in spans if s["end"] >= start_iso]


def bear_spans(grid: list[dict], threshold_pct: float = -20.0) -> list[dict]:
    """S&P bear periods (peak month to trough month) from monthly closes.

    A bear episode opens when the drawdown from the running peak breaches
    the threshold; it spans from the peak month to the lowest close before
    the prior peak is regained.
    """
    spans: list[dict] = []
    peak_iso, peak = grid[0]["iso"], grid[0]["close"]
    trough_iso, trough = peak_iso, peak
    in_bear = False
    for g in grid:
        if g["close"] >= peak:
            if in_bear:
                spans.append({"start": peak_iso, "end": trough_iso})
                in_bear = False
            peak_iso, peak = g["iso"], g["close"]
            trough_iso, trough = g["iso"], g["close"]
            continue
        if g["close"] < trough:
            trough_iso, trough = g["iso"], g["close"]
        if (g["close"] / peak - 1.0) * 100.0 <= threshold_pct:
            in_bear = True
    if in_bear:
        spans.append({"start": peak_iso, "end": trough_iso})
    return spans


def main() -> int:
    grid, meta = build_signal_grid()
    window = [g for g in grid if g["iso"] >= START]

    # Shared context bands for the per-indicator history charts: full-depth
    # NBER recessions and S&P bear periods over the stored price history.
    dump_json(DATA_DIR / "chart_context.json", {
        "computed_as_of": utc_now_iso(),
        "recessions": usrec_spans("1900-01-01"),
        "bears": bear_spans(grid),
        "note": (
            "Recessions per NBER (FRED USREC, verified); bears are S&P 500 declines of "
            "20% or more from a monthly-close peak, spanning peak month to trough month."
        ),
    })

    crossings = []
    previous = False
    for g in window:
        if g["lens2_alarm"] and not previous:
            crossings.append({"iso": g["iso"], "close": g["close"]})
        previous = g["lens2_alarm"]

    payload = {
        "computed_as_of": utc_now_iso(),
        "start": START,
        "alarm_share_pct": meta["alarm_share_pct"],
        "note": (
            "Point-in-time reconstructions (phases 4-5, filed in reviews/): Lens 1 core "
            "omits HY/PMI/LEI (no free history); the Lens 2 reconstruction omits the IPO "
            "gauge, so historical shares understate live ones in deal-froth eras (2022 "
            "does not cross on the reconstruction). Recessions per NBER via FRED USREC."
        ),
        "months": {
            "dates": [g["iso"] for g in window],
            "closes": [g["close"] for g in window],
        },
        "recessions": usrec_spans(START),
        "lens1_spans": spans_from_flags(window, "lens1_core"),
        "act_spans": spans_from_flags(window, "combined_act"),
        "lens2_crossings": crossings,
    }
    out = DATA_DIR / "signal_map.json"
    dump_json(out, payload)
    print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size:,} bytes)")
    print(f"months {len(window)}, recessions {len(payload['recessions'])}, "
          f"lens1 spans {len(payload['lens1_spans'])}, act spans {len(payload['act_spans'])}, "
          f"lens2 crossings {len(crossings)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
