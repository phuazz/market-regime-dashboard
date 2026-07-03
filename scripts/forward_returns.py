"""Conditional forward-return panels (SPEC.md section 7).

Usage:
    python scripts/forward_returns.py

For each lens signal and for the combined act rule, computes the S&P 500
forward 3-, 6-, and 12-month return distribution conditioned on the signal
being active, against the unconditional base rate over the same window, on
a point-in-time monthly grid. Writes data/forward_returns.json for the
dashboard panel. Run on demand — the distributions move slowly and the
scrape-heavy reconstruction does not belong in the scheduled workflows.

Signal reconstructions (documented availability, arms treated
conservatively as quiet where a series does not yet exist):
- Lens 1 core: yield-curve re-steepening window (T10Y3M, 1982 onwards) OR
  Sahm at/above 0.50 (SAHMREALTIME — real-time by construction) OR labour
  elevated (unemployment rise at/above 0.35 pp or negative three-month
  payroll change). HY OAS, PMI, and LEI are excluded — no free history —
  so this is the recession-timing core, not the full seven-row lens.
- Lens 2: composite share at/above the adopted 62.5% alarm (five gauges
  from 1990, seven from 2007; the IPO gauge is not reconstructable, which
  biases historical shares down in deal-froth eras).
- Lens 3: 50-day SMA below 150-day with both flat or falling (bear
  trigger), from stored daily closes (1970 onwards).
- Combined act: (Lens 1 core OR Lens 2 at alarm) AND Lens 3 bear trigger.

The three pre-registered silent-failure mitigations apply: expanding-window
or absolute triggers only; per-episode outcomes reported next to pooled
statistics; current-vintage and publication-lag caveats carried in the
output notes. Python datetime months are 1-indexed; month arithmetic uses
dateutil.relativedelta only.
"""
from __future__ import annotations

from bisect import bisect_right
from datetime import date

from dateutil.relativedelta import relativedelta

from alarm_calibration import build_composite_grid, load_spx_month_ends, month_ends_from_daily
from lens1 import find_sustained_inversions, three_month_average_rise
from lens3 import rolling_mean
from sources.fred import fetch_series
from util import DATA_DIR, ROOT, clean_series, dump_json, load_json, utc_now_iso

HORIZONS = (3, 6, 12)


def median(values: list[float]) -> float:
    ordered = sorted(values)
    return ordered[len(ordered) // 2]


def build_signal_grid() -> tuple[list[dict], dict]:
    """Monthly point-in-time signal grid shared by phases 5 and 6.

    Returns (grid, meta): one dict per month-end with iso, close, and the
    four signal booleans; meta carries the alarm level and the first month
    the Lens 2 reconstruction is defined.
    """
    thresholds = load_json(DATA_DIR / "thresholds.json")
    alarm = thresholds["lens2_composite"]["alarm_share_pct"]
    yc_params = thresholds["yield_curve_10y3m"]
    labour_params = thresholds["labour_market"]
    sahm_trigger = thresholds["sahm_rule"]["elevated_level"]
    sma_params = thresholds["sma_trend_sp500"]

    print("Reconstructing Lens 2 composite (scrape-heavy)...")
    lens2_grid = {g["iso"]: g for g in build_composite_grid() if g["n"] >= 5}
    lens2_start = min(lens2_grid) if lens2_grid else None

    print("Fetching FRED histories for Lens 1 core...")
    yc_dates, yc_values = fetch_series("T10Y3M")
    yc_clean_d, yc_clean_v = clean_series(yc_dates, yc_values)
    yc_episodes = find_sustained_inversions(
        yc_dates, yc_values, yc_params["sustained_inversion_min_observations"]
    )
    sahm_d, sahm_v = clean_series(*fetch_series("SAHMREALTIME"))
    un_d, un_v = clean_series(*fetch_series("UNRATE"))
    pay_d, pay_v = clean_series(*fetch_series("PAYEMS"))

    # S&P grid and Lens 3 SMAs (backward-looking, so a single full-series
    # computation is point-in-time at every sampled month-end).
    import json as _json
    gspc = _json.loads((ROOT / "data" / "history" / "gspc.json").read_text(encoding="utf-8"))
    daily_dates, daily_closes = gspc["dates"], gspc["values"]
    sma50 = rolling_mean(daily_closes, 50)
    sma150 = rolling_mean(daily_closes, 150)
    month_ends = month_ends_from_daily(daily_dates)
    close_by = dict(zip(daily_dates, daily_closes))
    daily_index = {d: i for i, d in enumerate(daily_dates)}
    lookback = sma_params["slope_lookback_trading_days"]
    tolerance = sma_params["flat_tolerance_pct"]

    def lens3_bear(iso: str) -> bool | None:
        i = daily_index[iso]
        if i < 150 + lookback or sma150[i] is None or sma150[i - lookback] is None:
            return None
        s50, s150 = sma50[i], sma150[i]
        slope50 = (sma50[i] / sma50[i - lookback] - 1.0) * 100.0
        slope150 = (sma150[i] / sma150[i - lookback] - 1.0) * 100.0
        return s50 < s150 and slope50 <= tolerance and slope150 <= tolerance

    def latest_leq(dates: list[str], values: list[float], iso: str):
        i = bisect_right(dates, iso)
        return values[i - 1] if i else None

    def yc_elevated(iso: str) -> bool:
        spread = latest_leq(yc_clean_d, yc_clean_v, iso)
        if spread is None or spread < 0:
            return False
        t = date.fromisoformat(iso)
        for start, end in reversed(yc_episodes):
            end_d = date.fromisoformat(end)
            if end_d < t:
                # Month arithmetic via relativedelta (months are 1-indexed).
                return t <= end_d + relativedelta(months=+yc_params["elevated_window_months"])
        return False

    def labour_elevated(iso: str) -> bool:
        i_un = bisect_right(un_d, iso)
        i_pay = bisect_right(pay_d, iso)
        if i_un < 15 or i_pay < 4:
            return False
        rise = three_month_average_rise(un_v[:i_un])
        changes = [b - a for a, b in zip(pay_v[i_pay - 4:i_pay - 1], pay_v[i_pay - 3:i_pay])]
        payroll_3m = sum(changes) / len(changes)
        return rise >= labour_params["elevated_rise"] or payroll_3m < 0

    def lens1_core(iso: str) -> bool:
        sahm = latest_leq(sahm_d, sahm_v, iso)
        return (
            yc_elevated(iso)
            or (sahm is not None and sahm >= sahm_trigger)
            or labour_elevated(iso)
        )

    print("Evaluating signals on the monthly grid...")
    grid = []
    for iso in month_ends:
        l3 = lens3_bear(iso)
        if l3 is None:
            continue
        l1 = lens1_core(iso)
        l2 = lens2_grid[iso]["share"] >= alarm if iso in lens2_grid else False
        grid.append({
            "iso": iso,
            "close": close_by[iso],
            "lens1_core": l1,
            "lens2_alarm": l2,
            "lens3_bear": l3,
            "combined_act": (l1 or l2) and l3,
        })
    return grid, {"alarm_share_pct": alarm, "lens2_start": lens2_start}


def main() -> int:
    grid, meta = build_signal_grid()
    alarm = meta["alarm_share_pct"]
    lens2_start = meta["lens2_start"]
    closes = [g["close"] for g in grid]

    def forward(i: int, months: int):
        if i + months < len(closes):
            return (closes[i + months] / closes[i] - 1.0) * 100.0
        return None

    def worst12(i: int):
        outs = [closes[i + k] / closes[i] - 1.0 for k in range(1, 13) if i + k < len(closes)]
        return min(outs) * 100.0 if outs else None

    signal_defs = [
        ("lens1_core", "Lens 1 — recession core (reconstructed)",
         "Yield-curve window (from 1982), real-time Sahm, labour momentum. "
         "HY spreads, PMI, and LEI excluded — no free history."),
        ("lens2_alarm", f"Lens 2 — froth composite at the {alarm:g}% alarm",
         f"Five gauges from 1990, seven from 2007 (window starts {lens2_start}); the IPO "
         "gauge is not reconstructable, so historical shares understate live ones in "
         "deal-froth eras."),
        ("lens3_bear", "Lens 3 — trend bear trigger",
         "50-day below 150-day with both flat or falling, daily closes from 1970."),
        ("combined_act", "Combined act rule",
         "(Lens 1 core OR Lens 2 at alarm) AND Lens 3 confirms. Arms are treated as "
         "quiet before a series exists, which only removes historical signals, never "
         "adds them."),
    ]

    signals_out = []
    for key, name, note in signal_defs:
        rows = [(i, g) for i, g in enumerate(grid)]
        if key == "lens2_alarm" and lens2_start:
            rows = [(i, g) for i, g in rows if g["iso"] >= lens2_start]
        active = [(i, g) for i, g in rows if g[key]]

        horizons = {}
        for h in HORIZONS:
            cond = [r for i, g in active if (r := forward(i, h)) is not None]
            uncond = [r for i, g in rows if (r := forward(i, h)) is not None]
            if not uncond:
                continue
            horizons[f"{h}m"] = {
                "n": len(cond),
                "cond_median_pct": round(median(cond), 1) if cond else None,
                "cond_hit_pct": round(100.0 * sum(1 for r in cond if r > 0) / len(cond), 0) if cond else None,
                "uncond_median_pct": round(median(uncond), 1),
                "uncond_hit_pct": round(100.0 * sum(1 for r in uncond if r > 0) / len(uncond), 0),
            }

        episodes = []
        run = []
        for i, g in rows:
            if g[key]:
                run.append((i, g))
            elif run:
                episodes.append(run)
                run = []
        if run:
            episodes.append(run)
        episode_rows = []
        for ep in episodes:
            i0, g0 = ep[0]
            f12 = forward(i0, 12)
            w12 = worst12(i0)
            episode_rows.append({
                "start": g0["iso"],
                "end": ep[-1][1]["iso"],
                "months": len(ep),
                "fwd_12m_pct": round(f12, 1) if f12 is not None else None,
                "worst_12m_pct": round(w12, 1) if w12 is not None else None,
            })

        # Left-tail decomposition: a confirmation-based risk trigger earns its
        # keep by catching deep drawdowns, not by lifting the pooled median.
        # Count onsets that preceded a fall worse than 20% within 12 months,
        # and record the worst and best onset outcomes with their dates.
        scored = [e for e in episode_rows if e["fwd_12m_pct"] is not None]
        drawdown_onsets = [e for e in episode_rows
                           if e["worst_12m_pct"] is not None and e["worst_12m_pct"] <= -20.0]
        worst_ep = min(scored, key=lambda e: e["fwd_12m_pct"]) if scored else None
        best_ep = max(scored, key=lambda e: e["fwd_12m_pct"]) if scored else None
        tail = {
            "scored_onsets": len(scored),
            "deep_drawdown_onsets": len(drawdown_onsets),
            "deep_drawdown_starts": [e["start"] for e in drawdown_onsets],
            "worst_fwd_12m_pct": worst_ep["fwd_12m_pct"] if worst_ep else None,
            "worst_fwd_12m_start": worst_ep["start"] if worst_ep else None,
            "best_fwd_12m_pct": best_ep["fwd_12m_pct"] if best_ep else None,
            "best_fwd_12m_start": best_ep["start"] if best_ep else None,
        }

        signals_out.append({
            "id": key,
            "name": name,
            "availability_note": note,
            "sample_start": rows[0][1]["iso"],
            "sample_end": rows[-1][1]["iso"],
            "active_months": len(active),
            "episode_count": len(episodes),
            "horizons": horizons,
            "episodes": episode_rows,
            "tail": tail,
        })
        print(f"{name}: {len(active)} active months, {len(episodes)} episodes")

    payload = {
        "computed_as_of": utc_now_iso(),
        "method": (
            "Point-in-time monthly grid; expanding-window or absolute triggers only; "
            "conditional S&P 500 forward returns from month-end onset versus the "
            "unconditional base rate over each signal's own sample window. Episode "
            "counts are small and clustered — per-episode outcomes matter more than "
            "pooled statistics. Entry-point discipline: signals are studied from "
            "onset, not conditioned on prior strong runs."
        ),
        "signals": signals_out,
    }
    out = DATA_DIR / "forward_returns.json"
    dump_json(out, payload)
    print(f"wrote {out.relative_to(ROOT)} ({out.stat().st_size:,} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
